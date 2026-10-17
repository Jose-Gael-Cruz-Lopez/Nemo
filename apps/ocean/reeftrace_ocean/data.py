"""NOAA ERDDAP CSV reader. These are observations of buoys, not plastic sources."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

NOAA_COLUMNS = ("ID", "time", "latitude", "longitude", "ve", "vn", "err_ve", "err_vn")
NOAA_UNITS = ("", "UTC", "degrees_north", "degrees_east", "m/s", "m/s", "m/s", "m/s")


def metres_per_second_to_cm_per_second(values):
    """Convert velocity units only. This does not turn longitude/latitude into tank XY."""
    return np.asarray(values, dtype=float) * 100.0


@dataclass(frozen=True)
class DrifterRecord:
    drifter_id: str
    time_utc: datetime
    latitude_deg: float
    longitude_deg: float
    eastward_m_s: float
    northward_m_s: float
    eastward_uncertainty_m_s: float
    northward_uncertainty_m_s: float


def parse_drifter_csv(text: str) -> list[DrifterRecord]:
    """Require the declared ERDDAP schema, unit row, UTC times and finite data.

    No random train/test split, interpolation, clipping, source labels or claimed
    prediction validation is performed here. NOAA uncertainty columns are retained.
    """
    rows = csv.reader(io.StringIO(text))
    if tuple(next(rows, [])) != NOAA_COLUMNS or tuple(next(rows, [])) != NOAA_UNITS:
        raise ValueError("Expected NOAA GDP columns and ERDDAP units row")
    records = []
    last_time_by_id: dict[str, datetime] = {}
    for row in rows:
        if not row:
            continue
        if len(row) != len(NOAA_COLUMNS):
            raise ValueError("Unexpected NOAA GDP CSV row length")
        try:
            when = datetime.fromisoformat(row[1])
            numeric = np.asarray(row[2:], dtype=float)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid NOAA GDP timestamp or numeric value") from exc
        if when.utcoffset() != UTC.utcoffset(when):
            raise ValueError("NOAA time must be timezone-aware UTC")
        if (
            not np.isfinite(numeric).all()
            or (np.abs(numeric) >= 1e20).any()
            or (numeric == -999999.0).any()
        ):
            raise ValueError("NOAA GDP missing/non-finite values require explicit handling")
        lat, lon, east, north, err_east, err_north = numeric.tolist()
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Geographic coordinates out of range")
        if min(err_east, err_north) < 0:
            raise ValueError("Negative uncertainty or missing-value sentinel")
        if not row[0] or when <= last_time_by_id.get(row[0], datetime.min.replace(tzinfo=UTC)):
            raise ValueError("Each drifter needs an ID and strictly increasing timestamps")
        last_time_by_id[row[0]] = when
        records.append(DrifterRecord(row[0], when, lat, lon, east, north, err_east, err_north))
    if not records:
        raise ValueError("No drifter records")
    return records


def load_drifter_csv(path: str | Path) -> list[DrifterRecord]:
    return parse_drifter_csv(Path(path).read_text(encoding="utf-8"))
