"""Seeded forward ensembles, explicit unsupported cells, and two evidence likelihoods."""

import hashlib
import itertools
import json
import math
import time

import cv2
import numpy as np

from .baselines import compare
from .contracts import CaseInput, ModelConfig, Profile

MODEL_VERSION = "forward-ensemble-v3"
PRESETS = {"age_short_v1": (0, 30), "age_wide_v1": (0, 60)}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def inside(point, polygon):
    return (
        cv2.pointPolygonTest(np.asarray(polygon, np.float32), tuple(map(float, point)), False) >= 0
    )


def grid_indices(profile, positions):
    ix = np.minimum(
        (positions[:, 0] / profile.width_cm * profile.flow.nx).astype(int), profile.flow.nx - 1
    )
    iy = np.minimum(
        (positions[:, 1] / profile.height_cm * profile.flow.ny).astype(int), profile.flow.ny - 1
    )
    return np.maximum(ix, 0), np.maximum(iy, 0)


def contains_many(points, polygon):
    result = np.zeros(len(points), dtype=bool)
    x, y = points[:, 0], points[:, 1]
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if a[1] != b[1]:
            result ^= ((a[1] > y) != (b[1] > y)) & (
                x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]
            )
    return result


def segment_intersections(start, end, polygon):
    direction = end - start
    earliest = np.full(len(start), np.inf)
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        edge = np.asarray(b) - a
        delta = np.asarray(a) - start
        denom = direction[:, 0] * edge[1] - direction[:, 1] * edge[0]
        nonparallel = np.abs(denom) > 1e-12
        safe = np.where(nonparallel, denom, 1.0)
        t = (delta[:, 0] * edge[1] - delta[:, 1] * edge[0]) / safe
        u = (delta[:, 0] * direction[:, 1] - delta[:, 1] * direction[:, 0]) / safe
        hit = nonparallel & (t > 1e-9) & (t <= 1) & (u >= 0) & (u <= 1)
        earliest = np.minimum(earliest, np.where(hit, t, np.inf))
    return earliest


def simulate(profile: Profile, config: ModelConfig, source):
    """No interpolation across gaps. Substep collision tests limit segment tunneling.

    Rectangular tank boundaries stop particles. Surface obstacles stop particles
    without counting as retention. Verified traps absorb at first intersection.
    """
    rng = np.random.default_rng(config.seed + ord(source.id))
    n = config.particles_per_source
    polygon = np.asarray(source.polygon_cm)
    lo, hi = polygon.min(axis=0), polygon.max(axis=0)
    positions = []
    for _ in range(n):
        for _ in range(10000):
            point = rng.uniform(lo, hi)
            if inside(point, source.polygon_cm):
                positions.append(point)
                break
        else:
            raise ValueError("Could not sample source polygon")
    pos = np.asarray(positions)
    steps = math.ceil(config.max_age_s / config.dt_s)
    paths = np.full((steps + 1, n, 2), np.nan)
    retained = np.full((steps + 1, n), -1, dtype=int)
    active = np.ones(n, dtype=bool)
    trapped = np.full(n, -1, dtype=int)
    paths[0] = pos
    field = np.asarray(profile.flow.velocity_cm_s)
    counts = np.asarray(profile.flow.counts)
    bias = rng.uniform(-config.drift_bound_cm_s, config.drift_bound_cm_s, (n, 2))
    for step in range(1, steps + 1):
        ix, iy = grid_indices(profile, pos)
        supported = counts[iy, ix] >= profile.flow.min_samples
        active &= supported
        proposal = (
            pos
            + (field[iy, ix] + bias) * config.dt_s
            + rng.normal(size=(n, 2)) * math.sqrt(2 * config.diffusion_cm2_s * config.dt_s)
        )
        indices = np.flatnonzero(active)
        old, target = pos[indices].copy(), proposal[indices]
        fractions = np.ones(len(indices))
        hits = np.full(len(indices), -2, dtype=int)
        boundary = [
            (0, 0),
            (profile.width_cm, 0),
            (profile.width_cm, profile.height_cm),
            (0, profile.height_cm),
        ]
        geometries = [(boundary, -1)] + [(p, -1) for p in profile.surface_obstacles]
        geometries += [
            (t.polygon_cm, i) for i, t in enumerate(profile.traps) if t.retention_verified
        ]
        for poly, kind in geometries:
            entry = segment_intersections(old, target, poly)
            # A boundary crossing blocks; an obstacle or trap starting point also intersects.
            if kind != -1 or poly is not boundary:
                entry = np.where(contains_many(old, poly), 0.0, entry)
            earlier = entry <= fractions
            fractions[earlier] = entry[earlier]
            hits[earlier] = kind
        # Coverage along the actual movement segment; unsupported regions never bridge.
        clipped = old + (target - old) * fractions[:, None]
        max_length = np.max(np.linalg.norm(clipped - old, axis=1)) if len(indices) else 0
        for f in np.linspace(0, 1, max(2, math.ceil(max_length / 0.2) + 1))[1:]:
            interim = old + (clipped - old) * f
            gx, gy = grid_indices(profile, interim)
            unsupported = counts[gy, gx] < profile.flow.min_samples
            hits[unsupported] = -1
        pos[indices] = clipped
        ended = hits != -2
        active[indices[ended]] = False
        trapped[indices[hits >= 0]] = hits[hits >= 0]
        valid = active | (trapped >= 0)
        paths[step, valid] = pos[valid]
        retained[step] = trapped
        if not active.any():
            paths[step + 1 :, trapped >= 0] = pos[trapped >= 0]
            retained[step + 1 :] = trapped
            break
    return paths, retained


def estimate(case: CaseInput, profile: Profile, config: ModelConfig | None = None):
    config = config or ModelConfig()
    report = {
        "model_version": MODEL_VERSION,
        "baselines": compare(case, profile),
        "config_hash": fingerprint(config.model_dump()),
        "geometry_hash": fingerprint(profile.model_dump()),
        "calibration_id": profile.id,
        "inference_mode": case.evidence_mode,
        "mode": case.mode,
        "confidence_kind": "relative_support_not_probability",
        "status": "unknown",
        "source": "Unknown",
        "relative_support": {},
        "raw_support": {},
        "absolute_fit": 0.0,
        "margin": 0.0,
        "coverage": 0.0,
        "reason_codes": [],
        "release_age_s": [config.min_age_s, config.max_age_s],
        "evidence_frame_ids": [p.frame_id for p in case.track if p.frame_id],
        "synthetic": profile.synthetic,
    }
    reasons = report["reason_codes"]
    if (
        case.calibration_id != profile.id
        or profile.validity == "invalid"
        or (profile.validity != "validated" and not profile.synthetic)
        or profile.synthetic != (case.mode == "synthetic")
        or case.token_class != profile.token_class
    ):
        reasons.append("CALIBRATION_INVALID")
    points = [p for p in case.track if p.observed and p.quality >= 0.7]
    if case.mode == "live" and (
        case.last_observed_at is None or not 0 <= time.time() - case.last_observed_at < 5
    ):
        reasons.append("STALE_OBSERVATION")
    if not case.observation_region_declared or not points:
        reasons.append("INSUFFICIENT_OBSERVATION")
    if any(not inside((p.x, p.y), profile.observation_polygon_cm) for p in points):
        reasons.append("OBSERVATION_REGION_VIOLATION")
    if case.evidence_mode == "trajectory":
        if len(points) < 5 or points[-1].t - points[0].t < 2:
            reasons.append("INSUFFICIENT_OBSERVATION")
        elif any(b.t - a.t > config.max_gap_s for a, b in itertools.pairwise(points)):
            reasons.append("TRACK_GAP")
    else:
        trap = next((t for t in profile.traps if t.id == case.retained_trap_id), None)
        if (
            trap is None
            or not trap.retention_verified
            or not points
            or not inside((points[-1].x, points[-1].y), trap.polygon_cm)
        ):
            reasons.append("RETENTION_UNVERIFIED")
    if points:
        xy = np.array([(p.x, p.y) for p in points])
        ix, iy = grid_indices(profile, xy)
        report["coverage"] = float(
            np.mean(np.asarray(profile.flow.counts)[iy, ix] >= profile.flow.min_samples)
        )
        if report["coverage"] < config.min_coverage:
            reasons.append("CALIBRATION_INVALID")
    if reasons:
        if "CALIBRATION_INVALID" in reasons:
            report["status"] = "invalid"
        report["reason_codes"] = list(dict.fromkeys(reasons))
        return report
    # Downsample correlated observations rather than multiplying frame likelihoods.
    sample = points[:: max(1, len(points) // 12)]
    times = np.asarray([p.t - points[0].t for p in sample])
    observed = np.asarray([(p.x, p.y) for p in sample])
    age_start = math.ceil(config.min_age_s / config.dt_s)
    for source in profile.sources:
        paths, retained = simulate(profile, config, source)
        if case.evidence_mode == "trajectory":
            offsets = np.rint(times / config.dt_s).astype(int)
            age_stop = len(paths) - int(offsets.max())
            scores = []
            for age in range(age_start, age_stop, max(1, round(0.5 / config.dt_s))):
                segment = paths[age + offsets]
                error = np.mean(np.sum((segment - observed[:, None, :]) ** 2, axis=2), axis=0)
                scores.append(np.nan_to_num(np.exp(-0.5 * error / config.bandwidth_cm**2), nan=0))
            likelihood = float(np.mean(scores)) if scores else 0.0
        else:
            trap_index = next(
                i for i, t in enumerate(profile.traps) if t.id == case.retained_trap_id
            )
            error = np.sum(
                (paths[age_start:] - np.array([points[-1].x, points[-1].y])) ** 2, axis=2
            )
            scores = np.nan_to_num(np.exp(-0.5 * error / config.bandwidth_cm**2), nan=0)
            likelihood = float(np.mean(scores * (retained[age_start:] == trap_index)))
        report["raw_support"][source.id] = likelihood * source.prior
    total = sum(report["raw_support"].values())
    report["relative_support"] = {
        s: v / total if total else 0.0 for s, v in report["raw_support"].items()
    }
    ranking = sorted(report["relative_support"], key=report["relative_support"].get, reverse=True)
    report["absolute_fit"] = max(report["raw_support"][s.id] / s.prior for s in profile.sources)
    report["margin"] = (
        report["relative_support"][ranking[0]] - report["relative_support"][ranking[1]]
    )
    if report["absolute_fit"] < config.min_fit:
        reasons.append("MODEL_MISMATCH")
    if report["margin"] < config.min_margin:
        reasons.append("AMBIGUOUS_SOURCES")
    if not reasons:
        report.update(status="ranked", source=ranking[0])
    return report


def sensitivity(case, profile, config, preset_id):
    if preset_id not in PRESETS:
        raise ValueError("Unknown predeclared sensitivity preset")
    low, high = PRESETS[preset_id]
    variants = [config, config.model_copy(update={"min_age_s": low, "max_age_s": high})]
    results = [estimate(case, profile, c) for c in variants]
    return {
        "preset_id": preset_id,
        "results": results,
        "assumption_sensitive": len({r["source"] for r in results}) > 1,
    }
