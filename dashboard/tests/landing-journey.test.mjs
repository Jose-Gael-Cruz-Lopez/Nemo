import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve, dirname } from "node:path";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url), loaded = new Map();
function component(path) {
  const file = resolve(path);
  if (loaded.has(file)) return loaded.get(file).exports;
  const mod = { exports: {} }; loaded.set(file, mod);
  const compiled = ts.transpileModule(readFileSync(file, "utf8"), { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
  new Function("require", "module", "exports", compiled)(name => {
    if (name.endsWith(".module.css")) return { __esModule: true, default: new Proxy({}, { get: (_, key) => String(key) }) };
    if (name === "next/link") return { __esModule: true, default: ({ children, ...props }) => React.createElement("a", props, children) };
    if (name === "next/navigation") return { useRouter: () => ({ replace() { assert.fail("Server rendering must not navigate"); } }) };
    if (name.startsWith(".")) {
      const base = resolve(dirname(file), name);
      const dependency = [base, `${base}.tsx`, `${base}.ts`].find(existsSync);
      if (dependency) return component(dependency);
    }
    return require(name);
  }, mod, mod.exports);
  return mod.exports;
}
const { JOURNEY_CHAPTERS, legacyWorkspaceDestination, journeyProgress, motionAllowed } = component("app/landing-journey-state.ts");
const { default: Landing } = component("app/page.tsx");


test("five distinct chapters link to real software routes and preserve evidence boundaries", () => {
  assert.deepEqual(JOURNEY_CHAPTERS.map(chapter => chapter.id), ["welcome", "observe", "trace", "prevent", "verify"]);
  for (const chapter of JOURNEY_CHAPTERS) {
    assert.ok(chapter.detail.length > 40);
    assert.ok(chapter.detail.split(/\s+/).length <= 20);
    assert.ok(!("eyebrow" in chapter));
    assert.match(chapter.href, /^\/(demo|workspace)(#(investigations|prevention|data))?$/);
    assert.ok(chapter.secondaryHref.startsWith("#journey-") || chapter.secondaryHref === "/workspace");
  }
  assert.deepEqual(JOURNEY_CHAPTERS.map(chapter => chapter.heading), ["Nemo", "Observe the drift.", "Find possible sources.", "Compare interception layouts.", "Check the evidence."]);
  assert.match(JOURNEY_CHAPTERS[2].evidence, /does not identify a polluter/);
  assert.match(JOURNEY_CHAPTERS[3].evidence, /separate; neither establishes measured reef protection/);
  assert.match(JOURNEY_CHAPTERS[4].evidence, /do not validate plastic motion/);
});

test("legacy observation links preserve view and safely encoded bounded case identity", () => {
  for (const view of ["overview", "investigations", "prevention", "camera", "data", "settings"]) {
    assert.equal(legacyWorkspaceDestination(`#${view}`), `/workspace#${view}`);
    assert.equal(legacyWorkspaceDestination(`#${view}?case=case-1%26x%3D2`), `/workspace#${view}?case=case-1%26x%3D2`);
  }
  assert.equal(legacyWorkspaceDestination(`#data?case=${"a".repeat(201)}`), "/workspace#data");
  assert.equal(legacyWorkspaceDestination("#data?unrelated=ignored"), "/workspace#data");
  for (const hash of ["", "#journey-welcome", "#journey-trace", "#other", "#https://example.com"]) assert.equal(legacyWorkspaceDestination(hash), null);
});

test("journey progress uses actual available scroll extent, clamps overscroll and rejects invalid dimensions", () => {
  assert.equal(journeyProgress(0, 5000, 1000), 0);
  assert.equal(journeyProgress(2000, 5000, 1000), 50);
  assert.equal(journeyProgress(4000, 5000, 1000), 100);
  assert.equal(journeyProgress(4100, 5000, 1000), 100);
  assert.equal(journeyProgress(-20, 5000, 1000), 0);
  for (const dimensions of [[0, 0, 0], [20, 900, 1000], [NaN, 5000, 1000], [0, Infinity, 1]]) assert.equal(journeyProgress(...dimensions), 0);
});

test("reduced motion or a hidden tab each independently prevents visual motion", () => {
  for (const reducedMotion of [false, true]) for (const hidden of [false, true]) {
    assert.equal(motionAllowed({ reducedMotion, hidden }), !reducedMotion && !hidden);
  }
});


test("rendered entry stays usable and truthful before client effects or media load", () => {
  const html = renderToStaticMarkup(React.createElement(Landing));
  assert.match(html, /data-motion="paused"/);
  assert.equal((html.match(/data-journey-chapter=/g) ?? []).length, 5);
  assert.equal((html.match(/<h1\b/g) ?? []).length, 1);
  assert.equal((html.match(/<h2\b/g) ?? []).length, 4);
  assert.match(html, /Start journey/);
  assert.equal((html.match(/<button\b/g) ?? []).length, 1);
  assert.doesNotMatch(html, /Pause motion|Resume motion|Reduced motion|OBSERVE\. TRACE\. PREVENT\.|EXPECTED IS ONLY HALF THE STORY|BEGIN WITH WHAT YOU CAN SEE|Honest limits|Every drift/);
  assert.match(html, /<h1[^>]*><strong>Nemo<\/strong><\/h1>/);
  assert.doesNotMatch(html, /narration|captions|Listen|Without voice|With voice|Mute narration|type="radio"|<audio/i);
  assert.match(html, /href="\/workspace"[^>]*>Skip journey/);
  assert.match(html, /href="\/login"/); assert.match(html, /href="\/workspace#data"/);
  assert.match(html, /role="progressbar"[^>]+aria-valuenow="0"/);
  assert.match(html, /Illustrative ocean · synthetic software demo · physical validation pending/);
  assert.match(html, /poster="\/tideward-ocean-hero\.png"/);
  assert.match(html, /preload="none"/); assert.doesNotMatch(html, /autoPlay|autoplay/);
  assert.doesNotMatch(html, /GPS|TEMPERATURE|DEPTH:|LIVE CURRENT|100% accuracy/i);
  for (const chapter of JOURNEY_CHAPTERS) {
    assert.match(html, new RegExp(`id="journey-${chapter.id}"`));
    assert.match(html, new RegExp(`aria-label="Chapter [1-5]: ${chapter.label}"`));
  }
});

// Exercise the actual entry handler, its committed ref and focus effect without
// adding a DOM dependency. Native browser focus is also checked separately.
function entryTransitionHarness({ alreadyEntered = false } = {}) {
  const states = [], refs = [];
  let stateIndex = 0, refIndex = 0, effects = [], firstFalse = true;
  const hooks = {
    useState(initial) {
      const index = stateIndex++;
      if (!(index in states)) {
        states[index] = initial;
        if (initial === false && firstFalse) { states[index] = alreadyEntered; firstFalse = false; }
      }
      return [states[index], value => { states[index] = typeof value === "function" ? value(states[index]) : value; }];
    },
    useRef(initial) { const index = refIndex++; return refs[index] ??= { current: initial }; },
    useEffect(effect, dependencies) { effects.push({ effect, dependencies }); },
  };
  const file = resolve("app/page.tsx"), mod = { exports: {} };
  const compiled = ts.transpileModule(readFileSync(file, "utf8"), { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
  new Function("require", "module", "exports", compiled)(name => {
    if (name === "react") return { ...React, ...hooks };
    if (name === "next/navigation") return { useRouter: () => ({ replace() { assert.fail("Focus test must not navigate"); } }) };
    if (name === "next/link") return { __esModule: true, default: props => React.createElement("a", props) };
    if (name.endsWith(".module.css")) return { __esModule: true, default: {} };
    if (name.startsWith(".")) { const base = resolve(dirname(file), name); return component([base, `${base}.ts`, `${base}.tsx`].find(existsSync)); }
    return require(name);
  }, mod, mod.exports);
  function render() { stateIndex = 0; refIndex = 0; effects = []; return mod.exports.default(); }
  function find(element, predicate) {
    if (!React.isValidElement(element)) return null;
    if (predicate(element)) return element;
    for (const child of React.Children.toArray(element.props.children)) { const match = find(child, predicate); if (match) return match; }
    return null;
  }
  function commitEntryFocusEffect() {
    // Browser subscriptions are outside this unit's scope; run the effect bound
    // to entry state, after the host has committed the actual target ref.
    for (const { effect, dependencies } of effects) if (dependencies?.length === 1 && typeof dependencies[0] === "boolean") effect();
  }
  return { render, find, commitEntryFocusEffect };
}

test("explicit Start journey retains keyboard focus on the newly committed primary link exactly once", () => {
  const h = entryTransitionHarness();
  const before = h.render();
  const start = h.find(before, element => element.type === "button" && React.Children.toArray(element.props.children).some(child => child === "Start journey "));
  assert.ok(start);
  h.commitEntryFocusEffect();
  start.props.onClick();
  const after = h.render(), target = h.find(after, element => element.props.href === "/demo");
  assert.ok(target?.props.ref);
  const focusCalls = [];
  target.props.ref.current = { focus: options => focusCalls.push(options) };
  h.commitEntryFocusEffect();
  assert.deepEqual(focusCalls, [{ preventScroll: true }]);
  h.render(); h.commitEntryFocusEffect();
  assert.equal(focusCalls.length, 1);
});

test("entered state without an explicit Start click never steals focus", () => {
  const h = entryTransitionHarness({ alreadyEntered: true });
  const target = h.find(h.render(), element => element.props.href === "/demo");
  assert.ok(target?.props.ref);
  target.props.ref.current = { focus: () => assert.fail("Scroll-based entry must retain current focus") };
  h.commitEntryFocusEffect();
});

test("reference headline fonts are bundled locally at their declared weights", () => {
  const css = readFileSync(resolve("app/landing.module.css"), "utf8");
  for (const [weight, name] of [[400, "Regular"], [500, "Medium"], [700, "Bold"]]) {
    const filename = `Rajdhani-${name}.ttf`;
    const font = readFileSync(resolve("public/fonts/rajdhani", filename));
    assert.equal(font.readUInt32BE(0), 0x00010000, `${filename} must be a real TrueType font`);
    assert.ok(font.length > 10_000);
    assert.match(css, new RegExp(`src:url\\('/fonts/rajdhani/${filename}'\\).*?font-weight:${weight};font-display:swap`));
  }
  assert.match(readFileSync(resolve("public/fonts/rajdhani/OFL.txt"), "utf8"), /SIL OPEN FONT LICENSE/);
  assert.match(css, /\.title\{font-family:"Rajdhani"/);
  assert.match(css, /\.welcomeChapter \.title\{font-weight:700/);
  assert.doesNotMatch(css, /Impact|fonts\.googleapis\.com|fonts\.gstatic\.com/);
});
