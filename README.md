# ReefTrace v3

ReefTrace is a controlled tank source-investigation prototype. A fixed USB camera
observes standardized floating tokens; a measured surface-drift model compares
forward source ensembles to permitted trajectories or verified retained endpoints.
Results rank A/B/C or return Unknown with evidence and limitations. A bounded
Gemini-backed investigator explains stored evidence; optional Photon 2.0 messaging
uses the same tool loop. Manual net recovery is the response baseline.

**Start with [the v3 setup guide](docs/GETTING_STARTED.md).**
The updated 66-page
manual is [ReefTrace_Final_Plan.pdf](ReefTrace_Final_Plan.pdf). Existing Uno dry-bench
instructions are retained in [LEGACY_BENCH.md](docs/LEGACY_BENCH.md).

## Implemented

- Seeded forward simulator, source priors, trajectory and retained-endpoint
  likelihoods, coverage/fit/margin/age-sensitivity gates and explicit Unknown.
- Water-plane homography/check-point report, masked single-token recording with
  actual timestamps and gaps, coarse-cell measured flow builder.
- SQLite immutable evidence, authenticated local API, bounded investigator,
  sensitivity tools, manual task approvals and human recovery confirmation.
- Next.js evidence/investigation console plus separate Uno bench telemetry panel.
- Optional Photon polling/route checks, persistent inbox/outbox and stable reply
  idempotency. Not started automatically by the API.
- Hardware-isolated replay backend, synthetic agent fixtures, local evaluation
  runner, scientific metrics with accuracy and coverage reported separately.
- Separate default-off water-sampler sketch and explicit local test client;
  existing two-servo bench sketch remains available.
- Windows/ASUS setup placeholders; no GPU required.

## Run locally

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,photon]'
cp .env.example .env
# Set a random REEFTRACE_LOCAL_TOKEN in .env before using protected routes.
python scripts/seed_demo.py --scenario moving
uvicorn apps.api.reeftrace_api.main:app --host 127.0.0.1 --workers 1
```

Then `cd dashboard`, `npm ci`, `npm run dev`. Open http://localhost:3000 and enter
the local token in the investigation console. Seeded cases are explicitly synthetic.
API contracts are at http://127.0.0.1:8000/docs; case routes use `/v1`.

## Verification and limits

Run `pytest -q`, `ruff check apps scripts tests eval`, then dashboard `npm run lint`
and `npm run build`. The software is tested locally, not validated against a real
tank. Calibration, trap retention, source identifiability, token behavior and frozen
physical trials must be measured. No source accuracy or environmental impact is
claimed. Continuous camera streaming/automatic observation fulfilment, physical sampling integration, and ASUS hardware verification
remain pending. Sponsor account calls and hardware actuation were not performed.

Scores are conditional relative support, not geographic probabilities. Manual
recovery is distinct from water sampling. Acknowledgements do not prove volume or
capture. See the setup guide for dependency advisories and restart/rig checks.

## AI provider setup

SQLite already stores local evidence; no database service is required. Set
`GEMINI_API_KEY` in your private `.env`, keep `REEFTRACE_AI_PROVIDER=gemini`,
and choose a model available on your account using `GEMINI_MODEL`
(default setup: `gemini-3.1-flash-lite`). Get a key at
https://aistudio.google.com/api-keys using an account with AI Studio access.
Free-tier availability and quotas depend on the model and account.
Run `.venv/bin/python -m scripts.check_gemini` to check configuration, then
add `--test` to send one synthetic JSON request. Restart the API and Photon
worker after changing `.env`. To use the existing adapter again, set
`REEFTRACE_AI_PROVIDER=butterbase`.

## Hosted database (Neon or Supabase)

Set the server-only `DATABASE_URL` in `.env` to a Postgres connection URI.
Neon: use the pooled connection from the Connect dialog, with `sslmode=require`.
Supabase: use the session pooler on IPv4 networks, percent-encode your database
password, and add `sslmode=require`. Both use the same Python Postgres adapter.
The app creates its tables in the private `reeftrace` schema; no browser database
keys or public Data API exposure are required. Choose one primary database.
`SUPABASE_DATABASE_URL` can hold an alternative URI but is not automatically used.
Leave `DATABASE_URL` empty to return to the existing local SQLite store.

Run `.venv/bin/python -m scripts.check_database` to initialize and verify the
connection, then restart the API and Photon worker. Existing SQLite records are
not automatically uploaded. To create a fresh synthetic demonstration in the
selected database, run `.venv/bin/python -m scripts.seed_demo --scenario moving`.
Do not run multiple API lifespans against the same live rig: startup invalidates
pending approvals. Postgres transactions serialize the small prototype's store
operations to preserve atomic approvals and durable queue claims.

For opt-in Postgres safety tests, set `REEFTRACE_TEST_DATABASE_URL` and run
`pytest tests/integration/test_postgres_store.py`; test records roll back.
