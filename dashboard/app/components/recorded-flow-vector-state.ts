// Stored evidence boundary; no browser API, provider or runtime dependency.
type Metrics = { sample_count: number; vector_rmse_cm_s: number | null; mean_speed_bias_cm_s: number | null; mean_absolute_speed_error_cm_s: number | null; mean_direction_error_deg: number | null; direction_defined_count: number };
export type RecordedVector = { sample_index: number; supported: boolean; x_cm: number; y_cm: number; observed_vx_cm_s: number; observed_vy_cm_s: number; predicted_vx_cm_s: number | null; predicted_vy_cm_s: number | null; residual_vx_cm_s: number | null; residual_vy_cm_s: number | null; vector_error_cm_s: number | null; speed_bias_cm_s: number | null; absolute_speed_error_cm_s: number | null; direction_error_deg: number | null; data_origin: string; physical_validation: false };
type Counts = { point_count: number; frame_count: number; observed_point_count: number; missing_point_count: number; ambiguous_point_count: number; no_detection_point_count: number; association_gap_count: number; track_count: number; extracted_sample_count: number; supported_sample_count: number; unsupported_sample_count: number };
export type RecordedFlowReport = { schema_version: 1; kind: "RECORDED_FIELD_VECTOR_DIAGNOSTIC"; status: "COMPLETED"; flow_id: string; flow_content_hash: string; calibration_id: string; camera_session_id: string; data_origin: "SYNTHETIC_CAPTURE_REPLAY" | "RECORDED_TANK_CAPTURE_UNVERIFIED"; capture_origin: "SYNTHETIC_CAPTURE_REPLAY" | "UNVERIFIED_STORED_CAPTURE"; physical_validation: false; position_units: "cm"; velocity_units: "cm/s"; provenance: { training_recording_ids: string[]; validation_recording_ids: string[]; frame_splits_disjoint: true }; coverage: { training_recording_count: number; validation_recording_count: number; training_sample_count: number; validation_sample_count: number; supported_sample_count: number; unsupported_sample_count: number; supported_fraction: number }; metrics: Metrics & { equal_recording_mean_rmse_cm_s: number | null; recordings_with_supported_samples: number }; recordings: { recording_id: string; recording_content_hash: string; data_origin: string; physical_validation: false; counts: Counts; metrics: Metrics; vectors: RecordedVector[] }[]; limitations: string[] };
const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value);
const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const count = (value: unknown): value is number => finite(value) && Number.isInteger(value) && value >= 0 && value <= 20_000;
const id = (value: unknown): value is string => typeof value === "string" && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$/.test(value);
const hash = (value: unknown): value is string => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
const near = (a: number, b: number) => Math.abs(a - b) <= 1e-7 * Math.max(1, Math.abs(b));
const fail = (): never => { throw new Error("The recorded-flow report has incompatible bindings, origins, support or scores. No result was accepted."); };
function bounded(value: unknown, depth = 0, budget = { nodes: 0 }): boolean {
  if (++budget.nodes > 400_000 || depth > 15) return false;
  if (Array.isArray(value)) return value.length <= 20_000 && value.every(v => bounded(v, depth + 1, budget));
  if (object(value)) return Object.keys(value).length <= 50 && Object.values(value).every(v => bounded(v, depth + 1, budget));
  return value === null || typeof value === "boolean" || finite(value) || typeof value === "string" && value.length <= 8_000;
}
function metricsMatch(value: unknown, vectors: RecordedVector[]): value is Metrics {
  if (!object(value)) return false;
  const eligible = vectors.filter(v => v.supported), n = eligible.length;
  const directional = eligible.filter(v => v.direction_error_deg !== null), k = directional.length;
  if (value.sample_count !== n || value.direction_defined_count !== k) return false;
  const expected: Record<string, number | null> = {
    vector_rmse_cm_s: n ? Math.sqrt(eligible.reduce((s, v) => s + v.vector_error_cm_s! ** 2, 0) / n) : null,
    mean_speed_bias_cm_s: n ? eligible.reduce((s, v) => s + v.speed_bias_cm_s!, 0) / n : null,
    mean_absolute_speed_error_cm_s: n ? eligible.reduce((s, v) => s + v.absolute_speed_error_cm_s!, 0) / n : null,
    mean_direction_error_deg: k ? directional.reduce((s, v) => s + v.direction_error_deg!, 0) / k : null,
  };
  return Object.entries(expected).every(([key, expectedValue]) => expectedValue === null ? value[key] === null : finite(value[key]) && near(value[key], expectedValue));
}
export function validateRecordedFlowReport(value: unknown, expectedFlowId: string): RecordedFlowReport {
  if (!object(value) || !bounded(value) || value.schema_version !== 1 || value.kind !== "RECORDED_FIELD_VECTOR_DIAGNOSTIC" || value.status !== "COMPLETED"
    || !id(expectedFlowId) || value.flow_id !== expectedFlowId || !hash(value.flow_content_hash) || !id(value.calibration_id) || !id(value.camera_session_id)
    || value.scope !== "CONDITIONAL_HELDOUT_FIELD_INTERPOLATION_ALREADY_REVIEWED_NOT_INDEPENDENT_TEST"
    || !["SYNTHETIC_CAPTURE_REPLAY", "RECORDED_TANK_CAPTURE_UNVERIFIED"].includes(value.data_origin as string)
    || value.capture_origin !== (value.data_origin === "SYNTHETIC_CAPTURE_REPLAY" ? "SYNTHETIC_CAPTURE_REPLAY" : "UNVERIFIED_STORED_CAPTURE")
    || value.recorded_data_origin !== "MEASURED_TANK" || value.position_units !== "cm" || value.velocity_units !== "cm/s" || value.timestamp_kind !== "host_receipt_not_exposure"
    || [value.physical_validation, value.capture_independently_verified, value.camera_started, value.hardware_actuation, value.provider_calls, value.store_written, value.refit_performed, value.model_selection_performed].some(v => v !== false)
    || !object(value.provenance) || !object(value.coverage) || !object(value.metrics) || !Array.isArray(value.recordings) || !value.recordings.length || value.recordings.length > 100
    || !Array.isArray(value.limitations) || !value.limitations.length || !value.limitations.every(v => typeof v === "string")) return fail();
  const p = value.provenance, c = value.coverage;
  if (p.frame_splits_disjoint !== true || !Array.isArray(p.training_recording_ids) || !p.training_recording_ids.length || p.training_recording_ids.length > 100 || !p.training_recording_ids.every(id)
    || !Array.isArray(p.validation_recording_ids) || !p.validation_recording_ids.length || !p.validation_recording_ids.every(id)
    || new Set([...p.training_recording_ids, ...p.validation_recording_ids]).size !== p.training_recording_ids.length + p.validation_recording_ids.length
    || c.training_recording_count !== p.training_recording_ids.length || c.validation_recording_count !== p.validation_recording_ids.length || value.recordings.length !== p.validation_recording_ids.length
    || !count(c.training_sample_count) || c.training_sample_count < 1 || !count(c.validation_sample_count) || c.validation_sample_count < 1 || c.training_sample_count + c.validation_sample_count > 10_000) return fail();
  const allVectors: RecordedVector[] = [], runErrors: number[] = [];
  let total = 0, supported = 0;
  for (const [index, candidate] of value.recordings.entries()) {
    if (!object(candidate) || candidate.recording_id !== p.validation_recording_ids[index] || !hash(candidate.recording_content_hash) || candidate.data_origin !== value.data_origin || candidate.physical_validation !== false || !object(candidate.counts) || !Array.isArray(candidate.vectors)) return fail();
    const d = candidate.counts;
    for (const key of ["point_count", "frame_count", "observed_point_count", "missing_point_count", "ambiguous_point_count", "no_detection_point_count", "association_gap_count", "track_count", "extracted_sample_count", "supported_sample_count", "unsupported_sample_count"]) if (!count(d[key])) return fail();
    const counts = d as Counts;
    if (counts.point_count < 1 || counts.frame_count !== counts.point_count || counts.observed_point_count + counts.missing_point_count !== counts.point_count || counts.track_count > counts.observed_point_count
      || counts.ambiguous_point_count + counts.no_detection_point_count > counts.missing_point_count || counts.association_gap_count > counts.observed_point_count
      || candidate.vectors.length !== counts.extracted_sample_count || counts.supported_sample_count + counts.unsupported_sample_count !== counts.extracted_sample_count || counts.extracted_sample_count * 2 > counts.observed_point_count) return fail();
    let supportedRun = 0;
    for (const [i, raw] of candidate.vectors.entries()) {
      if (!object(raw) || raw.sample_index !== i || typeof raw.supported !== "boolean" || raw.data_origin !== value.data_origin || raw.physical_validation !== false
        || ![raw.x_cm, raw.y_cm, raw.observed_vx_cm_s, raw.observed_vy_cm_s].every(finite)) return fail();
      const v = raw as RecordedVector;
      const fields = [v.predicted_vx_cm_s, v.predicted_vy_cm_s, v.residual_vx_cm_s, v.residual_vy_cm_s, v.vector_error_cm_s, v.speed_bias_cm_s, v.absolute_speed_error_cm_s];
      if (!v.supported) { if (fields.some(v => v !== null) || v.direction_error_deg !== null) return fail(); continue; }
      if (!fields.every(finite)) return fail();
      const observedSpeed = Math.hypot(v.observed_vx_cm_s, v.observed_vy_cm_s), predictedSpeed = Math.hypot(v.predicted_vx_cm_s!, v.predicted_vy_cm_s!);
      if (!near(v.residual_vx_cm_s!, v.predicted_vx_cm_s! - v.observed_vx_cm_s) || !near(v.residual_vy_cm_s!, v.predicted_vy_cm_s! - v.observed_vy_cm_s)
        || !near(v.vector_error_cm_s!, Math.hypot(v.residual_vx_cm_s!, v.residual_vy_cm_s!)) || !near(v.speed_bias_cm_s!, predictedSpeed - observedSpeed)
        || !near(v.absolute_speed_error_cm_s!, Math.abs(v.speed_bias_cm_s!))) return fail();
      if (Math.min(observedSpeed, predictedSpeed) < 0.01) { if (v.direction_error_deg !== null) return fail(); }
      else { const expectedAngle = Math.acos(Math.max(-1, Math.min(1, (v.observed_vx_cm_s * v.predicted_vx_cm_s! + v.observed_vy_cm_s * v.predicted_vy_cm_s!) / (observedSpeed * predictedSpeed)))) * 180 / Math.PI; if (!finite(v.direction_error_deg) || Math.abs(v.direction_error_deg - expectedAngle) > 1e-5) return fail(); }
      supportedRun++;
    }
    const vectors = candidate.vectors as RecordedVector[];
    if (supportedRun !== counts.supported_sample_count || !metricsMatch(candidate.metrics, vectors)) return fail();
    allVectors.push(...vectors); total += vectors.length; supported += supportedRun;
    if (candidate.metrics.vector_rmse_cm_s !== null) runErrors.push(candidate.metrics.vector_rmse_cm_s);
  }
  const aggregate = value.metrics;
  if (total !== c.validation_sample_count || supported !== c.supported_sample_count || total - supported !== c.unsupported_sample_count || !finite(c.supported_fraction) || !near(c.supported_fraction, supported / total)
    || !metricsMatch(value.metrics, allVectors) || aggregate.recordings_with_supported_samples !== runErrors.length) return fail();
  const equal = aggregate.equal_recording_mean_rmse_cm_s;
  if (runErrors.length ? !finite(equal) || !near(equal, runErrors.reduce((s, v) => s + v, 0) / runErrors.length) : equal !== null) return fail();
  return value as RecordedFlowReport;
}
