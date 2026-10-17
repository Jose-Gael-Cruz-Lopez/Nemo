import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

// NODE-ONLY regressions for accessibility defects found during the browser acceptance
// run (docs/software-demo-acceptance.md). They render markup and read CSS; they are not
// a substitute for the recorded browser checks.
const require = createRequire(import.meta.url);
const file = resolve("app/components/demo-guide.tsx");
const compiled = ts.transpileModule(readFileSync(file, "utf8"), { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
const mod = { exports: {} };
new Function("require", "module", "exports", compiled)(name => {
  if (name.endsWith(".module.css")) return { __esModule: true, default: new Proxy({}, { get: (_, key) => String(key) }) };
  if (name === "./icons") return { Icon: () => React.createElement("svg", { "aria-hidden": "true" }) };
  return require(name);
}, mod, mod.exports);
const { DemoGuide } = mod.exports;
const noAction = () => assert.fail("Rendering must not execute an action");
const html = renderToStaticMarkup(React.createElement(DemoGuide, { onTrace: noAction, onPrevention: noAction, onChalk: noAction }));
const buttons = [...html.matchAll(/<button\b([^>]*)>(.*?)<\/button>/g)];

test("guide actions are plain buttons, never implicit form submits", () => {
  assert.deepEqual(buttons.map(([, attrs]) => /\btype="button"/.test(attrs)), [true, true, true]);
});

test("each guide action keeps its visible name and is described by its own step text", () => {
  const names = buttons.map(([, , inner]) => inner.replace(/<[^>]+>/g, "").trim());
  assert.deepEqual(names, ["Open source trace", "Compare layouts", "Ask Chalk"]);
  for (const [, attrs] of buttons) {
    const id = attrs.match(/aria-describedby="([^"]+)"/)?.[1];
    assert.ok(id, "button has aria-describedby");
    const description = html.match(new RegExp(`<p id="${id}">([^<]+)</p>`))?.[1];
    assert.ok(description && description.length > 20, `description ${id} exists and is meaningful`);
  }
  const ids = buttons.map(([, attrs]) => attrs.match(/aria-describedby="([^"]+)"/)[1]);
  assert.equal(new Set(ids).size, 3, "descriptions are not shared between steps");
});

test("decorative step numbers are hidden from assistive technology", () => {
  const indexes = [...html.matchAll(/<span class="index"([^>]*)>(0\d)<\/span>/g)];
  assert.deepEqual(indexes.map(([, , n]) => n), ["01", "02", "03"]);
  for (const [, attrs] of indexes) assert.match(attrs, /aria-hidden="true"/);
});

test("guide focus ring keeps at least 3:1 contrast against the card background", () => {
  const css = readFileSync(resolve("app/components/demo-guide.module.css"), "utf8");
  const color = css.match(/\.step button:focus-visible\s*\{[^}]*outline:\s*\d+px solid (#[0-9a-f]{6})/i)?.[1];
  assert.ok(color, "guide declares its own focus-visible outline colour");
  const rgb = hex => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16));
  const luminance = channels => channels.map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; })
    .reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0);
  const ratio = (a, b) => { const [x, y] = [luminance(a), luminance(b)].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };
  // Card background measured in the browser: rgb(232, 243, 252). The shared ring #b4d5e8 measures 1.37:1.
  assert.ok(ratio(rgb(color), [232, 243, 252]) >= 3, `${color} is at least 3:1 on the card`);
  assert.ok(ratio(rgb("#b4d5e8"), [232, 243, 252]) < 3, "documents why the shared ring was overridden");
});
