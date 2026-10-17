# ReefTrace

A local USB-camera experiment for comparing candidate floating-debris entry points. OpenCV observes a standardized token; a measured drift field drives a forward particle model; the estimator saves conditional source evidence or **Unknown**. A bounded Gemini-backed investigator uses those saved reports in the dashboard and a Photon direct conversation. Recovery is manual.

This repository now implements the computational and application paths, rather than only starter directories. It follows **ReefTrace_Final_Plan.pdf, USB Webcam Edition 5.0**. Real tank calibration and held-out trials are still required; synthetic fixtures and passing tests are software evidence, not reef or tank accuracy claims.

## Start locally

Python 3.12 and Node 20.9+ are supported starting points; the verified environment uses Python 3.12 and Node 24. Run this installation once from the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,sponsors]'
cd dashboard
npm ci
cd ..
```

Start both services in one terminal:

```sh
python scripts/dev.py
```

The launcher checks the repository environment, dependencies, configuration and fixed local ports, then starts the single-worker API on http://127.0.0.1:8000 and the dashboard on http://127.0.0.1:3000. Existing verified ReefTrace services are reused; an unrelated port listener is reported as a conflict. Ctrl+C stops only services started by this invocation. `python scripts/dev.py --check` performs a read-only preflight. It does not install packages or start a camera.

Local bootstrap creates a private `.env`, or repairs a missing/blank operator token while preserving other settings. Existing nonblank tokens are kept. Open the root `.env` locally. Click **Load demo** in the dashboard, then enter `REEFTRACE_LOCAL_TOKEN` in **Connect operator** when prompted; vendor keys never go into the browser. After connecting, click **Load demo** to open the cases in **Investigations**. The workspace includes **Overview**, **Investigations**, **Camera**, **Data lab**, and **Settings**. The committed three cases demonstrate a ranked path, ambiguous retained endpoint, and invalid calibration. Gemini/Photon configuration is separate from a verified live response. Camera access starts only when explicitly selected by the operator.

If you explicitly enable the prepared Photon worker in `.env`, use `python scripts/dev.py --allow-photon` to start that messaging-enabled API. The default startup does not enable sponsor services.

## Run the complete demo

1. Connect operator access, then **Load demo**. Repeated loads reopen the same active observations. Loading after STOP makes a replacement while preserving the stopped case and its evidence.
2. Select **Observed trajectory**, run **Compute source support**, then **Test sensitivity**. This explicitly synthetic development path should rank candidate **C**.
3. Ask Gemini which candidate fits and what remains uncertain. A configured, successful model response includes the saved evidence ID and tool trace. If the gateway is unavailable, the app keeps the deterministic report and clearly says no live model response occurred.
4. Select **Retained endpoint** to see **Unknown**: the shared pocket has erased the distinguishing history. Select the invalid-mapping example to see **Invalid**. These are intended scientific outcomes.
5. Open **Data lab** (or **Explore real data** from Overview), then click **Run real-data replay**. It fits three motion models on the first 18 historical hourly positions and forecasts the final six without reading their positions during fitting. This separate experiment cannot identify a plastic release source.

Run the same backend story over HTTP while the local services are running:

```sh
python scripts/e2e_demo.py --output work/e2e-demo.json
```

The audit reads the private local operator token itself. It does not open a webcam, operate the pump, or send Photon messages. A configured Gemini API may make a real, metered request. Its JSON separates **PASS**, **FAIL**, and **BLOCKED**. Missing live credentials and physical trials remain blockers even when every local software assertion passes. See [the reproducible verification guide](docs/verification.md) for the exact checks and sponsor commissioning steps.

## What to build/measure next

See [docs/execution-plan.md](docs/execution-plan.md) for exact four-person execution, software responsibilities, first physical dataset, measurement gates, setup payloads and judging. [docs/physics.md](docs/physics.md) derives the implemented mathematics. [docs/datasets.md](docs/datasets.md) researches Copernicus, NOAA, TrashCan and MARIDA, with access/licensing/domain limits and the verified public data fixture. [docs/integrations.md](docs/integrations.md) documents exact Gemini/Photon contracts. [docs/architecture.md](docs/architecture.md) maps running modules and state ownership.

No neural network is needed for the controlled red-token MVP. The fitted drift field is the local learned model; source inference is a physics-based inverse comparison. The Data lab adds a training-only ridge velocity autoregression and two baselines on the pinned real NOAA sample. The learned model improves average error on this selected day but has worse final-position error than stationary persistence; all results stay visible. [The research note](docs/research-real-data.md) documents the data, mathematics and limits. Ocean currents or underwater trash photographs cannot supply this tank's flow or hidden release labels.

## Verification

```sh
python -m pytest -q
python -m ruff check apps adapters scripts tests
cd dashboard
npm run lint
npm run build
```

`python scripts/evaluate.py` generates a separate reproducible scientific software report on the synthetic cases. Public NOAA ingestion: `python scripts/fetch_public_sample.py --output-dir work/noaa-smoke`. Copernicus NetCDF support requires `pip install -e '.[ocean]'`; authenticated downloads are explicit and bounded, not run automatically.

Reproduce the real-data benchmark without accounts or network access:

```sh
python scripts/evaluate_real_data.py --output work/real-data-example.json
```

The implementation has no pump/robot actuation. Do not enable a serial/gantry feature from an older plan. Camera frames and private settings belong in ignored `data/local/` and `.env`; the committed small replay is explicitly synthetic. Reproducing a live sponsor call or physical source trial requires real credentials/hardware and a separate recorded result.
## Grok, satellite context and the SpaceXAI build

The investigation workspace includes a pinned NOAA Coral Reef Watch satellite-derived
heat-stress sample and a deterministic spoken-briefing script. Historical ecological
context is displayed separately and **never changes the tank source ranking**.
Use **Load satellite context**, then **Read briefing text** on a saved case.
The chart covers one Florida Keys-area grid cell on 1–7 July 2023, not present tank
conditions or confirmed bleaching.

**Generate Grok narration** is an explicit, operator-authenticated server request to
the xAI text-to-speech API. `GROK_VOICE_ENABLED=false` and no `XAI_API_KEY` keeps it
offline; the user selected completing the integration without a live key. No live
speech result or completed Voice API eligibility is claimed. Permanent keys must
never enter frontend environment variables. See [the data and API contract](docs/grok-space-context.md).

This branch uses direct Gemini inference and Neon Postgres. Photon replies
remain disabled until explicitly configured. GitHub checks run on every push and pull request without sponsor
credentials or hardware access. See [integration verification](docs/integrations.md)
and [CI](docs/ci.md). Cursor's Grok implementation and the reviewed ML diagnostic are
recorded separately from proof of any live Grok Voice request.

## Branch backend setup

The workspace calls Gemini directly with `GEMINI_API_KEY` and `GEMINI_MODEL`
(default local selection: `gemini-3.1-flash-lite`). Set `GEMINI_ENABLED=false`
to disable model calls. `REEFTRACE_AI_PROVIDER=gemini` selects this setup.
There is no Chalk gateway, environment ID, or hosted evaluation dependency.
Run `python -m scripts.check_gemini --test` for an explicit small model request.

Set the server-only `DATABASE_URL` to a Neon pooled Postgres URI or a Supabase
session-pooler URI. Connections require TLS. Supabase is an alternative primary
database; `SUPABASE_DATABASE_URL` does not automatically replicate records.
Leave `DATABASE_URL` empty for local SQLite. Credentials belong only in ignored
`.env`, never in frontend environment variables.

The main-branch workspace has a newer record format, so its tables use the
private `reeftrace_workspace` schema. Earlier branch records are preserved in
`reeftrace` and remain accessible through the legacy `/v1` endpoints. SQLite
records are not uploaded automatically. Load the committed synthetic demos in
the new dashboard to populate its workspace. `python -m scripts.check_database`
verifies the active workspace database. Camera files remain on the local computer.
