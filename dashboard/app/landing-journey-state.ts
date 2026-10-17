/** Landing-only presentation. No observations, scientific reports or provider calls. */
export const JOURNEY_CHAPTERS = [
  {
    id: "welcome", label: "Welcome", heading: "Nemo",
    detail: "Compare drifting-object observations, possible sources, and interception layouts using saved data and controlled tank experiments.",
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
