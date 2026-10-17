import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";
import { analysisDownloadJson, checkedValidationManifest, checkedValidationReceipt, MAX_VALIDATION_BYTES, parseValidationInput, validationAnswerMatches, validationReceiptIsCurrent, validationScopeKey, verifiedAnalysisExport } from "../app/components/validation-report-state.ts";

const scope = { comparisonId: "comparison-a", caseId: "case-a", sourceEvidenceId: "source-a", evaluationHash: "a".repeat(64) };
const manifest = { schema_version: "validation_report_v1", comparison_id: scope.comparisonId, input_payload_sha256: "b".repeat(64), evaluation_snapshot_hash: scope.evaluationHash, data_origin: "SYNTHETIC", outcome_origin: "SYNTHETIC_DEMO", protocol_id: "contract-rehearsal-v1", purpose: "CONTRACT_REHEARSAL", development_trial_ids: [], validation_trial_ids: ["trial-a", "trial-b"] };
function exportBundle() {
  const payload = { comparison: { id: scope.comparisonId, case_id: scope.caseId, source_evidence_id: scope.sourceEvidenceId, horizon_s: 1 }, frozen_plan: {}, provenance: {}, source_evidence: { id: scope.sourceEvidenceId }, evaluation_truth: { trials: [], evaluation: { comparison_id: scope.comparisonId, snapshot_hash: scope.evaluationHash } }, limitations: ["Synthetic test fixture"] };
  const canonical = JSON.stringify(payload).replace('"horizon_s":1}', '"horizon_s":1.0}');
  return { schema_version: "analysis_bundle_v1", payload, payload_canonical_json: canonical, payload_sha256: createHash("sha256").update(canonical).digest("hex"), metadata: { exported_at_utc: "2026-10-17T10:00:00Z", is_current: true, archive_reason: null } };
}
function receipt() {
  return { report: { ...manifest, id: "validation-a", case_id: scope.caseId, source_evidence_id: scope.sourceEvidenceId, case_revision: 1, created_at: 1, verification: "IDENTITY_AND_ACCOUNTING_CHECKED_METHOD_NOT_RERUN" }, checks: { identity_verified: true, accounting_verified: true, method_rerun: false, physical_validation: false }, summary: { by_source: [{ source_id: "A", layout: "baseline", released: 2, planned: 5, missing_planned: 3, zone_entries: 1, captured_before_entry: 1, no_entry: 0, unresolved: 0, entry_rate_bounds: { lower: .2, upper: .8, denominator: 5 }, predicted_entry_fraction: .9, predicted_entry_bounds: { lower: .9, upper: .9 } }], development_count: 0, validation_count: 2, missing_planned: 3, limitations: ["Contract rehearsal; no physical validation."], next_measurement: { action: "COMPLETE_FROZEN_PLAN", reason_codes: ["MISSING_VALIDATION_SLOTS"] } }, is_current: true, archive_reason: null };
}

test("export verifies exact canonical bytes and preserves Python float spelling in the download", async () => {
  const bundle = await verifiedAnalysisExport(exportBundle(), scope);
  assert.match(bundle.payload_canonical_json, /"horizon_s":1\.0/);
  const download = analysisDownloadJson(bundle), parsed = JSON.parse(download);
  assert.match(download, /"payload":.*"horizon_s":1\.0/);
  assert.equal(parsed.payload_canonical_json, bundle.payload_canonical_json);
  assert.equal(createHash("sha256").update(parsed.payload_canonical_json).digest("hex"), parsed.payload_sha256);
});

test("export rejects wrong case/evaluation identity and changed hash or semantic payload", async () => {
  await assert.rejects(verifiedAnalysisExport(exportBundle(), { ...scope, caseId: "case-other" }), /changed/);
  await assert.rejects(verifiedAnalysisExport(exportBundle(), { ...scope, evaluationHash: "c".repeat(64) }), /changed/);
  await assert.rejects(verifiedAnalysisExport({ ...exportBundle(), payload_sha256: "0".repeat(64) }, scope), /integrity hash/);
  const changed = exportBundle(); changed.payload.comparison.horizon_s = 2;
  await assert.rejects(verifiedAnalysisExport(changed, scope), /displayed payload differ/);
});

test("download keeps only whitelisted payload and metadata fields", async () => {
  const extra = exportBundle(); extra.payload.private_notes = "do-not-export";
  await assert.rejects(verifiedAnalysisExport(extra, scope), /whitelisted/);
  const bundle = exportBundle(); bundle.metadata.unexpected_field = "do-not-export";
  assert.doesNotMatch(analysisDownloadJson(await verifiedAnalysisExport(bundle, scope)), /do-not-export|unexpected_field/);
});

test("local JSON parsing is bounded and cannot become an accepted metric receipt", () => {
  assert.deepEqual(parseValidationInput(JSON.stringify(manifest)), manifest);
  for (const text of ["[]", "null", "{}", "not json", JSON.stringify({ ...manifest, note: "x".repeat(MAX_VALIDATION_BYTES) })]) assert.throws(() => parseValidationInput(text));
  assert.throws(() => checkedValidationReceipt(manifest, scope), /No validation metrics/);
  assert.throws(() => checkedValidationManifest({ ...manifest, purpose: "PROVEN_INDEPENDENT" }, scope), /unsupported/);
});

test("accepted report requires matching case/source identity and honest verification scope", () => {
  const result = receipt(); assert.equal(checkedValidationReceipt(result, scope), result);
  assert.throws(() => checkedValidationReceipt(result, { ...scope, caseId: "case-other" }), /No validation metrics/);
  assert.throws(() => checkedValidationReceipt(result, { ...scope, sourceEvidenceId: "source-other" }), /No validation metrics/);
  assert.throws(() => checkedValidationReceipt({ ...result, checks: { ...result.checks, physical_validation: true } }, scope), /No validation metrics/);
  assert.throws(() => checkedValidationReceipt({ ...result, checks: { ...result.checks, method_rerun: true } }, scope), /No validation metrics/);
});

test("archival reports remain readable but cannot be represented as the current evaluation", () => {
  const result = receipt();
  assert.equal(validationReceiptIsCurrent(result, scope, true), true);
  assert.equal(validationReceiptIsCurrent(result, { ...scope, evaluationHash: "c".repeat(64) }, true), false);
  assert.equal(validationReceiptIsCurrent(result, scope, false), false);
  assert.equal(validationReceiptIsCurrent({ ...result, is_current: false }, scope, true), false);
  assert.notEqual(validationScopeKey(scope), validationScopeKey({ ...scope, evaluationHash: "c".repeat(64) }));
  assert.notEqual(validationScopeKey(scope), validationScopeKey({ ...scope, caseId: "case-b" }));
});

test("invalid accepted summary numbers and malformed uncertainty bounds are withheld", () => {
  const result = receipt(); result.summary.by_source[0].entry_rate_bounds.lower = .9; result.summary.by_source[0].entry_rate_bounds.upper = .1;
  assert.throws(() => checkedValidationReceipt(result, scope), /No metric table/);
  const invalid = receipt(); invalid.summary.by_source[0].predicted_entry_fraction = NaN;
  assert.throws(() => checkedValidationReceipt(invalid, scope), /No metric table/);
});

test("unsupported nominal prediction remains unavailable while its explicit bounds remain readable", () => {
  const result = receipt();
  result.summary.by_source[0].predicted_entry_fraction = null;
  result.summary.by_source[0].predicted_entry_bounds = { lower: .2, upper: 1 };
  const accepted = checkedValidationReceipt(result, scope);
  assert.equal(accepted.summary.by_source[0].predicted_entry_fraction, null);
  assert.deepEqual(accepted.summary.by_source[0].predicted_entry_bounds, { lower: .2, upper: 1 });
  result.summary.by_source[0].predicted_entry_bounds = { lower: .8, upper: .1 };
  assert.throws(() => checkedValidationReceipt(result, scope), /No metric table/);
});

test("model answers are bound to the selected accepted receipt, including no selection", () => {
  assert.equal(validationAnswerMatches({ validation_report_id: "validation-a" }, "validation-a"), true);
  assert.equal(validationAnswerMatches({ validation_report_id: "validation-old" }, "validation-a"), false);
  assert.equal(validationAnswerMatches({}, "validation-a"), false);
  assert.equal(validationAnswerMatches({ validation_report_id: "validation-a" }, ""), false);
  assert.equal(validationAnswerMatches({}, ""), true);
  assert.equal(validationAnswerMatches(null, ""), false);
});
