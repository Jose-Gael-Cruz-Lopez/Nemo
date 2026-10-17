"""Explicit fresh NOAA acquisition under a frozen design; no model execution."""

from __future__ import annotations

import argparse
import json
import signal
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import httpx

from apps.ocean.reeftrace_ocean.fresh_drifter_protocol import (
    DIRECTORY,
    derive_groups,
    load_design,
    save_json,
    sha,
)


def utc():
    return datetime.now(UTC).isoformat()


class _DeadlineExpired(TimeoutError):
    """An actual I/O alarm, not only an elapsed-time check between chunks."""


@contextmanager
def _deadline(seconds):
    if threading.current_thread() is not threading.main_thread() or not hasattr(
        signal, "setitimer"
    ):
        raise RuntimeError("Strict acquisition deadlines require a supported main-thread CLI")
    old_handler = signal.getsignal(signal.SIGALRM)
    old_timer = signal.getitimer(signal.ITIMER_REAL)
    if old_timer[0] > 0:
        raise RuntimeError("Cannot replace an existing process alarm during acquisition")

    def expired(_signum, _frame):
        raise _DeadlineExpired("Acquisition I/O deadline")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        if old_timer[1]:
            signal.setitimer(signal.ITIMER_REAL, 0, old_timer[1])


class Budget:
    def __init__(self, client, protocol, directory):
        self.client = client
        self.limits = protocol["budgets"]
        self.directory = Path(directory)
        self.started = self._clock()
        self.requests = 0
        self.bytes = 0
        self.receipts = []

    def _clock(self):
        return time.monotonic()

    def fetch(self, url, role, path, maximum):
        start = utc()
        raw = bytearray()
        status = None
        reason = None
        complete = False
        remaining = self.limits["wall_time_s"] - (self._clock() - self.started)
        if (
            self.requests >= self.limits["requests_max"]
            or remaining <= 0
            or self.bytes >= self.limits["total_bytes"]
        ):
            reason = "ACQUISITION_BUDGET_EXHAUSTED"
        else:
            self.requests += 1
            duration = min(float(self.limits["timeout_s"]), remaining)
            timeout = httpx.Timeout(
                duration, connect=min(float(self.limits["connect_timeout_s"]), duration)
            )
            try:
                with (
                    _deadline(duration),
                    self.client.stream(
                        "GET", url, follow_redirects=False, timeout=timeout
                    ) as response,
                ):
                    status = response.status_code
                    for chunk in response.iter_bytes(chunk_size=8192):
                        self.bytes += len(chunk)
                        if (
                            len(raw) + len(chunk) > maximum
                            or self.bytes > self.limits["total_bytes"]
                        ):
                            reason = "RESPONSE_SIZE_BUDGET"
                            break
                        raw.extend(chunk)
                        if self._clock() - self.started >= self.limits["wall_time_s"]:
                            reason = "WALL_TIME_BUDGET"
                            break
                    else:
                        complete = True
                if reason is None and status != 200:
                    reason = "HTTP_ERROR"
            except _DeadlineExpired:
                reason = "ACQUISITION_DEADLINE"
            except httpx.HTTPError as error:
                reason = type(error).__name__
        receipt = {
            "role": role,
            "status": "DOWNLOADED"
            if complete and status == 200 and reason is None
            else "FETCH_FAILED",
            "reason": reason,
            "source_url": url,
            "started_at_utc": start,
            "finished_at_utc": utc(),
            "http_status": status,
            "response_complete": complete,
            "bytes": len(raw),
            "sha256": sha(raw),
            "raw_path": path,
        }
        if status is not None:
            with (self.directory / path).open("xb") as stream:
                stream.write(raw)
            with (self.directory / path).with_suffix(".sha256").open("x") as stream:
                stream.write(sha(raw) + "\n")
        else:
            receipt.update(raw_path=None, bytes=0, sha256=None)
        self.receipts.append(receipt)
        return receipt, bytes(raw) if receipt["status"] == "DOWNLOADED" else None


def url(base, query):
    return base + "?" + quote(query, safe=",&=")


def acquire_study(directory=DIRECTORY, *, client=None):
    directory = Path(directory)
    protocol, exclusions, hashes = load_design(directory)
    if any((directory / name).exists() for name in ("selection.json", "manifest.json")):
        raise ValueError(
            "Acquisition already attempted; never overwrite or replace selection/failures"
        )
    (directory / "raw").mkdir(exist_ok=False)
    owned = client is None
    client = client or httpx.Client(
        timeout=httpx.Timeout(
            protocol["budgets"]["timeout_s"], connect=protocol["budgets"]["connect_timeout_s"]
        ),
        follow_redirects=False,
    )
    budget = Budget(client, protocol, directory)
    started = utc()
    identity_raw = None
    snapshots = {}
    reasons = []
    try:
        source = protocol["source"]
        info, raw = budget.fetch(
            source["metadata_url"],
            "dataset_metadata",
            "raw/dataset-info.json",
            protocol["budgets"]["metadata_info_bytes"],
        )
        if raw is not None:
            try:
                doc = json.loads(raw)
                attrs = {
                    r[2]: r[4]
                    for r in doc["table"]["rows"]
                    if r[0] == "attribute" and r[1] == "NC_GLOBAL"
                }
                if (
                    "Creative Commons Attribution 4.0" not in attrs.get("license", "")
                    or source["license_url"] not in attrs.get("license", "")
                    or attrs.get("doi") != source["product_doi"]
                ):
                    raise ValueError("Source license/DOI does not match frozen design")
            except (ValueError, KeyError, TypeError, IndexError):
                raw = None
                info.update(status="METADATA_INVALID", reason="LICENSE_OR_METADATA_SCHEMA_INVALID")
        if raw is None:
            reasons.append("OFFICIAL_DATASET_METADATA_UNAVAILABLE")
        else:
            receipt, identity_raw = budget.fetch(
                url(source["base_url"], protocol["alias_policy"]["identity_query"]),
                "identity_aliases",
                "raw/identity-aliases.csv",
                protocol["budgets"]["identity_bytes"],
            )
            if identity_raw is not None:
                from apps.ocean.reeftrace_ocean.fresh_drifter_protocol import alias_maps

                try:
                    alias_maps(identity_raw)
                except ValueError:
                    identity_raw = None
                    receipt.update(status="METADATA_INVALID", reason="IDENTITY_METADATA_INVALID")
            save_json(
                directory / "identity-receipt.json",
                {
                    "schema_version": 1,
                    "protocol_sha256": hashes["protocol_sha256"],
                    "receipt": dict(receipt),
                    "saved_before_block_metadata": True,
                    "evaluation_outcomes_computed": False,
                },
            )
            if identity_raw is None:
                reasons.append("IDENTITY_METADATA_UNAVAILABLE")
            else:
                for block in protocol["selection"]["blocks"]:
                    query = ",".join(protocol["selection"]["metadata_columns"]) + (
                        f"&time={block['start_utc']}&latitude>={block['latitude_min']}&latitude<={block['latitude_max']}&longitude>={block['longitude_min']}&longitude<={block['longitude_max']}"
                    )
                    receipt, payload = budget.fetch(
                        url(source["base_url"], query),
                        "block:" + block["id"],
                        "raw/metadata-" + block["id"] + ".csv",
                        protocol["budgets"]["metadata_bytes_per_block"],
                    )
                    if payload is not None:
                        snapshots[block["id"]] = payload
        groups = []
        blocks = []
        aliases = {
            "reserved_gdp_id_count": len(exclusions["reserved_gdp_ids"]),
            "known_reserved_wmo_count": 0,
            "unresolved_reserved_alias_ids": exclusions["reserved_gdp_ids"],
            "unresolved_reserved_alias_count": len(exclusions["reserved_gdp_ids"]),
            "physical_alias_resolution_verified": False,
            "statistical_independence": False,
        }
        if identity_raw is not None:
            # Invalid identity metadata blocks all selection. Malformed blocks are retained as unfilled.
            from apps.ocean.reeftrace_ocean.fresh_drifter_protocol import alias_maps, metadata_rows

            try:
                alias_maps(identity_raw)
            except ValueError:
                identity_raw = None
                reasons.append("IDENTITY_METADATA_INVALID")
            if identity_raw is not None:
                for block in protocol["selection"]["blocks"]:
                    if block["id"] not in snapshots:
                        continue
                    try:
                        metadata_rows(snapshots[block["id"]], protocol, block)
                    except (ValueError, UnicodeError):
                        del snapshots[block["id"]]
                        next(
                            r for r in budget.receipts if r["role"] == "block:" + block["id"]
                        ).update(
                            status="METADATA_INVALID", reason="SNAPSHOT_SCHEMA_OR_IDENTITY_INVALID"
                        )
                groups, blocks, aliases = derive_groups(
                    protocol, exclusions, identity_raw, snapshots
                )
        selection = {
            "schema_version": 1,
            "study_id": protocol["study_id"],
            **hashes,
            "frozen_at_utc": utc(),
            "trajectory_payloads_fetched": False,
            "evaluation_outcomes_computed": False,
            "groups": groups,
            "blocks": blocks,
            "aliases": aliases,
            "reason_codes": reasons,
            "source_receipts": list(budget.receipts),
        }
        selection_hash = save_json(directory / "selection.json", selection)
        trajectories = []
        for group in groups:
            query = (
                ",".join(protocol["preprocessing"]["csv_columns"])
                + f'&ID="{group["drifter_id"]}"&time>={group["start_utc"]}&time<={group["end_utc"]}'
            )
            receipt, payload = budget.fetch(
                url(source["base_url"], query),
                "trajectory:" + group["drifter_id"],
                "raw/drifter-" + group["drifter_id"] + ".csv",
                protocol["budgets"]["trajectory_bytes"],
            )
            trajectories.append({**group, **receipt})
        manifest = {
            "schema_version": 1,
            "study_id": protocol["study_id"],
            **hashes,
            "selection_sha256": selection_hash,
            "started_at_utc": started,
            "finished_at_utc": utc(),
            "evaluation_outcomes_computed": False,
            "trajectories": trajectories,
            "source_receipts": budget.receipts,
            "requests_attempted": budget.requests,
            "response_bytes_received": budget.bytes,
            "no_replacements": True,
        }
        manifest_hash = save_json(directory / "manifest.json", manifest)
        return {
            "study_id": protocol["study_id"],
            **hashes,
            "selection_sha256": selection_hash,
            "manifest_sha256": manifest_hash,
            "selected_groups": len(groups),
            "downloaded_groups": sum(r["status"] == "DOWNLOADED" for r in trajectories),
            "reason_codes": reasons,
            "evaluation_outcomes_computed": False,
        }
    finally:
        if owned:
            client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DIRECTORY)
    print(json.dumps(acquire_study(parser.parse_args().output_dir), indent=2))


if __name__ == "__main__":
    main()
