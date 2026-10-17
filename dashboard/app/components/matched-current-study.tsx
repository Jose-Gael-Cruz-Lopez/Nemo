"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { Icon } from "./icons";
import { useOperator } from "./operator-provider";
import { HelpLabel, PlotSeriesControls } from "./plot-controls";
import { readVectorResponse } from "./vector-diagnostic-state";
import { MATCHED_GROUPS, MATCHED_MODELS, matchedStudyVersion, matchedHourlyDisplacement, matchedPlot, matchedSegments, validateMatchedAnswer, validateMatchedEnvelope, type MatchedAnswer, type MatchedEnvelope, type MatchedModelId, type MatchedPlotPoint, type MatchedStudyVersion } from "./matched-current-state";
import styles from "./matched-current-study.module.css";

type SeriesId = "recorded" | MatchedModelId;
type Visibility = Record<SeriesId, boolean>;
const labels: Record<SeriesId,string> = {recorded:"Recorded buoy",stationary:"Stationary",last_drift:"Last observed drift",current_only:"HYCOM current-only"};
const colors: Record<SeriesId,string> = {recorded:"#2d607a",stationary:"#a68747",last_drift:"#6a81b3",current_only:"#138e9d"};
const initialVisibility: Visibility = {recorded:true,stationary:true,last_drift:true,current_only:true};
const fmt = (value:number|null) => value === null ? "Withheld" : `${value.toLocaleString(undefined,{maximumFractionDigits:1})} m`;
const errorText = (cause:unknown) => cause instanceof Error ? cause.message : "The saved study is unavailable.";

export function MatchedCurrentFigure({envelope,groupId,visible,onToggle,hour,arrows}:{envelope:MatchedEnvelope;groupId:string;visible:Visibility;onToggle:(id:string,checked:boolean)=>void;hour:number;arrows:boolean}) {
  const title=useId(),arrow=useId(),plot=matchedPlot(envelope,groupId);
  if(!plot)return <div className={styles.empty} role="status"><strong>No supported path to draw for this buoy.</strong><p>The saved report has no usable origin or later positions. Missing paths remain missing; no synthetic route is substituted.</p></div>;
  const {domain}=plot,screen=(point:MatchedPlotPoint)=>[330+(point.x_m-domain.centerX)*340/domain.span,208-(point.y_m-domain.centerY)*340/domain.span];
  const polyline=(points:MatchedPlotPoint[])=>points.map(point=>screen(point).join(",")).join(" ");
  const ids=["recorded",...MATCHED_MODELS] as SeriesId[],empty=ids.every(id=>!visible[id]);
  return <figure className={styles.plotFrame}>
    <PlotSeriesControls legend="Show paths" series={ids.map(id=>({id,label:labels[id],explanation:id==="recorded"?"Saved processed NOAA buoy positions. Gaps are not joined.":`${labels[id]} predictions from the frozen origin. Missing hours remain gaps.`,color:colors[id],dashed:id!=="recorded",checked:visible[id]}))} onChange={onToggle}/>
    {empty&&<p className={styles.note} role="status">No trajectories selected. Restore a checkbox to show a path; scale and scores remain fixed.</p>}
    <svg className={styles.plot} viewBox="0 0 660 430" role="img" aria-labelledby={title} data-domain={`${domain.centerX},${domain.centerY},${domain.span}`}>
      <title id={title}>{`GDP ${groupId}: recorded buoy positions and three fixed candidate predictions. Selected hour ${hour}. Solid recorded; dashed predictions. Equal east/north display scale; toggles do not rescale the plot.`}</title>
      <defs>{ids.map(id=><marker id={`${arrow}-${id}`} key={id} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L8 4L0 8Z" fill={colors[id]}/></marker>)}</defs>
      <rect x="160" y="38" width="340" height="340" fill="#f7fbfe" stroke="#d3e5ef"/>
      {[0,1,2,3,4].map(index=><g key={index} stroke="#deebf3"><line x1={160+index*85} y1="38" x2={160+index*85} y2="378"/><line x1="160" y1={38+index*85} x2="500" y2={38+index*85}/></g>)}
      {ids.filter(id=>visible[id]).map(id=><g key={id} data-plot-series={id}>
        {matchedSegments(plot.series[id]).filter(points=>points.length>=2).map((points,index)=><polyline key={index} points={polyline(points)} fill="none" stroke={colors[id]} strokeWidth={id==="recorded"?2.8:2.2} strokeDasharray={id==="recorded"?undefined:"7 5"}/>)}
        {plot.series[id].map((point,index)=>{if(!point)return null;const[x,y]=screen(point);return <circle key={index} cx={x} cy={y} r={point.hour===hour?5:2.5} fill={point.hour===0?"white":colors[id]} stroke={colors[id]} strokeWidth="1.5"><title>{`${labels[id]} · ${point.hour===0?"origin":`hour ${point.hour}`} · ${point.time_utc} · ${point.latitude_deg.toFixed(5)}°, ${point.longitude_deg.toFixed(5)}°`}</title></circle>;})}
        {arrows&&(()=>{const pair=matchedHourlyDisplacement(plot.series[id],hour);if(!pair)return null;const[from,to]=pair,[x1,y1]=screen(from),[x2,y2]=screen(to);return <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={colors[id]} strokeWidth="2.3" markerEnd={`url(#${arrow}-${id})`}><title>{`${labels[id]} hourly displacement ${hour-1}→${hour}. Difference between saved hourly positions; not a native current sample.`}</title></line>;})()}
      </g>)}
      <text x="26" y="405" fontSize="11" fill="#526f83">Grid: {(domain.span/4).toLocaleString(undefined,{maximumFractionDigits:0})} display metres</text><text x="630" y="405" textAnchor="end" fontSize="11" fill="#526f83">East → · North ↑</text>
    </svg>
    <figcaption className={styles.note}>Only saved hourly endpoints are shown. Lines join adjacent available hours; gaps stay open. This local display projection does not calculate the report’s great-circle errors.{arrows&&" Arrows show adjacent-hour displacement estimates, not native HYCOM currents."}{!plot.originAvailable&&" The forecast origin is unavailable; the display is centred on the first available recorded point."}</figcaption>
  </figure>;
}

function MatchedChalk({api,envelope,token}:{api:string;envelope:MatchedEnvelope;token:string}) {
  const [question,setQuestion]=useState("Explain whether the matched current field describes the saved buoy motion better than the two baselines, retain every missing outcome, and state the next independent measurement needed.");
  const [answer,setAnswer]=useState<MatchedAnswer|null>(null),[loading,setLoading]=useState(false),[error,setError]=useState("");
  const controller=useRef<AbortController|null>(null);
  useEffect(()=>()=>{controller.current?.abort();controller.current=null;},[]);
  async function ask(){
    if(controller.current||!token||!question.trim()||question.trim().length>2000)return;
    const pending=new AbortController();controller.current=pending;const timer=window.setTimeout(()=>pending.abort(),90_000);setAnswer(null);setError("");setLoading(true);
    try{
      const response=await fetch(`${api.replace(/\/$/,"")}/api/v1/research/matched-current/investigate`,{method:"POST",cache:"no-store",headers:{"Content-Type":"application/json",Authorization:`Bearer ${token}`},body:JSON.stringify({question:question.trim(),study_version:matchedStudyVersion(envelope.report.study_id),report_sha256:envelope.artifact_identity.report_sha256,protocol_sha256:envelope.artifact_identity.protocol_sha256}),signal:pending.signal});
      const result=await readVectorResponse(response,value=>validateMatchedAnswer(value,envelope),5_000_000);
      if(controller.current===pending&&!pending.signal.aborted)setAnswer(result);
    }catch(cause){if(controller.current===pending)setError(pending.signal.aborted?"The bounded Chalk review timed out. The saved report remains available.":errorText(cause));}
    finally{window.clearTimeout(timer);if(controller.current===pending){controller.current=null;setLoading(false);}}
  }
  return <section className={styles.chalk} aria-label="Ask Chalk about matched-current evidence"><h3>What does this comparison support?</h3><p className={styles.note}>Chalk reads this report and its protocol. It explains the evidence without acquiring data, rerunning models, changing a case or sending messages.</p><details className="details-panel"><summary>Change the research question</summary><label className={styles.label}>Question<textarea rows={3} maxLength={2000} value={question} disabled={loading} onChange={event=>setQuestion(event.target.value)}/></label></details><button className="primary-button" disabled={!token||loading||!question.trim()} onClick={()=>void ask()}><Icon name="agent"/>{loading?"Reviewing the frozen evidence…":"Ask Chalk about matched currents"}</button>{!token&&<p className={styles.note}><Link href="/login" className="card-link">Connect local operator access</Link> to request a live review.</p>}{loading&&<p role="status" className={styles.note}>One evidence read and a bounded model discussion. Saved calculations remain authoritative.</p>}{error&&<p className="notice error" role="alert">{error} No automatic retry will occur.</p>}{answer&&<div className={styles.answer} role="status"><span className="pill">{answer.action} · {answer.live_model_response?"Live Chalk response":"No live model response"}</span><p>{answer.explanation}</p>{answer.failure_code&&<p className={styles.note}>Review unavailable: {answer.failure_code}{answer.provider_status_code?` · HTTP ${answer.provider_status_code}`:""}.</p>}<details className="details-panel"><summary>Exact citations and read-only trace</summary><ul>{answer.evidence_ids.map(id=><li className={styles.identity} key={id}>{id}</li>)}</ul><pre className="code-block">{JSON.stringify(answer.trace,null,2)}</pre></details></div>}</section>;
}

export function MatchedCurrentResults({api,envelope}:{api:string;envelope:MatchedEnvelope}) {
  const {token}=useOperator(),[groupId,setGroupId]=useState<string>(MATCHED_GROUPS[0]),[visible,setVisible]=useState<Visibility>(initialVisibility),[hour,setHour]=useState(6),[arrows,setArrows]=useState(false);
  const s=envelope.report.scores,group=s.groups.find(item=>item.group_id===groupId)!,complete=s.primary_common_cohort_complete;
  return <div className={styles.stack}>
    <p className={styles.note}>{matchedStudyVersion(envelope.report.study_id)==="v2"?"v2 compatibility amendment · same buoy groups and models. Frozen before new GDP outcomes, after the v1 forcing was decoded for diagnosis. The v1 failure remains available in the version selector.":"v1 original attempt · preserved without rewriting its inputs, predictions or failures."}</p>
    <div className={styles.summary}><strong>{complete?"A complete historical comparison is available.":"The comparison is incomplete; no overall model ranking is supported."}</strong><p>{s.scored_cell_count} / 36 scored model-hour cells · 2 planned buoy groups · 12 distinct later positions planned</p></div>
    <div className="table-scroll"><table className="metrics-table"><caption>All declared groups · primary comparison withheld unless every model-hour cell scores</caption><thead><tr><th>Fixed candidate</th><th>Coverage</th><th><HelpLabel label="Average miss" explanation="Equal-buoy average of each six-hour ADE, only when the complete shared cohort is available."/></th><th><HelpLabel label="Miss at 6h" explanation="Equal-buoy final position error. It is withheld here unless the full shared cohort is available."/></th></tr></thead><tbody>{s.models.map(model=>{const primary=s.primary_equal_id_macro_results?.find(row=>row.model_id===model.model_id);return <tr key={model.model_id}><th scope="row">{labels[model.model_id]}</th><td>{model.metrics.scored_count} / 12</td><td>{fmt(primary?.equal_id_macro_ade_m??null)}</td><td>{fmt(primary?.equal_id_macro_fde_m??null)}</td></tr>;})}</tbody></table></div>
    <div className={styles.controls}><label className={styles.label}>Buoy group<select value={groupId} onChange={event=>setGroupId(event.target.value)}>{MATCHED_GROUPS.map(id=><option key={id} value={id}>GDP {id}</option>)}</select></label><label className={styles.label}>Inspect saved hour<select value={hour} onChange={event=>setHour(Number(event.target.value))}>{[1,2,3,4,5,6].map(value=><option key={value} value={value}>{value}h · {String(value).padStart(2,"0")}:00 UTC</option>)}</select></label><label className={styles.checkbox}><input type="checkbox" checked={arrows} onChange={event=>setArrows(event.target.checked)}/>Hourly displacement arrows</label></div>
    <MatchedCurrentFigure envelope={envelope} groupId={groupId} visible={visible} onToggle={(id,checked)=>setVisible(previous=>({...previous,[id]:checked}))} hour={hour} arrows={arrows}/>
    <p className={styles.note}>Retrospective NOAA buoy motion and HYCOM analysis at 15 m. This does not establish operational forecast skill, observed plastic motion, reef protection or tank accuracy.</p>
    <MatchedChalk key={`${api}:${envelope.artifact_identity.report_sha256}:${token}`} api={api} envelope={envelope} token={token}/>
    <details className="details-panel"><summary>Coverage, missing paths and scientific lineage</summary><div className={styles.stack}>
      <p className={styles.note}>Every group, candidate and later hour remains in the planned denominator. The 36 model-hour cells reuse only 12 distinct processed NOAA position estimates; these are not independent observations. Reader verification checks pinned artifacts and their structure, rather than rerunning the numerical calculation.</p>
      <div className="table-scroll"><table className="metrics-table"><caption>Selected GDP group · complete six-hour scores and available prefixes remain distinct</caption><thead><tr><th>Candidate</th><th>Prediction status</th><th>Scored hours</th><th>Full 6h ADE</th><th>Available-cell mean</th></tr></thead><tbody>{group.candidates.map(model=><tr key={model.model_id}><th scope="row">{labels[model.model_id]}</th><td>{model.prediction_status}<br/><small>{model.prediction_reason_code??"All six predictions available"}</small></td><td>{model.metrics.scored_count}/6</td><td>{fmt(model.metrics.full_horizon_ade_m)}</td><td>{fmt(model.metrics.available_cell_mean_error_m)}{model.metrics.scored_count<6?" · incomplete":""}</td></tr>)}</tbody></table></div>
      <div className="table-scroll"><table className="metrics-table"><caption>Secondary comparisons use only explicitly common available cells; they are not the full-cohort result</caption><thead><tr><th>Paired candidates</th><th>Common cells</th><th>Stored mean miss A / B</th></tr></thead><tbody>{s.paired_comparisons.map(pair=><tr key={`${pair.model_a}:${pair.model_b}`}><th>{labels[pair.model_a]} / {labels[pair.model_b]}</th><td>{pair.common_scored_count}/12</td><td>{fmt(pair.mean_error_a_m)} / {fmt(pair.mean_error_b_m)}</td></tr>)}</tbody></table></div>
      {envelope.report.current_field_failure&&<p className={styles.note}>Current-field limitation: {envelope.report.current_field_failure}</p>}
      <ul className="reason-list">{s.limitations.map(limit=><li key={limit}>{limit}</li>)}</ul>
      <p className={styles.identity}>Report <code>{envelope.artifact_identity.report_sha256}</code><br/>Protocol <code>{envelope.artifact_identity.protocol_sha256}</code></p>
      <details className="details-panel"><summary>All saved evidence, receipts, positions and common-cell identities</summary><pre className="code-block">{JSON.stringify(envelope,null,2)}</pre></details>
    </div></details>
  </div>;
}

function Session({api,studyVersion}:{api:string;studyVersion:MatchedStudyVersion}) {
  const [envelope,setEnvelope]=useState<MatchedEnvelope|null>(null),[loading,setLoading]=useState(false),[error,setError]=useState("");
  const controller=useRef<AbortController|null>(null);
  useEffect(()=>()=>{controller.current?.abort();controller.current=null;},[]);
  async function load(){
    if(controller.current)return;
    const pending=new AbortController();controller.current=pending;const timer=window.setTimeout(()=>pending.abort(),30_000);setEnvelope(null);setError("");setLoading(true);
    try{const response=await fetch(`${api.replace(/\/$/,"")}/api/v1/research/matched-current?study_version=${studyVersion}`,{cache:"no-store",signal:pending.signal});const result=await readVectorResponse(response,value=>validateMatchedEnvelope(value,studyVersion),5_000_000);if(controller.current===pending&&!pending.signal.aborted)setEnvelope(result);}
    catch(cause){if(controller.current===pending)setError(pending.signal.aborted?"The frozen study read timed out; no result was accepted.":errorText(cause));}
    finally{window.clearTimeout(timer);if(controller.current===pending){controller.current=null;setLoading(false);}}
  }
  return <section className="card" aria-label="Matched current and real buoy study"><div className={`card-header ${styles.header}`}><div><h2 className="card-title">Do matched currents explain the buoy’s motion?</h2><p className="card-subtitle">{studyVersion==="v2"?"v2 compatibility amendment":"v1 original attempt"} · two GDP groups · three candidates · six later hours</p></div><button className="secondary-button" disabled={loading} onClick={()=>void load()}><Icon name="play"/>{loading?"Reading saved evidence…":"Load matched-current study"}</button></div><div className={`card-body ${styles.stack}`}>{!envelope&&!loading&&!error&&<p className={styles.note}>Inspect a separately frozen historical comparison, including failed acquisitions and missing paths. Loading this card never acquires data or performs a first score.</p>}{loading&&<p role="status" className={styles.note}>Reading the pinned result, protocol and all planned outcome slots…</p>}{error&&<div className="notice error" role="alert">{error} No fallback dataset or automatic retry will be used.</div>}{envelope&&<MatchedCurrentResults key={envelope.artifact_identity.report_sha256} api={api} envelope={envelope}/>}</div></section>;
}
export function MatchedCurrentStudy({api}:{api:string}){
  const [studyVersion,setStudyVersion]=useState<MatchedStudyVersion>("v2");
  return <div className={styles.stack}>
    <label className={styles.label}>Study version<select value={studyVersion} onChange={event=>setStudyVersion(event.target.value as MatchedStudyVersion)}><option value="v2">v2 · compatibility amendment</option><option value="v1">v1 · preserved original attempt</option></select></label>
    <Session key={`${api}:${studyVersion}`} api={api} studyVersion={studyVersion}/>
  </div>;
}
