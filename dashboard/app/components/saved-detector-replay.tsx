"use client";
/* Authenticated JSON contains local JPEGs; this image never uses an external asset service. */
/* eslint-disable @next/next/no-img-element */
import { useEffect, useId, useRef, useState } from "react";
import { parseDetectorReplay, type DetectorReplayReport, type DetectorReplayClip } from "./saved-detector-replay-state.ts";
import styles from "./saved-detector-replay.module.css";

type Request = <T>(path: string, body?: unknown, options?: { signal?: AbortSignal; independent?: boolean }) => Promise<T>;
export type SavedDetectorReplayProps = { request: Request; disabled: boolean; onBusyChange?: (busy:boolean)=>void };
export function ReplayFrame({ clip }: { clip: DetectorReplayClip }) {
  const [accepted,setAccepted] = useState(true), [rejected,setRejected] = useState(true), [baseline,setBaseline] = useState(false), [roi,setRoi] = useState(true);
  const example = clip.example, [width,height] = example.image_size_px;
  return <div className={styles.framePanel}>
    <div className={styles.toggles}>
      <label><input type="checkbox" checked={accepted} onChange={event=>setAccepted(event.target.checked)}/>Green-cap v2 accepted</label>
      <label><input type="checkbox" checked={rejected} onChange={event=>setRejected(event.target.checked)}/>Rejected objects</label>
      <label><input type="checkbox" checked={baseline} onChange={event=>setBaseline(event.target.checked)}/>Original v1 candidates</label>
      <label><input type="checkbox" checked={roi} onChange={event=>setRoi(event.target.checked)}/>Frozen tank outline</label>
    </div>
    <div className={styles.frame}>
      <img src={example.jpeg_data_url} width={width} height={height} alt={`Saved local frame from ${clip.label}. Detection overlays are development diagnostics.`}/>
      <svg viewBox={`0 0 ${width} ${height}`} className={styles.overlay} aria-hidden="true">
        {roi && <polygon className={styles.roi} points={example.detection_polygon_px.map(point=>point.join(",")).join(" ")}/>}
        {baseline && example.baseline_boxes_px.map(([x,y,w,h],i)=><rect key={i} className={styles.baseline} x={x} y={y} width={w} height={h}/>)}
        {accepted && example.accepted_boxes_px.map(([x,y,w,h],i)=><rect key={i} className={styles.accepted} x={x} y={y} width={w} height={h}/>)}
        {rejected && example.rejected_candidates.map(({bbox_px:[x,y,w,h],reason_codes},i)=><rect key={i} className={styles.rejected} x={x} y={y} width={w} height={h}><title>{reason_codes.join(", ")}</title></rect>)}
      </svg>
    </div>
    <p className={styles.caption}>Representative saved frame {example.sequence}. Green boxes pass the green-marker surface policy; red boxes show rejected foreground. These labels are detector decisions, not human-verified classification accuracy.</p>
  </div>;
}

/** No camera access or request on mount. Both buttons use saved local files only. */
export function SavedDetectorReplay({ request, disabled, onBusyChange }: SavedDetectorReplayProps) {
  const id = useId(), [report,setReport] = useState<DetectorReplayReport|null>(null), [selected,setSelected] = useState("");
  const [busy,setBusy] = useState(false), [error,setError] = useState("");
  const mounted = useRef(false), active = useRef(false), generation = useRef(0), pending = useRef<AbortController|null>(null), busyCallback = useRef(onBusyChange);
  useEffect(()=>{busyCallback.current=onBusyChange;},[onBusyChange]);
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;pending.current?.abort();busyCallback.current?.(false);};},[]);
  useEffect(()=>{if(disabled){generation.current++;pending.current?.abort();}},[disabled]);
  async function load(run:boolean) {
    if(disabled||active.current)return;
    active.current=true; const version=generation.current,controller=new AbortController();pending.current=controller;
    setBusy(true);setError("");busyCallback.current?.(true);
    try {
      const result=parseDetectorReplay(await request<unknown>("/camera/detector-replay",run?{}:undefined,{signal:controller.signal,independent:true}));
      if(mounted.current&&generation.current===version&&!controller.signal.aborted){setReport(result);setSelected(result.clips[0].id);}
    }catch(err){if(mounted.current&&generation.current===version&&!controller.signal.aborted)setError(err instanceof Error?err.message:"Saved-footage replay could not be read.");}
    finally{if(pending.current===controller)pending.current=null;active.current=false;if(mounted.current)setBusy(false);busyCallback.current?.(false);}
  }
  const clip=report?.clips.find(item=>item.id===selected)??report?.clips[0],locked=disabled||busy;
  return <section className={styles.panel} aria-labelledby={`${id}-heading`}>
    <div className={styles.heading}><h3 id={`${id}-heading`}>Replay saved camera footage</h3><span>Development replay</span></div>
    <p className={styles.help}>Compare the original detector with the green-cap surface detector on existing private clips and backgrounds. V2 requires a green marker; it is not a plastic classifier. No camera opens, no new tank setup is needed, and frames stay on this Mac.</p>
    <div className={styles.actions}><button type="button" disabled={locked} onClick={()=>void load(true)}>Replay saved camera footage</button><button type="button" disabled={locked} onClick={()=>void load(false)}>Show last saved replay</button></div>
    {busy&&<p role="status" className={styles.notice}>Reading and comparing saved footage locally…</p>}
    {error&&<p role="alert" className={styles.error}>{error}</p>}
    {report&&clip&&<div className={styles.result}>
      <p className={styles.scope}>Development regression · {report.totals.frames} saved frames across {report.clips.length} clips. These clips informed development; this is not an independent field-accuracy test.</p>
      <label className={styles.selection} htmlFor={`${id}-clip`}>Saved clip<select id={`${id}-clip`} value={clip.id} disabled={locked} onChange={event=>setSelected(event.target.value)}>{report.clips.map(item=><option key={item.id} value={item.id}>{item.label} · {item.frames} frames</option>)}</select></label>
      <div className={styles.tableWrap}><table><caption>Same saved frames · detector decisions</caption><thead><tr><th scope="col">Detector</th><th scope="col">Accepted frames</th><th scope="col">Gap frames</th><th scope="col">Multiple objects</th><th scope="col">Scene gaps</th></tr></thead><tbody><tr><th scope="row">Original v1</th><td>{clip.baseline.accepted_frames}</td><td>{clip.baseline.gap_frames}</td><td>{clip.baseline.multiple_frames}</td><td>{clip.baseline.scene_gap_frames}</td></tr><tr><th scope="row">Green-cap v2</th><td>{clip.surface.accepted_frames}</td><td>{clip.surface.gap_frames}</td><td>{clip.surface.multiple_frames}</td><td>{clip.surface.scene_gap_frames}</td></tr></tbody></table></div>
      <ReplayFrame key={`${report.report_id}-${clip.id}`} clip={clip}/>
      <p className={styles.scope}>Centimetre alignment and pollution origin remain unvalidated. This replay creates no measured flow, source case, or physical validation receipt. Photon messages: none.</p>
      <details><summary>Provenance and rejection reasons</summary><dl><dt>Report</dt><dd><code>{report.report_id}</code></dd><dt>Source</dt><dd>{clip.source_kind} · <code>{clip.source_id}</code></dd><dt>Original camera session</dt><dd><code>{clip.original_camera_session_id}</code></dd><dt>Frozen policy</dt><dd><code>{report.policy.id}</code><br/><code>{report.policy.sha256}</code></dd><dt>Saved manifest</dt><dd><code>{report.manifest_sha256}</code></dd><dt>Evaluated</dt><dd>{report.evaluated_at}</dd></dl><ul>{Object.entries(clip.diagnostics.rejection_counts).map(([reason,n])=><li key={reason}>{reason}: {n}</li>)}{report.warnings.map((warning,i)=><li key={`warning-${i}`}>{warning}</li>)}</ul></details>
    </div>}
  </section>;
}
