// Adapted from the user-supplied AtomicGlobe module. See vendor/atomic-globe/adapt.mjs and provenance.
/**
 * MeridianGlobe.tsx — interactive stippled world globe for Framer.
 *
 * Landmasses are drawn as a field of dots sampled with an equal-area ring
 * lattice (no Fibonacci spiral, so there is no spiral banding to hide). The
 * coastline comes from a run-length-encoded occupancy grid baked into this
 * file, expanded at runtime into a signed proximity field so coastlines can be
 * resolved below grid resolution and so each dot knows how far inland it sits.
 *
 * Rendering is three.js Points with one custom material. All per-frame work
 * lives in a plain GlobeRuntime object; React only constructs it, pushes
 * config into it, and tears it down.
 */ function _define_property(obj, key, value) { if (key in obj) {
    Object.defineProperty(obj, key, { value: value, enumerable: true, configurable: true, writable: true });
}
else {
    obj[key] = value;
} return obj; }
import * as THREE from "three";
/* ------------------------------------------------------------------ *
* Coastline data
*
* An occupancy grid (1 = land) walked in serpentine order and stored as
* alternating run lengths, starting with water. Each run length is a little-
* endian base-32 varint; every character carries five payload bits plus a
* continuation flag in bit 5. Derived from Natural Earth 110m land, which is
* public domain.
* ------------------------------------------------------------------ */
const GRID_COLS = 448;
const GRID_ROWS = 224;
const COAST_RUNS = ["LR3iWfC1291A1W622w12~1Sa7Q14t221J1w23g89M6b1k6X1B123329O29z6326Y2cC1Z19c29c2W57234k4z2E1751~27~8444G1x289137", "3i3X4a528522232dax2H11U17D1hw49utscx3Z1e65566452724X45g32fsL1$26x1vw1853Y3uy15~2I1H29G4ca345254239qI1Z24tF11", "655g5Y23eY16134g5Z2E1x1b5224123412131319D472d1446125ipE1$24h4311x2ddC11pH317d5s7V1E1kp35216i43A19n2mof212bl6", "54rgE1R1dJ172H3d2bb2S32555w1lR1x1jd5664245h3l4vk2fw284e73688kvS1rj15218352C82u335w1W1rdb3257291347225~1eaeC3", "614bdpX1y1422v2G81y121253qy12onafb31~2227b2a3E38d33cijbw1e3d6~a3f3dvamfhf561y383h1bU25413b314hdq2y1e3y63B63e", "Z1bh225pX2B1X2b131231263k9Y1f4N52fcc242F56fX18s8kV2A1h141y2kat4Y1g4E5513ar87B55hZ11o16alZ1641e31D1a21eV1kc33", "S2f7Y43474I14mN497j2D2ikP1p4T1313oP1jjC24f125721L4m8G19mO46433d4C2jeU1u3M13y1U1clA24d2248M4n8K18oL4a222c4A2n", "6Y1C12P2Y13sX1534ax522j6N15gI56624W1s4X132R315V14tV13473K5f3T12f22H528w2s3W1y4S222~171J522W222J581~12352G212", "A412C24254y212L522X213P5Z186F212F412E277Z1P531Y215H32g1N1~12cG2I4G21121F2E1333d6G3F3G36j3D1G2K2I4C223J2h3i52", "3c6G362V257G34adh343bL214B2G4z2I2g31553efa4D377V2112cw369736c36316gH2A2G4w2M2de53c384a7Z2d2~23e82Q24s1121141", "561acN2~1H4$1M2ca272345s5P22223g3$23f39M26s4441kcN2Z1J4X1P2ak1643s6M294d3x33b45R24t528321158aP2W1M4W1P21254d", "d16S35495y3a448F311sg42S2V1O4U1T2lr22F38268F3412dG3vmU2P1W4L1U2puH3a311S32bH3g28uU2K1Z4I1V2w14a324I3b1C4~32y", "1V2E122$423t4213V2E22W2N4U23g121R1U22915m21z512jh2T2G24T2P4R25g3V1Q23ih23y542gi3P2X13g631L2R4K2117h3Y1O22jf3", "1E523ek1N2$13i513H2R413~1d42j2~1J21pcM514bC3w24pcZ132O425W1cq3x2M24ia42P59h134I2z23pcr1rF522k5meo3z2G23a2c9x", "21U11~1b75b4E2z23nii7i32I533g9gjm4y2z2423c57b$11Y3c36g125x2y25kkecf32~42ifddlj3A2A2162ciz6gW2A24hmbfgg3M43fd", "13fbqc4C2V2dI623623Q2C24cr8i12ee2O41efl8ta2E2O2cX6aP2F227w17lfe121H4221ea22m7B121G2P26B75P2H2D17m248e141D414", "1f842m7t29F2z24d4F73a9y2F246u6m256g311E411141f371n4w1N2W111g94I782jX1M2w1321l262n2B45s2m221x1M2V1o15P713oV1K", "2B13l2r123A4481i3m2D1H2W1ow8p21T1f4T1w23g292L45e442X1S17bS1uw8vT11g22M1Y1424d6W45c414Z1L1H2x1$7z1H2K1~1413a8", "K41b98215y2J1F2A1X7B1F2I1A258c7122w4232223b66C2G1G2B1U7E1D2G1D257a31z44a2113975F2F1B2H1S7J1A2D1G266833e234x3", "81332843766I2B1$1P1T7S1Z1A1K24a253d11dJ228cg211h4L2z1Z1S1S7V1X1x1N23h121ib4111D222c41x12Q2x1X1V1T7U1Y1x1O242", "2x1c91C2ctaQ2x1X1U1W7T1Y1x1V25313241f733$11f2r241A3x1Z1R1Z7Q1Z1y1z3141t3P21$3z1Z1Q1~7N1~1z1O31b1X2277M3z1~1N", "1w8M1w2z192A3863V247822~229A1~1L1z8K1~1A184Z2d75q1X156fY267z1~1J1E8G1w2y167Y2i45r1d2G172lX268w1w2E1L8D1w2v96", "X2uD11I1vW26auw2D1M8D1x2rc6T2A1L2E1R25bsz2B1M8B1z2sa6Q2G1j1y12kI1O269sB2A1M8z1C2ra6O2J1F2K1P25aqG2w1M8uI2pc4", "O2M1B2M1Q23doK2sL8tK2nA3O1y2N1B3mL2tK8tL2lC3N1y2N1C3kN2sK8sO2iE3M1y2M1F3hQ2qK8qR2gF3M1z2q5fI3dU2oK8nV2cJ3cbn", "B2lebK3aV2nK8mW24R35j21hI11rgp3Q613iH8kQ7et1d2tdR7kF8kS7cv275y1312W7jF8dD9473C9fE8eE91c3t5B8bE8dA83t4g3t2B8b", "11E8az94k6x9cC8ay95o5z9aB8bAjbB8aZd1G5aA88Ij8A88a4Zi8D88Cj8K8411W$4131A9111zb1S72Z84L47C11g575k7w3w13n114121", "26x1dI44U83G4j34hO2M2U2bz191W34P8317z33eM16G3M1L36C227P2813G8818~1132332Q24X3oY33A3Z1738q7w6131d1p9X1B7pD7T1", "g52125c47s1K47fO1V1z7z1B7U1C3Q2A3P1H7E1N7X1V2y2F3Q1R7A1Y7a6A1z343H137~2z189V7I1J7hab1jV2C253A3478abS7K1~737f", "Q3w2Q35O8x1NcG14oNcaOcsU13TO2"].join("");
const RUN_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ$~";
let runDigits = null;
const digitOf = ch => { if (!runDigits) {
    runDigits = {};
    for (let i = 0; i < RUN_ALPHABET.length; i++)
        runDigits[RUN_ALPHABET[i]] = i;
} return runDigits[ch] ?? 0; }; /** Expand COAST_RUNS back into a row-major occupancy grid. */
const inflateCoastGrid = () => {
    const cells = new Uint8Array(GRID_COLS * GRID_ROWS);
    const serpentine = new Uint8Array(GRID_COLS * GRID_ROWS);
    let cursor = 0;
    let write = 0;
    let value = 0;
    while (cursor < COAST_RUNS.length && write < serpentine.length) {
        let run = 0;
        let shift = 0;
        let digit = 0;
        do {
            digit = digitOf(COAST_RUNS[cursor++]);
            run |= (digit & 31) << shift;
            shift += 5;
        } while (digit & 32 && cursor < COAST_RUNS.length);
        const stop = Math.min(write + run, serpentine.length);
        if (value)
            serpentine.fill(1, write, stop);
        write = stop;
        value ^= 1;
    } // Odd rows were walked right-to-left when the runs were built.
    let read = 0;
    for (let row = 0; row < GRID_ROWS; row++) {
        const base = row * GRID_COLS;
        if (row & 1) {
            for (let col = GRID_COLS - 1; col >= 0; col--)
                cells[base + col] = serpentine[read++];
        }
        else {
            for (let col = 0; col < GRID_COLS; col++)
                cells[base + col] = serpentine[read++];
        }
    }
    return cells;
}; /**
 * Chamfer distance transform over the grid, wrapping at the antimeridian.
 * Returns, for every cell, the approximate distance in cells to the nearest
 * cell whose occupancy differs — signed positive on land.
 */
const buildProximityField = cells => {
    const W = GRID_COLS;
    const H = GRID_ROWS;
    const FAR = 1e6;
    const ORTHO = 1;
    const DIAG = 1.41421356;
    const sweep = target => { const d = new Float32Array(W * H); for (let i = 0; i < d.length; i++)
        d[i] = cells[i] === target ? 0 : FAR; const wrapCol = c => c < 0 ? c + W : c >= W ? c - W : c; const relax = (i, j, cost) => { const v = d[j] + cost; if (v < d[i])
        d[i] = v; }; for (let y = 0; y < H; y++) {
        for (let x = 0; x < W; x++) {
            const i = y * W + x;
            const l = y * W + wrapCol(x - 1);
            relax(i, l, ORTHO);
            if (y > 0) {
                const up = (y - 1) * W;
                relax(i, up + x, ORTHO);
                relax(i, up + wrapCol(x - 1), DIAG);
                relax(i, up + wrapCol(x + 1), DIAG);
            }
        }
    } for (let y = H - 1; y >= 0; y--) {
        for (let x = W - 1; x >= 0; x--) {
            const i = y * W + x;
            const r = y * W + wrapCol(x + 1);
            relax(i, r, ORTHO);
            if (y < H - 1) {
                const dn = (y + 1) * W;
                relax(i, dn + x, ORTHO);
                relax(i, dn + wrapCol(x - 1), DIAG);
                relax(i, dn + wrapCol(x + 1), DIAG);
            }
        }
    } return d; }; // Land cells measure their distance to water and vice versa. Offsetting by
    // half a cell puts the zero crossing on the shared cell boundary, so a
    // bilinear read of this field describes the coastline continuously.
    const toWater = sweep(0);
    const toLand = sweep(1);
    const field = new Float32Array(W * H);
    for (let i = 0; i < field.length; i++)
        field[i] = cells[i] ? toWater[i] - .5 : .5 - toLand[i];
    return field;
};
let cachedField = null;
const proximityField = () => { if (!cachedField) {
    try {
        cachedField = buildProximityField(inflateCoastGrid());
    }
    catch {
        cachedField = new Float32Array(GRID_COLS * GRID_ROWS);
    }
} return cachedField; }; /**
 * Bilinear read of the proximity field. `u` runs west to east, `v` north to
 * south, both 0..1. Positive results are inland, in grid cells.
 */
const inlandDepth = (u, v) => { const field = proximityField(); const fx = u * GRID_COLS - .5; const fy = v * GRID_ROWS - .5; const x0 = Math.floor(fx); const y0 = Math.floor(fy); const tx = fx - x0; const ty = fy - y0; const col = c => (c % GRID_COLS + GRID_COLS) % GRID_COLS; const row = r => r < 0 ? 0 : r >= GRID_ROWS ? GRID_ROWS - 1 : r; const xa = col(x0); const xb = col(x0 + 1); const ya = row(y0) * GRID_COLS; const yb = row(y0 + 1) * GRID_COLS; const top = field[ya + xa] * (1 - tx) + field[ya + xb] * tx; const bottom = field[yb + xa] * (1 - tx) + field[yb + xb] * tx; return top * (1 - ty) + bottom * ty; }; /* ------------------------------------------------------------------ *
* Small helpers
* ------------------------------------------------------------------ */
const DEG = Math.PI / 180;
const TAU = Math.PI * 2;
const clamp = (v, lo, hi) => v < lo ? lo : v > hi ? hi : v; /**
* Framer hands colors over as hex, rgb()/hsl() or a `var(--token, fallback)`
* wrapper around one of those. three.js chokes on the wrapper and quietly
* stays white, so unwrap it first and pull the alpha out by hand.
*/
const readTint = input => { const tint = { rgb: new THREE.Color(16777215), alpha: 1 }; if (typeof input !== "string" || !input.length)
    return tint; let text = input.trim(); if (text.slice(0, 4).toLowerCase() === "var(") {
    const split = text.indexOf(",");
    const tail = text.lastIndexOf(")");
    if (split > -1 && tail > split)
        text = text.slice(split + 1, tail).trim();
} const hex = /^#([0-9a-f]{3,8})$/i.exec(text); if (hex) {
    const body = hex[1];
    if (body.length === 4 || body.length === 8) {
        const step = body.length / 4;
        const slice = body.slice(3 * step);
        const raw = step === 1 ? slice + slice : slice;
        tint.alpha = parseInt(raw, 16) / 255;
    }
    const rgbPart = body.slice(0, body.length >= 6 ? 6 : 3);
    try {
        tint.rgb.set("#" + rgbPart);
    }
    catch { /* leave white */ }
    return tint;
} const fn = /^(rgba?|hsla?)\(([^)]*)\)$/i.exec(text); if (fn) {
    const parts = fn[2].split(/[,/\s]+/).filter(Boolean);
    if (parts.length >= 4) {
        const last = parts[3];
        const n = parseFloat(last);
        if (!Number.isNaN(n))
            tint.alpha = clamp(last.endsWith("%") ? n / 100 : n, 0, 1);
    }
} try {
    tint.rgb.set(text);
}
catch {
    const embedded = /#[0-9a-f]{6}/i.exec(text);
    if (embedded) {
        try {
            tint.rgb.set(embedded[0]);
        }
        catch { /* leave white */ }
    }
} return tint; }; /** Unit vector for a latitude/longitude pair, +Y north, +Z at 0 degrees. */
const unitFromGeo = (latDeg, lngDeg, out) => { const lat = latDeg * DEG; const lng = lngDeg * DEG; const band = Math.cos(lat); const v = out || new THREE.Vector3; return v.set(Math.sin(lng) * band, Math.sin(lat), Math.cos(lng) * band); }; /** Deterministic stream so a given density always produces the same field. */
const makeRandom = seed => { let state = seed >>> 0 || 1; return () => { state ^= state << 13; state ^= state >>> 17; state ^= state << 5; state >>>= 0; return state / 4294967296; }; }; /**
* Lay dots over the land using rings of constant colatitude. Ring spacing and
* the number of dots per ring both track the target spacing, so cells stay
* close to square and the field reads as even scatter rather than a pattern.
* Each dot is jittered inside its own cell and kept only if the bilinear
* coastline field says it landed ashore.
*/
const scatterLandDots = targetDots => {
    // says 0.336, but equirectangular cells over-weight the poles; by area
    // it is ~0.292, which is what makes the requested dot count come out.
    const landShare = .292;
    const sphereDots = Math.max(64, Math.round(targetDots / landShare));
    const spacing = Math.sqrt(4 * Math.PI / sphereDots);
    const rings = Math.max(3, Math.round(Math.PI / spacing));
    const random = makeRandom(2654435769 ^ sphereDots);
    const coords = [];
    const seeds = [];
    const coastal = [];
    const COAST_CELLS = 6;
    for (let ring = 0; ring < rings; ring++) {
        const theta = Math.PI * (ring + .5) / rings;
        const band = Math.sin(theta);
        const perRing = Math.max(1, Math.round(TAU * band / spacing));
        const phase = random() * TAU;
        const dTheta = Math.PI / rings;
        const dPhi = TAU / perRing;
        for (let step = 0; step < perRing; step++) {
            const t = theta + (random() - .5) * dTheta * .85;
            const p = phase + (step + (random() - .5) * .85) * dPhi;
            const sinT = Math.sin(t);
            const x = sinT * Math.sin(p);
            const y = Math.cos(t);
            const z = sinT * Math.cos(p);
            const u = .5 + Math.atan2(x, z) / TAU;
            const v = clamp(.5 - Math.asin(clamp(y, -1, 1)) / Math.PI, 0, 1);
            const depth = inlandDepth(u - Math.floor(u), v);
            if (depth <= 0)
                continue;
            coords.push(x, y, z);
            seeds.push(random() * 512);
            coastal.push(clamp(depth / COAST_CELLS, 0, 1));
        }
    }
    return { position: new Float32Array(coords), seed: new Float32Array(seeds), coast: new Float32Array(coastal), count: seeds.length };
}; /* ------------------------------------------------------------------ *
 * Shaders
 * ------------------------------------------------------------------ */
const FIELD_VERTEX = `
attribute float aSeed;
attribute float aCoast;

uniform float uTime;
uniform float uProgress;
uniform float uFormation;
uniform vec3  uSweepAxis;

uniform float uDotSize;
uniform float uSizeJitter;
uniform float uCoastLift;
uniform float uBackFade;

uniform float uCursorMode;
uniform vec3  uCursor;
uniform float uCursorGain;
uniform float uReach;
uniform float uWaveLength;
uniform float uWaveSpeed;
uniform float uCrest;
uniform float uSwell;
uniform float uGlow;
uniform vec3  uDrift;

varying float vHeat;
varying float vFade;
varying float vGrain;
varying float vPx;

float noise1(float s) {
    return fract(sin(s * 78.233 + 12.9898) * 43758.5453);
}

void main() {
    vec3 nrm = normalize(position);
    float rA = noise1(aSeed);
    float rB = noise1(aSeed + 4.77);
    float rC = noise1(aSeed + 9.13);

    // ---- entrance -------------------------------------------------
    // Every mode resolves to a radius, a lateral spread that closes as the
    // dot settles, and a birth fade, so they share one composition step.
    float radius = 1.0;
    float spread = 0.0;
    float born = 1.0;

    if (uFormation < 0.5) {
        // Sweep: a terminator crosses the sphere and the surface rises
        // behind it with a small overshoot.
        float key = 0.5 - 0.5 * dot(nrm, uSweepAxis);
        float t = clamp((uProgress - key * 0.72) / 0.28, 0.0, 1.0);
        float e = 1.0 - pow(1.0 - t, 3.0);
        radius = mix(0.82, 1.0, e) + sin(e * 3.14159) * 0.045;
        born = smoothstep(0.0, 0.35, t);
    } else if (uFormation < 1.5) {
        // Bloom: the shell grows out of the core.
        float t = clamp((uProgress - rA * 0.32) / 0.68, 0.0, 1.0);
        float e = 1.0 - pow(1.0 - t, 4.0);
        radius = e;
        born = smoothstep(0.0, 0.22, t);
    } else if (uFormation < 2.5) {
        // Fall: dots converge from a loose cloud outside the sphere.
        float t = clamp((uProgress - rA * 0.4) / 0.6, 0.0, 1.0);
        float e = 1.0 - pow(1.0 - t, 3.0);
        radius = mix(2.05, 1.0, e);
        spread = 0.85 * (1.0 - e);
        born = smoothstep(0.0, 0.2, t);
    } else if (uFormation < 3.5) {
        // Drift: the same arrival, restaged forever on a per-dot cycle.
        float cyc = fract(uTime * 0.055 + rA * 13.0);
        float arrive = 0.22;
        if (cyc < arrive) {
            float t = cyc / arrive;
            float e = 1.0 - pow(1.0 - t, 3.0);
            radius = mix(1.85, 1.0, e);
            spread = 0.75 * (1.0 - e);
            born = smoothstep(0.0, 0.3, t);
        } else {
            born = 1.0 - smoothstep(0.90, 1.0, cyc);
        }
        born *= smoothstep(0.0, 0.18, uProgress);
    } else {
        born = uProgress;
    }

    vec3 wander = normalize(vec3(rA, rB, rC) - 0.5);
    vec3 pos = normalize(nrm + wander * spread) * radius;

    // ---- cursor ---------------------------------------------------
    float heat = 0.0;
    float swell = 1.0;

    if (uCursorMode < 2.5 && uCursorGain > 0.002) {
        float ang = acos(clamp(dot(nrm, uCursor), -1.0, 1.0));
        float env = 1.0 - smoothstep(0.0, uReach, ang);
        env *= env;
        float amp = env * uCursorGain;

        if (uCursorMode < 0.5) {
            // Sonar: wavefronts leave the contact point and run outward
            // along the surface, lifting the shell as each crest passes.
            float wave = sin(
                ang / max(uWaveLength, 0.02) * 6.2831853
                - uTime * uWaveSpeed * 6.2831853
            );
            pos += nrm * wave * amp * uCrest;
            heat = max(0.0, wave) * amp;
            swell = 1.0 + max(0.0, wave) * amp * uSwell;
        } else if (uCursorMode < 1.5) {
            // Halo: light only, no displacement.
            float breathe = 0.78 + 0.22 * sin(uTime * 1.7);
            heat = amp * breathe;
            swell = 1.0 + heat * uSwell * 0.6;
        } else {
            // Wake: the surface is combed along the pointer's travel.
            vec3 tangent = uDrift - dot(uDrift, nrm) * nrm;
            pos += tangent * amp * uCrest * 8.0;
            heat = amp * clamp(length(uDrift) * 24.0, 0.0, 1.0);
            swell = 1.0 + heat * uSwell * 0.5;
        }
    }

    vec4 mv = modelViewMatrix * vec4(pos, 1.0);
    gl_Position = projectionMatrix * mv;

    // Coastal dots read a little heavier than deep interior ones, which keeps
    // the outlines legible as density drops.
    float shore = mix(1.0 + uCoastLift * 0.9, 1.0 - uCoastLift * 0.35, aCoast);
    float jitter = 1.0 + (rB - 0.5) * 2.0 * uSizeJitter;
    float breath = 0.88 + 0.12 * sin(uTime * 1.9 + rA * 21.0);

    gl_PointSize = max(
        0.0,
        uDotSize * jitter * shore * swell * breath * (2.0 / -mv.z)
    );
    vPx = gl_PointSize;

    float facing = normalize(normalMatrix * nrm).z;
    vFade = mix(uBackFade, 1.0, smoothstep(-0.22, 0.28, facing)) * born;
    vHeat = clamp(heat * uGlow, 0.0, 1.0);
    vGrain = 0.45 + 0.55 * rC;
}
`;
const FIELD_FRAGMENT = `
uniform vec3  uInk;
uniform float uInkAlpha;
uniform vec3  uTint;

varying float vHeat;
varying float vFade;
varying float vGrain;
varying float vPx;

void main() {
    // Round dot with a one-pixel edge regardless of how large it is on screen.
    float r = length(gl_PointCoord - vec2(0.5));
    float edge = 1.2 / max(vPx, 1.0);
    float disc = 1.0 - smoothstep(0.5 - edge, 0.5, r);
    if (disc <= 0.0) discard;

    vec3 rgb = mix(uInk, uTint, vHeat);
    float a = disc * uInkAlpha * vGrain * vFade * (1.0 + vHeat * 0.85);
    gl_FragColor = vec4(rgb, clamp(a, 0.0, 1.0));
}
`;
const ROUTE_VERTEX = `
attribute float aStep;
attribute float aOffset;

uniform float uTime;
uniform float uSpeed;
uniform float uTrail;
uniform float uSize;
uniform float uStyle;

varying float vComet;
varying float vFront;
varying float vPx;

void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mv;

    if (uStyle > 0.5) {
        // Beads: an evenly lit dotted trace with nothing travelling along it.
        vComet = 0.7;
    } else {
        // Comet: distance behind the travelling head, wrapped into 0..1.
        float head = fract(uTime * uSpeed + aOffset);
        float behind = head - aStep;
        if (behind < 0.0) behind += 1.0;
        vComet = pow(clamp(1.0 - behind / max(uTrail, 0.01), 0.0, 1.0), 2.5);
    }

    vFront = smoothstep(-0.05, 0.25, normalize(normalMatrix * normalize(position)).z);
    gl_PointSize = max(0.0, uSize * (0.8 + 1.0 * vComet) * (2.0 / -mv.z));
    vPx = gl_PointSize;
}
`;
const ROUTE_FRAGMENT = `
uniform vec3  uColor;
uniform float uRest;
uniform float uProgress;

varying float vComet;
varying float vFront;
varying float vPx;

void main() {
    float r = length(gl_PointCoord - vec2(0.5));
    float edge = 1.3 / max(vPx, 1.0);
    float disc = 1.0 - smoothstep(0.5 - edge, 0.5, r);
    if (disc <= 0.0) discard;

    float a = (uRest + vComet * (1.0 - uRest)) * disc * vFront * uProgress;
    gl_FragColor = vec4(uColor, clamp(a, 0.0, 1.0));
}
`; /**
 * Screen-space expanded line. WebGL will not draw THREE.Line thicker than one
 * pixel on most platforms, so each route is a triangle strip that widens
 * itself along the screen-space normal in the vertex shader. That gives a real
 * stroke width that stays constant as the globe turns.
 */
const ROUTE_LINE_VERTEX = `
attribute vec3 aTangent;
attribute float aSide;
attribute float aStep;
attribute float aOffset;

uniform vec2 uResolution;
uniform float uWidth;

varying float vStep;
varying float vOffset;
varying float vFront;

void main() {
    vec4 clip = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    vec4 ahead = projectionMatrix * modelViewMatrix * vec4(position + aTangent * 0.01, 1.0);

    vec2 a = clip.xy / max(abs(clip.w), 0.0001);
    vec2 b = ahead.xy / max(abs(ahead.w), 0.0001);
    vec2 travel = (b - a) * uResolution;
    float len = length(travel);
    vec2 dir = len > 0.0001 ? travel / len : vec2(1.0, 0.0);
    vec2 perp = vec2(-dir.y, dir.x);

    // Half the stroke in pixels, converted to NDC and back into clip space.
    vec2 shift = perp * aSide * uWidth * 0.5 / (uResolution * 0.5);
    gl_Position = clip;
    gl_Position.xy += shift * clip.w;

    vStep = aStep;
    vOffset = aOffset;
    vFront = smoothstep(-0.05, 0.25, normalize(normalMatrix * normalize(position)).z);
}
`;
const ROUTE_LINE_FRAGMENT = `
uniform vec3  uColor;
uniform float uTime;
uniform float uSpeed;
uniform float uTrail;
uniform float uRest;
uniform float uProgress;
uniform float uStyle;
uniform float uDashCount;

varying float vStep;
varying float vOffset;
varying float vFront;

void main() {
    float a;
    if (uStyle < 0.5) {
        // Solid.
        a = uRest;
    } else if (uStyle < 1.5) {
        // Dashed, drifting along the path at the flow speed.
        float d = fract(vStep * uDashCount - uTime * uSpeed);
        if (d > 0.55) discard;
        a = uRest;
    } else {
        // Pulse: a lit head running along a resting line.
        float head = fract(uTime * uSpeed + vOffset);
        float behind = head - vStep;
        if (behind < 0.0) behind += 1.0;
        float comet = pow(clamp(1.0 - behind / max(uTrail, 0.01), 0.0, 1.0), 2.5);
        a = uRest + comet * (1.0 - uRest);
    }
    gl_FragColor = vec4(uColor, clamp(a * vFront * uProgress, 0.0, 1.0));
}
`; /* ------------------------------------------------------------------ *
 * Runtime
 *
 * Owns the renderer, the scene graph and the frame loop. React builds one of
 * these, pushes config into it and disposes it; nothing in here re-renders.
 * ------------------------------------------------------------------ */
const CAMERA_FOV = 45;
const CAMERA_Z = 3.5;
const SWEEP_AXIS = new THREE.Vector3(-.78, .46, .42).normalize();
const CURSOR_MODE_INDEX = { sonar: 0, halo: 1, wake: 2, off: 3 }; // Routes drawn as a cloud of dots, and routes drawn as a widened strip.
const ROUTE_DOT_STYLES = { comet: 0, beads: 1 };
const ROUTE_LINE_STYLES = { solid: 0, dashed: 1, pulse: 2 };
const isLineRoute = style => style in ROUTE_LINE_STYLES;
const RIBBON_SAMPLES = 96;
const FORMATION_INDEX = { sweep: 0, bloom: 1, fall: 2, drift: 3, instant: 4 };
export class GlobeRuntime {
    apply(cfg) { const prev = this.cfg; this.cfg = cfg; const u = this.fieldUniforms; const r = this.routeUniforms; const ink = readTint(cfg.ink); u.uInk.value.copy(ink.rgb); u.uInkAlpha.value = ink.alpha; u.uTint.value.copy(readTint(cfg.tint).rgb); u.uBackFade.value = clamp(cfg.backFade, 0, 1); u.uDotSize.value = cfg.dotSize; u.uSizeJitter.value = clamp(cfg.sizeJitter, 0, 1); u.uCoastLift.value = clamp(cfg.coastLift, 0, 1); u.uFormation.value = FORMATION_INDEX[cfg.formation] ?? 0; u.uCursorMode.value = CURSOR_MODE_INDEX[cfg.cursorMode] ?? 3; u.uReach.value = Math.max(.05, cfg.reach); u.uWaveLength.value = Math.max(.02, cfg.waveLength); u.uWaveSpeed.value = cfg.waveSpeed; u.uCrest.value = cfg.crest; u.uSwell.value = cfg.swell; u.uGlow.value = cfg.glow; const accent = readTint(cfg.accent).rgb; r.uColor.value.copy(accent); r.uSpeed.value = cfg.routeSpeed; r.uTrail.value = clamp(cfg.routeTrail, .02, 1); r.uSize.value = cfg.routeSize; r.uRest.value = clamp(cfg.routeRest, 0, 1); r.uStyle.value = ROUTE_DOT_STYLES[cfg.routeStyle] ?? 0; const ln = this.routeLineUniforms; ln.uColor.value.copy(accent); ln.uSpeed.value = cfg.routeSpeed; ln.uTrail.value = clamp(cfg.routeTrail, .02, 1); ln.uRest.value = clamp(cfg.routeRest, 0, 1); ln.uWidth.value = Math.max(.5, cfg.routeWidth ?? 2); ln.uDashCount.value = Math.max(2, cfg.dashCount ?? 18); ln.uStyle.value = ROUTE_LINE_STYLES[cfg.routeStyle] ?? 0; this.routeGroup.visible = !!cfg.routesOn; if (prev && prev.startLng !== cfg.startLng) {
        this.spinAngle = -(cfg.startLng || 0) * DEG;
    } if (this.still)
        this.paintStatic(); }
    setPlaces(list, lift) { const radius = 1.015 + Math.max(0, lift); this.places = list.map(p => ({ vec: unitFromGeo(p.lat, p.lng).multiplyScalar(radius), node: null })); }
    setPlaceNodes(nodes) { for (let i = 0; i < this.places.length; i++)
        this.places[i].node = nodes[i] || null; if (this.still)
        this.paintStatic(); }
    replayEntrance() { this.progress = 0; this.elapsed = 0; } /* ---------------- geometry ---------------- */
    buildField() { this.disposeField(); const budget = this.tier > 0 ? 1 : .45; const data = scatterLandDots(Math.max(600, Math.round(this.cfg.dotTarget * budget))); if (!data.count)
        return; const geo = new THREE.BufferGeometry; geo.setAttribute("position", new THREE.BufferAttribute(data.position, 3)); geo.setAttribute("aSeed", new THREE.BufferAttribute(data.seed, 1)); geo.setAttribute("aCoast", new THREE.BufferAttribute(data.coast, 1)); geo.setDrawRange(0, data.count); this.field = new THREE.Points(geo, this.fieldMaterial); this.field.frustumCulled = false; this.field.renderOrder = 1; this.pivot.add(this.field); if (this.still)
        this.paintStatic(); }
    buildRoutes() {
        this.disposeRoutes();
        const cfg = this.cfg;
        const pts = cfg.places || [];
        if (!cfg.routesOn || pts.length < 2)
            return;
        const pairs = [];
        if (cfg.routeMode === "mesh") {
            for (let a = 0; a < pts.length; a++)
                for (let b = a + 1; b < pts.length; b++)
                    pairs.push([a, b]);
        }
        else if (cfg.routeMode === "hub") {
            for (let b = 1; b < pts.length; b++)
                pairs.push([0, b]);
        }
        else {
            for (let a = 0; a < pts.length; a++)
                pairs.push([a, (a + 1) % pts.length]);
        }
        if (!pairs.length)
            return;
        const ribbon = isLineRoute(cfg.routeStyle); // Strip styles want enough samples to look smooth; dot styles use the
        // count the designer asked for, because there each sample is a dot.
        const samples = ribbon ? RIBBON_SAMPLES : Math.max(8, Math.round(cfg.routeDots));
        const start = new THREE.Vector3;
        const end = new THREE.Vector3;
        pairs.forEach(([a, b], index) => {
            unitFromGeo(pts[a].lat, pts[a].lng, start);
            unitFromGeo(pts[b].lat, pts[b].lng, end);
            const sweep = Math.acos(clamp(start.dot(end), -1, 1)); // Long hops climb higher than short ones so the network reads as
            // depth rather than a flat tangle.
            const lift = .05 + sweep / Math.PI * cfg.routeAltitude;
            const phase = index / pairs.length;
            const xyz = new Float32Array(samples * 3);
            for (let s = 0; s < samples; s++) {
                const t = s / (samples - 1);
                let x;
                let y;
                let z;
                if (sweep < 1e-4) {
                    x = start.x;
                    y = start.y;
                    z = start.z;
                }
                else { // Spherical interpolation keeps the path on a great circle.
                    const k = Math.sin(sweep);
                    const w0 = Math.sin((1 - t) * sweep) / k;
                    const w1 = Math.sin(t * sweep) / k;
                    x = start.x * w0 + end.x * w1;
                    y = start.y * w0 + end.y * w1;
                    z = start.z * w0 + end.z * w1;
                }
                const len = Math.hypot(x, y, z) || 1;
                const h = (1 + lift * Math.sin(Math.PI * t)) / len;
                xyz[s * 3] = x * h;
                xyz[s * 3 + 1] = y * h;
                xyz[s * 3 + 2] = z * h;
            }
            const geo = new THREE.BufferGeometry;
            if (!ribbon) {
                const steps = new Float32Array(samples);
                const offsets = new Float32Array(samples);
                for (let s = 0; s < samples; s++) {
                    steps[s] = s / (samples - 1);
                    offsets[s] = phase;
                }
                geo.setAttribute("position", new THREE.BufferAttribute(xyz, 3));
                geo.setAttribute("aStep", new THREE.BufferAttribute(steps, 1));
                geo.setAttribute("aOffset", new THREE.BufferAttribute(offsets, 1));
                const strand = new THREE.Points(geo, this.routeMaterial);
                strand.frustumCulled = false;
                this.routeGroup.add(strand);
                return;
            } // Two vertices per sample, pushed to opposite sides of the path in
            // the vertex shader, stitched into a strip of quads.
            const verts = samples * 2;
            const pos = new Float32Array(verts * 3);
            const tangent = new Float32Array(verts * 3);
            const sideAttr = new Float32Array(verts);
            const stepAttr = new Float32Array(verts);
            const offsetAttr = new Float32Array(verts);
            for (let s = 0; s < samples; s++) {
                const prev = Math.max(0, s - 1) * 3;
                const next = Math.min(samples - 1, s + 1) * 3;
                let tx = xyz[next] - xyz[prev];
                let ty = xyz[next + 1] - xyz[prev + 1];
                let tz = xyz[next + 2] - xyz[prev + 2];
                const tl = Math.hypot(tx, ty, tz) || 1;
                tx /= tl;
                ty /= tl;
                tz /= tl;
                for (let k = 0; k < 2; k++) {
                    const v = s * 2 + k;
                    pos[v * 3] = xyz[s * 3];
                    pos[v * 3 + 1] = xyz[s * 3 + 1];
                    pos[v * 3 + 2] = xyz[s * 3 + 2];
                    tangent[v * 3] = tx;
                    tangent[v * 3 + 1] = ty;
                    tangent[v * 3 + 2] = tz;
                    sideAttr[v] = k === 0 ? -1 : 1;
                    stepAttr[v] = s / (samples - 1);
                    offsetAttr[v] = phase;
                }
            }
            const index16 = new Uint16Array((samples - 1) * 6);
            for (let s = 0; s < samples - 1; s++) {
                const base = s * 2;
                const o = s * 6;
                index16[o] = base;
                index16[o + 1] = base + 1;
                index16[o + 2] = base + 2;
                index16[o + 3] = base + 1;
                index16[o + 4] = base + 3;
                index16[o + 5] = base + 2;
            }
            geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
            geo.setAttribute("aTangent", new THREE.BufferAttribute(tangent, 3));
            geo.setAttribute("aSide", new THREE.BufferAttribute(sideAttr, 1));
            geo.setAttribute("aStep", new THREE.BufferAttribute(stepAttr, 1));
            geo.setAttribute("aOffset", new THREE.BufferAttribute(offsetAttr, 1));
            geo.setIndex(new THREE.BufferAttribute(index16, 1));
            const strand = new THREE.Mesh(geo, this.routeLineMaterial);
            strand.frustumCulled = false;
            this.routeGroup.add(strand);
        });
        if (this.still)
            this.paintStatic();
    }
    bindPointer() { this.host.addEventListener("pointerdown", this.onDown); this.host.addEventListener("pointerleave", this.onLeave); window.addEventListener("pointermove", this.onMove); window.addEventListener("pointerup", this.onUp); window.addEventListener("pointercancel", this.onUp); } /* ---------------- frame ---------------- */
    measure() {
        // would fold in any CSS transform on an ancestor — and the Framer
        // canvas scales the whole artboard as you zoom. Sizing the renderer
        // from that shrinks the canvas element itself, which is why a zoomed
        // canvas parked a small globe in the top-left while preview was fine.
        this.width = Math.max(1, Math.min(512, this.host.clientWidth || 1));
        this.height = Math.max(1, Math.min(512, this.host.clientHeight || 1));
    }
    fitScale() {
        // sphere is framed the same way in tall, wide and square containers.
        const viewH = 2 * Math.tan(CAMERA_FOV * DEG / 2) * CAMERA_Z;
        const viewW = viewH * (this.width / this.height);
        return Math.min(viewH, viewW) / 2.6 * (this.cfg.zoom ?? 1);
    }
    resize() { this.measure(); this.camera.aspect = this.width / this.height; this.camera.updateProjectionMatrix(); this.renderer.setSize(this.width, this.height); this.routeLineUniforms.uResolution.value.set(this.width, this.height); if (this.still)
        this.paintStatic();
    else if (!this.visible)
        this.renderOnce(); }
    renderOnce() { this.renderer.render(this.scene, this.camera); } /**
         * One settled frame for exports, thumbnails and the paused editor. The
         * frame loop is what normally positions the DOM markers, so a static pass
         * has to lay them out itself or they never appear.
         */
    paintStatic() { this.progress = 1; this.fieldUniforms.uProgress.value = 1; this.routeUniforms.uProgress.value = 1; this.routeLineUniforms.uProgress.value = 1; this.scale = this.fitScale(); this.pivot.scale.setScalar(this.scale); this.pivot.position.set(this.cfg.offsetX || 0, this.cfg.offsetY || 0, 0); this.pivot.rotation.set(this.tiltAngle, this.spinAngle, 0); this.scene.updateMatrixWorld(true); this.renderer.render(this.scene, this.camera); this.placeProjection(); }
    trackCursor(dt) {
        const cfg = this.cfg;
        const live = cfg.cursorMode !== "off" && this.pointerInside && performance.now() - this.hoverSince >= (cfg.cursorDelay || 0) * 1e3;
        let want = 0;
        if (live) {
            this.ndc.set(this.pointerUV.x * 2 - 1, -(this.pointerUV.y * 2) + 1);
            this.ray.setFromCamera(this.ndc, this.camera);
            this.inverse.copy(this.pivot.matrixWorld).invert();
            this.localRay.copy(this.ray.ray).applyMatrix4(this.inverse);
            if (this.localRay.intersectSphere(this.unitSphere, this.hit)) {
                want = 1;
                this.contactLocal.copy(this.hit).normalize(); // The wake needs pointer travel, not globe spin. Measuring the
                // contact point in world space isolates the two: a still
                // pointer keeps hitting the same world point however fast the
                // globe turns underneath it.
                this.scratchA.copy(this.contactLocal).applyMatrix4(this.pivot.matrixWorld);
                if (this.lastWorldHit) {
                    this.scratchB.copy(this.scratchA).sub(this.lastWorldHit);
                    this.pivot.getWorldQuaternion(this.scratchQ).invert();
                    this.scratchB.applyQuaternion(this.scratchQ).divideScalar(Math.max(.001, this.scale));
                }
                else {
                    this.scratchB.set(0, 0, 0);
                    this.lastWorldHit = new THREE.Vector3;
                }
                this.lastWorldHit.copy(this.scratchA);
                this.drift.lerp(this.scratchB, .3);
            }
            else {
                this.lastWorldHit = null;
            }
        }
        else {
            this.lastWorldHit = null;
            this.drift.multiplyScalar(Math.pow(.001, dt));
        }
        this.cursorGain += (want - this.cursorGain) * (1 - Math.pow(.02, dt));
        this.fieldUniforms.uCursorGain.value = this.cursorGain;
        if (this.cursorGain > .004)
            this.fieldUniforms.uCursor.value.copy(this.contactLocal);
        this.fieldUniforms.uDrift.value.copy(this.drift);
    }
    placeProjection() {
        if (!this.places.length)
            return;
        const half = { x: this.width / 2, y: this.height / 2 }; // The globe can be nudged away from the world origin, so the surface
        // normal has to be measured from the pivot's own centre.
        this.pivotOrigin.set(0, 0, 0).applyMatrix4(this.pivot.matrixWorld);
        for (let i = 0; i < this.places.length; i++) {
            const place = this.places[i];
            const node = place.node;
            if (!node)
                continue;
            this.scratchA.copy(place.vec).applyMatrix4(this.pivot.matrixWorld); // Dot of the surface normal against the view direction tells us how
            // far around the limb the marker has travelled.
            this.scratchB.copy(this.camera.position).sub(this.scratchA).normalize();
            const facing = this.scratchC.copy(this.scratchA).sub(this.pivotOrigin).normalize().dot(this.scratchB);
            if (facing < -.08) {
                node.style.opacity = "0";
                node.style.visibility = "hidden";
                continue;
            }
            this.scratchA.project(this.camera);
            const sx = (this.scratchA.x + 1) * half.x;
            const sy = (1 - this.scratchA.y) * half.y;
            const fade = clamp((facing + .08) / .3, 0, 1) * this.progress;
            node.style.visibility = "visible";
            node.style.opacity = String(fade);
            node.style.transform = `translate3d(${sx.toFixed(1)}px, ${sy.toFixed(1)}px, 0)`;
        }
    } /* ---------------- teardown ---------------- */
    disposeField() { if (!this.field)
        return; this.pivot.remove(this.field); this.field.geometry.dispose(); this.field = null; }
    disposeRoutes() { for (let i = this.routeGroup.children.length - 1; i >= 0; i--) {
        const child = this.routeGroup.children[i];
        child.geometry?.dispose();
        this.routeGroup.remove(child);
    } }
    dispose() {
        if (this.disposed) return;
        this.disposed = true;
        // Construction can fail midway (e.g. unsupported WebGL). Release every
        // allocated resource even when a browser has already lost its context.
        const release = action => { try { action(); } catch { /* Continue cleanup. */ } };
        release(() => this.disposeField());
        release(() => this.disposeRoutes());
        for (const material of [this.fieldMaterial, this.routeMaterial, this.routeLineMaterial])
            release(() => material?.dispose());
        release(() => this.scene?.clear());
        release(() => this.renderer?.forceContextLoss());
        release(() => this.renderer?.dispose());
        release(() => { const canvas = this.renderer?.domElement;
            if (canvas?.parentNode === this.host) this.host.removeChild(canvas); });
    }
    constructor(host, cfg, still) {
        _define_property(this, "host", void 0);
        _define_property(this, "still", void 0);
        _define_property(this, "cfg", void 0);
        _define_property(this, "renderer", void 0);
        _define_property(this, "scene", void 0);
        _define_property(this, "camera", void 0);
        _define_property(this, "pivot", void 0);
        _define_property(this, "routeGroup", void 0);
        _define_property(this, "field", null);
        _define_property(this, "fieldMaterial", void 0);
        _define_property(this, "fieldUniforms", void 0);
        _define_property(this, "routeMaterial", void 0);
        _define_property(this, "routeUniforms", void 0);
        _define_property(this, "routeLineMaterial", void 0);
        _define_property(this, "routeLineUniforms", void 0);
        _define_property(this, "tier", 2);
        _define_property(this, "width", 1);
        _define_property(this, "height", 1);
        _define_property(this, "places", []);
        _define_property(this, "progress", 0);
        _define_property(this, "elapsed", 0);
        _define_property(this, "spinAngle", 0);
        _define_property(this, "tiltAngle", 0);
        _define_property(this, "scale", 1);
        _define_property(this, "flingX", 0);
        _define_property(this, "dragging", false);
        _define_property(this, "dragFrom", { x: 0, y: 0 });
        _define_property(this, "pointerInside", false);
        _define_property(this, "pointerUV", { x: -1, y: -1 });
        _define_property(this, "hoverSince", 0);
        _define_property(this, "cursorGain", 0);
        _define_property(this, "contactLocal", new THREE.Vector3(0, 0, 1));
        _define_property(this, "lastWorldHit", null);
        _define_property(this, "drift", new THREE.Vector3);
        _define_property(this, "visible", false);
        _define_property(this, "allowed", true);
        _define_property(this, "raf", null);
        _define_property(this, "last", null);
        _define_property(this, "ray", new THREE.Raycaster);
        _define_property(this, "ndc", new THREE.Vector2);
        _define_property(this, "localRay", new THREE.Ray);
        _define_property(this, "unitSphere", new THREE.Sphere(new THREE.Vector3(0, 0, 0), 1));
        _define_property(this, "inverse", new THREE.Matrix4);
        _define_property(this, "hit", new THREE.Vector3);
        _define_property(this, "scratchA", new THREE.Vector3);
        _define_property(this, "scratchB", new THREE.Vector3);
        _define_property(this, "scratchC", new THREE.Vector3);
        _define_property(this, "pivotOrigin", new THREE.Vector3);
        _define_property(this, "scratchQ", new THREE.Quaternion);
        _define_property(this, "resizeWatcher", null);
        _define_property(this, "viewWatcher", null); /* ---------------- pointer ---------------- */
        _define_property(this, "onDown", event => { const target = event.target; if (target && target.closest(".mg-interactive"))
            return; this.dragging = true; this.flingX = 0; this.dragFrom.x = event.clientX; this.dragFrom.y = event.clientY; this.cfg.onBackdropPress?.(); });
        _define_property(this, "onMove", event => {
            // transform, so normalise against the on-screen box rather than the
            // layout size. Keeping it as a 0..1 fraction makes the raycast correct
            // at any zoom level.
            const box = this.host.getBoundingClientRect();
            if (box.width <= 0 || box.height <= 0)
                return;
            this.pointerUV.x = (event.clientX - box.left) / box.width;
            this.pointerUV.y = (event.clientY - box.top) / box.height;
            const within = this.pointerUV.x >= 0 && this.pointerUV.x <= 1 && this.pointerUV.y >= 0 && this.pointerUV.y <= 1;
            if (within && !this.pointerInside)
                this.hoverSince = performance.now();
            this.pointerInside = within;
            if (!this.dragging)
                return; // Drag deltas are in the same zoomed space; divide it out so a drag
            // turns the globe by the same amount however far you are zoomed.
            const zoomed = box.width / this.width || 1;
            const dx = (event.clientX - this.dragFrom.x) / zoomed;
            const dy = (event.clientY - this.dragFrom.y) / zoomed;
            this.dragFrom.x = event.clientX;
            this.dragFrom.y = event.clientY;
            const GAIN = .0075;
            this.flingX = dx * GAIN;
            this.spinAngle += this.flingX;
            if (this.cfg.allowTiltDrag) {
                const limit = (this.cfg.tiltRange ?? 70) * DEG;
                this.tiltAngle = clamp(this.tiltAngle + dy * GAIN, -limit, limit);
            }
        });
        _define_property(this, "onUp", () => { this.dragging = false; });
        _define_property(this, "onLeave", () => { if (this.dragging)
            return; this.pointerInside = false; this.lastWorldHit = null; });
        _define_property(this, "tick", now => {
            if (this.disposed || !Number.isFinite(now)) return;
            const dt = this.last === null ? 1 / 60 : Math.min(.1, (now - this.last) / 1e3);
            this.last = now; // One "frame" is a 60Hz tick, so the same damping constants hold at any
            // refresh rate and after a stall.
            const frames = dt * 60;
            const ease = k => 1 - Math.pow(1 - k, frames);
            const clock = now / 1e3;
            const cfg = this.cfg;
            if (this.progress < 1) {
                this.elapsed += dt;
                this.progress = clamp(this.elapsed / Math.max(.016, cfg.entranceSeconds || .016), 0, 1);
            }
            this.fieldUniforms.uTime.value = clock;
            this.fieldUniforms.uProgress.value = this.progress;
            this.routeUniforms.uTime.value = clock;
            this.routeUniforms.uProgress.value = this.progress;
            this.routeLineUniforms.uTime.value = clock;
            this.routeLineUniforms.uProgress.value = this.progress;
            const focus = cfg.focus ?? -1;
            const target = focus >= 0 ? cfg.places?.[focus] : null;
            if (target) {
                this.spinAngle = -target.lng * DEG;
                this.tiltAngle = target.lat * DEG;
            }
            else if (!this.dragging) {
                this.spinAngle += (cfg.spin * .016 + (1 - this.progress) * .014) * frames;
                this.spinAngle += this.flingX * frames;
                this.flingX *= Math.pow(.94, frames);
                this.tiltAngle += (cfg.tilt * DEG - this.tiltAngle) * ease(.055);
            }
            const wanted = this.fitScale() * (target ? 1.5 : .88 + .12 * this.progress);
            this.scale += (wanted - this.scale) * ease(.08);
            this.pivot.scale.setScalar(this.scale);
            this.pivot.position.set(cfg.offsetX || 0, cfg.offsetY || 0, 0);
            this.pivot.rotation.y += (this.spinAngle - this.pivot.rotation.y) * ease(.1);
            this.pivot.rotation.x += (this.tiltAngle - this.pivot.rotation.x) * ease(.1);
            this.trackCursor(dt);
            this.renderer.render(this.scene, this.camera);
            this.placeProjection();
        });
        this.host = host;
        this.cfg = cfg;
        this.still = still;
        this.tier = resolveTier(cfg.quality);
        try {
        this.measure();
        this.renderer = new THREE.WebGLRenderer({ alpha: true, antialias: this.tier > 0, powerPreference: "low-power" });
        this.renderer.setPixelRatio(Math.max(1, Math.min(window.devicePixelRatio || 1, 1.5)));
        this.renderer.setSize(this.width, this.height);
        this.renderer.domElement.style.display = "block";
        this.renderer.domElement.style.touchAction = "none";
        host.appendChild(this.renderer.domElement);
        this.scene = new THREE.Scene;
        this.camera = new THREE.PerspectiveCamera(CAMERA_FOV, this.width / this.height, .1, 80);
        this.camera.position.z = CAMERA_Z;
        this.pivot = new THREE.Group; // Spin first around the globe's own pole, then apply the view tilt, so
        // the sphere never wobbles as it turns.
        this.pivot.rotation.order = "XYZ";
        this.scene.add(this.pivot);
        this.routeGroup = new THREE.Group;
        this.routeGroup.renderOrder = 2;
        this.pivot.add(this.routeGroup);
        this.fieldUniforms = { uTime: { value: 0 }, uProgress: { value: 0 }, uFormation: { value: 0 }, uSweepAxis: { value: SWEEP_AXIS.clone() }, uDotSize: { value: 5 }, uSizeJitter: { value: .6 }, uCoastLift: { value: .35 }, uBackFade: { value: .14 }, uCursorMode: { value: 0 }, uCursor: { value: new THREE.Vector3(0, 0, 1) }, uCursorGain: { value: 0 }, uReach: { value: .5 }, uWaveLength: { value: .22 }, uWaveSpeed: { value: .55 }, uCrest: { value: .035 }, uSwell: { value: 1.2 }, uGlow: { value: 1 }, uDrift: { value: new THREE.Vector3 }, uInk: { value: new THREE.Color(13229311) }, uInkAlpha: { value: 1 }, uTint: { value: new THREE.Color(8368895) } };
        this.fieldMaterial = new THREE.ShaderMaterial({ uniforms: this.fieldUniforms, vertexShader: FIELD_VERTEX, fragmentShader: FIELD_FRAGMENT, transparent: true, depthWrite: false, blending: THREE.NormalBlending });
        this.routeUniforms = { uTime: { value: 0 }, uSpeed: { value: .22 }, uTrail: { value: .3 }, uSize: { value: 4 }, uRest: { value: .22 }, uStyle: { value: 0 }, uProgress: { value: 0 }, uColor: { value: new THREE.Color(6003711) } };
        this.routeMaterial = new THREE.ShaderMaterial({ uniforms: this.routeUniforms, vertexShader: ROUTE_VERTEX, fragmentShader: ROUTE_FRAGMENT, transparent: true, depthWrite: false, blending: THREE.NormalBlending });
        this.routeLineUniforms = { uTime: { value: 0 }, uSpeed: { value: .22 }, uTrail: { value: .3 }, uRest: { value: .32 }, uProgress: { value: 0 }, uStyle: { value: 0 }, uWidth: { value: 2 }, uDashCount: { value: 18 }, uResolution: { value: new THREE.Vector2(this.width, this.height) }, uColor: { value: new THREE.Color(6003711) } };
        this.routeLineMaterial = new THREE.ShaderMaterial({ uniforms: this.routeLineUniforms, vertexShader: ROUTE_LINE_VERTEX, fragmentShader: ROUTE_LINE_FRAGMENT, transparent: true, depthWrite: false, side: THREE.DoubleSide, blending: THREE.NormalBlending });
        this.spinAngle = -(cfg.startLng || 0) * DEG;
        this.tiltAngle = (cfg.tilt || 0) * DEG;
        this.pivot.rotation.set(this.tiltAngle, this.spinAngle, 0);
        this.apply(cfg);
        this.buildField();
        this.buildRoutes();
        if (this.still) {
            this.paintStatic();
        }
        } catch (error) { this.dispose(); throw error; }
    }
} /** Coarse device tier: 0 trims the workload, 2 runs everything. */
const resolveTier = quality => { if (quality === "high")
    return 2; if (quality === "low")
    return 0; if (typeof navigator === "undefined")
    return 2; const nav = navigator; const cores = nav.hardwareConcurrency || 8; const memory = nav.deviceMemory || 8; const handheld = /Mobi|Android|iPhone|iPad|iPod/i.test(nav.userAgent || ""); return handheld || cores <= 4 || memory <= 4 ? 0 : 2; }; /* ------------------------------------------------------------------ *
 * Themes and presets
 * ------------------------------------------------------------------ */

export { scatterLandDots, inflateCoastGrid, inlandDepth };
