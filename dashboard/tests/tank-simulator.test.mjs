import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import { recordedTankPositionAt, resetTankCaptureCursor, supportedTankVectors, tankHeadline, tankPositionAt, tankSceneIsCurrent, tankWaterLabels, validateTankScene, visibleTankPaths } from "../app/components/tank-simulator-state.ts";

// Invented bounded contract fixture. Never a recorded physical experiment.
const H = "a".repeat(64), E = "b".repeat(64), expected = { comparisonId: "comparison-test", evaluationHash: E };
const clone = value => structuredClone(value);
function stats(released = 0) { return { planned: 4, released, missing_planned: 4 - released, zone_entries: 0, captured_before_entry: 0, no_entry: released, unresolved: 0, token_accounted: released, unaccounted: 0, recording_linked: released, entry_rate_bounds: { lower: 0, upper: (4 - released) / 4, denominator: 4 } }; }
function group(released = 0) { return { layouts: { baseline: stats(released), intervention: stats() }, plan: { expected_total: 8, recorded_total: released, complete: false, balanced: false, order_followed: true }, effect_bounds: { lower: -1, upper: (4 - released) / 4 } }; }
function fixture() {
  const geometry = { bounds_cm: { x_min_cm: 0, x_max_cm: 10, y_min_cm: 0, y_max_cm: 8 }, sources: ["A", "B"].map((id, index) => ({ id, polygon_cm: [[1 + 2 * index, 1], [2 + 2 * index, 1], [2 + 2 * index, 2], [1 + 2 * index, 2]] })), protected_zone_cm: [[8, 4], [9, 4], [9, 6], [8, 6]], layouts: ["baseline", "intervention"].map(id => ({ id, profile_id: `profile-${id}`, profile_hash: H, flow_hash: H, calibration_id: `map-${id}`, traps: [{ id: "mesh", polygon_cm: [[6, 4], [7, 4], [7, 6], [6, 6]], retention: "absorbing" }] })) };
  const paths = geometry.layouts.flatMap(layout => geometry.sources.map((source, index) => ({ layout: layout.id, source_id: source.id, particle_index: 0, points: [0, 1, 2].map(t => ({ t_s: t, x_cm: 1 + 2 * index + t, y_cm: 2 })), zone_entry_s: null, capture_s: null, display_stop_s: 2, support_status: "SUPPORTED_THROUGH_FIRST_EVENT_OR_HORIZON", sampling: "LEGACY_DECIMATED_REPRESENTATIVE", counts_derived_from_path: false })));
  return { schema_version: 1, kind: "TANK_RIG_SCENE", comparison_id: expected.comparisonId, comparison_sha256: H, numerical_report_sha256: H, evaluation_snapshot_hash: E, scene_sha256: H, case_id: "case-test", case_revision: 1, source_evidence_id: "estimate-test", is_current: true, archive_reason: null, data_origin: "SYNTHETIC", physical_validation: false, units: { position: "cm", time: "s", velocity: "cm/s" }, vertical: { mode: "SCHEMATIC_SURFACE_ONLY", surface_z_cm: 0, measured_depth_cm: null, physical_geometry_verified: false }, geometry, simulation: { engine: "EXISTING_TANK_EULER_MARUYAMA", scenario_id: "nominal", event_time_kind: "TIME_NODE_UPPER_BOUND_NOT_EXACT_COLLISION", horizon_s: 2, seed: 17, particles_per_source: 20, paths }, vectors: geometry.layouts.map(row => ({ layout: row.id, flow_hash: H, time_varying: false, nodes: [{ x_cm: 1, y_cm: 2, vx_cm_s: 1, vy_cm_s: 0, supported: true }] })), results: { recommendation: "INTERVENTION", robust_benefit_min: 0.4, robust_benefit_max: 0.4, rows: geometry.sources.map(source => ({ scenario_id: "nominal", source_id: source.id, baseline: { particles: 20, zone_entry_count: 10, zone_entry_fraction: 0.5, unsupported_count: 0 }, intervention: { particles: 20, zone_entry_count: 2, zone_entry_fraction: 0.1, unsupported_count: 0 } })), by_origin: { SYNTHETIC_DEMO: group(), OPERATOR_REPORTED_PHYSICAL: group() } }, actual: { status: "NOT_CAPTURED", reason_codes: ["NO_VERIFIED_RELEASE_TIME_ANCHOR"], clock: "CAPTURE_START_UNALIGNED", release_alignment: "MISSING", positional_error_metrics: null, reported_physical_trial_count: 0, recordings: [] }, limitations: ["Synthetic test fixture, not a physical tank."] };
}
function recordedFixture() {
  const f = fixture(); f.data_origin = "MEASURED_TANK";
  f.results.by_origin.OPERATOR_REPORTED_PHYSICAL = group(1);
  f.actual.status = "RECORDED_TRACKS_AVAILABLE"; f.actual.reported_physical_trial_count = 1;
  f.actual.recordings = [{ trial_id: "trial-one", recording_id: "recording-one", recording_content_hash: H, reason_codes: ["NO_DETECTION"], layout: "baseline", source_id: "A", calibration_id: "map-baseline", camera_session_id: "camera-test", segments: [{ track_id: "track-one", points: [{ t_s: 0.1, x_cm: 1, y_cm: 2 }, { t_s: 0.3, x_cm: 1.2, y_cm: 2 }] }, { track_id: "track-two", points: [{ t_s: 0.6, x_cm: 1.5, y_cm: 2 }, { t_s: 0.8, x_cm: 1.7, y_cm: 2 }] }], gaps: [{ t_s: 0.4, reason: "NO_DETECTION" }], outcome_automatically_verified: false }];
  return f;
}
const reject = f => assert.throws(() => validateTankScene(f, expected), /No result was accepted/);

test("a bound synthetic scene preserves its saved coordinates, counts and missing physical denominator", () => {
  const f = fixture(), before = JSON.stringify(f);
  assert.equal(validateTankScene(f, expected), f); assert.equal(JSON.stringify(f), before);
  assert.deepEqual(tankHeadline(f, "baseline"), { predictedEntries: 20, predictedParticles: 40, unsupportedParticles: 0, physicalEntries: 0, physicalReleased: 0, physicalPlanned: 4, missingPhysical: 4, physicalBounds: { lower: 0, upper: 1, denominator: 4 }, syntheticRecorded: 0 });
});
test("comparison, evaluation, units and physical-geometry boundaries reject stale or fabricated scenes", () => {
  for (const change of [f => { f.comparison_id = "another"; }, f => { f.evaluation_snapshot_hash = H; }, f => { f.physical_validation = true; }, f => { f.vertical.measured_depth_cm = 5; }, f => { f.vertical.physical_geometry_verified = true; }, f => { f.units.position = "m"; }, f => { f.geometry.bounds_cm.x_max_cm = Infinity; }, f => { f.geometry.layouts[0] = null; }, f => { f.simulation.engine = "NEW_CFD"; }, f => { f.simulation.event_time_kind = "EXACT_COLLISION"; }]) { const f = fixture(); change(f); reject(f); }
});
test("visibility filters never change frozen full-ensemble or trial counts", () => {
  const f = fixture(), before = JSON.stringify(f), counts = tankHeadline(f, "baseline");
  assert.equal(visibleTankPaths(f, "baseline", "all").length, 2);
  assert.equal(visibleTankPaths(f, "baseline", "A").length, 1);
  assert.equal(visibleTankPaths(f, "intervention", "B").length, 1);
  assert.equal(visibleTankPaths(f, "baseline", "unknown").length, 0);
  for (const time of [0, 0.5, 1, 2, 3]) for (const path of visibleTankPaths(f, "baseline", "A")) tankPositionAt(path.points, time, path.display_stop_s);
  assert.deepEqual(tankHeadline(f, "baseline"), counts); assert.equal(JSON.stringify(f), before);
});
test("display interpolation stays between saved points and never extrapolates an event prefix", () => {
  const points = [{ t_s: 0, x_cm: 1, y_cm: 2 }, { t_s: 0.7, x_cm: 2.4, y_cm: 4.8 }];
  assert.deepEqual(tankPositionAt(points, 0.35, 1), { t_s: 0.35, x_cm: 1.7, y_cm: 3.4 });
  assert.equal(tankPositionAt(points, 0.8, 1), null); assert.equal(tankPositionAt(points, 1.1, 1), null);
  assert.equal(tankPositionAt(points, -0.1, 1), null); assert.equal(tankPositionAt(points, NaN, 1), null); assert.equal(tankPositionAt([], 0, 1), null);
});
test("legacy decimation is conservatively censored at the first event without inventing a collision point", () => {
  const f = fixture(), path = f.simulation.paths[0]; path.zone_entry_s = 1.8; path.display_stop_s = 1.8; path.points = path.points.slice(0, 2);
  validateTankScene(f, expected); assert.equal(tankPositionAt(path.points, 1.5, path.display_stop_s), null);
  const outside = clone(f); outside.simulation.paths[0].points.push({ t_s: 1.9, x_cm: 2.9, y_cm: 2 }); reject(outside);
  const afterEvent = clone(f); afterEvent.simulation.paths[0].display_stop_s = 2; reject(afterEvent);
});
test("unsupported paths are absent rather than promoted to fully supported motion", () => {
  const f = fixture(), path = f.simulation.paths[0]; path.support_status = "UNSUPPORTED_PATH_WITHHELD"; path.points = []; path.display_stop_s = null;
  validateTankScene(f, expected); assert.equal(tankPositionAt(path.points, 0, 0), null);
  path.points = [{ t_s: 0, x_cm: 1, y_cm: 2 }]; reject(f);
});
test("malformed path chronology, identity, geometry and flow lineage are refused", () => {
  for (const change of [f => { f.simulation.paths[0].source_id = "unknown"; }, f => { f.simulation.paths[0].points[1].t_s = 0; }, f => { f.simulation.paths[0].points[1].x_cm = -1; }, f => { f.simulation.paths[0].points = null; }, f => { f.simulation.paths.push(clone(f.simulation.paths[0])); }, f => { f.vectors[0].flow_hash = E; }, f => { f.vectors[0].time_varying = true; }, f => { f.vectors[0].nodes[0].supported = "true"; }]) { const f = fixture(); change(f); reject(f); }
});
test("unsupported vector flags survive validation but never become visible current glyphs", () => {
  const f = fixture(); f.vectors[0].nodes.push({ x_cm: 8, y_cm: 7, vx_cm_s: 2, vy_cm_s: 3, supported: false });
  const before = JSON.stringify(f); validateTankScene(f, expected);
  assert.equal(supportedTankVectors(f, "baseline").length, 1); assert.equal(f.vectors[0].nodes.length, 2);
  assert.equal(f.vectors[0].nodes[1].supported, false); assert.equal(JSON.stringify(f), before);
});
test("water-plane labels use only declared source regions and bounds with a small fixed coordinate set", () => {
  const f = fixture(), before = JSON.stringify(f), labels = tankWaterLabels(f);
  assert.deepEqual(labels.filter(label => label.kind === "source").map(label => label.text), ["Source A", "Source B"]);
  assert.deepEqual(labels.filter(label => label.kind === "coordinate").map(label => label.text), ["x 0 cm", "x 5 cm", "x 10 cm", "y 4 cm", "y 8 cm"]);
  assert.ok(labels.length <= 11); assert.ok(labels.every(label => label.x_cm >= 0 && label.x_cm <= 10 && label.y_cm >= 0 && label.y_cm <= 8));
  assert.equal(JSON.stringify(f), before); assert.ok(labels.every(label => !/depth|pump|webcam/i.test(label.text)));
});
test("actual recordings keep their unaligned capture clock and never infer position error", () => {
  const f = recordedFixture(); validateTankScene(f, expected);
  const rec = f.actual.recordings[0];
  assert.deepEqual(recordedTankPositionAt(rec, 0.2), rec.segments[0].points[0]);
  assert.equal(recordedTankPositionAt(rec, 0), null); assert.equal(recordedTankPositionAt(rec, 0.4), null);
  assert.equal(recordedTankPositionAt(rec, 0.5), null); assert.equal(recordedTankPositionAt(rec, 0.9), null);
  assert.deepEqual(recordedTankPositionAt(rec, 0.7), rec.segments[1].points[0]);
  assert.equal(f.actual.positional_error_metrics, null); assert.equal(f.actual.release_alignment, "MISSING");
});
test("capture metadata cannot masquerade as synthetic truth, aligned release timing or camera-verified outcomes", () => {
  for (const change of [f => { f.data_origin = "SYNTHETIC"; }, f => { f.actual.clock = "RELEASE_ALIGNED"; }, f => { f.actual.positional_error_metrics = { ade_cm: 0 }; }, f => { f.actual.recordings[0].outcome_automatically_verified = true; }, f => { f.actual.recordings[0].calibration_id = "other-map"; }, f => { f.actual.reported_physical_trial_count = 2; }, f => { f.actual.recordings[0].segments[0].points[1].t_s = 1; }, f => { f.actual.recordings[0].gaps.push({ t_s: 0.2, reason: "NO_DETECTION" }); }]) { const f = recordedFixture(); change(f); reject(f); }
});
test("gap-only recording receipts remain counts-only with their failures preserved", () => {
  const f = recordedFixture(); f.actual.status = "REPORTED_COUNTS_ONLY"; f.actual.recordings[0].segments = [];
  validateTankScene(f, expected); assert.equal(recordedTankPositionAt(f.actual.recordings[0], 0.2), null);
  f.actual.status = "RECORDED_TRACKS_AVAILABLE"; reject(f);
});
test("a different source or layout starts a fresh capture cursor instead of inheriting another recording clock", () => {
  const f = recordedFixture(), old = { recordingId: "another-recording", captureTime: 19.5 };
  const reset = resetTankCaptureCursor();
  assert.deepEqual(reset, { recordingId: "", captureTime: 0 });
  assert.deepEqual(old, { recordingId: "another-recording", captureTime: 19.5 });
  assert.equal(recordedTankPositionAt(f.actual.recordings[0], old.captureTime), null);
  assert.equal(reset.captureTime < f.actual.recordings[0].segments[0].points[0].t_s, true);
});
test("both filter event handlers reset the recording identity and capture cursor, not just the displayed timer", () => {
  const source = ts.createSourceFile("tank-simulator.tsx", readFileSync("app/components/tank-simulator.tsx", "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const functions = new Map();
  function visit(node) { if (ts.isFunctionDeclaration(node) && node.name) functions.set(node.name.text, node); ts.forEachChild(node, visit); }
  visit(source);
  function calls(node) { const found = []; function walk(child) { if (ts.isCallExpression(child)) found.push(child.expression.getText(source)); ts.forEachChild(child, walk); } walk(node); return found; }
  assert.ok(calls(functions.get("changeSource")).includes("resetCapture"));
  assert.ok(calls(functions.get("changeLayout")).includes("resetCapture"));
  for (const name of ["resetTankCaptureCursor", "setCaptureTime", "setRecordingId", "setPlaying"]) assert.ok(calls(functions.get("resetCapture")).includes(name));
  const workspace = readFileSync("app/components/prevention-workspace.tsx", "utf8");
  assert.match(workspace, /<TankSimulator[^>]*current=\{current\}/);
});
test("trial accounting cannot turn missing releases into zero physical risk", () => {
  for (const change of [f => { f.results.by_origin.OPERATOR_REPORTED_PHYSICAL.layouts.baseline.entry_rate_bounds.upper = 0; }, f => { f.results.by_origin.OPERATOR_REPORTED_PHYSICAL.plan.recorded_total = 8; }, f => { f.results.by_origin.OPERATOR_REPORTED_PHYSICAL.layouts.baseline.missing_planned = 0; }, f => { f.results.rows[0].baseline.zone_entry_count = 21; }]) { const f = fixture(); change(f); reject(f); }
});

const require = createRequire(import.meta.url), loaded = new Map();
function component(path) {
  const file = resolve(path); if (loaded.has(file)) return loaded.get(file).exports;
  const mod = { exports: {} }; loaded.set(file, mod);
  let compiled = ts.transpileModule(readFileSync(file, "utf8"), { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
  if (file.endsWith("/tank-simulator.tsx")) compiled += "\nmodule.exports.TestReadyTankSimulator = ReadyTankSimulator;";
  new Function("require", "module", "exports", compiled)(name => {
    if (name.endsWith(".module.css")) return { __esModule: true, default: new Proxy({}, { get: (_, key) => String(key) }) };
    if (name === "next/dynamic") return { __esModule: true, default: () => () => React.createElement("span", null, "Lazy scene placeholder") };
    if (name.startsWith(".")) { const base = resolve(dirname(file), name); return component([base, `${base}.tsx`, `${base}.ts`].find(existsSync)); }
    assert.notEqual(name, "three", "closed server render must not load Three.js");
    return require(name);
  }, mod, mod.exports); return mod.exports;
}
test("closed-by-default server output exposes a labelled user-intent action and loads no graphics or recording data", () => {
  const { TankSimulator } = component("app/components/tank-simulator.tsx");
  let requests = 0;
  const html = renderToStaticMarkup(React.createElement(TankSimulator, { comparisonId: expected.comparisonId, evaluationHash: E, current: true, request: () => { requests++; throw new Error("must remain lazy"); }, operatorConnected: false, onRequireOperator() {}, measured: false }));
  assert.match(html, /Your tank, explained in 3D/); assert.match(html, /aria-expanded="false"/); assert.match(html, /Open 3D tank/);
  assert.doesNotMatch(html, /<canvas|Lazy scene placeholder|Not captured|measured_depth/); assert.equal(requests, 0);
});
test("parent STOP/recompute freshness archives an already-open scene even when the evaluation hash is unchanged", () => {
  const { TestReadyTankSimulator } = component("app/components/tank-simulator.tsx"), f = fixture(), before = JSON.stringify(f);
  assert.equal(tankSceneIsCurrent(true, true), true); assert.equal(tankSceneIsCurrent(false, true), false); assert.equal(tankSceneIsCurrent(true, false), false);
  const initial = renderToStaticMarkup(React.createElement(TestReadyTankSimulator, { report: f, current: tankSceneIsCurrent(true, f.is_current) }));
  const archived = renderToStaticMarkup(React.createElement(TestReadyTankSimulator, { report: f, current: tankSceneIsCurrent(false, f.is_current) }));
  assert.doesNotMatch(initial, /Archived comparison/); assert.match(archived, /Archived comparison/);
  assert.equal(JSON.stringify(f), before); assert.equal(f.evaluation_snapshot_hash, E);
});
