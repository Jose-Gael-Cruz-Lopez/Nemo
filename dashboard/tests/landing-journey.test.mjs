import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve, dirname } from "node:path";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url), loaded = new Map();
function component(path) {
  const file = resolve(path);
  if (loaded.has(file)) return loaded.get(file).exports;
  const mod = { exports: {} }; loaded.set(file, mod);
  const compiled = ts.transpileModule(readFileSync(file, "utf8"), { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
  new Function("require", "module", "exports", compiled)(name => {
    if (name.endsWith(".module.css")) return { __esModule: true, default: new Proxy({}, { get: (_, key) => String(key) }) };
    if (name === "next/link") return { __esModule: true, default: ({ children, ...props }) => React.createElement("a", props, children) };
    if (name === "next/navigation") return { useRouter: () => ({ replace() { assert.fail("Server rendering must not navigate"); } }) };
    if (name.startsWith(".")) {
      const base = resolve(dirname(file), name);
      const dependency = [base, `${base}.tsx`, `${base}.ts`].find(existsSync);
      if (dependency) return component(dependency);
    }
    return require(name);
  }, mod, mod.exports);
  return mod.exports;
}
const { JOURNEY_CHAPTERS, JOURNEY_ROUTE_PATH, JOURNEY_ROUTE_STOPS, JOURNEY_ROUTE_DOTS, chapterDepthFrame, createJourneyEntryAdvance, createJourneyHashRestore, journeyHashTarget, legacyWorkspaceDestination, journeyProgress, motionAllowed } = component("app/landing-journey-state.ts");
const { default: Landing } = component("app/page.tsx");


test("five distinct chapters link to real software routes and preserve evidence boundaries", () => {
  assert.deepEqual(JOURNEY_CHAPTERS.map(chapter => chapter.id), ["welcome", "observe", "trace", "prevent", "verify"]);
  for (const chapter of JOURNEY_CHAPTERS) {
    assert.ok(chapter.detail.length > 40);
    assert.ok(chapter.detail.split(/\s+/).length <= 20);
    assert.ok(!("eyebrow" in chapter));
    assert.match(chapter.href, /^\/(demo|workspace)(#(investigations|prevention|data))?$/);
    assert.ok(chapter.secondaryHref.startsWith("#journey-") || chapter.secondaryHref === "/workspace");
  }
  assert.deepEqual(JOURNEY_CHAPTERS.map(chapter => chapter.heading), ["Nemo", "Observe the drift.", "Find possible sources.", "Compare interception layouts.", "Check the evidence."]);
  assert.match(JOURNEY_CHAPTERS[2].evidence, /does not identify a polluter/);
  assert.match(JOURNEY_CHAPTERS[3].evidence, /separate; neither establishes measured reef protection/);
  assert.match(JOURNEY_CHAPTERS[4].evidence, /do not validate plastic motion/);
});

test("legacy observation links preserve view and safely encoded bounded case identity", () => {
  for (const view of ["overview", "investigations", "prevention", "camera", "data", "settings"]) {
    assert.equal(legacyWorkspaceDestination(`#${view}`), `/workspace#${view}`);
    assert.equal(legacyWorkspaceDestination(`#${view}?case=case-1%26x%3D2`), `/workspace#${view}?case=case-1%26x%3D2`);
  }
  assert.equal(legacyWorkspaceDestination(`#data?case=${"a".repeat(201)}`), "/workspace#data");
  assert.equal(legacyWorkspaceDestination("#data?unrelated=ignored"), "/workspace#data");
  for (const hash of ["", "#journey-welcome", "#journey-trace", "#other", "#https://example.com"]) assert.equal(legacyWorkspaceDestination(hash), null);
});

test("journey progress uses actual available scroll extent, clamps overscroll and rejects invalid dimensions", () => {
  assert.equal(journeyProgress(0, 5000, 1000), 0);
  assert.equal(journeyProgress(2000, 5000, 1000), 50);
  assert.equal(journeyProgress(4000, 5000, 1000), 100);
  assert.equal(journeyProgress(4100, 5000, 1000), 100);
  assert.equal(journeyProgress(-20, 5000, 1000), 0);
  for (const dimensions of [[0, 0, 0], [20, 900, 1000], [NaN, 5000, 1000], [0, Infinity, 1]]) assert.equal(journeyProgress(...dimensions), 0);
});

test("reduced motion or a hidden tab each independently prevents visual motion", () => {
  for (const reducedMotion of [false, true]) for (const hidden of [false, true]) {
    assert.equal(motionAllowed({ reducedMotion, hidden }), !reducedMotion && !hidden);
  }
});


test("rendered entry stays usable and truthful before client effects or media load", () => {
  const html = renderToStaticMarkup(React.createElement(Landing));
  assert.match(html, /data-motion="paused"/);
  assert.equal((html.match(/data-journey-chapter=/g) ?? []).length, 5);
  assert.equal((html.match(/<h1\b/g) ?? []).length, 1);
  assert.equal((html.match(/<h2\b/g) ?? []).length, 4);
  assert.match(html, /Start journey/);
  assert.match(html, /<h2[^>]+tabindex="-1"[^>]+id="journey-title-observe"/);
  assert.match(html, /Illustrative Earth with Natural Earth coastlines/);
  assert.equal((html.match(/<button\b/g) ?? []).length, 1);
  assert.doesNotMatch(html, /Pause motion|Resume motion|Reduced motion|OBSERVE\. TRACE\. PREVENT\.|EXPECTED IS ONLY HALF THE STORY|BEGIN WITH WHAT YOU CAN SEE|Honest limits|Every drift/);
  assert.match(html, /<h1[^>]*><strong>Nemo<\/strong><\/h1>/);
  assert.doesNotMatch(html, /narration|captions|Listen|Without voice|With voice|Mute narration|type="radio"|<audio/i);
  assert.match(html, /href="\/workspace"[^>]*>Skip journey/);
  assert.match(html, /href="\/login"/); assert.match(html, /href="\/workspace#data"/);
  assert.match(html, /role="progressbar"[^>]+aria-valuenow="0"/);
  assert.doesNotMatch(html, /Scroll to explore|Illustrative ocean · synthetic software demo · physical validation pending/);
  assert.match(html, /poster="\/nemo-ocean-depth-poster\.jpg"/);
  assert.match(html, /preload="none"/); assert.doesNotMatch(html, /autoPlay|autoplay/);
  assert.doesNotMatch(html, /GPS|TEMPERATURE|DEPTH:|LIVE CURRENT|100% accuracy/i);
  for (const chapter of JOURNEY_CHAPTERS) {
    assert.match(html, new RegExp(`id="journey-${chapter.id}"`));
    assert.match(html, new RegExp(`aria-label="Chapter [1-5]: ${chapter.label}"`));
  }
});

test("reference headline fonts are bundled locally at their declared weights", () => {
  const css = readFileSync(resolve("app/landing.module.css"), "utf8");
  for (const [weight, name] of [[400, "Regular"], [500, "Medium"], [700, "Bold"]]) {
    const filename = `Rajdhani-${name}.ttf`;
    const font = readFileSync(resolve("public/fonts/rajdhani", filename));
    assert.equal(font.readUInt32BE(0), 0x00010000, `${filename} must be a real TrueType font`);
    assert.ok(font.length > 10_000);
    assert.match(css, new RegExp(`src:url\\('/fonts/rajdhani/${filename}'\\).*?font-weight:${weight};font-display:swap`));
  }
  assert.match(readFileSync(resolve("public/fonts/rajdhani/OFL.txt"), "utf8"), /SIL OPEN FONT LICENSE/);
  assert.match(css, /\.title\{font-family:"Rajdhani"/);
  assert.match(css, /\.welcomeChapter \.title\{font-weight:700/);
  assert.doesNotMatch(css, /Impact|fonts\.googleapis\.com|fonts\.gstatic\.com/);
});

function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return{promise,resolve,reject}}
function entryHarness(){const finished=deferred(),events=[];let cancels=0,exits=0;const transition=createJourneyEntryAdvance({exit(){exits++;return{finished:finished.promise,cancel(){cancels++}}},advance(motion){events.push(['advance',motion])},running(value){events.push(['running',value])}});return{transition,events,finished,cancels:()=>cancels,exits:()=>exits}}
test('centered chapter is neutral and reduced motion remains readable at any native position',()=>{
 assert.deepEqual(chapterDepthFrame({sectionTop:0,sectionHeight:800,viewportHeight:800,motion:true}),{scale:1,opacity:1,shiftPx:0,visible:true});
 for(const top of [-900,-400,0,400,900]){const f=chapterDepthFrame({sectionTop:top,sectionHeight:800,viewportHeight:800,motion:false});assert.equal(f.scale,1);assert.equal(f.opacity,1);assert.equal(f.shiftPx,0)}
 for(const bad of [NaN,Infinity]){const f=chapterDepthFrame({sectionTop:bad,sectionHeight:800,viewportHeight:800,motion:true});assert.equal(f.scale,1);assert.equal(f.opacity,1);assert.equal(f.shiftPx,0)}
});
test('outgoing text approaches the viewer and fades; incoming text starts farther away',()=>{
 const out=chapterDepthFrame({sectionTop:-400,sectionHeight:800,viewportHeight:800,motion:true});
 assert.equal(out.scale,1.3);assert.ok(Math.abs(out.opacity-.15)<1e-12);assert.equal(out.shiftPx,300);
 const incoming=chapterDepthFrame({sectionTop:400,sectionHeight:800,viewportHeight:800,motion:true});
 assert.equal(incoming.scale,.94);assert.ok(Math.abs(incoming.opacity-.35)<1e-12);assert.equal(incoming.shiftPx,-300);
 const edge=chapterDepthFrame({sectionTop:-800,sectionHeight:1600,viewportHeight:800,motion:true});assert.equal(edge.scale,1.6);assert.equal(edge.opacity,0);
});
test('offscreen chapters are not transformed into view and geometry stays bounded',()=>{
 for(const top of [-800,800,2400]){const f=chapterDepthFrame({sectionTop:top,sectionHeight:800,viewportHeight:800,motion:true});assert.equal(f.visible,false);assert.equal(f.opacity,0);assert.equal(f.shiftPx,0)}
 for(let top=-799;top<800;top+=17){const f=chapterDepthFrame({sectionTop:top,sectionHeight:800,viewportHeight:800,motion:true});assert.ok(f.scale>=.88&&f.scale<=1.6);assert.ok(f.opacity>=0&&f.opacity<=1);assert.ok(Number.isFinite(f.shiftPx))}
});
test('Start waits for real animation completion, then performs one native handoff',async()=>{
 const h=entryHarness(),pending=h.transition.start(true);assert.deepEqual(h.events,[['running',true]]);h.finished.resolve();assert.equal(await pending,true);assert.deepEqual(h.events,[['running',true],['running',false],['advance',true]]);assert.equal(h.exits(),1);
});
test('reduced motion advances immediately without constructing an animation',async()=>{
 const h=entryHarness();assert.equal(await h.transition.start(false),true);assert.equal(h.exits(),0);assert.deepEqual(h.events,[['running',true],['running',false],['advance',false]]);
});
test('repeated clicks do not queue duplicate entry transitions',async()=>{
 const h=entryHarness(),first=h.transition.start(true);assert.equal(await h.transition.start(true),false);assert.equal(h.exits(),1);h.finished.resolve();assert.equal(await first,true);assert.equal(h.events.filter(e=>e[0]==='advance').length,1);
});
test('cancellation prevents an old completion from moving the page or focus',async()=>{
 const h=entryHarness(),pending=h.transition.start(true);h.transition.cancel();h.finished.resolve();assert.equal(await pending,false);assert.equal(h.events.some(e=>e[0]==='advance'),false);assert.equal(h.cancels(),1);
});
test("a rejected cancelled animation cannot release or prematurely advance a restarted entry", async () => {
  const completions = [deferred(), deferred()], cancelled = [], advances = [];
  let created = 0;
  const transition = createJourneyEntryAdvance({
    exit() {
      const index = created++;
      return { finished: completions[index].promise, cancel() {
        cancelled.push(index);
        completions[index].reject(new Error("Animation cancelled"));
      } };
    },
    advance(motion) { advances.push(motion); }, running() {},
  });
  const first = transition.start(true);
  transition.cancel();
  // Restart synchronously before the first animation's rejection catch resumes.
  const second = transition.start(true);
  let secondFinished = false;
  void second.then(() => { secondFinished = true; });
  assert.equal(await first, false);
  await Promise.resolve();
  assert.equal(secondFinished, false);
  assert.deepEqual(cancelled, [0]);
  assert.deepEqual(advances, []);
  completions[1].resolve();
  assert.equal(await second, true);
  assert.deepEqual(advances, [true]);
});
test('disposal cancels animation without sending state updates or accepting later starts',async()=>{
 const h=entryHarness(),pending=h.transition.start(true),count=h.events.length;h.transition.dispose();h.finished.resolve();assert.equal(await pending,false);assert.equal(h.events.length,count);assert.equal(await h.transition.start(false),false);assert.equal(h.cancels(),1);
});
test('failed or absent animation falls back to immediate native entry',async()=>{
 const events=[];for(const exit of [()=>null,()=>{throw Error('unsupported')}]){const t=createJourneyEntryAdvance({exit,advance:m=>events.push(m),running(){}});assert.equal(await t.start(true),true)}assert.deepEqual(events,[false,false]);
 const h=entryHarness(),pending=h.transition.start(true);h.finished.reject(Error('animation rejected'));assert.equal(await pending,true);assert.deepEqual(h.events.at(-1),['advance',false]);
});
test('release removes only the completed visual effect without a second handoff',async()=>{
 const h=entryHarness(),pending=h.transition.start(true);h.finished.resolve();await pending;const count=h.events.length;h.transition.release();h.transition.release();assert.equal(h.cancels(),1);assert.equal(h.events.length,count);
});


test("journey route preserves five real chapter anchors with decorative intermediate dots", () => {
  assert.equal(JOURNEY_ROUTE_STOPS.length, JOURNEY_CHAPTERS.length);
  assert.equal(JOURNEY_ROUTE_DOTS.length, 16);
  assert.match(JOURNEY_ROUTE_PATH, /^M30 20C/);
  const html = renderToStaticMarkup(React.createElement(Landing));
  JOURNEY_CHAPTERS.forEach(chapter => assert.match(html, new RegExp(`href="#journey-${chapter.id}"`)));
  for (const point of [...JOURNEY_ROUTE_STOPS, ...JOURNEY_ROUTE_DOTS]) {
    assert.ok(point.x >= 0 && point.x <= 43); assert.ok(point.y >= 0 && point.y <= 500);
  }
  assert.ok(JOURNEY_ROUTE_STOPS.every((point,index) => index === 0 || point.y > JOURNEY_ROUTE_STOPS[index - 1].y));
});

function hashRestoreHarness(initialHash, initiallyHidden = false) {
  let hash = initialHash, hidden = initiallyHidden, next = 0;
  const pending = new Map(), all = new Map(), cancelled = [], calls = [];
  const viewport = { scrollTop: 0, clientHeight: 748, scrollHeight: 3740 };
  const sections = new Map(JOURNEY_CHAPTERS.map((chapter, index) => [`journey-${chapter.id}`, {
    scrollIntoView(options) { calls.push({ id: chapter.id, options }); viewport.scrollTop = index * viewport.clientHeight; },
    focus() { assert.fail("URL restoration must not move keyboard focus"); },
  }]));
  const restore = createJourneyHashRestore({
    readHash: () => hash, hidden: () => hidden,
    findSection: id => sections.get(id) ?? null,
    requestFrame(callback) { const id = next++; pending.set(id, callback); all.set(id, callback); return id; },
    cancelFrame(id) { cancelled.push(id); pending.delete(id); },
  });
  return { restore, viewport, calls, pending, all, cancelled,
    hash(value) { hash = value; },
    hidden(value) { hidden = value; restore.visibilityChanged(); },
    frame() { const callbacks = [...pending.values()]; pending.clear(); callbacks.forEach(callback => callback()); },
  };
}

test("direct chapter URLs restore their real native scroll position after layout without setting fake progress or focus", () => {
  JOURNEY_CHAPTERS.forEach((chapter, index) => {
    const h = hashRestoreHarness(`#journey-${chapter.id}`);
    assert.equal(journeyHashTarget(`#journey-${chapter.id}`), `journey-${chapter.id}`);
    h.restore.resume(); assert.equal(h.pending.size, 1); assert.equal(h.calls.length, 0);
    h.frame(); assert.equal(h.calls.length, 0); assert.equal(h.pending.size, 1);
    h.frame();
    assert.deepEqual(h.calls, [{ id: chapter.id, options: { behavior: "instant", block: "start" } }]);
    assert.equal(h.viewport.scrollTop, index * 748);
    assert.equal(journeyProgress(h.viewport.scrollTop, h.viewport.scrollHeight, h.viewport.clientHeight), index * 25);
    h.restore.resume(); h.frame(); assert.equal(h.calls.length, 1); assert.equal(h.pending.size, 0);
  });
});

test("initial restoration ignores unknown or legacy hashes and never competes with newer native navigation", () => {
  for (const hash of ["", "#journey-other", "#journey-prevent?case=x", "#journey-prevent/extra", "#prevention?case=case-1", "#data", "#JOURNEY-prevent"]) {
    assert.equal(journeyHashTarget(hash), null);
    const h = hashRestoreHarness(hash); h.restore.resume(); assert.equal(h.pending.size, 0);
  }
  const h = hashRestoreHarness("#journey-prevent"); h.restore.resume(); h.frame(); h.hash("#journey-trace"); h.frame();
  assert.equal(h.calls.length, 0); assert.equal(h.pending.size, 0);
});

test("hidden-page restore waits for visibility and cannot revive cancelled frame chains", () => {
  const h = hashRestoreHarness("#journey-prevent", true);
  h.restore.resume(); assert.equal(h.pending.size, 0);
  h.hidden(false); assert.ok(h.pending.has(0)); const stale = h.all.get(0);
  h.hidden(true); assert.deepEqual(h.cancelled, [0]); h.hidden(false); assert.ok(h.pending.has(1));
  stale(); assert.equal(h.calls.length, 0); assert.equal(h.pending.size, 1);
  h.frame(); h.frame(); assert.equal(h.calls[0].id, "prevent"); assert.equal(h.viewport.scrollTop, 2244);
  h.hidden(true); h.hidden(false); assert.equal(h.pending.size, 0); assert.equal(h.calls.length, 1);
});

test("unmount cancels the exact pending initial restore and ignores an already queued callback", () => {
  const h = hashRestoreHarness("#journey-prevent"); h.restore.resume(); const stale = h.all.get(0);
  h.restore.dispose(); stale(); h.restore.resume();
  assert.deepEqual(h.cancelled, [0]); assert.equal(h.pending.size, 0); assert.equal(h.calls.length, 0);
});
