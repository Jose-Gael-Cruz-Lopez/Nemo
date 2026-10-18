import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as replay from "../app/components/saved-detector-replay-state.ts";
import { newDraft, parseTokenReference, detectionFields, buildSurfaceReferenceRequest, encodeDraft, decodeDraft } from "../app/components/field-workflow-state.ts";
import { buildEstimatedRehearsalRequest } from "../app/components/estimated-tank-rehearsal-state.ts";

function fixture() { return {
  schema_version: "nemo_surface_replay_v1", report_id: "replay-one", data_origin: "LOCAL_SAVED_FOOTAGE_REPLAY", purpose: "DEVELOPMENT_REGRESSION", validation_status: "UNVALIDATED", measured_flow_eligible: false, camera_accessed: false, photon_messages_sent: false, evaluated_at: "2026-10-18T22:00:00Z", policy: { id: "compact_cap_v1", sha256: "a".repeat(64), parameters: { shape: "frozen" } }, manifest_sha256: "b".repeat(64), totals: { frames: 2, baseline_accepted_frames: 0, surface_accepted_frames: 1, baseline_ambiguous_frames: 2, surface_ambiguous_frames: 0, scene_gap_frames: 0, roi_rejected_candidates: 1, shape_rejected_candidates: 1 }, warnings: ["Development footage; no independent field accuracy."], clips: [{ id: "clip-one", label: "Saved cap and strap", source_kind: "estimated_rehearsal", source_id: "rehearsal-one", original_camera_session_id: "usb-old", image_size_px: [1280,720], frames: 2, baseline: { accepted_frames: 0, gap_frames: 2, multiple_frames: 2, scene_gap_frames: 0 }, surface: { accepted_frames: 1, gap_frames: 1, multiple_frames: 0, scene_gap_frames: 0 }, diagnostics: { rejection_counts: { OUTSIDE_ROI: 1, ELONGATED: 1 } }, points: [{ t_s: 0, observed: true, reason: null, pixel_x: 110, pixel_y: 110, track_id: "track-one", association_break: true }, { t_s: 0.1, observed: false, reason: "NO_DETECTION" }], example: { jpeg_data_url: "data:image/jpeg;base64,/9j/2Q==", sequence: 1, image_size_px: [1280,720], detection_polygon_px: [[50,50],[500,50],[500,500],[50,500]], baseline_boxes_px: [[100,100,20,20],[300,200,150,10]], accepted_boxes_px: [[100,100,20,20]], rejected_candidates: [{ bbox_px: [300,200,150,10], reason_codes: ["ELONGATED"] }] } }] }; }

test("saved replay retains detector decisions and authentic local JPEG metadata without granting validation",()=>{
  const result=replay.parseDetectorReplay(fixture()); assert.equal(result.measured_flow_eligible,false); assert.equal(result.camera_accessed,false); assert.equal(result.photon_messages_sent,false);
  assert.equal(result.clips[0].surface.accepted_frames,1); assert.match(result.clips[0].example.jpeg_data_url,/^data:image\/jpeg/); assert.equal(result.purpose,"DEVELOPMENT_REGRESSION");
});
test("parser rejects promoted evidence, external images, invalid bounds, gap coordinates and false accounting",()=>{
  for(const change of [{data_origin:"MEASURED_TANK"},{purpose:"FIELD_VALIDATION"},{validation_status:"VALIDATED"},{measured_flow_eligible:true},{camera_accessed:true},{photon_messages_sent:true}])assert.throws(()=>replay.parseDetectorReplay({...fixture(),...change}));
  for(const url of ["https://external/image.jpg","data:image/svg+xml;base64,PHN2Zz4=","javascript:alert(1)","data:text/html;base64,PGgxPg==","data:image/jpeg;base64,"+"a".repeat(2000000)]){const bad=fixture();bad.clips[0].example.jpeg_data_url=url;assert.throws(()=>replay.parseDetectorReplay(bad));}
  for(const candidate of [[-1,0,5,5],[1270,0,20,20],[0,0,0,5],[0,0,NaN,5]]){const bad=fixture();bad.clips[0].example.accepted_boxes_px=[candidate];assert.throws(()=>replay.parseDetectorReplay(bad));}
  const gap=fixture();gap.clips[0].points[1].pixel_x=120;assert.throws(()=>replay.parseDetectorReplay(gap));
  const fake=fixture();fake.clips[0].surface.accepted_frames=2;fake.clips[0].surface.gap_frames=0;assert.throws(()=>replay.parseDetectorReplay(fake));
  const wrongTotal=fixture();wrongTotal.totals.frames=3;assert.throws(()=>replay.parseDetectorReplay(wrongTotal));
});

function componentExports(react=React){const require=createRequire(import.meta.url),mod={exports:{}};const compiled=ts.transpileModule(readFileSync(new URL("../app/components/saved-detector-replay.tsx",import.meta.url),"utf8"),{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText;new Function("require","module","exports",compiled)(name=>{if(name==="react")return react;if(name==="./saved-detector-replay-state.ts")return replay;if(name.endsWith(".module.css"))return{__esModule:true,default:new Proxy({},{get:(_,key)=>String(key)})};return require(name);},mod,mod.exports);return mod.exports;}
function descendants(element){return!React.isValidElement(element)?[]:[element,...React.Children.toArray(element.props.children).flatMap(descendants)];}
function deferred(){let resolve;const promise=new Promise(yes=>{resolve=yes;});return{promise,resolve};}
const settle=()=>new Promise(resolve=>setTimeout(resolve,0));
function harness(request=async()=>fixture()){
  const hooks=[],effects=[],busy=[];let cursor=0,tree,props={request,disabled:false,onBusyChange:value=>busy.push(value)};
  const mock={...React,useId:()=>"saved-replay-test",useState(initial){const i=cursor++;if(!hooks[i])hooks[i]={value:initial};return[hooks[i].value,value=>{hooks[i].value=typeof value==="function"?value(hooks[i].value):value;}];},useRef(initial){const i=cursor++;if(!hooks[i])hooks[i]={current:initial};return hooks[i];},useEffect(effect,deps){const i=cursor++;if(!hooks[i]||deps.some((dep,j)=>!Object.is(dep,hooks[i].deps[j]))){const old=hooks[i];hooks[i]={deps};effects.push(()=>{old?.cleanup?.();hooks[i].cleanup=effect();});}}};
  const{SavedDetectorReplay}=componentExports(mock);const render=changes=>{props={...props,...changes};cursor=0;tree=SavedDetectorReplay(props);while(effects.length)effects.shift()();return tree;};render();return{render,busy,tree:()=>tree,button:label=>descendants(tree).find(item=>item.type==="button"&&item.props.children===label),unmount:()=>hooks.forEach(hook=>hook.cleanup?.())};
}
test("server rendering and mounting do not read footage or access camera APIs",async()=>{
  let calls=0;const{SavedDetectorReplay}=componentExports();const html=renderToStaticMarkup(React.createElement(SavedDetectorReplay,{request:()=>{calls++;},disabled:false}));assert.equal(calls,0);assert.match(html,/No camera opens/);assert.doesNotMatch(html,/<img|<video/);
  const h=harness(async()=>{calls++;return fixture();});await settle();assert.equal(calls,0);h.unmount();
  const source=readFileSync(new URL("../app/components/saved-detector-replay.tsx",import.meta.url),"utf8");assert.doesNotMatch(source,/getUserMedia|\/camera\/start|\/camera\/record|\/camera\/reference|fetch\(/);
});
test("explicit run posts only {} and last-report action uses GET",async()=>{
  const calls=[],h=harness(async(path,body)=>{calls.push({path,body});return fixture();});h.button("Replay saved camera footage").props.onClick();await settle();h.render();
  assert.deepEqual(calls,[{path:"/camera/detector-replay",body:{}}]);assert.match(renderToStaticMarkup(h.tree()),/Development regression/);assert.match(renderToStaticMarkup(h.tree()),/Photon messages: none/);
  h.button("Show last saved replay").props.onClick();await settle();h.render();assert.equal(calls[1].body,undefined);assert.deepEqual(h.busy,[true,false,true,false]);h.unmount();
});
test("late replay results are discarded after disable or unmount",async()=>{
  for(const action of["disable","unmount"]){const pending=deferred(),options=[],h=harness(async(_path,_body,opts)=>{options.push(opts);return pending.promise;});h.button("Replay saved camera footage").props.onClick();if(action==="disable")h.render({disabled:true});else h.unmount();assert.equal(options[0].signal.aborted,true);pending.resolve(fixture());await settle();if(action==="disable"){h.render();assert.doesNotMatch(renderToStaticMarkup(h.tree()),/Saved cap and strap/);h.unmount();}}
});
test("overlay labels expose original, accepted, rejected and frozen ROI layers",()=>{
  const{ReplayFrame}=componentExports(),clip=replay.parseDetectorReplay(fixture()).clips[0];const html=renderToStaticMarkup(React.createElement(ReplayFrame,{clip}));assert.match(html,/Surface v2 accepted/);assert.match(html,/Rejected objects/);assert.match(html,/Original v1 candidates/);assert.match(html,/Frozen tank outline/);assert.equal((html.match(/<rect/g)||[]).length,2);assert.equal((html.match(/<polygon/g)||[]).length,1);assert.match(html,/ELONGATED/);assert.doesNotMatch(html,/accuracy 100|confidence/);
});

const camera={running:true,fresh:true,session_id:"usb-current",width:1280,height:720,backend:"AVFOUNDATION",device_index:0};
const polygon=[[10,10],[500,10],[500,500],[10,500]];
const v2={reference_id:"ref-v2",camera_session_id:camera.session_id,image_size_px:[1280,720],detector:"foreground_surface_v2",detection_polygon_px:polygon,policy_id:"compact_cap_v1",policy_sha256:"c".repeat(64),derived_from_reference_id:"ref-v1",token_size:{reference_id:"ref-v2",token_area_px:3000,token_area_px_range:[1000,9000]}};
test("surface reference is explicit, versioned and round trips while legacy bodies remain unchanged",()=>{
  const reference=parseTokenReference(v2),draft={...newDraft(),cameraSessionId:camera.session_id,detector:"foreground_surface_v2",tokenReference:reference};
  assert.deepEqual(detectionFields(draft),{detector:"foreground_surface_v2",reference_id:"ref-v2"});assert.deepEqual(decodeDraft(encodeDraft(draft)).tokenReference,reference);
  assert.deepEqual(buildSurfaceReferenceRequest(draft,camera,polygon),{detection_polygon_px:polygon});assert.equal(draft.calibration,null);
  assert.deepEqual(detectionFields({...draft,detector:"red_hsv"}),{});
  const legacy=parseTokenReference({...v2,reference_id:"ref-v1",detector:"foreground_reference_v1",token_size:{...v2.token_size,reference_id:"ref-v1"}});
  assert.deepEqual(detectionFields({...draft,detector:"foreground_reference_v1",tokenReference:legacy}),{detector:"foreground_reference_v1",reference_id:"ref-v1"});
  assert.throws(()=>detectionFields({...draft,tokenReference:legacy}),/Prepare the surface detector/);
  for(const points of[undefined,[[1,1],[2,2],[3,3]],[[-1,0],[10,0],[10,10]]])assert.throws(()=>buildSurfaceReferenceRequest(draft,camera,points));
  assert.throws(()=>parseTokenReference({...v2,policy_sha256:"bad"}));
});
test("estimated capture opts into v2 only when its reference carries frozen v2 policy",()=>{
  const calibration={id:"cal-aaaaaaaaaaaaaaaa",calibration_id:"cal-aaaaaaaaaaaaaaaa",camera_session_id:"usb-old",homography_image_to_cm:[[0.1,0,0],[0,0.1,0],[0,0,1]],mean_error_cm:0.2,max_error_cm:0.3,max_allowed_error_cm:3,approved:true,validation_count:3,image_size_px:[1280,720],plane:"measured_water_surface",units:"cm"};
  const source={schema_version:"nemo_saved_calibration_v1",calibration,calibration_json:JSON.stringify(calibration)};
  const body=buildEstimatedRehearsalRequest(source,camera,parseTokenReference(v2),"5");assert.equal(body.detector,"foreground_surface_v2");assert.equal(body.reference_id,"ref-v2");assert.equal(body.acknowledge_estimated_mapping,true);
});


test("each overlay checkbox changes only its own drawn boxes or outline",()=>{
  const values=[true,true,false,true];let cursor=0,tree;
  const{ReplayFrame}=componentExports({...React,useState:initial=>{const i=cursor++;return[values[i]??initial,value=>{values[i]=value;}];}});
  const clip=replay.parseDetectorReplay(fixture()).clips[0];
  const render=()=>{cursor=0;tree=ReplayFrame({clip});};
  const toggles=()=>descendants(tree).filter(item=>item.type==="input");
  const count=type=>descendants(tree).filter(item=>item.type===type).length;
  render();assert.equal(count("rect"),2);assert.equal(count("polygon"),1);
  toggles()[0].props.onChange({target:{checked:false}});render();assert.equal(count("rect"),1);
  toggles()[1].props.onChange({target:{checked:false}});render();assert.equal(count("rect"),0);
  toggles()[2].props.onChange({target:{checked:true}});render();assert.equal(count("rect"),2);
  toggles()[3].props.onChange({target:{checked:false}});render();assert.equal(count("rect"),2);assert.equal(count("polygon"),0);
});
