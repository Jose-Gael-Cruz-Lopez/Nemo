"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
type Case = { id: string; mode: string; evidence_mode: string; calibration_id: string; width_cm:number; height_cm:number; last_observed_at:number|null; track: {x:number;y:number;observed:boolean}[] };
type Evidence = { id:string; source:string; status:string; inference_mode:string; calibration_id:string; absolute_fit:number; margin:number; coverage:number; relative_support:Record<string,number>; reason_codes:string[]; confidence_kind:string };
type Investigation = { explanation:string; action:string; evidence_ids:string[]; trace:{tool:string;result:Record<string,unknown>}[] };
type Proposal = { id:string; approval_token:string; mode:string; expires_at:number; state:string };

export default function InvestigationConsole() {
  const [now,setNow] = useState(0);
  useEffect(()=>{const timer=setInterval(()=>setNow(Date.now()),1000);return ()=>clearInterval(timer);},[]);
  const [token,setToken] = useState("");
  const [cases,setCases] = useState<Case[]>([]);
  const [active,setActive] = useState<Case|null>(null);
  const [evidence,setEvidence] = useState<Evidence|null>(null);
  const [question,setQuestion] = useState("Could another inlet explain this observation?");
  const [answer,setAnswer] = useState<Investigation|null>(null);
  const [analysis,setAnalysis] = useState<unknown>(null);
  const [proposal,setProposal] = useState<Proposal|null>(null);
  const [message,setMessage] = useState("");
  const [busy,setBusy] = useState(false);
  async function request(path:string,body?:unknown) {
    const response = await fetch(`${API}/v1${path}`,{
      method:body===undefined?"GET":"POST",headers:{Authorization:`Bearer ${token}`,"Content-Type":"application/json"},
      body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(120000)});
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail==="string"?data.detail:`Request failed (${response.status})`);
    return data;
  }
  async function perform(operation:()=>Promise<void>) {
    setBusy(true);setMessage("");
    try {await operation();} catch(error) {setMessage(error instanceof Error?error.message:"Request failed");}
    finally {setBusy(false);}
  }
  async function choose(id:string) {
    setActive(null);setEvidence(null);setAnswer(null);setAnalysis(null);setProposal(null);
    const [selected,report] = await Promise.all([request(`/cases/${id}`),request(`/cases/${id}/evidence`)]);
    setActive(selected);setEvidence(report);
  }
  return <section className="workspace" aria-label="Version 3 evidence investigation">
    <p className="eyebrow">FORWARD MODEL · STORED EVIDENCE · MANUAL RECOVERY</p>
    <h2>Investigate a case</h2>
    <p className="muted">Load a recorded or live case. Source tables come directly from the estimator. The investigator uses the configured AI provider. ASUS computer details are pending; the baseline runs on CPU.</p>
    <label>Local operator token <input type="password" autoComplete="off" value={token} onChange={e=>setToken(e.target.value)} style={{padding:10,margin:10}} /></label>
    <button disabled={busy || !token} onClick={()=>void perform(async()=>setCases(await request("/cases")))}>Load cases</button>
    <p className="muted">Token stays in this component&apos;s memory. Configure REEFTRACE_LOCAL_TOKEN in the API environment.</p>
    <label>Case <select value={active?.id??""} disabled={busy} onChange={e=>void perform(()=>choose(e.target.value))} style={{padding:10,margin:10,maxWidth:"100%"}}>
      <option value="" disabled>Select a stored case</option>
      {cases.map(c=><option key={c.id} value={c.id}>{c.mode.toUpperCase()} · {c.evidence_mode} · {c.id}</option>)}
    </select></label>
    {active && evidence && <>
      <p><strong>{active.mode.toUpperCase()} · {evidence.source}</strong> · {evidence.inference_mode}</p>
      <p>Profile: {evidence.calibration_id} · Evidence: {evidence.id}</p>
      <p>Absolute fit: {evidence.absolute_fit.toFixed(4)} · Margin: {evidence.margin.toFixed(3)} · Observation coverage: {evidence.coverage.toFixed(3)}</p>
      <p>{evidence.reason_codes.length?evidence.reason_codes.join(", "):"Fit and source separation gates passed"}</p>
      <p className="muted">Relative support, conditional on the model and candidate set; not probability.</p>
      <ul>{Object.entries(evidence.relative_support).map(([s,v])=><li key={s}>Inlet {s}: {v.toFixed(3)} <progress max={1} value={v} /></li>)}</ul>
      <p>Observation age: {active.last_observed_at===null?"not available":`${Math.max(0,now/1000-active.last_observed_at).toFixed(1)} s`} · {active.mode==="live" && active.last_observed_at!==null && now/1000-active.last_observed_at>5?"STALE":"stored evidence"}</p>
      <svg viewBox="0 0 600 400" role="img" aria-label="Measured observation positions in the tank; gaps are omitted" style={{width:"100%",maxWidth:600,background:"#102e34",borderRadius:12}}>
        {active.track.filter(p=>p.observed).map((p,i)=><circle key={i} cx={p.x/active.width_cm*600} cy={400-p.y/active.height_cm*400} r={3} fill="#e7cc88"/>)}
      </svg>
      <p>Observed points: {active.track.filter(p=>p.observed).length} · Explicit gaps: {active.track.filter(p=>!p.observed).length}</p>
      <div style={{display:"flex",gap:12,flexWrap:"wrap",margin:"20px 0"}}>
        {["age_short_v1","age_wide_v1"].map(p=><button key={p} disabled={busy} onClick={()=>void perform(async()=>setAnalysis(await request(`/cases/${active.id}/sensitivity`,{preset_id:p})))}>{p}</button>)}
        <button disabled={busy} onClick={()=>void perform(async()=>{await request(`/cases/${active.id}/observe`,{});setMessage("A 3-second recording request is queued. Run the camera recorder; no new observation is implied.");})}>Request new observation</button>
      </div>
      {analysis!==null && <details open><summary>Stored sensitivity result</summary><pre style={{overflowX:"auto",maxHeight:320}}>{JSON.stringify(analysis,null,2)}</pre></details>}
      <label>Investigation question <textarea value={question} onChange={e=>setQuestion(e.target.value)} maxLength={4000} style={{display:"block",width:"100%",minHeight:80,margin:"12px 0"}} /></label>
      <button disabled={busy||!question.trim()} onClick={()=>void perform(async()=>setAnswer(await request(`/cases/${active.id}/investigate`,{question})))}>Ask investigator</button>
      {answer && <div><p><strong>{answer.action}</strong> · AI investigator</p><p>{answer.explanation}</p><p>Evidence: {answer.evidence_ids.join(", ")}</p><p>Tools: {answer.trace.map(t=>t.tool).join(" → ")}</p></div>}
      <h3>Optional manual net recovery</h3>
      <p className="muted">Creates a human task. Approval requires a fresh live observation, checked rig, and unchanged evidence. No pump or servo is triggered.</p>
      <button disabled={busy} onClick={()=>void perform(async()=>setProposal(await request("/actions/propose",{case_id:active.id,evidence_id:evidence.id,mode:"manual_net"})))}>Propose manual recovery</button>
      {proposal && <div><p>{proposal.id} · {proposal.state} · expires {new Date(proposal.expires_at*1000).toLocaleTimeString()}</p>
        <button disabled={busy||proposal.state!=="pending"} onClick={()=>void perform(async()=>{const result=await request(`/actions/${proposal.id}/approve`,{token:proposal.approval_token});setProposal({...proposal,state:result.state});setMessage("Manual task approved. Record actual recovery evidence using the API; camera disappearance alone is insufficient.");})}>Approve this manual task</button>
        <button onClick={()=>void perform(async()=>{await request(`/actions/${proposal.id}/stop`,{});setProposal({...proposal,state:"stopped"});})}>Cancel task</button>
      </div>}
    </>}
    <p role="status">{busy?"Working…":message}</p>
    <button onClick={()=>void request("/stop",{}).then(()=>setMessage("Local manual tasks stopped. Physical power is unchanged.")).catch(e=>setMessage(e.message))} style={{marginTop:12,padding:12}}>Stop local tasks</button>
  </section>;
}
