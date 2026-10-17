export const MAX_MULTI_DRIFTER_BYTES = 400_000;
export const STUDY_MODELS = ["stationary", "last_drift", "mean_drift", "ridge_ar1"] as const;
export const STUDY_BASELINES = ["stationary", "last_drift", "mean_drift"] as const;
export type StudyModel = typeof STUDY_MODELS[number];
type Outcome = { drifter_id: string; block_id: string; model_id: StudyModel; horizon_hours: number; time_utc: string | null; status: "SCORED" | "FAILED"; error_m: number | null; latitude_deg: number | null; longitude_deg: number | null; reason_codes: string[] };
type PairSummary = { count: number; mean_delta_m: number; median_delta_m: number; min_delta_m: number; max_delta_m: number; candidate_lower_error_count: number; equal_error_count: number; candidate_higher_error_count: number; skill_vs_baseline: number | null; reason_codes: string[] };
export type MultiDrifterReport = {
  schema_version: 1; kind: "MULTI_DRIFTER_RETROSPECTIVE_STUDY"; status: "COMPLETED" | "PARTIAL_COVERAGE" | "NO_SELECTED_GROUPS";
  data_origin: "REAL_HISTORICAL_NOAA_DRIFTERS"; study_id: string; test_data_used: true;
  model_selection_performed: false; calibrated_probability: false; physical_validation: false;
  automatic_model_promotion: false; independent_replication_verified: false; statistical_independence: false;
  metric_scope: "ACQUIRED_DECLARED_COHORT_NOT_FULL_PLANNED_TARGET";
  protocol: { sha256: string; selection_sha256: string; manifest_sha256: string; implementation_receipt_sha256: string; frozen_at_utc: string; selection_frozen_at_utc: string; implementation_frozen_at_utc: string; training_count: 18; horizons_hours: number[]; model_ids: StudyModel[]; development_only_ids: string[]; selection_method: unknown };
  coverage: { target_groups: number; declared_groups: number; eligible_groups: number; complete_groups: number; target_outcomes: number; attempted_outcomes: number; scored_outcomes: number; failed_outcomes: number; missing_selection_slots: number; selection_complete: boolean; acquired_cohort_complete: boolean; sampling_coverage_fraction: number; model_prediction_coverage_fraction: number };
  selection_failures: { block_id: string; status: string; reason: string; source_url: string; selected_count: number; target_count: number }[];
  groups: { drifter_id: string; block_id: string; status: string; eligible: boolean; reason_codes: string[]; source_url: string }[];
  outcomes: Outcome[];
  trajectory_summaries: { drifter_id: string; model_id: StudyModel; attempted_horizons: number; scored_horizons: number; failed_horizons: number; mean_error_m: number | null; rmse_error_m: number | null; endpoint_error_m: number | null; parameters: unknown }[];
  models: { id: StudyModel; macro: { attempted_groups: number; complete_groups: number; failed_groups: number; mean_trajectory_error_m: number | null; scope: string }; per_horizon: { horizon_hours: number; attempted_groups: number; scored_groups: number; failed_groups: number; mean_error_m: number | null; rmse_error_m: number | null }[] }[];
  paired_comparisons: { candidate_id: "ridge_ar1"; baseline_id: string; delta_definition: string; attempted_groups: number; scored_groups: number; failed_groups: number; summary: PairSummary | null; reason_codes: string[] }[];
  provenance: { provider: string; metadata_url: string; product_doi: string; license_name: string; license_url: string; integrity_verified: true; sources: { drifter_id: string; block_id: string; source_url: string; sha256: string; bytes: number; retrieved_at_utc: string; status: string }[] };
  limitations: string[];
};
const record = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const integer = (v: unknown): v is number => finite(v) && Number.isInteger(v) && v >= 0 && v <= 1000;
const error = (v: unknown): v is number | null => v === null || finite(v) && v >= 0;
const fraction = (v: unknown): v is number => finite(v) && v >= 0 && v <= 1;
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.length <= 40 && v.every(x => typeof x === "string" && x.length <= 5_000);
const sha = (v: unknown) => typeof v === "string" && /^[a-f0-9]{64}$/.test(v);
const identifier = (v: unknown): v is string => typeof v === "string" && /^[A-Za-z0-9_.:-]{1,150}$/.test(v);
const utc = (v: unknown): v is string => typeof v === "string" && /(?:Z|\+00:00)$/.test(v) && Number.isFinite(Date.parse(v));
function finiteJson(v: unknown, depth = 0, budget = { n: 0 }): boolean {
  if (++budget.n > 50_000 || depth > 35) return false;
  if (Array.isArray(v)) return v.every(x => finiteJson(x, depth + 1, budget));
  if (record(v)) return Object.values(v).every(x => finiteJson(x, depth + 1, budget));
  return v === null || typeof v === "boolean" || typeof v === "string" && v.length <= 8_000 || finite(v);
}
export function officialNoaaUrl(value: unknown): value is string {
  if (typeof value !== "string" || value.length > 4_000) return false;
  try { const u = new URL(value); return u.protocol === "https:" && u.hostname === "erddap.aoml.noaa.gov" && !u.username && !u.password && !u.port && u.pathname.startsWith("/gdp/erddap/"); } catch { return false; }
}
function ids(values: unknown, expected: readonly string[]): boolean {
  return Array.isArray(values) && values.length === expected.length && expected.every(id => values.filter(x => x === id).length === 1);
}
function checked(value: unknown): boolean {
  if (!record(value) || !finiteJson(value) || value.schema_version !== 1 || value.kind !== "MULTI_DRIFTER_RETROSPECTIVE_STUDY" || !["COMPLETED", "PARTIAL_COVERAGE", "NO_SELECTED_GROUPS"].includes(String(value.status))
    || value.data_origin !== "REAL_HISTORICAL_NOAA_DRIFTERS" || !identifier(value.study_id) || value.test_data_used !== true
    || [value.model_selection_performed, value.calibrated_probability, value.physical_validation, value.automatic_model_promotion, value.independent_replication_verified, value.statistical_independence].some(x => x !== false)
    || value.metric_scope !== "ACQUIRED_DECLARED_COHORT_NOT_FULL_PLANNED_TARGET" || !record(value.protocol) || !record(value.coverage)
    || !Array.isArray(value.groups) || !Array.isArray(value.outcomes) || !Array.isArray(value.trajectory_summaries) || !Array.isArray(value.models) || !Array.isArray(value.paired_comparisons)
    || !Array.isArray(value.selection_failures) || !strings(value.limitations) || !record(value.provenance)) return false;
  if (![value.groups, value.outcomes, value.trajectory_summaries, value.models, value.paired_comparisons].every(rows => rows.every(record))) return false;
  const p = value.protocol, c = value.coverage, groups = value.groups as Record<string, unknown>[], outcomes = value.outcomes as Record<string, unknown>[], models = value.models as Record<string, unknown>[], trajectories = value.trajectory_summaries as Record<string, unknown>[];
  if (![p.sha256, p.selection_sha256, p.manifest_sha256, p.implementation_receipt_sha256].every(sha) || !utc(p.frozen_at_utc) || !utc(p.selection_frozen_at_utc) || !utc(p.implementation_frozen_at_utc) || Date.parse(p.frozen_at_utc) > Date.parse(p.selection_frozen_at_utc) || Date.parse(p.selection_frozen_at_utc) > Date.parse(p.implementation_frozen_at_utc)
    || p.training_count !== 18 || !(Array.isArray(p.horizons_hours) && p.horizons_hours.length === 6 && p.horizons_hours.every((x, i) => x === i + 1))
    || !ids(p.model_ids, STUDY_MODELS) || !strings(p.development_only_ids) || !p.development_only_ids.includes("8707978")) return false;
  if (![c.target_groups, c.declared_groups, c.eligible_groups, c.complete_groups, c.target_outcomes, c.attempted_outcomes, c.scored_outcomes, c.failed_outcomes, c.missing_selection_slots].every(integer)
    || c.target_groups !== 6 || (c.declared_groups as number) > 6 || c.declared_groups !== groups.length || c.target_outcomes !== 144 || c.attempted_outcomes !== groups.length * 24
    || (c.scored_outcomes as number) + (c.failed_outcomes as number) !== c.attempted_outcomes || outcomes.length !== c.attempted_outcomes
    || c.missing_selection_slots !== 6 - groups.length || c.selection_complete !== (groups.length === 6)
    || !fraction(c.sampling_coverage_fraction) || Math.abs(c.sampling_coverage_fraction - groups.length / 6) > 1e-10
    || !fraction(c.model_prediction_coverage_fraction) || Math.abs(c.model_prediction_coverage_fraction - (outcomes.length ? (c.scored_outcomes as number) / outcomes.length : 0)) > 1e-10) return false;
  if (!groups.every(g => record(g) && identifier(g.drifter_id) && identifier(g.block_id) && typeof g.status === "string" && typeof g.eligible === "boolean" && strings(g.reason_codes) && officialNoaaUrl(g.source_url) && !(p.development_only_ids as string[]).includes(g.drifter_id))
    || new Set(groups.map(g => g.drifter_id)).size !== groups.length || groups.filter(g => g.eligible).length !== c.eligible_groups) return false;
  let scored = 0, complete = 0;
  for (const g of groups) {
    let completeGroup = true;
    for (const model of STUDY_MODELS) for (let h = 1; h <= 6; h++) {
      const matches = outcomes.filter(o => record(o) && o.drifter_id === g.drifter_id && o.block_id === g.block_id && o.model_id === model && o.horizon_hours === h);
      if (matches.length !== 1) return false;
      const o = matches[0];
      if (!strings(o.reason_codes) || !(o.time_utc === null || utc(o.time_utc))) return false;
      if (o.status === "SCORED") {
        if (!finite(o.error_m) || o.error_m < 0 || !finite(o.latitude_deg) || Math.abs(o.latitude_deg) > 90 || !finite(o.longitude_deg) || Math.abs(o.longitude_deg) > 180 || !utc(o.time_utc)) return false;
        scored++;
      } else if (o.status === "FAILED" && o.error_m === null && o.latitude_deg === null && o.longitude_deg === null && o.reason_codes.length) completeGroup = false;
      else return false;
    }
    if (completeGroup) complete++;
  }
  if (scored !== c.scored_outcomes || complete !== c.complete_groups || value.status !== (groups.length === 0 ? "NO_SELECTED_GROUPS" : complete === 6 && groups.length === 6 ? "COMPLETED" : "PARTIAL_COVERAGE")) return false;
  const allAcquiredComplete = groups.length > 0 && complete === groups.length;
  if (c.acquired_cohort_complete !== allAcquiredComplete) return false;
  if (models.length !== 4 || !STUDY_MODELS.every(id => models.filter(m => record(m) && m.id === id).length === 1) || trajectories.length !== groups.length * 4) return false;
  for (const model of models) {
    if (!record(model) || !record(model.macro) || !Array.isArray(model.per_horizon) || model.per_horizon.length !== 6) return false;
    const m = model.macro;
    const completeForModel = groups.filter(g => outcomes.filter(o => o.drifter_id === g.drifter_id && o.model_id === model.id && o.status === "SCORED").length === 6).length;
    if (m.attempted_groups !== groups.length || !integer(m.complete_groups) || !integer(m.failed_groups) || m.complete_groups + m.failed_groups !== groups.length
      || m.complete_groups !== completeForModel
      || m.scope !== value.metric_scope || !error(m.mean_trajectory_error_m) || (!allAcquiredComplete && m.mean_trajectory_error_m !== null)) return false;
    for (const [i, row] of model.per_horizon.entries()) {
      if (!record(row) || row.horizon_hours !== i + 1 || row.attempted_groups !== groups.length || !integer(row.scored_groups) || !integer(row.failed_groups) || row.scored_groups + row.failed_groups !== groups.length
        || row.scored_groups !== outcomes.filter(o => o.model_id === model.id && o.horizon_hours === i + 1 && o.status === "SCORED").length
        || !error(row.mean_error_m) || !error(row.rmse_error_m) || (!allAcquiredComplete && (row.mean_error_m !== null || row.rmse_error_m !== null))) return false;
    }
  }
  for (const g of groups) for (const model of STUDY_MODELS) {
    const matches = trajectories.filter(t => record(t) && t.drifter_id === g.drifter_id && t.model_id === model);
    if (matches.length !== 1) return false;
    const t = matches[0];
    if (t.attempted_horizons !== 6 || !integer(t.scored_horizons) || !integer(t.failed_horizons) || t.scored_horizons + t.failed_horizons !== 6 || ![t.mean_error_m, t.rmse_error_m, t.endpoint_error_m].every(error)
      || t.scored_horizons !== outcomes.filter(o => o.drifter_id === g.drifter_id && o.model_id === model && o.status === "SCORED").length
      || t.failed_horizons > 0 && (t.mean_error_m !== null || t.rmse_error_m !== null || t.endpoint_error_m !== null)) return false;
  }
  const pairs = value.paired_comparisons;
  if (pairs.length !== 3 || !STUDY_BASELINES.every(id => pairs.filter(x => record(x) && x.baseline_id === id).length === 1)) return false;
  for (const pair of pairs) {
    if (!record(pair) || pair.candidate_id !== "ridge_ar1" || pair.delta_definition !== "candidate_minus_baseline_error_m" || pair.attempted_groups !== groups.length
      || !integer(pair.scored_groups) || !integer(pair.failed_groups) || pair.scored_groups + pair.failed_groups !== groups.length || !strings(pair.reason_codes)) return false;
    const completePairs = groups.filter(g => ["ridge_ar1", pair.baseline_id].every(model => outcomes.filter(o => o.drifter_id === g.drifter_id && o.model_id === model && o.status === "SCORED").length === 6)).length;
    if (pair.scored_groups !== completePairs) return false;
    if (!allAcquiredComplete) { if (pair.summary !== null) return false; }
    else {
      const s = pair.summary;
      if (!record(s) || s.count !== groups.length || ![s.mean_delta_m, s.median_delta_m, s.min_delta_m, s.max_delta_m].every(finite)
        || ![s.candidate_lower_error_count, s.equal_error_count, s.candidate_higher_error_count].every(integer)
        || (s.candidate_lower_error_count as number) + (s.equal_error_count as number) + (s.candidate_higher_error_count as number) !== groups.length || !strings(s.reason_codes)
        || (s.skill_vs_baseline === null ? !s.reason_codes.includes("ZERO_BASELINE_ERROR") : !finite(s.skill_vs_baseline) || s.skill_vs_baseline > 1)) return false;
    }
  }
  const provenance = value.provenance;
  if (provenance.integrity_verified !== true || !officialNoaaUrl(provenance.metadata_url) || typeof provenance.provider !== "string" || typeof provenance.product_doi !== "string"
    || !Array.isArray(provenance.sources) || provenance.sources.length !== groups.length || !provenance.sources.every(s => record(s) && groups.some(g => g.drifter_id === s.drifter_id && g.block_id === s.block_id) && officialNoaaUrl(s.source_url) && sha(s.sha256) && finite(s.bytes) && Number.isInteger(s.bytes) && s.bytes > 0 && s.bytes <= 100_000 && utc(s.retrieved_at_utc))
    || !groups.every(g => (provenance.sources as unknown[]).filter(s => record(s) && s.drifter_id === g.drifter_id && s.block_id === g.block_id).length === 1)) return false;
  return value.selection_failures.every(f => record(f) && identifier(f.block_id) && typeof f.status === "string" && typeof f.reason === "string" && officialNoaaUrl(f.source_url) && integer(f.selected_count) && integer(f.target_count));
}

export function multiDrifterReport(value: unknown): MultiDrifterReport {
  if (!checked(value)) throw new Error("The multi-drifter report has an unsupported scope, coverage or failure matrix. No study result was accepted.");
  return value as MultiDrifterReport;
}
export async function readMultiDrifter(response: Response): Promise<MultiDrifterReport> {
  if (!response.body || Number(response.headers.get("content-length")) > MAX_MULTI_DRIFTER_BYTES) throw new Error("The multi-drifter response is empty or exceeds its bounded size.");
  const reader = response.body.getReader(), chunks: Uint8Array[] = []; let size = 0;
  try { for (;;) { const part = await reader.read(); if (part.done) break; size += part.value.byteLength; if (size > MAX_MULTI_DRIFTER_BYTES) { await reader.cancel(); throw new Error("The multi-drifter response exceeds its bounded size."); } chunks.push(part.value); } }
  finally { reader.releaseLock(); }
  const bytes = new Uint8Array(size); let offset = 0; for (const part of chunks) { bytes.set(part, offset); offset += part.byteLength; }
  let value: unknown; try { value = JSON.parse(new TextDecoder().decode(bytes)); } catch { throw new Error(`Unreadable multi-drifter JSON (HTTP ${response.status}).`); }
  if (!response.ok) throw new Error(record(value) && typeof value.detail === "string" ? value.detail.slice(0, 500) : `Multi-drifter study unavailable (HTTP ${response.status}).`);
  return multiDrifterReport(value);
}
