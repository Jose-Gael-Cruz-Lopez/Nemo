"use client";

import { useState, type ReactNode } from "react";
import { OceanPrevention } from "./ocean-prevention";

/** Ocean comparisons are the first view; tank records keep their own units and ledger. */
export function PreventionModes({ api, children, blocked = false }: { api: string; children: ReactNode; blocked?: boolean }) {
  const [mode, setMode] = useState<"ocean" | "tank">("ocean");
  return <>
    <div className={mode === "ocean" ? "page-heading prevention-heading" : "page-heading"}>
    {mode === "ocean" && <div><h1>Interception comparison</h1><p className="page-description">Compare two layouts under the same changing currents.</p></div>}
    <div className="action-bar" role="group" aria-label="Prevention environment">
      <button type="button" className={mode === "ocean" ? "primary-button" : "secondary-button"} aria-pressed={mode === "ocean"} disabled={blocked} onClick={() => setMode("ocean")}>Ocean · changing currents</button>
      <button type="button" className={mode === "tank" ? "primary-button" : "secondary-button"} aria-pressed={mode === "tank"} disabled={blocked} onClick={() => setMode("tank")}>Tank experiment &amp; trial ledger</button>
    </div>
    </div>
    {mode === "ocean" ? <OceanPrevention api={api} /> : children}
  </>;
}
