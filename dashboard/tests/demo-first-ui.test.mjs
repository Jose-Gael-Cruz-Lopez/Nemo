import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve, dirname } from "node:path";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

// Exercise the actual React presentation without a browser, Next server or network.
// Only framework routing and CSS-module loading are adapted for this test process.
const require = createRequire(import.meta.url);
const loaded = new Map();
function component(path) {
  const file = resolve(path);
  if (loaded.has(file)) return loaded.get(file).exports;
  const mod = { exports: {} }; loaded.set(file, mod);
  const compiled = ts.transpileModule(readFileSync(file, "utf8"), { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
  const localRequire = name => {
    if (name.endsWith(".module.css")) return { __esModule: true, default: new Proxy({}, { get: (_, key) => String(key) }) };
    if (name === "next/link") return { __esModule: true, default: ({ children, ...props }) => React.createElement("a", props, children) };
    if (name === "next/navigation") return { useRouter: () => ({ push() {} }) };
    if (name === "next/image") return { __esModule: true, default: props => React.createElement("img", { ...props, unoptimized: undefined }) };
    if (name.startsWith(".")) {
      const base = resolve(dirname(file), name);
      const dependency = [base, `${base}.tsx`, `${base}.ts`].find(candidate => existsSync(candidate));
      if (dependency) return component(dependency);
    }
    return require(name);
  };
  new Function("require", "module", "exports", compiled)(localRequire, mod, mod.exports);
  return mod.exports;
}
const root = resolve("app/components");
const { OperatorProvider } = component(`${root}/operator-provider.tsx`);
const { DemoGuide } = component(`${root}/demo-guide.tsx`);
const { SourceMap } = component(`${root}/source-map.tsx`);
const { FreshStudyResults, StudyPath } = component(`${root}/fresh-drifter-study.tsx`);
const { RealDataLab } = component(`${root}/real-data-lab.tsx`);
const { PreventionWorkspace, ComparisonDetail } = component(`${root}/prevention-workspace.tsx`);
const { default: Workspace } = component(resolve("app/workspace/page.tsx"));
const report = JSON.parse(readFileSync(new URL("./fixtures/fresh-drifter-report.json", import.meta.url), "utf8"));
const pending = JSON.parse(readFileSync(new URL("./fixtures/fresh-drifter-pending-report.json", import.meta.url), "utf8"));
const render = element => renderToStaticMarkup(React.createElement(OperatorProvider, null, element));

// Keep closed-summary labels, but exclude their hidden contents when assessing the default UI.
function defaultVisible(html) {
  const tokens = html.split(/(<\/?details\b[^>]*>|<\/?summary\b[^>]*>)/i);
  const stack = []; let summary = 0, out = "";
  for (const token of tokens) {
    if (/^<details\b/i.test(token)) stack.push(!/\bopen(?:\s|=|>)/i.test(token));
    else if (/^<\/details/i.test(token)) stack.pop();
    else if (/^<summary\b/i.test(token)) summary++;
    else if (/^<\/summary/i.test(token)) summary--;
    else if (!stack.some(Boolean) || summary > 0 && stack.length === 1) out += token;
  }
  return out;
}
const noAction = () => assert.fail("Rendering must not execute an action");

test("Overview has three explicit demo steps, distinguishes separate examples and collapses setup", () => {
  const html = render(React.createElement(Workspace));
  const visible = defaultVisible(html);
  for (const text of ["Start software demo", "Open source trace", "Compare layouts", "Ask Chalk"]) assert.match(visible, new RegExp(text));
  assert.match(visible, /source-tracing and prevention demos use separate saved examples/);
  assert.match(html, /<details class="card"><summary>Setup and saved observations/);
  assert.doesNotMatch(visible, /Fresh frames are arriving|Connect your overhead webcam|Measured tank profile|Configuration status is separate/);
  assert.equal((renderToStaticMarkup(React.createElement(DemoGuide, { disabled: true, onTrace: noAction, onPrevention: noAction, onChalk: noAction })).match(/disabled=""/g) ?? []).length, 3);
});

test("Camera puts the live preview before collapsed tank commissioning and advanced JSON", () => {
  const file = resolve("app/workspace/page.tsx");
  const compiled = ts.transpileModule(readFileSync(file, "utf8"), { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
  const mod = { exports: {} };
  new Function("require", "module", "exports", compiled)(name => {
    // Select the real Camera branch without opening a browser/device or running effects.
    if (name === "react") return { ...React, useState: initial => React.useState(initial === "overview" ? "camera" : initial) };
    if (name === "next/navigation") return { useRouter: () => ({ push() {} }) };
    if (name.endsWith(".module.css")) return { __esModule: true, default: new Proxy({}, { get: (_, key) => String(key) }) };
    if (name.startsWith(".")) {
      const base = resolve(dirname(file), name);
      return component([base, `${base}.tsx`, `${base}.ts`].find(candidate => existsSync(candidate)));
    }
    return require(name);
  }, mod, mod.exports);
  const html = render(React.createElement(mod.exports.default)), visible = defaultVisible(html);
  assert.ok(html.indexOf("<h1>Camera</h1>") < html.indexOf(">Live camera</h2>"));
  assert.ok(html.indexOf(">Live camera</h2>") < html.indexOf("Calibrate a tank and record trials when ready"));
  assert.match(html, /<details class="details-panel"><summary>Calibrate a tank and record trials when ready<\/summary>/);
  assert.ok(html.indexOf("Calibrate a tank and record trials when ready") < html.indexOf("Calibration request JSON"));
  assert.match(visible, /Live USB preview first/);
  assert.doesNotMatch(visible, /Field commissioning|Mapping pixel points|Calibration request JSON|Measured profile/);
});

test("Data Lab defaults to one changing-current comparison and keeps historical benchmarks closed", () => {
  const html = render(React.createElement(RealDataLab, { api: "" }));
  const visible = defaultVisible(html);
  assert.match(visible, /Follow the flow. Compare protection/);
  assert.match(visible, /Compare ocean layouts/);
  assert.match(html, /<details class="card"><summary>Research details and historical buoy validation/);
  assert.doesNotMatch(visible, /Load buoy comparison|Load current-driven prediction|Run reference buoy replay|Load fixed Kalman study|Load motion-vector diagnostic/);
});

test("completed study keeps the summary and plot visible while full model scores and provenance stay inspectable", () => {
  const html = render(React.createElement(FreshStudyResults, { api: "", report }));
  const visible = defaultVisible(html);
  assert.match(visible, /Last observed drift had the smallest average miss in this study/);
  assert.match(visible, /6\/6 historical groups.*180\/180 model-hour results/);
  for (const model of report.models) assert.ok(html.includes(model.label));
  assert.match(html, /<details class="details-panel"><summary>Compare all five models<\/summary>/);
  assert.match(visible, /Average miss.*1,573.4 m/);
  assert.doesNotMatch(visible, /<caption>Lower miss is better/);
  assert.match(visible, /Recorded · solid/); assert.match(visible, /Forecast · dashed/);
  assert.match(visible, /Grid spacing:/); assert.doesNotMatch(visible, /display units/);
  assert.match(visible, /Explain this result/); assert.match(visible, /Sign in to use Chalk/);
  assert.doesNotMatch(visible, /Pre-outcome acquisition amendment|Parent protocol|Frozen protocol:|100 m and acceleration/);
  assert.match(html, /<summary>Research details<\/summary>/);
  assert.match(html, /Pre-outcome acquisition amendment/); // Evidence stays accessible.
});

test("incomplete study exposes withheld results and never invents a forecast", () => {
  const html = render(React.createElement(FreshStudyResults, { api: "", report: pending }));
  const visible = defaultVisible(html);
  assert.match(visible, /performance remains unknown/);
  assert.match(visible, /Aggregate errors are withheld/);
  assert.match(visible, /Forecast unavailable/);
  assert.doesNotMatch(visible, /smallest average miss|<polyline/);
});

test("stationary plot has only one final label per path; all six timestamps remain inspectable", () => {
  const group = report.groups[0], model = group.models.find(m => m.id === "stationary");
  const html = renderToStaticMarkup(React.createElement(StudyPath, { group, model }));
  assert.equal((html.match(/Recorded · 6h/g) ?? []).length, 1);
  assert.equal((html.match(/Forecast · 6h/g) ?? []).length, 1);
  assert.doesNotMatch(html, /<text[^>]*>[1-5]h<\/text>/);
  for (const p of model.predictions) assert.ok(html.includes(p.time_utc));
  assert.match(html, /hour 1/);
});

test("endpoint-only map does not add an arrival path or start marker", () => {
  const profile = { id: "TEST_ONLY", bounds: { x_min_cm: 0, y_min_cm: 0, x_max_cm: 20, y_max_cm: 10 }, sources: [{ id: "A", polygon_cm: [[0,0],[2,0],[2,2]] }] };
  const html = renderToStaticMarkup(React.createElement(SourceMap, { profile, endpoint: { x_cm: 10, y_cm: 5, retained: true } }));
  assert.match(html, /arrival path unknown/); assert.match(html, /Water plane · cm/);
  assert.doesNotMatch(html, />Start<|>Last</);
  assert.match(html, /points=""/);
});

test("Prevention setup and saved-history controls are closed; synthetic example warning stays visible", () => {
  const html = render(React.createElement(PreventionWorkspace, { request: noAction, operatorConnected: false, onRequireOperator: noAction, cases: [], profiles: [], selectedCaseId: "", onSelectCase: noAction, onBusyChange: noAction, onStopCase: noAction }));
  const visible = defaultVisible(html);
  assert.match(visible, /Load prevention demo/);
  assert.match(visible, /separate synthetic example from the source-tracing demo/);
  assert.doesNotMatch(visible, /Reef-zone interception comparison|Freeze comparison|Baseline layout ID/);
  assert.match(html, /<details class="card"><summary>Create your own comparison from a source case/);
  assert.match(html, /<details class="card"><summary>Saved comparisons/);
});


test("recorded outcome origins stay visible before disclosure; unknown and archived limits cannot be hidden", () => {
  // Reuse the repository's existing policy fixture. It is test data, not physical evidence.
  const payload = JSON.parse(readFileSync(new URL("../../tests/fixtures/prevention_validation/analysis_bundle_v1.json", import.meta.url), "utf8")).payload;
  const detail = { comparison: payload.comparison, trials: payload.trials, evaluation: { ...payload.evaluation, id: "TEST_ONLY_EVALUATION", comparison_id: payload.comparison.id, snapshot_hash: payload.evaluation.source_snapshot_hash, physical_validation: false, limitations: ["Policy fixture only; no physical experiment."] }, is_current: false, archive_reason: "TEST_ONLY" };
  const html = render(React.createElement(ComparisonDetail, { report: detail, cases: [], disabled: false, request: noAction, mutate: noAction, onUpdated: noAction, operatorConnected: false, onRequireOperator: noAction }));
  const visible = defaultVisible(html);
  assert.match(visible, /Archived comparison/);
  const physical = payload.evaluation.by_origin.OPERATOR_REPORTED_PHYSICAL.plan.recorded_total;
  const synthetic = payload.evaluation.by_origin.SYNTHETIC_DEMO.plan.recorded_total;
  assert.ok(visible.includes(`${physical} operator-reported physical outcomes`));
  assert.ok(visible.includes(`${synthetic} synthetic demo outcomes`));
  assert.match(visible, /Review recorded outcomes/);
  assert.match(visible, /Synthetic records do not validate a physical collector/);
  assert.doesNotMatch(visible, /Actually released tokens and accounting|Predicted entry bounds|Save one-token outcome/);
  assert.match(html, /Recorded physical outcomes/); // The full ledger remains accessible.
});
