import assert from "node:assert/strict";
import test from "node:test";
import { newDraft, applyLoggedTrayMeasurements } from "../app/components/field-workflow-state.ts";

test("reusing the logged ruler survey converts bounds without approving a camera or changing its tolerance", () => {
  for (const [unit, expected] of [["cm", ["35.56", "22.86"]], ["in", ["14", "9"]], ["mm", ["355.6", "228.6"]]]) {
    const before = { ...newDraft(), unit, maxErrorCm: "0.5", flow: { id: "old-flow" }, profileId: "old-profile", firstCaseId: "old-case", manifestId: "old-receipt", attestations: { waterline_unchanged: true } };
    const after = applyLoggedTrayMeasurements(before);
    assert.deepEqual(after.bounds, { xMin: "0", xMax: expected[0], yMin: "0", yMax: expected[1] });
    assert.equal(after.unit, unit);
    assert.equal(after.maxErrorCm, "0.5");
    assert.equal(after.calibration, null);
    assert.equal(after.cameraSessionId, null);
    assert.equal(after.tokenReference, null);
    assert.equal(after.mappingPixels, "");
    assert.equal(after.checkWorld, "");
    assert.equal(after.tokenClass, "green-bottle-cap");
    for (const key of ["flow", "profileId", "firstCaseId", "manifestId"]) assert.equal(after[key], null);
    assert.ok(Object.values(after.attestations).every(value => value === false));
    assert.equal(before.profileId, "old-profile");
  }
});
