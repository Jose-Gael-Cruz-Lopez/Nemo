/** Landing-only presentation. No observations, scientific reports or provider calls. */
export const JOURNEY_CHAPTERS = [
  {
    id: "welcome", label: "Welcome", eyebrow: "OBSERVE. TRACE. PREVENT.",
    outline: "Follow the", solid: "current.",
    detail: "From a drifting object to a better place to intercept it. A clearer path to coastal protection.",
    action: "Explore the software demo", href: "/demo",
    secondaryAction: "Discover the experiment", secondaryHref: "#journey-observe",
    evidence: "Illustrative ocean, not a live observation.",
    narration: "Welcome to Tideward. Follow a drifting object from observation to evidence. Explore how we compare possible sources and interception layouts, then see what still needs to be tested in a real tank. This ocean scene is illustrative, the software demo is synthetic, and physical validation is pending.",
  },
  {
    id: "observe", label: "Observe", eyebrow: "01 / BEGIN WITH WHAT YOU CAN SEE",
    outline: "Every drift.", solid: "A clue.",
    detail: "Start with an observation. A moving path tells us more than an object already stuck in place.",
    action: "Open observations", href: "/workspace#investigations",
    secondaryAction: "Follow the evidence", secondaryHref: "#journey-trace",
    evidence: "Saved examples first. Measured tank paths require camera calibration.",
    narration: "Observe first. A sequence of recorded positions tells us how an object moved. An object already stuck in place may not tell us how it arrived. Tideward keeps synthetic examples separate from measured observations. A real tank recording needs a fixed camera and a measured water-plane calibration.",
  },
  {
    id: "trace", label: "Trace", eyebrow: "02 / ASK WHERE IT COULD HAVE ENTERED",
    outline: "Possible paths.", solid: "Honest limits.",
    detail: "Compare candidate sources against the saved movement. When the evidence cannot distinguish them, the answer stays unknown.",
    action: "Investigate a source", href: "/workspace#investigations",
    secondaryAction: "Look ahead", secondaryHref: "#journey-prevent",
    evidence: "Source support is conditional evidence, not proof of a polluter.",
    narration: "Trace the possibilities. Tideward compares declared candidate sources against the saved observation and model assumptions. Source support is relative evidence, not a calibrated probability or proof of who caused pollution. When the observation is insufficient, the result stays unknown. Chalk can explain the saved evidence and its limits, but cannot change it.",
  },
  {
    id: "prevent", label: "Prevent", eyebrow: "03 / TEST WHERE AN INTERCEPTION COULD HELP",
    outline: "Before it", solid: "reaches the reef.",
    detail: "Follow changing currents. Compare two layouts around a protected area, then explore the separate tank experiment in 3D.",
    action: "Compare interception layouts", href: "/workspace#prevention",
    secondaryAction: "What proves it works?", secondaryHref: "#journey-verify",
    evidence: "Ocean scenarios and the 3D tank replay are distinct model views. Neither is a measured protection claim.",
    narration: "Prevent is a testable question: which interception layout could keep more floating paths away from a protected area? The ocean scenario follows changing model currents. The separate three-dimensional tank replay displays saved simulated paths and the full comparison. A better simulated layout is a hypothesis for a real experiment, not measured reef protection.",
  },
  {
    id: "verify", label: "Verify", eyebrow: "04 / EXPECTED IS ONLY HALF THE STORY",
    outline: "Predict it.", solid: "Then test it.",
    detail: "Read the NOAA model comparisons. Record independent tank trials. Keep predictions beside what was actually measured.",
    action: "Explore Data Lab", href: "/workspace#data",
    secondaryAction: "Open the workspace", secondaryHref: "/workspace",
    evidence: "A completed buoy comparison does not validate plastic motion or a physical tank. Actual tank trials remain to be run.",
    narration: "Verify the prediction. Data Lab preserves real historical NOAA buoy comparisons, including results where a simple drift baseline performed better than a current-only model. Those processed buoy positions do not validate loose plastic or the tank. The next physical step is independent calibrated recordings and counted trials. Keep expected outcomes, measured outcomes, and missing evidence separate.",
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

export function motionAllowed(state: { reducedMotion: boolean; paused: boolean; hidden: boolean }): boolean {
  return !state.reducedMotion && !state.paused && !state.hidden;
}

export type NarrationState = "off" | "loading" | "speaking" | "unsupported" | "error";
type VoiceEngine = Pick<SpeechSynthesis, "speak" | "cancel">;
export type JourneyNarrator = { play: (text: string) => void; stop: () => void; dispose: () => void };

/** No speech until play() is explicitly called. Generation checks ignore late browser events. */
export function createJourneyNarrator(engine: VoiceEngine | null, utterance: (text: string) => SpeechSynthesisUtterance, onState: (state: NarrationState) => void): JourneyNarrator {
  let generation = 0, disposed = false;
  const stop = () => { generation++; engine?.cancel(); if (!disposed) onState("off"); };
  return {
    play(text) {
      if (disposed) return;
      stop();
      if (!engine) { onState("unsupported"); return; }
      const current = generation;
      try {
        const message = utterance(text);
        message.lang = "en-US"; message.rate = .93;
        message.onstart = () => { if (!disposed && generation === current) onState("speaking"); };
        message.onend = () => { if (!disposed && generation === current) onState("off"); };
        message.onerror = () => { if (!disposed && generation === current) onState("error"); };
        onState("loading"); engine.speak(message);
      } catch { if (!disposed && generation === current) onState("error"); }
    },
    stop,
    dispose() { disposed = true; generation++; engine?.cancel(); },
  };
}
