"use client";
/* The authenticated local response contains the exact JPEG used for these boxes. */
/* eslint-disable @next/next/no-img-element */
import { useEffect, useId, useMemo, useRef, useState, useSyncExternalStore } from "react";
import type { CameraStatus } from "./field-workflow-state";
import type { RehearsalBounds } from "./estimated-tank-rehearsal-state";
import { LiveSavedDetectorController, livePreviewGrid, type LivePreviewConfig, type LivePreviewFrame, type PreviewRequest } from "./live-saved-detector-state.ts";
import styles from "./live-saved-detector.module.css";

export type LiveSavedDetectorProps = { request:PreviewRequest;camera:CameraStatus|null;disabled:boolean;bounds?:RehearsalBounds;onActiveChange?:(active:boolean)=>void };
function reasonLabel(reason:string|null){return reason?reason.toLowerCase().replaceAll("_"," "):"Waiting for a detection";}

export function LiveSavedDetectorFrame({ config,frame }:{config:LivePreviewConfig;frame:LivePreviewFrame}) {
  const[showGrid,setShowGrid]=useState(true),[showBoxes,setShowBoxes]=useState(true),[showCandidates,setShowCandidates]=useState(true);
  const clip=useId().replaceAll(":", ""),grid=useMemo(()=>livePreviewGrid(config,frame),[config,frame]),[width,height]=frame.image_size_px;
  const point=frame.point,estimated=point&&point.estimated_x_cm!==null&&point.estimated_y_cm!==null?` · estimated tank ${point.estimated_x_cm.toFixed(2)}, ${point.estimated_y_cm.toFixed(2)} cm`:" · tank coordinates withheld: no accepted image registration";
  return <div className={styles.framePanel}>
    <div className={styles.view}>
      <img src={frame.jpeg_data_url} width={width} height={height} decoding="async" alt={`Exact local camera frame ${frame.sequence}, with matching green-marker detection overlay.`}/>
      <svg className={styles.overlay} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
        {grid&&showGrid&&<g data-live-layer="estimated-grid"><defs><clipPath id={clip}><polygon points={grid.hull.map(point=>point.join(",")).join(" ")}/></clipPath></defs><g clipPath={`url(#${clip})`}>{grid.lines.map(line=><g key={`${line.axis}-${line.value}`}><line className={styles.gridLine} x1={line.start[0]} y1={line.start[1]} x2={line.end[0]} y2={line.end[1]}/><text className={styles.gridLabel} x={line.start[0]+5} y={line.start[1]+18}>{line.axis} {line.value} cm est.</text></g>)}</g><polygon className={styles.outline} points={grid.hull.map(point=>point.join(",")).join(" ")}/></g>}
        {showBoxes&&frame.observed&&frame.point&&<g data-live-layer="green-cap"><rect className={styles.acceptedBox} x={frame.point.bbox_px[0]} y={frame.point.bbox_px[1]} width={frame.point.bbox_px[2]} height={frame.point.bbox_px[3]}/><circle className={styles.center} cx={frame.point.pixel_x} cy={frame.point.pixel_y} r="5"/><text className={styles.capLabel} x={frame.point.bbox_px[0]} y={Math.max(24,frame.point.bbox_px[1]-10)}>GREEN MARKER</text></g>}
        {showCandidates&&!frame.observed&&frame.detections.map((d,i)=><rect key={i} data-live-layer="ambiguous-candidate" className={styles.candidateBox} x={d.bbox_px[0]} y={d.bbox_px[1]} width={d.bbox_px[2]} height={d.bbox_px[3]}/>)}
      </svg>
    </div>
    <div className={styles.toggles}><label><input type="checkbox" checked={!!grid&&showGrid} disabled={!grid} onChange={event=>setShowGrid(event.target.checked)}/>Estimated grid (cm)</label><label><input type="checkbox" checked={showBoxes} onChange={event=>setShowBoxes(event.target.checked)}/>Green-marker box</label><label><input type="checkbox" checked={showCandidates} onChange={event=>setShowCandidates(event.target.checked)}/>Ambiguous candidates</label></div>
    <output className={frame.observed?styles.readout:styles.gap} aria-live="off">{frame.point&&frame.observed?`Green marker · image ${frame.point.pixel_x.toFixed(1)}, ${frame.point.pixel_y.toFixed(1)} px${estimated}`:`No position · ${reasonLabel(frame.reason)}`}</output>
    {frame.detector_mode==="saved_green_marker_preview_v1"&&frame.saved_foreground_status!=="OK"&&<p className={styles.notice}>Saved background changed; using green-marker preview. {frame.alignment?"Tank coordinates use a bounded image-translation estimate.":"The cap box is visible in pixels; grid and centimetres are withheld."}</p>}
    <p className={styles.caption}>Frame {frame.sequence} · {new Date(frame.received_utc).toLocaleTimeString()} · {frame.age_s.toFixed(2)} s old when received. The image and boxes come from the same frame; updates are limited to eight per second, with one request at a time. {frame.scene_rejection?"The saved background is incompatible with this scene; coordinates and grid are withheld.":"The grid reuses Megana’s historical mapping with an image-translation estimate; its current centimetre accuracy is unvalidated."}</p>
  </div>;
}

/** Explicit activation reads saved setup and the running camera buffer; never starts a camera. */
export function LiveSavedDetector({request,camera,disabled,bounds,onActiveChange}:LiveSavedDetectorProps){
  const[controller]=useState(()=>new LiveSavedDetectorController({request,camera,disabled,bounds}));
  const state=useSyncExternalStore(controller.subscribe,controller.getSnapshot,controller.getServerSnapshot),active=state.phase==="configuring"||state.phase==="live";
  const activeCallback=useRef(onActiveChange);
  useEffect(()=>{activeCallback.current=onActiveChange;},[onActiveChange]);
  useEffect(()=>{controller.setContext({request,camera,disabled,bounds});},[controller,request,camera,disabled,bounds]);
  useEffect(()=>{activeCallback.current?.(active);},[active]);
  useEffect(()=>()=>{controller.stop();activeCallback.current?.(false);},[controller]);
  const fresh=!!camera?.running&&camera.fresh;
  return <section className={styles.panel} aria-label="Live green-cap tracker using saved setup">
    <div className={styles.heading}><div><h3>Live green-cap tracker</h3><p>Saved measurements · estimated coordinates</p></div><span className={styles.badge} role="status">{state.phase==="live"?"Live display · unvalidated":state.phase==="configuring"?"Loading saved setup":"Display only"}</span></div>
    <div className={styles.actions}><button type="button" disabled={disabled||!fresh||active} onClick={()=>void controller.start()}>Show live detector with saved setup</button><button type="button" disabled={!active} onClick={controller.stop}>Hide live detector</button></div>
    {!fresh&&!active&&<p className={styles.caption}>The webcam needs fresh frames from the separate capture controls. This button does not start or restart it.</p>}
    {state.phase==="off"&&<p className={styles.caption}>Reuses the latest compatible saved background, Megana’s mapping, and the recorded tray dimensions. No ruler survey, new background capture, or calibration fit is performed by this display.</p>}
    {state.phase==="configuring"&&<p role="status" className={styles.notice}>Loading saved background and mapping, then reading the running camera’s buffer…</p>}
    {state.phase==="live"&&!state.frame&&<p role="status" className={styles.notice}>Waiting for the first matching detector frame…</p>}
    {state.config&&state.frame&&<LiveSavedDetectorFrame config={state.config} frame={state.frame}/>}
    {state.error&&<p role="alert" className={styles.error}>{state.error}</p>}
    <p className={styles.scope}>Green markers only; this display does not classify plastic or validate a source. Frames stay on this Mac. This display creates no recording, measured flow, source case, or validated calibration.</p>
    {state.config&&<details><summary>Saved setup and limits</summary><dl><dt>Background</dt><dd><code>{state.config.reference_id}</code> · session <code>{state.config.reference_camera_session_id}</code></dd><dt>Historical mapping</dt><dd><code>{state.config.source_calibration_id}</code> · session <code>{state.config.source_camera_session_id}</code></dd><dt>Current session</dt><dd><code>{state.config.camera_session_id}</code></dd><dt>Display mode</dt><dd>{state.config.detector_mode}</dd><dt>Detector policy</dt><dd><code>{state.config.policy_id}</code><br/><code>{state.config.policy_sha256}</code></dd>{state.config.marker_area_source&&<><dt>Historical green-marker size estimate</dt><dd>{state.config.marker_area_source.area_px.toFixed(0)} px from saved development replay <code>{state.config.marker_area_source.report_id}</code>. This is not a current token-size approval.</dd></>}</dl><ul>{state.config.warnings.map((warning,i)=><li key={i}>{warning}</li>)}</ul></details>}
  </section>;
}
