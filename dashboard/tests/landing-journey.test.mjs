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
const { JOURNEY_CHAPTERS, legacyWorkspaceDestination, journeyProgress, motionAllowed, createJourneyNarrator } = component("app/landing-journey-state.ts");
const { default: Landing } = component("app/page.tsx");

function audioHarness({ fail = false } = {}) {
  const states = [], messages = [];
  let cancellations = 0;
  const engine = { cancel() { cancellations++; }, speak(message) { if (fail) throw new Error("Browser speech unavailable"); messages.push(message); } };
  const narrator = createJourneyNarrator(engine, text => ({ text }), state => states.push(state));
  return { narrator, states, messages, cancellations: () => cancellations };
}

test("five distinct chapters link to real software routes and preserve evidence boundaries", () => {
  assert.deepEqual(JOURNEY_CHAPTERS.map(chapter => chapter.id), ["welcome", "observe", "trace", "prevent", "verify"]);
  for (const chapter of JOURNEY_CHAPTERS) {
    assert.ok(chapter.narration.length > 100);
    assert.match(chapter.href, /^\/(demo|workspace)(#(investigations|prevention|data))?$/);
    assert.ok(chapter.secondaryHref.startsWith("#journey-") || chapter.secondaryHref === "/workspace");
  }
  assert.match(JOURNEY_CHAPTERS[0].narration, /illustrative.*synthetic.*physical validation is pending/i);
  assert.match(JOURNEY_CHAPTERS[2].narration, /not a calibrated probability/);
  assert.match(JOURNEY_CHAPTERS[2].narration, /Chalk.*cannot change it/);
  assert.match(JOURNEY_CHAPTERS[3].narration, /separate.*tank replay/i);
  assert.match(JOURNEY_CHAPTERS[4].narration, /simple drift baseline performed better/);
  assert.match(JOURNEY_CHAPTERS[4].evidence, /does not validate plastic motion/);
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

test("reduced motion, manual pause or hidden tab each independently prevents visual motion", () => {
  for (const reducedMotion of [false, true]) for (const paused of [false, true]) for (const hidden of [false, true]) {
    assert.equal(motionAllowed({ reducedMotion, paused, hidden }), !reducedMotion && !paused && !hidden);
  }
});

test("narrator is silent until explicit play and confirms speaking only from native start", () => {
  const h = audioHarness();
  assert.deepEqual(h.states, []); assert.equal(h.messages.length, 0); assert.equal(h.cancellations(), 0);
  h.narrator.play(JOURNEY_CHAPTERS[0].narration);
  assert.deepEqual(h.states, ["off", "loading"]);
  assert.equal(h.messages[0].text, JOURNEY_CHAPTERS[0].narration);
  assert.equal(h.messages[0].lang, "en-US");
  h.messages[0].onstart(); assert.equal(h.states.at(-1), "speaking");
  h.messages[0].onend(); assert.equal(h.states.at(-1), "off");
});

test("chapter or visibility stop cancels speech and ignores late native events", () => {
  const h = audioHarness(); h.narrator.play("First chapter");
  const original = h.messages[0]; original.onstart(); h.narrator.stop();
  const count = h.states.length;
  original.onstart(); original.onerror(); original.onend();
  assert.equal(h.states.length, count); assert.equal(h.states.at(-1), "off");
  assert.equal(h.cancellations(), 2);
});

test("a second explicit chapter narration invalidates callbacks from the older utterance", () => {
  const h = audioHarness(); h.narrator.play("Old"); h.narrator.play("New");
  h.messages[1].onstart(); assert.equal(h.states.at(-1), "speaking");
  const count = h.states.length; h.messages[0].onend(); h.messages[0].onerror();
  assert.equal(h.states.length, count); assert.equal(h.states.at(-1), "speaking");
});

test("unmount disposes narration, cancels speech and prevents future work or updates", () => {
  const h = audioHarness(); h.narrator.play("Chapter"); h.narrator.dispose();
  const count = h.states.length, cancelled = h.cancellations();
  h.messages[0].onstart(); h.messages[0].onend(); h.narrator.play("After leaving"); h.narrator.stop();
  assert.equal(h.states.length, count); assert.equal(h.messages.length, 1); assert.ok(h.cancellations() >= cancelled);
});

test("unsupported or failed native speech is reported without pretending audio played", () => {
  const states = [];
  const unsupported = createJourneyNarrator(null, () => assert.fail("Unsupported speech must not construct utterances"), state => states.push(state));
  unsupported.play("Caption stays readable"); assert.deepEqual(states, ["off", "unsupported"]);
  const failed = audioHarness({ fail: true }); failed.narrator.play("Browser rejected speech");
  assert.equal(failed.states.at(-1), "error"); assert.ok(!failed.states.includes("speaking"));
  const native = audioHarness(); native.narrator.play("Later native error"); native.messages[0].onerror();
  assert.equal(native.states.at(-1), "error");
});

test("rendered entry stays usable and truthful before client effects or media load", () => {
  const html = renderToStaticMarkup(React.createElement(Landing));
  assert.match(html, /data-motion="paused"/);
  assert.equal((html.match(/data-journey-chapter=/g) ?? []).length, 5);
  assert.equal((html.match(/<h1\b/g) ?? []).length, 1);
  assert.equal((html.match(/<h2\b/g) ?? []).length, 4);
  assert.match(html, /Start journey/); assert.match(html, /Without voice/); assert.match(html, /With narration/);
  assert.match(html, /href="\/workspace"[^>]*>Skip journey/);
  assert.match(html, /href="\/login"/); assert.match(html, /href="\/workspace#data"/);
  assert.match(html, /role="progressbar"[^>]+aria-valuenow="0"/);
  assert.match(html, /Voice is off\. Listening is always your choice/);
  assert.match(html, /Read chapter narration/);
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
