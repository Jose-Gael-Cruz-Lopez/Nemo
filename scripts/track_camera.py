"""Record one colored floating token with explicit gaps and a permitted region.
No camera or motor is opened when importing this module.
"""

import argparse
import json
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv


def main():
    import os

    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--camera", type=int, default=int(os.environ.get("REEFTRACE_CAMERA_INDEX", "0"))
    )
    parser.add_argument(
        "--backend", choices=["auto", "dshow", "msmf", "avfoundation"], default="auto"
    )
    parser.add_argument("--calibration", required=True)
    parser.add_argument(
        "--site", required=True, help="Measured v3 profile JSON; geometry and inference mask"
    )
    parser.add_argument("--output", default="data/runs/camera_observation.json")
    parser.add_argument("--seconds", type=float, default=15)
    parser.add_argument(
        "--start-after-s", type=float, default=3, help="Hide release segment from inference"
    )
    parser.add_argument("--purpose", choices=["case", "flow_measurement"], default="case")
    parser.add_argument(
        "--evidence-mode", choices=["trajectory", "retained_endpoint"], default="trajectory"
    )
    parser.add_argument("--retained-trap")
    parser.add_argument(
        "--raw-video", help="Evaluator-only full-frame archive; never sent to inference"
    )
    parser.add_argument("--hue-low", type=int, default=35)
    parser.add_argument("--hue-high", type=int, default=85)
    parser.add_argument(
        "--live-submit", action="store_true", help="Submit this actual new recording to local API"
    )
    args = parser.parse_args()
    from apps.core.reeftrace_core.contracts import Profile

    profile = Profile.model_validate_json(Path(args.site).read_text())
    calibration = json.loads(Path(args.calibration).read_text())
    if (
        calibration.get("calibration_id") != profile.id
        or calibration.get("measurement_plane") != "water_surface"
    ):
        raise ValueError("Matching water-surface calibration required")
    matrix = np.asarray(calibration["homography"], np.float64)
    if (
        matrix.shape != (3, 3)
        or not np.isfinite(matrix).all()
        or abs(np.linalg.det(matrix)) < 1e-12
    ):
        raise ValueError("Invalid homography")
    if (
        not 0 <= args.hue_low <= args.hue_high <= 179
        or args.seconds <= args.start_after_s
        or args.start_after_s < 0
    ):
        raise ValueError("Invalid hue range or recording duration")
    if args.evidence_mode == "retained_endpoint" and not args.retained_trap:
        raise ValueError("Endpoint-only recording requires an identified verified surface trap")
    backend = {
        "auto": cv2.CAP_ANY,
        "dshow": cv2.CAP_DSHOW,
        "msmf": cv2.CAP_MSMF,
        "avfoundation": cv2.CAP_AVFOUNDATION,
    }[args.backend]
    camera = cv2.VideoCapture(args.camera, backend)
    if not camera.isOpened():
        raise RuntimeError(
            "Camera unavailable; check OS permission, USB data connection and camera index"
        )
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    camera.set(cv2.CAP_PROP_FPS, 30)
    actual = {
        "width": int(camera.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": camera.get(cv2.CAP_PROP_FPS),
        "backend": camera.getBackendName(),
    }
    expected = calibration.get("capture_size")
    if not expected or expected != [actual["width"], actual["height"]]:
        camera.release()
        raise ValueError(
            "Actual capture resolution differs from calibration capture_size; recalibrate"
        )
    inverse = np.linalg.inv(matrix)
    region = (
        profile.observation_polygon_cm
        if args.purpose == "case"
        else [
            (0, 0),
            (profile.width_cm, 0),
            (profile.width_cm, profile.height_cm),
            (0, profile.height_cm),
        ]
    )
    world = np.float32(region)[None]
    mask_polygon = cv2.perspectiveTransform(world, inverse)[0].astype(np.int32)
    observations, misses, writer = [], 0, None
    run_id = "camera-" + str(time.time_ns())
    frames_dir = Path("data/runs/frames")
    frames_dir.mkdir(parents=True, exist_ok=True)
    endpoint_frame = None
    start, time_origin, last_sample = time.monotonic(), time.time(), -1.0
    last_observed_at = None
    try:
        if args.raw_video:
            Path(args.raw_video).parent.mkdir(parents=True, exist_ok=True)
            writer = cv2.VideoWriter(
                args.raw_video,
                cv2.VideoWriter_fourcc(*"MJPG"),
                actual["fps"] or 30,
                (actual["width"], actual["height"]),
            )
            if not writer.isOpened():
                raise RuntimeError("Raw recording writer unavailable")
        while time.monotonic() - start < args.seconds:
            ok, frame = camera.read()
            if not ok:
                raise RuntimeError("Camera frame failed; no new observation inferred")
            elapsed = time.monotonic() - start
            if writer:
                writer.write(frame)
            if elapsed < args.start_after_s or elapsed - last_sample < 0.1:
                continue
            last_sample = elapsed
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(
                hsv, np.array([args.hue_low, 80, 60]), np.array([args.hue_high, 255, 255])
            )
            roi = np.zeros(mask.shape, np.uint8)
            cv2.fillPoly(roi, [mask_polygon], 255)
            mask = cv2.bitwise_and(mask, roi)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            blobs = [c for c in contours if cv2.contourArea(c) >= 30]
            frame_id = f"{run_id}-{int(elapsed * 1000)}"
            permitted_frame = cv2.bitwise_and(frame, frame, mask=roi)
            if args.evidence_mode == "trajectory":
                if not cv2.imwrite(str(frames_dir / (frame_id + ".jpg")), permitted_frame):
                    raise RuntimeError("Evidence frame write failed")
            else:
                endpoint_frame = (frame_id, permitted_frame.copy())
            if len(blobs) != 1:
                misses += 1
                observations.append(
                    {
                        "t": elapsed,
                        "x": 0.0,
                        "y": 0.0,
                        "observed": False,
                        "quality": 0.0,
                        "frame_id": frame_id,
                    }
                )
                continue
            moments = cv2.moments(blobs[0])
            px, py = moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]
            x, y = cv2.perspectiveTransform(np.float32([[[px, py]]]), matrix)[0, 0]
            observations.append(
                {
                    "t": elapsed,
                    "x": float(x),
                    "y": float(y),
                    "pixel_x": px,
                    "pixel_y": py,
                    "observed": True,
                    "quality": 1.0,
                    "frame_id": frame_id,
                }
            )
            last_observed_at = time_origin + elapsed
    finally:
        camera.release()
        if writer:
            writer.release()
    if args.evidence_mode == "retained_endpoint":
        # Explicit first-seen retained mode never exports an earlier moving path.
        observations = observations[-1:]
        if endpoint_frame is not None and not cv2.imwrite(
            str(frames_dir / (endpoint_frame[0] + ".jpg")), endpoint_frame[1]
        ):
            raise RuntimeError("Endpoint evidence frame write failed")
    if not observations:
        raise RuntimeError("No frames recorded in permitted interval")
    case = {
        "run_id": run_id,
        "calibration_id": profile.id,
        "token_class": profile.token_class,
        "mode": "live" if args.live_submit else "recorded",
        "evidence_mode": args.evidence_mode,
        "retained_trap_id": args.retained_trap,
        "observation_region_declared": True,
        "last_observed_at": last_observed_at,
        "track": observations,
    }
    record = {
        **case,
        "purpose": args.purpose,
        "capture": actual,
        "rejected_frames": misses,
        "source": "Unknown",
        "reason": "Requires registered measured profile and estimator; recording alone is not attribution",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2, allow_nan=False))
    if args.live_submit:
        if args.purpose != "case":
            raise ValueError("Flow measurements cannot be submitted as source cases")
        token = os.environ.get("REEFTRACE_LOCAL_TOKEN", "")
        request = urllib.request.Request(
            "http://127.0.0.1:8000/v1/cases",
            data=json.dumps(case).encode(),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            print(response.read().decode())
    print(
        f"Saved {len(observations)} points and {misses} gaps to {output}; actual capture: {actual}"
    )


if __name__ == "__main__":
    main()
