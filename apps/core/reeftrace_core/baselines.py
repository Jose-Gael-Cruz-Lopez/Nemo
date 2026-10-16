"""Simple comparators using the same permitted evidence, never release truth."""

import numpy as np


def compare(case, profile):
    points = [p for p in case.track if p.observed and p.quality >= 0.7]
    if not points:
        return {"nearest_inlet": "Unknown", "direction": "Unknown"}
    first = np.array([points[0].x, points[0].y])
    centers = {s.id: np.mean(s.polygon_cm, axis=0) for s in profile.sources}
    nearest = min(centers, key=lambda s: float(np.linalg.norm(centers[s] - first)))
    direction = "Unknown"
    if case.evidence_mode == "trajectory" and len(points) > 1:
        vector = np.array([points[-1].x, points[-1].y]) - first
        length = float(np.linalg.norm(vector))
        if length > 1:
            unit = vector / length
            # Distance of source center to upstream ray from first permitted point.
            scores = {}
            for source, center in centers.items():
                age_distance = max(0.0, float(np.dot(first - center, unit)))
                scores[source] = float(np.linalg.norm(first - unit * age_distance - center))
            direction = min(scores, key=scores.get)
    return {
        "nearest_inlet": nearest,
        "direction": direction,
        "note": "Uncalibrated comparison methods using permitted observations only",
    }
