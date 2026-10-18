/** Presentation-only globe math and lifecycle. No scientific or device state. */
import type { AtomicGlobeConfig } from "./atomic-globe-runtime.mjs";
export const GLOBE_MAX_DPR = 1.5;
export const GLOBE_MAX_FPS = 30;
export const GLOBE_ANGULAR_SPEED = 0.018;
const TAU = 2 * Math.PI;

export type GlobeControls = {
  progress: number;
  motion: boolean;
  reducedMotion: boolean;
  hidden: boolean;
  intersecting: boolean;
};
export type GlobePose = { rotationX: number; rotationY: number };

/** SVG attributes are serialized in both Node and the browser. Trig engines can
 * differ by a few ulps, so retain visual precision without hydration differences. */
export function globeReticleTicks() {
  return Array.from({ length: 33 }, (_, index) => {
    const angle = (-87 + index * 2.6) * Math.PI / 180;
    const outside = index % 4 === 0 ? 86 : 83;
    return { x1: (94.5 + 78 * Math.cos(angle)).toFixed(4),
      y1: (94.5 + 78 * Math.sin(angle)).toFixed(4),
      x2: (94.5 + outside * Math.cos(angle)).toFixed(4),
      y2: (94.5 + outside * Math.sin(angle)).toFixed(4) };
  });
}

export function clampGlobeProgress(value: number): number {
  return Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : 0;
}

export function globePixelRatio(value: number): number {
  return Number.isFinite(value) && value > 0 ? Math.min(value, GLOBE_MAX_DPR) : 1;
}

/** Actual supplied AtomicGlobe renderer settings; no operational place labels. */
export function atomicGlobeConfig(progress: number): AtomicGlobeConfig {
  return { ink: "#f4fbff", tint: "#a6edff", accent: "#a6edff", backFade: .14,
    dotSize: 3.2, sizeJitter: .6, coastLift: .35, dotTarget: 8000,
    spin: .035, tilt: 18, startLng: -15 + 1.1 * clampGlobeProgress(progress), zoom: .9,
    offsetX: 0, offsetY: 0, allowTiltDrag: false, tiltRange: 0,
    formation: "sweep", entranceSeconds: 2.2, replayOnScroll: false,
    cursorMode: "off", reach: .5, waveLength: .22, waveSpeed: 0,
    crest: .035, swell: 1.2, glow: 1, cursorDelay: 0,
    routesOn: false, routeMode: "chain", routeStyle: "comet", routeWidth: 2,
    dashCount: 18, routeSpeed: 0, routeAltitude: .4, routeTrail: .3,
    routeDots: 56, routeSize: 6, routeRest: .32, quality: "high",
    editorPlayback: false, places: [], focus: -1 };
}

export function globePose(progress: number, phase = 0): GlobePose {
  const boundedPhase = Number.isFinite(phase) ? ((phase % TAU) + TAU) % TAU : 0;
  // Three SphereGeometry's front is longitude -90 at rotationY=0.
  // Start centred over the Atlantic (-15 longitude,+15 latitude), then let
  // explicit journey progress turn toward the Americas. This is illustrative.
  return { rotationX: Math.PI / 12,
    rotationY: (-75 + 1.1 * clampGlobeProgress(progress)) * Math.PI / 180 + boundedPhase };
}

export function globeCanAnimate(state: GlobeControls): boolean {
  return state.motion && !state.reducedMotion && !state.hidden && state.intersecting;
}

export type LandPolygon = number[][][];
export type LandGeometry = LandPolygon[];

/** Admit only bounded, closed, geographic Polygon/MultiPolygon land rings. */
export function parseGlobeLand(value: unknown): LandGeometry {
  if (!value || typeof value !== "object" || !("type" in value) || value.type !== "FeatureCollection"
      || !("features" in value) || !Array.isArray(value.features)
      || !value.features.length || value.features.length > 256) throw new Error("Invalid land collection");
  const polygons: LandGeometry = [];
  let points = 0;
  for (const feature of value.features) {
    const geometry = feature?.geometry;
    const candidates = geometry?.type === "Polygon" ? [geometry.coordinates]
      : geometry?.type === "MultiPolygon" ? geometry.coordinates : null;
    if (!Array.isArray(candidates)) throw new Error("Unsupported land geometry");
    for (const polygon of candidates) {
      if (!Array.isArray(polygon) || !polygon.length || polygon.length > 64) throw new Error("Invalid land polygon");
      const copy: LandPolygon = [];
      for (const ring of polygon) {
        if (!Array.isArray(ring) || ring.length < 4) throw new Error("Invalid land ring");
        const coordinates: number[][] = [];
        for (const point of ring) {
          if (!Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite)
              || Math.abs(point[0]) > 180 || Math.abs(point[1]) > 90 || ++points > 20_000)
            throw new Error("Invalid geographic land coordinate");
          coordinates.push([point[0], point[1]]);
        }
        const first = coordinates[0], last = coordinates.at(-1)!;
        if (first[0] !== last[0] || first[1] !== last[1]) throw new Error("Land rings must close");
        for (let index = 1; index < coordinates.length; index++) {
          const previous = coordinates[index - 1], current = coordinates[index];
          // Natural Earth's global Antarctica polygon closes across the entire
          // south-pole edge. Keep that texture-edge closure; never unwrap it
          // through a continent. Any other unsplit seam is unsupported.
          if (Math.abs(current[0] - previous[0]) > 180
              && !(Math.abs(current[1]) === 90 && current[1] === previous[1]))
            throw new Error("Land ring crosses an unsplit longitude seam");
        }
        copy.push(coordinates);
      }
      polygons.push(copy);
    }
  }
  return polygons;
}

export function landTexturePoint(longitude: number, latitude: number, width: number, height: number): [number, number] {
  if (![longitude, latitude, width, height].every(Number.isFinite)
      || Math.abs(longitude) > 180 || Math.abs(latitude) > 90 || width <= 0 || height <= 0)
    throw new Error("Texture coordinates require finite geographic degrees and positive dimensions");
  return [(longitude + 180) / 360 * width, (90 - latitude) / 180 * height];
}

/** Dispose every registered resource exactly once, even if one cleanup throws. */
export function createGlobeResourceScope() {
  let disposed = false;
  const callbacks: Array<() => void> = [];
  const invoke = (callback: () => void) => { try { callback(); } catch { /* Continue remaining cleanup. */ } };
  return {
    add(callback: () => void) { if (disposed) invoke(callback); else callbacks.push(callback); },
    dispose() { if (disposed) return; disposed = true; callbacks.reverse().forEach(invoke); callbacks.length = 0; },
  };
}

export function createGlobeFrameDriver(options: {
  requestFrame: (callback: (time: number) => void) => number;
  cancelFrame: (id: number) => void;
  draw: (pose: GlobePose, elapsedSeconds: number) => void;
}) {
  let state: GlobeControls = { progress: 0, motion: false, reducedMotion: true, hidden: false, intersecting: false };
  let disposed = false, frame: number | null = null, previous: number | null = null, generation = 0;
  let lastDraw: number | null = null, dirty = true, phase = 0, elapsedSeconds = 0;
  let pose = globePose(0);
  const visible = () => !state.hidden && state.intersecting;
  function schedule() {
    if (!disposed && frame === null && visible()) {
      const current = generation;
      frame = options.requestFrame(time => { if (!disposed && generation === current) tick(time); });
    }
  }
  function cancel() { generation++; if (frame !== null) options.cancelFrame(frame); frame = null; previous = null; }
  function tick(time: number) {
    frame = null;
    if (disposed || !visible()) return;
    const animated = globeCanAnimate(state);
    if (animated) {
      const delta = previous === null || !Number.isFinite(time) ? 0 : Math.max(0, Math.min(.1, (time - previous) / 1000));
      elapsedSeconds += delta;
      phase = (phase + delta * GLOBE_ANGULAR_SPEED) % TAU;
      previous = time;
    } else previous = null;
    if (dirty || animated) {
      if (lastDraw === null || time - lastDraw >= 1000 / GLOBE_MAX_FPS - .01) {
        if (animated) pose = globePose(state.progress, phase);
        options.draw(pose, elapsedSeconds); dirty = false; lastDraw = time;
      }
    }
    if (animated || dirty) schedule();
  }
  return {
    update(next: Partial<GlobeControls>) {
      if (disposed) return;
      const before = globeCanAnimate(state), wasVisible = visible(), wasReduced = state.reducedMotion;
      const previousProgress = state.progress;
      state = { ...state, ...next, progress: clampGlobeProgress(next.progress ?? state.progress) };
      const animated = globeCanAnimate(state);
      if (!visible()) { cancel(); return; }
      if (!wasVisible || wasReduced !== state.reducedMotion) { dirty = true; lastDraw = null; }
      if (before !== animated) { previous = null; if (!animated) cancel(); }
      if (animated && previousProgress !== state.progress) dirty = true;
      if (animated || dirty) schedule();
    },
    invalidate() { if (!disposed) { dirty = true; schedule(); } },
    dispose() { if (disposed) return; disposed = true; cancel(); },
  };
}

export type GlobeFrameDriver = ReturnType<typeof createGlobeFrameDriver>;
