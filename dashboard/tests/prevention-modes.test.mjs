import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url);

// Exercise the actual environment-switch component and its click handlers.
// A tiny state adapter lets Node inspect successive renders; the separately
// tested ocean child is a presentation sentinel here. This is a controller
// regression, not a claim of browser, provider or physical experiment testing.
function controller() {
  let mode;
  const compiled = ts.transpileModule(readFileSync(resolve("app/components/prevention-modes.tsx"), "utf8"), {
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
  }).outputText;
  const mod = { exports: {} };
  new Function("require", "module", "exports", compiled)(name => {
    if (name === "react") return { ...React, useState: initial => {
      mode ??= initial;
      return [mode, next => { mode = typeof next === "function" ? next(mode) : next; }];
    } };
    if (name === "./ocean-prevention") return { OceanPrevention: ({ api }) => React.createElement("section", { "data-prevention-view": "ocean", "data-api": api }, "Dynamic current comparison") };
    return require(name);
  }, mod, mod.exports);
  return mod.exports.PreventionModes;
}
function descendants(element) {
  if (!React.isValidElement(element)) return [];
  return [element, ...React.Children.toArray(element.props.children).flatMap(descendants)];
}

test("Prevention starts with changing-current ocean mode and switches explicitly to the independent tank ledger", () => {
  const PreventionModes = controller();
  const tank = React.createElement("section", { "data-prevention-view": "tank" }, "Tank experiment and independent trial ledger");
  const props = { api: "https://synthetic-controller.test", children: tank };
  const render = () => PreventionModes(props);
  let tree = render(), html = renderToStaticMarkup(tree);
  let buttons = descendants(tree).filter(element => element.type === "button");
  assert.deepEqual(buttons.map(button => button.props["aria-pressed"]), [true, false]);
  assert.ok(buttons.every(button => button.props.type === "button"));
  assert.match(html, /aria-label="Prevention environment"/);
  assert.match(html, /data-prevention-view="ocean"/);
  assert.match(html, /data-api="https:\/\/synthetic-controller\.test"/);
  assert.match(html, /same changing currents/);
  assert.doesNotMatch(html, /data-prevention-view="tank"/);

  buttons[1].props.onClick();
  tree = render(); html = renderToStaticMarkup(tree);
  buttons = descendants(tree).filter(element => element.type === "button");
  assert.deepEqual(buttons.map(button => button.props["aria-pressed"]), [false, true]);
  assert.match(html, /data-prevention-view="tank"/);
  assert.doesNotMatch(html, /data-prevention-view="ocean"/);
  assert.equal(tree.props.children[1], tank, "switching preserves the actual independent tank child");

  buttons[0].props.onClick();
  tree = render(); html = renderToStaticMarkup(tree);
  assert.match(html, /data-prevention-view="ocean"/);
  assert.doesNotMatch(html, /data-prevention-view="tank"/);
  const blocked = descendants(PreventionModes({ ...props, blocked: true })).filter(element => element.type === "button");
  assert.equal(blocked.length, 2);
  assert.ok(blocked.every(button => button.props.disabled === true), "an in-progress tank operation prevents environment switching");
});
