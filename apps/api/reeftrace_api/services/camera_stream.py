"""Bounded, latest-frame-only preview; recording keeps its independent cadence."""

from __future__ import annotations

import asyncio

PREVIEW_INTERVAL_S = 1 / 15
MJPEG_BOUNDARY = "tideward-frame"


async def iter_camera_mjpeg(camera, request, session_id: str):
    """Never queue frames for a slow viewer or follow a replacement USB session."""
    last_sequence = 0
    while not await request.is_disconnected():
        try:
            status, frame = camera.preview_snapshot()
        except ValueError:
            return
        if status["session_id"] != session_id or frame["session_id"] != session_id:
            return
        sequence = frame["sequence"]
        if not isinstance(sequence, int) or sequence < last_sequence or sequence <= 0:
            return
        if sequence > last_sequence:
            jpeg = frame["jpeg"]
            # The immutable JPEG bytes are the exact capture-process output.
            # Backpressure resumes here, then the next iteration reads latest.
            yield (f"--{MJPEG_BOUNDARY}\r\n"
                   "Content-Type: image/jpeg\r\n"
                   f"Content-Length: {len(jpeg)}\r\n"
                   f"X-Frame-Id: {sequence}\r\n\r\n").encode("ascii") + jpeg + b"\r\n"
            last_sequence = sequence
        # Even repeated/unchanged frames yield to the event loop. Cancellation
        # propagates immediately; no capture process or queue belongs to a viewer.
        await asyncio.sleep(PREVIEW_INTERVAL_S)
