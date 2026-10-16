import time

import pytest

from apps.core.reeftrace_core.store import Store


def fresh(store, mode="live"):
    record = store.put(
        "case", {"mode": mode, "calibration_id": "CAL-test", "last_observed_at": time.time()}
    )
    evidence = store.put("estimate", {"status": "ranked"}, record["id"])
    store.check_rig("CAL-test")
    return record, evidence


def test_atomic_approval_duplicate_expiry_and_wrong_conversation(tmp_path):
    store = Store(tmp_path / "evidence.db")
    case, evidence = fresh(store)
    p = store.propose(case["id"], evidence["id"], "operator", "space")
    with pytest.raises(ValueError):
        store.approve(p["id"], p["approval_token"], "operator", "other-space")
    assert store.approve(p["id"], p["approval_token"], "operator", "space")["state"] == "acting"
    with pytest.raises(ValueError):
        store.approve(p["id"], p["approval_token"], "operator", "space")
    q = store.propose(case["id"], evidence["id"], "operator", "space")
    with store.connect() as db:
        db.execute("UPDATE actions SET expires=0 WHERE id=?", (q["id"],))
    with pytest.raises(ValueError):
        store.approve(q["id"], q["approval_token"], "operator", "space")


def test_restart_and_stale_evidence_prevent_action(tmp_path):
    store = Store(tmp_path / "evidence.db")
    case, evidence = fresh(store)
    p = store.propose(case["id"], evidence["id"], "operator", "space")
    store.put("estimate", {"status": "unknown"}, case["id"])
    with pytest.raises(ValueError):
        store.approve(p["id"], p["approval_token"], "operator", "space")
    store.startup_reset()
    assert store.action(p["id"])["state"] == "expired"


def test_synthetic_cannot_act_and_rig_invalidation_stops_tasks(tmp_path):
    store = Store(tmp_path / "evidence.db")
    case, evidence = fresh(store, "synthetic")
    p = store.propose(case["id"], evidence["id"], "operator", "space")
    with pytest.raises(ValueError):
        store.approve(p["id"], p["approval_token"], "operator", "space")
    store.invalidate_rig()
    assert store.action(p["id"])["state"] == "stopped"


def test_durable_message_dedup_and_immutable_outbox(tmp_path):
    path = tmp_path / "evidence.db"
    store = Store(path)
    message = {"id": "vendor-1", "space_id": "space", "agent_id": "agent", "text": "hello"}
    assert store.ingest_once(message)
    assert not Store(path).ingest_once(message)
    assert store.claim_message() == message
    assert store.claim_message() is None
    store.save_reply(message, "original")
    store.save_reply(message, "changed")
    assert Store(path).pending_replies()[0]["text"] == "original"


def test_recovery_requires_confirmation_evidence(tmp_path):
    store = Store(tmp_path / "evidence.db")
    case, evidence = fresh(store)
    p = store.propose(case["id"], evidence["id"], "operator", "space")
    store.approve(p["id"], p["approval_token"], "operator", "space")
    recovery = store.put(
        "recovery_evidence",
        {
            "action_id": p["id"],
            "frame_reference": "net-1.jpg",
            "human_confirmation": "One token in net",
        },
    )
    assert store.outcome(p["id"], True, recovery["id"], "operator")["state"] == "captured"
    assert store.setting("rig_state") == "recovering"
