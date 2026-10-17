"""Small, explicit planar geometry in centimetres; no GIS assumptions."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Bounds:
    x_min_cm: float
    x_max_cm: float
    y_min_cm: float
    y_max_cm: float

    @classmethod
    def from_dict(cls, value: dict) -> Bounds:
        result = cls(**{key: float(value[key]) for key in cls.__dataclass_fields__})
        if not np.isfinite(result.array).all():
            raise ValueError("Bounds must be finite")
        if result.x_max_cm <= result.x_min_cm or result.y_max_cm <= result.y_min_cm:
            raise ValueError("Bounds must have positive area")
        return result

    @property
    def array(self) -> np.ndarray:
        return np.array([self.x_min_cm, self.x_max_cm, self.y_min_cm, self.y_max_cm])

    @property
    def size(self) -> np.ndarray:
        return np.array([self.x_max_cm - self.x_min_cm, self.y_max_cm - self.y_min_cm])

    def contains(self, points: np.ndarray, tolerance: float = 1e-9) -> np.ndarray:
        return ((points[..., 0] >= self.x_min_cm - tolerance)
                & (points[..., 0] <= self.x_max_cm + tolerance)
                & (points[..., 1] >= self.y_min_cm - tolerance)
                & (points[..., 1] <= self.y_max_cm + tolerance))

    def to_dict(self) -> dict:
        return {key: getattr(self, key) for key in self.__dataclass_fields__}


def polygon_array(value: list, bounds: Bounds | None = None) -> np.ndarray:
    polygon = np.asarray(value, dtype=float)
    if polygon.ndim != 2 or polygon.shape[1] != 2 or not 3 <= len(polygon) <= 65:
        raise ValueError("A polygon requires 3–64 [x_cm, y_cm] vertices, plus optional closure")
    if not np.isfinite(polygon).all():
        raise ValueError("Polygon coordinates must be finite")
    if np.allclose(polygon[0], polygon[-1]):
        polygon = polygon[:-1]
    if len(polygon) > 64 or np.any(np.linalg.norm(polygon - np.roll(polygon, -1, axis=0),
                                                 axis=1) <= 1e-10):
        raise ValueError("Polygon edges must have positive length")
    area = abs(_cross(polygon, np.roll(polygon, -1, axis=0)).sum()) / 2
    if len(polygon) < 3 or area <= 1e-10:
        raise ValueError("Polygon must have positive area")
    if bounds is not None and not bounds.contains(polygon).all():
        raise ValueError("Polygon is outside tank bounds")
    # Reject non-adjacent edge intersections, including touching bow-ties.
    for i in range(len(polygon)):
        for j in range(i + 1, len(polygon)):
            if j == i + 1 or (i == 0 and j == len(polygon) - 1):
                continue
            a, b = polygon[i], polygon[(i + 1) % len(polygon)]
            c, d = polygon[j], polygon[(j + 1) % len(polygon)]
            if _segments_intersect(a, b, c, d):
                raise ValueError("Self-intersecting polygons are unsupported")
    return polygon


def _cross(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]


def _segments_intersect(a, b, c, d) -> bool:
    ab, cd = b - a, d - c
    denominator = _cross(ab, cd)
    if abs(denominator) < 1e-12:
        if abs(_cross(c - a, ab)) > 1e-12:
            return False
        return bool(np.all(np.maximum(np.minimum(a, b), np.minimum(c, d))
                           <= np.minimum(np.maximum(a, b), np.maximum(c, d)) + 1e-12))
    t, u = _cross(c - a, cd) / denominator, _cross(c - a, ab) / denominator
    return bool(-1e-12 <= t <= 1 + 1e-12 and -1e-12 <= u <= 1 + 1e-12)


def points_in_polygon(points: np.ndarray, polygon: np.ndarray) -> np.ndarray:
    """Ray casting, including polygon edges. Works for simple concave polygons."""
    points = np.asarray(points, dtype=float)
    x, y = points[..., 0], points[..., 1]
    inside = np.zeros(x.shape, dtype=bool)
    boundary = np.zeros(x.shape, dtype=bool)
    for a, b in zip(polygon, np.roll(polygon, -1, axis=0), strict=True):
        edge = b - a
        relative = points - a
        cross = _cross(edge, relative)
        boundary |= ((np.abs(cross) < 1e-9)
                     & (np.sum(relative * edge, axis=-1) >= -1e-9)
                     & (np.sum((points - b) * edge, axis=-1) <= 1e-9))
        if abs(edge[1]) > 1e-14:
            intersects = ((a[1] > y) != (b[1] > y)) & (
                x < edge[0] * (y - a[1]) / edge[1] + a[0])
            inside ^= intersects
    return inside | boundary


def sample_polygon(polygon: np.ndarray, count: int, rng: np.random.Generator) -> np.ndarray:
    """Uniform area rejection sampling with a finite work limit."""
    low, high = polygon.min(axis=0), polygon.max(axis=0)
    accepted = []
    total = 0
    for _ in range(100):
        candidates = rng.uniform(low, high, size=(max(64, 2 * (count - total)), 2))
        chosen = candidates[points_in_polygon(candidates, polygon)]
        accepted.append(chosen)
        total += len(chosen)
        if total >= count:
            return np.concatenate(accepted)[:count]
    raise ValueError("Polygon sampling budget exceeded; use a less degenerate source polygon")


def segment_polygon_hit(start: np.ndarray, delta: np.ndarray, polygon: np.ndarray) -> np.ndarray:
    """Earliest intersection fraction [0,1], or infinity; detects thin traps."""
    result = np.full(len(start), np.inf)
    result[points_in_polygon(start, polygon)] = 0.0
    for a, b in zip(polygon, np.roll(polygon, -1, axis=0), strict=True):
        edge = b - a
        denominator = _cross(delta, edge)
        valid = np.abs(denominator) > 1e-12
        t = np.full(len(start), np.inf)
        u = np.full(len(start), np.inf)
        t[valid] = _cross(a - start[valid], edge) / denominator[valid]
        u[valid] = _cross(a - start[valid], delta[valid]) / denominator[valid]
        hit = valid & (t >= -1e-10) & (t <= 1 + 1e-10) & (u >= -1e-10) & (u <= 1 + 1e-10)
        result[hit] = np.minimum(result[hit], np.clip(t[hit], 0, 1))
    return result


def advance_reflecting(start: np.ndarray, delta: np.ndarray, bounds: Bounds,
                       traps: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """Reflect at rectangle walls; stop at the first absorbing trap on each segment."""
    position = np.array(start, dtype=float, copy=True)
    remaining = np.array(delta, dtype=float, copy=True)
    retained = np.zeros(len(position), dtype=bool)
    active = np.ones(len(position), dtype=bool)
    for _ in range(12):
        idx = np.flatnonzero(active)
        if not len(idx):
            return position, retained
        p, d = position[idx], remaining[idx]
        times = np.full((len(idx), 2), np.inf)
        for axis, lo, hi in ((0, bounds.x_min_cm, bounds.x_max_cm),
                             (1, bounds.y_min_cm, bounds.y_max_cm)):
            nonzero = np.abs(d[:, axis]) > 1e-14
            target = np.where(d[:, axis] > 0, hi, lo)
            t = np.full(len(idx), np.inf)
            t[nonzero] = (target[nonzero] - p[nonzero, axis]) / d[nonzero, axis]
            times[:, axis] = np.where((t >= -1e-10) & (t <= 1), np.maximum(t, 0), np.inf)
        wall_t = times.min(axis=1)
        trap_t = np.full(len(idx), np.inf)
        for trap in traps:
            trap_t = np.minimum(trap_t, segment_polygon_hit(p, d, trap))
        trapped = np.isfinite(trap_t) & (trap_t <= wall_t + 1e-10)
        position[idx[trapped]] = p[trapped] + trap_t[trapped, None] * d[trapped]
        retained[idx[trapped]] = True
        active[idx[trapped]] = False
        free = ~trapped & ~np.isfinite(wall_t)
        position[idx[free]] = p[free] + d[free]
        active[idx[free]] = False
        bounce = ~trapped & np.isfinite(wall_t)
        if np.any(bounce):
            bidx, bt = idx[bounce], wall_t[bounce]
            position[bidx] = p[bounce] + bt[:, None] * d[bounce]
            rest = d[bounce] * (1 - bt[:, None])
            for axis in (0, 1):
                rest[np.isclose(times[bounce, axis], bt, atol=1e-10), axis] *= -1
            remaining[bidx] = rest
    raise ValueError("Boundary collision budget exceeded; reduce dt or dispersion")
