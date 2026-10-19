"""Constructed-frame rehearsal and printable references. Never opens a camera."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from apps.vision.reeftrace_vision.calibration import project
from apps.vision.reeftrace_vision.registration import (
    POLICY,
    RegistrationConfig,
    RegistrationMonitor,
    digest,
)


def synthetic_config():
    origins = [(-4, -4), (42, -4), (42, 32), (-4, 32), (19, -4), (42, 14), (19, 32)]
    return RegistrationConfig.model_validate({
        "schema_version": "tank_registration_config_v1", "data_origin": "SYNTHETIC",
        "dictionary": "DICT_4X4_50", "reference_plane": "measured_water_surface",
        "references_surveyed": True, "max_error_cm": 0.5,
        "context": {"waterline_id": "synthetic-waterline", "layout_id": "synthetic-layout",
                    "flow_configuration_id": "synthetic-flow", "token_class_id": "synthetic-red-token"},
        "markers": [{"id": i, "role": "fit" if i < 4 else "check",
                     "corners_cm": [[x, y], [x + 2, y], [x + 2, y + 2], [x, y + 2]]}
                    for i, (x, y) in enumerate(origins)],
        "water_polygon_cm": [[0, 0], [40, 0], [40, 30], [0, 30]],
        "expected_filter_polygon_cm": [[24, 10], [26, 10], [26, 20], [24, 20]],
    })


def constructed_frame(config=None):
    config = config or synthetic_config()
    image = np.full((840, 1040, 3), 235, np.uint8)
    world_to_pixel = np.array([[20., 0, 120], [0, 20., 120], [0, 0, 1.]])
    for m in config.markers:
        marker = cv2.aruco.generateImageMarker(
            cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), m.id, 40)
        x, y = np.rint(project(world_to_pixel, [m.corners_cm[0]])[0]).astype(int)
        image[y:y + 40, x:x + 40] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    cv2.polylines(image, [np.rint(project(world_to_pixel, config.water_polygon_cm)).astype(np.int32)],
                  True, (20, 20, 20), 5)
    if config.expected_filter_polygon_cm:
        cv2.polylines(image, [np.rint(project(world_to_pixel,
                                           config.expected_filter_polygon_cm)).astype(np.int32)],
                      True, (30, 170, 30), 3)
    return image, world_to_pixel


def printable_markers(config):
    # Individual printable tiles, not a surveyed tray-size template. Ruler-check
    # after printing; arrangement/height still needs the independent rig survey.
    parts = [('<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" '
             'viewBox="0 0 210 297"><rect width="210" height="297" fill="white"/>'),
             '<text x="10" y="12" font-size="4">ReefTrace ArUco DICT_4X4_50 · PRINT 100%</text>',
             '<text x="10" y="19" font-size="3">Example 20 mm markers. Survey each placement at water level.</text>']
    for index, m in enumerate(config.markers):
        cell = cv2.aruco.generateImageMarker(
            cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), m.id, 6)
        x, y = 15 + (index % 3) * 60, 35 + (index // 3) * 65
        parts.append(f'<text x="{x}" y="{y - 6}" font-size="4">ID {m.id} · {m.role}</text>')
        for row, col in np.argwhere(cell == 0):
            parts.append(f'<rect x="{x + col * 20 / 6:.6f}" y="{y + row * 20 / 6:.6f}" '
                         f'width="{20 / 6 + .001:.6f}" height="{20 / 6 + .001:.6f}"/>')
        parts.append(f'<text x="{x}" y="{y + 27}" font-size="3">20 mm black square</text>')
    parts.append('<path d="M15 250h50m-50 -2v4m50 -4v4" fill="none" stroke="black" stroke-width=".3"/>'
                 '<text x="15" y="260" font-size="4">Check this ruler is 50 mm. Do not fit to page.</text></svg>')
    return "".join(parts)


def overlay(image, status, config):
    output = image.copy()
    proposal = status.get("proposal")
    if proposal:
        matrix = np.linalg.inv(proposal["calibration"]["homography_image_to_cm"])
        mask = np.zeros(image.shape[:2], np.uint8)
        cv2.fillPoly(mask, [np.rint(proposal["water_polygon_px"]).astype(np.int32)], 255)
        drawing = output.copy()
        for x in range(0, 41, 5):
            pts = np.rint(project(matrix, [[x, 0], [x, 30]])).astype(int)
            cv2.line(drawing, tuple(pts[0]), tuple(pts[1]), (180, 100, 20), 1)
        for y in range(0, 31, 5):
            pts = np.rint(project(matrix, [[0, y], [40, y]])).astype(int)
            cv2.line(drawing, tuple(pts[0]), tuple(pts[1]), (180, 100, 20), 1)
        output[mask > 0] = drawing[mask > 0]
        for label, layer in status["geometry_layers"].items():
            for item in layer.get("candidates", []):
                cv2.polylines(output, [np.rint(item["polygon_px"]).astype(np.int32)], True,
                              (200, 30, 200) if label == "tray_boundary" else (0, 140, 0), 2)
    cv2.rectangle(output, (0, 0), (1040, 32), (245, 245, 245), -1)
    cv2.putText(output, "SYNTHETIC | " + status["state"], (10, 23), cv2.FONT_HERSHEY_SIMPLEX,
                .55, (0, 0, 0), 1, cv2.LINE_AA)
    return output


def rehearse(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    config = synthetic_config()
    image, _ = constructed_frame(config)
    moved = cv2.warpPerspective(image, np.array([[1., .015, 22], [-.01, 1., 12],
                                                [.00001, -.00001, 1.]]),
                                (1040, 840), borderValue=(235, 235, 235))
    missing = image.copy()
    missing[30:90, 30:90] = 235
    monitor = RegistrationMonitor(config)
    rows = []
    for index in range(3):
        status = monitor.observe(image, session_id="synthetic-dry", sequence=index, t_s=index * .5,
                                 context=config.context.model_dump())
    # Dry monitor approval is illustrative; API refuses physical admission of SYNTHETIC.
    monitor.approve(status["proposal_id"], ())
    steps = [("01-aligned", image, monitor.snapshot()),
             ("02-bumped-stale", moved, monitor.observe(moved, session_id="synthetic-dry",
               sequence=3, t_s=1.5, context=config.context.model_dump()))]
    monitor = RegistrationMonitor(config)
    for i in range(3):
        status = monitor.observe(moved, session_id="synthetic-dry", sequence=i, t_s=i * .5,
                                 context=config.context.model_dump())
    steps.append(("03-realigned-candidate", moved, status))
    steps.append(("04-missing-reference", missing, monitor.observe(missing, session_id="synthetic-dry",
                 sequence=3, t_s=1.5, context=config.context.model_dump())))
    for name, frame, state in steps:
        cv2.imwrite(str(directory / f"{name}.png"), overlay(frame, state, config))
        rows.append({"step": name, "status": state})
    (directory / "reference-config.synthetic.json").write_text(
        json.dumps(config.model_dump(), indent=2, allow_nan=False) + "\n")
    (directory / "printable-markers.svg").write_text(printable_markers(config))
    report = {"schema_version": "tank_registration_rehearsal_v1", "data_origin": "SYNTHETIC",
              "physical_accuracy_validated": False, "policy": POLICY, "steps": rows}
    report["report_sha256"] = digest(report)
    (directory / "rehearsal.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = rehearse(args.output_dir)
    print(json.dumps({"report_sha256": report["report_sha256"],
                      "steps": [{"step": r["step"], "state": r["status"]["state"]}
                                for r in report["steps"]]}))


if __name__ == "__main__":
    main()
