"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Icon } from "./icons";
import { readVectorResponse } from "./vector-diagnostic-state";
import { type KalmanPoint, type KalmanReport, type KalmanTrack, validateKalmanReport } from "./kalman-diagnostic-state";
import styles from "./kalman-diagnostic.module.css";

const fmt = (n: number, digits = 1) => n.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
function Trajectory({ group, model }: { group: KalmanReport["groups"][number]; model: KalmanTrack }) {
  const title = useId();
  if (model.status !== "SCORED" || !model.forecast_anchor) return <div className="notice error" role="status">All six forecasts for this track are withheld: {model.predictions.flatMap(p => p.reason_codes).filter((v,i,a) => a.indexOf(v) === i).join(", ")}. No predicted path is drawn.</div>;
  const observed = [group.training_track[17], ...group.heldout_track];
  const predicted = [model.forecast_anchor, ...model.predictions] as { x_m: number; y_m: number }[];
  const points = [...observed, ...predicted], xs = points.map(p => p.x_m), ys = points.map(p => p.y_m);
  // Equal metre scales preserve geometry; north is up. No image or decorative path.
  const range = Math.max(Math.max(...xs)-Math.min(...xs), Math.max(...ys)-Math.min(...ys), 100)*1.18;
  const cx = (Math.min(...xs)+Math.max(...xs))/2, cy = (Math.min(...ys)+Math.max(...ys))/2;
  // Uniform viewport scale on both axes (the plot is intentionally wider than its data extent).
  const scale = 300/range;
  const screen = (p: { x_m: number; y_m: number }) => [330+(p.x_m-cx)*scale, 178-(p.y_m-cy)*scale];
  const path = (ps: { x_m: number; y_m: number }[]) => ps.map(p => screen(p).join(",")).join(" ");
  const anchor = screen(model.forecast_anchor), raw = screen(observed[0]);
  return <div className={styles.plotFrame}><svg className={styles.plot} viewBox="0 0 660 370" role="img" aria-labelledby={title}>
    <title id={title}>{group.drifter_id}: six hourly observed positions compared with {model.label}. East is right, north is up; both axes use the same metre scale.</title>
    {[0,1,2,3,4].map(i => <g key={i}><line x1={45+i*142.5} y1="22" x2={45+i*142.5} y2="330" stroke="#dcecf5" /><line x1="45" y1={22+i*77} x2="615" y2={22+i*77} stroke="#dcecf5" /></g>)}
    <polyline points={path(observed)} fill="none" stroke="#2e6b89" strokeWidth="2.7" />
    <polyline points={path(predicted)} fill="none" stroke="#0d88b1" strokeWidth="2.7" strokeDasharray="7 5" />
    {observed.slice(1).map((p,i) => { const [x,y]=screen(p); return <g key={p.time_utc}><circle cx={x} cy={y} r="4" fill="#2e6b89" /><text x={x+7} y={y+12} fontSize="10" fill="#315b73">{i+1}h</text></g>; })}
    {model.predictions.map((p,i) => { const [x,y]=screen(p as KalmanPoint); return <g key={p.time_utc}><circle cx={x} cy={y} r="3.5" fill="#0d88b1" /><text x={x+7} y={y-7} fontSize="10" fill="#17688d">{i+1}h</text></g>; })}
    <circle cx={raw[0]} cy={raw[1]} r="5" fill="#fff" stroke="#2e6b89" strokeWidth="2" />
    <path d={`M${anchor[0]} ${anchor[1]-5}l5 5-5 5-5-5Z`} fill="#b38337" />
    <text x="45" y="354" fontSize="11" fill="#526f83">Equal scale · {fmt(range/3,0)} m per 100 display units</text><text x="615" y="354" textAnchor="end" fontSize="11" fill="#526f83">East → · North ↑</text>
  </svg><div className={styles.legend}><span><i className={styles.key} />Observed buoy</span><span><i className={`${styles.key} ${styles.predictedKey}`} />Free-running forecast · dashed</span><span>◇ Model start · ○ raw last observation</span></div></div>;
}
function Results({ report }: { report: KalmanReport }) {
  const [drifter, setDrifter] = useState(report.groups[0].drifter_id), [modelId, setModelId] = useState("kalman_cv");
  const group=report.groups.find(g=>g.drifter_id===drifter)!, model=group.models.find(m=>m.id===modelId)!;
  const c=report.coverage, hit=report.uncertainty?.per_drifter.find(r=>r.drifter_id===drifter);
  return <div className={styles.stack}>
    <div className={styles.metrics}><div className={styles.metric}><strong>4 / 6</strong><span>Previously viewed NOAA drifters acquired · two target groups missing</span></div><div className={styles.metric}><strong>{c.scored_outcomes} / 180</strong><span>Model-hour scores vs full target · {c.attempted_outcomes} attempted; {c.failed_outcomes} acquired failures</span></div><div className={styles.metric}><strong>24</strong><span>Unique observed intervals · reused across five models, giving 120 attempted outcomes</span></div></div>
    <div className={styles.scope}><strong>Fixed assumptions, not a new independent test</strong><p>Each drifter contributes 18 earlier hourly positions and six later observations. Five models forecast those same six hours without receiving later positions. These already-viewed drifters support a post-hoc comparison only. No winner, confidence calibration, source attribution or physical reef benefit is established.</p></div>
    <div className="table-scroll"><table className="metrics-table"><caption>Five-model study · four acquired drifters · equal-drifter averages</caption><thead><tr><th>Model</th><th>Mean position error / ADE (m)</th><th>Final position error / FDE (m)</th><th>Vector RMSE (m/s)</th><th>Complete drifters</th></tr></thead><tbody>{report.models.map(m=><tr key={m.id} className={m.id===modelId?styles.selected:undefined}><th scope="row">{m.label}</th><td className={styles.tableNumber}>{m.metrics?fmt(m.metrics.ade_m):"Withheld"}</td><td className={styles.tableNumber}>{m.metrics?fmt(m.metrics.fde_m):"Withheld"}</td><td className={styles.tableNumber}>{m.metrics?fmt(m.metrics.vector_rmse_m_s,3):"Withheld"}</td><td>{m.complete_groups}/4</td></tr>)}</tbody></table></div>
    <p className={styles.note}>ADE averages the six great-circle position errors; FDE is the error at hour six. Vector RMSE compares local east/north displacements per second. Common-cohort averages are withheld if any acquired model track fails. These metrics compare buoy motion, not actual plastic interception or coral protection.</p>
    <div className={styles.controls}><label className={styles.select}>Inspect fixed NOAA drifter<select value={drifter} onChange={e=>setDrifter(e.target.value)}>{report.groups.map(g=><option key={g.drifter_id} value={g.drifter_id}>{g.drifter_id} · {g.training_track[0].time_utc.slice(0,10)}</option>)}</select></label><label className={styles.select}>Inspect fixed motion model<select value={modelId} onChange={e=>setModelId(e.target.value)}>{group.models.map(m=><option key={m.id} value={m.id}>{m.label}</option>)}</select></label></div>
    <p className={styles.note}>Forecasts after {group.training_track[17].time_utc} · {model.id==="kalman_cv"?"Kalman starts at its filtered last training state; that position may differ from the raw observation. The diamond shows this model start.":"This baseline starts at the raw last training observation."} Subsequent forecasts begin at their own previous prediction, never the next observed point.</p>
    <Trajectory group={group} model={model} />
    {model.metrics && <div className={styles.metrics}><div className={styles.metric}><strong>{fmt(model.metrics.ade_m)} m</strong><span>Selected drifter’s mean position error</span></div><div className={styles.metric}><strong>{fmt(model.metrics.fde_m)} m</strong><span>Selected drifter’s six-hour final error</span></div><div className={styles.metric}><strong>{fmt(model.metrics.vector_rmse_m_s,3)} m/s</strong><span>Selected drifter’s vector RMSE</span></div></div>}
    <div className={styles.scope}><strong>What the Kalman assumptions mean</strong><p>We assume 100 m position-measurement standard deviation and acceleration spectral density 1×10⁻⁶ m²/s³. These are arbitrary fixed diagnostic values, not fitted sensor accuracy or validated ocean physics. Kalman’s spread comes from these assumptions; comparison to observed positions uses predicted position covariance plus the assumed measurement variance.</p>{hit && <p>For this drifter’s Kalman forecast, {hit.nominal50_hit_count ?? "unavailable"}/{hit.scored_count} positions lie inside the nominal 50% ellipse and {hit.nominal90_hit_count ?? "unavailable"}/{hit.scored_count} inside nominal 90%. These Kalman-only hit counts remain uncalibrated, including when another model is selected above.</p>}</div>
    <details className="details-panel"><summary>All six-hour positions, covariance, fixed parameters and study provenance</summary><ul className="reason-list">{report.limitations.map(v=><li key={v}>{v}</li>)}</ul><pre className="code-block">{JSON.stringify(report,null,2)}</pre></details>
  </div>;
}
function Session({ api }: { api: string }) {
  const [report,setReport]=useState<KalmanReport|null>(null), [loading,setLoading]=useState(false), [error,setError]=useState("");
  const controller=useRef<AbortController|null>(null);
  useEffect(()=>()=>{controller.current?.abort();controller.current=null;},[]);
  async function load() {
    if(controller.current) return;
    const pending=new AbortController();controller.current=pending;
    const timer=window.setTimeout(()=>pending.abort(),30_000);
    setReport(null);setError("");setLoading(true);
    try {
      const response=await fetch(`${api.replace(/\/$/,"")}/api/v1/research/kalman-diagnostic`,{cache:"no-store",signal:pending.signal});
      const result=await readVectorResponse(response,validateKalmanReport,500_000);
      if(controller.current===pending&&!pending.signal.aborted)setReport(result);
    } catch(cause) {
      if(controller.current===pending)setError(pending.signal.aborted?"The fixed Kalman study timed out. No result was accepted.":cause instanceof Error?cause.message:"The fixed study is unavailable.");
    } finally {
      window.clearTimeout(timer);
      if(controller.current===pending){controller.current=null;setLoading(false);}
    }
  }
  return <section className={`card ${styles.card}`} aria-label="Fixed Kalman motion study"><div className={`card-header ${styles.header}`}><div><h2 className="card-title"><Icon name="wave" />A fixed Kalman motion study</h2><p className="card-subtitle">Five transparent motion models · the same four historical NOAA drifters</p></div><button className="primary-button" disabled={loading} onClick={()=>void load()}><Icon name="play" />{loading?"Loading fixed Kalman study…":"Load fixed Kalman study"}</button></div><div className={`card-body ${styles.stack}`}><p className={styles.intro}>Compare a constant-velocity Kalman filter with the existing motion baselines. The study is read-only: it uses saved historical positions and fixed Kalman noise assumptions, makes no provider calls, starts no camera and promotes no model. Mean-drift and ridge baselines learn only from each drifter’s earlier training prefix.</p>{loading&&<p role="status">Checking pinned NOAA evidence and all 120 attempted model-hour outcomes…</p>}{error&&<div className="notice error" role="alert">{error} No automatic retry will occur.</div>}{report&&<Results report={report}/>}</div></section>;
}
export function KalmanDiagnostic({api}:{api:string}) { return <Session key={api} api={api}/>; }
