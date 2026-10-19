import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { parseRegistration, registrationMapping, registrationStage } from "../app/components/tank-registration-state.ts";
import { insidePolygon, metricGrid } from "../app/components/camera-grid-state.ts";
import { decodeDraft, encodeDraft, newDraft } from "../app/components/field-workflow-state.ts";

const demo = JSON.parse(readFileSync(new URL("../public/registration-demo/rehearsal.json", import.meta.url), "utf8"));

test("dry four-step proposal, stale, recovery and loss match the frontend mapping gates", () => {
  assert.equal(registrationStage.length, 4);
  const statuses = demo.steps.map(r => parseRegistration(r.status));
  assert.deepEqual(statuses.map(s => s.state), ["STABLE_APPROVED", "MOVED_STALE", "CANDIDATE_MAPPING", "MOVED_STALE"]);
  assert.equal(registrationMapping(statuses[1]), null);
  assert.equal(registrationMapping(statuses[3]), null);
  const candidate = registrationMapping(statuses[2]);
  assert.equal(candidate.approved, false);
  assert.equal(candidate.estimated, true);
  assert.ok(metricGrid(candidate, "synthetic-dry", 1040, 840));
  assert.equal(statuses[2].physical_accuracy_validated, false);
  assert.equal(statuses[2].mapping_current, false);
});
test("independent error, matrix and contradictory approval fail closed", () => {
  for (const mutate of [
    s => { s.mapping_current = false; },
    s => { s.calibration_id = "another"; },
    s => { s.proposal.calibration.max_error_cm = Infinity; },
    s => { s.proposal.calibration.homography_image_to_cm = [[1,0,0],[0,0,0],[0,0,1]]; },
    s => { s.proposal.water_polygon_px[0][0] = NaN; },
  ]) {
    const status = structuredClone(demo.steps[0].status); mutate(status);
    assert.throws(() => parseRegistration(status));
  }
});
test("the centimetre grid moves with recovery; resize and other sessions cannot inherit it", () => {
  const before = registrationMapping(parseRegistration(demo.steps[0].status));
  const after = registrationMapping(parseRegistration(demo.steps[2].status));
  const a = metricGrid(before, "synthetic-dry", 1040, 840);
  const b = metricGrid(after, "synthetic-dry", 1040, 840);
  assert.ok(a && b);
  assert.notDeepEqual(a.lines[0], b.lines[0]);
  assert.equal(metricGrid(after, "new-session", 1040, 840), null);
  assert.equal(metricGrid(after, "synthetic-dry", 520, 420), null);
});
test("concave support clips readout without filling in the notch", () => {
  const polygon = [[0,0],[40,0],[40,30],[20,30],[20,25],[0,25]];
  assert.equal(insidePolygon([5, 28], polygon), false);
  assert.equal(insidePolygon([25, 28], polygon), true);
  assert.equal(insidePolygon([0, 10], polygon), true);
});
test("a saved managed-map draft requires fresh monitoring after reload", () => {
  const draft = newDraft();
  draft.calibration = { ...demo.steps[0].status.proposal.calibration, marker_managed: true };
  const restored = decodeDraft(encodeDraft(draft));
  assert.equal(restored.calibration, null);
  assert.equal(restored.flow, null);
});
