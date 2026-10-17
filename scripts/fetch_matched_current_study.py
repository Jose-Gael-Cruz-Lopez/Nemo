"""Explicit immutable six-role acquisition; never fits, forecasts or scores models."""
from __future__ import annotations

import argparse
import json
import signal
import subprocess
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from apps.ocean.reeftrace_ocean.matched_current_protocol import (
    DIRECTORY,
    IDENTITY_RELATIVE,
    NETCDF_CONTENT_TYPES,
    ROLE_ORDER,
    ROOT,
    STUDY_ID,
    contract,
    load_protocol,
    save_json,
    sha,
    utc,
    validate_source,
)


class DeadlineExpired(TimeoutError):
    """Real I/O deadline; a peer cannot extend the budget by trickling bytes."""


@contextmanager
def _deadline(seconds):
    if threading.current_thread() is not threading.main_thread() or not hasattr(signal, "setitimer"):
        raise RuntimeError("Strict acquisition deadlines require the main-thread CLI")
    if signal.getitimer(signal.ITIMER_REAL)[0] > 0:
        raise RuntimeError("Cannot replace an existing acquisition alarm")
    previous = signal.getsignal(signal.SIGALRM)

    def expired(_signum, _frame):
        raise DeadlineExpired("Acquisition deadline")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _require_committed(root, directory, protocol):
    """The root must commit reviewed code and the generated freeze before I/O."""
    root, directory = Path(root), Path(directory)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    paths = [*protocol["implementation_sha256"],
             *(row["path"] for row in protocol["metadata_evidence"].values()), IDENTITY_RELATIVE,
             (directory / "protocol.json").relative_to(root).as_posix(),
             (directory / "protocol.sha256").relative_to(root).as_posix()]
    for name in paths:
        try:
            committed = subprocess.check_output(["git", "show", f"{head}:{name}"], cwd=root,
                                                stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as error:
            raise ValueError("Commit the matched-current freeze and sources before acquisition") from error
        if (root / name).read_bytes() != committed:
            raise ValueError("Uncommitted matched-current source/freeze cannot acquire values")
    return head


class Budget:
    def __init__(self, client, protocol, directory):
        self.client, self.directory = client, Path(directory)
        self.limits = protocol["budgets"]
        self.started = time.monotonic()
        self.requests = self.received = self.retained = 0

    def fetch(self, role, spec, *, blocked=False):
        """Only the fixed protocol URL/path is accepted, never a caller query."""
        if spec != contract()["sources"].get(role):
            raise ValueError("Unknown matched-current query, role or filename")
        started = utc()
        body = bytearray()
        status = None
        complete = attempted = False
        reason = "DEPENDENCY_UNAVAILABLE" if blocked else None
        encoding = content_type = None
        remaining = self.limits["wall_time_s"] - (time.monotonic() - self.started)
        if reason is None and (remaining <= 0 or self.requests >= self.limits["requests_max"]
                               or self.received >= self.limits["total_bytes"]):
            reason = "ACQUISITION_BUDGET_EXHAUSTED"
        received = 0
        if reason is None:
            uri = urlsplit(spec["url"])
            if (uri.scheme != "https" or uri.hostname not in {
                    "erddap.aoml.noaa.gov", "ncss.hycom.org"} or uri.username or uri.password
                    or uri.fragment or uri.port not in {None, 443}):
                raise ValueError("Unsafe matched-current source URI")
            attempted = True
            self.requests += 1
            duration = min(float(self.limits["timeout_s"]), remaining)
            try:
                with _deadline(duration), self.client.stream(
                    "GET", spec["url"], headers={"Accept-Encoding": "identity"},
                    follow_redirects=False,
                    timeout=httpx.Timeout(duration, connect=min(duration, 5)),
                ) as response:
                    status = response.status_code
                    encoding = response.headers.get("content-encoding", "identity").lower()
                    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                    for chunk in response.iter_raw(chunk_size=8192):
                        received += len(chunk)
                        self.received += len(chunk)
                        allowed = min(spec["max_bytes"] - len(body),
                                      self.limits["total_bytes"] - self.retained)
                        retained = chunk[:max(0, allowed)]
                        body.extend(retained)
                        self.retained += len(retained)
                        if len(retained) < len(chunk):
                            reason = "RESPONSE_SIZE_BUDGET"
                            break
                        if time.monotonic() - self.started >= self.limits["wall_time_s"]:
                            reason = "WALL_TIME_BUDGET"
                            break
                    else:
                        complete = True
                if reason is None:
                    if status != 200:
                        reason = "HTTP_ERROR"
                    elif encoding not in {"", "identity"}:
                        reason = "CONTENT_ENCODING_MISMATCH"
                    elif role == "hycom_currents" and content_type not in NETCDF_CONTENT_TYPES:
                        reason = "CONTENT_TYPE_MISMATCH"
            except DeadlineExpired:
                complete = False
                reason = "ACQUISITION_DEADLINE"
            except httpx.HTTPError as error:
                complete = False
                reason = type(error).__name__
        raw_path = spec["raw_path"] if status is not None else None
        if raw_path is not None:
            path = self.directory / raw_path
            with path.open("xb") as stream:
                stream.write(body)
            with path.with_suffix(".sha256").open("x") as stream:
                stream.write(sha(body) + "\n")
        row = {
            "role": role, "status": "BLOCKED" if blocked else
            "DOWNLOADED" if attempted and complete and reason is None else "FETCH_FAILED",
            "reason": reason, "source_url": spec["url"], "raw_path": raw_path,
            "sha256": sha(body) if raw_path is not None else None,
            "bytes": len(body), "received_bytes": received, "retained_bytes": len(body),
            "request_attempted": attempted, "http_status": status,
            "response_complete": complete, "content_type": content_type,
            "content_encoding": encoding, "started_at_utc": started, "finished_at_utc": utc(),
            "elapsed_wall_s": time.monotonic() - self.started,
        }
        if row["status"] == "DOWNLOADED":
            try:
                validate_source(role, bytes(body), spec)
            except (ValueError, UnicodeError, KeyError, TypeError, OverflowError):
                row.update(status="METADATA_INVALID" if "expected_sha256" in spec else
                           "SCHEMA_INVALID", reason="PINNED_METADATA_CHANGED" if
                           "expected_sha256" in spec else "FROZEN_VALUE_SCHEMA_INVALID")
        return row, bytes(body) if row["status"] == "DOWNLOADED" else None


def acquire_study(directory=None, *, client=None, root=None):
    """Explicit CLI/test entry only. Public report readers must not call this."""
    root = Path(root or ROOT)
    directory = Path(directory or root / "data/public/matched-current-v1")
    protocol, hashes = load_protocol(directory, root=root)
    if any((directory / name).exists() for name in (
        "raw", "acquisition-start.json", "acquisition-start.sha256",
        "manifest.json", "manifest.sha256",
    )):
        raise ValueError("Acquisition already attempted; never overwrite or replace a failure")
    head = _require_committed(root, directory, protocol)
    # Exclusive sentinel survives crashes, so a failed/partial attempt is not retried silently.
    save_json(directory / "acquisition-start.json", {
        "study_id": STUDY_ID, **hashes, "started_at_utc": utc(),
        "git_head_at_acquisition": head, "scientific_scores_computed": False,
    })
    (directory / "raw").mkdir(exist_ok=False)
    owned = client is None
    if owned:
        client = httpx.Client(
            timeout=httpx.Timeout(45, connect=5), follow_redirects=False,
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
            headers={"Accept-Encoding": "identity"},
        )
    budget = Budget(client, protocol, directory)
    started = utc()
    sources, receipts = {}, []
    try:
        for role in ROLE_ORDER:
            spec = protocol["sources"][role]
            blocked = any(sources.get(dep) is None for dep in spec["depends_on"])
            row, payload = budget.fetch(role, spec, blocked=blocked)
            receipts.append(row)
            sources[role] = payload
        manifest = {
            "schema_version": 1, "study_id": STUDY_ID, **hashes,
            "started_at_utc": started, "finished_at_utc": utc(),
            "git_head_at_acquisition": head, "source_receipts": receipts,
            "requests_attempted": budget.requests, "response_bytes_received": budget.received,
            "response_bytes_retained": budget.retained, "scientific_scores_computed": False,
            "no_replacements": True,
        }
        digest = save_json(directory / "manifest.json", manifest)
        return {"study_id": STUDY_ID, **hashes, "manifest_sha256": digest,
                "requests_attempted": budget.requests,
                "downloaded_trajectories": sum(sources["trajectory:" + i] is not None
                                               for i, _ in protocol_groups(protocol)),
                "current_values_downloaded": sources["hycom_currents"] is not None,
                "scientific_scores_computed": False}
    finally:
        if owned:
            client.close()


def protocol_groups(protocol):
    return [(row["drifter_id"], row["wmo"]) for row in protocol["groups"]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DIRECTORY)
    print(json.dumps(acquire_study(parser.parse_args().output_dir), indent=2))


if __name__ == "__main__":
    main()
