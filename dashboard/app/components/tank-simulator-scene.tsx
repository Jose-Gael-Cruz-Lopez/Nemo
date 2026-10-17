"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { recordedTankPositionAt, supportedTankVectors, tankPositionAt, tankWaterLabels, visibleTankPaths, type TankLayout, type TankScene } from "./tank-simulator-state";
import styles from "./tank-simulator.module.css";

export type TankSceneView = {
  layout: TankLayout; source: string; paths: boolean; grid: boolean; flow: boolean; hardware: boolean; labels: boolean;
  clock: "model" | "capture"; time: number; recordingId: string;
  camera: "orbit" | "overhead"; cameraRevision: number; active: boolean;
};
type Props = { report: TankScene; view: TankSceneView; onUnavailable: (message: string) => void };
type Engine = { update: (view: TankSceneView) => void; reset: (view: TankSceneView) => void; dispose: () => void };

/** Render saved paths. There is deliberately no advection, random motion or CFD here. */
export default function TankSimulatorScene({ report, view, onUnavailable }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const engine = useRef<Engine | null>(null);
  const latestView = useRef(view);
  useEffect(() => { latestView.current = view; engine.current?.update(view); }, [view]);
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    let renderer: THREE.WebGLRenderer;
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "low-power" }); }
    catch { onUnavailable("3D rendering is unavailable in this browser. The saved 2D layout maps and results remain available below."); return; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.setClearColor(0xeaf6fc, 1);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    const canvas = renderer.domElement;
    canvas.setAttribute("aria-label", "Interactive 3D schematic of the saved tank water plane. Drag or use arrow keys to orbit; Home resets the view. Separate controls replay saved paths.");
    canvas.setAttribute("role", "img");
    canvas.tabIndex = 0;
    element.appendChild(canvas);
    const scene = new THREE.Scene();
    const b = report.geometry.bounds_cm, widthCm = b.x_max_cm - b.x_min_cm, lengthCm = b.y_max_cm - b.y_min_cm;
    const scale = 12 / Math.max(widthCm, lengthCm), width = widthCm * scale, length = lengthCm * scale;
    const centerX = (b.x_min_cm + b.x_max_cm) / 2, centerY = (b.y_min_cm + b.y_max_cm) / 2;
    const vector = (x: number, y: number, height = 0.025) => new THREE.Vector3((x - centerX) * scale, height, -(y - centerY) * scale);
    const camera = new THREE.PerspectiveCamera(38, 1, 0.05, 120);
    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = false;
    controls.enablePan = false;
    controls.minDistance = 8; controls.maxDistance = 36;
    controls.minPolarAngle = 0.015; controls.maxPolarAngle = Math.PI / 2.08;
    controls.target.set(-0.5, 0, 0);
    const geometry: THREE.BufferGeometry[] = [], materials: THREE.Material[] = [], textures: THREE.Texture[] = [];
    const keepGeometry = <T extends THREE.BufferGeometry>(item: T): T => { geometry.push(item); return item; };
    const keepMaterial = <T extends THREE.Material>(item: T): T => { materials.push(item); return item; };
    const material = (color: number, opacity = 1) => keepMaterial(new THREE.MeshBasicMaterial({ color, transparent: opacity < 1, opacity, side: THREE.DoubleSide, depthWrite: opacity === 1 }));
    const lineMaterial = (color: number, opacity = 1) => keepMaterial(new THREE.LineBasicMaterial({ color, transparent: opacity < 1, opacity }));
    function box(parent: THREE.Object3D, x: number, y: number, z: number, sx: number, sy: number, sz: number, color: number, opacity = 1) {
      const mesh = new THREE.Mesh(keepGeometry(new THREE.BoxGeometry(sx, sy, sz)), material(color, opacity));
      mesh.position.set(x, y, z); parent.add(mesh); return mesh;
    }
    function line(parent: THREE.Object3D, points: THREE.Vector3[], color: number, opacity = 1) {
      const item = new THREE.Line(keepGeometry(new THREE.BufferGeometry().setFromPoints(points)), lineMaterial(color, opacity));
      parent.add(item); return item;
    }
    function footprint(parent: THREE.Object3D, polygon: number[][], color: number, height = 0.035, opacity = 0.6) {
      const shape = new THREE.Shape(polygon.map(([x, y]) => new THREE.Vector2((x - centerX) * scale, (y - centerY) * scale)));
      const mesh = new THREE.Mesh(keepGeometry(new THREE.ShapeGeometry(shape)), material(color, opacity));
      mesh.rotation.x = -Math.PI / 2; mesh.position.y = height; parent.add(mesh);
      line(parent, [...polygon, polygon[0]].map(([x, y]) => vector(x, y, height + 0.01)), color);
    }
    let labelCount = 0;
    function label(parent: THREE.Object3D, text: string, position: THREE.Vector3, size = 2) {
      if (++labelCount > 24) return;
      const bitmap = document.createElement("canvas"), context = bitmap.getContext("2d");
      if (!context) return;
      context.font = "500 26px system-ui, sans-serif";
      bitmap.width = Math.min(640, Math.ceil(context.measureText(text).width) + 32); bitmap.height = 62;
      context.fillStyle = "rgba(248,253,255,0.95)"; context.fillRect(0, 0, bitmap.width, bitmap.height);
      context.strokeStyle = "#abcbdc"; context.lineWidth = 2; context.strokeRect(1, 1, bitmap.width - 2, bitmap.height - 2);
      context.fillStyle = "#284e66"; context.font = "500 26px system-ui, sans-serif"; context.textAlign = "center"; context.textBaseline = "middle"; context.fillText(text, bitmap.width / 2, 31, bitmap.width - 20);
      const texture = new THREE.CanvasTexture(bitmap); texture.colorSpace = THREE.SRGBColorSpace; texture.generateMipmaps = false; texture.minFilter = THREE.LinearFilter; textures.push(texture);
      const sprite = new THREE.Sprite(keepMaterial(new THREE.SpriteMaterial({ map: texture, depthTest: false, depthWrite: false })));
      sprite.position.copy(position); sprite.scale.set(size, size * bitmap.height / bitmap.width, 1); sprite.renderOrder = 10; parent.add(sprite);
    }
    // Wall height is an explicitly schematic display extrusion, not measured depth.
    const walls = new THREE.Group(); scene.add(walls);
    box(walls, 0, -0.95, 0, width + 0.1, 0.06, length + 0.1, 0xc3dcea, 0.45);
    box(walls, -width / 2, -0.45, 0, 0.05, 1, length, 0x9cc9de, 0.25);
    box(walls, width / 2, -0.45, 0, 0.05, 1, length, 0x9cc9de, 0.25);
    box(walls, 0, -0.45, length / 2, width, 1, 0.05, 0x9cc9de, 0.25);
    box(walls, 0, -0.45, -length / 2, width, 1, 0.05, 0x9cc9de, 0.25);
    const water = new THREE.Mesh(keepGeometry(new THREE.PlaneGeometry(width, length)), material(0xb9dff0, 0.55));
    water.rotation.x = -Math.PI / 2; scene.add(water);
    const grid = new THREE.Group(); scene.add(grid);
    const rawStep = Math.max(widthCm, lengthCm) / 8, magnitude = 10 ** Math.floor(Math.log10(rawStep));
    const step = ([1, 2, 5, 10].find(value => value * magnitude >= rawStep) ?? 10) * magnitude;
    for (let x = Math.ceil(b.x_min_cm / step) * step; x <= b.x_max_cm; x += step) line(grid, [vector(x, b.y_min_cm), vector(x, b.y_max_cm)], 0x7fa9be, 0.35);
    for (let y = Math.ceil(b.y_min_cm / step) * step; y <= b.y_max_cm; y += step) line(grid, [vector(b.x_min_cm, y), vector(b.x_max_cm, y)], 0x7fa9be, 0.35);
    const sources = new THREE.Group(); scene.add(sources);
    report.geometry.sources.forEach((source, index) => footprint(sources, source.polygon_cm, [0x5498b9, 0x779ebc, 0x9fa9c8][index % 3]));
    footprint(scene, report.geometry.protected_zone_cm, 0xe3ad7f, 0.045, 0.55);
    const waterLabels = new THREE.Group(), coordinateLabels = new THREE.Group(); scene.add(waterLabels, coordinateLabels);
    for (const item of tankWaterLabels(report)) {
      const anchor = vector(item.x_cm, item.y_cm, item.kind === "coordinate" ? 0.08 : 0.45);
      if (item.kind === "coordinate") { if (item.text.startsWith("x ")) anchor.z += 0.43; else anchor.x -= 0.7; }
      if (item.kind === "source") anchor.z += 0.5;
      const labelText = item.kind === "source" ? item.text.replace(/^Source /, "") : item.text;
      label(item.kind === "coordinate" ? coordinateLabels : waterLabels, labelText, anchor, item.kind === "coordinate" ? 1.5 : item.kind === "source" ? Math.min(1.6, Math.max(0.65, labelText.length * 0.2)) : 2.2);
    }
    // This short coral proxy marks the saved protected footprint, not coral geometry.
    const zone = report.geometry.protected_zone_cm;
    const proxyX = zone.reduce((sum, point) => sum + point[0], 0) / zone.length;
    const proxyY = zone.reduce((sum, point) => sum + point[1], 0) / zone.length;
    const coral = new THREE.Group(); coral.position.copy(vector(proxyX, proxyY, 0.06)); scene.add(coral);
    const branchMaterial = material(0xd39d82);
    for (const [x, y, z] of [[0, 0.45, 0], [-0.18, 0.28, 0], [0.18, 0.33, 0.08]]) {
      const branch = new THREE.Mesh(keepGeometry(new THREE.CylinderGeometry(0.025, 0.04, y, 6)), branchMaterial);
      branch.position.set(x, y / 2, z); branch.rotation.z = x * 1.8; coral.add(branch);
    }
    const collectors: Record<TankLayout, THREE.Group> = { baseline: new THREE.Group(), intervention: new THREE.Group() };
    for (const side of report.geometry.layouts) {
      scene.add(collectors[side.id]);
      for (const trap of side.traps) {
        footprint(collectors[side.id], trap.polygon_cm, 0x479d92, 0.06, 0.5);
        const closed = [...trap.polygon_cm, trap.polygon_cm[0]];
        line(collectors[side.id], closed.map(([x, y]) => vector(x, y, 0.48)), 0x387a75);
        for (let i = 0; i < closed.length - 1; i++) {
          const a = closed[i], c = closed[i + 1];
          for (let j = 0; j <= 8; j++) { const fraction = j / 8, x = a[0] + (c[0] - a[0]) * fraction, y = a[1] + (c[1] - a[1]) * fraction; line(collectors[side.id], [vector(x, y, 0.06), vector(x, y, 0.48)], 0x639e95, 0.6); }
        }
      }
    }
    const paths = new Map<string, { line: THREE.Line; token: THREE.Mesh }>();
    const tokenGeometry = keepGeometry(new THREE.SphereGeometry(0.07, 10, 7));
    const tokenMaterial = material(0xc65c50);
    for (const path of report.simulation.paths) {
      if (!path.points.length) continue;
      const item = line(scene, path.points.map(point => vector(point.x_cm, point.y_cm, 0.075)), path.layout === "baseline" ? 0x5c83b3 : 0x168879, 0.55);
      const token = new THREE.Mesh(tokenGeometry, tokenMaterial); scene.add(token);
      paths.set(`${path.layout}:${path.source_id}:${path.particle_index}`, { line: item, token });
    }
    const flow: Record<TankLayout, THREE.Group> = { baseline: new THREE.Group(), intervention: new THREE.Group() };
    for (const row of report.vectors) {
      scene.add(flow[row.layout]);
      for (const node of supportedTankVectors(report, row.layout)) {
        const speed = Math.hypot(node.vx_cm_s, node.vy_cm_s);
        if (!speed) continue;
        const direction = new THREE.Vector3(node.vx_cm_s, 0, -node.vy_cm_s).normalize();
        // Glyph length is normalized for readability; the numerical value remains in cm/s.
        const arrow = new THREE.ArrowHelper(direction, vector(node.x_cm, node.y_cm, 0.12), 0.4, 0x366b8a, 0.12, 0.065);
        scene.add(arrow); flow[row.layout].add(arrow);
        geometry.push(arrow.line.geometry, arrow.cone.geometry);
        materials.push(...(Array.isArray(arrow.line.material) ? arrow.line.material : [arrow.line.material]), ...(Array.isArray(arrow.cone.material) ? arrow.cone.material : [arrow.cone.material]));
      }
    }
    const actualLines = new Map<string, THREE.Group>();
    for (const recording of report.actual.recordings) {
      const group = new THREE.Group(); scene.add(group); actualLines.set(recording.recording_id, group);
      for (const segment of recording.segments) {
        line(group, segment.points.map(point => vector(point.x_cm, point.y_cm, 0.095)), 0x9a5d35, 0.9);
        const dots = new THREE.Points(keepGeometry(new THREE.BufferGeometry().setFromPoints(segment.points.map(point => vector(point.x_cm, point.y_cm, 0.1)))), keepMaterial(new THREE.PointsMaterial({ color: 0x9a5d35, size: 0.055 })));
        group.add(dots);
      }
    }
    const actualToken = new THREE.Mesh(tokenGeometry, material(0x9a5d35)); scene.add(actualToken);
    // Equipment sits outside the measured XY footprint. Its scale and placement
    // are diagrammatic: no hardware dimensions, tubing coordinates or actuation.
    const hardware = new THREE.Group(); scene.add(hardware);
    const hx = -width / 2 - 1.8;
    box(hardware, hx, -0.15, 0, 0.65, 0.55, 0.7, 0x45677a);
    box(hardware, hx, 1.7, -length / 2, 0.09, 3.5, 0.09, 0x6f8a9a);
    box(hardware, hx + 1.05, 3.4, -length / 2, 2.2, 0.08, 0.1, 0x6f8a9a);
    box(hardware, hx + 2.1, 3.25, -length / 2, 0.75, 0.3, 0.25, 0x365767);
    const lens = new THREE.Mesh(keepGeometry(new THREE.CylinderGeometry(0.085, 0.085, 0.13, 12)), material(0x182f41)); lens.position.set(hx + 2.1, 3.07, -length / 2); hardware.add(lens);
    const tubeCurve = new THREE.CatmullRomCurve3([new THREE.Vector3(hx - 0.25, 0.15, 0), new THREE.Vector3(hx - 0.65, 0.9, 0.2), new THREE.Vector3(hx - 0.3, 1.15, 0.8), new THREE.Vector3(hx + 0.4, 0.55, 0.9)]);
    hardware.add(new THREE.Mesh(keepGeometry(new THREE.TubeGeometry(tubeCurve, 20, 0.055, 6, false)), material(0x8daebb, 0.8)));
    const equipmentLabels = new THREE.Group(); hardware.add(equipmentLabels);
    label(equipmentLabels, "USB webcam · dry", new THREE.Vector3(hx + 2.1, 3.9, -length / 2), 3.1);
    label(equipmentLabels, "Pump + tubing · schematic", new THREE.Vector3(hx - 0.15, 1.4, 1.1), 3.4);
    let active = true, disposed = false;
    const render = () => { if (!disposed && active) renderer.render(scene, camera); };
    const reset = (state: TankSceneView) => {
      if (state.camera === "overhead") camera.position.set(0, 20, 0.02);
      else camera.position.set(14, 13, 17);
      controls.target.set(state.hardware ? -0.8 : 0, 0, 0); controls.update(); render();
    };
    function update(state: TankSceneView) {
      active = state.active;
      grid.visible = state.grid; hardware.visible = state.hardware;
      waterLabels.visible = state.labels; coordinateLabels.visible = state.labels && state.grid; equipmentLabels.visible = state.labels;
      for (const side of ["baseline", "intervention"] as const) { collectors[side].visible = side === state.layout; flow[side].visible = state.flow && side === state.layout; }
      const selected = new Set(visibleTankPaths(report, state.layout, state.source));
      for (const path of report.simulation.paths) {
        const item = paths.get(`${path.layout}:${path.source_id}:${path.particle_index}`);
        if (!item) continue;
        const show = selected.has(path) && state.clock === "model";
        item.line.visible = state.paths && show;
        const point = show ? tankPositionAt(path.points, state.time, path.display_stop_s ?? 0) : null;
        item.token.visible = point !== null;
        if (point) item.token.position.copy(vector(point.x_cm, point.y_cm, 0.13));
      }
      const recording = report.actual.recordings.find(row => row.recording_id === state.recordingId && row.layout === state.layout && (state.source === "all" || row.source_id === state.source));
      for (const [id, lines] of actualLines) lines.visible = state.clock === "capture" && state.paths && recording?.recording_id === id;
      const actual = state.clock === "capture" && recording ? recordedTankPositionAt(recording, state.time) : null;
      actualToken.visible = actual !== null;
      if (actual) actualToken.position.copy(vector(actual.x_cm, actual.y_cm, 0.14));
      render();
    }
    const resize = () => {
      if (disposed) return;
      const rect = element.getBoundingClientRect(), w = Math.max(1, rect.width), h = Math.max(1, rect.height);
      renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); render();
    };
    const observer = new ResizeObserver(resize); observer.observe(element);
    controls.addEventListener("change", render);
    const keyboard = (event: KeyboardEvent) => {
      if (event.key === "Home") { event.preventDefault(); reset(latestView.current); return; }
      if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return;
      event.preventDefault();
      const offset = camera.position.clone().sub(controls.target), spherical = new THREE.Spherical().setFromVector3(offset);
      if (event.key === "ArrowLeft") spherical.theta -= Math.PI / 12;
      if (event.key === "ArrowRight") spherical.theta += Math.PI / 12;
      if (event.key === "ArrowUp") spherical.phi -= Math.PI / 18;
      if (event.key === "ArrowDown") spherical.phi += Math.PI / 18;
      spherical.phi = Math.max(controls.minPolarAngle, Math.min(controls.maxPolarAngle, spherical.phi));
      camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(spherical)); controls.update(); render();
    };
    canvas.addEventListener("keydown", keyboard);
    const lost = (event: Event) => { event.preventDefault(); onUnavailable("The browser released its 3D graphics context. The saved 2D layouts and evidence remain available below; reopen 3D explicitly to retry."); };
    canvas.addEventListener("webglcontextlost", lost);
    let lastCamera = `${latestView.current.camera}:${latestView.current.cameraRevision}`;
    const api: Engine = {
      update(state) { const key = `${state.camera}:${state.cameraRevision}`; if (key !== lastCamera) { lastCamera = key; reset(state); } update(state); },
      reset,
      dispose() {
        disposed = true; observer.disconnect(); controls.removeEventListener("change", render); controls.dispose(); canvas.removeEventListener("webglcontextlost", lost); canvas.removeEventListener("keydown", keyboard);
        for (const item of new Set(geometry)) item.dispose(); for (const item of new Set(materials)) item.dispose(); for (const item of textures) item.dispose();
        renderer.renderLists.dispose(); renderer.dispose(); renderer.forceContextLoss(); canvas.remove(); scene.clear();
      },
    };
    engine.current = api; reset(latestView.current); update(latestView.current); resize();
    return () => { engine.current = null; api.dispose(); };
  }, [report, onUnavailable]);
  return <div ref={host} className={styles.canvas} />;
}
