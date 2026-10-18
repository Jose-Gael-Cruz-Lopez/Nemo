"""Short SQLite transactions; inference evidence is append-only, truth is not ingested."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def uid(prefix: str) -> str:
    return prefix + "-" + uuid.uuid4().hex[:16]


def encode(value: Any) -> str:
    return json.dumps(value, allow_nan=False, separators=(",", ":"))


class Store:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "reeftrace.sqlite3"
        with self.connection() as db:
            db.executescript("""
              PRAGMA journal_mode=WAL;
              CREATE TABLE IF NOT EXISTS records(
                kind TEXT NOT NULL,id TEXT NOT NULL,payload TEXT NOT NULL,
                created REAL NOT NULL,PRIMARY KEY(kind,id));
              CREATE TABLE IF NOT EXISTS cases(
                id TEXT PRIMARY KEY,payload TEXT NOT NULL,revision INTEGER NOT NULL);
              CREATE TABLE IF NOT EXISTS actions(
                id TEXT PRIMARY KEY,payload TEXT NOT NULL,state TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS inbox(
                id TEXT PRIMARY KEY,payload TEXT NOT NULL,state TEXT NOT NULL,
                lease REAL NOT NULL DEFAULT 0,error TEXT);
              CREATE TABLE IF NOT EXISTS outbox(
                id TEXT PRIMARY KEY,payload TEXT NOT NULL,state TEXT NOT NULL,
                lease REAL NOT NULL DEFAULT 0,attempts INTEGER NOT NULL DEFAULT 0,
                retry_at REAL NOT NULL DEFAULT 0,request_id TEXT,error TEXT);
              CREATE TABLE IF NOT EXISTS transport_errors(
                created REAL,kind TEXT,detail TEXT);
            """)
            db.execute(
                "INSERT OR IGNORE INTO settings VALUES('session_start',?)",
                (datetime.now(UTC).isoformat(),),
            )

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def put(self, kind: str, payload: dict, record_id: str | None = None) -> dict:
        record = {**payload, "id": record_id or uid(kind)}
        try:
            with self.connection() as db:
                db.execute(
                    "INSERT INTO records VALUES(?,?,?,?)",
                    (kind, record["id"], encode(record), time.time()),
                )
        except sqlite3.IntegrityError as error:
            raise ValueError("Record ID already exists; immutable records need a new ID") from error
        return record

    def get(self, kind: str, record_id: str) -> dict:
        with self.connection() as db:
            row = db.execute(
                "SELECT payload FROM records WHERE kind=? AND id=?", (kind, record_id)
            ).fetchone()
        if row is None:
            raise KeyError(record_id)
        return json.loads(row[0])

    def put_case_result(
        self, kind: str, payload: dict, case_id: str, expected_revision: int,
        *, changes: dict | None = None,
    ) -> dict:
        """Commit a computed result only while its exact source case is active.

        STOP uses a separate short transaction and never waits for the numerical
        worker. Its revision change prevents an in-flight worker from publishing
        a stale estimate or sensitivity report after the operator stopped it.
        """
        record = {**payload, "id": uid(kind)}
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload,revision FROM cases WHERE id=?", (case_id,)).fetchone()
            if row is None:
                raise KeyError(case_id)
            case = json.loads(row["payload"])
            if (row["revision"] != expected_revision
                    or case["state"] in {"STOPPED", "RECOVERING"}):
                raise ValueError("Case changed or stopped while computing; result was discarded")
            db.execute("INSERT INTO records VALUES(?,?,?,?)",
                       (kind, record["id"], encode(record), time.time()))
            if changes is not None:
                case.update(changes, revision=expected_revision + 1)
                if kind == "estimate":
                    case["evidence_id"] = record["id"]
                db.execute("UPDATE cases SET payload=?,revision=? WHERE id=?",
                           (encode(case), case["revision"], case_id))
        return record

    def reusable_demo_case(self, fixture_key: str) -> dict | None:
        """A repeated load reopens the same immutable fixture, preserving STOP."""
        with self.connection() as db:
            rows = db.execute("SELECT payload FROM cases ORDER BY rowid DESC").fetchall()
        for row in rows:
            case = json.loads(row[0])
            if (case.get("demo_fixture_key") == fixture_key
                    and case["state"] not in {"STOPPED", "RECOVERING"}):
                return case
        return None

    def list(self, kind: str, limit: int = 100) -> list[dict]:
        with self.connection() as db:
            rows = db.execute(
                "SELECT payload FROM records WHERE kind=? ORDER BY created DESC LIMIT ?",
                (kind, limit),
            ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def add_case(self, observation: dict) -> dict:
        case = {
            **observation,
            "id": uid("case"),
            "revision": 1,
            "state": "OBSERVED",
            "created_at": time.time(),
            "evidence_id": None,
        }
        with self.connection() as db:
            db.execute("INSERT INTO cases VALUES(?,?,?)", (case["id"], encode(case), 1))
        return case

    def case(self, case_id: str) -> dict:
        with self.connection() as db:
            row = db.execute("SELECT payload FROM cases WHERE id=?", (case_id,)).fetchone()
        if row is None:
            raise KeyError(case_id)
        return json.loads(row[0])

    def cases(self) -> list[dict]:
        with self.connection() as db:
            rows = db.execute("SELECT payload FROM cases ORDER BY rowid DESC LIMIT 100").fetchall()
        return [json.loads(r[0]) for r in rows]

    def update_case(self, case_id: str, expected_revision: int, changes: dict) -> dict:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload,revision FROM cases WHERE id=?", (case_id,)).fetchone()
            if row is None:
                raise KeyError(case_id)
            if row["revision"] != expected_revision:
                raise ValueError("Case changed; refresh the evidence")
            case = {**json.loads(row["payload"]), **changes, "revision": expected_revision + 1}
            db.execute(
                "UPDATE cases SET payload=?,revision=? WHERE id=?",
                (encode(case), case["revision"], case_id),
            )
        return case

    def propose(self, case_id: str, evidence_id: str, *, allowed: bool) -> dict:
        if not allowed:
            raise ValueError("Only current LIVE cases may create manual recovery tasks")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM cases WHERE id=?", (case_id,)).fetchone()
            if row is None:
                raise KeyError(case_id)
            case = json.loads(row[0])
            if (
                case.get("mode") != "LIVE"
                or not isinstance(evidence_id, str)
                or not evidence_id
                or case["evidence_id"] != evidence_id
                or case["state"] in {"STOPPED", "RECOVERING"}
            ):
                raise ValueError("Proposal does not match current case evidence/state")
            pending = db.execute(
                "SELECT id FROM actions WHERE state IN ('proposed','awaiting_human')"
            ).fetchall()
            for other in pending:
                a = db.execute("SELECT payload FROM actions WHERE id=?", (other[0],)).fetchone()
                if json.loads(a[0])["case_id"] == case_id:
                    raise ValueError("A recovery task already exists for this case")
            action = {
                "id": uid("action"),
                "case_id": case_id,
                "evidence_id": evidence_id,
                "case_revision": case["revision"],
                "kind": "manual_net",
                "state": "proposed",
                "created_at": time.time(),
                "expires_at": time.time() + 60,
            }
            db.execute(
                "INSERT INTO actions VALUES(?,?,?)", (action["id"], encode(action), "proposed")
            )
        return action

    def action(self, action_id: str) -> dict:
        with self.connection() as db:
            r = db.execute("SELECT payload FROM actions WHERE id=?", (action_id,)).fetchone()
        if r is None:
            raise KeyError(action_id)
        return json.loads(r[0])

    def actions_for_case(self, case_id: str) -> list[dict]:
        self.case(case_id)  # Missing case is a 404, not an empty successful list.
        with self.connection() as db:
            rows = db.execute("SELECT payload FROM actions ORDER BY rowid DESC").fetchall()
        return [action for row in rows if (action := json.loads(row[0]))["case_id"] == case_id]

    def transition_action(self, action_id: str, target: str, *, note: dict | None = None) -> dict:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT payload,state FROM actions WHERE id=?", (action_id,)
            ).fetchone()
            if row is None:
                raise KeyError(action_id)
            action = json.loads(row["payload"])
            case_row = db.execute(
                "SELECT payload FROM cases WHERE id=?", (action["case_id"],)
            ).fetchone()
            case = json.loads(case_row[0])
            if target == "awaiting_human":
                if row["state"] != "proposed" or action["expires_at"] < time.time():
                    raise ValueError("Task is expired, consumed or cancelled")
                if case["revision"] != action["case_revision"] or case["state"] == "STOPPED":
                    raise ValueError("Case changed after proposal")
            elif target in {"manual_recovered", "failed", "uncertain"}:
                if row["state"] != "awaiting_human":
                    raise ValueError("Only an approved manual task can receive an outcome")
                if case["revision"] != action["case_revision"] or case["state"] in {
                    "STOPPED",
                    "RECOVERING",
                }:
                    raise ValueError("Case changed after approval; record a new observation")
                case["state"] = "RECOVERING"
                case["revision"] += 1
                db.execute(
                    "UPDATE cases SET payload=?,revision=? WHERE id=?",
                    (encode(case), case["revision"], case["id"]),
                )
            elif target == "cancelled":
                if row["state"] == "cancelled":
                    return action
                if row["state"] not in {"proposed", "awaiting_human"}:
                    raise ValueError("A completed manual outcome cannot be cancelled")
            else:
                raise ValueError("Unsupported manual task transition")
            action.update(state=target, updated_at=time.time())
            if note:
                action["outcome"] = note
            db.execute(
                "UPDATE actions SET state=?,payload=? WHERE id=?",
                (target, encode(action), action_id),
            )
        return action

    def stop_case(self, case_id: str) -> dict:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM cases WHERE id=?", (case_id,)).fetchone()
            if row is None:
                raise KeyError(case_id)
            case = json.loads(row[0])
            case["state"] = "STOPPED"
            case["revision"] += 1
            db.execute(
                "UPDATE cases SET payload=?,revision=? WHERE id=?",
                (encode(case), case["revision"], case_id),
            )
            for row in db.execute(
                "SELECT id,payload FROM actions WHERE state IN ('proposed','awaiting_human')"
            ).fetchall():
                action = json.loads(row["payload"])
                if action["case_id"] == case_id:
                    action["state"] = "cancelled"
                    db.execute(
                        "UPDATE actions SET state='cancelled',payload=? WHERE id=?",
                        (encode(action), row["id"]),
                    )
        return case

    # Photon durable inbox/outbox protocol. Leases recover work after crashes.
    def load_session_start(self) -> str:
        with self.connection() as db:
            return db.execute("SELECT value FROM settings WHERE key='session_start'").fetchone()[0]

    def bind_photon_project(self, project_id: str) -> None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT value FROM settings WHERE key='photon_project'").fetchone()
            if row is not None and row[0] != project_id:
                raise ValueError("Use a separate data directory for a different Photon project")
            db.execute("INSERT OR IGNORE INTO settings VALUES('photon_project',?)", (project_id,))

    def ingest_once(self, item) -> bool:
        from dataclasses import asdict

        with self.connection() as db:
            cur = db.execute(
                "INSERT OR IGNORE INTO inbox(id,payload,state) VALUES(?,?,'pending')",
                (item.id, encode(asdict(item))),
            )
        return cur.rowcount == 1

    def claim_inbound(self):
        return self._claim_inbound(control=False)

    def claim_control_inbound(self):
        return self._claim_inbound(control=True)

    def _claim_inbound(self, *, control):
        from adapters.photon.transport import Inbound

        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT id,payload FROM inbox WHERE state='pending' OR (state='processing' AND lease<?) ORDER BY rowid",
                (time.time(),),
            ).fetchall()
            selected = None
            for row in rows:
                data = json.loads(row["payload"])
                # Candidate routing only. The handler still validates full grammar.
                first = data["text"].split(maxsplit=1)
                is_control = bool(first and first[0] in {"STOP", "CANCEL", "APPROVE"})
                if is_control == control:
                    selected = row, data
                    break
            if selected is None:
                return None
            row, data = selected
            db.execute(
                "UPDATE inbox SET state='processing',lease=? WHERE id=?",
                (time.time() + 120, row["id"]),
            )
        data["allowed_cases"] = tuple(data["allowed_cases"])
        return Inbound(**data)

    def finish_inbound(self, inbound_id: str, outgoing) -> None:
        from dataclasses import asdict

        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            inbound = db.execute(
                "SELECT payload,state FROM inbox WHERE id=?", (inbound_id,)
            ).fetchone()
            if inbound is None:
                raise KeyError(inbound_id)
            original = json.loads(inbound["payload"])
            if (
                outgoing.key != "reeftrace:reply:" + inbound_id
                or outgoing.parent_message_id != inbound_id
                or outgoing.space_id != original["space_id"]
                or outgoing.agent_id != original["agent_id"]
            ):
                raise ValueError("Reply route/key does not match the durable inbound message")
            saved = db.execute("SELECT payload FROM outbox WHERE id=?", (outgoing.key,)).fetchone()
            payload = encode(asdict(outgoing))
            if saved is not None:
                if saved[0] != payload:
                    raise ValueError("A durable reply body cannot change under its idempotency key")
                if inbound["state"] == "done":
                    return
            if inbound["state"] != "processing":
                raise ValueError("Claim the inbound message before completing it")
            db.execute(
                "INSERT OR IGNORE INTO outbox(id,payload,state) VALUES(?,?,'pending')",
                (outgoing.key, payload),
            )
            db.execute("UPDATE inbox SET state='done',lease=0 WHERE id=?", (inbound_id,))

    def fail_inbound(self, inbound_id: str, error: str) -> None:
        with self.connection() as db:
            db.execute(
                "UPDATE inbox SET state='failed',error=? WHERE id=? AND state='processing'",
                (error[:200], inbound_id),
            )

    def completed_inbound(self, inbound_id: str):
        """Read the immutable original for send authorization; never claim/revive it."""
        from adapters.photon.transport import Inbound

        with self.connection() as db:
            row = db.execute(
                "SELECT payload FROM inbox WHERE id=? AND state='done'", (inbound_id,)
            ).fetchone()
        if row is None:
            return None
        data = json.loads(row["payload"])
        fields = set(Inbound.__dataclass_fields__)
        if (not isinstance(data, dict) or set(data) != fields or data.get("id") != inbound_id
                or any(not isinstance(data[key], str) for key in fields - {"allowed_cases"})
                or not isinstance(data["allowed_cases"], list) or not data["allowed_cases"]
                or any(not isinstance(case_id, str) or not case_id for case_id in data["allowed_cases"])):
            raise ValueError("Invalid completed inbound record")
        data["allowed_cases"] = tuple(data["allowed_cases"])
        return Inbound(**data)

    def claim_outgoing(self):
        from adapters.photon.transport import Outgoing

        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT id,payload FROM outbox WHERE (state='pending' AND retry_at<=?) OR (state='sending' AND lease<?) ORDER BY rowid LIMIT 1",
                (time.time(), time.time()),
            ).fetchone()
            if row is None:
                return None
            db.execute(
                "UPDATE outbox SET state='sending',lease=?,attempts=attempts+1 WHERE id=?",
                (time.time() + 60, row["id"]),
            )
        return Outgoing(**json.loads(row["payload"]))

    def update_outgoing(
        self, key: str, status: str, *, request_id=None, error=None, retry_after_s=None
    ) -> None:
        if status not in {"pending", "accepted", "delivered", "failed"}:
            raise ValueError("Unsupported outbox status")
        with self.connection() as db:
            db.execute(
                "UPDATE outbox SET state=?,lease=0,request_id=?,error=?,retry_at=? WHERE id=?",
                (status, request_id, error, time.time() + (retry_after_s or 0), key),
            )

    def log_transport_error(self, kind: str, detail: str) -> None:
        with self.connection() as db:
            db.execute(
                "INSERT INTO transport_errors VALUES(?,?,?)",
                (time.time(), kind[:100], detail[:200]),
            )
