# Local store

SQLite WAL store: apps/core/reeftrace_core/store.py. Default file:
data/runs/reeftrace.sqlite3 (ignored). Stores profiles, immutable cases/estimates,
analyses, agent investigations, manual actions, approvals, messages and replies.
Truth labels and evaluator full-frame archives are excluded from its query contract.
Back up the database and all calibration artifacts before moving the experiment.
