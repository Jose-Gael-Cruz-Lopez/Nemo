"""Strict local raw reader for the reviewed HYCOM GOFS 3.1 2022 NCSS contract.

This reader acquires nothing and proves no transport provenance. The acquisition
protocol must separately freeze geographic bounds, requested UTC knots and hashes.
Only a singleton 15 m subset is accepted, never a nearest/averaged depth.

The pinned metadata declare float32 scale/offset attributes. Validate their exact
encoded float32 values, then apply the reviewed decimal 0.001 once in float64.
In particular, np.float32('0.001') has a binary representation slightly above the
decimal value: accepting that encoding is not permission to adopt a changed
scale. Adjacent float32 values, float64 attributes and predecoded arrays fail.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np

from .field import OceanField

MAX_FILE_BYTES = 10_000_000
MAX_SAMPLES = 250_000
SCALE = 0.001
FILL = -30000
DEPTH_M = 15.0
TIME_UNITS = "hours since 2000-01-01 00:00:00"
TIME_START = np.datetime64("2022-01-01T12:00:00", "us")
TIME_END = np.datetime64("2023-01-01T09:00:00", "us")
METADATA_URL = (
    "https://ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z/2022/dataset.xml"
)
DIMS = ("time", "depth", "lat", "lon")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError("HYCOM_METADATA_ERROR: " + message)


def _monotonic(values: np.ndarray) -> bool:
    return values.size <= 1 or bool(np.all(np.diff(values) > 0) or np.all(np.diff(values) < 0))


def normalize_native_longitudes(values) -> np.ndarray:
    """Normalize the actual native indices; never sort, stitch or expand support."""
    native = np.asarray(values, dtype=float)
    _require(native.ndim == 1 and native.size > 0 and np.isfinite(native).all(),
             "longitude must be a nonempty finite one-dimensional axis")
    _require(bool(np.all((native >= 0) & (native < 360))) and _monotonic(native),
             "native longitude must be strictly monotonic in [0,360)")
    normalized = ((native + 180.0) % 360.0) - 180.0
    _require(_monotonic(normalized) and np.ptp(native) < 180 and np.ptp(normalized) < 180,
             "longitude tile crosses a seam or has unsupported extent")
    return normalized


def _scalar_attribute(variable, name: str, *, kind: str, size: int, expected) -> None:
    _require(name in variable.ncattrs(), f"{variable.name} is missing {name}")
    value = np.asarray(variable.getncattr(name))
    _require(value.ndim == 0 and value.dtype.kind == kind and value.dtype.itemsize == size,
             f"{variable.name}.{name} has an unexpected encoded scalar type")
    _require(bool(value == expected), f"{variable.name}.{name} changed its pinned encoding")


def _axis(dataset, name: str, units: str) -> np.ndarray:
    _require(name in dataset.variables, f"missing coordinate {name}")
    variable = dataset.variables[name]
    _require(variable.dimensions == (name,) and np.dtype(variable.dtype).kind == "f"
             and np.dtype(variable.dtype).itemsize == 8,
             f"{name} must retain its one-dimensional double coordinate encoding")
    _require(variable.getncattr("units") == units if "units" in variable.ncattrs() else False,
             f"{name} has unexpected units")
    _require(not any(key in variable.ncattrs() for key in (
        "scale_factor", "add_offset", "_Unsigned")), f"packed coordinate {name} is unsupported")
    result = np.asarray(variable[:], dtype=np.float64)
    _require(result.ndim == 1 and result.size > 0 and np.isfinite(result).all(),
             f"{name} must be finite and nonempty")
    for key in ("_FillValue", "missing_value"):
        if key in variable.ncattrs():
            missing = np.asarray(variable.getncattr(key))
            _require(missing.ndim == 0 and missing.dtype.kind in "if"
                     and not np.any(result == missing),
                     f"{name} contains a declared missing coordinate")
    return result


def _time(dataset) -> np.ndarray:
    hours = _axis(dataset, "time", TIME_UNITS)
    coordinate = dataset.variables["time"]
    _require("calendar" in coordinate.ncattrs()
             and coordinate.getncattr("calendar") == "gregorian",
             "time calendar must remain gregorian")
    # Native metadata use integer-valued double hours on an increasing 3-hour
    # grid. Require that exact support rather than rounding fractional times or
    # bridging a missing nominal knot. All accepted dates are modern Gregorian.
    _require(hours.size >= 2 and np.all(hours == np.floor(hours))
             and np.all(np.diff(hours) == 3), "time must retain consecutive three-hour UTC knots")
    lower = float((TIME_START - np.datetime64("2000-01-01", "us")) / np.timedelta64(1, "h"))
    upper = float((TIME_END - np.datetime64("2000-01-01", "us")) / np.timedelta64(1, "h"))
    _require(bool(np.all((hours >= lower) & (hours <= upper))),
             "time lies outside the pinned 2022 aggregate calendar bounds")
    return (np.datetime64("2000-01-01T00:00:00", "us")
            + hours.astype("timedelta64[h]")).astype("datetime64[us]")


def _raw_velocity(dataset, name: str) -> np.ndarray:
    _require(name in dataset.variables, f"missing velocity {name}")
    variable = dataset.variables[name]
    dtype = np.dtype(variable.dtype)
    _require(variable.dimensions == DIMS and dtype.kind == "i" and dtype.itemsize == 2,
             f"{name} must be raw signed int16 with dimensions time depth lat lon")
    _require("units" in variable.ncattrs() and variable.getncattr("units") == "m/s",
             f"{name} must declare exactly m/s")
    _require("_Unsigned" not in variable.ncattrs(), f"{name} unsigned reinterpretation is unsupported")
    _scalar_attribute(variable, "_FillValue", kind="i", size=2, expected=np.int16(FILL))
    _scalar_attribute(variable, "missing_value", kind="i", size=2, expected=np.int16(FILL))
    _scalar_attribute(variable, "scale_factor", kind="f", size=4, expected=np.float32("0.001"))
    _scalar_attribute(variable, "add_offset", kind="f", size=4, expected=np.float32(0))
    raw = np.asarray(variable[:])
    _require(raw.dtype.kind == "i" and raw.dtype.itemsize == 2,
             f"{name} was automatically decoded before the raw reader")
    return raw[:, 0, :, :]


def load_hycom_field(path: str | Path, *, max_samples: int = MAX_SAMPLES,
                     max_file_bytes: int = MAX_FILE_BYTES) -> OceanField:
    """Read bounded local bytes with CF mask/scale disabled; never access a URL.

    Public provenance contains a byte digest and reviewed format contract, not a
    machine path, copied global attributes or proof of scientific acquisition.
    Missing either velocity component masks both; missing currents are not zero.
    """
    try:
        from netCDF4 import Dataset
    except ImportError as error:
        raise ImportError("Install the ocean extra to read local HYCOM NetCDF") from error
    _require(type(max_file_bytes) is int and 0 < max_file_bytes <= MAX_FILE_BYTES
             and type(max_samples) is int and 0 < max_samples <= MAX_SAMPLES,
             "reader budgets must be positive integers within the hard bounds")
    source = Path(path)
    _require(source.is_file(), "select an existing local NetCDF file")
    _require(0 < source.stat().st_size <= max_file_bytes, "local file exceeds its byte budget")
    with source.open("rb") as handle:
        payload = handle.read(max_file_bytes + 1)
    _require(0 < len(payload) <= max_file_bytes, "local file exceeds its byte budget")
    try:
        dataset = Dataset("hycom-local-subset", mode="r", memory=payload)
    except (OSError, ValueError, RuntimeError) as error:
        raise ValueError("HYCOM_METADATA_ERROR: bytes are not a supported NetCDF file") from error
    with dataset:
        # Disable both automatic masking and scaling before ANY variable reads.
        dataset.set_auto_maskandscale(False)
        _require(set(DIMS) <= set(dataset.dimensions), "missing native coordinate dimensions")
        shape = tuple(len(dataset.dimensions[name]) for name in DIMS)
        _require(shape[0] >= 2 and shape[1] == 1 and shape[2] >= 2 and shape[3] >= 2,
                 "subset needs time knots, a singleton 15 m depth, and a rectilinear tile")
        _require(math.prod(shape) <= max_samples, "subset exceeds its sample budget")
        depth = _axis(dataset, "depth", "m")
        _require(depth.size == 1 and depth[0] == DEPTH_M
                 and "positive" in dataset.variables["depth"].ncattrs()
                 and dataset.variables["depth"].getncattr("positive") == "down",
                 "depth must be exactly 15 m positive down")
        when = _time(dataset)
        latitude = _axis(dataset, "lat", "degrees_north")
        native_longitude = _axis(dataset, "lon", "degrees_east")
        _require(_monotonic(latitude) and bool(np.all((latitude >= -80) & (latitude <= 85))),
                 "latitude must be strictly monotonic in supported nonpolar HYCOM degrees")
        longitude = normalize_native_longitudes(native_longitude)
        raw_u, raw_v = _raw_velocity(dataset, "water_u"), _raw_velocity(dataset, "water_v")
        valid = (raw_u != FILL) & (raw_v != FILL)
        # Mask in integer space BEFORE multiplying once by the reviewed decimal.
        east = np.full(raw_u.shape, np.nan, dtype=float)
        north = np.full(raw_v.shape, np.nan, dtype=float)
        east[valid], north[valid] = raw_u[valid].astype(float) * SCALE, raw_v[valid].astype(float) * SCALE
        _require(bool(np.all(np.hypot(east[valid], north[valid]) <= 10)),
                 "supported current speed exceeds the bounded integrator's m/s limit")
    metadata = {
        "product": "HYCOM_GOFS3.1_GLBy0.08_expt93.0_UV3Z_2022_format_contract",
        "contract_metadata_url": METADATA_URL, "sha256": hashlib.sha256(payload).hexdigest(),
        "source_bytes": len(payload), "u_variable": "water_u", "v_variable": "water_v",
        "velocity_units": "m/s", "data_kind": "local_model_subset_not_observed_plastic",
        "source_origin_verified": False, "issue_time_verified": False,
        "calendar": "gregorian", "time_units": TIME_UNITS,
        "longitude_normalization": "((native_lon+180)%360)-180_without_reordering",
        "raw_encoding": {"dtype": "signed_int16", "fill_and_missing": FILL,
                         "scale_factor_encoding": "exact_pinned_float32",
                         "applied_decimal_scale": SCALE, "add_offset": 0,
                         "mask_before_scaling": True, "decode_count": 1},
        "limitations": [
            "Local format and byte identity do not verify service transport or product origin.",
            "The acquisition protocol must separately bind the tile and requested UTC knots.",
            "Analysis/hindcast valid times do not establish origin-time forecast availability.",
            "No assimilation independence, drifter skill, plastic accuracy or tank calibration is established.",
        ],
    }
    return OceanField(when, longitude, latitude, east, north, valid, DEPTH_M, metadata)
