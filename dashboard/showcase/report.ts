import { createHash } from "node:crypto";
import bundle from "./ocean-reports.json";
import { validateOceanPrevention } from "../app/components/ocean-prevention-state";

export const SHOWCASE_PROVENANCE = { generatedAt: bundle.generated_at_utc, sourceCommit: bundle.git_head_at_export };
export const SCENARIOS = ["downstream-corridor-v2", "initial-proxy-v1"] as const;
type Scenario = (typeof SCENARIOS)[number];
const sha = (raw: string) => createHash("sha256").update(raw).digest("hex");

/** Preserve Python's exact canonical number spellings when verifying its digest. */
export function verifyExport(raw: string, byteHash: string, reportHash: string) {
  if (Buffer.byteLength(raw) > 750_000 || sha(raw) !== byteHash) throw new Error("Invalid public snapshot bytes");
  const report = validateOceanPrevention(JSON.parse(raw));
  const entry = `,"report_sha256":"${report.report_sha256}"`;
  if (report.report_sha256 !== reportHash || raw.split(entry).length !== 2 || sha(raw.replace(entry, "")) !== reportHash) throw new Error("Invalid public report identity");
  return report;
}

export function readShowcaseReport(scenarioId: string, now = Date.now()) {
  if (!SCENARIOS.includes(scenarioId as Scenario) || !Number.isFinite(now)) throw new Error("Unsupported public scenario or clock");
  const variants = bundle.reports[scenarioId as Scenario];
  const first = variants.forecast_snapshot;
  const forecast = verifyExport(first.report_json, first.bytes_sha256, first.report_sha256);
  const mode = now > Date.parse(forecast.forcing.valid_end_utc) ? "archived_forecast_snapshot" : "forecast_snapshot";
  const selected = variants[mode];
  const report = verifyExport(selected.report_json, selected.bytes_sha256, selected.report_sha256);
  if (report.mode !== mode || report.scenario.id !== scenarioId) throw new Error("Public snapshot selection changed");
  return { raw: selected.report_json, report };
}

export function showcaseGet(request: Request, now = Date.now()) {
  const query = new URL(request.url).searchParams;
  const ids = query.getAll("scenario_id");
  const id = ids[0] ?? SCENARIOS[0];
  if ([...query.keys()].some(key => key !== "scenario_id") || ids.length > 1 || !SCENARIOS.includes(id as Scenario)) {
    return Response.json({ detail: "Choose one of the two fixed public scenarios." }, { status: 422, headers: { "Cache-Control": "no-store" } });
  }
  try {
    return new Response(readShowcaseReport(id, now).raw, { headers: {
      "Content-Type": "application/json", "Cache-Control": "no-store",
      "X-Tideward-Scope": "public-read-only-snapshot", "X-Tideward-Exported-At": bundle.generated_at_utc,
    } });
  } catch {
    return Response.json({ detail: "The public snapshot failed its integrity checks." }, { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}

export function showcaseWriteBlocked() {
  return Response.json({ detail: "This public showcase is read-only. Provider calls, messages, camera and experiment writes are unavailable." }, { status: 405, headers: { Allow: "GET, HEAD", "Cache-Control": "no-store" } });
}
