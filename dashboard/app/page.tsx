"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { BrandMark } from "./components/brand-mark";
import { BRAND_NAME } from "./components/brand";
import { Icon } from "./components/icons";
import styles from "./landing.module.css";

const CHAPTERS = [
  { label: "Observe", heading: "Every path is a piece of evidence.", detail: "Begin with a saved observation or a token recorded in your tank.", target: "investigations", icon: "camera" as const },
  { label: "Trace", heading: "Follow the evidence, including its limits.", detail: "Compare possible entry points. Keep an unknown source unknown.", target: "investigations", icon: "wave" as const },
  { label: "Prevent", heading: "Test what protects the area.", detail: "Compare two interception layouts, then check their predictions against recorded trials.", target: "prevention", icon: "check" as const },
];

function ResearchGlobe({ chapter }: { chapter: number }) {
  return <figure className={styles.globeFrame}>
    <svg viewBox="0 0 540 540" role="img" aria-labelledby="globe-title globe-desc" className={styles.globe}>
      <title id="globe-title">An illustrative journey from observation to protection</title>
      <desc id="globe-desc">An ocean sphere with three candidate entry areas, a possible route and a protected area. This is a concept illustration, not experimental or geographic evidence.</desc>
      <defs><radialGradient id="ocean-sphere" cx="32%" cy="26%"><stop offset="0" stopColor="#f1fbff" stopOpacity=".95"/><stop offset=".65" stopColor="#c4e5f5" stopOpacity=".84"/><stop offset="1" stopColor="#87b7d1" stopOpacity=".85"/></radialGradient><clipPath id="sphere-clip"><circle cx="270" cy="270" r="178"/></clipPath></defs>
      <circle cx="270" cy="270" r="238" fill="none" stroke="#477e9c" strokeOpacity=".32" strokeDasharray="2 7"/>
      <circle cx="270" cy="270" r="208" fill="none" stroke="#477e9c" strokeOpacity=".26"/>
      <path d="M88 170A208 208 0 0 1 428 133" fill="none" stroke="#267da8" strokeWidth="2"/>
      <circle cx="270" cy="270" r="178" fill="url(#ocean-sphere)" stroke="#6295b1" strokeWidth="1.2"/>
      <g clipPath="url(#sphere-clip)" fill="none" stroke="#6c9eb9" strokeOpacity=".36">
        {[-100,-50,0,50,100].map(y=><ellipse key={y} cx="270" cy={270+y} rx={Math.sqrt(178*178-y*y)} ry="26"/>)}
        {[45,95,142].map(rx=><ellipse key={rx} cx="270" cy="270" rx={rx} ry="178"/>)}
        <path d="M92 270H448M270 92V448"/>
      </g>
      <g fill="#a3cbbb" fillOpacity=".72" stroke="#6eaaa7" strokeWidth="1">
        <path d="M151 191l34-24 35 6 15 26-18 24 8 26-23 21-27-13-14-37Z"/>
        <path d="M222 278l31 13 12 30-16 41-18 26-10-35-16-34Z"/>
        <path d="M308 170l48-8 31 23-5 29-24 5-15-22-25 17-27-17Z"/>
        <path d="M300 241l33-13 29 22 4 35-29 37-25-13-16-35Z"/>
        <path d="M370 339l29-7 20 18-7 18-31-2Z"/>
      </g>
      <g fill="#267da8" stroke="#eff9fe" strokeWidth="3">
        <circle cx="188" cy="235" r={chapter===0?8:5}/><circle cx="234" cy="314" r="5"/><circle cx="349" cy="228" r="5"/>
      </g>
      <path d="M188 235C230 195 267 221 285 259S331 301 357 325" stroke="#267da8" strokeWidth="2" strokeDasharray={chapter===0?"2 9":"7 5"} fill="none" opacity={chapter===0?.35:1}/>
      <g opacity={chapter===2?1:.5}><rect x="342" y="311" width="30" height="30" fill="#d9b48e" fillOpacity=".75" stroke="#946336"/><path d="M329 307l-13 28" stroke="#426b60" strokeWidth="5"/></g>
      <g fontFamily="monospace" fontSize="10" fill="#315e78"><text x="168" y="220">A</text><text x="242" y="310">B</text><text x="361" y="228">C</text></g>
      <path d="M454 331h35v35M86 209H51v-35" stroke="#477e9c" fill="none"/>
      <text x="270" y="505" textAnchor="middle" fontFamily="monospace" fontSize="10" letterSpacing="2" fill="#315e78">OBSERVE / TRACE / PREVENT</text>
    </svg>
    <figcaption>Illustrative coastal system · not measured evidence</figcaption>
  </figure>;
}

export default function Home() {
  const [chapter, setChapter] = useState(0);
  const router = useRouter();
  useEffect(() => {
    function restoreLegacyLink() {
      const [view, search = ""] = window.location.hash.slice(1).split("?");
      if (!["overview", "investigations", "prevention", "camera", "data", "settings"].includes(view)) return;
      const caseId = new URLSearchParams(search).get("case");
      router.replace(`/workspace#${view}${caseId && caseId.length <= 200 ? `?case=${encodeURIComponent(caseId)}` : ""}`);
    }
    restoreLegacyLink(); window.addEventListener("hashchange", restoreLegacyLink);
    return () => window.removeEventListener("hashchange", restoreLegacyLink);
  }, [router]);
  return <main className={styles.landing}>
    <a className="sr-only skip-link" href="#hero-main">Skip to content</a>
    <section className={styles.experience} aria-label="Tideward coastal research">
      <header className={styles.header}>
        <Link href="/" className={styles.wordmark} aria-label={`${BRAND_NAME} home`}><BrandMark/><span>{BRAND_NAME}<small>COASTAL RESEARCH</small></span></Link>
        <nav aria-label="Main navigation"><a href="#workflow">The workflow</a><Link href="/workspace#data">The evidence</Link><Link href="/login" className={styles.signIn}>Open workspace <Icon name="arrow"/></Link></nav>
      </header>
      <div className={styles.hero} id="hero-main">
        <div className={styles.heroCopy}>
          <p className={styles.kicker}>OBSERVATION → INTERVENTION → EVIDENCE</p>
          <h1><span>Follow the</span><br/>current.</h1>
          <p className={styles.intro}>Understand where pollution may enter.<br/>Test what keeps it from reaching a protected area.</p>
          <div className={styles.actions}><Link href="/login" className={styles.primary}>Start your experiment <Icon name="arrow"/></Link><Link href="/workspace#data" className={styles.secondary}>Explore NOAA evidence <Icon name="arrow"/></Link></div>
          <p className={styles.accessNote}>No setup needed to explore. Operator access is required to run experiments.</p>
        </div>
        <ResearchGlobe chapter={chapter}/>
        <nav className={styles.chapters} aria-label="Explore the Tideward workflow">{CHAPTERS.map((item,index)=><button type="button" key={item.label} aria-pressed={chapter===index} aria-label={`0${index+1} ${item.label}`} aria-controls="chapter-detail" onClick={()=>setChapter(index)}><span>0{index+1}</span><strong>{item.label}</strong></button>)}</nav>
      </div>
      <div className={styles.bottomRail}>
        <div className={styles.projectStamp}><BrandMark/><span>CONTROLLED PROTOTYPE<br/><strong>Tank experiments + NOAA research</strong></span></div>
        <div className={styles.chapterDetail} id="chapter-detail" aria-live="polite" aria-atomic="true"><span>0{chapter+1} / {CHAPTERS[chapter].label}</span><strong>{CHAPTERS[chapter].heading}</strong><p>{CHAPTERS[chapter].detail}</p></div>
        <a href="#workflow" className={styles.discover}>Discover the workflow <span>↓</span></a>
      </div>
      <span className={styles.artNote}>Higgsfield ocean illustration</span>
    </section>
    <section className={styles.workflow} id="workflow" aria-labelledby="workflow-title">
      <div className={styles.sectionHeading}><p className={styles.kicker}>THE EXPERIMENT, MADE CLEAR</p><h2 id="workflow-title">One question at a time.</h2><p>Start with an observation. Follow the evidence to your next test.</p></div>
      <div className={styles.workflowGrid}>{CHAPTERS.map((item,index)=><Link href={`/workspace#${item.target}`} key={item.label} className={styles.workflowCard}><span className={styles.cardNumber}>0{index+1}</span><Icon name={item.icon}/><h3>{item.label}</h3><p>{item.detail}</p><span className={styles.cardAction}>Open {item.label.toLowerCase()} <Icon name="arrow"/></span></Link>)}</div>
      <p className={styles.evidenceNote}><Icon name="help"/>The demo is synthetic. NOAA records describe historical buoy motion. Real tank performance still needs to be measured.</p>
    </section>
    <footer className={styles.footer}><span>{BRAND_NAME} · Observe. Trace. Prevent.</span><Link href="/workspace#data">Data & methods <Icon name="arrow"/></Link><Link href="/login">Operator sign in <Icon name="arrow"/></Link></footer>
  </main>;
}
