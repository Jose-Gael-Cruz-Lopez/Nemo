"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { BrandMark } from "./components/brand-mark";
import { BRAND_NAME } from "./components/brand";
import { JOURNEY_CHAPTERS, JOURNEY_ROUTE_PATH, JOURNEY_ROUTE_STOPS, JOURNEY_ROUTE_DOTS, chapterDepthFrame, createJourneyEntryAdvance, createJourneyHashRestore, legacyWorkspaceDestination, journeyProgress, motionAllowed } from "./landing-journey-state";
import { LandingGlobe } from "./components/landing-globe";
import styles from "./landing.module.css";


export default function Home() {
  const router = useRouter();
  const viewport = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const progress = useRef<HTMLDivElement>(null);
  const progressText = useRef<HTMLSpanElement>(null);
  const camera = useRef<HTMLDivElement>(null);
  const welcomeCopy = useRef<HTMLDivElement>(null);
  const observeSection = useRef<HTMLElement>(null);
  const observeHeading = useRef<HTMLHeadingElement>(null);
  const routePath = useRef<SVGPathElement>(null);
  const routeArrow = useRef<SVGPolygonElement>(null);
  const entry = useRef<ReturnType<typeof createJourneyEntryAdvance> | null>(null);
  const entryRunning = useRef(false);
  const activeChapter = useRef(0);
  const [chapter, setChapter] = useState(0);
  const [entered, setEntered] = useState(false);
  const [starting, setStarting] = useState(false);
  // Keep a still poster until the actual motion preference is known.
  const [reducedMotion, setReducedMotion] = useState(true);
  const [hidden, setHidden] = useState(false);
  const [videoFailed, setVideoFailed] = useState(false);
  const [videoReady, setVideoReady] = useState(false);
  const allowMotion = motionAllowed({ reducedMotion, hidden });

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
    const visibility = () => setHidden(document.hidden);
    visibility(); document.addEventListener("visibilitychange", visibility);
    return () => { query.removeEventListener("change", update); document.removeEventListener("visibilitychange", visibility); };
  }, []);

  useEffect(() => {
    const transition = createJourneyEntryAdvance({
      exit: () => welcomeCopy.current?.animate?.([
        { opacity: 1, transform: "scale(1)" },
        { opacity: 0, transform: "scale(1.35)" },
      ], { duration: 460, easing: "cubic-bezier(.22,.61,.36,1)", fill: "forwards" }) ?? null,
      running(value) { entryRunning.current = value; setStarting(value); },
      advance(motion) {
        setEntered(true);
        observeSection.current?.scrollIntoView({ behavior: motion ? "smooth" : "instant", block: "start" });
        observeHeading.current?.focus({ preventScroll: true });
        window.history.replaceState(window.history.state, "", "#journey-observe");
      },
    });
    entry.current = transition;
    return () => { transition.dispose(); entry.current = null; };
  }, []);

  useEffect(() => {
    const element = viewport.current;
    if (!element) return;
    const sections = Array.from(element.querySelectorAll<HTMLElement>("[data-journey-chapter]"));
    const copies = sections.map(section => section.querySelector<HTMLElement>("[data-journey-copy]"));
    const visibility = new Map<Element, number>();
    const observer = new IntersectionObserver(entries => {
      entries.forEach(item => visibility.set(item.target, item.intersectionRect.height));
      const mostVisible = sections.reduce((best, section) => (visibility.get(section) ?? 0) > (visibility.get(best) ?? 0) ? section : best, sections[0]);
      if (!mostVisible || (visibility.get(mostVisible) ?? 0) < Math.min(50, element.clientHeight * .2)) return;
      const next = Number(mostVisible.dataset.journeyChapter);
      if (next !== activeChapter.current) {
        activeChapter.current = next; setChapter(next);
        if (next > 0) setEntered(true);
      }
    }, { root: element, threshold: [0, .01, .05, .1, .2, .4, .6, .8, 1] });
    sections.forEach(section => observer.observe(section));
    let frame = 0;
    const path = routePath.current;
    const pathLength = path?.getTotalLength() ?? 0;
    const updateFrame = () => {
      frame = 0;
      if (document.hidden) return;
      const viewportBox = element.getBoundingClientRect();
      // Read all layout first, then write presentation only. No React state per frame.
      const positions = sections.map(section => section.getBoundingClientRect());
      const depth = positions.map(box => chapterDepthFrame({ sectionTop: box.top - viewportBox.top, sectionHeight: box.height, viewportHeight: element.clientHeight, motion: allowMotion }));
      const extent = element.scrollHeight - element.clientHeight;
      const fraction = extent > 0 ? Math.max(0, Math.min(1, element.scrollTop / extent)) : 0;
      const value = journeyProgress(element.scrollTop, element.scrollHeight, element.clientHeight);
      copies.forEach((copy, index) => {
        const visual = depth[index];
        copy?.style.setProperty("--copy-scale", String(visual.scale));
        copy?.style.setProperty("--copy-opacity", String(visual.opacity));
        copy?.style.setProperty("--copy-shift", `${visual.shiftPx}px`);
        if (copy) copy.style.willChange = visual.visible && allowMotion ? "transform,opacity" : "auto";
      });
      camera.current?.style.setProperty("--camera-scale", String(allowMotion ? 1 + fraction * .15 : 1));
      camera.current?.style.setProperty("--camera-drift", `${allowMotion ? fraction * -1.3 : 0}%`);
      camera.current?.style.setProperty("--camera-hue", `${allowMotion ? fraction * 5 : 0}deg`);
      progress.current?.style.setProperty("--progress", String(fraction));
      progress.current?.setAttribute("aria-valuenow", String(value));
      if (progressText.current) progressText.current.textContent = `${value}%`;
      if (path && routeArrow.current && pathLength) {
        const point = path.getPointAtLength(fraction * pathLength);
        const previous = path.getPointAtLength(Math.max(0, fraction * pathLength - 1));
        const next = path.getPointAtLength(Math.min(pathLength, fraction * pathLength + 1));
        const angle = Math.atan2(next.y - previous.y, next.x - previous.x) * 180 / Math.PI - 90;
        routeArrow.current.setAttribute("transform", `translate(${point.x} ${point.y}) rotate(${angle})`);
      }
      if (entryRunning.current && element.scrollTop > element.clientHeight * .15) entry.current?.cancel();
      if (positions[0].bottom <= viewportBox.top + 1) entry.current?.release();
    };
    const onScroll = () => { if (!frame) frame = window.requestAnimationFrame(updateFrame); };
    const resize = new ResizeObserver(onScroll);
    resize.observe(element); sections.forEach(section => resize.observe(section));
    element.addEventListener("scroll", onScroll, { passive: true }); updateFrame();
    return () => { observer.disconnect(); resize.disconnect(); element.removeEventListener("scroll", onScroll); if (frame) window.cancelAnimationFrame(frame); };
  }, [allowMotion]);

  useEffect(() => {
    const restore = createJourneyHashRestore({
      readHash: () => window.location.hash,
      hidden: () => document.hidden,
      findSection(id) {
        const section = document.getElementById(id);
        return section && viewport.current?.contains(section) ? section : null;
      },
      requestFrame: callback => window.requestAnimationFrame(callback),
      cancelFrame: id => window.cancelAnimationFrame(id),
    });
    restore.resume();
    document.addEventListener("visibilitychange", restore.visibilityChanged);
    return () => { document.removeEventListener("visibilitychange", restore.visibilityChanged); restore.dispose(); };
  }, []);

  useEffect(() => {
    const element = video.current;
    if (!allowMotion) entry.current?.cancel();
    if (!element) return;
    if (allowMotion && !videoFailed) void element.play().catch(() => setVideoReady(false));
    else element.pause();
    return () => element.pause();
  }, [allowMotion, videoFailed]);

  function startJourney() { void entry.current?.start(allowMotion); }

  const current = JOURNEY_CHAPTERS[chapter];

  return <main className={styles.landing} data-motion={allowMotion ? "running" : "paused"} data-entered={entered}>
    <a className={styles.skip} href="/workspace">Skip journey · open workspace</a>
    <div className={styles.oceanBackdrop} aria-hidden="true">
      <div ref={camera} className={styles.cameraFrame}>
      <div className={styles.poster}/>
      <video ref={video} className={styles.oceanVideo} data-ready={videoReady && !videoFailed && !reducedMotion} src="/nemo-ocean-depth.mp4" poster="/nemo-ocean-depth-poster.jpg" muted loop playsInline preload="none" onPlaying={() => setVideoReady(true)} onError={() => { setVideoFailed(true); setVideoReady(false); }}/>
      </div>
      <div className={styles.shade}/>
    </div>
    <header className={styles.header}>
      <Link href="/" className={styles.wordmark} aria-label={`${BRAND_NAME} home`}><BrandMark/><span>{BRAND_NAME}<small>COASTAL INTELLIGENCE</small></span></Link>
      <nav aria-label="Main navigation"><a href="#journey-welcome">Journey</a><Link href="/workspace#data">Evidence</Link><Link href="/workspace" className={styles.workspaceLink}>Open workspace <span aria-hidden="true">↗</span></Link></nav>
    </header>
    <div ref={viewport} className={styles.journeyViewport} id="journey-content" tabIndex={0} aria-label={`The ${BRAND_NAME} journey. Scroll or use chapter links to explore.`}>
      {JOURNEY_CHAPTERS.map((item, index) => <section ref={index === 1 ? observeSection : undefined} key={item.id} id={`journey-${item.id}`} className={`${styles.chapter} ${index === 0 ? styles.welcomeChapter : ""}`} data-journey-chapter={index} data-active={chapter === index} aria-labelledby={`journey-title-${item.id}`}>
        <div ref={index === 0 ? welcomeCopy : undefined} className={styles.chapterInner} data-journey-copy>
          {index === 0 ? <h1 className={styles.title} id={`journey-title-${item.id}`}><strong>{item.heading}</strong></h1> : <h2 ref={index === 1 ? observeHeading : undefined} tabIndex={-1} className={styles.title} id={`journey-title-${item.id}`}><strong>{item.heading}</strong></h2>}
          <p className={styles.chapterText}>{item.detail}</p>
          {index === 0 && !entered ? <div className={styles.entryGate}>
            <button type="button" className={`${styles.primaryAction} ${styles.entryButton}`} onClick={startJourney} disabled={starting} aria-busy={starting}>Start journey <span aria-hidden="true">↓</span></button>
            <Link href="/workspace" className={styles.skipEntry}>Or go straight to the workspace ↗</Link>
          </div> : <div className={styles.chapterActions}><Link href={item.href} className={styles.primaryAction}>{item.action}<span aria-hidden="true">↗</span></Link><a href={item.secondaryHref} className={styles.secondaryAction}>{item.secondaryAction}<span aria-hidden="true">↓</span></a></div>}
          {index > 0 && <p className={styles.chapterEvidence}>{item.evidence}</p>}
          {index === 4 && <Link className={styles.operatorLink} href="/login">Operator sign in ↗</Link>}
        </div>
      </section>)}
    </div>
    <nav className={styles.route} aria-label="Journey chapters">
      <svg viewBox="0 0 43 500" preserveAspectRatio="none" aria-hidden="true"><path ref={routePath} d={JOURNEY_ROUTE_PATH}/>{JOURNEY_ROUTE_DOTS.map((point, index) => <circle key={index} cx={point.x} cy={point.y} r=".8"/>)}<polygon ref={routeArrow} className={styles.routeArrow} points="0,6 -3,-3 0,-1 3,-3" transform="translate(30 20)"/></svg>
      {JOURNEY_CHAPTERS.map((item, index) => <a key={item.id} href={`#journey-${item.id}`} style={{ top: `${JOURNEY_ROUTE_STOPS[index].y / 5}%`, left: `${JOURNEY_ROUTE_STOPS[index].x / 43 * 100}%` }} aria-label={`Chapter ${index + 1}: ${item.label}`} aria-current={chapter === index ? "step" : undefined} className={styles.routeStop}><span className={styles.routeDot}/><span className={styles.routeLabel}><small>0{index + 1}</small>{item.label}</span></a>)}
    </nav>
    <div className={styles.expedition}>
      <LandingGlobe progress={chapter / (JOURNEY_CHAPTERS.length - 1) * 100} motion={allowMotion} className={styles.globeSlot}/>
      <div className={styles.expeditionInfo}><span className={styles.expeditionTitle}>THE {BRAND_NAME.toUpperCase()} JOURNEY</span><span>0{chapter + 1} / 05 <b>{current.label}</b></span><div ref={progress} className={styles.progress} role="progressbar" aria-label="Journey scroll progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={0}><span/></div><span className={styles.progressLabel}>Scroll progress <span ref={progressText}>0%</span></span></div>
    </div>
  </main>;
}
