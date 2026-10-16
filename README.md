# Reeftrace

Reeftrace is a controlled source-intelligence proof of concept. It uses camera
observations and a measured tank transport model to compare candidate debris
sources. Its core value is the moving-trajectory and stationary-deposition
inference; physical collection is an optional, human-approved response layer.

This repository follows the project plan's Python, FastAPI, Next.js/TypeScript,
and Arduino stack. The generated dashboard and API are starter scaffolds; the
vision, transport, estimation, persistence, and hardware modules still need to
be implemented and validated against the plan.

## Repository layout

```text
apps/
  api/reeftrace_api/        FastAPI routes, schemas, services, and orchestration
  vision/reeftrace_vision/  Camera calibration, detection, and tracking
  transport/                Flow fields and particle transport simulation
  estimation/               Moving/stationary source inference
  hardware/                 Serial client and coordinate transforms
adapters/                   Local storage plus optional Butterbase, Chalk, Photon
config/                     Tank geometry and calibration templates
dashboard/                  Next.js + TypeScript operator dashboard
data/sample_runs/           Sanitized replay fixtures; no private or secret data
docs/                       Architecture and operating documentation
firmware/reeftrace_arduino/ Arduino device-side safety firmware
scripts/                    Developer and data preparation scripts
tests/                      Unit, integration, and replay tests
```

## Local development

Requires Python 3.11+ and Node.js 20+.

1. Create and activate a virtual environment, then install the Python project:

	```sh
	python -m venv .venv
	source .venv/bin/activate
	pip install -e '.[dev]'
	```

2. Copy `.env.example` to `.env` and keep credentials out of source control.
3. Start the API from the repository root:

	```sh
	uvicorn apps.api.reeftrace_api.main:app --reload
	```

	API docs are available at `http://127.0.0.1:8000/docs` and health at
	`http://127.0.0.1:8000/api/v1/health`.
4. In another terminal, start the dashboard:

	```sh
	cd dashboard
	npm install
	npm run dev
	```

5. Run the Python checks with `pytest` from the repository root.

## Safety and evidence

Hardware is disabled by default in `config/tank.yaml`. Fill in measured
geometry and calibration, verify the safe polygon and emergency-stop behavior,
and complete the hardware checks in the project plan before enabling movement
or suction. The source estimator must return `Unknown` when the evidence is
insufficient; unvalidated match scores must not be presented as probabilities
or geographic attribution.

Secrets belong in server-side environment variables only. Do not commit `.env`
files, credentials, private run footage, or raw test data containing sensitive
information.