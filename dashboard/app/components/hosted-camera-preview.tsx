"use client";

import { useEffect, useId, useRef, useState, useSyncExternalStore } from "react";
import { HostedCameraController, INITIAL_HOSTED_CAMERA_STATE, LOCAL_CAMERA_COMPANION } from "./hosted-camera-state.ts";
import styles from "./hosted-camera-preview.module.css";

/** Local browser preview, independent of the hosted API's physical-capture capability. */
export function HostedCameraPreview({ active = true, className = "" }: { active?: boolean; className?: string }) {
  const [controller] = useState(() => new HostedCameraController());
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, () => INITIAL_HOSTED_CAMERA_STATE);
  const video = useRef<HTMLVideoElement>(null);
  const id = useId();

  useEffect(() => {
    if (!active) controller.close();
    // Restartable close also handles React's development setup/cleanup cycle.
    return () => controller.close();
  }, [active, controller]);

  useEffect(() => {
    const element = video.current;
    const stream = state.stream;
    if (!element || !stream || !active) return;
    element.srcObject = stream;
    element.play()?.catch(() => controller.playbackFailed(stream));
    return () => { element.pause(); element.srcObject = null; };
  }, [active, controller, state.stream]);

  if (!active) return null;

  return <section className={`${styles.preview} ${className}`} aria-labelledby={`${id}-title`}>
    <header className={styles.heading}>
      <div><h2 id={`${id}-title`}>Camera preview</h2><p id={`${id}-privacy`}>Preview only · frames stay on this device</p></div>
      <span className={styles.status} role="status">{state.status === "live" ? "Live on this device" : state.status === "requesting" ? "Waiting for camera permission…" : "Preview closed"}</span>
    </header>
    <div className={styles.view}>
      {state.stream ? <video ref={video} autoPlay muted playsInline aria-label="Live camera preview, unmirrored and uncropped" aria-describedby={`${id}-privacy ${id}-scope`}
        onLoadedMetadata={event => { if (state.stream) controller.setDimensions(state.stream, event.currentTarget.videoWidth, event.currentTarget.videoHeight); }}
        onError={() => { if (state.stream) controller.playbackFailed(state.stream); }} />
        : <div className={styles.placeholder}><strong>{state.status === "requesting" ? "Allow camera access in your browser" : "See your webcam here"}</strong><p>{state.status === "requesting" ? "You can close this preview while a permission request is open." : "Press Start preview, then choose your USB webcam from the camera list."}</p></div>}
    </div>
    <div className={styles.controls}>
      <button type="button" onClick={() => { void controller.start(); }} disabled={state.status === "requesting" || state.status === "live"}>Start preview</button>
      <button type="button" onClick={controller.close} disabled={state.status === "idle"}>Close preview</button>
      <div className={styles.picker}><label htmlFor={`${id}-camera`}>Camera</label><select id={`${id}-camera`} value={state.selectedDeviceId} disabled={state.status !== "live" || !state.devices.length}
        onChange={event => { if (event.target.value) void controller.start(event.target.value); }}>
        {!state.devices.some(device => device.id === state.selectedDeviceId) ? <option value={state.selectedDeviceId}>{state.cameraLabel || "Grant access to list cameras"}</option> : null}
        {state.devices.map(device => <option key={device.id} value={device.id}>{device.label}</option>)}
      </select></div>
    </div>
    {state.error ? <p className={styles.error} role="alert">{state.error}</p> : null}
    {state.warning ? <p className={styles.note} role="status">{state.warning}</p> : null}
    {state.status === "live" ? <p className={styles.note}>{state.cameraLabel}{state.dimensions ? ` · ${state.dimensions.width} × ${state.dimensions.height} px` : ""}. The view is unmirrored and shows the full camera frame.</p> : null}
    <p className={styles.note} id={`${id}-scope`}>This preview does not upload or record frames, detect a token, calibrate distances, or create a tank trial. No tank is needed to preview.</p>
    <div className={styles.companion}>
      <div><strong>Ready to measure a tank?</strong><p>Run the local Nemo app on this computer for OpenCV tracking, water-surface calibration and recorded trials.</p></div>
      <a href={LOCAL_CAMERA_COMPANION} target="_blank" rel="noopener noreferrer" onClick={controller.close} onAuxClick={controller.close} onContextMenu={controller.close}>Open local camera workspace <span aria-hidden="true">↗</span></a>
      <p className={styles.note}>Opening the local workspace closes this preview first so the local app can use the camera. The link requires the local app to be running on port 3000.</p>
    </div>
  </section>;
}
