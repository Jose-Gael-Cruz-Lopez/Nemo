"use client";

import { useEffect, useRef, useState } from "react";
import type { CalibrationReport } from "./field-workflow-state";
import { parseRegistration, type RegistrationStatus } from "./tank-registration-state";
import styles from "./field-workflow.module.css";

type Request = <T>(path: string, body?: unknown, options?: { signal?: AbortSignal; independent?: boolean }) => Promise<T>;
export function TankRegistration({ request, active, disabled, onStatus, onApply, onInvalidate }: {
  request: Request; active: boolean; disabled: boolean;
  onStatus: (value: RegistrationStatus | null) => void;
  onApply: (value: CalibrationReport) => void; onInvalidate: () => void;
}) {
  const [config, setConfig] = useState("");
  const [monitoring, setMonitoring] = useState(false), [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<RegistrationStatus | null>(null), [error, setError] = useState("");
  const [confirmed, setConfirmed] = useState(false), [filter, setFilter] = useState(false), [tray, setTray] = useState(false);
  const callbacks = useRef({ onStatus, onApply, onInvalidate });
  useEffect(() => { callbacks.current = { onStatus, onApply, onInvalidate }; }, [onStatus, onApply, onInvalidate]);
  useEffect(() => {
    if (!monitoring || !active) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const next = parseRegistration(await request("/vision/registration/status", undefined, { signal: controller.signal, independent: true }));
        if (controller.signal.aborted) return;
        setStatus(next); callbacks.current.onStatus(next);
        if (!next.mapping_current) callbacks.current.onInvalidate();
      } catch (cause) {
        if (controller.signal.aborted) return;
        setError(cause instanceof Error ? cause.message : "Registration monitoring unavailable");
        callbacks.current.onStatus(null); callbacks.current.onInvalidate();
        setMonitoring(false); setStatus(null);
        return;
      }
      if (!controller.signal.aborted) timer = setTimeout(poll, 500);
    };
    void poll();
    return () => { controller.abort(); if (timer) clearTimeout(timer); };
  }, [request, monitoring, active]);
  useEffect(() => {
    if (active || !monitoring) return;
    const timer = setTimeout(() => {
      callbacks.current.onStatus(null); callbacks.current.onInvalidate();
      setMonitoring(false); setStatus(null);
    }, 0);
    return () => clearTimeout(timer);
  }, [active, monitoring]);
  useEffect(() => {
    if (!monitoring) return;
    const hidden = () => {
      if (document.visibilityState === "hidden") {
        setMonitoring(false); setStatus(null);
        callbacks.current.onStatus(null); callbacks.current.onInvalidate();
      }
    };
    document.addEventListener("visibilitychange", hidden);
    return () => document.removeEventListener("visibilitychange", hidden);
  }, [monitoring]);
  async function configure() {
    setBusy(true); setMonitoring(false); setError(""); setStatus(null); callbacks.current.onStatus(null); setConfirmed(false); setTray(false); setFilter(false);
    callbacks.current.onInvalidate();
    try {
      if (config.length > 24000) throw new Error("Reference configuration exceeds 24 KB");
      const next = parseRegistration(await request("/vision/registration/configure", JSON.parse(config)));
      setStatus(next); callbacks.current.onStatus(next); setMonitoring(true);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Proposal failed"); }
    finally { setBusy(false); }
  }
  return <section className={styles.step} aria-label="Marker-assisted water-plane registration">
    <h3>Recognize measured reference markers</h3>
    <p className={styles.explain}>Survey identifiable ArUco IDs once at the water-surface height. This tool proposes a mapping; it cannot measure reference height or certify unchanged flow from an image.</p>
    <a href="/registration-demo" target="_blank" rel="noreferrer">Walk through the dry synthetic demonstration</a>
    <label>Surveyed reference configuration (JSON; centimetres)<textarea rows={5} maxLength={24000} value={config} disabled={busy || disabled} onChange={event => { setConfig(event.target.value); setMonitoring(false); setStatus(null); callbacks.current.onStatus(null); callbacks.current.onInvalidate(); }} /></label>
    <div className={styles.actions}><button className="secondary-button" disabled={disabled || busy || !active || !config.trim()} onClick={() => void configure()}>Propose / recover marker mapping</button><button className="ghost-button" disabled={busy} onClick={() => { setMonitoring(false); setStatus(null); callbacks.current.onStatus(null); callbacks.current.onInvalidate(); }}>Use manual mapping</button></div>
    {status && <><p role="status"><strong>{status.state.replaceAll("_", " ")}</strong> · {status.reason}</p>
      {status.proposal && <p>Separate check error: {status.proposal.calibration.max_error_cm.toFixed(3)} cm (frozen maximum {status.proposal.calibration.max_allowed_error_cm} cm).</p>}
      <label><input type="checkbox" checked={confirmed} disabled={disabled || busy} onChange={event => setConfirmed(event.target.checked)} />I checked surveyed scale, waterline and reference height on the rig.</label>
      {(["tray_boundary", "filter_border"] as const).map((name, i) => <label key={name}><input type="checkbox" checked={i ? filter : tray} disabled={disabled || busy || status.geometry_layers[name]?.status !== "CANDIDATE"} onChange={event => (i ? setFilter : setTray)(event.target.checked)} />Confirm {name.replaceAll("_", " ")} candidate (does not rewrite trial geometry)</label>)}
      <button className="primary-button" disabled={disabled || busy || !confirmed || !status.ready_for_approval || status.mapping_current || status.data_origin !== "OPERATOR_SURVEYED"} onClick={async () => {
        setBusy(true); setError("");
        try {
          const next = parseRegistration(await request("/vision/registration/approve", { proposal_id: status.proposal_id, water_surface_and_scale_confirmed: confirmed, confirmed_layers: [...tray ? ["tray_boundary"] : [], ...filter ? ["filter_border"] : []] }));
          setStatus(next); callbacks.current.onStatus(next);
          if (next.mapping_current && next.proposal) callbacks.current.onApply({ ...next.proposal.calibration, marker_managed: true, mapping_polygon_px: next.proposal.fit_pixels, water_region_polygon_px: next.proposal.water_polygon_px });
        } catch (cause) { setError(cause instanceof Error ? cause.message : "Approval failed"); callbacks.current.onInvalidate(); }
        finally { setBusy(false); }
      }}>Approve current mapping</button>
      <button className="secondary-button" disabled={disabled || busy} onClick={async () => {
        setBusy(true);
        try {
          const body = JSON.parse(config).context;
          // Explicitly invalidate; new measured configuration is required for recovery.
          const next = parseRegistration(await request("/vision/registration/context", body));
          setStatus(next); callbacks.current.onStatus(next); callbacks.current.onInvalidate();
        } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not invalidate mapping"); callbacks.current.onInvalidate(); }
        finally { setBusy(false); }
      }}>Report moved filter / pump / outlet / waterline / token change</button>
    </>}
    {error && <p role="alert">{error}</p>}
    <p className={styles.help}>Markers missing, camera moved, session/resolution changed or monitoring failed: centimetres are withheld. Recovery never resumes a trial automatically. Declare rig changes and revalidate drift through the existing commissioning steps.</p>
  </section>;
}
