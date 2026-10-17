"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "./icons";
import { TrainingDiagnostic } from "./training-diagnostic";
import { MotionAblation } from "./motion-ablation";
import { MultiDrifterStudy } from "./multi-drifter-study";
import { DatasetReadiness } from "./dataset-readiness";
import { TransferDiagnostic } from "./transfer-diagnostic";
import { VectorDiagnostic } from "./vector-diagnostic";
import { CohortVectors } from "./cohort-vectors";
import { KalmanDiagnostic } from "./kalman-diagnostic";
import { FreshDrifterStudy } from "./fresh-drifter-study";
import { CurrentForecastPreview } from "./current-forecast";

type Position = { time_utc: string; latitude_deg: number; longitude_deg: number };
type Prediction = Position & { horizon_hours: number; error_m: number };
type Forecast = {
  id: string; label: string; kind: string; predictions: Prediction[];
  metrics: { mean_error_m: number; endpoint_error_m: number; rmse_error_m: number; mae_skill_vs_stationary: number };
};
type RealData = {
  schema_version: number; title: string; data_origin: string;
  training_track: Position[]; heldout_track: Position[]; models: Forecast[];
  split: { training_count: number; heldout_count: number; training_end_utc: string; step_seconds: number };
  source_attribution: { status: string; reason: string };
  uncertainty_method: { note: string };
  provenance: { source_url: string; metadata_url: string; product_doi: string; license: string; license_url: string; attribution: string; sha256: string; integrity_verified: boolean; row_count: number; drifter_id: string };
  limitations: string[];
};
const COLORS = ["#a78344", "#4f88ac", "#087fac"];
const metres = (value: number) => `${Math.round(value).toLocaleString()} m`;
function utc(value: string) { return `${value.slice(11, 16)} UTC`; }
function https(value: string) { return value.startsWith("https://") ? value : "#"; }

function ForecastMap({ data }: { data: RealData }) {
  const all = [...data.training_track, ...data.heldout_track, ...data.models.flatMap(model => model.predictions)];
  const lat = data.training_track[0].latitude_deg;
  const lon = data.training_track[0].longitude_deg;
  const project = (p: Position) => [(p.longitude_deg - lon) * Math.cos(lat * Math.PI / 180) * 111195, (p.latitude_deg - lat) * 111195];
  const xy = all.map(project);
  const xs = xy.map(p => p[0]), ys = xy.map(p => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const span = Math.max(x1 - x0, y1 - y0, 1);
  const point = (p: Position) => { const q = project(p); return [45 + (q[0] - (x0 + x1) / 2 + span / 2) / span * 430, 460 - (q[1] - (y0 + y1) / 2 + span / 2) / span * 430]; };
  const polyline = (positions: Position[]) => positions.map(p => point(p).join(",")).join(" ");
  const lastTraining = data.training_track[data.training_track.length - 1];
  return <div className="geographic-map">
    <svg viewBox="0 0 520 500" role="img" aria-label="Real NOAA buoy training positions, held-out positions, and three motion forecast paths">
      <rect x="25" y="15" width="470" height="470" rx="0" fill="#f5f8fa" stroke="#e3e9ed" />
      {[1, 2, 3, 4].map(i => <g key={i} stroke="#e4e9ed" strokeWidth="1"><path d={`M${25 + i * 94} 15v470`} /><path d={`M25 ${15 + i * 94}h470`} /></g>)}
      {data.models.map((model, i) => <polyline key={model.id} points={polyline([lastTraining, ...model.predictions])} fill="none" stroke={COLORS[i % COLORS.length]} strokeWidth="2.5" strokeDasharray="6 5"><title>{model.label}</title></polyline>)}
      <polyline points={polyline(data.training_track)} fill="none" stroke="#a4b1ba" strokeWidth="3" />
      <polyline points={polyline([lastTraining, ...data.heldout_track])} fill="none" stroke="#287b62" strokeWidth="3" />
      {data.training_track.map(p => { const q = point(p); return <circle key={p.time_utc} cx={q[0]} cy={q[1]} r="3" fill="#8e9da8"><title>Training observation {utc(p.time_utc)}</title></circle>; })}
      {data.heldout_track.map(p => { const q = point(p); return <circle key={p.time_utc} cx={q[0]} cy={q[1]} r="4.5" fill="#287b62" stroke="white" strokeWidth="1"><title>Held-out observation {utc(p.time_utc)}</title></circle>; })}
      <text x="38" y="39" fontSize="11" fill="#71828b">N ↑ · Pacific Ocean · {data.training_track[0].time_utc.slice(0, 10)}</text>
      <text x="38" y="469" fontSize="10" fill="#71828b">Position plot · approximate local projection · no map tiles</text>
    </svg>
    <div className="forecast-legend"><span><i style={{ background: "#8e9da8" }} />Training observations</span><span><i style={{ background: "#287b62" }} />Held-out observations</span>{data.models.map((model, i) => <span key={model.id}><i style={{ background: COLORS[i % COLORS.length] }} />{model.label}</span>)}</div>
  </div>;
}

export function RealDataLab({ api }: { api: string }) {
  const [data, setData] = useState<RealData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function run() {
    if (controller.current) return;
    const pending = new AbortController(); controller.current = pending;
    setLoading(true); setError("");
    try {
      const response = await fetch(`${api}/api/v1/research/real-data`, { cache: "no-store", signal: pending.signal });
      const report = await response.json();
      if (!response.ok) throw new Error(typeof report.detail === "string" ? report.detail : `Real-data replay failed (${response.status}).`);
      if (report.schema_version !== 1 || !report.training_track?.length || !report.heldout_track?.length || !report.models?.length) throw new Error("The dataset report has an unsupported or incomplete format.");
      if (!pending.signal.aborted) setData(report as RealData);
    } catch (cause) { if (!pending.signal.aborted) setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { if (!pending.signal.aborted) { controller.current = null; setLoading(false); } }
  }
  return <>
    <div className="page-heading"><div><p className="kicker">Data Lab</p><h1>How well does it predict?</h1><p className="page-description">Test buoy-motion models or follow a changing ocean-current forecast.</p></div></div>
    <p className="settings-note">Historical buoy motion tests the forecasting software. It does not identify a plastic source or validate the tank.</p>
    <FreshDrifterStudy api={api} />
    <CurrentForecastPreview api={api} />
    <details className="card"><summary>Research details and earlier studies</summary><div className="card-body data-lab-results">
    <button className="secondary-button" disabled={loading} onClick={() => void run()}><Icon name="play" />{loading ? "Running reference replay…" : "Run reference buoy replay"}</button>
    <CohortVectors api={api} />
    <KalmanDiagnostic api={api} />
    {loading && <div className="busy-notice" role="status">Loading the verified dataset and fitting the predeclared motion models…</div>}
    {error && <div className="notice error" role="alert">{error}<button className="card-link" onClick={() => void run()}>Retry replay <Icon name="arrow" /></button></div>}
    {!data && !loading && !error && <section className="card dataset-intro"><span className="observation-icon"><Icon name="wave" /></span><h2>A small real-data test you can inspect.</h2><p>Train on the first eighteen hourly positions. Forecast the next six hours without reading those held-out positions.</p><div className="dataset-methods"><span>Stationary baseline</span><span>Last observed drift</span><span>Regularized velocity model</span></div><p className="settings-note">The replay runs locally from the collected NOAA CSV. No account, camera, or sponsor credentials are required.</p></section>}
    {data && <div className="data-lab-results" aria-live="polite">
      <div className="summary-strip"><div className="summary-item"><span className="summary-value">{data.split.training_count}</span>training positions</div><div className="summary-item"><span className="summary-value">{data.split.heldout_count}</span>held-out hours</div><span className="pill green">{data.provenance.integrity_verified ? "Dataset integrity verified" : "Integrity unverified"}</span><span className="pill">Real historical NOAA buoy</span></div>
      <div className="dataset-grid"><section className="card"><div className="card-header"><div><h2 className="card-title">Observed motion and forecast paths</h2><p className="card-subtitle">Solid lines are observed. Dashed lines are model forecasts.</p></div></div><ForecastMap data={data} /></section>
        <section className="card"><div className="card-header"><div><h2 className="card-title">Held-out model comparison</h2><p className="card-subtitle">Lower position error is better for this sample.</p></div></div><div className="card-body"><div className="table-scroll"><table className="metrics-table"><caption className="sr-only">Six-hour held-out position errors</caption><thead><tr><th>Model</th><th>Mean error</th><th>Final error</th></tr></thead><tbody>{data.models.map((model, i) => <tr key={model.id}><th><span className="model-name"><i style={{ background: COLORS[i % COLORS.length] }} />{model.label}</span></th><td>{metres(model.metrics.mean_error_m)}</td><td>{metres(model.metrics.endpoint_error_m)}</td></tr>)}</tbody></table></div><p className="settings-note">The model settings were fixed before this comparison. Six dependent hours are too small to establish general accuracy.</p><div className="dataset-scope"><strong>Source attribution: unsupported</strong><p>{data.source_attribution.reason}</p></div><p className="settings-note">{data.uncertainty_method.note}</p></div></section>
      </div>
      <section className="card"><div className="card-header"><div><h2 className="card-title">Dataset provenance</h2><p className="card-subtitle">NOAA Global Drifter Program · buoy {data.provenance.drifter_id} · {data.provenance.row_count} positions</p></div><a className="card-link" href={https(data.provenance.metadata_url)} target="_blank" rel="noreferrer">NOAA metadata <Icon name="arrow" /></a></div><div className="card-body"><p>{data.provenance.attribution}</p><div className="heading-actions"><a className="secondary-button" href={https(data.provenance.source_url)} target="_blank" rel="noreferrer">View source CSV <Icon name="arrow" /></a><a className="card-link" href={https(data.provenance.license_url)} target="_blank" rel="noreferrer">{data.provenance.license} <Icon name="arrow" /></a></div><details className="details-panel"><summary>Integrity hash and experiment limits</summary><p className="settings-note">CSV SHA-256</p><code className="evidence-id">{data.provenance.sha256}</code><ul className="reason-list">{data.limitations.map(limit => <li key={limit}>{limit}</li>)}</ul></details><details className="details-panel"><summary>Full reproducible benchmark report</summary><pre className="code-block">{JSON.stringify(data, null, 2)}</pre></details></div></section>
    </div>}
    <VectorDiagnostic api={api} />
    <TrainingDiagnostic api={api} />
    <MotionAblation api={api} />
    <MultiDrifterStudy api={api} />
    <TransferDiagnostic api={api} />
    <DatasetReadiness api={api} />
    </div></details>
  </>;
}
