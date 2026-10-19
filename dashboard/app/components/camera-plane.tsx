"use client";

/* Native MJPEG stays in one browser image connection; Next image optimization cannot stream it. */
/* eslint-disable @next/next/no-img-element */
import { useEffect, useId, useMemo, useRef, useState, type MouseEvent } from "react";
import { cameraStreamSource, insideHull, insidePolygon, metricGrid, nativePixel, projectPoint, type Point, type WaterMapping } from "./camera-grid-state";
import styles from "./camera-plane.module.css";
import type { RegistrationStatus } from "./tank-registration-state";

export type CameraPlaneProps = {
  apiBase:string; width:number; height:number; sessionId:string|null; active:boolean;
  calibration?:WaterMapping|null; registration?:RegistrationStatus|null; onPick?:(point:Point)=>void;
};

/** The commissioning draft stays mounted, but a closed panel must not open an image stream. */
export function CalibrationCameraPreview({ visible, ...props }: CameraPlaneProps & { visible:boolean }) {
  return visible ? <CameraPlane {...props} /> : null;
}

export function CameraPlane({ apiBase, width, height, sessionId, active, calibration, registration, onPick }: CameraPlaneProps) {
  const [pixelGuide,setPixelGuide] = useState(true), [cmGuide,setCmGuide] = useState(true), [cursor,setCursor] = useState<Point|null>(null);
  const [failedSession,setFailedSession] = useState("");
  const clipId = useId().replaceAll(":","");
  const grid = useMemo(() => metricGrid(calibration,sessionId,width,height), [calibration,sessionId,width,height]);
  const cursorFrame = useRef<number|null>(null), pendingCursor = useRef<Point|null>(null);
  useEffect(() => () => { if (cursorFrame.current !== null) window.cancelAnimationFrame(cursorFrame.current); }, []);
  function moveCursor(value: Point|null) {
    pendingCursor.current = value;
    if (cursorFrame.current !== null) return;
    cursorFrame.current = window.requestAnimationFrame(() => { cursorFrame.current = null; setCursor(pendingCursor.current); });
  }
  function leaveCursor() {
    if (cursorFrame.current !== null) window.cancelAnimationFrame(cursorFrame.current);
    cursorFrame.current = null; pendingCursor.current = null; setCursor(null);
  }
  const spacing = width >= 1000 ? 200 : 100;
  const xs = Array.from({length:Math.floor((width-1)/spacing)},(_,i)=>(i+1)*spacing);
  const ys = Array.from({length:Math.floor((height-1)/spacing)},(_,i)=>(i+1)*spacing);
  function point(event:MouseEvent<HTMLImageElement>) {
    const box = event.currentTarget.getBoundingClientRect();
    return nativePixel(event.clientX-box.left,event.clientY-box.top,box.width,box.height,width,height);
  }
  const world = cursor && grid && insideHull(cursor,grid.hull) && insidePolygon(cursor,grid.clipPolygon) ? projectPoint(grid.matrix,cursor) : null;
  return <div className={styles.stack}>
    <div className={styles.view}>
      <img width={width} height={height} decoding="async" src={cameraStreamSource(apiBase,sessionId,active)} alt="Live external USB webcam. Pixel guide is not a physical measurement." onMouseMove={event=>moveCursor(point(event))} onMouseLeave={leaveCursor} onError={()=>setFailedSession(sessionId ?? "")} onClick={event=>{const p=point(event);if(active&&p)onPick?.(p);}} />
      <svg className={styles.overlay} viewBox={`0 0 ${width} ${height}`} style={{fontSize:Math.max(14,width/40)}} aria-hidden="true">
        {pixelGuide && <g data-camera-layer="pixels">{xs.map(x=><g key={`x${x}`}><line className={styles.pixel} x1={x} x2={x} y1={0} y2={height}/><text className={styles.label} x={x+5} y={Math.max(20,width/35)}>{x} px</text></g>)}{ys.map(y=><g key={`y${y}`}><line className={styles.pixel} x1={0} x2={width} y1={y} y2={y}/><text className={styles.label} x={6} y={y-6}>{y} px</text></g>)}</g>}
        {grid && cmGuide && <g data-camera-layer="centimetres"><defs><clipPath id={clipId}><polygon points={grid.clipPolygon.map(p=>p.join(",")).join(" ")}/></clipPath></defs><g clipPath={`url(#${clipId})`}>{grid.lines.map(line=><g key={`${line.axis}${line.value}`}><line className={styles.metric} x1={line.start[0]} y1={line.start[1]} x2={line.end[0]} y2={line.end[1]}/><text className={`${styles.label} ${styles.metricLabel}`} x={line.start[0]+5} y={line.start[1]+18}>{line.axis} {line.value} cm</text></g>)}</g><polygon className={styles.hull} points={grid.clipPolygon.map(p=>p.join(",")).join(" ")}/></g>}
        {registration?.proposal && Object.entries(registration.geometry_layers).map(([name, layer]) => <g key={name} data-camera-layer={name}>{layer.candidates?.map((candidate, index) => <polygon key={index} points={candidate.polygon_px.map(p => p.join(",")).join(" ")} fill="none" stroke={name === "tray_boundary" ? "#a855f7" : "#168879"} strokeWidth={3} strokeDasharray={layer.operator_confirmed ? undefined : "8 5"} />)}</g>)}
        {cursor && <g className={styles.crosshair}><line x1={cursor[0]-12} x2={cursor[0]+12} y1={cursor[1]} y2={cursor[1]}/><line x1={cursor[0]} x2={cursor[0]} y1={cursor[1]-12} y2={cursor[1]+12}/></g>}
      </svg>
    </div>
    {failedSession && failedSession === sessionId && <p className={styles.caption} role="alert">The camera preview stream is unavailable. Check capture status or reopen Camera after the connection recovers. No background retry or camera restart was started.</p>}
    {registration && <p role="status">{registration.state.replaceAll("_", " ")}: {registration.reason}</p>}
    <div className={styles.controls}><label><input type="checkbox" checked={pixelGuide} onChange={event=>setPixelGuide(event.target.checked)}/>Pixel guide (px)</label><label><input type="checkbox" checked={!!grid&&cmGuide} disabled={!grid} onChange={event=>setCmGuide(event.target.checked)}/>{grid?.estimated ? "Estimated grid (cm · unvalidated)" : "Measured grid (cm)"}</label><output className={styles.readout} aria-live="off">{cursor ? `Image x ${cursor[0].toFixed(1)}, y ${cursor[1].toFixed(1)} px${world ? ` · ${grid?.estimated ? "estimated " : ""}tank x ${world[0].toFixed(2)}, y ${world[1].toFixed(2)} cm` : ""}` : "Move over the image to inspect coordinates."}</output></div>
    <p className={styles.caption}>{registration?.proposal && grid ? `${grid.spacingCm} cm candidate grid clipped to the surveyed water region. Separate check error ${registration.proposal.calibration.max_error_cm.toFixed(3)} cm; ${registration.mapping_current ? "operator approved, flow admission separate" : "not approved for analysis"}. Grid spacing is not sensor precision.` : grid?.estimated ? `${grid.spacingCm} cm estimated grid from the historical mapping and reported tray bounds. Current alignment and centimetre accuracy are unvalidated; this is a rehearsal overlay, not a measured calibration.` : grid ? `${grid.spacingCm} cm grid, clipped to the fitting-mark hull. Accuracy is limited by the independent check-point error; outside that area no centimetre readout is shown.` : "Pixel origin is image top-left: +x right, +y down. This guide is not centimetre calibration. A measured grid appears only after a valid water-surface mapping in this camera session."}{onPick ? " Click a surveyed mark to append its pixel position below." : ""}</p>
  </div>;
}
