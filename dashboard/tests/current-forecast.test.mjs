import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import { validateCurrentForecast } from "../app/components/current-forecast-state.ts";

// Entirely synthetic presentation/contract fixture. Its coordinates are not
// PacIOOS observations, a numerical advection benchmark or measured waste.
const start = "2026-10-17T18:00:00Z", end = "2026-10-18T00:00:00Z";
const point = (elapsed_s, latitude_deg, longitude_deg, eastward_m_s, northward_m_s) => ({
  elapsed_s, latitude_deg, longitude_deg, eastward_m_s, northward_m_s,
  speed_m_s: Math.hypot(eastward_m_s, northward_m_s),
  time_utc: new Date(Date.parse(start) + elapsed_s * 1000).toISOString(),
});
function fixture() {
  const first = point(0, 21, -158, 0.2, 0.1);
  return {
    schema_version: 1, kind: "CURRENT_FORCED_PREVIEW", status: "COMPLETED", mode: "forecast_snapshot",
    snapshot_sha256: "a".repeat(64), method_sha256: "b".repeat(64), manifest_sha256: "c".repeat(64),
    release: { latitude_deg: 21, longitude_deg: -158, start_time_utc: start, horizon_s: 21600 },
    dynamic: { status: "COMPLETED", reason_code: null, requested_horizon_s: 21600, completed_horizon_s: 21600,
      track: [first, point(10800, 21.005, -157.995, -0.1, 0.2), point(21600, 21.01, -158.01, -0.3, 0.05)] },
    persistence: { status: "COMPLETED", reason_code: null, requested_horizon_s: 21600, completed_horizon_s: 21600,
      track: [structuredClone(first), point(10800, 21.005, -157.98, 0.2, 0.1), point(21600, 21.01, -157.96, 0.2, 0.1)] },
    forcing: { source_url: "https://example.org/synthetic-current-test.csv", metadata_url: "https://example.org/synthetic-test-metadata",
      attribution: "Synthetic display fixture; no physical evidence", captured_at_utc: "2026-10-17T17:00:00Z",
      valid_start_utc: start, valid_end_utc: end, model_issue_time_utc: null, depth_m: 0.25 },
    vector_frames: [0, 10800, 21600].map((elapsed, index) => ({ time_utc: point(elapsed, 0, 0, 0, 0).time_utc,
      vectors: [
        { latitude_deg: 21, longitude_deg: -158, eastward_m_s: 0.2 - index * 0.1, northward_m_s: 0.1 },
        { latitude_deg: 21.008, longitude_deg: -157.98, eastward_m_s: 0.1, northward_m_s: 0.15 + index * 0.05 },
        { latitude_deg: 21.5, longitude_deg: -157.5, eastward_m_s: 0.5, northward_m_s: 0.5 },
      ] })),
    endpoint_separation_m: 5000, validation: { measured_track_available: false, physical_validation: false,
      plastic_motion_validated: false, forecast_skill_established: false, tank_flow_used: false,
      heldout_buoy_positions_used: false, ade_m: null, fde_m: null },
    limitations: ["Synthetic display fixture; not measured waste or a claim of accuracy."],
  };
}
const reject = value => assert.throws(() => validateCurrentForecast(value), /unsupported scientific scope/);

test("current preview validates a bounded forcing illustration without changing evidence", () => {
  const report = fixture(), before = JSON.stringify(report);
  assert.equal(validateCurrentForecast(report), report);
  assert.equal(JSON.stringify(report), before);
  assert.equal(report.validation.ade_m, null);
  const archived = fixture(); archived.mode = "archived_forecast_snapshot";
  validateCurrentForecast(archived);
});

test("a forecast snapshot cannot become measured waste, measured skill or tank calibration", () => {
  for (const mutate of [
    report => { report.validation.measured_track_available = true; },
    report => { report.validation.physical_validation = true; },
    report => { report.validation.plastic_motion_validated = true; },
    report => { report.validation.forecast_skill_established = true; },
    report => { report.validation.tank_flow_used = true; },
    report => { report.validation.heldout_buoy_positions_used = true; },
    report => { report.validation.ade_m = 0; }, report => { report.validation.fde_m = 0; },
  ]) { const report = fixture(); mutate(report); reject(report); }
});

test("missing identities, invalid calendars, geography, units and unsafe source links are refused", () => {
  for (const mutate of [
    report => { report.snapshot_sha256 = "bad"; }, report => { report.method_sha256 = null; },
    report => { report.release.latitude_deg = 90; }, report => { report.release.longitude_deg = 400; },
    report => { report.release.horizon_s = -1; }, report => { report.release.horizon_s = 21601; },
    report => { report.release.start_time_utc = "2026-02-30T18:00:00Z"; },
    report => { report.forcing.valid_end_utc = report.forcing.valid_start_utc; },
    report => { report.forcing.depth_m = -0.25; },
    report => { report.forcing.source_url = "javascript:alert(1)"; },
    report => { report.forcing.metadata_url = "https://credential:secret@example.org/"; },
    report => { report.mode = "live_water_measurement"; },
    report => { report.dynamic.track[1].eastward_m_s = Infinity; },
    report => { report.dynamic.track[1].northward_m_s = 11; },
    report => { report.dynamic.track[1].speed_m_s = -1; },
    report => { report.dynamic.track[1].speed_m_s = 0; },
    report => { report.dynamic.track[1].latitude_deg = NaN; },
  ]) { const report = fixture(); mutate(report); reject(report); }
});

test("completed paths must begin at the release and finish at their declared horizon", () => {
  for (const mutate of [
    report => { report.dynamic.track = []; }, report => { report.dynamic.track.pop(); },
    report => { report.dynamic.completed_horizon_s = -1; },
    report => { report.dynamic.completed_horizon_s = 21601; },
    report => { report.dynamic.requested_horizon_s = 3600; },
    report => { report.dynamic.track[0].longitude_deg += 0.01; },
    report => { report.dynamic.track[1].elapsed_s = 100; },
    report => { report.dynamic.track[1].time_utc = report.dynamic.track[0].time_utc; },
    report => { report.dynamic.track[2].time_utc = "2026-10-18T01:00:00Z"; },
    report => { report.dynamic.reason_code = "MASKED_CURRENT_CELL"; },
    report => { report.status = "PARTIAL"; }, report => { report.endpoint_separation_m = null; },
  ]) { const report = fixture(); mutate(report); reject(report); }
});

function partialFixture() {
  const report = fixture();
  Object.assign(report.dynamic, { status: "PARTIAL", reason_code: "MASKED_CURRENT_CELL", completed_horizon_s: 10800 });
  report.dynamic.track.pop(); report.status = "PARTIAL"; report.endpoint_separation_m = null;
  return report;
}

test("partial tracks retain only accepted positions and withhold full-horizon endpoint disagreement", () => {
  const partial = partialFixture(); validateCurrentForecast(partial);
  assert.equal(partial.dynamic.track.at(-1).elapsed_s, partial.dynamic.completed_horizon_s);
  for (const mutate of [
    report => { report.endpoint_separation_m = 1; }, report => { report.status = "COMPLETED"; },
    report => { report.dynamic.completed_horizon_s = 21600; },
    report => { report.dynamic.reason_code = null; },
  ]) { const report = partialFixture(); mutate(report); reject(report); }
  const unsupported = fixture();
  for (const path of [unsupported.dynamic, unsupported.persistence]) Object.assign(path, {
    status: "UNSUPPORTED", reason_code: "MASKED_CURRENT_CELL", completed_horizon_s: 0, track: [],
  });
  unsupported.status = "UNSUPPORTED"; unsupported.endpoint_separation_m = null;
  validateCurrentForecast(unsupported);
});

test("current arrow frames must remain chronological, finite and within supplied valid times", () => {
  for (const mutate of [
    report => { report.vector_frames = []; },
    report => { report.vector_frames[1].time_utc = report.vector_frames[0].time_utc; },
    report => { report.vector_frames[0].time_utc = "2026-10-17T17:59:59Z"; },
    report => { report.vector_frames[2].time_utc = "2026-10-18T00:00:01Z"; },
    report => { report.vector_frames[1].vectors[0].eastward_m_s = NaN; },
    report => { report.vector_frames[1].vectors[0].latitude_deg = 86; },
  ]) { const report = fixture(); mutate(report); reject(report); }
});

// Render actual TSX with the same framework/CSS adaptation used by existing
// plot-controls tests. No mock current solver or live provider is substituted.
const require = createRequire(import.meta.url), loaded = new Map();
function component(path) {
  const file = resolve(path);
  if (loaded.has(file)) return loaded.get(file).exports;
  const mod = { exports: {} }; loaded.set(file, mod);
  const compiled = ts.transpileModule(readFileSync(file, "utf8"), { compilerOptions: {
    jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true,
  } }).outputText;
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
const { CurrentForecastFigure } = component("app/components/current-forecast.tsx");
const noAction = () => assert.fail("Rendering must not trigger a mutation or provider request");
const draw = (report = fixture(), visible = { dynamic: true, persistence: true, currents: true }, frame = 0) => renderToStaticMarkup(React.createElement(CurrentForecastFigure, { report, visible, frame, onToggle: noAction }));
const pathPoints = (html, series) => html.match(new RegExp(`data-plot-series="${series}"><polyline points="([^"]*)"`))?.[1];
const grid = html => html.match(/(?:Grid spacing|Plot grid): ([^<]+)/)?.[1];

test("checkbox layers and valid-time changes preserve complete-data path coordinates and scale", () => {
  const report = fixture(), before = JSON.stringify(report), all = draw(report);
  const dynamic = draw(report, { dynamic: true, persistence: false, currents: false });
  const baseline = draw(report, { dynamic: false, persistence: true, currents: false });
  const later = draw(report, undefined, 2);
  assert.ok(pathPoints(all, "dynamic")); assert.ok(pathPoints(all, "persistence"));
  assert.ok(grid(all));
  assert.equal(pathPoints(dynamic, "dynamic"), pathPoints(all, "dynamic"));
  assert.equal(pathPoints(baseline, "persistence"), pathPoints(all, "persistence"));
  assert.equal(pathPoints(later, "dynamic"), pathPoints(all, "dynamic"));
  assert.equal(pathPoints(later, "persistence"), pathPoints(all, "persistence"));
  for (const html of [dynamic, baseline, later]) assert.equal(grid(html), grid(all));
  assert.equal(pathPoints(dynamic, "persistence"), undefined);
  assert.equal(pathPoints(baseline, "dynamic"), undefined);
  assert.equal(JSON.stringify(report), before);
});

test("hiding every forecast layer is explicit and keeps its scientific frame", () => {
  const all = draw(), hidden = draw(fixture(), { dynamic: false, persistence: false, currents: false });
  assert.match(hidden, /No layers selected/);
  assert.doesNotMatch(hidden, /data-plot-series=/);
  assert.equal(grid(hidden), grid(all));
  assert.match(hidden, /No observed waste track/);
});

test("partial paths do not acquire a made-up continuation through plotting", () => {
  const report = partialFixture(), html = draw(report);
  const points = pathPoints(html, "dynamic").split(" ");
  assert.equal(points.length, report.dynamic.track.length);
  assert.equal(points.length, 2);
  assert.match(html, /Both are predictions/);
});

test("the trajectory view does not shrink to fit distant vectors and clips current arrows", () => {
  const report = fixture(), all = draw(report);
  const withoutDistantVectors = fixture();
  withoutDistantVectors.vector_frames.forEach(frame => { frame.vectors.pop(); });
  const local = draw(withoutDistantVectors);
  assert.equal(pathPoints(all, "dynamic"), pathPoints(local, "dynamic"));
  assert.equal(pathPoints(all, "persistence"), pathPoints(local, "persistence"));
  assert.equal(grid(all), grid(local));
  assert.match(all, /<clipPath/);
  assert.match(all, /clip-path="url\(#/);
});
