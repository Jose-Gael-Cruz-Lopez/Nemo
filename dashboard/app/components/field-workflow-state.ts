/**
 * Pure state for the guided field-commissioning workflow.
 *
 * Every response parser mirrors an actual API contract and throws on a shape it
 * does not recognise. Local checks only help the operator; the server re-verifies
 * every artifact and is the only authority that can report READY.
 */

export const STEP_IDS = ["camera_session", "water_plane_mapping", "drift_recordings", "recorded_flow", "measured_profile", "rig_state", "first_source_observation", "operator_attestations"] as const;
export type StepId = typeof STEP_IDS[number];
export const ATTESTATION_KEYS = ["waterline_unchanged", "pump_setting_unchanged", "hose_and_pocket_unchanged", "camera_and_light_unchanged", "coordinates_measured_in_cm"] as const;
export type AttestationKey = typeof ATTESTATION_KEYS[number];
export type Attestations = Record<AttestationKey, boolean>;
export type LengthUnit = "cm" | "mm" | "in";
export const UNIT_TO_CM: Record<LengthUnit, number> = { cm: 1, mm: 0.1, in: 2.54 };
export const MAX_TABLETOP_SPAN_CM = 200;
export const DRAFT_KEY = "reeftrace.field-workflow.draft.v1";

export type CameraStatus = { running: boolean; session_id: string | null; fresh: boolean; width: number | null; height: number | null; backend: string | null; device_index: number | null };
export type CalibrationReport = { calibration_id: string; approved: boolean; camera_session_id: string; max_error_cm: number; max_allowed_error_cm: number; mean_error_cm: number; validation_count: number; image_size_px: [number, number]; homography_image_to_cm?: number[][]; plane?: string; units?: string; mapping_polygon_px?: number[][] };
export type RecordingSummary = { id: string; camera_session_id: string; calibration_id: string; profile_id: string | null; frames: number; observed: number; gaps: number; tracks: number };
export type FlowNode = { x_cm: number; y_cm: number; vx_cm_s: number; vy_cm_s: number };
export type FlowResult = { id: string; data_origin: string; nodes: FlowNode[]; diagnostics: { validation_rmse_cm_s: number | null; validation_coverage_fraction: number | null; node_count: number; sample_count: number }; provenance: { calibration_id: string; camera_session_id: string; training_recording_ids: string[]; validation_recording_ids: string[] }; [key: string]: unknown };
export type CaseSummary = { id: string; mode: string; state: string; profile_id: string; recording_id: string | null };
export type StepStatus = "PASSED" | "BLOCKED" | "MISSING";
export type ServerStep = { step: StepId; status: StepStatus; code: string; message: string; help: string };
export type Preflight = { status: "READY" | "BLOCKED"; steps: ServerStep[]; content_hash: string | null; manifest_id: string | null };
export type ManifestDetail = { manifest: { manifest_id: string; content_hash: string; status: "READY"; created_at: number | null; warnings: string[]; capture: { capture_origin: string; camera_session_id: string }; profile: { profile_id: string }; first_observation: { case_id: string }; rig_check_id: string | null }; is_current: boolean; stale_reasons: string[] };
export type Bounds = { x_min_cm: number; x_max_cm: number; y_min_cm: number; y_max_cm: number };
export type TokenDetector = "foreground_reference_v1" | "red_hsv";
/** Empty-tank reference for colour-independent tracking, plus the measured size of one token. */
export type TokenReference = { reference_id: string; camera_session_id: string; image_size_px: [number, number]; token_area_px: number | null; token_area_px_range: [number, number] | null };

export type Draft = {
  version: 1;
  unit: LengthUnit;
  deviceIndex: number;
  cameraSessionId: string | null;
  mappingPixels: string; mappingWorld: string; checkPixels: string; checkWorld: string; maxErrorCm: string;
  calibration: CalibrationReport | null;
  trainingRecordingIds: string[]; validationRecordingIds: string[]; durationS: string;
  bounds: { xMin: string; xMax: string; yMin: string; yMax: string };
  coverageRadiusCm: string; cellSizeCm: string;
  flow: FlowResult | null;
  tokenClass: string; sources: { id: string; polygon: string }[]; observationPolygon: string; pocketPolygon: string; pocketValidated: boolean;
  maxValidationRmse: string; revalidationRmse: string;
  profileId: string | null;
  rigCheckId: string | null;
  firstCaseId: string | null;
  attestations: Attestations;
  manifestId: string | null;
  detector: TokenDetector;
  tokenReference: TokenReference | null;
};

export function emptyAttestations(): Attestations {
  return { waterline_unchanged: false, pump_setting_unchanged: false, hose_and_pocket_unchanged: false, camera_and_light_unchanged: false, coordinates_measured_in_cm: false };
}

export function newDraft(): Draft {
  return {
    version: 1, unit: "cm", deviceIndex: 0, cameraSessionId: null,
    mappingPixels: "", mappingWorld: "", checkPixels: "", checkWorld: "", maxErrorCm: "0.5", calibration: null,
    trainingRecordingIds: [], validationRecordingIds: [], durationS: "5",
    bounds: { xMin: "", xMax: "", yMin: "", yMax: "" }, coverageRadiusCm: "3", cellSizeCm: "1", flow: null,
    tokenClass: "red-foam-10mm", sources: ["A", "B", "C"].map(id => ({ id, polygon: "" })), observationPolygon: "", pocketPolygon: "", pocketValidated: false,
    maxValidationRmse: "", revalidationRmse: "", profileId: null, rigCheckId: null, firstCaseId: null,
    attestations: emptyAttestations(), manifestId: null,
    detector: "foreground_reference_v1", tokenReference: null,
  };
}

const isObject = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const text = (value: unknown, max = 200): value is string => typeof value === "string" && value.length > 0 && value.length <= max;
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(item => text(item));
function fail(label: string): never { throw new Error(`${label}. The API response did not match the expected contract; nothing was saved in this draft.`); }

/** Parse "x, y" pairs separated by new lines or semicolons. */
export function parsePairs(input: string, label: string): number[][] {
  const rows = input.split(/[;\n]+/).map(row => row.trim()).filter(Boolean);
  return rows.map((row, index) => {
    const parts = row.split(/[\s,]+/).filter(Boolean).map(Number);
    if (parts.length !== 2 || !parts.every(Number.isFinite)) throw new Error(`${label}, row ${index + 1}: write two numbers as “x, y”.`);
    return parts;
  });
}

export function toCm(value: number, unit: LengthUnit): number { return Math.round(value * UNIT_TO_CM[unit] * 1e9) / 1e9; }
function lengthsCm(input: string, label: string, unit: LengthUnit) { return parsePairs(input, label).map(([x, y]) => [toCm(x, unit), toCm(y, unit)]); }
function positive(input: string, label: string, max = Infinity): number {
  const value = Number(input);
  if (!input.trim() || !Number.isFinite(value) || value <= 0 || value > max) throw new Error(`${label} must be a positive number${Number.isFinite(max) ? ` up to ${max}` : ""}.`);
  return value;
}

/** Build POST /vision/calibrate. Unit conversion is explicit; the server decides approval. */
export function buildCalibrationRequest(draft: Draft, camera: CameraStatus | null) {
  if (!draft.cameraSessionId) throw new Error("Select the camera session first.");
  if (!camera || camera.session_id !== draft.cameraSessionId || !camera.width || !camera.height) throw new Error("The selected camera session has no current frames; its image size is unknown.");
  const pixels = parsePairs(draft.mappingPixels, "Mapping pixel points");
  const world = lengthsCm(draft.mappingWorld, "Mapping water-surface points", draft.unit);
  const checkPixels = parsePairs(draft.checkPixels, "Check pixel points");
  const checkWorld = lengthsCm(draft.checkWorld, "Check water-surface points", draft.unit);
  if (pixels.length < 4 || pixels.length !== world.length) throw new Error("Use four or more mapping correspondences, with one water-surface point for each pixel point.");
  if (checkPixels.length < 3 || checkPixels.length !== checkWorld.length) throw new Error("Use at least three separate check points, with one water-surface point for each pixel point.");
  const key = (point: number[]) => point.join(",");
  if (new Set(checkPixels.map(key)).size !== checkPixels.length) throw new Error("Check points must be distinct.");
  if (checkPixels.some(point => pixels.some(other => key(other) === key(point)))) throw new Error("Check points must be separate marks, not repeats of mapping points.");
  const [w, h] = [camera.width, camera.height];
  if ([...pixels, ...checkPixels].some(([x, y]) => x < 0 || y < 0 || x > w - 1 || y > h - 1)) throw new Error(`Pixel points must lie inside the ${w} × ${h} frame.`);
  const all = [...world, ...checkWorld];
  const span = Math.max(Math.max(...all.map(p => p[0])) - Math.min(...all.map(p => p[0])), Math.max(...all.map(p => p[1])) - Math.min(...all.map(p => p[1])));
  if (span > MAX_TABLETOP_SPAN_CM) throw new Error(`These points span ${span.toFixed(0)} cm, beyond a tabletop tank. Check the unit selector: millimetres or inches entered as centimetres are the usual cause.`);
  return { pixel_points: pixels, world_cm_points: world, check_pixels: checkPixels, check_world_cm: checkWorld, max_error_cm: positive(draft.maxErrorCm, "Check-point tolerance (cm)", 5), image_size_px: [w, h], camera_session_id: draft.cameraSessionId };
}

export function parseCameraStatus(value: unknown): CameraStatus {
  if (!isObject(value) || typeof value.running !== "boolean" || typeof value.fresh !== "boolean") fail("Camera status was incomplete");
  const optionalNumber = (v: unknown) => v === null || v === undefined ? null : finite(v) ? v : fail("Camera status had a non-numeric size");
  return { running: value.running, fresh: value.fresh, session_id: text(value.session_id) ? value.session_id : null, width: optionalNumber(value.width), height: optionalNumber(value.height), backend: text(value.backend) ? value.backend : null, device_index: optionalNumber(value.device_index) };
}

export function parseCalibration(value: unknown, fittingPixels?: number[][]): CalibrationReport {
  if (!isObject(value) || !text(value.calibration_id) || typeof value.approved !== "boolean" || !text(value.camera_session_id)
    || !finite(value.max_error_cm) || !finite(value.max_allowed_error_cm) || !finite(value.mean_error_cm) || !finite(value.validation_count)
    || !Array.isArray(value.image_size_px) || value.image_size_px.length !== 2 || !value.image_size_px.every(finite)) fail("Mapping result was incomplete");
  const matrix = value.homography_image_to_cm;
  if (matrix !== undefined) {
    if (!Array.isArray(matrix) || matrix.length !== 3 || matrix.some(row => !Array.isArray(row) || row.length !== 3 || !row.every(finite))) fail("Mapping matrix was invalid");
    const scale = Math.max(...matrix.flat().map(Math.abs));
    if (!scale) fail("Mapping matrix was invalid");
    const [[a,b,c],[d,e,f],[g,h,i]] = matrix.map(row => row.map((v: number) => v / scale));
    if (Math.abs(a*(e*i-f*h)-b*(d*i-f*g)+c*(d*h-e*g)) <= 1e-12) fail("Mapping matrix was singular");
  }
  const marks = fittingPixels ?? value.mapping_polygon_px;
  const fittingMarks = Array.isArray(marks) && marks.length >= 4 && marks.length <= 100 && marks.every(p => Array.isArray(p) && p.length === 2 && p.every(finite)) ? marks as number[][] : null;
  return { calibration_id: value.calibration_id, approved: value.approved, camera_session_id: value.camera_session_id, max_error_cm: value.max_error_cm, max_allowed_error_cm: value.max_allowed_error_cm, mean_error_cm: value.mean_error_cm, validation_count: value.validation_count, image_size_px: [value.image_size_px[0], value.image_size_px[1]],
    ...(value.homography_image_to_cm !== undefined ? { homography_image_to_cm: value.homography_image_to_cm as number[][] } : {}),
    ...(typeof value.plane === "string" ? { plane: value.plane } : {}), ...(typeof value.units === "string" ? { units: value.units } : {}),
    ...(fittingMarks ? { mapping_polygon_px: fittingMarks.map(p => [...p]) } : {}),
  };
}

export function parseRecording(value: unknown): RecordingSummary {
  if (!isObject(value) || !text(value.id) || !text(value.camera_session_id) || !text(value.calibration_id) || !Array.isArray(value.points) || !strings(value.evidence_frame_ids)
    || value.data_origin !== "MEASURED_TANK") fail("Recording result was incomplete");
  const points = value.points.filter(isObject);
  const tracks = new Set(points.filter(p => p.observed === true).map(p => p.track_id));
  let gaps = 0;
  points.forEach((p, i) => { if (p.observed !== true && (i === 0 || points[i - 1].observed === true)) gaps += 1; });
  return { id: value.id, camera_session_id: value.camera_session_id, calibration_id: value.calibration_id, profile_id: text(value.profile_id) ? value.profile_id : null, frames: value.evidence_frame_ids.length, observed: points.filter(p => p.observed === true).length, gaps, tracks: tracks.size };
}

export function parseFlow(value: unknown): FlowResult {
  if (!isObject(value) || !text(value.id) || !Array.isArray(value.nodes) || !isObject(value.diagnostics) || !isObject(value.provenance)) fail("Recorded-flow result was incomplete");
  const d = value.diagnostics, p = value.provenance;
  const nullable = (v: unknown) => v === null || finite(v);
  if (!nullable(d.validation_rmse_cm_s) || !nullable(d.validation_coverage_fraction) || !finite(d.node_count) || !finite(d.sample_count)
    || !text(p.calibration_id) || !text(p.camera_session_id) || !strings(p.training_recording_ids) || !strings(p.validation_recording_ids)) fail("Recorded-flow diagnostics were incomplete");
  return value as FlowResult;
}

export function flowSupported(flow: FlowResult | null): boolean {
  const d = flow?.diagnostics;
  return Boolean(d && d.validation_rmse_cm_s !== null && d.validation_coverage_fraction !== null && d.validation_coverage_fraction >= 0.9);
}

export function parseProfile(value: unknown): { id: string; data_origin: string; calibration_id: string } {
  if (!isObject(value) || !text(value.id) || value.data_origin !== "MEASURED_TANK" || !text(value.calibration_id)) fail("Profile result was not a measured profile");
  return { id: value.id, data_origin: value.data_origin, calibration_id: value.calibration_id };
}

export function parseCase(value: unknown): CaseSummary {
  if (!isObject(value) || !text(value.id) || value.mode !== "LIVE" || !text(value.state) || !text(value.profile_id)) fail("Source observation result was not a LIVE case");
  return { id: value.id, mode: value.mode, state: value.state, profile_id: value.profile_id, recording_id: text(value.recording_id) ? value.recording_id : null };
}

export function parseRigCheck(value: unknown): { id: string; profile_id: string } {
  if (!isObject(value) || !text(value.id) || !text(value.profile_id) || !finite(value.rmse_cm_s)) fail("Revalidation result was incomplete");
  return { id: value.id, profile_id: value.profile_id };
}

export function parsePreflight(value: unknown): Preflight {
  if (!isObject(value) || (value.status !== "READY" && value.status !== "BLOCKED") || !Array.isArray(value.steps)) fail("Field-session check was incomplete");
  const steps = value.steps.map(step => {
    if (!isObject(step) || !STEP_IDS.includes(step.step as StepId) || !["PASSED", "BLOCKED", "MISSING"].includes(step.status as string) || !text(step.code, 80) || !text(step.message, 400) || typeof step.help !== "string") fail("A field-session step was malformed");
    return step as ServerStep;
  });
  if (steps.map(s => s.step).join() !== STEP_IDS.join()) fail("Field-session steps were missing or out of order");
  const ready = steps.every(s => s.status === "PASSED");
  if ((value.status === "READY") !== ready) fail("Field-session status disagreed with its steps");
  if (ready && (!text(value.manifest_id) || !text(value.content_hash))) fail("A READY check lacked its manifest identity");
  return { status: value.status, steps, content_hash: ready ? value.content_hash as string : null, manifest_id: ready ? value.manifest_id as string : null };
}

/** Only a sealed READY receipt with every step passed is accepted for display. */
export function parseManifestDetail(value: unknown): ManifestDetail {
  if (!isObject(value) || !isObject(value.manifest) || typeof value.is_current !== "boolean" || !strings(value.stale_reasons)) fail("Field receipt was incomplete");
  const m = value.manifest;
  if (m.schema_version !== "field_manifest_v1" || m.status !== "READY" || !/^fm-[0-9a-f]{16}$/.test(String(m.manifest_id)) || !/^[0-9a-f]{64}$/.test(String(m.content_hash))
    || String(m.content_hash).slice(0, 16) !== String(m.manifest_id).slice(3) || !Array.isArray(m.checks) || m.checks.length !== STEP_IDS.length
    || !m.checks.every(c => isObject(c) && c.status === "PASSED") || !strings(m.warnings) || !isObject(m.capture) || !isObject(m.profile) || !isObject(m.first_observation)
    || !isObject(m.provenance) || m.provenance.hardware_independently_verified !== false) fail("Field receipt was not a complete READY manifest");
  return value as ManifestDetail;
}

export function addRecording(draft: Draft, split: "training" | "validation", id: string): Draft {
  const other = split === "training" ? draft.validationRecordingIds : draft.trainingRecordingIds;
  if (other.includes(id)) throw new Error("A recording cannot be both training and validation drift.");
  const key = split === "training" ? "trainingRecordingIds" : "validationRecordingIds";
  if (draft[key].includes(id)) return draft;
  return invalidateAfter({ ...draft, [key]: [...draft[key], id] }, "drift_recordings");
}

export function boundsCm(draft: Draft): Bounds {
  const read = (value: string, label: string) => { const n = Number(value); if (!value.trim() || !Number.isFinite(n)) throw new Error(`Tank bound ${label} must be a number.`); return toCm(n, draft.unit); };
  const b = { x_min_cm: read(draft.bounds.xMin, "x min"), x_max_cm: read(draft.bounds.xMax, "x max"), y_min_cm: read(draft.bounds.yMin, "y min"), y_max_cm: read(draft.bounds.yMax, "y max") };
  if (b.x_max_cm <= b.x_min_cm || b.y_max_cm <= b.y_min_cm) throw new Error("Each tank bound maximum must exceed its minimum.");
  if (Math.max(b.x_max_cm - b.x_min_cm, b.y_max_cm - b.y_min_cm) > MAX_TABLETOP_SPAN_CM) throw new Error("These bounds are larger than a tabletop tank; check the unit selector.");
  return b;
}

export function buildFlowRequest(draft: Draft) {
  if (!draft.trainingRecordingIds.length || !draft.validationRecordingIds.length) throw new Error("Record at least one training and one separate validation drift run.");
  if (draft.trainingRecordingIds.some(id => draft.validationRecordingIds.includes(id))) throw new Error("Training and validation recordings must be different runs.");
  return { training_recording_ids: draft.trainingRecordingIds, validation_recording_ids: draft.validationRecordingIds, bounds: boundsCm(draft), coverage_radius_cm: positive(draft.coverageRadiusCm, "Coverage radius (cm)", 50), cell_size_cm: positive(draft.cellSizeCm, "Cell size (cm)", 20) };
}

function polygon(input: string, label: string, draft: Draft, bounds: Bounds): number[][] {
  const points = lengthsCm(input, label, draft.unit);
  if (points.length < 3) throw new Error(`${label} needs at least three corner points.`);
  if (points.some(([x, y]) => x < bounds.x_min_cm || x > bounds.x_max_cm || y < bounds.y_min_cm || y > bounds.y_max_cm)) throw new Error(`${label} must lie inside the tank bounds.`);
  return points;
}

/** Build POST /profiles around the exact immutable flow object; gates stay server-side. */
export function buildProfile(draft: Draft) {
  if (!draft.calibration?.approved) throw new Error("Use an approved water-plane mapping first.");
  if (!draft.flow) throw new Error("Fit recorded flow first.");
  if (!flowSupported(draft.flow)) throw new Error("The recorded flow is unsupported: under 90% of validation drift is inside measured coverage. Record more drift; a measured profile cannot use it.");
  const bounds = boundsCm(draft);
  const sources = draft.sources.filter(s => s.polygon.trim()).map(s => ({ id: s.id, polygon_cm: polygon(s.polygon, `Inlet ${s.id} region`, draft, bounds) }));
  if (sources.length < 2 || sources.length > 5) throw new Error("Measure two to five candidate inlet regions.");
  const pocket = draft.pocketPolygon.trim() ? [{ id: "pocket", validated: draft.pocketValidated, polygon_cm: polygon(draft.pocketPolygon, "Retention pocket", draft, bounds) }] : [];
  const tokenClass = draft.tokenClass.trim();
  if (!tokenClass || tokenClass.length > 100) throw new Error("Name the standardized token class.");
  return {
    calibration_id: draft.calibration.calibration_id, data_origin: "MEASURED_TANK", valid: true, token_class: tokenClass, bounds, flow: draft.flow,
    sources: sources.map(s => ({ ...s, prior: 1 / sources.length })), traps: pocket, observation_polygon_cm: polygon(draft.observationPolygon, "Permitted observation region", draft, bounds),
    transport: { particles_per_source: 500, dt_s: 0.1, max_age_s: 60, diffusivity_cm2_s: 0.05, drift_bias_cm_s: [0, 0], age_prior: { min_s: 0, max_s: 30, count: 16 } },
    gates: { position_sigma_cm: 0.7, model_error_cm: 0.3, correlation_time_s: 0.8 },
    max_validation_rmse_cm_s: positive(draft.maxValidationRmse, "Held-out drift error limit (cm/s)"), revalidation_max_rmse_cm_s: positive(draft.revalidationRmse, "Revalidation error limit (cm/s)"),
  };
}

export function buildFieldRequest(draft: Draft) {
  if (!draft.cameraSessionId) throw new Error("Select the camera session first.");
  const attested = ATTESTATION_KEYS.some(key => draft.attestations[key]);
  return {
    camera_session_id: draft.cameraSessionId,
    ...(draft.calibration ? { calibration_id: draft.calibration.calibration_id } : {}),
    training_recording_ids: draft.trainingRecordingIds, validation_recording_ids: draft.validationRecordingIds,
    ...(draft.flow ? { flow_id: draft.flow.id } : {}), ...(draft.profileId ? { profile_id: draft.profileId } : {}),
    ...(draft.firstCaseId ? { first_case_id: draft.firstCaseId } : {}), ...(draft.rigCheckId ? { rig_check_id: draft.rigCheckId } : {}),
    ...(attested ? { attestations: draft.attestations } : {}),
  };
}

/** A server check applies only to the exact request it evaluated. */
export function requestKey(draft: Draft): string { try { return JSON.stringify(buildFieldRequest(draft)); } catch { return ""; } }

const DOWNSTREAM: Record<StepId, (keyof Draft)[]> = {
  camera_session: ["tokenReference", "calibration", "trainingRecordingIds", "validationRecordingIds", "flow", "profileId", "rigCheckId", "firstCaseId"],
  water_plane_mapping: ["trainingRecordingIds", "validationRecordingIds", "flow", "profileId", "rigCheckId", "firstCaseId"],
  drift_recordings: ["flow", "profileId", "rigCheckId", "firstCaseId"],
  recorded_flow: ["profileId", "rigCheckId", "firstCaseId"],
  measured_profile: ["rigCheckId", "firstCaseId"],
  rig_state: ["firstCaseId"],
  first_source_observation: [],
  operator_attestations: [],
};

/** Changing an upstream artifact clears everything derived from it and the receipt. */
export function invalidateAfter(draft: Draft, step: StepId): Draft {
  const next: Draft = { ...draft, manifestId: null, attestations: emptyAttestations() };
  for (const key of DOWNSTREAM[step]) (next as Record<string, unknown>)[key] = Array.isArray(draft[key]) ? [] : null;
  return next;
}

/** Recorded ruler survey, not a camera mapping or a passed physical check. */
export function applyLoggedTrayMeasurements(draft: Draft): Draft {
  const factor = UNIT_TO_CM[draft.unit];
  const display = (cm: number) => String(Math.round(cm / factor * 1e9) / 1e9);
  return { ...invalidateAfter(draft, "drift_recordings"),
    bounds: { xMin: "0", xMax: display(35.56), yMin: "0", yMax: display(22.86) },
    tokenClass: "green-bottle-cap",
  };
}

export type StepView = { id: StepId; state: "done" | "blocked" | "missing" | "server"; message: string; help: string };

export function deriveSteps(draft: Draft, camera: CameraStatus | null, preflight: Preflight | null, preflightKey: string): StepView[] {
  const local: Record<StepId, StepView> = Object.fromEntries(STEP_IDS.map(id => [id, { id, state: "missing", message: "", help: "" }])) as Record<StepId, StepView>;
  const set = (id: StepId, state: StepView["state"], message: string, help = "") => { local[id] = { id, state, message, help }; };
  if (!draft.cameraSessionId) set("camera_session", "missing", "No camera session selected.", "Start the external webcam yourself, then select its session.");
  else if (!camera?.running || camera.session_id !== draft.cameraSessionId) set("camera_session", "blocked", "The selected session is no longer current; the camera stopped or restarted.", "Select the current session. Mapping, drift and observations from the old session must be redone.");
  else if (!camera.fresh) set("camera_session", "blocked", "No fresh frames from the selected session.", "Check the USB cable and lighting.");
  else set("camera_session", "done", `Session ${draft.cameraSessionId}`);
  if (!draft.calibration) set("water_plane_mapping", "missing", "No mapping fitted.", "Enter four or more mapping points and three separate check points.");
  else if (!draft.calibration.approved) set("water_plane_mapping", "blocked", `Check-point error ${draft.calibration.max_error_cm.toFixed(2)} cm exceeds ${draft.calibration.max_allowed_error_cm} cm.`, "Re-measure in centimetres on the water surface. Do not raise the tolerance to pass.");
  else set("water_plane_mapping", "done", `Approved on ${draft.calibration.validation_count} check points; max error ${draft.calibration.max_error_cm.toFixed(2)} cm.`);
  const t = draft.trainingRecordingIds.length, v = draft.validationRecordingIds.length;
  if (draft.detector === "foreground_reference_v1" && !draft.tokenReference?.token_area_px_range) set("drift_recordings", "missing", draft.tokenReference ? "Measure one token before recording." : "Capture the empty tank before recording.", "With no token in the water, the pump on and hands out of view, capture the empty tank. Then place one cap and measure it.");
  else if (!t || !v) set("drift_recordings", "missing", `${t} training and ${v} validation runs.`, "Record at least one of each, as separate runs.");
  else set("drift_recordings", "done", `${t} training and ${v} validation runs.`);
  if (!draft.flow) set("recorded_flow", "missing", "No recorded flow fitted.");
  else if (!flowSupported(draft.flow)) set("recorded_flow", "blocked", `Only ${Math.round((draft.flow.diagnostics.validation_coverage_fraction ?? 0) * 100)}% of validation drift is supported (90% required).`, "Record more training drift where validation runs pass; do not widen coverage after seeing results.");
  else set("recorded_flow", "done", `Held-out error ${draft.flow.diagnostics.validation_rmse_cm_s?.toFixed(2)} cm/s.`);
  if (!draft.profileId) set("measured_profile", "missing", "No measured profile admitted.");
  else set("measured_profile", "done", `Profile ${draft.profileId}`);
  set("rig_state", draft.profileId ? "server" : "missing", draft.profileId ? "Checked by the server against recorded disturbances." : "Admit a profile first.");
  if (!draft.firstCaseId) set("first_source_observation", "missing", "No new source observation.", "Record a new source case. A live preview frame is not case evidence.");
  else set("first_source_observation", "done", `Case ${draft.firstCaseId}`);
  const missing = ATTESTATION_KEYS.filter(key => !draft.attestations[key]);
  set("operator_attestations", missing.length ? "missing" : "done", missing.length ? `${missing.length} physical checks unconfirmed.` : "Confirmed by the operator (not independently verified).");
  const current = preflight && preflightKey && preflightKey === requestKey(draft) ? preflight : null;
  return STEP_IDS.map(id => {
    const server = current?.steps.find(s => s.step === id);
    if (!server) return local[id];
    return { id, state: server.status === "PASSED" ? "done" : server.status === "BLOCKED" ? "blocked" : "missing", message: server.message, help: server.help };
  });
}

export function canFreeze(draft: Draft, preflight: Preflight | null, preflightKey: string): boolean {
  return Boolean(preflight && preflight.status === "READY" && preflightKey && preflightKey === requestKey(draft));
}

/** Network, timeout and server errors may be retried by the operator; the draft is always kept. */
export function failureNotice(cause: unknown): { message: string; retryable: boolean } {
  const status = isObject(cause) && finite(cause.status) ? cause.status : null;
  const raw = cause instanceof Error && cause.message.trim() ? cause.message.trim() : "The request failed.";
  const detail = /[.!?]$/.test(raw) ? raw : raw + ".";
  // fetch() rejects with TypeError when the API is unreachable; other status-less errors are local input checks.
  const retryable = status === null ? cause instanceof TypeError : status === 408 || status >= 500;
  return { message: `${detail} Your draft is kept${retryable ? "; retry when the API is reachable." : "."}`, retryable };
}

export function encodeDraft(draft: Draft): string { return JSON.stringify(draft); }

export function decodeDraft(raw: string | null): Draft | null {
  if (!raw || raw.length > 2_000_000) return null;
  try {
    const value = JSON.parse(raw) as unknown;
    if (!isObject(value) || value.version !== 1) return null;
    const base = newDraft();
    const merged = { ...base, ...value } as Draft;
    if (!["cm", "mm", "in"].includes(merged.unit) || !Number.isInteger(merged.deviceIndex) || !strings(merged.trainingRecordingIds)
      || !strings(merged.validationRecordingIds) || !isObject(merged.attestations) || !Array.isArray(merged.sources)) return null;
    merged.attestations = { ...emptyAttestations(), ...Object.fromEntries(ATTESTATION_KEYS.map(key => [key, (value.attestations as Record<string, unknown>)?.[key] === true])) };
    if (merged.calibration) merged.calibration = parseCalibration(merged.calibration);
    if (merged.flow) merged.flow = parseFlow(merged.flow);
    if (merged.detector !== "red_hsv" && merged.detector !== "foreground_reference_v1") return null;
    if (merged.tokenReference) merged.tokenReference = checkTokenReference(merged.tokenReference);
    return merged;
  } catch { return null; }
}

function checkTokenReference(value: unknown): TokenReference {
  if (!isObject(value) || !text(value.reference_id) || !text(value.camera_session_id) || !Array.isArray(value.image_size_px) || value.image_size_px.length !== 2 || !value.image_size_px.every(finite)
    || !(value.token_area_px === null || finite(value.token_area_px)) || !(value.token_area_px_range === null || Array.isArray(value.token_area_px_range) && value.token_area_px_range.length === 2 && value.token_area_px_range.every(finite))) fail("Empty-tank reference was incomplete");
  return value as TokenReference;
}

/** POST /camera/reference. A carried-over token size (same session, camera unmoved) is kept. */
export function parseTokenReference(value: unknown): TokenReference {
  if (!isObject(value) || value.detector !== "foreground_reference_v1") fail("Empty-tank reference was incomplete");
  const size = isObject(value.token_size) && value.token_size.reference_id === value.reference_id ? value.token_size : null;
  return checkTokenReference({ reference_id: value.reference_id, camera_session_id: value.camera_session_id, image_size_px: value.image_size_px,
    token_area_px: size ? size.token_area_px : null, token_area_px_range: size ? size.token_area_px_range : null });
}

/** Body for POST /camera/reference: reuse the measured size when asked and still valid. */
export function referenceCaptureBody(draft: Draft, keepTokenSize: boolean): { frame_count: number; token_size_from?: string } {
  const previous = draft.tokenReference;
  return keepTokenSize && previous?.token_area_px_range && previous.camera_session_id === draft.cameraSessionId
    ? { frame_count: 10, token_size_from: previous.reference_id } : { frame_count: 10 };
}

/** POST /camera/reference/{id}/token-size, applied only to the matching reference. */
export function withTokenSize(reference: TokenReference, value: unknown): TokenReference {
  if (!isObject(value) || value.reference_id !== reference.reference_id || !finite(value.token_area_px) || !Array.isArray(value.token_area_px_range)
    || value.token_area_px_range.length !== 2 || !value.token_area_px_range.every(finite)) fail("Token measurement was incomplete or for another reference");
  return { ...reference, token_area_px: value.token_area_px, token_area_px_range: [value.token_area_px_range[0], value.token_area_px_range[1]] };
}

/** A new reference changes how tokens are found, so earlier recordings and everything after them are cleared. */
export function setTokenReference(draft: Draft, reference: TokenReference | null): Draft {
  return { ...invalidateAfter(draft, "water_plane_mapping"), tokenReference: reference };
}

/** Extra fields for POST /camera/record. Red keeps the original body unchanged. */
export function detectionFields(draft: Draft): Record<string, string> {
  if (draft.detector === "red_hsv") return {};
  const reference = draft.tokenReference;
  if (!reference?.token_area_px_range) throw new Error("Capture the empty tank and measure one token first.");
  if (reference.camera_session_id !== draft.cameraSessionId) throw new Error("The empty-tank reference is from another camera session; capture it again.");
  return { detector: "foreground_reference_v1", reference_id: reference.reference_id };
}

/** Convert a click on a scaled preview into source-image pixel coordinates. */
export function previewPixel(offsetX: number, offsetY: number, shownWidth: number, shownHeight: number, imageWidth: number, imageHeight: number): [number, number] {
  if (![offsetX, offsetY, shownWidth, shownHeight, imageWidth, imageHeight].every(Number.isFinite) || shownWidth <= 0 || shownHeight <= 0) throw new Error("The preview has no size yet.");
  const x = Math.min(imageWidth - 1, Math.max(0, offsetX * imageWidth / shownWidth));
  const y = Math.min(imageHeight - 1, Math.max(0, offsetY * imageHeight / shownHeight));
  return [Math.round(x * 10) / 10, Math.round(y * 10) / 10];
}
