import type { Metadata } from "next";
import { BrandMark } from "../components/brand-mark";
import { BRAND_NAME } from "../components/brand";
import { OceanPrevention } from "../components/ocean-prevention";
import { SHOWCASE_PROVENANCE } from "../../showcase/report";
import styles from "./showcase.module.css";

export const metadata: Metadata = { title: `${BRAND_NAME} | Ocean prevention demo`, description: "Explore two interception layouts in a verified changing-current ocean snapshot." };

export default function OceanShowcase() {
  return <main className={styles.main}>
    <a className="sr-only skip-link" href="#ocean-demo">Skip to ocean comparison</a>
    <header className={styles.header}><div className={styles.brand}><BrandMark/><strong>{BRAND_NAME}</strong><span>COASTAL RESEARCH</span></div><span className="pill">Public · read-only demo</span></header>
    <section className={styles.intro} id="ocean-demo"><p className={styles.kicker}>OBSERVE THE FLOW. COMPARE PROTECTION.</p><h1>Which layout keeps paths out?</h1><p>Explore six hypothetical releases driven by a captured PacIOOS ocean-current forecast. Compare equal-length interception layouts in one interactive plot.</p><p className={styles.disclosure}>This hosted showcase serves verified saved numerical reports. It is separate from the team’s full local experiment software. It does not connect to your camera, change trials, send Photon messages or call Chalk. No sign-in or credentials are needed.</p></section>
    <OceanPrevention api="/showcase" readOnly />
    <section className={styles.validation}><h2>What still needs to happen in the tank?</h2><p>Calibrate the fixed webcam to measured tank coordinates. Record independent drift trials, fit the measured flow, and check predictions against held-out recordings. Then test no interception and both layouts with the same release protocol, count actual captures and protected-area entries, and compare those observations with the frozen predictions.</p><p>Ocean paths are measured in metres; tank observations are measured in centimetres. A successful tabletop experiment would validate the tank setup under its tested conditions. It would not establish ocean-scale capture efficiency or real reef protection.</p></section>
    <footer className={styles.footer}><span>Snapshot export: {SHOWCASE_PROVENANCE.generatedAt} · source checkpoint {SHOWCASE_PROVENANCE.sourceCommit.slice(0, 7)}. Exact scientific source and report hashes are available in the method disclosure.</span><a href="https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/ocean-prevention.md" target="_blank" rel="noreferrer">Read the method and validation limits ↗</a></footer>
  </main>;
}
