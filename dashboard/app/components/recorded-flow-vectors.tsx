"use client";

import { useEffect, useRef, useState } from "react";
import { VectorArrows } from "./vector-diagnostic";
import { type ArrowRow, readVectorResponse } from "./vector-diagnostic-state";
import { type RecordedFlowReport, validateRecordedFlowReport } from "./recorded-flow-vector-state";
import styles from "./vector-diagnostic.module.css";

const number = (v: number | null, digits = 3) => v === null ? "Unavailable" : v.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
function Result({ report }: { report: RecordedFlowReport }) {
  const [recordingId, setRecordingId] = useState(report.recordings[0].recording_id);
  const run = report.recordings.find(v => v.recording_id === recordingId)!;
  const first = run.vectors.slice(0, 12), c = report.coverage, m = report.metrics;
  const arrows: ArrowRow[] = first.filter(v => v.supported).map(v => ({ label: `Pair ${v.sample_index + 1}`, detail: `x ${number(v.x_cm, 1)}, y ${number(v.y_cm, 1)} cm`, observed: [v.observed_vx_cm_s, v.observed_vy_cm_s], predicted: [v.predicted_vx_cm_s!, v.predicted_vy_cm_s!], residual: [v.residual_vx_cm_s!, v.residual_vy_cm_s!], angle: v.direction_error_deg }));
  return <div className={styles.stack}>
    <div className={styles.scope}><strong>{report.data_origin === "SYNTHETIC_CAPTURE_REPLAY" ? "Synthetic capture replay · no physical validation" : "Recorded tank capture · provenance not independently verified"}</strong><p>This is a frozen field checked at observed validation midpoints. It is a conditional interpolation check, not a free-running forecast or a new independent experiment. Stored capture labels do not establish physical validation.</p></div>
    <div className={styles.note}>Frozen flow <code>{report.flow_id}</code> · SHA-256 <code className="evidence-id">{report.flow_content_hash}</code><p>{c.supported_sample_count}/{c.validation_sample_count} extracted validation vectors supported ({number(c.supported_fraction * 100, 1)}%); {c.unsupported_sample_count} unsupported. All {c.validation_recording_count} validation runs contribute to this denominator.</p></div>
    <div className={styles.metrics}><div><strong>{number(m.vector_rmse_cm_s)} cm/s</strong><span>Pooled supported-vector RMSE</span></div><div><strong>{number(m.mean_speed_bias_cm_s)} cm/s</strong><span>Speed bias · predicted − observed</span></div><div><strong>{number(m.equal_recording_mean_rmse_cm_s)} cm/s</strong><span>Equal-run mean RMSE · {m.recordings_with_supported_samples}/{c.validation_recording_count} runs supported</span></div></div>
    <label className={styles.select}>Inspect recorded validation run<select value={recordingId} onChange={event => setRecordingId(event.target.value)}>{report.recordings.map(v => <option value={v.recording_id} key={v.recording_id}>{v.recording_id}</option>)}</select></label>
    <p className={styles.note}>{run.counts.observed_point_count}/{run.counts.point_count} positions observed; {run.counts.missing_point_count} missing, including {run.counts.ambiguous_point_count} ambiguous detections; {run.counts.association_gap_count} association gaps and {run.counts.track_count} tracks. Gaps are never bridged. Run support: {run.counts.supported_sample_count}/{run.counts.extracted_sample_count} extracted vectors.</p>
    <p className={styles.note}>Showing the first {first.length} of {run.vectors.length} vectors in this run, capped at 12 for display. Metrics above use every supported vector from every validation run. Unsupported rows retain observed components; predictions and errors are withheld. Direction is undefined below 0.01 cm/s. Arrow display uses +x right and +y down; the physical axes follow your water-plane calibration, not a universal tank orientation.</p>
    {arrows.length ? <VectorArrows rows={arrows} unit="cm/s" northUp={false} /> : <p className={styles.note}>No supported arrows in this displayed subset. Unsupported observations are retained below.</p>}
    <div className="table-scroll"><table className="metrics-table"><caption>First {first.length} recorded vectors · cm/s · calibration coordinate components</caption><thead><tr><th>Pair</th><th>Support</th><th>Observed x, y</th><th>Predicted x, y</th><th>Error x, y</th></tr></thead><tbody>{first.map(v => <tr key={v.sample_index}><th scope="row">{v.sample_index + 1}</th><td>{v.supported ? "Supported" : "Unsupported"}</td><td>{number(v.observed_vx_cm_s)}, {number(v.observed_vy_cm_s)}</td><td>{v.supported ? `${number(v.predicted_vx_cm_s)}, ${number(v.predicted_vy_cm_s)}` : "Withheld"}</td><td>{v.supported ? `${number(v.residual_vx_cm_s)}, ${number(v.residual_vy_cm_s)}` : "Withheld"}</td></tr>)}</tbody></table></div>
    <details className="details-panel"><summary>All recorded vectors, bindings and limitations</summary><ul className="reason-list">{report.limitations.map(text => <li key={text}>{text}</li>)}</ul><pre className="code-block">{JSON.stringify(report, null, 2)}</pre></details>
  </div>;
}
function Session({ api, flowId }: { api: string; flowId: string }) {
  const [report, setReport] = useState<RecordedFlowReport | null>(null), [loading, setLoading] = useState(false), [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => { controller.current?.abort(); controller.current = null; }, []);
  async function inspect() {
    if (controller.current) return;
    const pending = new AbortController(); controller.current = pending;
    const deadline = window.setTimeout(() => pending.abort(), 30_000);
    setReport(null); setLoading(true); setError("");
    try {
      const response = await fetch(`${api.replace(/\/$/, "")}/api/v1/flow/${encodeURIComponent(flowId)}/vector-diagnostic`, { cache: "no-store", signal: pending.signal });
      const result = await readVectorResponse(response, value => validateRecordedFlowReport(value, flowId), 8_000_000);
      if (controller.current === pending && !pending.signal.aborted) setReport(result);
    } catch (cause) { if (controller.current === pending) setError(pending.signal.aborted ? "Recorded-vector inspection timed out. No result was accepted." : cause instanceof Error ? cause.message : "Recorded drift inspection unavailable."); }
    finally { window.clearTimeout(deadline); if (controller.current === pending) { controller.current = null; setLoading(false); } }
  }
  return <section className={styles.stack} aria-label="Recorded drift vector inspection"><h3>Check the recorded drift vectors</h3><p className={styles.note}>Inspect the saved fit and its exact validation recordings. This read-only check does not refit, start a webcam, send messages or admit a profile.</p><button className="secondary-button" disabled={loading} onClick={() => void inspect()}>{loading ? "Inspecting recorded drift…" : "Inspect recorded drift vectors"}</button>{loading && <p role="status">Reading frozen flow and saved validation evidence…</p>}{error && <div className="notice error" role="alert">{error} No automatic retry will occur.</div>}{report && <Result report={report} />}</section>;
}
export function RecordedFlowVectors({ api, flowId }: { api: string; flowId: string }) { return <Session key={`${api}\n${flowId}`} api={api} flowId={flowId} />; }
