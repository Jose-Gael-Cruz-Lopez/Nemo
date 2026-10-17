"use client";

/**
 * Guided field commissioning. Each step calls an existing API endpoint; the new
 * /field-sessions endpoints only re-verify those artifacts and freeze a receipt.
 * Lane 3 mounts this component; props are documented in docs/field-commissioning.md.
 */
import Image from "next/image";
import { useCallback, useEffect, useRef, useState, type MouseEvent, type ReactNode } from "react";
import {
  ATTESTATION_KEYS, DRAFT_KEY, addRecording, buildCalibrationRequest, buildFieldRequest, buildFlowRequest, buildProfile, canFreeze,
  decodeDraft, deriveSteps, encodeDraft, failureNotice, invalidateAfter, newDraft, parseCalibration, parseCameraStatus, parseCase,
  parseFlow, parseManifestDetail, parsePreflight, parseProfile, parseRecording, parseRigCheck, previewPixel, requestKey,
  type AttestationKey, type CameraStatus, type Draft, type LengthUnit, type ManifestDetail, type Preflight, type StepId, type StepView,
} from "./field-workflow-state";
import styles from "./field-workflow.module.css";

type Request = <T>(path: string, body?: unknown, options?: { signal?: AbortSignal; independent?: boolean }) => Promise<T>;
export type FieldWorkflowProps = {
  /** The page's request helper: prefixes /api/v1 and adds the in-memory operator token. */
  request: Request;
  /** API origin, used only for the latest-frame preview image. */
  apiBase: string;
  operatorConnected: boolean;
  onRequireOperator: () => void;
  onBusyChange?: (busy: boolean) => void;
  onOpenCase?: (caseId: string) => void;
  blocked?: boolean;
};

const TITLES: Record<StepId, string> = {
  camera_session: "Select the camera session",
  water_plane_mapping: "Map the water surface",
  drift_recordings: "Record training and validation drift",
  recorded_flow: "Fit the recorded flow",
  measured_profile: "Admit the measured profile",
  rig_state: "Confirm the rig is undisturbed",
  first_source_observation: "Record the first source observation",
  operator_attestations: "Confirm the physical setup",
};
const ATTESTATION_TEXT: Record<AttestationKey, string> = {
  waterline_unchanged: "The waterline is at the measured mark.",
  pump_setting_unchanged: "The pump dial and outlet are unchanged.",
  hose_and_pocket_unchanged: "The hose and retention pocket are in their measured positions.",
  camera_and_light_unchanged: "The camera mount and lighting are unchanged.",
  coordinates_measured_in_cm: "I measured every coordinate myself, in the unit selected above.",
};
const RIG_CHECKS = ATTESTATION_KEYS.filter(key => key !== "coordinates_measured_in_cm");
const STATE_LABEL: Record<StepView["state"], string> = { done: "Passed", blocked: "Blocked", missing: "Missing", server: "Server check" };

function loadDraft(): Draft {
  try { return decodeDraft(sessionStorage.getItem(DRAFT_KEY)) || newDraft(); } catch { return newDraft(); }
}

function Step({ item, n, children }: { item: StepView; n: number; children: ReactNode }) {
  return <section className={styles.step} data-state={item.state} aria-labelledby={`field-step-${item.id}`}>
    <div className={styles.stepHead}><h3 id={`field-step-${item.id}`}><span className={styles.index}>{String(n).padStart(2, "0")}</span>{TITLES[item.id]}</h3><span className={styles.badge} data-state={item.state}>{STATE_LABEL[item.state]}</span></div>
    {item.message && <p className={styles.explain}>{item.message}</p>}
    {item.state !== "done" && item.help && <p className={styles.help}>{item.help}</p>}
    {children}
  </section>;
}

export function FieldWorkflow({ request, apiBase, operatorConnected, onRequireOperator, onBusyChange, onOpenCase, blocked = false }: FieldWorkflowProps) {
  // Restored after mount: the server render has no sessionStorage, so reading it during render would not hydrate.
  const [draft, setDraft] = useState<Draft>(newDraft);
  const [restored, setRestored] = useState(false);
  const [camera, setCamera] = useState<CameraStatus | null>(null);
  const [preflight, setPreflight] = useState<Preflight | null>(null);
  const [preflightKey, setPreflightKey] = useState("");
  const [receipt, setReceipt] = useState<ManifestDetail | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pickTarget, setPickTarget] = useState<"mapping" | "check">("mapping");
  const [rigChecks, setRigChecks] = useState<Record<string, boolean>>({});
  const [tick, setTick] = useState(0);
  const mounted = useRef(true);

  useEffect(() => {
    const restore = setTimeout(() => { setDraft(loadDraft()); setRestored(true); }, 0);
    return () => clearTimeout(restore);
  }, []);
  useEffect(() => {
    if (!restored) return; // Never overwrite a saved draft with the initial empty one.
    try { sessionStorage.setItem(DRAFT_KEY, encodeDraft(draft)); } catch { /* Private mode: the draft stays in memory. */ }
  }, [draft, restored]);

  const refreshCamera = useCallback(async () => {
    try {
      const status = await request<{ camera: unknown }>("/status", undefined, { independent: true });
      if (mounted.current) { setCamera(parseCameraStatus(status.camera)); setTick(value => value + 1); }
    } catch { if (mounted.current) setCamera(null); }
  }, [request]);

  useEffect(() => {
    mounted.current = true;
    const first = setTimeout(() => void refreshCamera(), 0);
    const timer = setInterval(() => void refreshCamera(), 3000);
    return () => { mounted.current = false; clearTimeout(first); clearInterval(timer); };
  }, [refreshCamera]);

  useEffect(() => {
    if (!draft.manifestId) return;
    const controller = new AbortController();
    request<unknown>(`/field-sessions/${encodeURIComponent(draft.manifestId)}`, undefined, { signal: controller.signal })
      .then(value => setReceipt(parseManifestDetail(value)))
      .catch(() => { if (!controller.signal.aborted) setReceipt(null); });
    return () => controller.abort();
  }, [draft.manifestId, request]);

  useEffect(() => () => onBusyChange?.(false), [onBusyChange]);

  async function run(label: string, action: () => Promise<void>) {
    if (!operatorConnected) { onRequireOperator(); return; }
    setBusy(label); onBusyChange?.(true); setError(""); setNotice("");
    try { await action(); }
    catch (cause) { setError(failureNotice(cause).message); }
    finally { setBusy(""); onBusyChange?.(false); void refreshCamera(); }
  }
  const update = (change: (current: Draft) => Draft) => setDraft(current => change(current));
  const field = <K extends keyof Draft>(key: K) => (value: Draft[K]) => update(current => ({ ...current, [key]: value }));
  const locked = !!busy || blocked || !restored;
  const steps = deriveSteps(draft, camera, preflight, preflightKey);
  const view = (id: StepId) => steps.find(step => step.id === id)!;
  const sessionCurrent = !!camera?.fresh && camera.session_id === draft.cameraSessionId;
  const duration = Number(draft.durationS);
  const durationValid = Number.isFinite(duration) && duration >= 1 && duration <= 20;

  async function record(body: Record<string, unknown>) {
    return parseRecording(await request<unknown>("/camera/record", { ...body, duration_s: duration }));
  }

  function pick(event: MouseEvent<HTMLImageElement>) {
    if (!camera?.width || !camera.height) return;
    const box = event.currentTarget.getBoundingClientRect();
    const [x, y] = previewPixel(event.clientX - box.left, event.clientY - box.top, box.width, box.height, camera.width, camera.height);
    const key = pickTarget === "mapping" ? "mappingPixels" : "checkPixels";
    update(current => ({ ...current, [key]: `${current[key].trim() ? current[key].trimEnd() + "\n" : ""}${x}, ${y}` }));
  }

  const rigView = view("rig_state");
  return <div className={styles.stack}>
    <section className="card"><div className="card-header"><div><h2 className="card-title">Field commissioning</h2><p className="card-subtitle">One measured tank setup → a frozen, reproducible field receipt.</p></div></div>
      <div className="card-body"><p className={styles.intro}>Each step uses an existing endpoint and its gates. The receipt is saved only after the server re-checks every stored artifact. A draft is not an approved physical setup, and operator confirmations are recorded as statements, not verified hardware. Pump power and token recovery stay manual.</p>
        <details><summary>Measuring in the right units</summary><p className={styles.explain}>Measure on the water surface from one fixed corner of the tank. Choose the unit you measured in; the wizard converts it to centimetres explicitly (10 mm = 1 cm, 1 in = 2.54 cm). Speeds are cm/s. The server refuses a mapping whose view spans more than a tabletop tank, the usual sign of millimetres entered as centimetres.</p></details>
        {!operatorConnected && <div className={styles.info}>Connect operator access to run setup actions. <button className="card-link" onClick={onRequireOperator}>Connect operator</button></div>}
        {busy && <div className={styles.info} role="status">{busy}…</div>}
        {error && <div className={styles.error} role="alert">{error}</div>}
        {notice && <div className={styles.info} role="status">{notice}</div>}
      </div>
    </section>

    <div className={styles.steps}>
      <Step item={view("camera_session")} n={1}>
        <div className={styles.form}><div className={styles.grid2}>
          <label>USB device index<input type="number" min={0} max={20} value={draft.deviceIndex} disabled={locked || !!camera?.running} onChange={event => field("deviceIndex")(Number(event.target.value))} /></label>
          <label>Current session<input readOnly value={camera?.session_id ?? "No camera running"} /></label>
        </div>
          <div className={styles.actions}>
            <button className="secondary-button" disabled={locked || !!camera?.running || !Number.isInteger(draft.deviceIndex) || draft.deviceIndex < 0 || draft.deviceIndex > 20} onClick={() => void run("Opening the selected webcam", async () => { await request("/camera/start", { device_index: draft.deviceIndex }); })}>Start this webcam</button>
            <button className="primary-button" disabled={locked || !camera?.fresh || !camera.session_id || camera.session_id === draft.cameraSessionId} onClick={() => { const id = camera!.session_id!; update(current => ({ ...invalidateAfter(current, "camera_session"), cameraSessionId: id })); setNotice(draft.cameraSessionId ? "New session selected. Earlier mapping, drift and observations were cleared from this draft; their saved records remain readable." : "Session selected."); }}>Use current session</button>
            {camera?.backend === "SYNTHETIC_FAKE_CAPTURE" && <span className={styles.warning}>Synthetic fake capture — not a physical camera.</span>}
          </div></div>
      </Step>

      <Step item={view("water_plane_mapping")} n={2}>
        <div className={styles.form}>
          {sessionCurrent && camera?.width && camera.height ? <div className={styles.preview}><Image unoptimized width={camera.width} height={camera.height} src={`${apiBase}/api/v1/camera/frame.jpg?t=${tick}`} alt="Latest frame. Click a mark to add its pixel position." onClick={pick} /></div> : <p className={styles.explain}>A preview appears when the selected session has fresh frames.</p>}
          <div className={styles.grid2}>
            <label>Clicking the preview adds to<select value={pickTarget} onChange={event => setPickTarget(event.target.value as "mapping" | "check")}><option value="mapping">Mapping pixel points</option><option value="check">Check pixel points</option></select></label>
            <label>Measured unit<select value={draft.unit} disabled={locked} onChange={event => field("unit")(event.target.value as LengthUnit)}><option value="cm">Centimetres</option><option value="mm">Millimetres</option><option value="in">Inches</option></select></label>
          </div>
          <div className={styles.grid2}>
            <label>Mapping pixel points (x, y per line; four or more)<textarea rows={5} value={draft.mappingPixels} disabled={locked} onChange={event => field("mappingPixels")(event.target.value)} /></label>
            <label>Matching water-surface points ({draft.unit})<textarea rows={5} value={draft.mappingWorld} disabled={locked} onChange={event => field("mappingWorld")(event.target.value)} /></label>
            <label>Check pixel points (three or more separate marks)<textarea rows={4} value={draft.checkPixels} disabled={locked} onChange={event => field("checkPixels")(event.target.value)} /></label>
            <label>Matching check water-surface points ({draft.unit})<textarea rows={4} value={draft.checkWorld} disabled={locked} onChange={event => field("checkWorld")(event.target.value)} /></label>
          </div>
          <label>Check-point tolerance (cm, declared before fitting)<input inputMode="decimal" value={draft.maxErrorCm} disabled={locked} onChange={event => field("maxErrorCm")(event.target.value)} /></label>
          <div className={styles.actions}><button className="primary-button" disabled={locked || !sessionCurrent} onClick={() => void run("Fitting and validating the mapping", async () => {
            const calibration = parseCalibration(await request<unknown>("/vision/calibrate", buildCalibrationRequest(draft, camera)));
            update(current => ({ ...invalidateAfter(current, "water_plane_mapping"), calibration }));
            if (!calibration.approved) setNotice("The mapping was saved but not approved. Recording stays blocked until a new mapping passes.");
          })}>Fit and validate mapping</button></div>
        </div>
      </Step>

      <Step item={view("drift_recordings")} n={3}>
        <div className={styles.form}>
          <label>Recording length (1–20 s)<input inputMode="decimal" value={draft.durationS} disabled={locked} onChange={event => field("durationS")(event.target.value)} /></label>
          <p className={styles.explain}>Release one token per run and keep it in view. Gaps or a second token split the track; they are never joined.</p>
          <div className={styles.actions}>
            {(["training", "validation"] as const).map(split => <button key={split} className="secondary-button" disabled={locked || !sessionCurrent || !draft.calibration?.approved || !durationValid} onClick={() => void run(`Recording ${split} drift`, async () => {
              const result = await record({ calibration_id: draft.calibration!.calibration_id });
              update(current => addRecording(current, split, result.id));
              setNotice(`${split === "training" ? "Training" : "Validation"} run ${result.id}: ${result.observed}/${result.frames} frames observed, ${result.gaps} gap${result.gaps === 1 ? "" : "s"}, ${result.tracks} track${result.tracks === 1 ? "" : "s"}.`);
            })}>Record {split} run</button>)}
          </div>
          <ul className={styles.ids}>
            {draft.trainingRecordingIds.map(id => <li key={id}>Training <code>{id}</code></li>)}
            {draft.validationRecordingIds.map(id => <li key={id}>Validation <code>{id}</code></li>)}
          </ul>
          {(draft.trainingRecordingIds.length > 0 || draft.validationRecordingIds.length > 0) && <div className={styles.actions}><button className="ghost-button" disabled={locked} onClick={() => update(current => ({ ...invalidateAfter(current, "water_plane_mapping") }))}>Clear drift runs from this draft</button></div>}
        </div>
      </Step>

      <Step item={view("recorded_flow")} n={4}>
        <div className={styles.form}>
          <div className={styles.grid4}>
            {(["xMin", "xMax", "yMin", "yMax"] as const).map(key => <label key={key}>Tank {key.replace("Min", " min").replace("Max", " max")} ({draft.unit})<input inputMode="decimal" value={draft.bounds[key]} disabled={locked} onChange={event => update(current => ({ ...current, bounds: { ...current.bounds, [key]: event.target.value } }))} /></label>)}
          </div>
          <div className={styles.grid2}>
            <label>Coverage radius (cm, declared before fitting)<input inputMode="decimal" value={draft.coverageRadiusCm} disabled={locked} onChange={event => field("coverageRadiusCm")(event.target.value)} /></label>
            <label>Cell size (cm)<input inputMode="decimal" value={draft.cellSizeCm} disabled={locked} onChange={event => field("cellSizeCm")(event.target.value)} /></label>
          </div>
          <div className={styles.actions}><button className="primary-button" disabled={locked || !draft.trainingRecordingIds.length || !draft.validationRecordingIds.length} onClick={() => void run("Fitting measured flow", async () => {
            const flow = parseFlow(await request<unknown>("/flow/fit-recordings", buildFlowRequest(draft)));
            update(current => ({ ...invalidateAfter(current, "drift_recordings"), flow }));
          })}>Fit recorded flow</button></div>
          {draft.flow && <p className={styles.explain}>Flow <code>{draft.flow.id}</code>: {draft.flow.diagnostics.sample_count} training samples, {draft.flow.diagnostics.node_count} nodes, held-out error {draft.flow.diagnostics.validation_rmse_cm_s?.toFixed(3) ?? "unavailable"} cm/s, {Math.round((draft.flow.diagnostics.validation_coverage_fraction ?? 0) * 100)}% supported.</p>}
        </div>
      </Step>

      <Step item={view("measured_profile")} n={5}>
        <div className={styles.form}>
          <p className={styles.explain}>Polygons are corner points (x, y per line, in {draft.unit}). Declare both error limits from development runs, not by adjusting them until this flow passes.</p>
          <div className={styles.grid2}>
            {draft.sources.map((source, index) => <label key={source.id}>Inlet {source.id} region{index > 1 ? " (optional)" : ""}<textarea rows={3} value={source.polygon} disabled={locked} onChange={event => update(current => ({ ...current, sources: current.sources.map(item => item.id === source.id ? { ...item, polygon: event.target.value } : item) }))} /></label>)}
            <label>Permitted observation region<textarea rows={3} value={draft.observationPolygon} disabled={locked} onChange={event => field("observationPolygon")(event.target.value)} /></label>
            <label>Retention pocket (optional)<textarea rows={3} value={draft.pocketPolygon} disabled={locked} onChange={event => field("pocketPolygon")(event.target.value)} /></label>
            <label>Token class<input value={draft.tokenClass} disabled={locked} onChange={event => field("tokenClass")(event.target.value)} /></label>
            <label>Held-out drift error limit (cm/s)<input inputMode="decimal" value={draft.maxValidationRmse} disabled={locked} onChange={event => field("maxValidationRmse")(event.target.value)} /></label>
            <label>Revalidation error limit (cm/s)<input inputMode="decimal" value={draft.revalidationRmse} disabled={locked} onChange={event => field("revalidationRmse")(event.target.value)} /></label>
          </div>
          <label className={styles.check}><input type="checkbox" checked={draft.pocketValidated} disabled={locked} onChange={event => field("pocketValidated")(event.target.checked)} /><span>I tested that tokens stay in the retention pocket.</span></label>
          <div className={styles.actions}><button className="primary-button" disabled={locked || !draft.flow} onClick={() => void run("Admitting the measured profile", async () => {
            const profile = parseProfile(await request<unknown>("/profiles", buildProfile(draft)));
            update(current => ({ ...invalidateAfter(current, "recorded_flow"), profileId: profile.id }));
          })}>Admit measured profile</button></div>
        </div>
      </Step>

      <Step item={view("rig_state")} n={6}>
        {rigView.state === "blocked" ? <div className={styles.form}>
          <p className={styles.explain}>Restore the frozen setup, confirm each check, then record new drift with this profile. Earlier observations cannot be reused afterwards.</p>
          {RIG_CHECKS.map(key => <label key={key} className={styles.check}><input type="checkbox" checked={!!rigChecks[key]} disabled={locked} onChange={event => setRigChecks(current => ({ ...current, [key]: event.target.checked }))} /><span>{ATTESTATION_TEXT[key]}</span></label>)}
          <div className={styles.actions}><button className="primary-button" disabled={locked || !sessionCurrent || !draft.profileId || !durationValid || !RIG_CHECKS.every(key => rigChecks[key])} onClick={() => void run("Recording and revalidating drift", async () => {
            const drift = await record({ profile_id: draft.profileId });
            const check = parseRigCheck(await request<unknown>("/rig/revalidate", { profile_id: draft.profileId, recording_id: drift.id, checks: Object.fromEntries(RIG_CHECKS.map(key => [key, true])) }));
            update(current => ({ ...invalidateAfter(current, "rig_state"), rigCheckId: check.id }));
            setRigChecks({});
          })}>Record drift and revalidate</button></div>
        </div> : draft.rigCheckId ? <p className={styles.explain}>Rig check <code>{draft.rigCheckId}</code></p> : null}
      </Step>

      <Step item={view("first_source_observation")} n={7}>
        <div className={styles.actions}>
          <button className="primary-button" disabled={locked || !sessionCurrent || !draft.profileId || !durationValid} onClick={() => void run("Recording a new source observation", async () => {
            const recording = await record({ profile_id: draft.profileId });
            const item = parseCase(await request<unknown>(`/recordings/${encodeURIComponent(recording.id)}/case`, { observation_type: "trajectory" }));
            update(current => ({ ...current, firstCaseId: item.id, manifestId: null }));
          })}>Record new source case</button>
          {draft.firstCaseId && onOpenCase && <button className="ghost-button" onClick={() => onOpenCase(draft.firstCaseId!)}>Open case</button>}
        </div>
      </Step>

      <Step item={view("operator_attestations")} n={8}>
        <div className={styles.form}>{ATTESTATION_KEYS.map(key => <label key={key} className={styles.check}><input type="checkbox" checked={draft.attestations[key]} disabled={locked} onChange={event => update(current => ({ ...current, attestations: { ...current.attestations, [key]: event.target.checked }, manifestId: null }))} /><span>{ATTESTATION_TEXT[key]}</span></label>)}</div>
      </Step>
    </div>

    <section className="card"><div className="card-header"><div><h2 className="card-title">Field receipt</h2><p className="card-subtitle">Checked and frozen by the server from saved artifacts.</p></div></div>
      <div className="card-body">
        <div className={styles.actions}>
          <button className="secondary-button" disabled={locked || !draft.cameraSessionId} onClick={() => void run("Checking every step", async () => {
            const key = requestKey(draft);
            const result = parsePreflight(await request<unknown>("/field-sessions/preflight", buildFieldRequest(draft)));
            setPreflight(result); setPreflightKey(key);
          })}>Check all steps</button>
          <button className="primary-button" disabled={locked || !canFreeze(draft, preflight, preflightKey)} title={canFreeze(draft, preflight, preflightKey) ? "Save the immutable receipt" : "Run Check all steps until every step passes"} onClick={() => void run("Freezing the field receipt", async () => {
            const detail = parseManifestDetail(await request<unknown>("/field-sessions", buildFieldRequest(draft)));
            setReceipt(detail); update(current => ({ ...current, manifestId: detail.manifest.manifest_id }));
          })}>Freeze field receipt</button>
          <button className="ghost-button" disabled={locked} onClick={() => { if (window.confirm("Start a new field draft? Saved server records are kept.")) { setDraft(newDraft()); setPreflight(null); setPreflightKey(""); setReceipt(null); } }}>Start a new draft</button>
        </div>
        {preflight && preflightKey === requestKey(draft) && preflight.status === "BLOCKED" && <p className={styles.help}>Not ready: {preflight.steps.filter(step => step.status !== "PASSED").length} step(s) need attention above.</p>}
        {receipt && <div className={styles.receipt}>
          <dl>
            <dt>Manifest</dt><dd><code>{receipt.manifest.manifest_id}</code></dd>
            <dt>Content hash</dt><dd><code>{receipt.manifest.content_hash}</code></dd>
            <dt>Profile</dt><dd><code>{receipt.manifest.profile.profile_id}</code></dd>
            <dt>First case</dt><dd><code>{receipt.manifest.first_observation.case_id}</code></dd>
            <dt>Capture</dt><dd>{receipt.manifest.capture.capture_origin === "SYNTHETIC_FAKE_CAPTURE" ? <span className={styles.warning}>Synthetic fake capture — not a physical measurement</span> : "USB camera device"}</dd>
            <dt>Current</dt><dd>{receipt.is_current ? "Yes" : <span className={styles.warning}>No — {receipt.stale_reasons.join(", ").toLowerCase().replaceAll("_", " ")}</span>}</dd>
          </dl>
          <p className={styles.explain}>Warnings: {receipt.manifest.warnings.join(", ").toLowerCase().replaceAll("_", " ")}. Operator confirmations are not independent hardware verification.</p>
        </div>}
      </div>
    </section>
  </div>;
}
