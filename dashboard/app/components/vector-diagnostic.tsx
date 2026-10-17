"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Icon } from "./icons";
import styles from "./vector-diagnostic.module.css";

import { type MotionVectorReport as Report, type ArrowRow, readMotionVectorReport as readReport } from "./vector-diagnostic-state";

const number = (v: number, digits = 3) => v.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
const signed = (v: number) => `${v > 0 ? "+" : ""}${number(v)}`;
export function VectorArrows({ rows, unit, northUp }: { rows: ArrowRow[]; unit: string; northUp: boolean }) {
  const id = useId().replace(/:/g, "");
  const max = Math.max(...rows.flatMap(row => [Math.hypot(...row.observed), Math.hypot(...row.predicted), Math.hypot(...row.residual)]), 0.001);
  const scale = 45 / max;
  const arrow = (v: [number, number], x: number, y: number, color: string, key: string) => {
    const dx = v[0] * scale, dy = v[1] * scale * (northUp ? -1 : 1);
    return Math.hypot(dx, dy) < 0.5 ? <circle cx={x} cy={y} r="3" fill={color}><title>Near-zero vector</title></circle> : <path d={`M ${x} ${y} l ${dx} ${dy}`} stroke={color} strokeWidth="2.5" fill="none" markerEnd={`url(#${id}-${key})`} />;
  };
  return <div className={styles.plot}><svg viewBox={`0 0 420 ${rows.length * 134 + 62}`} role="img" aria-label={`Paired observed, predicted and error velocity arrows in ${unit}. Each row shares one scale; arrows are placed together for comparison, not on a geographic map.`}>
    <defs>{[["o", "#267864"], ["p", "#087fac"], ["r", "#ad5b31"]].map(([key, color]) => <marker key={key} id={`${id}-${key}`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill={color} /></marker>)}</defs>
    <text x="47" y="20">Observed</text><text x="178" y="20">Predicted</text><text x="286" y="20">Error · pred − obs</text>
    {rows.map((row, i) => { const y = 100 + i * 134; return <g key={row.label}><title>{row.label}: observed ({row.observed.join(", ")}), predicted ({row.predicted.join(", ")}), error ({row.residual.join(", ")}) {unit}</title><path d={`M 12 ${y + 55} h 396`} stroke="#d9eaf1" /><text x="14" y={y - 56}>{row.label}</text><text className={styles.smallText} x="90" y={y - 56}>{row.detail}</text>{[75, 205, 335].map(x => <path key={x} d={`M ${x - 49} ${y} h 98 M ${x} ${y - 46} v 92`} stroke="#d5e8ef" strokeDasharray="2 3" />)}{arrow(row.observed, 75, y, "#267864", "o")}{arrow(row.predicted, 205, y, "#087fac", "p")}{arrow(row.residual, 335, y, "#ad5b31", "r")}</g>; })}
    <text x="14" y={rows.length * 134 + 48}>45 display units = {number(max)} {unit} · {northUp ? "east → · north ↑" : "+x → · +y ↓"}</text>
  </svg><p className={styles.note}>Each arrow starts at a display origin for comparison. These rows are interval velocities, not a spatial current field. Zero motion is a dot. Axes and scales differ between NOAA and the synthetic tank.</p></div>;
}
function Results({ report }: { report: Report }) {
  const [mode, setMode] = useState<"noaa" | "tank">("noaa"), [modelId, setModelId] = useState("ridge_ar1");
  const model = report.noaa.models.find(v => v.id === modelId)!;
  const rows: ArrowRow[] = mode === "noaa" ? model.intervals.map(r => ({ label: `Hour ${r.horizon_hours}`, detail: `${r.end_utc.slice(11, 16)} UTC`, observed: [r.observed_velocity.eastward_m_s, r.observed_velocity.northward_m_s], predicted: [r.predicted_velocity.eastward_m_s, r.predicted_velocity.northward_m_s], residual: [r.residual_predicted_minus_observed.eastward_m_s, r.residual_predicted_minus_observed.northward_m_s], angle: r.angular_error_deg })) : report.synthetic_tank.vectors.map((r, i) => ({ label: `Pair ${i + 1}`, detail: `x ${number(r.x_cm, 1)} cm`, observed: [r.observed_vx_cm_s, r.observed_vy_cm_s], predicted: [r.predicted_vx_cm_s, r.predicted_vy_cm_s], residual: [r.residual_vx_cm_s, r.residual_vy_cm_s], angle: r.direction_error_deg }));
  const metric = mode === "noaa" ? { rmse: model.metrics.vector_rmse_m_s, bias: model.metrics.speed_bias_predicted_minus_observed_m_s, angular: model.metrics.angular_mae_deg, count: model.metrics.angular_scored_count } : { rmse: report.synthetic_tank.metrics.vector_rmse_cm_s, bias: report.synthetic_tank.metrics.mean_speed_bias_cm_s, angular: report.synthetic_tank.metrics.mean_direction_error_deg, count: report.synthetic_tank.metrics.direction_defined_count };
  const unit = mode === "noaa" ? "m/s" : "cm/s";
  return <div className={styles.stack}>
    <div className={styles.controls} aria-label="Vector diagnostic evidence type"><button className={mode === "noaa" ? "primary-button" : "secondary-button"} aria-pressed={mode === "noaa"} onClick={() => setMode("noaa")}>Historical NOAA</button><button className={mode === "tank" ? "primary-button" : "secondary-button"} aria-pressed={mode === "tank"} onClick={() => setMode("tank")}>Synthetic OpenCV replay</button></div>
    <div className={styles.scope}><strong>{mode === "noaa" ? "Real historical buoy motion · already-viewed sample" : "Synthetic software replay · no camera or tank measurement"}</strong><p>{mode === "noaa" ? "Six hourly observed intervals reused across three models produce 18 paired scores. This is post-hoc inspection, not an independent model test. No ocean-current field or debris survey is connected." : "Eight generated red-token frames pass through the real HSV detector, tracker and independently checked homography. The token moves 5 cm/s; the frozen reference says 4 cm/s. Four dependent pairs expose the deliberate 1 cm/s discrepancy. Nothing is saved as measured field evidence."}</p></div>
    {mode === "noaa" && <label className={styles.select}>Inspect forecast model<select value={modelId} onChange={event => setModelId(event.target.value)}>{report.noaa.models.map(m => <option value={m.id} key={m.id}>{m.label}</option>)}</select></label>}
    <div className={styles.metrics}><div><strong>{number(metric.rmse)} {unit}</strong><span>Vector RMSE · smaller is closer</span></div><div><strong>{signed(metric.bias)} {unit}</strong><span>Speed bias · predicted − observed</span></div><div><strong>{metric.angular === null ? "Undefined" : `${number(metric.angular, 1)}°`}</strong><span>Mean direction error · {metric.count}/{rows.length} eligible</span></div></div>
    <p className={styles.note}>Direction is withheld when either speed is below {mode === "noaa" ? "0.005 m/s" : "0.01 cm/s"}. Negative speed bias means the prediction is slower. Error arrows show how the full vector differs; they are not measured current forcing.</p>
    <VectorArrows rows={rows} unit={unit} northUp={mode === "noaa"} />
    <details className="details-panel"><summary>Exact interval components and direction errors</summary><div className="table-scroll"><table className="metrics-table"><caption className="sr-only">Observed, predicted and error vector components in {unit}; x is east for NOAA or mapped tank x</caption><thead><tr><th>Interval</th><th>Observed x, y ({unit})</th><th>Predicted x, y ({unit})</th><th>Error x, y ({unit})</th><th>Direction error</th></tr></thead><tbody>{rows.map(row => <tr key={row.label}><th scope="row">{row.label}</th><td>{row.observed.map(v => number(v)).join(", ")}</td><td>{row.predicted.map(v => number(v)).join(", ")}</td><td>{row.residual.map(v => signed(v)).join(", ")}</td><td>{row.angle === null ? "Undefined" : `${number(row.angle, 1)}°`}</td></tr>)}</tbody></table></div></details>
    {mode === "noaa" && <div className="table-scroll"><table className="metrics-table"><caption>Same forecasts, different questions · no model selected</caption><thead><tr><th>Model</th><th>Vector RMSE (m/s)</th><th>Average position error (m)</th><th>Final position error (m)</th></tr></thead><tbody>{report.noaa.models.map(m => <tr key={m.id}><th scope="row">{m.label}</th><td>{number(m.metrics.vector_rmse_m_s)}</td><td>{number(m.metrics.ade_m, 1)}</td><td>{number(m.metrics.fde_m, 1)}</td></tr>)}</tbody></table><p className={styles.note}>A lower average error need not mean a closer endpoint. These dependent motion metrics cannot be multiplied into independent evidence or calibrated source probabilities.</p></div>}
    <details className="details-panel"><summary>Provenance, limitations and complete vector report</summary><ul className="reason-list">{(mode === "noaa" ? report.noaa.limitations : report.synthetic_tank.limitations).map(limit => <li key={limit}>{limit}</li>)}</ul><pre className="code-block">{JSON.stringify(mode === "noaa" ? report.noaa : report.synthetic_tank, null, 2)}</pre></details>
    <p className={styles.next}><strong>What this makes possible next:</strong> use independently recorded tank motion to check travel times and whether a layout captures debris before its first protected-zone entry. A useful intervention needs recorded outcomes, not just a more attractive trajectory plot.</p>
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
    try { const response = await fetch(`${api.replace(/\/$/, "")}/api/v1/research/vector-diagnostic`, { cache: "no-store", signal: pending.signal }); const result = await readReport(response); if (controller.current === pending && !pending.signal.aborted) setReport(result); }
    catch (cause) { if (controller.current === pending) setError(pending.signal.aborted ? "The vector diagnostic timed out. No result was accepted." : cause instanceof Error ? cause.message : "Vector diagnostic unavailable."); }
    finally { window.clearTimeout(deadline); if (controller.current === pending) { controller.current = null; setLoading(false); } }
  }
  return <section className={`card ${styles.card}`} aria-label="Motion vector diagnostic"><div className={`card-header ${styles.header}`}><div><h2 className="card-title"><Icon name="wave" />Motion vectors, not just endpoints</h2><p className="card-subtitle">Compare direction, speed and position errors · separate evidence and units</p></div><button className="secondary-button" disabled={loading} onClick={() => void run()}><Icon name="play" />{loading ? "Running vector diagnostic…" : "Run vector diagnostic"}</button></div><div className={`card-body ${styles.stack}`}><p className={styles.note}>Inspect the existing NOAA forecasts and a synthetic replay through the real OpenCV pipeline. This read-only diagnostic does not fit a new model, open a camera, send messages or change source/prevention evidence.</p>{loading && <p role="status">Computing paired vectors from local fixtures…</p>}{error && <div className="notice error" role="alert">{error} No automatic retry will occur.</div>}{report && <Results report={report} />}</div></section>;
}
export function VectorDiagnostic({ api }: { api: string }) { return <Session key={api} api={api} />; }
