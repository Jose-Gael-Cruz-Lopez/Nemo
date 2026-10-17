"""Bounded, immutable NOAA acquisition for a separately preregistered extension.

No forecast or outcome is examined. Previously viewed IDs stay excluded, selection
is pinned before trajectory downloads, and original v1 data are never modified.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from scripts.fetch_multidrifter_study import _fetch, _json, _metadata_rows, _save, _sha, _url

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "data/public/noaa-indian-extension-v1"
PROTOCOL_SHA256 = "e07c5acef71c08ae0bb4e39fa94e904cd9d5a7bea9b7fab5c7e785d6ae6ce2f2"


def acquire_extension(directory=DIRECTORY, *, client=None):
    directory = Path(directory)
    payload = (directory / "protocol.json").read_bytes()
    if (_sha(payload) != PROTOCOL_SHA256
            or (directory / "protocol.sha256").read_text().strip() != PROTOCOL_SHA256):
        raise ValueError("Extension protocol differs from its pre-acquisition receipt")
    if (directory / "selection.json").exists() or (directory / "manifest.json").exists():
        raise ValueError("Never overwrite or replace a frozen extension acquisition")
    protocol = json.loads(payload)
    source, block = protocol["source"], protocol["selection"]["blocks"][0]
    reserved = set(protocol["selection"]["excluded_entire_drifter_ids"])
    raw = directory / "raw"
    raw.mkdir(exist_ok=True)
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(40, connect=10))
    try:
        snapshot = source["metadata_snapshot"]
        info_bytes = (ROOT / snapshot["path"]).read_bytes()
        if _sha(info_bytes) != snapshot["sha256"]:
            raise ValueError("Previously acquired official metadata snapshot is corrupt")
        info = {"status": "REUSED_PINNED_METADATA", "sha256": snapshot["sha256"],
                "bytes": len(info_bytes), "retrieved_at_utc": snapshot["retrieved_at_utc"],
                "freshly_downloaded": False}
        attributes = {row[2]: row[4] for row in json.loads(info_bytes)["table"]["rows"]
                      if row[0] == "attribute" and row[1] == "NC_GLOBAL"}
        if (source["license_url"] not in attributes.get("license", "")
                or attributes.get("doi") != source["product_doi"]):
            raise ValueError("NOAA license or DOI differs from the frozen protocol")
        _save(raw / "dataset-info.json", info_bytes)
        query = ",".join(protocol["selection"]["metadata_columns"]) + (
            f'&time={block["start_utc"]}&latitude>={block["latitude_min"]}'
            f'&latitude<={block["latitude_max"]}&longitude>={block["longitude_min"]}'
            f'&longitude<={block["longitude_max"]}')
        url = _url(source["base_url"], query)
        receipt, metadata = _fetch(client, url, 256_000)
        receipt.update(block_id=block["id"], source_url=url, raw_path="raw/metadata-indian-2010.csv")
        if metadata is not None:
            _save(directory / receipt["raw_path"], metadata)
        candidates = {}
        if receipt["status"] == "DOWNLOADED":
            try:
                candidates = _metadata_rows(metadata, protocol, block)
            except (ValueError, KeyError) as error:
                receipt.update(status="METADATA_INVALID", reason=str(error))
        chosen = sorted(set(candidates) - reserved, key=int)[:2]
        receipt.update(candidate_count=len(candidates), selected_ids=chosen,
                       reserved_excluded_ids=sorted(set(candidates) & reserved))
        groups = [{"drifter_id": value, "block_id": block["id"], "split_label": "evaluation",
                   "start_utc": block["start_utc"], "end_utc": block["end_utc"],
                   "selection_metadata": candidates[value]} for value in chosen]
        selection = {"schema_version": 1, "study_id": protocol["study_id"],
            "protocol_sha256": PROTOCOL_SHA256, "frozen_at_utc": datetime.now(UTC).isoformat(),
            "evaluation_outcomes_computed": False, "trajectory_payloads_fetched": False,
            "dataset_metadata": {**info, "source_url": source["metadata_url"],
                                 "raw_path": "raw/dataset-info.json"},
            "blocks": [receipt], "groups": groups, "excluded_previously_viewed_ids": sorted(reserved)}
        selection_sha = _json(directory / "selection.json", selection)
        trajectories = []
        for group in groups:
            query = ",".join(protocol["preprocessing"]["csv_columns"]) + (
                f'&ID="{group["drifter_id"]}"&time>={group["start_utc"]}&time<={group["end_utc"]}')
            url = _url(source["base_url"], query)
            item, trajectory = _fetch(client, url, 32_000)
            relative = f'raw/drifter-{group["drifter_id"]}-2010-06-01.csv'
            if trajectory is not None:
                _save(directory / relative, trajectory)
            trajectories.append({**group, **item, "source_url": url, "raw_path": relative,
                "license_name": source["license_name"], "license_url": source["license_url"],
                "preprocessing": "Unmodified NOAA ERDDAP bytes; no fitting or interpolation in acquisition"})
        manifest = {"schema_version": 1, "study_id": protocol["study_id"],
            "protocol_sha256": PROTOCOL_SHA256, "selection_sha256": selection_sha,
            "acquired_at_utc": datetime.now(UTC).isoformat(), "evaluation_outcomes_computed": False,
            "source": source, "no_replacements": True, "trajectories": trajectories}
        manifest_sha = _json(directory / "manifest.json", manifest)
        return {"protocol_sha256": PROTOCOL_SHA256, "selection_sha256": selection_sha,
                "manifest_sha256": manifest_sha, "selected_ids": chosen,
                "downloaded": sum(row["status"] == "DOWNLOADED" for row in trajectories),
                "evaluation_outcomes_computed": False}
    finally:
        if owned:
            client.close()


if __name__ == "__main__":
    print(json.dumps(acquire_extension(), indent=2))
