"use client";

import { useId, useState } from "react";
import styles from "./plot-controls.module.css";

/** A short explanation available to pointer, keyboard and touch users. */
export function HelpLabel({ label, explanation }: { label: string; explanation: string }) {
  const id = useId();
  const [hovered, setHovered] = useState(false), [focused, setFocused] = useState(false);
  const [pinned, setPinned] = useState(false), [dismissed, setDismissed] = useState(false);
  const visible = !dismissed && (hovered || focused || pinned);
  return <span className={styles.help} onMouseEnter={() => { setHovered(true); setDismissed(false); }} onMouseLeave={() => setHovered(false)}>
    <button type="button" className={styles.helpButton} aria-describedby={id}
      onFocus={() => { setFocused(true); setDismissed(false); }} onBlur={() => { setFocused(false); setPinned(false); }}
      onClick={() => { setPinned(value => !value); setDismissed(false); }}
      onKeyDown={event => { if (event.key === "Escape") { setDismissed(true); setPinned(false); } }}>
      {label}<span className={styles.helpMark} aria-hidden="true">?</span>
    </button>
    <span id={id} role="tooltip" className={`${styles.tooltip} ${visible ? styles.tooltipVisible : ""}`}>{explanation}</span>
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
