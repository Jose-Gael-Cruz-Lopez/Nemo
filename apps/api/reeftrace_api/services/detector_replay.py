"""Bounded, local saved-footage regression. Never produces measured evidence."""
from __future__ import annotations

import base64
import hashlib
import json
import math
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np

from apps.vision.reeftrace_vision.foreground import (
    EmptyTankReference,
    SceneChanged,
    ViewObstructed,
    detect_foreground,
    measure_token_area,
    token_area_range,
)
from apps.vision.reeftrace_vision.surface_token import (
    measure_surface_token_area,
    surface_policy,
    surface_token_diagnostic,
    validate_detection_polygon,
)
from apps.vision.reeftrace_vision.tracking import SingleTokenTracker

from ..schemas.saved_calibrations import SavedCalibrationBundle
from .saved_calibrations import validate_saved_record
from .store import uid

KIND = "detector_replay"
MANIFEST_SCHEMA = "nemo_private_surface_replay_v1"
WARNING = (
    "Development replay of saved local footage, not independent physical accuracy validation. "
    "Coordinates use an estimated historical map. No camera, flow model, case, trial receipt "
    "or Photon message is created. Wall reflections shaped like a cap can remain ambiguous."
)


def _private_file(root, relative, limit):
    path = Path(relative)
    if path.is_absolute():
        raise ValueError("Replay manifest paths must be relative to private local data")
    path = (root / path).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Replay input is outside private local data or missing")
    if not 0 < path.stat().st_size <= limit:
        raise ValueError("Replay input exceeds its bounded file size")
    return path


def _bytes(root, item, limit):
    payload = _private_file(root, item["path"], limit).read_bytes()
    if hashlib.sha256(payload).hexdigest() != item["sha256"]:
        raise ValueError("Saved replay input hash changed; nothing was admitted")
    return payload


def _counts():
    return {"accepted_frames": 0, "gap_frames": 0, "multiple_frames": 0,
            "scene_gap_frames": 0}


def _count(counts, point):
    counts["accepted_frames" if point["observed"] else "gap_frames"] += 1
    counts["multiple_frames"] += point.get("reason") == "MULTIPLE_TOKENS"
    counts["scene_gap_frames"] += point.get("reason") in {"SCENE_CHANGED", "VIEW_OBSTRUCTED"}


class DetectorReplayService:
    def __init__(self, runtime):
        self.runtime = runtime

    def latest(self):
        records = self.runtime.store.list(KIND, 1)
        if not records:
            raise KeyError("No local saved-footage replay exists")
        if records[0].get("policy", {}).get("sha256") != surface_policy()["policy_sha256"]:
            raise ValueError("The last replay predates the current detector policy; replay saved footage")
        return records[0]

    def run(self):
        root = self.runtime.settings.data_dir
        manifest_path = _private_file(root, "detector_replay/manifest.json", 4_000_000)
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw)
        if not isinstance(manifest, dict) or manifest.get("schema_version") != MANIFEST_SCHEMA:
            raise ValueError("Unsupported private replay manifest")
        source = validate_saved_record(
            SavedCalibrationBundle.model_validate(manifest["source_calibration"]).source_record)
        clips = manifest["clips"]
        if not isinstance(clips, list) or not 1 <= len(clips) <= 10:
            raise ValueError("Replay requires 1-10 saved clips")
        if any(not isinstance(clip, dict) or not isinstance(clip.get("frames"), list)
               for clip in clips):
            raise ValueError("Each saved clip requires a bounded frame list")
        if sum(len(clip["frames"]) for clip in clips) > 300:
            raise ValueError("Replay is limited to 300 saved frames")
        report_clips = [self._clip(root, clip, source, manifest["detection_polygon_px"])
                        for clip in clips]
        totals = {"frames": sum(c["frames"] for c in report_clips)}
        for prefix, key in (("baseline", "baseline"), ("surface", "surface")):
            totals[prefix + "_accepted_frames"] = sum(
                c[key]["accepted_frames"] for c in report_clips)
            totals[prefix + "_ambiguous_frames"] = sum(
                c[key]["multiple_frames"] for c in report_clips)
        totals["scene_gap_frames"] = sum(c["surface"]["scene_gap_frames"] for c in report_clips)
        reasons = Counter()
        for clip in report_clips:
            reasons.update(clip["diagnostics"]["rejection_counts"])
        totals["roi_rejected_candidates"] = reasons["OUTSIDE_DETECTION_POLYGON"]
        totals["shape_rejected_candidates"] = sum(reasons[k] for k in (
            "ELONGATED_COMPONENT", "WEAK_CIRCULARITY", "LOW_SOLIDITY"))
        report_id = uid("surface-replay")
        policy = surface_policy()
        report = {"schema_version": "nemo_surface_replay_v1", "report_id": report_id,
                  "data_origin": "LOCAL_SAVED_FOOTAGE_REPLAY", "purpose": "DEVELOPMENT_REGRESSION",
                  "validation_status": "UNVALIDATED", "measured_flow_eligible": False,
                  "camera_accessed": False, "photon_messages_sent": False,
                  "evaluated_at": datetime.now(UTC).isoformat(),
                  "policy": {"id": policy["policy_id"], "sha256": policy["policy_sha256"],
                             "parameters": policy},
                  "manifest_sha256": hashlib.sha256(raw).hexdigest(),
                  "totals": totals, "clips": report_clips, "warnings": [WARNING]}
        return self.runtime.store.put(KIND, report, report_id)

    def _clip(self, root, clip, source, polygon):
        width, height = clip["image_size_px"]
        if ([width, height] != source["image_size_px"]
                or width > 4096 or height > 4096):
            raise ValueError("Saved clip dimensions differ from the historical mapping")
        polygon = validate_detection_polygon([width, height], polygon)
        ref_bytes = _bytes(root, clip["reference"], 64_000_000)
        # Load only bounded NPZ arrays, never pickle or external file references.
        import io
        import zipfile
        with zipfile.ZipFile(io.BytesIO(ref_bytes)) as archive:
            if sum(info.file_size for info in archive.infolist()) > 100_000_000:
                raise ValueError("Replay reference expands beyond its memory bound")
        with np.load(io.BytesIO(ref_bytes), allow_pickle=False) as arrays:
            reference = EmptyTankReference.from_arrays(
                arrays, expected_id=clip["reference"]["content_id"])
        if reference.shape != (height, width):
            raise ValueError("Saved background dimensions differ from the clip")
        if clip["reference"]["camera_session_id"] != clip["camera_session_id"]:
            raise ValueError("Saved background belongs to another camera session")
        if not 1 <= len(clip["frames"]) <= 300:
            raise ValueError("Saved clip must contain 1-300 frames")
        trackers = [SingleTokenTracker(), SingleTokenTracker()]
        counts = [_counts(), _counts()]
        bounds = [clip.get("original_token_area_px_range"), None]
        size_checked = [bounds[0] is not None, False]
        reasons, points, example = Counter(), [], None
        previous_t, previous_sequence = -math.inf, -1
        for frame in clip["frames"]:
            t_s, sequence = frame["t_s"], frame["sequence"]
            if (type(t_s) not in (int, float) or not math.isfinite(t_s) or t_s < 0
                    or t_s <= previous_t
                    or type(sequence) is not int or sequence <= previous_sequence):
                raise ValueError("Saved frame timestamps and sequences must increase")
            previous_t, previous_sequence = t_s, sequence
            payload = _bytes(root, frame, 6_000_000)
            image = cv2.imdecode(np.frombuffer(payload, np.uint8), cv2.IMREAD_COLOR)
            if image is None or image.shape != (height, width, 3):
                raise ValueError("Saved frame has invalid image dimensions")
            found, diagnostic, gaps = [[], []], None, [None, None]
            baseline_boxes = []
            for index in (0, 1):
                try:
                    if not size_checked[index]:
                        size_checked[index] = True
                        try:
                            area = (measure_token_area(image, reference) if index == 0 else
                                    measure_surface_token_area(image, reference, polygon))
                            bounds[index] = token_area_range(area)
                        except ValueError:
                            bounds[index] = None
                    if index == 0:
                        raw_found = detect_foreground(image, reference, area_px_range=bounds[index])
                        baseline_boxes = [d["bbox_px"] for d in raw_found]
                    else:
                        diagnostic = surface_token_diagnostic(
                            image, reference, polygon, area_px_range=bounds[index])
                        raw_found = diagnostic["detections"]
                        reasons.update(diagnostic["diagnostics"]["rejection_counts"])
                    if bounds[index] is None:
                        gaps[index] = "TOKEN_SIZE_AMBIGUOUS"
                    else:
                        found[index] = raw_found
                except ViewObstructed:
                    gaps[index] = "VIEW_OBSTRUCTED"
                except SceneChanged:
                    gaps[index] = "SCENE_CHANGED"
                point = dict(trackers[index].update(found[index], t_s, source))
                if gaps[index]:
                    point["reason"] = gaps[index]
                _count(counts[index], point)
                if index == 1:
                    x, y = point.pop("x_cm", None), point.pop("y_cm", None)
                    if point["observed"]:
                        point.update(estimated_x_cm=x, estimated_y_cm=y)
                    points.append(point)
            if example is None:
                preview = payload
                # The UI accepts at most a 2 MB data URI. Preserve dimensions,
                # while bounding the authenticated representative JPEG too.
                for quality in (70, 40, 20):
                    if len(preview) <= 1_400_000:
                        break
                    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
                    if not ok:
                        raise ValueError("Saved replay preview could not be encoded")
                    preview = encoded.tobytes()
                if len(preview) > 1_400_000:
                    raise ValueError("Saved replay preview exceeds its display bound")
                example = {"jpeg_data_url": "data:image/jpeg;base64," +
                           base64.b64encode(preview).decode(), "sequence": sequence,
                           "image_size_px": [width, height], "detection_polygon_px": polygon,
                           "baseline_boxes_px": baseline_boxes,
                           "accepted_boxes_px": [d["bbox_px"] for d in found[1]],
                           "rejected_candidates": [
                               {"bbox_px": c["bbox_px"], "reason_codes": c["rejection_codes"]}
                               for c in (diagnostic or {}).get("diagnostics", {}).get("candidates", [])
                               if not c["accepted"]]}
        return {"id": clip["id"], "label": clip["label"], "source_kind": clip["source_kind"],
                "source_id": clip["source_id"],
                "original_camera_session_id": clip["camera_session_id"],
                "image_size_px": [width, height], "frames": len(points),
                "baseline": counts[0], "surface": counts[1],
                "diagnostics": {"rejection_counts": dict(reasons)},
                "points": points, "example": example}
