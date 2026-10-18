# Nemo ocean landing journey

Nemo is the current product name; stable `reeftrace` package names, API routes
and historical evidence IDs keep their identifiers. This guide describes the
current interface. The final local presentation check passed all 283 frontend
tests, full ESLint, TypeScript and an isolated production build. Hosted checks
are identified separately by their exact commit.

## Journey and presentation

The landing adapts the observed entry, underwater motion, typography and chapter
navigation of [Blue Marine Foundation — The Sea We Breathe](https://www.bluemarinefoundation.com/the-sea-we-breathe/journeys/marine-protected-areas/?section=12).
It uses Nemo's own copy and original generated ocean media. It is not a
pixel-identical or frame-by-frame reproduction of the reference.

- The entry headline is **Nemo**. The self-hosted **Rajdhani** family uses bold
  entry text and smaller **32–52 px** desktop chapter headings. Font files and
  their license are under `dashboard/public/fonts/rajdhani/`.
- Five chapters lead through **Welcome → Observe → Trace → Prevent → Verify**.
  Their feature links work without completing the story; **Open workspace**
  skips it and operator sign-in remains available.
- The slim curved route is **43 px** on desktop and **32 px** on narrow screens.
  Its progress follows actual native scroll extent, not environmental depth.
- **Scroll to explore** and the former bottom landing disclaimer are completely
  removed from rendered landing markup, rather than hidden with CSS. Source
  contracts assert their absence. Scientific scope remains visible inside the
  experiment and research features where a result is interpreted.
- There are no eyebrow labels, opening slogan, narration, voice choices,
  captions or manual motion controls. The video is silent and muted.

Native scrolling remains available for wheel, touch and keyboard. A bounded
animation-frame update reads section geometry before updating presentation.
Outgoing copy scales from **1 toward 1.6**, moves toward the viewer and fades;
incoming copy has its own arrival treatment. These are decorative depth cues,
not a fluid simulation or a measured camera calibration.

**Start journey** waits for its actual **460 ms** Web Animations entry transition
to finish, then scrolls natively to **Observe** and focuses its heading. The next
Tab reaches **Open observations**. Cancellation, repeated activation and unmount
are handled; ordinary scrolling does not steal focus. Reduced motion uses direct
entry and a still presentation. Hidden tabs pause media and continuous motion.

## Supplied AtomicGlobe integration

The current globe uses the actual supplied **AtomicGlobe / MeridianGlobe**
component, adapted locally to the existing Three.js dependency. It replaces the
earlier textured-sphere implementation. The preserved algorithm includes the
baked Natural Earth 110m occupancy grid, signed proximity field, deterministic
equal-area scatter, projection/formation math and **all six original GLSL
shaders**. An 8,000-dot target produces **7,996 actual land dots**. The globe is
illustrative Earth geography, not observation or reef-boundary data.

The local adapter removes Framer editor/property controls and unconfigured place
cards. It does **not** install a Framer package or fetch executable component code
at runtime. The [source receipt](research-evidence/atomic-globe-source.json)
records exact upstream URLs, immutable source capture and adapter hashes. The
captured 68,999-byte component SHA-256 is
`062a928e2d2244426ac8815a6b50ea455a5b6830aea03b4673902e40b2b696bb`.
Natural Earth coast geometry is public domain; the receipt records that no
explicit component-license declaration was present, without inventing one.

The globe is lazy-loaded only when eligible, caps device pixel ratio at **1.5**,
canvas layout at **512 × 512** and animation at **30 fps**. Hidden, off-screen or
reduced-motion state stops continuous updates; virtual time excludes pauses.
Context loss and initialization/render failure use the still fallback generated
from the same dot lattice. Pending frames, observers, listeners, geometry,
materials and renderer resources have deterministic teardown. The reticle and
white/cyan theme are presentation, with no cursor capture or evidence mutation.

## Original ocean media

The selected **`/nemo-ocean-depth.mp4`** is an original Higgsfield `seedance_2_5`
underwater journey: **20 seconds, 1920 × 1080, 16:9**, audio generation disabled.
It depicts a slow submerged camera glide. No reference-site footage or narration
is reused. The still fallback is **`/nemo-ocean-depth-poster.jpg`**.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| Video | 1,570,806 | `c2376dcc0da812eaa6108d48d7b07d2893166abbc89f45b640d6ee31c5710b87` |
| Poster | 67,698 | `4bf863f1b3a74da864e1971777e28f8461885be94be85ead7d815810bc8f1d8a` |

The [media receipt](research-evidence/nemo-ocean-depth-media-20261017.json)
preserves the generation prompt/job and actual browser decode: **20.041667 s**,
1920 × 1080, ready state 4 and no media error. The poster is the first decoded
frame resized to 1280 × 720. Earlier ten-second Tideward media remains historical.
The page starts with a poster until motion preference is known and retains it
when video cannot play.

## Workspace continuation and verification scope

The [scientific demo guide](nemo-scientific-demo.md) describes the separate
light-blue workspace: a full-height scientific layout, compact navigation,
three short demo steps and one interception plot before its checkbox controls.
Its supplied Glyph Trail background is decorative. Landing media, globe,
scroll effects and glyph motion never become source, current or trial evidence.
Opening the landing enables no camera, pump, model request or Photon reply.

The historical **`f3353e0`** checkpoint's [hosted CI run 39079486572](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/actions/runs/39079486572)
passed all three jobs. The newer AtomicGlobe/Glyph Trail/workspace revision
passed 283 frontend tests, full ESLint, TypeScript and an isolated production
build. Browser checks verified the live AtomicGlobe, blue Glyph Trail, removed
footer elements, layout comparison and checkbox/filter behavior. Its exact-commit
hosted result must be read from the release checks. Device performance, live
provider success and physical interception require their own evidence.
