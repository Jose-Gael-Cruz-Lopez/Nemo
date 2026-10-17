"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import Image from "next/image";
import { Icon, type IconName } from "./components/icons";
import { SourceMap, type SourceProfile } from "./components/source-map";
import { RealDataLab } from "./components/real-data-lab";
import { ReefBriefing } from "./components/reef-briefing";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
type View = "overview" | "investigations" | "camera" | "data" | "settings";
type Case = { id: string; profile_id: string; mode: string; state: string; evidence_id: string | null; points: { x_cm: number; y_cm: number }[]; endpoint?: { x_cm: number; y_cm: number; retained: boolean } | null };
type Evidence = { id: string; status: string; relative_support: Record<string, number>; reason_codes?: string[]; inference_mode?: string; [key: string]: unknown };
type Readiness = { ready: boolean; connection_verified: boolean; reasons: string[] };
type Status = { camera: { fresh: boolean; running: boolean; session_id: string | null; width: number | null; height: number | null }; chalk: Readiness; photon: Readiness; operator_configured: boolean };
type Investigation = { action: string; explanation: string; live_model_response?: boolean; evidence_ids: string[]; source_report?: Evidence; trace?: unknown[] };
type ManualAction = { id: string; case_id: string; evidence_id: string; state: string; expires_at: number; created_at: number; outcome?: { outcome: string; recovered_count: number; note: string } };
const VIEWS: { id: View; label: string; icon: IconName }[] = [
  { id: "overview", label: "Overview", icon: "overview" },
  { id: "investigations", label: "Investigations", icon: "cases" },
  { id: "camera", label: "Camera", icon: "camera" },
  { id: "data", label: "Data lab", icon: "wave" },
  { id: "settings", label: "Settings", icon: "settings" },
];

function Pill({ children, tone = "neutral" }: { children: ReactNode; tone?: string }) {
  return <span className={`pill ${tone}`}>{children}</span>;
}
function caseKind(item: Case) { return item.endpoint ? "Retained endpoint" : "Observed trajectory"; }
function readableReason(reason: string) { return reason.toLowerCase().replaceAll("_", " "); }
function errorMessage(cause: unknown) { return cause instanceof Error ? cause.message : String(cause); }
function isAbort(cause: unknown) { return cause instanceof DOMException && cause.name === "AbortError"; }
type RequestOptions = { signal?: AbortSignal; independent?: boolean };
type CompletionNotice = { message: string; tone: "success" | "info" };
function investigationNotice(result: Investigation): CompletionNotice {
  return result.live_model_response
    ? { message: "Chalk returned a live model investigation. Review its explanation and tool trace below.", tone: "success" }
    : { message: "Chalk did not run a live model. Review its connection status below; saved source evidence remains available.", tone: "info" };
}
class ApiError extends Error {
  constructor(message: string, readonly status: number) { super(message); this.name = "ApiError"; }
}
function apiError(detail: unknown, status: number) {
  if (typeof detail === "string") return detail.slice(0, 700);
  if (Array.isArray(detail)) {
    const fields = detail.slice(0, 6).flatMap(item => {
      if (!item || typeof item !== "object") return [];
      const location = Array.isArray(item.loc) ? item.loc.filter((part: unknown) => part !== "body" && (typeof part === "string" || typeof part === "number")).map((part: string | number) => String(part).slice(0, 70)).join(".") : "request";
      return [`${location || "request"}: ${typeof item.msg === "string" ? item.msg.slice(0, 130) : "Invalid value"}`];
    });
    if (fields.length) return `Check the request fields. ${fields.join("; ")}${detail.length > 6 ? `; and ${detail.length - 6} more. See the API reference for the full schema.` : "."}`;
  }
  return `Request failed (${status}). Review the fields and try again.`;
}
function parseRequestJson(text: string, label: string): Record<string, unknown> {
  let value: unknown;
  try { value = JSON.parse(text); }
  catch { throw new Error(`${label} needs valid JSON. Use double quotes around field names and text, remove trailing commas, and close every bracket.`); }
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} must be a JSON object enclosed in braces, with the fields shown in the API reference.`);
  return value as Record<string, unknown>;
}
function SourceReport({ evidence }: { evidence: Evidence | null }) {
  return <aside className="evidence-panel" aria-live="polite">
    <div className="evidence-heading"><h3>Source support</h3>{evidence && <Pill tone={evidence.status === "ranked" ? "purple" : evidence.status === "unknown" ? "amber" : "red"}>{evidence.status === "unknown" ? "Unknown" : evidence.status === "ranked" ? "Ranked" : "Invalid"}</Pill>}</div>
    {evidence ? <>
      <p className="card-subtitle">Relative support among the candidate sources.</p>
      <div className="source-scores">{Object.entries(evidence.relative_support ?? {}).map(([source, support]) => <div className="score-row" key={source}>
        <span>Source {source}</span><meter className="score-track" min={0} max={1} value={support} aria-label={`Relative support for source ${source}`} /><strong>{(support * 100).toFixed(1)}%</strong>
      </div>)}</div>
      {evidence.reason_codes?.length ? <ul className="reason-list">{evidence.reason_codes.map(reason => <li key={reason}>{readableReason(reason)}</li>)}</ul> : <p className="card-subtitle">Based on the saved observation and frozen transport model.</p>}
      <p className="settings-note">These values are not geographic probabilities.</p>
      <code className="evidence-id">{evidence.id}</code>
    </> : <div className="empty-state"><Icon name="file" /><p>No report yet</p><span>Compute source support to compare this observation with the candidate sources.</span></div>}
  </aside>;
}

export default function Home() {
  const [view, setView] = useState<View>("overview");
  const [query, setQuery] = useState("");
  const [token, setToken] = useState("");
  const [status, setStatus] = useState<Status | null>(null);
  const [profiles, setProfiles] = useState<SourceProfile[]>([]);
  const [cases, setCases] = useState<Case[]>([]);
  const [selected, setSelected] = useState("");
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [answer, setAnswer] = useState<Investigation | null>(null);
  const [question, setQuestion] = useState("Which candidate sources fit this evidence, and what remains uncertain?");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [noticeTone, setNoticeTone] = useState<"success" | "info">("success");
  const [connectionError, setConnectionError] = useState("");
  const [observationType, setObservationType] = useState("trajectory");
  const [busy, setBusy] = useState("");
  const [taskCaseId, setTaskCaseId] = useState("");
  const [device, setDevice] = useState(0);
  const [clock, setClock] = useState(0);
  const [calibration, setCalibration] = useState("");
  const [profileJson, setProfileJson] = useState("");
  const [calibrationId, setCalibrationId] = useState("");
  const [flowJson, setFlowJson] = useState("");
  const [setupResult, setSetupResult] = useState<unknown>(null);
  const [analysis, setAnalysis] = useState<unknown>(null);
  const [actionId, setActionId] = useState("");
  const [actionState, setActionState] = useState("");
  const [caseActions, setCaseActions] = useState<ManualAction[]>([]);
  const [actionReadError, setActionReadError] = useState("");
  const [manualOutcome, setManualOutcome] = useState("");
  const [recoveredCount, setRecoveredCount] = useState(0);
  const [outcomeNote, setOutcomeNote] = useState("");
  const [physicalConfirmed, setPhysicalConfirmed] = useState(false);
  const [recordProfileId, setRecordProfileId] = useState("");
  const [tokenDraft, setTokenDraft] = useState("");
  const [stopping, setStopping] = useState(false);
  const operatorDialog = useRef<HTMLDialogElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  const actionRun = useRef(0);
  const actionController = useRef<AbortController | null>(null);
  const stoppingRef = useRef(false);
  const refreshRun = useRef(0);
  const selectedRef = useRef("");

  function navigate(nextView: View) {
    setView(nextView);
    const route = `#${nextView}${selectedRef.current ? `?case=${encodeURIComponent(selectedRef.current)}` : ""}`;
    if (window.location.hash !== route) window.history.pushState(null, "", route);
    window.scrollTo({ top: 0, behavior: "auto" });
  }
  function selectCase(id: string, internal = false) {
    if (!internal && (actionController.current || stoppingRef.current)) return;
    selectedRef.current = id;
    window.history.replaceState(null, "", `#${view}?case=${encodeURIComponent(id)}`);
    setSelected(id); setEvidence(null); setAnswer(null); setAnalysis(null); setActionId(""); setActionState("");
    setCaseActions([]); setActionReadError(""); setManualOutcome(""); setRecoveredCount(0); setOutcomeNote(""); setPhysicalConfirmed(false);
    setError(""); setNotice("");
  }
  function openCase(id: string, internal = false) { selectCase(id, internal); navigate("investigations"); }
  function openOperator() {
    setTokenDraft(token); operatorDialog.current?.showModal();
  }
  const request = useCallback(async <T,>(path: string, body?: unknown, options: RequestOptions = {}): Promise<T> => {
    const signal = options.signal ?? (options.independent ? undefined : body !== undefined ? actionController.current?.signal : undefined);
    const response = await fetch(API + "/api/v1" + path, {
      method: body === undefined ? "GET" : "POST", cache: "no-store",
      headers: { ...(body === undefined ? {} : { "Content-Type": "application/json" }), ...(token ? { Authorization: "Bearer " + token } : {}) },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
    const raw = await response.text();
    let data: { detail?: unknown } = {};
    try { data = raw ? JSON.parse(raw) : {}; }
    catch { throw new ApiError(`The API returned an unreadable response (${response.status}). Check the backend terminal.`, response.status); }
    signal?.throwIfAborted();
    if (!response.ok) throw new ApiError(apiError(data.detail, response.status), response.status);
    return data as T;
  }, [token]);
  const refresh = useCallback(async (signal?: AbortSignal) => {
    const run = ++refreshRun.current;
    const [nextStatus, nextProfiles, nextCases] = await Promise.all([request<Status>("/status", undefined, { signal }), request<SourceProfile[]>("/profiles", undefined, { signal }), request<Case[]>("/cases", undefined, { signal })]);
    if (signal?.aborted || run !== refreshRun.current) return;
    setStatus(nextStatus); setProfiles(nextProfiles); setCases(nextCases); setConnectionError("");
  }, [request]);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function tick() {
      try { await refresh(controller.signal); }
      catch (cause) { if (!controller.signal.aborted) setConnectionError(errorMessage(cause)); }
      if (!controller.signal.aborted) { setClock(Date.now()); timer = setTimeout(tick, 3000); }
    }
    void tick();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [refresh]);
  useEffect(() => {
    const controller = new AbortController();
    if (selected) request<Evidence>(`/cases/${encodeURIComponent(selected)}/evidence`, undefined, { signal: controller.signal }).then(result => { if (!controller.signal.aborted && selectedRef.current === selected) setEvidence(result); }).catch(cause => {
      if (!controller.signal.aborted && !(cause instanceof ApiError && cause.status === 404)) setError(errorMessage(cause));
    });
    return () => controller.abort();
  }, [selected, request]);
  useEffect(() => {
    if (!selected || busy || stopping) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function tick() {
      try {
        const tasks = await request<ManualAction[]>(`/cases/${encodeURIComponent(selected)}/actions`, undefined, { signal: controller.signal });
        if (controller.signal.aborted || selectedRef.current !== selected) return;
        setCaseActions(tasks); setActionReadError("");
        const current = tasks.find(task => ["proposed", "awaiting_human"].includes(task.state)) ?? tasks[0];
        setActionId(current?.id ?? ""); setActionState(current?.state ?? "");
      } catch (cause) { if (!controller.signal.aborted) setActionReadError(errorMessage(cause)); }
      if (!controller.signal.aborted) timer = setTimeout(tick, 3000);
    }
    void tick();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [selected, request, busy, stopping]);
  useEffect(() => () => { actionController.current?.abort(); }, []);
  useEffect(() => {
    function restoreLocation() {
      if (actionController.current || stoppingRef.current) return;
      const [route, search = ""] = window.location.hash.slice(1).split("?");
      const nextView = VIEWS.find(item => item.id === route)?.id;
      if (nextView) setView(nextView);
      const id = new URLSearchParams(search).get("case") ?? "";
      if (id.length <= 200 && id !== selectedRef.current) {
        selectedRef.current = id; setSelected(id); setEvidence(null); setAnswer(null); setAnalysis(null);
        setActionId(""); setActionState(""); setCaseActions([]); setActionReadError("");
        setManualOutcome(""); setRecoveredCount(0); setOutcomeNote(""); setPhysicalConfirmed(false);
      }
    }
    restoreLocation();
    window.addEventListener("popstate", restoreLocation);
    window.addEventListener("hashchange", restoreLocation);
    return () => { window.removeEventListener("popstate", restoreLocation); window.removeEventListener("hashchange", restoreLocation); };
  }, []);
  useEffect(() => {
    function focusSearch(event: KeyboardEvent) {
      const target = event.target as HTMLElement;
      if (event.key === "/" && !event.ctrlKey && !event.metaKey && !["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName) && !target.isContentEditable && !operatorDialog.current?.open) {
        event.preventDefault(); searchInput.current?.focus();
      }
    }
    window.addEventListener("keydown", focusSearch);
    return () => window.removeEventListener("keydown", focusSearch);
  }, []);
  async function perform(name: string, job: () => Promise<void | CompletionNotice>, caseId = "") {
    if (actionController.current || stoppingRef.current) return;
    if (!token) { openOperator(); return; }
    const run = ++actionRun.current;
    const controller = new AbortController();
    actionController.current = controller;
    setBusy(name); setTaskCaseId(caseId); setError(""); setNotice("");
    try {
      const completion = await job();
      if (run !== actionRun.current || controller.signal.aborted) return;
      await refresh(controller.signal).catch(cause => { if (!controller.signal.aborted) setConnectionError(errorMessage(cause)); });
      if (run === actionRun.current) { setNoticeTone(completion?.tone ?? "success"); setNotice(completion?.message ?? `${name} complete.`); }
    }
    catch (cause) {
      if (run === actionRun.current && !isAbort(cause)) {
        setError(errorMessage(cause));
        if (cause instanceof ApiError && cause.status === 401) openOperator();
      }
    }
    finally { if (run === actionRun.current) { actionController.current = null; setBusy(""); setTaskCaseId(""); } }
  }
  function performCase(name: string, job: () => Promise<void | CompletionNotice>) { return perform(name, job, selected); }
  function loadDemo() {
    if (!token) { openOperator(); return; }
    void perform("Loading synthetic observations", async () => {
      const data = await request<{ cases: { case: Case }[] }>("/demo/load", {});
      if (data.cases[0]) {
        const id = data.cases[0].case.id;
        selectedRef.current = id; setSelected(id); setEvidence(null); setAnswer(null); setAnalysis(null); setActionId(""); setActionState(""); navigate("investigations");
        setCaseActions([]); setActionReadError(""); setManualOutcome(""); setRecoveredCount(0); setOutcomeNote(""); setPhysicalConfirmed(false);
      }
    });
  }
  const activeCase = cases.find(item => item.id === selected);
  const profile = profiles.find(item => item.id === activeCase?.profile_id);
  const filteredCases = cases.filter(item => `${item.id} ${item.mode} ${item.state} ${caseKind(item)}`.toLowerCase().includes(query.toLowerCase().trim()));
  const measuredProfiles = profiles.filter(item => item.data_origin === "MEASURED_TANK");
  const caseStopped = activeCase?.state === "STOPPED" || activeCase?.state === "RECOVERING";
  const currentAction = caseActions.find(item => item.id === actionId);
  const actionExpired = currentAction ? currentAction.expires_at * 1000 <= clock : false;
  const validOutcome = ["manual_recovered", "failed", "uncertain"].includes(manualOutcome) && Number.isInteger(recoveredCount) && recoveredCount >= 0 && recoveredCount <= 20 && (manualOutcome !== "manual_recovered" || recoveredCount > 0) && !!outcomeNote.trim() && physicalConfirmed;
  const locked = !!busy || !token || stopping;
  const connected = status !== null && !connectionError;
  const currentView = VIEWS.find(item => item.id === view)!;
  const reportCount = cases.filter(item => item.evidence_id).length;
  const cameraLabel = status ? (status.camera.fresh ? "Live" : status.camera.running ? "Stale" : "Off") : "Checking";
  async function stopCase(caseId = selected) {
    if (!token) { openOperator(); return; }
    if (!caseId || stoppingRef.current) return;
    stoppingRef.current = true; setStopping(true);
    ++actionRun.current; actionController.current?.abort(); actionController.current = null;
    setBusy("Stopping software tasks"); setError(""); setAnswer(null); setAnalysis(null);
    try {
      await request(`/cases/${encodeURIComponent(caseId)}/stop`, {}, { independent: true, signal: AbortSignal.timeout(8000) });
      await refresh();
      setNoticeTone("success"); setNotice("Software tasks stopped for this observation. The pump remains powered through its original cord.");
    } catch (cause) { setError(`Stop was not confirmed. ${errorMessage(cause)}`); }
    finally { stoppingRef.current = false; setStopping(false); setBusy(""); setTaskCaseId(""); }
  }

  return <div className="app-shell">
    <a className="sr-only skip-link" href="#workspace-main">Skip to workspace</a>
    <aside className="sidebar" aria-label="Workspace navigation">
      <button className="brand" onClick={() => navigate("overview")} aria-label="ReefTrace overview"><span className="brand-symbol"><Icon name="wave" /></span>ReefTrace</button>
      <div className="workspace-switch"><span className="workspace-avatar">R</span><div className="workspace-name"><strong>ReefTrace team</strong><span>Tank experiment</span></div></div>
      <div className="sidebar-section">Workspace</div>
      <nav>{VIEWS.slice(0, 4).map(item => <button className="nav-item" key={item.id} aria-current={view === item.id ? "page" : undefined} onClick={() => navigate(item.id)}><Icon name={item.icon} /><span className="nav-label">{item.label}</span>{item.id === "investigations" && status && <span className="nav-count">{cases.length}</span>}</button>)}</nav>
      <div className="sidebar-section">Manage</div>
      <button className="nav-item" aria-current={view === "settings" ? "page" : undefined} onClick={() => navigate("settings")}><Icon name="settings" /><span>Settings</span></button>
      <button className="nav-item" onClick={openOperator}><Icon name="key" /><span>Operator access</span></button>
      <div className="sidebar-bottom"><div className="local-indicator"><span className={`status-dot ${connected ? "is-live" : "is-off"}`} />{connectionError ? "Local API unavailable" : connected ? "Local API connected" : "Connecting to API"}</div><div className="team-profile"><span className="team-avatar">RT</span><div className="team-meta"><strong>ReefTrace workspace</strong><span>4 builders · local prototype</span></div></div></div>
    </aside>
    <div className="main-column">
      <header className="topbar"><div className="breadcrumb"><span>Workspace</span><Icon name="chevron" /><strong>{currentView.label}</strong></div><div className="topbar-actions"><label className="search-field"><Icon name="search" /><span className="sr-only">Search observations</span><input ref={searchInput} type="search" value={query} onChange={event => setQuery(event.target.value)} onKeyDown={event => { if (event.key === "Enter") navigate("investigations"); }} placeholder="Find an observation…" /><kbd className="search-shortcut" aria-hidden="true">/</kbd></label><button className="icon-button" title="Operator access" aria-label="Open operator access" onClick={openOperator}><Icon name="key" /></button></div></header>
      <main id="workspace-main" className="page-content" tabIndex={-1} aria-busy={!!busy}>
        {connectionError && <div className="notice error" role="alert">Could not reach the local API. {connectionError}</div>}
        {notice && <div className={`notice operation-notice ${noticeTone}`} role="status"><Icon name={noticeTone === "success" ? "check" : "help"} /><span>{notice}</span><button className="icon-button" aria-label="Dismiss notice" onClick={() => setNotice("")}><Icon name="close" /></button></div>}
        {error && <div className="notice error" role="alert">{error}<button className="icon-button" aria-label="Dismiss error" onClick={() => setError("")}><Icon name="close" /></button></div>}
        {busy && <div className="busy-notice" role="status"><span className="status-dot is-live" />{busy}…{taskCaseId && <button className="ghost-button" disabled={!token || stopping} onClick={() => void stopCase(taskCaseId)}>Stop task</button>}</div>}

        {view === "overview" && <>
          <div className="page-heading"><div><p className="kicker">Your workspace</p><h1>Your reef, at a glance.</h1><p className="page-description">Observations, source evidence, and the next step. All in one place.</p></div><div className="heading-actions"><button className="secondary-button" onClick={() => navigate("data")}><Icon name="wave" />Explore real data</button><button className="primary-button" disabled={!!busy} onClick={loadDemo}><Icon name="plus" />Load demo</button></div></div>
          <div className="summary-strip"><div className="summary-item"><span className="summary-value">{status ? cases.length : "—"}</span>saved observations</div><div className="summary-item"><span className="summary-value">{status ? reportCount : "—"}</span>source reports</div><div className="summary-item"><span className={`status-dot ${status?.camera.fresh ? "is-live" : "is-off"}`} />Camera {cameraLabel.toLowerCase()}</div><Pill>Controlled tank prototype</Pill></div>
          <div className="overview-grid">
            <section className="card"><div className="card-header"><div><h2 className="card-title">Recent observations</h2><p className="card-subtitle">Pick up an investigation.</p></div><button className="card-link" onClick={() => navigate("investigations")}>View all <Icon name="arrow" /></button></div><div className="observation-list">{filteredCases.length ? filteredCases.slice(0, 4).map(item => <button className="observation-row" key={item.id} disabled={!!busy} onClick={() => openCase(item.id)}><span className="observation-icon"><Icon name={item.endpoint ? "wave" : "cases"} /></span><span className="observation-copy"><span className="observation-title">{caseKind(item)}</span><span className="observation-meta">{item.id.slice(-8)} · {item.evidence_id ? "Report saved" : "Ready to compare"}</span></span><Pill tone={item.mode === "LIVE" ? "green" : "neutral"}>{item.mode === "SYNTHETIC" ? "Demo" : item.mode}</Pill><Icon name="chevron" /></button>) : <div className="empty-state"><Icon name="cases" /><p>{query ? "No matching observations" : "Your first observation starts here"}</p><span>{query ? "Try a case ID, mode, or observation type." : "Load the demo or record a calibrated camera observation."}</span></div>}</div></section>
            <section className="card"><div className="card-header"><div><h2 className="card-title">Ready to trace</h2><p className="card-subtitle">What your next experiment needs.</p></div><Icon name="check" /></div><div className="checklist"><div className="check-row"><span className={`check-icon ${token ? "complete" : ""}`}><Icon name="key" /></span><div className="check-copy"><span className="check-title">Operator access</span><span>{token ? "Token entered for this tab" : "Connect to run workspace actions"}</span></div><button className="card-link" onClick={openOperator}>{token ? "Manage" : "Connect"} <Icon name="arrow" /></button></div><div className="check-row"><span className={`check-icon ${status?.camera.fresh ? "complete" : ""}`}><Icon name="camera" /></span><div className="check-copy"><span className="check-title">USB camera</span><span>{status?.camera.fresh ? "Fresh frames are arriving" : "Connect your overhead webcam"}</span></div><button className="card-link" onClick={() => navigate("camera")}>Set up <Icon name="arrow" /></button></div><div className="check-row"><span className={`check-icon ${measuredProfiles.length ? "complete" : ""}`}><Icon name="wave" /></span><div className="check-copy"><span className="check-title">Measured tank profile</span><span>{measuredProfiles.length ? `${measuredProfiles.length} frozen profile${measuredProfiles.length === 1 ? "" : "s"}` : "Calibrate before a physical source trial"}</span></div><Pill tone={measuredProfiles.length ? "green" : "neutral"}>{measuredProfiles.length ? "Saved" : "Pending"}</Pill></div></div></section>
            <section className="card"><div className="card-header"><div><h2 className="card-title">Your workflow</h2><p className="card-subtitle">From an observation to an honest answer.</p></div></div><div className="card-body">{[{ title: "Observe", detail: "Record a path or retained endpoint.", target: "camera" }, { title: "Compare", detail: "Test candidate sources with measured flow.", target: "investigations" }, { title: "Investigate", detail: "Ask Chalk to explain the saved evidence.", target: "investigations" }].map((step, index) => <button className="workflow-step" key={step.title} onClick={() => navigate(step.target as View)}><span className="step-index">0{index + 1}</span><span><strong>{step.title}</strong><span>{step.detail}</span></span><Icon name="arrow" /></button>)}</div></section>
            <section className="card"><div className="card-header"><div><h2 className="card-title">Connected tools</h2><p className="card-subtitle">One investigator. Two ways to reach it.</p></div><button className="card-link" onClick={() => navigate("settings")}>Manage <Icon name="arrow" /></button></div><div className="card-body">{(["chalk", "photon"] as const).map(provider => <div className="tool-row" key={provider}><span className={`tool-logo ${provider}`}>{provider === "chalk" ? "c" : <Icon name="agent" />}</span><div className="tool-description"><strong>{provider === "chalk" ? "Chalk" : "Photon"}</strong><span>{provider === "chalk" ? "Evidence investigator" : "Messaging channel"}</span></div><Pill tone={status?.[provider].ready ? "purple" : "neutral"}>{status?.[provider].ready ? "Configured" : "Not configured"}</Pill></div>)}<p className="settings-note">Configuration status is separate from a verified live connection.</p></div></section>
          </div>
          <div className="notice info"><Icon name="help" /><span>New here? The demo includes a ranked path, an ambiguous endpoint, and an invalid calibration.</span><button className="card-link" disabled={!!busy} onClick={loadDemo}>Try the demo <Icon name="arrow" /></button></div>
        </>}

        {view === "investigations" && <>
          <div className="page-heading"><div><h1>Investigations</h1><p className="page-description">Follow an observation. Compare where it could have entered.</p></div><button className="secondary-button" disabled={!!busy} onClick={loadDemo}><Icon name="plus" />Load demo</button></div>
          {!token && <div className="notice info"><Icon name="key" /><span>Connect operator access to compute source evidence or ask the investigator.</span><button className="card-link" onClick={openOperator}>Connect operator <Icon name="arrow" /></button></div>}
          <div className="case-layout"><section className="card case-list" aria-label="Saved cases"><div className="card-header"><h2 className="card-title">Observations</h2><Pill>{filteredCases.length}</Pill></div>{filteredCases.length ? filteredCases.map(item => <button className="case-item" key={item.id} aria-current={item.id === selected ? "true" : undefined} disabled={!!busy} onClick={() => selectCase(item.id)}><span><strong>{caseKind(item)}</strong><span>{item.id.slice(-8)}</span></span><Pill tone={item.mode === "LIVE" ? "green" : "neutral"}>{item.mode === "SYNTHETIC" ? "Demo" : item.mode}</Pill></button>) : <div className="empty-state"><p>{query ? "No matches" : "No observations yet"}</p><span>{query ? "Try another search." : "Load a demo to get started."}</span></div>}</section>
            <div className="case-detail">{activeCase ? <>
              <section className="card"><div className="card-header case-detail-heading"><div><div className="case-meta"><Pill tone={activeCase.mode === "LIVE" ? "green" : "purple"}>{activeCase.mode}</Pill><span>{activeCase.id}</span></div><h2>{caseKind(activeCase)}</h2></div><Pill>{activeCase.state.replaceAll("_", " ").toLowerCase()}</Pill></div><div className="report-grid"><div><SourceMap profile={profile} points={activeCase.points} endpoint={activeCase.endpoint} /><div className="map-legend"><span><i className="legend-dot purple" />Observed debris</span><span><i className="legend-dot green" />Retention pocket</span><span>Regions {profile?.sources.map(source => source.id).join(" · ") || "not loaded"}</span></div></div><SourceReport evidence={evidence} /></div><div className="action-bar"><button className="primary-button" title={caseStopped ? "This case is stopped. Load a new observation to compute." : !token ? "Connect operator access first" : busy ? "Wait for the current task or stop it" : "Compare the saved observation with its frozen source model"} disabled={locked || caseStopped} onClick={() => void performCase("Comparing candidate sources", async () => setEvidence(await request(`/cases/${encodeURIComponent(selected)}/estimate`, {})))}><Icon name="play" />Compute source support</button><button className="secondary-button" title={!evidence ? "Compute source support first" : caseStopped ? "This case is stopped" : "Compare the predeclared transport assumptions"} disabled={locked || !evidence || caseStopped} onClick={() => void performCase("Testing transport sensitivity", async () => setAnalysis(await request(`/cases/${encodeURIComponent(selected)}/sensitivity`, { preset_id: "predeclared-transport-envelope-v1" })))}>Test sensitivity</button><button className="danger-button" disabled={!token || stopping || caseStopped} onClick={() => void stopCase()}><Icon name="stop" />Stop task</button></div><p className="settings-note card-body">{caseStopped ? "This observation is stopped. Load a new demo or camera observation to start another investigation. " : ""}Stop ends software tasks for this case. The circulation pump stays on its original wall cord.</p>{analysis != null && <details className="details-panel" open><summary>Sensitivity evidence</summary><pre className="code-block">{JSON.stringify(analysis, null, 2)}</pre></details>}{evidence && <details className="details-panel"><summary>Full immutable source report</summary><pre className="code-block">{JSON.stringify(evidence, null, 2)}</pre></details>}</section>
              <section className="card agent-card"><div className="card-header"><div><h2 className="card-title">Ask the investigator</h2><p className="card-subtitle">Chalk explains the same saved evidence used by Photon.</p></div><span className="tool-logo chalk">c</span></div><div className="card-body"><label className="question-field"><span className="sr-only">Investigation question</span><textarea value={question} onChange={event => setQuestion(event.target.value)} maxLength={4000} rows={2} /></label><div className="action-bar"><button className="primary-button" title={!evidence ? "Compute source support first" : !question.trim() ? "Enter a question" : caseStopped ? "This case is stopped" : "Ask the case-bound Chalk investigator"} disabled={locked || !evidence || !question.trim() || caseStopped} onClick={() => void performCase("Investigating through Chalk", async () => { const result = await request<Investigation>(`/cases/${encodeURIComponent(selected)}/investigate`, { text: question.trim() }); setAnswer(result); return investigationNotice(result); })}><Icon name="agent" />Ask Chalk</button><button className="card-link" onClick={() => navigate("settings")}>Channel settings <Icon name="arrow" /></button></div>{!status?.chalk.ready && <p className="settings-note">Chalk is not configured yet. Asking will show its connection status; source evidence stays available. Set the server credentials in Settings to enable a live model.</p>}{answer && <div className="answer" aria-live="polite"><Pill tone={answer.action === "STOP" ? "amber" : "purple"}>{answer.action === "STOP" && !answer.live_model_response ? "No live model response" : answer.action}</Pill><p>{answer.explanation}</p><p className="settings-note">Live model response: {answer.live_model_response ? "yes" : "no"} · Evidence: {answer.evidence_ids.join(", ") || "none"}</p><details className="details-panel"><summary>Tool trace</summary><pre className="code-block">{JSON.stringify(answer.trace, null, 2)}</pre></details></div>}</div></section>
              <ReefBriefing api={API} caseId={activeCase.id} evidenceId={evidence?.id} operatorToken={token} stopped={caseStopped} />
              {activeCase.mode === "LIVE" && evidence && <section className="card"><div className="card-header"><h2 className="card-title">Manual recovery</h2><Pill>Human task</Pill></div><div className="card-body">
                <p className="card-subtitle">Approve a task, physically recover the token, then record what happened. Pending tasks are restored from the backend.</p>
                {actionReadError && <p className="notice error" role="alert">Could not restore this case’s tasks: {actionReadError}</p>}
                {currentAction && <div className="manual-task-status"><strong>{readableReason(actionState)}</strong><code>{actionId}</code>{actionState === "proposed" && <span>{actionExpired ? "Approval window expired. Cancel this task and record a fresh observation." : `Approval window ends ${new Date(currentAction.expires_at * 1000).toLocaleTimeString()}.`}</span>}{actionState === "awaiting_human" && <span>Approved human task. Record the actual physical outcome when the task is complete.</span>}</div>}
                <div className="action-bar">
                  <button className="secondary-button" disabled={locked || caseStopped || !!actionReadError || actionState === "proposed" || actionState === "awaiting_human"} onClick={() => void performCase("Proposing manual recovery", async () => { const result = await request<ManualAction>("/actions/propose", { case_id: selected, evidence_id: evidence.id }); setActionId(result.id); setActionState(result.state); setCaseActions(previous => [result, ...previous]); })}>Propose recovery</button>
                  <button className="secondary-button" disabled={locked || caseStopped || !actionId || actionState !== "proposed" || actionExpired || !!actionReadError} onClick={() => void performCase("Approving manual task", async () => { const result = await request<ManualAction>(`/actions/${encodeURIComponent(actionId)}/approve`, {}); setActionState(result.state); setCaseActions(previous => previous.map(item => item.id === result.id ? result : item)); })}>Approve task</button>
                  <button className="ghost-button" disabled={locked || !actionId || !["proposed", "awaiting_human"].includes(actionState)} onClick={() => void performCase("Cancelling manual task", async () => { const result = await request<ManualAction>(`/actions/${encodeURIComponent(actionId)}/cancel`, {}); setActionState(result.state); setCaseActions(previous => previous.map(item => item.id === result.id ? result : item)); })}>Cancel manual task</button>
                </div>
                {actionState === "awaiting_human" && !caseStopped && <div className="manual-outcome-form"><h3>Record the physical outcome</h3><div className="form-grid"><label>Observed outcome<select value={manualOutcome} onChange={event => setManualOutcome(event.target.value)} disabled={locked}><option value="">Choose what happened</option><option value="manual_recovered">Recovered and counted</option><option value="failed">Recovery failed</option><option value="uncertain">Outcome uncertain</option></select></label><label>Tokens physically recovered<input type="number" min={0} max={20} step={1} value={recoveredCount} onChange={event => setRecoveredCount(Number(event.target.value))} disabled={locked} /></label></div><label>Operator observation<textarea rows={2} maxLength={1000} value={outcomeNote} onChange={event => setOutcomeNote(event.target.value)} placeholder="Describe what you physically observed." disabled={locked} /></label><label className="checkbox-label"><input type="checkbox" checked={physicalConfirmed} onChange={event => setPhysicalConfirmed(event.target.checked)} disabled={locked} /><span>I performed this physical task and verified this count.</span></label><button className="primary-button" disabled={locked || caseStopped || !validOutcome || !!actionReadError} onClick={() => void performCase("Saving physical recovery", async () => { const result = await request<ManualAction>(`/actions/${encodeURIComponent(actionId)}/outcome`, { outcome: manualOutcome, recovered_count: recoveredCount, note: outcomeNote.trim() }); setActionState(result.state); setCaseActions(previous => previous.map(item => item.id === result.id ? result : item)); setPhysicalConfirmed(false); })}>Save manual outcome</button><p className="settings-note">Choose an outcome, enter the actual count and note, then confirm the physical task. A recovery report requires at least one counted token.</p></div>}
                {caseActions.length > 0 && <details className="details-panel"><summary>Saved manual-task history</summary><pre className="code-block">{JSON.stringify(caseActions, null, 2)}</pre></details>}
              </div></section>}
            </> : <section className="card empty-state investigation-empty"><Icon name="cases" width={30} height={30} /><h2>Choose an observation</h2><p>Its path, source comparison, and investigator will appear here.</p><button className="secondary-button" disabled={!!busy} onClick={loadDemo}>Load a demo</button></section>}</div>
          </div>
        </>}

        {view === "camera" && <>
          <div className="page-heading"><div><h1>Camera</h1><p className="page-description">One USB webcam. A measured view of your tank.</p></div><Pill tone={status?.camera.fresh ? "green" : "neutral"}><span className={`status-dot ${status?.camera.fresh ? "is-live" : "is-off"}`} />{cameraLabel}</Pill></div>
          <div className="camera-grid"><section className="card"><div className="card-header"><h2 className="card-title">Tank view</h2><span className="card-subtitle">Logitech C920s · USB</span></div><div className="camera-stage">{status?.camera.fresh ? <Image unoptimized width={status.camera.width ?? 1920} height={status.camera.height ?? 1080} className="camera-preview" src={`${API}/api/v1/camera/frame.jpg?t=${clock}`} alt="Latest external USB camera frame" /> : <div className="camera-empty"><Icon name="camera" width={32} height={32} /><h2>{status?.camera.running ? "Waiting for fresh frames" : "Your camera feed goes here"}</h2><p>Connect the overhead webcam, then start capture.</p></div>}</div><div className="camera-session"><span>Session <code>{status?.camera.session_id ?? "Not started"}</code></span><span>{status?.camera.width && status.camera.height ? `${status.camera.width} × ${status.camera.height}` : "No frames"}</span></div></section><section className="card"><div className="card-header"><h2 className="card-title">Capture controls</h2></div><div className="card-body"><label>USB device index<input type="number" min={0} max={20} value={device} onChange={event => setDevice(Number(event.target.value))} disabled={locked || status?.camera.running} /></label><p className="settings-note">Select the external C920s, rather than your laptop camera.</p><div className="device-controls"><button className="primary-button" disabled={locked || status?.camera.running || !Number.isInteger(device) || device < 0 || device > 20} onClick={() => void perform("Opening USB webcam", async () => { await request("/camera/start", { device_index: device }); })}><Icon name="play" />Start webcam</button><button className="secondary-button" disabled={locked || !status?.camera.running} onClick={() => void perform("Closing webcam", async () => { await request("/camera/stop", {}); })}>Close webcam</button></div>{!token && <button className="card-link" onClick={openOperator}>Connect operator to enable capture <Icon name="arrow" /></button>}<div className="settings-note"><strong>Before recording</strong><p>Keep the camera dry and fixed. Check the whole water surface, steady light, and token visibility.</p></div></div></section></div>
          <details className="card setup-steps"><summary>Measured tank setup and recordings <span>Mapping → drift → profile → source trial</span></summary><div className="card-body"><p className="settings-note">Use your actual tank measurements. JSON templates are in the repository’s config folder; the API reference describes each field.</p><a className="card-link" href={`${API}/docs`} target="_blank" rel="noreferrer">Open API reference <Icon name="arrow" /></a><div className="setup-step"><h3><span className="step-index">01</span>Map the water surface</h3><label>Calibration request JSON<textarea rows={5} value={calibration} onChange={event => setCalibration(event.target.value)} /></label><button className="secondary-button" disabled={locked || !calibration} onClick={() => void perform("Validating water-plane mapping", async () => { const result = await request<{ calibration_id: string }>("/vision/calibrate", parseRequestJson(calibration, "Calibration request")); setCalibrationId(result.calibration_id); setSetupResult(result); })}>Fit and validate mapping</button></div><div className="setup-step"><h3><span className="step-index">02</span>Record and validate drift</h3><label>Calibration ID<input value={calibrationId} onChange={event => setCalibrationId(event.target.value)} /></label><button className="secondary-button" disabled={locked || !calibrationId || !status?.camera.fresh} onClick={() => void perform("Recording five seconds of drift", async () => setSetupResult(await request("/camera/record", { calibration_id: calibrationId, duration_s: 5 })))}>Record flow calibration</button><label>Recorded-flow fit JSON<textarea rows={5} value={flowJson} onChange={event => setFlowJson(event.target.value)} /></label><p className="settings-note">Use separate training_recording_ids and validation_recording_ids.</p><button className="secondary-button" disabled={locked || !flowJson} onClick={() => void perform("Fitting measured drift", async () => setSetupResult(await request("/flow/fit-recordings", parseRequestJson(flowJson, "Recorded-flow request"))))}>Fit measured flow</button></div><div className="setup-step"><h3><span className="step-index">03</span>Freeze a measured profile</h3><label>Complete measured profile JSON<textarea rows={5} value={profileJson} onChange={event => setProfileJson(event.target.value)} /></label><button className="secondary-button" disabled={locked || !profileJson} onClick={() => void perform("Freezing measured profile", async () => { const result = await request<{ id: string }>("/profiles", parseRequestJson(profileJson, "Measured profile")); setRecordProfileId(result.id); setSetupResult(result); })}>Register frozen profile</button></div><div className="setup-step"><h3><span className="step-index">04</span>Record a source trial</h3><div className="form-grid"><label>Measured profile<select value={recordProfileId} onChange={event => setRecordProfileId(event.target.value)}><option value="">Select a frozen measured profile</option>{measuredProfiles.map(item => <option key={item.id} value={item.id}>{item.id}</option>)}</select></label><label>Evidence mode<select value={observationType} onChange={event => setObservationType(event.target.value)}><option value="trajectory">Observed moving trajectory</option><option value="retained_endpoint">First seen already retained</option></select></label></div><button className="primary-button" disabled={locked || !recordProfileId || !status?.camera.fresh} onClick={() => void perform("Recording permitted observation", async () => { const recording = await request<{ id: string }>("/camera/record", { profile_id: recordProfileId, duration_s: 5 }); const item = await request<Case>(`/recordings/${recording.id}/case`, { observation_type: observationType }); openCase(item.id, true); })}>Record a new source case</button></div>{setupResult != null && <details className="details-panel" open><summary>Setup result</summary><pre className="code-block">{JSON.stringify(setupResult, null, 2)}</pre></details>}</div></details>
        </>}

        {view === "data" && <RealDataLab api={API} />}

        {view === "settings" && <>
          <div className="page-heading"><div><h1>Workspace settings</h1><p className="page-description">Operator access and the tools behind your investigations.</p></div></div>
          <section className="card"><div className="card-header"><div><h2 className="card-title">Operator access</h2><p className="card-subtitle">Required to load demos, record, or compute a new report.</p></div><Pill tone={token ? "purple" : "neutral"}>{token ? "Token entered" : "Not connected"}</Pill></div><div className="card-body setting-row"><p className="settings-note">The local token stays in memory in this browser tab.</p><button className="secondary-button" onClick={openOperator}><Icon name="key" />{token ? "Manage access" : "Connect operator"}</button></div></section>
          <div className="settings-grid">{(["chalk", "photon"] as const).map(provider => <section className="card integration-card" key={provider}><div className="card-header"><div className="integration-heading"><span className={`tool-logo ${provider}`}>{provider === "chalk" ? "c" : <Icon name="agent" />}</span><h2 className="card-title">{provider === "chalk" ? "Chalk" : "Photon"}</h2></div><Pill tone={status?.[provider].ready ? "purple" : "neutral"}>{status?.[provider].ready ? "Configured" : "Not configured"}</Pill></div><div className="card-body"><p>{provider === "chalk" ? "A bounded investigator that reads source reports, tests sensitivity, and explains the evidence." : "The same case-bound investigator, available in your prepared direct messaging conversation."}</p><div className="integration-state"><span>Live connection verified</span><strong>{status?.[provider].connection_verified ? "Yes" : "Not verified"}</strong></div><div className="integration-reasons">{status?.[provider].reasons?.map(reason => <Pill key={reason}>{readableReason(reason)}</Pill>)}</div><p className="settings-note">{provider === "chalk" ? "Set the gateway key, environment, and model in the server’s .env." : "Set your key, project, and allowlisted route in the server’s .env."} Restart the API after changes. See docs/integrations.md for setup.</p></div></section>)}</div>
          <section className="card"><div className="card-header"><h2 className="card-title">About this workspace</h2><Pill>Local prototype</Pill></div><div className="card-body"><div className="setting-row"><span>Collection method</span><strong>Manual recovery</strong></div><div className="setting-row"><span>Hardware actuation</span><strong>None</strong></div><p className="settings-note">Synthetic cases test the software. Real source attribution requires calibrated tank measurements and held-out physical trials.</p></div></section>
        </>}
        <footer className="workspace-footer"><span>ReefTrace · Source tracing first</span><span>Demo data is not physical validation.</span></footer>
      </main>
    </div>
    <dialog ref={operatorDialog} className="operator-dialog" aria-labelledby="operator-title" onClick={event => { if (event.target === event.currentTarget) operatorDialog.current?.close(); }}><div className="dialog-header"><h2 id="operator-title">Connect operator</h2><button className="icon-button" aria-label="Close operator access" onClick={() => operatorDialog.current?.close()}><Icon name="close" /></button></div><p className="dialog-help">Find <code>REEFTRACE_LOCAL_TOKEN</code> in your local <code>reeftrace/.env</code>. Enter it here to run workspace actions.</p><form method="dialog" onSubmit={() => { setToken(tokenDraft.trim()); setNoticeTone("info"); setNotice(tokenDraft.trim() ? "Operator token entered for this browser tab. Actions will verify it with the API." : "Operator access cleared for this tab."); }}><label>Local operator token<input type="password" autoComplete="off" value={tokenDraft} onChange={event => setTokenDraft(event.target.value)} disabled={!!busy} placeholder="Enter your local token" /></label><p className="settings-note">Stored only in this tab’s memory. Sponsor keys stay on the server.</p><div className="dialog-actions">{tokenDraft && <button type="button" className="ghost-button" disabled={!!busy} onClick={() => setTokenDraft("")}>Clear token</button>}<button className="primary-button" type="submit" disabled={!!busy}>Done</button></div></form></dialog>
  </div>;
}
