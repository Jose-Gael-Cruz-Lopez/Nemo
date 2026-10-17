"""Preview backpressure/session/freshness regressions without opening a device."""

import asyncio
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
from apps.api.reeftrace_api.services import camera_stream
from apps.vision.reeftrace_vision import capture


def encoded_frame(sequence=1, *, received=100.0):
    ok, jpeg = cv2.imencode(".jpg", np.zeros((12, 16, 3), dtype=np.uint8))
    assert ok
    return {"sequence": sequence, "received_mono_s": received,
            "received_utc": "2026-10-17T12:00:00+00:00", "width": 16,
            "height": 12, "jpeg": jpeg.tobytes(), "backend": "TEST"}


@pytest.fixture
def camera(monkeypatch):
    # Keep asyncio's real monotonic clock running while pinning camera receipt age.
    monkeypatch.setattr(capture, "time", SimpleNamespace(monotonic=lambda: 100.0))
    camera = capture.Camera()
    camera.process = SimpleNamespace(is_alive=lambda: True)
    camera.session_id = "usb-stream-test"
    camera.device = 0
    camera.latest = encoded_frame()
    return camera


@pytest.fixture
def app(tmp_path, monkeypatch, camera):
    for key in ("PHOTON_ENABLED", "CHALK_ENABLED", "GROK_VOICE_ENABLED"):
        monkeypatch.setenv(key, "false")
    monkeypatch.setenv("PHOTON_ROUTES_JSON", "[]")
    app = create_app(Settings(data_dir=tmp_path, local_token="stream-test-only"))
    app.state.runtime.camera = camera
    return app


def test_preview_reuses_exact_encoded_bytes_without_decode_or_reencode(camera, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Preview must not open, decode or re-encode a camera")

    monkeypatch.setattr(capture.cv2, "imdecode", forbidden)
    monkeypatch.setattr(capture.cv2, "imencode", forbidden)
    monkeypatch.setattr(capture.cv2, "VideoCapture", forbidden)
    status, frame = camera.preview_snapshot()
    assert status["fresh"] is True
    assert status["session_id"] == frame["session_id"] == "usb-stream-test"
    assert frame["jpeg"] is camera.latest["jpeg"]
    assert frame["sequence"] == status["sequence"] == 1


@pytest.mark.parametrize("change", ["stale", "future", "stopped", "empty", "invalid-jpeg"])
def test_unavailable_preview_returns_no_store_json_before_stream_headers(app, camera, change):
    if change == "stale":
        camera.latest["received_mono_s"] = 97.9
    elif change == "future":
        camera.latest["received_mono_s"] = 100.1
    elif change == "stopped":
        camera.process = None
    elif change == "empty":
        camera.latest = None
    else:
        camera.latest["jpeg"] = b"invalid-jpeg"
    response = TestClient(app).get("/api/v1/camera/stream.mjpg?session_id=usb-stream-test")
    assert response.status_code == 503
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == "no-store"
    assert "detail" in response.json()


def test_old_or_absent_session_cannot_attach_to_a_new_camera(app):
    client = TestClient(app)
    response = client.get("/api/v1/camera/stream.mjpg?session_id=usb-old")
    assert response.status_code == 409
    assert response.headers["cache-control"] == "no-store"
    assert "session changed" in response.json()["detail"]
    assert client.get("/api/v1/camera/stream.mjpg").status_code == 422
    assert client.get("/api/v1/camera/stream.mjpg?session_id=").status_code == 422


def test_real_asgi_stream_has_multipart_lengths_and_exits_on_disconnect(app, camera):
    async def run():
        disconnected = asyncio.Event()
        sent = []
        parts = []

        async def receive():
            await disconnected.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)
            if message["type"] == "http.response.body" and message.get("body"):
                parts.append(message["body"])
                if len(parts) == 1:
                    camera.latest = encoded_frame(2)
                else:
                    disconnected.set()

        scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
                 "http_version": "1.1", "method": "GET", "scheme": "http",
                 "path": "/api/v1/camera/stream.mjpg", "raw_path": b"/api/v1/camera/stream.mjpg",
                 "query_string": b"session_id=usb-stream-test", "headers": [],
                 "client": ("127.0.0.1", 1234), "server": ("127.0.0.1", 8000)}
        await asyncio.wait_for(app(scope, receive, send), timeout=2)
        start = next(message for message in sent if message["type"] == "http.response.start")
        headers = dict(start["headers"])
        assert start["status"] == 200
        assert headers[b"content-type"] == (
            b"multipart/x-mixed-replace; boundary=tideward-frame")
        assert headers[b"cache-control"] == b"no-store"
        assert headers[b"x-accel-buffering"] == b"no"
        assert len(parts) == 2
        for sequence, part in enumerate(parts, 1):
            head, content = part.split(b"\r\n\r\n", 1)
            jpeg = encoded_frame()["jpeg"]
            assert head.startswith(b"--tideward-frame\r\nContent-Type: image/jpeg\r\n")
            assert f"Content-Length: {len(jpeg)}".encode() in head
            assert f"X-Frame-Id: {sequence}".encode() in head
            assert content == jpeg + b"\r\n"
        assert app.state.runtime.store.cases() == []

    asyncio.run(run())


def test_slow_or_idle_preview_never_replays_backlog_or_duplicate_frames(camera, monkeypatch):
    sleeps = []

    async def wait_latest(delay):
        sleeps.append(delay)
        if len(sleeps) == 2:
            # Simulate a consumer resuming after many capture frames elapsed.
            camera.latest = encoded_frame(400)
        if len(sleeps) == 3:
            camera.process = None

    async def connected():
        return False

    monkeypatch.setattr(camera_stream.asyncio, "sleep", wait_latest)

    async def run():
        request = SimpleNamespace(is_disconnected=connected)
        return [part async for part in camera_stream.iter_camera_mjpeg(
            camera, request, "usb-stream-test")]

    parts = asyncio.run(run())
    assert len(parts) == 2
    assert b"X-Frame-Id: 1\r\n" in parts[0]
    assert b"X-Frame-Id: 400\r\n" in parts[1]
    assert len(sleeps) == 3
    assert all(delay >= 1 / 15 for delay in sleeps)


@pytest.mark.parametrize("change", ["session", "stale", "invalid", "backward-sequence"])
def test_stream_ends_without_switching_session_or_sending_bad_frames(camera, monkeypatch, change):
    async def change_camera(delay):
        if change == "session":
            camera.session_id = "usb-replacement"
            camera.latest["sequence"] = 2
        elif change == "stale":
            camera.latest["received_mono_s"] = 97.0
        elif change == "invalid":
            camera.latest["jpeg"] = b"not-a-jpeg"
        else:
            camera.latest["sequence"] = 0

    async def connected():
        return False

    monkeypatch.setattr(camera_stream.asyncio, "sleep", change_camera)

    async def run():
        return [part async for part in camera_stream.iter_camera_mjpeg(
            camera, SimpleNamespace(is_disconnected=connected), "usb-stream-test")]

    assert len(asyncio.run(run())) == 1


def test_cancellation_does_not_stop_shared_capture_or_leave_background_work(camera, monkeypatch):
    async def run():
        entered_sleep = asyncio.Event()

        async def pending_sleep(delay):
            entered_sleep.set()
            await asyncio.Event().wait()

        async def connected():
            return False

        monkeypatch.setattr(camera_stream.asyncio, "sleep", pending_sleep)

        async def consume():
            async for _ in camera_stream.iter_camera_mjpeg(
                    camera, SimpleNamespace(is_disconnected=connected), "usb-stream-test"):
                pass

        task = asyncio.create_task(consume())
        await asyncio.wait_for(entered_sleep.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert camera.process.is_alive()
        assert camera.session_id == "usb-stream-test"
        assert task.done()

    asyncio.run(run())


def test_legacy_jpeg_endpoint_still_returns_identical_camera_frame(app, camera):
    response = TestClient(app).get("/api/v1/camera/frame.jpg")
    assert response.status_code == 200
    assert response.content == camera.latest["jpeg"]
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["x-frame-id"] == "1"
    assert response.headers["cache-control"] == "no-store"
