"use client";

import { useState, type ReactNode } from "react";
import { OceanSource } from "./ocean-source";

/** Keep the registered tank contract separate from geographic source research. */
export function SourceModes({ api, children, blocked = false }: { api: string; children: ReactNode; blocked?: boolean }) {
  const [mode, setMode] = useState<"tank" | "ocean">("tank");
  return <>
    <div className="action-bar" role="group" aria-label="Source tracing environment">
      <button type="button" className={mode === "tank" ? "primary-button" : "secondary-button"} aria-pressed={mode === "tank"} disabled={blocked} onClick={() => setMode("tank")}>Tank source tracing</button>
      <button type="button" className={mode === "ocean" ? "primary-button" : "secondary-button"} aria-pressed={mode === "ocean"} disabled={blocked} onClick={() => setMode("ocean")}>Ocean source research</button>
    </div>
    {mode === "tank" ? children : <OceanSource api={api} />}
  </>;
}
