"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "./icons";
import { readMethodReplay, type MethodExample, type MethodReplay } from "./method-validation-state";
import styles from "./method-validation.module.css";

const readable = (value: string) => value.toLowerCase().replaceAll("_", " ");
const percent = (value: number) => `${(100 * value).toFixed(1)}%`;
const interval = (lower: number, upper: number) => `${percent(lower)}–${percent(upper)}`;

function ExampleReport({ example }: { example: MethodExample }) {
  const r = example.report, group = r.by_origin.SYNTHETIC_DEMO;
  return <div className={styles.stack}>
    <div className={styles.badges}><span className="pill amber">Synthetic alternative · not your current case</span><span className="pill">Actual validator rerun</span><span className="pill">Physical validation: no</span></div>
    <h3>{example.label}</h3><p className={styles.scope}>{readable(r.selected_layout_usefulness.SYNTHETIC_DEMO.status)}. This is a descriptive result on hand-authored synthetic outcomes, without a claim of independent physical validation.</p>
    <p className="settings-note">This example alone has {group.plan.recorded_total}/{group.plan.expected_total} planned one-token releases. The alternative example reuses trial identities: do not add their counts. No physical trials were performed.</p>
    <div className="table-scroll"><table className={`metrics-table ${styles.table}`}><caption className="sr-only">Synthetic trial accounting and nominal model entry bounds, by source and layout</caption><thead><tr><th>Source / layout</th><th>Predicted entry bounds · nominal simulation</th><th>Recorded entry bounds · planned</th><th>Released / planned</th><th>Missing</th><th>Entered</th><th>Intercepted first</th><th>Unresolved</th></tr></thead><tbody>{group.by_source.flatMap(source => (["baseline", "intervention"] as const).map(layout => {
      const stats = source[layout], nominal = r.diagnostics.find(row => row.data_origin === "SYNTHETIC_DEMO" && row.scenario_id === "nominal" && row.source_id === source.source_id)!.layouts[layout].predicted;
      return <tr key={`${source.source_id}-${layout}`}><th scope="row">{source.source_id} · {layout}</th><td>{interval(nominal.zone_entry_lower_fraction, nominal.zone_entry_upper_fraction)}{nominal.unsupported_count > 0 && <small>Unsupported paths remain unknown.</small>}</td><td>{interval(stats.entry_rate_bounds.lower, stats.entry_rate_bounds.upper)}</td><td>{stats.released}/{stats.planned}</td><td>{stats.missing_planned}</td><td>{stats.zone_entries}</td><td>{stats.captured_before_entry}</td><td>{stats.unresolved}</td></tr>;
    }))}</tbody></table></div>
    <p className="settings-note">Missing and unresolved planned slots remain unknown. Nominal predictions are model-conditional fractions, not calibrated probabilities. Other scenario rows compare the same releases; they are not additional experiments.</p>
    <div className={styles.scope}><h3>What to measure next</h3><p>{readable(r.next_measurement.kind)}{r.next_measurement.source_id ? ` · source ${r.next_measurement.source_id}` : ""}.</p><p>{r.next_measurement.explanation}</p><ul className="reason-list">{r.next_measurement.reason_codes.map(code => <li key={code}>{readable(code)}</li>)}</ul><p>No precise new sensor region is identified by this saved report.</p></div>
    <details className="details-panel"><summary>Frozen identity, provenance and limitations</summary><p className="settings-note">Computed report <code>{r.id}</code> · synthetic comparison <code>{r.comparison_id}</code>. The original private hash is not independently verified. The numerical method was rerun, and the {example.id === "unresolved" ? "shared report exactly matched its pinned fixture" : "positive control was recomputed"}.</p><p className="settings-note">Input: {example.provenance.input.path}</p><code className="evidence-id">{example.provenance.input.sha256}</code>{example.provenance.expected_report && <><p className="settings-note">Expected shared report: {example.provenance.expected_report.path}</p><code className="evidence-id">{example.provenance.expected_report.sha256}</code></>}<ul className="reason-list">{r.limitations.map((limit, i) => <li key={i}>{limit}</li>)}</ul></details>
    <details className="details-panel"><summary>Full recomputed example JSON</summary><pre className="code-block">{JSON.stringify(example, null, 2)}</pre></details>
  </div>;
}

function MethodValidationSession({ api }: { api: string }) {
  const [report, setReport] = useState<MethodReplay | null>(null);
  const [selected, setSelected] = useState<MethodExample["id"]>("unresolved");
  const [loading, setLoading] = useState(false), [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function run() {
    if (controller.current) return;
    const pending = new AbortController(); controller.current = pending; setLoading(true); setError(""); setReport(null);
    try {
      const response = await fetch(`${api.replace(/\/$/, "")}/api/v1/research/prevention-method-example`, { signal: pending.signal, cache: "no-store" });
      const result = await readMethodReplay(response);
      if (controller.current === pending && !pending.signal.aborted) { setReport(result); setSelected("unresolved"); }
    } catch (cause) { if (controller.current === pending && !pending.signal.aborted) setError(cause instanceof Error ? cause.message : "The pinned method example could not be read."); }
    finally { if (controller.current === pending && !pending.signal.aborted) { controller.current = null; setLoading(false); } }
  }
  const example = report?.examples.find(item => item.id === selected);
  return <section className="card" aria-label="Synthetic Trace 2 method validation example"><div className={`card-header ${styles.header}`}><div><h2 className="card-title">Trace 2 · numerical validation example</h2><p className="card-subtitle">Replay the team’s pinned examples through the actual validator.</p></div><button className="secondary-button" disabled={loading} onClick={() => void run()}><Icon name="play" />{loading ? "Replaying examples…" : "Run Trace 2 validation example"}</button></div><div className={`card-body ${styles.stack}`}>
    <p className={styles.scope}><strong>This is a synthetic method demonstration, separate from the selected case.</strong> Both example files are content-pinned, the validator is actually rerun, and the unresolved example is checked against the shared report. No imported JSON is trusted merely because its hash is valid.</p>
    {loading && <p className="settings-note" role="status">Recomputing both bounded synthetic examples… No provider, camera, actuator or messaging action is requested.</p>}
    {error && <div className="notice error" role="alert"><span>{error} No automatic retry will occur.</span><button className="card-link" disabled={loading} onClick={() => void run()}>Retry example <Icon name="arrow" /></button></div>}
    {report && <><div className={styles.actions} aria-label="Choose synthetic alternative">{report.examples.map(item => <button className="secondary-button" key={item.id} aria-pressed={selected === item.id} onClick={() => setSelected(item.id)}>{item.label}</button>)}</div>{example && <ExampleReport key={example.id} example={example} />}<details className="details-panel"><summary>What is still required for your current case?</summary><ul className="reason-list">{report.current_case_requirements.map((requirement, i) => <li key={i}>{requirement}</li>)}</ul><ul className="reason-list">{report.limitations.map((limit, i) => <li key={i}>{limit}</li>)}</ul></details></>}
    {!report && !loading && !error && <p className="settings-note">Explicit read-only replay of two synthetic alternatives. It does not create a new current-case validation receipt, modify trials or send any model request.</p>}
  </div></section>;
}

export function MethodValidation({ api }: { api: string }) {
  return <MethodValidationSession key={api} api={api} />;
}
