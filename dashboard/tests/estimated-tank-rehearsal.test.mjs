import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as rehearsal from "../app/components/estimated-tank-rehearsal-state.ts";

const { estimatedTrayMapping, buildEstimatedRehearsalRequest, parseEstimatedRehearsal, rehearsalSegments } = rehearsal;
const original = { id: "cal-aaaaaaaaaaaaaaaa", calibration_id: "cal-aaaaaaaaaaaaaaaa", camera_session_id: "usb-old", homography_image_to_cm: [[0.1,0,0],[0,0.1,0],[0,0,1]], mean_error_cm: 0.2, max_error_cm: 0.3, max_allowed_error_cm: 3, approved: true, validation_count: 3, image_size_px: [1280,720], plane: "measured_water_surface", units: "cm" };
const raw = JSON.stringify(original).replace("[0,0,1]", "[0.0,0.0,1.0]");
const source = { schema_version: "nemo_saved_calibration_v1", calibration: original, calibration_json: raw };
const camera = { running: true, fresh: true, session_id: "usb-current", width: 1280, height: 720, backend: "AVFOUNDATION", device_index: 0 };
const reference = { reference_id: "ref-current", camera_session_id: camera.session_id, image_size_px: [1280,720], token_area_px: 3000, token_area_px_range: [1000,9000] };
function observed(index, changes = {}) { return { observed: true, t_s: (index+1)/10, frame_id: `rehearsal-frame-${index}`, pixel_x: 100+index*10, pixel_y: 100, estimated_x_cm: 10+index, estimated_y_cm: 10, track_id: "track-one", association_break: index === 0, reason: null, area_px: 3000, bbox_px: [95+index*10,95,10,10], quality: 1, ...changes }; }
function fixture(changes = {}) {
  const points = [observed(0), observed(1), { observed: false, t_s: 0.3, frame_id: "rehearsal-frame-2", reason: "NO_DETECTION" }, observed(3, { track_id: "track-two", association_break: true })];
  return { id: "rehearsal-aabbccdd", schema_version: "nemo_estimated_rehearsal_v1", camera_session_id: camera.session_id, image_size_px: [1280,720], data_origin: "LOCAL_CAPTURE_ESTIMATED_COORDINATES", validation_status: "UNVALIDATED", validation_warning: "Current alignment is unvalidated.", warnings: ["Current alignment is unvalidated."], calibration_id: null, profile_id: null, case_id: null, source_calibration_id: original.calibration_id, source_content_sha256: "a".repeat(64), source_camera_session_id: original.camera_session_id, historical_max_error_cm: original.max_error_cm, historical_tolerance_cm: original.max_allowed_error_cm, current_alignment_verified: false, approved_for_inference: false, capture_backend: "AVFOUNDATION", timestamp_kind: "host_receipt_not_exposure", duration_s: 5, recorded_at: 1792296000, detection: { detector: "foreground_reference_v1", reference_id: reference.reference_id, token_area_px_range: [1000,9000] }, points, evidence_frame_ids: points.map(p => p.frame_id), frames: points.length, observed: 3, ...changes };
}

test("estimated grid reuses H without approving or relabelling historical calibration", () => {
  const mapping = estimatedTrayMapping(source, camera);
  assert.equal(mapping.approved, false); assert.equal(mapping.estimated, true); assert.equal(mapping.plane, "estimated_water_surface");
  assert.equal(mapping.camera_session_id, camera.session_id); assert.deepEqual(mapping.image_size_px, [1280,720]);
  assert.deepEqual(mapping.homography_image_to_cm, original.homography_image_to_cm);
  assert.equal(mapping.mapping_polygon_px.length, 4); assert.equal(source.calibration.camera_session_id, "usb-old");
  assert.equal(source.calibration_json, raw); assert.equal(Object.hasOwn(mapping, "calibration_id"), false);
  const corners = mapping.mapping_polygon_px.map(([x,y]) => [x*0.1,y*0.1]);
  assert.ok(corners.some(([x,y]) => Math.abs(x-35.56)<1e-9 && Math.abs(y-22.86)<1e-9));
});

test("fresh matching frames and visible estimated tray are required", () => {
  for (const next of [null, { ...camera, fresh: false }, { ...camera, running: false }, { ...camera, session_id: null }]) assert.throws(() => estimatedTrayMapping(source, next), /local camera/);
  assert.throws(() => estimatedTrayMapping(null, camera), /Load the saved mapping/);
  assert.throws(() => estimatedTrayMapping(source, { ...camera, width: 640 }), /resolution/);
  const shifted = { ...original, homography_image_to_cm: [[0.1,0,100],[0,0.1,0],[0,0,1]] };
  assert.throws(() => estimatedTrayMapping({ ...source, calibration: shifted, calibration_json: JSON.stringify(shifted) }, camera), /outside/);
});

test("rehearsal body is isolated, explicitly estimated, bounded and preserves original raw JSON", () => {
  const body = buildEstimatedRehearsalRequest(source, camera, reference, "5");
  assert.deepEqual(body, { source, camera_session_id: camera.session_id, image_size_px: [1280,720], duration_s: 5, detector: "foreground_reference_v1", reference_id: reference.reference_id, acknowledge_estimated_mapping: true });
  assert.equal(body.source.calibration_json, raw); assert.match(body.source.calibration_json, /1\.0/);
  for (const next of [null, { ...reference, camera_session_id: "usb-other" }, { ...reference, image_size_px: [640,480] }, { ...reference, token_area_px_range: null }, { ...reference, token_area_px_range: [9000,1000] }]) assert.throws(() => buildEstimatedRehearsalRequest(source, camera, next, "5"), /Measure one token/);
  for (const duration of ["", "NaN", "0", "11"]) assert.throws(() => buildEstimatedRehearsalRequest(source, camera, reference, duration), /between 1 and 10/);
});

test("parser preserves actual pixels, gaps and approximate coordinates without accepting measured-evidence fields", () => {
  const parsed = parseEstimatedRehearsal(fixture(), source, camera);
  assert.equal(parsed.observed, 3); assert.equal(parsed.frames, 4); assert.equal(parsed.validation_status, "UNVALIDATED");
  assert.equal(parsed.calibration_id, null); assert.equal(parsed.case_id, null); assert.equal(parsed.profile_id, null);
  assert.equal(parsed.points[0].pixel_x, 100); assert.equal(parsed.points[0].estimated_x_cm, 10);
  for (const changes of [{ data_origin: "MEASURED_TANK" }, { validation_status: "VALIDATED" }, { calibration_id: original.calibration_id }, { profile_id: "live" }, { case_id: "case-live" }, { current_alignment_verified: true }, { approved_for_inference: true }, { camera_session_id: "usb-other" }, { source_calibration_id: "cal-bbbbbbbbbbbbbbbb" }, { frames: 5 }, { observed: 4 }, { timestamp_kind: "exposure" }]) assert.throws(() => parseEstimatedRehearsal(fixture(changes), source, camera));
  const measured = fixture(); measured.points[0].x_cm = 10;
  assert.throws(() => parseEstimatedRehearsal(measured, source, camera), /unsupported fields/);
  const invented = fixture(); invented.points[0].estimated_x_cm = 99;
  assert.throws(() => parseEstimatedRehearsal(invented, source, camera), /unchanged saved mapping/);
  const bridged = fixture(); bridged.points[2].estimated_x_cm = 10;
  assert.throws(() => parseEstimatedRehearsal(bridged, source, camera), /unsupported fields/);
  const badTime = fixture(); badTime.points[1].t_s = 0.1;
  assert.throws(() => parseEstimatedRehearsal(badTime, source, camera), /timing/);
});

test("trajectory segments never bridge gaps, association breaks or changed identities", () => {
  const points = [observed(0), observed(1), { observed: false, t_s: 0.3, frame_id: "gap", reason: "VIEW_OBSTRUCTED" }, observed(3), observed(4, { association_break: true }), observed(5, { track_id: "track-other" })];
  assert.deepEqual(rehearsalSegments(points).map(group => group.map(p => p.frame_id)), [["rehearsal-frame-0","rehearsal-frame-1"], ["rehearsal-frame-3"], ["rehearsal-frame-4"], ["rehearsal-frame-5"]]);
});

function componentExports(react = React) {
  const require = createRequire(import.meta.url), mod = { exports: {} };
  const compiled = ts.transpileModule(readFileSync(new URL("../app/components/estimated-tank-rehearsal.tsx", import.meta.url), "utf8"), { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
  new Function("require", "module", "exports", compiled)(name => { if (name === "react") return react; if (name === "./estimated-tank-rehearsal-state.ts") return rehearsal; if (name.endsWith(".module.css")) return { __esModule: true, default: new Proxy({}, { get: (_,key) => String(key) }) }; return require(name); }, mod, mod.exports);
  return mod.exports;
}
function descendants(element) { return !React.isValidElement(element) ? [] : [element, ...React.Children.toArray(element.props.children).flatMap(descendants)]; }
const settle = () => new Promise(resolve => setTimeout(resolve, 0));
function deferred() { let resolve; const promise = new Promise(yes => { resolve = yes; }); return { promise, resolve }; }
function harness(request = async () => fixture()) {
  const hooks = [], effects = [], mappings = [], busy = []; let cursor = 0, tree;
  let props = { request, source, camera, reference, disabled: false, onEstimatedMapping: value => mappings.push(value), onBusyChange: value => busy.push(value) };
  const mock = { ...React, useId: () => "rehearsal-test",
    useState(initial) { const i = cursor++; if (!hooks[i]) hooks[i] = { value: initial }; return [hooks[i].value, value => { hooks[i].value = typeof value === "function" ? value(hooks[i].value) : value; }]; },
    useRef(initial) { const i = cursor++; if (!hooks[i]) hooks[i] = { current: initial }; return hooks[i]; },
    useMemo(calculate, deps) { const i = cursor++; if (!hooks[i] || deps.some((dep,j) => !Object.is(dep,hooks[i].deps[j]))) hooks[i] = { value: calculate(), deps }; return hooks[i].value; },
    useEffect(effect, deps) { const i = cursor++; if (!hooks[i] || deps.some((dep,j) => !Object.is(dep,hooks[i].deps[j]))) { const old = hooks[i]; hooks[i] = { deps }; effects.push(() => { old?.cleanup?.(); hooks[i].cleanup = effect(); }); } },
  };
  const { EstimatedTankRehearsal } = componentExports(mock);
  const render = changes => { props = { ...props, ...changes }; cursor = 0; tree = EstimatedTankRehearsal(props); while (effects.length) effects.shift()(); return tree; };
  const button = label => descendants(tree).find(item => item.type === "button" && item.props.children === label);
  render(); return { render, button, mappings, busy, tree: () => tree, unmount: () => { for (const hook of hooks) hook.cleanup?.(); } };
}

test("initial render never captures or applies a grid automatically", () => {
  let calls = 0; const { EstimatedTankRehearsal } = componentExports();
  const html = renderToStaticMarkup(React.createElement(EstimatedTankRehearsal, { request: () => { calls++; }, source, camera, reference, disabled: false, onEstimatedMapping: () => { calls++; } }));
  assert.equal(calls, 0); assert.match(html, /Estimated tank rehearsal/); assert.match(html, /Unvalidated/); assert.match(html, /Frames stay on this Mac/);
  assert.doesNotMatch(html, /<video|<img|validated source identified/);
});

test("explicit grid and rehearsal actions stay separate from measured commissioning", async () => {
  const calls = [], h = harness(async (path, body) => { calls.push({ path, body }); return fixture(); }); await settle();
  assert.equal(h.mappings.length, 0); h.button("Use estimated grid").props.onClick();
  assert.equal(h.mappings.length, 1); assert.equal(h.mappings[0].approved, false); assert.equal(calls.length, 0);
  await h.button("Record estimated rehearsal").props.onClick(); h.render();
  assert.equal(calls.length, 1); assert.equal(calls[0].path, "/camera/rehearsals"); assert.equal(calls[0].body.source.calibration_json, raw);
  assert.equal(h.mappings.length, 1, "capturing does not approve or replace the displayed mapping");
  const html = renderToStaticMarkup(h.tree()); assert.match(html, /Recorded rehearsal · unvalidated/); assert.match(html, /3 accepted detections/); assert.match(html, /cannot train measured flow/);
  h.unmount();
});

test("camera, reference and disabled changes discard delayed capture results", async () => {
  for (const changes of [{ camera: { ...camera, session_id: "usb-other" } }, { reference: { ...reference, reference_id: "ref-other" } }, { disabled: true }]) {
    const pending = deferred(), options = [], h = harness(async (_path,_body,opts) => { options.push(opts); return pending.promise; }); await settle();
    const task = h.button("Record estimated rehearsal").props.onClick(); h.render(changes); assert.equal(options[0].signal.aborted, true);
    pending.resolve(fixture()); await task; await settle(); h.render(); assert.doesNotMatch(renderToStaticMarkup(h.tree()), /Recorded rehearsal · unvalidated/); h.unmount();
  }
});

test("zero detections remain a missing trajectory, never a simulated success", async () => {
  const point = { observed: false, t_s: 0.1, frame_id: "only-gap", reason: "NO_DETECTION" };
  const h = harness(async () => fixture({ points: [point], frames: 1, observed: 0, evidence_frame_ids: [point.frame_id] })); await settle();
  await h.button("Record estimated rehearsal").props.onClick(); h.render();
  assert.match(renderToStaticMarkup(h.tree()), /No cap position was accepted. This capture contains no trajectory/); h.unmount();
});

test("plot shows actual captured scatter, joins only accepted tracks, and labels estimates", () => {
  const { RehearsalPlot } = componentExports(); const html = renderToStaticMarkup(React.createElement(RehearsalPlot, { result: parseEstimatedRehearsal(fixture(), source, camera) }));
  assert.equal((html.match(/<circle/g) || []).length, 3); assert.equal((html.match(/<polyline/g) || []).length, 1);
  assert.match(html, /Actual captured cap positions/); assert.match(html, /unknown current accuracy/); assert.match(html, /pixel 100.0, 100.0/);
  assert.doesNotMatch(html, /forecast|probability|confidence|100%/);
});


test("declared tray bounds remain bounded estimates rather than new measured marks", () => {
  const smaller = { x_min_cm: 1, x_max_cm: 20, y_min_cm: 2, y_max_cm: 15 };
  const mapping = estimatedTrayMapping(source, camera, smaller);
  assert.equal(mapping.approved, false); assert.deepEqual(mapping.homography_image_to_cm, original.homography_image_to_cm);
  assert.ok(mapping.mapping_polygon_px.every(([x,y]) => x>=10-1e-9 && x<=200+1e-9 && y>=20-1e-9 && y<=150+1e-9));
  for (const bounds of [{ ...smaller, x_max_cm: 1 }, { ...smaller, y_min_cm: NaN }, { ...smaller, y_max_cm: 500 }]) assert.throws(() => estimatedTrayMapping(source, camera, bounds), /finite, ordered tabletop/);
});

test("unmount releases pending request and clears only an explicitly shown estimated grid", async () => {
  const pending = deferred(), options = [], h = harness(async (_path,_body,opts) => { options.push(opts); return pending.promise; }); await settle();
  assert.equal(h.mappings.length, 0); h.button("Use estimated grid").props.onClick();
  const task = h.button("Record estimated rehearsal").props.onClick(); h.unmount();
  assert.equal(options[0].signal.aborted, true); assert.equal(h.mappings.at(-1), null);
  pending.resolve(fixture()); await task; assert.equal(h.busy.at(-1), false);
});
