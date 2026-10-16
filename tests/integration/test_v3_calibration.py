import json
import subprocess
import sys
from pathlib import Path

import pytest


def test_water_plane_fit_and_independent_check_points(tmp_path):
    source = Path("config/water_plane_references.example.json")
    output = tmp_path / "calibration.json"
    subprocess.run(
        [
            sys.executable,
            "scripts/calibrate_camera.py",
            "--references",
            str(source),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
    )
    report = json.loads(output.read_text())
    assert report["max_error_cm"] < 1e-4
    assert report["measurement_plane"] == "water_surface"
    assert report["validity"] == "development"


def test_flow_counts_and_unsupported_cells(tmp_path):
    profile = json.loads(Path("config/site.example.json").read_text())
    marker = {
        "calibration_id": profile["id"],
        "purpose": "flow_measurement",
        "track": [{"t": i * 0.1, "x": 1 + i * 0.1, "y": 1.0} for i in range(6)],
    }
    path = tmp_path / "markers.json"
    path.write_text(json.dumps(marker))
    output = tmp_path / "flow.json"
    subprocess.run(
        [
            sys.executable,
            "scripts/build_flow.py",
            "--site",
            "config/site.example.json",
            "--tracks",
            str(path),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
    )
    result = json.loads(output.read_text())
    assert result["validity"] == "development"
    assert result["flow"]["counts"][0][0] == 5
    assert result["flow"]["velocity_cm_s"][0][0] == pytest.approx([1.0, 0.0])
    assert result["flow"]["counts"][1][1] == 0
