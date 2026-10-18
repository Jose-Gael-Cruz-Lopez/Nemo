#!/usr/bin/env python3
"""Load an ESTIMATED (not measured) model of the team's tabletop rig into the local app.

Real drift could not be recorded on the first rig: the outlet current carries a cap
into the mesh in about one second, faster than the 20 cm/s tracker association
limit, and the cap then hides under the mesh strap. This script therefore builds an
explicitly labelled estimate from what was observed and measured on 17 Oct 2026:

* waterline interior 14 x 9 in (35.56 x 22.86 cm), measured with a ruler;
* mesh footprint, outlet region and the point where caps end up, located in camera
  frames through the coarse cap-placement mapping (about +/-1.5 cm typical, up to 3 cm);
* cap positions seen sliding along the mesh's front edge in two recordings;
* transit outlet -> mesh of roughly one second (operator observation).

A quadratic y(x) is fitted through those path points and an assumed continuation
toward the top-right (where water would go without the mesh). Drift samples are then
generated along that curve at the estimated jet speed, plus a slow assumed return flow
toward the pump intake. Everything is SYNTHETIC: it is not a measured flow, cannot
admit a measured profile or a field receipt, and makes no physical-validity claim.

Usage, with the app running (``scripts/dev.py``):
    .venv/bin/python scripts/load_estimated_rig.py            # loads into the local API
    .venv/bin/python scripts/load_estimated_rig.py --offline  # dry run on a temporary store
The operator token is read from this checkout's private ``.env`` and never printed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.transport.reeftrace_transport import fit_flow

# Tank coordinates (cm): origin at the inside bottom-right waterline corner (pump side),
# +x along the bottom long wall toward the left wall, +y up the right short wall.
L_CM, W_CM = 35.56, 22.86
BOUNDS = {"x_min_cm": 0.0, "x_max_cm": L_CM, "y_min_cm": 0.0, "y_max_cm": W_CM}
OUTLET = (34.2, 6.0)                      # left-wall tube outlet, located 1.4-10.9 cm up; midpoint used
CAPTURE = (17.6, 12.7)                    # where caps end up: mesh front edge under the strap
MESH_FOOTPRINT = [[8.0, 11.5], [24.0, 11.5], [24.0, W_CM], [8.0, W_CM]]
PUMP_INTAKE = (3.0, 3.0)                  # pump body in the bottom-right corner (approximate)
OBSERVED_EDGE = [(15.9, 13.5), (16.2, 13.6), (16.3, 13.2), (16.5, 13.2), (20.7, 13.1),
                 (20.9, 12.8), (20.9, 12.9), (21.2, 12.8), (21.6, 12.7), (22.1, 12.7)]
ASSUMED_CONTINUATION = (4.5, 18.5)        # assumption: without the mesh, flow carries on to the top right
JET_SPEED_CM_S = {"low": 8.0, "nominal": 15.0, "high": 25.0}
RETURN_SPEED_CM_S = 2.0
JET_HALF_WIDTH_CM = 1.5
PROTECTED_ZONE = [[2.0, 15.5], [7.0, 15.5], [7.0, 21.5], [2.0, 21.5]]   # downstream "reef proxy"
SOURCES = [  # candidate entry regions (illustrative): at the outlet, upper left wall, lower bottom wall
    {"id": "A", "polygon_cm": [[32.5, 4.0], [35.0, 4.0], [35.0, 8.0], [32.5, 8.0]]},
    {"id": "B", "polygon_cm": [[32.5, 13.0], [35.0, 13.0], [35.0, 17.0], [32.5, 17.0]]},
    {"id": "C", "polygon_cm": [[24.0, 0.5], [28.0, 0.5], [28.0, 3.0], [24.0, 3.0]]},
]
PROVENANCE = {
    "kind": "ESTIMATED_RIG_MODEL_NOT_MEASURED",
    "method": "quadratic path fit through observed outlet, mesh-edge cap positions and an assumed "
              "continuation; samples at an estimated jet speed plus an assumed slow return flow",
    "jet_speed_cm_s": JET_SPEED_CM_S,
    "mapping": "coarse cap-placement water-plane mapping, about +/-1.5 cm typical and up to 3 cm",
    "observed": ["waterline 14 x 9 in", "mesh footprint and outlet from camera frames",
                 "cap positions along the mesh edge (recordings f7682c36, c8f3f60b)",
                 "about one-second outlet-to-mesh transit (operator report)"],
    "not_measured": ["the flow field itself", "jet width", "return flow", "behaviour without the mesh"],
    "physical_validation": False,
}


def fit_path():
    """Least-squares quadratic y(x) through the path points; returns coefficients."""
    xs = [OUTLET[0], *[p[0] for p in OBSERVED_EDGE], ASSUMED_CONTINUATION[0]]
    ys = [OUTLET[1], *[p[1] for p in OBSERVED_EDGE], ASSUMED_CONTINUATION[1]]
    weights = [3.0] + [1.0] * len(OBSERVED_EDGE) + [3.0]   # keep both ends, let the edge points shape it
    return np.polyfit(xs, ys, 2, w=weights)


def drift_samples(jet_speed=JET_SPEED_CM_S["nominal"]):
    coeffs = fit_path()
    deriv = np.polyder(coeffs)
    samples = []
    for x in np.arange(OUTLET[0], ASSUMED_CONTINUATION[0], -0.75):     # filled-in points along the curve
        y = float(np.polyval(coeffs, x))
        tangent = np.array([-1.0, -float(np.polyval(deriv, x))])      # flow runs toward decreasing x
        tangent /= np.linalg.norm(tangent)
        normal = np.array([-tangent[1], tangent[0]])
        for offset in (-JET_HALF_WIDTH_CM, 0.0, JET_HALF_WIDTH_CM):
            px, py = np.array([x, y]) + offset * normal
            if 0 <= px <= L_CM and 0 <= py <= W_CM:
                samples.append({"x_cm": float(px), "y_cm": float(py),
                                "vx_cm_s": float(tangent[0] * jet_speed), "vy_cm_s": float(tangent[1] * jet_speed)})
    path = np.array([[s["x_cm"], s["y_cm"]] for s in samples])
    for x in np.arange(1.0, L_CM, 3.0):                               # assumed slow return toward the pump
        for y in np.arange(1.0, W_CM, 3.0):
            if np.min(np.hypot(*(path - [x, y]).T)) < 2.5:
                continue
            toward = np.array(PUMP_INTAKE) - [x, y]
            toward /= max(np.linalg.norm(toward), 1e-9)
            samples.append({"x_cm": float(x), "y_cm": float(y),
                            "vx_cm_s": float(toward[0] * RETURN_SPEED_CM_S), "vy_cm_s": float(toward[1] * RETURN_SPEED_CM_S)})
    return samples


def profiles(jet_speed=JET_SPEED_CM_S["nominal"]):
    flow = fit_flow(drift_samples(jet_speed), BOUNDS, cell_size_cm=1.5, coverage_radius_cm=4.0,
                    data_origin="SYNTHETIC")
    base = {"valid": True, "data_origin": "SYNTHETIC", "calibration_id": "estimated-rig-map-v1",
            "bounds": BOUNDS, "sources": [{**s, "prior": 1 / 3} for s in SOURCES],
            "token_class": "green-bottle-cap-estimated", "flow": flow,
            "transport": {"particles_per_source": 120, "dt_s": 0.05, "max_age_s": 8,
                          "diffusivity_cm2_s": 0.3, "age_prior": {"min_s": 0, "max_s": 4, "count": 16}},
            "estimate_provenance": PROVENANCE}
    baseline = {**base, "id": "estimated-rig-baseline-v1", "traps": []}
    intervention = {**base, "id": "estimated-rig-intervention-v1",
                    "traps": [{"id": "green-mesh", "polygon_cm": MESH_FOOTPRINT,
                               "retention": "absorbing", "validated": True}]}
    return baseline, intervention


def observation():
    """An estimated cap path leaving the outlet (illustrative, not a recording)."""
    coeffs = fit_path()
    xs = [33.5, 31.0, 28.5, 26.0]
    return [{"t_s": round(i * 0.17, 2), "x_cm": x, "y_cm": float(np.polyval(coeffs, x))} for i, x in enumerate(xs)]


def load(post):
    baseline, intervention = profiles()
    for profile in (baseline, intervention):
        post("/profiles", profile, allow_existing=True)
    case = post("/cases", {"profile_id": baseline["id"], "calibration_id": baseline["calibration_id"],
                           "token_class": baseline["token_class"], "mode": "SYNTHETIC", "points": observation()})
    evidence = post(f"/cases/{case['id']}/estimate", {})
    comparison = post("/prevention/comparisons", {
        "case_id": case["id"], "baseline_profile_id": baseline["id"],
        "intervention_profile_id": intervention["id"], "protected_zone_cm": PROTECTED_ZONE,
        "name": "Estimated rig model (not measured): mesh vs no mesh", "horizon_s": 8, "particles": 120,
        "trials_per_source": 1})
    return {"case_id": case["id"], "evidence_status": evidence.get("status"),
            "relative_support": evidence.get("relative_support"),
            "comparison_id": comparison["comparison"]["id"],
            "recommendation": comparison["comparison"]["numerical_report"].get("recommendation"),
            "path_fit_coefficients": [round(float(c), 4) for c in fit_path()]}


def local_poster(token):
    import httpx
    client = httpx.Client(base_url="http://127.0.0.1:8000/api/v1", timeout=120,
                          headers={"Authorization": "Bearer " + token})

    def post(path, body, allow_existing=False):
        response = client.post(path, json=body)
        if allow_existing and response.status_code == 409 and "already exists" in response.text:
            return body
        if response.status_code >= 400:
            raise SystemExit(f"{path} failed ({response.status_code}): {response.text[:300]}")
        return response.json()
    return post


def offline_poster():
    from fastapi.testclient import TestClient

    from apps.api.reeftrace_api.core.settings import Settings
    from apps.api.reeftrace_api.main import create_app
    token = "offline-estimated-rig-check"
    client = TestClient(create_app(Settings(data_dir=Path(tempfile.mkdtemp()), local_token=token)))

    def post(path, body, allow_existing=False):
        response = client.post("/api/v1" + path, json=body, headers={"Authorization": "Bearer " + token})
        if response.status_code >= 400:
            raise SystemExit(f"{path} failed ({response.status_code}): {response.text[:300]}")
        return response.json()
    return post


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--offline", action="store_true", help="dry run against a temporary store")
    args = parser.parse_args()
    if args.offline:
        post = offline_poster()
    else:
        from dotenv import dotenv_values
        token = dotenv_values(ROOT / ".env").get("REEFTRACE_LOCAL_TOKEN") or os.environ.get("REEFTRACE_LOCAL_TOKEN", "")
        if not token:
            raise SystemExit("No REEFTRACE_LOCAL_TOKEN in .env; start the app once with scripts/dev.py")
        post = local_poster(token)
    print(json.dumps({"label": "ESTIMATED RIG MODEL - NOT MEASURED", **load(post)}, indent=2))


if __name__ == "__main__":
    main()
