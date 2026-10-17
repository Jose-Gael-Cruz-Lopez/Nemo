"""Mock-only protocol/acquisition invariants. Never freeze or request real study data."""
from __future__ import annotations

import csv
import io
import shutil
from contextlib import contextmanager

import httpx
import pytest

from apps.ocean.reeftrace_ocean import matched_current_protocol as p
from scripts import fetch_matched_current_study as fetch


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    for name in p.SOURCE_PATHS:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        source = p.ROOT / name
        target.write_bytes(source.read_bytes() if source.exists() else b"# test dependency\n")
    extras = ["data/public/noaa-fresh-drifter-v2/raw/identity-aliases.csv",
              "data/public/noaa-fresh-drifter-v2/exclusions.json",
              "data/public/noaa-fresh-drifter-v2/selection.json"]
    extras += ["docs/research-evidence/matched-current-metadata/" + name
               for name, _ in p.METADATA.values()]
    for name in extras:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p.ROOT / name, target)
    monkeypatch.setattr(p, "_git_head", lambda _root: "1" * 40)
    monkeypatch.setattr(fetch, "_require_committed", lambda *args: "2" * 40)
    directory = root / "data/public/matched-current-v1"
    result = p.freeze_protocol(directory, root=root)
    protocol, hashes = p.load_protocol(directory, root=root)
    assert result["protocol_sha256"] == hashes["protocol_sha256"]
    return root, directory, protocol


def trajectory(identifier, *, broken=None):
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(p.CSV_COLUMNS)
    writer.writerow(p.CSV_UNITS)
    for index in range(31):
        row = [identifier, (p.when(p.CONTEXT_START) + p.timedelta(hours=index)).isoformat().replace(
            "+00:00", "Z"),
               "NOT_DECODED_DURING_ACQUISITION", "also not a numeric coordinate"]
        if broken == "identity" and index == 0:
            row[0] = "999"
        if broken == "hour" and index == 30:
            row[1] = p.ORIGIN
        writer.writerow(row)
    return stream.getvalue().encode()


def responses(protocol):
    bodies = {}
    for role, (name, _) in p.METADATA.items():
        bodies[role] = (p.ROOT / "docs/research-evidence/matched-current-metadata" / name).read_bytes()
    for identifier, _ in p.GROUPS:
        bodies["trajectory:" + identifier] = trajectory(identifier)
    # Transport/schema magic only. Deliberately NOT a scientifically valid field;
    # actual HYCOM reader tests independently verify dimensions/depth/CF/masks.
    bodies["hycom_currents"] = b"CDF\x01transport-test-only"
    urls = {spec["url"]: role for role, spec in protocol["sources"].items()}
    seen = []

    def handle(request):
        assert request.method == "GET"
        assert request.headers["accept-encoding"] == "identity"
        assert "authorization" not in request.headers
        role = urls[str(request.url)]
        seen.append(role)
        payload = bodies[role]
        if isinstance(payload, Exception):
            raise payload
        status, data = payload if isinstance(payload, tuple) else (200, payload)
        content_type = "application/x-netcdf" if role == "hycom_currents" else "text/plain"
        return httpx.Response(status, headers={"content-type": content_type},
                              stream=httpx.ByteStream(data))
    return bodies, seen, httpx.Client(transport=httpx.MockTransport(handle))


def acquire(frozen, bodies=None):
    root, directory, protocol = frozen
    response, seen, client = responses(protocol)
    response.update(bodies or {})
    with client:
        result = fetch.acquire_study(directory, root=root, client=client)
    loaded = p.load_acquisition(directory, root=root)
    return result, loaded, seen


def test_missing_identity_is_gracefully_unfrozen_and_never_executes_it(tmp_path):
    with pytest.raises(ValueError, match="not frozen"):
        p.load_protocol(tmp_path, root=tmp_path)
    path = tmp_path / p.IDENTITY_RELATIVE
    path.parent.mkdir(parents=True)
    path.write_text("raise RuntimeError('must not execute')\n")
    with pytest.raises(ValueError, match="Untrusted"):
        p.load_protocol(tmp_path, root=tmp_path)


def test_metadata_only_freeze_is_exclusive_and_does_not_make_network_calls(frozen):
    root, directory, protocol = frozen
    assert protocol["metrics"]["planned_cells"] == 36
    assert protocol["models"] == ["stationary", "last_drift", "current_only"]
    assert not (directory / "raw").exists()
    assert set(p._trusted_hash(root)) <= set("0123456789abcdef")
    assert len(__import__("ast").parse((root / p.IDENTITY_RELATIVE).read_text()).body) == 2
    with pytest.raises(ValueError, match="never overwrite"):
        p.freeze_protocol(directory, root=root)


def test_six_roles_download_and_replay_without_decoding_coordinate_cells(frozen):
    result, (protocol, manifest, hashes, sources), seen = acquire(frozen)
    assert seen == list(p.ROLE_ORDER)
    assert result["requests_attempted"] == 6
    assert result["downloaded_trajectories"] == 2
    assert result["scientific_scores_computed"] is False
    assert manifest["response_bytes_received"] == manifest["response_bytes_retained"]
    assert hashes["manifest_sha256"]
    assert len(sources) == 6
    for identifier, _ in p.GROUPS:
        assert b"NOT_DECODED" in sources["trajectory:" + identifier]
    assert protocol["flags"]["assimilation_independence_verified"] is False


def test_metadata_failures_gate_only_their_related_values_and_preserve_bodies(frozen):
    result, (_, manifest, _, sources), seen = acquire(frozen, {"hycom_metadata": b"changed"})
    assert result["downloaded_trajectories"] == 2
    assert result["current_values_downloaded"] is False
    assert "hycom_currents" not in seen
    assert sources["hycom_currents"] is None
    row = next(r for r in manifest["source_receipts"] if r["role"] == "hycom_metadata")
    assert row["status"] == "METADATA_INVALID"
    assert (frozen[1] / row["raw_path"]).read_bytes() == b"changed"
    assert manifest["source_receipts"][-1]["status"] == "BLOCKED"


def test_bad_gdp_identity_blocks_both_tracks_but_not_current_transport(frozen):
    result, (_, manifest, _, sources), seen = acquire(frozen, {"gdp_identity": b"changed"})
    assert result["downloaded_trajectories"] == 0
    assert result["current_values_downloaded"] is True
    assert not any(role.startswith("trajectory:") for role in seen)
    assert all(sources["trajectory:" + i] is None for i, _ in p.GROUPS)
    assert sum(r["status"] == "BLOCKED" for r in manifest["source_receipts"]) == 2


@pytest.mark.parametrize("broken", ["identity", "hour"])
def test_structural_ambiguity_is_a_whole_payload_failure_without_replacement(frozen, broken):
    identifier = p.GROUPS[0][0]
    _, (_, manifest, _, sources), seen = acquire(
        frozen, {"trajectory:" + identifier: trajectory(identifier, broken=broken)})
    assert sources["trajectory:" + identifier] is None
    assert seen.count("trajectory:" + identifier) == 1
    assert next(r for r in manifest["source_receipts"] if
                r["role"] == "trajectory:" + identifier)["status"] == "SCHEMA_INVALID"


def test_oversized_body_is_bounded_preserved_and_keeps_full_six_role_receipts(frozen):
    identifier = p.GROUPS[0][0]
    payload = b"x" * (32 * 1024 + 12000)
    _, (_, manifest, _, sources), _ = acquire(frozen, {"trajectory:" + identifier: payload})
    row = next(r for r in manifest["source_receipts"] if r["role"] == "trajectory:" + identifier)
    assert row["retained_bytes"] == 32 * 1024
    assert row["received_bytes"] > row["retained_bytes"]
    assert row["reason"] == "RESPONSE_SIZE_BUDGET"
    assert (frozen[1] / row["raw_path"]).read_bytes() == payload[:32768]
    assert sources["trajectory:" + identifier] is None
    assert len(manifest["source_receipts"]) == 6


def test_http_failure_and_redirect_are_not_retried_or_followed(frozen):
    _, (_, manifest, _, sources), seen = acquire(frozen, {"hycom_currents": (302, b"redirect")})
    assert seen.count("hycom_currents") == 1
    assert sources["hycom_currents"] is None
    assert manifest["source_receipts"][-1]["http_status"] == 302
    assert manifest["source_receipts"][-1]["reason"] == "HTTP_ERROR"


def test_actual_deadline_failure_retains_all_roles_and_never_retries(frozen, monkeypatch):
    @contextmanager
    def expired(_seconds):
        raise fetch.DeadlineExpired("synthetic deadline")
        yield
    monkeypatch.setattr(fetch, "_deadline", expired)
    _, (_, manifest, _, sources), seen = acquire(frozen)
    assert seen == []
    assert manifest["requests_attempted"] == 3  # Three metadata attempts; dependent values blocked.
    assert len(manifest["source_receipts"]) == 6
    assert all(value is None for value in sources.values())
    assert manifest["source_receipts"][0]["reason"] == "ACQUISITION_DEADLINE"


def test_failed_acquisition_and_crash_sentinel_cannot_be_retried(frozen):
    acquire(frozen, {"hycom_currents": (503, b"unavailable")})
    root, directory, protocol = frozen
    _, seen, client = responses(protocol)
    with client, pytest.raises(ValueError, match="never overwrite"):
        fetch.acquire_study(directory, root=root, client=client)
    assert seen == []
    (directory / "manifest.json").unlink()
    (directory / "raw").rename(directory / "old-raw")
    with pytest.raises(ValueError, match="never overwrite"):
        fetch.acquire_study(directory, root=root, client=client)


def test_source_and_protocol_tampering_fail_before_any_transport(frozen):
    root, directory, protocol = frozen
    path = root / "apps/ocean/reeftrace_ocean/hycom.py"
    path.write_bytes(path.read_bytes() + b"\n# changed\n")
    with pytest.raises(ValueError, match="implementation changed"):
        p.load_protocol(directory, root=root)
    path.write_bytes(path.read_bytes().removesuffix(b"\n# changed\n"))
    protocol["sources"]["hycom_currents"]["url"] += "&unknown=1"
    (directory / "protocol.json").write_bytes(p.canonical_json(protocol))
    (directory / "protocol.sha256").write_text(p.sha(p.canonical_json(protocol)))
    with pytest.raises(ValueError, match="hash changed"):
        p.load_protocol(directory, root=root)


def test_rehashed_unknown_query_still_fails_the_fixed_semantic_contract(frozen):
    root, directory, protocol = frozen
    protocol["sources"]["hycom_currents"]["url"] += "&unknown=1"
    payload = p.canonical_json(protocol)
    (directory / "protocol.json").write_bytes(payload)
    (directory / "protocol.sha256").write_text(p.sha(payload))
    (root / p.IDENTITY_RELATIVE).write_text(
        f"STUDY_ID={p.STUDY_ID!r}\nPROTOCOL_SHA256={p.sha(payload)!r}\n")
    with pytest.raises(ValueError, match="contract changed"):
        p.load_protocol(directory, root=root)


def test_raw_byte_and_manifest_receipt_tampering_fail_replay(frozen):
    _, (_, manifest, _, _), _ = acquire(frozen)
    root, directory, _ = frozen
    row = manifest["source_receipts"][0]
    path = directory / row["raw_path"]
    path.write_bytes(path.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="hash changed"):
        p.load_acquisition(directory, root=root)


def test_uncommitted_freeze_is_rejected_before_any_io(frozen, monkeypatch):
    def reject(*_args):
        raise ValueError("Uncommitted matched-current source/freeze cannot acquire values")
    monkeypatch.setattr(fetch, "_require_committed", reject)
    root, directory, protocol = frozen
    _, seen, client = responses(protocol)
    with client, pytest.raises(ValueError, match="Uncommitted"):
        fetch.acquire_study(directory, root=root, client=client)
    assert seen == []
    assert not (directory / "acquisition-start.json").exists()


def rewrite_manifest(directory, manifest):
    payload = p.canonical_json(manifest)
    (directory / "manifest.json").write_bytes(payload)
    (directory / "manifest.sha256").write_text(p.sha(payload) + "\n")


@pytest.mark.parametrize("status,reason,role", [
    ("METADATA_INVALID", "PINNED_METADATA_CHANGED", "gdp_metadata"),
    ("SCHEMA_INVALID", "FROZEN_VALUE_SCHEMA_INVALID", "trajectory:" + p.GROUPS[0][0]),
    ("FETCH_FAILED", "ReadTimeout", "gdp_metadata"),
    ("FETCH_FAILED", "HTTP_ERROR", "gdp_metadata"),
])
def test_coherent_rehash_cannot_relabel_valid_complete_bodies_as_failures(frozen, status, reason, role):
    _, (_, manifest, _, _), _ = acquire(frozen)
    row = next(r for r in manifest["source_receipts"] if r["role"] == role)
    assert row["http_status"] == 200 and row["response_complete"]
    row.update(status=status, reason=reason)
    rewrite_manifest(frozen[1], manifest)
    with pytest.raises(ValueError, match="failure reason contradicts"):
        p.load_acquisition(frozen[1], root=frozen[0])


def test_blocked_receipt_cannot_forge_http_or_body_evidence_after_rehash(frozen):
    _, (_, manifest, _, _), _ = acquire(frozen, {"gdp_identity": b"changed"})
    row = next(r for r in manifest["source_receipts"] if r["role"].startswith("trajectory:"))
    assert row["status"] == "BLOCKED" and row["request_attempted"] is False
    row["http_status"] = 200
    rewrite_manifest(frozen[1], manifest)
    with pytest.raises(ValueError, match="failure reason contradicts"):
        p.load_acquisition(frozen[1], root=frozen[0])


def test_unattempted_budget_failure_requires_actual_budget_exhaustion(frozen):
    _, (_, manifest, _, _), _ = acquire(frozen)
    row = manifest["source_receipts"][0]
    row.update(status="FETCH_FAILED", reason="ACQUISITION_BUDGET_EXHAUSTED",
               request_attempted=False, http_status=None, raw_path=None, sha256=None,
               bytes=0, received_bytes=0, retained_bytes=0, response_complete=False,
               content_encoding=None, content_type=None)
    assert row["elapsed_wall_s"] < 180
    rewrite_manifest(frozen[1], manifest)
    with pytest.raises(ValueError, match="failure reason contradicts"):
        p.load_acquisition(frozen[1], root=frozen[0])


def test_partial_read_timeout_preserves_the_observed_prefix_and_has_no_retry(frozen):
    root, directory, protocol = frozen
    bodies, seen, _ = responses(protocol)
    target = "trajectory:" + p.GROUPS[0][0]
    urls = {spec["url"]: role for role, spec in protocol["sources"].items()}

    class BrokenStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b"partial-prefix:" + b"p" * (8192 - len(b"partial-prefix:"))
            raise httpx.ReadTimeout("synthetic timeout")

    def handler(request):
        role = urls[str(request.url)]
        seen.append(role)
        return httpx.Response(200, headers={"content-type": "application/x-netcdf"
            if role == "hycom_currents" else "text/plain"}, stream=BrokenStream()
            if role == target else httpx.ByteStream(bodies[role]))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        fetch.acquire_study(directory, root=root, client=client)
    _, manifest, _, sources = p.load_acquisition(directory, root=root)
    row = next(r for r in manifest["source_receipts"] if r["role"] == target)
    assert row["status"] == "FETCH_FAILED" and row["reason"] == "ReadTimeout"
    assert row["received_bytes"] == row["retained_bytes"] == 8192
    assert (directory / row["raw_path"]).read_bytes().startswith(b"partial-prefix:")
    assert sources[target] is None and seen.count(target) == 1


def test_unknown_direct_budget_query_is_rejected_without_transport(frozen):
    _, directory, protocol = frozen
    _, seen, client = responses(protocol)
    budget = fetch.Budget(client, protocol, directory)
    altered = {**protocol["sources"]["hycom_currents"], "url": p.HYCOM_BASE + "?unknown=1"}
    with client, pytest.raises(ValueError, match="Unknown matched-current query"):
        budget.fetch("hycom_currents", altered)
    assert seen == []


def test_gzip_is_rejected_without_decompression_and_raw_bytes_are_preserved(frozen):
    _, directory, protocol = frozen
    (directory / "raw").mkdir()
    raw = b"gzip-looking-untrusted-transport-data"
    def handler(_request):
        return httpx.Response(200, headers={"content-encoding": "gzip",
                              "content-type": "application/x-netcdf"},
                              stream=httpx.ByteStream(raw))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        row, accepted = fetch.Budget(client, protocol, directory).fetch(
            "hycom_currents", protocol["sources"]["hycom_currents"])
    assert accepted is None and row["reason"] == "CONTENT_ENCODING_MISMATCH"
    assert row["received_bytes"] == len(raw)
    assert (directory / row["raw_path"]).read_bytes() == raw
