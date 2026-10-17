"""Verified acquisition state and primary-source next-data roadmap.

This read-only report does not score, fit, fetch or select a model. A failed
acquisition is evidence of missing data, never a substitute benchmark result.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .benchmark import ROOT

DIRECTORY = ROOT / "data/public/noaa-indian-extension-v1"
PROTOCOL_SHA256 = "e07c5acef71c08ae0bb4e39fa94e904cd9d5a7bea9b7fab5c7e785d6ae6ce2f2"
SELECTION_SHA256 = "857e907f6a66f7b97dbe2aaee8c9f214774010005b5f17949f45c5591a5e440c"
MANIFEST_SHA256 = "cb14170dc4939c2b5c48afaa1db4e0add05361e65f66100784c3642f931828a7"
SEEN_IDS = {"8707978", "12730", "12731", "300234063243480", "300234063472530"}


def _pinned(directory, name, digest):
    path = directory / (name + ".json")
    with path.open("rb") as stream:
        payload = stream.read(100_001)
    if (len(payload) > 100_000 or hashlib.sha256(payload).hexdigest() != digest
            or path.with_suffix(".sha256").read_text().strip() != digest):
        raise ValueError("Dataset acquisition receipt integrity check failed")
    document = json.loads(payload)
    if not isinstance(document, dict):
        raise TypeError("Dataset acquisition receipt is not an object")
    return document


def load_dataset_readiness(directory=None):
    """Show the exact failed extension without repairing or pooling v1 scores."""
    directory = Path(directory or DIRECTORY)
    protocol = _pinned(directory, "protocol", PROTOCOL_SHA256)
    selection = _pinned(directory, "selection", SELECTION_SHA256)
    manifest = _pinned(directory, "manifest", MANIFEST_SHA256)
    study_id = "noaa-indian-extension-retrospective-v1"
    if (any(document.get("study_id") != study_id or document.get("schema_version") != 1
            for document in (protocol, selection, manifest))
            or selection["protocol_sha256"] != PROTOCOL_SHA256
            or manifest["protocol_sha256"] != PROTOCOL_SHA256
            or manifest["selection_sha256"] != SELECTION_SHA256
            or selection["evaluation_outcomes_computed"] is not False
            or manifest["evaluation_outcomes_computed"] is not False
            or selection["trajectory_payloads_fetched"] is not False
            or set(selection["excluded_previously_viewed_ids"]) != SEEN_IDS
            or selection["groups"] or manifest["trajectories"]):
        raise ValueError("Frozen blocked acquisition identity changed; no unverified outcomes accepted")
    for relative, expected in protocol["models"]["implementation_sha256"].items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Previously frozen model or preprocessing implementation changed")
    metadata = selection["dataset_metadata"]
    payload = (directory / metadata["raw_path"]).read_bytes()
    if (hashlib.sha256(payload).hexdigest() != metadata["sha256"]
            or len(payload) != metadata["bytes"] or metadata["freshly_downloaded"] is not False):
        raise ValueError("Reused official metadata snapshot integrity failed")
    attempt = selection["blocks"][0]
    if (attempt["status"] != "FETCH_FAILED" or attempt["reason"] != "ConnectTimeout"
            or attempt["selected_ids"]):
        raise ValueError("Frozen acquisition-failure record changed")
    return {
        "schema_version": 1, "kind": "DATASET_READINESS_REPORT", "status": "ACQUISITION_BLOCKED",
        "study_id": study_id, "integrity_verified": True,
        "test_data_used": False, "new_evaluation_outcomes_computed": False,
        "model_selection_performed": False, "automatic_model_promotion": False,
        "physical_validation": False, "calibrated_probability": False,
        "protocol_sha256": PROTOCOL_SHA256, "selection_sha256": SELECTION_SHA256,
        "manifest_sha256": MANIFEST_SHA256, "excluded_previously_viewed_ids": sorted(SEEN_IDS),
        "coverage": {"target_new_drifters": 2, "selected_new_drifters": 0,
                     "downloaded_trajectories": 0, "new_position_rows": 0,
                     "planned_model_horizon_outcomes": 48, "scored_outcomes": 0},
        "acquisition": {key: attempt[key] for key in (
            "status", "reason", "source_url", "retrieved_at_utc", "http_status")},
        "metadata_snapshot": {"freshly_downloaded": False,
                              "retrieved_at_utc": metadata["retrieved_at_utc"],
                              "sha256": metadata["sha256"]},
        "previous_study": {"unchanged": True, "declared_groups": 4, "target_groups": 6,
                           "scored_outcomes": 96, "target_outcomes": 144,
                           "status": "PARTIAL_COVERAGE", "pooling_performed": False},
        "next_datasets": [
            {"id": "noaa-gdp-gts", "name": "NOAA near-real-time GTS drifter fixes",
             "primary_source_url": "https://www.aoml.noaa.gov/phod/gdp/real-time_data.php",
             "role": "Future motion forecasting with actual message-time availability",
             "why_better_for_this_question": "A causal replay can test forecasts against later arriving fixes instead of an interpolated retrospective target.",
             "acquired": False, "training_ready": False,
             "required_before_use": ["Verify redistribution terms and data dictionary",
                 "Pin raw fix payload and receive-time/as-of metadata",
                 "Map WMO IDs to GDP IDs and exclude all previously viewed physical drifters",
                 "Freeze irregular-cadence handling and held-out whole-drifter groups before scoring"],
             "cannot_prove": "Buoy motion alone does not establish plastic origin, collector performance or reef benefit."},
            {"id": "noaa-mdmap", "name": "NOAA MDMAP shoreline debris surveys",
             "primary_source_url": "https://marinedebris.noaa.gov/our-work/monitoring/marine-debris-monitoring-and-assessment-project",
             "role": "Debris outcome and prevention evaluation",
             "why_better_for_this_question": "Measures actual shoreline debris amounts and types, closer to prevention outcomes than buoy forecast error.",
             "acquired": False, "training_ready": False,
             "required_before_use": ["Use documented export/API and verify reuse terms",
                 "Retain site, survey date, surveyed area, effort and protocol metadata",
                 "Join interventions only with valid timing and independent comparison design"],
             "cannot_prove": "Observational shoreline counts alone do not identify a release source or establish that a particular interception layout caused a reduction."},
            {"id": "copernicus-glorys12", "name": "Copernicus GLORYS12 ocean reanalysis",
             "primary_source_url": "https://data.marine.copernicus.eu/product/GLOBAL_MULTIYEAR_PHY_001_030/description",
             "role": "Retrospective ocean-current forcing and regional context",
             "why_better_for_this_question": "Adds gridded current fields that position-only extrapolation cannot represent.",
             "acquired": False, "training_ready": False,
             "required_before_use": ["Verify licence, exact dataset version, subset bounds and depth",
                 "Freeze temporal/spatial interpolation and coastline handling",
                 "Audit assimilation and data availability before any operational forecast claim"],
             "cannot_prove": "An assimilative reanalysis is not independent observed plastic ground truth; its approximately 8 km grid does not resolve a tabletop tank or an individual reef channel."},
        ],
        "limitations": [
            "The bounded Indian metadata request timed out; no replacement dataset, IDs or outcomes were invented.",
            "A pre-outcome protocol amendment reused an older pinned official metadata snapshot after a separate metadata-info failure; this is not a fresh licence/metadata download.",
            "The original four-drifter study remains unchanged; this unsuccessful extension does not repair its missing basin or alter its metrics.",
            "Grok provided static research review; local code verifies receipts. No new model improvement or real-world prevention benefit is established.",
        ],
    }
