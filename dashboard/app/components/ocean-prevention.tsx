"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { Icon } from "./icons";
import { useOperator } from "./operator-provider";
import { HelpLabel, PlotSeriesControls } from "./plot-controls";
import { readVectorResponse } from "./vector-diagnostic-state";
import { type OceanLayout, type OceanOutcome, type OceanPoint, type OceanPreventionAnswer, type OceanPreventionReport, type OceanXY, validateOceanPrevention, validateOceanPreventionAnswer } from "./ocean-prevention-state";
import styles from "./ocean-prevention.module.css";
import { OceanNumerics } from "./ocean-numerics";

const date = (value: string) => value.replace("T", " ").replace(/:00(?:\.000)?Z$/, " UTC");
const fmt = (value: number) => value.toLocaleString(undefined, { maximumFractionDigits: 1 });
const bounds = (range: [number, number]) => range[0] === range[1] ? `${range[0]}` : `${range[0]}–${range[1]}`;
const palette = ["#087fac", "#9a6d31"];
const outcomeText = (outcome: OceanOutcome) => ({ ENTERED_PROTECTED_ZONE: "entered the hypothetical protected zone", IDEALIZED_INTERCEPTION: "idealized first-contact capture", NO_ENTRY_WITHIN_HORIZON: "no entry during the supported six-hour horizon", UNRESOLVED: "unresolved after forcing stopped" })[outcome.status];
const releaseName = (identity: string) => `R${identity.replace(/^release-/, "")}`;
export type OceanVisibility = { baseline: boolean; layoutA: boolean; layoutB: boolean; reef: boolean; interceptors: boolean; currents: boolean };
export const DEFAULT_OCEAN_VISIBILITY: OceanVisibility = { baseline: false, layoutA: true, layoutB: true, reef: true, interceptors: true, currents: false };

/** Display controls never change the common domain, summaries or six-release denominator. */
export function OceanPreventionFigure({ report, visible, frame = 0, releaseId = "all", onToggle }: { report: OceanPreventionReport; visible: OceanVisibility; frame?: number; releaseId?: string; onToggle: (id: string, checked: boolean) => void }) {
  const title = useId(), marker = useId().replaceAll(":", "");
  const allLayouts = [report.baseline, ...report.layouts];
  const positions: OceanXY[] = [...report.protected_zone.polygon_xy_m, ...report.releases.map(p => [p.x_m, p.y_m] as OceanXY), ...allLayouts.flatMap(layout => [...layout.segments.flatMap(s => [s.start_xy_m, s.end_xy_m]), ...layout.outcomes.flatMap(o => o.track.map(p => [p.x_m, p.y_m] as OceanXY))])];
  const xs = [...positions.map(p => p[0]), ...report.display_bounds_xy_m.x_m], ys = [...positions.map(p => p[1]), ...report.display_bounds_xy_m.y_m];
  const span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys), 1000) * 1.24;
  const cx = (Math.max(...xs) + Math.min(...xs)) / 2, cy = (Math.max(...ys) + Math.min(...ys)) / 2;
  const screen = ([x, y]: OceanXY) => [360 + (x - cx) * 392 / span, 227 - (y - cy) * 392 / span];
  const line = (track: OceanPoint[]) => track.map(p => screen([p.x_m, p.y_m]).join(",")).join(" ");
  const frames = report.vector_frames ?? [], vectors = frames[frame]?.vectors ?? [];
  const vectorScale = Math.max(...frames.flatMap(f => f.vectors.map(v => Math.hypot(v.eastward_m_s, v.northward_m_s))), 0.01);
  const frameOrigin = report.scenario.frame;
  const vectorXY = (v: (typeof vectors)[number]): OceanXY => [v.x_m ?? (v.longitude_deg - frameOrigin.origin_longitude_deg) * frameOrigin.east_metres_per_degree, v.y_m ?? (v.latitude_deg - frameOrigin.origin_latitude_deg) * frameOrigin.north_metres_per_degree];
  const empty = !visible.baseline && !visible.layoutA && !visible.layoutB && !visible.reef && !visible.interceptors && (!visible.currents || frames.length === 0);
  const selected = (layout: OceanLayout) => layout.outcomes.filter(o => releaseId === "all" || o.release_id === releaseId);
  const description = (outcome: OceanOutcome, p: OceanPoint, label: string) => `${releaseName(outcome.release_id)} · ${label} · ${date(p.time_utc)} · ${fmt(p.elapsed_s / 3600)} h · ${outcomeText(outcome)}. All positions are simulated.`;
  function paths(layout: OceanLayout, color: string, id: string, dashed: boolean) {
    return <g data-ocean-layer={id}>{selected(layout).map(outcome => {
      const end = outcome.track.at(-1), endpoint = end ? screen([end.x_m, end.y_m]) : null;
      return <g key={outcome.release_id} data-release-id={outcome.release_id} data-outcome={outcome.status}>
        {outcome.track.length > 0 && !dashed && <polyline points={line(outcome.track)} stroke={color} strokeWidth="8" strokeOpacity=".2" strokeLinecap="round" strokeLinejoin="round" fill="none" aria-hidden="true" />}
        {outcome.track.length > 0 && <polyline points={line(outcome.track)} stroke={color} strokeWidth={dashed ? 2.3 : 1.8} strokeDasharray={dashed ? "7 5" : undefined} strokeLinecap="round" strokeLinejoin="round" fill="none"><title>{`${releaseName(outcome.release_id)} · ${layout.label} · ${outcomeText(outcome)}. Current-driven prediction, not an observed trajectory.`}</title></polyline>}
        {outcome.track.filter((_, i) => i > 0 && i % 12 === 0).map(p => { const [x, y] = screen([p.x_m, p.y_m]); return <circle key={p.time_utc} cx={x} cy={y} r="1.9" fill={color} opacity=".75"><title>{description(outcome, p, layout.label)}</title></circle>; })}
        {end && endpoint && <g tabIndex={0} aria-label={description(outcome, end, layout.label)}><title>{description(outcome, end, layout.label)}</title>
          {outcome.status === "IDEALIZED_INTERCEPTION" ? <rect x={endpoint[0] - 4.5} y={endpoint[1] - 4.5} width="9" height="9" fill={color} stroke="white" strokeWidth="1.5" />
            : outcome.status === "ENTERED_PROTECTED_ZONE" ? <path d={`M${endpoint[0]},${endpoint[1] - 6.5}l6.5,11h-13Z`} fill={color} stroke="white" strokeWidth="1.5" strokeLinejoin="round" />
              : outcome.status === "UNRESOLVED" ? <path d={`M${endpoint[0] - 4},${endpoint[1] - 4}l8,8m-8,0l8,-8`} stroke={color} strokeWidth="2.5" strokeLinecap="round" />
                : <circle cx={endpoint[0]} cy={endpoint[1]} r="4.5" fill="white" stroke={color} strokeWidth="2" />}
        </g>}
      </g>;
    })}</g>;
  }
  return <figure className={styles.figure}>
    <PlotSeriesControls legend="Choose the layers to compare" series={[
      { id: "baseline", label: "No interception", explanation: "Changing-current trajectories without an interception line. This is another dynamic simulation, not a constant-speed path.", color: "#8296a3", dashed: true, checked: visible.baseline },
      { id: "layoutA", label: `Layout A · ${report.layouts[0].label}`, explanation: "Dynamic paths stop at their first idealized capture or protected-zone entry. Solid blue. The blue halo helps distinguish overlapping paths; it does not represent uncertainty.", color: palette[0], checked: visible.layoutA },
      { id: "layoutB", label: `Layout B · ${report.layouts[1].label}`, explanation: "The same changing currents and releases, with the other line layout. Dashed gold.", color: palette[1], dashed: true, checked: visible.layoutB },
      { id: "reef", label: "Protected reef proxy", explanation: "Hypothetical protected polygon. It is not a mapped real reef boundary.", color: "#d57a40", checked: visible.reef },
      { id: "interceptors", label: "Interception lines", explanation: "Illustrative ideal absorbing lines. Each layout has the same 2,000 metre total line length; feasibility and capture efficiency are unmeasured.", color: "#368c76", checked: visible.interceptors },
      ...(frames.length ? [{ id: "currents", label: "Changing-current arrows", explanation: "Direction and relative speed sampled from the captured model field. These are interpolated display vectors, not finer observations.", color: "#758da0", checked: visible.currents }] : []),
    ]} onChange={onToggle} />
    {empty && <p className={styles.scope} role="status">No layers selected. Check a layout or geometry layer to inspect it. All six releases remain in the comparison.</p>}
    <svg className={styles.plot} viewBox="132 0 456 484" role="img" aria-labelledby={title}>
      <title id={title}>One combined ocean comparison: dynamic current-driven paths for two hypothetical interception layouts, an optional no-interception context and protected reef-area proxy. Equal east/north metre scales. No measured waste, real reef boundary or measured protection.</title>
      <defs>
        <marker id={marker} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="#758da0" /></marker>
        <clipPath id={`${marker}-clip`}><rect x="152" y="19" width="416" height="416" /></clipPath>
        <linearGradient id={`${marker}-sea`} x1="0" y1="0" x2="0.4" y2="1"><stop offset="0" stopColor="#f1f9fd" /><stop offset="1" stopColor="#e1f0f8" /></linearGradient>
        <linearGradient id={`${marker}-reef`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#fbe9db" /><stop offset="1" stopColor="#f5d8c2" /></linearGradient>
        <pattern id={`${marker}-hatch`} width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="8" stroke="#e3a57a" strokeWidth="1" strokeOpacity=".35" /></pattern>
      </defs>
      <rect x="164" y="31" width="392" height="392" fill={`url(#${marker}-sea)`} stroke="#cfe4f0" />
      {[1, 2, 3].map(i => <g key={i} stroke="#ffffff" strokeOpacity=".9" strokeWidth="1"><line x1={164 + i * 98} y1="31" x2={164 + i * 98} y2="423" /><line x1="164" y1={31 + i * 98} x2="556" y2={31 + i * 98} /></g>)}
      {visible.currents && frames.length > 0 && <g data-ocean-layer="currents" clipPath={`url(#${marker}-clip)`}>{vectors.map((v, i) => { const [x, y] = screen(vectorXY(v)); return <line key={i} x1={x} y1={y} x2={x + v.eastward_m_s / vectorScale * 24} y2={y - v.northward_m_s / vectorScale * 24} stroke="#758da0" strokeWidth="1.4" strokeLinecap="round" opacity=".8" markerEnd={`url(#${marker})`}><title>{`Interpolated model current ${Math.hypot(v.eastward_m_s, v.northward_m_s).toFixed(3)} m/s · ${date(frames[frame].time_utc)}`}</title></line>; })}</g>}
      {visible.reef && (() => { const points = report.protected_zone.polygon_xy_m.map(p => screen(p).join(",")).join(" "), label = screen(report.protected_zone.polygon_xy_m[0])[0], top = screen(report.protected_zone.polygon_xy_m[2])[1]; return <g data-ocean-layer="reef"><polygon points={points} fill={`url(#${marker}-reef)`} /><polygon points={points} fill={`url(#${marker}-hatch)`} stroke="#d57a40" strokeWidth="1.6" strokeLinejoin="round" /><rect x={label} y={top - 26} width="138" height="19" fill="#fff" stroke="#efc7a8" /><text x={label + 69} y={top - 13} textAnchor="middle" fontSize="10.5" fontWeight="600" fill="#96592e">Hypothetical reef proxy</text></g>; })()}
      {visible.interceptors && <g data-ocean-layer="interceptors">{report.layouts.map((layout, i) => <g key={layout.id}>{layout.segments.map((segment, s) => { const a = screen(segment.start_xy_m), b = screen(segment.end_xy_m), top = a[1] < b[1] ? a : b, badge = s === layout.segments.length - 1, mid = i ? [top[0] - 15, top[1] - 16] : [top[0] - 30, top[1] + 4]; return <g key={segment.id}><line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke="#fff" strokeWidth="8" strokeLinecap="round" /><line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke={palette[i]} strokeWidth="4.5" strokeLinecap="round" strokeDasharray={i ? "8 4" : undefined} opacity=".85"><title>{`Layout ${i ? "B" : "A"} · ${layout.label} · ideal absorbing line · ${segment.id}`}</title></line>{badge && <><circle cx={mid[0] + 15} cy={mid[1]} r="8" fill="#fff" stroke={palette[i]} strokeWidth="1.4" /><text x={mid[0] + 15} y={mid[1] + 3.6} textAnchor="middle" fontSize="10" fontWeight="700" fill={palette[i]}>{i ? "B" : "A"}</text></>}</g>; })}</g>)}</g>}
      {visible.baseline && paths(report.baseline, "#8296a3", "baseline", true)}
      {visible.layoutA && paths(report.layouts[0], palette[0], "layoutA", false)}
      {visible.layoutB && paths(report.layouts[1], palette[1], "layoutB", true)}
      {!empty && report.releases.filter(r => releaseId === "all" || r.id === releaseId).map(release => { const [x, y] = screen([release.x_m, release.y_m]); return <g key={release.id}><circle cx={x} cy={y} r="7" fill="#225b7c" opacity=".12" /><circle cx={x} cy={y} r="4" fill="white" stroke="#225b7c" strokeWidth="1.8"><title>{`${releaseName(release.id)} hypothetical release · ${date(release.start_time_utc)}`}</title></circle><text x={x + 10} y={y + 3.8} fontSize="10.5" fontWeight="600" fill="#315d77">{releaseName(release.id)}</text></g>; })}
      <text x="360" y="454" textAnchor="middle" fontSize="11" fill="#526f83">Plot grid: {fmt(span / 4000)} km · equal axes</text><text x="360" y="475" textAnchor="middle" fontSize="11" fill="#526f83">East → · North ↑</text>
    </svg>
    <figcaption className={styles.caption}>Every path follows the same changing-current field. Overlapping paths are expected before a layout makes contact; checkbox layers and the release filter separate them. ■ idealized capture · ▲ protected-zone entry · ○ completed without entry · × unresolved. Hover a dot or endpoint for its release, time and outcome.</figcaption>
  </figure>;
}

export function OceanResults({ report, api, readOnly = false }: { report: OceanPreventionReport; api: string; readOnly?: boolean }) {
  const { token } = useOperator();
  const [visible, setVisible] = useState<OceanVisibility>(DEFAULT_OCEAN_VISIBILITY), [frame, setFrame] = useState(0), [releaseId, setReleaseId] = useState("all");
  const [review, setReview] = useState<OceanPreventionAnswer | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  const frames = report.vector_frames ?? [], recommendation = report.recommendation, best = report.layouts.find(item => item.id === recommendation.best_layout_id);
  const heading = recommendation.status === "BEST_LAYOUT" && best ? `${best.label} has fewer predicted reef entries.` : recommendation.status === "TIE" ? "The two layouts tie in this scenario." : "These currents do not support a best layout yet.";
  async function ask() {
    if (readOnly || !token || controller.current) return;
    const pending = new AbortController(); controller.current = pending; setBusy(true); setError(""); setReview(null);
    const timer = window.setTimeout(() => pending.abort(), 90_000);
    try {
      const response = await fetch(`${api}/api/v1/research/ocean-prevention/investigate`, { method: "POST", cache: "no-store", signal: pending.signal, headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ question: "Explain which interception layout the frozen changing-current comparison supports, including ties or unresolved outcomes, and what must be measured before claiming real reef protection. Keep simulation separate from measurement.", scenario_id: report.scenario.id, snapshot_sha256: report.snapshot_sha256, method_sha256: report.method_sha256, scenario_sha256: report.scenario_sha256, report_sha256: report.report_sha256 }) });
      const result = await readVectorResponse(response, value => validateOceanPreventionAnswer(value, report), 2_000_000);
      if (!pending.signal.aborted) setReview(result);
    } catch (cause) { if (controller.current === pending) setError(pending.signal.aborted ? "Chalk exceeded this comparison’s review time limit. The numerical result remains available." : cause instanceof Error ? cause.message : "Chalk could not review this comparison."); }
    finally { window.clearTimeout(timer); if (controller.current === pending) { controller.current = null; setBusy(false); } }
  }
  return <div className={styles.stack}>
    <div className={styles.summary}><h3>{heading}</h3><p>{recommendation.reason}</p></div>
    <p className={styles.scope}>Simulation with a captured PacIOOS current forecast: six hypothetical releases, the same changing flow, and 2,000 m of idealized line per layout. The orange reef proxy is illustrative. Measured interception and ecological protection are not yet available.</p>
    {report.scenario.id === "downstream-corridor-v2" && <p className={styles.note}>{report.scenario.design_disclosure}</p>}
    {report.mode === "archived_forecast_snapshot" && <p className={styles.note} role="status">This forecast window has passed. The saved comparison is an archived model scenario, not current ocean conditions.</p>}
    <div className={styles.metrics}>{report.layouts.map((layout, i) => <section key={layout.id} className={styles.metric} aria-label={`Layout ${i ? "B" : "A"} model outcome`}><h4>Layout {i ? "B" : "A"} · {layout.label}</h4><strong>{bounds(layout.summary.protected_entry_count_bounds)} of {layout.summary.release_count}</strong><p><HelpLabel label="Predicted reef entries" explanation="The number of hypothetical releases that reach the protected polygon. A range keeps every unresolved release in the upper bound. Lower is better within this model scenario." /></p><p><span>{layout.summary.intercepted_count}</span> idealized captures · <span>{layout.summary.unresolved_count}</span> unresolved</p></section>)}</div>
    <p className={styles.note}>Without interception: {bounds(report.baseline.summary.protected_entry_count_bounds)} of {report.baseline.summary.release_count} predicted entries. These counts are simulated releases, not measured kilograms, probabilities or field effectiveness.</p>
    <label className={styles.label}>Inspect a release<select aria-label="Ocean comparison release" value={releaseId} onChange={event => setReleaseId(event.target.value)}><option value="all">All six releases</option>{report.releases.map(release => <option key={release.id} value={release.id}>{releaseName(release.id)} · hypothetical release</option>)}</select><span className={styles.note}>This changes only the drawing. The comparison always counts all six releases.</span></label>
    <OceanPreventionFigure report={report} visible={visible} frame={frame} releaseId={releaseId} onToggle={(id, checked) => setVisible(previous => ({ ...previous, [id]: checked }))} />
    {frames.length > 0 && visible.currents && <label className={styles.label}>Current arrows at {date(frames[frame].time_utc)}<input aria-label="Ocean comparison current valid time" type="range" min={0} max={frames.length - 1} step={1} value={frame} onChange={event => setFrame(Number(event.target.value))} /><span className={styles.note}>Only the arrow display time changes. Full paths, outcomes and the arrow speed scale stay fixed.</span></label>}
    {readOnly ? <section className={styles.chalk} aria-label="Chalk availability in public showcase"><h3>Chalk is available in the full local experiment software</h3><p className={styles.note}>This public showcase does not call a model or display a live Chalk response. The numerical comparison above is the verified saved simulation. On the team’s local app, an authorized operator can ask Chalk to explain that exact evidence without changing its counts.</p><button type="button" className="primary-button" disabled>Chalk unavailable in public showcase</button></section> : <section className={styles.chalk} aria-label="Chalk ocean prevention review"><h3>Explain this comparison with Chalk</h3><p className={styles.note}>Chalk reads this exact current snapshot, method and scenario. It cannot change the numerical result or manufacture a winning layout.</p><button type="button" className="primary-button" disabled={!token || busy} onClick={() => void ask()}><Icon name="agent" />{busy ? "Reviewing ocean comparison…" : "Ask Chalk about these layouts"}</button>{!token && <p className={styles.note}><Link href="/login">Sign in to use Chalk</Link></p>}{error && <p className="notice error" role="alert">{error} No automatic retry will occur.</p>}<p className="sr-only" role="status" aria-atomic="true">{review ? `${review.action}. ${review.explanation}` : busy ? "Chalk is reviewing the frozen ocean comparison." : ""}</p>{review && <div className={styles.answer}><span className="pill">{review.action} · {review.live_model_response ? "Live Chalk response" : "No live model response"}</span><p>{review.explanation}</p><details className="details-panel"><summary>Comparison evidence citations</summary><pre className="code-block">{JSON.stringify(review.evidence_ids, null, 2)}</pre></details></div>}</section>}
    {report.numerical_sensitivity && <OceanNumerics report={report.numerical_sensitivity} layouts={report.layouts} />}
    <details className={`details-panel ${styles.method}`}><summary>Scientific method, current source and full report</summary><p>{report.forcing.attribution}</p><p>Captured {date(report.forcing.captured_at_utc)} · valid {date(report.forcing.valid_start_utc)} to {date(report.forcing.valid_end_utc)} · depth {fmt(report.forcing.depth_m)} m. Single verified issue time: {report.forcing.model_issue_time_utc ?? "not provided by the best-forecast aggregation"}.</p><p>The solver samples current direction and speed at each moving position and time, using RK4 and spatial/temporal interpolation. Capture and reef contact are localized along supported five-minute output chords. Lines absorb on first contact without changing the water; actual booms, waves, object response and reef-scale currents require measurement.</p><p>The two equal-length geometries are illustrative hypotheses. Ranking uses strictly nonoverlapping protected-entry bounds; equal resolved counts are a tie and overlapping unresolved ranges are indeterminate. Counts retain all six releases, including missing forcing.</p><a className="card-link" href={report.forcing.product_url} target="_blank" rel="noreferrer">PacIOOS source documentation <Icon name="arrow" /></a><ul className="reason-list">{report.limitations.map(item => <li key={item}>{item}</li>)}</ul><p className={styles.identity}>Comparison identity: {report.report_sha256}</p><details className="details-panel"><summary>Complete read-only ocean report</summary><pre className="code-block">{JSON.stringify(report, null, 2)}</pre></details></details>
  </div>;
}

export function OceanPrevention({ api, readOnly = false }: { api: string; readOnly?: boolean }) {
  const [scenarioId, setScenarioId] = useState("downstream-corridor-v2");
  const [report, setReport] = useState<OceanPreventionReport | null>(null), [loading, setLoading] = useState(false), [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  function selectScenario(id: string) { controller.current?.abort(); controller.current = null; setScenarioId(id); setReport(null); setError(""); setLoading(false); }
  async function load() {
    if (controller.current) return;
    const pending = new AbortController(); controller.current = pending; setLoading(true); setError("");
    const timer = window.setTimeout(() => pending.abort(), 30_000);
    try {
      const response = await fetch(`${api}/api/v1/research/ocean-prevention?scenario_id=${encodeURIComponent(scenarioId)}`, { cache: "no-store", signal: pending.signal });
      const result = await readVectorResponse(response, validateOceanPrevention, 2_000_000);
      if (result.scenario.id !== scenarioId) throw new Error("The API returned a different ocean scenario. No comparison was accepted.");
      if (!pending.signal.aborted && controller.current === pending) setReport(result);
    } catch (cause) { if (controller.current === pending) setError(pending.signal.aborted ? "The saved ocean comparison timed out." : cause instanceof Error ? cause.message : "The saved comparison is unavailable."); }
    finally { window.clearTimeout(timer); if (controller.current === pending) { controller.current = null; setLoading(false); } }
  }
  return <section className={`card ${styles.card}`} aria-label="Ocean-mode prevention comparison"><div className={`card-header ${styles.header}`}><div><h2 className="card-title"><Icon name="wave" />Which layout keeps more pollution away?</h2><p className="card-subtitle">One changing-current comparison. Two layouts. A shared reef proxy.</p></div><button type="button" className="primary-button" disabled={loading} onClick={() => void load()}><Icon name="play" />{loading ? "Loading ocean comparison…" : "Compare ocean layouts"}</button></div><div className={`card-body ${styles.stack}`}><label className={styles.label}>Ocean scenario<select aria-label="Ocean scenario" value={scenarioId} onChange={event => selectScenario(event.target.value)}><option value="downstream-corridor-v2">Downstream corridor · illustrative what-if</option><option value="initial-proxy-v1">Original proxy · no-entry model control</option></select></label>{!report && <p className={styles.note}>Start with the captured dynamic-current scenario. The combined plot lets you choose which layout paths and geometry to see; the full method stays behind one disclosure.</p>}{loading && <p role="status">Verifying the current snapshot and comparing both layouts on the same six dynamic paths…</p>}{error && <p className="notice error" role="alert">{error} No automatic retry will occur.</p>}{report && <OceanResults key={report.report_sha256} api={api} report={report} readOnly={readOnly} />}</div></section>;
}
