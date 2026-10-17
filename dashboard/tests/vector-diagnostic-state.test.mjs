import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { readMotionVectorReport, validateMotionVectorReport } from "../app/components/vector-diagnostic-state.ts";

// Generated offline from run_noaa_vector_diagnostic() plus
// run_synthetic_vector_diagnostic(), with the API's unmodified outer wrapper.
// NOAA is an already-viewed historical buoy; the OpenCV frames are synthetic.
// This public fixture contains no credentials or physical tank measurements.
const frozen = JSON.parse(readFileSync(new URL("./fixtures/motion-vector-report.json", import.meta.url), "utf8"));
const fixture = () => structuredClone(frozen);
const rejected = report => assert.throws(() => validateMotionVectorReport(report), /No result was accepted/);

test("the actual offline NOAA and OpenCV report is accepted without mutating evidence", () => {
  const report = fixture(), before = JSON.stringify(report);
  assert.equal(validateMotionVectorReport(report), report);
  assert.equal(JSON.stringify(report), before);
  assert.equal(report.noaa.provenance.drifter_id, "8707978");
  assert.equal(report.noaa.coverage.unique_observed_intervals, 6);
  assert.equal(report.noaa.coverage.scored_model_intervals, 18);
  assert.equal(report.synthetic_tank.metrics.sample_count, 4);
  assert.equal(report.synthetic_tank.data_origin, "SYNTHETIC_SOFTWARE_REPLAY");
  assert.equal(report.noaa.independent_evaluation, false);
});

test("unit substitution, origin laundering and physical or provider claims are rejected", () => {
  for (const mutate of [
    r => { r.noaa.velocity_units = "cm/s"; },
    r => { r.synthetic_tank.coordinates.velocity_units = "m/s"; },
    r => { r.synthetic_tank.coordinates.position_units = "m"; },
    r => { r.noaa.data_origin = "MEASURED_TANK"; },
    r => { r.synthetic_tank.data_origin = "MEASURED_TANK"; },
    r => { r.physical_validation = true; },
    r => { r.noaa.physical_validation = true; },
    r => { r.synthetic_tank.physical_validation = true; },
    r => { r.synthetic_tank.vectors[0].physical_validation = true; },
    r => { r.synthetic_tank.admission.measured_profile_admitted = true; },
    r => { r.provider_calls = true; },
    r => { r.noaa.field_forcing_available = true; },
  ]) { const report = fixture(); mutate(report); rejected(report); }
});

test("forged NOAA zero-angle rows cannot pass by updating their aggregate consistently", () => {
  const report = fixture(), model = report.noaa.models.find(m => m.id === "ridge_ar1");
  assert.ok(model.intervals.some(row => row.angular_error_deg > 1));
  for (const row of model.intervals) row.angular_error_deg = 0;
  model.metrics.angular_mae_deg = 0;
  // Counts and mean agree; only reconstruction from the vectors catches this.
  assert.equal(model.metrics.angular_scored_count, 6);
  rejected(report);
});

test("opposite tank vectors cannot claim zero direction error with matching aggregates", () => {
  const report = fixture(), tank = report.synthetic_tank;
  for (const row of tank.vectors) {
    row.predicted_vx_cm_s = -4; row.predicted_vy_cm_s = 0;
    row.residual_vx_cm_s = row.predicted_vx_cm_s - row.observed_vx_cm_s;
    row.residual_vy_cm_s = row.predicted_vy_cm_s - row.observed_vy_cm_s;
    row.vector_error_cm_s = Math.hypot(row.residual_vx_cm_s, row.residual_vy_cm_s);
    row.speed_bias_cm_s = 4 - Math.hypot(row.observed_vx_cm_s, row.observed_vy_cm_s);
    row.absolute_speed_error_cm_s = Math.abs(row.speed_bias_cm_s);
    row.direction_error_deg = 0;
  }
  tank.metrics.vector_rmse_cm_s = Math.sqrt(tank.vectors.reduce((sum, r) => sum + r.vector_error_cm_s ** 2, 0) / 4);
  tank.metrics.mean_speed_bias_cm_s = tank.vectors.reduce((sum, r) => sum + r.speed_bias_cm_s, 0) / 4;
  tank.metrics.mean_absolute_speed_error_cm_s = tank.vectors.reduce((sum, r) => sum + r.absolute_speed_error_cm_s, 0) / 4;
  tank.metrics.mean_direction_error_deg = 0;
  rejected(report);
  // The same complete numerical report is accepted once its true angle is used.
  for (const row of tank.vectors) row.direction_error_deg = 180;
  tank.metrics.mean_direction_error_deg = 180;
  validateMotionVectorReport(report);
});

test("headings must follow clockwise-from-north components and remain bounded", () => {
  for (const heading of ["north", -1, 360, null, Number.NaN]) {
    const report = fixture();
    report.noaa.models[2].intervals[0].predicted_velocity.heading_deg_clockwise_from_north = heading;
    rejected(report);
  }
  const wrongDirection = fixture(), vector = wrongDirection.noaa.models[2].intervals[0].predicted_velocity;
  vector.heading_deg_clockwise_from_north = (vector.heading_deg_clockwise_from_north + 90) % 360;
  rejected(wrongDirection);
});

test("stationary motion retains null headings and undefined angular metrics", () => {
  const report = fixture(), stationary = report.noaa.models[0];
  assert.ok(stationary.intervals.every(r => r.predicted_velocity.heading_deg_clockwise_from_north === null && r.angular_error_deg === null));
  assert.equal(stationary.metrics.angular_mae_deg, null);
  assert.equal(stationary.metrics.angular_scored_count, 0);
  assert.equal(stationary.metrics.angular_withheld_count, 6);
  validateMotionVectorReport(report);
  stationary.intervals[0].predicted_velocity.heading_deg_clockwise_from_north = 0;
  rejected(report);
});

test("missing intervals, count drift and nonfinite components cannot reach the display", () => {
  for (const mutate of [
    r => { r.noaa.models[0].intervals.pop(); },
    r => { r.noaa.coverage.unique_observed_intervals = 18; },
    r => { r.noaa.models[0].intervals[1].horizon_hours = 1; },
    r => { r.noaa.models[0].intervals[0].observed_velocity.eastward_m_s = Infinity; },
    r => { r.synthetic_tank.vectors[0].observed_vx_cm_s = Number.NaN; },
    r => { r.synthetic_tank.vectors.pop(); },
  ]) { const report = fixture(); mutate(report); rejected(report); }
});

test("the residual is predicted minus observed, not an equally sized reversed vector", () => {
  const report = fixture(), residual = report.noaa.models[0].intervals[0].residual_predicted_minus_observed;
  residual.eastward_m_s *= -1; residual.northward_m_s *= -1;
  residual.heading_deg_clockwise_from_north = (residual.heading_deg_clockwise_from_north + 180) % 360;
  // Magnitude, headings, RMSE and every aggregate remain internally unchanged.
  // The component-level sign convention must still reject this report.
  rejected(report);
});

test("the response reader accepts the real report and keeps HTTP failures as failures", async () => {
  const result = await readMotionVectorReport(new Response(JSON.stringify(fixture())));
  assert.equal(result.kind, "MOTION_VECTOR_DIAGNOSTIC");
  await assert.rejects(readMotionVectorReport(new Response('{"detail":"Pinned vector source unavailable"}', { status: 503 })), /Pinned vector source unavailable/);
  await assert.rejects(readMotionVectorReport(new Response("not JSON", { status: 409 })), /Unreadable.*HTTP 409/);
  await assert.rejects(readMotionVectorReport(new Response(null)), /empty/);
});

test("oversized response bodies are rejected and a streaming producer is cancelled", async () => {
  await assert.rejects(readMotionVectorReport(new Response("{}", { headers: { "content-length": "120001" } })), /bounded size/);
  let cancelled = false;
  const stream = new ReadableStream({
    start(controller) { controller.enqueue(new Uint8Array(120001)); },
    cancel() { cancelled = true; },
  });
  await assert.rejects(readMotionVectorReport(new Response(stream)), /bounded size/);
  assert.equal(cancelled, true);
});
