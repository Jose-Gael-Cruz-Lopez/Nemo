"""Bounded NOAA GDP ERDDAP subsets with geographic units preserved."""

import csv
from collections import defaultdict
from datetime import datetime
from urllib.parse import quote

from pydantic import Field, model_validator

from apps.core.reeftrace_core.contracts import Contract

from .common import cache_root, download, save_import, sha256, write_json

BASE = "https://erddap.aoml.noaa.gov/gdp/erddap"
DATASET = "drifter_6hour_qc"


class DrifterQuery(Contract):
    start: datetime
    end: datetime
    minimum_latitude: float = Field(ge=-90, le=90)
    maximum_latitude: float = Field(ge=-90, le=90)
    minimum_longitude: float = Field(ge=-180, le=180)
    maximum_longitude: float = Field(ge=-180, le=180)

    @model_validator(mode="after")
    def bounds(self):
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("Use timezone-aware UTC timestamps")
        if not 0 < (self.end - self.start).total_seconds() <= 31 * 86400:
            raise ValueError("Request between zero and 31 days")
        if (
            self.minimum_latitude >= self.maximum_latitude
            or self.minimum_longitude >= self.maximum_longitude
        ):
            raise ValueError("Use ordered bounds; split antimeridian requests into two regions")
        return self


def query_url(query):
    clauses = [
        "ID,time,latitude,longitude",
        f"time>={query.start.isoformat()}",
        f"time<={query.end.isoformat()}",
        f"latitude>={query.minimum_latitude}",
        f"latitude<={query.maximum_latitude}",
        f"longitude>={query.minimum_longitude}",
        f"longitude<={query.maximum_longitude}",
    ]
    return BASE + "/tabledap/" + DATASET + ".csv?" + quote("&".join(clauses), safe=",&=><:")


def read_tracks(path):
    groups = defaultdict(list)
    rejected = 0
    with open(path, newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"ID", "time", "latitude", "longitude"} <= set(reader.fieldnames or []):
            raise ValueError("NOAA schema changed: expected ID,time,latitude,longitude")
        for row in reader:
            if row["time"] == "UTC":
                continue  # ERDDAP's CSV units row, not a buoy observation.
            try:
                timestamp = datetime.fromisoformat(row["time"])
                lat, lon = float(row["latitude"]), float(row["longitude"])
                if (
                    timestamp.tzinfo is None
                    or not -90 <= lat <= 90
                    or not -180 <= lon <= 180
                    or not row["ID"]
                ):
                    raise ValueError("Invalid coordinate/time")
                point = {"time": timestamp.isoformat(), "latitude": lat, "longitude": lon}
                groups[row["ID"]].append(point)
            except (TypeError, ValueError):
                rejected += 1
    features = []
    for drifter, points in sorted(groups.items()):
        unique = {p["time"]: p for p in points}
        points = sorted(unique.values(), key=lambda p: p["time"])
        # Keep geographic records; never relabel degrees as centimeters.
        features.append({"drifter_id": drifter, "points": points})
    return {
        "units": {"latitude": "degrees_north", "longitude": "degrees_east", "time": "UTC"},
        "trajectories": features,
        "valid_rows": sum(len(f["points"]) for f in features),
        "rejected_rows": rejected,
        "note": "Quality-controlled six-hour interpolated buoy positions; not plastic or tank observations.",
    }


def import_noaa(query, client=None, store=None):
    query = DrifterQuery.model_validate(query)
    root = cache_root() / "noaa-gdp"
    encoded = query.model_dump(mode="json")
    import hashlib
    import json

    directory = (
        root
        / "downloads"
        / hashlib.sha256(json.dumps(encoded, sort_keys=True).encode()).hexdigest()[:16]
    )
    metadata = download(
        BASE + "/info/" + DATASET + "/index.json", directory / "metadata.json", client=client
    )
    csv_path = download(query_url(query), directory / "positions.csv", client=client)
    # Freeze content-addressed artifacts; later provider revisions cannot replace old evidence.
    import shutil

    frozen = root / (sha256(csv_path)[:16] + "-" + sha256(metadata)[:8])
    frozen.mkdir(parents=True, exist_ok=True)
    for source in (metadata, csv_path):
        destination = frozen / source.name
        if not destination.exists():
            shutil.copyfile(source, destination)
    metadata, csv_path = frozen / "metadata.json", frozen / "positions.csv"
    directory = frozen
    tracks = read_tracks(csv_path)
    if not tracks["valid_rows"]:
        raise ValueError("No valid NOAA observations in this subset; choose another region/date")
    path = directory / "trajectories.json"
    write_json(path, tracks)
    summary = {
        "dataset": DATASET,
        "drifters": len(tracks["trajectories"]),
        "valid_rows": tracks["valid_rows"],
        "rejected_rows": tracks["rejected_rows"],
        "units": tracks["units"],
        "preview": tracks["trajectories"][:5],
        "data_sha256": sha256(csv_path),
    }
    return save_import(
        "noaa-gdp",
        encoded,
        summary,
        [metadata, csv_path, path],
        "https://www.aoml.noaa.gov/phod/gdp/interpolated/data/all.php",
        store,
    )
