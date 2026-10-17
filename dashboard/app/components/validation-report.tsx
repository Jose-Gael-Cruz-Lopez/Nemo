"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "./icons";
import { analysisDownloadJson, checkedValidationManifest, checkedValidationReceipt, isRecord, MAX_VALIDATION_BYTES, parseValidationInput, validationReceiptIsCurrent, validationScopeKey, verifiedAnalysisExport, type AnalysisExport, type OutcomeOrigin, type ValidationReceipt, type ValidationScope } from "./validation-report-state";
import styles from "./validation-report.module.css";

type Request = <T>(path: string, body?: unknown, options?: { signal?: AbortSignal; independent?: boolean }) => Promise<T>;
type Mutate = <T>(label: string, path: string, body: unknown) => Promise<T>;
type OriginCount = { data_origin: OutcomeOrigin; recorded_count: number };
type HistoryRow = { id: string; comparison_id: string; evaluation_snapshot_hash: string; input_payload_sha256: string; data_origin: string; protocol_id: string; created_at: number; is_current: boolean; verification: string };
type Download = { url: string; filename: string };
type Operation = "export" | "template" | "import" | "history" | "read" | "file";
export type ValidationWorkspaceProps = ValidationScope & {
  request: Request;
  mutate: Mutate;
  current: boolean;
  operatorConnected: boolean;
  onRequireOperator: () => void;
  availableOrigins: OriginCount[];
  onSelected?: (id: string) => void;
  blocked?: boolean;
};
const percent = (n: number) => `${(n * 100).toFixed(1)}%`;
const readable = (text: string) => text.toLowerCase().replaceAll("_", " ");
const originLabel = (origin: OutcomeOrigin) => origin === "SYNTHETIC_DEMO" ? "Synthetic demonstration records" : "Operator-reported physical records";
const message = (error: unknown) => error instanceof Error ? error.message : "The evidence request failed. Review the saved state and retry explicitly.";
const safeFilename = (name: string) => name.replace(/[^A-Za-z0-9_.-]/g, "_").slice(0, 110);

function SavedValidation({ receipt, scope, comparisonCurrent }: { receipt: ValidationReceipt; scope: ValidationScope; comparisonCurrent: boolean }) {
  const report = receipt.report, summary = receipt.summary;
  const current = validationReceiptIsCurrent(receipt, scope, comparisonCurrent);
  return <section className={styles.results} aria-label="Server-accepted validation receipt">
    <div className={styles.badges}><span className="pill">{current ? "Current evidence snapshot" : "Archival evidence snapshot"}</span><span className={`pill ${report.outcome_origin === "SYNTHETIC_DEMO" ? "amber" : "neutral"}`}>{originLabel(report.outcome_origin)}</span></div>
    <h3>Identity and accounting checked · method not rerun</h3>
    <p className={styles.scope}>{report.purpose === "CONTRACT_REHEARSAL" ? "Contract rehearsal: these existing ledger records exercise the report interface. This is not an independent validation experiment." : "Declared development/validation split: the server checked its evidence identity and accounting. Independence and the external analysis method have not been validated."} No physical validation or coral benefit is established.</p>
    {!current && <p className={styles.scope} role="status">This report describes an earlier or archived snapshot. Its metrics remain tied to the evaluation shown below and do not describe the current comparison state.</p>}
    <dl className={styles.identity}><dt>Accepted report</dt><dd><code>{report.id}</code></dd><dt>Comparison / case</dt><dd><code>{report.comparison_id}</code> / <code>{report.case_id}</code></dd><dt>Source evidence</dt><dd><code>{report.source_evidence_id}</code></dd><dt>Evaluation snapshot</dt><dd><code>{report.evaluation_snapshot_hash}</code></dd><dt>Input export SHA-256</dt><dd><code>{report.input_payload_sha256}</code></dd><dt>Protocol / purpose</dt><dd>{report.protocol_id} · {readable(report.purpose)}</dd><dt>Layout input origin</dt><dd>{report.data_origin === "SYNTHETIC" ? "Synthetic layout inputs" : "Measured tank layout inputs"}</dd></dl>
    <p className="settings-note">Declared development partition: <strong>{summary.development_count}</strong> records · declared validation partition: <strong>{summary.validation_count}</strong> records · missing planned slots: <strong>{summary.missing_planned}</strong>.</p>
    <div className="table-scroll"><table className={`metrics-table ${styles.table}`}><caption className="sr-only">Server-computed validation-partition accounting and nominal predicted entry reference by source and layout</caption><thead><tr><th>Source / layout</th><th>Nominal predicted entry · simulation</th><th>Reported entry bounds · planned</th><th>Released / planned</th><th>Missing</th><th>Entered</th><th>Intercepted first</th><th>No entry</th><th>Unresolved</th></tr></thead><tbody>{summary.by_source.map(row => <tr key={`${row.source_id}-${row.layout}`}><th>{row.source_id} · {row.layout}</th><td>{row.predicted_entry_fraction === null ? "Unavailable: unsupported paths" : percent(row.predicted_entry_fraction)}<small className={styles.predictedBounds}>Bounds {percent(row.predicted_entry_bounds.lower)}–{percent(row.predicted_entry_bounds.upper)}</small></td><td>{percent(row.entry_rate_bounds.lower)}–{percent(row.entry_rate_bounds.upper)}</td><td>{row.released}/{row.planned}</td><td>{row.missing_planned}</td><td>{row.zone_entries}</td><td>{row.captured_before_entry}</td><td>{row.no_entry}</td><td>{row.unresolved}</td></tr>)}</tbody></table></div>
    <p className="settings-note">All displayed counts and bounds come from the backend-accepted report. Planned denominators use the frozen quota; development records are excluded from validation-only releases. Missing or unresolved records are not successful prevention. The nominal simulation is separate from reported outcomes and is not a calibrated probability.</p>
    <div><h3>Next measurement to resolve the gap</h3><p>{readable(summary.next_measurement.action)}{summary.next_measurement.source_id ? ` · source ${summary.next_measurement.source_id}` : ""}.</p><ul className="reason-list">{summary.next_measurement.reason_codes.map(reason => <li key={reason}>{readable(reason)}</li>)}</ul></div>
    <details className="details-panel"><summary>Verification scope and limitations</summary><p className="settings-note">{report.verification}. Identity checked: yes. Accounting checked: yes. External method rerun: no. Physical validation: no.</p><ul className="reason-list">{summary.limitations.map((limit, i) => <li key={i}>{limit}</li>)}</ul></details>
  </section>;
}

function ValidationPanel(props: ValidationWorkspaceProps) {
  const { request, mutate, current, operatorConnected, onRequireOperator, availableOrigins, blocked = false } = props;
  const scope: ValidationScope = { comparisonId: props.comparisonId, caseId: props.caseId, sourceEvidenceId: props.sourceEvidenceId, evaluationHash: props.evaluationHash };
  const path = `/prevention/comparisons/${encodeURIComponent(scope.comparisonId)}`;
  const choices = availableOrigins.filter(item => item.recorded_count > 0);
  const [origin, setOrigin] = useState<OutcomeOrigin | "">(() => choices[0]?.data_origin ?? "");
  const [busy, setBusy] = useState<Operation | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [bundle, setBundle] = useState<AnalysisExport | null>(null);
  const [exportDownload, setExportDownload] = useState<Download | null>(null);
  const [templateDownload, setTemplateDownload] = useState<Download | null>(null);
  const [text, setText] = useState("");
  const [draftSource, setDraftSource] = useState("");
  const [history, setHistory] = useState<HistoryRow[] | null>(null);
  const [receipt, setReceipt] = useState<ValidationReceipt | null>(null);
  const pending = useRef<AbortController | null>(null);
  const urls = useRef(new Set<string>());
  const disabled = blocked || busy !== null;
  useEffect(() => () => { pending.current?.abort(); for (const url of urls.current) URL.revokeObjectURL(url); urls.current.clear(); }, []);

  function download(text: string, filename: string, previous: Download | null): Download {
    if (previous) { URL.revokeObjectURL(previous.url); urls.current.delete(previous.url); }
    const url = URL.createObjectURL(new Blob([text], { type: "application/json;charset=utf-8" })); urls.current.add(url);
    return { url, filename };
  }
  async function run(operation: Operation, job: (signal: AbortSignal) => Promise<void>, auth = true) {
    if (pending.current || blocked) return;
    if (auth && !operatorConnected) { onRequireOperator(); return; }
    const controller = new AbortController(); pending.current = controller; setBusy(operation); setError(""); setNotice("");
    try { await job(controller.signal); }
    catch (cause) {
      if (!controller.signal.aborted) { setError(message(cause)); if (isRecord(cause) && cause.status === 401) onRequireOperator(); }
    }
    finally { if (pending.current === controller) { pending.current = null; if (!controller.signal.aborted) setBusy(null); } }
  }
  function exportEvidence() {
    void run("export", async signal => {
      const result = await mutate<unknown>("Preparing frozen evidence export", `${path}/export`, undefined);
      const checked = await verifiedAnalysisExport(result, scope); signal.throwIfAborted();
      setBundle(checked); setExportDownload(download(analysisDownloadJson(checked), safeFilename(`ReefTrace-${scope.comparisonId}-${checked.payload_sha256.slice(0, 12)}.json`), exportDownload));
      setNotice("Export integrity and evidence identity checked. Use Download evidence JSON to save the whitelisted bundle.");
    });
  }
  function template() {
    if (!origin) return;
    void run("template", async signal => {
      const result = await mutate<unknown>("Preparing contract-rehearsal manifest", `${path}/validation-template?origin=${encodeURIComponent(origin)}`, undefined);
      const manifest = checkedValidationManifest(result, scope);
      if (manifest.evaluation_snapshot_hash !== scope.evaluationHash || manifest.purpose !== "CONTRACT_REHEARSAL" || manifest.outcome_origin !== origin) throw new Error("The template targets different evidence. Reload the current comparison.");
      signal.throwIfAborted(); const json = JSON.stringify(manifest, null, 2);
      setText(json); setDraftSource("Server-provided contract-rehearsal manifest; not yet imported");
      setTemplateDownload(download(json, safeFilename(`ReefTrace-rehearsal-${scope.comparisonId}.json`), templateDownload));
      setNotice("Rehearsal manifest loaded into the editor. Existing records were selected; no new measurements or independent holdout were created.");
    });
  }
  function importReport() {
    if (!current) return;
    void run("import", async signal => {
      const input = parseValidationInput(text), manifest = checkedValidationManifest(input, scope);
      if (manifest.evaluation_snapshot_hash !== scope.evaluationHash || bundle && manifest.input_payload_sha256 !== bundle.payload_sha256) throw new Error("The manifest targets a different export or evaluation snapshot. Prepare a current export or matching template first.");
      const result = await mutate<unknown>("Checking validation report identity and accounting", `${path}/validation-reports`, { report: input });
      const accepted = checkedValidationReceipt(result, scope); signal.throwIfAborted(); setReceipt(accepted);
      props.onSelected?.(validationReceiptIsCurrent(accepted, scope, current) ? accepted.report.id : "");
      setNotice("The server accepted the manifest’s identity and accounting. It did not rerun the external method or validate physical outcomes.");
    });
  }
  function loadHistory() {
    void run("history", async signal => {
      const result = await request<unknown>(`${path}/validation-reports`, undefined, { signal });
      if (!Array.isArray(result) || result.length > 200 || !result.every(item => isRecord(item) && typeof item.id === "string" && item.comparison_id === scope.comparisonId && typeof item.protocol_id === "string" && typeof item.evaluation_snapshot_hash === "string" && typeof item.is_current === "boolean")) throw new Error("The saved validation history has an unsupported format.");
      signal.throwIfAborted(); setHistory(result as HistoryRow[]);
    });
  }
  function readReport(id: string) {
    void run("read", async signal => {
      const result = await request<unknown>(`${path}/validation-reports/${encodeURIComponent(id)}`, undefined, { signal });
      const accepted = checkedValidationReceipt(result, scope);
      if (accepted.report.id !== id) throw new Error("The server returned a different validation report.");
      signal.throwIfAborted(); setReceipt(accepted);
      props.onSelected?.(validationReceiptIsCurrent(accepted, scope, current) ? accepted.report.id : "");
    });
  }
  function readFile(file: File | undefined) {
    if (!file) return;
    void run("file", async signal => {
      if (file.size > MAX_VALIDATION_BYTES) throw new Error("Choose a JSON report no larger than 128,000 bytes.");
      const raw = await file.text(); parseValidationInput(raw); signal.throwIfAborted();
      setText(raw); setDraftSource(`Local file: ${file.name.slice(0, 140)} · not yet imported or accepted`);
      setNotice("Local JSON loaded into the editor. No server request or validation has occurred.");
    }, false);
  }

  return <section className="card" aria-label="Evidence export and validation reports"><div className={`card-header ${styles.header}`}><div><h2 className="card-title">Evidence export and validation</h2><p className="card-subtitle">Frozen evidence in · identity-checked accounting out · no external method rerun</p></div><span className="pill">{current ? "Current comparison" : "Archived comparison"}</span></div><div className={`card-body ${styles.stack}`}>
    <p className={styles.scope}>A content hash checks consistency, not an authenticated signature or physical truth. Trial source labels are evaluation ground truth and must stay outside source inference. Importing a report cannot authorize a physical action.</p>
    {!operatorConnected && <div className={styles.actions}><p className="settings-note">Connect operator access to export evidence or read/import validation reports.</p><button className="card-link" disabled={disabled} onClick={onRequireOperator}>Connect operator</button></div>}
    {busy && <p className="settings-note" role="status">{busy === "file" ? "Reading local JSON" : busy === "import" ? "Checking the manifest with the backend" : "Loading frozen evidence"}… No model, camera, pump or messaging action is requested.</p>}
    {error && <p className={styles.error} role="alert">{error} No automatic retry will occur.</p>}
    {notice && <p className={styles.scope} role="status">{notice}</p>}
    <div className={styles.columns}>
      <div className={`${styles.section} ${styles.form}`}><h3>Export the analysis bundle</h3><p className="settings-note">A whitelisted snapshot includes frozen comparison geometry, provenance, source evidence and a separate trial ledger. Private notes, keys, messages and camera frames are excluded.</p><button className="secondary-button" disabled={disabled} onClick={exportEvidence}><Icon name="file" />Prepare evidence download</button>
        {bundle && exportDownload && <><div className={styles.badges}><span className="pill green">SHA-256 integrity checked</span><span className="pill">{current && bundle.metadata.is_current ? "Current when exported" : "Archival export"}</span></div><dl className={styles.identity}><dt>Comparison / case</dt><dd><code>{scope.comparisonId}</code> / <code>{scope.caseId}</code></dd><dt>Evaluation</dt><dd><code>{scope.evaluationHash}</code></dd><dt>Exported at</dt><dd>{bundle.metadata.exported_at_utc}</dd><dt>Payload SHA-256</dt><dd><code>{bundle.payload_sha256}</code></dd></dl><a className="secondary-button" href={exportDownload.url} download={exportDownload.filename}><Icon name="file" />Download evidence JSON</a></>}
      </div>
      <div className={`${styles.section} ${styles.form}`}><h3>Prepare a contract rehearsal</h3><p className="settings-note">This manifest selects existing records of one origin. It tests the interface and accounting; it creates no independent experiment.</p><label>Existing record origin<select value={origin} disabled={disabled || !current || !choices.length} onChange={event => setOrigin(event.target.value as OutcomeOrigin)}><option value="">Select recorded outcomes</option>{choices.map(item => <option value={item.data_origin} key={item.data_origin}>{originLabel(item.data_origin)} · {item.recorded_count} records</option>)}</select></label><button className="secondary-button" disabled={disabled || !current || !origin || !choices.some(item => item.data_origin === origin)} onClick={template}>Load rehearsal manifest</button>{!choices.length && <p className="settings-note">No recorded trials are available for a rehearsal template. Missing trials are not invented.</p>}{templateDownload && <a className="card-link" href={templateDownload.url} download={templateDownload.filename}>Download rehearsal manifest <Icon name="arrow" /></a>}</div>
    </div>
    <div className={styles.form}><h3>Import a validation manifest</h3><p className="settings-note">Use the strict validation_report_v1 manifest. It declares the exported evidence and development/validation trial IDs; uploaded numerical metrics are not accepted. Local JSON is never displayed as a validated result.</p><label>Local JSON file · maximum 128,000 bytes<input type="file" accept=".json,application/json" disabled={disabled || !current} onChange={event => { readFile(event.target.files?.[0]); event.target.value = ""; }} /></label><label>Manifest JSON<textarea rows={7} value={text} disabled={disabled || !current} spellCheck={false} maxLength={MAX_VALIDATION_BYTES} placeholder="Paste a validation_report_v1 manifest or load a labeled rehearsal template." onChange={event => { setText(event.target.value); setDraftSource("Edited local JSON · not yet imported or accepted"); }} /></label>{draftSource && <p className="settings-note">{draftSource}</p>}{!current && <p className={styles.scope}>Archival evidence remains readable and exportable. Import requires a current comparison snapshot.</p>}<button className="primary-button" disabled={disabled || !current || !text.trim()} onClick={importReport}><Icon name="check" />Check and import manifest</button></div>
    <section className={styles.form}><div className={styles.actions}><h3>Saved validation reports</h3><button className="card-link" disabled={disabled} onClick={loadHistory}>Load saved reports <Icon name="arrow" /></button></div>{history && (history.length ? <div className={styles.history}>{history.map(item => <button key={item.id} disabled={disabled} aria-current={receipt?.report.id === item.id ? "true" : undefined} onClick={() => readReport(item.id)}><strong>{item.protocol_id}</strong><small>{item.id} · {current && item.is_current && item.evaluation_snapshot_hash === scope.evaluationHash ? "Current snapshot" : "Archival snapshot"}</small><small>{item.data_origin === "SYNTHETIC" ? "Synthetic layout inputs" : "Measured layout inputs"} · identity/accounting check only</small></button>)}</div> : <p className="settings-note">No saved validation report for this comparison.</p>)}</section>
    {receipt && <SavedValidation receipt={receipt} scope={scope} comparisonCurrent={current} />}
  </div></section>;
}

/** Scope changes unmount pending reads, revoke downloads and clear local/imported state. */
export function ValidationWorkspace(props: ValidationWorkspaceProps) {
  return <ValidationPanel key={validationScopeKey(props)} {...props} />;
}
