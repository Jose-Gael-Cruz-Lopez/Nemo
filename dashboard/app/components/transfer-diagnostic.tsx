"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "./icons";
import styles from "./transfer-diagnostic.module.css";

const MODEL_IDS = ["stationary", "last_drift", "mean_drift", "ridge_ar1", "pooled_residual_ar1"] as const;
type ModelId = typeof MODEL_IDS[number];
const DRIFTER_IDS = ["12730", "12731", "300234063243480", "300234063472530"];
const LABELS: Record<ModelId, string> = { stationary: "Stationary", last_drift: "Last observed drift", mean_drift: "Mean observed drift", ridge_ar1: "Ridge · own earlier positions", pooled_residual_ar1: "Pooled residual AR1 · other drifters" };
type Outcome = { drifter_id: string; model_id: ModelId; horizon_hours: number; status: "SCORED" | "FAILED"; error_m: number | null; reason_codes: string[] };
type Fold = { held_out_drifter_id: string; held_out_canonical_id: string; training_drifter_ids: string[]; training_canonical_ids: string[]; parameters: { held_group_used_to_fit_shared_matrix: false; training_drifters: 3 } };
type Report = {
  schema_version: 1; kind: "LEAVE_ONE_DRIFTER_OUT_DIAGNOSTIC"; status: "COMPLETED" | "INCOMPLETE_OUTCOMES";
  design_status: "POST_HOC_ALREADY_VIEWED_DRIFTERS_NOT_INDEPENDENT_TEST"; data_origin: "REAL_HISTORICAL_NOAA_DRIFTERS_ALREADY_VIEWED";
  protocol_sha256: string; implementation_receipt: { protocol_sha256: string; evaluator_sha256: string; already_viewed_data: true; new_pooled_outcomes_computed: false; frozen_before_first_new_pooled_score_at_utc: string };
  test_data_used: true; model_selection_performed: false; automatic_model_promotion: false; physical_validation: false; calibrated_probability: false; independent_evaluation: false; physical_alias_resolution_verified: false;
  original_study_unchanged: true; identity_scope: string;
  coverage: { folds: 4; models: 5; horizons: 6; attempted_outcomes: 120; scored_outcomes: number; failed_outcomes: number };
  folds: Fold[]; outcomes: Outcome[]; models: { id: ModelId; mean_trajectory_error_m: number | null }[];
  trajectory_summaries: { drifter_id: string; model_id: ModelId; mean_error_m: number | null }[]; limitations: string[];
};
const record = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const count = (v: unknown): v is number => finite(v) && Number.isInteger(v) && v >= 0 && v <= 120;
const text = (v: unknown): v is string => typeof v === "string" && v.length > 0 && v.length <= 4_000;
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.length <= 20 && v.every(text);
const sha = (v: unknown) => typeof v === "string" && /^[a-f0-9]{64}$/.test(v);
const errorValue = (v: unknown): v is number | null => v === null || finite(v) && v >= 0;
const close = (a: number, b: number) => Math.abs(a - b) <= 1e-8 * Math.max(1, Math.abs(b));
function finiteJson(value: unknown, depth = 0, budget = { count: 0 }): boolean {
  if (++budget.count > 8_000 || depth > 20) return false;
  if (Array.isArray(value)) return value.every(item => finiteJson(item, depth + 1, budget));
  if (record(value)) return Object.values(value).every(item => finiteJson(item, depth + 1, budget));
  return value === null || typeof value === "boolean" || typeof value === "string" && value.length <= 4_000 || finite(value);
}
function validate(value: unknown): Report {
  const fail = () => { throw new Error("The transfer diagnostic has an unsupported scope, fold assignment or outcome matrix. No result was accepted."); };
  if (!record(value) || !finiteJson(value) || value.schema_version !== 1 || value.kind !== "LEAVE_ONE_DRIFTER_OUT_DIAGNOSTIC"
    || !["COMPLETED", "INCOMPLETE_OUTCOMES"].includes(String(value.status))
    || value.design_status !== "POST_HOC_ALREADY_VIEWED_DRIFTERS_NOT_INDEPENDENT_TEST" || value.data_origin !== "REAL_HISTORICAL_NOAA_DRIFTERS_ALREADY_VIEWED"
    || value.test_data_used !== true || value.original_study_unchanged !== true || !text(value.identity_scope) || !sha(value.protocol_sha256)
    || [value.model_selection_performed, value.automatic_model_promotion, value.physical_validation, value.calibrated_probability, value.independent_evaluation, value.physical_alias_resolution_verified].some(v => v !== false)
    || !record(value.coverage) || !record(value.implementation_receipt) || !strings(value.limitations) || !value.limitations.length
    || !Array.isArray(value.folds) || value.folds.length !== 4 || !Array.isArray(value.models) || value.models.length !== 5
    || !Array.isArray(value.outcomes) || value.outcomes.length !== 120 || !Array.isArray(value.trajectory_summaries) || value.trajectory_summaries.length !== 20
    || ![...value.folds, ...value.models, ...value.outcomes, ...value.trajectory_summaries].every(record)) return fail();
  const c = value.coverage, receipt = value.implementation_receipt;
  if (c.folds !== 4 || c.models !== 5 || c.horizons !== 6 || c.attempted_outcomes !== 120 || !count(c.scored_outcomes) || !count(c.failed_outcomes)
    || c.scored_outcomes + c.failed_outcomes !== 120 || value.status !== (c.failed_outcomes === 0 ? "COMPLETED" : "INCOMPLETE_OUTCOMES")
    || receipt.protocol_sha256 !== value.protocol_sha256 || !sha(receipt.evaluator_sha256) || receipt.already_viewed_data !== true || receipt.new_pooled_outcomes_computed !== false
    || !text(receipt.frozen_before_first_new_pooled_score_at_utc) || !Number.isFinite(Date.parse(receipt.frozen_before_first_new_pooled_score_at_utc))) return fail();
  const folds = value.folds as Record<string, unknown>[], outcomes = value.outcomes as Record<string, unknown>[], summaries = value.trajectory_summaries as Record<string, unknown>[];
  let scored = 0;
  for (const id of DRIFTER_IDS) {
    const found = folds.filter(f => f.held_out_drifter_id === id); if (found.length !== 1) return fail();
    const fold = found[0];
    if (fold.held_out_canonical_id !== id || !strings(fold.training_drifter_ids) || !strings(fold.training_canonical_ids)
      || fold.training_drifter_ids.length !== 3 || fold.training_canonical_ids.length !== 3
      || !DRIFTER_IDS.filter(other => other !== id).every(other => Array.isArray(fold.training_drifter_ids) && fold.training_drifter_ids.filter(v => v === other).length === 1 && Array.isArray(fold.training_canonical_ids) && fold.training_canonical_ids.filter(v => v === other).length === 1)
      || !record(fold.parameters) || fold.parameters.held_group_used_to_fit_shared_matrix !== false || fold.parameters.training_drifters !== 3) return fail();
    for (const model of MODEL_IDS) {
      const rows = outcomes.filter(o => o.drifter_id === id && o.model_id === model);
      if (rows.length !== 6) return fail();
      for (let horizon = 1; horizon <= 6; horizon++) {
        const matches = rows.filter(o => o.horizon_hours === horizon); if (matches.length !== 1) return fail();
        const row = matches[0]; if (!strings(row.reason_codes)) return fail();
        if (row.status === "SCORED" && finite(row.error_m) && row.error_m >= 0 && row.reason_codes.length === 0) scored++;
        else if (!(row.status === "FAILED" && row.error_m === null && row.reason_codes.length > 0)) return fail();
      }
      const matching = summaries.filter(s => s.drifter_id === id && s.model_id === model);
      if (matching.length !== 1 || !errorValue(matching[0].mean_error_m)) return fail();
      if (c.failed_outcomes > 0 ? matching[0].mean_error_m !== null : !finite(matching[0].mean_error_m) || !close(matching[0].mean_error_m, rows.reduce((sum, row) => sum + (row.error_m as number), 0) / 6)) return fail();
    }
  }
  if (scored !== c.scored_outcomes) return fail();
  for (const id of MODEL_IDS) {
    const found = value.models.filter(model => record(model) && model.id === id);
    if (found.length !== 1 || !record(found[0]) || !errorValue(found[0].mean_trajectory_error_m)) return fail();
    const mean = found[0].mean_trajectory_error_m;
    if (c.failed_outcomes > 0 ? mean !== null : !finite(mean) || !close(mean, summaries.filter(s => s.model_id === id).reduce((sum, s) => sum + (s.mean_error_m as number), 0) / 4)) return fail();
  }
  return value as Report;
}
async function readReport(response: Response): Promise<Report> {
  const max = 200_000;
  if (!response.body || Number(response.headers.get("content-length")) > max) throw new Error("The transfer diagnostic response is empty or exceeds its bounded size.");
  const reader = response.body.getReader(), parts: Uint8Array[] = []; let size = 0;
  try { for (;;) { const part = await reader.read(); if (part.done) break; size += part.value.byteLength; if (size > max) { await reader.cancel(); throw new Error("The transfer diagnostic exceeds its bounded size."); } parts.push(part.value); } } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(size); let offset = 0; for (const part of parts) { bytes.set(part, offset); offset += part.byteLength; }
  let value: unknown; try { value = JSON.parse(new TextDecoder().decode(bytes)); } catch { throw new Error(`Unreadable transfer diagnostic JSON (HTTP ${response.status}).`); }
  if (!response.ok) throw new Error(record(value) && text(value.detail) ? value.detail.slice(0, 500) : `Transfer diagnostic unavailable (HTTP ${response.status}).`);
  return validate(value);
}
const metres = (v: number | null) => v === null ? "Withheld" : `${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} m`;
function Result({ report }: { report: Report }) {
  const pooled = report.models.find(m => m.id === "pooled_residual_ar1")!.mean_trajectory_error_m;
  const ridge = report.models.find(m => m.id === "ridge_ar1")!.mean_trajectory_error_m;
  const last = report.models.find(m => m.id === "last_drift")!.mean_trajectory_error_m;
  return <div className={styles.stack}>
    <div className={styles.coverage}><div><strong>{report.coverage.folds}</strong><span>leave-one-drifter-out folds · already-viewed groups</span></div><div><strong>{report.coverage.scored_outcomes}/{report.coverage.attempted_outcomes}</strong><span>model/horizon outcomes scored · {report.coverage.failed_outcomes} failed</span></div><div><strong>No</strong><span>independent evaluation or automatic promotion</span></div></div>
    <div className={styles.warning}><strong>{report.status === "COMPLETED" ? "Replay complete; this is exploratory evidence." : "Incomplete outcomes; aggregate errors withheld."}</strong><p>All four drifters and their original results had already been inspected. Holding one group out of the pooled matrix fit does not turn this post-hoc design into an unseen or independent test.</p>{pooled !== null && ridge !== null && last !== null && <p>The pooled transfer hypothesis has {metres(pooled)} mean error, {pooled > ridge ? "higher" : "lower"} than own-prefix ridge ({metres(ridge)}) and {pooled > last ? "higher" : "lower"} than last drift ({metres(last)}). {pooled > ridge && pooled > last ? "This candidate does not improve on either comparator in this diagnostic." : "These descriptive results do not establish generalization."} No model is selected or promoted.</p>}</div>
    <div className="table-scroll"><table className="metrics-table"><caption className="sr-only">Exploratory post-hoc mean trajectory errors on four already-viewed drifters; lower error is better within this diagnostic only</caption><thead><tr><th scope="col">Motion model</th><th scope="col">Mean trajectory error</th></tr></thead><tbody>{report.models.map(model => <tr key={model.id}><th scope="row">{LABELS[model.id]}</th><td>{metres(model.mean_trajectory_error_m)}</td></tr>)}</tbody></table></div>
    <p className={styles.scope}>Each fold fits a shared residual transition matrix using only the earlier prefixes of the other three logical drifter IDs. The held group supplies its own earlier motion context; six later positions are then scored. Means weight each drifter equally. {report.identity_scope}. Physical independence, operational accuracy, plastic origin and reef benefit remain unestablished; the original study is unchanged.</p>
    <details className="details-panel"><summary>Fold assignments and drifter-level errors</summary><div className="table-scroll"><table className={`metrics-table ${styles.foldTable}`}><caption className="sr-only">Grouped pooled-matrix fit assignments</caption><thead><tr><th scope="col">Held from pooled fitting</th><th scope="col">Other prefixes used to fit pooled matrix</th><th scope="col">Held group used in matrix fit</th></tr></thead><tbody>{report.folds.map(fold => <tr key={fold.held_out_drifter_id}><th scope="row">{fold.held_out_drifter_id}</th><td>{fold.training_drifter_ids.join(", ")}</td><td>No</td></tr>)}</tbody></table></div><div className="table-scroll"><table className={`metrics-table ${styles.foldTable}`}><caption className="sr-only">Each already-viewed drifter’s six-hour mean error by model</caption><thead><tr><th scope="col">Drifter</th>{MODEL_IDS.map(id => <th scope="col" key={id}>{LABELS[id]}</th>)}</tr></thead><tbody>{DRIFTER_IDS.map(id => <tr key={id}><th scope="row">{id}</th>{MODEL_IDS.map(model => <td key={model}>{metres(report.trajectory_summaries.find(s => s.drifter_id === id && s.model_id === model)!.mean_error_m)}</td>)}</tr>)}</tbody></table></div></details>
    <details className="details-panel"><summary>Protocol, implementation receipt and limits</summary><p className="settings-note">Protocol SHA-256</p><code className="evidence-id">{report.protocol_sha256}</code><p className="settings-note">Evaluator SHA-256</p><code className="evidence-id">{report.implementation_receipt.evaluator_sha256}</code><ul className={styles.limits}>{report.limitations.map(limit => <li key={limit}>{limit}</li>)}</ul></details>
    <details className="details-panel"><summary>Full exploratory diagnostic report</summary><pre className="code-block">{JSON.stringify(report, null, 2)}</pre></details>
  </div>;
}
function Session({ api }: { api: string }) {
  const [report, setReport] = useState<Report | null>(null), [loading, setLoading] = useState(false), [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => { controller.current?.abort(); controller.current = null; }, []);
  async function run() {
    if (controller.current) return;
    const pending = new AbortController(); controller.current = pending; const deadline = window.setTimeout(() => pending.abort(), 30_000);
    setReport(null); setLoading(true); setError("");
    try { const response = await fetch(`${api.replace(/\/$/, "")}/api/v1/research/lopo-diagnostic`, { cache: "no-store", signal: pending.signal }); const result = await readReport(response); if (controller.current === pending && !pending.signal.aborted) setReport(result); }
    catch (cause) { if (controller.current === pending) setError(pending.signal.aborted ? "The transfer diagnostic timed out. No result was accepted." : cause instanceof Error ? cause.message : "The exploratory transfer diagnostic could not be loaded."); }
    finally { window.clearTimeout(deadline); if (controller.current === pending) { controller.current = null; setLoading(false); } }
  }
  return <section className={`card ${styles.card}`} aria-label="Exploratory transfer test"><div className={`card-header ${styles.header}`}><div><h2 className="card-title"><Icon name="wave" />Exploratory transfer test</h2><p className="card-subtitle">Five models · four already-viewed drifters · post-hoc grouped fitting</p></div><button className="secondary-button" disabled={loading} onClick={() => void run()}><Icon name="play" />{loading ? "Running transfer diagnostic…" : "Run transfer diagnostic"}</button></div><div className={`card-body ${styles.stack}`}><p className={styles.scope}>Can patterns learned from other drifters help a new statistical model? Replay this bounded hypothesis on the existing, already-viewed cohort. This is research development, not a new independent benchmark, and it cannot upgrade ReefTrace’s source or prevention claims.</p>{loading && <p className="settings-note" role="status">Running the frozen exploratory design from local NOAA data… No download, provider, camera or message is requested.</p>}{error && <div className="notice error" role="alert"><span>{error} No automatic retry will occur.</span><button className="card-link" onClick={() => void run()}>Retry diagnostic <Icon name="arrow" /></button></div>}{report && <Result report={report} />}</div></section>;
}
export function TransferDiagnostic({ api }: { api: string }) { return <Session key={api} api={api} />; }
