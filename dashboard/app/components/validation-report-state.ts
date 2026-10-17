export type ValidationScope = { comparisonId: string; caseId: string; sourceEvidenceId: string; evaluationHash: string };
export const MAX_VALIDATION_BYTES = 128_000;
const MAX_CANONICAL_BYTES = 400_000;
export const isRecord = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value);
const sha256 = (value: unknown): value is string => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);

export function validationScopeKey(scope: ValidationScope): string {
  return JSON.stringify([scope.comparisonId, scope.caseId, scope.sourceEvidenceId, scope.evaluationHash]);
}

/** Parsing a local file never constitutes acceptance or method validation. */
export function parseValidationInput(text: string): Record<string, unknown> {
  if (new TextEncoder().encode(text).byteLength > MAX_VALIDATION_BYTES) throw new Error("The validation JSON exceeds 128,000 bytes.");
  let value: unknown;
  try { value = JSON.parse(text); } catch { throw new Error("Use a complete JSON object with double-quoted field names and no trailing commas."); }
  if (!isRecord(value)) throw new Error("The report must be a JSON object; arrays and primitive values cannot be imported.");
  if (value.schema_version !== "validation_report_v1") throw new Error("Use the validation_report_v1 contract. A local JSON file has not been accepted until the server checks it.");
  return value;
}

/** Compare JSON semantics without depending on key order or float text spelling. */
function semanticJson(value: unknown, depth = 0, budget = { nodes: 0 }): string {
  if (++budget.nodes > 50_000 || depth > 40) throw new Error("The export JSON exceeds the bounded evidence structure.");
  if (Array.isArray(value)) return `[${value.map(item => semanticJson(item, depth + 1, budget)).join(",")}]`;
  if (isRecord(value)) return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${semanticJson(value[key], depth + 1, budget)}`).join(",")}}`;
  if (value === null || typeof value === "string" || typeof value === "boolean" || typeof value === "number" && Number.isFinite(value)) return JSON.stringify(value);
  throw new Error("The export contains a value outside the JSON evidence contract.");
}

export type AnalysisExport = {
  schema_version: "analysis_bundle_v1";
  payload: Record<string, unknown> & { comparison: Record<string, unknown>; evaluation_truth: { evaluation: Record<string, unknown> } };
  payload_canonical_json: string;
  payload_sha256: string;
  metadata: { exported_at_utc: string; is_current: boolean; archive_reason: string | null };
};

export async function verifiedAnalysisExport(value: unknown, scope: ValidationScope): Promise<AnalysisExport> {
  if (!isRecord(value) || value.schema_version !== "analysis_bundle_v1" || !isRecord(value.payload)
    || !isRecord(value.payload.comparison) || !isRecord(value.payload.evaluation_truth) || !isRecord(value.payload.evaluation_truth.evaluation)
    || typeof value.payload_canonical_json !== "string" || !sha256(value.payload_sha256)
    || !isRecord(value.metadata) || typeof value.metadata.exported_at_utc !== "string" || !Number.isFinite(Date.parse(value.metadata.exported_at_utc))
    || typeof value.metadata.is_current !== "boolean" || value.metadata.archive_reason !== null && typeof value.metadata.archive_reason !== "string") throw new Error("The server export has an unsupported or incomplete evidence format.");
  const payload = value.payload;
  const comparison = value.payload.comparison, evaluation = value.payload.evaluation_truth.evaluation;
  if (comparison.id !== scope.comparisonId || comparison.case_id !== scope.caseId || comparison.source_evidence_id !== scope.sourceEvidenceId
    || evaluation.comparison_id !== scope.comparisonId || evaluation.snapshot_hash !== scope.evaluationHash) throw new Error("The comparison or evaluation changed. Refresh the current evidence before preparing an export.");
  const allowed = ["comparison", "frozen_plan", "provenance", "source_evidence", "evaluation_truth", "limitations"];
  if (Object.keys(payload).some(key => !allowed.includes(key)) || allowed.some(key => !(key in payload))) throw new Error("The export payload does not match the whitelisted evidence contract.");
  const bytes = new TextEncoder().encode(value.payload_canonical_json);
  if (bytes.byteLength > MAX_CANONICAL_BYTES) throw new Error("The canonical export exceeds the bounded evidence size.");
  let canonical: unknown;
  try { canonical = JSON.parse(value.payload_canonical_json); } catch { throw new Error("The canonical export is not valid JSON."); }
  if (semanticJson(canonical) !== semanticJson(value.payload)) throw new Error("The canonical export and displayed payload differ.");
  if (!globalThis.crypto?.subtle) throw new Error("This browser cannot verify SHA-256. Open the local workspace in a browser with Web Crypto support.");
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), byte => byte.toString(16).padStart(2, "0")).join("");
  if (digest !== value.payload_sha256) throw new Error("The export integrity hash did not match. No download was prepared.");
  return value as AnalysisExport;
}

/** Preserve the exact canonical numeric text in downloaded evidence. */
export function analysisDownloadJson(bundle: AnalysisExport): string {
  const metadata = { exported_at_utc: bundle.metadata.exported_at_utc, is_current: bundle.metadata.is_current, archive_reason: bundle.metadata.archive_reason };
  return `{"schema_version":"analysis_bundle_v1","payload":${bundle.payload_canonical_json},"payload_canonical_json":${JSON.stringify(bundle.payload_canonical_json)},"payload_sha256":${JSON.stringify(bundle.payload_sha256)},"metadata":${JSON.stringify(metadata)}}`;
}

export type OutcomeOrigin = "SYNTHETIC_DEMO" | "OPERATOR_REPORTED_PHYSICAL";
export type ValidationManifest = {
  schema_version: "validation_report_v1";
  comparison_id: string;
  input_payload_sha256: string;
  evaluation_snapshot_hash: string;
  data_origin: "SYNTHETIC" | "MEASURED_TANK";
  outcome_origin: OutcomeOrigin;
  protocol_id: string;
  purpose: "CONTRACT_REHEARSAL" | "DECLARED_VALIDATION_SPLIT";
  development_trial_ids: string[];
  validation_trial_ids: string[];
};
export type ValidationSummaryRow = {
  source_id: string;
  layout: "baseline" | "intervention";
  released: number;
  planned: number;
  missing_planned: number;
  zone_entries: number;
  captured_before_entry: number;
  no_entry: number;
  unresolved: number;
  entry_rate_bounds: { lower: number; upper: number; denominator: number };
  predicted_entry_fraction: number | null;
  predicted_entry_bounds: { lower: number; upper: number };
};
export type ValidationReceipt = {
  report: ValidationManifest & { id: string; case_id: string; source_evidence_id: string; case_revision: number; created_at: number; verification: "IDENTITY_AND_ACCOUNTING_CHECKED_METHOD_NOT_RERUN" };
  checks: { identity_verified: true; accounting_verified: true; method_rerun: false; physical_validation: false };
  summary: { by_source: ValidationSummaryRow[]; development_count: number; validation_count: number; missing_planned: number; limitations: string[]; next_measurement: { action: string; reason_codes: string[]; source_id?: string } };
  is_current: boolean;
  archive_reason: string | null;
};

export function checkedValidationManifest(value: unknown, scope: ValidationScope): ValidationManifest {
  if (!isRecord(value) || value.schema_version !== "validation_report_v1" || value.comparison_id !== scope.comparisonId
    || !sha256(value.input_payload_sha256) || !sha256(value.evaluation_snapshot_hash)
    || !["SYNTHETIC", "MEASURED_TANK"].includes(String(value.data_origin))
    || !["SYNTHETIC_DEMO", "OPERATOR_REPORTED_PHYSICAL"].includes(String(value.outcome_origin))
    || typeof value.protocol_id !== "string" || !value.protocol_id || value.protocol_id.length > 120
    || !["CONTRACT_REHEARSAL", "DECLARED_VALIDATION_SPLIT"].includes(String(value.purpose))
    || !Array.isArray(value.development_trial_ids) || !Array.isArray(value.validation_trial_ids)
    || ![...value.development_trial_ids, ...value.validation_trial_ids].every(id => typeof id === "string" && id.length > 0 && id.length <= 200)) throw new Error("The validation manifest has an unsupported identity or contract.");
  return value as ValidationManifest;
}

/** Only a server-accepted identity/accounting receipt can populate metric tables. */
export function checkedValidationReceipt(value: unknown, scope: ValidationScope): ValidationReceipt {
  if (!isRecord(value) || !isRecord(value.report) || !isRecord(value.checks) || !isRecord(value.summary)
    || typeof value.report.id !== "string" || value.report.case_id !== scope.caseId || value.report.source_evidence_id !== scope.sourceEvidenceId
    || value.report.verification !== "IDENTITY_AND_ACCOUNTING_CHECKED_METHOD_NOT_RERUN"
    || value.checks.identity_verified !== true || value.checks.accounting_verified !== true || value.checks.method_rerun !== false || value.checks.physical_validation !== false
    || typeof value.is_current !== "boolean" || value.archive_reason !== null && typeof value.archive_reason !== "string") throw new Error("The server did not return a verified identity/accounting receipt for this comparison. No validation metrics were accepted.");
  checkedValidationManifest(value.report, scope);
  const summary = value.summary;
  const count = (n: unknown): n is number => typeof n === "number" && Number.isInteger(n) && n >= 0 && n <= 200;
  const fraction = (n: unknown): n is number => typeof n === "number" && Number.isFinite(n) && n >= 0 && n <= 1;
  if (!Array.isArray(summary.by_source) || summary.by_source.length > 10 || !summary.by_source.every(row => isRecord(row)
    && typeof row.source_id === "string" && ["baseline", "intervention"].includes(String(row.layout))
    && [row.released, row.planned, row.missing_planned, row.zone_entries, row.captured_before_entry, row.no_entry, row.unresolved].every(count)
    && isRecord(row.entry_rate_bounds) && fraction(row.entry_rate_bounds.lower) && fraction(row.entry_rate_bounds.upper)
    && row.entry_rate_bounds.lower <= row.entry_rate_bounds.upper && count(row.entry_rate_bounds.denominator)
    && isRecord(row.predicted_entry_bounds) && fraction(row.predicted_entry_bounds.lower) && fraction(row.predicted_entry_bounds.upper)
    && row.predicted_entry_bounds.lower <= row.predicted_entry_bounds.upper
    && (row.predicted_entry_fraction === null || fraction(row.predicted_entry_fraction)))
    || ![summary.development_count, summary.validation_count, summary.missing_planned].every(count)
    || !Array.isArray(summary.limitations) || !summary.limitations.every(item => typeof item === "string")
    || !isRecord(summary.next_measurement) || typeof summary.next_measurement.action !== "string"
    || !Array.isArray(summary.next_measurement.reason_codes) || !summary.next_measurement.reason_codes.every(item => typeof item === "string")) throw new Error("The accepted validation summary is incomplete. No metric table was displayed.");
  return value as ValidationReceipt;
}

export function validationReceiptIsCurrent(receipt: ValidationReceipt, scope: ValidationScope, comparisonCurrent: boolean): boolean {
  return comparisonCurrent && receipt.is_current && receipt.report.comparison_id === scope.comparisonId && receipt.report.case_id === scope.caseId
    && receipt.report.source_evidence_id === scope.sourceEvidenceId && receipt.report.evaluation_snapshot_hash === scope.evaluationHash;
}

/** A model response stays bound to the explicitly selected validation receipt. */
export function validationAnswerMatches(answer: { validation_report_id?: unknown } | null, selectedId: string): boolean {
  return answer !== null && (answer.validation_report_id || "") === selectedId;
}
