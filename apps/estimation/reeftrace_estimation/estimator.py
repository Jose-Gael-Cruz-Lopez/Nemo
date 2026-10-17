"""Conditional source match scores from one forward model and two evidence modes."""

from __future__ import annotations

import copy
import hashlib
import json
import math

import numpy as np
from scipy.special import logsumexp

from apps.transport.reeftrace_transport import Bounds, FlowField, simulate
from apps.transport.reeftrace_transport.geometry import points_in_polygon, polygon_array

MODEL_VERSION = "reeftrace-forward-1.0"
DEFAULT_GATES = {
    "position_sigma_cm": 0.7,
    "model_error_cm": 0.3,
    "correlation_time_s": 0.8,
    "min_absolute_fit": 0.02,
    "min_margin": 0.20,
    "min_likelihood_margin": 0.10,
    "min_observation_coverage": 1.0,
    "min_path_coverage": 0.90,
    "min_quality": 0.50,
    "min_trajectory_points": 3,
    "min_trajectory_duration_s": 0.5,
    "max_observation_points": 20,
}


def _hash(document: dict) -> str:
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _empty(profile: dict, observation: dict) -> dict:
    def text_or_none(value):
        return value if isinstance(value, str) else None

    frames = observation.get("evidence_frame_ids", [])
    return {
        "case_id": text_or_none(observation.get("case_id")),
        "calibration_id": text_or_none(profile.get("calibration_id")),
        "profile_id": text_or_none(profile.get("id")), "model_version": MODEL_VERSION,
        "config_hash": None, "inference_mode": None, "status": "invalid",
        "ranked_source": None, "leading_source": None, "compatible_sources": [],
        "relative_support": {}, "confidence_kind": "relative_support_not_probability",
        "absolute_fit": 0.0, "best_absolute_fit": 0.0,
        "margin": 0.0, "likelihood_margin": 0.0,
        "coverage": 0.0, "coverage_detail": {}, "reason_codes": [],
        "source_diagnostics": {}, "assumptions": {}, "sensitivity_results": [],
        "evidence_frame_ids": ([frame for frame in frames if isinstance(frame, str)]
                               if isinstance(frames, list) else []),
        "data_origin": text_or_none(profile.get("data_origin")) or "UNVERIFIED",
        "physical_validation": False,
    }


def _age_prior(transport: dict) -> tuple[np.ndarray, np.ndarray]:
    age = transport.get("age_prior", {"min_s": 0, "max_s": 30, "count": 16})
    if "values_s" in age:
        values = np.asarray(age["values_s"], dtype=float)
        weights = np.asarray(age.get("weights", np.ones(len(values))), dtype=float)
    else:
        if age.get("kind", "uniform") != "uniform":
            raise ValueError("Only uniform or explicitly discrete age priors are supported")
        low, high, count = float(age["min_s"]), float(age["max_s"]), int(age.get("count", 16))
        if (not 1 <= count <= 100 or count != age.get("count", 16)
                or not math.isfinite(low + high) or high < low):
            raise ValueError("Invalid age prior interval/count")
        values = (np.array([low]) if high == low else
                  low + (np.arange(count) + 0.5) * (high - low) / count)
        weights = np.ones(len(values))
    if (values.ndim != 1 or not 1 <= len(values) <= 100 or weights.shape != values.shape
            or not np.isfinite(values).all() or not np.isfinite(weights).all()
            or np.any(values < 0) or np.any(weights < 0) or not np.any(weights > 0)):
        raise ValueError("Age values and weights must be finite, nonnegative and nonempty")
    positive = weights > 0
    weights = np.exp(np.log(weights[positive]) - logsumexp(np.log(weights[positive])))
    if np.any(weights == 0):
        raise ValueError("Age-prior weight range exceeds supported floating-point resolution")
    return values[positive], weights


def _gates(profile: dict) -> dict:
    supplied = profile.get("gates", {})
    if set(supplied) - set(DEFAULT_GATES):
        raise ValueError("Unknown gate setting")
    result = {**DEFAULT_GATES, **supplied}
    if not np.isfinite(list(result.values())).all():
        raise ValueError("Gate values must be finite")
    if result["position_sigma_cm"] <= 0 or result["model_error_cm"] < 0:
        raise ValueError("Invalid position residual bandwidth")
    if result["correlation_time_s"] <= 0 or result["min_trajectory_duration_s"] < 0:
        raise ValueError("Invalid temporal settings")
    for name in ("min_absolute_fit", "min_margin", "min_likelihood_margin",
                 "min_observation_coverage", "min_path_coverage", "min_quality"):
        if not 0 <= result[name] <= 1:
            raise ValueError("Fractional gates must lie in [0,1]")
    for name in ("min_trajectory_points", "max_observation_points"):
        if int(result[name]) != result[name] or not 2 <= result[name] <= 100:
            raise ValueError("Invalid point-count gate")
    return result


def _observations(observation: dict, bounds: Bounds, gates: dict) -> tuple[str, np.ndarray,
                                                                               np.ndarray, np.ndarray]:
    points = [p for p in observation.get("points", []) if p.get("observed", True) is True]
    # History determines the mode, even after a tracked token stops moving.
    if len(points) >= 2:
        array = np.array([[p["t_s"], p["x_cm"], p["y_cm"], p.get("quality", 1.0)]
                          for p in points], dtype=float)
        if not np.isfinite(array).all() or np.any(np.diff(array[:, 0]) <= 0):
            raise ValueError("Measured trajectory times must be finite and strictly increasing")
        if np.any(array[:, 3] <= 0) or np.any(array[:, 3] > 1):
            raise ValueError("Measured point quality must lie in (0,1]")
        if not bounds.contains(array[:, 1:3]).all():
            raise ValueError("Observed trajectory is outside tank bounds")
        if len(array) > gates["max_observation_points"]:
            selected = np.unique(np.linspace(0, len(array) - 1,
                                             int(gates["max_observation_points"])).astype(int))
            array = array[selected]
        return "trajectory", array[:, 0] - array[0, 0], array[:, 1:3], array[:, 3]
    endpoint = observation.get("endpoint")
    if endpoint and endpoint.get("retained") is True:
        xy = np.array([[endpoint["x_cm"], endpoint["y_cm"]]], dtype=float)
        quality = np.array([endpoint.get("quality", 1.0)], dtype=float)
        if not np.isfinite(xy).all() or not bounds.contains(xy).all():
            raise ValueError("Retained endpoint is outside tank bounds")
        if not np.isfinite(quality).all() or np.any(quality <= 0) or np.any(quality > 1):
            raise ValueError("Endpoint quality must lie in (0,1]")
        return "retained_endpoint", np.array([0.0]), xy, quality
    return "insufficient", np.array([]), np.empty((0, 2)), np.array([])


def _score_source(ensemble, mode: str, times: np.ndarray, xy: np.ndarray,
                  quality: np.ndarray, ages: np.ndarray, age_weights: np.ndarray,
                  gates: dict) -> tuple[float, dict]:
    if mode == "trajectory":
        query = (ages[:, None] + times[None]).reshape(-1)
        predicted, _ = ensemble.at(query)
        predicted = predicted.reshape(len(ages), len(times), -1, 2).transpose(0, 2, 1, 3)
        residual = predicted - xy[None, None]
        correlation = np.exp(-np.abs(times[:, None] - times[None])
                             / gates["correlation_time_s"])
        covariance = (gates["position_sigma_cm"] ** 2 * correlation
                      / np.sqrt(quality[:, None] * quality[None]))
        # A shared mapping/model offset is not averaged away by a longer track.
        # The small independent component keeps the declared residual model SPD.
        covariance += gates["model_error_cm"] ** 2
        covariance += np.diag(0.05 * gates["position_sigma_cm"] ** 2 / quality)
        inverse = np.linalg.inv(covariance)
        quadratic = np.einsum("anid,ij,anjd->an", residual, inverse, residual)
        log_kernel = -0.5 * np.maximum(quadratic, 0)
        best_rmse = float(np.sqrt(np.sum(residual ** 2, axis=-1).mean(axis=-1).min()))
        retained_fraction = None
    else:
        predicted, retained = ensemble.at(ages)
        residual = predicted - xy[0]
        sigma2 = (gates["position_sigma_cm"] ** 2 / quality[0]
                  + gates["model_error_cm"] ** 2)
        log_kernel = np.where(retained, -0.5 * np.sum(residual ** 2, axis=-1) / sigma2,
                              -np.inf)
        best_rmse = (float(np.sqrt(np.sum(residual ** 2, axis=-1)[retained].min()))
                     if np.any(retained) else None)
        retained_fraction = float((retained.mean(axis=1) * age_weights).sum())
    log_likelihood = float(logsumexp(log_kernel + np.log(age_weights)[:, None])
                           - np.log(ensemble.positions_cm.shape[1]))
    # Per-coordinate Gaussian normalizers are common to sources and omitted.
    # Absolute fit uses a length-normalized kernel score, NOT a calibrated p-value.
    absolute_fit = float(np.exp(log_likelihood / max(1, len(times))))
    return log_likelihood, {
        "log_likelihood": log_likelihood if np.isfinite(log_likelihood) else None,
        "absolute_fit": absolute_fit, "best_path_rmse_cm": best_rmse,
        "path_coverage_fraction": float(ensemble.supported.mean()),
        "retained_fraction": retained_fraction, "dt_used_s": ensemble.dt_s,
        "particles": int(ensemble.positions_cm.shape[1]),
    }


def _estimate_once(profile: dict, observation: dict, seed: int) -> dict:
    result = _empty(profile, observation)
    result["config_hash"] = _hash(profile)
    frames = observation.get("evidence_frame_ids", [])
    if not isinstance(frames, list) or any(not isinstance(frame, str) for frame in frames):
        raise ValueError("evidence_frame_ids must be a list of strings")
    if profile.get("valid") is not True:
        result["reason_codes"] = ["CALIBRATION_INVALID"]
        return result
    if (observation.get("calibration_id") != profile.get("calibration_id")
            or not profile.get("calibration_id") or observation.get("stale", False)):
        result["reason_codes"] = ["CALIBRATION_INVALID"]
        return result
    if profile.get("token_class") and observation.get("token_class") != profile["token_class"]:
        result["reason_codes"] = ["UNSUPPORTED_TOKEN_CLASS"]
        return result
    gates = _gates(profile)
    bounds = Bounds.from_dict(profile["bounds"])
    field = FlowField(profile["flow"])
    mode, times, xy, quality = _observations(observation, bounds, gates)
    result["inference_mode"] = None if mode == "insufficient" else mode
    reasons = []
    if mode == "insufficient":
        result.update(status="unknown", reason_codes=["INSUFFICIENT_OBSERVATION"])
        return result
    if observation.get("association_valid", True) is not True:
        reasons.append("INSUFFICIENT_OBSERVATION")
    if (mode == "trajectory" and (len(times) < gates["min_trajectory_points"]
                                  or times[-1] < gates["min_trajectory_duration_s"])):
        reasons.append("INSUFFICIENT_OBSERVATION")
    if quality.mean() < gates["min_quality"]:
        reasons.append("LOW_OBSERVATION_QUALITY")
    observation_coverage = float(field.evaluate(xy)[1].mean())
    if observation_coverage < gates["min_observation_coverage"]:
        reasons.append("CALIBRATION_INVALID")
    sources = profile["sources"]
    if not 2 <= len(sources) <= 8:
        raise ValueError("Compare between two and eight declared candidate sources")
    ids = [str(source["id"]) for source in sources]
    if len(set(ids)) != len(ids):
        raise ValueError("Candidate source IDs must be unique")
    prior = np.array([source.get("prior", 1 / len(sources)) for source in sources], dtype=float)
    if not np.isfinite(prior).all() or np.any(prior <= 0):
        raise ValueError("Each explicit candidate prior must be finite and positive")
    prior = np.exp(np.log(prior) - logsumexp(np.log(prior)))
    if np.any(prior == 0):
        raise ValueError("Candidate-prior range exceeds supported floating-point resolution")
    traps = profile.get("traps", [])
    for trap in traps:
        polygon_array(trap["polygon_cm"], bounds)
    if mode == "retained_endpoint":
        supported_trap = any(trap.get("validated") is True
                             and points_in_polygon(xy, polygon_array(trap["polygon_cm"]))[0]
                             for trap in traps)
        if not supported_trap:
            reasons.append("RETENTION_UNSUPPORTED")
    if any(trap.get("validated") is not True for trap in traps):
        reasons.append("RETENTION_UNVALIDATED")
    transport = profile.get("transport", {})
    ages, age_weights = _age_prior(transport)
    duration = float(times[-1])
    horizon = float(ages.max() + duration)
    limit = float(transport.get("max_age_s", 60.0))
    if horizon > limit + 1e-9 or horizon > 180:
        raise ValueError("Declared release ages plus observation exceed the model horizon")
    horizon = max(horizon, float(transport.get("dt_s", 0.1)))
    particles = transport.get("particles_per_source", 500)
    if len(ages) * float(particles) * len(times) > 1_000_000:
        raise ValueError("Likelihood work budget exceeded; reduce ages, particles or observations")
    log_likelihoods = []
    for source_id, source in zip(ids, sources, strict=True):
        ensemble = simulate(
            profile["flow"], source["polygon_cm"], bounds=profile["bounds"], traps=traps,
            particles=particles,
            dt_s=transport.get("dt_s", 0.1), horizon_s=horizon,
            diffusivity_cm2_s=transport.get("diffusivity_cm2_s", 0.05),
            drift_bias_cm_s=transport.get("drift_bias_cm_s", [0.0, 0.0]), seed=seed,
        )
        log_likelihood, diagnostic = _score_source(ensemble, mode, times, xy, quality,
                                                 ages, age_weights, gates)
        log_likelihoods.append(log_likelihood)
        result["source_diagnostics"][source_id] = diagnostic
    log_likelihoods = np.array(log_likelihoods)
    if np.isfinite(log_likelihoods).any():
        support = np.exp(log_likelihoods + np.log(prior)
                         - logsumexp(log_likelihoods + np.log(prior)))
        likelihood_support = np.exp(log_likelihoods - logsumexp(log_likelihoods))
        order = np.argsort(-support, kind="stable")
        like_order = np.argsort(-likelihood_support, kind="stable")
        result["leading_source"] = ids[order[0]]
        result["margin"] = float(support[order[0]] - support[order[1]])
        result["likelihood_margin"] = float(likelihood_support[like_order[0]]
                                            - likelihood_support[like_order[1]])
        result["compatible_sources"] = [ids[i] for i in order
                                         if support[i] >= support[order[0]] * 0.25]
    else:
        support = np.zeros(len(sources))
    result["relative_support"] = dict(zip(ids, support.tolist(), strict=True))
    result["best_absolute_fit"] = max(d["absolute_fit"] for d in result["source_diagnostics"].values())
    if result["leading_source"] is not None:
        result["absolute_fit"] = result["source_diagnostics"][result["leading_source"]]["absolute_fit"]
    path_coverage = min(d["path_coverage_fraction"] for d in result["source_diagnostics"].values())
    result["coverage"] = min(observation_coverage, path_coverage)
    result["coverage_detail"] = {
        "observation_fraction": observation_coverage,
        "minimum_candidate_path_fraction": path_coverage,
        "flow_grid_fraction": profile["flow"].get("diagnostics", {}).get("grid_coverage_fraction"),
    }
    if path_coverage < gates["min_path_coverage"]:
        reasons.append("CALIBRATION_INVALID")
    if result["absolute_fit"] < gates["min_absolute_fit"] or not np.isfinite(log_likelihoods).any():
        reasons.append("MODEL_MISMATCH")
    if (result["margin"] < gates["min_margin"]
            or result["likelihood_margin"] < gates["min_likelihood_margin"]):
        reasons.append("AMBIGUOUS_SOURCES")
    result["assumptions"] = {
        "world_units": "cm", "time_units": "s", "velocity_units": "cm/s",
        "diffusivity_units": "cm^2/s", "boundary": "reflecting_rectangle",
        "retention": "absorbing_only_when_validated",
        "candidate_priors": dict(zip(ids, prior.tolist(), strict=True)),
        "release_age_values_s": ages.tolist(), "release_age_weights": age_weights.tolist(),
        "age_reference": "age_at_first_observed_point" if mode == "trajectory" else "age_at_endpoint_observation",
        "position_sigma_cm": gates["position_sigma_cm"],
        "model_error_cm": gates["model_error_cm"],
        "correlation_time_s": gates["correlation_time_s"],
        "observation_points_used": len(xy), "seed": int(seed),
        "absolute_fit_kind": "length_normalized_mean_position_kernel_not_p_value",
        "scope": "declared_tank_candidates_only_not_geographic_origin",
    }
    result["reason_codes"] = list(dict.fromkeys(reasons))
    result["status"] = "unknown" if reasons else "ranked"
    result["ranked_source"] = result["leading_source"] if not reasons else None
    return result


def estimate(profile: dict, observation: dict, *, seed: int = 7) -> dict:
    """JSON boundary: return finite conditional match scores, or explicit invalid/Unknown.

    Optional profile.sensitivity_variants are predeclared {id,transport:{...}} entries.
    They may override only diffusivity, drift bias, age prior and dt, never fit outcomes.
    """
    if not isinstance(profile, dict) or not isinstance(observation, dict):
        result = _empty({}, {})
        result.update(reason_codes=["INVALID_INPUT"], error="Profile and observation must be JSON objects")
        return result
    try:
        baseline = _estimate_once(profile, observation, seed)
        original_status = baseline["status"]
        variants = profile.get("sensitivity_variants", [])
        if len(variants) > 8:
            raise ValueError("At most eight predeclared sensitivity variants")
        for variant in variants:
            if set(variant) != {"id", "transport"}:
                raise ValueError("Sensitivity variants require exactly id and transport")
            if set(variant["transport"]) - {"diffusivity_cm2_s", "drift_bias_cm_s", "age_prior", "dt_s"}:
                raise ValueError("Unsupported sensitivity override")
            changed = copy.deepcopy(profile)
            changed.pop("sensitivity_variants", None)
            changed["transport"] = {**changed.get("transport", {}), **variant["transport"]}
            alternative = _estimate_once(changed, observation, seed)
            baseline["sensitivity_results"].append({
                "id": str(variant["id"]), "config_hash": alternative["config_hash"],
                "status": alternative["status"], "leading_source": alternative["leading_source"],
                "relative_support": alternative["relative_support"],
                "absolute_fit": alternative["absolute_fit"],
                "reason_codes": alternative["reason_codes"],
            })
            if (alternative["leading_source"] != baseline["leading_source"]
                    or alternative["status"] != original_status):
                if "ASSUMPTION_SENSITIVE" not in baseline["reason_codes"]:
                    baseline["reason_codes"].append("ASSUMPTION_SENSITIVE")
                if baseline["status"] != "invalid":
                    baseline["status"], baseline["ranked_source"] = "unknown", None
        # No NaN/Infinity can enter the API/store even for a tiny likelihood.
        json.dumps(baseline, allow_nan=False)
        return baseline
    except (ValueError, KeyError, TypeError, AttributeError, IndexError, OverflowError,
            np.linalg.LinAlgError) as error:
        result = _empty(profile, observation)
        result["reason_codes"] = ["INVALID_INPUT"]
        result["error"] = str(error)
        return result
