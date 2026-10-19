"use client";

/* eslint-disable @next/next/no-img-element */
import { useEffect, useState } from "react";
import { metricGrid } from "../components/camera-grid-state";
import { parseRegistration, registrationMapping, registrationStage, type RegistrationStatus } from "../components/tank-registration-state";
import styles from "./registration-demo.module.css";

type Demo = { steps: { step: string; status: RegistrationStatus }[]; report_sha256: string };
export default function RegistrationDemo() {
  const [demo, setDemo] = useState<Demo | null>(null), [step, setStep] = useState(0);
  const [gridOn, setGridOn] = useState(true), [geometry, setGeometry] = useState(true), [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    fetch("/registration-demo/rehearsal.json", { signal: controller.signal }).then(r => { if (!r.ok) throw new Error("Rehearsal unavailable"); return r.json(); }).then((data: Demo) => {
      if (data.steps.length !== 4) throw new Error("Unsupported dry rehearsal");
      data.steps.forEach(row => parseRegistration(row.status));
      setDemo(data);
    }).catch(cause => { if (!controller.signal.aborted) setError(String(cause)); });
    return () => controller.abort();
  }, []);
  const status = demo?.steps[step].status;
  const grid = status ? metricGrid(registrationMapping(status), "synthetic-dry", 1040, 840) : null;
  const image = step === 1 || step === 2 ? "moved" : step === 3 ? "missing" : "aligned";
  return <main className={styles.main}>
    <a href="/workspace#camera">← Return to workspace</a>
    <p className={styles.origin}>SYNTHETIC · CONSTRUCTED FRAMES · NO CAMERA CONNECTION</p>
    <h1>Keep the grid attached to the water plane.</h1>
    <p>Step through detection, a camera bump, a new proposal and reference loss. No physical centimetre accuracy or unchanged flow is claimed.</p>
    <nav className={styles.steps} aria-label="Registration rehearsal steps">{registrationStage.map((item, i) => <button key={item.title} aria-current={step === i ? "step" : undefined} onClick={() => setStep(i)}>{item.title}</button>)}</nav>
    <div className={styles.layout}><section><h2>{registrationStage[step].title}</h2><p>{registrationStage[step].description}</p>
      <div className={styles.frame}>
        <img src={`/registration-demo/${image}.png`} width={1040} height={840} alt={`Constructed tray image: ${registrationStage[step].title}`} />
        <svg viewBox="0 0 1040 840" aria-label="Projected grid and separate geometry candidates">
          <defs><clipPath id="water-region"><polygon points={grid?.clipPolygon.map(p => p.join(",")).join(" ") ?? ""} /></clipPath></defs>
          {grid && gridOn && <g data-camera-layer="centimetres" clipPath="url(#water-region)">{grid.lines.map(line => <line key={`${line.axis}${line.value}`} x1={line.start[0]} y1={line.start[1]} x2={line.end[0]} y2={line.end[1]} stroke="#2375a8" strokeWidth={2} opacity={.8} />)}</g>}
          {geometry && status?.proposal && Object.entries(status.geometry_layers).map(([name, layer]) => layer.candidates?.map((c, i) => <polygon key={`${name}${i}`} points={c.polygon_px.map(p => p.join(",")).join(" ")} fill="none" stroke={name === "tray_boundary" ? "#a855f7" : "#168879"} strokeWidth={5} strokeDasharray="10 5" />))}
        </svg>
      </div>
      <div className={styles.controls}><label><input type="checkbox" checked={gridOn} onChange={e => setGridOn(e.target.checked)} />Show projected 5 cm grid</label><label><input type="checkbox" checked={geometry} onChange={e => setGeometry(e.target.checked)} />Show geometry candidates</label></div>
    </section><aside aria-live="polite"><h2>{status?.state.replaceAll("_", " ") ?? "Reading rehearsal…"}</h2><p>{status?.reason}</p>
      <dl><dt>Independent check error</dt><dd>{status?.proposal ? `${status.proposal.calibration.max_error_cm.toFixed(3)} cm / frozen 0.500 cm maximum` : "Withheld · no current mapping"}</dd><dt>Approval</dt><dd>{step === 0 ? "Illustrative dry approval only" : step === 2 ? "Candidate only · operator approval required" : "Stale · scientific recording blocked"}</dd><dt>Flow and intervention geometry</dt><dd>Separate drift validation and existing admission required. Colour candidates do not rewrite trial geometry.</dd></dl>
      <p>Blue = grid · purple = black-tape tray candidate · green = filter-border candidate. Grid spacing is a drawing choice, not sensor precision.</p>
      <a href="/registration-demo/printable-markers.svg" download>Printable example reference tiles</a><br/><a href="/registration-demo/reference-config.synthetic.json" download>Synthetic example configuration</a>
      {error && <p role="alert">{error}</p>}
    </aside></div>
    <div className={styles.controls}><button disabled={step === 0} onClick={() => setStep(s => s - 1)}>Previous step</button><output>Step {step + 1} of 4</output><button disabled={step === 3} onClick={() => setStep(s => s + 1)}>Next step</button></div>
    <p>For manual correction, edit measured reference coordinates in commissioning and create a new proposal, or use the existing manual mapping form. Never increase the frozen tolerance to pass a frame.</p>
    <small>Deterministic rehearsal report: {demo?.report_sha256 ?? "loading"}</small>
  </main>;
}
