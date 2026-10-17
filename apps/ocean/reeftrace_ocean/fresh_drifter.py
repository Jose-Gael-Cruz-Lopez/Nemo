"""Frozen new-GDP-ID evaluation with known-alias exclusions; no automatic promotion.

Acquisition and evaluation are separate. The public reader never makes a first
score: before a frozen report exists it returns explicit unscored coverage.
"""

from __future__ import annotations

import csv
import io
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from .ablation import mean_drift_forecast
from .benchmark import EARTH_MEAN_RADIUS_M, SphericalLocalFrame, _forecast, great_circle_distance_m
from .fresh_drifter_protocol import (
    DIRECTORY,
    LABELS,
    MODEL_IDS,
    PROTOCOL_SHA256,
    ROOT,
    derive_groups,
    load_design,
    pinned_json,
    raw_receipt,
    read_bytes,
    save_json,
    sha,
)
from .kalman import _fit_and_forecast

STUDY_ID = "noaa-fresh-gdp-id-study-v2"
DESIGN_STATUS = "FROZEN_NEW_GDP_ID_GROUP_EVALUATION_WITH_KNOWN_ALIAS_EXCLUSIONS"
CHI2 = {"nominal50": -2 * math.log(0.5), "nominal90": -2 * math.log(0.1)}
IMPLEMENTATION_PATHS = (
    "apps/ocean/reeftrace_ocean/fresh_drifter.py",
    "apps/ocean/reeftrace_ocean/fresh_drifter_protocol.py",
    "scripts/fetch_fresh_drifter_study.py",
)


def _time(t):
    return t.isoformat().replace("+00:00", "Z")


def _when(text):
    t = datetime.fromisoformat(text)
    if t.utcoffset() != timedelta(0):
        raise ValueError("Fresh-study timestamps require UTC")
    return t


def _raw(directory, receipt):
    data = raw_receipt(directory, receipt)
    if data is not None and read_bytes(
        (Path(directory) / receipt["raw_path"]).with_suffix(".sha256"), 80
    ).decode().strip() != sha(data):
        raise ValueError("Fresh-study raw detached receipt changed")
    if _when(receipt["finished_at_utc"]) < _when(receipt["started_at_utc"]):
        raise ValueError("Acquisition timestamps reversed")
    return data


def _inputs(directory):
    p, e, hashes = load_design(directory)
    if not (Path(directory) / "manifest.json").exists():
        return p, e, hashes, None, None, {}
    s, h = pinned_json(directory, "selection")
    hashes["selection_sha256"] = h
    m, h = pinned_json(directory, "manifest")
    hashes["manifest_sha256"] = h
    if (
        s["study_id"] != STUDY_ID
        or m["study_id"] != STUDY_ID
        or s["protocol_sha256"] != PROTOCOL_SHA256
        or m["protocol_sha256"] != PROTOCOL_SHA256
        or m["selection_sha256"] != hashes["selection_sha256"]
        or s["trajectory_payloads_fetched"] is not False
        or s["evaluation_outcomes_computed"] is not False
        or m["evaluation_outcomes_computed"] is not False
        or m["no_replacements"] is not True
    ):
        raise ValueError("Fresh-study selection/acquisition lineage changed")
    if (
        m["requests_attempted"] > p["budgets"]["requests_max"]
        or m["response_bytes_received"] > p["budgets"]["total_bytes"] + 8192
    ):
        raise ValueError("Fresh-study acquisition exceeded frozen request/response budget")
    sources = {}
    for receipt in m["source_receipts"]:
        if receipt["role"] in sources:
            raise ValueError("Duplicate acquisition role")
        sources[receipt["role"]] = (_raw(directory, receipt), receipt)
    if s["source_receipts"] != m["source_receipts"][: len(s["source_receipts"])]:
        raise ValueError("Selection metadata receipts changed after acquisition")
    identity = sources.get("identity_aliases")
    if identity is not None:
        ir, ih = pinned_json(directory, "identity-receipt")
        hashes["identity_receipt_sha256"] = ih
        if (
            ir["receipt"] != identity[1]
            or ir["protocol_sha256"] != PROTOCOL_SHA256
            or ir["saved_before_block_metadata"] is not True
        ):
            raise ValueError("Global alias preselection receipt changed")
    if identity is not None and identity[1]["status"] == "DOWNLOADED":
        snapshots = {
            b["id"]: sources["block:" + b["id"]][0]
            for b in p["selection"]["blocks"]
            if "block:" + b["id"] in sources
            and sources["block:" + b["id"]][1]["status"] == "DOWNLOADED"
        }
        groups, blocks, aliases = derive_groups(p, e, identity[0], snapshots)
        if (groups, blocks, aliases) != (s["groups"], s["blocks"], s["aliases"]):
            raise ValueError("Selection no longer matches raw metadata/exclusion/alias rule")
    elif s["groups"]:
        raise ValueError("No trajectory selection is valid without alias metadata")
    elif identity is not None and identity[1]["status"] == "METADATA_INVALID":
        from .fresh_drifter_protocol import alias_maps

        try:
            alias_maps(identity[0])
        except ValueError:
            pass
        else:
            raise ValueError("Invalid-identity failure does not match actual raw metadata")
    if len(s["groups"]) > 6 or len(m["trajectories"]) != len(s["groups"]):
        raise ValueError("Acquisition group count changed")
    for g, t in zip(s["groups"], m["trajectories"], strict=True):
        if any(t[k] != v for k, v in g.items()) or sources.get(
            "trajectory:" + g["drifter_id"], (None, None)
        )[1] != {k: v for k, v in t.items() if k not in g}:
            raise ValueError("Acquired trajectory differs from frozen selection/receipt")
        if _when(t["started_at_utc"]) < _when(s["frozen_at_utc"]):
            raise ValueError("Trajectory request preceded immutable selection")
    return p, e, hashes, s, m, sources


def _flags(acquired=False, attempted=False, evaluated=False, aliases=False):
    return {
        "physical_validation": False,
        "calibrated_probability": False,
        "automatic_model_promotion": False,
        "operational_causality": False,
        "statistical_independence": False,
        "physical_alias_resolution_verified": aliases,
        "provider_calls": False,
        "camera_started": False,
        "store_written": False,
        "global_training": False,
        "heldout_tuning": False,
        "acquisition_attempted": attempted,
        "new_acquisition": acquired,
        "new_gdp_id_group_evaluation": evaluated,
    }


def _empty_prediction(block, h, status="UNFILLED", reasons=None):
    t = _when(block["start_utc"]) + timedelta(hours=17 + h)
    return {
        "horizon_hours": h,
        "time_utc": _time(t),
        "status": status,
        "reason_codes": reasons or ["UNSELECTED_TARGET_SLOT"],
        **dict.fromkeys(
            (
                "latitude_deg",
                "longitude_deg",
                "x_m",
                "y_m",
                "position_error_m",
                "observed_velocity_m_s",
                "predicted_velocity_m_s",
                "residual_velocity_m_s",
                "position_covariance_m2",
                "observation_covariance_m2",
                "ellipse_hits",
            )
        ),
    }


def _base(p, e, hashes, selection, manifest):
    selected = selection["groups"] if selection else []
    downloaded = (
        sum(t["status"] == "DOWNLOADED" for t in manifest["trajectories"]) if manifest else 0
    )
    groups = []
    for block in p["selection"]["blocks"]:
        for slot in (1, 2):
            g = next(
                (g for g in selected if g["block_id"] == block["id"] and g["slot"] == slot), None
            )
            reasons = ["EVALUATION_NOT_FROZEN"] if g else ["UNSELECTED_TARGET_SLOT"]
            status = "FAILED" if g else "UNFILLED"
            groups.append(
                {
                    "block_id": block["id"],
                    "slot": slot,
                    "drifter_id": g["drifter_id"] if g else None,
                    "wmo": g["wmo"] if g else None,
                    "status": status,
                    "reason_codes": reasons,
                    "coordinate_system": None,
                    "training_track": [],
                    "heldout_track": [],
                    "models": [
                        {
                            "id": i,
                            "label": LABELS[i],
                            "status": status,
                            "reason_codes": reasons,
                            "forecast_anchor": None,
                            "parameters": {},
                            "predictions": [
                                _empty_prediction(block, h, status, reasons) for h in range(1, 7)
                            ],
                            "metrics": None,
                        }
                        for i in MODEL_IDS
                    ],
                }
            )
    aliases = (
        selection["aliases"]
        if selection
        else {
            "reserved_gdp_id_count": len(e["reserved_gdp_ids"]),
            "known_reserved_wmo_count": 0,
            "unresolved_reserved_alias_ids": e["reserved_gdp_ids"],
            "unresolved_reserved_alias_count": len(e["reserved_gdp_ids"]),
            "physical_alias_resolution_verified": False,
            "statistical_independence": False,
        }
    )
    full_hashes = dict.fromkeys(
        (
            "protocol_sha256",
            "exclusions_sha256",
            "selection_sha256",
            "manifest_sha256",
            "identity_receipt_sha256",
            "implementation_receipt_sha256",
            "forecast_receipt_sha256",
            "reference_report_sha256",
        )
    )
    full_hashes.update(hashes)
    return {
        "schema_version": 1,
        "kind": "FRESH_NOAA_DRIFTER_STUDY",
        "study_id": STUDY_ID,
        "report_id": STUDY_ID,
        "status": "NOT_ACQUIRED"
        if manifest is None
        else "ACQUISITION_BLOCKED"
        if not downloaded
        else "PARTIAL_COVERAGE",
        "design_status": DESIGN_STATUS,
        "data_origin": "REAL_HISTORICAL_NOAA_GDP_NEW_ID_GROUPS"
        if downloaded
        else "NO_NEW_TRAJECTORY_DATA",
        "protocol_sha256": PROTOCOL_SHA256,
        "protocol": p,
        "coverage": {
            "target_groups": 6,
            "selected_groups": len(selected),
            "downloaded_groups": downloaded,
            "scored_groups": 0,
            "models": 5,
            "horizons": 6,
            "planned_outcomes": 180,
            "attempted_outcomes": len(selected) * 30,
            "scored_outcomes": 0,
            "failed_outcomes": len(selected) * 30,
            "unfilled_outcomes": (6 - len(selected)) * 30,
            "unique_observed_intervals": 0,
            "unique_observed_positions": 0,
            "common_target_cohort_complete": False,
        },
        "groups": groups,
        "models": [
            {
                "id": i,
                "label": LABELS[i],
                "complete_groups": 0,
                "metrics": None,
                "reason_codes": ["INCOMPLETE_TARGET_COHORT"],
            }
            for i in MODEL_IDS
        ],
        "uncertainty": {
            "kind": "UNCALIBRATED_OBSERVATION_PREDICTIVE_ELLIPSE_HITS",
            "comparison_covariance": "position_covariance_plus_assumed_R",
            "chi2_thresholds": CHI2,
            "per_drifter": [],
        },
        "provenance": {
            "integrity_verified": True,
            "hashes": full_hashes,
            "provider": "NOAA AOML Global Drifter Program",
            "source_receipts": manifest["source_receipts"] if manifest else [],
            "aliases": aliases,
            "excluded_gdp_id_count": len(e["reserved_gdp_ids"]),
            "reserved_gdp_ids": e["reserved_gdp_ids"],
            "acquisition_timestamps": {
                "started_at_utc": manifest["started_at_utc"] if manifest else None,
                "finished_at_utc": manifest["finished_at_utc"] if manifest else None,
            },
        },
        "flags": _flags(
            downloaded > 0,
            manifest is not None,
            False,
            aliases["physical_alias_resolution_verified"],
        ),
        "replay": {"verified_numeric_replay": False, "reference_report_sha256": None},
        "limitations": [
            "New previously unscored canonical GDP-ID groups with known-alias exclusions, not proven physically or statistically independent.",
            "All existing exposed fixture IDs are excluded; no cross-ID/shared training or held-out tuning is performed.",
            "18 prefix positions are permitted observation context for each fixed algorithm, not evaluation labels for shared fitting.",
            "NOAA hourly positions are QC/interpolated historical estimates; upstream raw-fix causality is not established.",
            "Assumed Kalman noise and ellipse spread are uncalibrated; no source probability or physical benefit follows.",
            "No matched current forcing, observed plastic labels, source/prevention mutation, camera access or provider calls.",
        ],
    }


@dataclass(frozen=True)
class _Record:
    drifter_id: str
    time_utc: datetime
    raw_lat: str
    raw_lon: str

    @property
    def latitude_deg(self):
        value = float(self.raw_lat)
        if not math.isfinite(value) or not -90 <= value <= 90:
            raise ValueError("Unavailable latitude")
        return value

    @property
    def longitude_deg(self):
        value = float(self.raw_lon)
        if not math.isfinite(value) or not -180 <= value <= 180:
            raise ValueError("Unavailable longitude")
        return value


def _records(raw, g, p):
    rows = list(csv.reader(io.StringIO(raw.decode())))
    if (
        len(rows) != 26
        or rows[0] != p["preprocessing"]["csv_columns"]
        or rows[1] != p["preprocessing"]["units"]
    ):
        raise ValueError("Trajectory requires exact frozen 24-row schema/units")
    result = []
    for index, row in enumerate(rows[2:]):
        if (
            len(row) != 8
            or row[0] != g["drifter_id"]
            or _when(row[1]) != _when(g["start_utc"]) + timedelta(hours=index)
        ):
            raise ValueError("Trajectory ID/hourly UTC window changed")
        result.append(_Record(row[0], _when(row[1]), row[2], row[3]))
    return result


def _xy(frame, record, limited=True):
    lat, lon = record.latitude_deg, record.longitude_deg
    if limited:
        return frame.to_xy(lat, lon)
    lat0, lon0, a, b = map(math.radians, (frame.latitude_deg, frame.longitude_deg, lat, lon))
    dl = math.atan2(math.sin(b - lon0), math.cos(b - lon0))
    east = math.cos(a) * math.sin(dl)
    north = math.cos(lat0) * math.sin(a) - math.sin(lat0) * math.cos(a) * math.cos(dl)
    dot = math.sin(lat0) * math.sin(a) + math.cos(lat0) * math.cos(a) * math.cos(dl)
    norm = math.hypot(east, north)
    angle = math.atan2(norm, dot)
    if angle * EARTH_MEAN_RADIUS_M < 1e-9:
        return np.zeros(2)
    if norm < 1e-15:
        raise ValueError("Antipodal truth vector is undefined")
    return np.array([east, north]) * (angle * EARTH_MEAN_RADIUS_M / norm)


def _point(record, frame, limited=True):
    xy = _xy(frame, record, limited)
    return {
        "time_utc": _time(record.time_utc),
        "latitude_deg": record.latitude_deg,
        "longitude_deg": record.longitude_deg,
        "x_m": float(xy[0]),
        "y_m": float(xy[1]),
    }


def _one_forecast(model, xy, times, future):
    covariance = None
    anchor = xy[-1].copy()
    if model == "kalman_cv":
        positions, covariance, state, _ = _fit_and_forecast(times, xy, future)
        anchor = state[:2]
        params = {
            "forecast_start": "FILTERED_LAST_TRAINING_STATE",
            "position_std_m": 100.0,
            "acceleration_spectral_density_m2_s3": 1e-6,
            "noise_parameter_fitting_performed": False,
        }
    elif model == "mean_drift":
        positions = mean_drift_forecast(xy, 6, 3600)
        params = {"learned_parameters": 2, "forecast_start": "RAW_LAST_TRAINING_POSITION"}
    else:
        positions, params = _forecast(xy, 6, 3600, model)
        params = {**params, "forecast_start": "RAW_LAST_TRAINING_POSITION"}
    return positions, covariance, anchor, params


def _prepare(p, selection, manifest, sources):
    """Every model track is built before accessing any future coordinate property."""
    prepared = {}
    for g, t in zip(selection["groups"], manifest["trajectories"], strict=True):
        state = {"group": g, "records": None, "frame": None, "training_track": [], "models": {}}
        try:
            if t["status"] != "DOWNLOADED":
                raise ValueError("Trajectory not downloaded")
            records = _records(sources["trajectory:" + g["drifter_id"]][0], g, p)
            state["records"] = records
            frame = SphericalLocalFrame(records[0].latitude_deg, records[0].longitude_deg)
            state["frame"] = frame
            state["training_track"] = [_point(r, frame) for r in records[:18]]
            xy = np.array([[r["x_m"], r["y_m"]] for r in state["training_track"]])
            times = np.array(
                [(r.time_utc - records[0].time_utc).total_seconds() for r in records[:18]]
            )
            future = np.array(
                [(r.time_utc - records[0].time_utc).total_seconds() for r in records[18:]]
            )
        except (ValueError, UnicodeError, TypeError, OverflowError):
            xy = None
        for model in MODEL_IDS:
            try:
                if xy is None:
                    raise ValueError("Unavailable prefix")
                means, covs, anchor, params = _one_forecast(model, xy, times, future)
                if np.asarray(means).shape != (6, 2):
                    raise ValueError("Incomplete model track")
                predictions = []
                for index, point in enumerate(means):
                    lat, lon = frame.to_latlon(point)
                    predictions.append(
                        {
                            "horizon_hours": index + 1,
                            "time_utc": _time(records[18 + index].time_utc),
                            "latitude_deg": lat,
                            "longitude_deg": lon,
                            "x_m": float(point[0]),
                            "y_m": float(point[1]),
                            "position_covariance_m2": None
                            if covs is None
                            else covs[index].tolist(),
                            "observation_covariance_m2": None
                            if covs is None
                            else (covs[index] + 10000 * np.eye(2)).tolist(),
                        }
                    )
                result = {
                    "predictions": predictions,
                    "parameters": params,
                    "forecast_anchor": {
                        "x_m": float(anchor[0]),
                        "y_m": float(anchor[1]),
                        "time_utc": _time(records[17].time_utc),
                    },
                    "reason_codes": [],
                }
                json.dumps(result, allow_nan=False)
                state["models"][model] = result
            except (
                ValueError,
                TypeError,
                OverflowError,
                FloatingPointError,
                np.linalg.LinAlgError,
            ):
                state["models"][model] = {
                    "predictions": None,
                    "parameters": {},
                    "forecast_anchor": None,
                    "reason_codes": ["UNAVAILABLE_PREFIX_OR_MODEL_FORECAST"],
                }
        prepared[g["drifter_id"]] = state
    return prepared


def _forecast_payload(prepared):
    return {
        identifier: {"group": s["group"], "models": s["models"]}
        for identifier, s in prepared.items()
    }


def _score(base, prepared):
    """Read later truth after the receipt; never bridge or hide missing hours."""
    scored = 0
    observed_intervals = 0
    observed_positions = 0
    for group in base["groups"]:
        if group["drifter_id"] is None:
            continue
        state = prepared[group["drifter_id"]]
        records = state["records"]
        frame = state["frame"]
        group["training_track"] = state["training_track"]
        if frame is not None:
            group["coordinate_system"] = {
                "origin_latitude_deg": frame.latitude_deg,
                "origin_longitude_deg": frame.longitude_deg,
                "projection": "spherical_azimuthal_equidistant",
                "position_units": "m",
                "velocity_units": "m/s",
            }
        truth = []
        for record in records[18:] if records else []:
            try:
                point = _point(record, frame, False) if frame else None
            except (ValueError, OverflowError):
                point = None
            truth.append(point)
        group["heldout_track"] = [
            (
                {**point, "status": "OBSERVED", "reason_codes": []}
                if point is not None
                else {
                    "time_utc": _time(records[18 + i].time_utc),
                    "latitude_deg": None,
                    "longitude_deg": None,
                    "x_m": None,
                    "y_m": None,
                    "status": "UNAVAILABLE",
                    "reason_codes": ["HELDOUT_TRUTH_UNAVAILABLE"],
                }
            )
            for i, point in enumerate(truth)
        ]
        previous_valid = bool(state["training_track"])
        for point in truth:
            observed_positions += point is not None
            observed_intervals += previous_valid and point is not None
            previous_valid = point is not None
        full_truth = len(truth) == 6 and all(point is not None for point in truth)
        for model in group["models"]:
            fixed = state["models"][model["id"]]
            model.update(parameters=fixed["parameters"], forecast_anchor=fixed["forecast_anchor"])
            errors = []
            velocity = []
            hits = []
            can_score = (
                full_truth and fixed["predictions"] is not None and bool(state["training_track"])
            )
            reasons = fixed["reason_codes"] or ["HELDOUT_TRUTH_INCOMPLETE_WHOLE_TRACK_WITHHELD"]
            if can_score:
                prev_p = np.array([fixed["forecast_anchor"][k] for k in ("x_m", "y_m")])
                prev_o = np.array([state["training_track"][-1][k] for k in ("x_m", "y_m")])
                previous_time = _when(state["training_track"][-1]["time_utc"])
            for index, row in enumerate(model["predictions"]):
                row.update(status="FAILED", reason_codes=reasons)
                if not can_score:
                    continue
                actual = truth[index]
                predicted = fixed["predictions"][index]
                error = great_circle_distance_m(
                    (predicted["latitude_deg"], predicted["longitude_deg"]),
                    (actual["latitude_deg"], actual["longitude_deg"]),
                )
                actual_xy = np.array([actual[k] for k in ("x_m", "y_m")])
                pred_xy = np.array([predicted[k] for k in ("x_m", "y_m")])
                now = _when(actual["time_utc"])
                dt = (now - previous_time).total_seconds()
                observed = (actual_xy - prev_o) / dt
                predicted_v = (pred_xy - prev_p) / dt
                residual = predicted_v - observed
                ellipse = None
                if predicted["observation_covariance_m2"] is not None:
                    delta = pred_xy - actual_xy
                    squared = float(
                        delta @ np.linalg.solve(predicted["observation_covariance_m2"], delta)
                    )
                    if not math.isfinite(squared) or squared < -1e-8:
                        raise ValueError("Invalid observation ellipse score")
                    ellipse = {k: squared <= value for k, value in CHI2.items()}
                    hits.append(ellipse)
                row.update(
                    **predicted,
                    status="SCORED",
                    reason_codes=[],
                    position_error_m=error,
                    observed_velocity_m_s=observed.tolist(),
                    predicted_velocity_m_s=predicted_v.tolist(),
                    residual_velocity_m_s=residual.tolist(),
                    ellipse_hits=ellipse,
                )
                errors.append(error)
                velocity.append(float(residual @ residual))
                scored += 1
                prev_o, prev_p, previous_time = actual_xy, pred_xy, now
            complete = len(errors) == 6
            model.update(
                status="SCORED" if complete else "FAILED",
                reason_codes=[] if complete else ["INCOMPLETE_MODEL_TRACK"],
                metrics={
                    "ade_m": float(np.mean(errors)),
                    "fde_m": errors[-1],
                    "vector_rmse_m_s": math.sqrt(float(np.mean(velocity))),
                }
                if complete
                else None,
            )
            if model["id"] == "kalman_cv":
                base["uncertainty"]["per_drifter"].append(
                    {
                        "drifter_id": group["drifter_id"],
                        "scored_count": len(hits),
                        **{
                            k + "_hit_count": sum(h[k] for h in hits) if hits else None
                            for k in CHI2
                        },
                        **{
                            k + "_hit_fraction": sum(h[k] for h in hits) / len(hits)
                            if hits
                            else None
                            for k in CHI2
                        },
                    }
                )
        complete = all(model["status"] == "SCORED" for model in group["models"])
        group.update(
            status="SCORED" if complete else "FAILED",
            reason_codes=[] if complete else ["INCOMPLETE_GROUP"],
        )
    coverage = base["coverage"]
    coverage.update(
        scored_outcomes=scored,
        failed_outcomes=coverage["attempted_outcomes"] - scored,
        scored_groups=sum(g["status"] == "SCORED" for g in base["groups"]),
        unique_observed_intervals=observed_intervals,
        unique_observed_positions=observed_positions,
        common_target_cohort_complete=scored == 180,
    )
    for model in base["models"]:
        tracks = [next(m for m in g["models"] if m["id"] == model["id"]) for g in base["groups"]]
        model["complete_groups"] = sum(m["status"] == "SCORED" for m in tracks)
        if scored == 180:
            model.update(
                metrics={
                    "ade_m": float(np.mean([m["metrics"]["ade_m"] for m in tracks])),
                    "fde_m": float(np.mean([m["metrics"]["fde_m"] for m in tracks])),
                    "vector_rmse_m_s": math.sqrt(
                        float(np.mean([m["metrics"]["vector_rmse_m_s"] ** 2 for m in tracks]))
                    ),
                },
                reason_codes=[],
            )
    if scored == 180:
        base["status"] = "COMPLETED"
    elif base["coverage"]["downloaded_groups"]:
        base["status"] = "PARTIAL_COVERAGE"
    base["flags"]["new_gdp_id_group_evaluation"] = scored > 0
    json.dumps(base, allow_nan=False)
    return base


def _verify_implementation(directory):
    receipt, h = pinned_json(directory, "implementation-receipt")
    if (
        receipt["protocol_sha256"] != PROTOCOL_SHA256
        or receipt["evaluation_outcomes_computed"] is not False
        or set(receipt["implementation_sha256"]) != set(IMPLEMENTATION_PATHS)
    ):
        raise ValueError("Fresh-study evaluator freeze changed")
    for path, expected in receipt["implementation_sha256"].items():
        if sha(read_bytes(ROOT / path)) != expected:
            raise ValueError("Fresh-study implementation changed after score freeze")
    return receipt, h


def _same(actual, expected):
    if type(actual) is not type(expected):
        raise ValueError("Fresh replay reference type changed")
    if isinstance(expected, float):
        if not math.isfinite(actual) or not math.isclose(
            actual, expected, rel_tol=1e-10, abs_tol=1e-8
        ):
            raise ValueError("Fresh replay reference metric changed")
    elif isinstance(expected, dict):
        if actual.keys() != expected.keys():
            raise ValueError("Fresh replay reference fields changed")
        for k in expected:
            _same(actual[k], expected[k])
    elif isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError("Fresh replay denominator changed")
        for a, b in zip(actual, expected, strict=True):
            _same(a, b)
    elif actual != expected:
        raise ValueError("Fresh replay identity/status changed")


def _evaluated(directory, p, e, hashes, s, m, sources, *, first=False):
    _receipt, h = _verify_implementation(directory)
    hashes["implementation_receipt_sha256"] = h
    prepared = _prepare(p, s, m, sources)
    forecasts = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "protocol_sha256": PROTOCOL_SHA256,
        "implementation_receipt_sha256": h,
        "manifest_sha256": hashes["manifest_sha256"],
        "future_coordinates_accessed": False,
        "declared_model_tracks": 30,
        "selected_model_tracks": len(prepared) * 5,
        "unfilled_model_tracks": (6 - len(prepared)) * 5,
        "forecast_tracks": _forecast_payload(prepared),
    }
    if first:
        forecasts["frozen_at_utc"] = datetime.now(UTC).isoformat()
        h = save_json(Path(directory) / "forecast-receipt.json", forecasts)
    else:
        old, h = pinned_json(directory, "forecast-receipt")
        forecasts["frozen_at_utc"] = old["frozen_at_utc"]
        _same(forecasts, old)
    hashes["forecast_receipt_sha256"] = h
    return _score(_base(p, e, hashes, s, m), prepared)


def freeze_first_report(directory=DIRECTORY):
    """Explicit CLI-only first scoring after tests/implementation receipt freeze."""
    directory = Path(directory)
    if (directory / "report.json").exists() or (directory / "forecast-receipt.json").exists():
        raise ValueError("Never overwrite a scored fresh study")
    p, e, hashes, s, m, sources = _inputs(directory)
    if m is None:
        raise ValueError("Acquisition has not been attempted")
    report = _evaluated(directory, p, e, hashes, s, m, sources, first=True)
    save_json(directory / "report.json", report)
    return report


def run_fresh_drifter_study(directory=DIRECTORY):
    """Offline read-only verified replay; never silently executes a first score."""
    directory = Path(directory)
    p, e, hashes, s, m, sources = _inputs(directory)
    if not (directory / "report.json").exists():
        return _base(p, e, hashes, s, m)
    actual = _evaluated(directory, p, e, hashes, s, m, sources)
    reference, h = pinned_json(directory, "report")
    _same(actual, reference)
    actual["provenance"]["hashes"]["reference_report_sha256"] = h
    actual["replay"] = {"verified_numeric_replay": True, "reference_report_sha256": h}
    return actual
