"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { BrandMark } from "./components/brand-mark";
import { BRAND_NAME } from "./components/brand";
import { JOURNEY_CHAPTERS, createJourneyNarrator, legacyWorkspaceDestination, journeyProgress, motionAllowed, type JourneyNarrator, type NarrationState } from "./landing-journey-state";
import styles from "./landing.module.css";

function JourneyGlobe() {
  return <svg viewBox="0 0 110 110" className={styles.globe} aria-hidden="true" focusable="false">
    <circle cx="55" cy="55" r="49" fill="none" stroke="currentColor" strokeOpacity=".38"/>
    <circle cx="55" cy="55" r="42" fill="none" stroke="currentColor" strokeDasharray="1 3"/>
    <circle cx="55" cy="55" r="34" fill="currentColor" fillOpacity=".04" stroke="currentColor" strokeOpacity=".75"/>
    <g stroke="currentColor" strokeOpacity=".34" fill="none"><ellipse cx="55" cy="55" rx="15" ry="34"/><ellipse cx="55" cy="55" rx="34" ry="13"/><path d="M21 55h68M55 21v68"/></g>
    <g fill="currentColor" fillOpacity=".86"><path d="m32 38 12-8 10 6-3 9-8 2-5 11-8-7Z"/><path d="m45 57 12 5 3 10-8 12-5-12Z"/><path d="m66 32 11 6 8 12-9 4-6-7-9-1Z"/><path d="m65 54 12 4 3 11-11 9-6-10Z"/></g>
    <path d="M55 1v10M55 99v10M1 55h10M99 55h10" stroke="currentColor" strokeOpacity=".6"/>
  </svg>;
}

export default function Home() {
  const router = useRouter();
  const viewport = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const progress = useRef<HTMLDivElement>(null);
  const progressText = useRef<HTMLSpanElement>(null);
  const narrator = useRef<JourneyNarrator | null>(null);
  const startTarget = useRef<HTMLAnchorElement>(null);
  const startFocusRequested = useRef(false);
  const activeChapter = useRef(0);
  const [chapter, setChapter] = useState(0);
  const [entered, setEntered] = useState(false);
  const [voiceChoice, setVoiceChoice] = useState(false);
  const [narration, setNarration] = useState<NarrationState>("off");
  // Keep a still poster until the actual motion preference is known.
  const [reducedMotion, setReducedMotion] = useState(true);
  const [paused, setPaused] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [videoFailed, setVideoFailed] = useState(false);
  const [videoReady, setVideoReady] = useState(false);
  const allowMotion = motionAllowed({ reducedMotion, paused, hidden });

  useEffect(() => {
    function restoreLegacyLink() {
      const destination = legacyWorkspaceDestination(window.location.hash);
      if (destination) router.replace(destination);
    }
    restoreLegacyLink(); window.addEventListener("hashchange", restoreLegacyLink);
    return () => window.removeEventListener("hashchange", restoreLegacyLink);
  }, [router]);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(query.matches);
    update(); query.addEventListener("change", update);
    const visibility = () => { setHidden(document.hidden); if (document.hidden) narrator.current?.stop(); };
    visibility(); document.addEventListener("visibilitychange", visibility);
    narrator.current = createJourneyNarrator(
      "speechSynthesis" in window && "SpeechSynthesisUtterance" in window ? window.speechSynthesis : null,
      text => new SpeechSynthesisUtterance(text), setNarration,
    );
    return () => { query.removeEventListener("change", update); document.removeEventListener("visibilitychange", visibility); narrator.current?.dispose(); narrator.current = null; };
  }, []);

  useEffect(() => {
    const element = viewport.current;
    if (!element) return;
    const sections = Array.from(element.querySelectorAll<HTMLElement>("[data-journey-chapter]"));
    const visibility = new Map<Element, number>();
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => visibility.set(entry.target, entry.intersectionRect.height));
      const mostVisible = sections.reduce((best, section) => (visibility.get(section) ?? 0) > (visibility.get(best) ?? 0) ? section : best, sections[0]);
      if (!mostVisible || (visibility.get(mostVisible) ?? 0) < Math.min(50, element.clientHeight * .2)) return;
      const next = Number(mostVisible.dataset.journeyChapter);
      if (next !== activeChapter.current) {
        activeChapter.current = next; setChapter(next); narrator.current?.stop();
        // Scrolling is always allowed; no gate can trap the visitor.
        if (next > 0) setEntered(true);
      }
    }, { root: element, threshold: [0, .01, .05, .1, .2, .4, .6, .8, 1] });
    sections.forEach(section => observer.observe(section));
    let frame = 0;
    const updateProgress = () => {
      frame = 0;
      const value = journeyProgress(element.scrollTop, element.scrollHeight, element.clientHeight);
      progress.current?.style.setProperty("--progress", String(value / 100));
      progress.current?.setAttribute("aria-valuenow", String(value));
      if (progressText.current) progressText.current.textContent = `${value}%`;
    };
    const onScroll = () => { if (!frame) frame = window.requestAnimationFrame(updateProgress); };
    const resize = new ResizeObserver(onScroll);
    resize.observe(element); sections.forEach(section => resize.observe(section));
    element.addEventListener("scroll", onScroll, { passive: true }); updateProgress();
    return () => { observer.disconnect(); resize.disconnect(); element.removeEventListener("scroll", onScroll); if (frame) window.cancelAnimationFrame(frame); };
  }, []);

  useEffect(() => {
    const element = video.current;
    if (!element) return;
    if (allowMotion && !videoFailed) void element.play().catch(() => setVideoReady(false));
    else element.pause();
    return () => element.pause();
  }, [allowMotion, videoFailed]);

  useEffect(() => {
    if (entered && startFocusRequested.current && startTarget.current) {
      startFocusRequested.current = false;
      startTarget.current.focus({ preventScroll: true });
    }
  }, [entered]);

  function startJourney() {
    // Preserve keyboard position when the entry gate is replaced after this click.
    // Merely scrolling past the gate never requests or moves focus.
    startFocusRequested.current = true; setEntered(true);
    if (voiceChoice) narrator.current?.play(JOURNEY_CHAPTERS[0].narration);
  }
  function toggleAudio() {
    if (narration === "speaking" || narration === "loading") narrator.current?.stop();
    else narrator.current?.play(JOURNEY_CHAPTERS[chapter].narration);
  }
  const current = JOURNEY_CHAPTERS[chapter];
  const next = JOURNEY_CHAPTERS[Math.min(chapter + 1, JOURNEY_CHAPTERS.length - 1)];
  const audioLabel = narration === "speaking" || narration === "loading" ? "Mute narration" : "Listen to chapter";

  return <main className={styles.landing} data-motion={allowMotion ? "running" : "paused"} data-entered={entered}>
    <a className={styles.skip} href="/workspace">Skip journey · open workspace</a>
    <div className={styles.oceanBackdrop} aria-hidden="true">
      <div className={styles.poster}/>
      <video ref={video} className={styles.oceanVideo} data-ready={videoReady && !videoFailed && !reducedMotion} src="/tideward-ocean-journey.mp4" poster="/tideward-ocean-hero.png" muted loop playsInline preload="none" onPlaying={() => setVideoReady(true)} onError={() => { setVideoFailed(true); setVideoReady(false); }}/>
      <div className={styles.waterLight}/>
      <svg className={styles.currentLines} viewBox="0 0 1440 900" preserveAspectRatio="none"><path d="M-80 705C240 420 340 800 750 530S1170 360 1540 180M-100 747C220 462 360 840 770 570S1200 390 1550 230M-90 789C240 504 380 882 800 612S1230 440 1570 280"/></svg>
      <div className={styles.particles}>{Array.from({ length: 9 }, (_, index) => <i key={index}/>)}</div>
      <div className={styles.shade}/>
    </div>
    <header className={styles.header}>
      <Link href="/" className={styles.wordmark} aria-label={`${BRAND_NAME} home`}><BrandMark/><span>{BRAND_NAME}<small>COASTAL INTELLIGENCE</small></span></Link>
      <nav aria-label="Main navigation"><a href="#journey-welcome">Journey</a><Link href="/workspace#data">Evidence</Link><Link href="/workspace" className={styles.workspaceLink}>Open workspace <span aria-hidden="true">↗</span></Link></nav>
    </header>
    <div ref={viewport} className={styles.journeyViewport} id="journey-content" tabIndex={0} aria-label="The Tideward journey. Scroll or use chapter links to explore.">
      {JOURNEY_CHAPTERS.map((item, index) => <section key={item.id} id={`journey-${item.id}`} className={`${styles.chapter} ${index === 0 ? styles.welcomeChapter : ""}`} data-journey-chapter={index} data-active={chapter === index} aria-labelledby={`journey-title-${item.id}`}>
        <div className={styles.chapterInner}>
          <p className={styles.eyebrow}>{item.eyebrow}</p>
          {index === 0 ? <h1 className={styles.title} id={`journey-title-${item.id}`}><span>{item.outline}</span><strong>{item.solid}</strong></h1> : <h2 className={styles.title} id={`journey-title-${item.id}`}><span>{item.outline}</span><strong>{item.solid}</strong></h2>}
          <p className={styles.chapterText}>{item.detail}</p>
          {index === 0 && !entered ? <div className={styles.entryGate}>
            <fieldset className={styles.voiceChoice}><legend>Choose your journey</legend><label><input type="radio" name="journey-voice" checked={!voiceChoice} onChange={() => setVoiceChoice(false)}/>Without voice</label><label><input type="radio" name="journey-voice" checked={voiceChoice} onChange={() => setVoiceChoice(true)}/>With narration</label></fieldset>
            <button type="button" className={`${styles.primaryAction} ${styles.entryButton}`} onClick={startJourney}>Start journey <span aria-hidden="true">↓</span></button>
            <Link href="/workspace" className={styles.skipEntry}>Or go straight to the workspace ↗</Link>
          </div> : <div className={styles.chapterActions}><Link ref={index === 0 ? startTarget : undefined} href={item.href} className={styles.primaryAction}>{item.action}<span aria-hidden="true">↗</span></Link><a href={item.secondaryHref} className={styles.secondaryAction}>{item.secondaryAction}<span aria-hidden="true">↓</span></a></div>}
          {index > 0 && <p className={styles.chapterEvidence}>{item.evidence}</p>}
          {index === 4 && <Link className={styles.operatorLink} href="/login">Operator sign in ↗</Link>}
        </div>
        <span className={styles.watermark} aria-hidden="true">0{index + 1}</span>
      </section>)}
    </div>
    <nav className={styles.route} aria-label="Journey chapters">
      <svg viewBox="0 0 100 500" preserveAspectRatio="none" aria-hidden="true"><path d="M67 40C82 90 16 109 45 145S87 210 60 250 12 313 35 355 84 410 62 460"/><path className={styles.routeGhost} d="M67 40C82 90 16 109 45 145S87 210 60 250 12 313 35 355 84 410 62 460"/></svg>
      {JOURNEY_CHAPTERS.map((item, index) => <a key={item.id} href={`#journey-${item.id}`} style={{ top: `${8 + index * 21}%`, left: `${[67,45,60,35,62][index]}%` }} aria-label={`Chapter ${index + 1}: ${item.label}`} aria-current={chapter === index ? "step" : undefined} className={styles.routeStop} onClick={() => narrator.current?.stop()}><span className={styles.routeDot}/><span className={styles.routeLabel}><small>0{index + 1}</small>{item.label}</span></a>)}
    </nav>
    <div className={styles.expedition}>
      <JourneyGlobe/>
      <div className={styles.expeditionInfo}><span className={styles.expeditionTitle}>THE TIDEWARD JOURNEY</span><span>0{chapter + 1} / 05 <b>{current.label}</b></span><div ref={progress} className={styles.progress} role="progressbar" aria-label="Journey scroll progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={0}><span/></div><span className={styles.progressLabel}>Scroll progress <span ref={progressText}>0%</span></span></div>
    </div>
    {chapter < JOURNEY_CHAPTERS.length - 1 && (entered || chapter > 0) && <a href={`#journey-${next.id}`} className={styles.scrollCue}><span aria-hidden="true">⌄<br/>⌄</span>Scroll to explore</a>}
    <div className={styles.controls}>
      <button type="button" onClick={toggleAudio} aria-pressed={narration === "speaking" || narration === "loading"} aria-describedby="narration-status"><span aria-hidden="true">{narration === "speaking" ? "◖))" : "◖)"}</span>{audioLabel}</button>
      <button type="button" onClick={() => setPaused(!paused)} aria-pressed={paused} disabled={reducedMotion}><span aria-hidden="true">{allowMotion ? "Ⅱ" : "▷"}</span>{reducedMotion ? "Reduced motion" : paused ? "Resume motion" : "Pause motion"}</button>
    </div>
    <p id="narration-status" className={styles.audioStatus} role="status">{narration === "unsupported" ? "Narration is unavailable in this browser. Read the chapter text or captions." : narration === "error" ? "Narration could not start. The full script is available in captions." : narration === "speaking" ? "Narration playing · browser voice" : narration === "loading" ? "Starting browser narration…" : "Voice is off. Listening is always your choice."}</p>
    <details className={styles.captions}><summary>Read chapter narration</summary><p>{current.narration}</p></details>
    <p className={styles.disclosure}>Illustrative ocean · synthetic software demo · physical validation pending</p>
  </main>;
}
