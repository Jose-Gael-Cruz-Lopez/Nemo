"""The estimated rig model stays labelled SYNTHETIC and follows the observed cap path."""
import importlib.util
from pathlib import Path

import numpy as np

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "load_estimated_rig.py"
spec = importlib.util.spec_from_file_location("load_estimated_rig", SCRIPT)
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)


def test_path_fit_passes_near_observed_mesh_edge_and_outlet():
    coeffs = model.fit_path()
    residuals = [abs(np.polyval(coeffs, x) - y) for x, y in model.OBSERVED_EDGE]
    assert max(residuals) < 1.5          # within the mapping's typical error
    assert abs(np.polyval(coeffs, model.OUTLET[0]) - model.OUTLET[1]) < 1.0


def test_profiles_are_synthetic_and_flagged_as_estimates():
    baseline, intervention = model.profiles()
    for profile in (baseline, intervention):
        assert profile["data_origin"] == "SYNTHETIC"
        assert profile["flow"]["data_origin"] == "SYNTHETIC"
        assert profile["estimate_provenance"]["kind"] == "ESTIMATED_RIG_MODEL_NOT_MEASURED"
        assert profile["estimate_provenance"]["physical_validation"] is False
    assert baseline["traps"] == [] and intervention["traps"][0]["id"] == "green-mesh"
    assert baseline["sources"] == intervention["sources"]


def test_jet_samples_run_away_from_the_outlet_at_the_stated_speed():
    samples = model.drift_samples(15.0)
    jet = [s for s in samples if np.hypot(s["vx_cm_s"], s["vy_cm_s"]) > 10]
    assert jet and all(s["vx_cm_s"] < 0 for s in jet)
    assert all(abs(np.hypot(s["vx_cm_s"], s["vy_cm_s"]) - 15.0) < 1e-6 for s in jet)
