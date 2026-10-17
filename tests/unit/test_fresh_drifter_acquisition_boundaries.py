"""Synthetic malformed-source and real timer boundaries; no NOAA requests."""

import json
import shutil
import signal
import threading
import time

import httpx
import pytest

from apps.ocean.reeftrace_ocean import fresh_drifter
from apps.ocean.reeftrace_ocean import fresh_drifter_protocol as protocol
from scripts import fetch_fresh_drifter_study as acquisition


def study_directory(tmp_path):
    directory = tmp_path / "synthetic-study"
    directory.mkdir()
    for name in ("protocol.json", "protocol.sha256", "exclusions.json", "exclusions.sha256"):
        shutil.copyfile(protocol.DIRECTORY / name, directory / name)
    return directory


def official_metadata_fixture():
    return json.dumps(
        {
            "table": {
                "rows": [
                    [
                        "attribute",
                        "NC_GLOBAL",
                        "license",
                        "String",
                        "Creative Commons Attribution 4.0 https://creativecommons.org/licenses/by/4.0/",
                    ],
                    ["attribute", "NC_GLOBAL", "doi", "String", "10.25921/x46c-3620"],
                ]
            }
        }
    ).encode()


@pytest.mark.parametrize(
    "invalid", [b"ID,WMO\n,\n1,\xff\n", b"ID,WMO\n,\n1," + b"x" * 131073 + b"\n"]
)
def test_invalid_identity_encoding_or_csv_field_retains_manifest_without_block_or_trajectory_requests(
    tmp_path,
    invalid,
):
    directory = study_directory(tmp_path)
    requests = []

    def handler(request):
        requests.append(request)
        assert len(requests) <= 2, (
            "Invalid identity must block later metadata and trajectory requests"
        )
        return httpx.Response(
            200, content=official_metadata_fixture() if len(requests) == 1 else invalid
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = acquisition.acquire_study(directory, client=client)
    assert len(requests) == 2
    assert result["selected_groups"] == result["downloaded_groups"] == 0
    manifest, _ = protocol.pinned_json(directory, "manifest")
    selection, _ = protocol.pinned_json(directory, "selection")
    identity, _ = protocol.pinned_json(directory, "identity-receipt")
    assert manifest["requests_attempted"] == 2 and manifest["trajectories"] == []
    assert selection["groups"] == [] and selection["trajectory_payloads_fetched"] is False
    assert identity["receipt"]["status"] == "METADATA_INVALID"
    assert identity["receipt"]["reason"] == "IDENTITY_METADATA_INVALID"
    assert (directory / identity["receipt"]["raw_path"]).read_bytes() == invalid
    # A known malformed source is a blocked acquisition, not a forged valid study.
    report = fresh_drifter.run_fresh_drifter_study(directory)
    assert report["status"] == "ACQUISITION_BLOCKED"
    assert report["coverage"]["scored_outcomes"] == 0
    assert report["coverage"]["unfilled_outcomes"] == 180


@pytest.mark.skipif(
    not hasattr(signal, "setitimer"), reason="Strict CLI deadline uses POSIX timers"
)
def test_deadline_interrupts_real_blocking_wait_and_restores_inactive_handler():
    previous = signal.getsignal(signal.SIGALRM)
    assert signal.getitimer(signal.ITIMER_REAL)[0] == 0
    start = time.monotonic()
    with pytest.raises(acquisition._DeadlineExpired), acquisition._deadline(0.03):
        time.sleep(0.5)
    assert time.monotonic() - start < 0.4
    assert signal.getsignal(signal.SIGALRM) == previous
    assert signal.getitimer(signal.ITIMER_REAL)[0] == 0
    with pytest.raises(ValueError, match="synthetic body"), acquisition._deadline(0.1):
        raise ValueError("synthetic body failure")
    assert signal.getsignal(signal.SIGALRM) == previous
    assert signal.getitimer(signal.ITIMER_REAL)[0] == 0


def test_existing_process_alarm_is_rejected_without_replacing_it(monkeypatch):
    calls = []
    monkeypatch.setattr(signal, "getitimer", lambda kind: (0.2, 0))
    monkeypatch.setattr(signal, "signal", lambda *args: calls.append(args))
    monkeypatch.setattr(signal, "setitimer", lambda *args: calls.append(args))
    with pytest.raises(RuntimeError, match="existing process alarm"), acquisition._deadline(0.05):
        raise AssertionError("Must not enter a conflicting deadline")
    assert calls == []


def test_non_main_thread_cannot_silently_bypass_strict_deadline():
    errors = []

    def run():
        try:
            with acquisition._deadline(0.1):
                raise AssertionError("Unsupported thread entered the acquisition scope")
        except RuntimeError as error:
            errors.append(str(error))

    worker = threading.Thread(target=run)
    worker.start()
    worker.join(timeout=1)
    assert not worker.is_alive()
    assert len(errors) == 1 and "main-thread" in errors[0]


def test_request_timeout_is_clamped_to_remaining_wall_budget_and_no_extra_request_occurs(
    tmp_path, monkeypatch
):
    instant = [100.0]
    monkeypatch.setattr(acquisition.Budget, "_clock", lambda self: instant[0])
    requests = []

    def handler(request):
        requests.append(request)
        phases = request.extensions["timeout"]
        assert all(0 < phases[key] <= 0.11 for key in ("connect", "read", "write", "pool"))
        return httpx.Response(200, content=b"synthetic")

    (tmp_path / "raw").mkdir()
    limits = {
        "budgets": {
            "wall_time_s": 300,
            "timeout_s": 45,
            "connect_timeout_s": 5,
            "requests_max": 11,
            "total_bytes": 4194304,
        }
    }
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        budget = acquisition.Budget(client, limits, tmp_path)
        instant[0] = 399.9
        receipt, raw = budget.fetch(
            "https://synthetic.test/no-network", "first", "raw/first.csv", 100
        )
        assert receipt["status"] == "DOWNLOADED" and raw == b"synthetic"
        instant[0] = 400.1
        receipt, raw = budget.fetch(
            "https://synthetic.test/no-network", "second", "raw/second.csv", 100
        )
    assert len(requests) == 1 and budget.requests == 1
    assert receipt["reason"] == "ACQUISITION_BUDGET_EXHAUSTED" and raw is None
    assert not (tmp_path / "raw/second.csv").exists()


@pytest.mark.skipif(
    not hasattr(signal, "setitimer"), reason="Strict CLI deadline uses POSIX timers"
)
def test_midstream_deadline_retains_partial_bytes_and_exhaustion_blocks_later_http(tmp_path):
    class BlockingStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b"x" * 8192
            time.sleep(0.5)
            yield b"must-not-arrive"

    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, stream=BlockingStream())

    (tmp_path / "raw").mkdir()
    limits = {
        "budgets": {
            "wall_time_s": 0.03,
            "timeout_s": 45,
            "connect_timeout_s": 5,
            "requests_max": 11,
            "total_bytes": 4194304,
        }
    }
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        budget = acquisition.Budget(client, limits, tmp_path)
        receipt, raw = budget.fetch(
            "https://synthetic.test/no-network", "partial", "raw/partial.csv", 32768
        )
        assert receipt["reason"] == "ACQUISITION_DEADLINE" and raw is None
        assert receipt["status"] == "FETCH_FAILED" and receipt["response_complete"] is False
        assert receipt["bytes"] == 8192
        assert (tmp_path / "raw/partial.csv").read_bytes() == b"x" * 8192
        later, raw = budget.fetch(
            "https://synthetic.test/no-network", "later", "raw/later.csv", 32768
        )
    assert later["reason"] == "ACQUISITION_BUDGET_EXHAUSTED" and raw is None
    assert len(requests) == budget.requests == 1
