"""Local SQLite evidence, atomic manual approvals and durable messaging queues."""

import hashlib
import json
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import UTC
from pathlib import Path


def identifier(prefix):
    return prefix + "-" + str(uuid.uuid4())


def encode(value):
    return json.dumps(value, sort_keys=True, allow_nan=False)


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS records (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, parent TEXT,
                created REAL NOT NULL, payload TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS record_kind ON records(kind,created);
            CREATE TABLE IF NOT EXISTS actions (
                id TEXT PRIMARY KEY, case_id TEXT NOT NULL, evidence_id TEXT NOT NULL,
                operator TEXT NOT NULL, conversation TEXT NOT NULL, token_hash TEXT NOT NULL,
                body TEXT NOT NULL, body_hash TEXT NOT NULL, expires REAL NOT NULL,
                state TEXT NOT NULL, outcome TEXT);
            CREATE TABLE IF NOT EXISTS jobs (
                proposal_id TEXT PRIMARY KEY, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS inbox (
                id TEXT PRIMARY KEY, payload TEXT NOT NULL, state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS outbox (
                id TEXT PRIMARY KEY, parent_id TEXT UNIQUE NOT NULL,
                payload TEXT NOT NULL, state TEXT NOT NULL, request_id TEXT);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def setting(self, key, default=None):
        with self.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        with self.connect() as db:
            db.execute(
                "INSERT INTO settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def check_rig(self, calibration_id):
        self.set_setting("active_calibration", calibration_id)
        self.set_setting("rig_state", "ready")
        return {"calibration_id": calibration_id, "state": "ready", "operator_checked": True}

    def invalidate_rig(self):
        self.set_setting("rig_state", "invalid")
        self.stop()
        return {"state": "invalid", "new_attribution_enabled": False}

    def put(self, kind, payload, parent=None):
        record_id = identifier(kind)
        with self.connect() as db:
            db.execute(
                "INSERT INTO records VALUES (?,?,?,?,?)",
                (record_id, kind, parent, time.time(), encode(payload)),
            )
            if kind == "case" and payload.get("mode") == "live":
                db.execute(
                    "INSERT INTO settings VALUES ('active_case',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (record_id,),
                )
        return {"id": record_id, **payload}

    def get(self, record_id, kind=None):
        with self.connect() as db:
            row = db.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone()
        if row is None or (kind is not None and row["kind"] != kind):
            raise KeyError(record_id)
        return {"id": row["id"], "created_at": row["created"], **json.loads(row["payload"])}

    def list(self, kind, parent=None):
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM records WHERE kind=? AND (? IS NULL OR parent=?) ORDER BY created DESC LIMIT 100",
                (kind, parent, parent),
            ).fetchall()
        return [
            {"id": r["id"], "created_at": r["created"], **json.loads(r["payload"])} for r in rows
        ]

    def latest_evidence(self, case_id):
        rows = self.list("estimate", case_id)
        if not rows:
            raise KeyError("No estimate")
        return rows[0]

    def startup_reset(self):
        self.set_setting("rig_state", "startup_check_required")
        # A restarted process cannot replay pre-restart authorizations.
        with self.connect() as db:
            db.execute("UPDATE actions SET state='expired' WHERE state IN ('pending','approved')")
            db.execute("UPDATE actions SET state='uncertain' WHERE state='acting'")
            db.execute("UPDATE inbox SET state='pending' WHERE state='processing'")

    def propose(self, case_id, evidence_id, operator, conversation):
        case = self.get(case_id, "case")
        if self.latest_evidence(case_id)["id"] != evidence_id:
            raise ValueError("Stale evidence")
        proposal_id, token = identifier("action"), secrets.token_urlsafe(24)
        body = {
            "id": proposal_id,
            "case_id": case_id,
            "evidence_id": evidence_id,
            "calibration_id": case["calibration_id"],
            "mode": "manual_net",
            "operator": operator,
            "conversation": conversation,
            "expires_at": time.time() + 60,
        }
        body_text = encode(body)
        with self.connect() as db:
            db.execute(
                "INSERT INTO actions VALUES (?,?,?,?,?,?,?,?,?,?,NULL)",
                (
                    proposal_id,
                    case_id,
                    evidence_id,
                    operator,
                    conversation,
                    hashlib.sha256(token.encode()).hexdigest(),
                    body_text,
                    hashlib.sha256(body_text.encode()).hexdigest(),
                    body["expires_at"],
                    "pending",
                ),
            )
        return {**body, "state": "pending", "approval_token": token}

    def action(self, action_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
        if row is None:
            raise KeyError(action_id)
        return {
            **json.loads(row["body"]),
            "state": row["state"],
            "outcome": json.loads(row["outcome"]) if row["outcome"] else None,
        }

    def approve(self, action_id, token, operator, conversation):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
            if row is None:
                raise KeyError(action_id)
            case = db.execute("SELECT * FROM records WHERE id=?", (row["case_id"],)).fetchone()
            latest = db.execute(
                "SELECT id FROM records WHERE kind='estimate' AND parent=? ORDER BY created DESC LIMIT 1",
                (row["case_id"],),
            ).fetchone()
            profile = json.loads(case["payload"])
            rig = {
                r["key"]: r["value"]
                for r in db.execute(
                    "SELECT key,value FROM settings WHERE key IN ('active_calibration','rig_state','active_case')"
                )
            }
            valid = (
                rig.get("active_case") == row["case_id"]
                and rig.get("rig_state") == "ready"
                and rig.get("active_calibration") == profile["calibration_id"]
                and row["state"] == "pending"
                and row["expires"] > time.time()
                and row["operator"] == operator
                and row["conversation"] == conversation
                and secrets.compare_digest(
                    row["token_hash"], hashlib.sha256(token.encode()).hexdigest()
                )
                and hashlib.sha256(row["body"].encode()).hexdigest() == row["body_hash"]
                and latest
                and latest["id"] == row["evidence_id"]
                and profile["mode"] == "live"
                and profile.get("last_observed_at") is not None
                and 0 <= time.time() - profile["last_observed_at"] < 15
            )
            if not valid:
                raise ValueError("Approval expired, unauthorized, stale or not a fresh live scene")
            db.execute("INSERT INTO jobs VALUES (?,?)", (action_id, time.time()))
            db.execute("UPDATE actions SET state='acting' WHERE id=?", (action_id,))
        return self.action(action_id)

    def stop(self, action_id=None):
        with self.connect() as db:
            if action_id:
                db.execute(
                    "UPDATE actions SET state='stopped' WHERE id=? AND state IN ('pending','approved','acting')",
                    (action_id,),
                )
            else:
                db.execute(
                    "UPDATE actions SET state='stopped' WHERE state IN ('pending','approved','acting')"
                )
        return {"state": "stopped", "physical_power_cut": False}

    def outcome(self, action_id, recovered, evidence_id, operator):
        evidence = self.get(evidence_id, "recovery_evidence")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
            if (
                not row
                or row["state"] != "acting"
                or row["operator"] != operator
                or evidence["action_id"] != action_id
            ):
                raise ValueError("Invalid recovery confirmation")
            result = {
                "manual": True,
                "recovered": recovered,
                "evidence_id": evidence_id,
                "operator": operator,
                "recovering": True,
            }
            state = "captured" if recovered else "failed"
            db.execute(
                "UPDATE actions SET state=?,outcome=? WHERE id=?",
                (state, encode(result), action_id),
            )
        self.set_setting("rig_state", "recovering")
        return self.action(action_id)

    def ingest_once(self, message):
        with self.connect() as db:
            return (
                db.execute(
                    "INSERT OR IGNORE INTO inbox VALUES (?,?,'pending')",
                    (message["id"], encode(message)),
                ).rowcount
                == 1
            )

    def claim_message(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM inbox WHERE state='pending' LIMIT 1").fetchone()
            if not row:
                return None
            db.execute("UPDATE inbox SET state='processing' WHERE id=?", (row["id"],))
            return json.loads(row["payload"])

    def save_reply(self, message, text):
        payload = {
            "key": identifier("reply"),
            "space_id": message["space_id"],
            "agent_id": message["agent_id"],
            "parent_message_id": message["id"],
            "text": text,
        }
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO outbox VALUES (?,?,?,'pending',NULL)",
                (payload["key"], message["id"], encode(payload)),
            )
            db.execute("UPDATE inbox SET state='done' WHERE id=?", (message["id"],))

    def pending_replies(self):
        with self.connect() as db:
            return [
                json.loads(r[0])
                for r in db.execute("SELECT payload FROM outbox WHERE state='pending'").fetchall()
            ]

    def reply_accepted(self, key, request_id):
        with self.connect() as db:
            db.execute(
                "UPDATE outbox SET state='accepted',request_id=? WHERE id=?", (request_id, key)
            )

    def session_start(self):
        with self.connect() as db:
            value = db.execute(
                "SELECT value FROM settings WHERE key='photon_session_start'"
            ).fetchone()
            if value:
                return value[0]
            from datetime import datetime

            start = datetime.now(UTC).isoformat()
            db.execute("INSERT INTO settings VALUES ('photon_session_start',?)", (start,))
            return start
