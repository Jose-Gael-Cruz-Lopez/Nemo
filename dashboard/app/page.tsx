"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Icon } from "./components/icons";
import { CoastalTerrain } from "./components/coastal-terrain";
import styles from "./welcome.module.css";

const PHASES = [
  { title: "See the movement.", detail: "Start with a saved observation. Keep what was measured separate from what the model predicts.", label: "Observe", icon: "camera" as const },
  { title: "Follow the evidence.", detail: "Compare candidate sources, test the assumptions, and ask Chalk what the evidence supports.", label: "Trace", icon: "wave" as const },
  { title: "Protect what matters.", detail: "Compare interception layouts, record trials, and see whether the intervention delivers.", label: "Prevent", icon: "check" as const },
];

export default function Home() {
  const [phase, setPhase] = useState(0);
  const router = useRouter();
  useEffect(() => {
    // Existing shared links keep their case and view when the landing page moves in.
    function restoreLegacyLink() {
      const [view, search = ""] = window.location.hash.slice(1).split("?");
      if (!["overview", "investigations", "prevention", "camera", "data", "settings"].includes(view)) return;
      const caseId = new URLSearchParams(search).get("case");
      router.replace(`/workspace#${view}${caseId && caseId.length <= 200 ? `?case=${encodeURIComponent(caseId)}` : ""}`);
    }
    restoreLegacyLink();
    window.addEventListener("hashchange", restoreLegacyLink);
    return () => window.removeEventListener("hashchange", restoreLegacyLink);
  }, [router]);
  return <main className={styles.welcome}>
    <a className="sr-only skip-link" href="#hero-main">Skip to content</a>
    <div className={styles.landingFrame}>
      <header className={styles.header}>
        <Link href="/" className={styles.wordmark} aria-label="ReefTrace home"><span className={styles.mark}><Icon name="wave" /></span>ReefTrace<span className={styles.brandLabel}>COASTAL INTELLIGENCE</span></Link>
        <nav aria-label="Main navigation" className={styles.navigation}><a href="#how-it-works">How it works</a><Link href="/workspace#data">Explore the evidence</Link><Link className={styles.navLogin} href="/login">Open workspace <Icon name="arrow" /></Link></nav>
      </header>
      <section className={styles.hero} id="hero-main">
        <div className={styles.eyebrow}><span />FROM OBSERVATION TO PREVENTION</div>
        <h1>Follow the current.<br /><span>Change what reaches the reef.</span></h1>
        <p className={styles.heroDescription}>Turn floating pollution into actionable evidence.<br className={styles.desktopBreak} /> Trace possible sources. Test smarter places to intercept it.</p>
        <div className={styles.heroActions}><Link href="/login" className={styles.primary}>Enter ReefTrace <Icon name="arrow" /></Link><Link href="/workspace" className={styles.textLink}><span className={styles.playIcon}><Icon name="play" /></span>Explore saved observations</Link></div>
        <div className={styles.terrainStage}>
          <CoastalTerrain phase={phase} className={styles.terrain} />
          <div className={styles.mapCaption}><span className={styles.mapCross}>+</span>ILLUSTRATIVE COASTAL MODEL <span>01 / REEFTRACE</span></div>
          <div className={styles.floatingInsight} aria-live="polite"><span className={styles.insightIcon}><Icon name={PHASES[phase].icon} /></span><div><small>THE REEFTRACE APPROACH</small><strong>{PHASES[phase].title}</strong><p>{PHASES[phase].detail}</p></div></div>
          <div className={styles.phaseSwitch} aria-label="Explore the ReefTrace workflow">{PHASES.map((item, i) => <button key={item.label} type="button" aria-pressed={phase === i} onClick={() => setPhase(i)}><span>0{i + 1}</span>{item.label}</button>)}</div>
        </div>
      </section>
      <div className={styles.heroFoot}><span><span className={styles.smallDot} />BUILT FOR BETTER COASTAL DECISIONS</span><a href="#how-it-works">Discover the workflow <span>↓</span></a><span>OBSERVE. TRACE. PREVENT.</span></div>
    </div>
    <section className={styles.workflowSection} id="how-it-works" aria-labelledby="workflow-title">
      <div className={styles.sectionHeading}><div><p className={styles.eyebrow}>A CLEARER WAY FORWARD</p><h2 id="workflow-title">One observation.<br />A more informed next step.</h2></div><p>ReefTrace connects movement, models, and recorded outcomes so your next intervention starts with evidence.</p></div>
      <div className={styles.workflowGrid}>{PHASES.map((item, i) => <Link href={`/workspace#${i === 0 ? "investigations" : i === 1 ? "data" : "prevention"}`} key={item.label} className={styles.workflowCard}><span className={styles.stepNumber}>0{i + 1}</span><Icon name={item.icon} /><h3>{item.label}</h3><p>{item.detail}</p><span className={styles.cardAction}>Explore {item.label.toLowerCase()} <Icon name="arrow" /></span></Link>)}</div>
      <div className={styles.evidenceNote}><Icon name="help" /><p>Know what the evidence can say. Source rankings are conditional, synthetic trials are clearly labeled, and uncertainty stays visible.</p><Link href="/workspace#prevention">See the comparison <Icon name="arrow" /></Link></div>
    </section>
    <footer className={styles.footer}><Link href="/" className={styles.wordmark}><span className={styles.mark}><Icon name="wave" /></span>ReefTrace</Link><span>A clearer current. A better next step.</span><Link href="/login">Operator sign in <Icon name="arrow" /></Link></footer>
  </main>;
}
