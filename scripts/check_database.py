"""Initialize the private database schema and verify connectivity without printing secrets."""

import sqlite3

import psycopg
from dotenv import load_dotenv

from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.services.store import Store


def main():
    load_dotenv()
    try:
        settings = Settings()
        store = Store(settings.data_dir, database_url=settings.database_url)
        with store.connection() as db:
            count = db.execute("SELECT count(*) FROM records").fetchone()[0]
        print(f"Database connected: {'Postgres' if store.is_postgres else 'SQLite'}; {count} records")
    except (psycopg.Error, sqlite3.Error, OSError, ValueError) as error:
        raise SystemExit("Database connection failed: " + type(error).__name__) from None


if __name__ == "__main__":
    main()
