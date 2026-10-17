/** Saved tank XY replay only. This module never integrates physics or scores paths. */
export type TankLayout = "baseline" | "intervention";
export type TankPoint = { t_s: number; x_cm: number; y_cm: number };
export type TankBounds = { x_min_cm: number; x_max_cm: number; y_min_cm: number; y_max_cm: number };
export type TankPath = { layout: TankLayout; source_id: string; particle_index: number; points: TankPoint[]; zone_entry_s: number | null; capture_s: number | null; display_stop_s: number | null; support_status: "SUPPORTED_THROUGH_FIRST_EVENT_OR_HORIZON" | "UNSUPPORTED_PATH_WITHHELD"; sampling: "LEGACY_DECIMATED_REPRESENTATIVE"; counts_derived_from_path: false };
export type TankStats = { planned: number; released: number; missing_planned: number; zone_entries: number; captured_before_entry: number; no_entry: number; unresolved: number; token_accounted: number; unaccounted: number; recording_linked: number; entry_rate_bounds: { lower: number; upper: number; denominator: number } };
export type TankOutcomeGroup = { layouts: Record<TankLayout, TankStats>; plan: { expected_total: number; recorded_total: number; complete: boolean; balanced: boolean; order_followed: boolean }; effect_bounds: { lower: number; upper: number } };
export type TankNumericalRow = { scenario_id: string; source_id: string; baseline: { particles: number; zone_entry_count: number; zone_entry_fraction: number; unsupported_count: number }; intervention: { particles: number; zone_entry_count: number; zone_entry_fraction: number; unsupported_count: number } };
export type TankRecording = { trial_id: string; recording_id: string; recording_content_hash: string; reason_codes: string[]; layout: TankLayout; source_id: string; calibration_id: string; camera_session_id: string; segments: { track_id: string; points: TankPoint[] }[]; gaps: { t_s: number; reason: string }[]; outcome_automatically_verified: false };
export type TankScene = {
  schema_version: 1; kind: "TANK_RIG_SCENE"; comparison_id: string; comparison_sha256: string; numerical_report_sha256: string; evaluation_snapshot_hash: string; scene_sha256: string;
  case_id: string; case_revision: number; source_evidence_id: string; is_current: boolean; archive_reason: string | null; data_origin: "SYNTHETIC" | "MEASURED_TANK"; physical_validation: false;
  units: { position: "cm"; time: "s"; velocity: "cm/s" };
  vertical: { mode: "SCHEMATIC_SURFACE_ONLY"; surface_z_cm: 0; measured_depth_cm: null; physical_geometry_verified: false };
  geometry: { bounds_cm: TankBounds; sources: { id: string; polygon_cm: number[][] }[]; protected_zone_cm: number[][]; layouts: { id: TankLayout; profile_id: string; profile_hash: string; flow_hash: string; calibration_id: string; traps: { id: string; polygon_cm: number[][]; retention: "absorbing" }[] }[] };
  simulation: { engine: "EXISTING_TANK_EULER_MARUYAMA"; scenario_id: "nominal"; event_time_kind: "TIME_NODE_UPPER_BOUND_NOT_EXACT_COLLISION"; horizon_s: number; seed: number; particles_per_source: number; paths: TankPath[] };
  vectors: { layout: TankLayout; flow_hash: string; time_varying: false; nodes: { x_cm: number; y_cm: number; vx_cm_s: number; vy_cm_s: number; supported: boolean }[] }[];
  results: { recommendation: string; robust_benefit_min: number; robust_benefit_max: number; rows: TankNumericalRow[]; by_origin: Record<"SYNTHETIC_DEMO" | "OPERATOR_REPORTED_PHYSICAL", TankOutcomeGroup> };
  actual: { status: "NOT_CAPTURED" | "REPORTED_COUNTS_ONLY" | "RECORDED_TRACKS_AVAILABLE"; reason_codes: string[]; clock: "CAPTURE_START_UNALIGNED"; release_alignment: "MISSING"; positional_error_metrics: null; reported_physical_trial_count: number; recordings: TankRecording[] };
  limitations: string[];
};
export type TankSceneExpected = { comparisonId: string; evaluationHash: string };
export type TankCaptureCursor = { recordingId: string; captureTime: number };

/** A different source/layout is a different capture selection, never a shared clock. */
export function resetTankCaptureCursor(): TankCaptureCursor {
  return { recordingId: "", captureTime: 0 };
}

export function tankSceneIsCurrent(parentCurrent: boolean, sceneCurrent: boolean): boolean {
  // A STOP/recompute can archive a plan without changing its frozen evaluation.
  return parentCurrent && sceneCurrent;
}

const object = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === "object" && !Array.isArray(v);
const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const nonnegative = (v: unknown): v is number => finite(v) && v >= 0;
const count = (v: unknown): v is number => nonnegative(v) && Number.isInteger(v) && v <= 20_000;
const id = (v: unknown): v is string => typeof v === "string" && /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(v) && !/^(?:sk-|ck-|xai-|ghp_|github_pat_|aiza)/i.test(v);
const hash = (v: unknown): v is string => typeof v === "string" && /^[a-f0-9]{64}$/.test(v);
const layout = (v: unknown): v is TankLayout => v === "baseline" || v === "intervention";
const near = (a: number, b: number) => Math.abs(a - b) <= 1e-9 * Math.max(1, Math.abs(a), Math.abs(b));
const fail = (): never => { throw new Error("The tank scene has stale, incompatible or incomplete evidence. Reload the saved comparison. No result was accepted."); };
function bounded(value: unknown, depth = 0, budget = { nodes: 0 }): boolean {
  if (++budget.nodes > 300_000 || depth > 18) return false;
  if (Array.isArray(value)) return value.length <= 20_000 && value.every(item => bounded(item, depth + 1, budget));
  if (object(value)) return Object.keys(value).length <= 80 && Object.values(value).every(item => bounded(item, depth + 1, budget));
  return value === null || typeof value === "boolean" || finite(value) || typeof value === "string" && value.length <= 8_000;
}
function inside(x: unknown, y: unknown, b: TankBounds): boolean {
  return finite(x) && finite(y) && x >= b.x_min_cm && x <= b.x_max_cm && y >= b.y_min_cm && y <= b.y_max_cm;
}
function polygon(value: unknown, b: TankBounds): boolean {
  return Array.isArray(value) && value.length >= 3 && value.length <= 65 && value.every(p => Array.isArray(p) && p.length === 2 && inside(p[0], p[1], b));
}
function timedPoints(value: unknown, b: TankBounds, max: number, limit: number): value is TankPoint[] {
  if (!Array.isArray(value) || value.length > limit) return false;
  let previous = -1;
  return value.every(point => {
    if (!object(point) || !nonnegative(point.t_s) || point.t_s > max || point.t_s <= previous || !inside(point.x_cm, point.y_cm, b)) return false;
    previous = point.t_s;
    return true;
  });
}
function validStats(value: unknown): value is TankStats {
  if (!object(value) || ![value.planned, value.released, value.missing_planned, value.zone_entries, value.captured_before_entry, value.no_entry, value.unresolved, value.token_accounted, value.unaccounted, value.recording_linked].every(count) || !object(value.entry_rate_bounds)) return false;
  const s = value as TankStats;
  return s.planned > 0 && s.released <= s.planned && s.missing_planned === s.planned - s.released && s.zone_entries + s.captured_before_entry + s.no_entry + s.unresolved === s.released && s.token_accounted + s.unaccounted === s.released && s.recording_linked <= s.released && s.entry_rate_bounds.denominator === s.planned && near(s.entry_rate_bounds.lower, s.zone_entries / s.planned) && near(s.entry_rate_bounds.upper, (s.zone_entries + s.unresolved + s.missing_planned) / s.planned);
}

export function validateTankScene(value: unknown, expected: TankSceneExpected): TankScene {
  if (!object(value) || !bounded(value) || !id(expected.comparisonId) || !hash(expected.evaluationHash) || value.schema_version !== 1 || value.kind !== "TANK_RIG_SCENE" || value.comparison_id !== expected.comparisonId || value.evaluation_snapshot_hash !== expected.evaluationHash
    || ![value.comparison_sha256, value.numerical_report_sha256, value.scene_sha256].every(hash) || !id(value.case_id) || !count(value.case_revision) || value.case_revision < 1 || !id(value.source_evidence_id) || typeof value.is_current !== "boolean" || !(value.archive_reason === null || typeof value.archive_reason === "string") || !["SYNTHETIC", "MEASURED_TANK"].includes(value.data_origin as string) || value.physical_validation !== false
    || !object(value.units) || value.units.position !== "cm" || value.units.time !== "s" || value.units.velocity !== "cm/s" || !object(value.vertical) || value.vertical.mode !== "SCHEMATIC_SURFACE_ONLY" || value.vertical.surface_z_cm !== 0 || value.vertical.measured_depth_cm !== null || value.vertical.physical_geometry_verified !== false
    || !object(value.geometry) || !object(value.geometry.bounds_cm) || !object(value.simulation) || !Array.isArray(value.vectors) || !object(value.results) || !object(value.actual) || !Array.isArray(value.limitations) || !value.limitations.length || !value.limitations.every(v => typeof v === "string")) return fail();
  const scene = value as TankScene, b = scene.geometry.bounds_cm, g = scene.geometry, sim = scene.simulation;
  if (![b.x_min_cm, b.x_max_cm, b.y_min_cm, b.y_max_cm].every(finite) || !(b.x_max_cm > b.x_min_cm) || !(b.y_max_cm > b.y_min_cm) || !finite(b.x_max_cm - b.x_min_cm) || !finite(b.y_max_cm - b.y_min_cm)
    || !Array.isArray(g.sources) || g.sources.length < 2 || g.sources.length > 5 || !g.sources.every(s => object(s) && id(s.id) && polygon(s.polygon_cm, b)) || new Set(g.sources.map(s => s.id)).size !== g.sources.length || !polygon(g.protected_zone_cm, b)
    || !Array.isArray(g.layouts) || g.layouts.length !== 2 || !g.layouts.every(object) || g.layouts[0].id !== "baseline" || g.layouts[1].id !== "intervention") return fail();
  for (const row of g.layouts) if (!id(row.profile_id) || !hash(row.profile_hash) || !hash(row.flow_hash) || !id(row.calibration_id) || !Array.isArray(row.traps) || row.traps.length > 5 || !row.traps.every(t => object(t) && id(t.id) && t.retention === "absorbing" && polygon(t.polygon_cm, b))) return fail();
  if (sim.engine !== "EXISTING_TANK_EULER_MARUYAMA" || sim.scenario_id !== "nominal" || sim.event_time_kind !== "TIME_NODE_UPPER_BOUND_NOT_EXACT_COLLISION" || !finite(sim.horizon_s) || sim.horizon_s < 1 || sim.horizon_s > 20 || !Number.isInteger(sim.seed) || sim.seed < 0 || sim.seed > 4294967295 || !count(sim.particles_per_source) || sim.particles_per_source < 20 || sim.particles_per_source > 200 || !Array.isArray(sim.paths) || sim.paths.length > 60) return fail();
  const pathKeys = new Set<string>();
  for (const path of sim.paths) {
    if (!object(path) || !Array.isArray(path.points) || !layout(path.layout) || !g.sources.some(s => s.id === path.source_id) || !count(path.particle_index) || path.particle_index >= sim.particles_per_source || path.sampling !== "LEGACY_DECIMATED_REPRESENTATIVE" || path.counts_derived_from_path !== false || ![path.zone_entry_s, path.capture_s, path.display_stop_s].every(v => v === null || nonnegative(v) && v <= sim.horizon_s)) return fail();
    const key = `${path.layout}:${path.source_id}:${path.particle_index}`;
    if (pathKeys.has(key)) return fail();
    pathKeys.add(key);
    if (path.support_status === "UNSUPPORTED_PATH_WITHHELD") { if (path.points.length || path.display_stop_s !== null) return fail(); continue; }
    if (path.support_status !== "SUPPORTED_THROUGH_FIRST_EVENT_OR_HORIZON" || !nonnegative(path.display_stop_s) || !timedPoints(path.points, b, path.display_stop_s, 81) || !path.points.length || path.points[0].t_s !== 0 || path.points[path.points.length - 1].t_s > path.display_stop_s) return fail();
    const firstEvent = Math.min(path.zone_entry_s ?? sim.horizon_s, path.capture_s ?? sim.horizon_s, sim.horizon_s);
    if (path.display_stop_s > firstEvent) return fail();
  }
  if (scene.vectors.length !== 2) return fail();
  for (const [index, vector] of scene.vectors.entries()) {
    if (!object(vector) || vector.layout !== g.layouts[index].id || vector.flow_hash !== g.layouts[index].flow_hash || vector.time_varying !== false || !Array.isArray(vector.nodes) || vector.nodes.length > 512 || !vector.nodes.every(node => object(node) && inside(node.x_cm, node.y_cm, b) && finite(node.vx_cm_s) && finite(node.vy_cm_s) && Math.abs(node.vx_cm_s) <= 100 && Math.abs(node.vy_cm_s) <= 100 && typeof node.supported === "boolean")) return fail();
  }
  const r = scene.results;
  if (!["INTERVENTION", "BASELINE", "NO_ROBUST_RECOMMENDATION"].includes(r.recommendation) || !finite(r.robust_benefit_min) || !finite(r.robust_benefit_max) || r.robust_benefit_min > r.robust_benefit_max || !Array.isArray(r.rows) || r.rows.length < g.sources.length || r.rows.length > 15 || !object(r.by_origin)) return fail();
  for (const row of r.rows) {
    if (!object(row) || !id(row.scenario_id) || !g.sources.some(s => s.id === row.source_id)) return fail();
    for (const side of [row.baseline, row.intervention]) if (!object(side) || side.particles !== sim.particles_per_source || !count(side.zone_entry_count) || !count(side.unsupported_count) || side.zone_entry_count > side.particles || side.unsupported_count > side.particles || !finite(side.zone_entry_fraction) || !near(side.zone_entry_fraction, side.zone_entry_count / side.particles)) return fail();
  }
  if (g.sources.some(source => r.rows.filter(row => row.scenario_id === "nominal" && row.source_id === source.id).length !== 1)) return fail();
  for (const origin of ["SYNTHETIC_DEMO", "OPERATOR_REPORTED_PHYSICAL"] as const) {
    const group = r.by_origin[origin];
    if (!object(group) || !object(group.layouts) || !object(group.plan) || !object(group.effect_bounds) || !validStats(group.layouts.baseline) || !validStats(group.layouts.intervention)) return fail();
    const a = group.layouts.baseline, z = group.layouts.intervention;
    if (group.plan.expected_total !== a.planned + z.planned || group.plan.recorded_total !== a.released + z.released || ![group.plan.complete, group.plan.balanced, group.plan.order_followed].every(v => typeof v === "boolean") || !near(group.effect_bounds.lower, a.entry_rate_bounds.lower - z.entry_rate_bounds.upper) || !near(group.effect_bounds.upper, a.entry_rate_bounds.upper - z.entry_rate_bounds.lower)) return fail();
  }
  const actual = scene.actual;
  if (!["NOT_CAPTURED", "REPORTED_COUNTS_ONLY", "RECORDED_TRACKS_AVAILABLE"].includes(actual.status) || !Array.isArray(actual.reason_codes) || !actual.reason_codes.every(reason => typeof reason === "string" && reason.length > 0 && reason.length <= 200) || actual.clock !== "CAPTURE_START_UNALIGNED" || actual.release_alignment !== "MISSING" || actual.positional_error_metrics !== null || actual.reported_physical_trial_count !== r.by_origin.OPERATOR_REPORTED_PHYSICAL.plan.recorded_total || !Array.isArray(actual.recordings) || actual.recordings.length > 200 || scene.data_origin === "SYNTHETIC" && (actual.reported_physical_trial_count !== 0 || actual.recordings.length > 0)) return fail();
  const recordings = new Set<string>(); let totalPoints = 0;
  for (const recording of actual.recordings) {
    if (!object(recording) || !id(recording.trial_id) || !id(recording.recording_id) || recordings.has(recording.recording_id) || !hash(recording.recording_content_hash) || !Array.isArray(recording.reason_codes) || !recording.reason_codes.every(reason => typeof reason === "string" && reason.length > 0 && reason.length <= 200) || !layout(recording.layout) || !g.sources.some(s => s.id === recording.source_id) || recording.calibration_id !== g.layouts.find(l => l.id === recording.layout)?.calibration_id || !id(recording.camera_session_id) || recording.outcome_automatically_verified !== false || !Array.isArray(recording.segments) || !Array.isArray(recording.gaps)) return fail();
    recordings.add(recording.recording_id);
    let previous = -1, recordingPoints = 0;
    for (const segment of recording.segments) {
      if (!object(segment) || !id(segment.track_id) || !timedPoints(segment.points, b, 60, 2000) || !segment.points.length || segment.points[0].t_s <= previous || segment.points.some((point, index) => index > 0 && point.t_s - segment.points[index - 1].t_s > 0.5)) return fail();
      previous = segment.points[segment.points.length - 1].t_s; totalPoints += segment.points.length; recordingPoints += segment.points.length;
    }
    if (recordingPoints > 2000 || !recording.gaps.every(gap => object(gap) && nonnegative(gap.t_s) && gap.t_s <= 60 && typeof gap.reason === "string" && gap.reason.length > 0 && gap.reason.length <= 200) || recording.segments.some(segment => recording.gaps.some(gap => gap.t_s > segment.points[0].t_s && gap.t_s < segment.points[segment.points.length - 1].t_s))) return fail();
  }
  if (totalPoints > 20_000 || actual.status === "RECORDED_TRACKS_AVAILABLE" && !actual.recordings.some(rec => rec.segments.length) || actual.status !== "RECORDED_TRACKS_AVAILABLE" && actual.recordings.some(rec => rec.segments.length) || actual.status === "NOT_CAPTURED" && (actual.reported_physical_trial_count !== 0 || actual.recordings.length !== 0) || actual.status === "REPORTED_COUNTS_ONLY" && actual.reported_physical_trial_count === 0) return fail();
  return scene;
}

export function visibleTankPaths(scene: TankScene, selected: TankLayout, sourceId: string): TankPath[] {
  return scene.simulation.paths.filter(path => path.layout === selected && (sourceId === "all" || path.source_id === sourceId));
}

export function tankWaterLabels(scene: TankScene): { text: string; x_cm: number; y_cm: number; kind: "source" | "coordinate" | "protected" }[] {
  const bounds = scene.geometry.bounds_cm;
  const center = (points: number[][]) => ({ x_cm: points.reduce((sum, point) => sum + point[0], 0) / points.length, y_cm: points.reduce((sum, point) => sum + point[1], 0) / points.length });
  const labels = scene.geometry.sources.map(source => ({ text: `Source ${source.id}`, ...center(source.polygon_cm), kind: "source" as const }));
  const coordinates: { text: string; x_cm: number; y_cm: number; kind: "coordinate" }[] = [];
  const number = (value: number) => String(Number(value.toFixed(2)));
  for (const fraction of [0, 0.5, 1]) { const x = bounds.x_min_cm + (bounds.x_max_cm - bounds.x_min_cm) * fraction; coordinates.push({ text: `x ${number(x)} cm`, x_cm: x, y_cm: bounds.y_min_cm, kind: "coordinate" }); }
  for (const fraction of [0.5, 1]) { const y = bounds.y_min_cm + (bounds.y_max_cm - bounds.y_min_cm) * fraction; coordinates.push({ text: `y ${number(y)} cm`, x_cm: bounds.x_min_cm, y_cm: y, kind: "coordinate" }); }
  return [...labels, { text: "Protected zone", ...center(scene.geometry.protected_zone_cm), kind: "protected" as const }, ...coordinates];
}

export function supportedTankVectors(scene: TankScene, selected: TankLayout) {
  return scene.vectors.find(row => row.layout === selected)?.nodes.filter(node => node.supported) ?? [];
}

/** Straight interpolation between saved display samples; never extrapolate a prefix. */
export function tankPositionAt(points: TankPoint[], time: number, stop: number): TankPoint | null {
  if (!points.length || !finite(time) || time < points[0].t_s || time > stop || time > points[points.length - 1].t_s) return null;
  for (let index = 0; index < points.length; index++) {
    const point = points[index];
    if (point.t_s === time) return point;
    if (point.t_s > time) {
      const a = points[index - 1], fraction = (time - a.t_s) / (point.t_s - a.t_s);
      return { t_s: time, x_cm: a.x_cm + (point.x_cm - a.x_cm) * fraction, y_cm: a.y_cm + (point.y_cm - a.y_cm) * fraction };
    }
  }
  return null;
}

/** Observed samples remain samples: no interpolation, extrapolation or gap bridging. */
export function recordedTankPositionAt(recording: TankRecording, time: number): TankPoint | null {
  if (!finite(time)) return null;
  for (const segment of recording.segments) {
    if (!segment.points.length || time < segment.points[0].t_s || time > segment.points[segment.points.length - 1].t_s) continue;
    const sample = segment.points.findLast(point => point.t_s <= time);
    if (sample && !recording.gaps.some(gap => gap.t_s >= sample.t_s && gap.t_s <= time)) return sample;
  }
  return null;
}

export function tankHeadline(scene: TankScene, selected: TankLayout) {
  const nominal = scene.results.rows.filter(row => row.scenario_id === "nominal");
  const physical = scene.results.by_origin.OPERATOR_REPORTED_PHYSICAL.layouts[selected];
  return {
    predictedEntries: nominal.reduce((sum, row) => sum + row[selected].zone_entry_count, 0),
    predictedParticles: nominal.reduce((sum, row) => sum + row[selected].particles, 0),
    unsupportedParticles: nominal.reduce((sum, row) => sum + row[selected].unsupported_count, 0),
    physicalEntries: physical.zone_entries, physicalReleased: physical.released, physicalPlanned: physical.planned,
    missingPhysical: physical.missing_planned, physicalBounds: physical.entry_rate_bounds,
    syntheticRecorded: scene.results.by_origin.SYNTHETIC_DEMO.plan.recorded_total,
  };
}
