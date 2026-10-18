"""Private mapping export reads only its bounded contract, never a real capture store."""
import copy
import hashlib
import importlib.util
import json
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/export_tank_calibration.py"
spec = importlib.util.spec_from_file_location("export_tank_calibration", SCRIPT)
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


def calibration(**changes):
    report = {
        "homography_image_to_cm": [[0.1, 0, 0], [0, 0.1, 0], [0, 0, 1]],
        "mean_error_cm": 0.1, "max_error_cm": 0.2, "validation_count": 3,
        "max_allowed_error_cm": 0.5, "approved": True, "image_size_px": [640, 480],
        "camera_session_id": "usb-synthetic-unit-test", "plane": "measured_water_surface",
        "units": "cm", **changes,
    }
    identifier = "cal-" + hashlib.sha256(
        json.dumps(report, sort_keys=True, allow_nan=False).encode()).hexdigest()[:16]
    return {**report, "calibration_id": identifier, "id": identifier}


def database(tmp_path, records=()):
    path = tmp_path / "capture.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE records(kind TEXT,id TEXT,payload TEXT,created REAL)")
        db.execute("CREATE TABLE settings(key TEXT,value TEXT)")
        db.execute("INSERT INTO settings VALUES('private-key','must-never-leave-settings')")
        for index, (kind, record) in enumerate(records):
            db.execute("INSERT INTO records VALUES(?,?,?,?)",
                       (kind, record["id"], json.dumps(record), index))
    return path


def test_legacy_record_exports_exactly_without_mutation_and_with_private_permissions(tmp_path):
    original = calibration()
    path = database(tmp_path, [("calibration", original)])
    before = path.read_bytes()
    output = tmp_path / "mapping.json"
    result = exporter.export_calibration(path, original["id"], output)
    assert result["exported"] is True
    assert json.loads(output.read_text()) == {
        "schema_version": "nemo_saved_calibration_v1", "calibration": original,
        "calibration_json": json.dumps(original, allow_nan=False, sort_keys=True),
    }
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert path.read_bytes() == before


def test_new_reuse_record_preserves_fresh_check_provenance(tmp_path):
    original = calibration()
    reuse = {
        "method": "fixed_homography_current_checks_v1",
        "source_calibration_id": original["id"], "source_content_sha256": "a" * 64,
        "check_pixels": [[10, 10], [100, 10], [10, 100]],
        "check_world_cm": [[1, 1], [10, 1], [1, 10]], "water_plane_unchanged": True,
    }
    record = calibration(camera_session_id="usb-new-synthetic-session", reuse=reuse)
    path = database(tmp_path, [("calibration", record)])
    output = tmp_path / "reuse.json"
    exporter.export_calibration(path, record["id"], output)
    assert json.loads(output.read_text())["calibration"] == record


def test_export_preserves_python_float_identity_through_browser_numeric_round_trip(tmp_path):
    record = calibration(homography_image_to_cm=[
        [0.1, 0.0, 0.0], [0.0, 0.1, 0.0], [0.0, 0.0, 1.0],
    ])
    path = database(tmp_path, [("calibration", record)])
    output = tmp_path / "browser-round-trip.json"
    exporter.export_calibration(path, record["id"], output)
    bundle = json.loads(output.read_text())

    # JavaScript JSON.stringify emits integral Number values as 0 or 1, not 0.0/1.0.
    def browser_numbers(value):
        if isinstance(value, dict):
            return {key: browser_numbers(item) for key, item in value.items()}
        if isinstance(value, list):
            return [browser_numbers(item) for item in value]
        if type(value) is float and value.is_integer():
            return int(value)
        return value

    forwarded = json.loads(json.dumps(browser_numbers(bundle)))
    assert forwarded["calibration"] == record
    assert type(forwarded["calibration"]["homography_image_to_cm"][2][2]) is int
    assert "1.0" in forwarded["calibration_json"]
    restored = exporter.checked_calibration(forwarded["calibration_json"], record["id"])
    assert type(restored["homography_image_to_cm"][2][2]) is float
    assert restored == record
    with pytest.raises(ValueError, match="content-derived"):
        exporter.checked_calibration(json.dumps(forwarded["calibration"]), record["id"])


def test_list_is_bounded_and_reveals_no_matrix_or_other_record_payloads(tmp_path):
    records = [("calibration", calibration(camera_session_id=f"usb-test-{i}"))
               for i in range(exporter.LIST_LIMIT + 1)]
    records.append(("token_reference", {"id": "ref-test", "private": "do-not-export-frames"}))
    path = database(tmp_path, records)
    result = exporter.list_calibrations(path)
    assert result["truncated"] is True and len(result["calibrations"]) == exporter.LIST_LIMIT
    encoded = json.dumps(result)
    assert "homography_image_to_cm" not in encoded
    assert "must-never-leave-settings" not in encoded
    assert "do-not-export-frames" not in encoded
    assert all(row["integrity"] == "verified" for row in result["calibrations"])


def test_nonexistent_database_is_not_created(tmp_path):
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(ValueError, match="no database was created"):
        exporter.list_calibrations(missing)
    assert not missing.exists()


def test_export_rejects_tampered_content(tmp_path):
    record = calibration()
    changed = copy.deepcopy(record)
    changed["homography_image_to_cm"][0][0] = 0.2
    path = database(tmp_path, [("calibration", changed)])
    output = tmp_path / "mapping.json"
    with pytest.raises(ValueError, match="content-derived"):
        exporter.export_calibration(path, record["id"], output)
    assert not output.exists()


def test_export_preserves_existing_output(tmp_path):
    record = calibration()
    path = database(tmp_path, [("calibration", record)])
    output = tmp_path / "mapping.json"
    output.write_text("keep this file")
    with pytest.raises(FileExistsError):
        exporter.export_calibration(path, record["id"], output)
    assert output.read_text() == "keep this file"


@pytest.mark.parametrize("changes", [
    {"private_key": "must-never-be-exported"},
    {"camera_session_id": "ck-must-never-be-exported"},
    {"homography_image_to_cm": [["private", 0, 0], [0, 1, 0], [0, 0, 1]]},
    {"reuse": {"provider_key": "must-never-be-exported"}},
])
def test_rejects_unknown_or_private_content_even_when_hash_is_intact(tmp_path, changes):
    record = calibration(**changes)
    path = database(tmp_path, [("calibration", record)])
    output = tmp_path / "mapping.json"
    with pytest.raises(ValueError):
        exporter.export_calibration(path, record["id"], output)
    assert not output.exists()
    assert "must-never-be-exported" not in json.dumps(exporter.list_calibrations(path))


def test_oversize_record_is_rejected_before_json_decode(tmp_path):
    record = calibration(extra="x" * exporter.MAX_RECORD_BYTES)
    path = database(tmp_path, [("calibration", record)])
    output = tmp_path / "mapping.json"
    with pytest.raises(ValueError, match="64 KiB"):
        exporter.export_calibration(path, record["id"], output)
    assert not output.exists()
    assert exporter.list_calibrations(path)["calibrations"][0]["integrity"] == "rejected"


def test_refuses_exports_into_git_tracked_directories(tmp_path, monkeypatch):
    record = calibration()
    path = database(tmp_path, [("calibration", record)])
    monkeypatch.setattr(exporter, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="outside Git-tracked"):
        exporter.export_calibration(path, record["id"], tmp_path / "README-export.json")
    assert not (tmp_path / "README-export.json").exists()


def test_cli_works_without_app_imports_or_credentials_and_requires_output(tmp_path):
    record = calibration()
    path = database(tmp_path, [("calibration", record)])
    result = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--database", str(path), "--list"],
        capture_output=True, text=True, check=True,
    )
    assert json.loads(result.stdout)["calibrations"][0]["id"] == record["id"]
    assert result.stderr == ""
    missing_output = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--database", str(path),
         "--calibration-id", record["id"]], check=False, capture_output=True, text=True,
    )
    assert missing_output.returncode == 2 and "requires --output" in missing_output.stderr
