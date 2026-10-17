import { validateOceanNumerics, type OceanNumericalSensitivity } from "./ocean-numerics-state.ts";

/** Read-only ocean comparison: real modeled forcing, hypothetical geometry and releases. */
export type OceanXY = [number, number];
export type OceanGeo = { latitude_deg: number; longitude_deg: number };
export type OceanFrame = { origin_latitude_deg: number; origin_longitude_deg: number; east_metres_per_degree: number; north_metres_per_degree: number; position_units: "m"; axes: "x east, y north"; [key: string]: unknown };
export type OceanRelease = OceanGeo & { id: string; x_m: number; y_m: number; start_time_utc: string; horizon_s: number; kind: "hypothetical_passive_tracer_not_observed_waste" };
export type OceanPoint = OceanGeo & { x_m: number; y_m: number; elapsed_s: number; time_utc: string; eastward_m_s: number; northward_m_s: number; speed_m_s: number; interpolated_event?: true };
export type OceanSegment = { id: string; start_xy_m: OceanXY; end_xy_m: OceanXY; start_geo: OceanGeo; end_geo: OceanGeo };
export type OceanZone = { id: string; label: string; polygon_xy_m: OceanXY[]; polygon_geo: OceanGeo[]; is_mapped_real_reef: false };
export type OceanOutcome = { release_id: string; status: "ENTERED_PROTECTED_ZONE" | "IDEALIZED_INTERCEPTION" | "NO_ENTRY_WITHIN_HORIZON" | "UNRESOLVED"; event: (OceanPoint & { kind: "PROTECTED_ZONE_ENTRY" | "IDEALIZED_CAPTURE"; segment_id: string | null }) | null; forcing_status: "COMPLETED" | "PARTIAL" | "UNSUPPORTED"; forcing_reason_code: string | null; requested_horizon_s: number; integrated_horizon_s: number; track_end_elapsed_s: number | null; track: OceanPoint[] };
export type OceanSummary = { release_count: number; entered_count: number; intercepted_count: number; no_entry_count: number; unresolved_count: number; protected_entry_count_bounds: [number, number]; protected_entry_fraction_bounds: [number, number]; entry_reduction_count_bounds_vs_baseline?: [number, number]; denominator_policy: string };
export type OceanLayout = { id: string; label: string; segments: OceanSegment[]; total_length_m: number; outcomes: OceanOutcome[]; summary: OceanSummary };
export type OceanRecommendation = { status: "BEST_LAYOUT" | "TIE" | "INDETERMINATE"; best_layout_id: string | null; reason: string; comparison_basis: string };
export type OceanVectorFrame = { time_utc: string; vectors: (OceanGeo & { x_m?: number; y_m?: number; eastward_m_s: number; northward_m_s: number })[] };
export type OceanPreventionReport = {
  schema_version: 1; kind: "OCEAN_PREVENTION_COMPARISON"; status: "COMPLETED" | "PARTIAL" | "UNSUPPORTED"; mode: "forecast_snapshot" | "archived_forecast_snapshot";
  snapshot_sha256: string; manifest_sha256: string; method_sha256: string; scenario_sha256: string; report_sha256: string;
  scenario: { id: string; label: string; frame: OceanFrame; start_time_utc: string; horizon_s: number; geometry_status: string; design_status: string; design_disclosure: string; protected_zone: OceanZone; releases: OceanRelease[]; layouts: { id: string; label: string; total_length_m: number; segments: OceanSegment[] }[]; resource_constraint: string; event_model: Record<string, unknown> };
  protected_zone: OceanZone; releases: OceanRelease[]; baseline: OceanLayout; layouts: OceanLayout[]; recommendation: OceanRecommendation;
  forcing: { source_url: string; metadata_url: string; product_url: string; attribution: string; captured_at_utc: string; valid_start_utc: string; valid_end_utc: string; model_issue_time_utc: string | null; depth_m: number; [key: string]: unknown };
  method: { trajectory: "dynamic_current_advection_only"; equation: string; solver: string; spatial_interpolation: string; temporal_interpolation: string; step_s: number; output_step_s: number; geometry_frame: OceanFrame; event_model: Record<string, unknown>; identical_unmodified_forcing_for_every_layout: true; paths_integrated_once_per_release: true; barriers_modify_flow: false; capture_efficiency_assumption: string; winner_rule: string };
  validation: { measured_track_available: false; physical_validation: false; plastic_motion_validated: false; forecast_skill_established: false; interception_benefit_established: false; real_reef_boundary_used: false; tank_flow_used: false; heldout_buoy_positions_used: false; measured_entry_count: null; measured_intercepted_count: null };
  numerical_sensitivity?: OceanNumericalSensitivity;
  vector_frames?: OceanVectorFrame[]; vector_speed_scale_m_s?: number; display_bounds_xy_m: { x_m: OceanXY; y_m: OceanXY }; limitations: string[];
};
export type OceanPreventionAnswer = { schema_version: 1; kind: "OCEAN_PREVENTION_INVESTIGATION"; scope: "READ_ONLY_OCEAN_PREVENTION"; scenario_id: string; action: "REPORT" | "STOP"; provider: "chalk"; live_model_response: boolean; explanation: string; evidence_ids: string[]; snapshot_sha256: string; method_sha256: string; scenario_sha256: string; report_sha256: string; research_report: OceanPreventionReport; store_written: false; physical_validation: false; hardware_actuation: false; failure_code?: string };

const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value);
const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const text = (value: unknown, max = 2000): value is string => typeof value === "string" && value.length > 0 && value.length <= max;
const hash = (value: unknown) => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
const near = (a: number, b: number, tolerance = 0.002) => Math.abs(a - b) <= tolerance;
const time = (value: unknown): value is string => typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z$/.test(value) && Number.isFinite(Date.parse(value)) && new Date(Date.parse(value)).toISOString().slice(0, 19) === value.slice(0, 19);
const geo = (value: unknown): value is OceanGeo & Record<string, unknown> => object(value) && finite(value.latitude_deg) && Math.abs(value.latitude_deg) <= 85 && finite(value.longitude_deg) && value.longitude_deg >= -180 && value.longitude_deg < 180;
const xy = (value: unknown): value is OceanXY => Array.isArray(value) && value.length === 2 && value.every(v => finite(v) && Math.abs(v) <= 100_000);
const pair = (value: unknown): value is [number, number] => Array.isArray(value) && value.length === 2 && value.every(finite);
function bounded(value: unknown, depth = 0, budget = { nodes: 0 }): boolean {
  if (++budget.nodes > 100_000 || depth > 22) return false;
  if (Array.isArray(value)) return value.length <= 2049 && value.every(v => bounded(v, depth + 1, budget));
  if (object(value)) return Object.keys(value).length <= 100 && Object.values(value).every(v => bounded(v, depth + 1, budget));
  return value === null || typeof value === "boolean" || finite(value) || typeof value === "string" && value.length <= 8000;
}
function same(a: unknown, b: unknown): boolean {
  if (Array.isArray(a) || Array.isArray(b)) return Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((item, i) => same(item, b[i]));
  if (object(a) || object(b)) return object(a) && object(b) && Object.keys(a).length === Object.keys(b).length && Object.keys(a).every(key => key in b && same(a[key], b[key]));
  return a === b;
}
const consistentPosition = (point: OceanGeo, local: OceanXY, frame: OceanFrame) => near((point.longitude_deg - frame.origin_longitude_deg) * frame.east_metres_per_degree, local[0], 0.0001) && near((point.latitude_deg - frame.origin_latitude_deg) * frame.north_metres_per_degree, local[1], 0.0001);
function point(value: unknown, release: OceanRelease, frame: OceanFrame, max: number): value is OceanPoint & Record<string, unknown> {
  if (!object(value) || !geo(value) || !finite(value.x_m) || !finite(value.y_m) || !xy([value.x_m, value.y_m]) || !consistentPosition(value, [value.x_m, value.y_m], frame)
    || !finite(value.elapsed_s) || value.elapsed_s < 0 || value.elapsed_s > max || !time(value.time_utc) || !near((Date.parse(value.time_utc) - Date.parse(release.start_time_utc)) / 1000, value.elapsed_s)
    || !finite(value.eastward_m_s) || !finite(value.northward_m_s) || Math.hypot(value.eastward_m_s, value.northward_m_s) > 10 || !finite(value.speed_m_s) || value.speed_m_s < 0 || value.speed_m_s > 10
    || !(value.interpolated_event === undefined || value.interpolated_event === true)) return false;
  return value.interpolated_event === true || near(value.speed_m_s, Math.hypot(value.eastward_m_s, value.northward_m_s), 1e-9);
}
function segments(value: unknown, frame: OceanFrame, length: number): value is OceanSegment[] {
  if (!Array.isArray(value) || value.length > 16 || !finite(length) || length < 0) return false;
  const ids = new Set(); let total = 0;
  for (const item of value) {
    if (!object(item) || !text(item.id, 100) || ids.has(item.id) || !xy(item.start_xy_m) || !xy(item.end_xy_m) || !geo(item.start_geo) || !geo(item.end_geo)
      || !consistentPosition(item.start_geo, item.start_xy_m, frame) || !consistentPosition(item.end_geo, item.end_xy_m, frame)) return false;
    ids.add(item.id); const distance = Math.hypot(item.end_xy_m[0] - item.start_xy_m[0], item.end_xy_m[1] - item.start_xy_m[1]);
    if (distance <= 0) return false; total += distance;
  }
  return near(total, length, 1e-6);
}
function layout(value: unknown, releases: OceanRelease[], frame: OceanFrame): value is OceanLayout {
  if (!object(value) || !text(value.id, 100) || !text(value.label, 200) || !finite(value.total_length_m) || !segments(value.segments, frame, value.total_length_m)
    || !Array.isArray(value.outcomes) || value.outcomes.length !== releases.length || !object(value.summary)) return false;
  const counts = { entered_count: 0, intercepted_count: 0, no_entry_count: 0, unresolved_count: 0 };
  for (const [index, row] of value.outcomes.entries()) {
    const release = releases[index];
    if (!object(row) || row.release_id !== release.id || !["ENTERED_PROTECTED_ZONE", "IDEALIZED_INTERCEPTION", "NO_ENTRY_WITHIN_HORIZON", "UNRESOLVED"].includes(String(row.status))
      || !["COMPLETED", "PARTIAL", "UNSUPPORTED"].includes(String(row.forcing_status)) || row.requested_horizon_s !== release.horizon_s || !finite(row.integrated_horizon_s)
      || row.integrated_horizon_s < 0 || row.integrated_horizon_s > release.horizon_s || !Array.isArray(row.track) || row.track.length > 2049) return false;
    if (row.forcing_status === "COMPLETED" ? row.forcing_reason_code !== null || row.integrated_horizon_s !== release.horizon_s
      : !text(row.forcing_reason_code, 100) || row.forcing_status === "PARTIAL" && (row.integrated_horizon_s <= 0 || row.integrated_horizon_s >= release.horizon_s) || row.forcing_status === "UNSUPPORTED" && row.integrated_horizon_s !== 0) return false;
    for (const [i, p] of row.track.entries()) {
      if (!point(p, release, frame, row.integrated_horizon_s) || (i === 0 ? p.elapsed_s !== 0 || !near(p.x_m, release.x_m, 0.0001) || !near(p.y_m, release.y_m, 0.0001) : p.elapsed_s <= row.track[i - 1].elapsed_s)) return false;
    }
    const end = row.track.at(-1) as OceanPoint | undefined;
    if (row.track_end_elapsed_s !== (end?.elapsed_s ?? null)) return false;
    if (row.status === "ENTERED_PROTECTED_ZONE" || row.status === "IDEALIZED_INTERCEPTION") {
      if (!end || !object(row.event) || !point(row.event, release, frame, row.integrated_horizon_s) || !["x_m", "y_m", "elapsed_s", "time_utc"].every(key => row.event !== null && (row.event as Record<string, unknown>)[key] === (end as unknown as Record<string, unknown>)[key])) return false;
      if (row.status === "ENTERED_PROTECTED_ZONE") { if (row.event.kind !== "PROTECTED_ZONE_ENTRY" || row.event.segment_id !== null) return false; counts.entered_count++; }
      else { if (row.event.kind !== "IDEALIZED_CAPTURE" || !value.segments.some(segment => segment.id === (row.event as Record<string, unknown>).segment_id)) return false; counts.intercepted_count++; }
    } else {
      if (row.event !== null) return false;
      if (row.status === "NO_ENTRY_WITHIN_HORIZON") { if (row.forcing_status !== "COMPLETED" || !end || end.elapsed_s !== release.horizon_s) return false; counts.no_entry_count++; }
      else { if (row.forcing_status === "COMPLETED") return false; counts.unresolved_count++; }
    }
  }
  const s = value.summary, n = releases.length, lo = counts.entered_count, hi = lo + counts.unresolved_count;
  return s.release_count === n && Object.entries(counts).every(([key, count]) => s[key] === count) && pair(s.protected_entry_count_bounds) && s.protected_entry_count_bounds[0] === lo && s.protected_entry_count_bounds[1] === hi
    && pair(s.protected_entry_fraction_bounds) && near(s.protected_entry_fraction_bounds[0], lo / n, 1e-9) && near(s.protected_entry_fraction_bounds[1], hi / n, 1e-9)
    && s.denominator_policy === "all_fixed_releases_including_missing_forcing_and_partial_paths";
}
export function validateOceanPrevention(value: unknown): OceanPreventionReport {
  const fail = (): never => { throw new Error("The ocean comparison has incompatible identities, geometry, outcomes or scientific scope. No result was accepted."); };
  if (!object(value) || !bounded(value) || value.schema_version !== 1 || value.kind !== "OCEAN_PREVENTION_COMPARISON" || !["snapshot_sha256", "manifest_sha256", "method_sha256", "scenario_sha256", "report_sha256"].every(key => hash(value[key]))
    || !["forecast_snapshot", "archived_forecast_snapshot"].includes(String(value.mode)) || !object(value.scenario) || !object(value.scenario.frame) || !object(value.forcing) || !object(value.method) || !object(value.validation)
    || !["measured_track_available", "physical_validation", "plastic_motion_validated", "forecast_skill_established", "interception_benefit_established", "real_reef_boundary_used", "tank_flow_used", "heldout_buoy_positions_used"].every(key => (value.validation as Record<string, unknown>)[key] === false)
    || value.validation.measured_entry_count !== null || value.validation.measured_intercepted_count !== null || !Array.isArray(value.limitations) || value.limitations.length < 1 || value.limitations.length > 40 || !value.limitations.every(item => text(item))) return fail();
  const scenario = value.scenario, frame = scenario.frame as OceanFrame;
  if (frame.position_units !== "m" || frame.axes !== "x east, y north" || !finite(frame.origin_latitude_deg) || Math.abs(frame.origin_latitude_deg) > 85 || !finite(frame.origin_longitude_deg) || frame.origin_longitude_deg < -180 || frame.origin_longitude_deg >= 180
    || !finite(frame.east_metres_per_degree) || frame.east_metres_per_degree <= 0 || !finite(frame.north_metres_per_degree) || frame.north_metres_per_degree <= 0 || !time(scenario.start_time_utc) || scenario.horizon_s !== 21600
    || !text(scenario.id, 100) || !text(scenario.label) || !((scenario.id === "initial-proxy-v1" && scenario.design_status === "INITIAL_GEOMETRY_NEGATIVE_CONTROL" && scenario.geometry_status === "fixed_pre_outcome_illustrative_hypothesis_not_optimized") || (scenario.id === "downstream-corridor-v2" && scenario.design_status === "ILLUSTRATIVE_WHAT_IF_AFTER_VIEWING_PREVIEW" && scenario.geometry_status === "fixed_post_preview_illustrative_hypothesis_not_independent_validation")) || !text(scenario.design_disclosure) || !text(scenario.resource_constraint)
    || !object(value.protected_zone) || value.protected_zone.is_mapped_real_reef !== false || !text(value.protected_zone.label) || !text(value.protected_zone.id, 100)
    || !Array.isArray(value.protected_zone.polygon_xy_m) || value.protected_zone.polygon_xy_m.length < 3 || value.protected_zone.polygon_xy_m.length > 32 || !value.protected_zone.polygon_xy_m.every(xy)
    || !Array.isArray(value.protected_zone.polygon_geo) || value.protected_zone.polygon_geo.length !== value.protected_zone.polygon_xy_m.length || !value.protected_zone.polygon_geo.every((p, i) => geo(p) && consistentPosition(p, (value.protected_zone as OceanZone).polygon_xy_m[i], frame))
    || !Array.isArray(value.releases) || value.releases.length !== 6 || !same(value.protected_zone, scenario.protected_zone) || !same(value.releases, scenario.releases)) return fail();
  const ids = new Set();
  for (const r of value.releases) {
    if (!object(r) || !geo(r) || !text(r.id, 100) || ids.has(r.id) || !finite(r.x_m) || !finite(r.y_m) || !xy([r.x_m, r.y_m]) || !consistentPosition(r, [r.x_m, r.y_m], frame)
      || r.start_time_utc !== scenario.start_time_utc || r.horizon_s !== scenario.horizon_s || r.kind !== "hypothetical_passive_tracer_not_observed_waste") return fail();
    ids.add(r.id);
  }
  const releases = value.releases as OceanRelease[];
  if (!object(value.display_bounds_xy_m) || !pair(value.display_bounds_xy_m.x_m) || !pair(value.display_bounds_xy_m.y_m) || value.display_bounds_xy_m.x_m[0] >= value.display_bounds_xy_m.x_m[1] || value.display_bounds_xy_m.y_m[0] >= value.display_bounds_xy_m.y_m[1] || ![...value.display_bounds_xy_m.x_m, ...value.display_bounds_xy_m.y_m].every(v => Math.abs(v) <= 100_000)) return fail();
  if (!layout(value.baseline, releases, frame) || value.baseline.id !== "no-interceptor" || value.baseline.total_length_m !== 0 || value.baseline.summary.intercepted_count !== 0
    || !Array.isArray(value.layouts) || value.layouts.length !== 2 || !Array.isArray(scenario.layouts) || scenario.layouts.length !== 2 || !value.layouts.every(item => layout(item, releases, frame))) return fail();
  const layouts = value.layouts as OceanLayout[], base = value.baseline;
  if (layouts[0].id === layouts[1].id || layouts.some((item, i) => item.id === base.id || item.total_length_m !== 2000
    || !same({ id: item.id, label: item.label, total_length_m: item.total_length_m, segments: item.segments }, (scenario.layouts as unknown[])[i])
    || !pair(item.summary.entry_reduction_count_bounds_vs_baseline) || item.summary.entry_reduction_count_bounds_vs_baseline[0] !== base.summary.protected_entry_count_bounds[0] - item.summary.protected_entry_count_bounds[1]
    || item.summary.entry_reduction_count_bounds_vs_baseline[1] !== base.summary.protected_entry_count_bounds[1] - item.summary.protected_entry_count_bounds[0]
    || item.outcomes.some((row, j) => row.forcing_status !== base.outcomes[j].forcing_status || row.forcing_reason_code !== base.outcomes[j].forcing_reason_code || row.integrated_horizon_s !== base.outcomes[j].integrated_horizon_s))) return fail();
  const expectedStatus = base.outcomes.every(row => row.forcing_status === "COMPLETED") ? "COMPLETED" : base.outcomes.some(row => row.integrated_horizon_s > 0) ? "PARTIAL" : "UNSUPPORTED";
  const [a, b] = layouts.map(item => item.summary.protected_entry_count_bounds);
  const best = a[1] < b[0] ? layouts[0].id : b[1] < a[0] ? layouts[1].id : null;
  const expectedRecommendation = best ? "BEST_LAYOUT" : a[0] === a[1] && a[0] === b[0] && a[0] === b[1] ? "TIE" : "INDETERMINATE";
  if (value.status !== expectedStatus || !object(value.recommendation) || value.recommendation.status !== expectedRecommendation || value.recommendation.best_layout_id !== best || !text(value.recommendation.reason)
    || value.recommendation.comparison_basis !== "strict_nonoverlap_of_model_protected_entry_count_bounds") return fail();
  const method = value.method, forcing = value.forcing;
  if (method.trajectory !== "dynamic_current_advection_only" || method.identical_unmodified_forcing_for_every_layout !== true || method.paths_integrated_once_per_release !== true || method.barriers_modify_flow !== false
    || method.capture_efficiency_assumption !== "ideal_absorbing_first_contact_not_measured" || method.step_s !== 300 || method.output_step_s !== 300 || !same(method.geometry_frame, frame) || !same(method.event_model, scenario.event_model)
    || !time(forcing.captured_at_utc) || !time(forcing.valid_start_utc) || !time(forcing.valid_end_utc) || Date.parse(forcing.valid_start_utc) > Date.parse(scenario.start_time_utc) || Date.parse(forcing.valid_end_utc) < Date.parse(scenario.start_time_utc) + 21600000
    || !(forcing.model_issue_time_utc === null || time(forcing.model_issue_time_utc)) || !finite(forcing.depth_m) || forcing.depth_m < 0 || !text(forcing.attribution)) return fail();
  for (const key of ["source_url", "metadata_url", "product_url"]) {
    if (!text(forcing[key], 5000)) return fail();
    try { const url = new URL(forcing[key]); if (url.protocol !== "https:" || url.username || url.password) return fail(); } catch { return fail(); }
  }
  if (value.vector_frames !== undefined) {
    if (!Array.isArray(value.vector_frames) || value.vector_frames.length < 1 || value.vector_frames.length > 25) return fail();
    for (const [i, f] of value.vector_frames.entries()) {
      if (!object(f) || !time(f.time_utc) || Date.parse(f.time_utc) < Date.parse(forcing.valid_start_utc) || Date.parse(f.time_utc) > Date.parse(forcing.valid_end_utc)
        || i > 0 && Date.parse(f.time_utc) <= Date.parse(value.vector_frames[i - 1].time_utc) || !Array.isArray(f.vectors) || f.vectors.length > 500
        || !f.vectors.every(v => object(v) && geo(v) && finite(v.eastward_m_s) && finite(v.northward_m_s) && Math.hypot(v.eastward_m_s, v.northward_m_s) <= 10 && (v.x_m === undefined && v.y_m === undefined || finite(v.x_m) && finite(v.y_m) && consistentPosition(v, [v.x_m, v.y_m], frame)))) return fail();
    }
  }
  if (Object.hasOwn(value, "numerical_sensitivity")) validateOceanNumerics(value.numerical_sensitivity, { releases, scenario: { horizon_s: scenario.horizon_s, releases: scenario.releases as OceanRelease[] }, baseline: base, layouts });
  return value as OceanPreventionReport;
}
export function validateOceanPreventionAnswer(value: unknown, report: OceanPreventionReport): OceanPreventionAnswer {
  const fail = (): never => { throw new Error("Chalk's review did not match this ocean comparison. No explanation was accepted."); };
  if (!object(value) || value.schema_version !== 1 || value.kind !== "OCEAN_PREVENTION_INVESTIGATION" || value.scope !== "READ_ONLY_OCEAN_PREVENTION" || value.provider !== "chalk" || value.scenario_id !== report.scenario.id
    || !["REPORT", "STOP"].includes(String(value.action)) || typeof value.live_model_response !== "boolean" || !text(value.explanation, 1200)
    || value.store_written !== false || value.physical_validation !== false || value.hardware_actuation !== false
    || !["snapshot_sha256", "method_sha256", "scenario_sha256", "report_sha256"].every(key => value[key] === (report as unknown as Record<string, unknown>)[key]) || !Array.isArray(value.evidence_ids)) return fail();
  const allowed = [`ocean-comparison:${report.report_sha256}`, `ocean-method:${report.method_sha256}`];
  if (value.evidence_ids.some(id => !allowed.includes(id)) || new Set(value.evidence_ids).size !== value.evidence_ids.length || value.action === "REPORT" && (value.evidence_ids.length !== 2 || !value.live_model_response || value.failure_code !== undefined) || value.failure_code !== undefined && (value.live_model_response || !text(value.failure_code, 100))) return fail();
  const nested = validateOceanPrevention(value.research_report);
  if (!same(nested, report)) return fail();
  return value as OceanPreventionAnswer;
}
