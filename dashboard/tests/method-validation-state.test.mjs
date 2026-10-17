import assert from "node:assert/strict";
import test from "node:test";
import { MAX_METHOD_EXAMPLE_BYTES, methodReplay, readMethodReplay } from "../app/components/method-validation-state.ts";

// Contract-only invented values; the actual method is separately replayed by backend tests.
function fixture() {
  const stats = (released = 2) => ({ planned: 2, released, missing_planned: 2 - released, zone_entries: released, captured_before_entry: 0, no_entry: 0, unresolved: 0, entry_rate_bounds: { lower: released / 2, upper: 1 }, observed_entry_rate_bounds: { lower: released ? 1 : 0, upper: 1 } });
  const group = physical => ({ layouts: { baseline: stats(physical ? 0 : 2), intervention: stats(physical ? 0 : 2) }, by_source: ["A", "B"].map(source_id => ({ source_id, baseline: stats(physical ? 0 : 2), intervention: stats(physical ? 0 : 2) })), plan: { expected_total: 8, recorded_total: physical ? 0 : 8, complete: !physical, balanced: !physical, order_followed: true } });
  const artifact = { path: "tests/fixtures/example.json", sha256: "a".repeat(64), bytes: 100 };
  return { schema_version: "prevention_method_replay_v1", kind: "SYNTHETIC_REPLAY_EXAMPLE", status: "COMPLETED", not_current_case: true, physical_validation: false, method_rerun: true, examples_are_independent: false, protocols: { development: "development-prevention-v1", validation: "heldout-prevention-v1" }, limitations: ["Synthetic alternatives reuse IDs; never pool."], current_case_requirements: ["Actual frozen protocols and full flow inputs required."], examples: ["unresolved", "positive_control"].map(id => ({ id, label: id, data_origin: "SYNTHETIC", not_current_case: true, physical_validation: false, method_rerun: true, provenance: { input: artifact, integrity_verified: true, expected_report: id === "unresolved" ? artifact : null, expected_report_match: id === "unresolved" ? true : null }, report: { schema_version: "validation_report_v1", id: "example-report", content_hash: "b".repeat(64), comparison_id: "synthetic-comparison", numerical_replay_verified: true, original_private_hash_verified: false, physical_validation: false, supports_significance_or_causal_claim: false, data_origin: "SYNTHETIC", source_identification: { evaluated: false }, by_origin: { SYNTHETIC_DEMO: group(false), OPERATOR_REPORTED_PHYSICAL: group(true) }, diagnostics: ["A", "B"].map(source_id => ({ source_id, data_origin: "SYNTHETIC_DEMO", scenario_id: "nominal", layouts: Object.fromEntries(["baseline", "intervention"].map(layout => [layout, { predicted: { zone_entry_fraction: 1, zone_entry_lower_fraction: 1, zone_entry_upper_fraction: 1, unsupported_count: 0 }, observed: stats() }])) })), selected_layout_usefulness: Object.fromEntries(["SYNTHETIC_DEMO", "OPERATOR_REPORTED_PHYSICAL"].map(origin => [origin, { status: "UNRESOLVED_ON_REPORTED_NEW_TRIALS", selected_layout: "intervention", physical_results_claimed: false }])), next_measurement: { kind: "INDEPENDENT_PAIRED_TRIAL", source_id: "B", reason_codes: ["UNRESOLVED"], explanation: "Measure a new independent paired release.", region_identified: false, region_cm: null }, limitations: ["No causal claim."] } })) };
}

test("distinct synthetic replay envelope keeps both alternatives separate", () => {
  const result = fixture(), checked = methodReplay(result);
  assert.equal(checked, result); assert.equal(checked.examples.length, 2);
  assert.equal(checked.examples_are_independent, false);
  assert.equal(checked.examples[0].report.next_measurement.source_id, "B");
  assert.throws(() => methodReplay(result.examples[0].report), /No report/);
});

test("physical/current-case/independence/method-not-rerun claims are rejected", () => {
  for (const edit of [{ not_current_case: false }, { physical_validation: true }, { examples_are_independent: true }, { method_rerun: false }, { schema_version: "analysis_bundle_v1" }]) assert.throws(() => methodReplay({ ...fixture(), ...edit }), /No report/);
  const result = fixture(); result.examples[0].report.data_origin = "MEASURED_TANK";
  assert.throws(() => methodReplay(result), /No report/);
});

test("tampered shared-report evidence and physical trial counts are rejected", () => {
  const mismatch = fixture(); mismatch.examples[0].provenance.expected_report_match = false;
  assert.throws(() => methodReplay(mismatch), /No report/);
  const physical = fixture(); physical.examples[0].report.by_origin.OPERATOR_REPORTED_PHYSICAL.plan.recorded_total = 1;
  assert.throws(() => methodReplay(physical), /No report/);
  const counted = fixture(); counted.examples[0].report.by_origin.SYNTHETIC_DEMO.by_source[0].baseline.unresolved = 2;
  assert.throws(() => methodReplay(counted), /No report/);
  const duplicate = fixture(); duplicate.examples[1].id = "unresolved";
  assert.throws(() => methodReplay(duplicate), /No report/);
});

test("nonfinite values, invented regions and malformed nominal bounds are withheld", () => {
  const nonfinite = fixture(); nonfinite.examples[0].report.diagnostics[0].layouts.baseline.predicted.zone_entry_fraction = NaN;
  assert.throws(() => methodReplay(nonfinite), /No report/);
  const region = fixture(); region.examples[0].report.next_measurement.region_identified = true;
  assert.throws(() => methodReplay(region), /No report/);
  const bound = fixture(); bound.examples[0].report.diagnostics[0].layouts.baseline.predicted.zone_entry_upper_fraction = .2;
  assert.throws(() => methodReplay(bound), /No report/);
});

test("bounded response reader accepts valid JSON and rejects oversize streams", async () => {
  assert.equal((await readMethodReplay(new Response(JSON.stringify(fixture())))).kind, "SYNTHETIC_REPLAY_EXAMPLE");
  let cancelled = false;
  const stream = new ReadableStream({ start(c) { c.enqueue(new Uint8Array(MAX_METHOD_EXAMPLE_BYTES + 1)); }, cancel() { cancelled = true; } });
  await assert.rejects(readMethodReplay(new Response(stream)), /bounded size/);
  assert.equal(cancelled, true);
});

test("HTTP failures and malformed JSON do not become successful reports", async () => {
  await assert.rejects(readMethodReplay(new Response('{"detail":"Pinned replay failed"}', { status: 409 })), /Pinned replay failed/);
  await assert.rejects(readMethodReplay(new Response("<html>backend unavailable</html>")), /unreadable JSON/);
});
