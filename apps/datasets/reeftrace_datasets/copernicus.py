"""Optional Copernicus subset and NetCDF preview; no tank profile conversion."""

import math
from datetime import datetime

import numpy as np
from pydantic import Field, model_validator

from apps.core.reeftrace_core.contracts import Contract

from .common import cache_root, save_import, write_json


class MarineQuery(Contract):
    dataset_id: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_.-]+$")
    dataset_version: str | None = None
    minimum_longitude: float = Field(ge=-180, le=180)
    maximum_longitude: float = Field(ge=-180, le=180)
    minimum_latitude: float = Field(ge=-90, le=90)
    maximum_latitude: float = Field(ge=-90, le=90)
    start_datetime: datetime
    end_datetime: datetime

    @model_validator(mode="after")
    def bounds(self):
        if self.start_datetime.tzinfo is None or self.end_datetime.tzinfo is None:
            raise ValueError("Use timezone-aware dates")
        if not 0 < (self.end_datetime - self.start_datetime).total_seconds() <= 7 * 86400:
            raise ValueError("Start with a subset of at most seven days")
        if (
            not 0 < self.maximum_latitude - self.minimum_latitude <= 10
            or not 0 < self.maximum_longitude - self.minimum_longitude <= 10
        ):
            raise ValueError("Start with an ordered bounding box no larger than 10 by 10 degrees")
        return self


def subset_arguments(query, directory):
    return {
        **query.model_dump(exclude_none=True),
        "variables": ["uo", "vo"],
        "minimum_depth": 0,
        "maximum_depth": 1,
        "output_directory": str(directory),
        "output_filename": "currents.nc",
        "overwrite": False,
    }


def summarize_netcdf(path):
    import xarray as xr

    with xr.open_dataset(path) as dataset:
        if not {"uo", "vo"} <= set(dataset.data_vars):
            raise ValueError("Expected eastward uo and northward vo current variables")
        if not {"latitude", "longitude"} <= set(dataset.coords):
            raise ValueError("Only geographic latitude/longitude products are supported")
        selected = dataset[["uo", "vo"]]
        selected_time = None
        selected_depth = None
        if "time" in selected.dims:
            selected_time = str(selected.time.values[0])
            selected = selected.isel(time=0)
        if "depth" in selected.dims:
            if selected.depth.attrs.get("units") not in {"m", "meters", "metres", "meter", "metre"}:
                raise ValueError("Depth units must explicitly be meters")
            depth_index = int(np.argmin(np.abs(selected.depth.values)))
            selected_depth = float(selected.depth.values[depth_index])
            selected = selected.isel(depth=depth_index)
        if set(selected.uo.dims) != {"latitude", "longitude"} or set(selected.vo.dims) != {
            "latitude",
            "longitude",
        }:
            raise ValueError("Unsupported current array dimensions")
        selected = selected.isel(
            latitude=slice(None, None, max(1, math.ceil(selected.sizes["latitude"] / 24))),
            longitude=slice(None, None, max(1, math.ceil(selected.sizes["longitude"] / 24))),
        )
        units = [selected[v].attrs.get("units") for v in ["uo", "vo"]]
        if any(unit not in {"m/s", "m s-1", "m s^-1", "m s**-1"} for unit in units):
            raise ValueError("Current units must explicitly be meters per second")
        lon, lat = np.meshgrid(selected.longitude.values, selected.latitude.values)
        u = selected.uo.transpose("latitude", "longitude").values
        v = selected.vo.transpose("latitude", "longitude").values
        valid = np.isfinite(u) & np.isfinite(v) & np.isfinite(lat) & np.isfinite(lon)
        valid &= (lat >= -90) & (lat <= 90) & (lon >= -180) & (lon <= 180)
        vectors = [
            {
                "longitude": float(lon[i, j]),
                "latitude": float(lat[i, j]),
                "eastward_m_s": float(u[i, j]),
                "northward_m_s": float(v[i, j]),
            }
            for i, j in zip(*np.nonzero(valid))
        ]
        return {
            "units": {"coordinates": "geographic degrees", "velocity": "m/s"},
            "selected_time": selected_time,
            "selected_depth_m": selected_depth,
            "vectors": vectors,
            "valid_sampled_vectors": len(vectors),
            "missing_sampled_vectors": int(valid.size - valid.sum()),
            "preview_only": True,
            "field_attribution_validated": False,
        }


def import_netcdf(path, dataset_id, dataset_version=None, store=None, subset_query=None):
    summary = summarize_netcdf(path)
    if not summary["valid_sampled_vectors"]:
        raise ValueError("No finite current vectors in imported subset")
    from .common import sha256

    directory = cache_root() / "copernicus" / sha256(path)[:16]
    directory.mkdir(parents=True, exist_ok=True)
    import shutil

    frozen = directory / "currents.nc"
    if not frozen.exists():
        shutil.copyfile(path, frozen)
    preview = directory / "preview.json"
    write_json(preview, summary)
    return save_import(
        "copernicus",
        {"dataset_id": dataset_id, "dataset_version": dataset_version, "subset": subset_query},
        summary,
        [frozen, preview],
        "https://marine.copernicus.eu/",
        store,
    )


def fetch_subset(query, dry_run=True, store=None):
    import copernicusmarine

    query = MarineQuery.model_validate(query)
    import hashlib

    directory = (
        cache_root()
        / "copernicus"
        / hashlib.sha256(query.model_dump_json().encode()).hexdigest()[:16]
    )
    arguments = subset_arguments(query, directory)
    copernicusmarine.subset(**arguments, dry_run=dry_run)
    if dry_run:
        return {
            "dry_run": True,
            "downloaded": False,
            "dataset_id": query.dataset_id,
            "message": "Toolbox preview completed. Rerun with --download after checking size, product and licence.",
        }
    record = import_netcdf(
        directory / "currents.nc",
        query.dataset_id,
        query.dataset_version,
        store,
        query.model_dump(mode="json"),
    )
    return record
