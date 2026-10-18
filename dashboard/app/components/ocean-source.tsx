"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { Icon } from "./icons";
import { useOperator } from "./operator-provider";
import { HelpLabel, PlotSeriesControls } from "./plot-controls";
import { readVectorResponse } from "./vector-diagnostic-state";
import { createOceanPipelinePlayback, createOceanSourceRequests, OCEAN_SOURCE_GROUPS, OCEAN_SOURCE_LOOKBACKS, oceanPipelinePlot, oceanSourcePlot, oceanSourceQuestion, oceanSourceSegments, validateOceanSourceAnswer, validateOceanSourceEnvelope, type OceanPipeline, type OceanSourceAnswer, type OceanSourceEnvelope, type OceanSourceModel, type OceanSourcePlotPoint } from "./ocean-source-state";
import styles from "./ocean-source.module.css";

export type OceanSourceVisibility = { nominal: boolean; scenarios: boolean; candidates: boolean };
const modelLabels: Record<OceanSourceModel,string> = { stationary:"Stationary endpoint", last_drift:"Last observed drift reversed", reverse_current:"Changing-current reverse trajectory" };
const modelColors: Record<OceanSourceModel,string> = { stationary:"#a68a55", last_drift:"#8970a3", reverse_current:"#087fac" };
const metres = (value: number | null) => value === null ? "Unavailable" : `${value.toLocaleString(undefined,{maximumFractionDigits:1})} m`;
const errorText = (cause: unknown) => cause instanceof Error ? cause.message : "The saved ocean earlier-position result is unavailable.";

function useRequests() {
  const requests = useRef<ReturnType<typeof createOceanSourceRequests> | null>(null);
  useEffect(() => {
    const gate = createOceanSourceRequests(); requests.current = gate;
    return () => { gate.dispose(); if (requests.current === gate) requests.current = null; };
  },[]);
  return requests;
}

export function OceanSourceFigure({envelope,groupId,lookback,visible,onToggle,showValidation}: {envelope:OceanSourceEnvelope;groupId:string;lookback:number;visible:OceanSourceVisibility;onToggle:(id:string,checked:boolean)=>void;showValidation:boolean}) {
  const title = useId(), arrow = useId(), plot = oceanSourcePlot(envelope,groupId);
  if (!plot) return <p className={styles.empty} role="status">No supported positions for this group. No replacement path was generated.</p>;
  const group = envelope.report.forecasts.groups.find(row => row.group_id === groupId)!;
  const {domain} = plot, size = 360;
  const screen = (point:OceanSourcePlotPoint) => [(340+(point.x_m-domain.centerX)*size/domain.span).toFixed(3),(210-(point.y_m-domain.centerY)*size/domain.span).toFixed(3)];
  const paths = plot.scenarios.filter(row => row.scenario_id === group.reverse_current.nominal_scenario_id ? visible.nominal : visible.scenarios);
  const candidates = plot.earlier.find(row => row.lookback_hours === lookback)?.points ?? [];
  const [observedX,observedY] = screen(plot.observation), validationTarget = plot.validation.find(row => row.target_point)?.target_point;
  return <figure className={styles.figure}>
    <PlotSeriesControls legend="Show earlier-position layers" series={[
      {id:"nominal",label:"Nominal reverse path",explanation:"Current-only model run backward in physical time. It is not a recovered measured journey.",color:"#087fac",checked:visible.nominal},
      {id:"scenarios",label:"Assumption paths",explanation:"Declared endpoint and current perturbations. These cases are not independent trials or a calibrated confidence region.",color:"#8eb1c8",checked:visible.scenarios},
      {id:"candidates",label:"Earlier candidate points",explanation:"Supported scenario positions at the selected known lookback. Missing candidates remain absent from the drawing and present in coverage counts.",color:"#88729b",checked:visible.candidates},
    ]} onChange={onToggle}/>
    {!visible.nominal && !visible.scenarios && !visible.candidates && <p className={styles.caption} role="status">Model layers are hidden. The observed endpoint, axes and stored results remain unchanged.</p>}
    <svg className={styles.plot} viewBox="0 0 680 450" role="img" aria-labelledby={title} data-domain={`${domain.centerX},${domain.centerY},${domain.span}`}>
      <title id={title}>{`GDP ${groupId}: observed endpoint at 06:00 UTC and conditional earlier locations at ${lookback} hours lookback. Equal east/north display scale, fixed across layer toggles. ${showValidation ? "Earlier-position validation is shown separately." : "Earlier-position validation is hidden."}`}</title>
      <defs><marker id={arrow} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L8 4L0 8Z" fill="#087fac"/></marker></defs>
      <rect x="160" y="30" width={size} height={size} fill="#f5fbfe" stroke="#c9dfe9"/>
      {[0,1,2,3,4].map(index => <g key={index} stroke="#d9e9f2"><line x1={160+index*90} x2={160+index*90} y1="30" y2="390"/><line x1="160" x2="520" y1={30+index*90} y2={30+index*90}/></g>)}
      {paths.map(row => { const nominal = row.scenario_id === group.reverse_current.nominal_scenario_id; return <g key={row.scenario_id} data-ocean-source-layer={nominal ? "nominal" : "scenarios"}>
        {oceanSourceSegments(row.points.filter(point => (point.lookback_s ?? 0) <= lookback*3600)).filter(segment => segment.length > 1).map((segment,index) => <polyline key={index} points={segment.map(point => screen(point).join(",")).join(" ")} fill="none" stroke={nominal ? "#087fac" : "#7eabc2"} strokeWidth={nominal ? 2.7 : 1.2} opacity={nominal ? 1 : 0.48} strokeDasharray={nominal ? undefined : "3 3"} markerEnd={nominal ? `url(#${arrow})` : undefined}><title>{`${row.scenario_id} · descending physical time · stops at the last supported saved point`}</title></polyline>)}
      </g>; })}
      {visible.candidates && <g data-ocean-source-layer="candidates">{candidates.map(point => { const [x,y] = screen(point); return <circle key={point.scenario_id} cx={x} cy={y} r="3" fill="#88729b" fillOpacity="0.75"><title>{`${point.scenario_id} · ${lookback}h earlier · ${point.latitude_deg.toFixed(5)}°, ${point.longitude_deg.toFixed(5)}°`}</title></circle>; })}</g>}
      {showValidation && <g data-ocean-source-layer="validation">
        {plot.validation.map(row => { if (!row.prediction_point) return null; const [x,y] = screen(row.prediction_point); return <rect key={row.model_id} x={Number(x)-4} y={Number(y)-4} width="8" height="8" fill="white" stroke={modelColors[row.model_id]} strokeWidth="1.8"><title>{`${modelLabels[row.model_id]} · six-hour reconstruction · ${metres(row.error_m)} stored error`}</title></rect>; })}
        {validationTarget && (() => { const [x,y] = screen(validationTarget); return <g data-validation-truth="true" stroke="#ba6e27" strokeWidth="2.5"><path d={`M${Number(x)-6} ${y}h12M${x} ${Number(y)-6}v12`}/><circle cx={x} cy={y} r="9" fill="none"/><title>Known 00:00 UTC processed buoy position · validation only, never an inference input</title></g>; })()}
      </g>}
      <circle cx={observedX} cy={observedY} r="5" fill="#244e65" stroke="white" strokeWidth="1.5"><title>Observed endpoint · 06:00 UTC</title></circle>
      <text x={Number(observedX)+10} y={Number(observedY)-10} fill="#244e65" fontSize="11">06:00 observation</text>
      <text x="22" y="420" fill="#526f83" fontSize="11">Grid: {(domain.span/4).toLocaleString(undefined,{maximumFractionDigits:0})} display metres</text><text x="655" y="420" textAnchor="end" fill="#526f83" fontSize="11">East → · North ↑</text>
    </svg>
    <figcaption className={`${styles.note} ${styles.caption}`}>Arrow follows descending time toward an earlier modeled location. Points show {candidates.length}/25 declared cases at the selected lookback. No probability, source hull or confidence percentage is inferred. Display interpolation is not measured water motion.{showValidation && " Orange cross: known 00:00 position; outlined squares: six-hour reconstruction models. Validation always compares six hours, even when the candidate selector shows one or three."}</figcaption>
  </figure>;
}

const pipelineTitles = ["Plot the observations","Connect the positions","Filter the motion","Apply the model","Trace back and project ahead"];
const pipelineDescriptions = [
  "Three processed NOAA buoy positions at 01:00, 02:00 and 03:00 UTC. The dots are observations; motion between them is not directly observed.",
  "Lines connect consecutive observed positions. They estimate the route between hourly fixes; they do not measure every turn or water-current change.",
  "A fixed-noise Kalman filter updates position and velocity from these three fixes. It is a small state estimate, not a newly trained neural model.",
  "At 03:00, subtract the modeled current from filtered object velocity. Carry that fixed east/north discrepancy through the changing current field.",
  "From the filtered 03:00 state, run separate modeled branches toward 00:00 and 06:00. They are hypotheses to check, not a verified source or capture.",
];
export type OceanPipelineVisibility = { raw:boolean; filtered:boolean; branches:boolean };

export function OceanPipelineFigure({pipeline,groupId,step,visible,showValidation,onToggle,branchMinutes=180}:{pipeline:OceanPipeline;groupId:string;step:number;visible:OceanPipelineVisibility;showValidation:boolean;onToggle:(id:string,checked:boolean)=>void;branchMinutes?:number}) {
  const title = useId(), backArrow = useId(), forwardArrow = useId(), plot = oceanPipelinePlot(pipeline,groupId);
  if (!plot) return <p className={styles.empty} role="status">The recorded positions are unavailable. No teaching path or replacement measurement was generated.</p>;
  const screen = (point:OceanSourcePlotPoint) => [(340+(point.x_m-plot.domain.centerX)*360/plot.domain.span).toFixed(3),(210-(point.y_m-plot.domain.centerY)*360/plot.domain.span).toFixed(3)];
  const line = (points:OceanSourcePlotPoint[],color:string,key:string,maximumGap:number,dashed=false,arrow?:string) => oceanSourceSegments(points,maximumGap).filter(segment => segment.length>1).map((segment,index) => <polyline key={`${key}-${index}`} points={segment.map(point => screen(point).join(",")).join(" ")} fill="none" stroke={color} strokeWidth="2.4" strokeDasharray={dashed ? "6 5" : undefined} markerEnd={arrow ? `url(#${arrow})` : undefined}/>);
  const elapsed = Math.max(0,Math.min(180,Number.isFinite(branchMinutes) ? branchMinutes : 180))*60;
  const backward = plot.backward.filter(point=>(point.lookback_s ?? 0)<=elapsed), forward = plot.forward.filter(point=>(point.lookback_s ?? 0)<=elapsed);
  const ends: {points:OceanSourcePlotPoint[];color:string;description:string}[] = [
    {points:backward,color:"#88729b",description:"Earlier modeled position; a possible search location, not a verified pollution source."},
    {points:forward,color:"#138f9d",description:"Projected later location: a possible inspection opportunity, not a modeled or guaranteed capture."},
  ];
  return <figure className={styles.figure}>
    <PlotSeriesControls legend="Show walkthrough layers" series={[
      {id:"raw",label:"Observed positions",explanation:"Three permitted processed buoy fixes. Connecting lines are an estimate between them.",color:"#607f91",checked:visible.raw},
      {id:"filtered",label:"Filtered state",explanation:"Kalman position/velocity estimates, visible from the filtering step. Assumed noise is not measured buoy uncertainty.",color:"#087fac",checked:visible.filtered},
      {id:"branches",label:"Modeled hypotheses",explanation:"Earlier and later motion under the declared current-plus-offset model; visible in the final step.",color:"#88729b",checked:visible.branches},
    ]} onChange={onToggle}/>
    {!visible.raw && (!visible.filtered || step<2) && (!visible.branches || step<4) && !showValidation && <p className={styles.caption} role="status">All currently available layers are hidden. Choose a layer to display; saved calculations and axes stay unchanged.</p>}
    <svg className={styles.plot} viewBox="0 0 680 450" role="img" aria-labelledby={title} data-domain={`${plot.domain.centerX},${plot.domain.centerY},${plot.domain.span}`}>
      <title id={title}>{`Step ${step+1}: ${pipelineTitles[step]}. GDP ${groupId}. Measured, connected, filtered and modeled layers stay separate. Fixed equal east/north scale.`}</title>
      <defs>{[[backArrow,"#88729b"],[forwardArrow,"#138f9d"]].map(([id,color]) => <marker id={id} key={id} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L8 4L0 8Z" fill={color}/></marker>)}</defs>
      <rect x="160" y="30" width="360" height="360" fill="#f5fbfe" stroke="#c9dfe9"/>
      {[0,1,2,3,4].map(index => <g key={index} stroke="#d9e9f2"><line x1={160+index*90} x2={160+index*90} y1="30" y2="390"/><line x1="160" x2="520" y1={30+index*90} y2={30+index*90}/></g>)}
      {visible.raw && <g data-pipeline-layer="observed">
        {step>=1 && <g data-pipeline-layer="connected">{line(plot.raw,"#7c939f","connected",3600,true)}</g>}
        {plot.raw.map((point,index) => {const [x,y]=screen(point);return <g key={index}><circle cx={x} cy={y} r="4" fill="white" stroke="#607f91" strokeWidth="2"/><text x={Number(x)+9} y={Number(y)-9} fontSize="11" fill="#526f83">{point.time_utc?.slice(11,16)}</text><title>{`Recorded ${point.time_utc} · ${point.latitude_deg.toFixed(5)}°, ${point.longitude_deg.toFixed(5)}°`}</title></g>;})}
      </g>}
      {step>=2 && visible.filtered && <g data-pipeline-layer="filtered">{line(plot.filtered,"#087fac","filtered",3600)}{plot.filtered.map((point,index) => {const [x,y]=screen(point);return <circle key={index} cx={x} cy={y} r="3.3" fill="#087fac"><title>{`Filtered state · ${point.time_utc}`}</title></circle>;})}</g>}
      {step>=4 && visible.branches && <g data-pipeline-layer="hypotheses" data-branch-minutes={branchMinutes}><g data-pipeline-branch="backward">{line(backward,"#88729b","backward",300,true,backArrow)}</g><g data-pipeline-branch="forward">{line(forward,"#138f9d","forward",300,true,forwardArrow)}</g>{ends.map(({points,color,description},index)=>{const end=points.at(-1);if(!end)return null;const [x,y]=screen(end);return <circle key={index} cx={x} cy={y} r="6" fill="white" stroke={color} strokeWidth="2"><title>{`${description} Saved time: ${end.time_utc}.`}</title></circle>;})}</g>}
      {showValidation && <g data-pipeline-layer="validation">{plot.validation.map(row => {if(!row.point)return null;const [x,y]=screen(row.point);return <g key={`${row.direction}-${row.time_utc}`} data-validation-truth="true" stroke="#ba6e27" strokeWidth="2.2"><path d={`M${Number(x)-5} ${y}h10M${x} ${Number(y)-5}v10`}/><title>{`Separate validation · ${row.time_utc} · stored miss ${metres(row.error_m)}`}</title></g>;})}</g>}
      <text x="22" y="420" fill="#526f83" fontSize="11">Grid: {(plot.domain.span/4).toLocaleString(undefined,{maximumFractionDigits:0})} display metres</text><text x="655" y="420" textAnchor="end" fill="#526f83" fontSize="11">East → · North ↑</text>
    </svg>
    <figcaption className={`${styles.note} ${styles.caption}`}>{pipelineDescriptions[step]}{step>=4 && " Purple: earlier hypothesis. Teal: later projection. No collector geometry or capture efficiency is modeled here."}{showValidation && " Orange crosses are separately revealed validation positions."}</figcaption>
  </figure>;
}

export function OceanPipelineTutorial({pipeline}:{pipeline:OceanPipeline}) {
  const [groupId,setGroupId] = useState<string>(OCEAN_SOURCE_GROUPS[0]), [step,setStep] = useState(0), [playing,setPlaying] = useState(false), [showValidation,setShowValidation] = useState(false), [motionNote,setMotionNote] = useState(""), [branchMinutes,setBranchMinutes] = useState(180);
  const [visible,setVisible] = useState<OceanPipelineVisibility>({raw:true,filtered:true,branches:true});
  const playback = useRef<ReturnType<typeof createOceanPipelinePlayback>|null>(null), validationId=useId();
  useEffect(()=>{
    const controller=createOceanPipelinePlayback({schedule:(callback,delay)=>window.setTimeout(callback,delay),cancel:id=>window.clearTimeout(id),onStep:setStep,onPlaying:setPlaying});
    playback.current=controller;
    const hidden=()=>{if(document.hidden)controller.pause();}, media=window.matchMedia("(prefers-reduced-motion: reduce)"), reduced=()=>{if(media.matches)controller.pause();};
    document.addEventListener("visibilitychange",hidden);media.addEventListener("change",reduced);
    return()=>{controller.dispose();document.removeEventListener("visibilitychange",hidden);media.removeEventListener("change",reduced);if(playback.current===controller)playback.current=null;};
  },[]);
  function play(){if(window.matchMedia("(prefers-reduced-motion: reduce)").matches){setMotionNote("Automatic playback respects reduced motion. Use the numbered steps or Next step.");return;}setMotionNote("");playback.current?.start(step);}
  const group=pipeline.forecasts.groups.find(row=>row.group_id===groupId)!, validation=pipeline.validation.rows.filter(row=>row.group_id===groupId), state=group.filtered_states.at(-1), pair=(value:number[]|null|undefined)=>value ? `(${value.map(v=>v.toLocaleString(undefined,{maximumFractionDigits:4})).join(", ")}) m/s` : "Unavailable";
  return <section className={styles.stack} aria-label="Five-step motion walkthrough"><div className={styles.summary}><strong>Watch the calculation build from three observations</strong><p>Observed points → connected estimate → filtered state → model equation → earlier/later hypotheses. All positions are saved results; playback runs no new calculation.</p></div>
    <label className={styles.label}>Historical buoy<select value={groupId} onChange={event=>{playback.current?.select(0);setGroupId(event.target.value);setBranchMinutes(180);setShowValidation(false);}}>{OCEAN_SOURCE_GROUPS.map(id=><option key={id} value={id}>GDP {id}</option>)}</select></label>
    <ol className={styles.steps} aria-label="Calculation steps">{pipelineTitles.map((title,index)=><li key={title}><button type="button" aria-current={step===index ? "step" : undefined} onClick={()=>playback.current?.select(index)}><span>{index+1}</span>{title}</button></li>)}</ol>
    <div className={styles.controls}><button type="button" className="secondary-button" disabled={step===0} onClick={()=>playback.current?.select(step-1)}>Previous step</button><button type="button" className="primary-button" disabled={step===4} onClick={()=>playback.current?.select(step+1)}>Next step</button><button type="button" className="secondary-button" onClick={()=>playing ? playback.current?.pause() : play()}>{playing ? "Pause walkthrough" : step===4 ? "Replay walkthrough" : "Play walkthrough"}</button></div>
    <p className={styles.note} role="status">Step {step+1} of 5 · {pipelineTitles[step]}{playing ? " · playing one pass" : ""}{motionNote ? ` · ${motionNote}` : ""}</p>
    {step===4 && <label className={styles.scrubber}>Reveal saved branch time · {branchMinutes} minutes from 03:00 UTC<input type="range" min="0" max="180" step="5" value={branchMinutes} aria-valuetext={`${branchMinutes} minutes in each direction from 03:00 UTC`} onChange={event=>{playback.current?.pause();setBranchMinutes(Number(event.target.value));}}/><span>0 → 180 minutes · each displayed point is a saved five-minute model output; unsupported branches stop early.</span></label>}
    <OceanPipelineFigure pipeline={pipeline} groupId={groupId} step={step} visible={visible} showValidation={showValidation} branchMinutes={branchMinutes} onToggle={(id,checked)=>setVisible(previous=>({...previous,[id]:checked}))}/>
    {step>=3 && <section className={styles.formula} aria-label="Saved model calculation"><h3>From filtered velocity to a changing-current trajectory</h3><code>{group.formula?.equation ?? "Model equation unavailable"}</code><p className={styles.note}>At 03:00, b = filtered velocity − current velocity. RK4 integrates that fixed offset plus changing currents. This is an assumed motion model; it does not identify windage or train a new model.</p><dl><div><dt>Filtered velocity</dt><dd>{pair(group.formula?.filtered_velocity_east_north_m_s)}</dd></div><div><dt>Current at 03:00</dt><dd>{pair(group.formula?.current_east_north_m_s)}</dd></div><div><dt>Constant offset b</dt><dd>{pair(group.formula?.residual_bias_east_north_m_s)}</dd></div></dl><details><summary>Filtering state and assumptions</summary><p className={styles.note}>State = [x, y, velocity east, velocity north]. Predict position from velocity, then correct it using the next observed position. Position noise is assumed to be 100 m and acceleration spectral density is fixed at 10⁻⁶ m²/s³; these are not measured camera settings.</p><p className={styles.note}>Saved final state: {state ? `${state.east_m.toFixed(1)} m east, ${state.north_m.toFixed(1)} m north; ${state.status}.` : "Unavailable."} The first fix has no velocity estimate; initialization waits for the second fix.</p><code className={styles.equation}>{pipeline.forecasts.stages[2].formula}</code></details></section>}
    <label className={styles.checkbox}><input type="checkbox" checked={showValidation} aria-controls={validationId} onChange={event=>setShowValidation(event.target.checked)}/>Show reserved comparison positions · 00:00 and 04:00–06:00</label>
    {showValidation && <section className={styles.validation} id={validationId} aria-label="Separate walkthrough validation"><h3>Compare hypotheses with separately reserved positions</h3><p className={styles.note}>These positions are withheld from this three-fix calculation. The full historical groups were already viewed during project development, so this is not a new independent test.</p><div className="table-scroll"><table className="metrics-table"><caption>Stored earlier/later position errors · selected group</caption><thead><tr><th>Direction</th><th>UTC</th><th>Status</th><th>Position miss</th></tr></thead><tbody>{validation.map(row=><tr key={`${row.direction}-${row.time_utc}`}><th scope="row">{row.direction}</th><td>{row.time_utc.slice(11,16)}</td><td>{row.status}</td><td>{metres(row.error_m)}</td></tr>)}</tbody></table></div><p className={styles.note}>{pipeline.validation.scored_rows}/8 planned model/time rows scored across two already-viewed groups. Missing errors stay unavailable. These distances do not measure plastic-source accuracy or interceptor capture.</p></section>}
    <details className="details-panel"><summary>Scope and missing physics</summary><ul className="reason-list">{pipeline.forecasts.limitations.map(text=><li key={text}>{text}</li>)}</ul><p className={styles.note}>Group status: {group.status}{group.reason_code ? ` · ${group.reason_code}` : ""}. Backward: {group.backward.status}. Forward: {group.forward.status}. The forecast may guide where to inspect an intervention; a separate layout comparison and physical trial are still needed.</p></details>
  </section>;
}

export function OceanSourceReview({api,envelope,token}: {api:string;envelope:OceanSourceEnvelope;token:string}) {
  const [question,setQuestion] = useState("Explain what these conditional earlier locations support, distinguish numerical closure from earlier-position validation, and state what is needed before claiming a pollution source.");
  const [answer,setAnswer] = useState<OceanSourceAnswer | null>(null), [loading,setLoading] = useState(false), [error,setError] = useState("");
  const requests = useRequests();
  async function ask() {
    if (!token || !question.trim()) return;
    const gate = requests.current, pending = gate?.begin(); if (!gate || !pending) return;
    const timer = window.setTimeout(() => pending.controller.abort(),90_000);
    pending.controller.signal.addEventListener("abort",() => window.clearTimeout(timer),{once:true});
    setAnswer(null); setError(""); setLoading(true);
    try {
      const response = await fetch(`${api.replace(/\/$/,"")}/api/v1/research/ocean-source/investigate`,{method:"POST",cache:"no-store",headers:{"Content-Type":"application/json",Authorization:`Bearer ${token}`},body:JSON.stringify(oceanSourceQuestion(question,envelope)),signal:pending.controller.signal});
      const result = await readVectorResponse(response,value => validateOceanSourceAnswer(value,envelope),5_000_000);
      if (gate.current(pending)) setAnswer(result);
    } catch (cause) { if (gate.owns(pending)) setError(pending.controller.signal.aborted ? "The bounded Chalk review timed out. Saved numerical evidence remains available." : errorText(cause)); }
    finally { window.clearTimeout(timer); if (gate.owns(pending)) { gate.finish(pending); setLoading(false); } }
  }
  return <section className={styles.review} aria-label="Ask Chalk about ocean earlier locations"><h3>Explain the evidence with Chalk</h3><p className={styles.note}>A read-only review of this exact report. Chalk cannot acquire data, change the model, record a trial or identify a polluter.</p>
    <details className="details-panel"><summary>Change the question</summary><label className={styles.label}>Research question<textarea rows={3} value={question} maxLength={2000} disabled={loading} onChange={event => setQuestion(event.target.value)}/></label></details>
    <button type="button" className="primary-button" disabled={!token || loading || !question.trim()} onClick={() => void ask()}><Icon name="agent"/>{loading ? "Reviewing saved evidence…" : "Ask Chalk about earlier locations"}</button>
    {!token && <p className={styles.note}><Link href="/login" className="card-link">Connect local operator access</Link> to request a live review.</p>}
    {loading && <p role="status" className={styles.note}>One read-only evidence tool; at most two bounded model calls.</p>}
    {error && <p role="alert" className="notice error">{error} No automatic retry will occur.</p>}
    {answer && <div className={styles.answer} role="status"><span className="pill">{answer.action} · {answer.live_model_response ? "Live Chalk response" : "No live model response"}</span><p>{answer.explanation}</p>{answer.failure_code && <p className={styles.note}>Review unavailable: {answer.failure_code}{answer.provider_status_code ? ` · HTTP ${answer.provider_status_code}` : ""}.</p>}<details className="details-panel"><summary>Exact citations and read-only trace</summary><ul>{answer.evidence_ids.map(id => <li key={id} className={styles.identity}>{id}</li>)}</ul><pre className="code-block">{JSON.stringify(answer.trace,null,2)}</pre></details></div>}
  </section>;
}

export function OceanSourceSensitivity({envelope}: {envelope:OceanSourceEnvelope}) {
  const [groupId,setGroupId] = useState<string>(OCEAN_SOURCE_GROUPS[0]), [lookback,setLookback] = useState(6), [visible,setVisible] = useState<OceanSourceVisibility>({nominal:true,scenarios:false,candidates:true}), [showValidation,setShowValidation] = useState(false);
  const validationId = useId(), group = envelope.report.forecasts.groups.find(row => row.group_id === groupId)!, coverage = group.reverse_current.coverage;
  const rows = envelope.report.validation.rows.filter(row => row.group_id === groupId);
  return <div className={styles.stack}>
    <div className={styles.summary}><strong>Conditional earlier locations · known lookback, not a pollution release source</strong><p>Starting from a processed buoy observation at 06:00 UTC, the model traces prescribed changing currents backward. These two groups and their earlier positions were already viewed; this is an exploratory retrospective diagnostic.</p></div>
    <div className={styles.controls}><label className={styles.label}>Buoy group<select value={groupId} onChange={event => setGroupId(event.target.value)}>{OCEAN_SOURCE_GROUPS.map(id => <option key={id} value={id}>GDP {id}</option>)}</select></label><label className={styles.label}>Known lookback<select value={lookback} onChange={event => setLookback(Number(event.target.value))}>{OCEAN_SOURCE_LOOKBACKS.map(hours => <option key={hours} value={hours}>{hours}h earlier · {String(6-hours).padStart(2,"0")}:00 UTC</option>)}</select></label></div>
    <OceanSourceFigure envelope={envelope} groupId={groupId} lookback={lookback} visible={visible} showValidation={showValidation} onToggle={(id,checked) => setVisible(previous => ({...previous,[id]:checked}))}/>
    <p className={styles.note}>{coverage.completed_scenarios}/25 complete assumption cases · {coverage.partial_scenarios} partial · {coverage.unsupported_scenarios} unsupported. Twenty-five endpoint/current perturbation cases are not twenty-five independent trials or a calibrated uncertainty region. Unsupported candidates remain missing.</p>
    <label className={styles.checkbox}><input type="checkbox" checked={showValidation} aria-controls={validationId} onChange={event => setShowValidation(event.target.checked)}/>Show validation evidence · known 00:00 position and reconstruction errors</label>
    {showValidation && <section className={styles.validation} id={validationId} aria-label="Separate earlier-position validation"><h3>Compare with the known earlier buoy position</h3><p className={styles.note}>The known 00:00 UTC position was withheld from candidate construction and revealed for this separate six-hour reconstruction check. It is a processed historical buoy position, not a release or plastic source.</p><div className="table-scroll"><table className="metrics-table"><caption>Selected group · stored six-hour earlier-position error</caption><thead><tr><th>Fixed reconstruction</th><th>Status</th><th><HelpLabel label="Earlier-position miss" explanation="Stored distance from the reconstructed 00:00 position to the known processed buoy position. This is empirical reconstruction error, distinct from a model round trip."/></th></tr></thead><tbody>{rows.map(row => <tr key={row.model_id}><th scope="row">{modelLabels[row.model_id]}</th><td>{row.status}{row.reason_code && <><br/><small>{row.reason_code}</small></>}</td><td>{metres(row.error_m)}</td></tr>)}</tbody></table></div><p className={styles.note}>{envelope.report.validation.scored_model_rows}/6 model/group rows scored using two known earlier positions. {envelope.report.validation.primary_complete ? "Complete descriptive comparison on this already-viewed pair; no operational model is selected." : "Incomplete comparison: the common-cohort mean is withheld."}</p></section>}
    <details className="details-panel"><summary>Method, numerical check and provenance</summary><div className={styles.stack}><p className={styles.note}>Current sign and physical time order both reverse. HYCOM is retrospective model output at 15 m. Endpoint/current perturbations are declared assumptions; the display contains no posterior probability, release-time estimate or calibrated confidence.</p><p className={styles.note}>Numerical forward/reverse closure: {group.numerical_closure.status}, endpoint distance {metres(group.numerical_closure.endpoint_distance_m)}. This checks the model calculation, not agreement with earlier real motion, a polluter identity, tank accuracy or reef protection.</p><ul className="reason-list">{envelope.report.limitations?.map(text => <li key={text}>{text}</li>)}</ul><p className={styles.identity}>Report: {envelope.artifact_identity.report_sha256}<br/>Protocol: {envelope.artifact_identity.protocol_sha256}<br/>Identity: {envelope.artifact_identity.identity_sha256}</p><p className={styles.note}>Saved bytes and lineage checked by the backend. This display does not rerun the transport or score a new dataset. For a retained endpoint or unknown lookback, deterministic reverse drift does not recover the missing history.</p></div></details>
  </div>;
}

export function OceanSourceResults({api,envelope,token}: {api:string;envelope:OceanSourceEnvelope;token:string}) {
  return <div className={styles.stack}>{envelope.report.pipeline_tutorial ? <><OceanPipelineTutorial pipeline={envelope.report.pipeline_tutorial}/><details className="details-panel"><summary>06:00 endpoint: earlier-location sensitivity and source-model validation</summary><OceanSourceSensitivity envelope={envelope}/></details></> : <OceanSourceSensitivity envelope={envelope}/>}<OceanSourceReview key={`${api}:${token}:${envelope.artifact_identity.identity_sha256}`} api={api} envelope={envelope} token={token}/></div>;
}

function Session({api,token}: {api:string;token:string}) {
  const [envelope,setEnvelope] = useState<OceanSourceEnvelope | null>(null), [loading,setLoading] = useState(false), [error,setError] = useState("");
  const requests = useRequests();
  async function load() {
    const gate = requests.current, pending = gate?.begin(); if (!gate || !pending) return;
    const timer = window.setTimeout(() => pending.controller.abort(),30_000);
    pending.controller.signal.addEventListener("abort",() => window.clearTimeout(timer),{once:true});
    setEnvelope(null); setLoading(true); setError("");
    try {
      const response = await fetch(`${api.replace(/\/$/,"")}/api/v1/research/ocean-source`,{cache:"no-store",signal:pending.controller.signal});
      const result = await readVectorResponse(response,validateOceanSourceEnvelope,5_000_000);
      if (gate.current(pending)) setEnvelope(result);
    } catch (cause) { if (gate.owns(pending)) setError(pending.controller.signal.aborted ? "The saved report request timed out. No result was accepted." : errorText(cause)); }
    finally { window.clearTimeout(timer); if (gate.owns(pending)) { gate.finish(pending); setLoading(false); } }
  }
  return <section className="card" aria-label="Ocean earlier-location diagnostic"><div className={`card-header ${styles.header}`}><div><h2 className="card-title"><Icon name="wave"/>Explore earlier ocean locations</h2><p className="card-subtitle">A saved changing-current diagnostic · separate from tank source tracing</p></div><button type="button" className="secondary-button" disabled={loading} onClick={() => void load()}><Icon name="play"/>{loading ? "Checking saved evidence…" : "Load ocean earlier-location example"}</button></div><div className={`card-body ${styles.stack}`}><p className={styles.note}>Loading reads saved local evidence. It does not acquire trajectories, use a provider, start a camera or send messages.</p>{loading && <p role="status">Checking saved report identities and supported paths…</p>}{error && <p role="alert" className="notice error">{error} No automatic retry will occur.</p>}{envelope && <OceanSourceResults key={envelope.artifact_identity.identity_sha256} api={api} envelope={envelope} token={token}/>}</div></section>;
}

export function OceanSource({api}: {api:string}) { const {token} = useOperator(); return <Session key={api} api={api} token={token}/>; }
