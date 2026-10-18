import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as preview from "../app/components/hosted-camera-state.ts";

const { HostedCameraController, INITIAL_HOSTED_CAMERA_STATE, LOCAL_CAMERA_COMPANION, cameraPermissionMessage } = preview;

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function track(id, { kind = "video", label = `Webcam ${id}`, width = 1280, height = 720 } = {}) {
  const listeners = new Set();
  return {
    id, kind, label, readyState: "live", stopped: 0,
    getSettings() { return { deviceId: id, width, height }; },
    stop() { this.stopped++; this.readyState = "ended"; },
    addEventListener(event, callback) { assert.equal(event, "ended"); listeners.add(callback); },
    removeEventListener(event, callback) { assert.equal(event, "ended"); listeners.delete(callback); },
    disconnect() { this.readyState = "ended"; for (const listener of [...listeners]) listener(); },
    listenerCount() { return listeners.size; },
  };
}

function stream(...tracks) {
  return {
    getTracks: () => tracks,
    getVideoTracks: () => tracks.filter(item => item.kind === "video"),
    getAudioTracks: () => tracks.filter(item => item.kind === "audio"),
  };
}

function harness({ enumerate } = {}) {
  const requests = [], events = [];
  let enumerations = 0, resolutions = 0;
  const media = {
    getUserMedia(constraints) {
      const pending = deferred(); requests.push({ constraints, ...pending }); events.push("request");
      return pending.promise;
    },
    async enumerateDevices() {
      enumerations++;
      return enumerate ? enumerate() : [
        { kind: "audioinput", deviceId: "microphone", label: "Do not request this" },
        { kind: "videoinput", deviceId: "built-in", label: "Built-in camera" },
        { kind: "videoinput", deviceId: "usb", label: "External USB Video" },
        { kind: "videoinput", deviceId: "usb", label: "Duplicate" },
        { kind: "videoinput", deviceId: "", label: "No usable identity" },
      ];
    },
  };
  const controller = new HostedCameraController(() => { resolutions++; return media; });
  return { controller, requests, events, get enumerations() { return enumerations; }, get resolutions() { return resolutions; } };
}

test("construction and subscription do not ask permission; one explicit start requests video without audio", async () => {
  const h = harness(), observed = [];
  const unsubscribe = h.controller.subscribe(() => observed.push(h.controller.getSnapshot()));
  assert.equal(h.resolutions, 0);
  assert.equal(h.requests.length, 0);
  assert.equal(h.controller.getSnapshot(), INITIAL_HOSTED_CAMERA_STATE);
  const task = h.controller.start();
  assert.equal(h.resolutions, 1);
  assert.equal(h.enumerations, 0, "list camera labels only after permission");
  assert.deepEqual(h.requests[0].constraints, { audio: false, video: true });
  assert.equal(h.controller.getSnapshot().status, "requesting");
  const usb = track("usb"), result = stream(usb);
  h.requests[0].resolve(result); await task;
  const state = h.controller.getSnapshot();
  assert.equal(state.status, "live"); assert.equal(state.stream, result);
  assert.equal(state.cameraLabel, "Webcam usb"); assert.equal(state.selectedDeviceId, "usb");
  assert.deepEqual(state.dimensions, { width: 1280, height: 720 });
  assert.deepEqual(state.devices, [{ id: "built-in", label: "Built-in camera" }, { id: "usb", label: "External USB Video" }]);
  assert.equal(h.enumerations, 1); assert.equal(h.requests.length, 1);
  unsubscribe(); const count = observed.length;
  h.controller.close(); assert.equal(observed.length, count, "unsubscribed views receive no updates");
  assert.equal(usb.stopped, 1); assert.equal(usb.listenerCount(), 0);
});

test("close invalidates pending permission and releases every late-returned track", async () => {
  const h = harness(), task = h.controller.start();
  h.controller.close();
  const video = track("usb"), unexpectedAudio = track("audio", { kind: "audio" });
  h.requests[0].resolve(stream(video, unexpectedAudio)); await task;
  assert.equal(h.controller.getSnapshot(), INITIAL_HOSTED_CAMERA_STATE);
  assert.equal(video.stopped, 1); assert.equal(unexpectedAudio.stopped, 1);
  assert.equal(h.enumerations, 0, "discarded permission result is never enumerated or published");
});

test("switch releases the old camera before requesting the exact new device and late requests cannot replace it", async () => {
  const h = harness(), first = track("built-in"), firstTask = h.controller.start();
  h.requests[0].resolve(stream(first)); await firstTask;
  const secondTask = h.controller.start("usb");
  assert.equal(first.stopped, 1, "old camera released synchronously before new request resolves");
  assert.equal(first.listenerCount(), 0);
  assert.deepEqual(h.requests[1].constraints, { audio: false, video: { deviceId: { exact: "usb" } } });
  assert.equal(h.controller.getSnapshot().stream, null);
  const thirdTask = h.controller.start("third"), latest = track("third");
  h.requests[2].resolve(stream(latest)); await thirdTask;
  const stale = track("usb"); h.requests[1].resolve(stream(stale)); await secondTask;
  assert.equal(stale.stopped, 1); assert.equal(latest.stopped, 0);
  assert.equal(h.controller.getSnapshot().selectedDeviceId, "third");
  assert.equal(h.controller.getSnapshot().cameraLabel, "Webcam third");
  h.controller.close(); assert.equal(latest.stopped, 1);
});

test("close then restart is safe when the first permission prompt resolves last", async () => {
  const h = harness(), oldTask = h.controller.start();
  h.controller.close();
  const newTask = h.controller.start("usb"), current = track("usb");
  h.requests[1].resolve(stream(current)); await newTask;
  const old = track("built-in"); h.requests[0].resolve(stream(old)); await oldTask;
  assert.equal(old.stopped, 1); assert.equal(current.stopped, 0);
  assert.equal(h.controller.getSnapshot().selectedDeviceId, "usb");
  h.controller.close(); h.controller.close();
  assert.equal(current.stopped, 1, "idempotent close never retains a camera");
});

test("late enumeration and late errors cannot overwrite the selected newer camera", async () => {
  const listings = [deferred(), deferred()]; let count = 0;
  const h = harness({ enumerate: () => listings[count++].promise });
  const firstTask = h.controller.start(), first = track("built-in");
  h.requests[0].resolve(stream(first)); await Promise.resolve();
  const secondTask = h.controller.start("usb"), second = track("usb");
  h.requests[1].resolve(stream(second)); await Promise.resolve();
  listings[1].resolve([{ kind: "videoinput", deviceId: "usb", label: "Chosen USB camera" }]); await secondTask;
  listings[0].reject(new Error("old enumeration failed")); await firstTask;
  assert.equal(h.controller.getSnapshot().warning, null);
  assert.deepEqual(h.controller.getSnapshot().devices, [{ id: "usb", label: "Chosen USB camera" }]);
  h.controller.playbackFailed(stream(first));
  assert.equal(h.controller.getSnapshot().status, "live", "obsolete player errors cannot close a newer stream");
  h.controller.close();
});

test("a disconnected track stops all remaining tracks, detaches handlers, and does not restart", async () => {
  const h = harness(), a = track("one"), b = track("two"), task = h.controller.start();
  h.requests[0].resolve(stream(a, b)); await task;
  a.disconnect();
  assert.equal(h.controller.getSnapshot().status, "error");
  assert.match(h.controller.getSnapshot().error, /disconnected/);
  assert.equal(h.controller.getSnapshot().stream, null);
  assert.equal(a.stopped, 1); assert.equal(b.stopped, 1);
  assert.equal(a.listenerCount(), 0); assert.equal(b.listenerCount(), 0);
  assert.equal(h.requests.length, 1);
});

test("no-video and playback errors release streams; invalid or stale dimension updates are ignored", async () => {
  const h = harness(), noVideo = track("audio", { kind: "audio" });
  const emptyTask = h.controller.start(); h.requests[0].resolve(stream(noVideo)); await emptyTask;
  assert.equal(noVideo.stopped, 1); assert.match(h.controller.getSnapshot().error, /no live video/);
  const valid = track("usb"), result = stream(valid), task = h.controller.start();
  h.requests[1].resolve(result); await task;
  h.controller.setDimensions(result, 1920, 1080);
  assert.deepEqual(h.controller.getSnapshot().dimensions, { width: 1920, height: 1080 });
  for (const pair of [[0, 500], [500, NaN], [1.5, 4]]) h.controller.setDimensions(result, ...pair);
  h.controller.setDimensions(stream(valid), 4, 4);
  assert.deepEqual(h.controller.getSnapshot().dimensions, { width: 1920, height: 1080 });
  h.controller.playbackFailed(result);
  assert.equal(valid.stopped, 1); assert.match(h.controller.getSnapshot().error, /could not play/);
});

test("the no-audio request is enforced by releasing any unexpected audio track", async () => {
  const h = harness(), video = track("usb"), audio = track("microphone", { kind: "audio" });
  const task = h.controller.start(); h.requests[0].resolve(stream(video, audio)); await task;
  assert.equal(h.requests[0].constraints.audio, false);
  assert.equal(audio.readyState, "ended"); assert.equal(video.readyState, "live");
  h.controller.close(); assert.equal(video.readyState, "ended");
});

test("camera enumeration failure keeps a granted video working and shows an honest picker warning", async () => {
  const h = harness({ enumerate: () => { throw new Error("OS-private-details"); } });
  const task = h.controller.start(), video = track("usb");
  h.requests[0].resolve(stream(video)); await task;
  assert.equal(h.controller.getSnapshot().status, "live");
  assert.match(h.controller.getSnapshot().warning, /could not list other cameras/);
  assert.doesNotMatch(h.controller.getSnapshot().warning, /OS-private-details/);
  assert.equal(video.stopped, 0); h.controller.close();
});

test("permission, busy, missing-device and unsupported-browser errors are actionable and never leak raw error details", async () => {
  const expected = { NotAllowedError: /site settings/, NotReadableError: /other camera apps/, NotFoundError: /Connect a webcam/,
    OverconstrainedError: /selected camera is unavailable/, SecurityError: /HTTPS or localhost/, CameraUnavailableError: /HTTPS or localhost/, AbortError: /interrupted/ };
  for (const [name, pattern] of Object.entries(expected)) {
    const h = harness(), task = h.controller.start();
    h.requests[0].reject({ name, message: "sensitive native OS/device string" }); await task;
    assert.equal(h.controller.getSnapshot().status, "error");
    assert.match(h.controller.getSnapshot().error, pattern);
    assert.doesNotMatch(h.controller.getSnapshot().error, /sensitive native/);
    assert.equal(h.requests.length, 1, "no hidden retry");
  }
  assert.match(cameraPermissionMessage(null), /could not start/);
  const blocked = new HostedCameraController(() => { throw { name: "CameraUnavailableError" }; });
  await blocked.start(); assert.match(blocked.getSnapshot().error, /HTTPS or localhost/);
});

function componentExports(react = React) {
  const require = createRequire(import.meta.url);
  const source = readFileSync(new URL("../app/components/hosted-camera-preview.tsx", import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX,
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
  const mod = { exports: {} };
  new Function("require", "module", "exports", compiled)(name => {
    if (name === "react") return react;
    if (name === "./hosted-camera-state.ts") return preview;
    if (name.endsWith(".module.css")) return { __esModule: true, default: new Proxy({}, { get: (_, key) => String(key) }) };
    return require(name);
  }, mod, mod.exports);
  return mod.exports;
}

function descendants(element) {
  return !React.isValidElement(element) ? [] : [element, ...React.Children.toArray(element.props.children).flatMap(descendants)];
}

function mountedView(controller, active = true) {
  const effects = [], video = { srcObject: null, played: 0, paused: 0,
    play() { this.played++; return Promise.resolve(); }, pause() { this.paused++; } };
  // Exercise the actual component's binding and effect cleanup around the real,
  // independently tested controller; only React's DOM/lifecycle host is mocked.
  const { HostedCameraPreview } = componentExports({ ...React,
    useState: () => [controller, () => {}], useSyncExternalStore: (_subscribe, snapshot) => snapshot(),
    useRef: () => ({ current: video }), useId: () => "preview-test", useEffect: effect => effects.push(effect),
  });
  const tree = HostedCameraPreview({ active });
  const cleanup = effects.map(effect => effect());
  return { tree, video, cleanup: () => { for (const dispose of cleanup) dispose?.(); } };
}

test("component close and handoff release tracks before following the link; cleanup detaches video", async () => {
  const h = harness(), task = h.controller.start(), usb = track("usb"), result = stream(usb);
  h.requests[0].resolve(result); await task;
  const view = mountedView(h.controller);
  assert.equal(view.video.srcObject, result); assert.equal(view.video.played, 1);
  const link = descendants(view.tree).find(element => element.type === "a");
  assert.equal(link.props.href, LOCAL_CAMERA_COMPANION);
  link.props.onClick();
  assert.equal(usb.stopped, 1, "stop completes synchronously in the click handler, before browser navigation");
  assert.equal(h.controller.getSnapshot().stream, null);
  view.cleanup();
  assert.equal(view.video.srcObject, null); assert.equal(view.video.paused, 1);

  const next = h.controller.start(), again = track("usb"); h.requests[1].resolve(stream(again)); await next;
  const second = mountedView(h.controller);
  const closeButton = descendants(second.tree).find(element => element.type === "button" && element.props.children === "Close preview");
  closeButton.props.onClick(); assert.equal(again.stopped, 1); second.cleanup();
});

test("a hidden preview has no video and its active-change cleanup invalidates pending permission", async () => {
  const h = harness(), task = h.controller.start();
  const hidden = mountedView(h.controller, false);
  assert.equal(hidden.tree, null); assert.equal(hidden.video.played, 0);
  const late = track("usb"); h.requests[0].resolve(stream(late)); await task;
  assert.equal(late.stopped, 1); assert.equal(h.controller.getSnapshot().stream, null);
  hidden.cleanup();
  const retry = h.controller.start(), newTrack = track("usb"); h.requests[1].resolve(stream(newTrack)); await retry;
  const visible = mountedView(h.controller, true); visible.cleanup();
  assert.equal(newTrack.stopped, 1, "unmount releases current camera without a new capture request");
  assert.equal(visible.video.srcObject, null); assert.equal(h.requests.length, 2);
});

test("server rendering is permission-free, privacy-labelled and contains only a fixed safe local handoff link", () => {
  const { HostedCameraPreview } = componentExports();
  const html = renderToStaticMarkup(React.createElement(HostedCameraPreview));
  assert.match(html, /Preview only · frames stay on this device/);
  assert.match(html, /Start preview/); assert.match(html, /does not upload or record/);
  assert.match(html, /does not upload or record frames, detect a token, calibrate distances, or create a tank trial/);
  assert.match(html, /href="http:\/\/127\.0\.0\.1:3000\/workspace#camera" target="_blank" rel="noopener noreferrer"/);
  assert.equal(LOCAL_CAMERA_COMPANION, "http://127.0.0.1:3000/workspace#camera");
  assert.doesNotMatch(html, /<video|<img|api\/v1|token=|Logitech|C920|C270|mirror\(-1/);
  assert.equal(renderToStaticMarkup(React.createElement(HostedCameraPreview, { active: false })), "");
});

test("the browser-only boundary contains no frame transport, recording, provider or persistence path", () => {
  for (const file of ["hosted-camera-preview.tsx", "hosted-camera-state.ts"]) {
    const text = readFileSync(new URL(`../app/components/${file}`, import.meta.url), "utf8");
    assert.doesNotMatch(text, /\bfetch\s*\(|XMLHttpRequest|sendBeacon|WebSocket|MediaRecorder|toDataURL|toBlob|drawImage|localStorage|sessionStorage|api\/v1/);
  }
  const css = readFileSync(new URL("../app/components/hosted-camera-preview.module.css", import.meta.url), "utf8");
  assert.match(css, /\.view video\s*\{[^}]*width:100%;[^}]*height:auto;[^}]*object-fit:contain;[^}]*transform:none;/);
  assert.doesNotMatch(css, /object-fit:cover|scaleX\(-1\)|max-width:640/);
});
