"""USB acquisition in an isolated process. A native read cannot block the API."""

from __future__ import annotations

import logging
import multiprocessing as mp
import threading
import time
import uuid
from datetime import UTC, datetime
from queue import Empty, Full

import cv2
import numpy as np

FIRST_FRAME_WARMUP_S = 2.0
FIRST_FRAME_RETRY_S = 0.05
GRACEFUL_STOP_S = 1.0
LOGGER = logging.getLogger(__name__)


def _capture_worker(index, queue, stop_event):
    cap = cv2.VideoCapture(index, cv2.CAP_ANY)
    try:
        if not cap.isOpened():
            LOGGER.warning("USB camera %s could not be opened", index)
            return
        # Preserve the device/backend's negotiated native mode. Some USB cameras
        # accept unsupported width/height setters but then fail every read;
        # requesting a large display does not require renegotiating the sensor.
        seq = 0
        first_frame_deadline = time.monotonic() + FIRST_FRAME_WARMUP_S
        while not stop_event.is_set():
            ok, image = cap.read()
            if not ok:
                # Some USB backends briefly report no frame while acquiring a
                # just-released device. This is startup-only, bounded and
                # cancellable; loss of an established recording still exits.
                remaining = first_frame_deadline - time.monotonic()
                if seq == 0 and remaining > 0:
                    stop_event.wait(min(FIRST_FRAME_RETRY_S, remaining))
                    continue
                LOGGER.warning("USB camera %s frame read failed (%s)", index,
                               "first-frame timeout" if seq == 0 else "established stream")
                return
            if stop_event.is_set():
                return
            received = time.monotonic()
            utc = datetime.now(UTC).isoformat()
            ok, jpg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
            if not ok:
                if seq == 0 and time.monotonic() >= first_frame_deadline:
                    return
                continue
            seq += 1
            item = {
                "sequence": seq,
                "received_mono_s": received,
                "received_utc": utc,
                "width": image.shape[1],
                "height": image.shape[0],
                "jpeg": jpg.tobytes(),
                "backend": cap.getBackendName(),
            }
            try:
                queue.put_nowait(item)
            except Full:
                try:
                    queue.get_nowait()
                except Empty:
                    pass
                try:
                    queue.put_nowait(item)
                except Full:
                    pass
    finally:
        cap.release()
        # No queued preview frame needs flushing after this worker exits. Avoid
        # waiting on its feeder while the parent is joining during a USB stop.
        queue.cancel_join_thread()


class Camera:
    def __init__(self, stale_s=2):
        self.stale_s = stale_s
        self.lock = threading.RLock()
        self.process = self.queue = self.latest = self.session_id = None
        self.stop_event = None
        self.device = None

    def start(self, device):
        with self.lock:
            # Stop and replacement form one lifecycle operation. Concurrent starts
            # cannot overwrite the only reference to a still-running worker.
            self._stop_locked()
            ctx = mp.get_context("spawn")
            queue = ctx.Queue(maxsize=1)
            stop_event = ctx.Event()
            process = ctx.Process(target=_capture_worker, args=(device, queue, stop_event),
                                  daemon=True)
            try:
                process.start()
            except BaseException:
                queue.close()
                raise
            self.queue = queue
            self.process = process
            self.stop_event = stop_event
            self.session_id = "usb-" + uuid.uuid4().hex[:16]
            self.device = device
            return self._status_locked(self._snapshot_locked())

    def _snapshot_locked(self):
        if self.queue is not None:
            while True:
                try:
                    self.latest = self.queue.get_nowait()
                except Empty:
                    break
        if self.latest is None:
            return None
        return {**self.latest, "session_id": self.session_id}

    def snapshot(self):
        with self.lock:
            return self._snapshot_locked()

    def _status_locked(self, frame):
        # Pin the process and all session metadata under the same lock as frame
        # selection; stop/start cannot change them between these reads.
        process = self.process
        running = process is not None and process.is_alive()
        age = None if frame is None else time.monotonic() - frame["received_mono_s"]
        return {
            "running": running,
            "session_id": self.session_id,
            "device_index": self.device,
            "fresh": bool(running and age is not None and 0 <= age <= self.stale_s),
            "age_s": age,
            "sequence": frame["sequence"] if frame else None,
            "width": frame["width"] if frame else None,
            "height": frame["height"] if frame else None,
            "backend": frame["backend"] if frame else None,
        }

    def status(self):
        with self.lock:
            return self._status_locked(self._snapshot_locked())

    def preview_snapshot(self):
        """Return one fresh, session-consistent encoded frame without JPEG decoding.

        The capture process already encoded these bytes. Preview consumers share
        this single latest-frame slot instead of opening another camera, copying
        a frame history or re-encoding an image for every connected viewer.
        """
        with self.lock:
            frame = self._snapshot_locked()
            status = self._status_locked(frame)
            if frame is None or not status["fresh"]:
                raise ValueError("Camera is stopped, unavailable or stale")
            jpeg = frame.get("jpeg")
            if (not isinstance(jpeg, bytes) or len(jpeg) < 4
                    or not jpeg.startswith(b"\xff\xd8") or not jpeg.endswith(b"\xff\xd9")):
                raise ValueError("Camera returned an invalid JPEG frame")
            return status, frame

    def image(self):
        with self.lock:
            frame = self._snapshot_locked()
            # Freshness refers to this exact frame, never a second newer snapshot.
            if frame is None or not self._status_locked(frame)["fresh"]:
                raise ValueError("Camera is stopped, unavailable or stale")
            image = cv2.imdecode(np.frombuffer(frame["jpeg"], np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("Camera returned an invalid JPEG frame")
            return image, frame

    def _stop_locked(self):
        process = self.process
        if process is not None:
            if self.stop_event is not None:
                self.stop_event.set()
                # Let normal native reads return and cap.release() run. A hung
                # backend remains bounded by the terminate/kill fallback below.
                process.join(timeout=GRACEFUL_STOP_S)
            if process.is_alive():
                process.terminate()
            process.join(timeout=1)
            if process.is_alive():
                process.kill()
                process.join(timeout=1)
            if process.is_alive():
                # Keep the reference so a failed stop cannot silently orphan it.
                raise RuntimeError("Camera capture worker did not stop")
        if self.queue is not None:
            self.queue.close()
        self.process = self.queue = self.latest = self.session_id = None
        self.stop_event = None
        self.device = None

    def stop(self):
        with self.lock:
            self._stop_locked()
