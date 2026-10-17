export const MAX_MOTION_ABLATION_BYTES = 180_000;
export const MOTION_MODEL_IDS = ["stationary", "last_drift", "mean_drift", "ridge_ar1"] as const;
export const MOTION_BASELINE_IDS = ["stationary", "last_drift", "mean_drift"] as const;
export type MotionModelId = typeof MOTION_MODEL_IDS[number];
export type MotionBaselineId = typeof MOTION_BASELINE_IDS[number];
type Prediction = { time_utc: string; horizon_hours: number; latitude_deg: number; longitude_deg: number; error_m: number };
export type MotionErrors = { horizon_hours: number; count: number; mean_error_m: number; median_error_m: number; min_error_m: number; max_error_m: number; rmse_error_m: number };
export type PairedMotionErrors = {
  horizon_hours: number; count: number; mean_delta_m: number; median_delta_m: number;
  min_delta_m: number; max_delta_m: number; candidate_lower_error_count: number;
  equal_error_count: number; candidate_higher_error_count: number;
  skill_vs_baseline: number | null; reason_codes: string[];
};
export type MotionAblationReport = {
  schema_version: 1; kind: "TRAINING_ONLY_MOTION_ABLATION"; status: "COMPLETED";
  data_origin: "REAL_HISTORICAL_NOAA_DRIFTER";
  test_data_used: false; model_selection_performed: false; calibrated_probability: false;
  physical_validation: false; automatic_model_promotion: false;
  split: { training_count: 18; min_prefix: 8; horizons: 6; prefix_counts: number[]; origin_count: 5; step_seconds: 3600; test_data_used: false; model_selection_performed: false };
  origins: { prefix_count: number; fit_end_utc: string; models: { id: MotionModelId; parameters: Record<string, unknown>; predictions: Prediction[] }[] }[];
  aggregates: { id: MotionModelId; per_horizon: MotionErrors[] }[];
  paired_comparisons: { candidate_id: "ridge_ar1"; baseline_id: MotionBaselineId; delta_definition: "candidate_minus_baseline_error_m"; per_horizon: PairedMotionErrors[] }[];
  limitations: string[];
  provenance: { integrity_verified: true; row_count: 24; drifter_id: "8707978"; sha256: string; source_url: string };
};
const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const nonnegative = (value: unknown): value is number => finite(value) && value >= 0;
const count = (value: unknown): value is number => finite(value) && Number.isInteger(value) && value >= 0 && value <= 5;
const strings = (value: unknown, max = 20): value is string[] => Array.isArray(value) && value.length <= max && value.every(item => typeof item === "string" && item.length <= 2_000);
const hour = (value: number) => `1987-10-03T${String(value).padStart(2, "0")}:00:00Z`;

function finiteJson(value: unknown, depth = 0, budget = { nodes: 0 }): boolean {
  if (++budget.nodes > 20_000 || depth > 30) return false;
  if (Array.isArray(value)) return value.every(item => finiteJson(item, depth + 1, budget));
  if (record(value)) return Object.values(value).every(item => finiteJson(item, depth + 1, budget));
  return value === null || typeof value === "boolean" || typeof value === "string" && value.length <= 5_000 || finite(value);
}
function uniqueModels(value: unknown, ids: readonly string[]): value is Record<string, unknown>[] {
  return Array.isArray(value) && value.length === ids.length && ids.every(id => value.filter(item => record(item) && item.id === id).length === 1);
}
function errors(value: unknown, index: number): boolean {
  return record(value) && value.horizon_hours === index + 1 && value.count === 5
    && [value.mean_error_m, value.median_error_m, value.min_error_m, value.max_error_m, value.rmse_error_m].every(nonnegative)
    && (value.min_error_m as number) <= (value.mean_error_m as number) && (value.mean_error_m as number) <= (value.max_error_m as number)
    && (value.min_error_m as number) <= (value.median_error_m as number) && (value.median_error_m as number) <= (value.max_error_m as number);
}
function pairedErrors(value: unknown, index: number): boolean {
  if (!record(value) || value.horizon_hours !== index + 1 || value.count !== 5
    || ![value.mean_delta_m, value.median_delta_m, value.min_delta_m, value.max_delta_m].every(finite)
    || ![value.candidate_lower_error_count, value.equal_error_count, value.candidate_higher_error_count].every(count)
    || (value.candidate_lower_error_count as number) + (value.equal_error_count as number) + (value.candidate_higher_error_count as number) !== 5
    || !strings(value.reason_codes)
    || (value.min_delta_m as number) > (value.mean_delta_m as number) || (value.mean_delta_m as number) > (value.max_delta_m as number)
    || (value.min_delta_m as number) > (value.median_delta_m as number) || (value.median_delta_m as number) > (value.max_delta_m as number)) return false;
  return value.skill_vs_baseline === null ? value.reason_codes.includes("ZERO_BASELINE_ERROR")
    : finite(value.skill_vs_baseline) && value.skill_vs_baseline <= 1 && !value.reason_codes.includes("ZERO_BASELINE_ERROR");
}
function noaaSource(value: unknown): value is string {
  if (typeof value !== "string" || value.length > 2_000) return false;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.hostname === "erddap.aoml.noaa.gov" && !url.username && !url.password && !url.port
      && url.pathname === "/gdp/erddap/tabledap/drifter_hourly_qc.csv";
  } catch { return false; }
}

/** Accept only the bounded, fixed training-only experiment; this does not recompute metrics. */
export function motionAblationReport(value: unknown): MotionAblationReport {
  const invalid = () => new Error("The motion ablation has an unsupported format, provenance or training-only split. No comparison was accepted.");
  if (!record(value) || !finiteJson(value) || value.schema_version !== 1 || value.kind !== "TRAINING_ONLY_MOTION_ABLATION" || value.status !== "COMPLETED"
    || value.data_origin !== "REAL_HISTORICAL_NOAA_DRIFTER"
    || [value.test_data_used, value.model_selection_performed, value.calibrated_probability, value.physical_validation, value.automatic_model_promotion].some(flag => flag !== false)
    || !record(value.split) || value.split.training_count !== 18 || value.split.min_prefix !== 8 || value.split.horizons !== 6 || value.split.origin_count !== 5
    || value.split.step_seconds !== 3600 || value.split.test_data_used !== false || value.split.model_selection_performed !== false
    || !Array.isArray(value.split.prefix_counts) || value.split.prefix_counts.length !== 5 || !value.split.prefix_counts.every((n, i) => n === i + 8)
    || !uniqueModels(value.aggregates, MOTION_MODEL_IDS) || !value.aggregates.every(model => Array.isArray(model.per_horizon) && model.per_horizon.length === 6 && model.per_horizon.every(errors))
    || !Array.isArray(value.paired_comparisons) || value.paired_comparisons.length !== 3
    || !MOTION_BASELINE_IDS.every(id => (value.paired_comparisons as unknown[]).filter(item => record(item) && item.baseline_id === id).length === 1)
    || !value.paired_comparisons.every(item => record(item) && item.candidate_id === "ridge_ar1" && item.delta_definition === "candidate_minus_baseline_error_m"
      && Array.isArray(item.per_horizon) && item.per_horizon.length === 6 && item.per_horizon.every(pairedErrors))
    || !Array.isArray(value.origins) || value.origins.length !== 5
    || !value.origins.every((origin, i) => record(origin) && origin.prefix_count === i + 8 && origin.fit_end_utc === hour(i + 7)
      && uniqueModels(origin.models, MOTION_MODEL_IDS) && origin.models.every(model => record(model.parameters) && Array.isArray(model.predictions) && model.predictions.length === 6
        && model.predictions.every((point, h) => record(point) && point.horizon_hours === h + 1 && point.time_utc === hour(i + 8 + h)
          && finite(point.latitude_deg) && Math.abs(point.latitude_deg) <= 90 && finite(point.longitude_deg) && Math.abs(point.longitude_deg) <= 180 && nonnegative(point.error_m))))
    || !strings(value.limitations, 30) || !record(value.provenance) || value.provenance.integrity_verified !== true
    || value.provenance.row_count !== 24 || value.provenance.drifter_id !== "8707978" || typeof value.provenance.sha256 !== "string"
    || !/^[a-f0-9]{64}$/.test(value.provenance.sha256) || !noaaSource(value.provenance.source_url)) throw invalid();
  return value as MotionAblationReport;
}

export function parseMotionAblation(text: string): MotionAblationReport {
  if (new TextEncoder().encode(text).byteLength > MAX_MOTION_ABLATION_BYTES) throw new Error("The motion ablation exceeded its bounded report size.");
  let value: unknown;
  try { value = JSON.parse(text); } catch { throw new Error("The API returned unreadable motion-ablation JSON. Check the backend connection."); }
  return motionAblationReport(value);
}

/** Bound received bytes before parsing, including a response without Content-Length. */
export async function readMotionAblation(response: Response): Promise<MotionAblationReport> {
  const length = response.headers.get("content-length");
  if (length !== null && Number(length) > MAX_MOTION_ABLATION_BYTES) throw new Error("The motion ablation exceeded its bounded report size.");
  if (!response.body) throw new Error("The API returned an empty motion-ablation response.");
  const reader = response.body.getReader(), chunks: Uint8Array[] = [];
  let size = 0;
  try {
    for (;;) {
      const next = await reader.read();
      if (next.done) break;
      size += next.value.byteLength;
      if (size > MAX_MOTION_ABLATION_BYTES) { await reader.cancel(); throw new Error("The motion ablation exceeded its bounded report size."); }
      chunks.push(next.value);
    }
  } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  const text = new TextDecoder().decode(bytes);
  if (!response.ok) {
    let value: unknown;
    try { value = JSON.parse(text); } catch { /* A safe status-based fallback covers non-JSON upstream errors. */ }
    const detail = record(value) && typeof value.detail === "string" ? value.detail.slice(0, 500) : `Motion ablation unavailable (HTTP ${response.status}).`;
    throw new Error(detail);
  }
  return parseMotionAblation(text);
}

/** Undefined skill remains unavailable; negative values are allowed and mean worse MAE. */
export function motionSkillLabel(value: number | null): string {
  return value === null ? "Unavailable · zero baseline error" : value.toLocaleString(undefined, { maximumFractionDigits: 3 });
}
