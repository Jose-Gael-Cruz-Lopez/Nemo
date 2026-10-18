/** Portable mapping metadata only. The local server verifies content hashes and approval. */
import { parseCalibration, parsePairs, type CalibrationReport, type CameraStatus } from "./field-workflow-state.ts";

export const SAVED_CALIBRATION_SCHEMA = "nemo_saved_calibration_v1" as const;
export const MAX_SAVED_CALIBRATION_BYTES = 64 * 1024;
export const MAX_CALIBRATION_JSON_BYTES = 32000;
const ID = /^cal-[a-f0-9]{16}$/;
const SESSION = /^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,99}$/;
const BASE_KEYS = ["id", "calibration_id", "homography_image_to_cm", "mean_error_cm", "max_error_cm", "validation_count", "max_allowed_error_cm", "approved", "image_size_px", "camera_session_id", "plane", "units"];
const SUMMARY_KEYS = ["calibration_id", "camera_session_id", "image_size_px", "approved", "max_error_cm", "max_allowed_error_cm", "mean_error_cm", "validation_count"];
export type SavedCalibrationSummary = Pick<CalibrationReport, "calibration_id" | "camera_session_id" | "image_size_px" | "approved" | "max_error_cm" | "max_allowed_error_cm" | "mean_error_cm" | "validation_count">;
export type SavedCalibrationReuse = { method: "fixed_homography_current_checks_v1"; source_calibration_id: string; source_content_sha256: string; check_pixels: number[][]; check_world_cm: number[][]; water_plane_unchanged: true };
export type SavedCalibrationRecord = CalibrationReport & { id: string; homography_image_to_cm: number[][]; plane: "measured_water_surface"; units: "cm"; reuse?: SavedCalibrationReuse };
export type SavedCalibrationBundle = { schema_version: typeof SAVED_CALIBRATION_SCHEMA; calibration: SavedCalibrationRecord; calibration_json: string };
const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
function invalid(message: string): never { throw new Error(message); }
function exactKeys(value: Record<string, unknown>, keys: string[], optional: string[] = []) {
  if (keys.some(key => !Object.hasOwn(value, key)) || Object.keys(value).some(key => !keys.includes(key) && !optional.includes(key))) invalid("The saved mapping contains missing or unsupported fields. Export only a Nemo calibration bundle; do not include credentials, images, or database files.");
}
function pairs(value: unknown): value is number[][] {
  return Array.isArray(value) && value.length >= 3 && value.length <= 100 && value.every(row => Array.isArray(row) && row.length === 2 && row.every(finite));
}
function summary(value: unknown): SavedCalibrationSummary {
  if (!object(value) || typeof value.calibration_id !== "string" || !ID.test(value.calibration_id)
    || typeof value.camera_session_id !== "string" || !SESSION.test(value.camera_session_id)
    || typeof value.approved !== "boolean" || !Array.isArray(value.image_size_px) || value.image_size_px.length !== 2
    || !value.image_size_px.every(n => Number.isInteger(n) && n >= 2 && n <= 16384)
    || !finite(value.max_error_cm) || value.max_error_cm < 0 || !finite(value.mean_error_cm) || value.mean_error_cm < 0
    || value.mean_error_cm > value.max_error_cm || !finite(value.max_allowed_error_cm) || value.max_allowed_error_cm <= 0 || value.max_allowed_error_cm > 5
    || !Number.isInteger(value.validation_count) || (value.validation_count as number) < 3 || (value.validation_count as number) > 100
    || value.approved !== (value.max_error_cm <= value.max_allowed_error_cm)) invalid("The saved mapping metadata is incomplete or inconsistent.");
  return { calibration_id: value.calibration_id, camera_session_id: value.camera_session_id, approved: value.approved,
    image_size_px: [value.image_size_px[0], value.image_size_px[1]], max_error_cm: value.max_error_cm, mean_error_cm: value.mean_error_cm,
    max_allowed_error_cm: value.max_allowed_error_cm, validation_count: value.validation_count as number };
}

/** Validate every echoed/raw record field without silently dropping credentials or frames. */
function parseSavedCalibrationRecord(value: unknown): SavedCalibrationRecord {
  if (!object(value)) invalid("The saved mapping record is invalid.");
  const record = value;
  exactKeys(record, BASE_KEYS, ["reuse"]);
  summary(record);
  const parsed = parseCalibration(record);
  if (record.id !== parsed.calibration_id || record.plane !== "measured_water_surface" || record.units !== "cm" || !parsed.homography_image_to_cm) invalid("The mapping ID, centimetre units, or measured water-surface matrix is missing.");
  let reuse: SavedCalibrationReuse | undefined;
  if (record.reuse !== undefined) {
    if (!object(record.reuse)) invalid("The saved alignment-check provenance is invalid.");
    const r = record.reuse;
    exactKeys(r, ["method", "source_calibration_id", "source_content_sha256", "check_pixels", "check_world_cm", "water_plane_unchanged"]);
    if (r.method !== "fixed_homography_current_checks_v1" || typeof r.source_calibration_id !== "string" || !ID.test(r.source_calibration_id)
      || typeof r.source_content_sha256 !== "string" || !/^[a-f0-9]{64}$/.test(r.source_content_sha256)
      || !pairs(r.check_pixels) || !pairs(r.check_world_cm) || r.check_pixels.length !== r.check_world_cm.length || r.water_plane_unchanged !== true) invalid("The saved alignment-check provenance is invalid.");
    reuse = { method: r.method, source_calibration_id: r.source_calibration_id, source_content_sha256: r.source_content_sha256,
      check_pixels: r.check_pixels.map(row => [...row]), check_world_cm: r.check_world_cm.map(row => [...row]), water_plane_unchanged: true };
  }
  return { ...parsed, id: record.id as string,
    homography_image_to_cm: parsed.homography_image_to_cm.map(row => [...row]), plane: "measured_water_surface", units: "cm", ...(reuse ? { reuse } : {}) };
}

function semanticJson(value: unknown): string {
  if (Array.isArray(value)) return "[" + value.map(semanticJson).join(",") + "]";
  if (object(value)) return "{" + Object.keys(value).sort().map(key => JSON.stringify(key) + ":" + semanticJson(value[key])).join(",") + "}";
  return JSON.stringify(value);
}

/** Keep the original stored JSON byte-for-byte: legacy Python hashes distinguish 1.0 from 1. */
export function parseSavedCalibrationBundle(value: unknown): SavedCalibrationBundle {
  if (!object(value)) invalid("Choose a Nemo saved calibration JSON file.");
  exactKeys(value, ["schema_version", "calibration", "calibration_json"]);
  if (value.schema_version !== SAVED_CALIBRATION_SCHEMA) invalid("This is not a supported Nemo saved calibration bundle.");
  if (typeof value.calibration_json !== "string" || !value.calibration_json.length
    || new TextEncoder().encode(value.calibration_json).byteLength > MAX_CALIBRATION_JSON_BYTES) invalid("The original calibration JSON must be a non-empty string of 32,000 bytes or less.");
  let raw: unknown;
  try { raw = JSON.parse(value.calibration_json); } catch { invalid("The original calibration JSON is not valid JSON."); }
  const calibration = parseSavedCalibrationRecord(value.calibration);
  const rawCalibration = parseSavedCalibrationRecord(raw);
  if (semanticJson(calibration) !== semanticJson(rawCalibration)) invalid("The echoed mapping does not match the original calibration JSON. Nothing was loaded.");
  return { schema_version: SAVED_CALIBRATION_SCHEMA, calibration, calibration_json: value.calibration_json };
}

export function parseSavedCalibrationText(text: string, fileSize?: number): SavedCalibrationBundle {
  if ((fileSize !== undefined && (!Number.isInteger(fileSize) || fileSize < 0 || fileSize > MAX_SAVED_CALIBRATION_BYTES))
    || new TextEncoder().encode(text).byteLength > MAX_SAVED_CALIBRATION_BYTES) invalid("The saved mapping file must be 64 KB or smaller.");
  let value: unknown;
  try { value = JSON.parse(text); } catch { invalid("The saved mapping file is not valid JSON."); }
  return parseSavedCalibrationBundle(value);
}

export function serializeSavedCalibration(bundle: SavedCalibrationBundle): string {
  const text = JSON.stringify(parseSavedCalibrationBundle(bundle), null, 2);
  if (new TextEncoder().encode(text).byteLength > MAX_SAVED_CALIBRATION_BYTES) invalid("The saved mapping file must be 64 KB or smaller.");
  return text + "\n";
}

export function parseSavedCalibrationList(value: unknown): SavedCalibrationSummary[] {
  if (!object(value)) invalid("The saved mapping list is invalid.");
  exactKeys(value, ["calibrations"]);
  if (!Array.isArray(value.calibrations) || value.calibrations.length > 500) invalid("The saved mapping list is invalid.");
  const reports = value.calibrations.map(item => {
    if (!object(item)) invalid("The saved mapping list is invalid.");
    exactKeys(item, SUMMARY_KEYS);
    return summary(item);
  });
  if (new Set(reports.map(item => item.calibration_id)).size !== reports.length) invalid("The saved mapping list contains repeated IDs.");
  return reports;
}

function noncollinear(points: number[][]): boolean {
  const [x, y] = points[0];
  return points.some(([ax, ay], i) => points.slice(i + 1).some(([bx, by]) => Math.abs((ax - x) * (by - y) - (ay - y) * (bx - x)) > 1e-8));
}

/** Reuses the saved H and surveyed cm positions; never infers new survey points from H. */
export function buildSavedCalibrationCheck(source: SavedCalibrationBundle, camera: CameraStatus | null, pixelText: string, worldText: string, unchanged: boolean) {
  const bundle = parseSavedCalibrationBundle(source), old = bundle.calibration;
  if (!old.approved) invalid("This saved mapping did not pass its original checks and cannot be reused.");
  if (!camera?.running || !camera.fresh || !camera.session_id || !SESSION.test(camera.session_id) || !camera.width || !camera.height) invalid("Start the local webcam and select its fresh camera session first.");
  if (camera.width !== old.image_size_px[0] || camera.height !== old.image_size_px[1]) invalid(`Use the saved ${old.image_size_px[0]} × ${old.image_size_px[1]} camera resolution before checking alignment.`);
  if (!unchanged) invalid("Confirm the camera still views the same surveyed water-surface plane.");
  const pixel = parsePairs(pixelText, "Current check pixels"), world = parsePairs(worldText, "Saved surveyed check positions (cm)");
  if (pixel.length < 3 || pixel.length > 100 || pixel.length !== world.length) invalid("Use three or more matching check points, with one saved centimetre position for each current pixel point.");
  if (pixel.some(([x, y]) => x < 0 || y < 0 || x >= camera.width! || y >= camera.height!)) invalid("Current check pixels must lie inside the camera frame.");
  for (const p of [pixel, world]) {
    if (new Set(p.map(row => row.join(","))).size !== p.length || !noncollinear(p)) invalid("Use distinct check points spread across the water surface, rather than a single line.");
  }
  const span = Math.max(...[0, 1].map(axis => Math.max(...world.map(p => p[axis])) - Math.min(...world.map(p => p[axis]))));
  if (span > 200) invalid("Saved check positions span more than 200 cm. Enter the original survey in centimetres.");
  return { source: bundle, camera_session_id: camera.session_id, image_size_px: [camera.width, camera.height] as [number, number], check_pixels: pixel, check_world_cm: world, water_plane_unchanged: true as const };
}

/** The server is authoritative; a historical report or changed matrix is never applied. */
export function acceptSavedCalibrationResult(value: unknown, source: SavedCalibrationBundle, camera: CameraStatus | null): CalibrationReport {
  const checked = parseSavedCalibrationRecord(value);
  const result = parseCalibration(checked), old = parseSavedCalibrationBundle(source).calibration;
  if (!checked.reuse || checked.reuse.source_calibration_id !== old.calibration_id) invalid("The response does not identify the saved source mapping. Nothing was applied.");
  if (!camera?.running || !camera.fresh || result.camera_session_id !== camera.session_id
    || result.image_size_px[0] !== camera.width || result.image_size_px[1] !== camera.height) invalid("The camera session changed during the check. Nothing was applied; check the current alignment again.");
  if (!result.approved) invalid(`Alignment check failed: ${result.max_error_cm.toFixed(2)} cm maximum error exceeds the saved ${result.max_allowed_error_cm.toFixed(2)} cm tolerance. Nothing was applied.`);
  if (result.max_allowed_error_cm !== old.max_allowed_error_cm || result.max_error_cm > old.max_allowed_error_cm
    || JSON.stringify(result.homography_image_to_cm) !== JSON.stringify(old.homography_image_to_cm)) invalid("The alignment response changed the saved matrix or tolerance. Nothing was applied.");
  if (result.calibration_id === old.calibration_id) invalid("The server returned the historical mapping instead of a new current-session alignment check.");
  return result;
}
