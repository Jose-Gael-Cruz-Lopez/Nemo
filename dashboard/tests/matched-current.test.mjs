import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import { MATCHED_GROUPS, matchedHourlyDisplacement, matchedPlot, matchedSegments, validateMatchedAnswer, validateMatchedEnvelope } from "../app/components/matched-current-state.ts";
import { readVectorResponse } from "../app/components/vector-diagnostic-state.ts";

// Entirely invented unit fixtures built using the existing pure evaluator and
// reader test helper. No acquired NOAA/HYCOM values or new study outcomes.
const saved = Object.fromEntries(["report", "partial", "blocked"].map(name => [name, JSON.parse(readFileSync(new URL(`./fixtures/matched-current-synthetic-${name}.json`, import.meta.url), "utf8"))]));
const fixture = (name = "report") => structuredClone(saved[name]);
const reject = value => assert.throws(() => validateMatchedEnvelope(value), /No result was accepted/);

test("frozen complete and blocked fixtures retain both identities and all thirty-six declared cells", () => {
  for (const [name, expected] of [["report", 36], ["partial", 33], ["blocked", 0]]) {
    const f = fixture(name), before = JSON.stringify(f);
    assert.equal(validateMatchedEnvelope(f), f);
    assert.equal(f.report.scores.scored_cell_count, expected);
    assert.equal(f.report.scores.groups.flatMap(g => g.candidates.flatMap(m => m.cells)).length, 36);
    assert.equal(f.report.scores.planned_distinct_target_count, 12);
    assert.equal(JSON.stringify(f), before);
    assert.equal(f.report.scores.primary_equal_id_macro_results === null, expected !== 36);
    assert.equal(f.report.scores.primary_paired_comparisons === null, expected !== 36);
    assert.equal(f.artifact_identity.numeric_replay_verified, false);
  }
});

test("fixed groups, models, hourly clocks, target denominators and immutable lineage cannot drift", () => {
  for (const mutate of [
    f => { f.report.scores.planned_distinct_target_count = 36; },
    f => { f.report.scores.planned_cell_count = 35; },
    f => f.report.scores.groups.pop(),
    f => { f.report.scores.groups[1].group_id = MATCHED_GROUPS[0]; },
    f => f.report.scores.groups[0].candidates.pop(),
    f => { f.report.scores.groups[0].candidates[0].model_id = "kalman_cv"; },
    f => f.report.scores.groups[0].candidates[0].cells.pop(),
    f => { f.report.scores.groups[0].candidates[0].cells[0].time_utc = "2022-06-01T02:00:00Z"; },
    f => { f.report.scores.forecast_report.future_positions_used = true; },
    f => { f.report.scores.forecast_report.groups[0].context_count = 24; },
    f => { f.report.lineage.protocol_sha256 = "f".repeat(64); },
    f => { f.artifact_identity.result_pin_verified = false; },
    f => { f.artifact_identity.numeric_replay_verified = true; },
    f => { f.report.scores.forecast_report.forecast_sha256 = "f".repeat(64); },
  ]) { const f = fixture(); mutate(f); reject(f); }
});

test("partial outcomes stay in the ledger and cannot become complete primary scores or zero error", () => {
  const p = fixture("partial"), s = p.report.scores;
  assert.equal(s.groups[0].candidates[0].cells[0].target_status, "UNAVAILABLE");
  assert.equal(s.groups[0].candidates[0].cells[0].error_m, null);
  assert.equal(s.groups[0].candidates[0].metrics.full_horizon_ade_m, null);
  assert.equal(s.groups[0].candidates[0].metrics.scored_count, 5);
  assert.equal(s.paired_comparisons[0].common_scored_count, 11);
  for (const mutate of [
    f => { f.report.scores.primary_equal_id_macro_results = fixture().report.scores.primary_equal_id_macro_results; },
    f => { f.report.scores.primary_paired_comparisons = fixture().report.scores.primary_paired_comparisons; },
    f => { f.report.scores.primary_common_cohort_complete = true; },
    f => { f.report.scores.groups[0].candidates[0].cells[0].error_m = 0; },
    f => { f.report.scores.groups[0].candidates[0].metrics.full_horizon_ade_m = 0; },
    f => { f.report.scores.groups[0].candidates[0].metrics.scored_prefix_count = 5; },
    f => { f.report.scores.paired_comparisons[0].planned_common_cell_count = 11; },
    f => { f.report.scores.paired_comparisons[0].common_scored_count = 12; },
  ]) { const f = fixture("partial"); mutate(f); reject(f); }
});

test("numeric evidence, candidate forecasts and shared later targets cannot contradict their saved summaries", () => {
  for (const mutate of [
    f => { f.report.scores.groups[0].candidates[0].cells[0].latitude_deg += .01; },
    f => { f.report.scores.groups[0].candidates[1].cells[0].target_latitude_deg += .01; },
    f => { f.report.scores.groups[0].candidates[0].cells[0].error_m = -1; },
    f => { f.report.scores.groups[0].candidates[0].metrics.available_cell_mean_error_m += 10; },
    f => { f.report.scores.models[0].per_horizon[0].complete_group_mean_error_m += 1; },
    f => { f.report.scores.primary_equal_id_macro_results[0].equal_id_macro_ade_m += 1; },
    f => { f.report.scores.paired_comparisons[0].cells[0].error_a_m += 1; },
    f => { f.report.scores.paired_comparisons[0].mean_delta_a_minus_b_m += 1; },
    f => { f.report.scores.forecast_report.groups[0].candidates[0].future_positions_used = true; },
  ]) { const f = fixture(); mutate(f); reject(f); }
});

test("invalid geography, impossible UTC dates, nonfinite values and validation promotions are refused", () => {
  for (const mutate of [
    f => { f.report.scores.groups[0].candidates[0].cells[0].target_latitude_deg = 91; },
    f => { f.report.scores.groups[0].candidates[0].cells[0].target_longitude_deg = -181; },
    f => { f.report.forecast_frozen_at_utc = "2026-02-30T00:00:04Z"; },
    f => { f.report.scored_at_utc = "2025-01-01T00:00:04Z"; },
    f => { f.report.scored_at_utc = "2026-01-01T00:00:05-04:00"; },
    f => { f.report.scores.scored_cell_count = NaN; },
    f => { f.report.current_field.foo = Infinity; },
    f => { f.report.physical_validation = true; },
    f => { f.report.operational_causality = true; },
    f => { f.report.scores.forecast_report.physical_validation = true; },
    f => { f.report.scores.automatic_winner_selected = true; },
    f => { f.report.scores.limitations.push("x".repeat(16_001)); },
  ]) { const f = fixture(); mutate(f); reject(f); }
});

test("the display never censors a valid later target outside the forecast frame's fifty-kilometre radius", () => {
  const f = fixture();
  // A display-only coordinate injection. Stored errors are not re-scored here;
  // the trusted server reader owns immutable artifact provenance.
  for (const candidate of f.report.scores.groups[0].candidates) candidate.cells[5].target_latitude_deg = 31.2;
  validateMatchedEnvelope(f);
  const plot = matchedPlot(f, MATCHED_GROUPS[0]);
  assert.ok(plot.series.recorded[6].y_m > 130_000);
  assert.ok(plot.domain.span > 130_000);
  assert.equal(f.report.scores.scored_cell_count, 36);
});

test("missing hourly endpoints retain gaps and arrows require exactly adjacent saved hours", () => {
  const plot = matchedPlot(fixture("partial"), MATCHED_GROUPS[0]);
  assert.equal(plot.series.recorded[1], null);
  assert.deepEqual(matchedSegments(plot.series.recorded).map(segment => segment.map(p => p.hour)), [[0], [2, 3, 4, 5, 6]]);
  assert.equal(matchedHourlyDisplacement(plot.series.recorded, 1), null);
  assert.equal(matchedHourlyDisplacement(plot.series.recorded, 2), null);
  assert.deepEqual(matchedHourlyDisplacement(plot.series.recorded, 3).map(p => p.hour), [2, 3]);
  for (const hour of [0, .5, 6.5, 7, NaN]) assert.equal(matchedHourlyDisplacement(plot.series.recorded, hour), null);
  assert.equal(matchedPlot(fixture("blocked"), MATCHED_GROUPS[0]), null);
  assert.equal(matchedPlot(fixture(), "not-a-selected-buoy"), null);
});

function answer(envelope = fixture()) {
  const identity = envelope.artifact_identity, r = envelope.report, s = r.scores;
  const ids = [`matched-current-report:${identity.report_sha256}`, `matched-current-protocol:${identity.protocol_sha256}`];
  const compact = { report_sha256: identity.report_sha256, protocol_sha256: identity.protocol_sha256, artifact_verification: structuredClone(identity), coverage: { planned_group_count: 2, planned_model_track_count: 6, planned_cell_count: 36, scored_cell_count: s.scored_cell_count, planned_distinct_target_count: 12, primary_common_cohort_complete: s.primary_common_cohort_complete }, models: s.models, primary_equal_id_macro_results: s.primary_equal_id_macro_results, groups: s.groups.map((g, i) => ({ group_id: g.group_id, target_issues: g.target_issues, candidates: g.candidates.map((c, j) => ({ model_id: c.model_id, prediction_status: c.prediction_status, prediction_reason_code: c.prediction_reason_code, metrics: c.metrics, forecast_available_count: s.forecast_report.groups[i].candidates[j].available_count })) })) };
  return structuredClone({ schema_version: 1, kind: "MATCHED_CURRENT_RESEARCH_INVESTIGATION", scope: "READ_ONLY_MATCHED_CURRENT_STUDY", action: "REPORT", explanation: "This invented fixture only exercises a bounded evidence discussion; it does not establish physical protection.", evidence_ids: ids, live_model_response: true, provider: "chalk", report_sha256: identity.report_sha256, protocol_sha256: identity.protocol_sha256, research_report: r, artifact_identity: identity, trace: [{ tool: "get_study_evidence", arguments: {}, result: { ok: true, evidence_ids: ids, matched_current_study: compact } }], numeric_replay_verified: false, store_written: false, physical_validation: false, hardware_actuation: false });
}

test("Chalk answers cite the exact loaded report and protocol regardless of object key order", () => {
  const f = fixture(), a = answer(f);
  assert.equal(validateMatchedAnswer(a, f), a);
  a.research_report = Object.fromEntries(Object.entries(a.research_report).reverse());
  a.artifact_identity = Object.fromEntries(Object.entries(a.artifact_identity).reverse());
  validateMatchedAnswer(a, f);
});

test("stale, fabricated, unbound or action-capable Chalk discussions fail closed", () => {
  for (const mutate of [
    a => { a.report_sha256 = "f".repeat(64); },
    a => { a.evidence_ids = []; },
    a => { a.trace = []; },
    a => { a.trace[0].tool = "request_collection"; },
    a => { a.trace[0].arguments = { case_id: "unrelated-case" }; },
    a => { a.trace[0].result.evidence_ids[1] = a.trace[0].result.evidence_ids[0]; },
    a => { a.trace[0].result.matched_current_study.coverage.scored_cell_count = 35; },
    a => { a.trace[0].result.matched_current_study.groups[0].candidates[0].forecast_available_count = 0; },
    a => { a.research_report.scores.limitations.push("Changed after load"); },
    a => { a.live_model_response = false; },
    a => { a.provider = "direct_gemini"; },
    a => { a.hardware_actuation = true; },
    a => { a.store_written = true; },
    a => { a.numeric_replay_verified = true; },
    a => { a.failure_code = {}; },
    a => { a.provider_status_code = "401"; },
  ]) { const a = answer(); mutate(a); assert.throws(() => validateMatchedAnswer(a, fixture()), /No result was accepted/); }
});

test("a provider STOP keeps the frozen blocked result without fabricating a live response", () => {
  const f = fixture("blocked"), a = answer(f);
  Object.assign(a, { action: "STOP", evidence_ids: [], trace: [], live_model_response: false, failure_code: "NOT_CONFIGURED", explanation: "Chalk is not configured. The frozen unavailable outcomes remain available for inspection." });
  validateMatchedAnswer(a, f);
  assert.equal(a.research_report.scores.scored_cell_count, 0);
  a.action = "REPORT";
  assert.throws(() => validateMatchedAnswer(a, f), /No result was accepted/);
});

test("bounded HTTP reads preserve missing artifacts, snapshot conflicts and auth errors", async () => {
  const text = JSON.stringify(fixture("blocked"));
  assert.equal((await readVectorResponse(new Response(text), validateMatchedEnvelope, 5_000_000)).report.scores.scored_cell_count, 0);
  await assert.rejects(readVectorResponse(new Response(text, { headers: { "Content-Length": "5000001" } }), validateMatchedEnvelope, 5_000_000), /exceeds/);
  for (const status of [401, 404, 409, 503]) await assert.rejects(readVectorResponse(new Response(JSON.stringify({ detail: "Pinned study unavailable" }), { status }), validateMatchedEnvelope), /Pinned study unavailable/);
});

const require = createRequire(import.meta.url), loaded = new Map();
function component(path) {
  const file = resolve(path); if (loaded.has(file)) return loaded.get(file).exports;
  const mod = { exports: {} }; loaded.set(file, mod);
  const compiled = ts.transpileModule(readFileSync(file, "utf8"), { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
  new Function("require", "module", "exports", compiled)(name => {
    if (name.endsWith(".module.css")) return { __esModule: true, default: new Proxy({}, { get: (_, key) => String(key) }) };
    if (name === "next/link") return { __esModule: true, default: ({ children, ...props }) => React.createElement("a", props, children) };
    if (name.startsWith(".")) { const base = resolve(dirname(file), name); return component([base, `${base}.tsx`, `${base}.ts`].find(existsSync)); }
    assert.notEqual(name, "three", "this hourly research plot never loads a 3D runtime");
    return require(name);
  }, mod, mod.exports); return mod.exports;
}
const visibility = { recorded: true, stationary: true, last_drift: true, current_only: true };

test("visibility toggles retain the same all-series plot domain, stored scores and hourly endpoint selection", () => {
  const { MatchedCurrentFigure } = component("app/components/matched-current-study.tsx"), envelope = fixture(), before = JSON.stringify(envelope);
  const render = visible => renderToStaticMarkup(React.createElement(MatchedCurrentFigure, { envelope, groupId: MATCHED_GROUPS[0], visible, onToggle() {}, hour: 3, arrows: true }));
  const all = render(visibility), recorded = render({ ...visibility, stationary: false, last_drift: false, current_only: false }), none = render(Object.fromEntries(Object.keys(visibility).map(k => [k, false])));
  const domain = html => /data-domain="([^"]+)"/.exec(html)?.[1];
  assert.equal(domain(all), domain(recorded)); assert.equal(domain(all), domain(none));
  assert.match(all, /data-plot-series="stationary"/); assert.doesNotMatch(recorded, /data-plot-series="stationary"/);
  assert.match(all, /stroke-dasharray="7 5"/); assert.match(all, /adjacent-hour displacement estimates, not native HYCOM currents/);
  assert.match(none, /No trajectories selected/); assert.match(all, /Selected hour 3/);
  assert.equal(JSON.stringify(envelope), before);
});

test("a blocked research result displays withheld primary scores and no fabricated SVG trajectory", () => {
  const { MatchedCurrentResults } = component("app/components/matched-current-study.tsx"), { OperatorProvider } = component("app/components/operator-provider.tsx");
  const html = renderToStaticMarkup(React.createElement(OperatorProvider, null, React.createElement(MatchedCurrentResults, { api: "", envelope: fixture("blocked") })));
  assert.match(html, /0 \/ 36 scored model-hour cells/); assert.match(html, /no overall model ranking is supported/);
  assert.match(html, /No supported path to draw/); assert.match(html, /no synthetic route is substituted/);
  assert.equal((html.match(/Withheld/g) ?? []).length >= 6, true);
  assert.doesNotMatch(html, /data-domain=|data-plot-series=/);
  assert.match(html, /disabled=""[^>]*><svg[^>]*|Ask Chalk about matched currents/);
});

test("closed initial card is read-only, concise and starts no request or provider call", () => {
  const { MatchedCurrentStudy } = component("app/components/matched-current-study.tsx");
  const previous = globalThis.fetch; let calls = 0;
  globalThis.fetch = () => { calls++; throw new Error("The closed card must stay idle"); };
  try {
    const html = renderToStaticMarkup(React.createElement(MatchedCurrentStudy, { api: "" }));
    assert.match(html, /Load matched-current study/); assert.doesNotMatch(html, /<canvas|data-domain=|Chalk about matched currents/);
    assert.equal(calls, 0);
  } finally { globalThis.fetch = previous; }
});

test("two connected credentials remount the Chalk request boundary without entering rendered markup", () => {
  // Inspect real component element keys with invented credentials; no browser,
  // provider, credential storage or new renderer dependency is involved.
  function resultTree(token, api = "", envelope = fixture("blocked")) {
    const file = resolve("app/components/matched-current-study.tsx"), mod = { exports: {} };
    const compiled = ts.transpileModule(readFileSync(file, "utf8"), { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
    new Function("require", "module", "exports", compiled)(name => {
      if (name === "react") return { ...React, useState: initial => [typeof initial === "function" ? initial() : initial, () => {}] };
      if (name === "./operator-provider") return { useOperator: () => ({ token }) };
      if (name.endsWith(".module.css")) return { __esModule: true, default: new Proxy({}, { get: (_, key) => String(key) }) };
      if (name === "next/link") return { __esModule: true, default: ({ children, ...props }) => React.createElement("a", props, children) };
      if (name.startsWith(".")) { const base = resolve(dirname(file), name); return component([base, `${base}.tsx`, `${base}.ts`].find(existsSync)); }
      return require(name);
    }, mod, mod.exports);
    return mod.exports.MatchedCurrentResults({ api, envelope });
  }
  function boundary(node) {
    if (Array.isArray(node)) return node.map(boundary).find(Boolean);
    if (!React.isValidElement(node)) return null;
    if (typeof node.type === "function" && node.type.name === "MatchedChalk") return node;
    return boundary(node.props.children);
  }
  const tokenA = "invented-local-credential-alpha", tokenB = "invented-local-credential-beta";
  const a = resultTree(tokenA), b = resultTree(tokenB), repeated = resultTree(tokenA);
  assert.notEqual(boundary(a).key, boundary(b).key);
  assert.equal(boundary(a).key, boundary(repeated).key);
  assert.notEqual(boundary(a).key, boundary(resultTree(tokenA, "https://example.invalid")).key);
  const revised = fixture("blocked"); revised.artifact_identity.report_sha256 = "f".repeat(64);
  assert.notEqual(boundary(a).key, boundary(resultTree(tokenA, "", revised)).key);
  for (const tree of [a, b]) {
    const html = renderToStaticMarkup(tree);
    assert.ok(!html.includes(tokenA) && !html.includes(tokenB));
    assert.doesNotMatch(html, /Authorization|Bearer /);
    assert.match(html, /Ask Chalk about matched currents/);
  }
});

test("v2 selection requires its own study identity and refuses cross-version or unknown responses", () => {
  const amended = fixture();
  amended.report.study_id = amended.artifact_identity.study_id = "matched-current-gdp-hycom-15m-v2";
  assert.equal(validateMatchedEnvelope(amended, "v2"), amended);
  assert.throws(() => validateMatchedEnvelope(amended, "v1"), /No result was accepted/);
  assert.throws(() => validateMatchedEnvelope(fixture(), "v2"), /No result was accepted/);
  assert.throws(() => validateMatchedEnvelope(fixture(), "v3"), /No result was accepted/);
  const a = answer(amended);
  assert.equal(validateMatchedAnswer(a, amended), a);
  assert.throws(() => validateMatchedAnswer(answer(), amended), /No result was accepted/);
});

test("v2 rendering discloses prior forcing exposure and retains the original attempt choice", () => {
  const { MatchedCurrentStudy, MatchedCurrentResults } = component("app/components/matched-current-study.tsx");
  const { OperatorProvider } = component("app/components/operator-provider.tsx");
  const amended = fixture();
  amended.report.study_id = amended.artifact_identity.study_id = "matched-current-gdp-hycom-15m-v2";
  const card = renderToStaticMarkup(React.createElement(MatchedCurrentStudy, { api: "" }));
  assert.match(card, /Study version/);
  assert.match(card, /value="v2" selected/);
  assert.match(card, /v1 · preserved original attempt/);
  const result = renderToStaticMarkup(React.createElement(OperatorProvider, null, React.createElement(MatchedCurrentResults, { api: "", envelope: amended })));
  assert.match(result, /after the v1 forcing was decoded for diagnosis/);
  assert.match(result, /same buoy groups and models/);
  assert.match(result, /does not establish operational forecast skill/);
});
