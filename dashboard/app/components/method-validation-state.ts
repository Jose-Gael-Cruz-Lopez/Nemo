export const MAX_METHOD_EXAMPLE_BYTES = 250_000;
type Layout = "baseline" | "intervention";
type Bounds = { lower: number; upper: number; denominator?: number };
export type MethodStats = { planned: number; released: number; missing_planned: number; zone_entries: number; captured_before_entry: number; no_entry: number; unresolved: number; entry_rate_bounds: Bounds; observed_entry_rate_bounds: Bounds };
type Prediction = { zone_entry_lower_fraction: number; zone_entry_upper_fraction: number; unsupported_count: number; zone_entry_fraction: number };
export type MethodExample = {
  id: "unresolved" | "positive_control"; label: string; data_origin: "SYNTHETIC";
  not_current_case: true; physical_validation: false; method_rerun: true;
  provenance: { input: { path: string; sha256: string; bytes: number }; integrity_verified: true; expected_report: { path: string; sha256: string; bytes: number } | null; expected_report_match: true | null };
  report: {
    schema_version: "validation_report_v1"; id: string; content_hash: string;
    comparison_id: string; numerical_replay_verified: true; physical_validation: false;
    original_private_hash_verified: false; supports_significance_or_causal_claim: false;
    data_origin: "SYNTHETIC";
    by_origin: Record<"SYNTHETIC_DEMO" | "OPERATOR_REPORTED_PHYSICAL", { layouts: Record<Layout, MethodStats>; by_source: { source_id: string; baseline: MethodStats; intervention: MethodStats }[]; plan: { expected_total: number; recorded_total: number; complete: boolean; balanced: boolean; order_followed: boolean } }>;
    diagnostics: { data_origin: string; source_id: string; scenario_id: string; layouts: Record<Layout, { predicted: Prediction; observed: MethodStats }> }[];
    selected_layout_usefulness: Record<string, { status: string; selected_layout: Layout; physical_results_claimed: false }>;
    next_measurement: { kind: string; source_id?: string; scenario_id?: string; reason_codes: string[]; explanation: string; region_identified: false; region_cm: null };
    source_identification: { evaluated: false }; limitations: string[];
  };
};
export type MethodReplay = {
  schema_version: "prevention_method_replay_v1"; kind: "SYNTHETIC_REPLAY_EXAMPLE"; status: "COMPLETED";
  not_current_case: true; physical_validation: false; method_rerun: true; examples_are_independent: false;
  protocols: { development: "development-prevention-v1"; validation: "heldout-prevention-v1" };
  examples: MethodExample[]; limitations: string[]; current_case_requirements: string[];
};
const record = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const count = (v: unknown): v is number => finite(v) && Number.isInteger(v) && v >= 0 && v <= 100;
const fraction = (v: unknown): v is number => finite(v) && v >= 0 && v <= 1;
const sha = (v: unknown): v is string => typeof v === "string" && /^[a-f0-9]{64}$/.test(v);
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.length <= 30 && v.every(x => typeof x === "string" && x.length <= 2_000);
function safeJson(v: unknown, depth = 0, budget = { n: 0 }): boolean {
  if (++budget.n > 30_000 || depth > 35) return false;
  if (Array.isArray(v)) return v.every(x => safeJson(x, depth + 1, budget));
  if (record(v)) return Object.values(v).every(x => safeJson(x, depth + 1, budget));
  return v === null || typeof v === "boolean" || typeof v === "string" && v.length <= 5_000 || finite(v);
}
function bounds(v: unknown): boolean { return record(v) && fraction(v.lower) && fraction(v.upper) && v.lower <= v.upper; }
function stats(v: unknown): boolean {
  return record(v) && [v.planned, v.released, v.missing_planned, v.zone_entries, v.captured_before_entry, v.no_entry, v.unresolved].every(count)
    && bounds(v.entry_rate_bounds) && bounds(v.observed_entry_rate_bounds)
    && (v.zone_entries as number) + (v.captured_before_entry as number) + (v.no_entry as number) + (v.unresolved as number) === v.released;
}
function artifact(v: unknown): boolean { return record(v) && typeof v.path === "string" && v.path.startsWith("tests/fixtures/") && !v.path.includes("..") && sha(v.sha256) && countBytes(v.bytes); }
function countBytes(v: unknown): boolean { return finite(v) && Number.isInteger(v) && v > 0 && v <= 150_000; }
const STATUSES = ["NO_NEW_TRIALS", "DESCRIPTIVELY_USEFUL_ON_REPORTED_NEW_TRIALS", "CONTRADICTED_BY_REPORTED_NEW_TRIALS", "UNRESOLVED_ON_REPORTED_NEW_TRIALS"];
function example(v: unknown): boolean {
  if (!record(v) || !["unresolved", "positive_control"].includes(String(v.id)) || typeof v.label !== "string"
    || v.data_origin !== "SYNTHETIC" || v.not_current_case !== true || v.physical_validation !== false || v.method_rerun !== true
    || !record(v.provenance) || v.provenance.integrity_verified !== true || !artifact(v.provenance.input)
    || (v.id === "unresolved" ? v.provenance.expected_report_match !== true || !artifact(v.provenance.expected_report) : v.provenance.expected_report_match !== null || v.provenance.expected_report !== null)
    || !record(v.report)) return false;
  const r = v.report;
  if (r.schema_version !== "validation_report_v1" || typeof r.id !== "string" || typeof r.comparison_id !== "string" || !sha(r.content_hash)
    || r.data_origin !== "SYNTHETIC" || r.numerical_replay_verified !== true || r.original_private_hash_verified !== false || r.physical_validation !== false
    || r.supports_significance_or_causal_claim !== false || !record(r.source_identification) || r.source_identification.evaluated !== false
    || !record(r.by_origin) || !record(r.selected_layout_usefulness) || !Array.isArray(r.diagnostics) || r.diagnostics.length > 30
    || !strings(r.limitations) || !record(r.next_measurement) || !["INDEPENDENT_PAIRED_TRIAL", "INDEPENDENT_LAYOUT_DRIFT", "NO_USEFUL_NEXT_MEASUREMENT_IDENTIFIED"].includes(String(r.next_measurement.kind))
    || !strings(r.next_measurement.reason_codes) || typeof r.next_measurement.explanation !== "string" || r.next_measurement.region_identified !== false || r.next_measurement.region_cm !== null) return false;
  for (const origin of ["SYNTHETIC_DEMO", "OPERATOR_REPORTED_PHYSICAL"]) {
    const group = r.by_origin[origin], conclusion = r.selected_layout_usefulness[origin];
    if (!record(group) || !record(group.layouts) || !["baseline", "intervention"].every(layout => stats((group.layouts as Record<string, unknown>)[layout]))
      || !record(group.plan) || group.plan.expected_total !== 8 || group.plan.recorded_total !== (origin === "SYNTHETIC_DEMO" ? 8 : 0)
      || !Array.isArray(group.by_source) || group.by_source.length !== 2 || !["A", "B"].every(id => (group.by_source as unknown[]).filter(row => record(row) && row.source_id === id).length === 1)
      || !group.by_source.every(row => record(row) && stats(row.baseline) && stats(row.intervention))
      || !record(conclusion) || !STATUSES.includes(String(conclusion.status)) || !["baseline", "intervention"].includes(String(conclusion.selected_layout)) || conclusion.physical_results_claimed !== false) return false;
  }
  for (const id of ["A", "B"]) {
    const nominal = r.diagnostics.filter(row => record(row) && row.data_origin === "SYNTHETIC_DEMO" && row.source_id === id && row.scenario_id === "nominal");
    if (nominal.length !== 1 || !record(nominal[0]) || !record(nominal[0].layouts)) return false;
    for (const layout of ["baseline", "intervention"]) {
      const value = nominal[0].layouts[layout];
      if (!record(value) || !record(value.predicted) || !stats(value.observed) || !fraction(value.predicted.zone_entry_fraction)
        || !fraction(value.predicted.zone_entry_lower_fraction) || !fraction(value.predicted.zone_entry_upper_fraction)
        || value.predicted.zone_entry_lower_fraction > value.predicted.zone_entry_upper_fraction || !count(value.predicted.unsupported_count)) return false;
    }
  }
  return true;
}

/** This parser never accepts uploaded Trace 2 JSON or upgrades a Trace 3 receipt. */
export function methodReplay(value: unknown): MethodReplay {
  if (!record(value) || !safeJson(value) || value.schema_version !== "prevention_method_replay_v1" || value.kind !== "SYNTHETIC_REPLAY_EXAMPLE" || value.status !== "COMPLETED"
    || value.not_current_case !== true || value.physical_validation !== false || value.method_rerun !== true || value.examples_are_independent !== false
    || !record(value.protocols) || value.protocols.development !== "development-prevention-v1" || value.protocols.validation !== "heldout-prevention-v1"
    || !strings(value.limitations) || !strings(value.current_case_requirements) || !Array.isArray(value.examples) || value.examples.length !== 2
    || !value.examples.every(example) || !["unresolved", "positive_control"].every(id => (value.examples as unknown[]).filter(item => record(item) && item.id === id).length === 1)) throw new Error("The method example has an unsupported format or scientific scope. No report was accepted.");
  return value as MethodReplay;
}

export async function readMethodReplay(response: Response): Promise<MethodReplay> {
  if (!response.body || Number(response.headers.get("content-length")) > MAX_METHOD_EXAMPLE_BYTES) throw new Error("The method example response is empty or exceeds its bounded size.");
  const reader = response.body.getReader(), chunks: Uint8Array[] = []; let size = 0;
  try {
    for (;;) {
      const part = await reader.read(); if (part.done) break; size += part.value.byteLength;
      if (size > MAX_METHOD_EXAMPLE_BYTES) { await reader.cancel(); throw new Error("The method example exceeds its bounded size."); }
      chunks.push(part.value);
    }
  } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const part of chunks) { bytes.set(part, offset); offset += part.byteLength; }
  let value: unknown;
  try { value = JSON.parse(new TextDecoder().decode(bytes)); } catch { throw new Error(`The method example returned unreadable JSON (HTTP ${response.status}).`); }
  if (!response.ok) throw new Error(record(value) && typeof value.detail === "string" ? value.detail.slice(0, 500) : `Method replay unavailable (HTTP ${response.status}).`);
  return methodReplay(value);
}
