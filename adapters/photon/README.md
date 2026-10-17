# Photon direct conversation adapter

Implemented `transport.py` and `worker.py` use the pinned official Photon Python0.5.0 SDK. Direct messages must match configured human/agent handles, role, project and exact allowed cases. Persistent SQLite inbox/outbox, stable reply keys, leases, and a dedicated STOP/CANCEL/APPROVE lane surround the same Gemini investigator used by the UI. Approval creates a human manual-net task and never controls hardware. SDK contract tests use HTTP mocks; real account sends were not executed. See `docs/integrations.md`.
