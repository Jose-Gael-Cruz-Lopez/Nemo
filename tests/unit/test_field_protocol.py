"""Field-manifest v1 contract: parser, content address and request boundary.

The committed fixture is a SYNTHETIC contract fixture (fake capture, placeholder
artifact hashes). It demonstrates the shape Lanes 2/3 parse, not a tank result.
"""
import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from apps.api.reeftrace_api.schemas.field_sessions import (
    STEP_IDS,
    FieldManifestV1,
    FieldSessionInput,
)
from apps.api.reeftrace_api.services.field_sessions import (
    Blocked,
    _step,
    calibration_intact,
    digest,
    seal,
    verify_manifest,
)
from apps.vision.reeftrace_vision.calibration import fit_homography

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/team_handoff/field_manifest_v1.json"
BODY_EXCLUDE = ("manifest_id", "content_hash", "created_at")


def fixture():
    return json.loads(FIXTURE.read_text())


def body():
    return {k: v for k, v in fixture().items() if k not in BODY_EXCLUDE}


def test_committed_fixture_parses_and_its_id_is_derived_from_its_hash():
    document = fixture()
    manifest = verify_manifest(document)
    assert isinstance(manifest, FieldManifestV1)
    assert manifest.schema_version == "field_manifest_v1"
    assert manifest.content_hash == digest(body())
    assert manifest.manifest_id == "fm-" + manifest.content_hash[:16]
    assert manifest.capture.capture_origin == "SYNTHETIC_FAKE_CAPTURE"
    assert "SYNTHETIC_FAKE_CAPTURE_NOT_PHYSICAL" in manifest.warnings
    assert manifest.provenance.hardware_independently_verified is False


def test_detached_timestamp_does_not_change_identity():
    document = fixture()
    for created_at in (None, 0.0, 2e9):
        assert verify_manifest({**document, "created_at": created_at}).content_hash == document["content_hash"]


@pytest.mark.parametrize("path,value", [
    (("flow", "validation_rmse_cm_s"), 0.0),
    (("profile", "source_ids"), ["A", "B"]),
    (("recordings", "validation_recording_ids"), ["recording-other"]),
    (("first_observation", "case_id"), "case-other"),
    (("rig_check_id",), "rig_check-other"),
    (("rig_change_id",), "rig-change-other"),
])
def test_any_body_change_breaks_the_content_address(path, value):
    document = copy.deepcopy(fixture())
    target = document
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError, match="hash"):
        verify_manifest(document)


def test_sealing_is_deterministic_and_normalizes_numbers():
    as_int = body()
    as_int["profile"]["max_validation_rmse_cm_s"] = 1
    assert seal(as_int)["content_hash"] == seal(body())["content_hash"] == fixture()["content_hash"]


@pytest.mark.parametrize("mutate,message", [
    (lambda b: b["checks"][3].update(status="BLOCKED"), "PASSED"),
    (lambda b: b["checks"].pop(), "PASSED"),
    (lambda b: b["checks"].reverse(), "PASSED"),
    (lambda b: b["operator_attestations"].update(pump_setting_unchanged=False), "attestation"),
    (lambda b: b["warnings"].remove("SYNTHETIC_FAKE_CAPTURE_NOT_PHYSICAL"), "synthetic"),
    (lambda b: b["capture"].update(capture_origin="USB_CAMERA_DEVICE"), "backend"),
    (lambda b: b["flow"].update(validation_coverage_fraction=0.5), "greater"),
    (lambda b: b["flow"].update(data_origin="SYNTHETIC"), "MEASURED_TANK"),
    (lambda b: b["provenance"].update(hardware_independently_verified=True), "False"),
    (lambda b: b.update(status="DRAFT"), "READY"),
    (lambda b: b.update(true_source="A"), "Extra"),
])
def test_incomplete_or_overclaiming_body_cannot_be_sealed_ready(mutate, message):
    draft = body()
    mutate(draft)
    with pytest.raises(ValidationError, match=message):
        seal(draft)


def test_fixture_contains_no_paths_secrets_images_or_release_truth():
    document = fixture()
    assert document["provenance"].pop("excludes") == [
        "source_release_truth", "credentials", "absolute_paths", "raw_camera_images", "free_text_notes"]
    text = json.dumps(document).lower()
    for forbidden in ("/users/", "/private/", ".jpg", "jpeg", "token", "api_key", "true_source",
                      "release", "actual_inlet", "note", "path"):
        assert forbidden not in text


def test_request_boundary_rejects_overlap_duplicates_and_extra_claims():
    base = {"camera_session_id": "usb-1", "calibration_id": "cal-1", "training_recording_ids": ["a", "b"],
            "validation_recording_ids": ["c"], "flow_id": "f", "profile_id": "p"}
    assert FieldSessionInput(**base).first_case_id is None
    assert FieldSessionInput(camera_session_id="usb-1").training_recording_ids == []
    for changes in ({"validation_recording_ids": ["b"]}, {"training_recording_ids": ["a", "a"]},
                    {"training_recording_ids": [""]}, {"status": "READY"}, {"approved": True},
                    {"attestations": {"waterline_unchanged": True}}, {"camera_session_id": ""}):
        with pytest.raises(ValidationError):
            FieldSessionInput(**{**base, **changes})


@pytest.mark.parametrize("unsafe", ["contact@example.test", "+15555550123", "/private/frames",
                                    "ck-FAKE-NOT-A-REAL-KEY", "ghp_FAKE_NOT_A_REAL_KEY"])
def test_receipt_identifiers_reject_contacts_paths_and_credential_shapes(unsafe):
    for section, key, value in (("capture", "camera_session_id", unsafe),
                                ("calibration", "calibration_id", unsafe),
                                ("recordings", "training_recording_ids", [unsafe]),
                                ("flow", "flow_id", unsafe), ("profile", "profile_id", unsafe),
                                ("profile", "source_ids", ["A", unsafe]),
                                ("first_observation", "case_id", unsafe)):
        draft = body()
        draft[section][key] = value
        with pytest.raises(ValueError):
            seal(draft)


def test_saved_calibration_integrity_is_recomputed_from_its_own_report():
    report = fit_homography([[0, 0], [100, 0], [100, 100], [0, 100]], [[0, 0], [5, 0], [5, 5], [0, 5]],
                            [[20, 30], [70, 20], [50, 80]], [[1, 1.5], [3.5, 1], [2.5, 4]],
                            image_size_px=(101, 101), camera_session_id="usb-1")
    stored = json.loads(json.dumps({**report, "id": report["calibration_id"]}))
    assert calibration_intact(stored)
    assert not calibration_intact({**stored, "approved": not stored["approved"]})
    assert not calibration_intact({**stored, "max_allowed_error_cm": 50})


def test_every_blocked_step_explains_itself_and_blocked_error_names_steps():
    for step in STEP_IDS:
        assert _step(step, "BLOCKED", "X", "message")["help"]
        assert _step(step, "PASSED", "X", "message")["help"] == ""
    error = Blocked([_step("camera_session", "MISSING", "CAMERA_NOT_RUNNING", "m"),
                     _step("rig_state", "PASSED", "OK", "m")])
    assert "camera_session: CAMERA_NOT_RUNNING" in str(error) and "rig_state" not in str(error)
