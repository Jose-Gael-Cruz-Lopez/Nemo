import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { validateRecordedTrajectoryReport } from "../app/components/recorded-trajectory-state.ts";

// Actual offline inspector output from explicitly synthetic contract recordings.
// One full path scores; one unsupported path is wholly withheld, never fabricated.
const frozen = JSON.parse(readFileSync(new URL("./fixtures/recorded-trajectory-report.json", import.meta.url), "utf8"));
const fixture = () => structuredClone(frozen);
const validate = report => validateRecordedTrajectoryReport(report, "flow-test");
const rejected = report => assert.throws(() => validate(report), /No result was accepted/);

function completeFixture() {
  const r = fixture(), run = r.recordings[0];
  r.recordings = [run]; r.provenance.validation_recording_ids = [run.recording_id];
  r.coverage = { validation_recordings: 1, complete_recordings: 1, planned_forecast_points: run.planned_forecast_points, scored_forecast_points: run.scored_forecast_points, withheld_forecast_points: 0 };
  r.integration.total_steps = run.integration_steps; r.status = "COMPLETED";
  r.metrics = { equal_recording_ade_cm: run.metrics.ade_cm, equal_recording_fde_cm: run.metrics.fde_cm, pooled_position_rmse_cm: run.metrics.position_rmse_cm };
  return r;
}

test("actual forward replay retains a whole failed run and all planned points", () => {
  const r = fixture(), before = JSON.stringify(r);
  assert.equal(validate(r), r); assert.equal(JSON.stringify(r), before);
  assert.equal(r.data_origin, "SYNTHETIC_CAPTURE_REPLAY");
  assert.equal(r.coverage.validation_recordings, 2); assert.equal(r.coverage.complete_recordings, 1);
  assert.equal(r.coverage.planned_forecast_points, 10); assert.equal(r.coverage.scored_forecast_points, 5);
  assert.equal(r.coverage.withheld_forecast_points, 5); assert.equal(r.metrics, null);
  assert.equal(r.recordings[1].comparisons.length, 0); assert.equal(r.recordings[1].metrics, null);
  assert.ok(Math.abs(r.recordings[0].metrics.ade_cm - 0.6) < 1e-8);
  assert.ok(Math.abs(r.recordings[0].metrics.fde_cm - 1) < 1e-8);
});

test("complete-run aggregates reconstruct without resetting predicted positions", () => {
  const r = completeFixture(); validate(r);
  const run = r.recordings[0];
  assert.ok(run.comparisons[4].position_error_cm > run.comparisons[0].position_error_cm);
  r.metrics.equal_recording_ade_cm = 0; rejected(r);
});

test("actual nonzero capture offsets are preserved and elapsed time uses their difference", () => {
  const r = completeFixture(), run = r.recordings[0];
  run.time_origin_s += 2; run.initial_position.t_s += 2;
  for (const point of run.comparisons) point.t_s += 2;
  validate(r);
  assert.ok(Math.abs(run.comparisons.at(-1).t_s - run.time_origin_s - run.horizon_s) < 1e-8);
  run.comparisons[1].t_s = run.comparisons[0].t_s; rejected(r);
});

test("flow binding, mean-field assumptions and physical or independent upgrades cannot change", () => {
  for (const mutate of [
    r => { r.flow_id = "other-flow"; },
    r => { r.provenance.validation_recording_ids[0] = "training"; },
    r => { r.model.observed_position_updates = true; },
    r => { r.model.initial_observation_only = false; },
    r => { r.model.maximum_step_s = 1; },
    r => { r.model.diffusivity_cm2_s = 0.05; },
    r => { r.model.traps = "absorbing"; },
    r => { r.physical_validation = true; },
    r => { r.independent_evaluation = true; },
    r => { r.data_origin = "MEASURED_TANK"; },
    r => { r.position_units = "m"; },
  ]) { const r = fixture(); mutate(r); rejected(r); }
});

test("a withheld run cannot gain a partial successful path or disappear from aggregates", () => {
  for (const mutate of [
    r => { r.recordings[1].comparisons = [structuredClone(r.recordings[0].comparisons[0])]; },
    r => { r.recordings[1].scored_forecast_points = 1; },
    r => { r.recordings[1].metrics = r.recordings[0].metrics; },
    r => { r.recordings[1].reason_codes = []; },
    r => { r.coverage.withheld_forecast_points = 0; },
    r => { r.metrics = completeFixture().metrics; },
    r => { r.status = "COMPLETED"; },
  ]) { const r = fixture(); mutate(r); rejected(r); }
});

test("coordinate errors, time gaps, integration counts and overflow cannot forge valid path scores", () => {
  for (const mutate of [
    r => { r.recordings[0].comparisons[0].position_error_cm = 0; },
    r => { r.recordings[0].comparisons[0].predicted_x_cm = 100; },
    r => { r.recordings[0].comparisons[0].observed_x_cm = NaN; },
    r => { r.recordings[0].comparisons[0].t_s = 0.8; },
    r => { r.recordings[0].horizon_s = 0.5; },
    r => { r.recordings[0].integration_steps = 1; },
    r => { r.integration.total_steps++; },
    r => { r.recordings[0].metrics.position_rmse_cm = Infinity; },
    r => { r.bounds.x_max_cm = r.bounds.x_min_cm; },
  ]) { const r = fixture(); mutate(r); rejected(r); }
});
