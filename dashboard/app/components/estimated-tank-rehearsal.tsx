"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { WaterMapping } from "./camera-grid-state";
import type { CameraStatus, TokenReference } from "./field-workflow-state";
import type { SavedCalibrationBundle } from "./saved-calibration-state";
import {
  ESTIMATED_TRAY_BOUNDS, buildEstimatedRehearsalRequest, estimatedTrayMapping, parseEstimatedRehearsal, rehearsalSegments,
  type EstimatedRehearsal, type RehearsalBounds,
} from "./estimated-tank-rehearsal-state.ts";
import styles from "./estimated-tank-rehearsal.module.css";

type Request = <T>(path: string, body?: unknown, options?: { signal?: AbortSignal; independent?: boolean }) => Promise<T>;
export type EstimatedTankRehearsalProps = {
  request: Request; camera: CameraStatus | null; source: SavedCalibrationBundle | null; reference: TokenReference | null;
  bounds?: RehearsalBounds; disabled: boolean; onBusyChange?: (busy: boolean) => void; onEstimatedMapping?: (mapping: WaterMapping | null) => void;
};
function message(error: unknown) { return error instanceof Error ? error.message : "The estimated rehearsal could not be recorded."; }

export function RehearsalPlot({ result, bounds = ESTIMATED_TRAY_BOUNDS }: { result: EstimatedRehearsal; bounds?: RehearsalBounds }) {
  const clip = useId().replaceAll(":", "");
  const scale = Math.min(510 / (bounds.x_max_cm - bounds.x_min_cm), 328 / (bounds.y_max_cm - bounds.y_min_cm));
  const plotWidth = (bounds.x_max_cm - bounds.x_min_cm) * scale, plotHeight = (bounds.y_max_cm - bounds.y_min_cm) * scale;
  const xy = (x: number, y: number) => [50 + plotWidth - (x - bounds.x_min_cm) * scale, 25 + plotHeight - (y - bounds.y_min_cm) * scale];
  const ticks = (start: number, end: number) => Array.from({ length: Math.min(21, Math.floor(end/10)-Math.ceil(start/10)+1) }, (_, i) => (Math.ceil(start/10)+i)*10);
  const observed = result.points.filter(point => point.observed);
  const segments = rehearsalSegments(result.points);
  const outside = observed.filter(point => point.estimated_x_cm < bounds.x_min_cm || point.estimated_x_cm > bounds.x_max_cm || point.estimated_y_cm < bounds.y_min_cm || point.estimated_y_cm > bounds.y_max_cm).length;
  return <figure className={styles.figure}>
    <svg role="img" aria-label="Actual captured cap positions shown in estimated, unvalidated tank coordinates" viewBox="0 0 610 410">
      <defs><clipPath id={clip}><rect x="50" y="25" width={plotWidth} height={plotHeight} /></clipPath></defs>
      <rect className={styles.tank} x="50" y="25" width={plotWidth} height={plotHeight} />
      {ticks(bounds.x_min_cm,bounds.x_max_cm).map(x => <g key={`x-${x}`}><line className={styles.grid} x1={xy(x,0)[0]} x2={xy(x,0)[0]} y1="25" y2={25+plotHeight} /><text x={xy(x,0)[0]} y={45+plotHeight} textAnchor="middle">{x}</text></g>)}
      {ticks(bounds.y_min_cm,bounds.y_max_cm).map(y => <g key={`y-${y}`}><line className={styles.grid} x1="50" x2={50+plotWidth} y1={xy(bounds.x_min_cm,y)[1]} y2={xy(bounds.x_min_cm,y)[1]} /><text x="40" y={xy(bounds.x_min_cm,y)[1]+4} textAnchor="end">{y}</text></g>)}
      <g clipPath={`url(#${clip})`}>
        {segments.filter(segment => segment.length > 1).map((segment, i) => <polyline key={i} className={styles.path} points={segment.map(point => xy(point.estimated_x_cm, point.estimated_y_cm).join(",")).join(" ")} />)}
        {observed.map(point => <circle key={point.frame_id} className={styles.point} cx={xy(point.estimated_x_cm,point.estimated_y_cm)[0]} cy={xy(point.estimated_x_cm,point.estimated_y_cm)[1]} r="3"><title>{`t ${point.t_s.toFixed(2)} s · pixel ${point.pixel_x.toFixed(1)}, ${point.pixel_y.toFixed(1)} · estimated ${point.estimated_x_cm.toFixed(2)}, ${point.estimated_y_cm.toFixed(2)} cm`}</title></circle>)}
      </g>
      <text x="305" y="395" textAnchor="middle">Estimated x (cm) · increases toward the left wall</text>
      <text transform="translate(14 190) rotate(-90)" textAnchor="middle">Estimated y (cm)</text>
    </svg>
    <figcaption>Dots are accepted camera detections. Lines join only consecutive detections in the same track; gaps and identity breaks stay disconnected. Coordinates use the historical mapping and have unknown current accuracy. The origin is the pump-side bottom-right corner.{outside > 0 ? ` ${outside} accepted detection${outside === 1 ? " is" : "s are"} outside the estimated tray bounds and clipped from this plot.` : ""}</figcaption>
  </figure>;
}

/** Explicit, local-only capture; its record can never replace the measured commissioning draft. */
export function EstimatedTankRehearsal({ request, camera, source, reference, bounds = ESTIMATED_TRAY_BOUNDS, disabled, onBusyChange, onEstimatedMapping }: EstimatedTankRehearsalProps) {
  const id = useId();
  const [duration, setDuration] = useState("5"), [busy, setBusy] = useState(false);
  const [result, setResult] = useState<EstimatedRehearsal | null>(null), [error, setError] = useState("");
  const generation = useRef(0), pending = useRef<AbortController | null>(null), active = useRef(false), mounted = useRef(false), shownGrid = useRef(false);
  const callbacks = useRef({ onBusyChange, onEstimatedMapping });
  useEffect(() => { callbacks.current = { onBusyChange, onEstimatedMapping }; }, [onBusyChange, onEstimatedMapping]);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; pending.current?.abort(); callbacks.current.onBusyChange?.(false); if (shownGrid.current) callbacks.current.onEstimatedMapping?.(null); };
  }, []);
  useEffect(() => {
    generation.current++; pending.current?.abort();
    if (shownGrid.current) { shownGrid.current = false; callbacks.current.onEstimatedMapping?.(null); }
    const reset = setTimeout(() => { setResult(null); setError(""); }, 0);
    return () => clearTimeout(reset);
  }, [source?.calibration_json, camera?.session_id, camera?.width, camera?.height, camera?.running, camera?.fresh, reference?.reference_id, bounds.x_min_cm, bounds.x_max_cm, bounds.y_min_cm, bounds.y_max_cm]);
  // Sibling captures disable this control without erasing the last archival rehearsal.
  useEffect(() => { if (disabled) { generation.current++; pending.current?.abort(); } }, [disabled]);
  const gridProblem = useMemo(() => { try { estimatedTrayMapping(source, camera, bounds); return ""; } catch (err) { return message(err); } }, [source, camera, bounds]);
  const captureProblem = useMemo(() => { try { buildEstimatedRehearsalRequest(source, camera, reference, duration, bounds); return ""; } catch (err) { return message(err); } }, [source, camera, reference, duration, bounds]);
  const locked = disabled || busy;
  function showGrid() {
    if (locked) return;
    try { callbacks.current.onEstimatedMapping?.(estimatedTrayMapping(source, camera, bounds)); shownGrid.current = true; setError(""); }
    catch (err) { setError(message(err)); }
  }
  async function record() {
    if (disabled || active.current) return;
    let body;
    try { body = buildEstimatedRehearsalRequest(source, camera, reference, duration, bounds); } catch (err) { setError(message(err)); return; }
    active.current = true;
    const version = generation.current, controller = new AbortController(); pending.current = controller;
    setBusy(true); setError(""); setResult(null); callbacks.current.onBusyChange?.(true);
    try {
      const response = await request<unknown>("/camera/rehearsals", body, { signal: controller.signal, independent: true });
      if (mounted.current && generation.current === version && !controller.signal.aborted) setResult(parseEstimatedRehearsal(response, source, camera));
    } catch (err) { if (mounted.current && generation.current === version && !controller.signal.aborted) setError(message(err)); }
    finally {
      if (pending.current === controller) pending.current = null;
      active.current = false;
      if (mounted.current) setBusy(false);
      callbacks.current.onBusyChange?.(false);
    }
  }
  return <section className={styles.panel} aria-labelledby={`${id}-heading`}>
    <div className={styles.heading}><h4 id={`${id}-heading`}>Estimated tank rehearsal</h4><span>Unvalidated</span></div>
    <p className={styles.help}>Use the saved {(bounds.x_max_cm-bounds.x_min_cm).toFixed(2)} × {(bounds.y_max_cm-bounds.y_min_cm).toFixed(2)} cm tray and mapping as an approximation. This avoids repeating the survey; it does not verify today’s camera alignment or centimetre accuracy.</p>
    <div className={styles.actions}><button type="button" disabled={locked || Boolean(gridProblem) || !onEstimatedMapping} onClick={showGrid}>Use estimated grid</button><button type="button" disabled={locked || !onEstimatedMapping} onClick={() => { shownGrid.current = false; callbacks.current.onEstimatedMapping?.(null); }}>Clear estimated grid</button></div>
    {gridProblem && <p className={styles.help}>{gridProblem}</p>}
    <div className={styles.actions}><label htmlFor={`${id}-duration`}>Capture duration (seconds)<input id={`${id}-duration`} type="number" min="1" max="10" step="1" value={duration} disabled={locked} onChange={event => setDuration(event.target.value)} /></label><button type="button" disabled={locked || Boolean(captureProblem)} onClick={record}>Record estimated rehearsal</button></div>
    {captureProblem && !gridProblem && <p className={styles.help}>{captureProblem}</p>}
    <p className={styles.help}>Keep one cap visible and free to move; keep hands out of the view. Frames stay on this Mac. A cap trapped at the mesh or strap does not establish water flow.</p>
    {busy && <p role="status" className={styles.notice}>Recording local camera detections… keep the view clear.</p>}
    {error && <p role="alert" className={styles.error}>{error}</p>}
    {result && <div className={styles.result}>
      <h5>Recorded rehearsal · unvalidated</h5>
      <dl><dt>Local record</dt><dd><code>{result.id}</code></dd><dt>Detection accounting</dt><dd>{result.observed} accepted detections · {result.frames-result.observed} gap frames · {result.frames} frames</dd><dt>Capture window</dt><dd>{result.duration_s} s · {new Date(result.recorded_at*1000).toLocaleString()}</dd><dt>Timing</dt><dd>Host receipt timestamps; exposure timing is unknown.</dd></dl>
      {result.observed > 1 ? <RehearsalPlot result={result} bounds={bounds} /> : <p className={styles.notice}>{result.observed === 0 ? "No cap position was accepted. This capture contains no trajectory." : "Only one cap position was detected; no movement can be shown."}</p>}
      <p className={styles.warning}>This is an estimated rehearsal, not an accepted tank trial. It cannot train measured flow, identify a validated source, or create a live case. Independent alignment and drift checks are still needed for those claims.</p>
      <details><summary>Capture warnings</summary><ul>{result.warnings.map((warning,index) => <li key={index}>{warning}</li>)}</ul></details>
    </div>}
  </section>;
}
