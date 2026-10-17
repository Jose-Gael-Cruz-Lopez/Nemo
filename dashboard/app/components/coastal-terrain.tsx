import { useId } from "react";

function height(x: number, y: number) {
  return 2.4 * Math.exp(-((x - .38) ** 2 / .025 + (y - .42) ** 2 / .045))
    + 1.7 * Math.exp(-((x - .73) ** 2 / .055 + (y - .68) ** 2 / .025))
    + 1.05 * Math.exp(-((x - .12) ** 2 / .02 + (y - .78) ** 2 / .08))
    + .16 * Math.sin(x * 12 + y * 9) + .09 * Math.cos(y * 22 - x * 4);
}
function project(x: number, y: number, z: number) { return [60 + x * 1280, 180 + y * 380 + x * 38 - z * 92]; }
// Deterministic vector contours: illustrative geometry, never a scientific map.
const CONTOURS = Array.from({ length: 32 }, (_, level) => {
  const z = -.12 + level * .082;
  const segments: string[] = [];
  for (let row = 0; row < 55; row++) for (let col = 0; col < 108; col++) {
    const corners = [[col / 108, row / 55], [(col + 1) / 108, row / 55], [(col + 1) / 108, (row + 1) / 55], [col / 108, (row + 1) / 55]];
    const hits: number[][] = [];
    for (let edge = 0; edge < 4; edge++) {
      const a = corners[edge], b = corners[(edge + 1) % 4];
      const ha = height(a[0], a[1]), hb = height(b[0], b[1]);
      if ((ha < z) !== (hb < z)) {
        const t = (z - ha) / (hb - ha);
        hits.push(project(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, z));
      }
    }
    for (let i = 0; i + 1 < hits.length; i += 2) segments.push(`M${hits[i][0].toFixed(1)},${hits[i][1].toFixed(1)}L${hits[i + 1][0].toFixed(1)},${hits[i + 1][1].toFixed(1)}`);
  }
  return segments.join("");
});
const STATIONS = [{ x: 210, y: 400, top: 262, label: "OBS. 01" }, { x: 515, y: 248, top: 124, label: "SOURCE A" }, { x: 810, y: 458, top: 285, label: "SOURCE B" }, { x: 1110, y: 370, top: 204, label: "REEF ZONE" }];

export function CoastalTerrain({ phase = 0, className = "" }: { phase?: number; className?: string }) {
  const id = useId().replaceAll(":", "");
  return <svg className={className} viewBox="0 0 1400 630" fill="none" role="img" aria-label="Illustrative coastal terrain with observation sites, a possible drift route, and a protected reef zone">
    <defs><linearGradient id={`${id}-wash`} x1="150" y1="180" x2="1200" y2="600" gradientUnits="userSpaceOnUse"><stop stopColor="#c4eef8" stopOpacity=".15" /><stop offset=".5" stopColor="#2786a9" stopOpacity=".4" /><stop offset="1" stopColor="#80c9df" stopOpacity=".12" /></linearGradient><linearGradient id={`${id}-fade`} x1="0" y1="0" x2="0" y2="630" gradientUnits="userSpaceOnUse"><stop stopColor="#72bfd4" stopOpacity=".55" /><stop offset="1" stopColor="#72bfd4" stopOpacity=".18" /></linearGradient></defs>
    <path d="M45 411 421 183 1360 413 989 615Z" fill={`url(#${id}-wash)`} />
    <g stroke={`url(#${id}-fade)`} strokeWidth="1" strokeLinejoin="round">{CONTOURS.map((d, i) => <path key={i} d={d} />)}</g>
    <g stroke="#75dcf1" opacity={phase > 0 ? .95 : .45}>
      <path d="M210 400C355 360 349 439 504 436S742 322 866 357 1008 434 1110 370" strokeWidth="2" strokeDasharray="5 8" />
      <circle cx="504" cy="436" r="4" fill="#75dcf1" /><circle cx="866" cy="357" r="4" fill="#75dcf1" />
    </g>
    <path d="m1027 369 85-45 98 25-85 47Z" fill="#4cb4cf" fillOpacity={phase === 2 ? .45 : .15} stroke="#81d4e7" strokeWidth="1.5" strokeDasharray="4 5" />
    {STATIONS.map((s, i) => <g key={s.label} opacity={phase === 0 || phase === 1 && i < 3 || phase === 2 && i === 3 ? 1 : .45}>
      <ellipse cx={s.x} cy={s.y} rx="9" ry="4" fill="#7ad7ee" fillOpacity=".2" />
      <path d={`M${s.x} ${s.y}V${s.top}`} stroke="#7fd4e6" strokeWidth="1.2" />
      <path d={`m${s.x} ${s.top - 8} 7 4v8l-7 4-7-4v-8Z M${s.x} ${s.top - 8}v16m-7-12 7 4 7-4`} stroke="#61bdd9" strokeWidth="1.1" fill="#e9fbff" />
      <rect x={s.x + 11} y={s.top - 9} width={s.label.length * 6.5 + 12} height="20" rx="0" fill="#e7f8fd" fillOpacity=".85" />
      <text x={s.x + 17} y={s.top + 5} fill="#164861" fontSize="9" fontFamily="monospace" letterSpacing=".6">{s.label}</text>
    </g>)}
  </svg>;
}
