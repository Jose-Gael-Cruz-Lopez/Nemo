import type { BufferGeometry, WebGLRenderer } from "three";

export type AtomicGlobeConfig = {
  ink: string; tint: string; accent: string; backFade: number;
  dotSize: number; sizeJitter: number; coastLift: number; dotTarget: number;
  spin: number; tilt: number; startLng: number; zoom: number; offsetX: number; offsetY: number;
  allowTiltDrag: boolean; tiltRange: number; formation: string; entranceSeconds: number;
  replayOnScroll: boolean; cursorMode: string; reach: number; waveLength: number;
  waveSpeed: number; crest: number; swell: number; glow: number; cursorDelay: number;
  routesOn: boolean; routeMode: string; routeStyle: string; routeWidth: number;
  dashCount: number; routeSpeed: number; routeAltitude: number; routeTrail: number;
  routeDots: number; routeSize: number; routeRest: number; quality: string;
  editorPlayback: boolean; places: never[]; focus: number;
};
export class GlobeRuntime {
  constructor(host: HTMLDivElement, config: AtomicGlobeConfig, still: boolean);
  still: boolean;
  renderer: WebGLRenderer;
  field: { geometry: BufferGeometry } | null;
  tick(virtualTimeMilliseconds: number): void;
  apply(config: AtomicGlobeConfig): void;
  resize(): void;
  dispose(): void;
}
export function scatterLandDots(target: number): {
  position: Float32Array; seed: Float32Array; coast: Float32Array; count: number;
};
export function inflateCoastGrid(): Uint8Array;
export function inlandDepth(u: number, v: number): number;
