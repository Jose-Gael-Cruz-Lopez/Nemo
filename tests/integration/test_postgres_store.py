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
