# Developing Nemo locally

These are the local installation and startup instructions. The repository README presents the project story, science and screenshots.

## Start locally

Use **Python 3.12** and **Node.js 24** to match CI. Package metadata permits Python ≥3.11; Next.js requires Node ≥20.9. From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,sponsors,ocean]'
cd dashboard
npm ci
cd ..
.venv/bin/python scripts/dev.py
```

- Dashboard: **http://127.0.0.1:3000**. API: **http://127.0.0.1:8000**. Interactive request schemas: **http://127.0.0.1:8000/docs**.
- After the first bootstrap, `.venv/bin/python scripts/dev.py --check` is an optional read-only preflight. On a fresh checkout with no token, run the normal launcher first.
- The launcher checks dependencies/ports, creates a private `.env` and a missing/blank `REEFTRACE_LOCAL_TOKEN`, and preserves existing nonblank settings. The token is shared operator access, not an individual email account.
- Enter the token privately through `/login` or **Operator access**. It remains only in that browser tab's memory and clears on reload. The hosted service has its own separate token; a local token does not authenticate to Render.
- The launcher reuses verified running services, reports unrelated listeners and stops only services it started. It never silently changes sponsor enable flags.
- Starting a **new** messaging-enabled API requires explicit `--allow-photon`. An already running authorized worker is left untouched. The software demo requires neither Photon nor the camera.
- Base scientific/API dependencies are in `pyproject.toml`. `.[sponsors]` installs the Photon SDK; `.[ocean]` installs xarray/NetCDF/Copernicus readers; `.[evaluations]` adds explicit Chalk remote-evaluation tooling. Installing readers or SDKs does not acquire data or invoke a provider.


For isolated verification and deployment details, see [CI](ci.md), [the verification runbook](verification.md) and [the deployment package](../deploy/README.md).
