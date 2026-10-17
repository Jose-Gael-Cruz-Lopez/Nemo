"use client";

import { BRAND_NAME } from "./brand";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Icon } from "./icons";
import { ValidationWorkspace } from "./validation-report";
import { validationAnswerMatches } from "./validation-report-state";
import type { SourceProfile } from "./source-map";
import { canCorrectRejectedTrial, currentPreventionAnswer, decodePendingTrial, definitiveTrialStatus, parseProtectedZone, pendingTrialKey, safeInvestigationFailure, sourceCaseChanged, validTrialObservation, type PendingTrial, type TrialSubmission } from "./prevention-state";
import styles from "./prevention-workspace.module.css";

type Request = <T>(path: string, body?: unknown, options?: { signal?: AbortSignal; independent?: boolean }) => Promise<T>;
type Case = { id: string; profile_id: string; mode: string; state: string; evidence_id: string | null };
type Layout = "baseline" | "intervention";
type Origin = TrialSubmission["data_origin"];
type Bounds = { lower: number; upper: number; denominator?: number };
type Stats = { planned: number; released: number; missing_planned: number; zone_entries: number; captured_before_entry: number; no_entry: number; unresolved: number; token_accounted: number; unaccounted: number; recording_linked: number; entry_rate_bounds: Bounds; observed_entry_rate_bounds?: Bounds };
type Group = { layouts: Record<Layout, Stats>; by_source: { source_id: string; baseline: Stats; intervention: Stats }[]; plan: { expected_total: number; recorded_total: number; complete: boolean; balanced: boolean; order_followed: boolean }; effect_bounds: Bounds };
type SimulationStats = { particles: number; zone_entry_count: number; zone_entry_fraction: number; zone_entry_lower_fraction: number; zone_entry_upper_fraction: number; captured_before_zone_count: number; unresolved_count: number; unsupported_count: number };
type SimulatedPath = { layout: Layout; source_id: string; paths: { points: { t_s: number; x_cm: number; y_cm: number }[] }[] };
type Numerical = { status: string; results: { scenario_id: string; source_id: string; baseline: SimulationStats; intervention: SimulationStats; benefit_fraction: number; benefit_lower_fraction: number; benefit_upper_fraction: number }[]; nominal_paths?: SimulatedPath[]; recommendation: string; robust_benefit_min: number; robust_benefit_max: number; reason_codes: string[]; assumptions: Record<string, unknown> & { limitations?: string[] } };
type Summary = { id: string; name: string; case_id: string; source_evidence_id: string; data_origin: "SYNTHETIC" | "MEASURED_TANK"; status?: string; is_current: boolean; created_at: number };
type Comparison = Summary & { baseline_profile_id: string; intervention_profile_id: string; baseline_profile: SourceProfile; intervention_profile: SourceProfile; protected_zone_cm: number[][]; horizon_s: number; particles: number; trials_per_source: number; source_evidence_status: string; numerical_report: Numerical; plan: { id: string; source_ids: string[]; expected_total: number; sequence: { layout: Layout; source_id: string; repeat: number }[] } };
type Trial = TrialSubmission & { id: string; comparison_id: string; ordinal: number };
type Report = { comparison: Comparison; trials: Trial[]; evaluation: { id: string; snapshot_hash: string; comparison_id: string; physical_validation: false; by_origin: Record<Origin, Group>; limitations: string[] }; is_current: boolean; archive_reason: string | null };
type Answer = { validation_report_id?: string; comparison_id: string; evaluation_digest: string; action: string; explanation: string; live_model_response?: boolean; evidence_ids: string[]; trace?: unknown[]; prevention_evaluation?: { snapshot_hash: string }; failure_code?: unknown; provider_status_code?: unknown; timeout_stage?: unknown };
type Mutate = <T>(label: string, path: string, body: unknown) => Promise<T>;
type Props = { request: Request; operatorConnected: boolean; onRequireOperator: () => void; cases: Case[]; profiles: SourceProfile[]; selectedCaseId: string; onSelectCase: (id: string) => void; onBusyChange: (busy: boolean) => void; onStopCase: (id: string) => Promise<void>; blocked?: boolean };
const percent = (value: number) => `${(value * 100).toFixed(1)}%`;
const interval = (value?: Bounds) => value ? `${percent(value.lower)}–${percent(value.upper)}` : "No trials";
const effectInterval = (value: Bounds) => `${(value.lower * 100).toFixed(1)} to ${(value.upper * 100).toFixed(1)} percentage points`;
const pointsText = (points: number[][]) => points.map(point => point.join(",")).join(" ");
const readable = (text: string) => text.toLowerCase().replaceAll("_", " ");
function errorText(cause: unknown) { return cause instanceof Error ? cause.message : "The request failed. Check the API connection and retry explicitly."; }
function reportValue(value: Report, expectedId?: string): Report {
  if (!value?.comparison?.id || expectedId && value.comparison.id !== expectedId || !Array.isArray(value.trials) || value.evaluation?.comparison_id !== value.comparison.id || typeof value.evaluation.snapshot_hash !== "string" || !value.evaluation.by_origin || !value.comparison.plan?.sequence || !value.comparison.numerical_report) throw new Error("The comparison response is incomplete or belongs to a different plan. Reload it before continuing.");
  return value;
}
async function comparisonHistory(request: Request, signal: AbortSignal) {
  const values = await request<Summary[]>("/prevention/comparisons", undefined, { signal });
  if (!Array.isArray(values)) throw new Error("The comparison history response is incomplete.");
  return values;
}
async function savedComparison(request: Request, id: string, signal: AbortSignal) {
  return reportValue(await request<Report>(`/prevention/comparisons/${encodeURIComponent(id)}`, undefined, { signal }), id);
}
function defaultZone(profile?: SourceProfile) {
  if (!profile) return "";
  const b = profile.bounds, w = b.x_max_cm - b.x_min_cm, h = b.y_max_cm - b.y_min_cm;
  return JSON.stringify([[b.x_min_cm + .75 * w, b.y_min_cm + .35 * h], [b.x_min_cm + .85 * w, b.y_min_cm + .35 * h], [b.x_min_cm + .85 * w, b.y_min_cm + .65 * h], [b.x_min_cm + .75 * w, b.y_min_cm + .65 * h]].map(point => point.map(n => Number(n.toFixed(2)))));
}

function LayoutMap({ profile, zone, label, paths = [] }: { profile?: SourceProfile; zone: number[][]; label: string; paths?: SimulatedPath[] }) {
  const id = useId();
  if (!profile) return <p className="settings-note">Select a registered layout to preview its geometry.</p>;
  const b = profile.bounds, w = b.x_max_cm - b.x_min_cm, h = b.y_max_cm - b.y_min_cm;
  return <figure className={styles.map}><svg role="img" aria-labelledby={`${id}-title ${id}-desc`} viewBox={`${b.x_min_cm - 1} ${b.y_min_cm - 1} ${w + 2} ${h + 2}`}>
    <title id={`${id}-title`}>{label} layout in tank centimetres</title><desc id={`${id}-desc`}>Candidate source regions, collector or retention areas, and the protected zone. Dashed lines, when present, are representative simulated paths, not observed motion.</desc>
    <rect x={b.x_min_cm} y={b.y_min_cm} width={w} height={h} fill="#f2f7f6" stroke="#c0ceca" strokeWidth={w * .002} />
    {profile.sources.map((source, i) => <g key={source.id}><polygon points={pointsText(source.polygon_cm)} fill={["#8bc6d9", "#99b9cc", "#d5b281"][i % 3]} fillOpacity=".6" /><text x={source.polygon_cm[0][0]} y={source.polygon_cm[0][1] - h * .02} fontSize={w * .035} fill="#345a6b">{source.id}</text></g>)}
    {profile.traps?.map(trap => <polygon key={trap.id} points={pointsText(trap.polygon_cm)} fill="#dbe9e0" stroke="#9aafa0" strokeWidth={w * .003}><title>Collector or retention area {trap.id}</title></polygon>)}
    {paths.filter(path => path.layout === label.toLowerCase()).map(path => path.paths.slice(0, 3).map((item, i) => <polyline key={`${path.source_id}-${i}`} points={item.points.map(point => `${point.x_cm},${point.y_cm}`).join(" ")} fill="none" stroke="#087fac" strokeWidth={w * .002} strokeDasharray={`${w * .01} ${w * .008}`} opacity=".55" />))}
    {zone.length >= 3 && <polygon points={pointsText(zone)} fill="#f0c7a7" fillOpacity=".6" stroke="#bd8156" strokeWidth={w * .004}><title>Protected zone, a tabletop reef-area proxy</title></polygon>}
  </svg><figcaption><strong>{label} · {profile.id}</strong>Water plane · cm. {paths.length ? "At most three representative simulated paths per source." : "Geometry preview; no measured outcome is implied."}</figcaption></figure>;
}

function CreatePlan({ cases, profiles, selectedCaseId, onSelectCase, disabled, mutate, onCreated }: Pick<Props, "cases" | "profiles" | "selectedCaseId" | "onSelectCase"> & { disabled: boolean; mutate: Mutate; onCreated: (report: Report) => void }) {
  const active = cases.find(item => item.id === selectedCaseId);
  const baseline = profiles.find(item => item.id === active?.profile_id);
  const choices = profiles.filter(item => item.id !== baseline?.id && item.data_origin === baseline?.data_origin);
  const [interventionId, setInterventionId] = useState("");
  const [name, setName] = useState("Reef-zone interception comparison");
  const [zoneOverride, setZoneOverride] = useState<string | null>(null);
  const [error, setError] = useState("");
  const zoneText = zoneOverride ?? defaultZone(baseline);
  const intervention = choices.find(item => item.id === interventionId);
  let zone: number[][] = [], zoneError = "";
  if (baseline) { try { zone = parseProtectedZone(zoneText, baseline.bounds); } catch (cause) { zoneError = errorText(cause); } }
  const eligible = active?.evidence_id && !["STOPPED", "RECOVERING"].includes(active.state) && baseline && intervention && !zoneError && name.trim();
  async function create() {
    if (!eligible || !active || !baseline || !intervention) return;
    setError("");
    try { onCreated(reportValue(await mutate<Report>("Freezing prevention plan", "/prevention/comparisons", { case_id: active.id, baseline_profile_id: baseline.id, intervention_profile_id: intervention.id, protected_zone_cm: zone, name: name.trim(), horizon_s: 20, particles: 100, trials_per_source: 5 }))); }
    catch (cause) { setError(errorText(cause)); }
  }
  return <details className="card"><summary>Create a frozen comparison from source evidence</summary><div className={`card-body ${styles.form}`}>
    <p className="settings-note">Trace first, then compare independently registered layouts. The same candidate source regions and protected zone must apply to both. Moving a collector can change flow; measure and validate each physical layout separately.</p>
    <label>Source observation<select disabled={disabled} value={selectedCaseId} onChange={event => onSelectCase(event.target.value)}><option value="">Select a source case</option>{cases.map(item => <option key={item.id} value={item.id}>{item.id} · {item.mode} · {item.state}</option>)}</select></label>
    <div className={styles.pair}><label>Baseline layout (fixed by source case)<input readOnly value={baseline?.id ?? "Select an observation"} /></label><label>Intervention layout<select disabled={disabled} value={interventionId} onChange={event => setInterventionId(event.target.value)}><option value="">Select a different registered layout</option>{choices.map(item => <option key={item.id} value={item.id}>{item.id} · {item.data_origin}</option>)}</select></label></div>
    <label>Comparison name<input value={name} maxLength={80} disabled={disabled} onChange={event => setName(event.target.value)} /></label>
    <label>Protected zone · JSON vertices [[x, y], …] in centimetres<textarea rows={3} value={zoneText} disabled={disabled} onChange={event => setZoneOverride(event.target.value)} /></label>
    {zoneError && <p className={styles.validation} role="alert">{zoneError}</p>}
    <div className={styles.maps}><LayoutMap profile={baseline} zone={zone} label="Baseline" /><LayoutMap profile={intervention} zone={zone} label="Intervention" /></div>
    <p className="settings-note">Frozen defaults: 20-second horizon · 100 particles per source/layout/scenario · 5 one-token trials per source/layout. The server validates matching geometry, independent flow evidence and current source evidence.</p>
    {!active?.evidence_id && <p className="settings-note">Select an observation with a saved source report in Investigations first.</p>}
    {error && <p className={styles.validation} role="alert">{error}</p>}
    <button className="primary-button" disabled={disabled || !eligible} onClick={() => void create()}><Icon name="plus" />Freeze comparison</button>
  </div></details>;
}

function OutcomeGroup({ group, physical, predictions }: { group?: Group; physical: boolean; predictions: Numerical["results"] }) {
  if (!group || group.plan.recorded_total === 0) return <p className={styles.scope}>{physical ? "No physical trials yet. Simulated results and synthetic trial records are not physical intervention evidence." : "No synthetic trial records. Predictions remain separate from recorded outcomes."}</p>;
  return <><p className={styles.small}>{group.plan.recorded_total}/{group.plan.expected_total} planned one-token trials recorded · {group.plan.complete ? "Plan complete" : "Plan incomplete"} · {group.plan.balanced ? "Balanced counts" : "Unbalanced counts"} · {group.plan.order_followed ? "Planned order followed" : "Planned order not followed"}.</p>
    <div className="table-scroll"><table className="metrics-table"><caption className="sr-only">{physical ? "Operator-reported physical" : "Synthetic demonstration"} outcomes by source and layout</caption><thead><tr><th>Source / layout</th><th>Released / planned</th><th>Entered</th><th>Intercepted first</th><th>No entry</th><th>Unresolved</th><th>Predicted entry (simulation)</th><th>Recorded entry bounds · planned</th></tr></thead><tbody>{group.by_source.flatMap(row => (["baseline", "intervention"] as const).map(layout => { const s = row[layout], predicted = predictions.find(item => item.source_id === row.source_id)?.[layout]; return <tr key={`${row.source_id}-${layout}`}><th>{row.source_id} · {layout}</th><td>{s.released}/{s.planned}</td><td>{s.zone_entries}</td><td>{s.captured_before_entry}</td><td>{s.no_entry}</td><td>{s.unresolved}</td><td>{predicted && predicted.unsupported_count === 0 ? percent(predicted.zone_entry_fraction) : "Withheld: unsupported paths"}</td><td>{interval(s.entry_rate_bounds)}</td></tr>; }))}</tbody></table></div>
    <p className="settings-note">The predicted column repeats the frozen nominal simulation; it is not an observed outcome. Planned-denominator bounds treat missing and unresolved trials as unknown. They do not pretend unexecuted trials were released. Baseline minus intervention entry-rate bounds: <strong>{effectInterval(group.effect_bounds)}</strong>. Positive values favor intervention; bounds spanning zero do not establish improvement.</p>
    <div className="table-scroll"><table className="metrics-table"><caption className="sr-only">Actually released tokens and accounting</caption><thead><tr><th>Layout</th><th>Released-only entry bounds</th><th>Accounted / released</th><th>Unaccounted</th><th>Recording linked</th></tr></thead><tbody>{(["baseline", "intervention"] as const).map(layout => { const s = group.layouts[layout]; return <tr key={layout}><th>{layout}</th><td>{s.released ? interval(s.observed_entry_rate_bounds) : "No released tokens"}</td><td>{s.token_accounted}/{s.released}</td><td>{s.unaccounted}</td><td>{s.recording_linked}</td></tr>; })}</tbody></table></div>
    <p className="settings-note">{physical ? "These outcomes are entered and confirmed by an operator. A recording link does not automatically validate an outcome." : "These records exercise the ledger only. They were generated for the synthetic demonstration."} A completed small plan does not establish a causal or real-coral benefit.</p>
  </>;
}

function TrialForm({ report, disabled, archived, request, mutate, onUpdated }: { report: Report; disabled: boolean; archived: boolean; request: Request; mutate: Mutate; onUpdated: (value: Report) => void }) {
  const comparison = report.comparison;
  const physical = comparison.data_origin === "MEASURED_TANK";
  const origin: Origin = physical ? "OPERATOR_REPORTED_PHYSICAL" : "SYNTHETIC_DEMO";
  const [pending, setPending] = useState<PendingTrial | null>(() => { try { return typeof window === "undefined" ? null : decodePendingTrial(sessionStorage.getItem(pendingTrialKey(comparison.id)), comparison.id); } catch { return null; } });
  const [outcome, setOutcome] = useState<TrialSubmission["outcome"] | "">("");
  const [time, setTime] = useState("");
  const [accounted, setAccounted] = useState(false);
  const [horizonCompleted, setHorizonCompleted] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [note, setNote] = useState("");
  const [recording, setRecording] = useState("");
  const [error, setError] = useState("");
  const [reconciling, setReconciling] = useState(false);
  const reconciliation = useRef<AbortController | null>(null);
  useEffect(() => () => reconciliation.current?.abort(), []);
  const recorded = report.trials.filter(item => item.data_origin === origin);
  const next = comparison.plan.sequence[recorded.length];
  const needsTime = outcome === "zone_entry" || outcome === "intercepted_before_entry";
  const observation = { outcome: outcome as TrialSubmission["outcome"], data_origin: origin, ...(needsTime && time.trim() !== "" ? outcome === "zone_entry" ? { entry_time_s: Number(time) } : { interception_time_s: Number(time) } : {}), token_accounted: accounted, horizon_completed: horizonCompleted, physical_confirmed: physical && confirmed, note: note.trim() };
  const valid = !!next && !!outcome && validTrialObservation(observation, comparison.horizon_s);
  const alreadySaved = pending && report.trials.find(item => item.trial_key === pending.payload.trial_key);
  function acknowledge() {
    try { sessionStorage.removeItem(pendingTrialKey(comparison.id)); setPending(null); setError(""); }
    catch { setError("The browser could not clear its tab-local retry record. The saved ledger still confirms the trial."); }
  }
  function correctRejected() {
    if (!pending || !canCorrectRejectedTrial(pending, report.trials.map(item => item.trial_key)) || reconciling) return;
    try {
      const p = pending.payload, sameSlot = next?.layout === p.layout && next?.source_id === p.source_id;
      sessionStorage.removeItem(pendingTrialKey(comparison.id)); setPending(null);
      setOutcome(sameSlot ? p.outcome : ""); setTime(sameSlot ? String(p.entry_time_s ?? p.interception_time_s ?? "") : ""); setAccounted(sameSlot && p.token_accounted); setHorizonCompleted(sameSlot && p.horizon_completed); setConfirmed(false); setNote(sameSlot ? p.note : ""); setRecording(sameSlot ? p.recording_id ?? "" : "");
      setError(sameSlot ? "The rejected draft is editable. Correct its fields and reconfirm the actual observation before submitting a fresh key; do not release another token for this correction." : "The rejected draft was cleared, and the ledger has advanced. Verify the next stated layout/source before recording another observation.");
    } catch { setError("The browser could not clear the rejected draft. Its retry key remains retained."); }
  }
  async function save() {
    if ((!pending && !valid) || alreadySaved || reconciling || archived) return;
    setError("");
    let queued = pending;
    try {
      const payload: TrialSubmission = pending?.payload ?? { ...observation, trial_key: crypto.randomUUID(), layout: next.layout, source_id: next.source_id, ...(recording.trim() ? { recording_id: recording.trim() } : {}) };
      queued = { version: 1, comparison_id: comparison.id, payload };
      sessionStorage.setItem(pendingTrialKey(comparison.id), JSON.stringify(queued)); setPending(queued);
      const updated = reportValue(await mutate<Report>("Saving one-token trial", `/prevention/comparisons/${encodeURIComponent(comparison.id)}/trials`, payload), comparison.id);
      if (!updated.trials.some(item => item.trial_key === payload.trial_key)) throw new Error("The server did not confirm this trial key. Reload the comparison or retry the same trial.");
      onUpdated(updated); sessionStorage.removeItem(pendingTrialKey(comparison.id)); setPending(null); setOutcome(""); setTime(""); setAccounted(false); setHorizonCompleted(false); setConfirmed(false); setNote(""); setRecording("");
    } catch (cause) {
      setError(errorText(cause));
      const status = definitiveTrialStatus(cause);
      if (status !== null && queued) {
        const controller = new AbortController(); reconciliation.current = controller; setReconciling(true);
        try {
          const saved = await savedComparison(request, comparison.id, controller.signal);
          if (controller.signal.aborted) return;
          if (!saved.trials.some(item => item.trial_key === queued!.payload.trial_key)) {
            const rejected = { ...queued, rejected_status: status };
            sessionStorage.setItem(pendingTrialKey(comparison.id), JSON.stringify(rejected)); setPending(rejected);
          }
          onUpdated(saved);
        } catch (readFailure) { if (!controller.signal.aborted) setError(`${errorText(cause)} The ledger could not be reconciled: ${errorText(readFailure)}. Keep the exact queued trial until it can be checked.`); }
        finally { if (!controller.signal.aborted) setReconciling(false); }
      }
    }
  }
  return <section className="card"><div className="card-header"><h2 className="card-title">One-token trial ledger</h2><span className="pill">{physical ? "Operator-reported physical" : "Synthetic demonstration"}</span></div><div className={`card-body ${styles.form}`}>
    <p className="settings-note">The source label is the operator’s release log for this experiment. It is not a source inferred by {BRAND_NAME}. Record exactly one token per trial, following the frozen sequence.</p>
    {alreadySaved ? <div className={styles.scope}><p>This tab’s pending trial is already present in the saved ledger. No duplicate will be posted.</p><button className="secondary-button" disabled={disabled || reconciling} onClick={acknowledge}>Acknowledge saved trial</button></div> : pending ? <div className={styles.scope}><p><strong>{pending.rejected_status ? `Rejected submission (HTTP ${pending.rejected_status})` : "Unconfirmed submission"}:</strong> {pending.payload.layout} · source {pending.payload.source_id} · {readable(pending.payload.outcome)}.</p><p>{pending.rejected_status ? "The completed rejection was reconciled against the ledger; this key was absent. You may correct the rejected draft explicitly." : "The exact payload and key are retained in this tab until confirmed. Retry the same trial; do not release another token."}</p><code className={styles.small}>{pending.payload.trial_key}</code>{pending.rejected_status && <button className="secondary-button" disabled={disabled || reconciling} onClick={correctRejected}>Correct rejected draft</button>}</div> : next ? <p className={styles.scope}><strong>Next trial {recorded.length + 1}/{comparison.plan.expected_total}:</strong> {next.layout} layout · source {next.source_id} · repeat {next.repeat}. Observe for the complete {comparison.horizon_s}-second horizon.</p> : <p className={styles.scope}>The frozen trial sequence is complete. Inspect its recorded outcomes below; additional trials require a new comparison.</p>}
    {reconciling && <p className="settings-note" role="status">Checking the saved ledger before unlocking this rejected draft…</p>}
    {!pending && next && <fieldset disabled={disabled || archived}><legend>{physical ? "What physically happened?" : "Enter a synthetic test outcome"}</legend><div className={styles.form}>
      <div className={styles.pair}><label>Observed outcome<select value={outcome} onChange={event => { setOutcome(event.target.value as typeof outcome); setTime(""); }}><option value="">Choose an outcome</option><option value="zone_entry">Entered protected zone</option><option value="intercepted_before_entry">Intercepted before entry</option><option value="no_entry">No zone entry during horizon</option><option value="unresolved">Unresolved observation</option></select></label>{needsTime && <label>{outcome === "zone_entry" ? "First zone entry" : "Interception"} time · seconds<input type="number" min={0} max={comparison.horizon_s} step="any" value={time} onChange={event => setTime(event.target.value)} /></label>}</div>
      <label>Observation note<textarea rows={2} maxLength={1000} value={note} onChange={event => setNote(event.target.value)} placeholder="Record what you observed, including missed tracking or uncertainty." /></label>
      {physical && <label>Recording ID, if a matching recording exists<input maxLength={100} value={recording} onChange={event => setRecording(event.target.value)} placeholder="Leave blank when this trial has no recording." /></label>}
      <label className={styles.checkbox}><input type="checkbox" checked={accounted} onChange={event => setAccounted(event.target.checked)} /><span>The single token is {physical ? "physically accounted for" : "accounted for in this synthetic record"}. Required for all resolved outcomes.</span></label>
      <label className={styles.checkbox}><input type="checkbox" checked={horizonCompleted} onChange={event => setHorizonCompleted(event.target.checked)} /><span>{physical ? "I observed this trial for" : "This synthetic record covers"} the full {comparison.horizon_s}-second horizon. Required for no-entry and intercepted-before-entry outcomes.</span></label>
      {physical && <label className={styles.checkbox}><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} /><span>I performed this physical trial in the stated layout and verified the recorded outcome.</span></label>}
    </div></fieldset>}
    {error && <p className={styles.validation} role="alert">{error} The retry key is retained if a submission was queued.</p>}
    {!alreadySaved && !pending?.rejected_status && (pending || next) && <button className="primary-button" disabled={disabled || archived || reconciling || !pending && !valid} onClick={() => void save()}><Icon name="check" />{pending ? "Retry the same trial" : "Save one-token outcome"}</button>}
    <details className="details-panel"><summary>Saved trial records ({report.trials.length})</summary><div className={styles.ledger}><table className="metrics-table"><caption className="sr-only">Persisted one-token trial records</caption><thead><tr><th>Trial</th><th>Layout / source</th><th>Origin / outcome</th><th>Accounted</th></tr></thead><tbody>{report.trials.map(trial => <tr key={trial.id}><th>{trial.ordinal}<details><summary>Details</summary><pre className="code-block">{JSON.stringify(trial, null, 2)}</pre></details></th><td>{trial.layout} · {trial.source_id}</td><td><span className={styles.outcome}><span>{readable(trial.data_origin)}</span><span>{readable(trial.outcome)}</span></span></td><td>{trial.token_accounted ? "Yes" : "No"}</td></tr>)}</tbody></table></div></details>
  </div></section>;
}

function ComparisonDetail({ report, cases, disabled, request, mutate, onUpdated, snapshotReadAt, operatorConnected, onRequireOperator }: { report: Report; cases: Case[]; disabled: boolean; request: Request; mutate: Mutate; onUpdated: (value: Report) => void; snapshotReadAt?: number; operatorConnected: boolean; onRequireOperator: () => void }) {
  const c = report.comparison, numerical = c.numerical_report;
  const current = report.is_current && !sourceCaseChanged(c, cases);
  const [question, setQuestion] = useState("Which layout is supported by the simulation, what do the recorded trials show, and what evidence is still missing?");
  const [answerResult, setAnswer] = useState<Answer | null>(null);
  const [error, setError] = useState("");
  const [selectedValidationReport, setSelectedValidationReport] = useState<{ id: string; evaluationHash: string } | null>(null);
  const validationReportId = current && selectedValidationReport?.evaluationHash === report.evaluation.snapshot_hash ? selectedValidationReport.id : "";
  const answer = current && validationAnswerMatches(answerResult, validationReportId) ? currentPreventionAnswer(answerResult, c.id, report.evaluation.snapshot_hash) : null;
  const failure = answer ? safeInvestigationFailure(answer) : null;
  async function ask() {
    if (!current || !question.trim()) return;
    setError(""); setAnswer(null);
    try {
      const value = await mutate<Answer>("Investigating prevention evidence", `/prevention/comparisons/${encodeURIComponent(c.id)}/investigate`, { text: question.trim(), ...(validationReportId ? { validation_report_id: validationReportId } : {}) });
      if (!currentPreventionAnswer(value, c.id, report.evaluation.snapshot_hash) || !validationAnswerMatches(value, validationReportId)) throw new Error("The trial evaluation or selected validation receipt changed during the investigation. Reload this comparison before asking again.");
      setAnswer(value);
    } catch (cause) { setError(errorText(cause)); }
  }
  const nominal = numerical.results.filter(item => item.scenario_id === "nominal");
  return <div className={styles.stack}>
    <section className="card"><div className={`card-header ${styles.header}`}><div><h2 className="card-title">{c.name}</h2><p className="card-subtitle">{c.id}</p></div><span className={`pill ${c.data_origin === "SYNTHETIC" ? "amber" : "neutral"}`}>{c.data_origin === "SYNTHETIC" ? "SYNTHETIC DEMONSTRATION" : "Measured layout inputs"}</span></div><div className="card-body">
      {!current && <p className={styles.scope} role="status"><strong>Archived comparison.</strong> Its source case was stopped, changed or recomputed. Read its frozen evidence; create a fresh comparison before adding trials or asking Chalk.</p>}
      <div className={styles.badges}><span className="pill">Source evidence: {c.source_evidence_status}</span><span className="pill">{c.horizon_s}s horizon</span><span className="pill">{c.trials_per_source} trials / source / layout</span></div>
      <p className="settings-note">Frozen source report <code>{c.source_evidence_id}</code>. Comparisons consider every declared source; relative source-support scores are not treated as calibrated probabilities.</p>
      <p className={styles.small}>Frozen evaluation <code>{report.evaluation.id}</code>{snapshotReadAt ? ` · Last snapshot read ${new Date(snapshotReadAt).toISOString()}` : ""}. Saved evidence refreshes every five seconds while idle. A changed ledger clears the previous answer and unsaved trial draft; submitted retry data is retained.</p>
      <div className={styles.maps}><LayoutMap profile={c.baseline_profile} zone={c.protected_zone_cm} label="Baseline" paths={numerical.nominal_paths} /><LayoutMap profile={c.intervention_profile} zone={c.protected_zone_cm} label="Intervention" paths={numerical.nominal_paths} /></div>
      <div className={styles.mapLegend}><span><i className={`${styles.key} ${styles.protectedKey}`} />Protected-zone proxy</span><span><i className={`${styles.key} ${styles.trapKey}`} />Collector / retention area</span><span><i className={`${styles.key} ${styles.pathKey}`} />Representative simulated route</span></div>
    </div></section>
    <section className="card"><div className="card-header"><div><h2 className="card-title">Predicted entry, by source</h2><p className="card-subtitle">Simulation only · {readable(numerical.status)}</p></div></div><div className="card-body">
      <p className={styles.scope}>These particle counts are conditional model predictions, including when layout inputs were measured. They are separate from the one-token trial ledger. They do not establish coral damage avoided.</p>
      {nominal.length ? <div className="table-scroll"><table className="metrics-table"><caption className="sr-only">Nominal simulated protected-zone entries by source and layout</caption><thead><tr><th>Source</th><th>Baseline entry / particles</th><th>Intervention entry / particles</th><th>Baseline entry bounds</th><th>Intervention entry bounds</th><th>Benefit bounds</th></tr></thead><tbody>{nominal.map(row => <tr key={row.source_id}><th>{row.source_id}</th><td><meter className={styles.bar} min={0} max={1} value={row.baseline.zone_entry_fraction} aria-label={`Simulated baseline entry fraction for source ${row.source_id}`} />{row.baseline.zone_entry_count}/{row.baseline.particles}</td><td><meter className={styles.bar} min={0} max={1} value={row.intervention.zone_entry_fraction} aria-label={`Simulated intervention entry fraction for source ${row.source_id}`} />{row.intervention.zone_entry_count}/{row.intervention.particles}</td><td>{interval({ lower: row.baseline.zone_entry_lower_fraction, upper: row.baseline.zone_entry_upper_fraction })}</td><td>{interval({ lower: row.intervention.zone_entry_lower_fraction, upper: row.intervention.zone_entry_upper_fraction })}</td><td>{interval({ lower: row.benefit_lower_fraction, upper: row.benefit_upper_fraction })}</td></tr>)}</tbody></table></div> : <p className="settings-note">The numerical report withheld a comparison because flow support was insufficient.</p>}
      <p className="settings-note">Across declared sources and frozen scenarios: <strong>{readable(numerical.recommendation)}</strong>. Conservative benefit range {effectInterval({ lower: numerical.robust_benefit_min, upper: numerical.robust_benefit_max })}. Positive means fewer modeled entries with intervention. Unsupported paths remain unknown.</p>
      {numerical.reason_codes.length > 0 && <ul className="reason-list">{numerical.reason_codes.map(reason => <li key={reason}>{readable(reason)}</li>)}</ul>}
      <details className="details-panel"><summary>Simulation assumptions and full frozen comparison</summary><ul className="reason-list">{[...Object.values(numerical.assumptions).filter((value): value is string => typeof value === "string"), ...(numerical.assumptions.limitations ?? [])].map((assumption, i) => <li key={i}>{assumption}</li>)}</ul><pre className="code-block">{JSON.stringify(c, null, 2)}</pre></details>
    </div></section>
    <section className="card"><div className="card-header"><h2 className="card-title">Recorded physical outcomes</h2><span className="pill">Operator-reported evidence</span></div><div className="card-body"><OutcomeGroup group={report.evaluation.by_origin.OPERATOR_REPORTED_PHYSICAL} physical predictions={nominal} /></div></section>
    <section className="card"><div className="card-header"><h2 className="card-title">Synthetic ledger outcomes</h2><span className="pill amber">Demonstration only</span></div><div className="card-body"><OutcomeGroup group={report.evaluation.by_origin.SYNTHETIC_DEMO} physical={false} predictions={nominal} /></div></section>
    <TrialForm key={`${c.id}:${report.evaluation.snapshot_hash}`} report={report} disabled={disabled} archived={!current} request={request} mutate={mutate} onUpdated={onUpdated} />
    <ValidationWorkspace request={request} mutate={mutate} comparisonId={c.id} caseId={c.case_id} sourceEvidenceId={c.source_evidence_id} evaluationHash={report.evaluation.snapshot_hash} current={current} operatorConnected={operatorConnected} onRequireOperator={onRequireOperator} availableOrigins={Object.entries(report.evaluation.by_origin).map(([origin, group]) => ({ data_origin: origin as Origin, recorded_count: group.plan.recorded_total }))} blocked={disabled} onSelected={id => { setAnswer(null); setSelectedValidationReport(id ? { id, evaluationHash: report.evaluation.snapshot_hash } : null); }} />
    <section className="card"><div className="card-header"><h2 className="card-title">Ask Chalk about this comparison</h2><Icon name="agent" /></div><div className={`card-body ${styles.form}`}><label>Evidence question<textarea rows={3} maxLength={4000} value={question} disabled={disabled || !current} onChange={event => setQuestion(event.target.value)} /></label><button className="primary-button" disabled={disabled || !current || !question.trim()} onClick={() => void ask()}><Icon name="agent" />Ask Chalk about prevention</button><p className="settings-note">One explicit model request. It reads frozen simulation and trial evidence; no messages, actuator commands or automatic retries are sent.</p><p className="settings-note">Selected validation receipt: {validationReportId ? <code>{validationReportId}</code> : "None for this current evaluation"}.</p>{error && <p className={styles.validation} role="alert">{error}</p>}{answer && <div className={styles.answer}><span className="pill">{answer.live_model_response ? answer.action : "No live model response"}</span><p>{answer.explanation}</p>{failure && <div className={styles.scope} role="status"><p>{failure.message}</p><p className="settings-note">{failure.code && <>Failure code: <code>{failure.code}</code>. </>}{failure.httpStatus !== null && <>Provider HTTP status: <strong>{failure.httpStatus}</strong>. </>}{failure.stage && <>Timeout stage: <code>{failure.stage}</code>.</>}</p></div>}<p className="settings-note">Live model response: {answer.live_model_response ? "yes" : "no"} · Evaluation {answer.evaluation_digest} · Evidence {answer.evidence_ids.join(", ") || "none"}</p><details className="details-panel"><summary>Investigation tool trace</summary><pre className="code-block">{JSON.stringify(answer.trace, null, 2)}</pre></details></div>}</div></section>
    <details className="card"><summary>Frozen plan, evaluation and provenance</summary><div className="card-body"><ul className="reason-list">{report.evaluation.limitations.map((limit, i) => <li key={i}>{limit}</li>)}</ul><p className="settings-note">Evaluation snapshot hash</p><code className="evidence-id">{report.evaluation.snapshot_hash}</code><pre className="code-block">{JSON.stringify(report.evaluation, null, 2)}</pre></div></details>
  </div>;
}

export function PreventionWorkspace({ request, operatorConnected, onRequireOperator, cases, profiles, selectedCaseId, onSelectCase, onBusyChange, onStopCase, blocked = false }: Props) {
  const [comparisons, setComparisons] = useState<Summary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [readError, setReadError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  const [loading, setLoading] = useState(false);
  const [readAttempt, setReadAttempt] = useState(0);
  const [stopping, setStopping] = useState(false);
  const [snapshotRead, setSnapshotRead] = useState<{ comparison_id: string; snapshot_hash: string; at: number } | null>(null);
  const readController = useRef<AbortController | null>(null);
  const writeController = useRef<AbortController | null>(null);
  const listController = useRef<AbortController | null>(null);
  const readRun = useRef(0);
  const selectedRef = useRef("");
  const disabled = !!busy || blocked || stopping;
  function updated(value: Report) {
    setReport(value); selectedRef.current = value.comparison.id; setSelectedId(value.comparison.id);
    setSnapshotRead({ comparison_id: value.comparison.id, snapshot_hash: value.evaluation.snapshot_hash, at: Date.now() });
    setComparisons(previous => [{ ...value.comparison, is_current: value.is_current }, ...previous.filter(item => item.id !== value.comparison.id)]);
  }
  const readList = useCallback(async () => {
    listController.current?.abort(); const controller = new AbortController(); listController.current = controller;
    try {
      const values = await comparisonHistory(request, controller.signal);
      if (!controller.signal.aborted) { setComparisons(values); setReadError(""); if (!selectedRef.current && values[0]) { selectedRef.current = values[0].id; setSelectedId(values[0].id); } }
    } catch (cause) { if (!controller.signal.aborted) setReadError(errorText(cause)); }
  }, [request]);
  useEffect(() => {
    const controller = new AbortController(); listController.current = controller;
    void comparisonHistory(request, controller.signal).then(values => {
      if (!controller.signal.aborted) { setComparisons(values); setReadError(""); if (!selectedRef.current && values[0]) { selectedRef.current = values[0].id; setSelectedId(values[0].id); } }
    }).catch(cause => { if (!controller.signal.aborted) setReadError(errorText(cause)); });
    return () => controller.abort();
  }, [request]);
  function readComparison(id: string) {
    if (id !== selectedRef.current) return;
    setLoading(true); setReadError(""); setReadAttempt(attempt => attempt + 1);
  }
  useEffect(() => {
    if (!selectedId || busy || blocked || stopping) return;
    const controller = new AbortController(); let timer: ReturnType<typeof setTimeout>;
    function tick() {
      readController.current = controller; const run = ++readRun.current;
      void savedComparison(request, selectedId, controller.signal).then(value => {
        if (!controller.signal.aborted && selectedRef.current === selectedId && run === readRun.current) { setReport(value); setReadError(""); setSnapshotRead({ comparison_id: selectedId, snapshot_hash: value.evaluation.snapshot_hash, at: Date.now() }); setComparisons(previous => previous.map(item => item.id === selectedId ? { ...item, is_current: value.is_current } : item)); }
      }).catch(cause => { if (!controller.signal.aborted && selectedRef.current === selectedId && run === readRun.current) setReadError(errorText(cause)); }).finally(() => {
        if (!controller.signal.aborted) { if (run === readRun.current) setLoading(false); timer = setTimeout(tick, 5000); }
      });
    }
    tick();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [selectedId, request, busy, blocked, stopping, readAttempt]);
  useEffect(() => () => { ++readRun.current; readController.current?.abort(); writeController.current?.abort(); onBusyChange(false); }, [onBusyChange]);
  async function mutate<T>(label: string, path: string, body: unknown): Promise<T> {
    if (writeController.current || blocked) throw new Error("Wait for the current workspace action to finish.");
    if (!operatorConnected) { onRequireOperator(); throw new Error("Connect operator access, then retry this action."); }
    const controller = new AbortController(); writeController.current = controller; onBusyChange(true); setBusy(label); setError(""); setNotice("");
    ++readRun.current; readController.current?.abort(); setLoading(false);
    let authenticate = false;
    try { return await request<T>(path, body, { signal: controller.signal, independent: true }); }
    catch (cause) { authenticate = typeof cause === "object" && cause !== null && "status" in cause && cause.status === 401; throw cause; }
    finally { if (writeController.current === controller) { writeController.current = null; setBusy(""); onBusyChange(false); if (authenticate) onRequireOperator(); } }
  }
  async function demo() {
    try { const value = reportValue(await mutate<Report>("Loading synthetic prevention demo", "/prevention/demo", {})); updated(value); setNotice("Synthetic comparison loaded. All populated trial outcomes are demonstration records. No physical trial was performed."); }
    catch (cause) { setError(errorText(cause)); }
  }
  function select(id: string) {
    if (disabled) return;
    ++readRun.current; readController.current?.abort(); selectedRef.current = id; setSelectedId(id); setReport(null); setLoading(true); setError(""); setReadError(""); setNotice("");
  }
  async function stopInvestigation() {
    const id = report?.comparison.case_id;
    if (!id || stopping) return;
    setStopping(true);
    const pending = writeController.current;
    try { await onStopCase(id); pending?.abort(); await readComparison(report.comparison.id); }
    catch (cause) { setError(errorText(cause)); }
    finally { setStopping(false); }
  }
  const selectedReport = report?.comparison.id === selectedId ? report : null;
  return <div className={styles.stack}>
    <div className="page-heading"><div><p className="kicker">Trace → compare → intervene → verify</p><h1>Prevent the next entry.</h1><p className={`page-description ${styles.intro}`}>Compare two frozen tank layouts, then record whether fewer tokens reached a predefined reef-area proxy. Source tracing remains the evidence behind the experiment.</p></div><button className="primary-button" disabled={disabled} onClick={() => void demo()}><Icon name="play" />Load prevention demo</button></div>
    <div className="notice info"><Icon name="help" /><span>Simulation is a hypothesis. Operator-reported trials are separate evidence. Neither establishes real-coral impact or identifies a polluter.</span></div>
    {!operatorConnected && <div className="notice info"><Icon name="key" /><span>Read saved comparisons freely. Connect operator access to freeze a plan, save trials or ask Chalk.</span><button className="card-link" onClick={onRequireOperator}>Connect operator</button></div>}
    {busy && <div className="busy-notice" role="status"><span>{busy}… No camera, pump or messaging action is being performed.</span>{busy === "Investigating prevention evidence" && <button className="danger-button" disabled={stopping || blocked} onClick={() => void stopInvestigation()}>Stop source case</button>}</div>}
    {notice && <p className="notice info" role="status">{notice}</p>}
    {(error || readError) && <div className="notice error" role="alert"><span>{error || readError}</span><button className="card-link" disabled={disabled} onClick={() => { setError(""); setReadError(""); void readList(); if (selectedId) void readComparison(selectedId); }}>Reload saved comparisons</button></div>}
    <CreatePlan key={selectedCaseId} cases={cases} profiles={profiles} selectedCaseId={selectedCaseId} onSelectCase={onSelectCase} disabled={disabled} mutate={mutate} onCreated={updated} />
    <div className={styles.columns}><section className="card"><div className={`card-header ${styles.header}`}><h2 className="card-title">Saved comparisons</h2><button className="card-link" disabled={disabled} onClick={() => { void readList(); if (selectedId) void readComparison(selectedId); }}>Reload</button></div><div className={styles.history}>{comparisons.length ? comparisons.map(item => <button key={item.id} disabled={disabled} aria-current={item.id === selectedId ? "true" : undefined} onClick={() => select(item.id)}><strong>{item.name}</strong><small>{item.data_origin === "SYNTHETIC" ? "SYNTHETIC DEMO" : "Measured inputs"} · {item.is_current && !sourceCaseChanged(item, cases) ? "Current" : "Archived"}</small><small>{item.id}</small></button>) : <p className="settings-note">No saved comparison yet. Load the explicitly synthetic demonstration or create a plan from registered layouts.</p>}</div></section>
      <div className={styles.stack}>{loading && <p className="busy-notice" role="status">Loading saved comparison…</p>}{selectedReport ? <ComparisonDetail key={selectedReport.comparison.id} report={selectedReport} cases={cases} disabled={disabled || loading} request={request} mutate={mutate} onUpdated={updated} operatorConnected={operatorConnected} onRequireOperator={onRequireOperator} snapshotReadAt={snapshotRead?.comparison_id === selectedReport.comparison.id && snapshotRead.snapshot_hash === selectedReport.evaluation.snapshot_hash ? snapshotRead.at : undefined} /> : !loading && <section className="card empty-state"><Icon name="wave" /><p>Select or create a prevention comparison.</p><span>Each plan freezes the source evidence, both layouts, protected zone and trial sequence.</span></section>}</div>
    </div>
  </div>;
}
