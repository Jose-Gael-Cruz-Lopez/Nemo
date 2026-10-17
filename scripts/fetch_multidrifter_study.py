"""Explicit bounded NOAA acquisition under an already frozen, unscored protocol.

No forecast, fit, model selection, provider, account or application state is used.
The metadata-selected group manifest is frozen before trajectory requests begin.
Existing files are never overwritten, and failed selections are not replaced.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import httpx

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_SHA256 = "e8ad0cec2b48fa0e516a03b0bc14c42ba2f055439e534878f3db55def4d25845"
DEFAULT_DIRECTORY = ROOT / "data/public/noaa-multidrifter-v1"


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


def _save(path, payload):
    with path.open("xb") as stream:
        stream.write(payload)


def _json(path, value):
    payload = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    _save(path, payload)
    _save(path.with_suffix(".sha256"), (_sha(payload) + "\n").encode())
    return _sha(payload)


def _fetch(client, url, maximum):
    retrieved = datetime.now(UTC).isoformat()
    try:
        with client.stream("GET", url, follow_redirects=False) as response:
            payload = bytearray()
            for chunk in response.iter_bytes():
                payload.extend(chunk)
                if len(payload) > maximum:
                    return {"status": "FETCH_FAILED", "reason": "RESPONSE_SIZE_BUDGET",
                            "retrieved_at_utc": retrieved, "http_status": response.status_code}, None
            result = {"status": "DOWNLOADED" if response.status_code == 200 else "FETCH_FAILED",
                "reason": None if response.status_code == 200 else "HTTP_ERROR",
                "retrieved_at_utc": retrieved, "http_status": response.status_code,
                "bytes": len(payload), "sha256": _sha(payload)}
            return result, bytes(payload)
    except httpx.HTTPError as error:
        return {"status": "FETCH_FAILED", "reason": type(error).__name__,
                "retrieved_at_utc": retrieved, "http_status": None}, None


def _metadata_rows(payload, protocol, block):
    rows = list(csv.reader(io.StringIO(payload.decode("utf-8"))))
    columns = protocol["selection"]["metadata_columns"]
    if len(rows) < 2 or rows[0] != columns or rows[1][1:4] != ["UTC", "degrees_north", "degrees_east"]:
        raise ValueError("Metadata snapshot schema or units differ from the frozen query")
    result = {}
    for row in rows[2:]:
        if len(row) != len(columns):
            raise ValueError("Metadata snapshot row width is invalid")
        item = dict(zip(columns, row, strict=True))
        drifter_id = item["ID"]
        if not drifter_id.isascii() or not drifter_id.isdigit() or str(int(drifter_id)) != drifter_id:
            raise ValueError("Metadata snapshot ID is not a canonical numeric group")
        lat, lon = float(item["latitude"]), float(item["longitude"])
        if (item["time"] != block["start_utc"]
                or not block["latitude_min"] <= lat <= block["latitude_max"]
                or not block["longitude_min"] <= lon <= block["longitude_max"]
                or drifter_id in result):
            raise ValueError("Metadata snapshot does not match its frozen block or has duplicate IDs")
        result[drifter_id] = item
    return result


def _url(base, query):
    return base + "?" + quote(query, safe=",&=")


def acquire_study(directory=DEFAULT_DIRECTORY, *, client=None):
    directory = Path(directory)
    raw_protocol = (directory / "protocol.json").read_bytes()
    if _sha(raw_protocol) != PROTOCOL_SHA256 or (directory / "protocol.sha256").read_text().strip() != PROTOCOL_SHA256:
        raise ValueError("Acquisition requires the unchanged preregistered protocol")
    if (directory / "selection.json").exists() or (directory / "manifest.json").exists():
        raise ValueError("A frozen selection or acquisition already exists; never overwrite or replace its outcomes")
    protocol = json.loads(raw_protocol)
    raw = directory / "raw"
    raw.mkdir(exist_ok=True)
    owned_client = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(protocol["budgets"]["timeout_s"], connect=10))
    try:
        source = protocol["source"]
        info_receipt, info_bytes = _fetch(client, source["metadata_url"], protocol["budgets"]["metadata_info_bytes"])
        if info_receipt["status"] != "DOWNLOADED":
            raise ValueError("Official dataset metadata is unavailable; acquisition stopped before selection")
        _save(raw / "dataset-info.json", info_bytes)
        info = json.loads(info_bytes)
        attributes = {row[2]: row[4] for row in info["table"]["rows"]
                      if row[0] == "attribute" and row[1] == "NC_GLOBAL"}
        if ("Creative Commons Attribution 4.0" not in attributes.get("license", "")
                or source["license_url"] not in attributes.get("license", "")
                or attributes.get("doi") != source["product_doi"]):
            raise ValueError("Official NOAA license/DOI metadata no longer matches the frozen protocol")
        blocks, selected = [], []
        reserved = set(protocol["selection"]["excluded_entire_drifter_ids"])
        used = set()
        for block in protocol["selection"]["blocks"]:
            query = ",".join(protocol["selection"]["metadata_columns"]) + (
                f'&time={block["start_utc"]}&latitude>={block["latitude_min"]}'
                f'&latitude<={block["latitude_max"]}&longitude>={block["longitude_min"]}'
                f'&longitude<={block["longitude_max"]}')
            url = _url(source["base_url"], query)
            receipt, payload = _fetch(client, url, protocol["budgets"]["metadata_bytes_per_block"])
            receipt.update(block_id=block["id"], source_url=url,
                           raw_path=f'raw/metadata-{block["id"]}.csv')
            if payload is not None:
                _save(directory / receipt["raw_path"], payload)
            candidates = {}
            if receipt["status"] == "DOWNLOADED":
                try:
                    candidates = _metadata_rows(payload, protocol, block)
                except (ValueError, KeyError) as error:
                    receipt.update(status="METADATA_INVALID", reason=str(error))
            eligible = sorted(set(candidates) - reserved, key=int)
            chosen = eligible[:protocol["selection"]["target_per_block"]]
            receipt.update(candidate_count=len(candidates), eligible_candidate_count=len(eligible),
                           selected_ids=chosen, reserved_excluded_ids=sorted(set(candidates) & reserved))
            blocks.append(receipt)
            for drifter_id in chosen:
                if drifter_id in used:
                    raise ValueError("Frozen metadata rule selected a drifter in two groups; refuse reassignment")
                used.add(drifter_id)
                selected.append({"drifter_id": drifter_id, "block_id": block["id"],
                    "split_label": "evaluation", "start_utc": block["start_utc"], "end_utc": block["end_utc"],
                    "selection_metadata": candidates[drifter_id]})
        selection = {"schema_version": 1, "study_id": protocol["study_id"],
            "protocol_sha256": PROTOCOL_SHA256, "frozen_at_utc": datetime.now(UTC).isoformat(),
            "evaluation_outcomes_computed": False, "trajectory_payloads_fetched": False,
            "dataset_metadata": {**info_receipt, "source_url": source["metadata_url"], "raw_path": "raw/dataset-info.json"},
            "blocks": blocks, "groups": selected,
            "development_only_drifter_ids": sorted(reserved), "unselected_groups": "excluded"}
        selection_hash = _json(directory / "selection.json", selection)
        # This detached receipt exists before any trajectory request or forecast.
        work = ROOT / "work"
        work.mkdir(exist_ok=True)
        _json(work / "multidrifter-selection-freeze.json", {
            "protocol_sha256": PROTOCOL_SHA256, "selection_sha256": selection_hash,
            "frozen_at_utc": selection["frozen_at_utc"], "evaluation_outcomes_computed": False,
            "selected_ids": [group["drifter_id"] for group in selected]})
        trajectories = []
        for group in selected:
            query = ",".join(protocol["preprocessing"]["csv_columns"]) + (
                f'&ID="{group["drifter_id"]}"&time>={group["start_utc"]}&time<={group["end_utc"]}')
            url = _url(source["base_url"], query)
            receipt, payload = _fetch(client, url, protocol["budgets"]["trajectory_bytes"])
            path = f'raw/drifter-{group["drifter_id"]}-{group["start_utc"][:10]}.csv'
            if payload is not None:
                _save(directory / path, payload)
            trajectories.append({**group, **receipt, "source_url": url, "raw_path": path,
                "license_name": source["license_name"], "license_url": source["license_url"],
                "preprocessing": "original ERDDAP bytes; no model fit, filtering or interpolation in acquisition"})
        manifest = {"schema_version": 1, "study_id": protocol["study_id"],
            "protocol_sha256": PROTOCOL_SHA256, "selection_sha256": selection_hash,
            "acquired_at_utc": datetime.now(UTC).isoformat(), "evaluation_outcomes_computed": False,
            "source": source, "trajectories": trajectories, "no_replacements": True}
        manifest_hash = _json(directory / "manifest.json", manifest)
        return {"protocol_sha256": PROTOCOL_SHA256, "selection_sha256": selection_hash,
            "manifest_sha256": manifest_hash, "selected_ids": [group["drifter_id"] for group in selected],
            "downloaded": sum(row["status"] == "DOWNLOADED" for row in trajectories),
            "failed": sum(row["status"] != "DOWNLOADED" for row in trajectories),
            "evaluation_outcomes_computed": False}
    finally:
        if owned_client:
            client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIRECTORY)
    args = parser.parse_args()
    print(json.dumps(acquire_study(args.output_dir), indent=2))


if __name__ == "__main__":
    main()
