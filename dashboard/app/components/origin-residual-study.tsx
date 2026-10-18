"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { Icon } from "./icons";
import { useOperator } from "./operator-provider";
import { HelpLabel, PlotSeriesControls } from "./plot-controls";
import { readVectorResponse } from "./vector-diagnostic-state";
import { ORIGIN_GROUPS, ORIGIN_MODELS, createOriginRequestGate, originDisplacement, originPlot, originQuestion, originSegments, validateOriginAnswer, validateOriginEnvelope, type OriginAnswer, type OriginEnvelope, type OriginPlotPoint, type OriginSeriesId } from "./origin-residual-state";
import styles from "./matched-current-study.module.css";

export type OriginVisibility = Record<OriginSeriesId,boolean>;
const labels: Record<OriginSeriesId,string> = {recorded:"Recorded buoy",stationary:"Stationary",last_drift:"Last observed drift",current_only:"HYCOM current-only",origin_residual_current:"HYCOM + initial drift offset"};
const colors: Record<OriginSeriesId,string> = {recorded:"#2d607a",stationary:"#a68747",last_drift:"#6a81b3",current_only:"#138e9d",origin_residual_current:"#8d609c"};
const initialVisibility: OriginVisibility = {recorded:true,stationary:true,last_drift:true,current_only:true,origin_residual_current:true};
const fmt = (value: number | null) => value === null ? "Withheld" : `${value.toLocaleString(undefined,{maximumFractionDigits:1})} m`;
const errorText = (cause: unknown) => cause instanceof Error ? cause.message : "The saved exploratory result is unavailable.";
function useRequests() {
  const requests = useRef<ReturnType<typeof createOriginRequestGate> | null>(null);
  useEffect(() => {
    const gate = createOriginRequestGate(); requests.current = gate;
    return () => { gate.dispose(); if (requests.current === gate) requests.current = null; };
  }, []);
  return requests;
}

export function OriginResidualFigure({envelope,groupId,visible,onToggle,hour,arrows}: {envelope:OriginEnvelope;groupId:string;visible:OriginVisibility;onToggle:(id:string,checked:boolean)=>void;hour:number;arrows:boolean}) {
  const title = useId(), arrow = useId(), plot = originPlot(envelope,groupId);
  if (!plot) return <div className={styles.empty} role="status"><strong>No supported positions to draw for this group.</strong><p>Unavailable paths remain missing. No replacement trajectory is generated.</p></div>;
  const {domain} = plot, screen = (point:OriginPlotPoint) => [(330+(point.x_m-domain.centerX)*340/domain.span).toFixed(3),(208-(point.y_m-domain.centerY)*340/domain.span).toFixed(3)];
  const ids = ["recorded",...ORIGIN_MODELS] as OriginSeriesId[];
  return <figure className={styles.plotFrame}>
    <PlotSeriesControls legend="Show saved paths" series={ids.map(id => ({id,label:labels[id],explanation:id === "recorded" ? "Processed NOAA buoy positions already viewed in the earlier study; missing hours stay open." : `${labels[id]} saved hourly predictions. This checkbox changes the drawing, not scores or model selection.`,color:colors[id],dashed:id !== "recorded",checked:visible[id]}))} onChange={onToggle}/>
    {ids.every(id => !visible[id]) && <p className={styles.note} role="status">No paths selected. Restore a checkbox; axes and scores remain fixed.</p>}
    <svg className={styles.plot} viewBox="0 0 660 430" role="img" aria-labelledby={title} data-domain={`${domain.centerX},${domain.centerY},${domain.span}`}>
      <title id={title}>{`GDP ${groupId}: already-viewed recorded positions and four saved predictions. Selected hour ${hour}. Equal east/north scale; visibility does not rescale or change scores.`}</title>
      <defs>{ids.map(id => <marker id={`${arrow}-${id}`} key={id} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L8 4L0 8Z" fill={colors[id]}/></marker>)}</defs>
      <rect x="160" y="38" width="340" height="340" fill="#f7fbfe" stroke="#d3e5ef"/>
      {[0,1,2,3,4].map(index => <g key={index} stroke="#deebf3"><line x1={160+index*85} y1="38" x2={160+index*85} y2="378"/><line x1="160" y1={38+index*85} x2="500" y2={38+index*85}/></g>)}
      {ids.filter(id => visible[id]).map(id => <g key={id} data-origin-series={id}>
        {originSegments(plot.series[id]).filter(points => points.length >= 2).map((points,index) => <polyline key={index} points={points.map(point => screen(point).join(",")).join(" ")} fill="none" stroke={colors[id]} strokeWidth={id === "recorded" ? 2.8 : 2.2} strokeDasharray={id === "recorded" ? undefined : "7 5"}/>)}
        {plot.series[id].map((point,index) => { if (!point) return null; const [x,y] = screen(point); return <circle key={index} cx={x} cy={y} r={point.hour === hour ? 5 : 2.5} fill={point.hour === 0 ? "white" : colors[id]} stroke={colors[id]} strokeWidth="1.5"><title>{`${labels[id]} · ${point.hour === 0 ? "origin" : `hour ${point.hour}`} · ${point.time_utc} · ${point.latitude_deg.toFixed(5)}°, ${point.longitude_deg.toFixed(5)}°`}</title></circle>; })}
        {arrows && (() => { const pair = originDisplacement(plot.series[id],hour); if (!pair) return null; const [from,to] = pair, [x1,y1] = screen(from), [x2,y2] = screen(to); return <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={colors[id]} strokeWidth="2.3" markerEnd={`url(#${arrow}-${id})`}><title>{`${labels[id]} adjacent-endpoint displacement ${hour-1}→${hour}. Difference between saved positions, not native water currents.`}</title></line>; })()}
      </g>)}
      <text x="26" y="405" fontSize="11" fill="#526f83">Grid: {(domain.span/4).toLocaleString(undefined,{maximumFractionDigits:0})} display metres</text><text x="630" y="405" textAnchor="end" fontSize="11" fill="#526f83">East → · North ↑</text>
    </svg>
    <figcaption className={styles.note}>Solid recorded positions; dashed predictions. Lines connect adjacent saved hours and leave gaps open. This display projection does not calculate the stored great-circle errors.{arrows && " Arrows are adjacent-endpoint displacements, not sampled water-current vectors."}{!plot.originAvailable && " The origin is missing; the display is centred on the first available saved position."}</figcaption>
  </figure>;
}

export function OriginResidualReview({api,envelope,token}: {api:string;envelope:OriginEnvelope;token:string}) {
  const [question,setQuestion] = useState("Explain what this post-outcome initial drift offset comparison supports, what remains unverified, and the next independent measurement needed. Keep descriptive results separate from unseen-data skill.");
  const [answer,setAnswer] = useState<OriginAnswer | null>(null), [loading,setLoading] = useState(false), [error,setError] = useState("");
  const requests = useRequests();
  async function ask() {
    if (!token || !question.trim() || question.trim().length > 2000) return;
    const gate = requests.current, pending = gate?.begin(); if (!gate || !pending) return;
    const timer = window.setTimeout(() => pending.controller.abort(),90_000);
    pending.controller.signal.addEventListener("abort",() => window.clearTimeout(timer),{once:true});
    setAnswer(null); setError(""); setLoading(true);
    try {
      const response = await fetch(`${api.replace(/\/$/,"")}/api/v1/research/origin-residual/investigate`,{method:"POST",cache:"no-store",headers:{"Content-Type":"application/json",Authorization:`Bearer ${token}`},body:JSON.stringify(originQuestion(question,envelope)),signal:pending.controller.signal});
      const result = await readVectorResponse(response,value => validateOriginAnswer(value,envelope),5_000_000);
      if (gate.current(pending)) setAnswer(result);
    } catch (cause) { if (gate.owns(pending)) setError(pending.controller.signal.aborted ? "The bounded Chalk review timed out. The saved result remains available." : errorText(cause)); }
    finally { window.clearTimeout(timer); if (gate.owns(pending)) { gate.finish(pending); setLoading(false); } }
  }
  return <section className={styles.chalk} aria-label="Ask Chalk about the origin residual diagnostic"><h3>What does this result mean?</h3><p className={styles.note}>Chalk reads this exact saved report and protocol. It cannot change models, acquire data, run experiments or send messages.</p>
    <details className="details-panel"><summary>Change the research question</summary><label className={styles.label}>Question<textarea rows={3} maxLength={2000} value={question} disabled={loading} onChange={event => setQuestion(event.target.value)}/></label></details>
    <button type="button" className="primary-button" disabled={!token || loading || !question.trim()} onClick={() => void ask()}><Icon name="agent"/>{loading ? "Reviewing saved evidence…" : "Ask Chalk about the drift offset"}</button>
    {!token && <p className={styles.note}><Link href="/login" className="card-link">Connect local operator access</Link> to request a live review.</p>}
    {loading && <p role="status" className={styles.note}>One read-only evidence tool and at most two bounded model calls.</p>}
    {error && <p className="notice error" role="alert">{error} No automatic retry will occur.</p>}
    {answer && <div className={styles.answer} role="status"><span className="pill">{answer.action} · {answer.live_model_response ? "Live Chalk response" : "No live model response"}</span><p>{answer.explanation}</p>{answer.failure_code && <p className={styles.note}>Review unavailable: {answer.failure_code}{answer.provider_status_code ? ` · HTTP ${answer.provider_status_code}` : ""}. Saved numerical evidence remains available.</p>}<details className="details-panel"><summary>Exact citations and read-only trace</summary><ul>{answer.evidence_ids.map(id => <li className={styles.identity} key={id}>{id}</li>)}</ul><pre className="code-block">{JSON.stringify(answer.trace,null,2)}</pre></details></div>}
  </section>;
}

export function OriginResidualResults({api,envelope,token}: {api:string;envelope:OriginEnvelope;token:string}) {
  const [groupId,setGroupId] = useState<string>(ORIGIN_GROUPS[0]), [visible,setVisible] = useState<OriginVisibility>(initialVisibility), [hour,setHour] = useState(6), [arrows,setArrows] = useState(false);
  const scores = envelope.report.scores, group = scores.groups.find(group => group.group_id === groupId)!;
  return <div className={styles.stack}>
    <div className={styles.summary}><strong>Exploratory development · outcomes already viewed</strong><p>{scores.scored_cell_count} / 48 scored model-hour cells · 12 reused processed NOAA positions · 2 buoy groups</p><p>{scores.primary_common_cohort_complete ? "Descriptive comparison only; this is not a new holdout or an operational model recommendation." : "Incomplete shared cohort. Primary ADE and FDE are withheld; missing cells remain in the denominator."}</p><p>This tests later movement, not where pollution was released. Source tracing remains in Investigations.</p></div>
    <div className="table-scroll"><table className="metrics-table"><caption>Saved equal-buoy results · primary comparison requires all 48 cells</caption><thead><tr><th>Fixed candidate</th><th>Coverage</th><th><HelpLabel label="Average miss (ADE)" explanation="Stored equal-ID average of the two groups’ complete six-hour position errors. Lower is descriptive here; it does not establish independent skill."/></th><th><HelpLabel label="Miss at 6h (FDE)" explanation="Stored equal-ID average of final position errors. The primary table is withheld if the shared cohort is incomplete."/></th></tr></thead><tbody>{scores.models.map(model => { const primary = scores.primary_equal_id_macro_results?.find(row => row.model_id === model.model_id); return <tr key={model.model_id}><th scope="row">{labels[model.model_id]}</th><td>{model.metrics.scored_count} / 12</td><td>{fmt(primary?.equal_id_macro_ade_m ?? null)}</td><td>{fmt(primary?.equal_id_macro_fde_m ?? null)}</td></tr>; })}</tbody></table></div>
    <div className={styles.controls}><label className={styles.label}>Buoy group<select value={groupId} onChange={event => setGroupId(event.target.value)}>{ORIGIN_GROUPS.map(id => <option key={id} value={id}>GDP {id}</option>)}</select></label><label className={styles.label}>Inspect saved hour<select value={hour} onChange={event => setHour(Number(event.target.value))}>{[1,2,3,4,5,6].map(value => <option key={value} value={value}>{value}h · {String(value).padStart(2,"0")}:00 UTC</option>)}</select></label><label className={styles.checkbox}><input type="checkbox" checked={arrows} onChange={event => setArrows(event.target.checked)}/>Adjacent-endpoint displacement arrows</label></div>
    <OriginResidualFigure envelope={envelope} groupId={groupId} visible={visible} hour={hour} arrows={arrows} onToggle={(id,checked) => setVisible(previous => ({...previous,[id]:checked}))}/>
    <p className={styles.note}>HYCOM retrospective analysis at 15 m and processed NOAA buoy motion. Plastic behaviour, tank accuracy, reef protection and operational forecast skill remain unverified.</p>
    <OriginResidualReview key={`${api}:${token}:${envelope.artifact_identity.identity_sha256}:${envelope.artifact_identity.report_sha256}`} api={api} envelope={envelope} token={token}/>
    <details className="details-panel"><summary>Method, missing outcomes and provenance</summary><div className={styles.stack}>
      <p className={styles.note}>The initial offset is the last observed drift minus the HYCOM current at the forecast start. That same east/north offset is added throughout the changing field; RK4 samples the field several times in each short step. Here “origin” means the forecast start, not an estimated pollution source. It is unfitted kinematics, not an identified windage coefficient.</p>
      <p className={styles.note}>This candidate was designed after these outcomes were viewed. The earlier v2 study stays unchanged, and no active model is promoted. The backend checks saved bytes and lineage against a committed identity; this browser applies display guards. That code anchor is not independent scientific attestation or a new numerical replay.</p>
      <div className="table-scroll"><table className="metrics-table"><caption>Selected group · available means stay separate from complete-horizon ADE</caption><thead><tr><th>Candidate</th><th>Prediction</th><th>Scored hours</th><th>Full 6h ADE</th><th>Available-cell mean</th><th>Endpoint FDE</th></tr></thead><tbody>{group.candidates.map(row => <tr key={row.model_id}><th scope="row">{labels[row.model_id]}</th><td>{row.prediction_status}<br/><small>{row.prediction_reason_code}</small></td><td>{row.metrics.scored_count}/6</td><td>{fmt(row.metrics.full_horizon_ade_m)}</td><td>{fmt(row.metrics.available_cell_mean_error_m)}</td><td>{fmt(row.metrics.endpoint_fde_m)}</td></tr>)}</tbody></table></div>
      <ul className="reason-list">{scores.limitations.map(text => <li key={text}>{text}</li>)}</ul><p className={styles.identity}>Report <code>{envelope.artifact_identity.report_sha256}</code><br/>Protocol <code>{envelope.artifact_identity.protocol_sha256}</code><br/>Identity <code>{envelope.artifact_identity.identity_sha256}</code></p>
      <details className="details-panel"><summary>Full saved evidence, forecasts and lineage</summary><pre className="code-block">{JSON.stringify(envelope,null,2)}</pre></details>
    </div></details>
  </div>;
}

function Session({api,token}: {api:string;token:string}) {
  const [envelope,setEnvelope] = useState<OriginEnvelope | null>(null), [loading,setLoading] = useState(false), [error,setError] = useState("");
  const requests = useRequests();
  async function load() {
    const gate = requests.current, pending = gate?.begin(); if (!gate || !pending) return;
    const timer = window.setTimeout(() => pending.controller.abort(),30_000); setEnvelope(null); setError(""); setLoading(true);
    pending.controller.signal.addEventListener("abort",() => window.clearTimeout(timer),{once:true});
    try {
      const response = await fetch(`${api.replace(/\/$/,"")}/api/v1/research/origin-residual`,{cache:"no-store",signal:pending.controller.signal});
      const result = await readVectorResponse(response,validateOriginEnvelope,5_000_000);
      if (gate.current(pending)) setEnvelope(result);
    } catch (cause) { if (gate.owns(pending)) setError(pending.controller.signal.aborted ? "The saved result read timed out. No result was accepted." : errorText(cause)); }
    finally { window.clearTimeout(timer); if (gate.owns(pending)) { gate.finish(pending); setLoading(false); } }
  }
  return <section className="card" aria-label="Exploratory initial drift offset study"><div className={`card-header ${styles.header}`}><div><h2 className="card-title">What does an initial drift offset change?</h2><p className="card-subtitle">Four fixed candidates · two historical buoy groups · post-outcome exploration</p></div><button type="button" className="secondary-button" disabled={loading} onClick={() => void load()}><Icon name="play"/>{loading ? "Reading saved evidence…" : error ? "Retry saved drift-offset study" : "Load drift-offset study"}</button></div><div className={`card-body ${styles.stack}`}>
    {!envelope && !loading && !error && <p className={styles.note}>Inspect a saved adjustment to changing HYCOM currents using already-viewed NOAA positions. Loading reads frozen evidence; it does not acquire data or score a new experiment.</p>}
    {loading && <p role="status" className={styles.note}>Reading the pinned exploratory report, forecasts and identity…</p>}
    {error && <p className="notice error" role="alert">{error} Use the button to retry; no fallback dataset or automatic request is used.</p>}
    {envelope && <OriginResidualResults key={`${envelope.artifact_identity.identity_sha256}:${envelope.artifact_identity.report_sha256}`} api={api} envelope={envelope} token={token}/>}
    </div></section>;
}
export function OriginResidualStudy({api}: {api:string}) {
  const {token} = useOperator();
  return <Session key={`${api}:${token}`} api={api} token={token}/>;
}
