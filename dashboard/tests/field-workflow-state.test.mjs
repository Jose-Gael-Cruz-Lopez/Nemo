import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { STEP_IDS, addRecording, buildCalibrationRequest, buildFieldRequest, buildFlowRequest, buildProfile, canFreeze, decodeDraft, deriveSteps, encodeDraft, failureNotice, invalidateAfter, newDraft, parseCalibration, parseCameraStatus, parseCase, parseFlow, parseManifestDetail, parsePairs, parsePreflight, parseRecording, previewPixel, requestKey } from "../app/components/field-workflow-state.ts";

// Response shapes captured from the actual API with the explicit synthetic fake capture device.
const camera = { running: true, session_id: "usb-fake-df5bdd212ae3", device_index: 1, fresh: true, age_s: 0, sequence: 51, width: 640, height: 480, backend: "SYNTHETIC_FAKE_CAPTURE" };
const calibration = { homography_image_to_cm: [[0.05, 0, 0], [0, 0.05, 0], [0, 0, 1]], mean_error_cm: 5.2e-7, max_error_cm: 7.3e-7, validation_count: 3, max_allowed_error_cm: 0.5, approved: true, image_size_px: [640, 480], camera_session_id: camera.session_id, plane: "measured_water_surface", units: "cm", calibration_id: "cal-31c8879499a19a23", id: "cal-31c8879499a19a23" };
const point = (t, x, track = "track-d8698c79fb81") => ({ pixel_x: x * 20, pixel_y: 200, area_px: 284, bbox_px: [91, 191, 19, 19], t_s: t, x_cm: x, y_cm: 10, observed: true, quality: 1, track_id: track, association_break: false, reason: null, frame_id: `frame-${t}` });
const recording = { id: "recording-84462fb687f74fd5", profile_id: null, camera_session_id: camera.session_id, points: [point(0, 5), point(0.06, 5.2), { observed: false, t_s: 0.12, reason: "NO_DETECTION" }, point(0.18, 5.5, "track-other")], calibration_id: calibration.calibration_id, recorded_at: 1792214209.7, evidence_frame_ids: ["frame-a", "frame-b", "frame-c", "frame-d"], data_origin: "MEASURED_TANK", timestamp_kind: "host_receipt_not_exposure" };
const flow = { kind: "idw", units: "cm,s", id: "flow-05f22070157540d8", data_origin: "MEASURED_TANK", nodes: [{ x_cm: 5, y_cm: 8, vx_cm_s: 3, vy_cm_s: 0, sample_count: 2, scatter_cm_s: 0.1 }], diagnostics: { sample_count: 10, node_count: 6, training_rmse_cm_s: 0.10, loo_rmse_cm_s: 0.2, loo_supported_nodes: 6, grid_coverage_fraction: 0.12, max_speed_cm_s: 3.3, validation_rmse_cm_s: 0.147, validation_coverage_fraction: 1 }, provenance: { calibration_id: calibration.calibration_id, camera_session_id: camera.session_id, training_recording_ids: ["recording-783909d3eef24910", "recording-8e6c06db52a34a49"], validation_recording_ids: [recording.id], frame_splits_disjoint: true } };
const step = (id, status = "PASSED", code = "OK") => ({ step: id, status, code, message: `${id} message`, help: status === "PASSED" ? "" : `${id} help` });
const fixture = JSON.parse(readFileSync(new URL("../../tests/fixtures/team_handoff/field_manifest_v1.json", import.meta.url), "utf8"));

function commissionedDraft() {
  return {
    ...newDraft(), cameraSessionId: camera.session_id, calibration: parseCalibration(calibration),
    trainingRecordingIds: flow.provenance.training_recording_ids, validationRecordingIds: [recording.id], flow: parseFlow(flow),
    bounds: { xMin: "0", xMax: "32", yMin: "0", yMax: "24" },
    sources: [{ id: "A", polygon: "1,3; 3,3; 3,5" }, { id: "B", polygon: "1,10\n3,10\n3,12" }, { id: "C", polygon: "" }],
    observationPolygon: "0,0; 32,0; 32,24; 0,24", pocketPolygon: "28,10; 30,10; 30,12", pocketValidated: true,
    maxValidationRmse: "1", revalidationRmse: "1",
  };
}

test("API responses parse into the wizard's view, and malformed contracts are refused", () => {
  assert.equal(parseCameraStatus(camera).session_id, camera.session_id);
  assert.equal(parseCameraStatus({ running: false, session_id: null, fresh: false, width: null, height: null, backend: null, device_index: null }).session_id, null);
  assert.deepEqual(parseCalibration(calibration).image_size_px, [640, 480]);
  const summary = parseRecording(recording);
  assert.deepEqual([summary.frames, summary.observed, summary.gaps, summary.tracks], [4, 3, 1, 2]);
  assert.equal(parseFlow(flow).id, flow.id);
  assert.equal(parseCase({ id: "case-1", mode: "LIVE", state: "OBSERVED", profile_id: "profile-1", recording_id: "recording-1", points: [] }).recording_id, "recording-1");
  for (const [parse, bad] of [[parseCalibration, { ...calibration, approved: "yes" }], [parseRecording, { ...recording, data_origin: "SYNTHETIC" }], [parseFlow, { ...flow, diagnostics: { ...flow.diagnostics, validation_rmse_cm_s: "0.1" } }], [parseCase, { id: "case-1", mode: "SYNTHETIC", state: "OBSERVED", profile_id: "p" }], [parseCameraStatus, { running: "true" }]]) {
    assert.throws(() => parse(bad), /contract/);
  }
});

test("mapping needs ≥4 correspondences, ≥3 separate checks, in-frame pixels and an explicit unit", () => {
  const draft = { ...newDraft(), cameraSessionId: camera.session_id, mappingPixels: "0,0\n639,0\n639,479\n0,479", mappingWorld: "0,0\n31.95,0\n31.95,23.95\n0,23.95", checkPixels: "100,100; 500,120; 300,400", checkWorld: "5,5; 25,6; 15,20" };
  const body = buildCalibrationRequest(draft, camera);
  assert.deepEqual(body.image_size_px, [640, 480]);
  assert.equal(body.camera_session_id, camera.session_id);
  assert.deepEqual(buildCalibrationRequest({ ...draft, unit: "mm", mappingWorld: "0,0\n319.5,0\n319.5,239.5\n0,239.5", checkWorld: "50,50; 250,60; 150,200" }, camera).world_cm_points[1], [31.95, 0]);
  assert.deepEqual(buildCalibrationRequest({ ...draft, unit: "in", mappingWorld: "0,0\n10,0\n10,8\n0,8", checkWorld: "1,1; 8,2; 5,7" }, camera).world_cm_points[1], [25.4, 0]);
  assert.throws(() => buildCalibrationRequest({ ...draft, mappingWorld: "0,0\n319.5,0\n319.5,239.5\n0,239.5", checkWorld: "50,50; 250,60; 150,200" }, camera), /unit selector/);
  assert.throws(() => buildCalibrationRequest({ ...draft, mappingPixels: "0,0\n639,0\n639,479", mappingWorld: "0,0\n1,0\n1,1" }, camera), /four or more/);
  assert.throws(() => buildCalibrationRequest({ ...draft, checkPixels: "100,100; 500,120", checkWorld: "5,5; 25,6" }, camera), /three separate/);
  assert.throws(() => buildCalibrationRequest({ ...draft, checkPixels: "0,0; 500,120; 300,400" }, camera), /separate marks/);
  assert.throws(() => buildCalibrationRequest({ ...draft, checkPixels: "100,100; 700,120; 300,400" }, camera), /inside the 640/);
  assert.throws(() => buildCalibrationRequest(draft, { ...camera, session_id: "usb-other" }), /no current frames/);
  assert.throws(() => parsePairs("1, 2, 3", "Points"), /row 1/);
});

test("training and validation recordings stay disjoint and changing them clears derived work", () => {
  let draft = commissionedDraft();
  draft = { ...draft, profileId: "profile-1", firstCaseId: "case-1", manifestId: "fm-1", attestations: { ...draft.attestations, waterline_unchanged: true } };
  assert.throws(() => addRecording(draft, "training", recording.id), /both training and validation/);
  const added = addRecording(draft, "training", "recording-new");
  assert.equal(added.flow, null);
  assert.equal(added.profileId, null);
  assert.equal(added.firstCaseId, null);
  assert.equal(added.manifestId, null);
  assert.equal(added.attestations.waterline_unchanged, false);
  assert.deepEqual(added.validationRecordingIds, [recording.id]);
  assert.throws(() => buildFlowRequest({ ...draft, validationRecordingIds: [draft.trainingRecordingIds[0]] }), /different runs/);
  assert.throws(() => buildFlowRequest({ ...draft, validationRecordingIds: [] }), /separate validation/);
  assert.deepEqual(buildFlowRequest(draft).bounds, { x_min_cm: 0, x_max_cm: 32, y_min_cm: 0, y_max_cm: 24 });
  const restarted = invalidateAfter(draft, "camera_session");
  assert.equal(restarted.calibration, null);
  assert.deepEqual(restarted.trainingRecordingIds, []);
});

test("an unsupported flow is never wrapped as a measured profile; a supported one keeps the exact flow", () => {
  const draft = commissionedDraft();
  const profile = buildProfile(draft);
  assert.equal(profile.flow, draft.flow);
  assert.equal(profile.data_origin, "MEASURED_TANK");
  assert.deepEqual(profile.sources.map(s => s.id), ["A", "B"]);
  assert.equal(profile.traps[0].validated, true);
  const unsupported = { ...draft, flow: { ...draft.flow, diagnostics: { ...draft.flow.diagnostics, validation_coverage_fraction: 0.4 } } };
  assert.throws(() => buildProfile(unsupported), /unsupported/);
  assert.throws(() => buildProfile({ ...draft, sources: [{ id: "A", polygon: "1,3; 3,3; 3,5" }] }), /two to five/);
  assert.throws(() => buildProfile({ ...draft, observationPolygon: "0,0; 50,0; 50,24" }), /inside the tank/);
  assert.throws(() => buildProfile({ ...draft, maxValidationRmse: "" }), /positive/);
  assert.throws(() => buildProfile({ ...draft, calibration: { ...draft.calibration, approved: false } }), /approved/);
});

test("server checks only apply to the exact request they evaluated", () => {
  const draft = { ...commissionedDraft(), profileId: "profile-1", firstCaseId: "case-1" };
  const key = requestKey(draft);
  const ready = parsePreflight({ status: "READY", steps: STEP_IDS.map(id => step(id)), content_hash: fixture.content_hash, manifest_id: fixture.manifest_id });
  assert.equal(canFreeze(draft, ready, key), true);
  assert.equal(canFreeze({ ...draft, firstCaseId: "case-2" }, ready, key), false);
  const blocked = parsePreflight({ status: "BLOCKED", steps: STEP_IDS.map(id => id === "rig_state" ? step(id, "BLOCKED", "RIG_REVALIDATION_REQUIRED") : step(id)), content_hash: null, manifest_id: null });
  assert.equal(canFreeze(draft, blocked, key), false);
  const views = deriveSteps(draft, camera, blocked, key);
  assert.equal(views.find(v => v.id === "rig_state").state, "blocked");
  assert.equal(views.find(v => v.id === "rig_state").help, "rig_state help");
  const stale = deriveSteps({ ...draft, firstCaseId: "case-2" }, camera, blocked, key);
  assert.equal(stale.find(v => v.id === "rig_state").state, "server", "a check for another request is not shown as current");
  assert.throws(() => parsePreflight({ status: "READY", steps: STEP_IDS.map(id => id === "rig_state" ? step(id, "BLOCKED") : step(id)), content_hash: "x", manifest_id: "y" }), /disagreed/);
  assert.throws(() => parsePreflight({ status: "BLOCKED", steps: STEP_IDS.slice(1).map(id => step(id)) }), /out of order/);
  assert.equal(buildFieldRequest(draft).attestations, undefined, "unconfirmed attestations are not sent as false claims");
});

test("missing camera, restarted session and unapproved mapping are explained locally", () => {
  const draft = commissionedDraft();
  const byId = views => Object.fromEntries(views.map(v => [v.id, v]));
  assert.equal(byId(deriveSteps(newDraft(), null, null, "")).camera_session.state, "missing");
  const restarted = byId(deriveSteps(draft, { ...camera, session_id: "usb-new" }, null, ""));
  assert.equal(restarted.camera_session.state, "blocked");
  assert.match(restarted.camera_session.help, /redone/);
  assert.equal(byId(deriveSteps(draft, { ...camera, fresh: false }, null, "")).camera_session.state, "blocked");
  const mapping = byId(deriveSteps({ ...draft, calibration: { ...draft.calibration, approved: false, max_error_cm: 9 } }, camera, null, "")).water_plane_mapping;
  assert.equal(mapping.state, "blocked");
  assert.match(mapping.help, /centimetres/);
  for (const view of deriveSteps(newDraft(), null, null, "")) if (view.state !== "done") assert.ok(view.message, view.id);
});

test("only a sealed READY receipt is accepted, using the committed synthetic contract fixture", () => {
  const detail = parseManifestDetail({ manifest: fixture, is_current: true, stale_reasons: [] });
  assert.equal(detail.manifest.manifest_id, fixture.manifest_id);
  assert.ok(detail.manifest.warnings.includes("SYNTHETIC_FAKE_CAPTURE_NOT_PHYSICAL"));
  assert.equal(parseManifestDetail({ manifest: fixture, is_current: false, stale_reasons: ["RIG_CHANGED_AFTER_RECEIPT"] }).is_current, false);
  for (const manifest of [{ ...fixture, status: "DRAFT" }, { ...fixture, checks: fixture.checks.slice(1) }, { ...fixture, manifest_id: "fm-0000000000000000" },
    { ...fixture, checks: fixture.checks.map((c, i) => i ? c : { ...c, status: "BLOCKED" }) }, { ...fixture, provenance: { ...fixture.provenance, hardware_independently_verified: true } }]) {
    assert.throws(() => parseManifestDetail({ manifest, is_current: true, stale_reasons: [] }), /READY manifest/);
  }
});

test("drafts survive reloads and failures; corrupt drafts are discarded", () => {
  const draft = { ...commissionedDraft(), profileId: "profile-1" };
  assert.deepEqual(decodeDraft(encodeDraft(draft)), draft);
  assert.equal(decodeDraft("{"), null);
  assert.equal(decodeDraft(JSON.stringify({ ...draft, version: 2 })), null);
  assert.equal(decodeDraft(JSON.stringify({ ...draft, unit: "furlong" })), null);
  assert.equal(decodeDraft(JSON.stringify({ ...draft, calibration: { approved: true } })), null);
  assert.equal(decodeDraft(JSON.stringify({ ...draft, attestations: { waterline_unchanged: "yes" } })).attestations.waterline_unchanged, false);
  const network = failureNotice(new TypeError("Failed to fetch"));
  assert.equal(network.retryable, true);
  assert.match(network.message, /draft is kept/);
  const conflict = failureNotice(Object.assign(new Error("Rig changed"), { status: 409 }));
  assert.equal(conflict.retryable, false);
  assert.match(conflict.message, /Rig changed\. Your draft is kept\./);
  assert.equal(failureNotice(Object.assign(new Error("Down"), { status: 503 })).retryable, true);
  const local = failureNotice(new Error("Use four or more mapping correspondences."));
  assert.equal(local.retryable, false);
  assert.doesNotMatch(local.message, /API is reachable/);
});

test("preview clicks map to source-image pixels", () => {
  assert.deepEqual(previewPixel(160, 120, 320, 240, 640, 480), [320, 240]);
  assert.deepEqual(previewPixel(400, -5, 320, 240, 640, 480), [639, 0]);
  assert.throws(() => previewPixel(1, 1, 0, 0, 640, 480), /no size/);
});

test("green-token recording needs a measured empty-tank reference from the same session", async () => {
  const { detectionFields, parseTokenReference, setTokenReference, withTokenSize, newDraft: fresh, deriveSteps: steps, decodeDraft: decode, encodeDraft: encode } = await import("../app/components/field-workflow-state.ts");
  const saved = { detector: "foreground_reference_v1", reference_id: "ref-0123456789abcdef-a1b2c3d4", content_id: "ref-0123456789abcdef", camera_session_id: "usb-fake-session", image_size_px: [1280, 720], frame_count: 10, roi_fraction: 1, captured_at: 1, rig_change_at_capture: null, id: "ref-0123456789abcdef-a1b2c3d4" };
  let draft = { ...fresh(), cameraSessionId: "usb-fake-session", trainingRecordingIds: ["recording-a"], validationRecordingIds: ["recording-b"] };
  assert.equal(draft.detector, "foreground_reference_v1");
  assert.throws(() => detectionFields(draft), /empty tank/);
  const reference = parseTokenReference(saved);
  draft = setTokenReference(draft, reference);
  assert.deepEqual(draft.trainingRecordingIds, [], "a new reference clears recordings made another way");
  assert.throws(() => detectionFields(draft), /measure one token/);
  assert.equal(steps(draft, null, null, "").find(step => step.id === "drift_recordings").message, "Measure one token before recording.");
  assert.throws(() => withTokenSize(reference, { reference_id: "ref-other", token_area_px: 400, token_area_px_range: [140, 1200] }), /another reference/);
  draft = setTokenReference(draft, withTokenSize(reference, { reference_id: reference.reference_id, token_area_px: 400, token_area_px_range: [140, 1200] }));
  assert.deepEqual(detectionFields(draft), { detector: "foreground_reference_v1", reference_id: reference.reference_id });
  assert.throws(() => detectionFields({ ...draft, cameraSessionId: "usb-new-session" }), /another camera session/);
  assert.deepEqual(detectionFields({ ...draft, detector: "red_hsv" }), {}, "red keeps the original request body");
  assert.deepEqual(decode(encode(draft)).tokenReference, draft.tokenReference);
  assert.equal(decode(JSON.stringify({ ...draft, detector: "blue" })), null);
  assert.throws(() => parseTokenReference({ ...saved, detector: "red_hsv" }), /incomplete/);
});
