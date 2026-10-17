"""Explicit synthetic contracts for inspecting stored recordings, not tank evidence."""

import copy
import json

import cv2
import pytest

from apps.transport.reeftrace_transport.flow import fit_flow
from apps.vision.reeftrace_vision import field_vector_diagnostic as diagnostic
from apps.vision.reeftrace_vision.calibration import fit_homography
from apps.vision.reeftrace_vision.tracking import flow_samples


class ReadOnlyStore:
    def __init__(self):
        self.records = {}

    def get(self, kind, identifier):
        return copy.deepcopy(self.records[(kind, identifier)])


@pytest.fixture
def stored():
    store = ReadOnlyStore()
    calibration = fit_homography(
        [[0, 0], [200, 0], [200, 200], [0, 200]],
        [[0, 0], [20, 0], [20, 20], [0, 20]],
        [[20, 30], [80, 120], [180, 150]], [[2, 3], [8, 12], [18, 15]],
        image_size_px=[201, 201], camera_session_id="test-camera",
    )
    calibration["id"] = calibration["calibration_id"]
    store.records[("calibration", calibration["id"])] = calibration
    for recording_id, y, speed in (("training", 5, 1), ("validation-near", 5, 2),
                                    ("validation-far", 15, 2)):
        points, frames = [], []
        for index in range(6):
            frame_id = f"{recording_id}-frame-{index}"
            frames.append(frame_id)
            store.records[("frame", frame_id)] = {
                "id": frame_id, "camera_session_id": "test-camera",
                "test_fixture_origin": "SYNTHETIC_CONTRACT_TEST", "physical_validation": False,
                "path": "/private/must-not-be-exported.jpg",
            }
            points.append({"t_s": index * 0.2, "x_cm": 4 + index * 0.2 * speed,
                           "y_cm": y, "observed": True, "track_id": recording_id,
                           "frame_id": frame_id})
        store.records[("recording", recording_id)] = {
            "id": recording_id, "points": points, "evidence_frame_ids": frames,
            "data_origin": "MEASURED_TANK", "camera_session_id": "test-camera",
            "calibration_id": calibration["id"], "timestamp_kind": "host_receipt_not_exposure",
            "test_fixture_origin": "SYNTHETIC_CONTRACT_TEST", "physical_validation": False,
        }
    flow = fit_flow(flow_samples(store.records[("recording", "training")]["points"]),
                    {"x_min_cm": 0, "x_max_cm": 20, "y_min_cm": 0, "y_max_cm": 20},
                    cell_size_cm=1, coverage_radius_cm=3, data_origin="MEASURED_TANK")
    flow.update(id="flow-test", provenance={"calibration_id": calibration["id"],
        "camera_session_id": "test-camera", "training_recording_ids": ["training"],
        "validation_recording_ids": ["validation-near", "validation-far"],
        "frame_splits_disjoint": True})
    store.records[("flow", "flow-test")] = flow
    return store


def test_frozen_field_reports_supported_error_and_retains_unsupported_vectors(stored):
    report = diagnostic.inspect_recorded_flow_vectors(stored, "flow-test")
    assert report["data_origin"] == "SYNTHETIC_CAPTURE_REPLAY"
    assert report["capture_origin"] == "SYNTHETIC_CAPTURE_REPLAY"
    assert report["physical_validation"] is False
    assert report["coverage"] == {
        "training_recording_count": 1, "validation_recording_count": 2,
        "training_sample_count": 3, "validation_sample_count": 6,
        "supported_sample_count": 3, "unsupported_sample_count": 3, "supported_fraction": 0.5,
    }
    assert report["metrics"]["sample_count"] == 3
    assert report["metrics"]["vector_rmse_cm_s"] == pytest.approx(1)
    assert report["metrics"]["mean_speed_bias_cm_s"] == pytest.approx(-1)
    assert report["metrics"]["equal_recording_mean_rmse_cm_s"] == pytest.approx(1)
    near, far = report["recordings"]
    assert all(vector["supported"] for vector in near["vectors"])
    assert all(not vector["supported"] for vector in far["vectors"])
    for vector in far["vectors"]:
        assert vector["observed_vx_cm_s"] == pytest.approx(2)
        assert vector["predicted_vx_cm_s"] is None
        assert vector["vector_error_cm_s"] is None
    assert far["metrics"]["sample_count"] == 0
    assert far["metrics"]["vector_rmse_cm_s"] is None
    text = json.dumps(report, allow_nan=False)
    assert "/private/" not in text
    assert "NOT_INDEPENDENT_TEST" in report["scope"]


def test_store_data_unchanged_no_capture_or_refit_and_repeat_deterministic(stored, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Read-only diagnostic attempted acquisition or refit")

    monkeypatch.setattr(cv2, "VideoCapture", forbidden)
    monkeypatch.setattr("apps.transport.reeftrace_transport.flow.fit_flow", forbidden)
    before = copy.deepcopy(stored.records)
    first = diagnostic.inspect_recorded_flow_vectors(stored, "flow-test")
    assert first == diagnostic.inspect_recorded_flow_vectors(stored, "flow-test")
    assert stored.records == before
    for key in ("camera_started", "hardware_actuation", "provider_calls", "store_written",
                "refit_performed", "model_selection_performed", "capture_independently_verified"):
        assert first[key] is False


def test_without_fake_flags_capture_remains_unverified_never_physical(stored):
    for value in stored.records.values():
        value.pop("test_fixture_origin", None)
    report = diagnostic.inspect_recorded_flow_vectors(stored, "flow-test")
    assert report["data_origin"] == "RECORDED_TANK_CAPTURE_UNVERIFIED"
    assert report["capture_origin"] == "UNVERIFIED_STORED_CAPTURE"
    assert report["physical_validation"] is False
    assert report["capture_independently_verified"] is False


def test_one_fake_frame_cannot_be_upgraded_by_measured_recording_label(stored):
    for value in stored.records.values():
        value.pop("test_fixture_origin", None)
    stored.records[("frame", "training-frame-0")]["backend"] = "SYNTHETIC_FAKE_CAPTURE"
    assert diagnostic.inspect_recorded_flow_vectors(stored, "flow-test")["data_origin"] == "SYNTHETIC_CAPTURE_REPLAY"


@pytest.mark.parametrize("field,value", [("camera_session_id", "other-camera"),
    ("calibration_id", "other-calibration"), ("timestamp_kind", "invented-times"),
    ("data_origin", "SYNTHETIC")])
def test_wrong_recording_bindings_rejected(stored, field, value):
    stored.records[("recording", "validation-near")][field] = value
    with pytest.raises(ValueError, match="binding"):
        diagnostic.inspect_recorded_flow_vectors(stored, "flow-test")


def test_same_recording_in_both_splits_rejected(stored):
    stored.records[("flow", "flow-test")]["provenance"]["validation_recording_ids"] = ["training"]
    with pytest.raises(ValueError, match="overlap"):
        diagnostic.inspect_recorded_flow_vectors(stored, "flow-test")


def test_reused_frame_identity_across_splits_rejected(stored):
    record = stored.records[("recording", "validation-near")]
    record["evidence_frame_ids"][0] = record["points"][0]["frame_id"] = "training-frame-0"
    with pytest.raises(ValueError, match="frames overlap"):
        diagnostic.inspect_recorded_flow_vectors(stored, "flow-test")


def test_mapping_tamper_and_missing_saved_frame_are_rejected(stored):
    calibration = next(v for (kind, _), v in stored.records.items() if kind == "calibration")
    calibration["mean_error_cm"] = 0.1
    with pytest.raises(ValueError, match="calibration identity"):
        diagnostic.inspect_recorded_flow_vectors(stored, "flow-test")


def test_missing_saved_frame_is_not_replaced_with_invented_evidence(stored):
    del stored.records[("frame", "validation-near-frame-0")]
    with pytest.raises(KeyError):
        diagnostic.inspect_recorded_flow_vectors(stored, "flow-test")


def test_missing_and_ambiguous_points_preserve_counts_and_never_bridge(stored):
    record = stored.records[("recording", "validation-near")]
    record["points"][1].update(observed=False, reason="MULTIPLE_TOKENS")
    record["points"][2]["track_id"] = "new-track"
    for point in record["points"][3:]:
        point["track_id"] = "new-track"
    report = diagnostic.inspect_recorded_flow_vectors(stored, "flow-test")
    near = report["recordings"][0]
    assert near["counts"]["missing_point_count"] == 1
    assert near["counts"]["ambiguous_point_count"] == 1
    assert near["counts"]["no_detection_point_count"] == 0
    assert near["counts"]["observed_point_count"] == 5
    assert near["counts"]["track_count"] == 2
    assert near["counts"]["extracted_sample_count"] == 2
    assert all(vector["observed_vx_cm_s"] == pytest.approx(2) for vector in near["vectors"])


def test_no_supported_points_has_no_fake_zero_error(stored):
    flow = stored.records[("flow", "flow-test")]
    flow["provenance"]["validation_recording_ids"] = ["validation-far"]
    report = diagnostic.inspect_recorded_flow_vectors(stored, "flow-test")
    assert report["coverage"]["supported_fraction"] == 0
    assert report["metrics"]["sample_count"] == 0
    assert report["metrics"]["vector_rmse_cm_s"] is None
    assert report["metrics"]["equal_recording_mean_rmse_cm_s"] is None


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_recorded_coordinates_rejected(stored, value):
    stored.records[("recording", "validation-near")]["points"][0]["x_cm"] = value
    with pytest.raises(ValueError, match="finite coordinates"):
        diagnostic.inspect_recorded_flow_vectors(stored, "flow-test")
