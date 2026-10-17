import assert from "node:assert/strict";
import test from "node:test";
import { canCorrectRejectedTrial, currentPreventionAnswer, decodePendingTrial, definitiveTrialStatus, parseProtectedZone, safeInvestigationFailure, sourceCaseChanged, validTrialObservation } from "../app/components/prevention-state.ts";

const bounds = { x_min_cm: 0, x_max_cm: 20, y_min_cm: 0, y_max_cm: 10 };
const trial = { trial_key: "stable-trial-123", layout: "baseline", source_id: "A", data_origin: "OPERATOR_REPORTED_PHYSICAL", outcome: "no_entry", token_accounted: true, horizon_completed: true, physical_confirmed: true, note: "Observed for twenty seconds; token counted." };

test("protected-zone preview rejects crossed, degenerate, repeated and out-of-tank geometry", () => {
  assert.deepEqual(parseProtectedZone("[[1,1],[5,1],[5,4],[1,4]]", bounds), [[1, 1], [5, 1], [5, 4], [1, 4]]);
  for (const polygon of ["[[1,1],[5,4],[5,1],[1,4]]", "[[1,1],[2,2],[3,3]]", "[[1,1],[5,1],[1,1]]", "[[1,1],[21,1],[1,4]]", "[[1,1],[5,1],[null,4]]", "{}"]) assert.throws(() => parseProtectedZone(polygon, bounds));
});

test("physical no-entry and interception records need actual confirmation and a completed horizon", () => {
  assert.equal(validTrialObservation(trial, 20), true);
  assert.equal(validTrialObservation({ ...trial, horizon_completed: false }, 20), false);
  assert.equal(validTrialObservation({ ...trial, physical_confirmed: false }, 20), false);
  assert.equal(validTrialObservation({ ...trial, token_accounted: false }, 20), false);
  assert.equal(validTrialObservation({ ...trial, outcome: "intercepted_before_entry", interception_time_s: 4 }, 20), true);
  assert.equal(validTrialObservation({ ...trial, outcome: "intercepted_before_entry", interception_time_s: 4, horizon_completed: false }, 20), false);
});

test("entry needs a bounded event time and counted token; unresolved cannot claim an event", () => {
  assert.equal(validTrialObservation({ ...trial, outcome: "zone_entry", horizon_completed: false, entry_time_s: 4 }, 20), true);
  assert.equal(validTrialObservation({ ...trial, outcome: "zone_entry", entry_time_s: 21 }, 20), false);
  assert.equal(validTrialObservation({ ...trial, outcome: "zone_entry", entry_time_s: 4, token_accounted: false }, 20), false);
  assert.equal(validTrialObservation({ ...trial, outcome: "unresolved", token_accounted: false, horizon_completed: false }, 20), true);
  assert.equal(validTrialObservation({ ...trial, outcome: "unresolved", entry_time_s: 4 }, 20), false);
  assert.equal(validTrialObservation({ ...trial, data_origin: "SYNTHETIC_DEMO", physical_confirmed: true }, 20), false);
  assert.equal(validTrialObservation({ ...trial, data_origin: "SYNTHETIC_DEMO", physical_confirmed: false }, 20), true);
});

test("a failed trial submission round-trips its exact key and payload, scoped to its comparison", () => {
  const pending = { version: 1, comparison_id: "comparison-a", payload: trial };
  const raw = JSON.stringify(pending);
  assert.deepEqual(decodePendingTrial(raw, "comparison-a"), pending);
  assert.equal(decodePendingTrial(raw, "comparison-b"), null);
  assert.equal(decodePendingTrial(JSON.stringify({ ...pending, version: 2 }), "comparison-a"), null);
  assert.equal(decodePendingTrial(JSON.stringify({ ...pending, payload: { ...trial, horizon_completed: undefined } }), "comparison-a"), null);
  assert.equal(decodePendingTrial("not json", "comparison-a"), null);
});

test("an answer is hidden after new trial evidence or comparison selection changes", () => {
  const answer = { comparison_id: "comparison-a", evaluation_digest: "snapshot-old", explanation: "frozen answer" };
  assert.equal(currentPreventionAnswer(answer, "comparison-a", "snapshot-old"), answer);
  assert.equal(currentPreventionAnswer(answer, "comparison-a", "snapshot-new"), null);
  assert.equal(currentPreventionAnswer(answer, "comparison-b", "snapshot-old"), null);
});

test("source recomputation and STOP archive the corresponding comparison only", () => {
  const comparison = { case_id: "case-a", source_evidence_id: "source-old" };
  assert.equal(sourceCaseChanged(comparison, [{ id: "case-a", state: "OBSERVED", evidence_id: "source-old" }]), false);
  assert.equal(sourceCaseChanged(comparison, [{ id: "case-a", state: "OBSERVED", evidence_id: "source-new" }]), true);
  assert.equal(sourceCaseChanged(comparison, [{ id: "case-a", state: "STOPPED", evidence_id: "source-old" }]), true);
  assert.equal(sourceCaseChanged(comparison, [{ id: "case-b", state: "STOPPED", evidence_id: "source-old" }]), false);
});

test("completed HTTP validation rejections are distinct from ambiguous transport, server and abort failures", () => {
  for (const status of [400, 401, 403, 404, 409, 422, 429]) assert.equal(definitiveTrialStatus({ status }), status);
  for (const cause of [new TypeError("Failed to fetch"), new DOMException("Aborted", "AbortError"), { status: 500 }, { status: 503 }, { status: 408 }, { status: 499 }, { status: "422" }, { status: 200 }, null]) assert.equal(definitiveTrialStatus(cause), null);
});

test("a reconciled rejected draft is correctable only while its exact key is absent from the saved ledger", () => {
  const rejected = { version: 1, comparison_id: "comparison-a", payload: trial, rejected_status: 422 };
  assert.equal(canCorrectRejectedTrial(rejected, []), true);
  assert.equal(canCorrectRejectedTrial(rejected, [trial.trial_key]), false);
  assert.equal(canCorrectRejectedTrial({ ...rejected, rejected_status: undefined }, []), false);
  assert.equal(canCorrectRejectedTrial({ ...rejected, rejected_status: 503 }, []), false);
  assert.deepEqual(decodePendingTrial(JSON.stringify(rejected), "comparison-a"), rejected);
  assert.equal(decodePendingTrial(JSON.stringify({ ...rejected, rejected_status: 503 }), "comparison-a"), null);
});

test("safe provider diagnostics explain a rate limit without suggesting an automatic retry", () => {
  const failure = safeInvestigationFailure({ live_model_response: false, failure_code: "PROVIDER_HTTP_ERROR", provider_status_code: 429 });
  assert.equal(failure.code, "PROVIDER_HTTP_ERROR");
  assert.equal(failure.httpStatus, 429);
  assert.match(failure.message, /rate or quota limit/);
  assert.match(failure.message, /No automatic retry/);
  assert.equal(safeInvestigationFailure({ live_model_response: true, failure_code: "PROVIDER_HTTP_ERROR", provider_status_code: 429 }), null);
});

test("failure diagnostics allow known timeout stages and discard arbitrary upstream strings", () => {
  const timeout = safeInvestigationFailure({ failure_code: "TIMEOUT", timeout_stage: "tool:get_prevention_evidence" });
  assert.equal(timeout.stage, "tool:get_prevention_evidence");
  assert.equal(safeInvestigationFailure({ failure_code: "TIMEOUT", timeout_stage: "model_call_3" }).stage, "model_call_3");
  assert.equal(safeInvestigationFailure({ failure_code: "https://private.example/key", timeout_stage: "Authorization: private", provider_status_code: "429" }), null);
  const safe = safeInvestigationFailure({ failure_code: "TIMEOUT", timeout_stage: "https://private.example/key", provider_status_code: 999 });
  assert.equal(safe.stage, null);
  assert.equal(safe.httpStatus, null);
  assert.doesNotMatch(JSON.stringify(safe), /private\.example|Authorization/);
});
