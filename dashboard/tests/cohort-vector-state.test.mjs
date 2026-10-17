import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { readCohortVectorReport, validateCohortVectorReport } from "../app/components/vector-diagnostic-state.ts";

// Generated from run_noaa_cohort_vector_diagnostic() using the actual pinned
// historical NOAA cohort. Already-viewed forecasts are not a fresh test set.
// Mutations below exercise the display boundary and are not new observations.
const payload = readFileSync(new URL("./fixtures/cohort-vector-report.json", import.meta.url), "utf8");
const frozen = JSON.parse(payload);
const fixture = () => structuredClone(frozen);
const rejected = report => assert.throws(() => validateCohortVectorReport(report), /No result was accepted/);

function incompleteFixture() {
  const report = fixture(), track = report.groups[0].models[3];
  track.status = "WITHHELD"; track.metrics = null;
  track.reason_codes = ["INCOMPLETE_FORECAST_TRACK", "GEOMETRY_BUDGET"];
  track.intervals = track.intervals.map(row => ({
    horizon_hours: row.horizon_hours, end_utc: row.end_utc,
    status: "FAILED", reason_codes: ["INCOMPLETE_FORECAST_TRACK"],
  }));
  Object.assign(report.coverage, { scored_model_intervals: 90, failed_model_intervals: 6, common_acquired_cohort_complete: false });
  for (const model of report.models) {
    model.metrics = null;
    model.reason_codes = ["INCOMPLETE_COMMON_ACQUIRED_COHORT"];
  }
  report.models[3].complete_drifters = 3;
  return report;
}

test("the actual large cohort report retains 24 observations, 96 scores and the missing target", () => {
  assert.ok(Buffer.byteLength(payload) > 150_000 && Buffer.byteLength(payload) < 400_000);
  const report = fixture(), before = JSON.stringify(report);
  assert.equal(validateCohortVectorReport(report), report);
  assert.equal(JSON.stringify(report), before);
  assert.deepEqual(report.groups.map(g => g.drifter_id).sort(), ["12730", "12731", "300234063243480", "300234063472530"]);
  assert.equal(report.coverage.unique_observed_intervals, 24);
  assert.equal(report.coverage.scored_model_intervals, 96);
  assert.equal(report.coverage.planned_model_intervals, 144);
  assert.equal(report.coverage.missing_drifters, 2);
  assert.equal(report.status, "PARTIAL_COVERAGE");
});

test("origin, units, target coverage and independent or physical promotion cannot be changed", () => {
  for (const mutate of [
    r => { r.data_origin = "MEASURED_TANK"; },
    r => { r.velocity_units = "cm/s"; },
    r => { r.coverage.acquired_drifters = 6; },
    r => { r.coverage.missing_drifters = 0; },
    r => { r.coverage.unique_observed_intervals = 96; },
    r => { r.coverage.planned_model_intervals = 96; },
    r => { r.coverage.scored_model_intervals = 95; },
    r => { r.status = "COMPLETED"; },
    r => { r.physical_validation = true; },
    r => { r.independent_evaluation = true; },
    r => { r.automatic_model_promotion = true; },
    r => { r.calibrated_probability = true; },
    r => { r.metric_scope = "FULL_SIX_TARGET_GROUPS"; },
  ]) { const report = fixture(); mutate(report); rejected(report); }
});

test("missing or duplicate drifters, models and intervals cannot disappear from coverage", () => {
  for (const mutate of [
    r => { r.groups.pop(); },
    r => { r.groups[1].drifter_id = r.groups[0].drifter_id; },
    r => { r.groups[0].drifter_id = "unacquired-drifter"; },
    r => { r.groups[0].models.pop(); },
    r => { r.groups[0].models[3].id = "last_drift"; },
    r => { r.groups[0].models[3].intervals.pop(); },
    r => { r.models.pop(); },
  ]) { const report = fixture(); mutate(report); rejected(report); }
});

test("common-cohort aggregates are reconstructed from track metrics", () => {
  for (const key of ["vector_rmse_m_s", "speed_bias_predicted_minus_observed_m_s", "angular_mae_deg", "ade_m", "fde_m"]) {
    const report = fixture();
    report.models[3].metrics[key] += 1;
    rejected(report);
  }
  const invalid = fixture(); invalid.models[3].metrics.angular_scored_count--;
  rejected(invalid);
});

test("forged angles cannot pass with consistent per-track and common aggregate means", () => {
  const report = fixture();
  for (const group of report.groups) {
    const model = group.models[3];
    for (const row of model.intervals) if (row.angular_error_deg !== null) row.angular_error_deg = 0;
    model.metrics.angular_mae_deg = 0;
  }
  report.models[3].metrics.angular_mae_deg = 0;
  rejected(report);
});

test("one incomplete track withholds all six intervals and every common aggregate", () => {
  const report = incompleteFixture();
  validateCohortVectorReport(report);
  assert.equal(report.coverage.scored_model_intervals, 90);
  assert.equal(report.coverage.failed_model_intervals, 6);
  assert.ok(report.groups[0].models[3].intervals.every(row => row.status === "FAILED"));
  assert.ok(report.models.every(model => model.metrics === null));
  const hiddenFailure = incompleteFixture(); hiddenFailure.coverage.scored_model_intervals = 95;
  hiddenFailure.coverage.failed_model_intervals = 1;
  rejected(hiddenFailure);
  const promoted = incompleteFixture(); promoted.models[0].metrics = fixture().models[0].metrics;
  rejected(promoted);
  const missingReason = incompleteFixture(); missingReason.models[0].reason_codes = [];
  rejected(missingReason);
});

test("stationary headings and angles remain undefined rather than zero degrees", () => {
  const report = fixture();
  assert.equal(report.models[0].metrics.angular_mae_deg, null);
  assert.equal(report.models[0].metrics.angular_scored_count, 0);
  assert.equal(report.models[0].metrics.angular_withheld_count, 24);
  assert.ok(report.groups.every(group => group.models[0].intervals.every(row => row.predicted_velocity.heading_deg_clockwise_from_north === null)));
  report.groups[0].models[0].intervals[0].predicted_velocity.heading_deg_clockwise_from_north = 0;
  rejected(report);
});

test("large real reports stream within their own 400 kB budget and errors remain errors", async () => {
  const result = await readCohortVectorReport(new Response(payload));
  assert.equal(result.coverage.scored_model_intervals, 96);
  await assert.rejects(readCohortVectorReport(new Response('{"detail":"Pinned cohort unavailable"}', { status: 503 })), /Pinned cohort unavailable/);
  await assert.rejects(readCohortVectorReport(new Response("not JSON", { status: 409 })), /HTTP 409/);
  await assert.rejects(readCohortVectorReport(new Response(null)), /empty/);
});

test("declared and streaming over-budget cohort bodies are rejected and cancelled", async () => {
  await assert.rejects(readCohortVectorReport(new Response("{}", { headers: { "content-length": "400001" } })), /bounded size/);
  let cancelled = false;
  const stream = new ReadableStream({
    start(controller) { controller.enqueue(new Uint8Array(400001)); },
    cancel() { cancelled = true; },
  });
  await assert.rejects(readCohortVectorReport(new Response(stream)), /bounded size/);
  assert.equal(cancelled, true);
});
