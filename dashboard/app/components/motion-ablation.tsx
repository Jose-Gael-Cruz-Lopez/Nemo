"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "./icons";
import { MOTION_BASELINE_IDS, MOTION_MODEL_IDS, motionSkillLabel, readMotionAblation, type MotionAblationReport, type MotionModelId } from "./motion-ablation-state";
import styles from "./motion-ablation.module.css";

const LABELS: Record<MotionModelId, string> = { stationary: "Stationary", last_drift: "Last drift", mean_drift: "Mean drift", ridge_ar1: "Learned ridge" };
const metres = (value: number) => `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })} m`;
const delta = (value: number) => `${value > 0 ? "+" : ""}${metres(value)}`;

function MotionAblationSession({ api }: { api: string }) {
  const [report, setReport] = useState<MotionAblationReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);

  async function run() {
    if (controller.current) return;
    const pending = new AbortController(); controller.current = pending;
    setLoading(true); setError(""); setReport(null);
    try {
      const response = await fetch(`${api.replace(/\/$/, "")}/api/v1/research/motion-ablation`, { cache: "no-store", signal: pending.signal });
      const result = await readMotionAblation(response);
      if (!pending.signal.aborted && controller.current === pending) setReport(result);
    } catch (cause) {
      if (!pending.signal.aborted && controller.current === pending) setError(cause instanceof Error ? cause.message : "The motion ablation could not be loaded.");
    } finally {
      if (controller.current === pending && !pending.signal.aborted) { controller.current = null; setLoading(false); }
    }
  }

  return <section className={`card ${styles.card}`} aria-label="Training-only motion ablation">
    <div className={`card-header ${styles.header}`}><div><h2 className="card-title"><Icon name="wave" />What does learning add?</h2><p className="card-subtitle">Compare learned velocity memory with three simple motion baselines.</p></div><button className="secondary-button" disabled={loading} onClick={() => void run()}><Icon name="play" />{loading ? "Running motion ablation…" : "Run motion ablation"}</button></div>
    <div className={`card-body ${styles.stack}`}>
      <p className={styles.scope}><strong>Training-only comparison, no automatic winner.</strong> Five overlapping origins fit the first eight through twelve positions of one historical NOAA buoy-day. Six-hour forecasts are scored only inside its first eighteen training positions; the final six held-out hours stay outside this experiment.</p>
      <dl className={styles.models}><div><dt>Stationary</dt><dd>Stay at the last observed position.</dd></div><div><dt>Last drift</dt><dd>Continue the latest observed displacement.</dd></div><div><dt>Mean drift</dt><dd>Continue the prefix’s average displacement.</dd></div><div><dt>Learned ridge</dt><dd>Learn how the velocity changes from one step to the next.</dd></div></dl>
      <p className="settings-note">Mean drift helps separate the value of averaging past motion from the value of learning velocity memory. The same prefixes and forecast horizons are used for every model. These overlapping training origins are dependent observations, not independent replications.</p>
      {loading && <p className="settings-note" role="status">Running the fixed offline experiment on training positions only… No provider, camera or messaging action is requested.</p>}
      {error && <div className="notice error" role="alert"><span>{error} No automatic retry will occur.</span><button className="card-link" disabled={loading} onClick={() => void run()}>Retry motion ablation <Icon name="arrow" /></button></div>}
      {report && <>
        <div className={styles.badges}><span className="pill">5 dependent training origins</span><span className="pill">4 motion models</span><span className="pill">Held-out data not used</span><span className="pill">No model promotion</span></div>
        <p className="settings-note" role="status">Motion ablation ready. Negative error differences favor learned ridge; positive differences favor the named baseline.</p>
        <div className="table-scroll"><table className={`metrics-table ${styles.table}`}><caption className="sr-only">Learned ridge minus each baseline’s position error on five dependent training origins, by forecast horizon</caption><thead><tr><th rowSpan={2} scope="col">Hours ahead</th>{MOTION_BASELINE_IDS.map(id => <th key={id} colSpan={3} scope="colgroup">Ridge versus {LABELS[id].toLowerCase()}</th>)}</tr><tr>{MOTION_BASELINE_IDS.map(id => <ComparisonHeaders key={id} />)}</tr></thead><tbody>{Array.from({ length: 6 }, (_, i) => <tr key={i}><th scope="row">{i + 1}</th>{MOTION_BASELINE_IDS.map(id => {
          const row = report.paired_comparisons.find(item => item.baseline_id === id)!.per_horizon[i];
          return <ComparisonCells key={id} row={row} />;
        })}</tr>)}</tbody></table></div>
        <p className="settings-note">Δ error = ridge error − baseline error, paired at the same origin and horizon. “Lower / equal / higher” counts all five training origins; it is not a win probability. MAE skill = 1 − sum(ridge errors) / sum(baseline errors). Skill 0 means equal mean error; negative means worse. A zero baseline error makes skill undefined and is shown as unavailable.</p>
        <details className="details-panel"><summary>Absolute motion errors and paired error ranges</summary><div className="table-scroll"><table className="metrics-table"><caption className="sr-only">Mean position errors for all four motion models on five dependent training origins</caption><thead><tr><th scope="col">Hours ahead</th>{MOTION_MODEL_IDS.map(id => <th key={id} scope="col">{LABELS[id]} · mean</th>)}</tr></thead><tbody>{Array.from({ length: 6 }, (_, i) => <tr key={i}><th scope="row">{i + 1}</th>{MOTION_MODEL_IDS.map(id => <td key={id}>{metres(report.aggregates.find(item => item.id === id)!.per_horizon[i].mean_error_m)}</td>)}</tr>)}</tbody></table></div><div className="table-scroll"><table className="metrics-table"><caption className="sr-only">Median and range of paired ridge-minus-baseline error differences by horizon</caption><thead><tr><th scope="col">Baseline</th><th scope="col">Hours ahead</th><th scope="col">Median Δ</th><th scope="col">Minimum Δ</th><th scope="col">Maximum Δ</th></tr></thead><tbody>{report.paired_comparisons.flatMap(pair => pair.per_horizon.map(row => <tr key={`${pair.baseline_id}-${row.horizon_hours}`}><th scope="row">{LABELS[pair.baseline_id]}</th><td>{row.horizon_hours}</td><td>{delta(row.median_delta_m)}</td><td>{delta(row.min_delta_m)}</td><td>{delta(row.max_delta_m)}</td></tr>))}</tbody></table></div></details>
        <details className="details-panel"><summary>Limitations and source integrity</summary><ul className="reason-list">{report.limitations.map((limit, i) => <li key={i}>{limit}</li>)}</ul><p className="settings-note">NOAA hourly positions are quality-controlled and interpolated; upstream processing may use later raw fixes. Training-only code isolation does not establish real-time forecast skill. This buoy experiment does not establish plastic-source accuracy, physical validation, calibrated probabilities or coral benefit.</p><p className="settings-note">NOAA buoy {report.provenance.drifter_id} · {report.provenance.row_count} pinned source rows · first {report.split.training_count} used here. <a className="card-link" href={report.provenance.source_url} target="_blank" rel="noreferrer">Inspect the official NOAA source <Icon name="arrow" /></a></p><code className="evidence-id">{report.provenance.sha256}</code></details>
        <details className="details-panel"><summary>Full motion-ablation JSON</summary><pre className="code-block">{JSON.stringify(report, null, 2)}</pre></details>
      </>}
      {!report && !loading && !error && <p className="settings-note">Run explicitly to read the content-pinned local NOAA sample. No operator token or model-provider account is required.</p>}
    </div>
  </section>;
}

function ComparisonHeaders() {
  return <><th scope="col">Mean Δ error</th><th scope="col">Lower / equal / higher</th><th scope="col">MAE skill</th></>;
}
function ComparisonCells({ row }: { row: MotionAblationReport["paired_comparisons"][number]["per_horizon"][number] }) {
  return <><td>{delta(row.mean_delta_m)}</td><td>{row.candidate_lower_error_count} / {row.equal_error_count} / {row.candidate_higher_error_count}</td><td>{motionSkillLabel(row.skill_vs_baseline)}</td></>;
}

/** An API target change discards prior reads/results rather than crossing environments. */
export function MotionAblation({ api }: { api: string }) {
  return <MotionAblationSession key={api} api={api} />;
}
