"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import styles from "./plot-controls.module.css";

/** A short explanation available to pointer, keyboard and touch users. */
export function HelpLabel({ label, explanation }: { label: string; explanation: string }) {
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null), tooltip = useRef<HTMLSpanElement>(null);
  const [position, setPosition] = useState({ left: 12, top: 12 });
  const place = useCallback(() => {
    const rect = trigger.current?.getBoundingClientRect();
    if (!rect) return;
    const width = Math.min(260, window.innerWidth - 24);
    const height = tooltip.current?.getBoundingClientRect().height ?? 110;
    const left = Math.max(12, Math.min(rect.left, window.innerWidth - width - 12));
    const below = rect.bottom + 8;
    const top = below + height <= window.innerHeight - 12 ? below : Math.max(12, rect.top - height - 8);
    setPosition(previous => previous.left === left && previous.top === top ? previous : { left, top });
  }, []);
  const [hovered, setHovered] = useState(false), [focused, setFocused] = useState(false);
  const [pinned, setPinned] = useState(false), [dismissed, setDismissed] = useState(false);
  const visible = !dismissed && (hovered || focused || pinned);
  useEffect(() => {
    if (!visible) return;
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => { window.removeEventListener("resize", place); window.removeEventListener("scroll", place, true); };
  }, [visible, place]);
  const description = <span ref={tooltip} id={id} role="tooltip" style={position}
    onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}
    className={`${styles.tooltip} ${visible ? styles.tooltipVisible : ""}`}>{explanation}</span>;
  return <span className={styles.help} onMouseEnter={() => { place(); setHovered(true); setDismissed(false); }} onMouseLeave={() => setHovered(false)}>
    <button ref={trigger} type="button" className={styles.helpButton} aria-describedby={id}
      onFocus={() => { place(); setFocused(true); setDismissed(false); }} onBlur={() => { setFocused(false); setPinned(false); }}
      onClick={() => { place(); setPinned(value => !value); setDismissed(false); }}
      onKeyDown={event => { if (event.key === "Escape") { setDismissed(true); setPinned(false); } }}>
      {label}<span className={styles.helpMark} aria-hidden="true">?</span>
    </button>
    {visible && typeof document !== "undefined" ? createPortal(description, document.body) : description}
  </span>;
}

export type PlotSeries = { id: string; label: string; explanation: string; color: string; dashed?: boolean; checked: boolean };

/** Controls only plot visibility. Numeric evidence and plot scales stay unchanged. */
export function PlotSeriesControls({ legend, series, onChange }: {
  legend: string; series: PlotSeries[]; onChange: (id: string, checked: boolean) => void;
}) {
  return <fieldset className={styles.controls}>
    <legend>{legend}</legend>
    <div className={styles.series}>{series.map(item => <label className={styles.seriesLabel} key={item.id} title={item.explanation}>
      <input type="checkbox" checked={item.checked} onChange={event => onChange(item.id, event.target.checked)} />
      <span className={styles.swatch} style={{ borderColor: item.color, borderTopStyle: item.dashed ? "dashed" : "solid" }} aria-hidden="true" />
      <span>{item.label}</span><span className="sr-only">. {item.explanation}</span>
    </label>)}</div>
    <p className={styles.controlNote}>Hide a series to inspect the other. Scale and scores stay fixed.</p>
  </fieldset>;
}

export type PathVisibility = { recorded: boolean; forecast: boolean };
export type VectorVisibility = { observed: boolean; predicted: boolean; residual: boolean };
