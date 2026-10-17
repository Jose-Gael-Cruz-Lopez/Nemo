import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import { validateOceanPrevention, validateOceanPreventionAnswer } from "../app/components/ocean-prevention-state.ts";

// Entirely synthetic DISPLAY/CONTRACT fixture. Its motions and interception
// outcomes are invented; they do not validate the real advection/event solver.
const start = "2026-10-17T18:00:00Z", end = "2026-10-18T00:00:00Z";
const FRAME = { origin_latitude_deg: 21, origin_longitude_deg: -158, east_metres_per_degree: 103000, north_metres_per_degree: 111000, position_units: "m", axes: "x east, y north" };
const geo = (x, y) => ({ latitude_deg: 21 + y / 111000, longitude_deg: -158 + x / 103000 });
const point = (x, y, elapsed_s) => ({ x_m: x, y_m: y, ...geo(x, y), elapsed_s, time_utc: new Date(Date.parse(start) + elapsed_s * 1000).toISOString(), eastward_m_s: -0.2, northward_m_s: 0.05, speed_m_s: Math.hypot(0.2, 0.05) });
const segment = (id, y0, y1) => ({ id, start_xy_m: [-1500, y0], end_xy_m: [-1500, y1], start_geo: geo(-1500, y0), end_geo: geo(-1500, y1) });
function summary(outcomes) {
  const counts = { release_count: outcomes.length, entered_count: 0, intercepted_count: 0, no_entry_count: 0, unresolved_count: 0 };
  for (const o of outcomes) counts[{ ENTERED_PROTECTED_ZONE: "entered_count", IDEALIZED_INTERCEPTION: "intercepted_count", NO_ENTRY_WITHIN_HORIZON: "no_entry_count", UNRESOLVED: "unresolved_count" }[o.status]]++;
  const lo = counts.entered_count, hi = lo + counts.unresolved_count;
  return { ...counts, protected_entry_count_bounds: [lo, hi], protected_entry_fraction_bounds: [lo / outcomes.length, hi / outcomes.length], denominator_policy: "all_fixed_releases_including_missing_forcing_and_partial_paths" };
}
function fixture(initial = false) {
  const frame = { ...FRAME };
  const releases = Array.from({ length: 6 }, (_, index) => ({ id: `release-${index + 1}`, x_m: 0, y_m: (index - 2.5) * 500, ...geo(0, (index - 2.5) * 500), start_time_utc: start, horizon_s: 21600, kind: "hypothetical_passive_tracer_not_observed_waste" }));
  const polygon = initial ? [[-5000, -1000], [-3500, -1000], [-3500, 1000], [-5000, 1000]] : [[-6000, -5000], [-3500, -5000], [-3500, 500], [-6000, 500]];
  const protected_zone = { id: "test-reef-proxy", label: "Synthetic hypothetical protected reef proxy", polygon_xy_m: polygon, polygon_geo: polygon.map(([x, y]) => geo(x, y)), is_mapped_real_reef: false };
  const layouts = [{ id: "central", label: "Central coverage", total_length_m: 2000, segments: [segment("central-line", -1000, 1000)] }, { id: "flanking", label: "Flanking coverage", total_length_m: 2000, segments: [segment("south-line", -2000, -1000), segment("north-line", 1000, 2000)] }];
  function layout(id, label, segments, captures) {
    const outcomes = releases.map((release, i) => {
      const capture = i < captures, status = capture ? "IDEALIZED_INTERCEPTION" : initial ? "NO_ENTRY_WITHIN_HORIZON" : "ENTERED_PROTECTED_ZONE";
      const last = point(capture ? -1500 : -4000, release.y_m, capture ? 3600 : initial ? 21600 : 10800);
      return { release_id: release.id, status, event: status === "NO_ENTRY_WITHIN_HORIZON" ? null : { ...last, kind: capture ? "IDEALIZED_CAPTURE" : "PROTECTED_ZONE_ENTRY", segment_id: capture ? segments[0].id : null }, forcing_status: "COMPLETED", forcing_reason_code: null, requested_horizon_s: 21600, integrated_horizon_s: 21600, track_end_elapsed_s: last.elapsed_s, track: [point(0, release.y_m, 0), last] };
    });
    return { id, label, segments, total_length_m: segments.length ? 2000 : 0, outcomes, summary: summary(outcomes) };
  }
  const baseline = layout("no-interceptor", "No interception", [], 0);
  const evaluated = layouts.map((item, i) => layout(item.id, item.label, item.segments, initial ? 0 : i ? 2 : 4));
  evaluated.forEach(item => { item.summary.entry_reduction_count_bounds_vs_baseline = [baseline.summary.entered_count - item.summary.protected_entry_count_bounds[1], baseline.summary.entered_count - item.summary.protected_entry_count_bounds[0]]; });
  const event_model = { capture: "synthetic display fixture" };
  return {
    schema_version: 1, kind: "OCEAN_PREVENTION_COMPARISON", status: "COMPLETED", mode: "forecast_snapshot",
    snapshot_sha256: "a".repeat(64), method_sha256: "b".repeat(64), scenario_sha256: "c".repeat(64), report_sha256: "d".repeat(64), manifest_sha256: "e".repeat(64),
    scenario: { id: initial ? "initial-proxy-v1" : "downstream-corridor-v2", label: "Synthetic display scenario", frame, start_time_utc: start, horizon_s: 21600, design_status: initial ? "INITIAL_GEOMETRY_NEGATIVE_CONTROL" : "ILLUSTRATIVE_WHAT_IF_AFTER_VIEWING_PREVIEW", geometry_status: initial ? "fixed_pre_outcome_illustrative_hypothesis_not_optimized" : "fixed_post_preview_illustrative_hypothesis_not_independent_validation", design_disclosure: "Synthetic presentation fixture, not measured performance.", protected_zone, releases, layouts, resource_constraint: "Both hypothetical layouts use 2000 m of ideal line.", event_model },
    protected_zone, releases, baseline, layouts: evaluated,
    recommendation: { status: initial ? "TIE" : "BEST_LAYOUT", best_layout_id: initial ? null : "central", reason: "Synthetic fixture outcome, not empirical performance.", comparison_basis: "strict_nonoverlap_of_model_protected_entry_count_bounds" },
    display_bounds_xy_m: { x_m: [-6500, 0], y_m: [-5500, 2000] },
    forcing: { source_url: "https://example.org/synthetic-current-fixture", metadata_url: "https://example.org/synthetic-current-metadata", product_url: "https://example.org/synthetic-current-product", attribution: "Entirely synthetic display fixture", captured_at_utc: "2026-10-17T17:00:00Z", valid_start_utc: start, valid_end_utc: end, model_issue_time_utc: null, depth_m: 0.25 },
    method: { trajectory: "dynamic_current_advection_only", equation: "dX/dt = u(X,t)", solver: "Synthetic fixture, not solver evidence", spatial_interpolation: "bilinear", temporal_interpolation: "linear", step_s: 300, output_step_s: 300, geometry_frame: frame, event_model, identical_unmodified_forcing_for_every_layout: true, paths_integrated_once_per_release: true, barriers_modify_flow: false, capture_efficiency_assumption: "ideal_absorbing_first_contact_not_measured", winner_rule: "strict_nonoverlap_of_entry_bounds_else_tie_or_indeterminate" },
    validation: { measured_track_available: false, physical_validation: false, plastic_motion_validated: false, forecast_skill_established: false, interception_benefit_established: false, real_reef_boundary_used: false, tank_flow_used: false, heldout_buoy_positions_used: false, measured_entry_count: null, measured_intercepted_count: null },
    vector_frames: [start, end].map((time_utc, i) => ({ time_utc, vectors: [{ x_m: -1000, y_m: 0, ...geo(-1000, 0), eastward_m_s: -0.2, northward_m_s: i ? -0.1 : 0.1 }] })), limitations: ["Invented display fixture, not environmental or numerical evidence."],
  };
}
const reject = value => assert.throws(() => validateOceanPrevention(value), /No result was accepted/);
test("the comparison validates both honest scenario contracts without changing evidence", () => {
  for (const initial of [false, true]) { const report = fixture(initial), original = JSON.stringify(report); assert.equal(validateOceanPrevention(report), report); assert.equal(JSON.stringify(report), original); }
});
test("measured protection, plastic skill, mapped reef and tank calibration cannot be claimed", () => {
  for (const key of ["measured_track_available", "physical_validation", "plastic_motion_validated", "forecast_skill_established", "interception_benefit_established", "real_reef_boundary_used", "tank_flow_used", "heldout_buoy_positions_used"]) { const report = fixture(); report.validation[key] = true; reject(report); }
  for (const mutate of [r => { r.validation.measured_entry_count = 0; }, r => { r.validation.measured_intercepted_count = 0; }, r => { r.protected_zone.is_mapped_real_reef = true; }]) { const report = fixture(); mutate(report); reject(report); }
});
test("partial forcing preserves unresolved releases and overlapping bounds remain indeterminate", () => {
  const report = fixture();
  for (const layout of [report.baseline, ...report.layouts]) {
    for (let index = 0; index < 4; index++) {
      const release = report.releases[index], last = point(-1000, release.y_m, 10800);
      Object.assign(layout.outcomes[index], { status: "UNRESOLVED", event: null, forcing_status: "PARTIAL", forcing_reason_code: "MASKED_CURRENT_CELL", integrated_horizon_s: 10800, track_end_elapsed_s: 10800, track: [point(0, release.y_m, 0), last] });
    }
    layout.summary = summary(layout.outcomes);
  }
  for (const layout of report.layouts) layout.summary.entry_reduction_count_bounds_vs_baseline = [report.baseline.summary.protected_entry_count_bounds[0] - layout.summary.protected_entry_count_bounds[1], report.baseline.summary.protected_entry_count_bounds[1] - layout.summary.protected_entry_count_bounds[0]];
  report.status = "PARTIAL";
  Object.assign(report.recommendation, { status: "INDETERMINATE", best_layout_id: null });
  validateOceanPrevention(report);
  assert.deepEqual(report.layouts[0].summary.protected_entry_count_bounds, [2, 6]);
  assert.equal(report.layouts[0].summary.release_count, 6);
  report.recommendation.status = "BEST_LAYOUT"; report.recommendation.best_layout_id = "central"; reject(report);
});
test("display identity, metre coordinates, public links and local frame consistency are checked", () => {
  for (const mutate of [r => { r.report_sha256 = "wrong"; }, r => { r.scenario.frame.position_units = "cm"; }, r => { r.releases[0].longitude_deg = 200; }, r => { r.layouts[0].outcomes[0].track[1].x_m += 1; }, r => { r.forcing.source_url = "javascript:alert(1)"; }, r => { r.forcing.product_url = "https://secret:secret@example.org/"; }, r => { r.forcing.valid_end_utc = start; }, r => { r.display_bounds_xy_m.x_m = [0, 0]; }]) { const report = fixture(); mutate(report); reject(report); }
});
test("two layouts must have equal verified line resource and the same frozen geometry", () => {
  for (const mutate of [r => { r.layouts[0].total_length_m = 1999; }, r => { r.layouts[0].segments[0].end_xy_m[1] = 900; }, r => { r.layouts[0].id = "flanking"; }, r => { r.scenario.layouts = []; }, r => { r.layouts[0].outcomes[0].release_id = "other-release"; }, r => { r.method.barriers_modify_flow = true; }, r => { r.method.paths_integrated_once_per_release = false; }]) { const report = fixture(); mutate(report); reject(report); }
});
test("summary counts, unknown bounds and baseline reductions are derived from every release", () => {
  for (const mutate of [r => { r.layouts[0].summary.release_count = 5; }, r => { r.layouts[0].summary.entered_count = 0; }, r => { r.layouts[0].summary.protected_entry_count_bounds = [0, 0]; }, r => { r.layouts[0].summary.protected_entry_fraction_bounds = [1, 1]; }, r => { r.layouts[0].summary.entry_reduction_count_bounds_vs_baseline = [6, 6]; }, r => { r.baseline.summary.intercepted_count = 1; }]) { const report = fixture(); mutate(report); reject(report); }
});
test("recommendations cannot override a tie, select the worse count or change their basis", () => {
  const report = fixture(); report.recommendation.best_layout_id = "flanking"; reject(report);
  const tied = fixture(true); tied.recommendation.status = "BEST_LAYOUT"; tied.recommendation.best_layout_id = "central"; reject(tied);
  const invented = fixture(); invented.recommendation.comparison_basis = "visual impression"; reject(invented);
});
test("post-preview what-if design cannot be silently promoted to an independent experiment", () => {
  const report = fixture(); report.scenario.geometry_status = "fixed_pre_outcome_illustrative_hypothesis_not_optimized"; reject(report);
  const renamed = fixture(); renamed.scenario.design_status = "INDEPENDENT_TEST"; reject(renamed);
});
test("no-entry needs a complete horizon and a declared first event must match the drawn endpoint", () => {
  for (const mutate of [r => { r.layouts[0].outcomes[0].event = null; }, r => { r.layouts[0].outcomes[0].event.elapsed_s = 1200; }, r => { r.layouts[0].outcomes[0].event.segment_id = "unknown"; }, r => { r.layouts[0].outcomes[0].track_end_elapsed_s = 0; }, r => { r.layouts[0].outcomes[0].track[1].time_utc = start; }, r => { r.layouts[0].outcomes[0].track[1].eastward_m_s = NaN; }]) { const report = fixture(); mutate(report); reject(report); }
  const incomplete = fixture(true); incomplete.layouts[0].outcomes[0].forcing_status = "PARTIAL"; incomplete.layouts[0].outcomes[0].forcing_reason_code = "MISSING_CELL"; incomplete.layouts[0].outcomes[0].integrated_horizon_s = 10800; reject(incomplete);
});
function answer(report) { return { schema_version: 1, kind: "OCEAN_PREVENTION_INVESTIGATION", scope: "READ_ONLY_OCEAN_PREVENTION", provider: "chalk", scenario_id: report.scenario.id, action: "REPORT", live_model_response: true, explanation: "The central layout has fewer modeled entries in this hypothetical scenario. Real interception remains unmeasured.", evidence_ids: [`ocean-comparison:${report.report_sha256}`, `ocean-method:${report.method_sha256}`], snapshot_sha256: report.snapshot_sha256, method_sha256: report.method_sha256, scenario_sha256: report.scenario_sha256, report_sha256: report.report_sha256, research_report: report, store_written: false, physical_validation: false, hardware_actuation: false }; }
test("Chalk must cite the exact report, method and scenario and preserve the full numerical evidence", () => {
  const report = fixture(); validateOceanPreventionAnswer(answer(report), report);
  for (const mutate of [a => { a.snapshot_sha256 = "f".repeat(64); }, a => { a.scenario_id = "initial-proxy-v1"; }, a => { a.scenario_sha256 = "f".repeat(64); }, a => { a.report_sha256 = "f".repeat(64); }, a => { a.evidence_ids.pop(); }, a => { a.evidence_ids[1] = a.evidence_ids[0]; }, a => { a.evidence_ids[0] = "unrelated-case"; }, a => { a.store_written = true; }, a => { a.physical_validation = true; }, a => { a.live_model_response = false; }, a => { a.research_report.layouts[0].summary.entered_count = 0; }]) { const candidate = structuredClone(answer(report)); mutate(candidate); assert.throws(() => validateOceanPreventionAnswer(candidate, report)); }
});
test("a bounded unavailable STOP stays honest instead of masquerading as live success", () => {
  const report = fixture(), stopped = answer(report); Object.assign(stopped, { action: "STOP", live_model_response: false, evidence_ids: [], failure_code: "CHALK_DISABLED", explanation: "Chalk is not configured. The saved comparison remains available." });
  validateOceanPreventionAnswer(stopped, report);
  stopped.live_model_response = true; assert.throws(() => validateOceanPreventionAnswer(stopped, report));
});

// Render the actual TSX. No mock solver or live provider is substituted.
const require = createRequire(import.meta.url), loaded = new Map();
function component(path) {
  const file = resolve(path); if (loaded.has(file)) return loaded.get(file).exports;
  const mod = { exports: {} }; loaded.set(file, mod);
  const compiled = ts.transpileModule(readFileSync(file, "utf8"), { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
  new Function("require", "module", "exports", compiled)(name => {
    if (name.endsWith(".module.css")) return { __esModule: true, default: new Proxy({}, { get: (_, key) => String(key) }) };
    if (name === "next/link") return { __esModule: true, default: ({ children, ...props }) => React.createElement("a", props, children) };
    if (name.startsWith(".")) { const base = resolve(dirname(file), name), dependency = [base, `${base}.tsx`, `${base}.ts`].find(existsSync); if (dependency) return component(dependency); }
    return require(name);
  }, mod, mod.exports); return mod.exports;
}
const { OceanPreventionFigure, OceanPrevention, OceanResults, DEFAULT_OCEAN_VISIBILITY } = component("app/components/ocean-prevention.tsx");
const { OperatorProvider } = component("app/components/operator-provider.tsx");
const draw = (report = fixture(), visible = DEFAULT_OCEAN_VISIBILITY, releaseId = "all", frame = 0) => renderToStaticMarkup(React.createElement(OceanPreventionFigure, { report, visible, releaseId, frame, onToggle: () => assert.fail("Render must not mutate or call a provider") }));
const pathPoints = (html, layer) => [...(html.match(new RegExp(`data-ocean-layer="${layer}"[\\s\\S]*?</g></g>`))?.[0] ?? "").matchAll(/<polyline points="([^"]*)"/g)].map(m => m[1]);
const grid = html => html.match(/Plot grid: ([^<]+)/)?.[1];
test("the first view is concise, dynamic by default and offers only one explicit local comparison", () => {
  const html = renderToStaticMarkup(React.createElement(OceanPrevention, { api: "" }));
  assert.match(html, /Compare ocean layouts/); assert.match(html, /One changing-current comparison/); assert.match(html, /downstream-corridor-v2/); assert.match(html, /initial-proxy-v1/);
  assert.equal((html.match(/<svg/g) ?? []).length, 2); // two decorative button/title icons, no unloaded plot
  assert.equal(DEFAULT_OCEAN_VISIBILITY.baseline, false); assert.equal(DEFAULT_OCEAN_VISIBILITY.layoutA, true); assert.equal(DEFAULT_OCEAN_VISIBILITY.layoutB, true);
});
test("public results keep the real comparison controls but cannot offer sign-in or a live Chalk request", () => {
  const html = renderToStaticMarkup(React.createElement(OperatorProvider, null, React.createElement(OceanResults, { api: "/showcase", report: fixture(), readOnly: true })));
  assert.match(html, /Chalk unavailable in public showcase/);
  assert.match(html, /does not call a model or display a live Chalk response/);
  assert.match(html, /type="button" class="primary-button" disabled=""/);
  assert.doesNotMatch(html, /Sign in to use Chalk|href="\/login"|Ask Chalk about these layouts/);
  assert.equal((html.match(/type="checkbox"/g) ?? []).length, 6);
  assert.match(html, /Ocean comparison release/);
});
test("the combined figure exposes checkboxes and preserves coordinates when hiding a layout", () => {
  const report = fixture(), before = JSON.stringify(report), all = draw(report), a = draw(report, { ...DEFAULT_OCEAN_VISIBILITY, layoutB: false });
  assert.equal((all.match(/type="checkbox"/g) ?? []).length, 6);
  assert.equal((all.match(/viewBox="132 0 456 484"/g) ?? []).length, 1);
  assert.ok(pathPoints(all, "layoutA").length); assert.ok(pathPoints(all, "layoutB").length);
  assert.deepEqual(pathPoints(a, "layoutA"), pathPoints(all, "layoutA")); assert.doesNotMatch(a, /data-ocean-layer="layoutB"/); assert.equal(grid(a), grid(all)); assert.equal(JSON.stringify(report), before);
});
test("release selection retains the same equal-axis domain and full comparison denominator", () => {
  const report = fixture(), all = draw(report), selected = draw(report, undefined, "release-2");
  assert.equal(grid(all), grid(selected)); assert.match(selected, /data-release-id="release-2"/); assert.doesNotMatch(selected, /data-release-id="release-1"/);
  assert.equal(report.layouts[0].summary.release_count, 6); assert.match(selected, /All positions are simulated/);
});
test("all-hidden layers retain the scientific scale and make the empty view explicit", () => {
  const hidden = draw(fixture(), Object.fromEntries(Object.keys(DEFAULT_OCEAN_VISIBILITY).map(key => [key, false])));
  assert.match(hidden, /No layers selected/); assert.doesNotMatch(hidden, /data-ocean-layer=/); assert.equal(grid(hidden), grid(draw()));
});
test("current arrow time changes do not move paths or rescale their speed display", () => {
  const report = fixture(), visible = { ...DEFAULT_OCEAN_VISIBILITY, currents: true }, first = draw(report, visible, "all", 0), last = draw(report, visible, "all", 1);
  assert.deepEqual(pathPoints(first, "layoutA"), pathPoints(last, "layoutA")); assert.equal(grid(first), grid(last));
  assert.match(first, /data-ocean-layer="currents"/); assert.match(last, /2026-10-18 00:00 UTC/); assert.match(first, /clip-path=/);
});
test("endpoint symbols and hover descriptions distinguish modeled contact from measurement", () => {
  const html = draw(); assert.match(html, /data-outcome="IDEALIZED_INTERCEPTION"/); assert.match(html, /data-outcome="ENTERED_PROTECTED_ZONE"/);
  assert.match(html, /idealized capture/); assert.match(html, /protected-zone entry/); assert.match(html, /hypothetical release/); assert.match(html, /No measured waste, real reef boundary or measured protection/); assert.match(html, /stroke-dasharray="7 5"/);
});

test("the mobile plot viewport tightly frames unchanged scientific coordinates and both axis labels", () => {
  const html = draw(fixture(), { ...DEFAULT_OCEAN_VISIBILITY, currents: true });
  assert.match(html, /viewBox="132 0 456 484"/);
  for (const match of html.matchAll(/<polyline points="([^"]*)"/g)) {
    for (const point of match[1].split(" ")) {
      const [x, y] = point.split(",").map(Number);
      assert.ok(x >= 152 && x <= 568 && y >= 19 && y <= 435, `Path point ${point} stays inside the tight viewport`);
    }
  }
  assert.match(html, /<text x="360" y="454" text-anchor="middle"/);
  assert.match(html, /<text x="360" y="475" text-anchor="middle"/);
  assert.match(html, /<rect x="152" y="19" width="416" height="416"/);
});
