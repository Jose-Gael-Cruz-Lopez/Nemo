import assert from "node:assert/strict";
import test from "node:test";
import { canReloadSourceEvidence, currentSourceEvidence } from "../app/components/evidence-state.ts";

test("a report must match both the selected case and its current evidence ID", () => {
  const report = { id: "evidence-current", case_id: "case-a", status: "ranked" };
  assert.equal(currentSourceEvidence(report, "case-a", "evidence-current"), report);
  assert.equal(currentSourceEvidence(report, "case-b", "evidence-current"), null);
  assert.equal(currentSourceEvidence(report, "case-a", "evidence-old"), null);
  assert.equal(currentSourceEvidence(report, "case-a", null), null);
  assert.equal(currentSourceEvidence(report, "case-a", undefined), null);
  assert.equal(currentSourceEvidence(null, "case-a", "evidence-current"), null);
});

test("an external evidence ID change immediately hides the prior report", () => {
  const oldReport = { id: "evidence-old", case_id: "case-a" };
  const newReport = { id: "evidence-new", case_id: "case-a" };
  assert.equal(currentSourceEvidence(oldReport, "case-a", "evidence-old"), oldReport);
  assert.equal(currentSourceEvidence(oldReport, "case-a", "evidence-new"), null);
  assert.equal(currentSourceEvidence(newReport, "case-a", "evidence-new"), newReport);
});

test("a delayed old response cannot replace the current case evidence", async () => {
  const oldReport = { id: "evidence-old", case_id: "case-a" };
  const newReport = { id: "evidence-new", case_id: "case-a" };
  let resolveOld;
  const oldResponse = new Promise(resolve => { resolveOld = resolve; });
  let expectedId = "evidence-old";
  let displayed = oldReport;
  const pending = oldResponse.then(report => {
    const accepted = currentSourceEvidence(report, "case-a", expectedId);
    if (accepted) displayed = accepted;
  });
  expectedId = "evidence-new";
  displayed = currentSourceEvidence(newReport, "case-a", expectedId);
  resolveOld(oldReport);
  await pending;
  assert.equal(displayed, newReport);
});

test("a delayed previous-case report cannot cross a case switch", async () => {
  const response = Promise.resolve({ id: "evidence-a", case_id: "case-a" });
  const selected = "case-b";
  const expectedId = "evidence-b";
  assert.equal(currentSourceEvidence(await response, selected, expectedId), null);
});

test("failed source reads allow one explicit retry only for the current case and report", () => {
  const failure = { id: "evidence-current", case_id: "case-a", message: "Failed to fetch" };
  assert.equal(canReloadSourceEvidence(failure, "case-a", "evidence-current", false), true);
  assert.equal(canReloadSourceEvidence(failure, "case-a", "evidence-current", true), false);
  assert.equal(canReloadSourceEvidence(failure, "case-a", "evidence-new", false), false);
  assert.equal(canReloadSourceEvidence(failure, "case-b", "evidence-current", false), false);
  assert.equal(canReloadSourceEvidence(null, "case-a", "evidence-current", false), false);
});

test("a completion or failure tied to old evidence disappears when the canonical ID changes", () => {
  const completion = { id: "evidence-old", case_id: "case-a", message: "Chalk completed" };
  assert.equal(currentSourceEvidence(completion, "case-a", "evidence-old"), completion);
  assert.equal(currentSourceEvidence(completion, "case-a", "evidence-new"), null);
  assert.equal(currentSourceEvidence(completion, "case-b", "evidence-old"), null);
});
