# Tideward ocean landing journey

The landing page is a presentation layer. It introduces the existing workspace without changing observations, scientific reports, provider settings, camera state, or Photon replies.

## Reference and adaptation

Reference: [Blue Marine Foundation — The Sea We Breathe](https://www.bluemarinefoundation.com/the-sea-we-breathe/journeys/marine-protected-areas/?section=12).

The browser review captured the entry frame, entry fade, continuing underwater motion, story presentation, route navigation, and audio control. It did not verify every frame or all twelve source sections. The implementation adapts those observed patterns with original Tideward wording, branding and generated ocean media; it does not reuse Blue Marine's wildlife assets, narration or scientific readouts.

| Observed reference pattern | Tideward implementation |
| --- | --- |
| Full-screen ocean scene and slow movement | One muted 10-second Higgsfield video, a still fallback, restrained light/particle layers |
| Outlined first line and solid second line | Five readable chapter headlines with short explanatory text |
| Minimal upper navigation | Journey, Evidence, Open workspace; compact mobile header |
| Curved route and chapter points | Five native anchor links with current-step indication |
| Globe and expedition readouts | Decorative globe, actual scroll progress and chapter name; no invented location, depth or temperature |
| Entry and audio controls | Explicit voice choice; per-chapter listen/mute; readable full-script captions |

The chapters are Welcome → Observe → Trace → Prevent → Verify. Each offers a direct route into the corresponding working feature. The workspace, demo and operator login remain available without listening or completing the journey.

## Motion, voice and accessibility

- Native scrolling and anchor navigation; no scroll interception or heavyweight 3D landing renderer.
- The poster stays visible when video fails or the visitor requests reduced motion. Playback pauses when the page is hidden or Pause motion is selected.
- Scroll progress updates at most once per animation frame, with resize-aware extent calculation. Chapter state follows visible section height.
- Voice uses the browser's speech engine after an explicit choice or Listen action. It does not call xAI, Chalk or another paid API. Availability and voice quality depend on the browser/operating system.
- “Narration playing” is shown only after the native speech start event. Errors/unsupported engines retain the complete captions. Changing chapter, hiding or leaving the page cancels narration.
- Entry activation transfers keyboard focus to the revealed demo action. Scrolling into the journey never steals focus.
- Mobile layouts reserve a separate bottom control rail. Caption text, motion controls and chapter navigation remain accessible.

## Media provenance

`dashboard/public/tideward-ocean-journey.mp4` was generated with the connected Higgsfield MCP, model `seedance_2_5`, 10 seconds, 1080p, 16:9, audio disabled. The prompt requested original luminous cyan/azure water, restrained reef scenery, open space for typography, slow camera motion, no text, logo, charts, people or robotics. The full submitted prompt, generation identifier and media hash are recorded in [the media receipt](research-evidence/ocean-landing-media-20261017.json).

The ocean is illustrative. Neither the background nor the landing animation is an observation, numerical ocean simulation, or physical experiment. Existing Data Lab results and tank validation boundaries remain explicit.

## Verification checkpoint

- All **237 frontend tests** passed, including 12 landing tests for routing, scroll/motion state, narrator lifecycle and explicit-entry focus behavior.
- Targeted ESLint and TypeScript checks passed. An isolated production build compiled all routes successfully without disturbing the running local server.
- Browser verification covered desktop 1274 × 748 and narrow 335 × 647 layouts, native entry focus, chapter navigation/current-step/progress, generated video decoding/playback, pause/resume, captions, confirmed native speech start in the in-app browser and cancellation on chapter change.
- The video decoded as 1920 × 1080, 10.041667 seconds, muted, ready state 4, with no media error. Voice playback was not independently verified in every browser; the Chrome background session did not consistently show an active speech state.
- No scientific-model outcome or physical protection claim follows from these presentation checks.

The preceding committed baseline `33280da7` has its own green hosted CI (1,809 Python tests, 225 frontend tests, 174 HTTP passes and six expected blocked hardware/provider checks). That historical run is not evidence for these subsequent landing changes.
