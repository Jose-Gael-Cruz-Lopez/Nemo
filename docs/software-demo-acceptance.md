# Software demo acceptance: Tideward / ReefTrace

Owner: Megana (@megana111). Branch `team/software-demo-acceptance`.
Assignment: `docs/software-handoffs.md` (Megana: demo acceptance, accessibility and
browser end-to-end checks). This checks the **existing** software demo. It adds no
scientific capability, runs no physical setup, and makes no live provider call.

## Tested checkpoint and environment

| Item | Value |
| --- | --- |
| Base `main` (CI green) | `7448d1fe3aca230acd4cb7001b0c0b2380fe1d67` |
| Browser runs | Executed on `190a8e5`. `git diff 190a8e5 7448d1f -- dashboard apps` is empty: `7448d1f` adds only docs and images. `190a8e5` never went green on CI (its run was cancelled), so the branch is based on `7448d1f`. |
| Date | 17 October 2026 |
| Browser | Chromium 152.0.7977.149, the Claude desktop in-app browser pane |
| OS / runtimes | macOS 26.5.1; Node v24.15.0; Python 3.12.13; Next.js 16.4.2; React 19.3.1 |
| Servers | A disposable API (`uvicorn`, 127.0.0.1:8000) with a temporary data directory and a throwaway test token generated for this run, which is now deleted. `CHALK_ENABLED`, `PHOTON_ENABLED` and `GROK_VOICE_ENABLED` were all `false`. Dashboard served with `next dev` on 127.0.0.1:3000. |
| Not used | The team's running service or its operator token, `.env`, camera, pump, Photon, xAI and live Chalk. |

**Evidence labels used below:**
- **BROWSER**: clicked or typed in the real app, with the result read from the live page.
- **NODE**: a Node render or state test, with no browser.
- **PY**: a Python test using mocked provider transport.
- **HTTP**: the guarded `scripts/e2e_offline.py` workflow.
- **CODE**: confirmed by reading the source only.
- **BLOCKED**: not executable here; the reason is given.

## 1. Overview "Follow the evidence": acceptance matrix

Each row shows the step title and its button label, as the UI displays them.

| Step / action | Expected | Actual | Evidence |
| --- | --- | --- | --- |
| Section landmark | One labelled region | `section[aria-label="Follow the evidence"]`; a single `h1`; three `h2` step titles; decorative icons `aria-hidden` | BROWSER |
| "Trace a source" / "Open source trace" | Opens Investigations | URL becomes `#investigations`; the Investigations heading shows | BROWSER |
| "Compare two layouts" / "Compare layouts" | Opens Prevention with its own example | Prevention opens. The stock comparison is anchored to its own case (`case-13e08c6f…`), never the case selected in Investigations. | BROWSER |
| "Explain the evidence" / "Ask Chalk" | Opens the source investigator; sends nothing | Navigates to Investigations and scrolls to `#source-chalk`. No request is sent. With no demo loaded it shows "Choose an observation / Load a demo". | BROWSER |
| Busy state | Actions disabled while another action runs | `disabled={busy \|\| preventionBusy}`; all three render `disabled` | NODE (`demo-first-ui.test.mjs`) + CODE |
| Keyboard | Each action reachable and operable | Tab reaches every action and Enter activates it. **Defects 1 and 3** below. | BROWSER |
| 390 px | No hidden or off-screen primary action | `scrollWidth == 390`; "Start software demo" sits 458 px from the top of an 844 px viewport; the sidebar becomes a horizontally scrolling tab strip | BROWSER |

## 2. Source demo

These steps follow `docs/integrated-team-demo.txt` §1.

| Check | Actual | Evidence |
| --- | --- | --- |
| Sign in at `/login` with the keyboard only | Tab order: back link, token field, show-token button, then saved observations. Enter submits the form. The token is not in the URL, local or session storage, cookies or page markup. | BROWSER |
| "Load demo" | Button disabled while loading. Status region announces "Loading synthetic observations complete." The selected observation has `aria-current="true"`. | BROWSER |
| Observed-trajectory example | Ranked, Source C 100.0% (A and B 0.0%). The caption says "These values are not geographic probabilities." The saved identity sits under "Source report identity" (`estimate-4c4a3110…`). | BROWSER |
| "Ask Chalk", provider unconfigured | "No live model response · Chalk is not configured; deterministic evidence remains available." Sent to an `aria-live` region; the report stays visible. | BROWSER |
| "Recompute source support" (deliberate) | Button disabled during the run. Identity advanced `estimate-4c4a…` → `estimate-c006…`. The earlier Chalk answer was **no longer shown**. | BROWSER |
| "Test sensitivity" | "Sensitivity evidence" panel appears | BROWSER |
| Retained endpoint | **Unknown**: "The observation cannot distinguish a reliable source." A 40.3%, B 36.6%, C 23.1%, `ambiguous sources` | BROWSER |
| Invalid calibration | **Invalid**: "This input does not support a valid source comparison," `calibration invalid` | BROWSER |
| Navigate away mid-recompute | No error banner. On return the page showed the new current identity (`estimate-ce11…`) with its matching status. The write completes rather than being silently dropped or retried. | BROWSER |

## 3. Prevention demo

These steps follow `docs/integrated-team-demo.txt` §2.

| Check | Actual | Evidence |
| --- | --- | --- |
| "Load prevention demo" | Its own synthetic source case `case-13e08c6f…`; protected-zone polygon and both layout maps shown | BROWSER |
| Map labels | Baseline and intervention maps have correct `role="img"` titles. A third "Baseline" map is the preview inside the closed "Create your own comparison" panel. | BROWSER |
| Simulated versus recorded outcomes | "Which layout lets fewer tokens through? Simulation only" (100/100 baseline versus 0/100 intervention per source), shown separately from "Has it worked in recorded trials?" | BROWSER |
| Physical count | "0 operator-reported physical outcomes · 30 synthetic demo outcomes"; "No physical trials yet." | BROWSER |
| Denominators | Synthetic ledger 30/30, with 5/5 released of planned per source and layout. One unresolved per cell. Recorded bounds 80–100% (baseline) and 0–20% (intervention) use the planned denominator. | BROWSER |
| Trial entry on a **disposable** comparison | Created "Disposable synthetic acceptance test – not physical" (`prevention_comparison-51cb02fe…`) from `case-13e08c6f…`, using `prevention-demo-baseline-v1` and `prevention-demo-intervention-v1`. It is labelled SYNTHETIC DEMONSTRATION. Saved one synthetic baseline A zone entry at 15 s with a synthetic-only note. The ledger shows "1/30 · Plan incomplete · Unbalanced counts." The next slot advanced to 2/30; physical outcomes stay 0. The completed stock example was not changed. | BROWSER |
| Form labels | Outcome, entry time, note, both attestations, manifest and file inputs all have programmatic labels | BROWSER |
| Archival after the anchored case changes | Recomputed `case-13e08c6f…` (new `estimate-2dbc6a03…`). The disposable comparison became "Archived comparison" automatically. "Save one-token outcome" is disabled; the frozen ledger and export stay readable. | BROWSER + HTTP |
| Retry, pending, missing and unresolved state | Covered by the existing prevention-state and validation tests | NODE + HTTP |

## 4. Data Lab: fresh NOAA study and research discussion

These steps follow `docs/integrated-team-demo.txt` §5.

| Check | Actual | Evidence |
| --- | --- | --- |
| "Load buoy comparison" | "Six real buoy groups. Five forecasts." "6/6 historical groups · 180/180 model-hour results · no physical validation" | BROWSER |
| Groups and models distinguishable | "Buoy group" select has 6 options; "Prediction model" select has 5 | BROWSER |
| 36 intervals | "Valid adjacent observed intervals · 36 later positions; reused across five models" | BROWSER |
| Aggregate ADE / FDE (m) | Last observed drift 1,573.4 / 3,305.8; Kalman 1,655.7 / 3,410.8; ridge 1,772.1 / 3,460.2 | BROWSER |
| Units, starting points, limits | Paths in local metres, vector errors in m/s. "Kalman starts at its filtered final context state; the other models start at the raw final context observation." "Pre-outcome acquisition amendment." Unresolved-alias limitation shown. "This replay does not retune or automatically promote a model." | BROWSER |
| "Explain this result", unconfigured | "STOP · No live model response … Failure: NOT_CONFIGURED. The deterministic report remains visible above." The report figures remain on the page. **Defect 4** below. | BROWSER |
| Exact study and protocol citations; unrelated or stale response rejected; configured-but-failed gateway; timeout; unconfigured STOP; altered tool evidence | All present in the existing suites: `test_chalk_research.py` (forged or missing citations, unrelated backend evidence, sanitized provider failure, gateway and tool timeouts, unconfigured never calls the gateway), `test_fresh_physics.py` (mocked Chalk on the real report, lineage change rejected, trajectory tampering blocked before Chalk), and `fresh-drifter-study-state.test.mjs` (snapshot binding, STOP keeps the report, HTTP errors, snapshot substitution, amendment evidence). **60 passed** (PY) and **17 passed** (NODE). | PY + NODE |
| Earlier live Chalk REPORT | Recorded in `docs/integrated-team-demo.txt` as a separate 17 October event. It was not repeated and is not claimed here. | — |

## 5. Accessibility summary

| Area | Result | Evidence |
| --- | --- | --- |
| Skip link | "Skip to workspace" is present | BROWSER |
| Visible focus | **Defect 1** (contrast). Fixed for the guide; sitewide fix proposed. | BROWSER |
| Accessible names and labels | Guide buttons are named by their visible text. All trial and comparison form fields are labelled. Map SVGs have `role="img"` and titles. | BROWSER |
| Status and error announcements | Load and compute use `role="status"` and source Chalk uses `aria-live`. **Defect 4**: the Data Lab review result is not announced. **Defect 5**: the trial save and comparison freeze are not announced. | BROWSER |
| Disabled and loading controls | Load, Recompute and Freeze are disabled while busy; Save is disabled until the form is valid and on archived comparisons | BROWSER |
| 390 px and desktop | No horizontal overflow and no off-screen enabled button in Overview, Investigations, Prevention, Camera, Data lab or Settings | BROWSER |
| Reduced motion | `globals.css` has two `prefers-reduced-motion: reduce` blocks that disable animations and transitions, and `welcome.module.css` gates its entrance animation. **BLOCKED in the browser**: the in-app pane cannot emulate `prefers-reduced-motion`. Confirmed in CODE only. | CODE |

## 6. Defects found

### Fixed in this PR (leaf component `app/components/demo-guide.tsx` and its CSS module)

1. **Faint focus ring on the guide actions.** The shared ring `#b4d5e8` measured
   **1.37:1** against the guide card (`rgb(232,243,252)`); WCAG 2.2 asks for 3:1.
   The guide now uses `#1d6890` (5.43:1), checked in the browser with a real Tab
   press.
2. **Guide buttons defaulted to `type="submit"`.** Now `type="button"`.
3. **Step numbers read aloud** ("01", "02", "03") before each heading. They are now
   `aria-hidden`. Each action also gets `aria-describedby` pointing at its own step
   text, so a screen reader hears what "Ask Chalk" will do.

Regressions: `dashboard/tests/demo-guide-acceptance.test.mjs` (4 NODE tests). All 4
fail on the original component and pass with the fix.

### Proposed for Jose (shared files outside this scope; not changed here)

- **Sitewide focus ring** (`app/globals.css` line 51). Replacing `#b4d5e8` with a
  ≥3:1 colour such as `#1d6890` would fix every button, link and field. The login
  field's focus state (`welcome.module.css`, `.tokenField:focus-within`) changes the
  border from `#d0e1eb` to `#8cbedb` with a 5%-opacity glow, which is also weak.
- **Ask Chalk loses focus** (`app/workspace/page.tsx` line 389). After keyboard
  activation the view changes but focus falls to `<body>`. Moving focus to the
  `#source-chalk` heading (or the main heading on the target page) would fix it.
- **Defect 4: Data Lab review result not announced.** The STOP result and the
  report under "What does this result mean?" are not in a live region, unlike the
  source Chalk panel (`fresh-drifter-study.tsx`).
- **Defect 5: prevention writes not announced.** "Freeze comparison" and "Save
  one-token outcome" update the page without a status message (`prevention-workspace.tsx`).
- **Minor copy:** "1 synthetic demo outcomes" should be singular. In the source Chalk
  panel, "No live model response" appears twice and a stray "c" sits before
  "Change the question".
- **URL routing state:** the `#prevention?case=…` hash keeps the case selected in
  Investigations. The page itself never claims it, but a shared link could mislead.

## 7. Commands and exact results

```sh
cd dashboard
node --test tests/*.test.mjs        # 126 tests, 126 pass, 0 fail (122 existing + 4 new)
npm run lint                         # clean
npx next typegen                     # Types generated successfully
npx tsc --noEmit                     # clean
npm run build                        # Compiled successfully; routes / /login /workspace
cd ..
.venv/bin/python scripts/e2e_offline.py --output work/megana-software-http.json
# {"PASS": 122, "FAIL": 0, "BLOCKED": 6, "software_workflow_passed": true,
#  "expected_external_scopes_blocked": true, "physical_validation": false,
#  "live_provider_round_trip_verified": false}
# Guards: camera_opened false, provider_model_requests 0, new_photon_messages_sent 0,
#         live_port_8000_untouched true
.venv/bin/python -m pytest -q tests/unit/test_chalk_research.py tests/integration/test_fresh_physics.py
# 60 passed
```

The six BLOCKED HTTP scopes are expected:
- live Chalk model verification
- live Chalk prevention response
- live Chalk validation review
- physical webcam/tank calibration
- Photon device round trip
- xAI speech provider round trip

The production build ran only after both dev servers were stopped, so it did not
write into an active `.next`. `work/` is git-ignored.

## 8. Remaining limitations

- **One browser, one machine:** Chromium in the in-app pane. Safari, Firefox and
  real screen readers (VoiceOver, NVDA) were **not** tested. The accessible-name
  findings come from the DOM and accessibility tree, not from listening to a reader.
- **Reduced motion:** the browser check is BLOCKED (no emulation available); confirmed
  in CODE only.
- **Hidden-pane hydration:** while the in-app pane was hidden, pages did not hydrate,
  so typing reached the DOM but not React. That was this test environment, not the app.
  Every recorded browser result was taken with the pane visible.
- **Live and physical scopes are BLOCKED:** no live Chalk, Photon, xAI, camera or
  physical trial. Nothing here is physical validation.
- **Disposable data:** all browser data, including the disposable comparison and its
  one synthetic trial, lived in a temporary store that is now deleted. No physical
  recording, contact, token or provider output is committed.
