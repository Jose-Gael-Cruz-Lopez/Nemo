"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
type Bench = { connected: boolean; telemetry: null | { distance_cm: number | null; pot_raw: number; armed: boolean } };
type Demo = { track: { x: number; y: number; t: number }[]; estimate: { mode: string; source: string; reason: string; ranking: { source: string; match: number }[] } };

export default function BenchConsole() {
  const [bench, setBench] = useState<Bench | null>(null);
  const [demo, setDemo] = useState<Demo | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    let alive = true;
    const refresh = async () => {
      try {
        const response = await fetch(`${API}/api/v1/bench`, { signal: AbortSignal.timeout(2500) });
        if (!response.ok) throw new Error("API unavailable");
        const status: Bench = await response.json();
        if (alive) setBench(status);
      } catch { if (alive) setBench(null); }
    };
    void refresh();
    const timer = setInterval(refresh, 3000);
    return () => { alive = false; clearInterval(timer); };
  }, []);
  async function run(scenario: string) {
    setLoading(true); setError(""); setDemo(null);
    try {
      const response = await fetch(`${API}/api/v1/demo/${scenario}`, { signal: AbortSignal.timeout(10000) });
      if (!response.ok) throw new Error(`API returned ${response.status}`);
      setDemo(await response.json());
    } catch { setError("Cannot reach the local API. Start uvicorn on port 8000."); }
    finally { setLoading(false); }
  }
  return <section className="workspace" aria-label="Bench and synthetic inference">
    <p className="eyebrow">START WITH YOUR COMPONENTS</p>
    <h2>USB bench console</h2>
    <p role="status">{bench?.connected ? "Uno telemetry connected" : "No fresh Uno telemetry"}</p>
    {bench?.connected && bench.telemetry && <p>
      Distance: {bench.telemetry.distance_cm ?? "No echo"} {bench.telemetry.distance_cm === null ? "" : "cm"}
      {" · "}Slider: {bench.telemetry.pot_raw}/1023 · Servos: {bench.telemetry.armed ? "Armed" : "Disarmed"}
    </p>}
    <p className="muted">Collection is disabled. The range sensor measures distance; it does not locate debris.</p>
    <h2>Synthetic inference sandbox</h2>
    <p className="muted">Generated tracks, a uniform current, and synthetic absorbing surface traps. Both evidence modes use forward ensembles. These are software demonstrations; the field and retention behavior are not measured. Scores are relative model support, not probabilities.</p>
    <div style={{ display: "flex", gap: 12, flexWrap: "wrap", margin: "20px 0" }}>
      {["moving", "stationary", "unknown"].map(s => <button key={s} disabled={loading} onClick={() => void run(s)} style={{ padding: "10px 18px", cursor: "pointer" }}>{s} demo</button>)}
    </div>
    {loading && <p role="status">Running ensemble…</p>}
    {error && <p role="alert">{error}</p>}
    {demo && <div aria-live="polite">
      <svg viewBox="0 0 600 400" style={{ width: "100%", maxWidth: 600, background: "#102e34", borderRadius: 12 }} role="img" aria-label="Synthetic 60 by 40 centimeter tank and observation track">
        {[8, 20, 32].map((y, i) => <text key={y} x={30} y={400-y*10} fill="#a9e1c2">{["A", "B", "C"][i]}</text>)}
        <polyline points={demo.track.map(p => `${p.x*10},${400-p.y*10}`).join(" ")} fill="none" stroke="#e7cc88" strokeWidth={4} />
        {demo.track.map((p,i) => <circle key={i} cx={p.x*10} cy={400-p.y*10} r={4} fill="#e7cc88" />)}
      </svg>
      <p><strong>{demo.estimate.mode}: {demo.estimate.source}</strong> · SYNTHETIC</p>
      <p>{demo.estimate.reason}</p>
      <ul>{demo.estimate.ranking.map(r => <li key={r.source}>Inlet {r.source}: {r.match.toFixed(3)} relative match</li>)}</ul>
    </div>}
  </section>;
}
