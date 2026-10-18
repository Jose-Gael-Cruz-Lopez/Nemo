import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as saved from "../app/components/saved-calibration-state.ts";

const { SAVED_CALIBRATION_SCHEMA, MAX_SAVED_CALIBRATION_BYTES, parseSavedCalibrationBundle,
  parseSavedCalibrationText, serializeSavedCalibration, parseSavedCalibrationList,
  buildSavedCalibrationCheck, acceptSavedCalibrationResult } = saved;
const original = {
  id: "cal-aaaaaaaaaaaaaaaa", calibration_id: "cal-aaaaaaaaaaaaaaaa", camera_session_id: "usb-old",
  homography_image_to_cm: [[0.1, 0, 0], [0, 0.1, 0], [0, 0, 1]],
  mean_error_cm: 0.2, max_error_cm: 0.3, max_allowed_error_cm: 3, approved: true,
  validation_count: 3, image_size_px: [1280, 720], plane: "measured_water_surface", units: "cm",
};
const bundleFor = calibration => ({ schema_version: SAVED_CALIBRATION_SCHEMA, calibration, calibration_json: JSON.stringify(calibration) });
const originalJson = JSON.stringify(original).replace("[0,0,1]", "[0.0,0.0,1.0]");
const source = () => ({ ...bundleFor(structuredClone(original)), calibration_json: originalJson });
const camera = { running: true, fresh: true, session_id: "usb-current", width: 1280, height: 720, backend: "AVFOUNDATION", device_index: 0 };
const pixelText = "10,10\n110,10\n10,110", worldText = "1,1\n11,1\n1,11";
function result(changes = {}) {
  return { ...structuredClone(original), id: "cal-bbbbbbbbbbbbbbbb", calibration_id: "cal-bbbbbbbbbbbbbbbb", camera_session_id: camera.session_id,
    reuse: { method: "fixed_homography_current_checks_v1", source_calibration_id: original.calibration_id,
      source_content_sha256: "a".repeat(64), check_pixels: [[10,10],[110,10],[10,110]], check_world_cm: [[1,1],[11,1],[1,11]], water_plane_unchanged: true }, ...changes };
}
function summary() {
  return Object.fromEntries(["calibration_id", "camera_session_id", "image_size_px", "approved", "max_error_cm", "max_allowed_error_cm", "mean_error_cm", "validation_count"].map(key => [key, original[key]]));
}

test("mapping metadata round trips without frames, credentials or silent unknown-field stripping", () => {
  const parsed = parseSavedCalibrationBundle(source());
  assert.deepEqual(parseSavedCalibrationText(serializeSavedCalibration(parsed)), parsed);
  assert.deepEqual(parsed.calibration.homography_image_to_cm, original.homography_image_to_cm);
  for (const key of ["operator_token", "api_key", "frames", "reference_npz", "mapping_polygon_px", "__proto__"]) {
    const input = JSON.parse(JSON.stringify(source()));
    Object.defineProperty(input.calibration, key, { value: "unexpected", enumerable: true });
    assert.throws(() => parseSavedCalibrationBundle(input), /unsupported fields/);
  }
  assert.throws(() => parseSavedCalibrationBundle({ ...source(), note: "unsupported" }), /unsupported fields/);
  assert.throws(() => parseSavedCalibrationBundle({ ...source(), schema_version: "old" }), /supported/);
  assert.throws(() => parseSavedCalibrationBundle({ ...source(), calibration: { ...original, id: "cal-bbbbbbbbbbbbbbbb" } }), /mapping ID/);
});

test("invalid matrix, dimensions, history, units and provenance are rejected before use", () => {
  for (const changes of [
    { homography_image_to_cm: [[0,0,0],[0,0,0],[0,0,0]] },
    { homography_image_to_cm: [[1,0,0],[0,1,0],[0,0,NaN]] }, { image_size_px: [1280.5, 720] },
    { image_size_px: [1280, 0] }, { validation_count: 2 }, { mean_error_cm: 4 },
    { max_allowed_error_cm: 0 }, { max_allowed_error_cm: 6 }, { max_error_cm: -1 },
    { approved: false }, { plane: "tabletop" }, { units: "m" }, { camera_session_id: "../private" },
  ]) assert.throws(() => parseSavedCalibrationBundle(bundleFor({ ...original, ...changes })));
  const checked = result();
  assert.deepEqual(parseSavedCalibrationBundle(bundleFor(checked)).calibration.reuse, checked.reuse);
  for (const changes of [{ water_plane_unchanged: false }, { check_world_cm: [[1,1]] },
    { source_content_sha256: "not-a-hash" }, { api_key: "unexpected" }]) {
    assert.throws(() => parseSavedCalibrationBundle(bundleFor({ ...checked, reuse: { ...checked.reuse, ...changes } })));
  }
});

test("file limits count UTF-8 bytes and reject oversized files before parsing", () => {
  assert.throws(() => parseSavedCalibrationText("{}", MAX_SAVED_CALIBRATION_BYTES + 1), /64 KB/);
  assert.throws(() => parseSavedCalibrationText("🦀".repeat(17000)), /64 KB/);
  assert.throws(() => parseSavedCalibrationText("not JSON"), /valid JSON/);
  assert.throws(() => parseSavedCalibrationText(JSON.stringify(source()), -1), /64 KB/);
  assert.deepEqual(parseSavedCalibrationText(JSON.stringify(source()), 100), source());
});

test("local list accepts only bounded summary records, with no implied current-session approval", () => {
  assert.deepEqual(parseSavedCalibrationList({ calibrations: [summary()] }), [summary()]);
  assert.deepEqual(parseSavedCalibrationList({ calibrations: [] }), []);
  assert.throws(() => parseSavedCalibrationList({ calibrations: [summary(), summary()] }), /repeated/);
  assert.throws(() => parseSavedCalibrationList({ calibrations: Array(501).fill(summary()) }), /invalid/);
  assert.throws(() => parseSavedCalibrationList({ calibrations: [{ ...summary(), api_key: "unexpected" }] }), /unsupported/);
});

test("alignment check carries the original H and tolerance plus measured checks; no refit or inferred survey", () => {
  const body = buildSavedCalibrationCheck(source(), camera, pixelText, worldText, true);
  assert.deepEqual(body, { source: source(), camera_session_id: camera.session_id, image_size_px: [1280,720],
    check_pixels: [[10,10],[110,10],[10,110]], check_world_cm: [[1,1],[11,1],[1,11]], water_plane_unchanged: true });
  assert.equal(body.source.calibration.max_allowed_error_cm, 3);
  assert.equal(body.source.calibration.camera_session_id, "usb-old", "historical session ID is never relabelled");
  assert.notEqual(body.source.calibration.camera_session_id, body.camera_session_id);
  assert.throws(() => buildSavedCalibrationCheck(source(), camera, pixelText, worldText, false), /Confirm/);
  for (const next of [null, { ...camera, fresh: false }, { ...camera, running: false }, { ...camera, session_id: null }, { ...camera, width: null }]) {
    assert.throws(() => buildSavedCalibrationCheck(source(), next, pixelText, worldText, true), /fresh camera session/);
  }
  assert.throws(() => buildSavedCalibrationCheck(source(), { ...camera, width: 640 }, pixelText, worldText, true), /1280 × 720/);
  assert.throws(() => buildSavedCalibrationCheck(source(), camera, "-1,0\n110,10\n10,110", worldText, true), /inside/);
  assert.throws(() => buildSavedCalibrationCheck(source(), camera, "10,10\n110,10\n1280,110", worldText, true), /inside/);
  assert.throws(() => buildSavedCalibrationCheck(source(), camera, "0,0\n1,1\n2,2", worldText, true), /single line/);
  assert.throws(() => buildSavedCalibrationCheck(source(), camera, pixelText, "0,0\n1,1\n2,2", true), /single line/);
  assert.throws(() => buildSavedCalibrationCheck(source(), camera, pixelText, "1,1\n11,1", true), /matching/);
  assert.throws(() => buildSavedCalibrationCheck(source(), camera, pixelText, "0,0\n201,0\n0,201", true), /200 cm/);
});

test("only a newly approved matching-session result with unchanged H/tolerance may be applied", () => {
  assert.equal(acceptSavedCalibrationResult(result(), source(), camera).calibration_id, "cal-bbbbbbbbbbbbbbbb");
  assert.throws(() => acceptSavedCalibrationResult(original, source(), camera), /source mapping/);
  assert.throws(() => acceptSavedCalibrationResult(result({ approved: false, max_error_cm: 4 }), source(), camera), /Alignment check failed/);
  assert.throws(() => acceptSavedCalibrationResult(result({ camera_session_id: "usb-other" }), source(), camera), /session changed/);
  assert.throws(() => acceptSavedCalibrationResult(result(), source(), { ...camera, fresh: false }), /session changed/);
  assert.throws(() => acceptSavedCalibrationResult(result({ image_size_px: [640,480] }), source(), camera), /session changed/);
  assert.throws(() => acceptSavedCalibrationResult(result({ max_allowed_error_cm: 4 }), source(), camera), /matrix or tolerance/);
  assert.throws(() => acceptSavedCalibrationResult(result({ homography_image_to_cm: [[0.2,0,0],[0,0.1,0],[0,0,1]] }), source(), camera), /matrix or tolerance/);
  assert.throws(() => acceptSavedCalibrationResult(result({ reuse: { ...result().reuse, source_calibration_id: "cal-cccccccccccccccc" } }), source(), camera), /source mapping/);
});

function componentExports(react = React) {
  const require = createRequire(import.meta.url);
  const compiled = ts.transpileModule(readFileSync(new URL("../app/components/saved-calibration.tsx", import.meta.url), "utf8"), {
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
  }).outputText;
  const mod = { exports: {} };
  new Function("require", "module", "exports", compiled)(name => {
    if (name === "react") return react;
    if (name === "./saved-calibration-state.ts") return saved;
    if (name.endsWith(".module.css")) return { __esModule: true, default: new Proxy({}, { get: (_, key) => String(key) }) };
    return require(name);
  }, mod, mod.exports);
  return mod.exports;
}
function descendants(element) { return !React.isValidElement(element) ? [] : [element, ...React.Children.toArray(element.props.children).flatMap(descendants)]; }
function textOf(element) { return (typeof element === "string" || typeof element === "number") ? String(element) : React.isValidElement(element) ? React.Children.toArray(element.props.children).map(textOf).join("") : ""; }
const settle = () => new Promise(resolve => setTimeout(resolve, 0));
function deferred() { let resolve; const promise = new Promise(yes => { resolve = yes; }); return { promise, resolve }; }
function harness({ request = async () => { throw new Error("unexpected network call"); }, controlled = false } = {}) {
  const hooks = [], effects = [], applied = [], invalidated = [], busy = []; let cursor = 0, tree;
  let props = { request, camera, disabled: false, onApply: value => applied.push(value), onCheckStart: () => invalidated.push(true), onBusyChange: value => busy.push(value) };
  const mock = { ...React,
    useId: () => "saved-test",
    useState(initial) { const i = cursor++; if (!hooks[i]) hooks[i] = { value: typeof initial === "function" ? initial() : initial }; return [hooks[i].value, value => { hooks[i].value = typeof value === "function" ? value(hooks[i].value) : value; }]; },
    useRef(initial) { const i = cursor++; if (!hooks[i]) hooks[i] = { current: initial }; return hooks[i]; },
    useCallback(callback, deps) { const i = cursor++; if (!hooks[i] || deps.some((dep,j) => !Object.is(dep, hooks[i].deps[j]))) hooks[i] = { value: callback, deps }; return hooks[i].value; },
    useEffect(effect, deps) { const i = cursor++; if (!hooks[i] || !deps || deps.some((dep,j) => !Object.is(dep, hooks[i].deps?.[j]))) { const old = hooks[i]; hooks[i] = { deps }; effects.push(() => { old?.cleanup?.(); hooks[i].cleanup = effect(); }); } },
  };
  const { SavedCalibration } = componentExports(mock);
  const render = changes => { props = { ...props, ...changes }; cursor = 0; tree = SavedCalibration(props); while (effects.length) effects.shift()(); return tree; };
  if (controlled) props = { ...props, checkPixels: "", onCheckPixelsChange: value => { props.checkPixels = value; } };
  const elements = () => descendants(tree);
  const button = label => elements().find(item => item.type === "button" && textOf(item) === label);
  const upload = file => elements().find(item => item.type === "input" && item.props.type === "file").props.onChange({ target: { files: [file], value: "" } });
  const load = async () => { upload({ size: 1000, text: async () => JSON.stringify(source()) }); await settle(); render(); };
  const checks = () => {
    const fields = elements().filter(item => item.type === "textarea"); fields[0].props.onChange({ target: { value: pixelText } }); fields[1].props.onChange({ target: { value: worldText } });
    elements().find(item => item.type === "input" && item.props.type === "checkbox").props.onChange({ target: { checked: true } }); render();
  };
  render();
  return { render, elements, button, upload, load, checks, applied, invalidated, busy, unmount: () => { for (const hook of hooks) hook.cleanup?.(); } };
}

test("initial render is compact and permission-free, with explicit local metadata actions", () => {
  const { SavedCalibration } = componentExports(); let calls = 0;
  const html = renderToStaticMarkup(React.createElement(SavedCalibration, { request: () => { calls++; }, camera: null, disabled: false, onApply: () => {} }));
  assert.equal(calls, 0); assert.match(html, /Reuse saved measurements/); assert.match(html, /35.56 × 22.86 cm/);
  assert.match(html, /Frames, reference images, and tokens are not included/); assert.doesNotMatch(html, /<img|<video|<textarea/);
});

test("opening a JSON file does not upload it or approve a mapping; busy disables file selection", async () => {
  let calls = 0; const h = harness({ request: async () => { calls++; } }); await settle();
  const pending = deferred(); h.upload({ size: 1000, text: () => pending.promise }); h.render();
  assert.equal(h.elements().find(item => item.type === "input" && item.props.type === "file").props.disabled, true);
  pending.resolve(JSON.stringify(source())); await settle(); h.render();
  assert.equal(calls, 0); assert.equal(h.applied.length, 0); assert.equal(h.invalidated.length, 0);
  assert.match(textOf(h.render()), /Historical errors/); assert.match(textOf(h.render()), /3.00 cm · locked/);
  assert.deepEqual(h.busy, [true, false]); h.unmount();
});

test("oversized files are rejected before reading their contents", async () => {
  const h = harness(); await settle(); let read = false;
  h.upload({ size: MAX_SAVED_CALIBRATION_BYTES + 1, text: async () => { read = true; return "{}"; } });
  await settle(); h.render(); assert.equal(read, false); assert.match(textOf(h.render()), /64 KB/); h.unmount();
});

test("current alignment explicitly calls the local endpoint and applies one server-approved result", async () => {
  const requests = [], h = harness({ controlled: true, request: async (path, body) => { requests.push({ path, body }); return result(); } });
  await settle(); await h.load(); h.checks(); h.button("Check alignment, then use mapping").props.onClick(); await settle(); h.render();
  assert.equal(requests.length, 1); assert.equal(requests[0].path, "/vision/calibrations/revalidate");
  assert.deepEqual(requests[0].body.check_world_cm, [[1,1],[11,1],[1,11]]); assert.equal(h.applied.length, 1);
  assert.match(requests[0].body.source.calibration_json, /1\.0/);
  assert.equal(requests[0].body.source.calibration_json, originalJson, "the browser POST preserves legacy Python float spelling byte-for-byte");
  assert.match(textOf(h.render()), /Current alignment passed/); h.unmount();
});

test("camera changes or unmount discard delayed successful alignment responses", async () => {
  for (const action of ["camera", "unmount"]) {
    const pending = deferred(), requests = [], h = harness({ request: async (_path, _body, options) => { requests.push(options); return pending.promise; } });
    await settle(); await h.load(); h.checks(); h.button("Check alignment, then use mapping").props.onClick();
    if (action === "camera") h.render({ camera: { ...camera, session_id: "usb-new" } }); else h.unmount();
    assert.equal(requests[0].signal.aborted, true); pending.resolve(result()); await settle();
    assert.equal(h.applied.length, 0, "stale response must never revive historical approval");
    if (action === "camera") h.unmount();
  }
});

test("failed alignment never applies and the saved tolerance cannot be edited", async () => {
  const h = harness({ request: async () => { assert.equal(h.invalidated.length, 1, "invalidation precedes the check request"); return result({ approved: false, max_error_cm: 4 }); } });
  await settle(); await h.load(); h.checks(); h.button("Check alignment, then use mapping").props.onClick(); await settle(); h.render();
  assert.equal(h.applied.length, 0); assert.equal(h.invalidated.length, 1); assert.match(textOf(h.render()), /Alignment check failed/);
  assert.equal(h.elements().some(item => item.type === "input" && item.props.type === "number"), false); h.unmount();
});

test("local mappings are listed and selected explicitly; detail loading never auto-applies", async () => {
  const calls = [], h = harness({ request: async path => { calls.push(path); return path === "/vision/calibrations" ? { calibrations: [summary()] } : source(); } });
  await settle(); h.button("Find saved mappings on this Mac").props.onClick(); await settle(); h.render();
  assert.deepEqual(calls, ["/vision/calibrations"]); assert.equal(h.applied.length, 0);
  h.elements().find(item => item.type === "select").props.onChange({ target: { value: original.calibration_id } }); h.render();
  h.button("Load mapping").props.onClick(); await settle(); h.render();
  assert.deepEqual(calls, ["/vision/calibrations", `/vision/calibrations/${original.calibration_id}`]);
  assert.equal(h.applied.length, 0); assert.match(textOf(h.render()), /Historical errors/); h.unmount();
});

test("disabled state cancels pending alignment and does not apply its late success", async () => {
  const pending = deferred(), h = harness({ request: async () => pending.promise }); await settle(); await h.load(); h.checks();
  h.button("Check alignment, then use mapping").props.onClick(); h.render({ disabled: true }); pending.resolve(result()); await settle();
  assert.equal(h.applied.length, 0); h.unmount();
});


test("legacy raw JSON keeps float spelling through parse, export and request without regeneration", () => {
  assert.match(originalJson, /1\.0/);
  const value = parseSavedCalibrationBundle(source());
  assert.equal(value.calibration_json, originalJson);
  const exported = serializeSavedCalibration(value);
  assert.equal(JSON.parse(exported).calibration_json, originalJson);
  assert.equal(parseSavedCalibrationText(exported).calibration_json, originalJson);
  assert.equal(buildSavedCalibrationCheck(value, camera, pixelText, worldText, true).source.calibration_json, originalJson);
  const reordered = Object.fromEntries(Object.entries(original).reverse());
  assert.equal(parseSavedCalibrationBundle({ ...source(), calibration: reordered }).calibration_json, originalJson, "semantic comparison permits key ordering and integer/float spelling differences");
});

test("missing, oversized, malformed or mismatched original JSON is never accepted", () => {
  const missing = source(); delete missing.calibration_json;
  assert.throws(() => parseSavedCalibrationBundle(missing), /missing or unsupported/);
  for (const calibration_json of [null, "", "not json", " ".repeat(32001), JSON.stringify({ ...original, units: "m" })]) {
    assert.throws(() => parseSavedCalibrationBundle({ ...source(), calibration_json }));
  }
  assert.throws(() => parseSavedCalibrationBundle({ ...source(), calibration_json: JSON.stringify({ ...original, max_allowed_error_cm: 4 }) }), /does not match/);
  assert.throws(() => parseSavedCalibrationBundle({ ...source(), calibration_json: JSON.stringify({ ...original, api_key: "unsupported" }) }), /unsupported fields/);
});


test("malformed check inputs never invalidate or submit an existing mapping", async () => {
  let calls = 0; const h = harness({ request: async () => { calls++; return result(); } });
  await settle(); await h.load();
  h.button("Check alignment, then use mapping").props.onClick(); await settle(); h.render();
  assert.equal(calls, 0); assert.equal(h.invalidated.length, 0); assert.equal(h.applied.length, 0);
  assert.match(textOf(h.render()), /Confirm the camera/); h.unmount();
});


test("sibling capture disable/re-enable preserves observed checks and confirmation while discarding a pending response", async () => {
  const pending = deferred(), h = harness({ request: async () => pending.promise });
  await settle(); await h.load(); h.checks();
  const values = () => h.elements().filter(item => item.type === "textarea").map(item => item.props.value);
  const confirmed = () => h.elements().find(item => item.type === "input" && item.props.type === "checkbox").props.checked;
  assert.deepEqual(values(), [pixelText, worldText]); assert.equal(confirmed(), true);
  h.button("Check alignment, then use mapping").props.onClick();
  h.render({ disabled: true }); await settle(); h.render();
  assert.deepEqual(values(), [pixelText, worldText]); assert.equal(confirmed(), true);
  h.render({ disabled: false }); await settle(); h.render();
  assert.deepEqual(values(), [pixelText, worldText]); assert.equal(confirmed(), true);
  pending.resolve(result()); await settle(); h.render();
  assert.equal(h.applied.length, 0); assert.deepEqual(values(), [pixelText, worldText]); assert.equal(confirmed(), true);
  h.unmount();
});

test("a genuinely stale frame clears pixel checks and confirmation while retaining surveyed centimetres", async () => {
  const h = harness(); await settle(); await h.load(); h.checks();
  h.render({ camera: { ...camera, fresh: false } }); await settle(); h.render();
  assert.deepEqual(h.elements().filter(item => item.type === "textarea").map(item => item.props.value), ["", worldText]);
  assert.equal(h.elements().find(item => item.type === "input" && item.props.type === "checkbox").props.checked, false);
  h.unmount();
});
