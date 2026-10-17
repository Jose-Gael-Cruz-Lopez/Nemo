/** The ocean preview is a forcing experiment, never a measured waste track. */
export type CurrentPoint = { time_utc: string; elapsed_s: number; latitude_deg: number; longitude_deg: number; eastward_m_s: number; northward_m_s: number; speed_m_s: number };
export type CurrentPath = { status: "COMPLETED" | "PARTIAL" | "UNSUPPORTED"; track: CurrentPoint[]; reason_code: string | null; requested_horizon_s: number; completed_horizon_s: number };
export type CurrentVector = Pick<CurrentPoint, "latitude_deg" | "longitude_deg" | "eastward_m_s" | "northward_m_s">;
export type CurrentForecast = {
  schema_version: 1; kind: "CURRENT_FORCED_PREVIEW"; snapshot_sha256: string; method_sha256: string;
  status: "COMPLETED" | "PARTIAL" | "UNSUPPORTED"; mode: "forecast_snapshot" | "archived_forecast_snapshot";
  release: { latitude_deg: number; longitude_deg: number; start_time_utc: string; horizon_s: number };
  dynamic: CurrentPath; persistence: CurrentPath;
  forcing: { source_url: string; metadata_url: string; attribution: string; captured_at_utc: string; valid_start_utc: string; valid_end_utc: string; model_issue_time_utc: string | null; depth_m: number; [key: string]: unknown };
  vector_frames: { time_utc: string; vectors: CurrentVector[] }[];
  endpoint_separation_m: number | null;
  validation: { measured_track_available: false; physical_validation: false; [key: string]: unknown };
  limitations: string[];
};

const hash = (value: unknown) => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value);
const close = (a: number, b: number, tolerance = 0.002) => Math.abs(a - b) <= tolerance;
const time = (value: unknown): value is string => {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z$/.test(value)) return false;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) && new Date(parsed).toISOString().slice(0, 19) === value.slice(0, 19)
    && Number(value.slice(0, 4)) >= 1900 && Number(value.slice(0, 4)) <= 2100;
};
const coordinates = (value: Record<string, unknown>) => finite(value.latitude_deg) && Math.abs(value.latitude_deg) <= 85
  && finite(value.longitude_deg) && value.longitude_deg >= -180 && value.longitude_deg < 180;
function position(value: unknown): value is CurrentVector & Record<string, unknown> {
  return object(value) && coordinates(value) && finite(value.eastward_m_s) && finite(value.northward_m_s)
    && Math.hypot(value.eastward_m_s, value.northward_m_s) <= 10 + 1e-9;
}
const https = (value: unknown) => {
  if (typeof value !== "string" || value.length > 5000) return false;
  try { const url = new URL(value); return url.protocol === "https:" && !url.username && !url.password; }
  catch { return false; }
};
function path(value: unknown, release: CurrentForecast["release"], validStart: number, validEnd: number): value is CurrentPath {
  if (!object(value) || !["COMPLETED", "PARTIAL", "UNSUPPORTED"].includes(String(value.status))
    || !Array.isArray(value.track) || value.track.length > 2049 || !finite(value.completed_horizon_s)
    || value.completed_horizon_s < 0 || value.completed_horizon_s > release.horizon_s
    || value.requested_horizon_s !== release.horizon_s) return false;
  if (value.status === "COMPLETED") {
    if (value.track.length < 2 || !close(value.completed_horizon_s, release.horizon_s) || value.reason_code !== null) return false;
  } else {
    if (typeof value.reason_code !== "string" || value.reason_code.length < 1 || value.reason_code.length > 100) return false;
    if (value.status === "PARTIAL" && (value.track.length < 2 || value.completed_horizon_s <= 0 || value.completed_horizon_s >= release.horizon_s)) return false;
    if (value.status === "UNSUPPORTED" && (value.completed_horizon_s !== 0 || value.track.length > 1)) return false;
  }
  const start = Date.parse(release.start_time_utc);
  for (let index = 0; index < value.track.length; index++) {
    const point: unknown = value.track[index];
    if (!object(point) || !position(point) || !time(point.time_utc) || !finite(point.elapsed_s)
      || !finite(point.speed_m_s) || point.speed_m_s < 0
      || !close(point.speed_m_s, Math.hypot(point.eastward_m_s, point.northward_m_s), 1e-9)
      || point.elapsed_s < 0 || point.elapsed_s > value.completed_horizon_s) return false;
    const stamp = Date.parse(point.time_utc);
    if (stamp < validStart || stamp > validEnd || !close((stamp - start) / 1000, point.elapsed_s)) return false;
    if (index === 0) {
      if (point.elapsed_s !== 0 || stamp !== start || !close(point.latitude_deg, release.latitude_deg, 1e-10)
        || !close(point.longitude_deg, release.longitude_deg, 1e-10)) return false;
    } else if (stamp <= Date.parse(value.track[index - 1].time_utc)
      || point.elapsed_s <= value.track[index - 1].elapsed_s) return false;
  }
  return value.track.length === 0 || close(value.track[value.track.length - 1].elapsed_s, value.completed_horizon_s);
}

export function validateCurrentForecast(value: unknown): CurrentForecast {
  const reject = () => { throw new Error("The current forecast is incomplete or has an unsupported scientific scope."); };
  if (!object(value) || value.schema_version !== 1 || value.kind !== "CURRENT_FORCED_PREVIEW" || !hash(value.snapshot_sha256) || !hash(value.method_sha256)
    || !["forecast_snapshot", "archived_forecast_snapshot"].includes(String(value.mode))
    || !object(value.release) || !coordinates(value.release) || !time(value.release.start_time_utc)
    || !finite(value.release.horizon_s) || value.release.horizon_s <= 0 || value.release.horizon_s > 21600
    || !object(value.forcing) || !time(value.forcing.captured_at_utc) || !time(value.forcing.valid_start_utc) || !time(value.forcing.valid_end_utc)
    || !https(value.forcing.source_url) || !https(value.forcing.metadata_url)
    || typeof value.forcing.attribution !== "string" || value.forcing.attribution.length < 1 || value.forcing.attribution.length > 2000
    || !finite(value.forcing.depth_m) || value.forcing.depth_m < 0
    || !(value.forcing.model_issue_time_utc === null || time(value.forcing.model_issue_time_utc))
    || !object(value.validation) || !["measured_track_available", "physical_validation", "plastic_motion_validated", "forecast_skill_established", "tank_flow_used", "heldout_buoy_positions_used"].every(key => value.validation !== null && (value.validation as Record<string, unknown>)[key] === false)
    || value.validation.ade_m !== null || value.validation.fde_m !== null
    || !Array.isArray(value.limitations) || value.limitations.length < 1 || value.limitations.length > 40
    || !value.limitations.every(item => typeof item === "string" && item.length > 0 && item.length <= 2000)) return reject();
  const release = value.release as CurrentForecast["release"], forcing = value.forcing;
  const start = Date.parse(release.start_time_utc), validStart = Date.parse(forcing.valid_start_utc as string), validEnd = Date.parse(forcing.valid_end_utc as string);
  if (validStart >= validEnd || start < validStart || start > validEnd
    || !path(value.dynamic, release, validStart, validEnd) || !path(value.persistence, release, validStart, validEnd)) return reject();
  const expectedStatus = value.dynamic.status === "COMPLETED" && value.persistence.status === "COMPLETED" ? "COMPLETED"
    : value.dynamic.completed_horizon_s > 0 || value.persistence.completed_horizon_s > 0 ? "PARTIAL" : "UNSUPPORTED";
  if (value.status !== expectedStatus || !(value.endpoint_separation_m === null || finite(value.endpoint_separation_m) && value.endpoint_separation_m >= 0)
    || (expectedStatus === "COMPLETED" ? value.endpoint_separation_m === null : value.endpoint_separation_m !== null)) return reject();
  if (!Array.isArray(value.vector_frames) || value.vector_frames.length < 1 || value.vector_frames.length > 25) return reject();
  for (let index = 0; index < value.vector_frames.length; index++) {
    const frame: unknown = value.vector_frames[index];
    if (!object(frame) || !time(frame.time_utc) || !Array.isArray(frame.vectors) || frame.vectors.length > 500 || !frame.vectors.every(position)) return reject();
    const stamp = Date.parse(frame.time_utc);
    if (stamp < validStart || stamp > validEnd || index > 0 && stamp <= Date.parse(value.vector_frames[index - 1].time_utc)) return reject();
  }
  return value as CurrentForecast;
}
