import assert from "node:assert/strict";
import test from "node:test";
import { MAX_MULTI_DRIFTER_BYTES, STUDY_MODELS, STUDY_BASELINES, multiDrifterReport, readMultiDrifter } from "../app/components/multi-drifter-state.ts";

// Invented schema fixture only; real acquired observations are tested separately.
function fixture() {
  const source_url = "https://erddap.aoml.noaa.gov/gdp/erddap/tabledap/drifter_hourly_qc.csv?ID,time";
  const groups = Array.from({ length: 4 }, (_, i) => ({ drifter_id: String(1001 + i), block_id: `block-${i}`, status: "COMPLETED", eligible: true, reason_codes: [], source_url }));
  const scope = "ACQUIRED_DECLARED_COHORT_NOT_FULL_PLANNED_TARGET";
  return { schema_version: 1, kind: "MULTI_DRIFTER_RETROSPECTIVE_STUDY", status: "PARTIAL_COVERAGE", data_origin: "REAL_HISTORICAL_NOAA_DRIFTERS", study_id: "study-test", test_data_used: true, model_selection_performed: false, calibrated_probability: false, physical_validation: false, automatic_model_promotion: false, independent_replication_verified: false, statistical_independence: false, metric_scope: scope,
    protocol: { sha256: "a".repeat(64), selection_sha256: "b".repeat(64), manifest_sha256: "c".repeat(64), implementation_receipt_sha256: "e".repeat(64), implementation_frozen_at_utc: "2026-10-17T02:00:00+00:00", frozen_at_utc: "2026-10-17T00:00:00Z", selection_frozen_at_utc: "2026-10-17T01:00:00Z", training_count: 18, horizons_hours: [1, 2, 3, 4, 5, 6], model_ids: [...STUDY_MODELS], development_only_ids: ["8707978"], selection_method: "frozen-before-scoring" },
    coverage: { target_groups: 6, declared_groups: 4, eligible_groups: 4, complete_groups: 4, target_outcomes: 144, attempted_outcomes: 96, scored_outcomes: 96, failed_outcomes: 0, missing_selection_slots: 2, selection_complete: false, acquired_cohort_complete: true, sampling_coverage_fraction: 4 / 6, model_prediction_coverage_fraction: 1 }, groups,
    selection_failures: [{ block_id: "unfilled", status: "METADATA_TIMEOUT", reason: "Source acquisition failed; no replacement.", source_url, selected_count: 0, target_count: 2 }],
    outcomes: groups.flatMap(g => STUDY_MODELS.flatMap(model_id => Array.from({ length: 6 }, (_, h) => ({ drifter_id: g.drifter_id, block_id: g.block_id, model_id, horizon_hours: h + 1, time_utc: `1989-01-01T${String(18 + h).padStart(2, "0")}:00:00Z`, status: "SCORED", error_m: 10, latitude_deg: 20, longitude_deg: -40, reason_codes: [] })))),
    trajectory_summaries: groups.flatMap(g => STUDY_MODELS.map(model_id => ({ drifter_id: g.drifter_id, model_id, attempted_horizons: 6, scored_horizons: 6, failed_horizons: 0, mean_error_m: 10, rmse_error_m: 10, endpoint_error_m: 10, parameters: {} }))),
    models: STUDY_MODELS.map(id => ({ id, macro: { attempted_groups: 4, complete_groups: 4, failed_groups: 0, mean_trajectory_error_m: 10, scope }, per_horizon: Array.from({ length: 6 }, (_, h) => ({ horizon_hours: h + 1, attempted_groups: 4, scored_groups: 4, failed_groups: 0, mean_error_m: 10, rmse_error_m: 10 })) })),
    paired_comparisons: STUDY_BASELINES.map(baseline_id => ({ candidate_id: "ridge_ar1", baseline_id, delta_definition: "candidate_minus_baseline_error_m", attempted_groups: 4, scored_groups: 4, failed_groups: 0, summary: { count: 4, mean_delta_m: 0, median_delta_m: 0, min_delta_m: 0, max_delta_m: 0, candidate_lower_error_count: 0, equal_error_count: 4, candidate_higher_error_count: 0, skill_vs_baseline: 0, reason_codes: [] }, reason_codes: [] })),
    provenance: { provider: "NOAA AOML", metadata_url: "https://erddap.aoml.noaa.gov/gdp/erddap/info/drifter_hourly_qc/index.html", product_doi: "10.25921/x46c-3620", license_name: "CC-BY-4.0", license_url: "https://creativecommons.org/licenses/by/4.0/", integrity_verified: true, sources: groups.map(g => ({ drifter_id: g.drifter_id, block_id: g.block_id, source_url, sha256: "d".repeat(64), bytes: 2000, retrieved_at_utc: "2026-10-17T00:30:00Z", status: "ACQUIRED" })) }, limitations: ["Synthetic schema fixture only; actual cohort is retrospective and dependent."],
  };
}
function failedFixture() {
  const r = fixture(), o = r.outcomes[0]; Object.assign(o, { status: "FAILED", error_m: null, latitude_deg: null, longitude_deg: null, reason_codes: ["GEOMETRY_BUDGET"] });
  Object.assign(r.coverage, { complete_groups: 3, acquired_cohort_complete: false, scored_outcomes: 95, failed_outcomes: 1, model_prediction_coverage_fraction: 95 / 96 });
  const t = r.trajectory_summaries[0]; Object.assign(t, { scored_horizons: 5, failed_horizons: 1, mean_error_m: null, rmse_error_m: null, endpoint_error_m: null });
  r.models[0].macro.complete_groups = 3; r.models[0].macro.failed_groups = 1;
  r.models[0].per_horizon[0].scored_groups = 3; r.models[0].per_horizon[0].failed_groups = 1;
  for (const m of r.models) { m.macro.mean_trajectory_error_m = null; for (const row of m.per_horizon) row.mean_error_m = row.rmse_error_m = null; }
  for (const p of r.paired_comparisons) { p.summary = null; p.reason_codes = ["INCOMPLETE_DECLARED_COHORT"]; }
  r.paired_comparisons[0].scored_groups = 3; r.paired_comparisons[0].failed_groups = 1;
  return r;
}

test("four acquired drifters retain the six-drifter target and conditional macro scope", () => {
  const r = multiDrifterReport(fixture()); assert.equal(r.status, "PARTIAL_COVERAGE");
  assert.equal(r.coverage.target_outcomes, 144); assert.equal(r.coverage.attempted_outcomes, 96);
  assert.equal(r.models[0].macro.mean_trajectory_error_m, 10);
  assert.equal(r.test_data_used, true);
  const complete = fixture(); complete.status = "COMPLETED";
  assert.throws(() => multiDrifterReport(complete), /No study/);
});

test("a failure is retained as null and withholds all primary aggregate metrics", () => {
  const r = multiDrifterReport(failedFixture()); assert.equal(r.coverage.failed_outcomes, 1);
  assert.equal(r.outcomes[0].error_m, null); assert.equal(r.models[3].macro.mean_trajectory_error_m, null);
  const hidden = failedFixture(); hidden.models[3].macro.mean_trajectory_error_m = 10;
  assert.throws(() => multiDrifterReport(hidden), /No study/);
  const zeroed = failedFixture(); zeroed.outcomes[0].error_m = 0;
  assert.throws(() => multiDrifterReport(zeroed), /No study/);
});

test("Cartesian outcomes cannot be silently dropped, duplicated or reassigned", () => {
  const dropped = fixture(); dropped.outcomes.pop(); assert.throws(() => multiDrifterReport(dropped), /No study/);
  const duplicate = fixture(); duplicate.outcomes[1] = { ...duplicate.outcomes[0] }; assert.throws(() => multiDrifterReport(duplicate), /No study/);
  const counts = fixture(); counts.trajectory_summaries[0].scored_horizons = 5; counts.trajectory_summaries[0].failed_horizons = 1;
  assert.throws(() => multiDrifterReport(counts), /No study/);
  const cohorts = fixture(); cohorts.provenance.sources[1] = { ...cohorts.provenance.sources[0] }; assert.throws(() => multiDrifterReport(cohorts), /No study/);
});

test("false origin, independence, physical and training-only claims are rejected", () => {
  for (const patch of [{ data_origin: "SYNTHETIC" }, { test_data_used: false }, { statistical_independence: true }, { physical_validation: true }, { automatic_model_promotion: true }]) assert.throws(() => multiDrifterReport({ ...fixture(), ...patch }), /No study/);
  const reused = fixture(); reused.groups[0].drifter_id = "8707978"; assert.throws(() => multiDrifterReport(reused), /No study/);
  const reselected = fixture(); reselected.protocol.selection_frozen_at_utc = "2026-10-16T00:00:00Z"; assert.throws(() => multiDrifterReport(reselected), /No study/);
});

test("nonfinite values and zero-denominator skill never become finite-looking results", () => {
  const invalid = fixture(); invalid.models[0].macro.mean_trajectory_error_m = NaN; assert.throws(() => multiDrifterReport(invalid), /No study/);
  const zero = fixture(); zero.paired_comparisons[0].summary.skill_vs_baseline = null; zero.paired_comparisons[0].summary.reason_codes = ["ZERO_BASELINE_ERROR"];
  assert.equal(multiDrifterReport(zero).paired_comparisons[0].summary.skill_vs_baseline, null);
  zero.paired_comparisons[0].summary.reason_codes = []; assert.throws(() => multiDrifterReport(zero), /No study/);
});

test("bounded streaming, bad HTTP and invalid source links fail safely", async () => {
  assert.equal((await readMultiDrifter(new Response(JSON.stringify(fixture())))).groups.length, 4);
  let cancelled = false; const stream = new ReadableStream({ start(c) { c.enqueue(new Uint8Array(MAX_MULTI_DRIFTER_BYTES + 1)); }, cancel() { cancelled = true; } });
  await assert.rejects(readMultiDrifter(new Response(stream)), /bounded size/); assert.equal(cancelled, true);
  await assert.rejects(readMultiDrifter(new Response('{"detail":"Pinned study unavailable"}', { status: 503 })), /Pinned study unavailable/);
  const malicious = fixture(); malicious.groups[0].source_url = "https://erddap.aoml.noaa.gov.evil.test/gdp/erddap/"; assert.throws(() => multiDrifterReport(malicious), /No study/);
});
