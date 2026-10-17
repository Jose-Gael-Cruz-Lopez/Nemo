export type WaterBounds = { x_min_cm: number; x_max_cm: number; y_min_cm: number; y_max_cm: number };
export type TrialSubmission = {
  trial_key: string;
  layout: "baseline" | "intervention";
  source_id: string;
  data_origin: "SYNTHETIC_DEMO" | "OPERATOR_REPORTED_PHYSICAL";
  outcome: "zone_entry" | "intercepted_before_entry" | "no_entry" | "unresolved";
  entry_time_s?: number;
  interception_time_s?: number;
  token_accounted: boolean;
  horizon_completed: boolean;
  physical_confirmed: boolean;
  note: string;
  recording_id?: string;
};
export type PendingTrial = { version: 1; comparison_id: string; payload: TrialSubmission; rejected_status?: number };

/** Only completed local HTTP rejections can unlock a draft after ledger reconciliation. */
export function definitiveTrialStatus(cause: unknown): number | null {
  if (typeof cause !== "object" || cause === null || !("status" in cause)) return null;
  const status = cause.status;
  return typeof status === "number" && Number.isInteger(status) && status >= 400 && status < 500 && status !== 408 && status !== 499 ? status : null;
}

export function canCorrectRejectedTrial(pending: PendingTrial | null, savedTrialKeys: string[]): boolean {
  return Boolean(pending && definitiveTrialStatus({ status: pending.rejected_status }) !== null && !savedTrialKeys.includes(pending.payload.trial_key));
}

/** Render only adapter-owned failure identifiers, never upstream text or URLs. */
export function safeInvestigationFailure(value: { live_model_response?: boolean; failure_code?: unknown; provider_status_code?: unknown; timeout_stage?: unknown }) {
  if (value.live_model_response === true) return null;
  const allowedCodes = ["NOT_CONFIGURED", "PROVIDER_HTTP_ERROR", "TIMEOUT", "PROVIDER_CONNECTION_ERROR", "MODEL_OR_TOOL_CONTRACT_ERROR"];
  const code = typeof value.failure_code === "string" && allowedCodes.includes(value.failure_code) ? value.failure_code : null;
  const httpStatus = typeof value.provider_status_code === "number" && Number.isInteger(value.provider_status_code) && value.provider_status_code >= 400 && value.provider_status_code <= 599 ? value.provider_status_code : null;
  const stages = ["get_case", "get_source_evidence", "get_prevention_evidence", "run_predeclared_sensitivity", "observe_again", "propose_collection"].map(tool => `tool:${tool}`);
  const stage = typeof value.timeout_stage === "string" && (/^model_call_[1-9]$/.test(value.timeout_stage) || stages.includes(value.timeout_stage)) ? value.timeout_stage : null;
  if (!code && httpStatus === null && !stage) return null;
  const message = httpStatus === 429
    ? "Chalk’s model provider returned HTTP 429: a rate or quota limit. The investigation did not finish. Saved simulation and trial evidence remain available. No automatic retry will occur."
    : code === "TIMEOUT"
      ? "The investigation exceeded its time budget. Saved evidence remains available. No automatic retry will occur."
      : "The investigation did not finish. Saved evidence remains available. No automatic retry will occur.";
  return { code, httpStatus, stage, message };
}

export function validTrialObservation(p: Pick<TrialSubmission, "outcome" | "data_origin" | "entry_time_s" | "interception_time_s" | "token_accounted" | "horizon_completed" | "physical_confirmed" | "note">, horizon: number): boolean {
  const validTime = (value: number | undefined) => typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= horizon;
  if (!p.note.trim() || p.note.length > 1000 || !Number.isFinite(horizon) || horizon <= 0
    || p.data_origin === "OPERATOR_REPORTED_PHYSICAL" && !p.physical_confirmed
    || p.data_origin === "SYNTHETIC_DEMO" && p.physical_confirmed) return false;
  if (p.outcome === "zone_entry") return p.token_accounted && validTime(p.entry_time_s) && (p.interception_time_s === undefined || validTime(p.interception_time_s) && p.interception_time_s >= p.entry_time_s!);
  if (p.outcome === "intercepted_before_entry") return p.token_accounted && p.horizon_completed && validTime(p.interception_time_s) && p.entry_time_s === undefined;
  if (p.outcome === "no_entry") return p.token_accounted && p.horizon_completed && p.entry_time_s === undefined && p.interception_time_s === undefined;
  return p.outcome === "unresolved" && p.entry_time_s === undefined && p.interception_time_s === undefined;
}

/** A small, simple polygon in tank centimetres; the server remains authoritative. */
export function parseProtectedZone(text: string, bounds: WaterBounds): number[][] {
  let value: unknown;
  try { value = JSON.parse(text); } catch { throw new Error("Use a JSON array of [x, y] points, in centimetres."); }
  if (!Array.isArray(value) || value.length < 3 || value.length > 16 || !value.every(point => Array.isArray(point) && point.length === 2 && point.every(n => typeof n === "number" && Number.isFinite(n)))) {
    throw new Error("Use 3–16 finite [x, y] points for the protected zone.");
  }
  const points = value as number[][];
  if (points.some(([x, y]) => x < bounds.x_min_cm || x > bounds.x_max_cm || y < bounds.y_min_cm || y > bounds.y_max_cm)) throw new Error("Every protected-zone point must be inside the tank bounds.");
  if (new Set(points.map(point => point.join(","))).size !== points.length) throw new Error("Use distinct polygon vertices; do not repeat the first point at the end.");
  const cross = (a: number[], b: number[], c: number[]) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  const onSegment = (a: number[], b: number[], p: number[]) => Math.abs(cross(a, b, p)) < 1e-9 && p[0] >= Math.min(a[0], b[0]) && p[0] <= Math.max(a[0], b[0]) && p[1] >= Math.min(a[1], b[1]) && p[1] <= Math.max(a[1], b[1]);
  const intersects = (a: number[], b: number[], c: number[], d: number[]) => cross(a, b, c) * cross(a, b, d) < 0 && cross(c, d, a) * cross(c, d, b) < 0 || onSegment(a, b, c) || onSegment(a, b, d) || onSegment(c, d, a) || onSegment(c, d, b);
  for (let i = 0; i < points.length; i++) for (let j = i + 1; j < points.length; j++) {
    if (j === i + 1 || i === 0 && j === points.length - 1) continue;
    if (intersects(points[i], points[(i + 1) % points.length], points[j], points[(j + 1) % points.length])) throw new Error("Protected-zone edges cannot cross or touch one another.");
  }
  const area = points.reduce((sum, point, i) => sum + point[0] * points[(i + 1) % points.length][1] - points[(i + 1) % points.length][0] * point[1], 0);
  if (Math.abs(area) < 1e-6) throw new Error("The protected zone must enclose an area.");
  return points;
}

export function currentPreventionAnswer<T extends { comparison_id?: string; evaluation_digest?: string }>(answer: T | null, comparisonId: string, snapshotHash: string): T | null {
  return answer && answer.comparison_id === comparisonId && answer.evaluation_digest === snapshotHash ? answer : null;
}

/** Tab-local retry data has a version and scope, never a credential. */
export function decodePendingTrial(raw: string | null, comparisonId: string): PendingTrial | null {
  if (!raw || raw.length > 8000) return null;
  try {
    const item = JSON.parse(raw) as PendingTrial;
    const p = item?.payload;
    if (item.version !== 1 || item.comparison_id !== comparisonId || !p || typeof p.trial_key !== "string" || p.trial_key.length < 8 || p.trial_key.length > 120
      || !["baseline", "intervention"].includes(p.layout) || typeof p.source_id !== "string" || !p.source_id || p.source_id.length > 200
      || !["SYNTHETIC_DEMO", "OPERATOR_REPORTED_PHYSICAL"].includes(p.data_origin)
      || !["zone_entry", "intercepted_before_entry", "no_entry", "unresolved"].includes(p.outcome)
      || typeof p.token_accounted !== "boolean" || typeof p.physical_confirmed !== "boolean" || typeof p.horizon_completed !== "boolean"
      || typeof p.note !== "string" || p.note.length > 1000 || (p.recording_id !== undefined && (typeof p.recording_id !== "string" || p.recording_id.length > 200))
      || [p.entry_time_s, p.interception_time_s].some(time => time !== undefined && (typeof time !== "number" || !Number.isFinite(time) || time < 0))
      || item.rejected_status !== undefined && definitiveTrialStatus({ status: item.rejected_status }) === null) return null;
    return item;
  } catch { return null; }
}

export function pendingTrialKey(comparisonId: string) { return `reeftrace.prevention.pending.v1.${comparisonId}`; }

export function sourceCaseChanged(comparison: { case_id: string; source_evidence_id: string }, cases: { id: string; state: string; evidence_id: string | null }[]): boolean {
  const item = cases.find(value => value.id === comparison.case_id);
  return Boolean(item && (["STOPPED", "RECOVERING"].includes(item.state) || item.evidence_id !== comparison.source_evidence_id));
}
