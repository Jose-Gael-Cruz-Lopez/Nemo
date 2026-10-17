import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import test from "node:test";
import ts from "typescript";

const require = createRequire(import.meta.url), loaded = new Map();
function moduleAt(path) {
  const file = resolve(path);
  if (file.endsWith(".json")) return JSON.parse(readFileSync(file, "utf8"));
  if (loaded.has(file)) return loaded.get(file).exports;
  const mod = { exports: {} }; loaded.set(file, mod);
  const source = ts.transpileModule(readFileSync(file, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
  new Function("require", "module", "exports", source)(name => {
    if (name.startsWith(".")) { const base = resolve(dirname(file), name); return moduleAt([base, `${base}.ts`, `${base}.json`].find(existsSync)); }
    return require(name);
  }, mod, mod.exports);
  return mod.exports;
}
const api = moduleAt("showcase/report.ts"), bundle = JSON.parse(readFileSync("showcase/ocean-reports.json", "utf8"));
const route = moduleAt("app/showcase/api/v1/research/ocean-prevention/route.ts");
const request = (query = "") => new Request(`https://public.example/showcase/api/v1/research/ocean-prevention${query}`);
const before = Date.parse("2026-10-17T18:00:00Z"), boundary = Date.parse("2026-10-18T00:00:00Z");

test("both public scenarios retain exact verified numerical outcomes and first-contact assumptions", () => {
  for (const id of api.SCENARIOS) {
    const { report } = api.readShowcaseReport(id, before);
    assert.equal(report.scenario.id, id);
    assert.equal(report.method.barriers_modify_flow, false);
    assert.equal(report.method.trajectory, "dynamic_current_advection_only");
    assert.equal(report.validation.physical_validation, false);
    assert.equal(report.validation.measured_entry_count, null);
    assert.deepEqual(report.layouts.map(layout => layout.summary.entered_count), id === "downstream-corridor-v2" ? [2, 4] : [0, 0]);
    assert.equal(report.recommendation.status, id === "downstream-corridor-v2" ? "BEST_LAYOUT" : "TIE");
  }
});
test("UTC expiry chooses a separately hashed archived representation without changing paths", () => {
  for (const id of api.SCENARIOS) {
    const forecast = api.readShowcaseReport(id, boundary).report;
    const archived = api.readShowcaseReport(id, boundary + 1).report;
    assert.equal(forecast.mode, "forecast_snapshot"); assert.equal(archived.mode, "archived_forecast_snapshot");
    assert.notEqual(forecast.report_sha256, archived.report_sha256);
    const strip = report => { const rest = structuredClone(report); delete rest.mode; delete rest.report_sha256; return rest; };
    assert.deepEqual(strip(forecast), strip(archived));
    assert.throws(() => api.readShowcaseReport(id, NaN));
  }
});
test("raw-byte integrity and the actual canonical report digest reject tampering", () => {
  const item = bundle.reports["downstream-corridor-v2"].forecast_snapshot;
  const original = api.verifyExport(item.report_json, item.bytes_sha256, item.report_sha256);
  assert.equal(original.report_sha256, item.report_sha256);
  assert.throws(() => api.verifyExport(`${item.report_json} `, item.bytes_sha256, item.report_sha256));
  const changed = `${item.report_json} `;
  assert.throws(() => api.verifyExport(changed, createHash("sha256").update(changed).digest("hex"), item.report_sha256), /report identity/);
  assert.throws(() => api.verifyExport(item.report_json, item.bytes_sha256, "0".repeat(64)));
});
test("public HTTP handler defaults to dynamic comparison, serves no-store and rejects ambiguous queries", async () => {
  const response = api.showcaseGet(request(), before);
  assert.equal(response.status, 200); assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.headers.get("x-tideward-scope"), "public-read-only-snapshot");
  assert.equal((await response.json()).scenario.id, "downstream-corridor-v2");
  for (const query of ["?scenario_id=unknown", "?scenario_id=", "?scenario_id=initial-proxy-v1&scenario_id=downstream-corridor-v2", "?provider_key=anything", "?scenario_id=initial-proxy-v1&other=1"]) assert.equal(api.showcaseGet(request(query), before).status, 422);
  assert.equal(api.showcaseGet(request(), NaN).status, 503);
  assert.equal((await api.showcaseGet(request("?scenario_id=initial-proxy-v1"), before).json()).recommendation.status, "TIE");
});
test("the actual Next route exposes only read-only GET and explicit blocked POST", async () => {
  assert.equal(route.runtime, "nodejs"); assert.equal(route.dynamic, "force-dynamic");
  assert.equal((await route.GET(request())).status, 200);
  const rejected = route.POST(); assert.equal(rejected.status, 405); assert.equal(rejected.headers.get("allow"), "GET, HEAD");
  assert.match((await rejected.json()).detail, /Provider calls, messages, camera and experiment writes are unavailable/);
  assert.deepEqual(Object.keys(route).sort(), ["GET", "POST", "dynamic", "runtime"]);
});
test("cloud-only routing cannot send API traffic to the local machine and local configuration is preserved", async () => {
  const previous = process.env.TIDEWARD_PUBLIC_SHOWCASE;
  try {
    for (const enabled of [false, true]) {
      process.env.TIDEWARD_PUBLIC_SHOWCASE = enabled ? "true" : "false";
      loaded.delete(resolve("next.config.ts"));
      const config = moduleAt("next.config.ts").default;
      assert.deepEqual(await config.redirects(), enabled ? ["/", "/workspace", "/login"].map(source => ({ source, destination: "/demo", permanent: false })) : []);
      assert.deepEqual(await config.rewrites(), enabled ? [] : [{ source: "/api/v1/:path*", destination: "http://127.0.0.1:8000/api/v1/:path*" }]);
    }
  } finally { if (previous === undefined) delete process.env.TIDEWARD_PUBLIC_SHOWCASE; else process.env.TIDEWARD_PUBLIC_SHOWCASE = previous; }
});
