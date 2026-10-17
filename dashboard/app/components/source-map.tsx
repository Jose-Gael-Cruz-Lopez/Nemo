type Point = { x_cm: number; y_cm: number };
export type SourceProfile = {
  id: string;
  data_origin?: string;
  bounds: { x_min_cm: number; x_max_cm: number; y_min_cm: number; y_max_cm: number };
  sources: { id: string; polygon_cm: number[][] }[];
  traps?: { id: string; polygon_cm: number[][] }[];
};

export function SourceMap({ profile, points = [], endpoint }: {
  profile?: SourceProfile;
  points?: Point[];
  endpoint?: (Point & { retained: boolean }) | null;
}) {
  if (!profile) return <div className="map-panel empty-state"><p>No observation selected</p><span>Choose a saved case to view its path.</span></div>;
  const b = profile.bounds;
  const width = b.x_max_cm - b.x_min_cm;
  const height = b.y_max_cm - b.y_min_cm;
  const radius = Math.min(width, height) * 0.012;
  return <div className="map-panel">
    <svg className="source-map" role="img" aria-label="Candidate source regions, retained pocket, and permitted debris observations in centimeters" viewBox={`${b.x_min_cm - 2} ${b.y_min_cm - 2} ${width + 4} ${height + 4}`}>
      <defs><pattern id="tank-grid" width="2" height="2" patternUnits="userSpaceOnUse"><path d="M 2 0 L 0 0 0 2" fill="none" stroke="#e1e8e7" strokeWidth=".04" /></pattern></defs>
      <rect x={b.x_min_cm} y={b.y_min_cm} width={width} height={height} rx=".25" fill="#f2f7f6" stroke="#c0ceca" strokeWidth=".08" />
      <rect x={b.x_min_cm} y={b.y_min_cm} width={width} height={height} fill="url(#tank-grid)" />
      {profile.traps?.map(trap => <polygon key={trap.id} points={trap.polygon_cm.map(p => p.join(",")).join(" ")} fill="#dbe9e0" stroke="#9aafa0" strokeWidth=".1"><title>Retention pocket: {trap.id}</title></polygon>)}
      {profile.sources.map((source, index) => <g key={source.id}>
        <polygon points={source.polygon_cm.map(p => p.join(",")).join(" ")} fill={["#a9a2d4", "#99b9cc", "#d5b281"][index % 3]} fillOpacity=".7" />
        <text x={source.polygon_cm[0][0]} y={source.polygon_cm[0][1] - .55} fontSize={Math.max(width, height) * .032} fontWeight="600" fill="#57516c">{source.id}</text>
      </g>)}
      <polyline points={points.map(p => `${p.x_cm},${p.y_cm}`).join(" ")} fill="none" stroke="#6356b1" strokeWidth=".16" strokeLinecap="round" strokeLinejoin="round" />
      {points.map((point, index) => <circle key={index} cx={point.x_cm} cy={point.y_cm} r={radius * .32} fill="#6356b1" />)}
      {endpoint && <circle cx={endpoint.x_cm} cy={endpoint.y_cm} r={radius} fill="#6356b1" stroke="white" strokeWidth=".08"><title>Observed retained endpoint</title></circle>}
    </svg>
    <div className="map-footer"><span>Permitted observations</span><span>Water plane · cm</span></div>
  </div>;
}
