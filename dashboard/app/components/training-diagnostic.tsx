"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "./icons";
import styles from "./training-diagnostic.module.css";

const MODELS = [
  { id: "stationary", label: "Stationary" },
  { id: "last_drift", label: "Last drift" },
  { id: "ridge_ar1", label: "Learned ridge" },
] as const;
type ModelId = typeof MODELS[number]["id"];
type HorizonErrors = {
  horizon_hours: number;
  count: number;
  mean_error_m: number;
  rmse_error_m: number;
  max_error_m: number;
  per_horizon_error_lower_than_stationary_count: number;
};
type Diagnostic = {
  schema_version: number;
  kind: "TRAINING_ONLY_RETROSPECTIVE_DIAGNOSTIC";
  split: {
    training_count: number;
    min_prefix: number;
    horizons: number;
    prefix_counts: number[];
    origin_count: number;
    test_data_used: false;
    model_selection_performed: false;
  };
  aggregates: { id: ModelId; per_horizon: HorizonErrors[] }[];
  origins: unknown[];
  limitations: string[];
  provenance: {
    row_count: number;
    drifter_id: string;
    sha256: string;
    integrity_verified: true;
  };
};

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function nonnegative(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}
function validErrors(value: unknown, index: number): boolean {
  return record(value) && value.horizon_hours === index + 1 && value.count === 5
    && nonnegative(value.mean_error_m) && nonnegative(value.rmse_error_m)
    && nonnegative(value.max_error_m)
    && typeof value.per_horizon_error_lower_than_stationary_count === "number"
    && Number.isInteger(value.per_horizon_error_lower_than_stationary_count)
    && value.per_horizon_error_lower_than_stationary_count >= 0
    && value.per_horizon_error_lower_than_stationary_count <= 5;
}
function diagnosticReport(value: unknown): Diagnostic {
  if (!record(value) || value.schema_version !== 1
    || value.kind !== "TRAINING_ONLY_RETROSPECTIVE_DIAGNOSTIC"
    || !record(value.split) || value.split.training_count !== 18
    || value.split.min_prefix !== 8 || value.split.horizons !== 6 || value.split.origin_count !== 5
    || value.split.test_data_used !== false || value.split.model_selection_performed !== false
    || !Array.isArray(value.split.prefix_counts) || value.split.prefix_counts.length !== 5
    || !value.split.prefix_counts.every((count, index) => count === index + 8)
    || !Array.isArray(value.aggregates) || value.aggregates.length !== MODELS.length
    || !MODELS.every(model => {
      const matches = (value.aggregates as unknown[]).filter(item => record(item) && item.id === model.id);
      return matches.length === 1 && record(matches[0]) && Array.isArray(matches[0].per_horizon)
        && matches[0].per_horizon.length === 6 && matches[0].per_horizon.every(validErrors);
    })
    || !Array.isArray(value.origins) || value.origins.length !== 5
    || !Array.isArray(value.limitations) || !value.limitations.every(limit => typeof limit === "string")
    || !record(value.provenance) || value.provenance.integrity_verified !== true
    || value.provenance.row_count !== 24 || typeof value.provenance.drifter_id !== "string"
    || typeof value.provenance.sha256 !== "string" || !/^[a-f0-9]{64}$/.test(value.provenance.sha256)) {
    throw new Error("The training diagnostic has an unsupported format or does not preserve the fixed training-only split.");
  }
  return value as Diagnostic;
}
async function readReport(response: Response): Promise<Diagnostic> {
  const text = await response.text();
  if (text.length > 150_000) throw new Error("The diagnostic response exceeded its bounded report size.");
  let value: unknown;
  try { value = JSON.parse(text); }
  catch { throw new Error(`The API returned an unreadable response (${response.status}). Check the backend connection.`); }
  if (!response.ok) {
    const detail = record(value) && typeof value.detail === "string" ? value.detail.slice(0, 500) : `Training diagnostic unavailable (${response.status}).`;
    throw new Error(detail);
  }
  return diagnosticReport(value);
}
function metres(value: number): string {
  return Math.round(value).toLocaleString() + " m";
}

function TrainingDiagnosticSession({ api }: { api: string }) {
  const [report, setReport] = useState<Diagnostic | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);

  async function run() {
    if (controller.current) return;
    const pending = new AbortController();
    controller.current = pending;
    setLoading(true); setError("");
    try {
      const response = await fetch(`${api.replace(/\/$/, "")}/api/v1/research/training-diagnostic`, {
        cache: "no-store", signal: pending.signal,
      });
      const result = await readReport(response);
      if (controller.current === pending && !pending.signal.aborted) setReport(result);
    } catch (cause) {
      if (controller.current === pending && !pending.signal.aborted) {
        setError(cause instanceof Error ? cause.message : "The diagnostic could not be loaded.");
      }
    } finally {
      if (controller.current === pending && !pending.signal.aborted) {
        controller.current = null; setLoading(false);
      }
    }
  }

  return <section className={`card ${styles.card}`} aria-label="Training-only motion diagnostic">
    <div className={`card-header ${styles.header}`}><div><h2 className="card-title"><Icon name="wave" />Training-only motion diagnostic</h2><p className="card-subtitle">An expanding-origin check within the existing training window.</p></div><button className="secondary-button" disabled={loading} onClick={() => void run()}><Icon name="play" />{loading ? "Running diagnostic…" : "Run training diagnostic"}</button></div>
    <div className="card-body">
      <p className={styles.scope}><strong>Five overlapping forecast origins, one NOAA buoy-day.</strong> Fit prefixes of eight through twelve positions, then forecast six later hours still inside the first eighteen training positions. The final six held-out hours stay outside this diagnostic.</p>
      <p className="settings-note">These windows share observations and are statistically dependent. This is a retrospective training check, not model selection, an independent test, or a source-tracing result. Lower error is better for a given horizon; no model is promoted here.</p>
      {loading && <p className="settings-note" role="status">Fitting the fixed motion baselines on training prefixes only…</p>}
      {error && <div className="notice error" role="alert">{error}<button className={`card-link ${styles.retry}`} disabled={loading} onClick={() => void run()}>Retry diagnostic <Icon name="arrow" /></button></div>}
      {report ? <>
        <div className={styles.badges}><span className="pill">{report.split.origin_count} dependent origins</span><span className="pill">{report.split.training_count} training positions</span><span className="pill">Test data not used</span><span className="pill">No model selection</span></div>
        <p className="settings-note" role="status">Training diagnostic ready. Each table entry summarizes the same five forecast origins.</p>
        <div className="table-scroll"><table className={`metrics-table ${styles.table}`}><caption className="sr-only">Training-only mean and root mean square position errors in metres for each model and forecast horizon, averaged across five dependent origins</caption><thead><tr><th rowSpan={2} scope="col">Hours ahead</th>{MODELS.map(model => <th key={model.id} colSpan={2} scope="colgroup">{model.label}</th>)}</tr><tr>{MODELS.map(model => <ModelHeaders key={model.id} />)}</tr></thead><tbody>{Array.from({ length: report.split.horizons }, (_, index) => <tr key={index + 1}><th scope="row">{index + 1}</th>{MODELS.map(model => {
          const errors = report.aggregates.find(item => item.id === model.id)!.per_horizon[index];
          return <ModelErrors key={model.id} errors={errors} />;
        })}</tr>)}</tbody></table></div>
        <p className="settings-note">Mean error is the average position miss at that horizon. RMSE gives large misses more weight. The values shown are rounded to metres; exact values, maximum errors and every forecast are in the report below.</p>
        <details className="details-panel"><summary>Diagnostic limitations and source integrity</summary><ul className="reason-list">{report.limitations.map(limit => <li key={limit}>{limit}</li>)}</ul><p className="settings-note">NOAA buoy {report.provenance.drifter_id}; {report.provenance.row_count} source rows, of which the first {report.split.training_count} enter this diagnostic. The shared CSV is integrity verified.</p><code className="evidence-id">{report.provenance.sha256}</code></details>
        <details className="details-panel"><summary>Full training diagnostic JSON</summary><pre className="code-block">{JSON.stringify(report, null, 2)}</pre></details>
      </> : !loading && !error ? <p className="settings-note">Runs locally from the collected NOAA sample when requested. No camera, model-provider account or messaging is involved.</p> : null}
    </div>
  </section>;
}

function ModelHeaders() {
  return <><th scope="col">Mean</th><th scope="col">RMSE</th></>;
}
function ModelErrors({ errors }: { errors: HorizonErrors }) {
  return <><td>{metres(errors.mean_error_m)}</td><td>{metres(errors.rmse_error_m)}</td></>;
}

export function TrainingDiagnostic({ api }: { api: string }) {
  return <TrainingDiagnosticSession key={api} api={api} />;
}
