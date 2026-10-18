/** Approximate display/rehearsal coordinates never grant measured calibration approval. */
import { convexHull, invertMatrix, projectPoint, type Point, type WaterMapping } from "./camera-grid-state.ts";
import type { CameraStatus, TokenReference } from "./field-workflow-state.ts";
import { parseSavedCalibrationBundle, type SavedCalibrationBundle } from "./saved-calibration-state.ts";

export const ESTIMATED_TRAY_BOUNDS = { x_min_cm: 0, x_max_cm: 35.56, y_min_cm: 0, y_max_cm: 22.86 } as const;
export type RehearsalBounds = { x_min_cm: number; x_max_cm: number; y_min_cm: number; y_max_cm: number };
export type EstimatedWaterMapping = WaterMapping & { approved: false; estimated: true; plane: "estimated_water_surface"; units: "cm"; homography_image_to_cm: number[][]; mapping_polygon_px: number[][] };
const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
function invalid(message: string): never { throw new Error(message); }

function current(source: SavedCalibrationBundle | null, camera: CameraStatus | null) {
  if (!source) invalid("Load the saved mapping before using estimated coordinates.");
  const bundle = parseSavedCalibrationBundle(source);
  if (!camera?.running || !camera.fresh || !camera.session_id || !camera.width || !camera.height) invalid("Start the local camera and wait for fresh frames first.");
  if (camera.width !== bundle.calibration.image_size_px[0] || camera.height !== bundle.calibration.image_size_px[1]) invalid("The camera resolution must match the saved mapping before estimating coordinates.");
  return { bundle, camera };
}

/** An inverse projection of the declared tray rectangle, not newly measured marks. */
export function estimatedTrayMapping(source: SavedCalibrationBundle | null, camera: CameraStatus | null, bounds: RehearsalBounds = ESTIMATED_TRAY_BOUNDS): EstimatedWaterMapping {
  const { bundle, camera: live } = current(source, camera);
  const matrix = bundle.calibration.homography_image_to_cm;
  const inverse = invertMatrix(matrix);
  if (!inverse) invalid("The saved mapping matrix cannot be used for an estimated grid.");
  if (![bounds.x_min_cm, bounds.x_max_cm, bounds.y_min_cm, bounds.y_max_cm].every(finite) || bounds.x_max_cm <= bounds.x_min_cm || bounds.y_max_cm <= bounds.y_min_cm
    || bounds.x_max_cm - bounds.x_min_cm > 200 || bounds.y_max_cm - bounds.y_min_cm > 200) invalid("Use finite, ordered tabletop tray bounds spanning at most 200 cm.");
  const corners: Point[] = [[bounds.x_min_cm, bounds.y_min_cm], [bounds.x_max_cm, bounds.y_min_cm], [bounds.x_max_cm, bounds.y_max_cm], [bounds.x_min_cm, bounds.y_max_cm]];
  const signs = corners.map(([x, y]) => inverse[2][0] * x + inverse[2][1] * y + inverse[2][2]);
  if (Math.min(...signs) <= 0 && Math.max(...signs) >= 0) invalid("The saved mapping crosses a projection horizon over the estimated tray.");
  const pixels = corners.map(point => projectPoint(inverse, point));
  if (pixels.some(point => !point)) invalid("The estimated tray corners cannot be projected into this frame.");
  const hull = convexHull(pixels);
  if (hull.length !== 4 || hull.some(([x, y]) => x < 0 || y < 0 || x > live.width! - 1 || y > live.height! - 1)) invalid("The estimated tray extends outside this camera frame. Keep the whole tray visible before using this saved mapping.");
  return { approved: false, estimated: true, plane: "estimated_water_surface", units: "cm", camera_session_id: live.session_id!,
    image_size_px: [live.width!, live.height!], homography_image_to_cm: matrix.map(row => [...row]), mapping_polygon_px: hull };
}

/** A separate endpoint/record kind: never /recordings, /flow/fit-recordings or a LIVE case. */
export function buildEstimatedRehearsalRequest(source: SavedCalibrationBundle | null, camera: CameraStatus | null, reference: TokenReference | null, durationText: string, bounds: RehearsalBounds = ESTIMATED_TRAY_BOUNDS) {
  const { bundle, camera: live } = current(source, camera);
  estimatedTrayMapping(bundle, live, bounds);
  if (!bundle.calibration.approved) invalid("The historical mapping did not pass its own checks; it cannot be used for this estimated rehearsal.");
  if (!reference || reference.camera_session_id !== live.session_id || reference.image_size_px[0] !== live.width || reference.image_size_px[1] !== live.height
    || !reference.reference_id || !Array.isArray(reference.token_area_px_range) || reference.token_area_px_range.length !== 2
    || !reference.token_area_px_range.every(finite) || reference.token_area_px_range[0] <= 0 || reference.token_area_px_range[1] <= reference.token_area_px_range[0]) invalid(reference?.detector === "foreground_surface_v2" ? "The green-cap detector needs its own policy-specific image-size check before live capture. Saved-footage replay runs without this step." : "Capture a current empty-tank reference and use Measure one token to learn its pixel size. No ruler measurement is needed for that image-size step.");
  const duration = Number(durationText);
  if (!durationText.trim() || !Number.isFinite(duration) || duration < 1 || duration > 10) invalid("Use a rehearsal duration between 1 and 10 seconds.");
  return { source: bundle, camera_session_id: live.session_id!, image_size_px: [live.width!, live.height!] as [number, number], duration_s: duration,
    detector: reference.detector === "foreground_surface_v2" ? "foreground_surface_v2" as const : "foreground_reference_v1" as const, reference_id: reference.reference_id, acknowledge_estimated_mapping: true as const };
}

export type RehearsalObservedPoint = { observed: true; t_s: number; frame_id: string; pixel_x: number; pixel_y: number; estimated_x_cm: number; estimated_y_cm: number; track_id: string; association_break: boolean; reason: string | null; area_px: number; bbox_px: number[]; quality: number };
export type RehearsalGap = { observed: false; t_s: number; frame_id: string; reason: string };
export type EstimatedRehearsalPoint = RehearsalObservedPoint | RehearsalGap;
export type EstimatedRehearsal = { id: string; camera_session_id: string; image_size_px: [number, number]; data_origin: "LOCAL_CAPTURE_ESTIMATED_COORDINATES"; validation_status: "UNVALIDATED"; calibration_id: null; profile_id: null; case_id: null; source_calibration_id: string; duration_s: number; recorded_at: number; timestamp_kind: "host_receipt_not_exposure"; evidence_frame_ids: string[]; points: EstimatedRehearsalPoint[]; warnings: string[]; frames: number; observed: number };
const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const text = (value: unknown, max = 200): value is string => typeof value === "string" && value.length > 0 && value.length <= max;
function keys(record: Record<string, unknown>, required: string[], optional: string[] = []) {
  if (required.some(key => !Object.hasOwn(record, key)) || Object.keys(record).some(key => !required.includes(key) && !optional.includes(key))) invalid("The rehearsal response contains missing or unsupported fields. Nothing was displayed as a trial.");
}

/** Parse only the isolated unvalidated record; measured-coordinate fields are rejected. */
export function parseEstimatedRehearsal(value: unknown, source: SavedCalibrationBundle | null, camera: CameraStatus | null): EstimatedRehearsal {
  const { bundle, camera: live } = current(source, camera), original = bundle.calibration;
  if (!object(value)) invalid("The rehearsal response was incomplete.");
  keys(value, ["id", "schema_version", "camera_session_id", "image_size_px", "data_origin", "validation_status", "calibration_id", "profile_id", "case_id", "source_calibration_id", "source_content_sha256", "source_camera_session_id", "historical_max_error_cm", "historical_tolerance_cm", "current_alignment_verified", "approved_for_inference", "capture_backend", "timestamp_kind", "duration_s", "recorded_at", "detection", "points", "evidence_frame_ids", "frames", "observed", "warnings", "validation_warning"]);
  if (!text(value.id) || !/^rehearsal-[a-f0-9]+$/.test(value.id) || value.schema_version !== "nemo_estimated_rehearsal_v1"
    || value.data_origin !== "LOCAL_CAPTURE_ESTIMATED_COORDINATES" || value.validation_status !== "UNVALIDATED"
    || value.calibration_id !== null || value.profile_id !== null || value.case_id !== null || value.current_alignment_verified !== false || value.approved_for_inference !== false
    || value.timestamp_kind !== "host_receipt_not_exposure") invalid("This response is not an isolated, unvalidated camera rehearsal.");
  if (value.camera_session_id !== live.session_id || !Array.isArray(value.image_size_px) || value.image_size_px.length !== 2 || value.image_size_px[0] !== live.width || value.image_size_px[1] !== live.height) invalid("The camera session or resolution changed. The rehearsal was not applied.");
  if (value.source_calibration_id !== original.calibration_id || value.source_camera_session_id !== original.camera_session_id
    || value.historical_max_error_cm !== original.max_error_cm || value.historical_tolerance_cm !== original.max_allowed_error_cm
    || typeof value.source_content_sha256 !== "string" || !/^[a-f0-9]{64}$/.test(value.source_content_sha256)) invalid("The rehearsal does not identify the selected historical mapping.");
  if (!finite(value.duration_s) || value.duration_s < 1 || value.duration_s > 10 || !finite(value.recorded_at) || value.recorded_at <= 0 || value.recorded_at > 1e12
    || (value.capture_backend !== null && !text(value.capture_backend, 100)) || !text(value.validation_warning, 2000)
    || !Array.isArray(value.warnings) || value.warnings.length < 1 || value.warnings.length > 10 || !value.warnings.every(item => text(item, 2000))) invalid("The rehearsal timing or warning metadata is invalid.");
  const detection = value.detection;
  if (!object(detection)) invalid("The rehearsal detector metadata is invalid.");
  const surface = detection.detector === "foreground_surface_v2";
  keys(detection, ["detector", "reference_id", "token_area_px_range"], surface ? ["detection_polygon_px", "policy_id", "policy_sha256"] : []);
  if (surface && (!Array.isArray(detection.detection_polygon_px) || detection.detection_polygon_px.length < 3 || detection.detection_polygon_px.length > 100
    || !detection.detection_polygon_px.every(point => Array.isArray(point) && point.length === 2 && point.every(finite) && point[0] >= 0 && point[0] < live.width! && point[1] >= 0 && point[1] < live.height!)
    || detection.policy_id !== "foreground_green_cap_v1" || typeof detection.policy_sha256 !== "string" || !/^[a-f0-9]{64}$/.test(detection.policy_sha256))) invalid("The frozen surface detector policy is invalid.");
  if ((!surface && detection.detector !== "foreground_reference_v1") || !text(detection.reference_id) || !Array.isArray(detection.token_area_px_range)
    || detection.token_area_px_range.length !== 2 || !detection.token_area_px_range.every(finite) || detection.token_area_px_range[0] <= 0 || detection.token_area_px_range[1] <= detection.token_area_px_range[0]) invalid("The rehearsal detector metadata is invalid.");
  if (!Array.isArray(value.points) || !value.points.length || value.points.length > 1000 || !Array.isArray(value.evidence_frame_ids)
    || value.evidence_frame_ids.length !== value.points.length || !value.evidence_frame_ids.every(item => text(item))
    || new Set(value.evidence_frame_ids).size !== value.evidence_frame_ids.length) invalid("The rehearsal frame accounting is invalid.");
  let previousTime = -Infinity;
  const points: EstimatedRehearsalPoint[] = value.points.map((point, index) => {
    if (!object(point) || typeof point.observed !== "boolean" || !finite(point.t_s) || point.t_s < 0 || point.t_s > (value.duration_s as number) + 1
      || point.t_s <= previousTime || !text(point.frame_id) || point.frame_id !== (value.evidence_frame_ids as string[])[index]) invalid("The rehearsal point timing or frame identity is invalid.");
    previousTime = point.t_s;
    if (!point.observed) {
      keys(point, ["t_s", "observed", "reason", "frame_id"]);
      if (!text(point.reason)) invalid("Missing detections must retain their gap reason.");
      return { observed: false, t_s: point.t_s, reason: point.reason, frame_id: point.frame_id };
    }
    keys(point, ["t_s", "observed", "reason", "frame_id", "pixel_x", "pixel_y", "estimated_x_cm", "estimated_y_cm", "track_id", "association_break", "area_px", "bbox_px", "quality"]);
    if (!finite(point.pixel_x) || !finite(point.pixel_y) || point.pixel_x < 0 || point.pixel_x >= live.width! || point.pixel_y < 0 || point.pixel_y >= live.height!
      || !finite(point.estimated_x_cm) || !finite(point.estimated_y_cm) || !text(point.track_id) || typeof point.association_break !== "boolean"
      || (point.reason !== null && !text(point.reason)) || !finite(point.area_px) || point.area_px <= 0 || !finite(point.quality) || point.quality < 0 || point.quality > 1
      || !Array.isArray(point.bbox_px) || point.bbox_px.length !== 4 || !point.bbox_px.every(finite) || point.bbox_px[2] <= 0 || point.bbox_px[3] <= 0) invalid("The rehearsal detection metadata is invalid.");
    const projected = projectPoint(original.homography_image_to_cm, [point.pixel_x, point.pixel_y]);
    if (!projected || Math.abs(projected[0] - point.estimated_x_cm) > 1e-6 || Math.abs(projected[1] - point.estimated_y_cm) > 1e-6) invalid("Estimated coordinates do not match the unchanged saved mapping.");
    return { observed: true, t_s: point.t_s, reason: point.reason, frame_id: point.frame_id, pixel_x: point.pixel_x, pixel_y: point.pixel_y,
      estimated_x_cm: point.estimated_x_cm, estimated_y_cm: point.estimated_y_cm, track_id: point.track_id, association_break: point.association_break,
      area_px: point.area_px, bbox_px: [...point.bbox_px], quality: point.quality };
  });
  const observed = points.filter(point => point.observed).length;
  if (value.frames !== points.length || value.observed !== observed) invalid("The rehearsal frame counts do not match its captured points.");
  return { id: value.id, camera_session_id: live.session_id!, image_size_px: [live.width!, live.height!], data_origin: value.data_origin, validation_status: value.validation_status,
    calibration_id: null, profile_id: null, case_id: null, source_calibration_id: original.calibration_id, duration_s: value.duration_s,
    recorded_at: value.recorded_at, timestamp_kind: value.timestamp_kind, evidence_frame_ids: [...value.evidence_frame_ids], points,
    warnings: [...value.warnings], frames: points.length, observed };
}

/** Break lines at detector gaps, association breaks, or changed track identities. */
export function rehearsalSegments(points: EstimatedRehearsalPoint[]): RehearsalObservedPoint[][] {
  const segments: RehearsalObservedPoint[][] = []; let current: RehearsalObservedPoint[] = [];
  for (const point of points) {
    if (!point.observed) { current = []; continue; }
    if (!current.length || point.association_break || current.at(-1)?.track_id !== point.track_id) { current = []; segments.push(current); }
    current.push(point);
  }
  return segments;
}
