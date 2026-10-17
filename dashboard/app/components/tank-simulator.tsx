"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import { resetTankCaptureCursor, tankHeadline, tankSceneIsCurrent, validateTankScene, visibleTankPaths, type TankLayout, type TankScene } from "./tank-simulator-state";
import type { TankSceneView } from "./tank-simulator-scene";
import styles from "./tank-simulator.module.css";

const Scene = dynamic(() => import("./tank-simulator-scene"), { ssr: false, loading: () => <div className={styles.loading} role="status">Loading the 3D viewer… Saved evidence stays unchanged.</div> });
type Request = <T>(path: string, body?: unknown, options?: { signal?: AbortSignal; independent?: boolean }) => Promise<T>;
type Props = { comparisonId: string; evaluationHash: string; current: boolean; request: Request; operatorConnected: boolean; onRequireOperator: () => void; measured: boolean };
const text = (error: unknown) => error instanceof Error ? error.message : "The saved scene could not be read. Reload explicitly to retry.";

function SceneEvidence({ report, selected }: { report: TankScene; selected: TankLayout }) {
  const result = tankHeadline(report, selected);
  return <div className={styles.evidence}>
    <div><span>Predicted protected-zone entries</span><strong>{result.unsupportedParticles ? "Withheld" : `${result.predictedEntries} / ${result.predictedParticles}`}</strong><small>All declared sources · frozen full ensemble · {selected} layout{result.unsupportedParticles ? ` · ${result.unsupportedParticles} unsupported particles` : ""}</small></div>
    <div><span>Operator-reported physical outcomes</span><strong>{result.physicalReleased ? `${result.physicalEntries} entered / ${result.physicalReleased} released` : "Not captured"}</strong><small>{result.physicalReleased} / {result.physicalPlanned} planned releases logged · {result.missingPhysical} still missing</small></div>
  </div>;
}

function ReadyTankSimulator({ report, current }: { report: TankScene; current: boolean }) {
  const container = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState<TankLayout>("baseline");
  const [source, setSource] = useState("all");
  const [paths, setPaths] = useState(true), [grid, setGrid] = useState(true), [flow, setFlow] = useState(false), [hardware, setHardware] = useState(true);
  const [labels, setLabels] = useState(true);
  const [modelTime, setModelTime] = useState(0), [captureTime, setCaptureTime] = useState(0);
  const [clock, setClock] = useState<"model" | "capture">("model");
  const [recordingId, setRecordingId] = useState("");
  const [playing, setPlaying] = useState(false), [speed, setSpeed] = useState(1);
  const [visible, setVisible] = useState(true), [documentVisible, setDocumentVisible] = useState(true), [reducedMotion, setReducedMotion] = useState(false);
  const [camera, setCamera] = useState<"orbit" | "overhead">("orbit"), [cameraRevision, setCameraRevision] = useState(0);
  const [unavailable, setUnavailable] = useState("");
  const recorded = report.actual.recordings.filter(row => row.layout === selected && (source === "all" || row.source_id === source) && row.segments.length > 0);
  const recording = recorded.find(row => row.recording_id === recordingId) ?? recorded[0];
  const captureEnd = recording ? Math.max(...recording.segments.flatMap(segment => segment.points.map(point => point.t_s))) : 0;
  const time = clock === "model" ? modelTime : Math.min(captureTime, captureEnd);
  const end = clock === "model" ? report.simulation.horizon_s : captureEnd;
  const active = visible && documentVisible;
  const playback = useRef({ clock, speed, end, active, reducedMotion, time });
  useEffect(() => { playback.current = { clock, speed, end, active, reducedMotion, time }; }, [clock, speed, end, active, reducedMotion, time]);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const preference = () => setReducedMotion(media.matches);
    const visibility = () => setDocumentVisible(document.visibilityState !== "hidden");
    preference(); visibility(); media.addEventListener("change", preference); document.addEventListener("visibilitychange", visibility);
    const observer = new IntersectionObserver(entries => setVisible(entries.some(entry => entry.isIntersecting)), { threshold: 0.05 });
    if (container.current) observer.observe(container.current);
    return () => { observer.disconnect(); media.removeEventListener("change", preference); document.removeEventListener("visibilitychange", visibility); };
  }, []);
  useEffect(() => {
    if (!playing || !active || reducedMotion || unavailable) return;
    let frame = 0, previous = 0, lastUpdate = 0;
    function tick(now: number) {
      const settings = playback.current;
      if (!settings.active || settings.reducedMotion) return;
      if (settings.time >= settings.end) { setPlaying(false); return; }
      if (!previous) previous = now;
      if (!lastUpdate) lastUpdate = now;
      // Limit React/render updates to 30 Hz; pause/resume discards hidden time.
      if (now - lastUpdate >= 1000 / 30) {
        const delta = Math.min((now - previous) / 1000, 0.1) * settings.speed;
        const update = (value: number) => Math.min(settings.end, value + delta);
        if (settings.clock === "model") setModelTime(update); else setCaptureTime(update);
        previous = now; lastUpdate = now;
      }
      frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, active, reducedMotion, unavailable]);
  const failure = useCallback((message: string) => { setUnavailable(message); setPlaying(false); }, []);
  function setTime(value: number) { setPlaying(false); if (clock === "model") setModelTime(value); else setCaptureTime(value); }
  function play() {
    if (time >= end) { if (clock === "model") setModelTime(0); else setCaptureTime(0); }
    setPlaying(value => !value);
  }
  function resetCapture() { const cursor = resetTankCaptureCursor(); setCaptureTime(cursor.captureTime); setRecordingId(cursor.recordingId); setPlaying(false); }
  function changeLayout(value: TankLayout) { setSelected(value); resetCapture(); }
  function changeSource(value: string) { setSource(value); resetCapture(); }
  const view: TankSceneView = { layout: selected, source, paths, grid, flow, hardware, labels, clock, time, recordingId: recording?.recording_id ?? "", camera, cameraRevision, active };
  const displayed = visibleTankPaths(report, selected, source), drawable = displayed.filter(path => path.points.length > 0);
  return <div ref={container} className={styles.body}>
    <div className={styles.topline}><span className={`pill ${report.data_origin === "SYNTHETIC" ? "amber" : "neutral"}`}>{report.data_origin === "SYNTHETIC" ? "SYNTHETIC REHEARSAL" : "MEASURED INPUTS · CAPTURE UNVERIFIED"}</span><span>{report.simulation.horizon_s}s model horizon · {report.geometry.bounds_cm.x_max_cm - report.geometry.bounds_cm.x_min_cm} × {report.geometry.bounds_cm.y_max_cm - report.geometry.bounds_cm.y_min_cm} cm saved water plane</span></div>
    {!current && <p className={styles.notice}>Archived comparison. This viewer replays its frozen evidence; it cannot add trials or change the plan.</p>}
    <div className={styles.selectors}><label>Layout<select value={selected} onChange={event => changeLayout(event.target.value as TankLayout)}><option value="baseline">Baseline</option><option value="intervention">Intervention</option></select></label><label>Release source<select value={source} onChange={event => changeSource(event.target.value)}><option value="all">All declared sources</option>{report.geometry.sources.map(item => <option key={item.id} value={item.id}>Source {item.id}</option>)}</select></label><div className={styles.viewButtons}><button className="secondary-button" onClick={() => { setCamera("overhead"); setCameraRevision(value => value + 1); }}>Overhead</button><button className="secondary-button" onClick={() => { setCamera("orbit"); setCameraRevision(value => value + 1); }}>Reset 3D view</button></div></div>
    {unavailable ? <div className={styles.loading} role="status"><p>{unavailable}</p><button className="secondary-button" onClick={() => setUnavailable("")}>Retry 3D graphics</button></div> : <div className={styles.viewport}><Scene report={report} view={view} onUnavailable={failure} /><div className={styles.sceneLabels} aria-hidden="true"><span>Saved XY · centimetres</span><span>Coordinates follow the tank plane</span></div><span className={styles.schematic}>Equipment schematic · depth unknown</span></div>}
    <div className={styles.legend}><span><i style={{ background: "#c65c50" }} />Token playback</span><span><i style={{ background: "#5c83b3" }} />Baseline model</span><span><i style={{ background: "#168879" }} />Intervention model</span><span><i style={{ background: "#e3ad7f" }} />Protected-zone proxy</span><span><i style={{ background: "#479d92" }} />Collector footprint</span>{report.actual.status === "RECORDED_TRACKS_AVAILABLE" && <span><i style={{ background: "#9a5d35" }} />Recorded samples · separate capture clock</span>}</div>
    <fieldset className={styles.toggles}><legend className="sr-only">3D visibility controls</legend>{[["Saved paths", paths, setPaths], ["Coordinate grid", grid, setGrid], ["Labels", labels, setLabels], ["Frozen flow vectors", flow, setFlow], ["Schematic equipment", hardware, setHardware]].map(([label, checked, setter]) => <label key={label as string}><input type="checkbox" checked={checked as boolean} onChange={event => (setter as (value: boolean) => void)(event.target.checked)} />{label as string}</label>)}</fieldset>
    <p className={styles.note}>Equipment outside the water-plane footprint is an illustration, not its measured placement. In the real rig, keep the USB webcam dry and fixed; operate the rated submersible pump underwater by its own manual power connection.</p>
    <div className={styles.playback}>
      <fieldset className={styles.clocks}><legend>Playback clock</legend><label><input type="radio" name={`clock-${report.comparison_id}`} checked={clock === "model"} onChange={() => { setClock("model"); setPlaying(false); }} />Model release · t = 0</label><label><input type="radio" name={`clock-${report.comparison_id}`} checked={clock === "capture"} disabled={!recorded.length} onChange={() => { setClock("capture"); setPlaying(false); }} />Recorded capture · separate clock</label></fieldset>
      {clock === "capture" && <label>Recording<select value={recording?.recording_id ?? ""} onChange={event => { setRecordingId(event.target.value); setCaptureTime(0); setPlaying(false); }}>{recorded.length ? recorded.map(row => <option value={row.recording_id} key={row.recording_id}>{row.recording_id} · source {row.source_id}</option>) : <option value="">No matching recorded track</option>}</select></label>}
      <div className={styles.transport}><button className="primary-button" disabled={reducedMotion || !!unavailable || end <= 0 || !active} onClick={play}>{playing && time < end ? "Pause" : time >= end ? "Replay" : "Play saved path"}</button><label className={styles.scrub}>{clock === "model" ? "Model elapsed time" : "Capture elapsed time"}<input type="range" min={0} max={Math.max(end, 0.01)} step={0.05} value={Math.min(time, end)} disabled={end <= 0} onChange={event => setTime(Number(event.target.value))} aria-valuetext={`${Math.min(time, end).toFixed(2)} seconds on the ${clock === "model" ? "model release" : "unaligned capture"} clock`} /></label><output className={styles.timer} aria-label="Playback time">{Math.min(time, end).toFixed(2)} / {end.toFixed(2)} s</output><label>Speed<select value={speed} onChange={event => setSpeed(Number(event.target.value))}><option value={0.5}>0.5×</option><option value={1}>1×</option><option value={2}>2×</option></select></label></div>
      <p className={styles.note}>{reducedMotion ? "Reduced motion is enabled. Use the time slider to inspect saved samples without animation. " : !active ? "Playback rendering pauses while this viewer is outside the viewport or the tab is hidden. " : ""}{clock === "model" ? "Playback joins saved display samples with straight segments. No new motion is simulated in this viewer; tokens disappear at the last supported display sample." : "Brown points are recorded samples, held without interpolation only inside a continuous segment. Tracking gaps stay empty. Capture time is not aligned to token release; no predicted-versus-observed positional error is calculated."}</p>
    </div>
    <SceneEvidence report={report} selected={selected} />
    <p className={styles.note}><strong>{drawable.length} / {displayed.length} representative routes available for the selected view.</strong> Visibility and playback never change the full-ensemble counts above. These decimated routes stop conservatively at the first saved event prefix; they cannot establish exact contact time or collection efficiency.</p>
    <div className={styles.actual}><strong>{report.actual.status === "NOT_CAPTURED" ? "Real tank comparison: not captured yet" : report.actual.status === "REPORTED_COUNTS_ONLY" ? "Real tank comparison: reported counts only" : "Recorded tank tracks available · capture not independently verified"}</strong><p>{report.actual.status === "NOT_CAPTURED" ? "No physical trial or measured path is invented. Commission the camera and water-plane calibration, freeze each layout’s recorded flow, and link a fresh recording to a real trial before comparing measured motion." : report.actual.status === "REPORTED_COUNTS_ONLY" ? "The ledger contains physical outcomes, but no usable linked continuous track is available for playback. Outcomes are operator reports, not camera-verified results." : "Linked camera recordings remain on their own capture clocks. Source labels come from the operator’s release log; they are not inferred by playback."}</p><small>{report.results.by_origin.SYNTHETIC_DEMO.plan.recorded_total} synthetic ledger records remain separate from physical outcomes.</small></div>
    <details className="details-panel"><summary>What this 3D model represents</summary><ul className="reason-list"><li>The saved water-plane footprint, source regions, protected-zone proxy and collector areas use centimetre coordinates.</li><li>Walls, water depth, USB camera, mounting arm, manually powered pump, tubing and coral shape are schematic context. Their vertical size and equipment placement are not measured.</li><li>This is a surface-path replay of the existing tank model, not a 3D fluid simulation. The physical rig uses a USB webcam and a manual pump; no Arduino or actuator is commanded.</li><li>Flow arrows are fixed-field node glyphs with normalized display lengths; they do not represent changing currents or measured volumetric pump flow.</li>{report.limitations.map((limit, index) => <li key={index}>{limit}</li>)}</ul><dl className={styles.provenance}><dt>Comparison</dt><dd>{report.comparison_id}</dd><dt>Evaluation snapshot</dt><dd>{report.evaluation_snapshot_hash}</dd><dt>Scene snapshot</dt><dd>{report.scene_sha256}</dd></dl></details>
  </div>;
}

export function TankSimulator({ comparisonId, evaluationHash, current: parentCurrent, request, operatorConnected, onRequireOperator, measured }: Props) {
  const [open, setOpen] = useState(false), [report, setReport] = useState<TankScene | null>(null), [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0), [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!open || measured && !operatorConnected) return;
    const controller = new AbortController();
    void request<unknown>(`/prevention/comparisons/${encodeURIComponent(comparisonId)}/scene?evaluation_snapshot_hash=${encodeURIComponent(evaluationHash)}`, undefined, { signal: controller.signal }).then(value => {
      if (!controller.signal.aborted) { setReport(validateTankScene(value, { comparisonId, evaluationHash })); setError(""); }
    }).catch(cause => { if (!controller.signal.aborted) setError(text(cause)); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [open, comparisonId, evaluationHash, parentCurrent, request, measured, operatorConnected, attempt]);
  function toggle() { if (!open) { setError(""); setReport(null); setLoading(true); } setOpen(value => !value); }
  const current = report?.comparison_id === comparisonId && report.evaluation_snapshot_hash === evaluationHash ? report : null;
  return <section className="card" aria-label="3D tank experiment replay"><div className={`card-header ${styles.header}`}><div><h2 className="card-title">Your tank, explained in 3D</h2><p className="card-subtitle">Replay saved paths. Compare predictions with separately recorded evidence.</p></div><button className="secondary-button" aria-expanded={open} onClick={toggle}>{open ? "Close 3D tank" : "Open 3D tank"}</button></div>{open && <>
    {measured && !operatorConnected ? <div className={styles.body}><p>Connect operator access to read linked physical recording coordinates.</p><button className="primary-button" onClick={onRequireOperator}>Connect operator</button></div> : error ? <div className={styles.body} role="alert"><p>{error}</p><button className="secondary-button" onClick={() => { setError(""); setReport(null); setLoading(true); setAttempt(value => value + 1); }}>Reload the saved scene</button></div> : current ? <ReadyTankSimulator key={current.scene_sha256} report={current} current={tankSceneIsCurrent(parentCurrent, current.is_current)} /> : <p className={styles.loading} role="status">{loading ? "Reading the frozen comparison and recording evidence…" : "Waiting for the saved scene…"}</p>}
  </>}</section>;
}
