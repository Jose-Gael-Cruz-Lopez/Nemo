"""Run the store safety contracts on Postgres; test data always rolls back."""

import os
from contextlib import contextmanager

import pytest

from apps.core.reeftrace_core.postgres import Connection, connect
from apps.core.reeftrace_core.store import Store
from tests.unit import test_v3_store as contracts

URL = os.environ.get("REEFTRACE_TEST_DATABASE_URL")


@pytest.fixture
def pg_store(monkeypatch):
    if not URL:
        pytest.skip("Set REEFTRACE_TEST_DATABASE_URL to test Neon/Supabase")
    store = Store(URL)
    with connect(URL) as connection:
        @contextmanager
        def shared_connection(initialize=False):
            yield Connection(connection.db)

        monkeypatch.setattr(store, "connect", shared_connection)
        monkeypatch.setattr(contracts, "Store", lambda path: store)
        try:
            yield store
        finally:
            connection.db.rollback()


@pytest.mark.parametrize("contract", [
    contracts.test_atomic_approval_duplicate_expiry_and_wrong_conversation,
    contracts.test_restart_and_stale_evidence_prevent_action,
    contracts.test_synthetic_cannot_act_and_rig_invalidation_stops_tasks,
    contracts.test_durable_message_dedup_and_immutable_outbox,
    contracts.test_recovery_requires_confirmation_evidence,
])
def test_postgres_safety_contracts(pg_store, tmp_path, contract):
    contract(tmp_path)


@pytest.fixture
def workspace_pg_store(tmp_path, monkeypatch):
    if not URL:
        pytest.skip("Set REEFTRACE_TEST_DATABASE_URL to test Neon/Supabase")
    from apps.api.reeftrace_api.services.store import Store as WorkspaceStore

    store = WorkspaceStore(tmp_path, database_url=URL)
    with connect(URL, schema="reeftrace_workspace") as connection:
        @contextmanager
        def shared_connection(initialize=False):
            # A savepoint preserves the outer rollback after an expected conflict.
            with connection.db.transaction():
                yield Connection(connection.db)

        monkeypatch.setattr(store, "connection", shared_connection)
        from tests.unit import test_store as workspace_contracts

        monkeypatch.setattr(workspace_contracts, "Store", lambda directory: store)
        try:
            yield store
        finally:
            connection.db.rollback()


@pytest.mark.parametrize("contract_name", [
    "test_case_compare_and_swap_cannot_overwrite_concurrent_stop",
    "test_proposal_operator_permission_and_duplicate_pending_guards",
    "test_terminal_outcome_cannot_be_overwritten_or_cancelled",
    "test_case_change_after_approval_invalidates_outcome_and_stop_cancels_task",
    "test_cancel_is_idempotent_and_does_not_cancel_other_cases",
    "test_inbox_and_outbox_crash_recovery_reuse_exact_saved_payload",
    "test_invalid_reply_route_rolls_back_without_completing_inbox",
    "test_immutable_record_duplicate_is_explicit_conflict",
])
def test_workspace_postgres_contracts(workspace_pg_store, contract_name):
    from tests.unit import test_store as workspace_contracts

    getattr(workspace_contracts, contract_name)(workspace_pg_store)
