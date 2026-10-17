"""Camera lifecycle/freshness regressions; no real USB camera is opened."""

import threading
from queue import Queue
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from apps.vision.reeftrace_vision import capture


class FakeQueue(Queue):
    closed = False
    feeder_join_cancelled = False

    def close(self):
        self.closed = True

    def cancel_join_thread(self):
        self.feeder_join_cancelled = True


class FakeProcess:
    def __init__(self, *, target, args, daemon):
        self.alive = False
        self.terminated = False
        self.killed = False
        self.fail_start = False
        self.ignore_terminate = False
        self.stop_event = args[-1]
        self.exit_on_stop = False
        self.join_timeouts = []

    def start(self):
        if self.fail_start:
            raise OSError("Simulated spawn failure")
        self.alive = True

    def is_alive(self):
        return self.alive

    def terminate(self):
        self.terminated = True
        if not self.ignore_terminate:
            self.alive = False

    def join(self, timeout=None):
        self.join_timeouts.append(timeout)
        if self.exit_on_stop and self.stop_event.is_set():
            self.alive = False

    def kill(self):
        self.killed = True
        self.alive = False


class FakeContext:
    def __init__(self):
        self.processes = []
        self.queues = []
        self.fail_start = False

    def Queue(self, maxsize):
        queue = FakeQueue(maxsize)
        self.queues.append(queue)
        return queue

    def Event(self):
        return threading.Event()

    def Process(self, **kwargs):
        process = FakeProcess(**kwargs)
        process.fail_start = self.fail_start
        self.processes.append(process)
        return process


def frame(*, age=0, sequence=1, utc="2026-10-16T22:00:00.123456+00:00"):
    ok, image = cv2.imencode(".jpg", np.zeros((12, 12, 3), np.uint8))
    assert ok
    return {
        "sequence": sequence,
        "received_mono_s": 100.0 - age,
        "received_utc": utc,
        "width": 12,
        "height": 12,
        "jpeg": image.tobytes(),
        "backend": "FAKE",
    }


def ready_camera(monkeypatch):
    monkeypatch.setattr(capture.time, "monotonic", lambda: 100.0)
    camera = capture.Camera(stale_s=2)
    camera.process = SimpleNamespace(is_alive=lambda: True)
    camera.session_id = "session-one"
    camera.latest = frame()
    return camera


def test_stale_returned_frame_cannot_borrow_newer_frame_freshness(monkeypatch):
    camera = ready_camera(monkeypatch)
    camera.latest = frame(age=8)
    # Force the old two-snapshot implementation's failure: status would see a
    # new frame although image() had already chosen the old eight-second frame.
    snapshots = iter(
        [
            {**camera.latest, "session_id": camera.session_id},
            {**frame(sequence=2), "session_id": camera.session_id},
        ]
    )
    monkeypatch.setattr(camera, "snapshot", lambda: next(snapshots))
    with pytest.raises(ValueError, match="stale"):
        camera.image()


def test_fresh_image_preserves_exact_receipt_utc_and_session(monkeypatch):
    camera = ready_camera(monkeypatch)
    image, metadata = camera.image()
    assert image.shape == (12, 12, 3)
    assert metadata["received_utc"] == "2026-10-16T22:00:00.123456+00:00"
    assert metadata["received_mono_s"] == 100.0
    assert metadata["session_id"] == "session-one"
    assert metadata["sequence"] == 1


@pytest.mark.parametrize("age", [2.001, -0.01])
def test_image_rejects_expired_or_future_timestamp(monkeypatch, age):
    camera = ready_camera(monkeypatch)
    camera.latest = frame(age=age)
    assert camera.status()["fresh"] is False
    with pytest.raises(ValueError, match="stale"):
        camera.image()


def test_dead_worker_and_invalid_jpeg_are_refused(monkeypatch):
    camera = ready_camera(monkeypatch)
    camera.process = SimpleNamespace(is_alive=lambda: False)
    with pytest.raises(ValueError, match="unavailable"):
        camera.image()
    camera.process = SimpleNamespace(is_alive=lambda: True)
    camera.latest["jpeg"] = b"not-a-jpeg"
    with pytest.raises(ValueError, match="JPEG"):
        camera.image()


def test_concurrent_starts_do_not_orphan_a_worker(monkeypatch):
    context = FakeContext()
    monkeypatch.setattr(capture.mp, "get_context", lambda method: context)
    camera = capture.Camera()
    old_stop = camera.stop
    barrier = threading.Barrier(2)

    def interleaved_public_stop():
        old_stop()
        # Both old-style starts finish stop() before either spawns a worker.
        # The fixed atomic lifecycle uses its internal locked stop instead.
        barrier.wait(timeout=2)

    monkeypatch.setattr(camera, "stop", interleaved_public_stop)
    errors = []

    def start(device):
        try:
            camera.start(device)
        except (OSError, RuntimeError) as error:
            errors.append(error)

    threads = [threading.Thread(target=start, args=(device,)) for device in (0, 1)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)
    assert not errors
    assert all(not thread.is_alive() for thread in threads)
    assert len(context.processes) == 2
    assert sum(process.is_alive() for process in context.processes) == 1
    assert context.processes[0].terminated
    assert camera.process is context.processes[1]
    assert context.queues[0].closed
    old_stop()


def test_status_is_consistent_while_a_stop_waits(monkeypatch):
    context = FakeContext()
    monkeypatch.setattr(capture.mp, "get_context", lambda method: context)
    monkeypatch.setattr(capture.time, "monotonic", lambda: 100.0)
    camera = capture.Camera()
    camera.start(0)
    camera.latest = frame()
    session = camera.session_id
    entered = threading.Event()
    release = threading.Event()
    stop_attempted = threading.Event()
    stopped = threading.Event()
    original_alive = camera.process.is_alive

    def gated_alive():
        entered.set()
        assert release.wait(timeout=2)
        return original_alive()

    camera.process.is_alive = gated_alive
    results = []
    status_thread = threading.Thread(target=lambda: results.append(camera.status()))
    status_thread.start()
    assert entered.wait(timeout=2)

    def stop():
        stop_attempted.set()
        camera.stop()
        stopped.set()

    stop_thread = threading.Thread(target=stop)
    stop_thread.start()
    assert stop_attempted.wait(timeout=2)
    assert not stopped.wait(timeout=0.02)
    release.set()
    status_thread.join(timeout=2)
    stop_thread.join(timeout=2)
    assert results[0]["session_id"] == session
    assert results[0]["fresh"] is True
    assert stopped.is_set()
    assert camera.status()["session_id"] is None


def test_failed_spawn_closes_queue_and_does_not_publish_session(monkeypatch):
    context = FakeContext()
    context.fail_start = True
    monkeypatch.setattr(capture.mp, "get_context", lambda method: context)
    camera = capture.Camera()
    with pytest.raises(OSError, match="spawn"):
        camera.start(0)
    assert context.queues[0].closed
    assert camera.process is None and camera.session_id is None and camera.queue is None


def test_bounded_stop_kills_a_hung_worker_and_clears_session(monkeypatch):
    context = FakeContext()
    monkeypatch.setattr(capture.mp, "get_context", lambda method: context)
    camera = capture.Camera()
    camera.start(0)
    process = camera.process
    process.ignore_terminate = True
    camera.stop()
    assert process.terminated and process.killed
    assert process.stop_event.is_set()
    assert process.join_timeouts == [capture.GRACEFUL_STOP_S, 1, 1]
    assert not process.is_alive()
    assert context.queues[0].closed
    assert camera.status() == {
        "running": False,
        "session_id": None,
        "device_index": None,
        "fresh": False,
        "age_s": None,
        "sequence": None,
        "width": None,
        "height": None,
        "backend": None,
    }


def test_normal_stop_releases_worker_before_forced_termination(monkeypatch):
    context = FakeContext()
    monkeypatch.setattr(capture.mp, "get_context", lambda method: context)
    camera = capture.Camera()
    camera.start(0)
    process = camera.process
    process.exit_on_stop = True
    camera.stop()
    assert process.stop_event.is_set()
    assert not process.alive
    assert not process.terminated and not process.killed
    assert process.join_timeouts[0] == capture.GRACEFUL_STOP_S
    assert context.queues[0].closed
    assert camera.stop_event is None


def test_replacement_waits_for_old_release_and_keeps_only_one_owner(monkeypatch):
    context = FakeContext()
    monkeypatch.setattr(capture.mp, "get_context", lambda method: context)
    camera = capture.Camera()
    camera.start(0)
    first = camera.process
    first.exit_on_stop = True
    first_session = camera.session_id
    camera.start(0)
    assert first.stop_event.is_set() and not first.is_alive()
    assert not first.terminated and not first.killed
    assert context.queues[0].closed
    assert camera.session_id != first_session
    assert camera.process is context.processes[1]
    assert camera.stop_event is context.processes[1].stop_event
    assert not camera.stop_event.is_set()
    assert sum(process.is_alive() for process in context.processes) == 1
    camera.stop()


class WorkerStop:
    def __init__(self, clock, *, cancel_first_wait=False):
        self.clock = clock
        self.cancel_first_wait = cancel_first_wait
        self.stopped = False
        self.waits = []

    def is_set(self):
        return self.stopped

    def set(self):
        self.stopped = True

    def wait(self, delay):
        self.waits.append(delay)
        self.clock[0] += delay
        if self.cancel_first_wait:
            self.set()
        return self.stopped


class WorkerCapture:
    def __init__(self, outcomes, *, opened=True, on_read=None):
        self.outcomes = iter(outcomes)
        self.opened = opened
        self.on_read = on_read
        self.read_count = 0
        self.release_count = 0

    def isOpened(self):
        return self.opened

    def set(self, prop, value):
        raise AssertionError("Capture must preserve the backend's negotiated native mode")

    def read(self):
        self.read_count += 1
        if self.on_read:
            self.on_read()
        if next(self.outcomes, False):
            return True, np.zeros((12, 16, 3), dtype=np.uint8)
        return False, None

    def getBackendName(self):
        return "FAKE_WORKER"

    def release(self):
        self.release_count += 1


def run_fake_worker(monkeypatch, outcomes, *, cancel_first_wait=False, opened=True,
                    stop_on_read=False):
    clock = [100.0]
    stop = WorkerStop(clock, cancel_first_wait=cancel_first_wait)
    cap = WorkerCapture(outcomes, opened=opened, on_read=stop.set if stop_on_read else None)
    queue = FakeQueue(1)
    monkeypatch.setattr(capture, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(capture.cv2, "VideoCapture", lambda *args: cap)
    capture._capture_worker(0, queue, stop)
    return cap, queue, stop


def test_worker_recovers_transient_first_frame_read_then_exits_on_established_loss(monkeypatch):
    cap, queue, stop = run_fake_worker(monkeypatch, [False, False, True, False, True])
    assert cap.read_count == 4  # The second possible success must never be read.
    assert stop.waits == [capture.FIRST_FRAME_RETRY_S] * 2
    item = queue.get_nowait()
    assert item["sequence"] == 1
    assert item["received_mono_s"] == pytest.approx(100.1)
    assert item["width"] == 16 and item["height"] == 12
    assert cap.release_count == 1
    assert queue.feeder_join_cancelled


def test_worker_first_frame_retry_is_bounded_and_never_fakes_a_frame(monkeypatch, caplog):
    cap, queue, stop = run_fake_worker(monkeypatch, [])
    assert sum(stop.waits) == pytest.approx(capture.FIRST_FRAME_WARMUP_S)
    assert cap.read_count <= 42
    assert queue.empty()
    assert cap.release_count == 1
    assert queue.feeder_join_cancelled
    assert "first-frame timeout" in caplog.text


def test_worker_stop_interrupts_warmup_and_runs_native_release(monkeypatch):
    cap, queue, stop = run_fake_worker(monkeypatch, [], cancel_first_wait=True)
    assert cap.read_count == 1
    assert len(stop.waits) == 1
    assert stop.is_set()
    assert queue.empty()
    assert cap.release_count == 1
    assert queue.feeder_join_cancelled


def test_worker_does_not_publish_a_frame_if_stopped_during_native_read(monkeypatch):
    cap, queue, _ = run_fake_worker(monkeypatch, [True], stop_on_read=True)
    assert cap.read_count == 1 and queue.empty()
    assert cap.release_count == 1
    assert queue.feeder_join_cancelled


def test_unopenable_device_is_not_reopened_or_retried(monkeypatch, caplog):
    cap, queue, stop = run_fake_worker(monkeypatch, [], opened=False)
    assert cap.read_count == 0 and stop.waits == []
    assert queue.empty()
    assert cap.release_count == 1
    assert queue.feeder_join_cancelled
    assert "USB camera 0 could not be opened" in caplog.text
