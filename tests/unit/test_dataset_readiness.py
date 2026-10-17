"""Real blocked-acquisition receipts and synthetic acquisition policy tests."""

from __future__ import annotations

import json
import shutil

import httpx
import pytest

from apps.ocean.reeftrace_ocean import dataset_readiness as readiness
from scripts import fetch_indian_extension as acquisition


def test_real_blocked_receipt_never_implies_new_data_training_or_a_repaired_study():
    report = readiness.load_dataset_readiness()
    assert report == readiness.load_dataset_readiness()
    assert report["status"] == "ACQUISITION_BLOCKED"
    assert report["integrity_verified"] is True
    assert report["coverage"] == {"target_new_drifters": 2, "selected_new_drifters": 0,
        "downloaded_trajectories": 0, "new_position_rows": 0,
        "planned_model_horizon_outcomes": 48, "scored_outcomes": 0}
    assert report["previous_study"]["status"] == "PARTIAL_COVERAGE"
    assert report["previous_study"]["scored_outcomes"] == 96
    assert report["previous_study"]["pooling_performed"] is False
    for field in ("test_data_used", "new_evaluation_outcomes_computed", "model_selection_performed",
                  "automatic_model_promotion", "physical_validation", "calibrated_probability"):
        assert report[field] is False
    assert set(report["excluded_previously_viewed_ids"]) == readiness.SEEN_IDS
    assert len(report["next_datasets"]) == 3
    assert all(not row["acquired"] and not row["training_ready"] for row in report["next_datasets"])
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("name", ["protocol", "selection", "manifest"])
def test_modified_acquisition_receipt_fails_closed(tmp_path, name):
    shutil.copytree(readiness.DIRECTORY, tmp_path / "study")
    (tmp_path / "study" / (name + ".json")).write_text("{}\n")
    with pytest.raises(ValueError, match="integrity"):
        readiness.load_dataset_readiness(tmp_path / "study")


def test_reused_metadata_tampering_fails_closed(tmp_path):
    shutil.copytree(readiness.DIRECTORY, tmp_path / "study")
    (tmp_path / "study/raw/dataset-info.json").write_text("{}\n")
    with pytest.raises(ValueError, match="snapshot integrity"):
        readiness.load_dataset_readiness(tmp_path / "study")


def test_acquisition_excludes_every_viewed_drifter_and_freezes_selection_before_payloads(tmp_path):
    for name in ("protocol.json", "protocol.sha256"):
        shutil.copy(readiness.DIRECTORY / name, tmp_path / name)
    ids = ["900000002", *sorted(readiness.SEEN_IDS, reverse=True), "900000001"]
    metadata = ("ID,time,latitude,longitude,expno,location_type\n"
        ",UTC,degrees_north,degrees_east,,\n" + "\n".join(
        f"{value},2010-06-01T00:00:00Z,-10,70,123,GPS" for value in ids) + "\n")
    requested = []

    def respond(request):
        requested.append(str(request.url))
        if "expno,location_type" in str(request.url):
            return httpx.Response(200, text=metadata)
        # These are synthetic transport fixtures, never scientific trajectories.
        frozen = json.loads((tmp_path / "selection.json").read_bytes())
        assert frozen["trajectory_payloads_fetched"] is False
        assert [row["drifter_id"] for row in frozen["groups"]] == ["900000001", "900000002"]
        assert (tmp_path / "selection.sha256").exists()
        return httpx.Response(200, text="synthetic-not-evaluated\n")

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        receipt = acquisition.acquire_extension(tmp_path, client=client)
    assert receipt["selected_ids"] == ["900000001", "900000002"]
    assert receipt["evaluation_outcomes_computed"] is False
    assert len(requested) == 3
    selected = json.loads((tmp_path / "selection.json").read_bytes())
    assert set(selected["blocks"][0]["reserved_excluded_ids"]) == readiness.SEEN_IDS
    assert selected["dataset_metadata"]["freshly_downloaded"] is False
    with pytest.raises(ValueError, match="Never overwrite"):
        acquisition.acquire_extension(tmp_path)


def test_metadata_timeout_stays_an_empty_frozen_acquisition_not_a_replacement(tmp_path):
    for name in ("protocol.json", "protocol.sha256"):
        shutil.copy(readiness.DIRECTORY / name, tmp_path / name)
    requests = []

    def unavailable(request):
        requests.append(request)
        raise httpx.ConnectTimeout("synthetic timeout fixture")

    with httpx.Client(transport=httpx.MockTransport(unavailable)) as client:
        receipt = acquisition.acquire_extension(tmp_path, client=client)
    assert len(requests) == 1
    assert receipt["selected_ids"] == [] and receipt["downloaded"] == 0
    assert json.loads((tmp_path / "manifest.json").read_bytes())["trajectories"] == []
    assert json.loads((tmp_path / "selection.json").read_bytes())["blocks"][0]["reason"] == "ConnectTimeout"
