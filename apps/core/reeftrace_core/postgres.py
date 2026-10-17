"""Postgres connection adapter for Neon and Supabase, isolated in reeftrace schema."""

import re
from contextlib import contextmanager

import psycopg


class Row(dict):
    def __getitem__(self, key):
        return tuple(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


def row_factory(cursor):
    names = [column.name for column in cursor.description] if cursor.description else []
    return lambda values: Row(zip(names, values, strict=True))


class Connection:
    def __init__(self, db):
        self.db = db

    def execute(self, sql, parameters=()):
        # Store SQL is static: placeholders never occur inside string literals.
        sql = sql.replace("?", "%s")
        if sql == "BEGIN IMMEDIATE":
            # The transaction-wide lock is already held by connect().
            return self.db.execute("SELECT 1")
        if sql.startswith("INSERT OR IGNORE INTO"):
            sql = sql.replace("INSERT OR IGNORE INTO", "INSERT INTO", 1)
            sql += " ON CONFLICT DO NOTHING"
        return self.db.execute(sql, parameters)

    def executescript(self, script):
        for sql in script.split(";"):
            sql = sql.strip()
            if not sql or sql.startswith("PRAGMA"):
                continue
            self.execute(re.sub(r"\bREAL\b", "DOUBLE PRECISION", sql))


@contextmanager
def connect(url, initialize=False):
    with psycopg.connect(url, connect_timeout=15, sslmode="require", row_factory=row_factory) as db:
        # Preserve SQLite's serialized approval/queue transitions across workers.
        db.execute("SET LOCAL lock_timeout = '15s'")
        db.execute("SET LOCAL statement_timeout = '30s'")
        db.execute("SELECT pg_advisory_xact_lock(7265667472616365)")
        if initialize:
            db.execute("CREATE SCHEMA IF NOT EXISTS reeftrace")
        db.execute("SET LOCAL search_path TO reeftrace")
        yield Connection(db)
