# Field commissioning and the field-manifest v1 receipt

Lane 1 of the team handoff (`docs/team-handoff-prompts.md`). This adds a guided
workflow that turns one measured tank setup into a reproducible receipt. It does
not rebuild tracking, recording, drift fitting, profiles or source estimation.

**Status of the physical gate: BLOCKED.** This branch was built and tested with an
explicit synthetic fake capture device. No physical commissioning has been done.
Run the operator checklist below on the actual rig before you claim a commissioned tank.

## What the workflow does

There are eight linear steps. Each one calls an **existing** endpoint, and each
endpoint keeps its own gate:

| # | Step | Existing endpoint | Gate (unchanged) |
| - | ---- | ----------------- | ---------------- |
| 1 | Operator-selected camera session | `POST /camera/start` | The operator opens it explicitly; the wizard never opens a camera |
| 2 | Water-plane mapping | `POST /vision/calibrate`, or local `POST /vision/calibrations/revalidate` for an exported saved mapping | New fit: ≥4 correspondences and ≥3 separate checks. Reuse: unchanged saved matrix/tolerance and ≥3 current independent surveyed checks; current session and image size must match |
| 3 | Training and validation drift | `POST /camera/record` (with `calibration_id`) | Approved mapping, same session; gaps and second tokens split tracks |
| 4 | Recorded flow | `POST /flow/fit-recordings` | Disjoint recording IDs and frames, one mapping and session |
| 5 | Measured profile admission | `POST /profiles` | Exact immutable flow, ≥90% held-out coverage, frozen positive limits |
| 6 | Rig state | `POST /rig/revalidate` (only after a disturbance) | New drift after the disturbance, within the frozen revalidation limit |
| 7 | First source observation | `POST /camera/record` (with `profile_id`) → `POST /recordings/{id}/case` | The existing LIVE gate (`Runtime.validate_live`) |
| 8 | Operator attestations | — | Recorded as statements, never as verification |

The new endpoints only **re-read** those stored artifacts and decide:

- `POST /api/v1/field-sessions/preflight` (operator): explains every step as
  `PASSED`, `BLOCKED` or `MISSING`, with a code, a message and help. It saves
  nothing.
- `POST /api/v1/field-sessions` (operator): re-runs the same checks. If any step
  fails, it returns 409 and saves nothing. If every step passes, it saves one
  immutable READY receipt and returns it. Repeating an identical request returns
  the same receipt.
- `GET /api/v1/field-sessions` and `GET /api/v1/field-sessions/{manifest_id}`:
  local reads, like `GET /profiles`. The detail response is
  `{manifest, is_current, stale_reasons}`, and each read re-verifies the stored
  hash. `stale_reasons` can be `RIG_CHANGED_AFTER_RECEIPT`, `CAMERA_SESSION_ENDED`,
  `FIRST_OBSERVATION_INACTIVE` or `FIRST_OBSERVATION_MISSING`. A stale receipt stays
  readable and is never edited.

Freezing repeats the complete readiness check while holding the camera lifecycle
lock and one SQLite writer reservation through the insert. The hash-covered
`rig_change_id` records the latest committed disturbance by insertion order.
Currentness compares that identity rather than timestamps, because a queued
disturbance may carry a timestamp created before its database commit. A stale or
unavailable camera also archives the receipt as `CAMERA_STALE_OR_UNAVAILABLE`.

Receipt IDs and candidate-source labels are bounded public identifiers. Paths,
contacts and known credential prefixes are rejected, rather than renamed. These
values are withheld from blocked messages and public receipt-validation errors.

The request body (`FieldSessionInput`) contains only IDs and the five operator
attestation booleans. Extra fields are rejected with 422, so a caller cannot send
`status`, `approved`, `checks` or `true_source`. The server derives every pass/fail
result from stored objects. It recomputes the calibration's content-derived ID, and
it compares the flow inside the profile against the stored flow object.

The service adds one scope guard of its own: `MAPPING_SCALE_IMPLAUSIBLE`. A mapping
entered entirely in millimetres is self-consistent, so it passes the check-point
gate. The service therefore refuses a mapped camera view wider than 200 cm,
because this is a tabletop rig. This guard only adds a refusal; it does not weaken
any existing gate.

## Contract proposal: field-manifest v1 (Lane 1 → Lanes 2/3)

**This proposal needs confirmation from Lanes 2 and 3 before they integrate.**
Schema: `apps/api/reeftrace_api/schemas/field_sessions.py` (`FieldManifestV1`).
Synthetic fixture: `tests/fixtures/team_handoff/field_manifest_v1.json`.
Parser test: `tests/unit/test_field_protocol.py`.

```text
schema_version   "field_manifest_v1"
status           "READY"            (only READY receipts exist; nothing else is saved)
manifest_id      "fm-" + content_hash[:16]
content_hash     sha256 of canonical JSON (sorted keys, compact, allow_nan=false)
                 over every field except manifest_id, content_hash and created_at
created_at       detached save time; it is not part of the hash
capture          camera_session_id, device_index, backend,
                 capture_origin USB_CAMERA_DEVICE | SYNTHETIC_FAKE_CAPTURE, image_size_px
calibration      calibration_id, content_hash, validation_count ≥3, mean/max error,
                 max_allowed_error_cm, units "cm"
recordings       training/validation recording IDs, sample counts,
                 frame_splits_disjoint true, timestamp_kind host_receipt_not_exposure
flow             flow_id, content_hash, data_origin MEASURED_TANK,
                 validation_rmse_cm_s, validation_coverage_fraction ≥0.9, node_count
profile          profile_id, content_hash, data_origin MEASURED_TANK, source_ids,
                 max_validation_rmse_cm_s, revalidation_max_rmse_cm_s
rig_check_id     latest rig check after a disturbance, or null
rig_change_id    latest committed disturbance ID at freezing, or null
first_observation case_id, recording_id, mode LIVE, evidence_frame_count
operator_attestations  five booleans, all true
checks           the eight steps, in order, all PASSED
warnings         codes, e.g. SYNTHETIC_FAKE_CAPTURE_NOT_PHYSICAL,
                 HOST_RECEIPT_TIMESTAMPS_NOT_EXPOSURE,
                 OPERATOR_ATTESTATIONS_NOT_INDEPENDENTLY_VERIFIED,
                 SCORES_CONDITIONAL_ON_THIS_FROZEN_SETUP, PARTIAL_VALIDATION_COVERAGE
provenance       producer, gates "server_reverified_from_stored_artifacts",
                 hardware_independently_verified false,
                 physical_attestation "operator_attested_not_independently_verified",
                 excludes [source_release_truth, credentials, absolute_paths,
                           raw_camera_images, free_text_notes]
```

The receipt never contains release truth, credentials, phone handles, absolute
paths, frame file paths, raw images or free-text notes. The `content_hash` values
of the calibration, flow and profile let a consumer such as `analysis_bundle_v1`
check that a referenced artifact has not changed. Use
`apps.api.reeftrace_api.services.field_sessions.verify_manifest(document)` to
parse a receipt and check its hash. The fixture's artifact hashes are synthetic
placeholders.

Open points for Lanes 2/3:
- Should `analysis_bundle_v1` embed the full manifest or only `{manifest_id, content_hash}`?
- Lane 2 needs the profile drift training/validation recording IDs and session
  identity to detect dependence. They are in `recordings` and `capture.camera_session_id`.

## Lane 3: mounting the router

Add the router inside `create_app` in `apps/api/reeftrace_api/main.py`, after
`operator` is defined:

```python
from .api.v1.endpoints.field_sessions import create_field_sessions_router

app.include_router(create_field_sessions_router(runtime, operator), prefix="/api/v1")
```

The factory refuses to build without a callable operator dependency. The existing
global `ValueError → 409` and `KeyError → 404` handlers apply. No change to
Runtime, Store or `CaseInput` is required. Receipts use the existing
`Store.put/get/list` with kind `field_manifest`.

## Lane 3: mounting the component

```tsx
import { FieldWorkflow } from "./components/field-workflow";

<FieldWorkflow
  request={request}                 // page.tsx request helper (adds /api/v1 and the operator token)
  apiBase={API}                     // used only for the latest-frame preview
  operatorConnected={!!token}
  onRequireOperator={openOperator}
  onBusyChange={setFieldBusy}       // optional; lets the page lock other actions
  onOpenCase={id => openCase(id)}   // optional
  blocked={!!busy || stopping}      // optional
/>
```

The draft lives in `sessionStorage` under `reeftrace.field-workflow.draft.v1`, so
it survives reloads and failed requests. Changing an upstream artifact clears
everything derived from it, and also clears the attestations. "Freeze field
receipt" is enabled only when the latest server preflight was READY for that
exact request. The pure state module (`field-workflow-state.ts`) parses every API
response and throws on any shape it does not recognize. Its tests are in
`dashboard/tests/field-workflow-state.test.mjs`.

The component is not mounted on this branch, as the lane rules require. A full
browser rehearsal happens after Lane 3 mounts it.

## Operator checklist (executable on the actual rig)

Run these steps in order. If a step fails, stop: fix the cause and redo that step.
Do not move on. Pump power and token recovery stay manual throughout.

1. **Fixture.** Fill the bin to the measured waterline mark. Set the pump dial and
   outlet to the recorded position. Seat the hose and pocket on their marks. Fix the
   camera mount and turn on steady lighting. Write each setting down outside the
   software.
2. **Camera.** In the wizard, enter the C920s device index and press *Start this
   webcam*. Confirm the preview shows the tank and not the laptop camera. Press
   *Use current session*.
3. **Mapping.** Place at least seven marks on the water surface: four or more for
   mapping (spread toward the corners) and three or more separate check marks.
   Measure each mark from one tank corner with a ruler, in one unit, and select
   that unit. Click each mark in the preview to fill in its pixel position. Then
   type its measured position. Fit the mapping. If the check error exceeds the
   tolerance, re-measure. Do not raise the tolerance to pass.
4. **Drift.** For each run, release one red token at an inlet and keep your hands
   out of view. Record two or more **training** runs and at least one separate
   **validation** run. Cover the region where source observations will happen.
5. **Flow.** Enter the tank bounds and declare the coverage radius before fitting.
   Fit the flow. If supported coverage is under 90%, record more training drift
   where the validation run went. Do not widen the radius.
6. **Profile.** Measure each inlet region (A, B, C), the permitted observation
   region and the retention pocket. Enter the error limits you declared from
   development runs. Then admit the profile.
7. **Disturbance.** If the rig was bumped, refilled, re-aimed or recovered, a
   disturbance is recorded (`POST /rig/disturbed` or a manual outcome). Restore the
   setup, tick the four checks and press *Record drift and revalidate*.
8. **First observation.** Release one token and press *Record new source case*.
   A live preview frame is never case evidence.
9. **Attest and freeze.** Tick each statement only after you have checked it
   physically. Press *Check all steps*, read any blocked help, then press *Freeze
   field receipt*. Record the manifest ID and hash.

Report the physical gate as **BLOCKED**, not complete, in any of these cases:
- the C920s, bin, pump or tokens are unavailable,
- any step above failed,
- only the synthetic fake capture was used.

## Verification on this branch

These tests check software behavior with synthetic data. They are not evidence of
tank accuracy. They use `SyntheticFakeCapture`, which replaces only the capture
device. The real recorder, tracker, flow fit, profile gate, rig revalidation and
LIVE case gate all run unchanged.

```sh
.venv/bin/python -m pytest -q tests/integration/test_field_sessions.py tests/unit/test_field_protocol.py
.venv/bin/python -m ruff check apps adapters scripts tests
cd dashboard && node --test tests/field-workflow-state.test.mjs
```

The integration scenarios are:
- missing camera
- stale and restarted session
- wrong units: all millimetres, and mixed units
- invalid mapping: collinear points
- overlap between training and validation recordings, and swapped splits
- unsupported flow
- a successful explicit fake-capture protocol
- tampering with a stored receipt
- caller claims and truth injection
- operator authentication
- rig disturbance followed by a fresh case after revalidation

No invalid path creates a READY receipt.
