"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useOperator } from "../components/operator-provider";
import { BrandMark } from "../components/brand-mark";
import { BRAND_NAME } from "../components/brand";
import { GlyphTrail } from "../components/glyph-trail";
import { Icon, type IconName } from "../components/icons";
import { SourceMap, type SourceProfile } from "../components/source-map";
import { RealDataLab } from "../components/real-data-lab";
import { ReefBriefing } from "../components/reef-briefing";
import { PreventionWorkspace } from "../components/prevention-workspace";
import { PreventionModes } from "../components/prevention-modes";
import { MethodValidation } from "../components/method-validation";
import { DemoGuide } from "../components/demo-guide";
import demoStyles from "../components/demo-guide.module.css";
import { FieldWorkflow } from "../components/field-workflow";
import { CameraPlane } from "../components/camera-plane";
import type { CalibrationReport } from "../components/field-workflow-state";
import { canReloadSourceEvidence, currentSourceEvidence } from "../components/evidence-state";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
type View = "overview" | "investigations" | "prevention" | "camera" | "data" | "settings";
type Case = { id: string; profile_id: string; mode: string; state: string; evidence_id: string | null; points: { x_cm: number; y_cm: number }[]; endpoint?: { x_cm: number; y_cm: number; retained: boolean } | null };
type Evidence = { id: string; case_id: string; status: string; relative_support: Record<string, number>; reason_codes?: string[]; inference_mode?: string; [key: string]: unknown };
type Readiness = { enabled?: boolean; ready: boolean; connection_verified: boolean; reasons: string[]; worker_running?: boolean };
type Status = { camera: { fresh: boolean; running: boolean; session_id: string | null; width: number | null; height: number | null; device_index: number | null }; chalk: Readiness; photon: Readiness; operator_configured: boolean };
type Investigation = { action: string; explanation: string; live_model_response?: boolean; evidence_ids: string[]; source_report?: Evidence; trace?: unknown[] };
type ManualAction = { id: string; case_id: string; evidence_id: string; state: string; expires_at: number; created_at: number; outcome?: { outcome: string; recovered_count: number; note: string } };
type Sensitivity = { parent_estimate_id: string; [key: string]: unknown };
const VIEWS: { id: View; label: string; icon: IconName }[] = [
  { id: "overview", label: "Overview", icon: "overview" },
  { id: "investigations", label: "Investigations", icon: "cases" },
  { id: "prevention", label: "Prevention", icon: "check" },
  { id: "camera", label: "Camera", icon: "camera" },
  { id: "data", label: "Data lab", icon: "wave" },
  { id: "settings", label: "Settings", icon: "settings" },
];

function Pill({ children, tone = "neutral" }: { children: ReactNode; tone?: string }) {
  return <span className={`pill ${tone}`}>{children}</span>;
}
function caseKind(item: Case) { return item.endpoint ? "Retained endpoint" : "Observed trajectory"; }
function readableReason(reason: string) { return reason.toLowerCase().replaceAll("_", " "); }
function configurationLabel(provider: "chalk" | "photon", readiness?: Readiness) {
  if (!readiness) return "Checking configuration";
  if (readiness.enabled === false || readiness.reasons.includes("disabled")) {
    return provider === "photon" ? "Automatic replies off" : "Investigator disabled";
  }
  if (provider === "photon" && readiness.ready) return readiness.worker_running ? "Automatic replies on" : "Worker not running";
  return readiness.ready ? "Configured" : "Configuration incomplete";
}
function errorMessage(cause: unknown) { return cause instanceof Error ? cause.message : String(cause); }
function isAbort(cause: unknown) { return cause instanceof DOMException && cause.name === "AbortError"; }
type RequestOptions = { signal?: AbortSignal; independent?: boolean };
type EvidenceScope = { id: string; case_id: string };
type CompletionNotice = { message: string; tone: "success" | "info"; scope?: EvidenceScope };
function investigationNotice(result: Investigation): CompletionNotice {
  const completion: CompletionNotice = result.live_model_response
    ? { message: "Chalk returned a live model investigation. Review its explanation and tool trace below.", tone: "success" }
    : { message: "Chalk did not run a live model. Review its connection status below; saved source evidence remains available.", tone: "info" };
  return { ...completion, ...(result.source_report ? { scope: { id: result.source_report.id, case_id: result.source_report.case_id } } : {}) };
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
function SourceReport({ evidence, expectedEvidenceId, readError, reloadDisabled, onReload }: {
  evidence: Evidence | null;
  expectedEvidenceId?: string | null;
  readError: string;
  reloadDisabled: boolean;
  onReload: () => void;
}) {
  return <aside className="evidence-panel" aria-live="polite">
    <div className="evidence-heading"><h3>Source support</h3>{evidence && <Pill tone={evidence.status === "ranked" ? "purple" : evidence.status === "unknown" ? "amber" : "red"}>{evidence.status === "unknown" ? "Unknown" : evidence.status === "ranked" ? "Ranked" : "Invalid"}</Pill>}</div>
    {evidence ? <>
      <p className="card-subtitle">{evidence.status === "ranked" ? "Which candidate best matches this saved observation?" : evidence.status === "unknown" ? "The observation cannot distinguish a reliable source." : "This input does not support a valid source comparison."}</p>
      <div className="source-scores">{Object.entries(evidence.relative_support ?? {}).map(([source, support]) => <div className="score-row" key={source}>
        <span>Source {source}</span><meter className="score-track" min={0} max={1} value={support} aria-label={`Relative support for source ${source}`} /><strong>{(support * 100).toFixed(1)}%</strong>
      </div>)}</div>
      {evidence.reason_codes?.length ? <ul className="reason-list">{evidence.reason_codes.map(reason => <li key={reason}>{readableReason(reason)}</li>)}</ul> : <p className="card-subtitle">Based on the saved observation and frozen transport model.</p>}
      <p className="settings-note">These values are not geographic probabilities.</p>
      <details className="details-panel"><summary>Source report identity</summary><code className="evidence-id">{evidence.id}</code></details>
    </> : readError ? <div className="empty-state"><Icon name="help" /><p>Saved report could not be loaded</p><span role="alert">{readError}</span><button className="secondary-button" disabled={reloadDisabled} onClick={onReload}>Reload source report</button></div> : expectedEvidenceId ? <div className="empty-state" role="status"><Icon name="clock" /><p>Loading saved source report…</p><span>Reading the current evidence for this observation.</span></div> : <div className="empty-state"><Icon name="file" /><p>No report yet</p><span>Compute source support to compare this observation with the candidate sources.</span></div>}
  </aside>;
}

export default function Workspace() {
  const router = useRouter();
  const { token, connect, disconnect } = useOperator();
  const [view, setView] = useState<View>("overview");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<Status | null>(null);
  const [profiles, setProfiles] = useState<SourceProfile[]>([]);
  const [cases, setCases] = useState<Case[]>([]);
  const [selected, setSelected] = useState("");
  const [loadedEvidence, setLoadedEvidence] = useState<Evidence | null>(null);
  const [answerResult, setAnswer] = useState<Investigation | null>(null);
  const [question, setQuestion] = useState("Which candidate sources fit this evidence, and what remains uncertain?");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [noticeTone, setNoticeTone] = useState<"success" | "info">("success");
  const [noticeScope, setNoticeScope] = useState<EvidenceScope | null>(null);
  const [connectionError, setConnectionError] = useState("");
  const [observationType, setObservationType] = useState("trajectory");
  const [busy, setBusy] = useState("");
  const [taskCaseId, setTaskCaseId] = useState("");
  const [device, setDevice] = useState(0);
  const [clock, setClock] = useState(0);
  const [cameraMapping, setCameraMapping] = useState<CalibrationReport | null>(null);
  const [cameraSetupOpen, setCameraSetupOpen] = useState(false);
  const [calibration, setCalibration] = useState("");
  const [profileJson, setProfileJson] = useState("");
  const [calibrationId, setCalibrationId] = useState("");
  const [flowJson, setFlowJson] = useState("");
  const [setupResult, setSetupResult] = useState<unknown>(null);
  const [analysisResult, setAnalysis] = useState<Sensitivity | null>(null);
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
  const [accessPending, setAccessPending] = useState(false);
  const [accessError, setAccessError] = useState("");
  const [stopping, setStopping] = useState(false);
  const [preventionBusy, setPreventionBusy] = useState(false);
  const operatorDialog = useRef<HTMLDialogElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  const chalkHeading = useRef<HTMLHeadingElement>(null);
  const investigationHeading = useRef<HTMLHeadingElement>(null);
  const chalkFocusPending = useRef(false);
  const actionRun = useRef(0);
  const actionController = useRef<AbortController | null>(null);
  const stoppingRef = useRef(false);
  const preventionBusyRef = useRef(false);
  const onPreventionBusyChange = useCallback((value: boolean) => { preventionBusyRef.current = value; setPreventionBusy(value); }, []);
  const refreshRun = useRef(0);
  const selectedRef = useRef("");
  const evidenceReadRun = useRef(0);
  const evidenceRetryPending = useRef(false);
  const [evidenceReadAttempt, setEvidenceReadAttempt] = useState(0);
  const [evidenceReadFailure, setEvidenceReadFailure] = useState<(EvidenceScope & { message: string }) | null>(null);
  const activeCase = cases.find(item => item.id === selected);
  const selectedEvidenceId = activeCase?.evidence_id;
  const evidence = currentSourceEvidence(loadedEvidence, selected, selectedEvidenceId);
  const answer = evidence && currentSourceEvidence(answerResult?.source_report, selected, selectedEvidenceId) ? answerResult : null;
  const analysis = evidence && analysisResult?.parent_estimate_id === evidence.id ? analysisResult : null;
  const sourceReadError = currentSourceEvidence(evidenceReadFailure, selected, selectedEvidenceId)?.message ?? "";
  const visibleNotice = !noticeScope || (view === "investigations" && currentSourceEvidence(noticeScope, selected, selectedEvidenceId)) ? notice : "";

  function setEvidence(value: Evidence | null) {
    ++evidenceReadRun.current;
    evidenceRetryPending.current = false;
    setLoadedEvidence(value); setAnswer(null); setAnalysis(null); setEvidenceReadFailure(null);
  }
  function reloadSourceReport() {
    if (actionController.current || stoppingRef.current
      || !canReloadSourceEvidence(evidenceReadFailure, selected, selectedEvidenceId, evidenceRetryPending.current)) return;
    evidenceRetryPending.current = true;
    setEvidenceReadFailure(null);
    setEvidenceReadAttempt(attempt => attempt + 1);
  }

  function navigate(nextView: View) {
    if (preventionBusyRef.current) return;
    setView(nextView);
    const route = `#${nextView}${selectedRef.current ? `?case=${encodeURIComponent(selectedRef.current)}` : ""}`;
    if (window.location.hash !== route) window.history.pushState(null, "", route);
    window.scrollTo({ top: 0, behavior: "auto" });
  }
  useEffect(() => {
    if (view !== "investigations" || !chalkFocusPending.current) return;
    chalkFocusPending.current = false;
    const target = chalkHeading.current ?? investigationHeading.current;
    target?.focus({ preventScroll: true });
    target?.scrollIntoView({ behavior: "instant", block: "center" });
  }, [view]);
  function selectCase(id: string, internal = false) {
    if (!internal && (actionController.current || stoppingRef.current || preventionBusyRef.current)) return;
    selectedRef.current = id;
    window.history.replaceState(null, "", `#${view}?case=${encodeURIComponent(id)}`);
    setSelected(id); setEvidence(null); setAnswer(null); setAnalysis(null); setActionId(""); setActionState("");
    setCaseActions([]); setActionReadError(""); setManualOutcome(""); setRecoveredCount(0); setOutcomeNote(""); setPhysicalConfirmed(false);
    setError(""); setNotice("");
  }
  function openCase(id: string, internal = false) { selectCase(id, internal); navigate("investigations"); }
  function openOperator() {
    if (preventionBusyRef.current) return;
    setTokenDraft(token); setAccessError(""); operatorDialog.current?.showModal();
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
    if (response.status === 401 && token) disconnect();
    if (!response.ok) throw new ApiError(apiError(data.detail, response.status), response.status);
    return data as T;
  }, [token, disconnect]);
  const refresh = useCallback(async (signal?: AbortSignal) => {
    const run = ++refreshRun.current;
    const [nextStatus, nextProfiles, nextCases] = await Promise.all([request<Status>("/status", undefined, { signal }), request<SourceProfile[]>("/profiles", undefined, { signal }), request<Case[]>("/cases", undefined, { signal })]);
    if (signal?.aborted) return;
    if (run !== refreshRun.current) return nextCases;
    setStatus(nextStatus); setProfiles(nextProfiles); setCases(nextCases); setConnectionError("");
    return nextCases;
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
    const run = ++evidenceReadRun.current;
    if (selected && selectedEvidenceId) evidenceRetryPending.current = true;
    if (selected && selectedEvidenceId) request<Evidence>(`/cases/${encodeURIComponent(selected)}/evidence`, undefined, { signal: controller.signal }).then(result => {
      const accepted = currentSourceEvidence(result, selected, selectedEvidenceId);
      if (!controller.signal.aborted && selectedRef.current === selected && run === evidenceReadRun.current) {
        if (accepted) {
          setLoadedEvidence(accepted); setEvidenceReadFailure(null);
          setAnswer(previous => currentSourceEvidence(previous?.source_report, selected, selectedEvidenceId) ? previous : null);
          setAnalysis(previous => previous?.parent_estimate_id === selectedEvidenceId ? previous : null);
        } else setEvidenceReadFailure({ case_id: selected, id: selectedEvidenceId, message: "The saved report changed while loading. Reload the current source report." });
      }
    }).catch(cause => {
      if (!controller.signal.aborted && selectedRef.current === selected && run === evidenceReadRun.current) setEvidenceReadFailure({ case_id: selected, id: selectedEvidenceId, message: errorMessage(cause) });
    }).finally(() => {
      if (run === evidenceReadRun.current) evidenceRetryPending.current = false;
    });
    return () => controller.abort();
  }, [selected, selectedEvidenceId, request, evidenceReadAttempt]);
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
      if (actionController.current || stoppingRef.current || preventionBusyRef.current) return;
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
    if (actionController.current || stoppingRef.current || preventionBusyRef.current) return;
    if (!token) { openOperator(); return; }
    const run = ++actionRun.current;
    const controller = new AbortController();
    actionController.current = controller;
    setBusy(name); setTaskCaseId(caseId); setError(""); setNotice(""); setNoticeScope(null);
    try {
      const completion = await job();
      if (run !== actionRun.current || controller.signal.aborted) return;
      const refreshedCases = await refresh(controller.signal).catch(cause => { if (!controller.signal.aborted) setConnectionError(errorMessage(cause)); });
      if (run === actionRun.current) {
        const completedCase = (refreshedCases ?? cases).find(item => item.id === caseId);
        setNoticeScope(completion?.scope ?? (completedCase?.evidence_id ? { case_id: caseId, id: completedCase.evidence_id } : null));
        setNoticeTone(completion?.tone ?? "success"); setNotice(completion?.message ?? `${name} complete.`);
      }
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
  const profile = profiles.find(item => item.id === activeCase?.profile_id);
  const filteredCases = cases.filter(item => `${item.id} ${item.mode} ${item.state} ${caseKind(item)}`.toLowerCase().includes(query.toLowerCase().trim()));
  const measuredProfiles = profiles.filter(item => item.data_origin === "MEASURED_TANK");
  const caseStopped = activeCase?.state === "STOPPED" || activeCase?.state === "RECOVERING";
  const currentAction = caseActions.find(item => item.id === actionId);
  const actionExpired = currentAction ? currentAction.expires_at * 1000 <= clock : false;
  const validOutcome = ["manual_recovered", "failed", "uncertain"].includes(manualOutcome) && Number.isInteger(recoveredCount) && recoveredCount >= 0 && recoveredCount <= 20 && (manualOutcome !== "manual_recovered" || recoveredCount > 0) && !!outcomeNote.trim() && physicalConfirmed;
  const locked = !!busy || !token || stopping || preventionBusy;
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
      setNoticeScope(null); setNoticeTone("success"); setNotice("Software tasks stopped for this observation. The pump remains powered through its original cord.");
    } catch (cause) { setError(`Stop was not confirmed. ${errorMessage(cause)}`); }
    finally { stoppingRef.current = false; setStopping(false); setBusy(""); setTaskCaseId(""); }
  }

  return <div className="app-shell">
    <div className="workspace-glyph-background" aria-hidden="true"><GlyphTrail /></div>
    <a className="sr-only skip-link" href="#workspace-main">Skip to workspace</a>
    <aside className="sidebar" aria-label="Workspace navigation">
      <button className="brand" disabled={preventionBusy} onClick={() => navigate("overview")} aria-label={`${BRAND_NAME} overview`}><span className="brand-symbol"><BrandMark /></span>{BRAND_NAME}</button>
      <div className="sidebar-section">Workspace</div>
      <nav>{VIEWS.filter(item => item.id !== "settings").map(item => <button className="nav-item" key={item.id} disabled={preventionBusy} aria-current={view === item.id ? "page" : undefined} onClick={() => navigate(item.id)}><Icon name={item.icon} /><span className="nav-label">{item.label}</span>{item.id === "investigations" && status && <span className="nav-count">{cases.length}</span>}</button>)}</nav>
      <div className="sidebar-section">Manage</div>
      <button className="nav-item" disabled={preventionBusy} aria-current={view === "settings" ? "page" : undefined} onClick={() => navigate("settings")}><Icon name="settings" /><span>Settings</span></button>
      <div className="sidebar-bottom"><button className="nav-item" disabled={!!busy || preventionBusy || stopping} onClick={() => router.push("/")}><BrandMark /><span>{BRAND_NAME} home</span></button><div className="local-indicator"><span className={`status-dot ${connected ? "is-live" : "is-off"}`} />{connectionError ? "Local API unavailable" : connected ? "Local API connected" : "Connecting to API"}</div></div>
    </aside>
    <div className="main-column">
      <header className="topbar"><div className="breadcrumb"><span>Workspace</span><Icon name="chevron" /><strong>{currentView.label}</strong></div><div className="topbar-actions"><label className="search-field"><Icon name="search" /><span className="sr-only">Search observations</span><input ref={searchInput} type="search" value={query} onChange={event => setQuery(event.target.value)} onKeyDown={event => { if (event.key === "Enter") navigate("investigations"); }} placeholder="Find an observation…" /><kbd className="search-shortcut" aria-hidden="true">/</kbd></label><button className="icon-button" disabled={preventionBusy} title="Operator access" aria-label="Open operator access" onClick={openOperator}><Icon name="key" /></button></div></header>
      <main id="workspace-main" className="page-content" tabIndex={-1} aria-busy={!!busy || preventionBusy}>
        {connectionError && <div className="notice error" role="alert">Could not reach the local API. {connectionError}</div>}
        {visibleNotice && <div className={`notice operation-notice ${noticeTone}`} role="status"><Icon name={noticeTone === "success" ? "check" : "help"} /><span>{visibleNotice}</span><button className="icon-button" aria-label="Dismiss notice" onClick={() => setNotice("")}><Icon name="close" /></button></div>}
        {error && <div className="notice error" role="alert">{error}<button className="icon-button" aria-label="Dismiss error" onClick={() => setError("")}><Icon name="close" /></button></div>}
        {busy && <div className="busy-notice" role="status"><span className="status-dot is-live" />{busy}…{taskCaseId && <button className="ghost-button" disabled={!token || stopping} onClick={() => void stopCase(taskCaseId)}>Stop task</button>}</div>}

        {view === "overview" && <>
          <div className="page-heading"><div><h1>Experiment overview</h1><p className="page-description">Inspect an observation, compare layouts, and review the evidence.</p></div><button className="primary-button" disabled={!!busy || preventionBusy} onClick={loadDemo}><Icon name="play" />Start software demo</button></div>
          <DemoGuide disabled={!!busy || preventionBusy} onTrace={() => navigate("investigations")} onPrevention={() => navigate("prevention")} onChalk={() => { chalkFocusPending.current = true; navigate("investigations"); }} />
          <p className="settings-note">Software examples are synthetic. The source-tracing and prevention demos use separate saved examples; neither is a physical tank trial.</p>
          <details className="card"><summary>Setup and saved observations</summary><div className="card-body">
          <div className="summary-strip"><div className="summary-item"><span className="summary-value">{status ? cases.length : "—"}</span>saved observations</div><div className="summary-item"><span className="summary-value">{status ? reportCount : "—"}</span>source reports</div><div className="summary-item"><span className={`status-dot ${status?.camera.fresh ? "is-live" : "is-off"}`} />Camera {cameraLabel.toLowerCase()}</div><Pill>Controlled tank prototype</Pill></div>
          <div className="overview-grid">
            <section className="card"><div className="card-header"><div><h2 className="card-title">Recent observations</h2><p className="card-subtitle">Pick up an investigation.</p></div><button className="card-link" onClick={() => navigate("investigations")}>View all <Icon name="arrow" /></button></div><div className="observation-list">{filteredCases.length ? filteredCases.slice(0, 4).map(item => <button className="observation-row" key={item.id} disabled={!!busy} onClick={() => openCase(item.id)}><span className="observation-icon"><Icon name={item.endpoint ? "wave" : "cases"} /></span><span className="observation-copy"><span className="observation-title">{caseKind(item)}</span><span className="observation-meta">{item.id.slice(-8)} · {item.evidence_id ? "Report saved" : "Ready to compare"}</span></span><Pill tone={item.mode === "LIVE" ? "green" : "neutral"}>{item.mode === "SYNTHETIC" ? "Demo" : item.mode}</Pill><Icon name="chevron" /></button>) : <div className="empty-state"><Icon name="cases" /><p>{query ? "No matching observations" : "Your first observation starts here"}</p><span>{query ? "Try a case ID, mode, or observation type." : "Load the demo or record a calibrated camera observation."}</span></div>}</div></section>
            <section className="card"><div className="card-header"><div><h2 className="card-title">Ready to trace</h2><p className="card-subtitle">What your next experiment needs.</p></div><Icon name="check" /></div><div className="checklist"><div className="check-row"><span className={`check-icon ${token ? "complete" : ""}`}><Icon name="key" /></span><div className="check-copy"><span className="check-title">Operator access</span><span>{token ? "Verified for this browser tab" : "Connect to run workspace actions"}</span></div><button className="card-link" onClick={openOperator}>{token ? "Manage" : "Connect"} <Icon name="arrow" /></button></div><div className="check-row"><span className={`check-icon ${status?.camera.fresh ? "complete" : ""}`}><Icon name="camera" /></span><div className="check-copy"><span className="check-title">USB camera</span><span>{status?.camera.fresh ? "Fresh frames are arriving" : "Connect your overhead webcam"}</span></div><button className="card-link" onClick={() => navigate("camera")}>Set up <Icon name="arrow" /></button></div><div className="check-row"><span className={`check-icon ${measuredProfiles.length ? "complete" : ""}`}><Icon name="wave" /></span><div className="check-copy"><span className="check-title">Measured tank profile</span><span>{measuredProfiles.length ? `${measuredProfiles.length} frozen profile${measuredProfiles.length === 1 ? "" : "s"}` : "Calibrate before a physical source trial"}</span></div><Pill tone={measuredProfiles.length ? "green" : "neutral"}>{measuredProfiles.length ? "Saved" : "Pending"}</Pill></div></div></section>
            <section className="card"><div className="card-header"><div><h2 className="card-title">Your workflow</h2><p className="card-subtitle">From an observation to an honest answer.</p></div></div><div className="card-body">{[{ title: "Observe", detail: "Record a path or retained endpoint.", target: "camera" }, { title: "Compare", detail: "Test candidate sources with measured flow.", target: "investigations" }, { title: "Investigate", detail: "Ask Chalk to explain the saved evidence.", target: "investigations" }].map((step, index) => <button className="workflow-step" key={step.title} onClick={() => navigate(step.target as View)}><span className="step-index">0{index + 1}</span><span><strong>{step.title}</strong><span>{step.detail}</span></span><Icon name="arrow" /></button>)}</div></section>
            <section className="card"><div className="card-header"><div><h2 className="card-title">Connected tools</h2><p className="card-subtitle">One investigator. Two ways to reach it.</p></div><button className="card-link" onClick={() => navigate("settings")}>Manage <Icon name="arrow" /></button></div><div className="card-body">{(["chalk", "photon"] as const).map(provider => <div className="tool-row" key={provider}><span className={`tool-logo ${provider}`}>{provider === "chalk" ? "c" : <Icon name="agent" />}</span><div className="tool-description"><strong>{provider === "chalk" ? "Chalk" : "Photon"}</strong><span>{provider === "chalk" ? "Evidence investigator" : "Messaging channel"}</span></div><Pill tone={status?.[provider].ready ? "purple" : "neutral"}>{configurationLabel(provider, status?.[provider])}</Pill></div>)}<p className="settings-note">Configuration status is separate from a verified live connection.</p></div></section>
          </div>
          </div></details>
        </>}

        {view === "investigations" && <>
          <div className="page-heading"><div><h1 ref={investigationHeading} tabIndex={-1}>Investigations</h1><p className="page-description">Follow an observation. Compare where it could have entered.</p></div><button className="secondary-button" disabled={!!busy} onClick={loadDemo}><Icon name="plus" />Load demo</button></div>
          {!token && <div className="notice info"><Icon name="key" /><span>Connect operator access to compute source evidence or ask the investigator.</span><button className="card-link" onClick={openOperator}>Connect operator <Icon name="arrow" /></button></div>}
          <div className={demoStyles.investigations}><details className="card case-list"><summary>Choose a different observation ({filteredCases.length})</summary><section aria-label="Saved cases"><div className="card-header"><h2 className="card-title">Observations</h2><Pill>{filteredCases.length}</Pill></div>{filteredCases.length ? filteredCases.map(item => <button className="case-item" key={item.id} aria-current={item.id === selected ? "true" : undefined} disabled={!!busy} onClick={() => selectCase(item.id)}><span><strong>{caseKind(item)}</strong><span>{item.id.slice(-8)}</span></span><Pill tone={item.mode === "LIVE" ? "green" : "neutral"}>{item.mode === "SYNTHETIC" ? "Demo" : item.mode}</Pill></button>) : <div className="empty-state"><p>{query ? "No matches" : "No observations yet"}</p><span>{query ? "Try another search." : "Load a demo to get started."}</span></div>}</section></details>
            <div className="case-detail">{activeCase ? <>
              <section className="card"><div className="card-header case-detail-heading"><div><div className="case-meta"><Pill tone={activeCase.mode === "LIVE" ? "green" : "purple"}>{activeCase.mode}</Pill><span>{activeCase.id.slice(-8)}</span></div><h2>{caseKind(activeCase)}</h2></div><Pill>{activeCase.state.replaceAll("_", " ").toLowerCase()}</Pill></div><div className="report-grid"><div><SourceMap profile={profile} points={activeCase.points} endpoint={activeCase.endpoint} /><div className="map-legend"><span><i className="legend-dot purple" />Saved token movement</span><span><i className="legend-dot green" />Retention pocket</span><span>Regions {profile?.sources.map(source => source.id).join(" · ") || "not loaded"}</span></div></div><SourceReport evidence={evidence} expectedEvidenceId={selectedEvidenceId} readError={sourceReadError} reloadDisabled={!!busy || stopping} onReload={reloadSourceReport} /></div><div className="action-bar"><button className="primary-button" title={caseStopped ? "This case is stopped. Load a new observation to compute." : !token ? "Connect operator access first" : busy ? "Wait for the current task or stop it" : "Compare the saved observation with its frozen source model"} disabled={locked || caseStopped} onClick={() => void performCase("Comparing candidate sources", async () => setEvidence(await request(`/cases/${encodeURIComponent(selected)}/estimate`, {})))}><Icon name="play" />{evidence ? "Recompute source support" : "Compute source support"}</button><details className="details-panel"><summary>Analysis tools and software stop</summary><p className="settings-note">Recomputing source support creates a new revision and archives comparisons tied to the previous report.</p><div className="action-bar"><button className="secondary-button" title={!evidence ? "Compute source support first" : caseStopped ? "This case is stopped" : "Compare the predeclared transport assumptions"} disabled={locked || !evidence || caseStopped} onClick={() => void performCase("Testing transport sensitivity", async () => setAnalysis(await request(`/cases/${encodeURIComponent(selected)}/sensitivity`, { preset_id: "predeclared-transport-envelope-v1" })))}>Test sensitivity</button><button className="danger-button" disabled={!token || stopping || caseStopped} onClick={() => void stopCase()}><Icon name="stop" />Stop task</button></div></details></div><p className="settings-note card-body">{caseStopped ? "This observation is stopped. Load a new demo or camera observation to start another investigation. " : ""}Stop ends software tasks for this case. The circulation pump stays on its original wall cord.</p>{analysis != null && <details className="details-panel"><summary>Sensitivity evidence</summary><pre className="code-block">{JSON.stringify(analysis, null, 2)}</pre></details>}{evidence && <details className="details-panel"><summary>Full immutable source report</summary><pre className="code-block">{JSON.stringify(evidence, null, 2)}</pre></details>}</section>
              <section id="source-chalk" className="card agent-card"><div className="card-header"><div><h2 ref={chalkHeading} tabIndex={-1} className="card-title">Ask Chalk</h2><p className="card-subtitle">Chalk explains the same saved evidence used by Photon.</p></div><span className="tool-logo chalk" aria-hidden="true">c</span></div><div className="card-body"><details className="details-panel"><summary>Change the question</summary><label className="question-field"><span className="sr-only">Investigation question</span><textarea value={question} onChange={event => setQuestion(event.target.value)} maxLength={4000} rows={2} /></label></details><p className="card-subtitle">Explain the source result and what remains uncertain.</p><div className="action-bar"><button className="primary-button" title={!evidence ? "Compute source support first" : !question.trim() ? "Enter a question" : caseStopped ? "This case is stopped" : "Ask the case-bound Chalk investigator"} disabled={locked || !evidence || !question.trim() || caseStopped} onClick={() => void performCase("Investigating through Chalk", async () => { const result = await request<Investigation>(`/cases/${encodeURIComponent(selected)}/investigate`, { text: question.trim() }); setAnswer(result); return investigationNotice(result); })}><Icon name="agent" />Ask Chalk</button><button className="card-link" onClick={() => navigate("settings")}>Channel settings <Icon name="arrow" /></button></div>{!status?.chalk.ready && <p className="settings-note">Chalk is not configured yet. Asking will show its connection status; source evidence stays available. Set the server credentials in Settings to enable a live model.</p>}{answer && <div className="answer" aria-live="polite"><Pill tone={answer.action === "STOP" ? "amber" : "purple"}>{answer.action === "STOP" && !answer.live_model_response ? "No live model response" : answer.action}</Pill><p>{answer.explanation}</p>{answer.live_model_response && <p className="settings-note">Live Chalk explanation</p>}<details className="details-panel"><summary>Evidence citations and tool trace</summary><p className="settings-note">Evidence: {answer.evidence_ids.join(", ") || "none"}</p><pre className="code-block">{JSON.stringify(answer.trace, null, 2)}</pre></details></div>}</div></section>
              <details className="card"><summary>Satellite context and voice briefing</summary><div className="card-body"><ReefBriefing api={API} caseId={activeCase.id} evidenceId={evidence?.id} operatorToken={token} stopped={caseStopped} /></div></details>
              {activeCase.mode === "LIVE" && evidence && <details className="card"><summary>Record a manual recovery</summary><section><div className="card-header"><h2 className="card-title">Manual recovery</h2><Pill>Human task</Pill></div><div className="card-body">
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
              </div></section></details>}
            </> : <section className="card empty-state investigation-empty"><Icon name="cases" width={30} height={30} /><h2>Choose an observation</h2><p>Its path, source comparison, and investigator will appear here.</p><button className="secondary-button" disabled={!!busy} onClick={loadDemo}>Load a demo</button></section>}</div>
          </div>
        </>}

        {view === "camera" && <>
          <div className="page-heading"><div><h1>Camera</h1><p className="page-description">Live USB preview first. Calibrate coordinates when your tank is ready.</p></div><Pill tone={status?.camera.fresh ? "green" : "neutral"}><span className={`status-dot ${status?.camera.fresh ? "is-live" : "is-off"}`} />{cameraLabel}</Pill></div>
          <div className="camera-grid"><section className="card"><div className="card-header"><h2 className="card-title">Live camera</h2><span className="card-subtitle">External USB webcam · device {status?.camera.device_index ?? device}</span></div><div className="camera-stage">{status?.camera.fresh ? <CameraPlane apiBase={API} width={status.camera.width ?? 1280} height={status.camera.height ?? 720} sessionId={status.camera.session_id} active={status.camera.fresh} calibration={cameraMapping} /> : <div className="camera-empty"><Icon name="camera" width={32} height={32} /><h2>{status?.camera.running ? "Waiting for fresh frames" : "Your camera feed goes here"}</h2><p>Connect the overhead webcam, then start capture.</p></div>}</div><div className="camera-session"><span>Session <code>{status?.camera.session_id ?? "Not started"}</code></span><span>{status?.camera.width && status.camera.height ? `${status.camera.width} × ${status.camera.height}` : "No frames"}</span></div></section><section className="card camera-controls-panel"><div className="card-header"><h2 className="card-title">Capture controls</h2></div><div className="card-body camera-controls-row"><label>USB device index<input type="number" min={0} max={20} value={device} onChange={event => setDevice(Number(event.target.value))} disabled={locked || status?.camera.running} /></label><div className="device-controls"><button className="primary-button" disabled={locked || status?.camera.running || !Number.isInteger(device) || device < 0 || device > 20} onClick={() => void perform("Opening USB webcam", async () => { await request("/camera/start", { device_index: device }); })}><Icon name="play" />Start webcam</button><button className="secondary-button" disabled={locked || !status?.camera.running} onClick={() => void perform("Closing webcam", async () => { await request("/camera/stop", {}); })}>Close webcam</button></div><div className="camera-control-hint"><p className="settings-note">Use the external USB webcam. Device 0 is the connected external camera on this Mac. A tank is not required for this preview.</p>{!token && <button className="card-link" onClick={openOperator}>Connect operator to enable capture <Icon name="arrow" /></button>}</div></div></section></div>
          <details className="details-panel" open={cameraSetupOpen} onToggle={event => setCameraSetupOpen(event.currentTarget.open)}><summary>Calibrate a tank and record trials when ready</summary>
          <FieldWorkflow previewActive={cameraSetupOpen} onMappingChange={setCameraMapping} request={request} apiBase={API} operatorConnected={!!token} onRequireOperator={openOperator} onBusyChange={onPreventionBusyChange} onOpenCase={id => openCase(id, true)} blocked={!!busy || stopping} />
          </details>
          <details className="card setup-steps"><summary>Measured tank setup and recordings <span>Mapping → drift → profile → source trial</span></summary><div className="card-body"><p className="settings-note">Use your actual tank measurements. JSON templates are in the repository’s config folder; the API reference describes each field.</p><a className="card-link" href={`${API || "http://127.0.0.1:8000"}/docs`} target="_blank" rel="noreferrer">Open API reference <Icon name="arrow" /></a><div className="setup-step"><h3><span className="step-index">01</span>Map the water surface</h3><label>Calibration request JSON<textarea rows={5} value={calibration} onChange={event => setCalibration(event.target.value)} /></label><button className="secondary-button" disabled={locked || !calibration} onClick={() => void perform("Validating water-plane mapping", async () => { const result = await request<{ calibration_id: string }>("/vision/calibrate", parseRequestJson(calibration, "Calibration request")); setCalibrationId(result.calibration_id); setSetupResult(result); })}>Fit and validate mapping</button></div><div className="setup-step"><h3><span className="step-index">02</span>Record and validate drift</h3><label>Calibration ID<input value={calibrationId} onChange={event => setCalibrationId(event.target.value)} /></label><button className="secondary-button" disabled={locked || !calibrationId || !status?.camera.fresh} onClick={() => void perform("Recording five seconds of drift", async () => setSetupResult(await request("/camera/record", { calibration_id: calibrationId, duration_s: 5 })))}>Record flow calibration</button><label>Recorded-flow fit JSON<textarea rows={5} value={flowJson} onChange={event => setFlowJson(event.target.value)} /></label><p className="settings-note">Use separate training_recording_ids and validation_recording_ids.</p><button className="secondary-button" disabled={locked || !flowJson} onClick={() => void perform("Fitting measured drift", async () => setSetupResult(await request("/flow/fit-recordings", parseRequestJson(flowJson, "Recorded-flow request"))))}>Fit measured flow</button></div><div className="setup-step"><h3><span className="step-index">03</span>Freeze a measured profile</h3><label>Complete measured profile JSON<textarea rows={5} value={profileJson} onChange={event => setProfileJson(event.target.value)} /></label><button className="secondary-button" disabled={locked || !profileJson} onClick={() => void perform("Freezing measured profile", async () => { const result = await request<{ id: string }>("/profiles", parseRequestJson(profileJson, "Measured profile")); setRecordProfileId(result.id); setSetupResult(result); })}>Register frozen profile</button></div><div className="setup-step"><h3><span className="step-index">04</span>Record a source trial</h3><div className="form-grid"><label>Measured profile<select value={recordProfileId} onChange={event => setRecordProfileId(event.target.value)}><option value="">Select a frozen measured profile</option>{measuredProfiles.map(item => <option key={item.id} value={item.id}>{item.id}</option>)}</select></label><label>Evidence mode<select value={observationType} onChange={event => setObservationType(event.target.value)}><option value="trajectory">Observed moving trajectory</option><option value="retained_endpoint">First seen already retained</option></select></label></div><button className="primary-button" disabled={locked || !recordProfileId || !status?.camera.fresh} onClick={() => void perform("Recording permitted observation", async () => { const recording = await request<{ id: string }>("/camera/record", { profile_id: recordProfileId, duration_s: 5 }); const item = await request<Case>(`/recordings/${recording.id}/case`, { observation_type: observationType }); openCase(item.id, true); })}>Record a new source case</button></div>{setupResult != null && <details className="details-panel" open><summary>Setup result</summary><pre className="code-block">{JSON.stringify(setupResult, null, 2)}</pre></details>}</div></details>
        </>}

        {view === "prevention" && <PreventionModes api={API} blocked={!!busy || stopping || preventionBusy}><PreventionWorkspace request={request} operatorConnected={!!token} onRequireOperator={openOperator} cases={cases} profiles={profiles} selectedCaseId={selected} onSelectCase={selectCase} onBusyChange={onPreventionBusyChange} onStopCase={stopCase} blocked={!!busy || stopping} /><details className="card"><summary>Research details: prevention method checks</summary><div className="card-body"><MethodValidation api={API} /></div></details></PreventionModes>}

        {view === "data" && <RealDataLab api={API} />}

        {view === "settings" && <>
          <div className="page-heading"><div><h1>Workspace settings</h1><p className="page-description">Operator access and the tools behind your investigations.</p></div></div>
          <section className="card"><div className="card-header"><div><h2 className="card-title">Operator access</h2><p className="card-subtitle">Required to load demos, record, or compute a new report.</p></div><Pill tone={token ? "purple" : "neutral"}>{token ? "Connected" : "Not connected"}</Pill></div><div className="card-body setting-row"><p className="settings-note">The local token stays in memory in this browser tab.</p><button className="secondary-button" onClick={openOperator}><Icon name="key" />{token ? "Manage access" : "Connect operator"}</button></div></section>
          <div className="settings-grid">{(["chalk", "photon"] as const).map(provider => <section className="card integration-card" key={provider}><div className="card-header"><div className="integration-heading"><span className={`tool-logo ${provider}`}>{provider === "chalk" ? "c" : <Icon name="agent" />}</span><h2 className="card-title">{provider === "chalk" ? "Chalk" : "Photon"}</h2></div><Pill tone={status?.[provider].ready ? "purple" : "neutral"}>{configurationLabel(provider, status?.[provider])}</Pill></div><div className="card-body"><p>{provider === "chalk" ? "A bounded investigator that reads source reports, tests sensitivity, and explains the evidence." : "A prepared messaging channel for the same case-bound investigator. Reply state is shown below."}</p><div className="integration-state"><span>Configuration check</span><strong>{configurationLabel(provider, status?.[provider])}</strong></div><div className="integration-reasons">{status?.[provider].reasons?.map(reason => <Pill key={reason}>{readableReason(reason)}</Pill>)}</div><p className="settings-note">{provider === "chalk" ? "This checks configuration only. A completed investigation's live model response and tool trace are the evidence for that request. Credentials stay in the server's .env." : "This checks configuration only; it does not test phone pairing or message delivery. Disabled means automatic replies are off. Keys and routes stay on the server."}</p></div></section>)}</div>
          <section className="card"><div className="card-header"><h2 className="card-title">About this workspace</h2><Pill>Local prototype</Pill></div><div className="card-body"><div className="setting-row"><span>Collection method</span><strong>Manual recovery</strong></div><div className="setting-row"><span>Hardware actuation</span><strong>None</strong></div><p className="settings-note">Synthetic cases test the software. Real source attribution requires calibrated tank measurements and held-out physical trials.</p></div></section>
        </>}
        <footer className="workspace-footer"><span>{BRAND_NAME} · Research workspace</span><span>Simulated results are separate from measured tank trials.</span></footer>
      </main>
    </div>
    <dialog ref={operatorDialog} className="operator-dialog" aria-labelledby="operator-title" onCancel={event => { if (accessPending) event.preventDefault(); }} onClick={event => { if (!accessPending && event.target === event.currentTarget) operatorDialog.current?.close(); }}><div className="dialog-header"><h2 id="operator-title">Connect operator</h2><button className="icon-button" aria-label="Close operator access" disabled={accessPending} onClick={() => operatorDialog.current?.close()}><Icon name="close" /></button></div><p className="dialog-help">Find <code>REEFTRACE_LOCAL_TOKEN</code> in your local <code>reeftrace/.env</code>. Enter it here to run workspace actions.</p><form onSubmit={async event => {
      event.preventDefault(); setAccessPending(true); setAccessError("");
      try {
        if (tokenDraft.trim()) await connect(tokenDraft);
        else disconnect();
        setTokenDraft(""); operatorDialog.current?.close();
        setNoticeScope(null); setNoticeTone("info");
        setNotice(tokenDraft.trim() ? "Operator verified for this browser tab." : "Operator access cleared for this tab.");
      } catch (cause) { setAccessError(errorMessage(cause)); }
      finally { setAccessPending(false); }
    }}><label>Local operator token<input type="password" autoComplete="off" value={tokenDraft} onChange={event => setTokenDraft(event.target.value)} disabled={!!busy || preventionBusy || accessPending} placeholder="Enter your local token" /></label><p className="settings-note">Stored only in this tab’s memory. Sponsor keys stay on the server.</p>{accessError && <p className="notice error" role="alert">{accessError}</p>}<div className="dialog-actions">{tokenDraft && <button type="button" className="ghost-button" disabled={!!busy || preventionBusy || accessPending} onClick={() => setTokenDraft("")}>Clear token</button>}<button className="primary-button" type="submit" disabled={!!busy || preventionBusy || accessPending}>{accessPending ? "Verifying…" : "Done"}</button></div></form></dialog>
  </div>;
}
