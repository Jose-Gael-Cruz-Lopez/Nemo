import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url), mod = { exports: {} };
const source = readFileSync("app/components/globe-state.ts", "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
} }).outputText;
new Function("require", "module", "exports", compiled)(require, mod, mod.exports);
const { clampGlobeProgress, globePixelRatio, globePose, globeCanAnimate, globeReticleTicks,
  parseGlobeLand, landTexturePoint, createGlobeResourceScope, createGlobeFrameDriver,
  GLOBE_ANGULAR_SPEED } = mod.exports;

function harness() {
  let next = 0;
  const pending = new Map(), draws = [], cancelled = [];
  const driver = createGlobeFrameDriver({
    requestFrame(callback) { const id = next++; pending.set(id, callback); return id; },
    cancelFrame(id) { cancelled.push(id); pending.delete(id); },
    draw(pose) { draws.push({ ...pose }); },
  });
  return { driver, pending, draws, cancelled,
    frame(time) { const callbacks = [...pending.values()]; pending.clear(); callbacks.forEach(callback => callback(time)); } };
}
const running = { motion: true, reducedMotion: false, hidden: false, intersecting: true };

test("reticle SVG serialization survives cross-engine trigonometric rounding", () => {
  const expected = globeReticleTicks();
  assert.equal(expected.length, 33);
  for (const tick of expected) for (const coordinate of Object.values(tick)) {
    assert.match(coordinate, /^\d+\.\d{4}$/);
    assert.ok(Number(coordinate) >= 0 && Number(coordinate) <= 189);
  }
  const sin = Math.sin, cos = Math.cos;
  try {
    // Exceeds the measured Node/Chrome ulp difference while staying invisible
    // at four SVG decimals. The hydrated markup must remain byte-identical.
    Math.sin = angle => sin(angle) + 1e-14;
    Math.cos = angle => cos(angle) - 1e-14;
    assert.deepEqual(globeReticleTicks(), expected);
  } finally { Math.sin = sin; Math.cos = cos; }
});

test("server-rendered globe uses the rounded reticle coordinates for hydration", () => {
  const component = { exports: {} };
  const javascript = ts.transpileModule(readFileSync("app/components/landing-globe.tsx", "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  new Function("require", "module", "exports", javascript)(name => {
    if (name === "./globe-state") return mod.exports;
    if (name.endsWith(".module.css")) return { default: new Proxy({}, { get: (_, key) => String(key) }) };
    return require(name);
  }, component, component.exports);
  const html = renderToStaticMarkup(React.createElement(component.exports.LandingGlobe, { progress: 0, motion: false }));
  const lines = html.match(/<line\b[^>]+>/g) ?? [];
  assert.equal(lines.length, 33);
  for (const line of lines) for (const attribute of ["x1", "x2", "y1", "y2"])
    assert.match(line, new RegExp(`${attribute}="\\d+\\.\\d{4}"`));
});

test("pixel ratio and explicit progress stay bounded under invalid or oversized inputs", () => {
  assert.equal(globePixelRatio(4), 1.5); assert.equal(globePixelRatio(1.25), 1.25);
  for (const value of [0, -2, NaN, Infinity]) assert.equal(globePixelRatio(value), 1);
  assert.equal(clampGlobeProgress(-1), 0); assert.equal(clampGlobeProgress(200), 100);
  assert.equal(clampGlobeProgress(NaN), 0); assert.equal(clampGlobeProgress(37), 37);
});

test("initial orientation places the Atlantic view centre toward the camera", () => {
  const pose = globePose(0);
  // Independent spherical geometry: Three's UV globe has x=cos(lat)cos(lon),
  // y=sin(lat),z=-cos(lat)sin(lon). The requested lon-15/lat+15 must face +z.
  const lat = 15 * Math.PI / 180, lon = -15 * Math.PI / 180;
  const x = Math.cos(lat) * Math.cos(lon), y = Math.sin(lat), z = -Math.cos(lat) * Math.sin(lon);
  const rotatedX = x * Math.cos(pose.rotationY) + z * Math.sin(pose.rotationY);
  const rotatedZ = -x * Math.sin(pose.rotationY) + z * Math.cos(pose.rotationY);
  const rotatedY = y * Math.cos(pose.rotationX) - rotatedZ * Math.sin(pose.rotationX);
  const front = y * Math.sin(pose.rotationX) + rotatedZ * Math.cos(pose.rotationX);
  assert.ok(Math.abs(rotatedX) < 1e-14 && Math.abs(rotatedY) < 1e-14);
  assert.ok(Math.abs(front - 1) < 1e-14);
  assert.ok(globePose(100).rotationY > pose.rotationY);
  assert.deepEqual(globePose(0, Infinity), pose);
});

test("equirectangular coordinates retain both seam edges and north-up geographic units", () => {
  assert.deepEqual(landTexturePoint(-180, 90, 1024, 512), [0, 0]);
  assert.deepEqual(landTexturePoint(180, -90, 1024, 512), [1024, 512]);
  assert.deepEqual(landTexturePoint(0, 0, 1024, 512), [512, 256]);
  for (const args of [[181, 0, 1, 1], [0, 91, 1, 1], [0, 0, 0, 1], [NaN, 0, 1, 1]])
    assert.throws(() => landTexturePoint(...args), /geographic/);
});

function insideRing([x, y], ring) {
  let inside = false;
  for (let index = 0, previous = ring.length - 1; index < ring.length; previous = index++) {
    const [xi, yi] = ring[index], [xj, yj] = ring[previous];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
function isLand(point, polygons) {
  return polygons.some(rings => insideRing(point, rings[0]) && !rings.slice(1).some(ring => insideRing(point, ring)));
}

test("official coast asset represents real continents, oceans and the Caspian hole", () => {
  const raw = readFileSync("public/geo/land-110m.geojson");
  assert.equal(createHash("sha256").update(raw).digest("hex"), "9e0729ee253ca7d7a5c4ae9395fb1902264c5377c52e224d13dd85010e2835d9");
  const polygons = parseGlobeLand(JSON.parse(raw));
  assert.equal(polygons.length, 127);
  assert.equal(polygons.reduce((count, rings) => count + rings.reduce((sum, ring) => sum + ring.length, 0), 0), 5143);
  for (const point of [[12.5, 41.9], [36.8, -1.29], [-98, 39], [-55, -10], [135, -25], [100, 45], [-42, 72], [-100, -89]])
    assert.equal(isLand(point, polygons), true, `Expected continental land at ${point}`);
  for (const point of [[-30, 20], [-140, 0], [70, -20], [50, 42]])
    assert.equal(isLand(point, polygons), false, `Expected water at ${point}`);
  const fallback = readFileSync("public/geo/earth-atlantic-fallback.png");
  assert.deepEqual([...fallback.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
  assert.equal(fallback.readUInt32BE(16), 189); assert.equal(fallback.readUInt32BE(20), 189);
});

test("land validation preserves holes and pole closure but rejects unsplit nonpolar seams", () => {
  const outer = [[-10, -10], [10, -10], [10, 10], [-10, 10], [-10, -10]];
  const hole = [[-1, -1], [-1, 1], [1, 1], [1, -1], [-1, -1]];
  const collection = { type: "FeatureCollection", features: [{ geometry: { type: "Polygon", coordinates: [outer, hole] } }] };
  const parsed = parseGlobeLand(collection);
  assert.equal(isLand([0, 0], parsed), false); assert.equal(isLand([5, 5], parsed), true);
  parsed[0][0][0][0] = -20; assert.equal(outer[0][0], -10);
  const crossing = { type: "FeatureCollection", features: [{ geometry: { type: "Polygon",
    coordinates: [[[179, 0], [-179, 0], [-179, 1], [179, 0]]] } }] };
  assert.throws(() => parseGlobeLand(crossing), /seam/);
  const pole = { type: "FeatureCollection", features: [{ geometry: { type: "Polygon",
    coordinates: [[[180, -85], [180, -90], [-180, -90], [-180, -85], [180, -85]]] } }] };
  // A fake second cross-seam edge away from the pole is still inadmissible.
  assert.throws(() => parseGlobeLand(pole), /seam/);
});

test("invalid or excessive geometry cannot allocate an unbounded land texture", () => {
  for (const value of [null, {}, { type: "FeatureCollection", features: [] },
    { type: "FeatureCollection", features: Array(257).fill({}) },
    { type: "FeatureCollection", features: [{ geometry: { type: "LineString", coordinates: [] } }] },
    { type: "FeatureCollection", features: [{ geometry: { type: "Polygon", coordinates: [[[0, 0], [181, 0], [0, 1], [0, 0]]] } }] },
    { type: "FeatureCollection", features: [{ geometry: { type: "Polygon", coordinates: [[[0, 0], [1, 0], [0, 1], [0, 2]]] } }] }])
    assert.throws(() => parseGlobeLand(value));
});

test("hidden, offscreen, reduced motion and manual pause independently stop animation", () => {
  assert.equal(globeCanAnimate({ ...running, progress: 0 }), true);
  for (const change of [{ hidden: true }, { intersecting: false }, { reducedMotion: true }, { motion: false }])
    assert.equal(globeCanAnimate({ ...running, progress: 0, ...change }), false);
  const h = harness(); h.driver.update(running); h.frame(0);
  const late = [...h.pending.values()][0];
  h.driver.update({ hidden: true }); assert.equal(h.pending.size, 0);
  const count = h.draws.length; late(1000); assert.equal(h.draws.length, count);
  assert.equal(h.pending.size, 0);
  h.driver.update({ hidden: false }); assert.equal(h.pending.size, 1);
  late(2000); assert.equal(h.draws.length, count); assert.equal(h.pending.size, 1);
});

test("frame work is capped, progress updates coalesce and long gaps cannot produce spins", () => {
  const h = harness(); h.driver.update(running);
  for (let progress = 0; progress <= 100; progress++) h.driver.update({ progress });
  assert.equal(h.pending.size, 1);
  for (let frame = 0; frame <= 60; frame++) h.frame(frame * 1000 / 60);
  assert.ok(h.draws.length >= 25 && h.draws.length <= 31, `Draw count ${h.draws.length}`);
  const before = h.draws.at(-1).rotationY;
  h.frame(1_000_000);
  assert.ok(h.draws.at(-1).rotationY - before <= .1 * GLOBE_ANGULAR_SPEED + 1e-3);
  h.driver.dispose(); assert.equal(h.pending.size, 0);
});

test("pause freezes progress rotation and visibility resume does not integrate hidden time", () => {
  const h = harness(); h.driver.update(running); h.frame(0); h.frame(100);
  const first = h.draws.at(-1);
  h.driver.update({ motion: false }); h.driver.update({ progress: 100 });
  assert.equal(h.pending.size, 0);
  h.driver.invalidate(); h.frame(200); assert.deepEqual(h.draws.at(-1), first);
  h.driver.update({ progress: 0, motion: true }); h.frame(300);
  const before = h.draws.at(-1);
  h.driver.update({ intersecting: false }); assert.equal(h.pending.size, 0);
  h.driver.update({ intersecting: true }); h.frame(10_000_000);
  assert.deepEqual(h.draws.at(-1), before);
  h.driver.update({ reducedMotion: true }); h.frame(10_000_100);
  assert.deepEqual(h.draws.at(-1), before); assert.equal(h.pending.size, 0);
});

test("disposal cancels the exact pending frame and ignores late callbacks or new work", () => {
  const h = harness(); h.driver.update(running); h.frame(0);
  const late = [...h.pending.values()][0], count = h.draws.length;
  h.driver.dispose(); h.driver.dispose();
  assert.equal(h.pending.size, 0); late(1000);
  h.driver.update({ progress: 100 }); h.driver.invalidate();
  assert.equal(h.draws.length, count); assert.equal(h.pending.size, 0);
});

test("every GPU/listener resource disposes once even after partial initialization or one throwing cleanup", () => {
  const scope = createGlobeResourceScope(), events = [];
  scope.add(() => events.push("renderer"));
  scope.add(() => { events.push("texture"); throw new Error("Context already lost"); });
  scope.add(() => events.push("geometry"));
  scope.add(() => events.push("frame/listeners"));
  scope.dispose(); scope.dispose();
  assert.deepEqual(events, ["frame/listeners", "geometry", "texture", "renderer"]);
  scope.add(() => events.push("late texture")); assert.equal(events.at(-1), "late texture");
});
