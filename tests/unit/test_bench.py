from fastapi.testclient import TestClient

from apps.api.reeftrace_api.main import app

client = TestClient(app)


def test_telemetry_and_no_collection():
    event = {
        "type": "telemetry",
        "uptime_ms": 100,
        "distance_cm": None,
        "pot_raw": 512,
        "armed": False,
        "pan_deg": 90,
        "tilt_deg": 90,
    }
    assert client.post("/api/v1/bench/telemetry", json=event).status_code == 200
    status = client.get("/api/v1/bench").json()
    assert status["connected"] and status["telemetry"] == event
    assert status["collection_enabled"] is False
    event["distance_cm"] = 500
    assert client.post("/api/v1/bench/telemetry", json=event).status_code == 422


def test_demo_routes():
    assert client.get("/api/v1/demo/moving").json()["estimate"]["source"] == "B"
    assert client.get("/api/v1/demo/invalid").status_code == 422
