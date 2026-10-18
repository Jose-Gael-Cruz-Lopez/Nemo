"use client";

import { useCallback, useEffect, useId, useRef, useState, type ChangeEvent } from "react";
import type { CalibrationReport, CameraStatus } from "./field-workflow-state";
import {
  MAX_SAVED_CALIBRATION_BYTES, acceptSavedCalibrationResult, buildSavedCalibrationCheck,
  parseSavedCalibrationBundle, parseSavedCalibrationList, parseSavedCalibrationText, serializeSavedCalibration,
  type SavedCalibrationBundle, type SavedCalibrationSummary,
} from "./saved-calibration-state.ts";
import styles from "./saved-calibration.module.css";

type Request = <T>(path: string, body?: unknown, options?: { signal?: AbortSignal; independent?: boolean }) => Promise<T>;
export type SavedCalibrationProps = {
  request: Request;
  camera: CameraStatus | null;
  disabled: boolean;
  onApply: (report: CalibrationReport) => void;
  onCheckStart?: () => void;
  onBusyChange?: (busy: boolean) => void;
  checkPixels?: string;
  onCheckPixelsChange?: (pixels: string) => void;
};

/** Mounted only in the local capture workspace; never uploads frames or reference images. */
export function SavedCalibration({ request, camera, disabled, onApply, onCheckStart, onBusyChange, checkPixels, onCheckPixelsChange }: SavedCalibrationProps) {
  const id = useId();
  const [bundle, setBundle] = useState<SavedCalibrationBundle | null>(null);
  const [saved, setSaved] = useState<SavedCalibrationSummary[]>([]);
  const [selected, setSelected] = useState("");
  const [listed, setListed] = useState(false);
  const [ownPixelText, setOwnPixelText] = useState("");
  const pixelText = checkPixels ?? ownPixelText;
  const pixelChange = useRef(onCheckPixelsChange);
  useEffect(() => { pixelChange.current = onCheckPixelsChange; }, [onCheckPixelsChange]);
  const setPixelText = useCallback((text: string) => { setOwnPixelText(text); pixelChange.current?.(text); }, []);
  const [worldText, setWorldText] = useState("");
  const [unchanged, setUnchanged] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const generation = useRef(0);
  const pending = useRef<AbortController | null>(null);
  const mounted = useRef(false);
  const active = useRef(false);
  const onBusy = useRef(onBusyChange);
  useEffect(() => { onBusy.current = onBusyChange; }, [onBusyChange]);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; pending.current?.abort(); onBusy.current?.(false); };
  }, []);
  // Reuse centimetre measurements, but never reuse pixel checks across camera poses/sessions.
  useEffect(() => {
    generation.current++;
    pending.current?.abort();
    const reset = setTimeout(() => { setPixelText(""); setUnchanged(false); setNotice(""); }, 0);
    return () => clearTimeout(reset);
  }, [camera?.session_id, camera?.width, camera?.height, camera?.running, camera?.fresh, setPixelText]);

  // A sibling capture temporarily disables this form. Cancel requests, but keep
  // the operator's already observed pixel checks and water-plane confirmation.
  useEffect(() => {
    if (disabled) { generation.current++; pending.current?.abort(); }
  }, [disabled]);

  function choose(next: SavedCalibrationBundle) {
    generation.current++;
    setBundle(next); setPixelText(""); setWorldText(""); setUnchanged(false); setError("");
    setNotice("Saved measurements loaded. Check alignment before using this mapping.");
  }
  async function run(label: string, task: (signal: AbortSignal, current: () => boolean) => Promise<void>) {
    if (active.current || disabled) return;
    active.current = true;
    const version = generation.current, controller = new AbortController(); pending.current = controller;
    setBusy(label); setError(""); setNotice(""); onBusy.current?.(true);
    const current = () => mounted.current && version === generation.current && !controller.signal.aborted;
    try { await task(controller.signal, current); }
    catch (err) { if (current()) setError(err instanceof Error ? err.message : "The saved mapping could not be checked. Nothing was applied."); }
    finally {
      if (pending.current === controller) pending.current = null;
      active.current = false;
      if (mounted.current) setBusy("");
      onBusy.current?.(false);
    }
  }
  function readFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]; event.target.value = "";
    if (!file) return;
    void run("Reading saved mapping…", async (_signal, current) => {
      if (file.size > MAX_SAVED_CALIBRATION_BYTES) throw new Error("The saved mapping file must be 64 KB or smaller.");
      const parsed = parseSavedCalibrationText(await file.text(), file.size);
      if (current()) choose(parsed);
    });
  }
  function loadList() {
    void run("Finding local mappings…", async (signal, current) => {
      const result = parseSavedCalibrationList(await request<unknown>("/vision/calibrations", undefined, { signal, independent: true }));
      if (!current()) return;
      setSaved(result); setListed(true); setSelected("");
      if (!result.length) setNotice("No saved mappings were found on this Mac. Export the mapping from Megana’s capture laptop, then open that JSON file here.");
    });
  }
  function loadSelected() {
    if (!selected) return;
    void run("Loading saved mapping…", async (signal, current) => {
      const result = parseSavedCalibrationBundle(await request<unknown>(`/vision/calibrations/${encodeURIComponent(selected)}`, undefined, { signal, independent: true }));
      if (current()) choose(result);
    });
  }
  function download() {
    if (!bundle || busy || disabled) return;
    try {
      const content = serializeSavedCalibration(bundle);
      const url = URL.createObjectURL(new Blob([content], { type: "application/json" }));
      const link = document.createElement("a"); link.href = url; link.download = `nemo-${bundle.calibration.calibration_id}.json`;
      link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) { setError(err instanceof Error ? err.message : "The mapping could not be exported."); }
  }
  function revalidate() {
    if (!bundle) return;
    void run("Checking current alignment…", async (signal, current) => {
      const body = buildSavedCalibrationCheck(bundle, camera, pixelText, worldText, unchanged);
      onCheckStart?.();
      const response = await request<unknown>("/vision/calibrations/revalidate", body, { signal, independent: true });
      if (!current()) return;
      const result = acceptSavedCalibrationResult(response, bundle, camera);
      onApply(result);
      setNotice(`Current alignment passed: ${result.max_error_cm.toFixed(2)} cm maximum error. Mapping ${result.calibration_id} is ready for this camera session. Capture a current empty-tank reference before recording.`);
    });
  }
  const locked = disabled || Boolean(busy), old = bundle?.calibration;
  return <section className={styles.panel} aria-labelledby={`${id}-title`}>
    <h4 id={`${id}-title`}>Reuse saved measurements</h4>
    <p className={styles.help}>Load Megana’s saved mapping, then check its alignment against existing surveyed marks. Her recorded inside waterline is 35.56 × 22.86 cm; the saved mapping file is still required.</p>
    <div className={styles.actions}>
      <button type="button" disabled={locked} onClick={loadList}>Find saved mappings on this Mac</button>
      <label className={styles.file}>Open saved mapping JSON<input type="file" accept=".json,application/json" disabled={locked} onChange={readFile} /></label>
    </div>
    {listed && saved.length > 0 && <div className={styles.selection}>
      <label htmlFor={`${id}-saved`}>Mappings saved on this Mac<select id={`${id}-saved`} value={selected} disabled={locked} onChange={event => setSelected(event.target.value)}>
        <option value="">Choose a saved mapping</option>
        {saved.map(item => <option key={item.calibration_id} value={item.calibration_id}>{item.calibration_id} · {item.image_size_px.join(" × ")} · historical {item.approved ? "pass" : "fail"}</option>)}
      </select></label>
      <button type="button" disabled={locked || !selected} onClick={loadSelected}>Load mapping</button>
    </div>}
    {old && <>
      <dl className={styles.metadata}>
        <dt>Original mapping</dt><dd><code>{old.calibration_id}</code></dd>
        <dt>Saved frame</dt><dd>{old.image_size_px.join(" × ")} px</dd>
        <dt>Saved tolerance</dt><dd>{old.max_allowed_error_cm.toFixed(2)} cm · locked</dd>
        <dt>Historical errors</dt><dd>{old.mean_error_cm.toFixed(2)} cm mean · {old.max_error_cm.toFixed(2)} cm maximum · {old.validation_count} checks</dd>
      </dl>
      <p className={styles.help}>Historical errors do not approve the current camera pose. This check keeps the saved matrix and tolerance unchanged; it does not refit them.</p>
      <button type="button" disabled={locked} onClick={download}>Export this mapping</button>
      <div className={styles.checks}>
        <label htmlFor={`${id}-pixels`}>Current pixels of three or more existing check marks<textarea id={`${id}-pixels`} rows={4} value={pixelText} disabled={locked} onChange={event => setPixelText(event.target.value)} placeholder="x, y — one point per line" /></label>
        <label htmlFor={`${id}-world`}>Their saved surveyed positions in cm, in the same order<textarea id={`${id}-world`} rows={4} value={worldText} disabled={locked} onChange={event => setWorldText(event.target.value)} placeholder="x, y — reuse the original measured coordinates" /></label>
      </div>
      <p className={styles.help}>Read current pixels from the camera view. Reuse the measured centimetre positions of those marks. Do not calculate the check positions from the saved mapping.</p>
      <label className={styles.confirm}><input type="checkbox" checked={unchanged} disabled={locked} onChange={event => setUnchanged(event.target.checked)} />The camera views the same surveyed water-surface plane and waterline.</label>
      <button type="button" disabled={locked || !old.approved || !camera?.running || !camera.fresh} onClick={revalidate}>Check alignment, then use mapping</button>
    </>}
    <p className={styles.privacy}>Mapping metadata stays with the local capture service. Frames, reference images, and tokens are not included in this file.</p>
    {busy && <p role="status">{busy}</p>}
    {error && <p role="alert" className={styles.error}>{error}</p>}
    {notice && <p role="status" className={styles.notice}>{notice}</p>}
  </section>;
}
