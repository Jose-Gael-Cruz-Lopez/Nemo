# GitHub checks

The workflow at [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on every `push` and `pull_request`. It has three independent jobs on GitHub-hosted Ubuntu: **Python tests and scientific replay**, **Isolated offline HTTP workflow**, and **Dashboard tests, lint, types and production build**. A newer run cancels an older run for the same workflow/event/ref. There is no deployment, message sending, hardware access or live provider evaluation.

The workflow needs only GitHub's built-in `contents: read` permission. Checkout does not retain Git credentials, and no repository/account secrets are referenced. Official checkout/setup actions are pinned to inspected immutable commit SHAs, with their release versions in comments. Update a pin only after checking its official release and commit. [GitHub's concurrency documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency) describes the cancellation rule; [setup-node](https://github.com/actions/setup-node) and [setup-python](https://github.com/actions/setup-python) document dependency caching.

## Python job

Python 3.12 installs `.[dev,sponsors,evaluations,ocean]` from `pyproject.toml`, checks dependency consistency, verifies optional SDK imports, runs Ruff, and runs the full pytest suite. Sponsor SDKs and xarray/NetCDF are installed so their contract/reader tests do not silently skip because a package is absent. The macOS requirements snapshot is not used as a Linux lockfile.

Chalk, Photon and Grok Voice are explicitly disabled and their credentials/models/routes are empty. Runtime test data goes to the runner's temporary directory; its local operator token is a public, test-only string. Tests use explicit mocked HTTP transports for SDK contracts. The Chalk task-declaration test replaces deployment decorators before import; it does not deploy functions. This job never runs a live sponsor evaluation or camera capture.

Scientific CLI steps replay the original 18-context/6-heldout NOAA example, the training-only motion ablation, the earlier four-acquired-drifter study, the fresh six-GDP-ID study, and the separate synthetic Trace 2 validation example. JSON outputs go to the runner's temporary directory. The fresh reader verifies saved raw, selection, implementation, forecast and report lineage; CI never acquires a replacement dataset or makes a first score. Tests retain worse model results, missing/unresolved outcomes and explicit alias/interpolation limits. A Git diff check rejects rewrites of public or synthetic fixtures. This establishes reproducible computational behavior, not physical source accuracy, statistical independence or operational forecast skill.

The pip download cache is keyed from Python/platform and `pyproject.toml`. Python dependencies include version ranges, so this cache does not make their entire transitive graph immutable. `pip check` and the tests validate the installed resolution. Photon/Chalk evaluation package versions are explicitly pinned by the project.

Reproduce with a fresh Python 3.12 environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,sponsors,evaluations,ocean]'
python -m pip check
python -m ruff check apps adapters scripts tests
CHALK_ENABLED=false PHOTON_ENABLED=false PHOTON_ROUTES_JSON='[]' GROK_VOICE_ENABLED=false \
  python -m pytest -q --strict-config --strict-markers -ra
python scripts/evaluate_real_data.py --output work/real-data-ci.json
python scripts/evaluate_fresh_drifter_study.py --output work/fresh-drifters-ci.json
```

Use a source copy without private `.env` settings when reproducing clean CI. Full live-service commissioning is documented separately in [verification.md](verification.md).

## Isolated offline HTTP job

This five-minute job installs only `.[dev]` and executes the actual API over HTTP:

```sh
python scripts/e2e_offline.py --timeout-seconds 240 --output work/offline-http-ci.json
```

The runner accepts no existing API address. It starts and identifies its own child
on an OS-assigned loopback port, with a temporary store/token, no repository `.env`,
stripped provider credentials and explicit side-effect guards. It exercises source
rank/Unknown/Invalid, sensitivity and STOP, prevention/trials, exact retries,
exports/receipts, archival rejection, vector diagnostics and the fresh public study.
An authenticated research request with Chalk disabled must preserve deterministic
evidence and return an explicit unconfigured STOP, not a fabricated live answer.
The child is cleaned up after completion or failure.

The receipt distinguishes PASS, FAIL and six expected BLOCKED scopes: live Chalk
source verification, physical camera/tank commissioning, Photon device round trip,
xAI speech, live Chalk prevention response, and live Chalk validation review.
Camera-open, provider-HTTP, Photon-send and Photon-poll attempt counters must stay
zero. These blockers describe this deliberately isolated run; they do not negate a
separately recorded live Chalk or previously authorized Photon result. The job also
checks that public/sample inputs were not rewritten.

## Dashboard job

Node.js 24 installs the committed `dashboard/package-lock.json` with `npm ci`, then runs the evidence-freshness regressions, ESLint, Next.js route type generation, TypeScript and the production build. The complete `tests/*.test.mjs` suite uses Node's built-in test runner for evidence freshness, strict scientific report boundaries, failure states and delayed/stale responses. These are not browser click tests; actual browser verification is recorded separately. The npm download cache is keyed from the lockfile; `node_modules` and `.next` are not shared between runs. No frontend step requires a running API or a provider key.

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

Open the repository's **Actions** tab or a pull request's checks. All three jobs must pass to call this workflow green. A GitHub workflow run proves the exact uploaded commit was checked; local command success alone is not a completed GitHub run. These jobs do not configure branch protection or make checks required for merging. The repository owner can choose that policy separately.

No workflow credential, channel assignment or automatic Photon reply is needed for these checks. A live messaging or physical-tank demonstration remains a separate, explicitly authorized activity.

## Recorded local checkpoint and hosted status

The final local verification on 17 October 2026 recorded **1,061 Python tests**,
**122 frontend tests**, and **122 PASS / 0 FAIL / 6 expected BLOCKED** isolated HTTP
checks. Ruff, dependency checks, generated routes, TypeScript and the production
build passed. The fresh NOAA replay retained six GDP-ID groups and 180 outcomes
without changing frozen inputs. Actual browser checks verified the simplified
Overview, Ranked/Unknown/Invalid, prevention disclosures and fresh results; the
Overview had no horizontal overflow at a 390 px viewport.

An initial broad rerun from an empty temporary working directory encountered
relative fixture-path failures (19 setup errors and one test failure). The same
28-test source/recorded-path file subset passed from the repository root; the
subsequent full 1,061-test run passed there with isolated data and providers off.
No scientific code was changed to hide that invocation error.

Each commit needs its own completed hosted run before its CI can be called green.
Inspect the exact SHA and all three jobs in Actions rather than carrying forward
an earlier success. Local browser/live Chalk evidence, Node tests, offline HTTP
checks and hosted CI prove different scopes; none establishes a measured physical
interception or reef benefit.
