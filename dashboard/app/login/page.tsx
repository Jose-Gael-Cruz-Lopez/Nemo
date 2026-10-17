"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useOperator } from "../components/operator-provider";
import { Icon } from "../components/icons";
import { CoastalTerrain } from "../components/coastal-terrain";
import styles from "../welcome.module.css";

export default function Login() {
  const router = useRouter();
  const { token, connect, disconnect } = useOperator();
  const [draft, setDraft] = useState("");
  const [show, setShow] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const pendingRequest = useRef<AbortController | null>(null);
  useEffect(() => () => pendingRequest.current?.abort(), []);
  async function signIn(event: FormEvent) {
    event.preventDefault();
    if (pendingRequest.current) return;
    const controller = new AbortController(); pendingRequest.current = controller;
    setPending(true); setError("");
    try { await connect(draft, controller.signal); if (!controller.signal.aborted) { setDraft(""); router.push("/workspace"); } }
    catch (cause) { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Operator verification failed."); }
    finally { if (pendingRequest.current === controller) pendingRequest.current = null; if (!controller.signal.aborted) setPending(false); }
  }
  return <main className={`${styles.welcome} ${styles.loginPage}`}>
    <div className={styles.loginFrame}>
      <header className={styles.header}><Link href="/" className={styles.wordmark}><span className={styles.mark}><Icon name="wave" /></span>ReefTrace</Link><Link href="/" className={styles.backLink}>← Back to home</Link></header>
      <div className={styles.loginGrid}>
        <section className={styles.loginStory}><div className={styles.eyebrow}><span />YOUR NEXT STEP STARTS HERE</div><h1>A clearer view.<br /><span>A stronger impact.</span></h1><p>Bring your observations, your questions,<br />and your next coastal intervention together.</p><CoastalTerrain phase={1} className={styles.loginTerrain} /><span className={styles.loginCaption}>OBSERVE. TRACE. PREVENT.</span></section>
        <section className={styles.loginPanel} aria-labelledby="login-title">
          <div className={styles.loginPanelIcon}><Icon name="key" /></div><p className={styles.eyebrow}>REEFTRACE WORKSPACE</p><h2 id="login-title">Welcome to the current.</h2><p className={styles.loginIntro}>Sign in with your team’s local operator token to run observations and investigations.</p>
          {token ? <div className={styles.connectedState}><span className={styles.connectedBadge}><Icon name="check" />Operator connected</span><p>You’re verified in this browser tab.</p><Link href="/workspace" className={styles.primary}>Continue to workspace <Icon name="arrow" /></Link><button className={styles.textButton} onClick={disconnect}>Disconnect operator</button></div> : <form onSubmit={signIn} className={styles.loginForm}>
            <label htmlFor="operator-token">Operator token</label><div className={styles.tokenField}><Icon name="key" /><input id="operator-token" type={show ? "text" : "password"} autoComplete="off" autoCapitalize="none" spellCheck={false} required value={draft} onChange={event => { setDraft(event.target.value); setError(""); }} placeholder="Enter your local token" disabled={pending} aria-describedby="token-help" /><button type="button" onClick={() => setShow(!show)} disabled={pending} aria-label={show ? "Hide operator token" : "Show operator token"} aria-pressed={show}>{show ? "Hide" : "Show"}</button></div>
            <p id="token-help" className={styles.tokenHelp}>Find <code>REEFTRACE_LOCAL_TOKEN</code> in your team’s local <code>reeftrace/.env</code> file.</p>
            {error && <p className={styles.loginError} role="alert">{error}</p>}
            <button type="submit" className={styles.primary} disabled={pending || !draft.trim()}>{pending ? "Verifying access…" : "Sign in to workspace"}<Icon name={pending ? "clock" : "arrow"} /></button>
          </form>}
          <div className={styles.loginDivider}><span />Or explore first<span /></div><Link href="/workspace" className={styles.exploreLink}>View saved observations <Icon name="arrow" /></Link>
          <p className={styles.privacyNote}><Icon name="check" />Your operator token stays in this tab’s memory. Provider keys stay on the server. Reloading clears operator access.</p>
        </section>
      </div><div className={styles.loginBottom}><span>BETTER DECISIONS BEGIN WITH EVIDENCE.</span><span>Local research workspace</span></div>
    </div>
  </main>;
}
