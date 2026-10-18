/** A saved-footage development comparison, never independent tank validation. */
export type ReplayBox = [number, number, number, number];
export type ReplayCounts = { accepted_frames: number; gap_frames: number; multiple_frames: number; scene_gap_frames: number };
export type ReplayExample = { jpeg_data_url: string; sequence: number; image_size_px: [number,number]; detection_polygon_px: number[][]; baseline_boxes_px: ReplayBox[]; accepted_boxes_px: ReplayBox[]; rejected_candidates: { bbox_px: ReplayBox; reason_codes: string[] }[] };
export type DetectorReplayClip = { id: string; label: string; source_kind: "estimated_rehearsal" | "diagnostic_frame"; source_id: string; original_camera_session_id: string; image_size_px: [number,number]; frames: number; baseline: ReplayCounts; surface: ReplayCounts; diagnostics: { rejection_counts: Record<string,number> }; example: ReplayExample };
export type DetectorReplayReport = { schema_version: "nemo_surface_replay_v1"; report_id: string; data_origin: "LOCAL_SAVED_FOOTAGE_REPLAY"; purpose: "DEVELOPMENT_REGRESSION"; validation_status: "UNVALIDATED"; measured_flow_eligible: false; camera_accessed: false; photon_messages_sent: false; evaluated_at: string; policy: { id: string; sha256: string }; manifest_sha256: string; totals: { frames: number; baseline_accepted_frames: number; surface_accepted_frames: number; baseline_ambiguous_frames: number; surface_ambiguous_frames: number; scene_gap_frames: number; roi_rejected_candidates: number; shape_rejected_candidates: number }; clips: DetectorReplayClip[]; warnings: string[] };
const object = (value: unknown): value is Record<string,unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const text = (value: unknown, max = 200): value is string => typeof value === "string" && value.length > 0 && value.length <= max;
const hash = (value: unknown): value is string => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
const count = (value: unknown, max = 1000000): value is number => Number.isInteger(value) && (value as number) >= 0 && (value as number) <= max;
function bad(): never { throw new Error("The saved-footage replay response did not match the development-only contract. Nothing was displayed as validated evidence."); }
function size(value: unknown): [number,number] {
  if (!Array.isArray(value) || value.length !== 2 || !value.every(item => Number.isInteger(item) && item >= 2 && item <= 4096)) bad();
  return [value[0],value[1]];
}
function box(value: unknown, [width,height]: [number,number]): ReplayBox {
  if (!Array.isArray(value) || value.length !== 4 || !value.every(finite) || value[0] < 0 || value[1] < 0 || value[2] <= 0 || value[3] <= 0 || value[0]+value[2] > width || value[1]+value[3] > height) bad();
  return [value[0],value[1],value[2],value[3]];
}
function boxes(value: unknown, dimensions: [number,number]): ReplayBox[] {
  if (!Array.isArray(value) || value.length > 1000) bad();
  return value.map(item => box(item,dimensions));
}
function counts(value: unknown, frames: number): ReplayCounts {
  if (!object(value) || ![value.accepted_frames,value.gap_frames,value.multiple_frames,value.scene_gap_frames].every(item => count(item,frames))
    || (value.accepted_frames as number)+(value.gap_frames as number) !== frames || (value.multiple_frames as number) > (value.gap_frames as number) || (value.scene_gap_frames as number) > (value.gap_frames as number)) bad();
  return { accepted_frames: value.accepted_frames as number, gap_frames: value.gap_frames as number, multiple_frames: value.multiple_frames as number, scene_gap_frames: value.scene_gap_frames as number };
}

export function parseDetectorReplay(value: unknown): DetectorReplayReport {
  if (!object(value) || value.schema_version !== "nemo_surface_replay_v1" || !text(value.report_id)
    || value.data_origin !== "LOCAL_SAVED_FOOTAGE_REPLAY" || value.purpose !== "DEVELOPMENT_REGRESSION" || value.validation_status !== "UNVALIDATED"
    || value.measured_flow_eligible !== false || value.camera_accessed !== false || value.photon_messages_sent !== false || !text(value.evaluated_at) || !Number.isFinite(Date.parse(value.evaluated_at))
    || !hash(value.manifest_sha256) || !object(value.policy) || !text(value.policy.id) || !hash(value.policy.sha256) || !object(value.policy.parameters)
    || !Array.isArray(value.clips) || !value.clips.length || value.clips.length > 20 || !Array.isArray(value.warnings) || value.warnings.length > 20 || !value.warnings.every(item => text(item,3000))) bad();
  if (value.policy.id !== "foreground_green_cap_v1") throw new Error("This saved replay uses an older detector policy. Replay the saved footage again to see the green-marker surface detector.");
  const clips = value.clips.map(clip => {
    if (!object(clip) || !text(clip.id) || !text(clip.label,300) || (clip.source_kind !== "estimated_rehearsal" && clip.source_kind !== "diagnostic_frame")
      || !text(clip.source_id) || !text(clip.original_camera_session_id,100) || !count(clip.frames,10000) || clip.frames < 1 || !object(clip.example) || !object(clip.diagnostics) || !object(clip.diagnostics.rejection_counts)) bad();
    const dimensions = size(clip.image_size_px), example = clip.example, imageSize = size(example.image_size_px);
    if (imageSize.join() !== dimensions.join() || !count(example.sequence,1000000000)
      || typeof example.jpeg_data_url !== "string" || example.jpeg_data_url.length > 2000000 || !/^data:image\/jpeg;base64,\/9j\/[A-Za-z0-9+/]*={0,2}$/.test(example.jpeg_data_url)
      || !Array.isArray(example.detection_polygon_px) || example.detection_polygon_px.length < 3 || example.detection_polygon_px.length > 100
      || !example.detection_polygon_px.every(point => Array.isArray(point) && point.length === 2 && point.every(finite) && point[0] >= 0 && point[0] < dimensions[0] && point[1] >= 0 && point[1] < dimensions[1])
      || !Array.isArray(example.rejected_candidates) || example.rejected_candidates.length > 1000) bad();
    const rejectionCounts: Record<string,number> = {};
    for (const [reason,n] of Object.entries(clip.diagnostics.rejection_counts)) { if (!text(reason,100) || !count(n)) bad(); rejectionCounts[reason] = n; }
    const rejected = example.rejected_candidates.map(candidate => {
      if (!object(candidate) || !Array.isArray(candidate.reason_codes) || candidate.reason_codes.length < 1 || candidate.reason_codes.length > 20 || !candidate.reason_codes.every(reason => text(reason,100))) bad();
      return { bbox_px: box(candidate.bbox_px,dimensions), reason_codes: [...candidate.reason_codes] as string[] };
    });
    // Read bounded actual pixel points for contract validation; never fabricate gap coordinates.
    if (!Array.isArray(clip.points) || clip.points.length !== clip.frames) bad();
    let previous = -Infinity, observed = 0;
    for (const point of clip.points) {
      if (!object(point) || !finite(point.t_s) || point.t_s < 0 || point.t_s <= previous || typeof point.observed !== "boolean" || (point.reason !== null && !text(point.reason))) bad();
      previous = point.t_s;
      if (point.observed) {
        observed++;
        if (!finite(point.pixel_x) || !finite(point.pixel_y) || point.pixel_x < 0 || point.pixel_x >= dimensions[0] || point.pixel_y < 0 || point.pixel_y >= dimensions[1]) bad();
        if ((point.estimated_x_cm !== undefined || point.estimated_y_cm !== undefined) && (!finite(point.estimated_x_cm) || !finite(point.estimated_y_cm))) bad();
      } else if (point.pixel_x !== undefined || point.pixel_y !== undefined || point.estimated_x_cm !== undefined || point.estimated_y_cm !== undefined) bad();
    }
    const surfaceCounts = counts(clip.surface,clip.frames);
    if (surfaceCounts.accepted_frames !== observed) bad();
    return { id: clip.id, label: clip.label, source_kind: clip.source_kind, source_id: clip.source_id, original_camera_session_id: clip.original_camera_session_id,
      image_size_px: dimensions, frames: clip.frames, baseline: counts(clip.baseline,clip.frames), surface: surfaceCounts, diagnostics: { rejection_counts: rejectionCounts },
      example: { jpeg_data_url: example.jpeg_data_url, sequence: example.sequence as number, image_size_px: imageSize,
        detection_polygon_px: example.detection_polygon_px.map(point => [...point]), baseline_boxes_px: boxes(example.baseline_boxes_px,dimensions), accepted_boxes_px: boxes(example.accepted_boxes_px,dimensions), rejected_candidates: rejected } } as DetectorReplayClip;
  });
  if (new Set(clips.map(clip => clip.id)).size !== clips.length || !object(value.totals)) bad();
  const totalKeys = ["frames","baseline_accepted_frames","surface_accepted_frames","baseline_ambiguous_frames","surface_ambiguous_frames","scene_gap_frames","roi_rejected_candidates","shape_rejected_candidates"] as const;
  if (totalKeys.some(key => !count((value.totals as Record<string,unknown>)[key]))) bad();
  const totals = Object.fromEntries(totalKeys.map(key => [key,(value.totals as Record<string,number>)[key]])) as DetectorReplayReport["totals"];
  if (totals.frames !== clips.reduce((n,clip) => n+clip.frames,0) || totals.baseline_accepted_frames !== clips.reduce((n,clip) => n+clip.baseline.accepted_frames,0)
    || totals.surface_accepted_frames !== clips.reduce((n,clip) => n+clip.surface.accepted_frames,0)) bad();
  return { schema_version: value.schema_version, report_id: value.report_id, data_origin: value.data_origin, purpose: value.purpose, validation_status: value.validation_status,
    measured_flow_eligible: false, camera_accessed: false, photon_messages_sent: false, evaluated_at: value.evaluated_at,
    policy: { id: value.policy.id, sha256: value.policy.sha256 }, manifest_sha256: value.manifest_sha256, totals, clips, warnings: [...value.warnings] as string[] };
}
