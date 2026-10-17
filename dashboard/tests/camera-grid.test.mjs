import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as geometry from "../app/components/camera-grid-state.ts";
import { parseCalibration } from "../app/components/field-workflow-state.ts";

const { cameraStreamSource,convexHull,insideHull,invertMatrix,metricGrid,nativePixel,projectPoint } = geometry;
const fitPixels = [[100,100],[900,100],[900,500],[100,500]];
const mapping = { approved:true,camera_session_id:"usb-test",image_size_px:[1000,600],homography_image_to_cm:[[0.05,0,-5],[0,0.05,-5],[0,0,1]],mapping_polygon_px:fitPixels,plane:"measured_water_surface",units:"cm" };
const near = (a,b) => assert.ok(Math.abs(a-b) < 1e-7,`${a} ~= ${b}`);

test("native click coordinates remain correct on a scaled image and clamp at valid pixel centres",()=>{
  assert.deepEqual(nativePixel(250,150,500,300,1000,600),[500,300]);
  assert.deepEqual(nativePixel(700,-2,500,300,1000,600),[999,0]);
  assert.equal(nativePixel(1,2,0,300,1000,600),null);
});
test("a projective mapping round-trips points and refuses singular matrices or the horizon",()=>{
  const matrix = [[0.05,0.004,-5],[-0.003,0.04,2],[0.0002,0.0001,1]];
  const inverse = invertMatrix(matrix);
  assert.ok(inverse);
  for(const p of [[100,200],[700,400],[900,50]]) {
    const restored = projectPoint(inverse,projectPoint(matrix,p));
    near(restored[0],p[0]);near(restored[1],p[1]);
  }
  assert.equal(invertMatrix([[1,0,0],[1,0,0],[0,0,1]]),null);
  assert.equal(invertMatrix([[1,0,0],[0,NaN,0],[0,0,1]]),null);
  assert.equal(projectPoint([[1,0,0],[0,1,0],[1,0,-1]],[1,2]),null);
});
test("centimetre grid is confined to the measured fitting-mark hull",()=>{
  const grid = metricGrid(mapping,"usb-test",1000,600);
  assert.ok(grid);assert.equal(grid.spacingCm,5);
  assert.deepEqual(grid.hull,fitPixels);
  assert.ok(grid.lines.length > 5);
  for(const line of grid.lines) {
    assert.ok(insideHull(line.start,grid.hull));assert.ok(insideHull(line.end,grid.hull));
    for(const p of [line.start,line.end]) near(projectPoint(grid.matrix,p)[line.axis === "x" ? 0 : 1],line.value);
  }
  assert.equal(insideHull([50,200],grid.hull),false);
  assert.deepEqual(convexHull([[0,0],[1,1],[2,2]]),[]);
});
test("projective grid obeys an oblique measured boundary rather than extrapolating to its bounding box",()=>{
  const trapezoid = [[200,100],[850,180],[750,500],[100,450]];
  const grid = metricGrid({...mapping,mapping_polygon_px:trapezoid,homography_image_to_cm:[[0.05,0.004,-5],[-0.003,0.04,2],[0.0002,0.0001,1]]},"usb-test",1000,600);
  assert.ok(grid);
  assert.equal(insideHull([850,100],grid.hull),false);
  for(const line of grid.lines) for(const point of [line.start,line.end]) {
    assert.ok(insideHull(point,grid.hull));
    near(projectPoint(grid.matrix,point)[line.axis === "x" ? 0 : 1],line.value);
  }
});
test("missing, unapproved, stale, wrong-plane, wrong-size and horizon-crossing maps cannot produce a centimetre grid",()=>{
  for(const change of [{approved:false},{camera_session_id:"old"},{image_size_px:[1920,1080]},{units:"m"},{plane:"tank_bottom"},{homography_image_to_cm:undefined},{mapping_polygon_px:undefined},{mapping_polygon_px:[[0,0],[1,1],[2,2],[3,3]]},{homography_image_to_cm:[[1,0,0],[0,1,0],[1,0,-500]]}]) assert.equal(metricGrid({...mapping,...change},"usb-test",1000,600),null);
  assert.equal(metricGrid(null,"usb-test",1000,600),null);
});
test("calibration parsing freezes submitted fitting marks and preserves a legacy draft without inventing a matrix",()=>{
  const report = {...mapping,calibration_id:"cal-test",max_error_cm:0.2,max_allowed_error_cm:0.5,mean_error_cm:0.1,validation_count:3};
  const parsed = parseCalibration(report,fitPixels);
  assert.deepEqual(parsed.homography_image_to_cm,report.homography_image_to_cm);
  assert.notEqual(parsed.mapping_polygon_px,fitPixels);
  const legacy = {...report};delete legacy.homography_image_to_cm;delete legacy.mapping_polygon_px;
  assert.equal(parseCalibration(legacy).homography_image_to_cm,undefined);
  assert.equal(metricGrid(parseCalibration(legacy),"usb-test",1000,600),null);
  assert.throws(()=>parseCalibration({...report,homography_image_to_cm:[[1,0,0],[1,0,0],[0,0,1]]}),/singular/);
});

function controller() {
  const require = createRequire(import.meta.url), values=[],refs=[],effects=[];let cursor=0,refCursor=0;
  const compiled = ts.transpileModule(readFileSync(new URL("../app/components/camera-plane.tsx",import.meta.url),"utf8"),{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText;
  const mod = {exports:{}};
  new Function("require","module","exports",compiled)(name=>{
    if(name === "react")return {...React,useId:()=>"camera-test",useMemo:calculate=>calculate(),useEffect:effect=>{effects.push(effect);},useRef:initial=>{const index=refCursor++;return refs[index] ??= {current:initial};},useState:initial=>{const index=cursor++;if(!(index in values))values[index]=initial;return [values[index],next=>{values[index]=typeof next === "function" ? next(values[index]) : next;}];}};
    if(name === "./camera-grid-state")return geometry;
    if(name.endsWith(".module.css"))return {__esModule:true,default:new Proxy({},{get:(_,key)=>String(key)})};
    if(name === "next/image")return {__esModule:true,default:props=>React.createElement("img",{...props,unoptimized:undefined})};
    return require(name);
  },mod,mod.exports);
  const render = props=>{cursor=0;refCursor=0;return mod.exports.CameraPlane(props);};
  render.Preview=mod.exports.CalibrationCameraPreview;
  render.cleanup=()=>{for(const effect of effects)effect()?.();};
  return render;
}
function descendants(element) { return !React.isValidElement(element) ? [] : [element,...React.Children.toArray(element.props.children).flatMap(descendants)]; }

test("unmapped view is visibly pixels only, grid toggles hide actual layers, and picking uses native coordinates",()=>{
  const render = controller();let picked;
  const props = {apiBase:"",width:1000,height:600,sessionId:"usb-test",active:true,onPick:p=>{picked=p;}};
  let tree=render(props),html=renderToStaticMarkup(tree);
  assert.match(html,/data-camera-layer="pixels"/);assert.doesNotMatch(html,/data-camera-layer="centimetres"/);
  assert.match(html,/not centimetre calibration/);assert.match(html,/stream.mjpg\?session_id=usb-test/);assert.doesNotMatch(html,/frame.jpg|[?&]t=/);
  const controls=descendants(tree).filter(e=>e.type === "input");
  assert.equal(controls[1].props.disabled,true);
  controls[0].props.onChange({target:{checked:false}});
  tree=render(props);assert.doesNotMatch(renderToStaticMarkup(tree),/data-camera-layer="pixels"/);
  const image=descendants(tree).find(e=>e.props.alt?.startsWith("Live external"));
  image.props.onClick({clientX:260,clientY:170,currentTarget:{getBoundingClientRect:()=>({left:10,top:20,width:500,height:300})}});
  assert.deepEqual(picked,[500,300]);
  tree=render({...props,calibration:mapping});html=renderToStaticMarkup(tree);
  assert.match(html,/data-camera-layer="centimetres"/);assert.match(html,/clipped to the fitting-mark hull/);
  descendants(tree).filter(e=>e.type === "input")[1].props.onChange({target:{checked:false}});
  assert.doesNotMatch(renderToStaticMarkup(render({...props,calibration:mapping})),/data-camera-layer="centimetres"/);
});


test("stream source is session-bound and inactive previews contain no image request",()=>{
  assert.equal(cameraStreamSource("/","usb a/b",true),"/api/v1/camera/stream.mjpg?session_id=usb%20a%2Fb");
  assert.equal(cameraStreamSource("",null,true),undefined);
  assert.equal(cameraStreamSource("","usb-test",false),undefined);
  const render=controller(),props={apiBase:"",width:1280,height:720,sessionId:"usb-test",active:true};
  assert.equal(renderToStaticMarkup(React.createElement(render.Preview,{...props,visible:false})),"");
  const shown=renderToStaticMarkup(React.createElement(render.Preview,{...props,visible:true}));
  assert.equal((shown.match(/src="[^"]*stream.mjpg/g)??[]).length,1);
  assert.doesNotMatch(renderToStaticMarkup(render({...props,active:false})),/src=/);
});

test("cursor updates are coalesced, stream URL stays stable and pending animation work is cleaned up",()=>{
  const previousWindow=globalThis.window,callbacks=new Map(),cancelled=[];let next=0;
  globalThis.window={requestAnimationFrame:callback=>{callbacks.set(++next,callback);return next;},cancelAnimationFrame:id=>{cancelled.push(id);callbacks.delete(id);}};
  try {
    const render=controller(),props={apiBase:"",width:1000,height:600,sessionId:"usb-test",active:true};
    const image=()=>descendants(render(props)).find(e=>e.type==="img");
    const event=(x,y)=>({clientX:x,clientY:y,currentTarget:{getBoundingClientRect:()=>({left:0,top:0,width:500,height:300})}});
    image().props.onMouseMove(event(100,100));image().props.onMouseMove(event(200,150));
    assert.equal(callbacks.size,1);
    const [id,callback]=[...callbacks][0];callbacks.delete(id);callback();
    const html=renderToStaticMarkup(render(props));
    assert.match(html,/Image x 400.0, y 300.0 px/);
    assert.equal(image().props.src,"/api/v1/camera/stream.mjpg?session_id=usb-test");
    image().props.onMouseMove(event(250,160));render.cleanup();
    assert.equal(callbacks.size,0);assert.ok(cancelled.length>0);
    image().props.onError();
    assert.match(renderToStaticMarkup(render(props)),/No background retry or camera restart/);
    assert.equal(image().props.src,"/api/v1/camera/stream.mjpg?session_id=usb-test");
  } finally {globalThis.window=previousWindow;}
});
