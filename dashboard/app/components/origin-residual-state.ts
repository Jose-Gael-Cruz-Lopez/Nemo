/** Display guards for one saved exploratory result. No fitting, scoring or acquisition. */
export const ORIGIN_GROUPS = ["300234066836710", "300534061292930"] as const;
export const ORIGIN_MODELS = ["stationary", "last_drift", "current_only", "origin_residual_current"] as const;
export const ORIGIN_TIME = "2022-06-01T00:00:00Z";
export const ORIGIN_SCOPE = "POST_OUTCOME_EXPLORATORY";
export const ORIGIN_PINS = {
  study_id: "origin-residual-gdp-hycom-15m-exploratory-v1",
  identity_sha256: "d36bb0dcfb47db4c668215fa4f9f59db0ceea01917a360f14a04e1e5feda3f27",
  report_sha256: "801d7192ba138817f242401ae6706562f2b8c5c34306219ee37e04a2af2299c8",
  protocol_sha256: "e1073f84e83b2ea078d0890972659e778f87238c417287d8adf70e3649587163",
  forecast_file_sha256: "727e2ce329148c31194bd6fc7b17c39da8b83923439140b9eef5c378376cc0d1",
} as const;
const INNER_FORECAST = "8d9fa46727204ac8ff86ba3b03d3628756e1540b88e97b5551e0f3d4104e94b7";
const CLAIM_FLAGS = ["statistical_independence", "automatic_winner_selected", "automatic_model_promotion", "operational_forecast_skill_verified", "physical_validation", "heldout_tuning", "global_training"] as const;
const FALSE_CLAIMS = new Set<string>([...CLAIM_FLAGS,"future_positions_used","provider_calls","new_data_acquisition","frozen_source_study_changed","heldout_buoy_positions_used","plastic_motion_validated","tank_flow_used"]);
export type OriginModelId = typeof ORIGIN_MODELS[number];
export type OriginGeo = { time_utc: string; latitude_deg: number; longitude_deg: number };
export type OriginForecastCell = { horizon_hours: number; elapsed_s: number; time_utc: string; forecast_status: "AVAILABLE" | "UNAVAILABLE"; forecast_reason_code: string | null; latitude_deg: number | null; longitude_deg: number | null };
export type OriginCell = OriginForecastCell & { group_id: string; model_id: OriginModelId; score_status: "SCORED" | "FORECAST_UNAVAILABLE" | "TARGET_UNAVAILABLE"; error_m: number | null; target_latitude_deg: number | null; target_longitude_deg: number | null };
export type OriginMetrics = { planned_count: number; scored_count: number; coverage_complete: boolean; available_cell_mean_error_m: number | null; full_horizon_ade_m: number | null };
export type OriginCandidate = { model_id: OriginModelId; prediction_status: string; prediction_reason_code: string | null; metrics: OriginMetrics & { endpoint_fde_m: number | null }; cells: OriginCell[] };
export type OriginForecastCandidate = { model_id: OriginModelId; status: string; reason_code: string | null; requested_horizon_s: number; completed_horizon_s: number; planned_count: number; available_count: number; context_rows_used: number; learned_parameters: 0; future_positions_used: false; cells: OriginForecastCell[]; residual_east_north_m_s?: number[] | null; source_field_sha256?: string; derived_field_sha256?: string; [key: string]: unknown };
export type OriginPair = { model_a: OriginModelId; model_b: OriginModelId; planned_common_cell_count: number; common_scored_count: number; coverage_complete: boolean; analysis_scope: string; mean_delta_a_minus_b_m: number | null; cells: { group_id: string; horizon_hours: number; error_a_m: number; error_b_m: number }[] };
export type OriginScores = { schema_version: 1; kind: string; study_id: string; analysis_scope: string; previously_viewed_target_outcomes: true; planned_group_count: 2; planned_cell_count: 48; planned_distinct_target_count: 12; scored_cell_count: number; primary_common_cohort_complete: boolean; primary_equal_id_macro_results: { model_id: OriginModelId; group_count: 2; equal_id_macro_ade_m: number; equal_id_macro_fde_m: number }[] | null; groups: { group_id: string; target_issues: string[]; candidates: OriginCandidate[] }[]; models: { model_id: OriginModelId; metrics: OriginMetrics }[]; paired_comparisons: OriginPair[]; limitations: string[]; [key: string]: unknown };
export type OriginReport = { schema_version: 1; kind: string; study_id: string; analysis_scope: string; previously_viewed_target_outcomes: true; protocol_sha256: string; forecast_file_sha256: string; forecast_frozen_at_utc: string; scored_at_utc: string; source_artifact_pins: Record<string, string>; method_source_sha256: Record<string, string>; source_acquisition_lineage: Record<string, string>; scores: OriginScores; [key: string]: unknown };
export type OriginForecasts = { schema_version: 1; kind: string; study_id: string; origin_time_utc: string; group_ids: string[]; model_ids: OriginModelId[]; horizons_s: number[]; forecast_sha256: string; planned_group_count: 2; planned_cell_count: 48; planned_distinct_target_count: 12; groups: { group_id: string; context_count: number; origin_position: OriginGeo | null; candidates: OriginForecastCandidate[] }[]; [key: string]: unknown };
export type OriginIdentity = typeof ORIGIN_PINS & { schema_version: 1; kind: "ORIGIN_RESIDUAL_LOCAL_RESULT_IDENTITY"; integrity_verified: true; external_result_pin_verified: true; externally_trusted_pin_required_for_publication: true; numeric_replay_verified: false; verification_scope: "SAVED_BYTES_AND_LINEAGE_NOT_NUMERIC_REPLAY" };
export type OriginEnvelope = { report: OriginReport; forecasts: OriginForecasts; artifact_identity: OriginIdentity };
export type OriginAnswer = { schema_version: 1; kind: "ORIGIN_RESIDUAL_RESEARCH_INVESTIGATION"; scope: "READ_ONLY_POST_OUTCOME_EXPLORATORY_DIAGNOSTIC"; analysis_scope: typeof ORIGIN_SCOPE; previously_viewed_target_outcomes: true; action: "REPORT" | "STOP"; explanation: string; evidence_ids: string[]; trace: unknown[]; provider: "chalk"; live_model_response: boolean; research_report: OriginReport; artifact_identity: OriginIdentity; report_sha256: string; protocol_sha256: string; identity_sha256: string; numeric_replay_verified: false; store_written: false; hardware_actuation: false; physical_validation: false; automatic_model_promotion: false; failure_code?: string; provider_status_code?: number; timeout_stage?: string; model_calls_attempted?: number };

const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value);
const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const nonnegative = (value: unknown): value is number => finite(value) && value >= 0;
const count = (value: unknown, max: number): value is number => nonnegative(value) && Number.isInteger(value) && value <= max;
const hash = (value: unknown): value is string => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
const reason = (value: unknown) => value === null || typeof value === "string" && value.length > 0 && value.length <= 2000;
const geo = (lat: unknown, lon: unknown) => finite(lat) && finite(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180;
const pair = (value: unknown) => value === null || Array.isArray(value) && value.length === 2 && value.every(finite);
const when = (hour: number) => new Date(Date.parse(ORIGIN_TIME) + hour * 3600_000).toISOString().replace(".000Z", "Z");
const fail = (): never => { throw new Error("The exploratory result has incompatible identities, coverage or saved evidence. No result was accepted."); };
function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (object(value)) return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  return JSON.stringify(value);
}
function bounded(value: unknown, depth = 0, budget = { nodes: 0 }): boolean {
  if (++budget.nodes > 250_000 || depth > 24) return false;
  if (Array.isArray(value)) return value.length <= 20_000 && value.every(item => bounded(item, depth + 1, budget));
  if (object(value)) return Object.keys(value).length <= 100 && Object.values(value).every(item => bounded(item, depth + 1, budget));
  return value === null || typeof value === "boolean" || finite(value) || typeof value === "string" && value.length <= 16_000;
}
function conservativeClaims(value: unknown): boolean {
  if (Array.isArray(value)) return value.every(conservativeClaims);
  return !object(value) || Object.entries(value).every(([key,item]) => (!FALSE_CLAIMS.has(key) || item === false) && conservativeClaims(item));
}
function utc(value: unknown): number | null {
  if (typeof value !== "string") return null;
  const match = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,6}))?(?:Z|\+00:00)$/.exec(value);
  if (!match) return null;
  const text = `${match[1]}.${(match[2] ?? "").padEnd(3, "0").slice(0, 3)}Z`, time = Date.parse(text);
  return Number.isFinite(time) && new Date(time).toISOString() === text ? time : null;
}
function pins(value: unknown) {
  return object(value) && Object.entries(ORIGIN_PINS).every(([key, pin]) => value[key] === pin)
    && value.schema_version === 1 && value.kind === "ORIGIN_RESIDUAL_LOCAL_RESULT_IDENTITY"
    && value.integrity_verified === true && value.external_result_pin_verified === true
    && value.externally_trusted_pin_required_for_publication === true && value.numeric_replay_verified === false
    && value.verification_scope === "SAVED_BYTES_AND_LINEAGE_NOT_NUMERIC_REPLAY";
}
function hashes(value: unknown, keys: readonly string[]) {
  return object(value) && canonical(Object.keys(value).sort()) === canonical([...keys].sort()) && Object.values(value).every(hash);
}
function metrics(value: OriginMetrics, planned: number, scored: number) {
  if (!object(value) || value.planned_count !== planned || value.scored_count !== scored || value.coverage_complete !== (scored === planned)
    || (scored ? !nonnegative(value.available_cell_mean_error_m) : value.available_cell_mean_error_m !== null)
    || (scored === planned ? !nonnegative(value.full_horizon_ade_m) : value.full_horizon_ade_m !== null)) fail();
  // Stored errors and summaries remain authoritative. No geographic re-scoring,
  // ADE/FDE recomputation or model selection occurs in this display validator.
}
function forecastCell(value: OriginForecastCell, hour: number) {
  if (!object(value) || value.horizon_hours !== hour || value.elapsed_s !== hour * 3600 || value.time_utc !== when(hour) || !reason(value.forecast_reason_code)) fail();
  if (value.forecast_status === "AVAILABLE") { if (!geo(value.latitude_deg, value.longitude_deg) || value.forecast_reason_code !== null) fail(); }
  else if (value.forecast_status !== "UNAVAILABLE" || value.latitude_deg !== null || value.longitude_deg !== null || typeof value.forecast_reason_code !== "string") fail();
}

export function validateOriginEnvelope(value: unknown): OriginEnvelope {
  if (!object(value) || !bounded(value) || !conservativeClaims(value) || canonical(Object.keys(value).sort()) !== canonical(["artifact_identity", "forecasts", "report"]) || !object(value.report) || !object(value.forecasts) || !pins(value.artifact_identity)) return fail();
  const envelope = value as OriginEnvelope, r = envelope.report, f = envelope.forecasts, s = r.scores;
  if (r.schema_version !== 1 || r.kind !== "ORIGIN_RESIDUAL_EXPLORATORY_DIAGNOSTIC" || r.study_id !== ORIGIN_PINS.study_id || r.protocol_sha256 !== ORIGIN_PINS.protocol_sha256 || r.forecast_file_sha256 !== ORIGIN_PINS.forecast_file_sha256 || r.analysis_scope !== ORIGIN_SCOPE || r.previously_viewed_target_outcomes !== true || r.all_four_forecasts_saved_before_this_diagnostic_target_decode !== true
    || [r.new_data_acquisition, r.frozen_source_study_changed, r.provider_calls, r.physical_validation].some(flag => flag !== false)
    || utc(r.forecast_frozen_at_utc) === null || utc(r.scored_at_utc) === null || utc(r.scored_at_utc)! < utc(r.forecast_frozen_at_utc)!
    || !hashes(r.source_artifact_pins, ["evaluation.json", "forecasts.json", "manifest.json"])
    || !hashes(r.source_acquisition_lineage, ["acquisition_start_sha256", "manifest_sha256", "protocol_sha256", "trusted_identity_sha256"])
    || !hashes(r.method_source_sha256, ["apps/ocean/reeftrace_ocean/origin_residual.py", "scripts/evaluate_origin_residual_diagnostic.py", "tests/unit/test_origin_residual.py"])) return fail();
  if (f.schema_version !== 1 || f.kind !== "ORIGIN_RESIDUAL_EXPLORATORY_FORECASTS" || f.study_id !== ORIGIN_PINS.study_id || f.analysis_scope !== ORIGIN_SCOPE || f.previously_viewed_target_outcomes !== true || f.origin_time_utc !== ORIGIN_TIME || f.forecast_sha256 !== INNER_FORECAST || f.all_forecasts_built_before_target_decode !== true || f.future_positions_used !== false || f.automatic_model_promotion !== false || f.learned_parameters !== 0
    || canonical(f.group_ids) !== canonical(ORIGIN_GROUPS) || canonical(f.model_ids) !== canonical(ORIGIN_MODELS) || canonical(f.horizons_s) !== canonical([3600,7200,10800,14400,18000,21600]) || f.planned_group_count !== 2 || f.planned_cell_count !== 48 || f.planned_distinct_target_count !== 12 || !Array.isArray(f.groups) || f.groups.length !== 2
    || !object(s) || s.schema_version !== 1 || s.kind !== "ORIGIN_RESIDUAL_EXPLORATORY_SCORES" || s.study_id !== ORIGIN_PINS.study_id || s.analysis_scope !== ORIGIN_SCOPE || s.previously_viewed_target_outcomes !== true || s.planned_group_count !== 2 || s.planned_cell_count !== 48 || s.planned_distinct_target_count !== 12 || !count(s.scored_cell_count,48) || CLAIM_FLAGS.some(key => s[key] !== false) || !Array.isArray(s.groups) || s.groups.length !== 2 || !Array.isArray(s.models) || s.models.length !== 4 || !Array.isArray(s.limitations) || !s.limitations.length || !s.limitations.every(text => typeof text === "string" && text.length > 0)) return fail();
  const byModel: OriginCell[][] = ORIGIN_MODELS.map(() => []); let total = 0;
  for (let gi = 0; gi < 2; gi++) {
    const fg = f.groups[gi], group = s.groups[gi], groupId = ORIGIN_GROUPS[gi];
    if (!object(fg) || !object(group) || fg.group_id !== groupId || group.group_id !== groupId || !count(fg.context_count,20000) || !Array.isArray(fg.candidates) || fg.candidates.length !== 4 || !Array.isArray(group.candidates) || group.candidates.length !== 4 || !Array.isArray(group.target_issues) || !group.target_issues.every(text => typeof text === "string" && text.length > 0 && text.length <= 2000)) return fail();
    if (fg.origin_position !== null && (!object(fg.origin_position) || fg.origin_position.time_utc !== ORIGIN_TIME || !geo(fg.origin_position.latitude_deg,fg.origin_position.longitude_deg))) return fail();
    if (fg.context_count !== 25 && (fg.origin_position !== null || fg.candidates.some(row => !object(row) || row.status !== "UNSUPPORTED" || row.available_count !== 0 || row.completed_horizon_s !== 0))) return fail();
    for (let mi = 0; mi < 4; mi++) {
      const raw = fg.candidates[mi], candidate = group.candidates[mi], id = ORIGIN_MODELS[mi];
      if (!object(raw) || !object(candidate) || raw.model_id !== id || candidate.model_id !== id || !["COMPLETED","PARTIAL","UNSUPPORTED"].includes(raw.status) || candidate.prediction_status !== raw.status || candidate.prediction_reason_code !== raw.reason_code || !reason(raw.reason_code) || raw.planned_count !== 6 || raw.requested_horizon_s !== 21600 || !nonnegative(raw.completed_horizon_s) || raw.completed_horizon_s > 21600 || !count(raw.available_count,6) || raw.context_rows_used !== (mi === 1 || mi === 3 ? 2 : 1) || raw.learned_parameters !== 0 || raw.future_positions_used !== false || !Array.isArray(raw.cells) || raw.cells.length !== 6 || !Array.isArray(candidate.cells) || candidate.cells.length !== 6) return fail();
      if (mi === 3 && (raw.residual_definition !== "last_observed_origin_tangent_velocity_minus_origin_current" || raw.residual_units !== "m/s" || raw.residual_transport !== "constant_local_east_north_components" || !pair(raw.residual_east_north_m_s) || !pair(raw.last_observed_velocity_m_s) || !pair(raw.origin_current_east_north_m_s) || (raw.source_field_sha256 !== undefined && !hash(raw.source_field_sha256)) || (raw.derived_field_sha256 !== undefined && !hash(raw.derived_field_sha256)))) return fail();
      let available = 0, scored = 0;
      for (let index = 0; index < 6; index++) {
        const prediction = raw.cells[index], cell = candidate.cells[index]; forecastCell(prediction,index + 1); forecastCell(cell,index + 1);
        if (cell.group_id !== groupId || cell.model_id !== id || ["forecast_status","forecast_reason_code","latitude_deg","longitude_deg"].some(key => cell[key as keyof OriginCell] !== prediction[key as keyof OriginForecastCell])) return fail();
        const targetPresent = geo(cell.target_latitude_deg,cell.target_longitude_deg);
        if (!targetPresent && (cell.target_latitude_deg !== null || cell.target_longitude_deg !== null)) return fail();
        const expected = cell.forecast_status !== "AVAILABLE" ? "FORECAST_UNAVAILABLE" : !targetPresent ? "TARGET_UNAVAILABLE" : "SCORED";
        if (cell.score_status !== expected || (expected === "SCORED" ? !nonnegative(cell.error_m) : cell.error_m !== null)) return fail();
        const peer = group.candidates[0].cells[index];
        if (!object(peer) || peer.target_latitude_deg !== cell.target_latitude_deg || peer.target_longitude_deg !== cell.target_longitude_deg) return fail();
        if (cell.forecast_status === "AVAILABLE") { available++; if (cell.elapsed_s > raw.completed_horizon_s) return fail(); }
        if (cell.score_status === "SCORED") { scored++; total++; }
        byModel[mi].push(cell);
      }
      if (raw.available_count !== available || raw.status === "COMPLETED" && (available !== 6 || raw.completed_horizon_s !== 21600 || raw.reason_code !== null) || raw.status !== "COMPLETED" && raw.reason_code === null) return fail();
      metrics(candidate.metrics,6,scored);
      if (candidate.metrics.endpoint_fde_m !== candidate.cells[5].error_m) return fail();
    }
  }
  if (s.scored_cell_count !== total || s.primary_common_cohort_complete !== (total === 48)) return fail();
  for (let mi = 0; mi < 4; mi++) {
    const model = s.models[mi]; if (!object(model) || model.model_id !== ORIGIN_MODELS[mi]) return fail();
    metrics(model.metrics,12,byModel[mi].filter(cell => cell.score_status === "SCORED").length);
  }
  if (total === 48) {
    if (!Array.isArray(s.primary_equal_id_macro_results) || s.primary_equal_id_macro_results.length !== 4) return fail();
    s.primary_equal_id_macro_results.forEach((row,index) => { if (!object(row) || row.model_id !== ORIGIN_MODELS[index] || row.group_count !== 2 || !nonnegative(row.equal_id_macro_ade_m) || !nonnegative(row.equal_id_macro_fde_m)) fail(); });
  } else if (s.primary_equal_id_macro_results !== null) return fail();
  if (!Array.isArray(s.paired_comparisons) || s.paired_comparisons.length !== 6) return fail();
  let slot = 0;
  for (let a = 0; a < 4; a++) for (let b = a + 1; b < 4; b++) {
    const row = s.paired_comparisons[slot++], cells = byModel[a].flatMap((cell,index) => cell.score_status === "SCORED" && byModel[b][index].score_status === "SCORED" ? [{group_id:cell.group_id,horizon_hours:cell.horizon_hours,error_a_m:cell.error_m,error_b_m:byModel[b][index].error_m}] : []);
    if (!object(row) || row.model_a !== ORIGIN_MODELS[a] || row.model_b !== ORIGIN_MODELS[b] || row.planned_common_cell_count !== 12 || row.common_scored_count !== cells.length || row.coverage_complete !== (cells.length === 12) || row.analysis_scope !== (total === 48 ? "PRIMARY_COMPLETE_DEVELOPMENT_COHORT" : "SECONDARY_COMMON_AVAILABLE_CELLS") || canonical(row.cells) !== canonical(cells) || (cells.length ? !finite(row.mean_delta_a_minus_b_m) : row.mean_delta_a_minus_b_m !== null)) return fail();
  }
  return envelope;
}

export type OriginPlotPoint = OriginGeo & { hour: number; x_m: number; y_m: number };
export type OriginSeriesId = "recorded" | OriginModelId;
export type OriginPlot = { series: Record<OriginSeriesId,(OriginPlotPoint | null)[]>; originAvailable: boolean; domain: {centerX:number;centerY:number;span:number} };
export function originPlot(envelope: OriginEnvelope, groupId: string): OriginPlot | null {
  const index = ORIGIN_GROUPS.findIndex(id => id === groupId); if (index < 0) return null;
  const group = envelope.report.scores.groups[index], forecast = envelope.forecasts.groups[index];
  const recorded = group.candidates[0].cells.map(cell => cell.target_latitude_deg === null ? null : {time_utc:cell.time_utc,latitude_deg:cell.target_latitude_deg,longitude_deg:cell.target_longitude_deg!});
  const origin = forecast.origin_position ?? recorded.find(point => point !== null) ?? forecast.candidates.flatMap(row => row.cells).find(cell => cell.forecast_status === "AVAILABLE");
  if (!origin || origin.latitude_deg === null || origin.longitude_deg === null) return null;
  const latitude = origin.latitude_deg, longitude = origin.longitude_deg;
  const project = (point: OriginGeo | null, hour: number): OriginPlotPoint | null => {
    if (!point) return null;
    const delta = (point.longitude_deg - longitude) * Math.PI / 180;
    return {...point,hour,x_m:6371008.8 * Math.cos(latitude * Math.PI / 180) * Math.atan2(Math.sin(delta),Math.cos(delta)),y_m:6371008.8 * (point.latitude_deg - latitude) * Math.PI / 180};
  };
  const series = {recorded:[project(forecast.origin_position,0),...recorded.map((point,index) => project(point,index + 1))]} as OriginPlot["series"];
  for (const [index,id] of ORIGIN_MODELS.entries()) series[id] = [project(forecast.origin_position,0),...forecast.candidates[index].cells.map((cell,index) => project(cell.forecast_status === "AVAILABLE" ? {time_utc:cell.time_utc,latitude_deg:cell.latitude_deg!,longitude_deg:cell.longitude_deg!} : null,index + 1))];
  const points = Object.values(series).flat().filter((point): point is OriginPlotPoint => point !== null);
  const xs = points.map(point => point.x_m), ys = points.map(point => point.y_m);
  return {series,originAvailable:forecast.origin_position !== null,domain:{centerX:(Math.min(...xs)+Math.max(...xs))/2,centerY:(Math.min(...ys)+Math.max(...ys))/2,span:Math.max(100,Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys))*1.18}};
}
export function originSegments(points: (OriginPlotPoint | null)[]): OriginPlotPoint[][] {
  const segments: OriginPlotPoint[][] = []; let current: OriginPlotPoint[] = [];
  for (const point of points) { if (!point || current.length && point.hour !== current.at(-1)!.hour + 1) { if (current.length) segments.push(current); current = []; } if (point) current.push(point); }
  if (current.length) segments.push(current); return segments;
}
export function originDisplacement(points: (OriginPlotPoint | null)[], hour: number): [OriginPlotPoint,OriginPlotPoint] | null {
  if (!Number.isInteger(hour) || hour < 1 || hour > 6) return null;
  const from = points[hour - 1], to = points[hour]; return from && to && from.hour === hour - 1 && to.hour === hour ? [from,to] : null;
}

export function originQuestion(question: string, envelope: OriginEnvelope) {
  const text = question.trim(); if (!text || text.length > 2000) throw new Error("Enter a research question of one to two thousand characters.");
  return {question:text,report_sha256:envelope.artifact_identity.report_sha256,protocol_sha256:envelope.artifact_identity.protocol_sha256,identity_sha256:envelope.artifact_identity.identity_sha256};
}
export type OriginRequestTicket = { controller: AbortController; generation: number };
/** Own a bounded user-initiated read; obsolete generations can never publish. */
export function createOriginRequestGate() {
  let active: OriginRequestTicket | null = null, generation = 0, disposed = false;
  const owns = (ticket: OriginRequestTicket) => !disposed && active === ticket && ticket.generation === generation;
  function cancel() { generation++; active?.controller.abort(); active = null; }
  return {
    begin(): OriginRequestTicket | null { if (disposed || active) return null; active = {controller:new AbortController(),generation:++generation}; return active; },
    owns,
    current: (ticket: OriginRequestTicket) => owns(ticket) && !ticket.controller.signal.aborted,
    finish(ticket: OriginRequestTicket) { if (owns(ticket)) active = null; },
    cancel,
    dispose() { if (disposed) return; cancel(); disposed = true; },
  };
}
export function validateOriginAnswer(value: unknown, selected: OriginEnvelope): OriginAnswer {
  if (!object(value) || !bounded(value) || value.schema_version !== 1 || value.kind !== "ORIGIN_RESIDUAL_RESEARCH_INVESTIGATION" || value.scope !== "READ_ONLY_POST_OUTCOME_EXPLORATORY_DIAGNOSTIC" || value.analysis_scope !== ORIGIN_SCOPE || value.previously_viewed_target_outcomes !== true || !["REPORT","STOP"].includes(value.action as string) || typeof value.explanation !== "string" || !value.explanation.trim() || value.explanation.length > 1200 || typeof value.live_model_response !== "boolean" || value.provider !== "chalk" || !Array.isArray(value.evidence_ids) || !Array.isArray(value.trace) || value.trace.length > 1 || [value.numeric_replay_verified,value.store_written,value.hardware_actuation,value.physical_validation,value.automatic_model_promotion].some(flag => flag !== false)) return fail();
  const i = selected.artifact_identity;
  if (!pins(value.artifact_identity) || canonical(value.artifact_identity) !== canonical(i) || canonical(value.research_report) !== canonical(selected.report) || value.report_sha256 !== i.report_sha256 || value.protocol_sha256 !== i.protocol_sha256 || value.identity_sha256 !== i.identity_sha256) return fail();
  const allowed = [`origin-residual-report:${i.report_sha256}`,`origin-residual-protocol:${i.protocol_sha256}`];
  if (value.evidence_ids.some(id => typeof id !== "string" || !allowed.includes(id)) || new Set(value.evidence_ids).size !== value.evidence_ids.length || value.action === "REPORT" && (!value.live_model_response || value.evidence_ids.length !== 2 || value.trace.length !== 1) || value.live_model_response && (value.trace.length !== 1 || /\p{N}/u.test(value.explanation) || [value.failure_code,value.provider_status_code,value.timeout_stage,value.model_calls_attempted].some(item => item !== undefined)) || !value.live_model_response && (value.action !== "STOP" || value.evidence_ids.length !== 0 || typeof value.failure_code !== "string" || !value.failure_code.trim())) return fail();
  if (value.failure_code !== undefined && (typeof value.failure_code !== "string" || value.failure_code.length > 200) || value.provider_status_code !== undefined && (!count(value.provider_status_code,599) || (value.provider_status_code as number) < 100) || value.timeout_stage !== undefined && (typeof value.timeout_stage !== "string" || value.timeout_stage.length > 200) || value.model_calls_attempted !== undefined && !count(value.model_calls_attempted,2)) return fail();
  for (const step of value.trace) {
    if (!object(step) || step.tool !== "get_study_evidence" || !object(step.arguments) || Object.keys(step.arguments).length || !["model_requested","server_required_after_premature_finish"].includes(step.read_origin as string) || !object(step.result) || step.result.ok !== true || !Array.isArray(step.result.evidence_ids) || canonical([...step.result.evidence_ids].sort()) !== canonical([...allowed].sort())) return fail();
    const c = step.result.origin_residual_diagnostic, s = selected.report.scores;
    if (!object(c) || c.kind !== selected.report.kind || c.study_id !== i.study_id || c.analysis_scope !== ORIGIN_SCOPE || c.previously_viewed_target_outcomes !== true || c.report_sha256 !== i.report_sha256 || c.protocol_sha256 !== i.protocol_sha256 || c.identity_sha256 !== i.identity_sha256 || canonical(c.artifact_verification) !== canonical(i) || canonical(c.source_artifact_pins) !== canonical(selected.report.source_artifact_pins) || canonical(c.source_acquisition_lineage) !== canonical(selected.report.source_acquisition_lineage) || canonical(c.method_source_sha256) !== canonical(selected.report.method_source_sha256)
      || canonical(c.coverage) !== canonical({planned_group_count:2,planned_model_track_count:8,planned_cell_count:48,scored_cell_count:s.scored_cell_count,planned_distinct_target_count:12,primary_common_cohort_complete:s.primary_common_cohort_complete}) || canonical(c.models) !== canonical(s.models) || canonical(c.primary_equal_id_macro_results) !== canonical(s.primary_equal_id_macro_results) || canonical(c.limitations) !== canonical(s.limitations) || !object(c.scientific_flags) || CLAIM_FLAGS.some(key => c.scientific_flags && (c.scientific_flags as Record<string,unknown>)[key] !== false) || !Array.isArray(c.groups) || c.groups.length !== 2) return fail();
    for (let gi = 0; gi < 2; gi++) {
      const group = c.groups[gi], actual = s.groups[gi];
      if (!object(group) || group.group_id !== actual.group_id || canonical(group.target_issues) !== canonical(actual.target_issues) || !Array.isArray(group.candidates) || group.candidates.length !== 4) return fail();
      for (let mi = 0; mi < 4; mi++) {
        const row = group.candidates[mi], source = actual.candidates[mi], forecast = selected.forecasts.groups[gi].candidates[mi];
        if (!object(row) || row.model_id !== source.model_id || row.prediction_status !== source.prediction_status || row.prediction_reason_code !== source.prediction_reason_code || canonical(row.metrics) !== canonical(source.metrics) || row.forecast_available_count !== forecast.available_count || canonical(row.residual_east_north_m_s) !== canonical(forecast.residual_east_north_m_s ?? null) || row.source_field_sha256 !== (forecast.source_field_sha256 ?? null) || row.derived_field_sha256 !== (forecast.derived_field_sha256 ?? null)) return fail();
      }
    }
    const keys = ["model_a","model_b","planned_common_cell_count","common_scored_count","coverage_complete","analysis_scope","mean_delta_a_minus_b_m"];
    if (canonical(c.paired_comparisons) !== canonical(s.paired_comparisons.map(row => Object.fromEntries(keys.map(key => [key,row[key as keyof OriginPair]])))) || !object(c.model_definition) || c.model_definition.current_depth_m !== 15 || c.model_definition.learned_parameters !== 0 || c.model_definition.source_study_changed !== false || c.model_definition.residual_transport !== "constant_local_east_north_components" || c.model_definition.solver !== "unchanged bounded knot-aligned WGS84 RK4") return fail();
  }
  return value as OriginAnswer;
}
