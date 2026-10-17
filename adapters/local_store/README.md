# Local store

The implemented SQLite WAL store is `apps/api/reeftrace_api/services/store.py`. It stores immutable evidence and frozen profiles, transactionally versioned cases/manual tasks, and a durable Photon inbox/outbox. The API chooses the database directory through REEFTRACE_DATA_DIR; local camera evidence and private settings are ignored by Git.


This branch uses DATABASE_URL for Neon or Supabase Postgres, with SQLite when
empty. The current workspace uses private schema `reeftrace_workspace`; earlier
`/v1` evidence remains in `reeftrace`. Their formats differ and existing records
are preserved separately rather than silently converted.
