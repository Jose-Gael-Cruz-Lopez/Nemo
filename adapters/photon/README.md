# Photon 2.0

Install `pip install -e '.[photon]'` (photonhq-api==0.5.0). Worker:
`python -m apps.core.reeftrace_core.photon`. This explicitly starts polling and
sending replies; it does not start with FastAPI. Configure the exact project key,
assigned human/agent handles, role, active case and allowed case IDs in .env.

SDK request schemas were checked locally; account/device round-trip is unverified.
Persistent inbox/outbox, full bounded-session rescan, paging and idempotency prevent
logical duplicate work. STOP/CANCEL/APPROVE bypass ordinary agent turns. No physical
pump/servo dispatch exists. See docs/GETTING_STARTED.md before starting the worker.
