"""Public ocean exports preserve verified physics and never acquire or call models."""

from __future__ import annotations

import copy
import hashlib
import json
import socket
from datetime import UTC, datetime

import httpx
import pytest

from apps.api.reeftrace_api.services.ocean_prevention_investigation import snapshot_identity
from apps.ocean.reeftrace_ocean import ocean_prevention
from scripts.export_ocean_showcase import (
    ARCHIVAL_LIMITATION,
    DESTINATION,
    MODES,
    build_export,
    canonical,
    mode_variant,
)


@pytest.fixture(scope="module")
def exported():
    return build_export(generated_at=datetime(2026, 10, 17, 18, tzinfo=UTC),
                        source_commit="7fb4851367e1d35063009e0c3459596e95383e71")


def test_export_schema_has_only_public_verified_reports_and_source_provenance(exported):
    assert exported["kind"] == "PUBLIC_READ_ONLY_OCEAN_SHOWCASE"
    assert exported["generated_at_utc"] == "2026-10-17T18:00:00Z"
    assert len(exported["exporter_source_sha256"]) == 64
    assert set(exported["reports"]) == {"downstream-corridor-v2", "initial-proxy-v1"}
    assert all(exported[key] is False for key in (
        "provider_calls", "network_acquisition", "store_written", "hardware_actuation"))
    assert "API_KEY" not in canonical(exported)
    assert "Bearer " not in canonical(exported)


@pytest.mark.parametrize("scenario", ["downstream-corridor-v2", "initial-proxy-v1"])
def test_mode_representations_change_only_freshness_and_its_verified_report_hash(exported, scenario):
    variants = exported["reports"][scenario]
    reports = []
    for mode in MODES:
        item = variants[mode]
        assert hashlib.sha256(item["report_json"].encode()).hexdigest() == item["bytes_sha256"]
        report = json.loads(item["report_json"])
        assert snapshot_identity(report)[3] == item["report_sha256"]
        assert report["mode"] == mode
        assert report["scenario"]["id"] == scenario
        reports.append(report)
    assert ARCHIVAL_LIMITATION not in reports[0]["limitations"]
    assert reports[1]["limitations"] == [*reports[0]["limitations"], ARCHIVAL_LIMITATION]
    scientific = [{key: value for key, value in report.items()
                   if key not in {"mode", "report_sha256", "limitations"}}
                  for report in reports]
    assert scientific[0] == scientific[1]
    assert variants[MODES[0]]["report_sha256"] != variants[MODES[1]]["report_sha256"]
    report = json.loads(variants[MODES[0]]["report_json"])
    assert report["recommendation"]["status"] == (
        "BEST_LAYOUT" if scenario == "downstream-corridor-v2" else "TIE")


def test_mode_export_does_not_mutate_original_or_accept_invented_freshness(exported):
    report = json.loads(exported["reports"]["downstream-corridor-v2"][MODES[0]]["report_json"])
    original = copy.deepcopy(report)
    mode_variant(report, MODES[1])
    assert report == original
    with pytest.raises(ValueError, match="Unsupported"):
        mode_variant(report, "live_water_measurement")


def test_shipped_reports_match_current_verified_scientific_source(exported):
    shipped = json.loads(DESTINATION.read_text())
    assert shipped["reports"] == exported["reports"], (
        "Scientific bytes changed; explicitly regenerate and review the public showcase")


def test_export_reports_stay_identical_across_actual_source_expiry(monkeypatch):
    boundary = datetime.fromisoformat(ocean_prevention.END_UTC)
    expected = None
    # Reproduce the original failure through the real report factory, including
    # its extra archival limitation; do not replace it with a report stub.
    for offset in (-1, 0, 1):
        instant = datetime.fromtimestamp(boundary.timestamp() + offset, UTC)

        class Clock(datetime):
            frozen = instant

            @classmethod
            def now(cls, tz=None):
                return cls.frozen.astimezone(tz)

        monkeypatch.setattr(ocean_prevention, "datetime", Clock)
        result = build_export(generated_at=instant, source_commit="expiry-regression")
        if expected is None:
            expected = result["reports"]
        assert result["reports"] == expected
        for variants in result["reports"].values():
            forecast = json.loads(variants[MODES[0]]["report_json"])
            archived = json.loads(variants[MODES[1]]["report_json"])
            assert ARCHIVAL_LIMITATION not in forecast["limitations"]
            assert archived["limitations"] == [*forecast["limitations"], ARCHIVAL_LIMITATION]


def test_export_runs_without_any_network_or_provider_requests(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail("The public export must never acquire data or contact providers")
    monkeypatch.setattr(httpx.Client, "request", blocked)
    monkeypatch.setattr(httpx.AsyncClient, "request", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    result = build_export(generated_at=datetime(2026, 10, 17, tzinfo=UTC), source_commit="test")
    assert len(result["reports"]) == 2
    with pytest.raises(ValueError, match="timezone-aware"):
        build_export(generated_at=datetime(2026, 10, 17), source_commit="test")
