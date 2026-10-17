"""Pinned PacIOOS current forcing and a bounded, hypothetical ocean tracer preview.

Loading this report is entirely offline. Acquisition is an explicit script, and
the raw bytes, metadata and receipt must match reviewed hashes before use.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import numpy as np

from . import advection
from .advection import CurrentSampler, advect_current
from .field import OceanField, _wgs84_metres_per_degree

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data/current_fields/pacioos-current-forecast-v1"
DATASET_ID = "roms_hiig"
START_UTC = "2026-10-17T18:00:00Z"
END_UTC = "2026-10-18T00:00:00Z"
FILE_NAME = "pacioos-roms-hiig-surface-20261017T18-20261018T00.csv"
METADATA_FILE = "erddap-info.json"
MANIFEST_FILE = "manifest.json"
# Filled only after explicit, successful acquisition and inspection.
MANIFEST_SHA256 = "c790652416e87de208e3b84dec808998a5a3919909808f47d854be6c74298790"
MAX_BYTES = 1_000_000
MAX_METADATA_BYTES = 100_000
MAX_ROWS = 10_000
HEADERS = ("time", "depth", "latitude", "longitude", "u", "v")
UNITS = ("UTC", "m", "degrees_north", "degrees_east", "meter second-1", "meter second-1")
SUBSET = f"[({START_UTC}):1:({END_UTC})][0:1:0][(20.5):1:(21.5)][(-158.8):1:(-157.4)]"
QUERY = f"u{SUBSET},v{SUBSET}"
SOURCE_URL = (
    f"https://pae-paha.pacioos.hawaii.edu/erddap/griddap/{DATASET_ID}.csv?"
    + quote(QUERY, safe="")
)
METADATA_URL = f"https://pae-paha.pacioos.hawaii.edu/erddap/info/{DATASET_ID}/index.json"
PRODUCT_URL = "https://www.pacioos.hawaii.edu/metadata/roms_hiig.html"
ATTRIBUTION = "PacIOOS / University of Hawaiʻi ROMS Main Hawaiian Islands; NOAA IOOS support"
LIMITATIONS = [
    "Real ocean-model currents drive a hypothetical release, not an observed piece of waste.",
    "A 4 km grid with 3-hour forcing cannot resolve individual reef branches or tank eddies.",
    "This best-forecast aggregation supplies valid times but no verified single model issue time.",
    "No forecast skill, measured trajectory, source attribution or interception benefit is established.",
    "Windage, waves/Stokes drift, diffusion, beaching and object-specific response are not modeled.",
    "Missing cells or unavailable times stop integration; unsupported paths are never invented.",
    "Ocean metres/m/s are kept separate from camera-derived tank centimetres/cm/s.",
]


def _metadata(payload: bytes) -> dict:
    if not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_METADATA_BYTES:
        raise ValueError("Current metadata exceeds its bounded byte budget")
    try:
        rows = json.loads(payload)["table"]["rows"]
        values = {(row[1], row[2]): row[4] for row in rows if row[0] == "attribute"}
    except (ValueError, KeyError, TypeError, IndexError) as error:
        raise ValueError("Malformed PacIOOS metadata") from error
    for name, unit in (("u", "meter second-1"), ("v", "meter second-1"),
                       ("latitude", "degrees_north"), ("longitude", "degrees_east"),
                       ("depth", "m")):
        if values.get((name, "units")) != unit:
            raise ValueError("PacIOOS metadata has unexpected coordinate or velocity units")
    if values.get(("u", "standard_name")) != "eastward_sea_water_velocity" or values.get(
        ("v", "standard_name")
    ) != "northward_sea_water_velocity":
        raise ValueError("PacIOOS metadata does not describe east/north water velocity")
    return {
        "title": values.get(("NC_GLOBAL", "title")),
        "summary": values.get(("NC_GLOBAL", "summary")),
        "license": values.get(("NC_GLOBAL", "license")),
        "source": values.get(("NC_GLOBAL", "source")),
        "history": values.get(("NC_GLOBAL", "history")),
    }


def parse_current_csv(payload: bytes, *, metadata: dict | None = None) -> OceanField:
    """Decode only the reviewed six-hour, surface-layer ERDDAP subset schema."""
    if not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_BYTES:
        raise ValueError("Current CSV must be nonempty and within 1 MB")
    try:
        reader = csv.reader(io.StringIO(payload.decode("utf-8")))
        if tuple(next(reader, [])) != HEADERS or tuple(next(reader, [])) != UNITS:
            raise ValueError("Unexpected current CSV columns or units")
        records = []
        expected_times = {START_UTC, "2026-10-17T21:00:00Z", END_UTC}
        identities = set()
        for row in reader:
            if len(records) >= MAX_ROWS or len(row) != 6:
                raise ValueError("Current CSV row budget or schema violated")
            when, depth, latitude, longitude, east, north = row
            if when not in expected_times:
                raise ValueError("Unexpected current valid time")
            depth, latitude, longitude, east, north = map(
                float, (depth, latitude, longitude, east, north)
            )
            if (not all(map(math.isfinite, (depth, latitude, longitude)))
                    or depth != 0.25 or not 20.45 <= latitude <= 21.55
                    or not -158.85 <= longitude <= -157.35):
                raise ValueError("Current depth or geographic subset is invalid")
            if (math.isinf(east) or math.isinf(north)
                    or (math.isfinite(east) and abs(east) > 10)
                    or (math.isfinite(north) and abs(north) > 10)):
                raise ValueError("Current velocity exceeds its finite m/s budget")
            identity = (when, latitude, longitude)
            if identity in identities:
                raise ValueError("Duplicate current grid sample")
            identities.add(identity)
            records.append((when, latitude, longitude, east, north))
        if not records:
            raise ValueError("Current CSV is empty")
        times = sorted({row[0] for row in records})
        latitude = sorted({row[1] for row in records})
        longitude = sorted({row[2] for row in records})
        if (set(times) != expected_times or len(latitude) < 2 or len(longitude) < 2
                or len(records) != len(times) * len(latitude) * len(longitude)):
            raise ValueError("Current CSV must contain one complete rectilinear three-time grid")
        ti = {value: index for index, value in enumerate(times)}
        yi = {value: index for index, value in enumerate(latitude)}
        xi = {value: index for index, value in enumerate(longitude)}
        shape = (len(times), len(latitude), len(longitude))
        eastward = np.full(shape, np.nan)
        northward = np.full(shape, np.nan)
        for when, lat, lon, east, north in records:
            eastward[ti[when], yi[lat], xi[lon]] = east
            northward[ti[when], yi[lat], xi[lon]] = north
    except (UnicodeDecodeError, csv.Error, OverflowError) as error:
        raise ValueError("Malformed current CSV") from error
    valid = np.isfinite(eastward) & np.isfinite(northward)
    if not valid.any():
        raise ValueError("Current subset contains no finite paired velocity samples")
    return OceanField(
        np.array([np.datetime64(value.removesuffix("Z")) for value in times]),
        np.array(longitude), np.array(latitude),
        np.where(valid, eastward, np.nan), np.where(valid, northward, np.nan),
        valid, 0.25, metadata or {},
    )


def load_current_snapshot(data_dir: str | Path | None = None) -> tuple[OceanField, dict]:
    """Verify a frozen manifest and both source files; never contact a remote API."""
    directory = Path(data_dir) if data_dir is not None else DATA_DIR
    manifest_path = directory / MANIFEST_FILE
    if not manifest_path.is_file() or manifest_path.stat().st_size > 30_000:
        raise ValueError("Current snapshot receipt is unavailable or exceeds its byte budget")
    manifest_bytes = manifest_path.read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Current snapshot receipt differs from the reviewed immutable manifest")
    manifest = json.loads(manifest_bytes)
    source_path, info_path = directory / FILE_NAME, directory / METADATA_FILE
    for path, key, limit in ((source_path, "csv", MAX_BYTES),
                             (info_path, "metadata", MAX_METADATA_BYTES)):
        expected = manifest["files"][key]
        if (not path.is_file() or path.stat().st_size > limit
                or path.stat().st_size != expected["bytes"]):
            raise ValueError("Current snapshot source is unavailable or changed size")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected["sha256"]:
            raise ValueError("Current snapshot source differs from the reviewed bytes")
    info = _metadata(info_path.read_bytes())
    field = parse_current_csv(source_path.read_bytes(), metadata={
        "dataset": DATASET_ID, "product": "PacIOOS ROMS Main Hawaiian Islands",
        "title": info["title"], "source_url": SOURCE_URL,
        "u_variable": "u", "v_variable": "v", "velocity_units": "m/s",
        "sha256": manifest["files"]["csv"]["sha256"],
        "retrieved_at_utc": manifest["captured_at_utc"], "issued_at_utc": None,
        "license": info["license"], "data_kind": "model_output_not_plastic_ground_truth",
    })
    summary = field.summary()
    if (summary["shape"] != manifest["grid"]["shape"]
            or summary["valid_sample_count"] != manifest["grid"]["valid_sample_count"]):
        raise ValueError("Current snapshot grid differs from its reviewed receipt")
    return field, manifest


def _method_sha256() -> str:
    digest = hashlib.sha256()
    for name in ("advection.py", "field.py", "current_forecast.py"):
        digest.update(name.encode() + b"\0")
        digest.update(Path(__file__).with_name(name).read_bytes())
    return digest.hexdigest()


def _separation(left: dict, right: dict) -> float:
    metres_lon, metres_lat = _wgs84_metres_per_degree(
        (left["latitude_deg"] + right["latitude_deg"]) / 2
    )
    return math.hypot(
        (left["longitude_deg"] - right["longitude_deg"]) * metres_lon,
        (left["latitude_deg"] - right["latitude_deg"]) * metres_lat,
    )


def run_current_forecast() -> dict:
    """Run a fixed offshore release through real changing u/v, without measurements."""
    field, manifest = load_current_snapshot()
    release = {"latitude_deg": 21.0, "longitude_deg": -158.0,
               "start_time_utc": START_UTC, "horizon_s": 21600.0}
    dynamic = advect_current(field, **release)
    initial_u, initial_v = CurrentSampler(field).sample(21.0, -158.0, 0.0)
    constant = OceanField(
        field.time_utc, field.longitude_deg, field.latitude_deg,
        np.where(field.valid_mask, initial_u, np.nan),
        np.where(field.valid_mask, initial_v, np.nan), field.valid_mask,
        field.selected_depth_m,
        {**field.metadata, "data_kind": "constant_initial_current_persistence_baseline"},
    )
    persistence = advect_current(constant, **release)
    completed = dynamic["status"] == persistence["status"] == "COMPLETED"
    status = "COMPLETED" if completed else (
        "PARTIAL" if any(row["completed_horizon_s"] > 0 for row in (dynamic, persistence))
        else "UNSUPPORTED"
    )
    # A fixed local display domain follows both complete/partial predictions.
    # The 3x3 display samples are interpolated model velocities, not finer data.
    points = dynamic["track"] + persistence["track"]
    plot_latitude = [point["latitude_deg"] for point in points] or [release["latitude_deg"]]
    plot_longitude = [point["longitude_deg"] for point in points] or [release["longitude_deg"]]
    sample_latitudes = np.linspace(min(plot_latitude), max(plot_latitude), 3)
    sample_longitudes = np.linspace(min(plot_longitude), max(plot_longitude), 3)
    sampler = CurrentSampler(field)
    frames = []
    for t, when in enumerate(field.time_utc):
        vectors = []
        seconds = float((when - field.time_utc[0]) / np.timedelta64(1, "s"))
        for latitude in sample_latitudes:
            for longitude in sample_longitudes:
                try:
                    east, north = sampler.sample(float(latitude), float(longitude), seconds)
                except ValueError:
                    # Unsupported source cells have no display arrow. They are
                    # never imputed with zero or bridged across the mask.
                    continue
                vectors.append({
                    "latitude_deg": float(latitude), "longitude_deg": float(longitude),
                    "eastward_m_s": east, "northward_m_s": north,
                })
        frames.append({"time_utc": str(when) + "Z", "vectors": vectors})
    archived = datetime.now(UTC) > datetime.fromisoformat(END_UTC)
    summary = field.summary()
    return {
        "schema_version": 1, "kind": "CURRENT_FORCED_PREVIEW", "status": status,
        "mode": "archived_forecast_snapshot" if archived else "forecast_snapshot",
        "snapshot_sha256": manifest["files"]["csv"]["sha256"],
        "manifest_sha256": MANIFEST_SHA256, "method_sha256": _method_sha256(),
        "release": release, "dynamic": dynamic, "persistence": persistence,
        "forcing": {
            "dataset_id": DATASET_ID, "source_url": SOURCE_URL,
            "metadata_url": METADATA_URL, "product_url": PRODUCT_URL,
            "attribution": ATTRIBUTION, "captured_at_utc": manifest["captured_at_utc"],
            "valid_start_utc": START_UTC, "valid_end_utc": END_UTC,
            "model_issue_time_utc": None,
            "aggregation": "FMRC Best Dataset; not a separately pinned single model run",
            "future_valid_times_at_acquisition": manifest["future_valid_times_at_acquisition"],
            "depth_m": 0.25, "nominal_grid_spacing_m": 4000,
            "grid_spacing_m": {
                "east_west": summary["approx_east_west_grid_spacing_m_at_midlatitude"],
                "north_south": summary["approx_north_south_grid_spacing_m"],
            },
            "time_step_s": 10800, "grid_shape": summary["shape"],
            "geographic_bounds": {
                "latitude_deg": summary["latitude_range_deg"],
                "longitude_deg": summary["longitude_range_deg"],
            },
            "valid_sample_count": summary["valid_sample_count"],
            "invalid_sample_count": summary["invalid_sample_count"],
            "license": field.metadata["license"],
        },
        "method": {
            "equation": "dX/dt = u(X,t)",
            "solver": "RK4 with local WGS84 metric derivatives",
            "spatial_interpolation": "bilinear", "temporal_interpolation": "linear",
            "baseline": "Frozen initial east/north current; same solver and forcing domain",
            "initial_current_eastward_m_s": initial_u,
            "initial_current_northward_m_s": initial_v,
            "algorithm_sha256": hashlib.sha256(Path(advection.__file__).read_bytes()).hexdigest(),
        },
        "vector_frames": frames,
        "vector_sampling": "interpolated_display_samples_not_finer_observations",
        "vector_display_bounds": {
            "latitude_deg": [min(plot_latitude), max(plot_latitude)],
            "longitude_deg": [min(plot_longitude), max(plot_longitude)],
        },
        "endpoint_separation_m": _separation(dynamic["track"][-1], persistence["track"][-1])
        if completed else None,
        "endpoint_separation_description": "Difference between two predictions, not forecast error",
        "validation": {
            "measured_track_available": False, "physical_validation": False,
            "plastic_motion_validated": False, "forecast_skill_established": False,
            "tank_flow_used": False, "heldout_buoy_positions_used": False,
            "ade_m": None, "fde_m": None,
        },
        "limitations": LIMITATIONS + ([
            "The valid-time window has ended; this is an archived forecast snapshot, not live water conditions."
        ] if archived else []),
    }
