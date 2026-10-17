# Nemo ocean landing journey

Nemo is the current product name. `reeftrace`, existing package/API names, immutable evidence IDs and historical Tideward documents retain their identifiers. The landing introduces the existing workspace without changing observations, scientific reports, provider settings, camera state or Photon replies.

## Current design

Reference: [Blue Marine Foundation — The Sea We Breathe](https://www.bluemarinefoundation.com/the-sea-we-breathe/journeys/marine-protected-areas/?section=12).

The browser review captured the entry frame, entry fade, continuing underwater motion, story presentation, route navigation and typography. It did not verify every frame or all twelve source sections. Nemo adapts those observed patterns with original wording, branding and generated ocean media.

- The hero is the single word **Nemo**. The old opening slogan is removed.
- The exact reference headline family is **Rajdhani**: the live reference entry heading computed to Rajdhani 700, and its story headings to Rajdhani 500. The local page uses those weights, not Impact or a merely named fallback.
- Font files are self-hosted from the official [Google Fonts Rajdhani source](https://github.com/google/fonts/tree/main/ofl/rajdhani), with its SIL Open Font License preserved at `dashboard/public/fonts/rajdhani/OFL.txt`. No Google font request is needed at runtime or build time.
- There is no landing narration, voice choice, Listen/Mute button, audio status or caption panel. There are no Pause/Resume motion buttons.
- One original muted ocean video, a still fallback and restrained light/particle layers provide the background.
- The five native scroll chapters are Welcome → Observe → Trace → Prevent → Verify. Each links directly into the corresponding working feature.
- A curved route, decorative globe and real scroll progress introduce the journey without fabricated depth, temperature, coordinates or environmental readings.
- The workspace, read-only software demo and operator login remain available without completing the journey.

## Motion and accessibility

Native scrolling and anchors remain available; no scroll interception or heavyweight 3D landing renderer is used. The page respects `prefers-reduced-motion` automatically and suspends video/CSS motion when hidden. The poster remains visible when video fails or reduced motion is requested. Scroll progress updates at most once per animation frame, with resize-aware extent calculation; chapter state follows visible section height.

Explicit **Start journey** activation transfers keyboard focus to the revealed demo action. Scrolling into the journey does not steal focus. Mobile layouts keep the chapter content separate from the progress display. Text is real selectable text, with local-font fallback and normal keyboard links.

## Media provenance and scientific limits

`dashboard/public/tideward-ocean-journey.mp4` was generated with the connected Higgsfield MCP, model `seedance_2_5`, 10 seconds, 1080p, 16:9, audio disabled. The original asset filename remains stable. The full prompt, generation identifier and hash are in [the media receipt](research-evidence/ocean-landing-media-20261017.json).

The ocean is illustrative. Neither the background nor its animation is an observation, numerical ocean simulation or physical experiment. Data Lab results and tank validation boundaries remain explicit. The page makes no provider request and does not enable xAI, Chalk or Photon.

## Verification history

The earlier narrated Tideward landing passed 237 frontend tests and a production build, documented in its [historical receipt](research-evidence/ocean-landing-verification-20261017.json). That receipt describes its capture-time interface, not the current silent design.

The silent Nemo revision retains eight focused tests covering legacy routes, bounded scroll progress, automatic motion preferences/visibility, explicit-entry focus, the absence of removed controls and actual bundled font data/weights. Full frontend, browser and production-build results for the final pushed revision must be recorded separately. Completed presentation tests do not establish source probabilities, plastic-prediction skill, a measured tank result or reef benefit.
