"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "./icons";
import styles from "./dataset-readiness.module.css";

const MAX_BYTES = 64_000;
const DATASET_HOSTS: Record<string, string> = {
  "noaa-gdp-gts": "www.aoml.noaa.gov",
  "noaa-mdmap": "marinedebris.noaa.gov",
  "copernicus-glorys12": "data.marine.copernicus.eu",
};
type Dataset = {
  id: string; name: string; primary_source_url: string; role: string;
  why_better_for_this_question: string; acquired: false; training_ready: false;
  required_before_use: string[]; cannot_prove: string;
};
type ReadinessReport = {
  schema_version: 1; kind: "DATASET_READINESS_REPORT"; status: "ACQUISITION_BLOCKED";
  study_id: string; integrity_verified: true; test_data_used: false;
  new_evaluation_outcomes_computed: false; model_selection_performed: false;
  automatic_model_promotion: false; physical_validation: false; calibrated_probability: false;
  protocol_sha256: string; selection_sha256: string; manifest_sha256: string;
  excluded_previously_viewed_ids: string[];
  coverage: { target_new_drifters: 2; selected_new_drifters: 0; downloaded_trajectories: 0; new_position_rows: 0; planned_model_horizon_outcomes: 48; scored_outcomes: 0 };
  acquisition: { status: "FETCH_FAILED"; reason: "ConnectTimeout"; source_url: string; retrieved_at_utc: string; http_status: null };
  metadata_snapshot: { freshly_downloaded: false; retrieved_at_utc: string; sha256: string };
  previous_study: { unchanged: true; declared_groups: 4; target_groups: 6; scored_outcomes: 96; target_outcomes: 144; status: "PARTIAL_COVERAGE"; pooling_performed: false };
  next_datasets: Dataset[]; limitations: string[];
};
const object = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const text = (v: unknown): v is string => typeof v === "string" && v.length > 0 && v.length <= 4_000;
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.length > 0 && v.length <= 20 && v.every(text);
const sha = (v: unknown) => typeof v === "string" && /^[a-f0-9]{64}$/.test(v);
const utc = (v: unknown) => text(v) && /(?:Z|\+00:00)$/.test(v) && Number.isFinite(Date.parse(v));
function officialUrl(v: unknown, host: string): v is string {
  if (!text(v)) return false;
  try { const u = new URL(v); return u.protocol === "https:" && u.hostname === host && !u.username && !u.password && !u.port; } catch { return false; }
}
function validate(value: unknown): ReadinessReport {
  const fail = () => { throw new Error("The dataset-readiness report has an unsupported scope, integrity state or acquisition count. No new data or result was accepted."); };
  if (!object(value) || value.schema_version !== 1 || value.kind !== "DATASET_READINESS_REPORT" || value.status !== "ACQUISITION_BLOCKED"
    || value.study_id !== "noaa-indian-extension-retrospective-v1" || value.integrity_verified !== true
    || [value.test_data_used, value.new_evaluation_outcomes_computed, value.model_selection_performed, value.automatic_model_promotion, value.physical_validation, value.calibrated_probability].some(v => v !== false)
    || ![value.protocol_sha256, value.selection_sha256, value.manifest_sha256].every(sha)
    || !strings(value.excluded_previously_viewed_ids) || new Set(value.excluded_previously_viewed_ids).size !== value.excluded_previously_viewed_ids.length
    || !strings(value.limitations) || !object(value.coverage) || !object(value.acquisition) || !object(value.metadata_snapshot) || !object(value.previous_study)
    || !Array.isArray(value.next_datasets) || value.next_datasets.length !== 3) return fail();
  const c = value.coverage, a = value.acquisition, m = value.metadata_snapshot, p = value.previous_study;
  if (c.target_new_drifters !== 2 || [c.selected_new_drifters, c.downloaded_trajectories, c.new_position_rows, c.scored_outcomes].some(v => v !== 0)
    || c.planned_model_horizon_outcomes !== 48 || a.status !== "FETCH_FAILED" || a.reason !== "ConnectTimeout" || a.http_status !== null
    || !utc(a.retrieved_at_utc) || !officialUrl(a.source_url, "erddap.aoml.noaa.gov")
    || m.freshly_downloaded !== false || !utc(m.retrieved_at_utc) || !sha(m.sha256)
    || p.unchanged !== true || p.declared_groups !== 4 || p.target_groups !== 6 || p.scored_outcomes !== 96 || p.target_outcomes !== 144
    || p.status !== "PARTIAL_COVERAGE" || p.pooling_performed !== false) return fail();
  const seen = new Set<string>();
  for (const row of value.next_datasets) {
    if (!object(row) || !text(row.id) || !Object.hasOwn(DATASET_HOSTS, row.id) || seen.has(row.id)
      || !officialUrl(row.primary_source_url, DATASET_HOSTS[row.id]) || ![row.name, row.role, row.why_better_for_this_question, row.cannot_prove].every(text)
      || !strings(row.required_before_use) || row.acquired !== false || row.training_ready !== false) return fail();
    seen.add(row.id);
  }
  return value as ReadinessReport;
}
async function readReport(response: Response): Promise<ReadinessReport> {
  if (!response.body || Number(response.headers.get("content-length")) > MAX_BYTES) throw new Error("The dataset-readiness response is empty or exceeds its bounded size.");
  const reader = response.body.getReader(), parts: Uint8Array[] = []; let size = 0;
  try {
    for (;;) { const part = await reader.read(); if (part.done) break; size += part.value.byteLength; if (size > MAX_BYTES) { await reader.cancel(); throw new Error("The dataset-readiness response exceeds its bounded size."); } parts.push(part.value); }
  } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const part of parts) { bytes.set(part, offset); offset += part.byteLength; }
  let value: unknown;
  try { value = JSON.parse(new TextDecoder().decode(bytes)); } catch { throw new Error(`Unreadable dataset-readiness JSON (HTTP ${response.status}).`); }
  if (!response.ok) throw new Error(object(value) && text(value.detail) ? value.detail.slice(0, 500) : `Dataset readiness unavailable (HTTP ${response.status}).`);
  return validate(value);
}

function Result({ report }: { report: ReadinessReport }) {
  return <div className={styles.stack}>
    <div className={styles.metrics}>
      <div><strong>{report.coverage.downloaded_trajectories}</strong><span>new drifters downloaded · target {report.coverage.target_new_drifters}</span></div>
      <div><strong>{report.coverage.scored_outcomes}/{report.coverage.planned_model_horizon_outcomes}</strong><span>new model/horizon outcomes scored</span></div>
      <div><strong>{report.previous_study.declared_groups}/{report.previous_study.target_groups}</strong><span>original drifter coverage · unchanged</span></div>
    </div>
    <div className={styles.blocked} role="status"><strong>Acquisition blocked · no new model improvement established.</strong><p>The bounded request timed out before any new drifter was selected. Zero new position rows were collected, and none of the 48 planned outcomes were scored. The existing four-drifter study still has 96 scored outcomes against its 144-outcome target; these reports were not pooled.</p></div>
    <div className={styles.receipt}>
      <span className="pill purple">Local receipt integrity verified</span><span className="pill amber">Download attempt failed</span>
      <p>Recorded {report.acquisition.retrieved_at_utc} · {report.acquisition.reason}. Checking this receipt does not retry the download.</p>
      <a className="card-link" href={report.acquisition.source_url} target="_blank" rel="noreferrer">Inspect the attempted NOAA source <Icon name="arrow" /></a>
    </div>
    <h3>Three datasets that answer different questions</h3>
    <div className={styles.datasets}>{report.next_datasets.map(dataset => <article key={dataset.id} className={styles.dataset}>
      <div className={styles.datasetHead}><span className={styles.datasetType}>{dataset.id === "noaa-gdp-gts" ? "Motion" : dataset.id === "noaa-mdmap" ? "Debris outcomes" : "Ocean forcing"}</span><span className="pill neutral">Not acquired</span></div>
      <h4>{dataset.name}</h4><p className={styles.role}>{dataset.role}</p><p>{dataset.why_better_for_this_question}</p>
      <a className="card-link" href={dataset.primary_source_url} target="_blank" rel="noreferrer">Primary source <Icon name="arrow" /></a>
      <details className={styles.requirements}><summary>Required before training or scoring</summary><ul>{dataset.required_before_use.map(requirement => <li key={requirement}>{requirement}</li>)}</ul></details>
      <p className={styles.limit}><strong>What it cannot establish:</strong> {dataset.cannot_prove}</p>
    </article>)}</div>
    <details className="details-panel"><summary>Frozen acquisition receipts and limitations</summary><dl className={styles.identity}><dt>Study</dt><dd>{report.study_id}</dd><dt>Protocol SHA-256</dt><dd><code>{report.protocol_sha256}</code></dd><dt>Selection SHA-256</dt><dd><code>{report.selection_sha256}</code></dd><dt>Manifest SHA-256</dt><dd><code>{report.manifest_sha256}</code></dd><dt>Metadata snapshot</dt><dd>Reused from {report.metadata_snapshot.retrieved_at_utc}; not freshly downloaded</dd><dt>Excluded viewed drifters</dt><dd>{report.excluded_previously_viewed_ids.join(", ")}</dd></dl><ul className={styles.limitations}>{report.limitations.map(limit => <li key={limit}>{limit}</li>)}</ul></details>
    <details className="details-panel"><summary>Full dataset-readiness report</summary><pre className="code-block">{JSON.stringify(report, null, 2)}</pre></details>
  </div>;
}

function ReadinessSession({ api }: { api: string }) {
  const [report, setReport] = useState<ReadinessReport | null>(null), [loading, setLoading] = useState(false), [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => { controller.current?.abort(); controller.current = null; }, []);
  async function run() {
    if (controller.current) return;
    const pending = new AbortController(); controller.current = pending;
    const deadline = window.setTimeout(() => pending.abort(), 20_000);
    setReport(null); setError(""); setLoading(true);
    try {
      const response = await fetch(`${api.replace(/\/$/, "")}/api/v1/research/dataset-readiness`, { cache: "no-store", signal: pending.signal });
      const value = await readReport(response);
      if (controller.current === pending && !pending.signal.aborted) setReport(value);
    } catch (cause) {
      if (controller.current === pending) setError(pending.signal.aborted ? "The local readiness check timed out. No report was accepted." : cause instanceof Error ? cause.message : "The dataset-readiness report could not be loaded.");
    } finally {
      window.clearTimeout(deadline);
      if (controller.current === pending) { controller.current = null; setLoading(false); }
    }
  }
  return <section className={`card ${styles.card}`} aria-label="Dataset acquisition readiness">
    <div className={`card-header ${styles.header}`}><div><h2 className="card-title"><Icon name="wave" />What data can move this forward?</h2><p className="card-subtitle">Verified acquisition state · motion, debris outcomes and ocean forcing</p></div><button className="secondary-button" disabled={loading} onClick={() => void run()}><Icon name="play" />{loading ? "Checking dataset receipts…" : "Check dataset readiness"}</button></div>
    <div className={`card-body ${styles.stack}`}><p className={styles.intro}>More data helps only when it answers the right question. Inspect the frozen extension attempt and the primary sources proposed for future motion forecasting and prevention evaluation. This check does not download data, retrain models or change existing scores.</p>
      {loading && <p className="settings-note" role="status">Verifying the saved acquisition receipts… No provider, camera or message is requested.</p>}
      {error && <div className="notice error" role="alert"><span>{error} No automatic retry will occur.</span><button className="card-link" disabled={loading} onClick={() => void run()}>Retry readiness check <Icon name="arrow" /></button></div>}
      {report && <Result report={report} />}
    </div>
  </section>;
}
export function DatasetReadiness({ api }: { api: string }) { return <ReadinessSession key={api} api={api} />; }
