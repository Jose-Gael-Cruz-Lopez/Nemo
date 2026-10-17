"""A measured surface-drift interpolator with explicit spatial support and error diagnostics."""

from __future__ import annotations

import numpy as np

from .geometry import Bounds


class FlowField:
    def __init__(self, document: dict):
        if document.get("kind") != "idw":
            raise ValueError("Only the declared idw measured-flow model is supported")
        if document.get("units", "cm,s") != "cm,s":
            raise ValueError("Flow units must be cm,s")
        self.bounds = Bounds.from_dict(document["bounds"])
        nodes = document["nodes"]
        self.xy = np.array([[n["x_cm"], n["y_cm"]] for n in nodes], dtype=float)
        self.velocity = np.array([[n["vx_cm_s"], n["vy_cm_s"]] for n in nodes], dtype=float)
        if not 1 <= len(nodes) <= 512 or not np.isfinite(self.xy).all() or not np.isfinite(self.velocity).all():
            raise ValueError("Flow requires 1–512 finite measured nodes")
        if not self.bounds.contains(self.xy).all():
            raise ValueError("Flow nodes outside declared bounds")
        self.radius = float(document["coverage_radius_cm"])
        neighbors = document.get("neighbors", 8)
        self.neighbors = int(neighbors)
        self.power = float(document.get("power", 2.0))
        if (not np.isfinite([self.radius, self.power]).all() or self.radius <= 0
                or not 0 < self.power <= 8):
            raise ValueError("Coverage radius must be positive and interpolation power in (0,8]")
        if not 1 <= self.neighbors <= 64 or self.neighbors != neighbors:
            raise ValueError("neighbors must be an integer between 1 and 64")

    def evaluate(self, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        points = np.atleast_2d(np.asarray(points, dtype=float))
        if points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all():
            raise ValueError("Flow positions must be finite N by 2 coordinates")
        distance2 = np.sum((points[:, None] - self.xy[None]) ** 2, axis=2)
        k = min(self.neighbors, len(self.xy))
        indices = np.argsort(distance2, axis=1, kind="stable")[:, :k]
        selected = np.take_along_axis(distance2, indices, axis=1)
        log_weights = -self.power / 2 * np.log(np.maximum(selected, 1e-12))
        weights = np.exp(log_weights - log_weights.max(axis=1, keepdims=True))
        exact = selected[:, 0] <= 1e-16
        velocity = (self.velocity[indices] * weights[..., None]).sum(axis=1) / weights.sum(axis=1)[:, None]
        velocity[exact] = self.velocity[indices[exact, 0]]
        supported = (distance2.min(axis=1) <= self.radius ** 2) & self.bounds.contains(points)
        return velocity, supported


def _samples(value: list[dict], bounds: Bounds) -> tuple[np.ndarray, np.ndarray]:
    if not value or len(value) > 20000:
        raise ValueError("Between 1 and 20000 measured flow samples are required")
    array = np.array([[row[k] for k in ("x_cm", "y_cm", "vx_cm_s", "vy_cm_s")]
                      for row in value], dtype=float)
    if not np.isfinite(array).all():
        raise ValueError("Samples must be finite")
    if not bounds.contains(array[:, :2]).all():
        raise ValueError("Samples are outside tank bounds")
    return array[:, :2], array[:, 2:]


def fit_flow(samples: list[dict], bounds: dict, *, cell_size_cm: float = 5.0,
             coverage_radius_cm: float = 10.0, neighbors: int = 8, power: float = 2.0,
             validation_samples: list[dict] | None = None,
             data_origin: str = "UNVERIFIED") -> dict:
    """Median velocities per spatial cell, IDW interpolation, and independent support flags.

    Each sample is {x_cm,y_cm,vx_cm_s,vy_cm_s}; velocities must already be measured
    from real time-separated marker positions. This does not manufacture a flow from source labels.
    """
    rectangle = Bounds.from_dict(bounds)
    if not np.isfinite(cell_size_cm) or cell_size_cm <= 0:
        raise ValueError("cell_size_cm must be positive")
    xy, velocity = _samples(samples, rectangle)
    cells = np.floor((xy - [rectangle.x_min_cm, rectangle.y_min_cm]) / cell_size_cm)
    nodes = []
    for cell in np.unique(cells, axis=0):
        selected = np.all(cells == cell, axis=1)
        center = np.median(xy[selected], axis=0)
        drift = np.median(velocity[selected], axis=0)
        scatter = np.sqrt(np.mean(np.sum((velocity[selected] - drift) ** 2, axis=1)))
        nodes.append({"x_cm": float(center[0]), "y_cm": float(center[1]),
                          "vx_cm_s": float(drift[0]), "vy_cm_s": float(drift[1]),
                          "sample_count": int(selected.sum()), "scatter_cm_s": float(scatter)})
    document = {"kind": "idw", "units": "cm,s", "bounds": rectangle.to_dict(), "nodes": nodes,
                    "coverage_radius_cm": float(coverage_radius_cm), "neighbors": neighbors,
                    "power": float(power), "cell_size_cm": float(cell_size_cm),
                    "data_origin": str(data_origin), "validity": "DEVELOPMENT_ONLY_UNTIL_VALIDATED"}
    field = FlowField(document)
    training = field.evaluate(xy)[0]
    loo_residuals = []
    for i, node in enumerate(nodes):
        if len(nodes) < 2:
            break
        other = {**document, "nodes": nodes[:i] + nodes[i + 1:]}
        prediction, supported = FlowField(other).evaluate([[node["x_cm"], node["y_cm"]]])
        if supported[0]:
            loo_residuals.append(prediction[0] - [node["vx_cm_s"], node["vy_cm_s"]])
    gx = np.linspace(rectangle.x_min_cm, rectangle.x_max_cm, 21)
    gy = np.linspace(rectangle.y_min_cm, rectangle.y_max_cm, 21)
    grid = np.array(np.meshgrid(gx, gy)).reshape(2, -1).T
    diagnostics = {
        "sample_count": len(samples), "node_count": len(nodes),
        "training_rmse_cm_s": float(np.sqrt(np.mean(np.sum((training - velocity) ** 2, axis=1)))),
        "loo_rmse_cm_s": (float(np.sqrt(np.mean(np.sum(np.array(loo_residuals) ** 2, axis=1))))
                       if loo_residuals else None),
        "loo_supported_nodes": len(loo_residuals),
        "grid_coverage_fraction": float(field.evaluate(grid)[1].mean()),
        "max_speed_cm_s": float(np.linalg.norm(field.velocity, axis=1).max()),
        "validation_rmse_cm_s": None, "validation_coverage_fraction": None,
    }
    if validation_samples:
        val_xy, val_velocity = _samples(validation_samples, rectangle)
        prediction, supported = field.evaluate(val_xy)
        diagnostics["validation_coverage_fraction"] = float(supported.mean())
        if np.any(supported):
            diagnostics["validation_rmse_cm_s"] = float(np.sqrt(np.mean(
                np.sum((prediction[supported] - val_velocity[supported]) ** 2, axis=1))))
    document["diagnostics"] = diagnostics
    return document
