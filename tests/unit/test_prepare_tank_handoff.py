"""Offline preparation uses synthetic placement/reference fixtures, never a real rig."""
import hashlib
import importlib.util
import json
import stat
from pathlib import Path

import numpy as np
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/prepare_tank_handoff.py"
spec = importlib.util.spec_from_file_location("prepare_tank_handoff", SCRIPT)
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


@pytest.fixture(scope="module")
def reference_arrays():
    shape = (720, 1280)
    arrays = {
        "median": np.full((*shape, 3), 120, dtype=np.float32),
        "median_bgr": np.full((*shape, 3), 120, dtype=np.float32),
        "noise": np.zeros(shape, dtype=np.float32), "roi": np.ones(shape, dtype=bool),
        "gray": np.full(shape, 120, dtype=np.float32), "meta": np.array([5, 120.0]),
    }
    identifier = "ref-" + hashlib.sha256(
        np.round(arrays["median"]).astype(np.uint8).tobytes()
        + np.packbits(arrays["roi"]).tobytes() + repr(shape).encode()).hexdigest()[:16]
    return arrays, identifier


@pytest.fixture
def handoff(tmp_path, reference_arrays):
    directory = tmp_path / "handoff"
    directory.mkdir()
    arrays, identifier = reference_arrays
    np.savez_compressed(directory / "placement_reference.npz", **arrays)
    (directory / "placement_reference_id.txt").write_text(identifier)
    pixels = [[100, 100], [1100, 100], [1100, 600], [100, 600],
              [300, 200], [900, 200], [500, 450]]
    rows = [{"placement": index + 1, "role": "fit" if index < 4 else "check",
             "pixel_in_reference_pose": point,
             "world_cm": [0.03 * (point[0] - 100) + 3, 0.034 * (point[1] - 100) + 3],
             "where": f"synthetic mark {index + 1}"} for index, point in enumerate(pixels)]
    placements = {"image_size_px": [1280, 720], "declared_max_check_error_cm": 3.0,
                  "fit": rows[:4], "check": rows[4:]}
    (directory / "placements.json").write_text(json.dumps(placements))
    # Supplied code is inert input: the trusted helper must not execute or import it.
    (directory / "reuse_mapping.py").write_text(
        "raise RuntimeError('supplied script must never execute')\n")
    return directory, placements


def test_prepares_historical_source_bundle_and_private_check_notes(tmp_path, handoff):
    directory, placements = handoff
    output = tmp_path / "historical-map.json"
    result = prepare.prepare_handoff(directory, output)
    bundle = json.loads(output.read_text())
    notes_path = tmp_path / "historical-map.measurements.json"
    notes = json.loads(notes_path.read_text())
    assert result["historical_source_only"] is True
    assert result["current_camera_alignment_verified"] is False
    assert result["validation_count"] == 3
    assert result["max_error_cm"] < 1e-5
    assert bundle["calibration"]["camera_session_id"].startswith("reference-pose-")
    assert bundle["calibration"]["id"] == result["calibration_id"]
    assert json.loads(bundle["calibration_json"]) == bundle["calibration"]
    assert notes["check"] == placements["check"]
    assert notes["current_camera_alignment_verified"] is False
    assert notes["tolerance_selected_after_data"] is True
    assert stat.S_IMODE(output.stat().st_mode) == stat.S_IMODE(notes_path.stat().st_mode) == 0o600
    assert "median_bgr" not in output.read_text() + notes_path.read_text()


def test_refuses_reference_integrity_failure_without_creating_outputs(tmp_path, handoff):
    directory, _ = handoff
    (directory / "placement_reference_id.txt").write_text("ref-" + "0" * 16)
    output = tmp_path / "mapping.json"
    with pytest.raises(ValueError, match="does not match its ID"):
        prepare.prepare_handoff(directory, output)
    assert not output.exists() and not (tmp_path / "mapping.measurements.json").exists()


@pytest.mark.parametrize("mutation", [
    lambda data: data["check"].pop(),
    lambda data: data["check"][0].update(role="fit"),
    lambda data: data["check"][0].update(world_cm=data["fit"][0]["world_cm"]),
    lambda data: data["check"][0].update(pixel_in_reference_pose=[1280, 10]),
    lambda data: data.update(declared_max_check_error_cm=3.1),
    lambda data: data.update(unknown_secret="must-not-be-copied"),
])
def test_rejects_malformed_or_changed_historical_checks(tmp_path, handoff, mutation):
    directory, data = handoff
    mutation(data)
    (directory / "placements.json").write_text(json.dumps(data))
    with pytest.raises(ValueError):
        prepare.prepare_handoff(directory, tmp_path / "mapping.json")
    assert not (tmp_path / "mapping.json").exists()


def test_historical_fit_cannot_widen_bound_to_pass(tmp_path, handoff):
    directory, data = handoff
    data["check"][0]["world_cm"][0] += 8
    (directory / "placements.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="original 3.0 cm bound"):
        prepare.prepare_handoff(directory, tmp_path / "mapping.json")


def test_refuses_existing_metadata_and_keeps_it_unchanged(tmp_path, handoff):
    directory, _ = handoff
    companion = tmp_path / "mapping.measurements.json"
    companion.write_text("private notes already exist")
    with pytest.raises(ValueError, match="already exists"):
        prepare.prepare_handoff(directory, tmp_path / "mapping.json")
    assert companion.read_text() == "private notes already exist"
    assert not (tmp_path / "mapping.json").exists()


def test_bounds_placements_file_before_loading_json(tmp_path):
    path = tmp_path / "placements.json"
    path.write_text("x" * (prepare.MAX_JSON_BYTES + 1))
    with pytest.raises(ValueError, match="64 KiB"):
        prepare.load_placements(path)
