import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

// Render the actual presentation with framework/CSS loading adapted for Node.
// These checks do not pretend to be browser interaction or physical validation.
const require = createRequire(import.meta.url), loaded = new Map();
function component(path) {
  const file = resolve(path);
  if (loaded.has(file)) return loaded.get(file).exports;
  const mod = { exports: {} }; loaded.set(file, mod);
  const compiled = ts.transpileModule(readFileSync(file, "utf8"), { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
  new Function("require", "module", "exports", compiled)(name => {
    if (name.endsWith(".module.css")) return { __esModule: true, default: new Proxy({}, { get: (_, key) => String(key) }) };
    if (name === "next/link") return { __esModule: true, default: ({ children, ...props }) => React.createElement("a", props, children) };
    if (name.startsWith(".")) {
      const base = resolve(dirname(file), name), dependency = [base, `${base}.tsx`, `${base}.ts`].find(existsSync);
      if (dependency) return component(dependency);
    }
    return require(name);
  }, mod, mod.exports);
  return mod.exports;
}
const root = resolve("app/components");
const { PlotSeriesControls, HelpLabel } = component(`${root}/plot-controls.tsx`);
const { StudyPathFigure } = component(`${root}/fresh-drifter-study.tsx`);
const { VectorArrowPlot } = component(`${root}/vector-diagnostic.tsx`);
const { RecordedPathFigure } = component(`${root}/recorded-flow-trajectories.tsx`);
const study = JSON.parse(readFileSync(new URL("./fixtures/fresh-drifter-report.json", import.meta.url), "utf8"));
const pending = JSON.parse(readFileSync(new URL("./fixtures/fresh-drifter-pending-report.json", import.meta.url), "utf8"));
const tank = JSON.parse(readFileSync(new URL("./fixtures/recorded-trajectory-report.json", import.meta.url), "utf8"));
const render = (Component, props) => renderToStaticMarkup(React.createElement(Component, props));
const noAction = () => assert.fail("Rendering must not call an action");
function descendants(element) {
  if (!React.isValidElement(element)) return [];
  return [element, ...React.Children.toArray(element.props.children).flatMap(descendants)];
}

test("native series checkboxes have explanatory labels and report the actual checked value", () => {
  const calls = [];
  const tree = PlotSeriesControls({ legend: "Show paths", series: [
    { id: "recorded", label: "Recorded", explanation: "Saved positions.", color: "#267864", checked: true },
    { id: "forecast", label: "Forecast", explanation: "Model predictions.", color: "#087fac", dashed: true, checked: false },
  ], onChange: (...args) => calls.push(args) });
  const inputs = descendants(tree).filter(el => el.type === "input");
  assert.deepEqual(inputs.map(el => [el.props.type, el.props.checked]), [["checkbox", true], ["checkbox", false]]);
  inputs[0].props.onChange({ target: { checked: false } });
  inputs[1].props.onChange({ target: { checked: true } });
  assert.deepEqual(calls, [["recorded", false], ["forecast", true]]);
  const html = renderToStaticMarkup(tree);
  assert.match(html, /<fieldset/); assert.match(html, /<legend>Show paths/);
  assert.match(html, /Saved positions/); assert.match(html, /Model predictions/);
  assert.match(html, /Scale and scores stay fixed/);
});

test("metric help is a keyboard-focusable plain button with its own explanation", () => {
  const html = render(HelpLabel, { label: "ADE (m)", explanation: "Average forecast position miss." });
  const describedBy = html.match(/aria-describedby="([^"]+)"/)?.[1];
  assert.ok(describedBy);
  assert.match(html, /<button type="button"/);
  assert.ok(html.includes(`id="${describedBy}" role="tooltip"`));
  assert.match(html, /Average forecast position miss/);
  assert.doesNotMatch(html, /title=/); // No mouse-only native-title explanation.
});

const group = study.groups[0], model = group.models.find(m => m.id === "kalman_cv");
const path = visible => render(StudyPathFigure, { group, model, visible, onToggle: noAction });
const pathPoints = (html, series) => html.match(new RegExp(`data-plot-series="${series}"><polyline points="([^"]+)"`))?.[1];
const gridSpacing = html => html.match(/Grid spacing: ([^<]+)/)?.[1];

test("fresh NOAA paths can be inspected separately without changing coordinates or equal-axis scale", () => {
  const before = JSON.stringify({ group, model });
  const both = path({ recorded: true, forecast: true }), recorded = path({ recorded: true, forecast: false }), forecast = path({ recorded: false, forecast: true });
  assert.ok(pathPoints(both, "recorded")); assert.ok(pathPoints(both, "forecast"));
  assert.equal(pathPoints(recorded, "recorded"), pathPoints(both, "recorded"));
  assert.equal(pathPoints(forecast, "forecast"), pathPoints(both, "forecast"));
  assert.equal(pathPoints(recorded, "forecast"), undefined); assert.equal(pathPoints(forecast, "recorded"), undefined);
  assert.equal(gridSpacing(recorded), gridSpacing(both)); assert.equal(gridSpacing(forecast), gridSpacing(both));
  assert.match(both, /Equal east\/north metre scale/);
  assert.equal(JSON.stringify({ group, model }), before, "presentation does not alter saved evidence");
});

test("hiding every fresh-study path is explicit and preserves the plot grid", () => {
  const both = path({ recorded: true, forecast: true }), hidden = path({ recorded: false, forecast: false });
  assert.match(hidden, /role="status"[^>]*>No paths selected/);
  assert.doesNotMatch(hidden, /data-plot-series=/);
  assert.equal(gridSpacing(hidden), gridSpacing(both));
  assert.equal((hidden.match(/<line /g) ?? []).length, (both.match(/<line /g) ?? []).length);
});

test("pending NOAA data cannot gain a path from visibility controls", () => {
  const g = pending.groups[0], m = g.models[0];
  const html = render(StudyPathFigure, { group: g, model: m, visible: { recorded: true, forecast: true }, onToggle: noAction });
  assert.match(html, /Forecast unavailable/); assert.doesNotMatch(html, /<polyline|type="checkbox"/);
});

const rows = [{ label: "Hour 1", detail: "Test-only vectors", observed: [0.1, 0.2], predicted: [0.3, 0.5], residual: [0.2, 0.3], angle: 1 }];
const vectors = visible => render(VectorArrowPlot, { rows, unit: "m/s", northUp: true, visible, onToggle: noAction });
const arrowPath = (html, series) => html.match(new RegExp(`data-plot-series="${series}"><path d="([^"]+)"`))?.[1];
const arrowScale = html => html.match(/45 display units = ([^<]+)/)?.[1];

test("vector controls isolate error or forecast arrows at the same full-data scale", () => {
  const all = vectors({ observed: true, predicted: true, residual: true });
  for (const series of ["observed", "predicted", "residual"]) {
    const solo = vectors({ observed: series === "observed", predicted: series === "predicted", residual: series === "residual" });
    assert.equal(arrowPath(solo, series), arrowPath(all, series));
    assert.equal(arrowScale(solo), arrowScale(all));
    for (const other of ["observed", "predicted", "residual"].filter(s => s !== series)) assert.equal(arrowPath(solo, other), undefined);
  }
  assert.match(all, /Observed vectors/); assert.match(all, /Predicted vectors/); assert.match(all, /Error vectors/);
});

test("all-hidden vector display states what happened and keeps its numeric scale", () => {
  const all = vectors({ observed: true, predicted: true, residual: true }), hidden = vectors({ observed: false, predicted: false, residual: false });
  assert.match(hidden, /No vectors selected/); assert.doesNotMatch(hidden, /data-plot-series=/);
  assert.equal(arrowScale(hidden), arrowScale(all));
});

test("recorded tank path toggles retain physical bounds and withheld runs stay undrawn", () => {
  const run = tank.recordings[0], props = { report: tank, run, onToggle: noAction };
  const all = render(RecordedPathFigure, { ...props, visible: { recorded: true, forecast: true } });
  const solo = render(RecordedPathFigure, { ...props, visible: { recorded: false, forecast: true } });
  assert.equal(pathPoints(solo, "forecast"), pathPoints(all, "forecast"));
  assert.equal(pathPoints(solo, "recorded"), undefined);
  assert.equal(solo.match(/<rect[^>]+>/)?.[0], all.match(/<rect[^>]+>/)?.[0]);
  const hidden = render(RecordedPathFigure, { ...props, visible: { recorded: false, forecast: false } });
  assert.match(hidden, /No paths selected/); assert.doesNotMatch(hidden, /data-plot-series=/);
  const withheld = render(RecordedPathFigure, { ...props, run: tank.recordings[1], visible: { recorded: true, forecast: true } });
  assert.match(withheld, /No path is drawn for this withheld run/); assert.doesNotMatch(withheld, /<polyline|type="checkbox"/);
});
