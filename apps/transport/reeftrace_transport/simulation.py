"""Bounded forward Euler–Maruyama ensembles; no reverse-posterior shortcut."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .flow import FlowField
from .geometry import Bounds, advance_reflecting, points_in_polygon, polygon_array, sample_polygon


@dataclass
class Ensemble:
    times_s: np.ndarray
    positions_cm: np.ndarray  # [time, particle, xy]
    retained: np.ndarray  # [time, particle]
    supported: np.ndarray  # [time, particle]
    dt_s: float

    def at(self, times_s: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        times_s = np.asarray(times_s, dtype=float)
        if (times_s.ndim != 1 or not np.isfinite(times_s).all() or np.any(times_s < 0)
                or np.any(times_s > self.times_s[-1] + 1e-9)):
            raise ValueError("Requested simulation time is outside the forward horizon")
        indices = np.searchsorted(self.times_s, times_s, side="right") - 1
        indices = np.clip(indices, 0, len(self.times_s) - 2)
        alpha = (times_s - self.times_s[indices]) / np.diff(self.times_s)[indices]
        positions = (self.positions_cm[indices] * (1 - alpha[:, None, None])
                     + self.positions_cm[indices + 1] * alpha[:, None, None])
        # Conservative retained status: a substep interpolated position is not proof
        # of retention before the discrete collision time. Exact nodes use that node.
        held = self.retained[indices].copy()
        exact_next = np.isclose(alpha, 1, atol=1e-10)
        held[exact_next] = self.retained[indices[exact_next] + 1]
        return positions, held


def simulate(flow: dict, source_polygon: list, *, bounds: dict,
             traps: list[dict] | None = None, particles: int = 500,
             dt_s: float = 0.1, horizon_s: float = 30,
             diffusivity_cm2_s: float = 0.05, drift_bias_cm_s=(0.0, 0.0),
             seed: int = 7, max_steps: int = 4000) -> Ensemble:
    rectangle = Bounds.from_dict(bounds)
    field = FlowField(flow)
    if rectangle.to_dict() != field.bounds.to_dict():
        raise ValueError("Flow and tank bounds disagree")
    if not 1 <= int(particles) <= 5000 or int(particles) != particles:
        raise ValueError("particles must be an integer between 1 and 5000")
    particles = int(particles)
    scalars = np.array([dt_s, horizon_s, diffusivity_cm2_s], dtype=float)
    bias = np.asarray(drift_bias_cm_s, dtype=float)
    if (not np.isfinite(scalars).all() or dt_s <= 0 or horizon_s <= 0
            or diffusivity_cm2_s < 0 or bias.shape != (2,) or not np.isfinite(bias).all()):
        raise ValueError("Invalid time, diffusivity or drift discrepancy")
    if horizon_s > 180:
        raise ValueError("The prototype forward horizon is limited to 180 seconds")
    source = polygon_array(source_polygon, rectangle)
    trap_polygons = []
    for trap in traps or []:
        if trap.get("retention", "absorbing") != "absorbing":
            raise ValueError("Only explicit absorbing retention is implemented")
        trap_polygons.append(polygon_array(trap["polygon_cm"], rectangle))
    feature = min(rectangle.size)
    for polygon in trap_polygons:
        feature = min(feature, float(np.ptp(polygon, axis=0).min()))
    speed = float(np.linalg.norm(field.velocity, axis=1).max() + np.linalg.norm(bias))
    # Resolve half the narrowest geometric feature at a nominal 3-sigma step.
    while speed * dt_s + 3 * np.sqrt(2 * diffusivity_cm2_s * dt_s) > 0.5 * feature:
        dt_s /= 2
        if dt_s < horizon_s / max_steps:
            raise ValueError("Simulation budget exceeded while resolving geometric features")
    steps = max(1, int(np.ceil(horizon_s / dt_s)))
    if steps > max_steps or (steps + 1) * particles > 3_000_000:
        raise ValueError("Simulation budget exceeded; narrow the supported horizon/geometry")
    dt_s = horizon_s / steps
    times = np.linspace(0, horizon_s, steps + 1)
    rng = np.random.default_rng(seed)
    initial = sample_polygon(source, particles, rng)
    positions = np.empty((steps + 1, particles, 2))
    held = np.zeros((steps + 1, particles), dtype=bool)
    covered = np.empty_like(held)
    positions[0] = initial
    for trap in trap_polygons:
        held[0] |= points_in_polygon(initial, trap)
    covered[0] = field.evaluate(initial)[1]
    for step in range(steps):
        old = positions[step]
        velocity, supported = field.evaluate(old)
        noise = rng.normal(size=(particles, 2)) * np.sqrt(2 * diffusivity_cm2_s * dt_s)
        delta = (velocity + bias) * dt_s + noise
        delta[held[step]] = 0
        new, trapped = advance_reflecting(old, delta, rectangle, trap_polygons)
        positions[step + 1] = new
        held[step + 1] = held[step] | trapped
        covered[step + 1] = supported & field.evaluate(new)[1]
    return Ensemble(times, positions, held, covered, dt_s)
