/** Saved earlier-position display contracts; no transport, scoring or inference. */
export const OCEAN_SOURCE_GROUPS = ["300234066836710", "300534061292930"] as const;
export const OCEAN_SOURCE_MODELS = ["stationary", "last_drift", "reverse_current"] as const;
export const OCEAN_SOURCE_LOOKBACKS = [1, 3, 6] as const;
export const OCEAN_SOURCE_STUDY = "ocean-source-gdp-hycom-15m-v1";
export const OCEAN_SOURCE_OBSERVATION = "2022-06-01T06:00:00Z";
export type OceanSourceModel = typeof OCEAN_SOURCE_MODELS[number];
export type OceanSourceGeo = { latitude_deg: number; longitude_deg: number; time_utc?: string };
export type OceanSourceTrackPoint = OceanSourceGeo & { lookback_s: number; time_utc: string };
export type OceanSourceCandidate = { model_id: OceanSourceModel; status: string; reason_code: string | null; earlier_time_utc: string; latitude_deg: number | null; longitude_deg: number | null };
export type OceanSourceScenario = { scenario_id: string; endpoint_offset_east_north_m: number[]; current_bias_east_north_m_s: number[]; status: "COMPLETED" | "PARTIAL" | "UNSUPPORTED"; reason_code: string | null; completed_lookback_s: number; track: OceanSourceTrackPoint[] };
export type OceanSourceEarlier = { lookback_hours: number; time_utc: string; planned_scenarios: 25; available_count: number; points: (OceanSourceGeo & { scenario_id: string })[] };
export type OceanSourceGroup = { group_id: string; observed_endpoint: OceanSourceGeo | null; penultimate_observation: OceanSourceGeo | null; candidates: OceanSourceCandidate[]; reverse_current: { nominal_scenario_id: string; scenarios: OceanSourceScenario[]; earlier_candidates: OceanSourceEarlier[]; coverage: { planned_scenarios: 25; completed_scenarios: number; partial_scenarios: number; unsupported_scenarios: number } }; numerical_closure: { status: string; reason_code: string | null; endpoint_distance_m: number | null; forward_track: unknown[] } };
export type OceanSourceValidationRow = { group_id: string; model_id: OceanSourceModel; status: string; reason_code: string | null; earlier_target: OceanSourceGeo | null; predicted_earlier: OceanSourceGeo | null; error_m: number | null };
export type OceanSourceValidation = { rows: OceanSourceValidationRow[]; planned_model_rows: 6; scored_model_rows: number; planned_distinct_earlier_positions: 2; primary_complete: boolean; primary_mean_earlier_position_error_m: { model_id: OceanSourceModel; group_count: 2; mean_error_m: number }[] | null; [key: string]: unknown };
export const OCEAN_PIPELINE_STEPS = ["raw","connected","filtered","formula","branches"] as const;
export type OceanPipelineState = OceanSourceGeo & { east_m:number; north_m:number; eastward_m_s:number|null; northward_m_s:number|null; status:"POSITION_ONLY"|"INITIALIZED"|"UPDATED"; covariance:number[][]|null };
export type OceanPipelineGroup = {group_id:string;status:string;reason_code:string|null;raw_observations:OceanSourceGeo[];connected_path:OceanSourceGeo[];filtered_states:OceanPipelineState[];filtered_anchor:OceanSourceGeo|null;formula:{equation:"dX/dt = u(X,t) + b";current_east_north_m_s:number[]|null;filtered_velocity_east_north_m_s:number[]|null;residual_bias_east_north_m_s:number[]|null}|null;backward:{status:string;reason_code:string|null;track:OceanSourceTrackPoint[];completed_lookback_s:number};forward:{status:string;reason_code:string|null;track:(OceanSourceGeo&{elapsed_s:number})[];completed_horizon_s:number}};
export type OceanPipelineRow = {group_id:string;direction:"backward"|"forward";time_utc:string;status:string;reason_code:string|null;observed:OceanSourceGeo|null;predicted:OceanSourceGeo|null;error_m:number|null};
export type OceanPipeline = {kind:"THREE_FIX_BIDIRECTIONAL_RESEARCH_WALKTHROUGH";forecasts:{group_ids:string[];observation_times_utc:string[];anchor_time_utc:string;earlier_truth_used:false;later_truth_used:false;position_std_m:100;acceleration_spectral_density_m2_s3:number;stages:{id:typeof OCEAN_PIPELINE_STEPS[number];title:string;formula:string}[];groups:OceanPipelineGroup[];limitations:string[]};validation:{planned_rows:8;scored_rows:number;rows:OceanPipelineRow[];physical_validation:false;statistical_independence:false}};
export type OceanSourceReport = { schema_version: 1; kind: "OCEAN_SOURCE_EXPLORATORY_RESULT"; study_id: typeof OCEAN_SOURCE_STUDY; analysis_scope: "POST_OUTCOME_EXPLORATORY"; previously_viewed_earlier_positions: true; protocol_sha256: string; forecast_file_sha256: string; forecasts: { groups: OceanSourceGroup[]; [key: string]: unknown }; validation: OceanSourceValidation; pipeline_tutorial?:OceanPipeline; limitations?: string[]; flags?: Record<string,unknown>; provider_calls?: false; physical_validation?: false; source_attribution_validated?: false; [key: string]: unknown };
export type OceanSourceIdentity = { schema_version: 1; kind: "OCEAN_SOURCE_RESULT_IDENTITY"; study_id: typeof OCEAN_SOURCE_STUDY; identity_sha256: string; report_sha256: string; protocol_sha256: string; forecast_file_sha256: string; pipeline_forecast_file_sha256?:string; integrity_verified: true; external_result_pin_verified: true; numeric_replay_verified: false; externally_trusted_pin_required_for_publication: true; verification_scope: "SAVED_BYTES_AND_LINEAGE_NOT_NUMERIC_REPLAY" };
export type OceanSourceEnvelope = { report: OceanSourceReport; artifact_identity: OceanSourceIdentity };
export type OceanSourceAnswer = { schema_version: 1; kind: "OCEAN_SOURCE_RESEARCH_INVESTIGATION"; scope: "READ_ONLY_POST_OUTCOME_EARLIER_POSITION_DIAGNOSTIC"; analysis_scope: "POST_OUTCOME_EXPLORATORY"; previously_viewed_earlier_positions: true; action: "REPORT" | "STOP"; explanation: string; evidence_ids: string[]; trace: unknown[]; provider: "chalk"; live_model_response: boolean; research_report: OceanSourceReport; artifact_identity: OceanSourceIdentity; report_sha256: string; protocol_sha256: string; identity_sha256: string; failure_code?: string; provider_status_code?: number; timeout_stage?: string; model_calls_attempted?: number; [key: string]: unknown };

const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value);
const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const nonnegative = (value: unknown): value is number => finite(value) && value >= 0;
const count = (value: unknown, maximum: number): value is number => nonnegative(value) && Number.isInteger(value) && value <= maximum;
const hash = (value: unknown) => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
const reason = (value: unknown) => value === null || typeof value === "string" && value.length > 0 && value.length <= 2000;
const geo = (value: unknown): value is OceanSourceGeo => object(value) && finite(value.latitude_deg) && Math.abs(value.latitude_deg) <= 90 && finite(value.longitude_deg) && Math.abs(value.longitude_deg) <= 180;
const pair = (value: unknown) => Array.isArray(value) && value.length === 2 && value.every(finite);
const fail = (): never => { throw new Error("The ocean earlier-position report has incompatible identities, geometry or evidence. No result was accepted."); };
function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (object(value)) return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  return JSON.stringify(value);
}
function bounded(value: unknown, depth = 0, budget = { nodes: 0 }): boolean {
  if (++budget.nodes > 100_000 || depth > 20) return false;
  if (Array.isArray(value)) return value.length <= 5000 && value.every(item => bounded(item, depth + 1, budget));
  if (object(value)) return Object.keys(value).length <= 100 && Object.values(value).every(item => bounded(item, depth + 1, budget));
  return value === null || typeof value === "boolean" || finite(value) || typeof value === "string" && value.length <= 16000;
}
function conservative(value: unknown): boolean {
  const flags = new Set(["physical_validation", "source_attribution_validated", "automatic_model_promotion", "automatic_winner_selected", "statistical_independence", "plastic_motion_validated", "operational_forecast_skill_verified", "calibrated_confidence", "probability_calibrated", "earlier_truth_used_for_inference", "earlier_truth_used", "later_truth_used"]);
  if (Array.isArray(value)) return value.every(conservative);
  return !object(value) || Object.entries(value).every(([key,item]) => (!flags.has(key) || item === false) && conservative(item));
}
function time(value: unknown): number | null {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(value)) return null;
  const parsed = Date.parse(value), expected = value.replace(/(?:\.\d+)?(?:Z|\+00:00)$/, ".000Z");
  return Number.isFinite(parsed) && new Date(parsed).toISOString().slice(0,19) === expected.slice(0,19) ? parsed : null;
}
const earlierTime = (hours: number) => new Date(Date.parse(OCEAN_SOURCE_OBSERVATION) - hours * 3600_000).toISOString().replace(".000Z", "Z");
function identity(value: unknown): value is OceanSourceIdentity {
  return object(value) && value.schema_version === 1 && value.kind === "OCEAN_SOURCE_RESULT_IDENTITY" && value.study_id === OCEAN_SOURCE_STUDY
    && [value.identity_sha256,value.report_sha256,value.protocol_sha256,value.forecast_file_sha256].every(hash)
    && (value.pipeline_forecast_file_sha256 === undefined || hash(value.pipeline_forecast_file_sha256))
    && value.integrity_verified === true && value.external_result_pin_verified === true && value.numeric_replay_verified === false
    && value.externally_trusted_pin_required_for_publication === true && value.verification_scope === "SAVED_BYTES_AND_LINEAGE_NOT_NUMERIC_REPLAY";
}

function validatePipeline(pipeline: OceanPipeline) {
  const anchor = "2022-06-01T03:00:00Z", start = Date.parse(anchor), earlier = earlierTime(6);
  if (!object(pipeline) || pipeline.kind !== "THREE_FIX_BIDIRECTIONAL_RESEARCH_WALKTHROUGH" || !object(pipeline.forecasts) || !object(pipeline.validation)) fail();
  const forecast = pipeline.forecasts, validation = pipeline.validation;
  if (canonical(forecast.group_ids) !== canonical(OCEAN_SOURCE_GROUPS) || forecast.anchor_time_utc !== anchor || canonical(forecast.observation_times_utc) !== canonical([earlierTime(5),earlierTime(4),anchor]) || forecast.earlier_truth_used !== false || forecast.later_truth_used !== false || forecast.position_std_m !== 100 || forecast.acceleration_spectral_density_m2_s3 !== 1e-6 || !Array.isArray(forecast.stages) || forecast.stages.length !== 5 || !Array.isArray(forecast.groups) || forecast.groups.length !== 2 || !Array.isArray(forecast.limitations) || !forecast.limitations.every(item => typeof item === "string")) fail();
  forecast.stages.forEach((stage,index) => { if (!object(stage) || stage.id !== OCEAN_PIPELINE_STEPS[index] || typeof stage.title !== "string" || typeof stage.formula !== "string") fail(); });
  for (const [index,group] of forecast.groups.entries()) {
    if (!object(group) || group.group_id !== OCEAN_SOURCE_GROUPS[index] || !["COMPLETED","PARTIAL","UNSUPPORTED"].includes(group.status) || !reason(group.reason_code) || !Array.isArray(group.raw_observations) || group.raw_observations.length > 3 || group.raw_observations.some((point,index) => !geo(point) || point.time_utc !== forecast.observation_times_utc[index]) || canonical(group.connected_path) !== canonical(group.raw_observations) || !Array.isArray(group.filtered_states) || group.filtered_states.length > 3 || !object(group.backward) || !object(group.forward)) fail();
    group.filtered_states.forEach((state,index) => {
      if (!geo(state) || state.time_utc !== forecast.observation_times_utc[index] || !finite(state.east_m) || !finite(state.north_m) || state.status !== ["POSITION_ONLY","INITIALIZED","UPDATED"][index]) fail();
      if (index === 0 ? state.eastward_m_s !== null || state.northward_m_s !== null || state.covariance !== null : !finite(state.eastward_m_s) || !finite(state.northward_m_s) || !Array.isArray(state.covariance) || state.covariance.length !== 4 || state.covariance.some(row => !Array.isArray(row) || row.length !== 4 || !row.every(finite))) fail();
    });
    if (group.raw_observations.length !== group.filtered_states.length || group.status === "COMPLETED" && (group.raw_observations.length !== 3 || group.reason_code !== null || group.formula === null || group.backward.status !== "COMPLETED" || group.forward.status !== "COMPLETED") || group.status !== "COMPLETED" && typeof group.reason_code !== "string") fail();
    if (group.filtered_anchor !== null && (!geo(group.filtered_anchor) || group.filtered_anchor.time_utc !== anchor || group.filtered_states.length !== 3 || group.filtered_anchor.latitude_deg !== group.filtered_states[2].latitude_deg || group.filtered_anchor.longitude_deg !== group.filtered_states[2].longitude_deg)) fail();
    if (group.formula !== null) {
      const formula = group.formula, state = group.filtered_states.at(-1);
      if (!state) return fail();
      if (!object(formula) || formula.equation !== "dX/dt = u(X,t) + b" || !group.filtered_anchor || [formula.current_east_north_m_s,formula.filtered_velocity_east_north_m_s,formula.residual_bias_east_north_m_s].some(value => !pair(value))) fail();
      const current = formula.current_east_north_m_s!, velocity = formula.filtered_velocity_east_north_m_s!, bias = formula.residual_bias_east_north_m_s!;
      if (velocity[0] !== state.eastward_m_s || velocity[1] !== state.northward_m_s || bias.some((value,index) => Math.abs(value-(velocity[index]-current[index]))>1e-12)) fail();
    }
    for (const direction of ["backward","forward"] as const) {
      const branch = group[direction], duration = direction === "backward" ? group.backward.completed_lookback_s : group.forward.completed_horizon_s;
      if (!object(branch) || !["COMPLETED","PARTIAL","UNSUPPORTED"].includes(branch.status) || !reason(branch.reason_code) || !nonnegative(duration) || duration > 10800 || !Array.isArray(branch.track) || branch.track.length > 38 || branch.status === "COMPLETED" && (duration !== 10800 || branch.reason_code !== null) || branch.status !== "COMPLETED" && typeof branch.reason_code !== "string") fail();
      let previous = -1;
      for (const point of branch.track) {
        const elapsed = direction === "backward" ? (point as OceanSourceTrackPoint).lookback_s : (point as OceanSourceGeo&{elapsed_s:number}).elapsed_s;
        const clock = time(point.time_utc);
        if (!geo(point) || !nonnegative(elapsed) || elapsed <= previous || elapsed > duration || clock === null || Math.abs(clock-(start + (direction === "backward" ? -1 : 1)*elapsed*1000)) >= 1) fail();
        previous = elapsed;
      }
      if (branch.status === "UNSUPPORTED" && duration !== 0 || branch.status === "PARTIAL" && !(duration>0 && duration<10800) || duration > 0 && previous !== duration) fail();
      if (branch.track.length) {
        const first = branch.track[0], filtered = group.filtered_anchor;
        if (time(first.time_utc) !== start || !filtered || !group.formula || first.latitude_deg !== filtered.latitude_deg || first.longitude_deg !== filtered.longitude_deg) fail();
      }
    }
  }
  if (validation.planned_rows !== 8 || !count(validation.scored_rows,8) || validation.physical_validation !== false || validation.statistical_independence !== false || !Array.isArray(validation.rows) || validation.rows.length !== 8) fail();
  let scored = 0;
  validation.rows.forEach((row,index) => {
    const group = forecast.groups[Math.floor(index/4)], offset = index%4, direction = offset === 0 ? "backward" : "forward", timestamp = offset === 0 ? earlier : new Date(start+offset*3600_000).toISOString().replace(".000Z","Z");
    if (!object(row) || row.group_id !== group.group_id || row.direction !== direction || row.time_utc !== timestamp || !reason(row.reason_code) || row.observed !== null && (!geo(row.observed) || row.observed.time_utc !== timestamp) || row.predicted !== null && (!geo(row.predicted) || row.predicted.time_utc !== timestamp)) fail();
    const point = group[direction].track.find(point => point.time_utc === timestamp);
    const status = !row.observed ? "TRUTH_UNAVAILABLE" : !point ? "FORECAST_UNAVAILABLE" : "SCORED";
    if (status === "SCORED" ? !row.predicted || !point || row.predicted.latitude_deg !== point.latitude_deg || row.predicted.longitude_deg !== point.longitude_deg : row.predicted !== null) fail();
    if (row.status !== status || (status === "SCORED" ? !nonnegative(row.error_m) || row.reason_code !== null : row.error_m !== null || typeof row.reason_code !== "string")) fail();
    if (status === "SCORED") scored++;
  });
  if (scored !== validation.scored_rows) fail();
}

export function validateOceanSourceEnvelope(value: unknown): OceanSourceEnvelope {
  if (!object(value) || !bounded(value) || !conservative(value) || canonical(Object.keys(value).sort()) !== canonical(["artifact_identity","report"]) || !object(value.report) || !identity(value.artifact_identity)) return fail();
  const envelope = value as OceanSourceEnvelope, report = envelope.report, forecast = report.forecasts, pin = envelope.artifact_identity, flags = report.flags ?? report;
  if (report.schema_version !== 1 || report.kind !== "OCEAN_SOURCE_EXPLORATORY_RESULT" || report.study_id !== OCEAN_SOURCE_STUDY || report.analysis_scope !== "POST_OUTCOME_EXPLORATORY" || report.previously_viewed_earlier_positions !== true || report.protocol_sha256 !== pin.protocol_sha256 || report.forecast_file_sha256 !== pin.forecast_file_sha256 || [flags.provider_calls,flags.physical_validation,flags.source_attribution_validated,flags.automatic_model_promotion].some(flag => flag !== false)
    || !Array.isArray(report.limitations) || !report.limitations.length || !report.limitations.every(text => typeof text === "string" && text.length > 0)
    || !object(forecast) || forecast.schema_version !== 1 || forecast.kind !== "OCEAN_SOURCE_BACKTRACKING_FORECASTS" || forecast.study_id !== OCEAN_SOURCE_STUDY || forecast.analysis_scope !== "POST_OUTCOME_EXPLORATORY" || forecast.previously_viewed_earlier_positions !== true || forecast.observation_time_utc !== OCEAN_SOURCE_OBSERVATION || forecast.earlier_time_utc !== earlierTime(6) || !hash(forecast.forecast_sha256)
    || canonical(forecast.model_ids) !== canonical(OCEAN_SOURCE_MODELS) || canonical(forecast.group_ids) !== canonical(OCEAN_SOURCE_GROUPS) || canonical(forecast.lookback_hours) !== canonical(OCEAN_SOURCE_LOOKBACKS) || forecast.planned_model_rows !== 6 || forecast.planned_distinct_earlier_positions !== 2 || forecast.scenarios_per_group !== 25 || forecast.inference_uses_only_last_two_positions !== true || forecast.earlier_truth_used !== false || !Array.isArray(forecast.groups) || forecast.groups.length !== 2) return fail();
  const statuses = ["COMPLETED","PARTIAL","UNSUPPORTED"];
  for (const [index,group] of forecast.groups.entries()) {
    if (!object(group) || group.group_id !== OCEAN_SOURCE_GROUPS[index] || group.observed_endpoint !== null && (!geo(group.observed_endpoint) || group.observed_endpoint.time_utc !== OCEAN_SOURCE_OBSERVATION) || group.penultimate_observation !== null && (!geo(group.penultimate_observation) || group.penultimate_observation.time_utc !== earlierTime(1)) || !Array.isArray(group.candidates) || group.candidates.length !== 3 || !object(group.reverse_current)) return fail();
    group.candidates.forEach((row,index) => {
      if (!object(row) || row.model_id !== OCEAN_SOURCE_MODELS[index] || !statuses.includes(row.status) || !reason(row.reason_code) || row.earlier_time_utc !== earlierTime(6)
        || (row.status === "COMPLETED" ? !geo(row) || row.reason_code !== null : row.latitude_deg !== null || row.longitude_deg !== null || typeof row.reason_code !== "string")) fail();
    });
    const reverse = group.reverse_current;
    if (reverse.nominal_scenario_id !== "center|zero" || !Array.isArray(reverse.scenarios) || reverse.scenarios.length !== 25 || new Set(reverse.scenarios.map(row => row.scenario_id)).size !== 25 || !Array.isArray(reverse.earlier_candidates) || reverse.earlier_candidates.length !== 3 || !object(reverse.coverage) || reverse.coverage.planned_scenarios !== 25) return fail();
    for (const scenario of reverse.scenarios) {
      if (!object(scenario) || typeof scenario.scenario_id !== "string" || !scenario.scenario_id || scenario.scenario_id.length > 100 || !pair(scenario.endpoint_offset_east_north_m) || !pair(scenario.current_bias_east_north_m_s) || !statuses.includes(scenario.status) || !reason(scenario.reason_code) || !nonnegative(scenario.completed_lookback_s) || scenario.completed_lookback_s > 21600 || !Array.isArray(scenario.track) || scenario.track.length > 74) return fail();
      let previous = -1;
      for (const point of scenario.track) {
        const clock = time(point.time_utc);
        if (!geo(point) || !nonnegative(point.lookback_s) || point.lookback_s > scenario.completed_lookback_s || point.lookback_s <= previous || clock === null || Math.abs(clock-(Date.parse(OCEAN_SOURCE_OBSERVATION)-point.lookback_s*1000)) >= 1) return fail();
        previous = point.lookback_s;
      }
      if (scenario.status === "COMPLETED" ? scenario.completed_lookback_s !== 21600 || scenario.reason_code !== null || previous !== 21600 : typeof scenario.reason_code !== "string" || scenario.status === "UNSUPPORTED" && scenario.completed_lookback_s !== 0 || scenario.status === "PARTIAL" && !(scenario.completed_lookback_s > 0 && scenario.completed_lookback_s < 21600)) return fail();
      if (scenario.track.length && scenario.track[0].lookback_s !== 0 || scenario.completed_lookback_s > 0 && previous !== scenario.completed_lookback_s) return fail();
    }
    const nominal = reverse.scenarios.find(row => row.scenario_id === reverse.nominal_scenario_id);
    if (!nominal || canonical(nominal.endpoint_offset_east_north_m) !== "[0,0]" || canonical(nominal.current_bias_east_north_m_s) !== "[0,0]") return fail();
    const current = group.candidates[2], last = nominal.track.at(-1);
    if (current.status !== nominal.status || current.reason_code !== nominal.reason_code || current.status === "COMPLETED" && (!last || current.latitude_deg !== last.latitude_deg || current.longitude_deg !== last.longitude_deg)) return fail();
    for (const [index,earlier] of reverse.earlier_candidates.entries()) {
      const hours = OCEAN_SOURCE_LOOKBACKS[index], expected = reverse.scenarios.flatMap(row => row.track.filter(point => point.lookback_s === hours*3600).map(point => ({scenario_id:row.scenario_id,latitude_deg:point.latitude_deg,longitude_deg:point.longitude_deg})));
      if (!object(earlier) || earlier.lookback_hours !== hours || earlier.time_utc !== earlierTime(hours) || earlier.planned_scenarios !== 25 || earlier.available_count !== expected.length || !Array.isArray(earlier.points) || earlier.points.length !== expected.length || new Set(earlier.points.map(point => point.scenario_id)).size !== expected.length) return fail();
      for (const point of earlier.points) { const matched = expected.find(row => row.scenario_id === point.scenario_id); if (!geo(point) || !matched || point.latitude_deg !== matched.latitude_deg || point.longitude_deg !== matched.longitude_deg) return fail(); }
    }
    for (const [key,status] of [["completed_scenarios","COMPLETED"],["partial_scenarios","PARTIAL"],["unsupported_scenarios","UNSUPPORTED"]] as const) if (reverse.coverage[key] !== reverse.scenarios.filter(row => row.status === status).length) return fail();
    const closure = group.numerical_closure;
    if (!object(closure) || typeof closure.status !== "string" || !reason(closure.reason_code) || closure.endpoint_distance_m !== null && !nonnegative(closure.endpoint_distance_m) || !Array.isArray(closure.forward_track) || closure.forward_track.length > 74) return fail();
  }
  const validation = report.validation;
  if (!object(validation) || validation.planned_model_rows !== 6 || validation.planned_distinct_earlier_positions !== 2 || !count(validation.scored_model_rows,6) || validation.primary_complete !== (validation.scored_model_rows === 6) || !Array.isArray(validation.rows) || validation.rows.length !== 6) return fail();
  let scored = 0;
  for (const [index,row] of validation.rows.entries()) {
    const group = forecast.groups[Math.floor(index/3)], prediction = group.candidates[index%3];
    if (!object(row) || row.group_id !== group.group_id || row.model_id !== prediction.model_id || !reason(row.reason_code) || row.earlier_target !== null && (!geo(row.earlier_target) || row.earlier_target.time_utc !== earlierTime(6)) || row.predicted_earlier !== null && (!geo(row.predicted_earlier) || row.predicted_earlier.time_utc !== earlierTime(6))) return fail();
    const expectedStatus = prediction.status !== "COMPLETED" ? "FORECAST_UNAVAILABLE" : row.earlier_target === null ? "TRUTH_UNAVAILABLE" : "SCORED";
    if (row.status !== expectedStatus || (expectedStatus === "SCORED" ? !nonnegative(row.error_m) : row.error_m !== null) || (prediction.status === "COMPLETED" ? !row.predicted_earlier || row.predicted_earlier.latitude_deg !== prediction.latitude_deg || row.predicted_earlier.longitude_deg !== prediction.longitude_deg : row.predicted_earlier !== null)) return fail();
    const peer = validation.rows[Math.floor(index/3)*3];
    if (canonical(row.earlier_target) !== canonical(peer.earlier_target)) return fail();
    if (row.status === "SCORED") scored++;
  }
  if (scored !== validation.scored_model_rows) return fail();
  if (scored === 6) {
    if (!Array.isArray(validation.primary_mean_earlier_position_error_m) || validation.primary_mean_earlier_position_error_m.length !== 3) return fail();
    validation.primary_mean_earlier_position_error_m.forEach((row,index) => { if (!object(row) || row.model_id !== OCEAN_SOURCE_MODELS[index] || row.group_count !== 2 || !nonnegative(row.mean_error_m)) fail(); });
  } else if (validation.primary_mean_earlier_position_error_m !== null) return fail();
  if (report.pipeline_tutorial !== undefined) {
    validatePipeline(report.pipeline_tutorial);
    if (canonical(forecast.pipeline_tutorial) !== canonical(report.pipeline_tutorial.forecasts)) return fail();
    if (report.pipeline_forecast_file_sha256 !== pin.pipeline_forecast_file_sha256) return fail();
  }
  return envelope;
}

export type OceanSourcePlotPoint = OceanSourceGeo & { x_m: number; y_m: number; lookback_s?: number };
export type OceanSourcePlot = { observation: OceanSourcePlotPoint; scenarios: { scenario_id: string; points: OceanSourcePlotPoint[] }[]; earlier: { lookback_hours: number; points: (OceanSourcePlotPoint & { scenario_id: string })[] }[]; validation: (OceanSourceValidationRow & { target_point: OceanSourcePlotPoint | null; prediction_point: OceanSourcePlotPoint | null })[]; domain: { centerX: number; centerY: number; span: number } };

/** A display projection only; saved great-circle errors remain authoritative. */
export function oceanSourcePlot(envelope: OceanSourceEnvelope, groupId: string): OceanSourcePlot | null {
  const group = envelope.report.forecasts.groups.find(row => row.group_id === groupId);
  if (!group || !group.observed_endpoint) return null;
  const origin = group.observed_endpoint;
  const project = <T extends OceanSourceGeo>(point: T): T & OceanSourcePlotPoint => {
    const angle = (point.longitude_deg-origin.longitude_deg)*Math.PI/180;
    return {...point,x_m:6371008.8*Math.cos(origin.latitude_deg*Math.PI/180)*Math.atan2(Math.sin(angle),Math.cos(angle)),y_m:6371008.8*(point.latitude_deg-origin.latitude_deg)*Math.PI/180};
  };
  const observation = project(origin);
  const scenarios = group.reverse_current.scenarios.map(row => ({scenario_id:row.scenario_id,points:row.track.map(project)}));
  const earlier = group.reverse_current.earlier_candidates.map(row => ({lookback_hours:row.lookback_hours,points:row.points.map(project)}));
  const validation = envelope.report.validation.rows.filter(row => row.group_id === groupId).map(row => ({...row,target_point:row.earlier_target ? project(row.earlier_target) : null,prediction_point:row.predicted_earlier ? project(row.predicted_earlier) : null}));
  // Include every saved comparison layer, even hidden validation, to keep the
  // display scale fixed. This does not feed validation truth into inference.
  const points = [observation,...scenarios.flatMap(row => row.points),...earlier.flatMap(row => row.points),...validation.flatMap(row => [row.target_point,row.prediction_point]).filter((point): point is OceanSourcePlotPoint => point !== null)];
  const xs = points.map(point => point.x_m), ys = points.map(point => point.y_m);
  return {observation,scenarios,earlier,validation,domain:{centerX:(Math.min(...xs)+Math.max(...xs))/2,centerY:(Math.min(...ys)+Math.max(...ys))/2,span:Math.max(100,Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys))*1.16}};
}

/** Missing samples remain open; never bridge a gap to make a smoother path. */
export function oceanSourceSegments<T extends { lookback_s?: number }>(points: (T | null)[], maximumGapS = 300): T[][] {
  const segments: T[][] = []; let current: T[] = [];
  for (const point of points) {
    const previous = current.at(-1), gap = point && previous && finite(point.lookback_s) && finite(previous.lookback_s) ? point.lookback_s-previous.lookback_s : 0;
    if (!point || gap <= 0 && previous || gap > maximumGapS) { if (current.length) segments.push(current); current = []; }
    if (point) current.push(point);
  }
  if (current.length) segments.push(current);
  return segments;
}

export function oceanPipelinePlot(pipeline: OceanPipeline, groupId: string) {
  const group = pipeline.forecasts.groups.find(row => row.group_id === groupId);
  const origin = group?.filtered_anchor ?? group?.raw_observations[0];
  if (!group || !origin) return null;
  const project = <T extends OceanSourceGeo>(point:T):T&OceanSourcePlotPoint => {
    const longitude = (point.longitude_deg-origin.longitude_deg)*Math.PI/180;
    return {...point,x_m:6371008.8*Math.cos(origin.latitude_deg*Math.PI/180)*Math.atan2(Math.sin(longitude),Math.cos(longitude)),y_m:6371008.8*(point.latitude_deg-origin.latitude_deg)*Math.PI/180};
  };
  const earlier = Date.parse(pipeline.forecasts.observation_times_utc[0]);
  const sampled = <T extends OceanSourceGeo>(point:T) => ({...project(point),lookback_s:(Date.parse(point.time_utc!)-earlier)/1000});
  const raw = group.raw_observations.map(sampled), filtered = group.filtered_states.map(sampled);
  const backward = group.backward.track.map(project), forward = group.forward.track.map(point => ({...project(point),lookback_s:point.elapsed_s}));
  const validation = pipeline.validation.rows.filter(row => row.group_id === groupId).map(row => ({...row,point:row.observed ? project(row.observed) : null}));
  const points = [...raw,...filtered,...backward,...forward,...validation.map(row => row.point).filter((point):point is OceanSourcePlotPoint => point !== null)];
  const xs = points.map(point => point.x_m), ys = points.map(point => point.y_m);
  return {raw,filtered,backward,forward,validation,domain:{centerX:(Math.min(...xs)+Math.max(...xs))/2,centerY:(Math.min(...ys)+Math.max(...ys))/2,span:Math.max(100,Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys))*1.2}};
}

/** Five saved stages, one finite pass. No physics, network or background work. */
export function createOceanPipelinePlayback({schedule,cancel,onStep,onPlaying}:{schedule:(callback:()=>void,delayMs:number)=>number;cancel:(id:number)=>void;onStep:(index:number)=>void;onPlaying:(playing:boolean)=>void}) {
  let generation = 0, pending:number|null = null, index = 0, playing = false, disposed = false;
  const clear = () => { generation++; if (pending !== null) cancel(pending); pending = null; };
  function pause() { clear(); if (playing && !disposed) { playing = false; onPlaying(false); } }
  function queue() {
    const current = generation;
    pending = schedule(() => {
      if (disposed || !playing || current !== generation) return;
      pending = null; index++; onStep(index);
      if (disposed || !playing || current !== generation) return;
      if (index === 4) { playing = false; onPlaying(false); }
      else queue();
    },2800);
  }
  return {
    start(from:number) {
      if (disposed || playing || !Number.isInteger(from) || from < 0 || from > 4) return false;
      clear(); index = from === 4 ? 0 : from; playing = true; onStep(index); onPlaying(true); queue(); return true;
    },
    select(next:number) { if (disposed || !Number.isInteger(next) || next < 0 || next > 4) return false; pause(); index = next; onStep(index); return true; },
    pause,
    dispose() { if (disposed) return; clear(); playing = false; disposed = true; },
  };
}

export function oceanSourceQuestion(question: string, envelope: OceanSourceEnvelope) {
  const text = question.trim(); if (!text || text.length > 2000) throw new Error("Enter a research question of one to two thousand characters.");
  const pin = envelope.artifact_identity;
  return {question:text,report_sha256:pin.report_sha256,protocol_sha256:pin.protocol_sha256,identity_sha256:pin.identity_sha256};
}

export type OceanSourceTicket = { controller: AbortController; generation: number };
export function createOceanSourceRequests() {
  let active: OceanSourceTicket | null = null, generation = 0, disposed = false;
  const owns = (ticket: OceanSourceTicket) => !disposed && active === ticket && ticket.generation === generation;
  function cancel() { generation++; active?.controller.abort(); active = null; }
  return {
    begin(): OceanSourceTicket | null { if (disposed || active) return null; active = {controller:new AbortController(),generation:++generation}; return active; },
    owns, current:(ticket:OceanSourceTicket) => owns(ticket) && !ticket.controller.signal.aborted,
    finish(ticket:OceanSourceTicket) { if (owns(ticket)) active = null; }, cancel,
    dispose() { if (disposed) return; cancel(); disposed = true; },
  };
}

export function validateOceanSourceAnswer(value: unknown, envelope: OceanSourceEnvelope): OceanSourceAnswer {
  if (!object(value) || !bounded(value) || !conservative(value) || value.schema_version !== 1 || value.kind !== "OCEAN_SOURCE_RESEARCH_INVESTIGATION" || value.scope !== "READ_ONLY_POST_OUTCOME_EARLIER_POSITION_DIAGNOSTIC" || value.analysis_scope !== "POST_OUTCOME_EXPLORATORY" || value.previously_viewed_earlier_positions !== true || !["REPORT","STOP"].includes(value.action as string) || typeof value.explanation !== "string" || !value.explanation.trim() || value.explanation.length > 1200 || value.provider !== "chalk" || typeof value.live_model_response !== "boolean" || !Array.isArray(value.trace) || value.trace.length > 1 || !Array.isArray(value.evidence_ids)
    || [value.numeric_replay_verified,value.store_written,value.hardware_actuation,value.physical_validation,value.source_attribution_validated,value.automatic_model_promotion].some(flag => flag !== false)) return fail();
  const pin = envelope.artifact_identity;
  if (!identity(value.artifact_identity) || canonical(value.artifact_identity) !== canonical(pin) || canonical(value.research_report) !== canonical(envelope.report) || value.report_sha256 !== pin.report_sha256 || value.protocol_sha256 !== pin.protocol_sha256 || value.identity_sha256 !== pin.identity_sha256) return fail();
  const evidence = [`ocean-source-report:${pin.report_sha256}`,`ocean-source-protocol:${pin.protocol_sha256}`];
  if (value.evidence_ids.some(id => typeof id !== "string" || !evidence.includes(id)) || new Set(value.evidence_ids).size !== value.evidence_ids.length || value.action === "REPORT" && (!value.live_model_response || value.evidence_ids.length !== 2 || value.trace.length !== 1)
    || value.live_model_response && (value.trace.length !== 1 || /\p{N}/u.test(value.explanation) || [value.failure_code,value.provider_status_code,value.timeout_stage,value.model_calls_attempted].some(item => item !== undefined))
    || !value.live_model_response && (value.action !== "STOP" || value.evidence_ids.length !== 0 || typeof value.failure_code !== "string" || !value.failure_code.trim())) return fail();
  if (value.failure_code !== undefined && (typeof value.failure_code !== "string" || value.failure_code.length > 200) || value.provider_status_code !== undefined && (!count(value.provider_status_code,599) || value.provider_status_code < 100) || value.model_calls_attempted !== undefined && !count(value.model_calls_attempted,2)) return fail();
  for (const step of value.trace) {
    if (!object(step) || step.tool !== "get_study_evidence" || !object(step.arguments) || Object.keys(step.arguments).length || !["model_requested","server_required_after_premature_finish"].includes(step.read_origin as string) || !object(step.result) || step.result.ok !== true || canonical(step.result.evidence_ids) !== canonical(evidence) || !object(step.result.ocean_source_diagnostic)) return fail();
    const report = step.result.ocean_source_diagnostic;
    if (report.kind !== envelope.report.kind || report.study_id !== OCEAN_SOURCE_STUDY || report.report_sha256 !== pin.report_sha256 || report.protocol_sha256 !== pin.protocol_sha256 || report.identity_sha256 !== pin.identity_sha256 || report.analysis_scope !== "POST_OUTCOME_EXPLORATORY" || report.previously_viewed_earlier_positions !== true || canonical(report.artifact_verification) !== canonical(pin) || canonical(report.separate_retrospective_validation) !== canonical(envelope.report.validation) || canonical(report.limitations) !== canonical(envelope.report.limitations) || !object(report.scientific_flags) || ["provider_calls","physical_validation","source_attribution_validated","automatic_model_promotion","calibrated_probability","numeric_replay_verified"].some(key => (report.scientific_flags as Record<string,unknown>)[key] !== false)) return fail();
    const omit = (row:object,keys:string[]) => Object.fromEntries(Object.entries(row).filter(([key]) => !keys.includes(key)));
    const forecasts = envelope.report.forecasts;
    const expectedInference = {...omit(forecasts,["groups","pipeline_tutorial"]),groups:forecasts.groups.map(group => ({
      ...omit(group,["reverse_current","numerical_closure"]),
      reverse_current:{...omit(group.reverse_current,["scenarios","earlier_candidates"]),
        scenarios:group.reverse_current.scenarios.map(row => omit(row,["track","solver"])),
        nominal_solver:(group.reverse_current.scenarios[0] as OceanSourceScenario&{solver?:unknown}).solver ?? null,
        earlier_candidates:group.reverse_current.earlier_candidates.map(row => omit(row,["points"]))},
      numerical_closure:omit(group.numerical_closure,["forward_track"]),
    }))};
    if (canonical(report.inference) !== canonical(expectedInference)) return fail();
    for (const key of ["source_artifact_pins","source_acquisition_lineage","method_source_sha256","forecast_file_sha256","forecasts_saved_before_earlier_truth_decode"]) if (envelope.report[key] !== undefined && canonical(report[key]) !== canonical(envelope.report[key])) return fail();
    if (envelope.report.pipeline_tutorial) {
      const tutorial = envelope.report.pipeline_tutorial;
      const compact = {kind:tutorial.kind,inference:{...omit(tutorial.forecasts,["groups"]),groups:tutorial.forecasts.groups.map(group => ({
        ...omit(group,["connected_path","filtered_states","backward","forward"]),
        filtered_states:group.filtered_states.map(row => omit(row,["covariance"])),
        backward:omit(group.backward,["track"]),forward:omit(group.forward,["track"]),
      }))},separate_retrospective_validation:tutorial.validation};
      if (canonical(report.pipeline_tutorial) !== canonical(compact)) return fail();
    } else if (report.pipeline_tutorial !== undefined) return fail();
  }
  return value as OceanSourceAnswer;
}
