/** Browser-owned preview only. This module has no upload, recording or API transport. */
export const LOCAL_CAMERA_COMPANION = "http://127.0.0.1:3000/workspace#camera";

export type PreviewDevice = { id: string; label: string };
export type PreviewDimensions = { width: number; height: number };
export type HostedCameraState = {
  status: "idle" | "requesting" | "live" | "error";
  stream: MediaStream | null;
  devices: readonly PreviewDevice[];
  selectedDeviceId: string;
  cameraLabel: string;
  dimensions: PreviewDimensions | null;
  error: string | null;
  warning: string | null;
};

export type CameraMediaAccess = Pick<MediaDevices, "getUserMedia" | "enumerateDevices">;

export const INITIAL_HOSTED_CAMERA_STATE: HostedCameraState = {
  status: "idle", stream: null, devices: [], selectedDeviceId: "", cameraLabel: "",
  dimensions: null, error: null, warning: null,
};

/** Deliberately lazy: constructing or rendering a controller never reads a camera. */
export function browserCameraAccess(): CameraMediaAccess {
  if (typeof window === "undefined" || !window.isSecureContext ||
      !navigator.mediaDevices?.getUserMedia || !navigator.mediaDevices.enumerateDevices) {
    throw { name: "CameraUnavailableError" };
  }
  return {
    getUserMedia: constraints => navigator.mediaDevices.getUserMedia(constraints),
    enumerateDevices: () => navigator.mediaDevices.enumerateDevices(),
  };
}

export function cameraPermissionMessage(error: unknown): string {
  const name = error !== null && typeof error === "object" && "name" in error ? error.name : "";
  switch (name) {
    case "NotAllowedError":
    case "PermissionDeniedError":
      return "Camera permission was denied. Allow this site to use your camera in the browser’s site settings, then press Start preview again.";
    case "NotFoundError":
    case "DevicesNotFoundError":
      return "No camera was found. Connect a webcam, check its cable, then press Start preview again.";
    case "NotReadableError":
    case "TrackStartError":
      return "The camera could not be opened. Close other camera apps or tabs, check your system’s camera privacy settings, then try again.";
    case "OverconstrainedError":
    case "ConstraintNotSatisfiedError":
      return "The selected camera is unavailable. Reconnect it or press Start preview to choose a camera again.";
    case "CameraUnavailableError":
    case "SecurityError":
      return "Camera preview needs a supported browser on HTTPS or localhost. Open the secure app directly and try again.";
    case "AbortError":
      return "The camera request was interrupted. Press Start preview to try again.";
    default:
      return "Camera preview could not start. Check the camera connection and browser permissions, then press Start preview again.";
  }
}

function stopTracks(stream: MediaStream) {
  for (const track of stream.getTracks()) {
    try { track.stop(); } catch { /* Continue releasing every other track. */ }
  }
}

function dimensions(width?: number, height?: number): PreviewDimensions | null {
  return Number.isInteger(width) && Number.isInteger(height) && width! > 0 && height! > 0
    ? { width: width!, height: height! } : null;
}

/** Owns one local MediaStream and rejects every late permission/device-switch result. */
export class HostedCameraController {
  private state = INITIAL_HOSTED_CAMERA_STATE;
  private listeners = new Set<() => void>();
  private generation = 0;
  private currentStream: MediaStream | null = null;
  private detachEnded: (() => void)[] = [];
  private readonly resolveMedia: () => CameraMediaAccess;

  constructor(resolveMedia: () => CameraMediaAccess = browserCameraAccess) { this.resolveMedia = resolveMedia; }

  getSnapshot = (): HostedCameraState => this.state;
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };

  private publish(state: HostedCameraState) {
    this.state = state;
    for (const listener of this.listeners) listener();
  }

  private releaseCurrent() {
    for (const detach of this.detachEnded) detach();
    this.detachEnded = [];
    const stream = this.currentStream;
    this.currentStream = null;
    if (stream) stopTracks(stream);
  }

  /** Synchronous release is also used before following the local-companion link. */
  close = () => {
    this.generation++;
    this.releaseCurrent();
    if (this.state !== INITIAL_HOSTED_CAMERA_STATE) this.publish(INITIAL_HOSTED_CAMERA_STATE);
  };

  async start(deviceId?: string): Promise<void> {
    const request = ++this.generation;
    const previousDevices = this.state.devices;
    this.releaseCurrent();
    this.publish({ ...INITIAL_HOSTED_CAMERA_STATE, status: "requesting", devices: previousDevices,
      selectedDeviceId: deviceId ?? "" });

    let access: CameraMediaAccess;
    let stream: MediaStream;
    try {
      access = this.resolveMedia();
      stream = await access.getUserMedia({ audio: false,
        video: deviceId ? { deviceId: { exact: deviceId } } : true });
    } catch (error) {
      if (request === this.generation) this.publish({ ...INITIAL_HOSTED_CAMERA_STATE,
        status: "error", error: cameraPermissionMessage(error) });
      return;
    }
    if (request !== this.generation) { stopTracks(stream); return; }

    const videoTracks = stream.getVideoTracks();
    const track = videoTracks.find(candidate => candidate.readyState === "live");
    if (!track) {
      stopTracks(stream);
      this.publish({ ...INITIAL_HOSTED_CAMERA_STATE, status: "error",
        error: "The camera returned no live video. Reconnect it and press Start preview again." });
      return;
    }
    // The browser was asked for no audio. Release any unexpected audio tracks as well.
    for (const audioTrack of stream.getAudioTracks()) audioTrack.stop();
    this.currentStream = stream;
    const settings = track.getSettings();
    const ended = () => {
      if (request !== this.generation || stream !== this.currentStream) return;
      this.generation++;
      this.releaseCurrent();
      this.publish({ ...INITIAL_HOSTED_CAMERA_STATE, status: "error",
        error: "The camera disconnected or access ended. Reconnect it and press Start preview again." });
    };
    for (const videoTrack of videoTracks) {
      videoTrack.addEventListener("ended", ended);
      this.detachEnded.push(() => videoTrack.removeEventListener("ended", ended));
    }
    this.publish({ ...INITIAL_HOSTED_CAMERA_STATE, status: "live", stream,
      cameraLabel: track.label || "Browser-selected camera",
      selectedDeviceId: settings.deviceId ?? deviceId ?? "",
      dimensions: dimensions(settings.width, settings.height) });

    // Labels are often unavailable until permission is granted. Never request a second stream to list them.
    try {
      const devices = await access.enumerateDevices();
      if (request !== this.generation || stream !== this.currentStream) return;
      const cameras: PreviewDevice[] = [];
      const seen = new Set<string>();
      for (const device of devices) if (device.kind === "videoinput" && device.deviceId && !seen.has(device.deviceId)) {
        seen.add(device.deviceId);
        cameras.push({ id: device.deviceId, label: device.label || `Camera ${cameras.length + 1}` });
      }
      this.publish({ ...this.state, devices: cameras });
    } catch {
      if (request === this.generation && stream === this.currentStream) this.publish({ ...this.state,
        warning: "The preview is live, but this browser could not list other cameras. Close preview and try again to refresh the list." });
    }
  }

  setDimensions(stream: MediaStream, width: number, height: number) {
    const value = dimensions(width, height);
    if (stream !== this.currentStream || !value ||
        (value.width === this.state.dimensions?.width && value.height === this.state.dimensions.height)) return;
    this.publish({ ...this.state, dimensions: value });
  }

  playbackFailed(stream: MediaStream) {
    if (stream !== this.currentStream) return;
    this.generation++;
    this.releaseCurrent();
    this.publish({ ...INITIAL_HOSTED_CAMERA_STATE, status: "error",
      error: "This browser could not play the camera preview. Check camera permissions, then press Start preview again." });
  }
}
