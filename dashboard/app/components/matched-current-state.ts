/** Public frozen-artifact view. No scoring, fitting, acquisition or physics runs here. */
export const MATCHED_GROUPS = ["300234066836710", "300534061292930"] as const;
export const MATCHED_MODELS = ["stationary", "last_drift", "current_only"] as const;
export const MATCHED_ORIGIN = "2022-06-01T00:00:00Z";
export const MATCHED_STUDY = "matched-current-gdp-hycom-15m-v1";
export const MATCHED_STUDIES = { v1: MATCHED_STUDY, v2: "matched-current-gdp-hycom-15m-v2" } as const;
export type MatchedStudyVersion = keyof typeof MATCHED_STUDIES;
export function matchedStudyVersion(studyId: string): MatchedStudyVersion {
  if (studyId === MATCHED_STUDIES.v1) return "v1";
  if (studyId === MATCHED_STUDIES.v2) return "v2";
  throw new Error("Unknown matched-current study. No result was accepted.");
}
export type MatchedModelId = typeof MATCHED_MODELS[number];
export type GeoPoint = { time_utc: string; latitude_deg: number; longitude_deg: number };
export type MatchedForecastCell = { horizon_hours: number; elapsed_s: number; time_utc: string; forecast_status: "AVAILABLE" | "UNAVAILABLE"; forecast_reason_code: string | null; latitude_deg: number | null; longitude_deg: number | null };
export type MatchedCell = MatchedForecastCell & { group_id: string; model_id: MatchedModelId; target_status: "AVAILABLE" | "UNAVAILABLE"; target_reason_code: string | null; target_latitude_deg: number | null; target_longitude_deg: number | null; error_m: number | null; score_status: "SCORED" | "FORECAST_UNAVAILABLE" | "TARGET_UNAVAILABLE" };
export type MatchedMetrics = { planned_count: number; scored_count: number; missing_count: number; coverage_complete: boolean; available_cell_mean_error_m: number | null; full_horizon_ade_m: number | null; available_cell_summary_is_full_horizon_ade: boolean };
export type MatchedGroupMetrics = MatchedMetrics & { endpoint_fde_m: number | null; endpoint_scored: boolean; scored_prefix_count: number; scored_prefix_hours: number[]; scored_prefix_mean_error_m: number | null; prefix_is_full_horizon: boolean };
export type MatchedCandidate = { model_id: MatchedModelId; prediction_status: string; prediction_reason_code: string | null; cells: MatchedCell[]; metrics: MatchedGroupMetrics };
export type MatchedGroup = { group_id: string; target_issues: Record<string, unknown>[]; candidates: MatchedCandidate[] };
export type MatchedPair = { model_a: MatchedModelId; model_b: MatchedModelId; planned_common_cell_count: 12; common_scored_count: number; coverage_complete: boolean; analysis_scope: string; mean_error_a_m: number | null; mean_error_b_m: number | null; mean_delta_a_minus_b_m: number | null; cells: { group_id: string; time_utc: string; horizon_hours: number; error_a_m: number; error_b_m: number }[] };
export type MatchedScores = {
  schema_version: 1; kind: "MATCHED_CURRENT_SCORES"; origin_time_utc: string; planned_group_count: 2; planned_cell_count: 36; scored_cell_count: number; planned_distinct_target_count: 12;
  forecast_report: { schema_version: 1; kind: "MATCHED_CURRENT_FORECASTS"; origin_time_utc: string; group_ids: string[]; model_ids: MatchedModelId[]; horizons_s: number[]; planned_group_count: 2; planned_cell_count: 36; planned_distinct_target_count: 12; forecast_sha256: string; statistical_independence: false; operational_forecast_skill_verified: false; physical_validation: false; coordinate_method: "origin_anchored_mean_sphere_log_exp_50km_last_drift"; score_method: "mean_radius_sphere_great_circle_metres"; all_forecasts_built_before_target_decode: true; future_positions_used: false; groups: { group_id: string; context_count: number; origin_position: GeoPoint | null; candidates: { model_id: MatchedModelId; status: string; reason_code: string | null; requested_horizon_s: 21600; completed_horizon_s: number; planned_count: 6; available_count: number; context_rows_used: number; learned_parameters: 0; future_positions_used: false; cells: MatchedForecastCell[] }[] }[] };
  groups: MatchedGroup[]; models: { model_id: MatchedModelId; metrics: MatchedMetrics; per_horizon: { horizon_hours: number; planned_group_count: 2; scored_group_count: number; coverage_complete: boolean; available_group_mean_error_m: number | null; complete_group_mean_error_m: number | null }[] }[];
  paired_comparisons: MatchedPair[]; primary_common_cohort_complete: boolean; primary_equal_id_macro_results: { model_id: MatchedModelId; group_count: 2; equal_id_macro_ade_m: number; equal_id_macro_fde_m: number; per_horizon_mean_error_m: { horizon_hours: number; error_m: number }[] }[] | null; primary_paired_comparisons: MatchedPair[] | null;
  statistical_independence: false; automatic_winner_selected: false; operational_forecast_skill_verified: false; physical_validation: false; limitations: string[];
};
export type MatchedReport = { schema_version: 1; kind: "MATCHED_CURRENT_RETROSPECTIVE_DIAGNOSTIC"; study_id: string; lineage: Record<string, string>; forecast_file_sha256: string; forecast_frozen_at_utc: string; scored_at_utc: string; forecasts_saved_before_target_coordinate_decode: true; source_receipts: Record<string, unknown>[]; context_qc: Record<string, unknown>; current_field: Record<string, unknown> | null; current_field_failure: string | null; scores: MatchedScores; physical_validation: false; operational_causality: false; assimilation_independence_verified: false; physical_alias_resolution_verified: false; statistical_independence: false; global_training: false; heldout_tuning: false; automatic_model_promotion: false; provider_calls: false; camera_started: false; store_written: false };
export type MatchedArtifactIdentity = { schema_version: 1; study_id: string; report_sha256: string; forecast_file_sha256: string; forecast_sha256: string; protocol_sha256: string; trusted_protocol_identity_sha256: string; manifest_sha256: string; acquisition_start_sha256: string; integrity_verified: true; numeric_replay_verified: false; verification_scope: "FROZEN_ARTIFACT_LINEAGE_AND_STRUCTURE_NOT_NUMERIC_REPLAY"; result_pin_verified: true; pin_source: "TRUSTED_RESULT_IDENTITY"; result_identity_file_sha256: string };
export type MatchedEnvelope = { report: MatchedReport; artifact_identity: MatchedArtifactIdentity };
export type MatchedAnswer = { schema_version: 1; kind: "MATCHED_CURRENT_RESEARCH_INVESTIGATION"; scope: "READ_ONLY_MATCHED_CURRENT_STUDY"; action: "REPORT" | "STOP"; explanation: string; evidence_ids: string[]; live_model_response: boolean; provider: "chalk"; report_sha256: string; protocol_sha256: string; research_report: MatchedReport; artifact_identity: MatchedArtifactIdentity; trace: unknown[]; failure_code?: string; provider_status_code?: number; numeric_replay_verified: false; store_written: false; physical_validation: false; hardware_actuation: false };

const object = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === "object" && !Array.isArray(v);
const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const nonnegative = (v: unknown): v is number => finite(v) && v >= 0;
const count = (v: unknown): v is number => nonnegative(v) && Number.isInteger(v) && v <= 36;
const hash = (v: unknown): v is string => typeof v === "string" && /^[a-f0-9]{64}$/.test(v);
const reason = (v: unknown): v is string | null => v === null || typeof v === "string" && v.length > 0 && v.length <= 2000;
const near = (a: number | null, b: number | null) => a === null || b === null ? a === b : finite(a) && finite(b) && Math.abs(a - b) <= 1e-9 * Math.max(1, Math.abs(b));
const mean = (values: number[]) => values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
const fail = (): never => { throw new Error("The matched-current study has incompatible identities, coverage or saved evidence. No result was accepted."); };
const geo = (lat: unknown, lon: unknown) => finite(lat) && finite(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180;
const when = (hour: number) => new Date(Date.parse(MATCHED_ORIGIN) + hour * 3600_000).toISOString().replace(".000Z", "Z");
function utc(value: unknown): number | null {
  if (typeof value !== "string") return null;
  const match = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,6}))?(?:Z|\+00:00)$/.exec(value);
  if (!match) return null;
  const canonical = `${match[1]}.${(match[2] ?? "").padEnd(3, "0").slice(0, 3)}Z`;
  const result = Date.parse(canonical);
  return Number.isFinite(result) && new Date(result).toISOString() === canonical ? result : null;
}
function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (object(value)) return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  return JSON.stringify(value);
}
function bounded(value: unknown, depth = 0, budget = { nodes: 0 }): boolean {
  if (++budget.nodes > 300_000 || depth > 24) return false;
  if (Array.isArray(value)) return value.length <= 20_000 && value.every(v => bounded(v, depth + 1, budget));
  if (object(value)) return Object.keys(value).length <= 100 && Object.values(value).every(v => bounded(v, depth + 1, budget));
  return value === null || typeof value === "boolean" || finite(value) || typeof value === "string" && value.length <= 16_000;
}
function validateMetrics(metrics: MatchedMetrics, errors: (number | null)[], planned: number) {
  if (!object(metrics)) return fail();
  const known = errors.filter((v): v is number => v !== null);
  if (metrics.planned_count !== planned || metrics.scored_count !== known.length || metrics.missing_count !== planned - known.length || metrics.coverage_complete !== (known.length === planned) || metrics.available_cell_summary_is_full_horizon_ade !== (known.length === planned) || !near(metrics.available_cell_mean_error_m, mean(known)) || !near(metrics.full_horizon_ade_m, known.length === planned ? mean(known) : null)) return fail();
}
function validateCell(cell: MatchedForecastCell, hour: number) {
  if (!object(cell) || cell.horizon_hours !== hour || cell.elapsed_s !== hour * 3600 || cell.time_utc !== when(hour) || !reason(cell.forecast_reason_code)) return fail();
  if (cell.forecast_status === "AVAILABLE") { if (!geo(cell.latitude_deg, cell.longitude_deg) || cell.forecast_reason_code !== null) return fail(); }
  else if (cell.forecast_status !== "UNAVAILABLE" || cell.latitude_deg !== null || cell.longitude_deg !== null || typeof cell.forecast_reason_code !== "string") return fail();
}

export function validateMatchedEnvelope(value: unknown, studyVersion: MatchedStudyVersion = "v1"): MatchedEnvelope {
  if (!object(value) || !bounded(value) || !object(value.report) || !object(value.artifact_identity)) return fail();
  const envelope = value as MatchedEnvelope, r = envelope.report, identity = envelope.artifact_identity, s = r.scores;
  const expectedStudy = MATCHED_STUDIES[studyVersion];
  if (!expectedStudy || r.schema_version !== 1 || r.kind !== "MATCHED_CURRENT_RETROSPECTIVE_DIAGNOSTIC" || r.study_id !== expectedStudy || identity.schema_version !== 1 || identity.study_id !== expectedStudy || identity.integrity_verified !== true || identity.result_pin_verified !== true || identity.pin_source !== "TRUSTED_RESULT_IDENTITY" || identity.numeric_replay_verified !== false || identity.verification_scope !== "FROZEN_ARTIFACT_LINEAGE_AND_STRUCTURE_NOT_NUMERIC_REPLAY" || ![identity.report_sha256, identity.forecast_file_sha256, identity.forecast_sha256, identity.protocol_sha256, identity.trusted_protocol_identity_sha256, identity.manifest_sha256, identity.acquisition_start_sha256, identity.result_identity_file_sha256].every(hash)
    || !object(r.lineage) || r.lineage.protocol_sha256 !== identity.protocol_sha256 || r.lineage.trusted_identity_sha256 !== identity.trusted_protocol_identity_sha256 || r.lineage.manifest_sha256 !== identity.manifest_sha256 || r.lineage.acquisition_start_sha256 !== identity.acquisition_start_sha256 || r.forecast_file_sha256 !== identity.forecast_file_sha256 || r.forecasts_saved_before_target_coordinate_decode !== true || utc(r.forecast_frozen_at_utc) === null || utc(r.scored_at_utc) === null || utc(r.scored_at_utc)! < utc(r.forecast_frozen_at_utc)! || !Array.isArray(r.source_receipts) || !object(r.context_qc) || !(r.current_field === null || object(r.current_field)) || !reason(r.current_field_failure)
    || [r.physical_validation, r.operational_causality, r.assimilation_independence_verified, r.physical_alias_resolution_verified, r.statistical_independence, r.global_training, r.heldout_tuning, r.automatic_model_promotion, r.provider_calls, r.camera_started, r.store_written].some(v => v !== false)
    || !object(s) || s.schema_version !== 1 || s.kind !== "MATCHED_CURRENT_SCORES" || s.origin_time_utc !== MATCHED_ORIGIN || s.planned_group_count !== 2 || s.planned_cell_count !== 36 || s.planned_distinct_target_count !== 12 || !count(s.scored_cell_count) || [s.statistical_independence, s.automatic_winner_selected, s.operational_forecast_skill_verified, s.physical_validation].some(v => v !== false) || !Array.isArray(s.limitations) || !s.limitations.length || !s.limitations.every(v => typeof v === "string")) return fail();
  const f = s.forecast_report;
  if (!object(f) || f.schema_version !== 1 || f.kind !== "MATCHED_CURRENT_FORECASTS" || f.origin_time_utc !== MATCHED_ORIGIN || JSON.stringify(f.group_ids) !== JSON.stringify(MATCHED_GROUPS) || JSON.stringify(f.model_ids) !== JSON.stringify(MATCHED_MODELS) || JSON.stringify(f.horizons_s) !== JSON.stringify([3600,7200,10800,14400,18000,21600]) || f.planned_group_count !== 2 || f.planned_cell_count !== 36 || f.planned_distinct_target_count !== 12 || f.forecast_sha256 !== identity.forecast_sha256 || f.all_forecasts_built_before_target_decode !== true || f.future_positions_used !== false || [f.statistical_independence,f.operational_forecast_skill_verified,f.physical_validation].some(v=>v!==false) || f.coordinate_method!=="origin_anchored_mean_sphere_log_exp_50km_last_drift" || f.score_method!=="mean_radius_sphere_great_circle_metres" || !Array.isArray(f.groups) || f.groups.length !== 2 || !Array.isArray(s.groups) || s.groups.length !== 2 || !Array.isArray(s.models) || s.models.length !== 3) return fail();
  const cellsByModel: MatchedCell[][] = [[], [], []]; let total = 0;
  for (let groupIndex = 0; groupIndex < 2; groupIndex++) {
    const forecastGroup = f.groups[groupIndex], group = s.groups[groupIndex], id = MATCHED_GROUPS[groupIndex];
    if (!object(forecastGroup) || !object(group) || forecastGroup.group_id !== id || group.group_id !== id || ![0,25].includes(forecastGroup.context_count) || !Array.isArray(forecastGroup.candidates) || forecastGroup.candidates.length !== 3 || !Array.isArray(group.candidates) || group.candidates.length !== 3 || !Array.isArray(group.target_issues)) return fail();
    if (forecastGroup.origin_position !== null && (!object(forecastGroup.origin_position) || forecastGroup.origin_position.time_utc !== MATCHED_ORIGIN || !geo(forecastGroup.origin_position.latitude_deg, forecastGroup.origin_position.longitude_deg))) return fail();
    for (let modelIndex = 0; modelIndex < 3; modelIndex++) {
      const forecast = forecastGroup.candidates[modelIndex], candidate = group.candidates[modelIndex], model = MATCHED_MODELS[modelIndex];
      if (!object(forecast) || !object(candidate) || forecast.model_id !== model || candidate.model_id !== model || !["COMPLETED", "PARTIAL", "UNSUPPORTED", "FAILED"].includes(forecast.status) || candidate.prediction_status !== forecast.status || candidate.prediction_reason_code !== forecast.reason_code || !reason(forecast.reason_code) || forecast.requested_horizon_s !== 21600 || !nonnegative(forecast.completed_horizon_s) || forecast.completed_horizon_s > 21600 || forecast.planned_count !== 6 || !count(forecast.available_count) || forecast.available_count > 6 || forecast.context_rows_used !== (model === "last_drift" ? 2 : 1) || forecast.learned_parameters !== 0 || forecast.future_positions_used !== false || !Array.isArray(forecast.cells) || forecast.cells.length !== 6 || !Array.isArray(candidate.cells) || candidate.cells.length !== 6) return fail();
      let available = 0;
      for (let index = 0; index < 6; index++) {
        const raw = forecast.cells[index], cell = candidate.cells[index]; validateCell(raw, index + 1); validateCell(cell, index + 1);
        if (cell.group_id !== id || cell.model_id !== model || ["forecast_status", "forecast_reason_code", "latitude_deg", "longitude_deg"].some(key => cell[key as keyof MatchedCell] !== raw[key as keyof MatchedForecastCell]) || !reason(cell.target_reason_code)) return fail();
        if (cell.forecast_status === "AVAILABLE") { available++; if (cell.elapsed_s > forecast.completed_horizon_s) return fail(); }
        if (cell.target_status === "AVAILABLE") { if (!geo(cell.target_latitude_deg, cell.target_longitude_deg) || cell.target_reason_code !== null) return fail(); }
        else if (cell.target_status !== "UNAVAILABLE" || cell.target_latitude_deg !== null || cell.target_longitude_deg !== null || typeof cell.target_reason_code !== "string") return fail();
        const expectedStatus = cell.forecast_status !== "AVAILABLE" ? "FORECAST_UNAVAILABLE" : cell.target_status !== "AVAILABLE" ? "TARGET_UNAVAILABLE" : "SCORED";
        if (cell.score_status !== expectedStatus || (cell.score_status === "SCORED" ? !nonnegative(cell.error_m) : cell.error_m !== null)) return fail();
        const targetPeer = group.candidates[0].cells[index];
        if (["target_status", "target_reason_code", "target_latitude_deg", "target_longitude_deg"].some(key => cell[key as keyof MatchedCell] !== targetPeer[key as keyof MatchedCell])) return fail();
        if (cell.score_status === "SCORED") total++;
        cellsByModel[modelIndex].push(cell);
      }
      if (available !== forecast.available_count || forecast.status === "COMPLETED" && (available !== 6 || forecast.completed_horizon_s !== 21600 || forecast.reason_code !== null) || forecast.status !== "COMPLETED" && forecast.reason_code === null) return fail();
      const errors = candidate.cells.map(cell => cell.error_m); validateMetrics(candidate.metrics, errors, 6);
      const prefix = errors.findIndex(error => error === null), prefixCount = prefix < 0 ? 6 : prefix;
      if (candidate.metrics.endpoint_fde_m !== errors[5] || candidate.metrics.endpoint_scored !== (errors[5] !== null) || candidate.metrics.scored_prefix_count !== prefixCount || JSON.stringify(candidate.metrics.scored_prefix_hours) !== JSON.stringify(Array.from({length:prefixCount},(_,i)=>i+1)) || !near(candidate.metrics.scored_prefix_mean_error_m, mean(errors.slice(0,prefixCount) as number[])) || candidate.metrics.prefix_is_full_horizon !== (prefixCount === 6)) return fail();
    }
  }
  if (s.scored_cell_count !== total || s.primary_common_cohort_complete !== (total === 36)) return fail();
  for (const [index, model] of s.models.entries()) {
    if (!object(model) || model.model_id !== MATCHED_MODELS[index] || !Array.isArray(model.per_horizon) || model.per_horizon.length !== 6) return fail();
    validateMetrics(model.metrics, cellsByModel[index].map(cell => cell.error_m), 12);
    for (let hour = 1; hour <= 6; hour++) {
      const row = model.per_horizon[hour - 1], errors = cellsByModel[index].filter(cell => cell.horizon_hours === hour && cell.error_m !== null).map(cell => cell.error_m as number);
      if (!object(row) || row.horizon_hours !== hour || row.planned_group_count !== 2 || row.scored_group_count !== errors.length || row.coverage_complete !== (errors.length === 2) || !near(row.available_group_mean_error_m, mean(errors)) || !near(row.complete_group_mean_error_m, errors.length === 2 ? mean(errors) : null)) return fail();
    }
  }
  validatePairs(s.paired_comparisons, cellsByModel, "SECONDARY_COMMON_AVAILABLE_CELLS");
  if (total !== 36) { if (s.primary_equal_id_macro_results !== null || s.primary_paired_comparisons !== null) return fail(); }
  else {
    if (!Array.isArray(s.primary_equal_id_macro_results) || s.primary_equal_id_macro_results.length !== 3) return fail();
    for (const [index, primary] of s.primary_equal_id_macro_results.entries()) {
      const metrics = s.groups.map(group => group.candidates[index].metrics);
      if (!object(primary) || primary.model_id !== MATCHED_MODELS[index] || primary.group_count !== 2 || !near(primary.equal_id_macro_ade_m, mean(metrics.map(m => m.full_horizon_ade_m!))) || !near(primary.equal_id_macro_fde_m, mean(metrics.map(m => m.endpoint_fde_m!))) || !Array.isArray(primary.per_horizon_mean_error_m) || primary.per_horizon_mean_error_m.length !== 6) return fail();
      for (let hour = 1; hour <= 6; hour++) { const row = primary.per_horizon_mean_error_m[hour - 1]; if (!object(row) || row.horizon_hours !== hour || !near(row.error_m, s.models[index].per_horizon[hour-1].complete_group_mean_error_m)) return fail(); }
    }
    validatePairs(s.primary_paired_comparisons, cellsByModel, "PRIMARY_COMPLETE_COMMON_COHORT");
  }
  return envelope;
}

function validatePairs(value: MatchedPair[] | null, cells: MatchedCell[][], scope: string) {
  if (!Array.isArray(value) || value.length !== 3) return fail();
  for (const [index, pair] of value.entries()) {
    const [a,b] = [[0,1],[0,2],[1,2]][index], available = cells[a].filter((cell,i) => cell.error_m !== null && cells[b][i].error_m !== null);
    if (!object(pair) || pair.model_a !== MATCHED_MODELS[a] || pair.model_b !== MATCHED_MODELS[b] || pair.planned_common_cell_count !== 12 || pair.common_scored_count !== available.length || pair.coverage_complete !== (available.length === 12) || pair.analysis_scope !== scope || !Array.isArray(pair.cells) || pair.cells.length !== available.length) return fail();
    const errorsB: number[] = [];
    for (const [i,row] of pair.cells.entries()) { const left = available[i], right = cells[b].find(cell => cell.group_id === left.group_id && cell.horizon_hours === left.horizon_hours)!; if (!object(row) || row.group_id !== left.group_id || row.time_utc !== left.time_utc || row.horizon_hours !== left.horizon_hours || row.error_a_m !== left.error_m || row.error_b_m !== right.error_m) return fail(); errorsB.push(right.error_m!); }
    if (!near(pair.mean_error_a_m, mean(available.map(cell => cell.error_m!))) || !near(pair.mean_error_b_m, mean(errorsB)) || !near(pair.mean_delta_a_minus_b_m, mean(available.map((cell,i) => cell.error_m! - errorsB[i])))) return fail();
  }
}

export type MatchedPlotPoint = GeoPoint & { hour: number; x_m: number; y_m: number };
export type MatchedPlot = { origin: GeoPoint; series: Record<"recorded" | MatchedModelId, (MatchedPlotPoint | null)[]>; domain: { centerX: number; centerY: number; span: number }; originAvailable: boolean };
export function matchedPlot(envelope: MatchedEnvelope, groupId: string): MatchedPlot | null {
  const scores = envelope.report.scores, group = scores.groups.find(g => g.group_id === groupId), forecast = scores.forecast_report.groups.find(g => g.group_id === groupId);
  if (!group || !forecast) return null;
  const recorded = group.candidates[0].cells.map(cell => cell.target_status === "AVAILABLE" ? { time_utc: cell.time_utc, latitude_deg: cell.target_latitude_deg!, longitude_deg: cell.target_longitude_deg! } : null);
  const origin = forecast.origin_position ?? recorded.find((p): p is GeoPoint => p !== null);
  if (!origin) return null;
  const project = (point: GeoPoint | null, hour: number): MatchedPlotPoint | null => {
    if (!point) return null;
    const dlon = (point.longitude_deg - origin.longitude_deg) * Math.PI / 180;
    return { ...point, hour, x_m: 6_371_008.8 * Math.cos(origin.latitude_deg * Math.PI / 180) * Math.atan2(Math.sin(dlon), Math.cos(dlon)), y_m: 6_371_008.8 * (point.latitude_deg - origin.latitude_deg) * Math.PI / 180 };
  };
  const series = { recorded: [project(forecast.origin_position,0),...recorded.map((p,i)=>project(p,i+1))] } as MatchedPlot["series"];
  for (const model of MATCHED_MODELS) series[model] = [project(forecast.origin_position,0),...group.candidates.find(candidate => candidate.model_id === model)!.cells.map((cell,i)=>project(cell.forecast_status === "AVAILABLE" ? {time_utc:cell.time_utc,latitude_deg:cell.latitude_deg!,longitude_deg:cell.longitude_deg!}:null,i+1))];
  const points = Object.values(series).flat().filter((p): p is MatchedPlotPoint => p !== null), xs=points.map(p=>p.x_m), ys=points.map(p=>p.y_m);
  return {origin,series,originAvailable:forecast.origin_position!==null,domain:{centerX:(Math.min(...xs)+Math.max(...xs))/2,centerY:(Math.min(...ys)+Math.max(...ys))/2,span:Math.max(Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys),100)*1.18}};
}
export function matchedSegments(points: (MatchedPlotPoint | null)[]): MatchedPlotPoint[][] {
  const segments: MatchedPlotPoint[][] = []; let current: MatchedPlotPoint[] = [];
  for (const point of points) { if (!point) { if(current.length)segments.push(current);current=[]; } else {if(current.length&&point.hour!==current[current.length-1].hour+1){segments.push(current);current=[];} current.push(point);} }
  if(current.length)segments.push(current); return segments;
}
export function matchedHourlyDisplacement(points: (MatchedPlotPoint | null)[], hour: number): [MatchedPlotPoint, MatchedPlotPoint] | null {
  if (!Number.isInteger(hour) || hour < 1 || hour > 6) return null;
  const from = points[hour - 1], to = points[hour];
  return from && to && from.hour === hour - 1 && to.hour === hour ? [from, to] : null;
}

export function validateMatchedAnswer(value: unknown, selected: MatchedEnvelope): MatchedAnswer {
  if (!object(value) || !bounded(value) || value.schema_version !== 1 || value.kind !== "MATCHED_CURRENT_RESEARCH_INVESTIGATION" || value.scope !== "READ_ONLY_MATCHED_CURRENT_STUDY" || !["REPORT","STOP"].includes(value.action as string) || typeof value.explanation !== "string" || !value.explanation.trim() || value.explanation.length > 1200 || typeof value.live_model_response !== "boolean" || value.provider !== "chalk" || !Array.isArray(value.evidence_ids) || !Array.isArray(value.trace) || value.trace.length > 1 || [value.numeric_replay_verified,value.store_written,value.physical_validation,value.hardware_actuation].some(v=>v!==false)) return fail();
  const current = validateMatchedEnvelope({report:value.research_report,artifact_identity:value.artifact_identity}, matchedStudyVersion(selected.report.study_id)), identity=selected.artifact_identity;
  if (current.artifact_identity.report_sha256!==identity.report_sha256 || current.artifact_identity.protocol_sha256!==identity.protocol_sha256 || value.report_sha256!==identity.report_sha256 || value.protocol_sha256!==identity.protocol_sha256 || canonical(current)!==canonical(selected)) return fail();
  const allowed=[`matched-current-report:${identity.report_sha256}`,`matched-current-protocol:${identity.protocol_sha256}`];
  if (value.evidence_ids.some(id=>typeof id!=="string"||!allowed.includes(id)) || new Set(value.evidence_ids).size!==value.evidence_ids.length || value.action==="REPORT"&&(value.live_model_response!==true||value.evidence_ids.length!==2||value.trace.length!==1)) return fail();
  if (value.failure_code !== undefined && (typeof value.failure_code !== "string" || value.failure_code.length > 200) || value.provider_status_code !== undefined && (!Number.isInteger(value.provider_status_code) || (value.provider_status_code as number) < 100 || (value.provider_status_code as number) > 599)) return fail();
  for(const step of value.trace) {
    if(!object(step)||step.tool!=="get_study_evidence"||!object(step.arguments)||Object.keys(step.arguments).length!==0||!object(step.result)||step.result.ok!==true||!Array.isArray(step.result.evidence_ids)||step.result.evidence_ids.length!==2||new Set(step.result.evidence_ids).size!==2||step.result.evidence_ids.some(id=>!allowed.includes(id as string)))return fail();
    const compact=step.result.matched_current_study, s=selected.report.scores;
    if(!object(compact)||compact.report_sha256!==identity.report_sha256||compact.protocol_sha256!==identity.protocol_sha256||canonical(compact.artifact_verification)!==canonical(identity)||!object(compact.coverage)||compact.coverage.planned_cell_count!==36||compact.coverage.scored_cell_count!==s.scored_cell_count||compact.coverage.planned_distinct_target_count!==12||compact.coverage.planned_group_count!==2||compact.coverage.planned_model_track_count!==6||compact.coverage.primary_common_cohort_complete!==s.primary_common_cohort_complete||canonical(compact.models)!==canonical(s.models)||canonical(compact.primary_equal_id_macro_results)!==canonical(s.primary_equal_id_macro_results)||!Array.isArray(compact.groups)||compact.groups.length!==2)return fail();
    for(const [index,group] of compact.groups.entries()) {
      const source=s.groups[index], forecast=s.forecast_report.groups[index];
      if(!object(group)||group.group_id!==source.group_id||canonical(group.target_issues)!==canonical(source.target_issues)||!Array.isArray(group.candidates)||group.candidates.length!==3)return fail();
      for(const [modelIndex,candidate] of group.candidates.entries()) {
        const sourceCandidate=source.candidates[modelIndex];
        if(!object(candidate)||candidate.model_id!==sourceCandidate.model_id||candidate.prediction_status!==sourceCandidate.prediction_status||candidate.prediction_reason_code!==sourceCandidate.prediction_reason_code||candidate.forecast_available_count!==forecast.candidates[modelIndex].available_count||canonical(candidate.metrics)!==canonical(sourceCandidate.metrics))return fail();
      }
    }
  }
  return value as MatchedAnswer;
}
