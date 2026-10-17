// The display accepts this fixed, already-viewed study only. It never chooses a model.
export const KALMAN_MODEL_IDS = ["stationary", "last_drift", "mean_drift", "ridge_ar1", "kalman_cv"] as const;
const DRIFTERS = ["12730", "12731", "300234063243480", "300234063472530"];
type Covariance = [[number, number], [number, number]];
export type KalmanPoint = { time_utc: string; latitude_deg: number; longitude_deg: number; x_m: number; y_m: number };
type Metrics = { ade_m: number; fde_m: number; vector_rmse_m_s: number };
type Prediction = KalmanPoint & { horizon_hours: number; status: "SCORED"; reason_codes: string[]; position_error_m: number; position_covariance_m2: Covariance | null; observation_covariance_m2: Covariance | null; ellipse_hits: { nominal50: boolean; nominal90: boolean } | null };
type Failure = { horizon_hours: number; time_utc: string; status: "FAILED"; reason_codes: string[]; latitude_deg: null; longitude_deg: null; x_m: null; y_m: null; position_error_m: null; position_covariance_m2: null; observation_covariance_m2: null; ellipse_hits: null };
export type KalmanTrack = { id: string; label: string; status: "SCORED" | "FAILED"; parameters: Record<string, unknown>; forecast_anchor: { x_m: number; y_m: number; time_utc: string } | null; predictions: (Prediction | Failure)[]; metrics: Metrics | null };
export type KalmanReport = {
  schema_version: 1; kind: "FIXED_KALMAN_MOTION_DIAGNOSTIC"; status: "COMPLETED" | "INCOMPLETE_OUTCOMES";
  coverage: { target_groups: 6; acquired_groups: 4; missing_groups: 2; models: 5; horizons: 6; planned_outcomes: 180; attempted_outcomes: 120; scored_outcomes: number; failed_outcomes: number; unique_observed_intervals: 24; common_acquired_cohort_complete: boolean };
  groups: { drifter_id: string; block_id: string; coordinate_system: { origin_latitude_deg: number; origin_longitude_deg: number }; training_track: KalmanPoint[]; heldout_track: KalmanPoint[]; models: KalmanTrack[] }[];
  models: { id: string; label: string; complete_groups: number; metrics: Metrics | null }[];
  uncertainty: { kind: "UNCALIBRATED_OBSERVATION_PREDICTIVE_ELLIPSE_HITS"; comparison_covariance: "position_covariance_plus_assumed_R"; chi2_thresholds: { nominal50: number; nominal90: number }; per_drifter: { drifter_id: string; scored_count: number; nominal50_hit_count: number | null; nominal90_hit_count: number | null; nominal50_hit_fraction: number | null; nominal90_hit_fraction: number | null }[]; fraction_ranges: { nominal50: { min: number; max: number }; nominal90: { min: number; max: number } } | null } | null;
  limitations: string[];
};
const object = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === "object" && !Array.isArray(v);
const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const nonnegative = (v: unknown): v is number => finite(v) && v >= 0;
const close = (a: number, b: number) => Math.abs(a - b) <= 1e-6 * Math.max(1, Math.abs(b));
function bounded(v: unknown, depth = 0, budget = { count: 0 }): boolean {
  if (++budget.count > 25_000 || depth > 18) return false;
  if (Array.isArray(v)) return v.length <= 512 && v.every(x => bounded(x, depth + 1, budget));
  if (object(v)) return Object.keys(v).length <= 100 && Object.values(v).every(x => bounded(x, depth + 1, budget));
  return v === null || typeof v === "boolean" || finite(v) || typeof v === "string" && v.length <= 8_000;
}
function utc(v: unknown): number | null {
  if (typeof v !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(v)) return null;
  const t = Date.parse(v);
  return Number.isFinite(t) && new Date(t).toISOString().replace(".000Z", "Z") === v ? t : null;
}
function point(v: unknown): v is KalmanPoint & Record<string, unknown> {
  return object(v) && utc(v.time_utc) !== null && finite(v.x_m) && Math.abs(v.x_m) <= 1_000_000 && finite(v.y_m) && Math.abs(v.y_m) <= 1_000_000
    && finite(v.latitude_deg) && Math.abs(v.latitude_deg) <= 90 && finite(v.longitude_deg) && Math.abs(v.longitude_deg) <= 180;
}
function sameProjection(p: KalmanPoint, origin: { origin_latitude_deg: number; origin_longitude_deg: number }): boolean {
  const rad=Math.PI/180, lat0=origin.origin_latitude_deg*rad, lon0=origin.origin_longitude_deg*rad, lat=p.latitude_deg*rad, lon=p.longitude_deg*rad;
  const dl=Math.atan2(Math.sin(lon-lon0),Math.cos(lon-lon0));
  const east=Math.cos(lat)*Math.sin(dl), north=Math.cos(lat0)*Math.sin(lat)-Math.sin(lat0)*Math.cos(lat)*Math.cos(dl);
  const dot=Math.sin(lat0)*Math.sin(lat)+Math.cos(lat0)*Math.cos(lat)*Math.cos(dl), norm=Math.hypot(east,north);
  const distance=Math.atan2(norm,dot)*6_371_008.8;
  return distance<=50_000 && (distance<1e-9 ? close(p.x_m,0)&&close(p.y_m,0) : close(p.x_m,east*distance/norm)&&close(p.y_m,north*distance/norm));
}
function covariance(v: unknown): v is Covariance {
  if (!Array.isArray(v) || v.length !== 2 || !v.every(r => Array.isArray(r) && r.length === 2 && r.every(finite))) return false;
  const [[a,b],[c,d]] = v;
  return a > 0 && d > 0 && close(b,c) && a * d - b * c > 0;
}
const metric = (v: unknown): v is Metrics => object(v) && [v.ade_m, v.fde_m, v.vector_rmse_m_s].every(nonnegative);
const greatCircle = (a: KalmanPoint, b: KalmanPoint) => {
  const rad = Math.PI / 180, p = a.latitude_deg * rad, q = b.latitude_deg * rad;
  const sin2 = Math.sin((q-p)/2)**2 + Math.cos(p)*Math.cos(q)*Math.sin((b.longitude_deg-a.longitude_deg)*rad/2)**2;
  return 2 * 6_371_008.8 * Math.asin(Math.sqrt(Math.min(1,Math.max(0,sin2))));
};
export function validateKalmanReport(value: unknown): KalmanReport {
  const fail = (): never => { throw new Error("The fixed Kalman report has incompatible evidence, coverage, positions or scores. No result was accepted."); };
  if (!object(value) || !bounded(value) || value.schema_version !== 1 || value.kind !== "FIXED_KALMAN_MOTION_DIAGNOSTIC"
    || !["COMPLETED", "INCOMPLETE_OUTCOMES"].includes(value.status as string) || value.data_origin !== "REAL_HISTORICAL_NOAA_DRIFTERS_ALREADY_VIEWED"
    || value.design_status !== "POST_HOC_ALREADY_VIEWED_FIXED_PARAMETER_COMPARISON" || value.parameter_fitting_scope !== "KALMAN_NOISE_HYPERPARAMETERS_ONLY" || value.test_data_used !== true
    || [value.physical_validation, value.calibrated_probability, value.independent_evaluation, value.automatic_model_promotion, value.model_selection_performed, value.parameter_fitting_performed, value.new_trajectory_acquisition, value.physical_alias_resolution_verified, value.camera_started, value.provider_calls, value.store_written].some(v => v !== false)
    || !object(value.coverage) || !Array.isArray(value.groups) || value.groups.length !== 4 || !Array.isArray(value.models) || value.models.length !== 5
    || !Array.isArray(value.limitations) || !value.limitations.length || !value.limitations.every(x => typeof x === "string" && x.length > 0)) return fail();
  const coordinates=value.coordinate_system;
  if (!object(coordinates) || coordinates.position_units !== "m" || coordinates.velocity_units !== "m/s" || coordinates.projection !== "spherical_azimuthal_equidistant" || coordinates.earth_mean_radius_m !== 6_371_008.8 || coordinates.position_error !== "great_circle_on_declared_mean_radius_sphere") return fail();
  const hash=(v:unknown):v is string=>typeof v === "string"&&/^[a-f0-9]{64}$/.test(v);
  if (!hash(value.protocol_sha256) || !hash(value.implementation_receipt_sha256) || !hash(value.original_implementation_receipt_sha256) || !object(value.provenance) || value.provenance.integrity_verified !== true || !Array.isArray(value.provenance.sources) || value.provenance.sources.length !== 4 || !object(value.replay) || value.replay.verified_numeric_replay !== true || !hash(value.replay.reference_report_sha256)) return fail();
  const sourceIds=new Set<string>();
  for (const source of value.provenance.sources) {
    if (!object(source) || typeof source.drifter_id !== "string" || !DRIFTERS.includes(source.drifter_id) || sourceIds.has(source.drifter_id) || !hash(source.sha256) || !Number.isInteger(source.bytes) || (source.bytes as number)<=0 || typeof source.source_url !== "string" || !/^https:\/\/[^/]*\.noaa\.gov\//.test(source.source_url)) return fail();
    sourceIds.add(source.drifter_id);
  }
  const c = value.coverage;
  if (!Object.entries({ target_groups:6, acquired_groups:4, missing_groups:2, models:5, horizons:6, planned_outcomes:180, attempted_outcomes:120, unique_observed_intervals:24 }).every(([key,n]) => c[key] === n)) return fail();
  const ids = new Set<string>(); let scored = 0;
  for (const g of value.groups) {
    if (!object(g) || typeof g.drifter_id !== "string" || !DRIFTERS.includes(g.drifter_id) || ids.has(g.drifter_id) || typeof g.block_id !== "string" || !/^[\w.:-]{1,200}$/.test(g.block_id)
      || !object(g.coordinate_system) || !finite(g.coordinate_system.origin_latitude_deg) || Math.abs(g.coordinate_system.origin_latitude_deg) > 90 || !finite(g.coordinate_system.origin_longitude_deg) || Math.abs(g.coordinate_system.origin_longitude_deg) > 180
      || !Array.isArray(g.training_track) || g.training_track.length !== 18 || !g.training_track.every(point) || !Array.isArray(g.heldout_track) || g.heldout_track.length !== 6 || !g.heldout_track.every(point)
      || !Array.isArray(g.models) || g.models.length !== 5) return fail();
    ids.add(g.drifter_id);
    const observations = [...g.training_track, ...g.heldout_track] as KalmanPoint[], start = utc(observations[0].time_utc)!;
    if (!observations.every((p,i) => utc(p.time_utc) === start + i*3_600_000 && sameProjection(p,g.coordinate_system as {origin_latitude_deg:number;origin_longitude_deg:number}))) return fail();
    if (g.coordinate_system.origin_latitude_deg !== observations[0].latitude_deg || g.coordinate_system.origin_longitude_deg !== observations[0].longitude_deg) return fail();
    const rawAnchor = observations[17];
    for (const [index,t] of g.models.entries()) {
      if (!object(t) || t.id !== KALMAN_MODEL_IDS[index] || typeof t.label !== "string" || !t.label.length || !object(t.parameters) || !Array.isArray(t.predictions) || t.predictions.length !== 6 || !["SCORED","FAILED"].includes(t.status as string)) return fail();
      const kalman = t.id === "kalman_cv";
      if (kalman && t.status === "SCORED" && (t.parameters.position_std_m !== 100 || t.parameters.measurement_variance_m2 !== 10_000 || t.parameters.acceleration_spectral_density_m2_s3 !== 1e-6 || t.parameters.forecast_start !== "FILTERED_LAST_TRAINING_STATE" || t.parameters.parameter_fitting_performed !== false || t.parameters.noaa_velocity_uncertainty_used !== false)) return fail();
      if (t.status === "FAILED") {
        if (t.forecast_anchor !== null || t.metrics !== null || !Array.isArray(t.reason_codes) || !t.reason_codes.length || !t.predictions.every((p,j) => object(p) && p.horizon_hours === j+1 && utc(p.time_utc) === start + (18+j)*3_600_000 && p.status === "FAILED" && Array.isArray(p.reason_codes) && p.reason_codes.length > 0 && p.reason_codes.every(x => typeof x === "string") && [p.latitude_deg,p.longitude_deg,p.x_m,p.y_m,p.position_error_m,p.position_covariance_m2,p.observation_covariance_m2,p.ellipse_hits].every(x => x === null))) return fail();
        continue;
      }
      if (!object(t.forecast_anchor) || !finite(t.forecast_anchor.x_m) || !finite(t.forecast_anchor.y_m) || Math.hypot(t.forecast_anchor.x_m,t.forecast_anchor.y_m) > 50_000 || t.forecast_anchor.time_utc !== rawAnchor.time_utc || !metric(t.metrics)) return fail();
      if (!kalman && (t.parameters.forecast_start !== "RAW_LAST_TRAINING_POSITION" || !close(t.forecast_anchor.x_m,rawAnchor.x_m) || !close(t.forecast_anchor.y_m,rawAnchor.y_m))) return fail();
      let totalError = 0, vectorSquared = 0, previousPrediction = t.forecast_anchor, previousObservation = rawAnchor;
      for (const [j,p] of t.predictions.entries()) {
        if (!point(p) || !object(p) || p.status !== "SCORED" || p.horizon_hours !== j+1 || p.time_utc !== observations[18+j].time_utc || !nonnegative(p.position_error_m) || !Array.isArray(p.reason_codes) || p.reason_codes.length) return fail();
        const actual = observations[18+j];
        if (!sameProjection(p,g.coordinate_system as {origin_latitude_deg:number;origin_longitude_deg:number}) || !close(p.position_error_m, greatCircle(p,actual))) return fail();
        const dx = (p.x_m - (previousPrediction.x_m as number) - actual.x_m + previousObservation.x_m)/3600;
        const dy = (p.y_m - (previousPrediction.y_m as number) - actual.y_m + previousObservation.y_m)/3600;
        vectorSquared += dx*dx+dy*dy; totalError += p.position_error_m;
        if (kalman) {
          if (!covariance(p.position_covariance_m2) || !covariance(p.observation_covariance_m2) || !object(p.ellipse_hits) || typeof p.ellipse_hits.nominal50 !== "boolean" || typeof p.ellipse_hits.nominal90 !== "boolean") return fail();
          const a=p.position_covariance_m2, b=p.observation_covariance_m2;
          if (!close(b[0][0],a[0][0]+10_000) || !close(b[1][1],a[1][1]+10_000) || !close(b[0][1],a[0][1]) || !close(b[1][0],a[1][0])) return fail();
          const ex=actual.x_m-p.x_m, ey=actual.y_m-p.y_m, determinant=b[0][0]*b[1][1]-b[0][1]*b[1][0];
          const d=(b[1][1]*ex*ex-(b[0][1]+b[1][0])*ex*ey+b[0][0]*ey*ey)/determinant;
          if (p.ellipse_hits.nominal50 !== (d <= -2*Math.log(.5)) || p.ellipse_hits.nominal90 !== (d <= -2*Math.log(.1))) return fail();
        } else if ([p.position_covariance_m2,p.observation_covariance_m2,p.ellipse_hits].some(x => x !== null)) return fail();
        previousPrediction=p; previousObservation=actual;
      }
      const last=t.predictions[5] as Prediction;
      if (!close(t.metrics.ade_m,totalError/6) || !close(t.metrics.fde_m,last.position_error_m) || !close(t.metrics.vector_rmse_m_s,Math.sqrt(vectorSquared/6))) return fail();
      scored += 6;
    }
  }
  if (c.scored_outcomes !== scored || c.failed_outcomes !== 120-scored || c.common_acquired_cohort_complete !== (scored === 120) || value.status !== (scored === 120 ? "COMPLETED" : "INCOMPLETE_OUTCOMES")) return fail();
  const report = value as unknown as KalmanReport;
  for (const [i,m] of report.models.entries()) {
    const tracks=report.groups.map(g=>g.models[i]).filter(t=>t.status === "SCORED");
    if (m.id !== KALMAN_MODEL_IDS[i] || typeof m.label !== "string" || m.complete_groups !== tracks.length) return fail();
    if (scored !== 120) { if (m.metrics !== null) return fail(); continue; }
    if (!metric(m.metrics) || !close(m.metrics.ade_m,tracks.reduce((s,t)=>s+t.metrics!.ade_m,0)/4) || !close(m.metrics.fde_m,tracks.reduce((s,t)=>s+t.metrics!.fde_m,0)/4) || !close(m.metrics.vector_rmse_m_s,Math.sqrt(tracks.reduce((s,t)=>s+t.metrics!.vector_rmse_m_s**2,0)/4))) return fail();
  }
  // Uncertainty is a model-assumption diagnostic, never a calibrated confidence claim.
  const kalmanTracks=report.groups.map(g=>g.models[4]);
  const u=report.uncertainty;
  if (!u || u.kind !== "UNCALIBRATED_OBSERVATION_PREDICTIVE_ELLIPSE_HITS" || u.comparison_covariance !== "position_covariance_plus_assumed_R" || !object(u.chi2_thresholds) || !close(u.chi2_thresholds.nominal50,-2*Math.log(.5)) || !close(u.chi2_thresholds.nominal90,-2*Math.log(.1)) || !Array.isArray(u.per_drifter) || u.per_drifter.length !== 4) return fail();
  for (const [i,row] of u.per_drifter.entries()) {
    if (!object(row) || row.drifter_id !== report.groups[i].drifter_id) return fail();
    if (kalmanTracks[i].status === "FAILED") {
      if (row.scored_count !== 0 || [row.nominal50_hit_count,row.nominal90_hit_count,row.nominal50_hit_fraction,row.nominal90_hit_fraction].some(v=>v!==null)) return fail();
      continue;
    }
    const ps=kalmanTracks[i].predictions as Prediction[];
    if (row.scored_count !== 6) return fail();
    for (const key of ["nominal50","nominal90"] as const) {
      const count=ps.filter(p=>p.ellipse_hits![key]).length;
      if (row[`${key}_hit_count`] !== count || !finite(row[`${key}_hit_fraction`]) || !close(row[`${key}_hit_fraction`]!,count/6)) return fail();
    }
  }
  if (scored !== 120) { if (u.fraction_ranges !== null) return fail(); }
  else {
    if (!object(u.fraction_ranges)) return fail();
    for (const key of ["nominal50","nominal90"] as const) {
      const fractions=u.per_drifter.map(r=>r[`${key}_hit_fraction`]!), range=u.fraction_ranges[key];
      if (!object(range) || !close(range.min,Math.min(...fractions)) || !close(range.max,Math.max(...fractions))) return fail();
    }
  }
  return report;
}
