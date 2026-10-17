"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { Icon } from "./icons";
import { HelpLabel, PlotSeriesControls } from "./plot-controls";
import { useOperator } from "./operator-provider";
import { readVectorResponse } from "./vector-diagnostic-state";
import { type CurrentForecast, type CurrentPoint, validateCurrentForecast } from "./current-forecast-state";
import styles from "./fresh-drifter-study.module.css";

const date = (value: string) => `${value.replace("T", " ").replace(/:00(?:\.000)?Z$/, " UTC")}`;
const fmt = (value: number) => value.toLocaleString(undefined, { maximumFractionDigits: 1 });
type Visibility = { dynamic: boolean; persistence: boolean; currents: boolean };

export function CurrentForecastFigure({ report, frame, visible, onToggle }: { report: CurrentForecast; frame: number; visible: Visibility; onToggle: (id: string, checked: boolean) => void }) {
  const title = useId(), marker = useId().replaceAll(":", "");
  const vectors = report.vector_frames[frame]?.vectors ?? [];
  // A single full-data domain and vector scale survive every checkbox/valid-time change.
  const positions = [...report.dynamic.track, ...report.persistence.track, report.release];
  const origin = report.release, cos = Math.cos(origin.latitude_deg * Math.PI / 180);
  const local = (p: { longitude_deg: number; latitude_deg: number }) => [(p.longitude_deg - origin.longitude_deg) * 111195 * cos, (p.latitude_deg - origin.latitude_deg) * 111195];
  const xy = positions.map(local), xs = xy.map(p => p[0]), ys = xy.map(p => p[1]);
  const span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys), 1000) * 1.16;
  const cx = (Math.max(...xs) + Math.min(...xs)) / 2, cy = (Math.max(...ys) + Math.min(...ys)) / 2;
  const screen = (p: { longitude_deg: number; latitude_deg: number }) => { const [x, y] = local(p); return [330 + (x - cx) * 290 / span, 174 - (y - cy) * 290 / span]; };
  const line = (points: CurrentPoint[]) => points.map(p => screen(p).join(",")).join(" ");
  const speed = Math.max(...report.vector_frames.flatMap(f => f.vectors.map(v => Math.hypot(v.eastward_m_s, v.northward_m_s))), 0.01);
  const start = screen(origin), empty = !visible.dynamic && !visible.persistence && !visible.currents;
  return <figure className={styles.plotFrame}>
    <PlotSeriesControls legend="Show ocean predictions" series={[
      { id: "dynamic", label: "Current-driven path", explanation: "Simulated floating particle following the changing forecast current at each position and time.", color: "#087fac", checked: visible.dynamic },
      { id: "persistence", label: "Straight baseline", explanation: "The initial current held constant for the entire prediction. A comparison, not an observed path.", color: "#a78344", dashed: true, checked: visible.persistence },
      { id: "currents", label: "Forecast current arrows", explanation: "Direction and relative speed of the modeled surface current at the selected valid time. Arrows are not particle paths.", color: "#758da0", checked: visible.currents },
    ]} onChange={onToggle} />
    {empty && <p className={styles.note} role="status">No layers selected. Check a path or the current arrows to inspect the prediction.</p>}
    <svg className={styles.plot} viewBox="0 0 660 350" role="img" aria-labelledby={title}>
      <title id={title}>Hypothetical ocean release: changing-current particle path and initial-current baseline. Both are predictions, with equal east/north scale in an approximate local plot projection. No observed waste track.</title>
      <defs><marker id={marker} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="#758da0" /></marker><clipPath id={`${marker}-clip`}><rect x="170" y="14" width="320" height="320" /></clipPath></defs>
      {[0, 1, 2, 3, 4].map(i => <g key={i} stroke="#dcecf5"><line x1={185 + i * 72.5} y1="29" x2={185 + i * 72.5} y2="319" /><line x1="185" y1={29 + i * 72.5} x2="475" y2={29 + i * 72.5} /></g>)}
      {visible.currents && <g data-plot-series="currents" clipPath={`url(#${marker}-clip)`}>{vectors.map((v, i) => { const [x, y] = screen(v); return <line key={i} x1={x} y1={y} x2={x + v.eastward_m_s / speed * 18} y2={y - v.northward_m_s / speed * 18} stroke="#758da0" strokeWidth="1.4" markerEnd={`url(#${marker})`}><title>{`Interpolated forecast current ${Math.hypot(v.eastward_m_s, v.northward_m_s).toFixed(3)} m/s · ${date(report.vector_frames[frame].time_utc)}`}</title></line>; })}</g>}
      {visible.persistence && <g data-plot-series="persistence"><polyline points={line(report.persistence.track)} stroke="#a78344" strokeWidth="2.5" fill="none" strokeDasharray="7 5" /></g>}
      {visible.dynamic && <g data-plot-series="dynamic"><polyline points={line(report.dynamic.track)} stroke="#087fac" strokeWidth="3" fill="none" />{report.dynamic.track.filter((_, i) => i % 4 === 0 || i === report.dynamic.track.length - 1).map(p => { const [x, y] = screen(p); return <circle key={p.time_utc} cx={x} cy={y} r="3.5" fill="#087fac"><title>{`Predicted particle · ${date(p.time_utc)} · local modeled speed ${fmt(p.speed_m_s)} m/s`}</title></circle>; })}</g>}
      <circle cx={start[0]} cy={start[1]} r="5" fill="white" stroke="#225b7c" strokeWidth="2"><title>Hypothetical release point</title></circle>
      <text x="35" y="343" fontSize="11" fill="#526f83">Plot grid: {fmt(span / 4000)} km · equal axes</text><text x="625" y="343" textAnchor="end" fontSize="11" fill="#526f83">East → · North ↑</text>
    </svg>
    <figcaption className={styles.plotCaption}>A bend comes from changes in current direction. Dots mark predicted times. Arrows interpolate the roughly 4 km source grid; they are not finer observations.</figcaption>
  </figure>;
}

type Answer = { action: "REPORT" | "STOP"; explanation: string; live_model_response: boolean; snapshot_sha256: string; method_sha256: string; evidence_ids: string[]; failure_code?: string };
function answer(value: unknown, report: CurrentForecast): Answer {
  const v = value as Answer;
  if (!v || !["REPORT", "STOP"].includes(v.action) || typeof v.explanation !== "string" || typeof v.live_model_response !== "boolean" || v.snapshot_sha256 !== report.snapshot_sha256 || v.method_sha256 !== report.method_sha256 || !Array.isArray(v.evidence_ids)) throw new Error("The current-forecast review did not match this snapshot.");
  const allowed = [`current-snapshot:${report.snapshot_sha256}`, `current-method:${report.method_sha256}`];
  if (v.evidence_ids.some(id => !allowed.includes(id)) || v.action === "REPORT" && (v.evidence_ids.length !== 2 || new Set(v.evidence_ids).size !== 2)) throw new Error("The review cited unrelated current evidence.");
  return v;
}

function CurrentResults({ api, report }: { api: string; report: CurrentForecast }) {
  const { token } = useOperator();
  const [visible, setVisible] = useState<Visibility>({ dynamic: true, persistence: true, currents: true }), [frame, setFrame] = useState(0);
  const [review, setReview] = useState<Answer | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function ask() {
    if (!token || controller.current) return;
    const pending = new AbortController(); controller.current = pending; setBusy(true); setError(""); setReview(null);
    const timer = window.setTimeout(() => pending.abort(), 90_000);
    try {
      const response = await fetch(`${api}/api/v1/research/current-forecast/investigate`, { method: "POST", cache: "no-store", signal: pending.signal, headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ question: "Explain why the current-driven path differs from the straight baseline, and what must be measured before this predicts real waste accurately.", snapshot_sha256: report.snapshot_sha256, method_sha256: report.method_sha256 }) });
      const result = await readVectorResponse(response, value => answer(value, report), 200_000);
      if (!pending.signal.aborted) setReview(result);
    } catch (cause) { if (controller.current === pending) setError(pending.signal.aborted ? "Chalk exceeded this review’s time limit. The prediction remains available." : cause instanceof Error ? cause.message : "The review is unavailable."); }
    finally { window.clearTimeout(timer); if (controller.current === pending) { controller.current = null; setBusy(false); } }
  }
  return <div className={styles.stack}>
    <div className={styles.resultSummary}><h3>Follow the forecast flow as it changes.</h3><p>Hypothetical release south of Oʻahu · {date(report.release.start_time_utc)} · six-hour ocean prediction · no observed waste track</p></div>
    <p className={styles.note}>This is a captured PacIOOS forecast, separate from the historical NOAA buoy comparison above. It does not predict the water inside your tank.</p>
    {report.mode.includes("archived") && <div className={styles.scope} role="status">This forecast window has passed. The saved snapshot remains an archived model preview; it is not the latest forecast.</div>}
    {report.dynamic.status !== "COMPLETED" && <div className={styles.scope} role="status">Current-driven path stopped after {fmt(report.dynamic.completed_horizon_s / 3600)} hours: {report.dynamic.reason_code ?? report.dynamic.status}. No unsupported continuation is drawn.</div>}
    {report.persistence.status !== "COMPLETED" && <div className={styles.scope} role="status">Straight baseline stopped after {fmt(report.persistence.completed_horizon_s / 3600)} hours: {report.persistence.reason_code ?? report.persistence.status}. Its missing continuation stays unknown.</div>}
    <CurrentForecastFigure report={report} frame={frame} visible={visible} onToggle={(id, checked) => setVisible(previous => ({ ...previous, [id]: checked }))} />
    {report.vector_frames.length > 0 && <label className={styles.label}>Current arrows at {date(report.vector_frames[frame].time_utc)}<input aria-label="Forecast current valid time" type="range" min={0} max={report.vector_frames.length - 1} step={1} value={frame} onChange={event => setFrame(Number(event.target.value))} /><span className={styles.note}>Change the time to see the flow change. Both particle predictions stay fixed. The longest arrow represents {Math.max(...report.vector_frames.flatMap(f => f.vectors.map(v => Math.hypot(v.eastward_m_s, v.northward_m_s))), 0.01).toFixed(3)} m/s at every time.</span></label>}
    <p className={styles.note}><HelpLabel label="Endpoint separation" explanation="Distance between the two predicted endpoints. This is model disagreement, not a measured prediction error or proof one path is better." />: <strong>{report.endpoint_separation_m === null ? "Withheld" : `${fmt(report.endpoint_separation_m)} m`}</strong>. Real prediction error remains unknown until compared with an independently observed floating object.</p>
    <section className={styles.chalk} aria-label="Chalk current-forecast review"><h3>Why does this path turn?</h3><p className={styles.note}>Ask Chalk to explain this exact current snapshot and its limits.</p><button type="button" className="primary-button" disabled={!token || busy} onClick={() => void ask()}><Icon name="agent" />{busy ? "Reviewing current evidence…" : "Explain current-driven prediction"}</button>{!token && <p className={styles.note}><Link href="/login">Sign in to use Chalk</Link></p>}{error && <p className="notice error" role="alert">{error} No automatic retry will occur.</p>}<p className="sr-only" role="status" aria-atomic="true">{review ? `${review.action}. ${review.explanation}` : busy ? "Chalk is reviewing this current forecast." : ""}</p>{review && <div className={styles.answer}><span className="pill">{review.action} · {review.live_model_response ? "Live Chalk response" : "No live model response"}</span><p>{review.explanation}</p><details className="details-panel"><summary>Evidence citations</summary><pre className="code-block">{JSON.stringify(review.evidence_ids, null, 2)}</pre></details></div>}</section>
    <details className="details-panel"><summary>Current source, numerical method and limitations</summary><p>{report.forcing.attribution}</p><p className={styles.note}>Captured {date(report.forcing.captured_at_utc)} · valid {date(report.forcing.valid_start_utc)} to {date(report.forcing.valid_end_utc)} · depth {report.forcing.depth_m} m. Single model issue time: {report.forcing.model_issue_time_utc ?? "not exposed by this best-time-series API"}.</p><p className={styles.note}>The solver samples current direction and speed at the changing particle location and time. It stops at missing cells or outside the supplied field. Wind response, beaching, entanglement and reef-scale accuracy are not validated.</p><a className="card-link" href={report.forcing.metadata_url} target="_blank" rel="noreferrer">PacIOOS source documentation <Icon name="arrow" /></a><ul className="reason-list">{report.limitations.map(item => <li key={item}>{item}</li>)}</ul><details className="details-panel"><summary>Full current prediction report</summary><pre className="code-block">{JSON.stringify(report, null, 2)}</pre></details></details>
  </div>;
}

export function CurrentForecastPreview({ api }: { api: string }) {
  const [report, setReport] = useState<CurrentForecast | null>(null), [loading, setLoading] = useState(false), [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function load() {
    if (controller.current) return;
    const pending = new AbortController(); controller.current = pending; setLoading(true); setError("");
    const timer = window.setTimeout(() => pending.abort(), 30_000);
    try {
      const response = await fetch(`${api}/api/v1/research/current-forecast`, { cache: "no-store", signal: pending.signal });
      const result = await readVectorResponse(response, validateCurrentForecast, 800_000);
      if (!pending.signal.aborted) setReport(result);
    } catch (cause) { if (controller.current === pending) setError(pending.signal.aborted ? "The saved current forecast timed out." : cause instanceof Error ? cause.message : "The saved current forecast is unavailable."); }
    finally { window.clearTimeout(timer); if (controller.current === pending) { controller.current = null; setLoading(false); } }
  }
  return <section className={`card ${styles.card}`} aria-label="Changing ocean-current forecast"><div className={`card-header ${styles.header}`}><div><h2 className="card-title"><Icon name="wave" />What if the current turns?</h2><p className="card-subtitle">A real ocean-current forecast drives a hypothetical floating particle.</p></div><button type="button" className="primary-button" disabled={loading} onClick={() => void load()}><Icon name="play" />{loading ? "Loading saved currents…" : "Load current-driven prediction"}</button></div><div className={`card-body ${styles.stack}`}>{!report && <p className={styles.note}>Compare changing-current transport with the straight baseline. This opens a saved public forecast; it does not start a camera, send messages or change your experiment.</p>}{loading && <p role="status">Verifying the saved current field and integrating the two paths…</p>}{error && <p className="notice error" role="alert">{error} No automatic retry will occur.</p>}{report && <CurrentResults key={report.snapshot_sha256} api={api} report={report} />}</div></section>;
}
