/** Geometry for a display guide. A pixel lattice is never a physical calibration. */
export type Point = [number, number];
export type Matrix3 = [Point3, Point3, Point3];
type Point3 = [number, number, number];
export function cameraStreamSource(apiBase: string, sessionId: string | null, active: boolean): string | undefined {
  return active && sessionId ? `${apiBase.replace(/\/$/, "")}/api/v1/camera/stream.mjpg?session_id=${encodeURIComponent(sessionId)}` : undefined;
}
export type WaterMapping = {
  approved: boolean; camera_session_id: string; image_size_px: [number, number];
  homography_image_to_cm?: number[][]; plane?: string; units?: string;
  /** Frozen fitting-mark hull, retained by the UI from the submitted correspondences. */
  mapping_polygon_px?: number[][];
  /** Actual surveyed water outline; may be concave. Clip display/readout to it. */
  water_region_polygon_px?: number[][];
  /** An operator-authorized visual estimate; never a calibrated measurement. */
  estimated?: boolean;
};

export function invertMatrix(value: unknown): Matrix3 | null {
  if (!Array.isArray(value) || value.length !== 3 || value.some(row => !Array.isArray(row) || row.length !== 3 || row.some(v => typeof v !== "number" || !Number.isFinite(v)))) return null;
  const scale = Math.max(...value.flat().map(Math.abs));
  if (!scale) return null;
  const [[a,b,c],[d,e,f],[g,h,i]] = value.map(row => row.map((v: number) => v / scale));
  const cofactors = [[e*i-f*h,c*h-b*i,b*f-c*e],[f*g-d*i,a*i-c*g,c*d-a*f],[d*h-e*g,b*g-a*h,a*e-b*d]];
  const determinant = a*cofactors[0][0]+b*cofactors[1][0]+c*cofactors[2][0];
  if (!Number.isFinite(determinant) || Math.abs(determinant) <= 1e-12) return null;
  // The inverse may have an arbitrary homogeneous scale.
  return cofactors.map(row => row.map(v => v / determinant)) as Matrix3;
}

export function projectPoint(matrix: number[][], point: Point): Point | null {
  if (!invertMatrix(matrix) || !point.every(Number.isFinite)) return null;
  const [x,y] = point;
  const denominator = matrix[2][0]*x+matrix[2][1]*y+matrix[2][2];
  const magnitude = Math.abs(matrix[2][0]*x)+Math.abs(matrix[2][1]*y)+Math.abs(matrix[2][2]);
  if (Math.abs(denominator) <= 1e-10*Math.max(magnitude, 1e-300)) return null;
  const result: Point = [(matrix[0][0]*x+matrix[0][1]*y+matrix[0][2])/denominator, (matrix[1][0]*x+matrix[1][1]*y+matrix[1][2])/denominator];
  return result.every(Number.isFinite) ? result : null;
}

export function convexHull(value: unknown): Point[] {
  if (!Array.isArray(value) || value.length > 100 || value.some(p => !Array.isArray(p) || p.length !== 2 || !p.every(v => typeof v === "number" && Number.isFinite(v)))) return [];
  const points = [...new Map(value.map(p => [p.join(","), [p[0],p[1]] as Point])).values()].sort((a,b) => a[0]-b[0] || a[1]-b[1]);
  if (points.length < 3) return [];
  const cross = (a: Point,b: Point,c: Point) => (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
  const lower: Point[] = [], upper: Point[] = [];
  for (const p of points) { while (lower.length >= 2 && cross(lower.at(-2)!,lower.at(-1)!,p) <= 0) lower.pop(); lower.push(p); }
  for (const p of points.toReversed()) { while (upper.length >= 2 && cross(upper.at(-2)!,upper.at(-1)!,p) <= 0) upper.pop(); upper.push(p); }
  const hull = lower.slice(0,-1).concat(upper.slice(0,-1));
  return hull.length >= 3 ? hull : [];
}

export function insideHull(point: Point, hull: Point[]) {
  return hull.length >= 3 && hull.every((a,index) => {
    const b = hull[(index+1)%hull.length];
    return (b[0]-a[0])*(point[1]-a[1])-(b[1]-a[1])*(point[0]-a[0]) >= -1e-7;
  });
}

export function insidePolygon(point: Point, polygon: Point[]): boolean {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const a = polygon[j], b = polygon[i], dx = b[0] - a[0], dy = b[1] - a[1];
    const cross = dx * (point[1] - a[1]) - dy * (point[0] - a[0]);
    if (Math.abs(cross) < 1e-7 && point[0] >= Math.min(a[0], b[0]) - 1e-7 && point[0] <= Math.max(a[0], b[0]) + 1e-7 && point[1] >= Math.min(a[1], b[1]) - 1e-7 && point[1] <= Math.max(a[1], b[1]) + 1e-7) return true;
    if ((a[1] > point[1]) !== (b[1] > point[1]) && point[0] < (b[0] - a[0]) * (point[1] - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
  }
  return inside;
}

export function nativePixel(offsetX: number, offsetY: number, shownWidth: number, shownHeight: number, imageWidth: number, imageHeight: number): Point | null {
  if (![offsetX,offsetY,shownWidth,shownHeight,imageWidth,imageHeight].every(Number.isFinite) || shownWidth <= 0 || shownHeight <= 0 || imageWidth < 2 || imageHeight < 2) return null;
  return [Math.min(imageWidth-1,Math.max(0,offsetX*imageWidth/shownWidth)), Math.min(imageHeight-1,Math.max(0,offsetY*imageHeight/shownHeight))];
}

export type GridLine = { axis: "x" | "y"; value: number; start: Point; end: Point };
export function metricGrid(mapping: WaterMapping | null | undefined, sessionId: string | null, width: number, height: number): { hull: Point[]; clipPolygon: Point[]; lines: GridLine[]; spacingCm: number; matrix: number[][]; estimated: boolean } | null {
  const estimated = mapping?.estimated === true && mapping.approved === false && mapping.plane === "estimated_water_surface";
  const measured = mapping?.approved === true && !mapping.estimated && mapping.plane === "measured_water_surface";
  if ((!estimated && !measured) || !mapping || mapping.camera_session_id !== sessionId || mapping.image_size_px[0] !== width || mapping.image_size_px[1] !== height || mapping.units !== "cm") return null;
  const matrix = mapping.homography_image_to_cm, inverse = invertMatrix(matrix);
  const hull = convexHull(mapping.mapping_polygon_px);
  if (!matrix || !inverse || !hull.length || hull.some(([x,y]) => x < 0 || y < 0 || x > width-1 || y > height-1)) return null;
  const denominators = hull.map(([x,y]) => matrix[2][0]*x+matrix[2][1]*y+matrix[2][2]);
  if (Math.min(...denominators) <= 0 && Math.max(...denominators) >= 0) return null;
  const worldPoints = hull.map(p => projectPoint(matrix,p));
  if (worldPoints.some(p => !p)) return null;
  const world = convexHull(worldPoints), bounds = [0,1].map(axis => [Math.min(...world.map(p => p[axis])),Math.max(...world.map(p => p[axis]))]);
  const span = Math.max(...bounds.map(([a,b]) => b-a));
  if (!world.length || span <= 0 || span > 200) return null;
  const spacingCm = span <= 10 ? 1 : span <= 50 ? 5 : 10;
  const lines: GridLine[] = [];
  for (const axis of [0,1] as const) {
    const first = Math.ceil(bounds[axis][0]/spacingCm)*spacingCm;
    const count = Math.floor((bounds[axis][1]-first)/spacingCm+1e-8)+1;
    // Index-based bounded iteration also prevents floating-point stagnation at a large origin.
    for (let tick = 0; tick < Math.min(count,64); tick++) {
      const value = first+tick*spacingCm;
      const crossings: Point[] = [];
      world.forEach((a,index) => {
        const b = world[(index+1)%world.length], delta = b[axis]-a[axis];
        if (Math.abs(delta) < 1e-10) { if (Math.abs(a[axis]-value) < 1e-8) crossings.push(a,b); return; }
        const t = (value-a[axis])/delta;
        if (t >= -1e-8 && t <= 1+1e-8) crossings.push([a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])]);
      });
      crossings.sort((a,b) => a[1-axis]-b[1-axis]);
      if (crossings.length >= 2) {
        const start = projectPoint(inverse,crossings[0]), end = projectPoint(inverse,crossings.at(-1)!);
        if (start && end && insideHull(start,hull) && insideHull(end,hull) && Math.hypot(start[0]-end[0],start[1]-end[1]) > 1e-7) lines.push({ axis: axis === 0 ? "x" : "y",value,start,end });
      }
    }
  }
  const clipPolygon = mapping.water_region_polygon_px ?? hull;
  if (!Array.isArray(clipPolygon) || clipPolygon.length < 3 || clipPolygon.length > 100 || clipPolygon.some(p => !Array.isArray(p) || p.length !== 2 || !p.every(Number.isFinite) || !insideHull(p as Point, hull))) return null;
  return { hull,clipPolygon: clipPolygon as Point[],lines,spacingCm,matrix,estimated };
}
