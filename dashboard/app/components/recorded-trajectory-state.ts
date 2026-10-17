// A read-only mean-field replay, distinct from conditional vector interpolation.
type Comparison = { t_s: number; predicted_x_cm: number; predicted_y_cm: number; observed_x_cm: number; observed_y_cm: number; position_error_cm: number };
type RunMetrics = { ade_cm: number; fde_cm: number; position_rmse_cm: number };
export type TrajectoryRun = { recording_id: string; recording_content_hash: string; status: "SCORED" | "WITHHELD"; reason_codes: string[]; data_origin: string; physical_validation: false; planned_forecast_points: number; scored_forecast_points: number; integration_steps: number; horizon_s: number; time_origin_s: number; initial_position: { t_s: number; x_cm: number | null; y_cm: number | null }; comparisons: Comparison[]; metrics: RunMetrics | null };
export type RecordedTrajectoryReport = { schema_version: 1; kind: "RECORDED_FIELD_TRAJECTORY_DIAGNOSTIC"; status: "COMPLETED" | "WITHHELD_INCOMPLETE_RUNS"; flow_id: string; flow_content_hash: string; calibration_id: string; camera_session_id: string; data_origin: "SYNTHETIC_CAPTURE_REPLAY" | "RECORDED_TANK_CAPTURE_UNVERIFIED"; bounds: { x_min_cm: number; x_max_cm: number; y_min_cm: number; y_max_cm: number }; provenance: { training_recording_ids: string[]; validation_recording_ids: string[]; frame_splits_disjoint: true }; coverage: { validation_recordings: number; complete_recordings: number; planned_forecast_points: number; scored_forecast_points: number; withheld_forecast_points: number }; integration: { total_steps: number; maximum_total_steps: 20000; maximum_steps_per_run: 2000; maximum_horizon_s: 20; maximum_observation_gap_s: 0.5 }; recordings: TrajectoryRun[]; metrics: { equal_recording_ade_cm: number; equal_recording_fde_cm: number; pooled_position_rmse_cm: number } | null; limitations: string[] };
const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value);
const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const nonnegative = (value: unknown): value is number => finite(value) && value >= 0;
const count = (value: unknown): value is number => nonnegative(value) && Number.isInteger(value) && value <= 20_000;
const id = (value: unknown): value is string => typeof value === "string" && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$/.test(value);
const hash = (value: unknown): value is string => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
const near = (a: number, b: number) => Number.isFinite(a) && Number.isFinite(b) && Math.abs(a - b) <= 1e-7 * Math.max(1, Math.abs(b));
const fail = (): never => { throw new Error("The recorded trajectory report has incompatible evidence, chronology or scores. No result was accepted."); };
function bounded(value: unknown, depth = 0, budget = { nodes: 0 }): boolean {
  if (++budget.nodes > 300_000 || depth > 15) return false;
  if (Array.isArray(value)) return value.length <= 20_000 && value.every(v => bounded(v, depth + 1, budget));
  if (object(value)) return Object.keys(value).length <= 50 && Object.values(value).every(v => bounded(v, depth + 1, budget));
  return value === null || typeof value === "boolean" || finite(value) || typeof value === "string" && value.length <= 8_000;
}
export function validateRecordedTrajectoryReport(value: unknown, expectedFlowId: string): RecordedTrajectoryReport {
  if (!object(value) || !bounded(value) || value.schema_version !== 1 || value.kind !== "RECORDED_FIELD_TRAJECTORY_DIAGNOSTIC" || !["COMPLETED", "WITHHELD_INCOMPLETE_RUNS"].includes(value.status as string)
    || !id(expectedFlowId) || value.flow_id !== expectedFlowId || !hash(value.flow_content_hash) || !id(value.calibration_id) || !id(value.camera_session_id)
    || value.scope !== "ALREADY_REVIEWED_RECORDINGS_DETERMINISTIC_MEAN_FIELD_NOT_INDEPENDENT_TEST"
    || !["SYNTHETIC_CAPTURE_REPLAY", "RECORDED_TANK_CAPTURE_UNVERIFIED"].includes(value.data_origin as string)
    || value.position_units !== "cm" || value.time_units !== "s" || value.timestamp_kind !== "host_receipt_not_exposure"
    || [value.physical_validation, value.capture_independently_verified, value.camera_started, value.hardware_actuation, value.store_written, value.refit_performed, value.model_selection_performed, value.independent_evaluation, value.provider_calls, value.calibrated_probability].some(v => v !== false)
    || !object(value.model) || value.model.kind !== "DETERMINISTIC_FROZEN_MEAN_FIELD" || value.model.maximum_step_s !== 0.05 || value.model.boundary !== "reflecting_rectangle" || value.model.traps !== "NONE" || value.model.diffusivity_cm2_s !== 0 || value.model.initial_observation_only !== true || value.model.observed_position_updates !== false
    || !object(value.integration) || !count(value.integration.total_steps) || value.integration.maximum_total_steps !== 20_000 || value.integration.maximum_steps_per_run !== 2000 || value.integration.maximum_horizon_s !== 20 || value.integration.maximum_observation_gap_s !== 0.5
    || !object(value.bounds) || ![value.bounds.x_min_cm, value.bounds.x_max_cm, value.bounds.y_min_cm, value.bounds.y_max_cm].every(finite)
    || !object(value.provenance) || !object(value.coverage) || !Array.isArray(value.recordings) || !value.recordings.length || value.recordings.length > 100
    || !Array.isArray(value.limitations) || !value.limitations.length || !value.limitations.every(v => typeof v === "string")) return fail();
  const b = value.bounds as RecordedTrajectoryReport["bounds"], p = value.provenance, c = value.coverage;
  if (b.x_min_cm >= b.x_max_cm || b.y_min_cm >= b.y_max_cm || !finite(b.x_max_cm - b.x_min_cm) || !finite(b.y_max_cm - b.y_min_cm)
    || p.frame_splits_disjoint !== true || !Array.isArray(p.training_recording_ids) || !p.training_recording_ids.length || p.training_recording_ids.length > 100 || !p.training_recording_ids.every(id)
    || !Array.isArray(p.validation_recording_ids) || !p.validation_recording_ids.length || !p.validation_recording_ids.every(id)
    || new Set([...p.training_recording_ids, ...p.validation_recording_ids]).size !== p.training_recording_ids.length + p.validation_recording_ids.length || p.validation_recording_ids.length !== value.recordings.length) return fail();
  const inside = (x: number, y: number) => x >= b.x_min_cm - 1e-8 && x <= b.x_max_cm + 1e-8 && y >= b.y_min_cm - 1e-8 && y <= b.y_max_cm + 1e-8;
  let planned = 0, scored = 0, complete = 0, steps = 0, squared = 0, ades = 0, fdes = 0;
  for (const [index, raw] of value.recordings.entries()) {
    if (!object(raw) || raw.recording_id !== p.validation_recording_ids[index] || !hash(raw.recording_content_hash) || raw.data_origin !== value.data_origin || raw.physical_validation !== false
      || !Array.isArray(raw.reason_codes) || !raw.reason_codes.every(v => typeof v === "string" && v.length > 0 && v.length <= 200)
      || !count(raw.planned_forecast_points) || raw.planned_forecast_points < 1 || !count(raw.scored_forecast_points) || !count(raw.integration_steps) || raw.integration_steps > 2000
      || !nonnegative(raw.time_origin_s) || !finite(raw.horizon_s) || raw.horizon_s <= 0 || !object(raw.initial_position) || raw.initial_position.t_s !== raw.time_origin_s
      || ![raw.initial_position.x_cm, raw.initial_position.y_cm].every(v => v === null || finite(v)) || !Array.isArray(raw.comparisons)) return fail();
    planned += raw.planned_forecast_points; scored += raw.scored_forecast_points; steps += raw.integration_steps;
    if (raw.status === "WITHHELD") { if (!raw.reason_codes.length || raw.scored_forecast_points !== 0 || raw.comparisons.length !== 0 || raw.metrics !== null) return fail(); continue; }
    if (raw.status !== "SCORED" || raw.reason_codes.length || raw.horizon_s > 20 || raw.comparisons.length !== raw.planned_forecast_points || raw.scored_forecast_points !== raw.planned_forecast_points
      || !finite(raw.initial_position.x_cm) || !finite(raw.initial_position.y_cm) || !inside(raw.initial_position.x_cm, raw.initial_position.y_cm) || !object(raw.metrics)) return fail();
    let previous = raw.time_origin_s, sum = 0, sumSquared = 0;
    for (const row of raw.comparisons) {
      if (!object(row) || ![row.t_s, row.predicted_x_cm, row.predicted_y_cm, row.observed_x_cm, row.observed_y_cm, row.position_error_cm].every(finite)) return fail();
      const comparison = row as Comparison;
      if (comparison.t_s <= previous || comparison.t_s - previous > 0.5 + 1e-9 || !inside(comparison.observed_x_cm, comparison.observed_y_cm) || !inside(comparison.predicted_x_cm, comparison.predicted_y_cm)
        || !near(comparison.position_error_cm, Math.hypot(comparison.predicted_x_cm - comparison.observed_x_cm, comparison.predicted_y_cm - comparison.observed_y_cm))) return fail();
      previous = comparison.t_s; sum += comparison.position_error_cm; sumSquared += comparison.position_error_cm ** 2;
    }
    const n = raw.comparisons.length, last = raw.comparisons[n - 1] as Comparison;
    if (!near(previous - raw.time_origin_s, raw.horizon_s) || raw.integration_steps < Math.ceil(raw.horizon_s / 0.05 - 1e-8)
      || !nonnegative(raw.metrics.ade_cm) || !nonnegative(raw.metrics.fde_cm) || !nonnegative(raw.metrics.position_rmse_cm)
      || !near(raw.metrics.ade_cm, sum / n) || !near(raw.metrics.fde_cm, last.position_error_cm) || !near(raw.metrics.position_rmse_cm, Math.sqrt(sumSquared / n))) return fail();
    complete++; squared += sumSquared; ades += raw.metrics.ade_cm; fdes += raw.metrics.fde_cm;
  }
  if (planned > 20_000 || steps > 20_000 || value.integration.total_steps !== steps || c.validation_recordings !== value.recordings.length || c.complete_recordings !== complete
    || c.planned_forecast_points !== planned || c.scored_forecast_points !== scored || c.withheld_forecast_points !== planned - scored) return fail();
  if (complete !== value.recordings.length) { if (value.status !== "WITHHELD_INCOMPLETE_RUNS" || value.metrics !== null) return fail(); }
  else if (value.status !== "COMPLETED" || !object(value.metrics) || !nonnegative(value.metrics.equal_recording_ade_cm) || !nonnegative(value.metrics.equal_recording_fde_cm) || !nonnegative(value.metrics.pooled_position_rmse_cm)
    || !near(value.metrics.equal_recording_ade_cm, ades / complete) || !near(value.metrics.equal_recording_fde_cm, fdes / complete) || !near(value.metrics.pooled_position_rmse_cm, Math.sqrt(squared / scored))) return fail();
  return value as RecordedTrajectoryReport;
}
