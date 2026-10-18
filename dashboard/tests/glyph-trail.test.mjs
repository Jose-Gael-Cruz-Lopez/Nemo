import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require=createRequire(import.meta.url),loaded=new Map();
function component(path){
 const file=resolve(path);if(loaded.has(file))return loaded.get(file).exports;
 const mod={exports:{}};loaded.set(file,mod);
 const compiled=ts.transpileModule(readFileSync(file,"utf8"),{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText;
 new Function("require","module","exports",compiled)(name=>{
  if(name.endsWith(".module.css"))return{__esModule:true,default:new Proxy({},{get:(_,key)=>String(key)})};
  if(name.startsWith(".")){const base=resolve(dirname(file),name);return component([base,`${base}.ts`,`${base}.tsx`].find(existsSync));}
  return require(name);
 },mod,mod.exports);return mod.exports;
}
const {GLYPH_BAYER4,GLYPH_BAYER8,GLYPH_MAX_PIXELS,GLYPH_MAX_DIMENSION,GLYPH_MAX_STAMPS,GLYPH_FPS,glyphLayout,glyphMasks,glyphPackedColor,glyphPointer,createGlyphField,glyphCanAnimate,createGlyphFrameDriver}=component("app/components/glyph-trail-state.ts");
const {GlyphTrail}=component("app/components/glyph-trail.tsx");
const original=readFileSync("../docs/research-evidence/glyph-trail-source/Glyph_Trail.js.txt","utf8");
assert.equal(createHash("sha256").update(original).digest("hex"),"09092a4b69ad5321dd6c7f5a54ada9f248f468f2be74eb3164197e5922337a89");
// Evaluate only the reviewed, hash-pinned pure mask definitions. No imports,
// Framer APIs, network, component code, timers or browser globals execute here.
const masksSource=original.slice(original.indexOf("const BAYER4="),original.indexOf("let colorCtx="));
const reference=new Function(`${masksSource}\nreturn {BAYER4,BAYER8,INK_SETS,TRAIL_SETS,buildMasks};`)();

test("captured Framer entry resolves to the actual attributed immutable source",()=>{
 const receipt=JSON.parse(readFileSync("../docs/research-evidence/glyph-trail-source/provenance.json","utf8"));
 assert.equal(receipt.files["Glyph_Trail.js.txt"].bytes,15078);
 assert.equal(receipt.files["Glyph_Trail.js.txt"].sha256,createHash("sha256").update(original).digest("hex"));
 assert.equal(receipt.credited_creator.name,"Justyna");
 assert.match(original,/Made by \[Justyna\]\(https:\/\/justbuilt.it\)/);
 assert.equal(receipt.provider_calls,false);assert.equal(receipt.scientific_data_modified,false);
});
test("Bayer matrices and every source glyph mask remain exactly equal to the supplied component",()=>{
 assert.deepEqual(GLYPH_BAYER4,reference.BAYER4);assert.deepEqual(GLYPH_BAYER8,reference.BAYER8);
 for(const cell of [4,8,14,32]){
  for(const [name,shapes] of Object.entries(reference.INK_SETS))assert.deepEqual(glyphMasks(name,cell),reference.buildMasks(shapes,cell));
  for(const [name,shapes] of Object.entries(reference.TRAIL_SETS))assert.deepEqual(glyphMasks(name,cell,true),reference.buildMasks(shapes,cell));
 }
 for(const cell of [0,3,33,NaN,Infinity])assert.throws(()=>glyphMasks("mixed",cell),/cell/);
});
test("procedural field at native resolution is byte-for-byte equal to the original three-sine source",()=>{
 const start=original.indexOf("const sampleProcedural=()=>{")+"const sampleProcedural=()=>{".length;
 const end=original.indexOf("};const sampleImage=",start);
 assert.ok(start>0&&end>start);
 const sourceSample=new Function("rows","cols","cell","time","shape","dark",original.slice(start,end));
 const layout=glyphLayout(140,84,14),field=createGlyphField(layout,{tone:{contrast:1,brightness:0}});
 assert.equal(layout.scale,1);
 for(const time of [0,1.5,7.25]){
  const dark=new Float32Array(layout.cols*layout.rows);
  sourceSample(layout.rows,layout.cols,layout.cell,time,value=>Math.max(0,Math.min(1,value)),dark);
  field.procedural(time);assert.deepEqual(field.snapshot().dark,dark);
 }
});
test("ordered multi-level drawing matches the actual source for all glyph/trail sets and both matrices",()=>{
 const start=original.indexOf("const blit="),end=original.indexOf("const resize=",start);
 const makeDraw=new Function("buf","imgData","ctx","cell","W","rows","cols","matrix","mSize","mMask","half","inkMasks","trailMasks","inkLevels","trailLevels","BG","INK","TRAIL","dark","field","clamp01",`${original.slice(start,end)};return draw;`);
 const layout=glyphLayout(84,56,14),palette={background:0xfffef7ed,ink:0xfff4eadb,trail:0xfff1e1c7};
 for(const pattern of ["4","8"])for(const glyphs of ["mixed","circles","lines","crosses"])for(const shape of ["beads","stars","frames"]){
  const field=createGlyphField(layout,{glyphs,trailShape:shape,pattern,tone:{contrast:1,brightness:0}});
  field.procedural(1.7);field.step(0,{x:2,y:2},{radius:14,strength:.8});
  const snap=field.snapshot(),actual=new Uint32Array(layout.width*layout.height),expected=new Uint32Array(actual.length);
  field.draw(actual,palette);
  const ink=reference.buildMasks(reference.INK_SETS[glyphs],layout.cell),trail=reference.buildMasks(reference.TRAIL_SETS[shape],layout.cell),size=pattern==="4"?4:8;
  const draw=makeDraw(expected,{}, {putImageData(){}},layout.cell,layout.width,layout.rows,layout.cols,pattern==="4"?reference.BAYER4:reference.BAYER8,size,size-1,size>>1,ink,trail,ink.length,trail.length,palette.background,palette.ink,palette.trail,snap.dark,snap.field,v=>Math.max(0,Math.min(1,v)));
  draw();assert.deepEqual(actual,expected);
 }
});
test("canvas allocations stay bounded on large, narrow, zero or nonfinite viewports",()=>{
 for(const [w,h] of [[1274,748],[3840,2160],[100000,100000],[100000,1],[1,100000],[0,0],[NaN,Infinity]])for(const cell of [4,14,32,Infinity]){
  const layout=glyphLayout(w,h,cell);
  assert.ok(layout.width*layout.height<=GLYPH_MAX_PIXELS);assert.ok(layout.width<=GLYPH_MAX_DIMENSION&&layout.height<=GLYPH_MAX_DIMENSION);
  assert.ok(layout.cell>=4&&layout.cell<=32);assert.ok(layout.cols>=1&&layout.rows>=1);
  const field=createGlyphField(layout);assert.equal(field.snapshot().field.length,layout.cols*layout.rows);
 }
 assert.throws(()=>createGlyphField({cols:1e8,rows:1e8,width:4e8,height:4e8,cell:4,scale:1}),/budget/);
 assert.throws(()=>createGlyphField({...glyphLayout(100,100),width:NaN}),/budget/);
});
test("pointer coordinates respect CSS scaling and reject outside/nonfinite positions",()=>{
 const layout=glyphLayout(140,84,14),rect={left:100,top:50,width:280,height:168};
 assert.deepEqual(glyphPointer(240,134,rect,layout),{x:5,y:3});
 for(const [x,y] of [[99,100],[400,100],[200,20],[200,300],[NaN,100]])assert.equal(glyphPointer(x,y,rect,layout),null);
 assert.equal(glyphPointer(0,0,{left:0,top:0,width:0,height:100},layout),null);
 assert.equal(glyphPackedColor(12,34,56,255),0xff38220c);
});
test("sampled image keeps alpha compositing and source luminance coefficients",()=>{
 const layout=glyphLayout(56,14,14),field=createGlyphField(layout,{tone:{contrast:1,brightness:0}});
 field.image(new Uint8ClampedArray([0,0,0,255,255,255,255,255,0,0,0,0,255,0,0,255]));
 const dark=field.snapshot().dark;
 assert.equal(dark[0],1);assert.ok(Math.abs(dark[1])<1e-12);assert.ok(Math.abs(dark[2])<1e-12);assert.ok(Math.abs(dark[3]-.7874)<1e-7);
 assert.throws(()=>field.image(new Uint8ClampedArray(3)),/dimensions/);
});
test("diffusion uses the source reflecting edge and exponential decay instead of additive particle accumulation",()=>{
 const layout=glyphLayout(140,140,14),field=createGlyphField(layout);
 field.step(0,{x:0,y:0},{radius:14,strength:.45,spread:.2,duration:1.6});
 const initial=field.snapshot().field[0];field.step(.05,null,{radius:14,strength:.45,spread:.2,duration:1.6});
 const values=field.snapshot().field,decay=Math.pow(.03,.05/1.6),spread=.2*.05*60*.5;
 assert.ok(Math.abs(values[0]-(initial+(initial*.5-initial)*spread)*decay)<1e-7);
 assert.ok(Math.abs(values[1]-initial*.25*spread*decay)<1e-7);
 assert.ok(Math.abs(values[layout.cols]-values[1])<1e-9);
 for(let i=0;i<1000;i++)field.step(0,{x:4+(i%2),y:4},{radius:14,strength:.45});
 assert.ok(Math.max(...field.snapshot().field)<=.4500001);
 for(let i=0;i<500;i++)field.step(.05,null);
 assert.equal(field.snapshot().alive,false);assert.ok(field.snapshot().field.every(value=>value===0));
});
test("fast pointer paths retain continuous source stamping with an explicit work cap",()=>{
 const layout=glyphLayout(1600,300,4),field=createGlyphField(layout);
 field.step(0,{x:0,y:2},{radius:10});
 const result=field.step(0,{x:layout.cols,y:2},{radius:10});
 assert.ok(result.stamps<=GLYPH_MAX_STAMPS&&result.stamps>1);
 assert.ok(field.snapshot().field.slice(2*layout.cols,3*layout.cols).some(value=>value>0));
 field.clear();assert.equal(field.snapshot().alive,false);assert.ok(field.snapshot().field.every(value=>value===0));
 assert.equal(field.step(0,{x:Infinity,y:NaN}).stamps,0);
 assert.throws(()=>field.draw(new Uint32Array(2),{background:0,ink:1,trail:2}),/dimensions/);
});

const active={active:true,hidden:false,reducedMotion:false,intersecting:true};
function driverHarness({keepGoing=true,fail=false}={}){
 let next=0;const callbacks=new Map(),pending=new Map(),cancelled=[],draws=[],errors=[];
 const driver=createGlyphFrameDriver({requestFrame(callback){const id=next++;pending.set(id,callback);callbacks.set(id,callback);return id;},cancelFrame(id){cancelled.push(id);pending.delete(id);},render(dt){draws.push(dt);if(fail)throw Error("draw failed");return keepGoing;},onError:()=>errors.push(true)});
 return{driver,pending,callbacks,cancelled,draws,errors,frame(time){const work=[...pending.entries()];pending.clear();work.forEach(([,callback])=>callback(time));}};
}
test("active, visibility, intersection and reduced-motion gates each stop all scheduled work",()=>{
 for(const key of ["active","hidden","reducedMotion","intersecting"]){
  const state={...active,[key]:key==="hidden"||key==="reducedMotion"};assert.equal(glyphCanAnimate(state),false);
  const h=driverHarness();h.driver.update(active);assert.ok(h.pending.has(0));h.driver.update(state);assert.equal(h.pending.size,0);assert.deepEqual(h.cancelled,[0]);
 }
});
test("frame requests coalesce, draw frequency is capped and long visibility gaps do not advance time",()=>{
 const h=driverHarness();h.driver.update(active);h.driver.invalidate();h.driver.invalidate();assert.equal(h.pending.size,1);
 h.frame(0);h.frame(10);h.frame(20);h.frame(1000/GLYPH_FPS+1);assert.equal(h.draws.length,2);
 h.driver.update({...active,hidden:true});h.driver.update(active);h.frame(1e8);assert.equal(h.draws.at(-1),0);
 h.frame(1e8+100);assert.equal(h.draws.at(-1),.05);
});
test("idle field stops requesting frames and pointer invalidation wakes exactly one frame",()=>{
 const h=driverHarness({keepGoing:false});h.driver.update(active);h.frame(0);assert.equal(h.pending.size,0);
 h.driver.invalidate();h.driver.invalidate();assert.equal(h.pending.size,1);h.frame(100);assert.equal(h.pending.size,0);
});
test("cancelled callback cannot corrupt a resumed frame chain",()=>{
 const h=driverHarness();h.driver.update(active);const old=h.callbacks.get(0);
 h.driver.update({...active,hidden:true});h.driver.update(active);assert.equal(h.pending.size,1);assert.ok(h.pending.has(1));
 old(0);assert.equal(h.draws.length,0);assert.equal(h.pending.size,1);assert.ok(h.pending.has(1));
 h.frame(100);assert.equal(h.draws.length,1);assert.equal(h.pending.size,1);
});
test("disposal cancels exact pending callback and ignores late events or invalidation",()=>{
 const h=driverHarness();h.driver.update(active);const old=h.callbacks.get(0);h.driver.dispose();h.driver.dispose();
 old(1);h.driver.invalidate();h.driver.update(active);assert.deepEqual(h.cancelled,[0]);assert.equal(h.pending.size,0);assert.equal(h.draws.length,0);
});
test("drawing failure ends the chain once and exposes a quiet fallback",()=>{
 const h=driverHarness({fail:true});h.driver.update(active);h.frame(0);h.driver.invalidate();h.driver.update(active);
 assert.equal(h.errors.length,1);assert.equal(h.pending.size,0);assert.equal(h.draws.length,1);
});
test("server-rendered effect is light-blue decorative-only and cannot capture clicks or request a provider",()=>{
 const html=renderToStaticMarkup(React.createElement(GlyphTrail));
 assert.match(html,/aria-hidden="true"/);assert.match(html,/background-color:#edf7fe/);assert.match(html,/data-glyph-trail="fallback"/);
 assert.equal((html.match(/<canvas/g)??[]).length,1);assert.doesNotMatch(html,/<button|<a\b|<img\b|<video\b|<iframe\b|role="img"/);
 const css=readFileSync("app/components/glyph-trail.module.css","utf8");assert.match(css,/pointer-events:none/);
 const source=readFileSync("app/components/glyph-trail.tsx","utf8");assert.doesNotMatch(source,/from "framer"|fetch\(|getUserMedia|speechSynthesis|\/api\//);
});
