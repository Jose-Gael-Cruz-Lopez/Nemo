/** Reproduce the local adapter from the unchanged, user-supplied Framer module.
 * The globe's coastline decoder, equal-area scatter, geometry and shaders stay
 * source-identical after formatting. Only host/editor/lifecycle integration is
 * changed. Run from dashboard: node vendor/atomic-globe/adapt.mjs
 */
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import ts from "typescript";

export function adaptAtomicGlobe(original) {
  const file = ts.createSourceFile("AtomicGlobe.js", original, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
  let code = ts.createPrinter().printFile(file);
  code = code.slice(0, code.indexOf("const THEMES ="));
  function replaceOnce(before, after) {
    if (!code.includes(before) || code.indexOf(before) !== code.lastIndexOf(before))
      throw new Error(`AtomicGlobe adapter source changed at: ${before.slice(0, 70)}`);
    code = code.replace(before, after);
  }
  replaceOnce('import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";\n', "");
  replaceOnce('import { useEffect, useMemo, useRef, useState } from "react";\n', "");
  replaceOnce('import { addPropertyControls, ControlType, RenderTarget, useIsStaticRenderer } from "framer"; ', "");
  replaceOnce("class GlobeRuntime {", "export class GlobeRuntime {");
  // A single externally owned frame driver handles visibility, reduced motion,
  // a 30fps cap and a virtual clock that excludes time spent hidden or paused.
  replaceOnce('_define_property(this, "tick", () => {\n            this.raf = requestAnimationFrame(this.tick);\n            const editing = RenderTarget.current() === RenderTarget.canvas;\n            if (editing && !this.cfg.editorPlayback)\n                return;\n            if (!this.visible)\n                return;\n            const now = performance.now();',
    '_define_property(this, "tick", now => {\n            if (this.disposed || !Number.isFinite(now)) return;');
  replaceOnce('this.measure();\n        this.renderer = new THREE.WebGLRenderer({ alpha: true, antialias: this.tier > 0, powerPreference: "high-performance" });\n        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, this.tier > 0 ? 2 : 1.5));',
    'try {\n        this.measure();\n        this.renderer = new THREE.WebGLRenderer({ alpha: true, antialias: this.tier > 0, powerPreference: "low-power" });\n        this.renderer.setPixelRatio(Math.max(1, Math.min(window.devicePixelRatio || 1, 1.5)));');
  replaceOnce('this.width = Math.max(1, this.host.clientWidth || 1);\n        this.height = Math.max(1, this.host.clientHeight || 1);',
    'this.width = Math.max(1, Math.min(512, this.host.clientWidth || 1));\n        this.height = Math.max(1, Math.min(512, this.host.clientHeight || 1));');
  const observersStart = code.indexOf("        this.bindPointer();\n");
  const observersEnd = code.indexOf("        this.apply(cfg);", observersStart);
  if (observersStart < 0 || observersEnd < observersStart) throw new Error("AtomicGlobe observer boundaries changed");
  // React's wrapper owns all observers and listeners. Pointer effects are off:
  // this small HUD globe is decorative and must not capture journey scrolling.
  code = code.slice(0, observersStart) + code.slice(observersEnd);
  replaceOnce('        else {\n            this.raf = requestAnimationFrame(this.tick);\n        }\n    }\n} /** Coarse device tier:',
    '        } catch (error) { this.dispose(); throw error; }\n    }\n} /** Coarse device tier:');
  const disposeStart = code.indexOf("    dispose() { if (this.raf !== null)");
  const disposeEnd = code.indexOf("    constructor(host, cfg, still)", disposeStart);
  if (disposeStart < 0 || disposeEnd < disposeStart) throw new Error("AtomicGlobe disposal boundaries changed");
  code = code.slice(0, disposeStart) + `    dispose() {
        if (this.disposed) return;
        this.disposed = true;
        // Construction can fail midway (e.g. unsupported WebGL). Release every
        // allocated resource even when a browser has already lost its context.
        const release = action => { try { action(); } catch { /* Continue cleanup. */ } };
        release(() => this.disposeField());
        release(() => this.disposeRoutes());
        for (const material of [this.fieldMaterial, this.routeMaterial, this.routeLineMaterial])
            release(() => material?.dispose());
        release(() => this.scene?.clear());
        release(() => this.renderer?.forceContextLoss());
        release(() => this.renderer?.dispose());
        release(() => { const canvas = this.renderer?.domElement;
            if (canvas?.parentNode === this.host) this.host.removeChild(canvas); });
    }
` + code.slice(disposeEnd);
  code += '\nexport { scatterLandDots, inflateCoastGrid, inlandDepth };\n';
  code = code.replace(/catch \(err2?\)/g, "catch");
  return '// Adapted from the user-supplied AtomicGlobe module. See vendor/atomic-globe/adapt.mjs and provenance.\n' + code;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const original = readFileSync(new URL("./AtomicGlobe.original.js.txt", import.meta.url), "utf8");
  writeFileSync(new URL("../../app/components/atomic-globe-runtime.mjs", import.meta.url), adaptAtomicGlobe(original));
}
