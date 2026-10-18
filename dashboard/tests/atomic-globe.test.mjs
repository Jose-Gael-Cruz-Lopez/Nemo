import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import * as THREE from "three";
import ts from "typescript";
import { adaptAtomicGlobe } from "../vendor/atomic-globe/adapt.mjs";

const require = createRequire(import.meta.url);
const original = readFileSync("vendor/atomic-globe/AtomicGlobe.original.js.txt", "utf8");
const adapted = readFileSync("app/components/atomic-globe-runtime.mjs", "utf8");
function load(source, three = THREE, append = "") {
  const mod = { exports: {} };
  const javascript = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  } }).outputText;
  new Function("require", "module", "exports", javascript + append)(name => {
    if (name === "three") return three;
    if (name === "framer") return { addPropertyControls() {}, ControlType: new Proxy({}, { get: (_, key) => key }),
      RenderTarget: { current: () => "preview", canvas: "canvas" }, useIsStaticRenderer: () => false };
    return require(name);
  }, mod, mod.exports);
  return mod.exports;
}
const originalCore = load(original, THREE, "\nexports.core = { scatterLandDots, inflateCoastGrid, FIELD_VERTEX, FIELD_FRAGMENT, ROUTE_VERTEX, ROUTE_FRAGMENT, ROUTE_LINE_VERTEX, ROUTE_LINE_FRAGMENT };").core;
const local = load(adapted, THREE, "\nexports.shaders = { FIELD_VERTEX, FIELD_FRAGMENT, ROUTE_VERTEX, ROUTE_FRAGMENT, ROUTE_LINE_VERTEX, ROUTE_LINE_FRAGMENT };");
const state = load(readFileSync("app/components/globe-state.ts", "utf8"));

test("the supplied AtomicGlobe source is preserved and the adapter reproduces exactly", () => {
  assert.equal(Buffer.byteLength(original), 68999);
  assert.equal(createHash("sha256").update(original).digest("hex"), "062a928e2d2244426ac8815a6b50ea455a5b6830aea03b4673902e40b2b696bb");
  assert.equal(adaptAtomicGlobe(original), adapted);
  assert.doesNotMatch(adapted, /from ["']framer["']|requestAnimationFrame\(|cancelAnimationFrame\(/);
});

test("the actual source coast decoder, equal-area point field and all shaders survive adaptation", () => {
  assert.deepEqual(local.inflateCoastGrid(), originalCore.inflateCoastGrid());
  assert.deepEqual(local.shaders, Object.fromEntries(Object.keys(local.shaders).map(key => [key, originalCore[key]])));
  const expected = originalCore.scatterLandDots(8000), actual = local.scatterLandDots(8000);
  assert.equal(actual.count, 7996);
  for (const name of ["position", "seed", "coast"]) assert.deepEqual(actual[name], expected[name]);
  for (let index = 0; index < actual.position.length; index += 3)
    assert.ok(Math.abs(Math.hypot(...actual.position.subarray(index, index + 3)) - 1) < 1e-6);
});

test("Nemo settings cap the real source dot budget and never show fictitious operations", () => {
  for (const progress of [-10, 0, 50, 100, Infinity]) {
    const config = state.atomicGlobeConfig(progress);
    assert.equal(config.dotTarget, 8000); assert.deepEqual(config.places, []);
    assert.equal(config.routesOn, false); assert.equal(config.cursorMode, "off");
    assert.ok(Number.isFinite(config.startLng)); assert.ok(config.startLng >= -15 && config.startLng <= 95 + 1e-12);
  }
});

function runtimeHarness({ failSize = false } = {}) {
  const renderers = [], children = [];
  class Renderer {
    constructor(options) { this.options = options; this.domElement = { style: {}, parentNode: null }; this.renders = 0; this.disposes = 0; this.losses = 0; renderers.push(this); }
    setPixelRatio(value) { this.ratio = value; }
    setSize(width, height) { if (failSize) throw Error("GPU setup failed"); this.size = [width, height]; }
    render() { this.renders++; }
    forceContextLoss() { this.losses++; }
    dispose() { this.disposes++; }
  }
  const runtime = load(adapted, { ...THREE, WebGLRenderer: Renderer });
  const host = { clientWidth: 10000, clientHeight: 10000,
    appendChild(node) { children.push(node); node.parentNode = this; },
    removeChild(node) { children.splice(children.indexOf(node), 1); node.parentNode = null; },
    addEventListener() { assert.fail("The actual runtime must not own global or pointer listeners"); } };
  return { runtime, host, renderers, children };
}

test("actual runtime uses bounded low-power rendering with externally supplied time, then disposes once", () => {
  const previous = globalThis.window;
  globalThis.window = { devicePixelRatio: 5, addEventListener() { assert.fail("Unexpected global listener"); } };
  try {
    const h = runtimeHarness(), runtime = new h.runtime.GlobeRuntime(h.host, state.atomicGlobeConfig(0), false);
    const renderer = h.renderers[0];
    assert.equal(renderer.options.powerPreference, "low-power"); assert.equal(renderer.ratio, 1.5);
    assert.deepEqual(renderer.size, [512, 512]); assert.equal(runtime.field.geometry.getAttribute("position").count, 7996);
    runtime.tick(0); runtime.tick(100); assert.equal(renderer.renders, 2);
    runtime.dispose(); runtime.dispose(); runtime.tick(200);
    assert.equal(renderer.renders, 2); assert.equal(renderer.disposes, 1); assert.equal(renderer.losses, 1);
    assert.equal(h.children.length, 0);
  } finally { globalThis.window = previous; }
});

test("partial WebGL initialization failure still releases allocated resources", () => {
  const previous = globalThis.window; globalThis.window = { devicePixelRatio: 2 };
  try {
    const h = runtimeHarness({ failSize: true });
    assert.throws(() => new h.runtime.GlobeRuntime(h.host, state.atomicGlobeConfig(0), false), /GPU setup/);
    assert.equal(h.renderers[0].disposes, 1); assert.equal(h.renderers[0].losses, 1); assert.equal(h.children.length, 0);
  } finally { globalThis.window = previous; }
});

test("external virtual shader clock excludes hidden time", () => {
  let pending, next = 0; const clocks = [];
  const driver = state.createGlobeFrameDriver({ requestFrame(callback) { pending = callback; return next++; },
    cancelFrame() { pending = null; }, draw(_pose, elapsed) { clocks.push(elapsed); } });
  driver.update({ motion: true, reducedMotion: false, hidden: false, intersecting: true });
  pending(0); pending(100); const before = clocks.at(-1);
  driver.update({ hidden: true }); driver.update({ hidden: false }); pending(1000000);
  assert.equal(clocks.at(-1), before); driver.dispose();
});

test("static fallback is a small local image of the supplied lattice", () => {
  const png = readFileSync("public/geo/atomic-globe-fallback.png");
  assert.deepEqual([...png.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
  assert.equal(png.readUInt32BE(16), 189); assert.equal(png.readUInt32BE(20), 189);
  assert.ok(png.byteLength < 25000);
  assert.match(readFileSync("app/components/landing-globe.module.css", "utf8"), /\/geo\/atomic-globe-fallback\.png/);
});
