import assert from "node:assert/strict";
import test from "node:test";
import { MAX_MOTION_ABLATION_BYTES, MOTION_BASELINE_IDS, MOTION_MODEL_IDS, motionAblationReport, motionSkillLabel, parseMotionAblation, readMotionAblation } from "../app/components/motion-ablation-state.ts";

// Shape-only test fixture; these made-up values are never a measured NOAA result.
function fixture() {
  const hour = h => `1987-10-03T${String(h).padStart(2, "0")}:00:00Z`;
  return {
    schema_version: 1, kind: "TRAINING_ONLY_MOTION_ABLATION", status: "COMPLETED", data_origin: "REAL_HISTORICAL_NOAA_DRIFTER",
    test_data_used: false, model_selection_performed: false, calibrated_probability: false, physical_validation: false, automatic_model_promotion: false,
    split: { training_count: 18, min_prefix: 8, horizons: 6, prefix_counts: [8, 9, 10, 11, 12], origin_count: 5, step_seconds: 3600, test_data_used: false, model_selection_performed: false },
    origins: Array.from({ length: 5 }, (_, i) => ({ prefix_count: i + 8, fit_end_utc: hour(i + 7), models: MOTION_MODEL_IDS.map(id => ({ id, parameters: {}, predictions: Array.from({ length: 6 }, (_, h) => ({ time_utc: hour(i + 8 + h), horizon_hours: h + 1, latitude_deg: 46, longitude_deg: -137, error_m: 10 })) })) })),
    aggregates: MOTION_MODEL_IDS.map(id => ({ id, per_horizon: Array.from({ length: 6 }, (_, h) => ({ horizon_hours: h + 1, count: 5, mean_error_m: 10, median_error_m: 10, min_error_m: 10, max_error_m: 10, rmse_error_m: 10 })) })),
    paired_comparisons: MOTION_BASELINE_IDS.map(baseline_id => ({ candidate_id: "ridge_ar1", baseline_id, delta_definition: "candidate_minus_baseline_error_m", per_horizon: Array.from({ length: 6 }, (_, h) => ({ horizon_hours: h + 1, count: 5, mean_delta_m: 0, median_delta_m: 0, min_delta_m: 0, max_delta_m: 0, candidate_lower_error_count: 0, equal_error_count: 5, candidate_higher_error_count: 0, skill_vs_baseline: 0, reason_codes: [] })) })),
    limitations: ["SYNTHETIC_SHAPE_FIXTURE_ONLY; real experiment uses dependent training prefixes."],
    provenance: { integrity_verified: true, row_count: 24, drifter_id: "8707978", sha256: "a".repeat(64), source_url: "https://erddap.aoml.noaa.gov/gdp/erddap/tabledap/drifter_hourly_qc.csv?ID,time" },
  };
}

test("a fixed training-only report preserves signed deltas and negative skill", () => {
  const report = fixture(), pair = report.paired_comparisons[1].per_horizon[0];
  Object.assign(pair, { mean_delta_m: 60, median_delta_m: 50, min_delta_m: -10, max_delta_m: 100, candidate_lower_error_count: 1, equal_error_count: 0, candidate_higher_error_count: 4, skill_vs_baseline: -6 });
  const before = JSON.stringify(report), accepted = parseMotionAblation(before);
  assert.equal(accepted.paired_comparisons[1].per_horizon[0].skill_vs_baseline, -6);
  assert.equal(accepted.paired_comparisons[1].per_horizon[0].min_delta_m, -10);
  assert.equal(JSON.stringify(report), before);
});

test("zero baseline error is explicitly unavailable rather than zero skill", () => {
  const report = fixture(), row = report.paired_comparisons[0].per_horizon[0];
  row.skill_vs_baseline = null; row.reason_codes = ["ZERO_BASELINE_ERROR"];
  assert.equal(motionAblationReport(report).paired_comparisons[0].per_horizon[0].skill_vs_baseline, null);
  assert.match(motionSkillLabel(null), /Unavailable.*zero baseline/);
  assert.equal(motionSkillLabel(0), "0");
  assert.match(motionSkillLabel(-6), /-6/);
  row.reason_codes = []; assert.throws(() => motionAblationReport(report), /No comparison/);
  row.reason_codes = ["ZERO_BASELINE_ERROR"]; row.skill_vs_baseline = 0;
  assert.throws(() => motionAblationReport(report), /No comparison/);
});

test("false data origin, future-data claims and model promotion are rejected", () => {
  for (const patch of [{ data_origin: "SYNTHETIC" }, { data_origin: "MEASURED_TANK" }, { test_data_used: true }, { model_selection_performed: true }, { automatic_model_promotion: true }, { physical_validation: true }, { calibrated_probability: true }]) {
    assert.throws(() => motionAblationReport({ ...fixture(), ...patch }), /No comparison/);
  }
  const report = fixture(); report.split.training_count = 24;
  assert.throws(() => motionAblationReport(report), /No comparison/);
});

test("models, baselines, five paired counts and horizon identities must match", () => {
  const duplicate = fixture(); duplicate.aggregates[2].id = "last_drift";
  assert.throws(() => motionAblationReport(duplicate), /No comparison/);
  const missing = fixture(); missing.origins[0].models.pop();
  assert.throws(() => motionAblationReport(missing), /No comparison/);
  const pair = fixture(); pair.paired_comparisons[1].baseline_id = "stationary";
  assert.throws(() => motionAblationReport(pair), /No comparison/);
  const counts = fixture(); counts.paired_comparisons[0].per_horizon[0].candidate_lower_error_count = 1;
  assert.throws(() => motionAblationReport(counts), /No comparison/);
  const future = fixture(); future.origins[4].models[0].predictions[5].time_utc = "1987-10-03T18:00:00Z";
  assert.throws(() => motionAblationReport(future), /No comparison/);
});

test("nonfinite numbers, impossible ranges and non-NOAA links cannot reach display", () => {
  const invalid = fixture(); invalid.paired_comparisons[0].per_horizon[0].mean_delta_m = Infinity;
  assert.throws(() => motionAblationReport(invalid), /No comparison/);
  assert.throws(() => parseMotionAblation(JSON.stringify(fixture()).replace('"skill_vs_baseline":0', '"skill_vs_baseline":1e999')), /No comparison/);
  const range = fixture(); range.aggregates[0].per_horizon[0].min_error_m = 11;
  assert.throws(() => motionAblationReport(range), /No comparison/);
  for (const source_url of ["javascript:alert(1)", "https://erddap.aoml.noaa.gov.evil.test/gdp/erddap/tabledap/drifter_hourly_qc.csv", "https://private@erddap.aoml.noaa.gov/gdp/erddap/tabledap/drifter_hourly_qc.csv"]) {
    const report = fixture(); report.provenance.source_url = source_url;
    assert.throws(() => motionAblationReport(report), /No comparison/);
  }
});

test("text parsing rejects malformed or over-budget JSON including UTF-8 bytes", () => {
  for (const text of ["not json", "[]", "null", "{}"] ) assert.throws(() => parseMotionAblation(text));
  const report = fixture(); report.limitations = ["é".repeat(MAX_MOTION_ABLATION_BYTES / 2)];
  assert.throws(() => parseMotionAblation(JSON.stringify(report)), /bounded report size/);
});

test("bounded streaming accepts valid data and cancels oversized bodies without a length header", async () => {
  const accepted = await readMotionAblation(new Response(JSON.stringify(fixture())));
  assert.equal(accepted.kind, "TRAINING_ONLY_MOTION_ABLATION");
  let cancelled = false;
  const stream = new ReadableStream({ start(controller) { controller.enqueue(new Uint8Array(MAX_MOTION_ABLATION_BYTES + 1)); }, cancel() { cancelled = true; } });
  await assert.rejects(readMotionAblation(new Response(stream)), /bounded report size/);
  assert.equal(cancelled, true);
  await assert.rejects(readMotionAblation(new Response("{}", { headers: { "content-length": String(MAX_MOTION_ABLATION_BYTES + 1) } })), /bounded report size/);
});

test("HTTP failures stay failures and use a bounded status fallback for unreadable errors", async () => {
  await assert.rejects(readMotionAblation(new Response('{"detail":"Pinned source unavailable"}', { status: 503 })), /Pinned source unavailable/);
  await assert.rejects(readMotionAblation(new Response("not JSON", { status: 409 })), /HTTP 409/);
  await assert.rejects(readMotionAblation(new Response(null)), /empty/);
});
