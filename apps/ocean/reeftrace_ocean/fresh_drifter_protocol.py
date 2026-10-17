"""Content-pinned fresh-study design and raw metadata identity helpers; no fitting."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = ROOT / "data/public/noaa-fresh-drifter-v2"
PROTOCOL_SHA256 = "0f34c38c8cb02a6934de6764d6ec958042eccacdf6b0081d7ec71bbffb570d3d"
MODEL_IDS = ("stationary", "last_drift", "mean_drift", "ridge_ar1", "kalman_cv")
LABELS = {
    "stationary": "Stationary position persistence",
    "last_drift": "Last observed drift",
    "mean_drift": "Mean observed drift",
    "ridge_ar1": "Own-prefix ridge velocity AR(1)",
    "kalman_cv": "Fixed-noise constant-velocity Kalman",
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


KEYS = {
    "ID",
    "drifter_id",
    "drifter_ids",
    "excluded_entire_drifter_ids",
    "development_only_drifter_ids",
    "development_only",
    "excluded_drifter_ids",
}


def existing_fixture_inventory(root=ROOT):
    """Include exposed metadata IDs as well as scored trajectories; no network."""
    identifiers, files = set(), []

    def add(value):
        if isinstance(value, str) and value.isascii() and value.isdigit() and int(value) > 0:
            identifiers.add(str(int(value)))
        elif isinstance(value, list):
            for item in value:
                add(item)

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in KEYS:
                    add(item)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    for path in sorted((root / "data/public").rglob("*")):
        if (
            not path.is_file()
            or path.suffix not in {".csv", ".json"}
            or any(part.startswith("noaa-fresh-drifter-v") for part in path.parts)
        ):
            continue
        raw = path.read_bytes()
        files.append(
            {"path": path.relative_to(root).as_posix(), "sha256": sha(raw), "bytes": len(raw)}
        )
        if path.suffix == ".json":
            walk(json.loads(raw))
        else:
            with path.open(newline="") as stream:
                rows = csv.reader(stream)
                header = next(rows, [])
                if "ID" in header:
                    index = header.index("ID")
                    for row in rows:
                        if len(row) > index:
                            add(row[index])
    return {
        "schema_version": 1,
        "scope": "ALL_EXISTING_PUBLIC_CSV_JSON_INCLUDING_EXPOSED_METADATA",
        "reserved_gdp_ids": sorted(identifiers, key=int),
        "fixture_files": files,
    }


def canonical_json(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def save_json(path, value):
    raw = canonical_json(value)
    with Path(path).open("xb") as stream:
        stream.write(raw)
    with Path(path).with_suffix(".sha256").open("x") as stream:
        stream.write(sha(raw) + "\n")
    return sha(raw)


def read_bytes(path, maximum=4_194_304):
    with Path(path).open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("Fresh-study artifact exceeds byte budget")
    return raw


def pinned_json(directory, name, expected=None):
    raw = read_bytes(Path(directory) / (name + ".json"))
    digest = sha(raw)
    if (expected is not None and digest != expected) or read_bytes(
        Path(directory) / (name + ".sha256"), 80
    ).decode().strip() != digest:
        raise ValueError("Fresh-study content hash or detached receipt changed")
    doc = json.loads(raw)
    if not isinstance(doc, dict):
        raise TypeError("Fresh-study JSON must be an object")
    return doc, digest


def load_design(directory=DIRECTORY):
    protocol, h = pinned_json(directory, "protocol", PROTOCOL_SHA256)
    exclusions, e = pinned_json(directory, "exclusions", protocol["exclusions"]["snapshot_sha256"])
    if exclusions != existing_fixture_inventory(ROOT):
        raise ValueError(
            "Exposed public fixture inventory changed after the fresh-study exclusion freeze"
        )
    for path, expected in protocol["models"]["implementation_sha256"].items():
        if sha(read_bytes(ROOT / path)) != expected:
            raise ValueError("Frozen baseline implementation changed")
    if (
        protocol["models"]["ids"] != list(MODEL_IDS)
        or protocol["acquisition_or_scores_computed"] is not False
    ):
        raise ValueError("Fresh-study design identity changed")
    return protocol, exclusions, {"protocol_sha256": h, "exclusions_sha256": e}


def canonical_id(value):
    return (
        isinstance(value, str)
        and value.isascii()
        and value.isdigit()
        and int(value) > 0
        and str(int(value)) == value
    )


def _csv(raw, columns, units):
    try:
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8"))))
    except csv.Error as error:
        raise ValueError("Malformed bounded metadata CSV") from error
    if len(rows) < 2 or rows[0] != columns or rows[1] != units:
        raise ValueError("Frozen metadata CSV columns or units changed")
    if any(len(row) != len(columns) for row in rows[2:]):
        raise ValueError("Metadata CSV row width changed")
    return rows[2:]


def alias_maps(raw):
    rows = _csv(raw, ["ID", "WMO"], ["", ""])
    by_id, by_wmo = {}, {}
    for identifier, wmo in rows:
        if not canonical_id(identifier):
            raise ValueError("Alias table has a noncanonical GDP ID")
        by_id.setdefault(identifier, set())
        if canonical_id(wmo):
            by_id[identifier].add(wmo)
            by_wmo.setdefault(wmo, set()).add(identifier)
    return by_id, by_wmo


def metadata_rows(raw, protocol, block):
    cols = protocol["selection"]["metadata_columns"]
    rows = _csv(
        raw,
        cols,
        protocol["selection"].get(
            "metadata_units", ["", "UTC", "degrees_north", "degrees_east", "", "count", ""]
        ),
    )
    result = {}
    for row in rows:
        item = dict(zip(cols, row, strict=True))
        identifier = item["ID"]
        if not canonical_id(identifier) or identifier in result:
            raise ValueError("Snapshot IDs must be canonical and unique")
        lat, lon = float(item["latitude"]), float(item["longitude"])
        if (
            item["time"] != block["start_utc"]
            or not block["latitude_min"] <= lat <= block["latitude_max"]
            or not block["longitude_min"] <= lon <= block["longitude_max"]
        ):
            raise ValueError("Snapshot row is outside its declared time/space block")
        result[identifier] = item
    return result


def derive_groups(protocol, exclusions, identity_raw, snapshots):
    """No trajectory/forecast inputs; identical rule used for acquisition and replay."""
    reserved = set(exclusions["reserved_gdp_ids"])
    by_id, by_wmo = alias_maps(identity_raw)
    known = set().union(*(by_id.get(i, set()) for i in reserved))
    unresolved = sorted(
        (
            i
            for i in reserved
            if len(by_id.get(i, set())) != 1
            or any(len(by_wmo.get(w, set())) != 1 for w in by_id.get(i, set()))
        ),
        key=int,
    )
    groups, blocks, selected_ids, selected_wmo = [], [], set(), set()
    for block in protocol["selection"]["blocks"]:
        raw = snapshots.get(block["id"])
        candidates = metadata_rows(raw, protocol, block) if raw is not None else {}
        eligible = []
        rejected = {}
        for identifier in sorted(candidates, key=int):
            mapping = by_id.get(identifier, set())
            wmo = next(iter(mapping)) if len(mapping) == 1 else None
            if identifier in reserved:
                reason = "EXPOSED_GDP_ID"
            elif (
                wmo is None
                or len(by_wmo.get(wmo, set())) != 1
                or candidates[identifier]["WMO"] != wmo
            ):
                reason = "MISSING_OR_AMBIGUOUS_NEW_ALIAS"
            elif wmo in known:
                reason = "KNOWN_RESERVED_WMO"
            elif identifier in selected_ids or wmo in selected_wmo:
                reason = "ALREADY_SELECTED_IDENTITY"
            else:
                eligible.append(identifier)
                continue
            rejected[reason] = rejected.get(reason, 0) + 1
        chosen = eligible[: protocol["selection"]["target_per_block"]]
        for rank, identifier in enumerate(chosen, 1):
            wmo = next(iter(by_id[identifier]))
            selected_ids.add(identifier)
            selected_wmo.add(wmo)
            groups.append(
                {
                    "block_id": block["id"],
                    "slot": rank,
                    "drifter_id": identifier,
                    "wmo": wmo,
                    "start_utc": block["start_utc"],
                    "end_utc": block["end_utc"],
                    "selection_metadata": candidates[identifier],
                    "split_label": "evaluation",
                }
            )
        blocks.append(
            {
                "block_id": block["id"],
                "candidate_count": len(candidates),
                "eligible_candidate_count": len(eligible),
                "selected_ids": chosen,
                "rejected_counts": rejected,
            }
        )
    return (
        groups,
        blocks,
        {
            "reserved_gdp_id_count": len(reserved),
            "known_reserved_wmo_count": len(known),
            "unresolved_reserved_alias_ids": unresolved,
            "unresolved_reserved_alias_count": len(unresolved),
            "physical_alias_resolution_verified": not unresolved,
            "statistical_independence": False,
        },
    )


def raw_receipt(directory, receipt):
    path = receipt.get("raw_path")
    if path is None:
        return None
    relative = Path(path)
    if (
        relative.is_absolute()
        or not relative.parts
        or relative.parts[0] != "raw"
        or ".." in relative.parts
    ):
        raise ValueError("Fresh-study raw path escapes its directory")
    raw = read_bytes(Path(directory) / relative)
    if len(raw) != receipt["bytes"] or sha(raw) != receipt["sha256"]:
        raise ValueError("Fresh-study raw payload changed")
    return raw
