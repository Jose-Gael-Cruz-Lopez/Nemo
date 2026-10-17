"""Durable transactions and manual-task invariants against real SQLite."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from adapters.photon.transport import Inbound, Outgoing
from apps.api.reeftrace_api.services import store as module
from apps.api.reeftrace_api.services.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path)


def prepared_case(store, *, mode="LIVE", evidence_id="evidence-1"):
    case = store.add_case({"mode": mode, "profile_id": "profile-1", "points": []})
    return store.update_case(
        case["id"], case["revision"], {"state": "INVESTIGATE", "evidence_id": evidence_id}
    )


def inbound(text="Why source B?", ident="incoming-1"):
    return Inbound(
        ident,
        "2026-10-16T12:00:00Z",
        "human-1",
        "+15550001111",
        "agent-1",
        "+15550002222",
        "space-1",
        "operator",
        ("case-1",),
        text,
    )


def outgoing(item):
    return Outgoing(
        "reeftrace:reply:" + item.id,
        item.space_id,
        item.agent_id,
        item.id,
        "Conditional source remains unknown.",
    )


def test_case_compare_and_swap_cannot_overwrite_concurrent_stop(store):
    case = prepared_case(store)
    stopped = store.stop_case(case["id"])
    with pytest.raises(ValueError, match="Case changed"):
        store.update_case(case["id"], case["revision"], {"state": "INVESTIGATE"})
    assert store.case(case["id"])["state"] == "STOPPED"
    assert stopped["revision"] > case["revision"]


@pytest.mark.parametrize(
    "mode,evidence_id", [("SYNTHETIC", "evidence-1"), ("REPLAY", "evidence-1"), ("LIVE", None)]
)
def test_proposal_requires_actual_live_mode_and_nonempty_current_evidence(store, mode, evidence_id):
    case = prepared_case(store, mode=mode, evidence_id=evidence_id)
    with pytest.raises(ValueError):
        store.propose(case["id"], evidence_id, allowed=True)


def test_proposal_operator_permission_and_duplicate_pending_guards(store):
    case = prepared_case(store)
    with pytest.raises(ValueError):
        store.propose(case["id"], "evidence-1", allowed=False)
    action = store.propose(case["id"], "evidence-1", allowed=True)
    assert action["kind"] == "manual_net"
    with pytest.raises(ValueError, match="already exists"):
        store.propose(case["id"], "evidence-1", allowed=True)


def test_only_one_concurrent_approval_consumes_proposal(store):
    case = prepared_case(store)
    action = store.propose(case["id"], "evidence-1", allowed=True)

    def approve(_):
        try:
            return store.transition_action(action["id"], "awaiting_human")["state"]
        except ValueError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(approve, range(2)))
    assert sorted(outcomes) == ["awaiting_human", "rejected"]


def test_expired_and_superseded_proposals_cannot_be_approved(store, monkeypatch):
    now = 1000.0
    monkeypatch.setattr(module.time, "time", lambda: now)
    case = prepared_case(store)
    action = store.propose(case["id"], "evidence-1", allowed=True)
    now = 1061.0
    with pytest.raises(ValueError, match="expired"):
        store.transition_action(action["id"], "awaiting_human")
    store.transition_action(action["id"], "cancelled")
    new = store.propose(case["id"], "evidence-1", allowed=True)
    store.update_case(case["id"], case["revision"], {"evidence_id": "new-evidence"})
    with pytest.raises(ValueError, match="Case changed"):
        store.transition_action(new["id"], "awaiting_human")


def test_terminal_outcome_cannot_be_overwritten_or_cancelled(store):
    case = prepared_case(store)
    action = store.propose(case["id"], "evidence-1", allowed=True)
    with pytest.raises(ValueError, match="approved"):
        store.transition_action(action["id"], "manual_recovered")
    store.transition_action(action["id"], "awaiting_human")
    saved = store.transition_action(action["id"], "manual_recovered", note={"recovered_count": 1})
    for target in ("awaiting_human", "failed", "cancelled"):
        with pytest.raises(ValueError):
            store.transition_action(action["id"], target)
    assert store.action(action["id"]) == saved
    assert store.case(case["id"])["state"] == "RECOVERING"


def test_case_change_after_approval_invalidates_outcome_and_stop_cancels_task(store):
    case = prepared_case(store)
    action = store.propose(case["id"], "evidence-1", allowed=True)
    store.transition_action(action["id"], "awaiting_human")
    store.update_case(case["id"], case["revision"], {"evidence_id": "new-evidence"})
    with pytest.raises(ValueError, match="Case changed"):
        store.transition_action(action["id"], "uncertain")
    store.stop_case(case["id"])
    assert store.action(action["id"])["state"] == "cancelled"
    with pytest.raises(ValueError):
        store.transition_action(action["id"], "manual_recovered")


def test_cancel_is_idempotent_and_does_not_cancel_other_cases(store):
    first, second = prepared_case(store), prepared_case(store)
    a = store.propose(first["id"], "evidence-1", allowed=True)
    b = store.propose(second["id"], "evidence-1", allowed=True)
    cancelled = store.transition_action(a["id"], "cancelled")
    assert store.transition_action(a["id"], "cancelled") == cancelled
    store.stop_case(first["id"])
    assert store.action(b["id"])["state"] == "proposed"


@pytest.mark.parametrize(
    "text",
    ["STOP", "CANCEL", "APPROVE", "STOP case-1", "STOP\tcase-1", "APPROVE a extra", "  CANCEL a  "],
)
def test_control_candidates_use_disjoint_fast_lane(store, text):
    item = inbound(text)
    store.ingest_once(item)
    assert store.claim_inbound() is None
    assert store.claim_control_inbound() == item
    assert store.claim_control_inbound() is None


def test_inbox_and_outbox_crash_recovery_reuse_exact_saved_payload(store):
    item = inbound()
    assert store.ingest_once(item)
    assert store.claim_inbound() == item
    reopened = Store(store.directory)
    assert not reopened.ingest_once(item)
    assert reopened.claim_inbound() is None  # active lease
    with reopened.connection() as db:
        db.execute("UPDATE inbox SET lease=0 WHERE id=?", (item.id,))
    assert reopened.claim_inbound() == item
    reply = outgoing(item)
    reopened.finish_inbound(item.id, reply)
    reopened.finish_inbound(item.id, reply)  # replay after commit is harmless
    reopened.fail_inbound(item.id, "late duplicate processor")
    assert reopened.claim_inbound() is None
    first = reopened.claim_outgoing()
    assert first == reply
    assert Store(store.directory).claim_outgoing() is None
    with reopened.connection() as db:
        db.execute("UPDATE outbox SET lease=0 WHERE id=?", (reply.key,))
    assert Store(store.directory).claim_outgoing() == first
    with pytest.raises(ValueError, match="cannot change"):
        reopened.finish_inbound(item.id, replace(reply, text="A changed regenerated answer"))


def test_invalid_reply_route_rolls_back_without_completing_inbox(store):
    item = inbound()
    store.ingest_once(item)
    store.claim_inbound()
    with pytest.raises(ValueError, match="route/key"):
        store.finish_inbound(item.id, replace(outgoing(item), agent_id="human-1"))
    assert store.claim_outgoing() is None
    with store.connection() as db:
        assert (
            db.execute("SELECT state FROM inbox WHERE id=?", (item.id,)).fetchone()[0]
            == "processing"
        )


def test_outbox_retry_deadline_and_terminal_acceptance(store, monkeypatch):
    now = 1000.0
    monkeypatch.setattr(module.time, "time", lambda: now)
    item = inbound()
    store.ingest_once(item)
    store.claim_inbound()
    row = outgoing(item)
    store.finish_inbound(item.id, row)
    assert store.claim_outgoing() == row
    store.update_outgoing(row.key, "pending", retry_after_s=120)
    now = 1119.0
    assert store.claim_outgoing() is None
    now = 1120.0
    assert store.claim_outgoing() == row
    store.update_outgoing(row.key, "accepted", request_id="request-1")
    now = 9999.0
    assert Store(store.directory).claim_outgoing() is None
    with pytest.raises(ValueError, match="outbox status"):
        store.update_outgoing(row.key, "typo-status")


def test_immutable_record_duplicate_is_explicit_conflict(store):
    store.put("profile", {"value": 1}, "same")
    with pytest.raises(ValueError, match="immutable"):
        store.put("profile", {"value": 2}, "same")
    assert store.get("profile", "same")["value"] == 1
