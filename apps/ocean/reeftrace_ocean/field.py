"""Bounded local NetCDF ingestion. No network downloads or tank-coordinate coercion."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

_MPS_UNITS = {"m/s", "m s-1", "m s^-1", "m s**-1", "meter per second", "metres per second"}


def _spacing(values: np.ndarray) -> list[float] | None:
    if values.size < 2:
        return None
    differences = np.abs(np.diff(values))
    return [float(differences.min()), float(differences.max())]


def _wgs84_metres_per_degree(latitude_deg: float) -> tuple[float, float]:
    """Local WGS84 metric for grid-size disclosure, not a trajectory integrator.

    Geographic advection needs a geodesic solver/projection with its own error
    budget; adding metres or centimetres directly to degrees is never valid.
    """
    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = f * (2.0 - f)
    latitude = math.radians(latitude_deg)
    denominator = 1.0 - e2 * math.sin(latitude) ** 2
    prime_vertical = a / math.sqrt(denominator)
    meridional = a * (1.0 - e2) / denominator**1.5
    return (
        math.pi / 180.0 * prime_vertical * abs(math.cos(latitude)),
        math.pi / 180.0 * meridional,
    )


@dataclass(frozen=True)
class OceanField:
    """u/v and valid_mask have shape (time, latitude, longitude), velocity in m/s."""

    time_utc: np.ndarray
    longitude_deg: np.ndarray
    latitude_deg: np.ndarray
    eastward_m_s: np.ndarray
    northward_m_s: np.ndarray
    valid_mask: np.ndarray
    selected_depth_m: float | None
    metadata: dict

    def summary(self) -> dict:
        longitude_spacing = _spacing(self.longitude_deg)
        latitude_spacing = _spacing(self.latitude_deg)
        middle_latitude = float(np.mean(self.latitude_deg))
        metres_lon, metres_lat = _wgs84_metres_per_degree(middle_latitude)
        return {
            "coordinate_space": "geographic_lonlat_degrees",
            "velocity_units": "m/s",
            "array_dimensions": ["time", "latitude", "longitude"],
            "shape": list(self.eastward_m_s.shape),
            "time_start_utc": str(self.time_utc[0]) + "Z",
            "time_end_utc": str(self.time_utc[-1]) + "Z",
            "longitude_range_deg": [
                float(self.longitude_deg.min()),
                float(self.longitude_deg.max()),
            ],
            "latitude_range_deg": [float(self.latitude_deg.min()), float(self.latitude_deg.max())],
            "selected_depth_m": self.selected_depth_m,
            "valid_sample_count": int(self.valid_mask.sum()),
            "invalid_sample_count": int((~self.valid_mask).sum()),
            "longitude_spacing_degrees_min_max": longitude_spacing,
            "latitude_spacing_degrees_min_max": latitude_spacing,
            "approx_east_west_grid_spacing_m_at_midlatitude": (
                [step * metres_lon for step in longitude_spacing] if longitude_spacing else None
            ),
            "approx_north_south_grid_spacing_m": (
                [step * metres_lat for step in latitude_spacing] if latitude_spacing else None
            ),
            "limitations": [
                "Model grid spacing is not guaranteed effective physical resolution.",
                "These geographic fields cannot be passed to the centimetre tank estimator.",
                "No source attribution, ecological impact or field validation is established.",
            ],
            "provenance": self.metadata,
        }


def load_copernicus_field(
    path: str | Path,
    *,
    u_variable: str = "utotal",
    v_variable: str = "vtotal",
    depth_index: int = 0,
    max_samples: int = 250_000,
    max_file_bytes: int = 50_000_000,
) -> OceanField:
    """Read an explicitly selected local rectilinear CF NetCDF subset.

    xarray and a NetCDF backend are optional. Coordinates are preserved in degrees,
    velocities in m/s; decoded fill values stay NaN and have an explicit mask.
    Singleton depth is selected explicitly by index, never averaged or guessed.
    Curvilinear grids and non-standard time calendars are deliberately rejected.
    """
    try:
        import xarray as xr
    except ImportError as exc:
        raise ImportError("Install the ocean extra: pip install -e '.[ocean]'") from exc
    source = Path(path)
    if not source.is_file():
        raise ValueError("Select an existing local NetCDF file; remote URLs are not opened")
    if max_samples <= 0 or max_file_bytes <= 0 or source.stat().st_size > max_file_bytes:
        raise ValueError("Ocean subset exceeds the explicit local file budget")
    with xr.open_dataset(source, decode_times=True, mask_and_scale=True) as dataset:
        for name in ("longitude", "latitude", "time"):
            if name not in dataset.coords or dataset[name].dims != (name,):
                raise ValueError("Expected 1D longitude, latitude and time coordinates")
        count = math.prod(dataset.sizes[name] for name in ("time", "latitude", "longitude"))
        if count > max_samples:
            raise ValueError("Ocean subset exceeds the explicit sample budget")
        for name in (u_variable, v_variable):
            if name not in dataset:
                raise ValueError(f"Missing velocity variable: {name}")
            if str(dataset[name].attrs.get("units", "")).strip().lower() not in _MPS_UNITS:
                raise ValueError(f"{name} must declare velocity units in m/s")
        lon = np.asarray(dataset.longitude.values, dtype=float)
        lat = np.asarray(dataset.latitude.values, dtype=float)
        when = np.asarray(dataset.time.values)
        if not np.issubdtype(when.dtype, np.datetime64) or np.isnat(when).any():
            raise ValueError("Expected decoded UTC-compatible Gregorian times")
        if not (lon.size and lat.size and when.size):
            raise ValueError("Empty ocean subset")
        if not (np.isfinite(lon).all() and np.isfinite(lat).all()):
            raise ValueError("Invalid longitude/latitude")
        if np.abs(lat).max() > 90 or lon.min() < -180 or lon.max() > 360:
            raise ValueError("Coordinates must be geographic degrees, not tank centimetres")
        for coordinate in (lon, lat, when):
            differences = np.diff(coordinate)
            zero = np.timedelta64(0, "ns") if np.issubdtype(coordinate.dtype, np.datetime64) else 0
            if coordinate.size > 1 and not (
                np.all(differences > zero) or np.all(differences < zero)
            ):
                raise ValueError("Coordinates must be strictly monotonic")
        if when.size > 1 and not np.all(np.diff(when) > np.timedelta64(0, "ns")):
            raise ValueError("Time must increase")
        for name, expected in (("latitude", "degrees_north"), ("longitude", "degrees_east")):
            if dataset[name].attrs.get("units") != expected:
                raise ValueError(f"{name} must declare {expected}")
        selected_depth = None
        pair = dataset[[u_variable, v_variable]]
        if "depth" in pair.dims:
            if not 0 <= depth_index < pair.sizes["depth"]:
                raise ValueError("Depth index outside subset")
            if dataset.depth.attrs.get("units") not in {"m", "meter", "metre", "meters", "metres"}:
                raise ValueError("Depth must declare metres")
            if dataset.depth.attrs.get("positive", "down") != "down":
                raise ValueError("Only positive-down depth is supported")
            selected_depth = float(dataset.depth.values[depth_index])
            if not math.isfinite(selected_depth) or selected_depth < 0:
                raise ValueError("Invalid selected depth")
            pair = pair.isel(depth=depth_index)
        elif depth_index != 0:
            raise ValueError("No depth axis for the requested depth index")
        dimensions = {"time", "latitude", "longitude"}
        if any(set(pair[name].dims) != dimensions for name in (u_variable, v_variable)):
            raise ValueError("Velocity variables need time/latitude/longitude dimensions")
        if when.size * lat.size * lon.size > max_samples:
            raise ValueError("Ocean subset exceeds the explicit sample budget")
        u = np.asarray(pair[u_variable].transpose("time", "latitude", "longitude").values, float)
        v = np.asarray(pair[v_variable].transpose("time", "latitude", "longitude").values, float)
        valid = np.isfinite(u) & np.isfinite(v) & (np.abs(u) < 1e20) & (np.abs(v) < 1e20)
        u = np.where(valid, u, np.nan)
        v = np.where(valid, v, np.nan)
        metadata = {
            "source_file": str(source.resolve()),
            "product": str(dataset.attrs.get("product", "unspecified")),
            "dataset": str(dataset.attrs.get("dataset", "unspecified")).strip(),
            "title": str(dataset.attrs.get("title", "unspecified")),
            "u_variable": u_variable,
            "v_variable": v_variable,
            "data_kind": "model_output_not_plastic_ground_truth",
        }
    digest = hashlib.sha256()
    with source.open("rb") as file:
        for chunk in iter(lambda: file.read(65536), b""):
            digest.update(chunk)
    metadata["sha256"] = digest.hexdigest()
    return OceanField(when, lon, lat, u, v, valid, selected_depth, metadata)
