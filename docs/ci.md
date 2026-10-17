# GitHub checks

The workflow at [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on every `push` and `pull_request`. It has two independent jobs on GitHub-hosted Ubuntu: **Python tests and scientific replay**, and **Dashboard tests, lint, types and production build**. A newer run cancels an older run for the same workflow/event/ref. There is no deployment, message sending, hardware access or live provider evaluation.

The workflow needs only GitHub's built-in `contents: read` permission. Checkout does not retain Git credentials, and no repository/account secrets are referenced. Official checkout/setup actions are pinned to inspected immutable commit SHAs, with their release versions in comments. Update a pin only after checking its official release and commit. [GitHub's concurrency documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency) describes the cancellation rule; [setup-node](https://github.com/actions/setup-node) and [setup-python](https://github.com/actions/setup-python) document dependency caching.

## Python job

Python 3.12 installs `.[dev,photon,ocean]` from `pyproject.toml`, checks dependency consistency, verifies optional SDK imports, runs Ruff, and runs the full pytest suite. Sponsor SDKs and xarray/NetCDF are installed so their contract/reader tests do not silently skip because a package is absent. The macOS requirements snapshot is not used as a Linux lockfile.

Gemini and Photon are explicitly disabled and their credentials/models/routes are empty. Runtime test data goes to the runner's temporary directory; its local operator token is a public, test-only string. Tests use explicit mocked HTTP transports for SDK contracts. The Gemini policy tests use mocked HTTP; hosted task deployment is not supported. This job never runs a live sponsor evaluation or camera capture.

The scientific replay executes `scripts/evaluate_real_data.py` against the committed, hash-verified NOAA CSV and provenance. Its JSON goes to the runner's temporary directory, preserving the input files. Existing tests verify the chronological 18-training/6-heldout split, frozen model results, absence of heldout/velocity leakage, and the fact that the learned model does not win every metric. An additional Git diff check rejects any rewrite of public or synthetic fixtures. Passing this check establishes reproducible computational behavior; it does not establish real reef source attribution or operational forecast skill.

The pip download cache is keyed from Python/platform and `pyproject.toml`. Python dependencies include version ranges, so this cache does not make their entire transitive graph immutable. `pip check` and the tests validate the installed resolution. The Photon SDK version is explicitly pinned by the project.

Reproduce with a fresh Python 3.12 environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,photon,ocean]'
python -m pip check
python -m ruff check apps adapters scripts tests
GEMINI_ENABLED=false PHOTON_ENABLED=false PHOTON_ROUTES_JSON='[]' \
  python -m pytest -q --strict-config --strict-markers -ra
python scripts/evaluate_real_data.py --output work/real-data-ci.json
```

Use a source copy without private `.env` settings when reproducing clean CI. Full live-service commissioning is documented separately in [verification.md](verification.md).

## Dashboard job

Node.js 24 installs the committed `dashboard/package-lock.json` with `npm ci`, then runs the evidence-freshness regressions, ESLint, Next.js route type generation, TypeScript and the production build. The six regressions use Node's built-in test runner and cover case/evidence identity changes and delayed responses. The npm download cache is keyed from the lockfile; `node_modules` and `.next` are not shared between runs. No frontend step requires a running API or a provider key.

The `next typegen` step precedes `tsc --noEmit` so a clean checkout has generated route declarations. This follows the installed Next.js 16 CLI documentation, which treats those declarations and `next-env.d.ts` as generated files. The production build also performs its normal Next.js type validation.

```sh
cd dashboard
npm ci --no-audit --no-fund
node --test tests/*.test.mjs
npm run lint
npx next typegen
npx tsc --noEmit
npm run build
```

## Reading results

Open the repository's **Actions** tab or a pull request's checks. Both jobs must pass to call this workflow green. A GitHub workflow run proves the exact uploaded commit was checked; local command success alone is not a completed GitHub run. These jobs do not configure branch protection or make checks required for merging. The repository owner can choose that policy separately.

No workflow credential, channel assignment or automatic Photon reply is needed for these checks. A live messaging or physical-tank demonstration remains a separate, explicitly authorized activity.

## Validation before publication

The strict Python command passed **320 tests** locally, with one existing Starlette/httpx deprecation warning and no skips. Ruff and `pip check` passed. Six dashboard evidence-freshness and read-recovery regressions passed. A fresh isolated dashboard copy passed ESLint, `next typegen`, TypeScript and the production build without changing the running workspace's dependencies or build output. The real NOAA CLI verified its pinned hash and reproduced the declared 18/6 split and model metrics without changing input fixtures.

Workflow YAML structure, both event triggers, read-only permissions, disabled sponsor settings and immutable action pins were checked locally. The earlier hosted run at commit `3e068c1` passed both jobs. Each later commit needs its own completed hosted run before its CI can be called green; inspect the current commit's Actions results rather than carrying forward an earlier success.
