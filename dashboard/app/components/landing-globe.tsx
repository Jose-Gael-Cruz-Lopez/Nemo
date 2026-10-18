"use client";

import { memo, useEffect, useRef, useState } from "react";
import {
  atomicGlobeConfig, createGlobeFrameDriver, createGlobeResourceScope, globeReticleTicks,
  type GlobeFrameDriver,
} from "./globe-state";
import styles from "./landing-globe.module.css";

export type LandingGlobeProps = { progress: number; motion: boolean; className?: string };
const TICKS = globeReticleTicks();

/** Decorative Earth only. Natural Earth coastlines never become app evidence. */
export const LandingGlobe = memo(function LandingGlobe({ progress, motion, className }: LandingGlobeProps) {
  const host = useRef<HTMLDivElement>(null);
  const surface = useRef<HTMLDivElement>(null);
  const runtime = useRef<import("./atomic-globe-runtime.mjs").GlobeRuntime | null>(null);
  const syncRuntime = useRef<(() => void) | null>(null);
  const driver = useRef<GlobeFrameDriver | null>(null);
  const presentation = useRef({ progress, motion });
  const [rendererKind, setRendererKind] = useState<"still" | "webgl">("still");

  useEffect(() => {
    presentation.current = { progress, motion };
    runtime.current?.apply(atomicGlobeConfig(progress));
    driver.current?.update({ progress, motion });
    syncRuntime.current?.();
  }, [progress, motion]);

  useEffect(() => {
    const mount = host.current, target = surface.current;
    if (!mount || !target) return;
    const element: HTMLDivElement = mount, stage: HTMLDivElement = target;
    const resources = createGlobeResourceScope();
    let disposed = false, starting = false, failed = false;
    let resizeScene: (() => void) | null = null;
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const rect = element.getBoundingClientRect();
    let intersecting = rect.bottom > 0 && rect.right > 0
      && rect.top < window.innerHeight && rect.left < window.innerWidth;

    const sync = () => {
      if (disposed || failed) return;
      driver.current?.update({ ...presentation.current, reducedMotion: query.matches,
        hidden: document.hidden, intersecting });
      if (presentation.current.motion && !query.matches && !document.hidden && intersecting) void initialize();
    };
    syncRuntime.current = sync;
    async function initialize() {
      if (disposed || failed || starting || driver.current) return;
      starting = true;
      try {
        // This is the supplied Framer component's real coast/scatter/shader
        // runtime, with the auditable local lifecycle adapter. No remote code.
        const { GlobeRuntime } = await import("./atomic-globe-runtime.mjs");
        if (disposed || failed || !presentation.current.motion || query.matches || document.hidden || !intersecting) return;
        const globe = new GlobeRuntime(stage, atomicGlobeConfig(presentation.current.progress), false);
        runtime.current = globe;
        resources.add(() => { globe.dispose(); if (runtime.current === globe) runtime.current = null; });
        const canvas = globe.renderer.domElement;
        const onContextLost = (event: Event) => { event.preventDefault(); failToStill(); };
        canvas.addEventListener("webglcontextlost", onContextLost);
        resources.add(() => canvas.removeEventListener("webglcontextlost", onContextLost));
        let hasDrawn = false;
        const frames = createGlobeFrameDriver({
          requestFrame: callback => window.requestAnimationFrame(callback),
          cancelFrame: id => window.cancelAnimationFrame(id),
          draw: (_pose, elapsedSeconds) => {
            if (disposed || failed) return;
            try {
              globe.tick(elapsedSeconds * 1000);
              if (!hasDrawn) { hasDrawn = true; setRendererKind("webgl"); }
            } catch { failToStill(); }
          },
        });
        driver.current = frames;
        resources.add(() => { frames.dispose(); if (driver.current === frames) driver.current = null; });
        resizeScene = () => {
          if (disposed || failed) return;
          globe.resize(); frames.invalidate();
        };
        const resize = new ResizeObserver(() => resizeScene?.());
        resize.observe(element); resources.add(() => resize.disconnect());
        sync();
      } catch {
        if (!disposed) failToStill();
      } finally { starting = false; }
    }
    function failToStill() {
      if (disposed || failed) return;
      failed = true; setRendererKind("still"); resources.dispose(); resizeScene = null;
    }
    document.addEventListener("visibilitychange", sync);
    resources.add(() => document.removeEventListener("visibilitychange", sync));
    query.addEventListener("change", sync); resources.add(() => query.removeEventListener("change", sync));
    const onResize = () => resizeScene?.();
    window.addEventListener("resize", onResize); resources.add(() => window.removeEventListener("resize", onResize));
    if (typeof IntersectionObserver !== "undefined") {
      const observer = new IntersectionObserver(entries => {
        intersecting = entries.some(entry => entry.target === element && entry.isIntersecting);
        sync();
      });
      observer.observe(element); resources.add(() => observer.disconnect());
    }
    sync();
    return () => {
      disposed = true; resources.dispose(); resizeScene = null;
      if (syncRuntime.current === sync) syncRuntime.current = null;
    };
  }, []);

  return <div ref={host} className={`${styles.globe}${className ? ` ${className}` : ""}`}
    data-globe-renderer={rendererKind} role="img"
    aria-label="Illustrative Earth with Natural Earth coastlines, rendered with the supplied AtomicGlobe component. This globe is not observation data.">
    <div className={styles.still} aria-hidden="true"/>
    <div ref={surface} className={styles.surface} aria-hidden="true"/>
    <svg className={styles.reticle} viewBox="0 0 189 189" aria-hidden="true" focusable="false">
      <circle cx="94.5" cy="94.5" r="72" className={styles.innerRing}/>
      <circle cx="94.5" cy="94.5" r="88" className={styles.outerRing}/>
      <circle cx="94.5" cy="94.5" r="65" className={styles.sphereRing}/>
      <g className={styles.ticks}>{TICKS.map((tick, index) => <line key={index} {...tick}/>)}</g>
      <g className={styles.crosshairs}>
        <path d="M94.5 0v11m0 8v10m0 131v10m0 8v11M0 94.5h11m8 0h10m131 0h10m8 0h11"/>
        <path d="M87.5 6h14M87.5 183h14M6 87.5v14M183 87.5v14"/>
      </g>
      <g className={styles.labels}><text x="94.5" y="18">N</text><text x="174" y="96.5">E</text><text x="94.5" y="175">S</text><text x="15" y="96.5">W</text></g>
      <path className={styles.orbit} d="M31 128a72 72 0 0 1-6-52M143 41a72 72 0 0 1 20 28"/>
    </svg>
  </div>;
});
