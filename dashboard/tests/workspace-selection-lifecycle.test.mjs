import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { setImmediate as nextTurn } from "node:timers/promises";
import test from "node:test";
import React from "react";
import ts from "typescript";
import * as evidenceState from "../app/components/evidence-state.ts";
import * as preventionState from "../app/components/prevention-state.ts";

// Exercise the real selection handlers, request helpers, effect dependencies and
// cleanups. Only the DOM host and unrelated child presentation are replaced.
// Like saved-detector-replay.test.mjs, this needs no browser or renderer package.
const require = createRequire(import.meta.url);
const operator = { token: "invented-selection-test-token", connect: async () => {}, disconnect() {} };
const router = { push() {}, replace() {} };

function loadComponent(path, react) {
  const file = resolve(path), mod = { exports: {} }, leaves = new Map();
  const compiled = ts.transpileModule(readFileSync(file, "utf8"), { compilerOptions: {
    jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022, esModuleInterop: true,
  } }).outputText;
  new Function("require", "module", "exports", compiled)(name => {
    if (name === "react") return react;
    if (name === "next/navigation") return { useRouter: () => router };
    if (name.endsWith("/operator-provider")) return { useOperator: () => operator };
    if (name.endsWith("/evidence-state")) return evidenceState;
    if (name === "./prevention-state") return preventionState;
    if (name.endsWith("/brand")) return { BRAND_NAME: "Nemo" };
    if (name.endsWith(".module.css")) return { __esModule: true, default: new Proxy({}, { get: (_, key) => String(key) }) };
    if (name.startsWith(".")) return new Proxy({}, { get: (_, key) => {
      if (!leaves.has(key)) leaves.set(key, function PresentationLeaf() { return null; });
      return leaves.get(key);
    } });
    return require(name);
  }, mod, mod.exports);
  return mod.exports;
}

function mount(path, exportName, props = {}) {
  const hooks = [], effects = [];
  let cursor = 0, dirty = true, tree, unmounted = false;
  const changed = (before, after) => !before || !after || before.length !== after.length || after.some((value, index) => !Object.is(value, before[index]));
  const react = { ...React,
    useState(initial) {
      const index = cursor++;
      if (!hooks[index]) {
        const state = { value: typeof initial === "function" ? initial() : initial };
        state.set = value => {
          if (unmounted) return;
          const next = typeof value === "function" ? value(state.value) : value;
          if (!Object.is(next, state.value)) { state.value = next; dirty = true; }
        };
        hooks[index] = state;
      }
      return [hooks[index].value, hooks[index].set];
    },
    useRef(initial) {
      const index = cursor++;
      return hooks[index] ??= { current: initial };
    },
    useCallback(callback, dependencies) {
      const index = cursor++;
      if (changed(hooks[index]?.dependencies, dependencies)) hooks[index] = { dependencies, callback };
      return hooks[index].callback;
    },
    useEffect(effect, dependencies) {
      const index = cursor++, previous = hooks[index];
      if (!changed(previous?.dependencies, dependencies)) return;
      hooks[index] = { dependencies };
      effects.push(() => { previous?.cleanup?.(); hooks[index].cleanup = effect(); });
    },
  };
  const Component = loadComponent(path, react)[exportName];
  function render() {
    assert.equal(unmounted, false);
    cursor = 0; dirty = false; tree = Component(props);
    while (effects.length) effects.shift()();
    return tree;
  }
  async function settle() {
    // Each turn drains actual request/Response promises, then commits state and
    // only reruns effects whose dependency identities changed.
    for (let count = 0; count < 8; count++) {
      let renders = 0;
      while (dirty) { assert.ok(++renders < 30, "component reaches a stable render"); render(); }
      await nextTurn();
    }
    while (dirty) render();
  }
  render();
  return { settle, tree: () => tree, render,
    unmount() { unmounted = true; hooks.forEach(hook => hook.cleanup?.()); },
  };
}

function descendants(element) {
  if (!React.isValidElement(element)) return [];
  const children = [];
  React.Children.forEach(element.props.children, child => children.push(...descendants(child)));
  return [element, ...children];
}
function text(element) {
  if (typeof element === "string" || typeof element === "number") return String(element);
  if (!React.isValidElement(element)) return "";
  return React.Children.toArray(element.props.children).map(text).join("");
}
function find(h, predicate, description) {
  const element = descendants(h.tree()).find(predicate);
  assert.ok(element, description);
  return element;
}
function button(h, label) { return find(h, node => node.type === "button" && text(node).trim() === label, `button ${label} exists`); }
function click(element) { assert.ok(!element.props.disabled, "control is enabled"); return element.props.onClick(); }
function row(h, className, id) { return find(h, node => node.type === "button" && node.props.className === className && node.key === id, `${className} row ${id} exists`); }
function child(h, name) { return descendants(h.tree()).find(node => typeof node.type === "function" && node.type.name === name); }
function sourceReport(h) { return child(h, "SourceReport")?.props.evidence ?? null; }
function comparisonReport(h) { return child(h, "ComparisonDetail")?.props.report ?? null; }
function deferred() {
  let resolve;
  const promise = new Promise(yes => { resolve = yes; });
  return { promise, resolve };
}

function environment(hash = "") {
  const previous = new Map(), timers = new Map(), listeners = new Map();
  let nextTimer = 0;
  function install(key, value) { previous.set(key, Object.getOwnPropertyDescriptor(globalThis, key)); Object.defineProperty(globalThis, key, { configurable: true, writable: true, value }); }
  const location = { hash };
  const history = { state: null,
    pushState(state, _unused, url) { this.state = state; location.hash = String(url).split("#")[1] ? `#${String(url).split("#")[1]}` : ""; },
    replaceState(state, unused, url) { this.pushState(state, unused, url); },
  };
  install("setTimeout", (callback, delay) => { const id = ++nextTimer; timers.set(id, { callback, delay }); return id; });
  install("clearTimeout", id => timers.delete(id));
  install("window", { location, history, scrollTo() {},
    addEventListener(name, callback) { if (!listeners.has(name)) listeners.set(name, new Set()); listeners.get(name).add(callback); },
    removeEventListener(name, callback) { listeners.get(name)?.delete(callback); },
  });
  return {
    install,
    async tick(delay) {
      const pending = [...timers].filter(([, timer]) => timer.delay === delay);
      for (const [id, timer] of pending) { timers.delete(id); timer.callback(); }
      await nextTurn();
    },
    restore() {
      try {
        assert.equal(timers.size, 0, "unmount clears polling timers");
        assert.equal([...listeners.values()].reduce((sum, entries) => sum + entries.size, 0), 0, "unmount removes window listeners");
      } finally {
        for (const [key, descriptor] of previous) {
          if (descriptor) Object.defineProperty(globalThis, key, descriptor);
          else delete globalThis[key];
        }
      }
    },
  };
}

// Invented records exercise selection only; they are not physical observations.
const cases = ["alpha", "bravo"].map(name => ({ id: `case-${name}`, profile_id: "profile-test", mode: "SYNTHETIC", state: "ESTIMATED", evidence_id: `evidence-${name}`, points: [{ x_cm: 1, y_cm: 1 }] }));
const evidence = Object.fromEntries(cases.map(item => [item.id, { id: item.evidence_id, case_id: item.id, status: "ranked", relative_support: { A: 1 } }]));
const profiles = [{ id: "profile-test", data_origin: "SYNTHETIC", sources: [{ id: "A", polygon_cm: [[0, 0], [2, 0], [2, 2]] }], bounds: { x_min_cm: 0, x_max_cm: 10, y_min_cm: 0, y_max_cm: 10 } }];
const status = { camera: { running: false, fresh: false, session_id: null, width: null, height: null, device_index: null, backend: null }, chalk: { ready: false, reasons: ["disabled"] }, photon: { enabled: false, ready: false, reasons: ["disabled"] }, operator_configured: true };

async function withWorkspace(run, { readEvidence = id => evidence[id] } = {}) {
  const env = environment(`#investigations?case=${cases[0].id}`), calls = [];
  env.install("fetch", async (url, options = {}) => {
    const path = new URL(url, "http://selection.test").pathname;
    calls.push({ path, options });
    let value;
    if (path.endsWith("/status")) value = status;
    else if (path.endsWith("/profiles")) value = profiles;
    else if (path.endsWith("/cases")) value = cases;
    else if (path.endsWith("/demo/load")) value = { cases: [{ case: cases[0], evidence: evidence[cases[0].id] }] };
    else if (/\/cases\/[^/]+\/actions$/.test(path)) value = [];
    else if (/\/cases\/[^/]+\/evidence$/.test(path)) value = await readEvidence(decodeURIComponent(path.split("/").at(-2)), options);
    else assert.fail(`unexpected workspace API request ${path}`);
    return new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  const h = mount("app/workspace/page.tsx", "default");
  try { await h.settle(); await run(h, calls, env); }
  finally { h.unmount(); env.restore(); }
}

function assertSourceReady(h, id) {
  assert.equal(sourceReport(h)?.id, evidence[id].id, "selected source report stays available");
  assert.equal(button(h, "Ask Chalk").props.disabled, false, "matching saved evidence still enables Chalk");
}

test("reselecting the current source observation preserves its loaded report", async () => {
  await withWorkspace(async h => {
    assertSourceReady(h, cases[0].id);
    click(row(h, "case-item", cases[0].id));
    await h.settle();
    assertSourceReady(h, cases[0].id);
  });
});

test("Overview recent observations can reopen the already selected source case", async () => {
  await withWorkspace(async h => {
    assertSourceReady(h, cases[0].id);
    click(button(h, "Overview"));
    await h.settle();
    click(row(h, "observation-row", cases[0].id));
    await h.settle();
    assertSourceReady(h, cases[0].id);
  });
});

test("repeated Load demo accepts the reused case and immutable evidence", async () => {
  await withWorkspace(async (h, calls) => {
    assertSourceReady(h, cases[0].id);
    for (let count = 0; count < 2; count++) {
      click(button(h, "Load demo"));
      await h.settle();
      assertSourceReady(h, cases[0].id);
    }
    assert.equal(calls.filter(call => call.path.endsWith("/demo/load")).length, 2);
  });
});

test("a different source selection hides the previous report until its own evidence arrives", async () => {
  const next = deferred();
  await withWorkspace(async h => {
    assertSourceReady(h, cases[0].id);
    click(row(h, "case-item", cases[1].id));
    await h.settle();
    assert.equal(sourceReport(h), null, "old evidence is hidden during the new read");
    assert.equal(child(h, "SourceReport").props.expectedEvidenceId, cases[1].evidence_id);
    assert.equal(button(h, "Ask Chalk").props.disabled, true);
    next.resolve(evidence[cases[1].id]);
    await h.settle();
    assertSourceReady(h, cases[1].id);
  }, { readEvidence: id => id === cases[1].id ? next.promise : evidence[id] });
});

test("a late response from the previous source case cannot replace the new selection", async () => {
  const old = deferred(); let oldSignal;
  await withWorkspace(async h => {
    assert.equal(sourceReport(h), null);
    click(row(h, "case-item", cases[1].id));
    await h.settle();
    assert.equal(oldSignal.aborted, true, "case switch aborts the old read");
    assertSourceReady(h, cases[1].id);
    old.resolve(evidence[cases[0].id]);
    await h.settle();
    assertSourceReady(h, cases[1].id);
  }, { readEvidence: (id, options) => {
    if (id !== cases[0].id) return evidence[id];
    oldSignal = options.signal;
    return old.promise; // Deliberately ignores abort to exercise late completion.
  } });
});

function comparison(name) {
  const id = `comparison-${name}`;
  return {
    comparison: { id, name: `Selection fixture ${name}`, case_id: cases[0].id, source_evidence_id: cases[0].evidence_id, data_origin: "SYNTHETIC", is_current: true, created_at: 1, plan: { sequence: [] }, numerical_report: {} },
    trials: [], evaluation: { comparison_id: id, snapshot_hash: `snapshot-${name}`, by_origin: {} }, is_current: true,
  };
}
const comparisons = [comparison("alpha"), comparison("bravo")];

async function withPrevention(run, { readComparison = id => comparisons.find(report => report.comparison.id === id) } = {}) {
  const env = environment(), calls = [];
  const request = async (path, body, options = {}) => {
    calls.push({ path, body, options });
    if (path === "/prevention/comparisons") return comparisons.map(report => report.comparison);
    const id = path.split("/").at(-1);
    assert.ok(comparisons.some(report => report.comparison.id === id), `known comparison request ${path}`);
    return readComparison(id, options);
  };
  const props = { request, operatorConnected: true, onRequireOperator() {}, cases, profiles, selectedCaseId: cases[0].id, onSelectCase() {}, onBusyChange() {}, onStopCase: async () => {} };
  const h = mount("app/components/prevention-workspace.tsx", "PreventionWorkspace", props);
  try { await h.settle(); await run(h, calls, env); }
  finally { h.unmount(); env.restore(); }
}
function comparisonRow(h, id) {
  return find(h, node => node.type === "button" && node.key === id, `saved comparison ${id} exists`);
}

test("reselecting the current prevention comparison keeps its report and polling alive", async () => {
  await withPrevention(async (h, calls, env) => {
    const id = comparisons[0].comparison.id;
    assert.equal(comparisonReport(h)?.comparison.id, id);
    click(comparisonRow(h, id));
    await h.settle();
    assert.equal(comparisonReport(h)?.comparison.id, id, "current comparison stays visible");
    const before = calls.filter(call => call.path.endsWith(`/${id}`)).length;
    await env.tick(5000);
    await h.settle();
    assert.ok(calls.filter(call => call.path.endsWith(`/${id}`)).length > before, "the idle comparison continues to refresh");
    assert.equal(comparisonReport(h)?.comparison.id, id);
  });
});

test("a different prevention selection hides the old comparison while its detail loads", async () => {
  const next = deferred();
  await withPrevention(async h => {
    assert.equal(comparisonReport(h)?.comparison.id, comparisons[0].comparison.id);
    click(comparisonRow(h, comparisons[1].comparison.id));
    await h.settle();
    assert.equal(comparisonReport(h), null, "the prior comparison is hidden");
    next.resolve(comparisons[1]);
    await h.settle();
    assert.equal(comparisonReport(h)?.comparison.id, comparisons[1].comparison.id);
  }, { readComparison: id => id === comparisons[1].comparison.id ? next.promise : comparisons[0] });
});

test("a late previous-comparison response cannot overwrite the selected prevention report", async () => {
  const old = deferred(); let oldSignal;
  await withPrevention(async h => {
    assert.equal(comparisonReport(h), null);
    click(comparisonRow(h, comparisons[1].comparison.id));
    await h.settle();
    assert.equal(oldSignal.aborted, true, "comparison switch aborts the old read");
    assert.equal(comparisonReport(h)?.comparison.id, comparisons[1].comparison.id);
    old.resolve(comparisons[0]);
    await h.settle();
    assert.equal(comparisonReport(h)?.comparison.id, comparisons[1].comparison.id);
  }, { readComparison: (id, options) => {
    if (id !== comparisons[0].comparison.id) return comparisons[1];
    oldSignal = options.signal;
    return old.promise; // Resolve after selection even when the caller aborts.
  } });
});
