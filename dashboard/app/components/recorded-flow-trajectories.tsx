"use client";

import { useEffect, useRef, useState } from "react";
import { readVectorResponse } from "./vector-diagnostic-state";
import { type RecordedTrajectoryReport, type TrajectoryRun, validateRecordedTrajectoryReport } from "./recorded-trajectory-state";
import styles from "./vector-diagnostic.module.css";

const number = (v: number, digits = 2) => v.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
function PathPlot({ report, run }: { report: RecordedTrajectoryReport; run: TrajectoryRun }) {
  if (run.status !== "SCORED") return <p className={styles.note}>No path is drawn for this withheld run. A broken or unsupported track is never bridged into a successful forecast.</p>;
  const b = report.bounds, width = b.x_max_cm - b.x_min_cm, height = b.y_max_cm - b.y_min_cm;
  const scale = Math.min(430 / width, 280 / height), left = 35 + (430 - width * scale) / 2, top = 25 + (280 - height * scale) / 2;
  const x = (v: number) => left + scale * (v - b.x_min_cm), y = (v: number) => top + scale * (v - b.y_min_cm);
  const initial = `${x(run.initial_position.x_cm!)},${y(run.initial_position.y_cm!)}`;
  const observed = [initial, ...run.comparisons.map(p => `${x(p.observed_x_cm)},${y(p.observed_y_cm)}`)].join(" ");
  const predicted = [initial, ...run.comparisons.map(p => `${x(p.predicted_x_cm)},${y(p.predicted_y_cm)}`)].join(" ");
  const last = run.comparisons[run.comparisons.length - 1];
  return <div className={styles.plot}><svg viewBox="0 0 500 335" role="img" aria-label={`Recorded and free-running predicted paths in calibrated centimetres for ${run.recording_id}. Observed green; prediction purple dashed. Both start at the first observation.`}>
    <rect x={left} y={top} width={width * scale} height={height * scale} fill="#f5f2fb" stroke="#b9b0cb" />
    <polyline points={observed} fill="none" stroke="#267864" strokeWidth="3" /><polyline points={predicted} fill="none" stroke="#6350b2" strokeWidth="3" strokeDasharray="7 4" />
    <circle cx={x(run.initial_position.x_cm!)} cy={y(run.initial_position.y_cm!)} r="5" fill="#443657"><title>Common initial observation; no later observation resets the prediction</title></circle>
    <circle cx={x(last.observed_x_cm)} cy={y(last.observed_y_cm)} r="5" fill="#267864"><title>Recorded endpoint</title></circle><circle cx={x(last.predicted_x_cm)} cy={y(last.predicted_y_cm)} r="5" fill="#6350b2"><title>Predicted endpoint</title></circle>
    <text x="35" y="18" fontSize="11" fill="#4d455e">Tank bounds · {number(width, 1)} × {number(height, 1)} cm</text><text x="35" y="325" fontSize="11" fill="#4d455e">Green: recorded · Purple dashed: predicted · Dot: shared start</text>
  </svg><p className={styles.note}>Both axes share the same centimetre scale. Plot uses +x right, +y down as a display convention; physical coordinate directions follow your calibration. Lines join all {run.comparisons.length} scored timestamp positions; wall bounces and other motion between samples are not drawn. No ocean geography, traps or protection outcome is represented.</p></div>;
}
function Results({ report }: { report: RecordedTrajectoryReport }) {
  const [runId, setRunId] = useState(report.recordings[0].recording_id);
  const run = report.recordings.find(r => r.recording_id === runId)!, c = report.coverage;
  return <div className={styles.stack}>
    <div className={styles.scope}><strong>{report.data_origin === "SYNTHETIC_CAPTURE_REPLAY" ? "Synthetic capture replay" : "Recorded capture · provenance unverified"} · no physical validation</strong><p>This forecast starts once at the first recorded position, then advances through the frozen mean field without resetting to later observations. Saved later positions are used only for scoring. These already reviewed runs are not a new independent experiment.</p></div>
    <p className={styles.note}>Frozen flow <code>{report.flow_id}</code> · SHA-256 <code className="evidence-id">{report.flow_content_hash}</code></p>
    <div className={styles.metrics}><div><strong>{c.complete_recordings}/{c.validation_recordings}</strong><span>Complete declared validation runs</span></div><div><strong>{c.scored_forecast_points}/{c.planned_forecast_points}</strong><span>Scored / planned forecast points · {c.withheld_forecast_points} withheld</span></div><div><strong>{report.metrics ? `${number(report.metrics.equal_recording_ade_cm)} cm` : "Withheld"}</strong><span>Equal-run mean path error · withheld if any run fails</span></div></div>
    <p className={styles.note}>Deterministic Euler steps ≤0.05 s, reflecting rectangular walls, zero diffusion and no traps. The model advances from its own predictions at actual saved time intervals. This is separate from the conditional vector check and the stochastic source/prevention simulators.</p>
    <label className={styles.select}>Inspect free-running validation run<select value={runId} onChange={event => setRunId(event.target.value)}>{report.recordings.map(r => <option key={r.recording_id} value={r.recording_id}>{r.recording_id} · {r.status === "SCORED" ? "Scored" : "Withheld"}</option>)}</select></label>
    {run.metrics ? <div className={styles.metrics}><div><strong>{number(run.metrics.ade_cm)} cm</strong><span>This run’s mean path error</span></div><div><strong>{number(run.metrics.fde_cm)} cm</strong><span>Final position error</span></div><div><strong>{number(run.metrics.position_rmse_cm)} cm</strong><span>Position RMSE · {run.scored_forecast_points} dependent points</span></div></div> : <div className="notice error" role="status">Full run withheld: {run.reason_codes.join(", ")}. Its {run.planned_forecast_points} planned points stay in the denominator.</div>}
    <PathPlot report={report} run={run} />
    {run.status === "SCORED" && <details className="details-panel"><summary>Actual timestamps and path errors</summary><p className={styles.note}>Showing first {Math.min(12, run.comparisons.length)} points; plot and metrics use all scored points. Elapsed time subtracts the saved start offset ({number(run.time_origin_s, 3)} s), rather than assuming acquisition began at zero.</p><div className="table-scroll"><table className="metrics-table"><caption>Recorded versus predicted positions in calibrated cm</caption><thead><tr><th>Elapsed s</th><th>Recorded x, y</th><th>Predicted x, y</th><th>Error cm</th></tr></thead><tbody>{run.comparisons.slice(0, 12).map(p => <tr key={p.t_s}><th scope="row">{number(p.t_s - run.time_origin_s, 3)}</th><td>{number(p.observed_x_cm)}, {number(p.observed_y_cm)}</td><td>{number(p.predicted_x_cm)}, {number(p.predicted_y_cm)}</td><td>{number(p.position_error_cm)}</td></tr>)}</tbody></table></div></details>}
    <details className="details-panel"><summary>All trajectories, withheld runs and provenance</summary><ul className="reason-list">{report.limitations.map(text => <li key={text}>{text}</li>)}</ul><pre className="code-block">{JSON.stringify(report, null, 2)}</pre></details>
  </div>;
}
function Session({ api, flowId }: { api: string; flowId: string }) {
  const [report, setReport] = useState<RecordedTrajectoryReport | null>(null), [loading, setLoading] = useState(false), [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => { controller.current?.abort(); controller.current = null; }, []);
  async function run() {
    if (controller.current) return;
    const pending = new AbortController(); controller.current = pending; const timer = window.setTimeout(() => pending.abort(), 30_000);
    setReport(null); setLoading(true); setError("");
    try { const response = await fetch(`${api.replace(/\/$/, "")}/api/v1/flow/${encodeURIComponent(flowId)}/trajectory-diagnostic`, { cache: "no-store", signal: pending.signal }); const result = await readVectorResponse(response, value => validateRecordedTrajectoryReport(value, flowId), 8_000_000); if (controller.current === pending && !pending.signal.aborted) setReport(result); }
    catch (cause) { if (controller.current === pending) setError(pending.signal.aborted ? "Recorded trajectory replay timed out. No result was accepted." : cause instanceof Error ? cause.message : "Recorded trajectory replay unavailable."); }
    finally { window.clearTimeout(timer); if (controller.current === pending) { controller.current = null; setLoading(false); } }
  }
  return <section className={styles.stack} aria-label="Recorded free-running trajectory replay"><h3>Test the complete drift path</h3><p className={styles.note}>Replay the saved validation runs from each first observation using the frozen flow. This read-only action does not start a camera, fit a model, send messages or change a profile.</p><button className="secondary-button" disabled={loading} onClick={() => void run()}>{loading ? "Replaying recorded paths…" : "Replay free-running drift paths"}</button>{loading && <p role="status">Forecasting from initial positions, then scoring saved later observations…</p>}{error && <div className="notice error" role="alert">{error} No automatic retry will occur.</div>}{report && <Results report={report} />}</section>;
}
export function RecordedFlowTrajectories({ api, flowId }: { api: string; flowId: string }) { return <Session key={`${api}\n${flowId}`} api={api} flowId={flowId} />; }
