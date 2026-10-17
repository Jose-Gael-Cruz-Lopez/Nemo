"use client";

import { BRAND_NAME } from "./brand";

import { useEffect, useId, useRef, useState } from "react";
import { Icon } from "./icons";
import styles from "./reef-briefing.module.css";

export type ReefBriefingProps = {
  api: string;
  caseId: string;
  evidenceId?: string;
  operatorToken: string;
  stopped: boolean;
};

type HeatPoint = {
  time_utc: string;
  degree_heating_week_c_weeks: number;
};
type SatelliteContext = {
  schema_version: number;
  data_origin: string;
  time_series: HeatPoint[];
  location: { latitude_deg: number; longitude_deg: number; nominal_resolution_km: number };
  period: { start_utc: string; end_utc: string };
  summary: {
    latest_dhw_c_weeks: number;
    change_c_weeks: number;
    bleaching_risk_threshold_c_weeks: number;
  };
  source_attribution: { used_in_source_ranking: false };
  provenance: {
    integrity_verified: true;
    attribution: string;
    metadata_url: string;
    source_url: string;
    method_url: string;
    sha256: string;
  };
};
type Briefing = {
  schema_version: number;
  text: string;
  case_id: string;
  source_evidence_id: string;
  source_report_hash: string;
  source_status: string;
  source_data_origin: string;
  script_hash: string;
  narration_method: string;
  satellite_used_in_source_ranking: false;
};
type Operation = "satellite" | "briefing" | "audio";
type RequestScope = { controller: AbortController | null; audioUrl: string | null };

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function finite(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}
function noaaUrl(value: unknown): value is string {
  if (typeof value !== "string") return false;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && (url.hostname === "noaa.gov" || url.hostname.endsWith(".noaa.gov"));
  } catch { return false; }
}
function satelliteReport(value: unknown): SatelliteContext {
  if (!record(value) || value.schema_version !== 1
    || value.data_origin !== "REAL_HISTORICAL_NOAA_SATELLITE_DERIVED"
    || !Array.isArray(value.time_series) || value.time_series.length !== 7
    || !value.time_series.every((point, index) => record(point)
      && point.time_utc === `2023-07-${String(index + 1).padStart(2, "0")}T12:00:00Z`
      && finite(point.degree_heating_week_c_weeks) && point.degree_heating_week_c_weeks >= 0
      && point.degree_heating_week_c_weeks <= 100)
    || !record(value.location) || !finite(value.location.latitude_deg)
    || !finite(value.location.longitude_deg) || !finite(value.location.nominal_resolution_km)
    || !record(value.period) || typeof value.period.start_utc !== "string" || typeof value.period.end_utc !== "string"
    || !record(value.summary) || !finite(value.summary.latest_dhw_c_weeks)
    || !finite(value.summary.change_c_weeks) || !finite(value.summary.bleaching_risk_threshold_c_weeks)
    || !record(value.source_attribution) || value.source_attribution.used_in_source_ranking !== false
    || !record(value.provenance) || value.provenance.integrity_verified !== true
    || typeof value.provenance.attribution !== "string" || typeof value.provenance.sha256 !== "string"
    || !noaaUrl(value.provenance.metadata_url) || !noaaUrl(value.provenance.source_url)
    || !noaaUrl(value.provenance.method_url)) {
    throw new Error("The satellite context has an unsupported or incomplete format.");
  }
  return value as SatelliteContext;
}
function briefingReport(value: unknown, caseId: string, evidenceId: string | undefined): Briefing {
  if (!record(value) || value.schema_version !== 1 || value.case_id !== caseId
    || value.source_evidence_id !== evidenceId || typeof value.text !== "string"
    || value.text.length < 1 || value.text.length > 2000
    || typeof value.script_hash !== "string" || !/^[a-f0-9]{64}$/.test(value.script_hash)
    || typeof value.source_report_hash !== "string" || !/^[a-f0-9]{64}$/.test(value.source_report_hash)
    || !["ranked", "unknown", "invalid"].includes(String(value.source_status))
    || !["SYNTHETIC", "MEASURED_TANK", "UNVERIFIED"].includes(String(value.source_data_origin))
    || value.narration_method !== "deterministic_frozen_evidence_template"
    || value.satellite_used_in_source_ranking !== false) {
    throw new Error("The saved evidence changed or the briefing is incomplete. Refresh the case and try again.");
  }
  return value as Briefing;
}
function apiError(value: unknown, status: number): string {
  if (record(value)) {
    if (typeof value.detail === "string") return value.detail.slice(0, 500);
    if (typeof value.message === "string") return value.message.slice(0, 500);
  }
  return `Request failed (${status}). The saved text and source evidence remain available.`;
}
async function jsonResponse(response: Response): Promise<unknown> {
  const text = await response.text();
  if (text.length > 40_000) throw new Error("The API response exceeded this small context view's size limit.");
  let value: unknown;
  try { value = JSON.parse(text); }
  catch { throw new Error(`The API returned an unreadable response (${response.status}). Check the backend connection.`); }
  if (!response.ok) throw new Error(apiError(value, response.status));
  return value;
}

function HeatChart({ data }: { data: SatelliteContext }) {
  const id = useId();
  const points = data.time_series;
  const maximum = Math.max(6, Math.ceil(Math.max(...points.map(point => point.degree_heating_week_c_weeks)) / 2) * 2);
  const position = (point: HeatPoint, index: number) => [44 + index * 70, 135 - point.degree_heating_week_c_weeks / maximum * 100];
  const thresholdY = 135 - data.summary.bleaching_risk_threshold_c_weeks / maximum * 100;
  return <figure className={styles.chart}>
    <svg viewBox="0 0 510 176" role="img" aria-labelledby={`${id}-title ${id}-description`}>
      <title id={`${id}-title`}>Historical Florida Keys accumulated heat stress, July first to seventh, twenty twenty-three</title>
      <desc id={`${id}-description`}>{points.map(point => `${point.time_utc.slice(0, 10)}: ${point.degree_heating_week_c_weeks.toFixed(2)} degree Celsius weeks`).join("; ")}. This historical satellite context is not used in tank source ranking.</desc>
      <text x="44" y="17" fontSize="10" fill="#687782">DHW (°C-weeks)</text>
      {[0, maximum / 3, maximum * 2 / 3, maximum].map(tick => {
        const y = 135 - tick / maximum * 100;
        return <g key={tick}><line x1="44" y1={y} x2="464" y2={y} stroke="#e8e8ee" /><text x="33" y={y + 3} fontSize="9" fill="#687782" textAnchor="end">{tick.toFixed(0)}</text></g>;
      })}
      <line x1="44" y1={thresholdY} x2="464" y2={thresholdY} stroke="#b2935c" strokeDasharray="5 4" />
      <text x="464" y={thresholdY - 6} textAnchor="end" fontSize="9" fill="#927242">Bleaching-risk level ({data.summary.bleaching_risk_threshold_c_weeks.toFixed(0)})</text>
      <polyline points={points.map((point, index) => position(point, index).join(",")).join(" ")} fill="none" stroke="#087fac" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      {points.map((point, index) => {
        const [x, y] = position(point, index);
        return <g key={point.time_utc}><circle cx={x} cy={y} r="3.5" fill="#087fac" stroke="white" strokeWidth="1"><title>{point.time_utc.slice(0, 10)}: {point.degree_heating_week_c_weeks.toFixed(2)} °C-weeks</title></circle><text x={x} y="155" textAnchor="middle" fontSize="9" fill="#687782">{index + 1} Jul</text></g>;
      })}
    </svg>
    <figcaption>Accumulated thermal stress, not confirmed coral bleaching. One approximately {data.location.nominal_resolution_km} km grid cell; no tank or plastic-source measurement.</figcaption>
  </figure>;
}

function ReefBriefingSession({ api, caseId, evidenceId, operatorToken, stopped }: ReefBriefingProps) {
  const [satellite, setSatellite] = useState<SatelliteContext | null>(null);
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [audioUrl, setAudioUrl] = useState("");
  const [busy, setBusy] = useState<Operation | null>(null);
  const [satelliteError, setSatelliteError] = useState("");
  const [briefingError, setBriefingError] = useState("");
  const [voiceError, setVoiceError] = useState("");
  const resources = useRef<RequestScope>({ controller: null, audioUrl: null });
  const endpoint = api.replace(/\/$/, "") + "/api/v1";
  useEffect(() => {
    const scope = resources.current;
    return () => {
      scope.controller?.abort();
      if (scope.audioUrl) URL.revokeObjectURL(scope.audioUrl);
    };
  }, []);

  async function run(operation: Operation) {
    const scope = resources.current;
    if (scope.controller) return;
    if (operation !== "satellite" && (!caseId || !evidenceId || stopped)) return;
    if (operation === "audio" && (!briefing || !operatorToken || scope.audioUrl)) return;
    const controller = new AbortController();
    scope.controller = controller;
    setBusy(operation);
    if (operation === "satellite") setSatelliteError("");
    else if (operation === "briefing") {
      setBriefingError(""); setVoiceError("");
      if (scope.audioUrl) URL.revokeObjectURL(scope.audioUrl);
      scope.audioUrl = null; setAudioUrl("");
    } else setVoiceError("");
    const current = () => scope.controller === controller && !controller.signal.aborted;
    try {
      if (operation === "satellite") {
        const response = await fetch(`${endpoint}/research/satellite-context`, { cache: "no-store", signal: controller.signal });
        const result = satelliteReport(await jsonResponse(response));
        if (current()) setSatellite(result);
      } else if (operation === "briefing") {
        const response = await fetch(`${endpoint}/cases/${encodeURIComponent(caseId)}/briefing`, { cache: "no-store", signal: controller.signal });
        const result = briefingReport(await jsonResponse(response), caseId, evidenceId);
        if (current()) setBriefing(result);
      } else if (briefing) {
        const response = await fetch(`${endpoint}/cases/${encodeURIComponent(caseId)}/briefing/audio`, {
          method: "POST", cache: "no-store", signal: controller.signal,
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${operatorToken}` },
          body: "{}",
        });
        if (!response.ok || response.headers.get("content-type")?.split(";", 1)[0].trim() !== "audio/mpeg") {
          const value = await jsonResponse(response);
          throw new Error(apiError(value, response.status));
        }
        if (response.headers.get("X-Evidence-Id") !== briefing.source_evidence_id
          || response.headers.get("X-Script-Hash") !== briefing.script_hash) {
          throw new Error("The audio does not match the previewed evidence. Reload the briefing before trying again.");
        }
        const audio = await response.blob();
        if (audio.size < 1 || audio.size > 2_000_000) throw new Error("The audio response was empty or exceeded its size limit. The transcript remains available.");
        if (!current()) return;
        const url = URL.createObjectURL(audio);
        scope.audioUrl = url; setAudioUrl(url);
      }
    } catch (cause) {
      if (current()) {
        const message = cause instanceof Error ? cause.message : "The request could not be completed.";
        if (operation === "satellite") setSatelliteError(message);
        else if (operation === "briefing") setBriefingError(message);
        else setVoiceError(message);
      }
    } finally {
      if (current()) { scope.controller = null; setBusy(null); }
    }
  }

  return <div className={styles.stack}>
    <section className="card" aria-label="Historical satellite reef context">
      <div className={`card-header ${styles.header}`}><div><h2 className="card-title"><Icon name="wave" />Satellite reef context</h2><p className="card-subtitle">Florida Keys · 1–7 July 2023 · independent historical data</p></div><button className="secondary-button" disabled={busy !== null} onClick={() => void run("satellite")}><Icon name="wave" />{busy === "satellite" ? "Loading context…" : satellite ? "Reload context" : "Load satellite context"}</button></div>
      <div className="card-body">
        <p className={styles.scope}><strong>Historical context only.</strong> These heat-stress values are not this tank&apos;s conditions and never change the source ranking.</p>
        {satelliteError && <div className="notice error" role="alert">{satelliteError}</div>}
        {busy === "satellite" && <p role="status" className="settings-note">Reading the pinned, seven-day NOAA satellite sample…</p>}
        {satellite ? <>
          <div className={styles.metrics}><span><strong>{satellite.summary.latest_dhw_c_weeks.toFixed(2)}</strong> °C-weeks on 7 July 2023</span><span className="pill green">Integrity verified</span></div>
          <HeatChart data={satellite} />
          <div className={`heading-actions ${styles.links}`}><a className="card-link" href={satellite.provenance.metadata_url} target="_blank" rel="noreferrer">NOAA provenance <Icon name="arrow" /></a><a className="card-link" href={satellite.provenance.source_url} target="_blank" rel="noreferrer">Source CSV <Icon name="arrow" /></a><a className="card-link" href={satellite.provenance.method_url} target="_blank" rel="noreferrer">What DHW means <Icon name="arrow" /></a></div>
          <details className="details-panel"><summary>Daily measurements and provenance</summary><p className="settings-note">{satellite.provenance.attribution}. Grid cell: {satellite.location.latitude_deg.toFixed(3)}°, {satellite.location.longitude_deg.toFixed(3)}°.</p><div className="table-scroll"><table className="metrics-table"><caption className="sr-only">Seven historical daily Degree Heating Week measurements</caption><thead><tr><th>Date (UTC)</th><th>DHW (°C-weeks)</th></tr></thead><tbody>{satellite.time_series.map(point => <tr key={point.time_utc}><th>{point.time_utc.slice(0, 10)}</th><td>{point.degree_heating_week_c_weeks.toFixed(2)}</td></tr>)}</tbody></table></div><p className="settings-note">Pinned sample SHA-256</p><code className="evidence-id">{satellite.provenance.sha256}</code></details>
        </> : <p className="settings-note">Load seven real historical observations from the collected NOAA sample. This makes no live-provider request.</p>}
      </div>
    </section>

    <section className="card" aria-label="Evidence voice briefing">
      <div className={`card-header ${styles.header}`}><div><h2 className="card-title"><Icon name="file" />Evidence briefing</h2><p className="card-subtitle">A fixed script from the saved source report, with separate satellite context.</p></div><button className="secondary-button" disabled={busy !== null || !caseId || !evidenceId || stopped} onClick={() => void run("briefing")}><Icon name="file" />{busy === "briefing" ? "Reading briefing…" : briefing ? "Refresh briefing text" : "Read briefing text"}</button></div>
      <div className="card-body">
        {stopped ? <p className={styles.scope}>This case is stopped. Briefing requests and voice generation are disabled.</p> : !evidenceId ? <p className="settings-note">Compute source support for this observation before opening its briefing.</p> : <p className="settings-note">Read the text first. Generating Grok narration makes one explicit speech request; audio never plays automatically.</p>}
        {briefingError && <div className="notice error" role="alert">{briefingError}</div>}
        {busy === "briefing" && <p className="settings-note" role="status">Reading the current frozen evidence script…</p>}
        {briefing && <>
          <div className={styles.badges}><span className="pill">{briefing.source_data_origin === "SYNTHETIC" ? "Synthetic tabletop case" : briefing.source_data_origin === "MEASURED_TANK" ? "Measured tabletop case" : "Unverified evidence origin"}</span><span className="pill">Source result: {briefing.source_status === "unknown" ? "Unknown" : briefing.source_status === "invalid" ? "Invalid" : "Ranked"}</span></div>
          <p className={styles.transcript}>{briefing.text}</p>
          <div className={styles.voiceActions}><button className="secondary-button" disabled={busy !== null || !operatorToken || stopped || Boolean(audioUrl)} onClick={() => void run("audio")}><Icon name="play" />{busy === "audio" ? "Generating narration…" : audioUrl ? "Narration ready" : "Generate Grok narration"}</button><span className="settings-note">{!operatorToken ? "Connect operator access to request audio." : audioUrl ? "Use the player to listen or replay." : "The text remains usable if speech is unavailable."}</span></div>
          {busy === "audio" && <p className="settings-note" role="status">Generating speech from this exact script. It does not change the source analysis.</p>}
          {voiceError && <div className="notice error" role="alert">{voiceError}</div>}
          {audioUrl && <div className={styles.player}><audio controls preload="none" src={audioUrl} aria-label={`${BRAND_NAME} evidence briefing`} onError={() => setVoiceError("The browser could not play this audio. The full briefing text is still available above.")}>Your browser does not support audio playback. Read the transcript above.</audio><p className="settings-note">Grok speech from a deterministic script; no generated source claims, hardware action or messaging.</p></div>}
          <details className="details-panel"><summary>Script evidence</summary><p className="settings-note">Frozen source evidence</p><code className="evidence-id">{briefing.source_evidence_id}</code><p className="settings-note">Script SHA-256</p><code className="evidence-id">{briefing.script_hash}</code></details>
        </>}
      </div>
    </section>
  </div>;
}

export function ReefBriefing(props: ReefBriefingProps) {
  // A changed case, evidence, API, or STOP state disposes requests and audio together.
  return <ReefBriefingSession key={JSON.stringify([props.api, props.caseId, props.evidenceId ?? null, props.stopped])} {...props} />;
}
