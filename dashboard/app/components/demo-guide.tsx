import { Icon } from "./icons";
import styles from "./demo-guide.module.css";

type Props = { disabled?: boolean; onTrace: () => void; onPrevention: () => void; onChalk: () => void };

export function DemoGuide({ disabled = false, onTrace, onPrevention, onChalk }: Props) {
  const steps = [
    { title: "Trace a source", detail: "Open a source-tracing example. A saved path can support a candidate; an endpoint alone may stay unknown.", action: "Open source trace", onClick: onTrace, icon: "cases" as const },
    { title: "Compare two layouts", detail: "Open a separate synthetic prevention example. Compare how many simulated tokens enter the protected area.", action: "Compare layouts", onClick: onPrevention, icon: "wave" as const },
    { title: "Explain the evidence", detail: "Ask Chalk about the selected source report. It explains what the evidence supports and what is still uncertain.", action: "Ask Chalk", onClick: onChalk, icon: "agent" as const },
  ];
  return <section className={styles.guide} aria-label="Follow the evidence">
    {steps.map((step, i) => <article className={`card ${styles.step}`} key={step.title}>
      {/* The step number is visual ordering only; the headings already give the sequence. */}
      <span className={styles.index} aria-hidden="true">0{i + 1}</span><Icon name={step.icon} width={25} height={25}/>
      <h2>{step.title}</h2><p id={`demo-guide-step-${i + 1}`}>{step.detail}</p>
      <button type="button" className="secondary-button" disabled={disabled} aria-describedby={`demo-guide-step-${i + 1}`} onClick={step.onClick}>{step.action}<Icon name="arrow"/></button>
    </article>)}
  </section>;
}
