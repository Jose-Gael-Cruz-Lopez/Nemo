/** Landing-only presentation. No observations, scientific reports or provider calls. */
export const JOURNEY_CHAPTERS = [
  {
    id: "welcome", label: "Welcome", heading: "Nemo",
    detail: "Trace possible pollution sources from observed movement, then compare where to intercept it and test the outcome.",
    action: "Open the software demo", href: "/demo",
    secondaryAction: "Observe a track", secondaryHref: "#journey-observe",
    evidence: "Illustrative ocean, not a live observation.",
  },
  {
    id: "observe", label: "Observe", heading: "Observe the drift.",
    detail: "Load a saved track or record a calibrated tank observation.",
    action: "Open observations", href: "/workspace#investigations",
    secondaryAction: "Find possible sources", secondaryHref: "#journey-trace",
    evidence: "Tank measurements require a calibrated camera.",
  },
  {
    id: "trace", label: "Trace", heading: "Find possible sources.",
    detail: "Compare candidate entry points against the observed path. Insufficient evidence remains unknown.",
    action: "Investigate a source", href: "/workspace#investigations",
    secondaryAction: "Compare layouts", secondaryHref: "#journey-prevent",
    evidence: "Relative source support does not identify a polluter.",
  },
  {
    id: "prevent", label: "Prevent", heading: "Compare interception layouts.",
    detail: "Compare two interception layouts under the same simulated releases and currents.",
    action: "Compare interception layouts", href: "/workspace#prevention",
    secondaryAction: "Check the evidence", secondaryHref: "#journey-verify",
    evidence: "Ocean predictions and tank simulations are separate; neither establishes measured reef protection.",
  },
  {
    id: "verify", label: "Verify", heading: "Check the evidence.",
    detail: "Compare forecasts with historical NOAA buoy positions and separately recorded tank trials.",
    action: "Open Data Lab", href: "/workspace#data",
    secondaryAction: "Open the workspace", secondaryHref: "/workspace",
    evidence: "Buoy results do not validate plastic motion. Physical tank trials remain pending.",
  },
] as const;

const LEGACY_VIEWS = new Set(["overview", "investigations", "prevention", "camera", "data", "settings"]);
export function legacyWorkspaceDestination(hash: string): string | null {
  const [view, search = ""] = hash.replace(/^#/, "").split("?");
  if (!LEGACY_VIEWS.has(view)) return null;
  const caseId = new URLSearchParams(search).get("case");
  return `/workspace#${view}${caseId && caseId.length <= 200 ? `?case=${encodeURIComponent(caseId)}` : ""}`;
}

/** Actual native scroll extent only: no invented position, temperature or depth. */
export function journeyProgress(scrollTop: number, scrollHeight: number, clientHeight: number): number {
  if (![scrollTop, scrollHeight, clientHeight].every(Number.isFinite) || scrollHeight <= clientHeight) return 0;
  return Math.round(Math.max(0, Math.min(1, scrollTop / (scrollHeight - clientHeight))) * 100);
}

export function motionAllowed(state: { reducedMotion: boolean; hidden: boolean }): boolean {
  return !state.reducedMotion && !state.hidden;
}

/** Only native chapter IDs belong to the landing page; legacy views route elsewhere. */
export function journeyHashTarget(hash: string): string | null {
  const chapter = JOURNEY_CHAPTERS.find(item => hash === `#journey-${item.id}`);
  return chapter ? `journey-${chapter.id}` : null;
}

/** One initial post-layout native restore. No focus changes or persistent frame loop. */
export function createJourneyHashRestore(options: {
  readHash: () => string;
  hidden: () => boolean;
  findSection: (id: string) => { scrollIntoView: (options: { behavior: "instant"; block: "start" }) => void } | null;
  requestFrame: (callback: () => void) => number;
  cancelFrame: (id: number) => void;
}) {
  const target = journeyHashTarget(options.readHash());
  let complete = target === null, disposed = false, generation = 0, pending: number | null = null;
  function suspend() { generation++; if (pending !== null) options.cancelFrame(pending); pending = null; }
  function schedule(settleLayout: boolean) {
    const current = generation;
    pending = options.requestFrame(() => {
      if (disposed || current !== generation) return;
      pending = null;
      if (options.hidden()) return;
      // A newer native navigation always wins over the initial URL restore.
      if (journeyHashTarget(options.readHash()) !== target) { complete = true; return; }
      if (settleLayout) { schedule(false); return; }
      complete = true;
      if (target) options.findSection(target)?.scrollIntoView({ behavior: "instant", block: "start" });
    });
  }
  function resume() { if (!disposed && !complete && pending === null && !options.hidden()) schedule(true); }
  return {
    resume,
    visibilityChanged() { if (options.hidden()) suspend(); else resume(); },
    dispose() { disposed = true; suspend(); },
  };
}

/** Decorative journey path. Its points are interface positions, not geography. */
export const JOURNEY_ROUTE_PATH = "M30 20C39 64 4 94 16 135S39 208 28 250S1 322 12 365S40 438 26 480";
export const JOURNEY_ROUTE_STOPS = [{ x: 30, y: 20 }, { x: 16, y: 135 }, { x: 28, y: 250 }, { x: 12, y: 365 }, { x: 26, y: 480 }] as const;
const ROUTE_CURVES = [
  [[30,20],[39,64],[4,94],[16,135]],
  [[16,135],[28,176],[39,208],[28,250]],
  [[28,250],[17,292],[1,322],[12,365]],
  [[12,365],[23,408],[40,438],[26,480]],
] as const;
export const JOURNEY_ROUTE_DOTS = ROUTE_CURVES.flatMap(curve => [1,2,3,4].map(step => {
  const t = step / 5, u = 1 - t;
  const coordinate = (axis: 0 | 1) => u ** 3 * curve[0][axis] + 3 * u ** 2 * t * curve[1][axis] + 3 * u * t ** 2 * curve[2][axis] + t ** 3 * curve[3][axis];
  return { x: coordinate(0), y: coordinate(1) };
}));

/** Native-scroll presentation geometry, never a physical ocean measurement. */
export function chapterDepthFrame(input: { sectionTop: number; sectionHeight: number; viewportHeight: number; motion: boolean }) {
  const { sectionTop, sectionHeight, viewportHeight, motion } = input;
  const valid = [sectionTop, sectionHeight, viewportHeight].every(Number.isFinite) && sectionHeight > 0 && viewportHeight > 0;
  const visible = valid && sectionTop < viewportHeight && sectionTop + sectionHeight > 0;
  if (!motion || !valid) return { scale: 1, opacity: 1, shiftPx: 0, visible };
  if (!visible) return { scale: 1, opacity: 0, shiftPx: 0, visible: false };
  const depart = Math.max(0, Math.min(1, -sectionTop / viewportHeight));
  const arrive = Math.max(0, Math.min(1, sectionTop / viewportHeight));
  return {
    scale: 1 + .6 * depart - .12 * arrive,
    opacity: Math.max(0, 1 - Math.max(1.7 * depart, 1.3 * arrive)),
    // Compensate native vertical travel so the copy approaches the viewer.
    shiftPx: sectionTop === 0 ? 0 : -.75 * sectionTop,
    visible: true,
  };
}

type EntryExit = { finished: PromiseLike<unknown>; cancel: () => void };
export function createJourneyEntryAdvance(options: {
  exit: () => EntryExit | null;
  advance: (motion: boolean) => void;
  running: (value: boolean) => void;
}) {
  let generation = 0, disposed = false, running = false, animation: EntryExit | null = null;
  function release() { animation?.cancel(); animation = null; }
  function cancel() { generation++; running = false; release(); if (!disposed) options.running(false); }
  return {
    async start(motion: boolean): Promise<boolean> {
      if (disposed || running) return false;
      const current = ++generation; running = true; options.running(true);
      let animated = false;
      if (motion) {
        try {
          animation = options.exit();
          if (animation) { animated = true; await animation.finished; }
        } catch {
          // WAAPI cancel rejects asynchronously. A cancelled run must not release
          // an animation owned by a later Start click before this catch resumes.
          if (disposed || current !== generation) return false;
          animated = false; release(); /* Fall back to native entry. */
        }
      }
      if (disposed || current !== generation) return false;
      running = false; options.running(false); options.advance(motion && animated);
      return true;
    },
    release,
    cancel,
    dispose() { disposed = true; cancel(); },
  };
}
