// Read-only report boundary: reject mixed evidence, units and inconsistent vectors.
type Velocity = { eastward_m_s: number; northward_m_s: number; speed_m_s: number; heading_deg_clockwise_from_north: number | null };
type Interval = { horizon_hours: number; start_utc: string; end_utc: string; interval_seconds: number; observed_velocity: Velocity; predicted_velocity: Velocity; residual_predicted_minus_observed: Velocity; angular_error_deg: number | null; position_error_m: number; status: "SCORED" };
type Model = { id: string; label: string; intervals: Interval[]; metrics: { vector_rmse_m_s: number; speed_bias_predicted_minus_observed_m_s: number; angular_mae_deg: number | null; angular_scored_count: number; angular_withheld_count: number; ade_m: number; fde_m: number } };
type TankVector = { x_cm: number; y_cm: number; observed_vx_cm_s: number; observed_vy_cm_s: number; predicted_vx_cm_s: number; predicted_vy_cm_s: number; residual_vx_cm_s: number; residual_vy_cm_s: number; vector_error_cm_s: number; speed_bias_cm_s: number; absolute_speed_error_cm_s: number; direction_error_deg: number | null; data_origin: "SYNTHETIC_SOFTWARE_REPLAY"; physical_validation: false };
export type MotionVectorReport = {
  schema_version: 1; kind: "MOTION_VECTOR_DIAGNOSTIC"; status: "COMPLETED";
  camera_started: false; hardware_actuation: false; physical_validation: false; provider_calls: false; store_written: false;
  noaa: { schema_version: 1; kind: "NOAA_VECTOR_MOTION_DIAGNOSTIC"; status: "COMPLETED"; data_origin: "REAL_HISTORICAL_NOAA_DRIFTER"; design_status: "POST_HOC_ALREADY_VIEWED_FORECASTS_NOT_INDEPENDENT_TEST"; velocity_units: "m/s"; minimum_heading_speed_m_s: number; models: Model[]; coverage: { physical_drifters: 1; models: 3; intervals_per_model: 6; attempted_model_intervals: 18; scored_model_intervals: 18; failed_model_intervals: 0; unique_observed_intervals: 6 }; provenance: { drifter_id: string; source_url: string; sha256: string }; limitations: string[] };
  synthetic_tank: { schema_version: 1; kind: "SYNTHETIC_VISION_VECTOR_DIAGNOSTIC"; status: "COMPLETED"; data_origin: "SYNTHETIC_SOFTWARE_REPLAY"; physical_validation: false; coordinates: { velocity_units: "cm/s"; position_units: "cm"; frame_count: 8; timestamp_kind: "SYNTHETIC_MONOTONIC_OFFSETS"; direction_min_speed_cm_s: number }; vectors: TankVector[]; metrics: { sample_count: 4; vector_rmse_cm_s: number; mean_speed_bias_cm_s: number; mean_absolute_speed_error_cm_s: number; mean_direction_error_deg: number | null; direction_defined_count: number }; limitations: string[] };
};
export type ArrowRow = { label: string; detail: string; observed: [number, number]; predicted: [number, number]; residual: [number, number]; angle: number | null };
const record = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const positive = (v: unknown): v is number => finite(v) && v >= 0;
const angle = (v: unknown) => v === null || positive(v) && v <= 180;
const near = (a: number, b: number) => Math.abs(a - b) <= 1e-7 * Math.max(1, Math.abs(b));
const circularError = (a: number, b: number) => Math.abs((a - b + 540) % 360 - 180);
const vectorAngle = (a: [number, number], b: [number, number]) => circularError(Math.atan2(a[0], a[1]) * 180 / Math.PI, Math.atan2(b[0], b[1]) * 180 / Math.PI);
const sameAngle = (actual: number, expected: number) => Math.abs(actual - expected) <= 1e-5;
function boundedJson(value: unknown, depth = 0, budget = { nodes: 0 }): boolean {
  if (++budget.nodes > 15_000 || depth > 20) return false;
  if (Array.isArray(value)) return value.length <= 512 && value.every(v => boundedJson(v, depth + 1, budget));
  if (record(value)) return Object.keys(value).length <= 100 && Object.values(value).every(v => boundedJson(v, depth + 1, budget));
  return value === null || typeof value === "boolean" || finite(value) || typeof value === "string" && value.length <= 8_000;
}
export function validateNoaaVectorModels(models: unknown, ids: readonly string[]): Model[] {
  const fail = (): never => { throw new Error("The vector report has incompatible model intervals or metrics. No result was accepted."); };
  if (!Array.isArray(models) || models.length !== ids.length) return fail();
  for (const [index, model] of models.entries()) {
    if (!record(model) || model.id !== ids[index] || typeof model.label !== "string" || !record(model.metrics) || !Array.isArray(model.intervals) || model.intervals.length !== 6) return fail();
    const m = model.metrics; let squared = 0, bias = 0, angular = 0, angularCount = 0, ade = 0;
    for (const [i, row] of model.intervals.entries()) {
      if (!record(row) || row.status !== "SCORED" || row.horizon_hours !== i + 1 || row.interval_seconds !== 3600 || !positive(row.position_error_m)
        || typeof row.start_utc !== "string" || typeof row.end_utc !== "string" || !Number.isFinite(Date.parse(row.end_utc)) || Date.parse(row.end_utc) - Date.parse(row.start_utc) !== 3_600_000
        || !angle(row.angular_error_deg)) return fail();
      const vectors = [row.observed_velocity, row.predicted_velocity, row.residual_predicted_minus_observed];
      for (const v of vectors) {
        if (!record(v) || !finite(v.eastward_m_s) || !finite(v.northward_m_s) || !positive(v.speed_m_s) || !near(v.speed_m_s, Math.hypot(v.eastward_m_s, v.northward_m_s))) return fail();
        const expectedHeading = (Math.atan2(v.eastward_m_s, v.northward_m_s) * 180 / Math.PI + 360) % 360;
        if (v.speed_m_s < 0.005 ? v.heading_deg_clockwise_from_north !== null : !positive(v.heading_deg_clockwise_from_north) || v.heading_deg_clockwise_from_north >= 360 || circularError(v.heading_deg_clockwise_from_north, expectedHeading) > 1e-5) return fail();
      }
      const [o, p, r] = vectors as Velocity[];
      if (!near(r.eastward_m_s, p.eastward_m_s - o.eastward_m_s) || !near(r.northward_m_s, p.northward_m_s - o.northward_m_s)
        || (Math.min(o.speed_m_s, p.speed_m_s) < 0.005) !== (row.angular_error_deg === null)) return fail();
      if (row.angular_error_deg !== null && !sameAngle(row.angular_error_deg as number, vectorAngle([o.eastward_m_s, o.northward_m_s], [p.eastward_m_s, p.northward_m_s]))) return fail();
      squared += r.speed_m_s ** 2; bias += p.speed_m_s - o.speed_m_s; ade += row.position_error_m;
      if (row.angular_error_deg !== null) { angular += row.angular_error_deg as number; angularCount++; }
    }
    if (!positive(m.vector_rmse_m_s) || !finite(m.speed_bias_predicted_minus_observed_m_s) || !positive(m.ade_m) || !positive(m.fde_m) || !angle(m.angular_mae_deg)
      || m.angular_scored_count !== angularCount || m.angular_withheld_count !== 6 - angularCount
      || !near(m.vector_rmse_m_s, Math.sqrt(squared / 6)) || !near(m.speed_bias_predicted_minus_observed_m_s, bias / 6) || !near(m.ade_m, ade / 6)
      || !near(m.fde_m, model.intervals[5].position_error_m) || (angularCount ? !finite(m.angular_mae_deg) || !near(m.angular_mae_deg, angular / angularCount) : m.angular_mae_deg !== null)) return fail();
  }
  return models as Model[];
}
export function validateMotionVectorReport(value: unknown): MotionVectorReport {
  const fail = (): never => { throw new Error("The vector report has incompatible units, origins, counts or metrics. No result was accepted."); };
  if (!record(value) || !boundedJson(value) || value.schema_version !== 1 || value.kind !== "MOTION_VECTOR_DIAGNOSTIC" || value.status !== "COMPLETED"
    || [value.camera_started, value.hardware_actuation, value.physical_validation, value.provider_calls, value.store_written].some(v => v !== false)
    || !record(value.noaa) || !record(value.synthetic_tank)) return fail();
  const n = value.noaa, t = value.synthetic_tank;
  if (n.schema_version !== 1 || n.kind !== "NOAA_VECTOR_MOTION_DIAGNOSTIC" || n.status !== "COMPLETED" || n.data_origin !== "REAL_HISTORICAL_NOAA_DRIFTER"
    || n.design_status !== "POST_HOC_ALREADY_VIEWED_FORECASTS_NOT_INDEPENDENT_TEST" || n.velocity_units !== "m/s" || n.minimum_heading_speed_m_s !== 0.005
    || [n.field_forcing_available, n.debris_survey_context_available, n.independent_evaluation, n.model_selection_performed, n.automatic_model_promotion, n.physical_validation, n.calibrated_probability, n.plastic_source_attribution_supported, n.new_trajectory_acquisition].some(v => v !== false)
    || !record(n.coverage) || !record(n.provenance) || !Array.isArray(n.models) || n.models.length !== 3 || !Array.isArray(n.limitations) || !n.limitations.every(v => typeof v === "string")
    || !Object.entries({ physical_drifters: 1, models: 3, intervals_per_model: 6, attempted_model_intervals: 18, scored_model_intervals: 18, failed_model_intervals: 0, unique_observed_intervals: 6 }).every(([key, expected]) => (n.coverage as Record<string, unknown>)[key] === expected)
    || typeof n.provenance.drifter_id !== "string" || typeof n.provenance.sha256 !== "string" || !/^[a-f0-9]{64}$/.test(n.provenance.sha256)) return fail();
  validateNoaaVectorModels(n.models, ["stationary", "last_drift", "ridge_ar1"]);
  if (t.schema_version !== 1 || t.kind !== "SYNTHETIC_VISION_VECTOR_DIAGNOSTIC" || t.status !== "COMPLETED" || t.data_origin !== "SYNTHETIC_SOFTWARE_REPLAY"
    || [t.physical_validation, t.camera_started, t.hardware_actuation].some(v => v !== false) || !record(t.coordinates) || t.coordinates.velocity_units !== "cm/s" || t.coordinates.position_units !== "cm" || t.coordinates.frame_count !== 8 || t.coordinates.timestamp_kind !== "SYNTHETIC_MONOTONIC_OFFSETS" || t.coordinates.direction_min_speed_cm_s !== 0.01
    || !record(t.model) || t.model.frozen_before_scoring !== true || [t.model.trained, t.model.model_selection_performed, t.model.promotion_performed].some(v => v !== false)
    || !record(t.admission) || t.admission.measured_profile_admitted !== false || t.admission.store_written !== false
    || !Array.isArray(t.vectors) || t.vectors.length !== 4 || !record(t.metrics) || t.metrics.sample_count !== 4 || !Array.isArray(t.limitations) || !t.limitations.every(v => typeof v === "string")) return fail();
  let squared = 0, bias = 0, speedError = 0, angular = 0, angularCount = 0;
  for (const row of t.vectors) {
    if (!record(row) || row.data_origin !== "SYNTHETIC_SOFTWARE_REPLAY" || row.physical_validation !== false || !angle(row.direction_error_deg)
      || ![row.x_cm, row.y_cm, row.observed_vx_cm_s, row.observed_vy_cm_s, row.predicted_vx_cm_s, row.predicted_vy_cm_s, row.residual_vx_cm_s, row.residual_vy_cm_s, row.vector_error_cm_s, row.speed_bias_cm_s, row.absolute_speed_error_cm_s].every(finite)) return fail();
    const v = row as TankVector;
    const observedSpeed = Math.hypot(v.observed_vx_cm_s, v.observed_vy_cm_s), predictedSpeed = Math.hypot(v.predicted_vx_cm_s, v.predicted_vy_cm_s);
    if (!near(v.residual_vx_cm_s, v.predicted_vx_cm_s - v.observed_vx_cm_s) || !near(v.residual_vy_cm_s, v.predicted_vy_cm_s - v.observed_vy_cm_s)
      || !near(v.vector_error_cm_s, Math.hypot(v.residual_vx_cm_s, v.residual_vy_cm_s)) || !near(v.speed_bias_cm_s, predictedSpeed - observedSpeed)
      || !near(v.absolute_speed_error_cm_s, Math.abs(v.speed_bias_cm_s)) || (Math.min(observedSpeed, predictedSpeed) < 0.01) !== (v.direction_error_deg === null)) return fail();
    if (v.direction_error_deg !== null && !sameAngle(v.direction_error_deg, vectorAngle([v.observed_vx_cm_s, v.observed_vy_cm_s], [v.predicted_vx_cm_s, v.predicted_vy_cm_s]))) return fail();
    squared += v.vector_error_cm_s ** 2; bias += v.speed_bias_cm_s; speedError += v.absolute_speed_error_cm_s;
    if (v.direction_error_deg !== null) { angular += v.direction_error_deg; angularCount++; }
  }
  const m = t.metrics;
  if (!positive(m.vector_rmse_cm_s) || !finite(m.mean_speed_bias_cm_s) || !positive(m.mean_absolute_speed_error_cm_s) || !angle(m.mean_direction_error_deg)
    || m.direction_defined_count !== angularCount || !near(m.vector_rmse_cm_s, Math.sqrt(squared / 4)) || !near(m.mean_speed_bias_cm_s, bias / 4) || !near(m.mean_absolute_speed_error_cm_s, speedError / 4)
    || (angularCount ? !finite(m.mean_direction_error_deg) || !near(m.mean_direction_error_deg, angular / angularCount) : m.mean_direction_error_deg !== null)) return fail();
  return value as MotionVectorReport;
}
export async function readVectorResponse<T>(response: Response, validate: (value: unknown) => T, max = 120_000): Promise<T> {
  if (!response.body || Number(response.headers.get("content-length")) > max) throw new Error("The vector report is empty or exceeds its bounded size.");
  const reader = response.body.getReader(), parts: Uint8Array[] = []; let size = 0;
  try { for (;;) { const part = await reader.read(); if (part.done) break; size += part.value.byteLength; if (size > max) { await reader.cancel(); throw new Error("The vector report exceeds its bounded size."); } parts.push(part.value); } } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(size); let offset = 0; for (const part of parts) { bytes.set(part, offset); offset += part.byteLength; }
  let value: unknown; try { value = JSON.parse(new TextDecoder().decode(bytes)); } catch { throw new Error(`Unreadable vector report (HTTP ${response.status}).`); }
  if (!response.ok) throw new Error(record(value) && typeof value.detail === "string" ? value.detail.slice(0, 500) : `Vector diagnostic unavailable (HTTP ${response.status}).`);
  return validate(value);
}

export function readMotionVectorReport(response: Response): Promise<MotionVectorReport> { return readVectorResponse(response, validateMotionVectorReport); }

const COHORT_MODELS = ["stationary", "last_drift", "mean_drift", "ridge_ar1"];
const COHORT_DRIFTERS = ["12730", "12731", "300234063243480", "300234063472530"];
function cohortUtc(value: unknown): number | null {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(value)) return null;
  const milliseconds = Date.parse(value);
  // Date.parse normalizes impossible dates such as February 30; don't display
  // those as a different observation date or accept a timezone reinterpretation.
  return Number.isFinite(milliseconds) && new Date(milliseconds).toISOString().replace(".000Z", "Z") === value ? milliseconds : null;
}
type FailedTrack = { id: string; label: string; status: "WITHHELD"; metrics: null; reason_codes: string[]; intervals: { horizon_hours: number; end_utc: string; status: "FAILED"; reason_codes: string[] }[] };
type CohortTrack = Model & { status: "SCORED"; reason_codes: string[] } | FailedTrack;
export type CohortVectorReport = {
  schema_version: 1; kind: "NOAA_COHORT_VECTOR_MOTION_DIAGNOSTIC"; status: "PARTIAL_COVERAGE";
  data_origin: "REAL_HISTORICAL_NOAA_DRIFTERS"; velocity_units: "m/s";
  coverage: { target_drifters: 6; acquired_drifters: 4; missing_drifters: 2; models: 4; model_tracks: 16; intervals_per_track: 6; planned_model_intervals: 144; attempted_model_intervals: 96; scored_model_intervals: number; failed_model_intervals: number; unique_observed_intervals: 24; common_acquired_cohort_complete: boolean };
  groups: { drifter_id: string; block_id: string; start_utc: string; end_utc: string; models: CohortTrack[] }[];
  models: { id: string; label: string; complete_drifters: number; attempted_drifters: 4; metrics: Model["metrics"] | null; reason_codes: string[] }[];
  limitations: string[]; selection_failures: unknown[];
};
export function validateCohortVectorReport(value: unknown): CohortVectorReport {
  const fail = (): never => { throw new Error("The real-cohort vector report has incompatible evidence, coverage or scores. No result was accepted."); };
  if (!record(value) || !boundedJson(value) || value.schema_version !== 1 || value.kind !== "NOAA_COHORT_VECTOR_MOTION_DIAGNOSTIC" || value.status !== "PARTIAL_COVERAGE" || value.data_origin !== "REAL_HISTORICAL_NOAA_DRIFTERS" || value.velocity_units !== "m/s"
    || value.design_status !== "POST_HOC_ALREADY_VIEWED_COHORT_NOT_INDEPENDENT_TEST" || value.metric_scope !== "ACQUIRED_FOUR_DRIFTERS_NOT_SIX_TARGET_GROUPS" || value.minimum_heading_speed_m_s !== 0.005
    || [value.field_forcing_available, value.debris_survey_context_available, value.independent_evaluation, value.model_selection_performed, value.automatic_model_promotion, value.physical_validation, value.calibrated_probability, value.plastic_source_attribution_supported, value.new_trajectory_acquisition, value.physical_alias_resolution_verified].some(v => v !== false)
    || !record(value.coverage) || !Array.isArray(value.groups) || value.groups.length !== 4 || !Array.isArray(value.models) || value.models.length !== 4 || !Array.isArray(value.limitations) || !value.limitations.every(v => typeof v === "string") || !Array.isArray(value.selection_failures) || !value.selection_failures.length) return fail();
  const c = value.coverage;
  if (!Object.entries({ target_drifters: 6, acquired_drifters: 4, missing_drifters: 2, models: 4, model_tracks: 16, intervals_per_track: 6, planned_model_intervals: 144, attempted_model_intervals: 96, unique_observed_intervals: 24 }).every(([key, expected]) => c[key] === expected)) return fail();
  let scored = 0;
  const ids = new Set<string>();
  for (const group of value.groups) {
    if (!record(group) || typeof group.drifter_id !== "string" || !COHORT_DRIFTERS.includes(group.drifter_id) || ids.has(group.drifter_id) || typeof group.block_id !== "string" || !/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$/.test(group.block_id) || !Array.isArray(group.models) || group.models.length !== 4) return fail();
    const start = cohortUtc(group.start_utc), end = cohortUtc(group.end_utc);
    if (start === null || end === null || end - start !== 23 * 3_600_000) return fail();
    ids.add(group.drifter_id);
    for (const [i, track] of group.models.entries()) {
      if (!record(track) || track.id !== COHORT_MODELS[i] || typeof track.label !== "string" || !Array.isArray(track.reason_codes)) return fail();
      if (track.status === "SCORED") { validateNoaaVectorModels([track], [COHORT_MODELS[i]]); scored += 6; }
      else if (track.status !== "WITHHELD" || track.metrics !== null || !track.reason_codes.length || !Array.isArray(track.intervals) || track.intervals.length !== 6 || !track.intervals.every((row, j) => record(row) && row.status === "FAILED" && row.horizon_hours === j + 1 && Array.isArray(row.reason_codes) && row.reason_codes.length > 0)) return fail();
      // Every score (including a withheld outcome) belongs to this group's
      // declared six held-out hours after its 18-position training prefix.
      for (const [j, row] of (track.intervals as Record<string, unknown>[]).entries()) {
        if (cohortUtc(row.end_utc) !== start + (18 + j) * 3_600_000
          || track.status === "SCORED" && cohortUtc(row.start_utc) !== start + (17 + j) * 3_600_000) return fail();
      }
    }
  }
  if (c.scored_model_intervals !== scored || c.failed_model_intervals !== 96 - scored || c.common_acquired_cohort_complete !== (scored === 96)) return fail();
  const report = value as CohortVectorReport;
  for (const [index, aggregate] of report.models.entries()) {
    if (aggregate.id !== COHORT_MODELS[index] || typeof aggregate.label !== "string" || aggregate.attempted_drifters !== 4 || !Array.isArray(aggregate.reason_codes)) return fail();
    const tracks = report.groups.map(g => g.models[index]).filter((m): m is Model & { status: "SCORED"; reason_codes: string[] } => m.status === "SCORED");
    if (aggregate.complete_drifters !== tracks.length) return fail();
    if (scored !== 96) { if (aggregate.metrics !== null || !aggregate.reason_codes.length) return fail(); continue; }
    const m = aggregate.metrics;
    if (!m || ![m.vector_rmse_m_s, m.ade_m, m.fde_m].every(positive) || !finite(m.speed_bias_predicted_minus_observed_m_s) || !angle(m.angular_mae_deg)) return fail();
    const angles = tracks.flatMap(t => t.intervals.map(r => r.angular_error_deg).filter((v): v is number => v !== null));
    if (!near(m.vector_rmse_m_s, Math.sqrt(tracks.reduce((sum, t) => sum + t.metrics.vector_rmse_m_s ** 2, 0) / 4)) || !near(m.ade_m, tracks.reduce((sum, t) => sum + t.metrics.ade_m, 0) / 4) || !near(m.fde_m, tracks.reduce((sum, t) => sum + t.metrics.fde_m, 0) / 4) || !near(m.speed_bias_predicted_minus_observed_m_s, tracks.reduce((sum, t) => sum + t.metrics.speed_bias_predicted_minus_observed_m_s, 0) / 4)
      || m.angular_scored_count !== angles.length || m.angular_withheld_count !== 24 - angles.length || (angles.length ? !finite(m.angular_mae_deg) || !near(m.angular_mae_deg, angles.reduce((a, b) => a + b, 0) / angles.length) : m.angular_mae_deg !== null)) return fail();
  }
  return report;
}
export function readCohortVectorReport(response: Response): Promise<CohortVectorReport> { return readVectorResponse(response, validateCohortVectorReport, 400_000); }
