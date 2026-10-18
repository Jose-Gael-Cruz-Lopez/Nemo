import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as live from "../app/components/live-saved-detector-state.ts";

const camera={running:true,fresh:true,session_id:"usb-current",width:1280,height:720,backend:"AVFOUNDATION",device_index:0};
const calibration={id:"cal-aaaaaaaaaaaaaaaa",calibration_id:"cal-aaaaaaaaaaaaaaaa",camera_session_id:"usb-old",homography_image_to_cm:[[0.1,0,0],[0,0.1,0],[0,0,1]],mean_error_cm:0.2,max_error_cm:0.3,max_allowed_error_cm:3,approved:true,validation_count:3,image_size_px:[1280,720],plane:"measured_water_surface",units:"cm"};
const raw=JSON.stringify(calibration).replace("[0,0,1]","[0.0,0.0,1.0]"),source={schema_version:"nemo_saved_calibration_v1",calibration,calibration_json:raw};
const reference={reference_id:"ref-old",camera_session_id:"usb-old",image_size_px:[1280,720],captured_at:1792000000,detector:"foreground_reference_v1",full_frame:true};
const references={references:[reference]};
const summary=Object.fromEntries(["calibration_id","camera_session_id","image_size_px","approved","max_error_cm","max_allowed_error_cm","mean_error_cm","validation_count"].map(key=>[key,calibration[key]]));
const calibrations={calibrations:[summary]};
function configResponse(){return{schema_version:"nemo_detector_preview_config_v1",preview_id:"preview-one",detector_mode:"saved_green_marker_preview_v1",camera_session_id:camera.session_id,image_size_px:[1280,720],reference_id:reference.reference_id,reference_camera_session_id:reference.camera_session_id,source_calibration_id:calibration.calibration_id,source_content_sha256:"a".repeat(64),source_camera_session_id:calibration.camera_session_id,homography_image_to_cm:calibration.homography_image_to_cm,detection_polygon_px:[[0,0],[355.6,0],[355.6,228.6],[0,228.6]],policy:{policy_id:"saved_green_marker_preview_v1",policy_sha256:"b".repeat(64)},marker_area_source:{report_id:"surface-replay-old",clip_id:"green-cap",point_index:0,area_px:1500,area_px_range:[525,4500],source_policy_sha256:"c".repeat(64)},data_origin:"LOCAL_LIVE_DISPLAY_ESTIMATED_COORDINATES",validation_status:"UNVALIDATED",current_alignment_verified:false,approved_for_inference:false,measured_flow_eligible:false,calibration_id:null,profile_id:null,case_id:null,warnings:["Display only; centimetres are estimated."]};}
const config=()=>live.parseLivePreviewConfig(configResponse(),source,reference,camera);
function frameResponse(sequence=7){const d={pixel_x:100,pixel_y:100,reference_pixel_x:73,reference_pixel_y:100,area_px:1500,bbox_px:[90,90,20,20]};return{schema_version:"nemo_detector_preview_frame_v1",preview_id:"preview-one",detector_mode:"saved_green_marker_preview_v1",data_origin:"LOCAL_LIVE_DISPLAY_ESTIMATED_COORDINATES",validation_status:"UNVALIDATED",approved_for_inference:false,measured_flow_eligible:false,calibration_id:null,profile_id:null,case_id:null,camera_session_id:camera.session_id,image_size_px:[1280,720],sequence,received_utc:"2026-10-18T22:00:00Z",received_mono_s:100,age_s:0.05,timestamp_kind:"host_receipt_not_exposure",jpeg_data_url:"data:image/jpeg;base64,/9j/2Q==",observed:true,reason:null,scene_rejection:null,saved_foreground_status:"SCENE_CHANGED",saved_foreground_rejection:"Brightness changed",alignment_rejection:null,alignment:{method:"orb_translation_estimate_v1",applied:true,dx_px:27,dy_px:0,confidence:0.8},point:{...d,estimated_x_cm:7.3,estimated_y_cm:10},detections:[d],diagnostics:{candidate_count:1,accepted_count:1,rejected_count:0,rejection_counts:{}}};}
const parsedFrame=()=>live.parseLivePreviewFrame(frameResponse(),config());

test("saved setup selection prefers compatible original-session pairing without inventing measurements",()=>{
  const selected=live.selectSavedPreviewInputs(references,calibrations,camera);assert.equal(selected.reference.reference_id,"ref-old");assert.equal(selected.calibration.calibration_id,calibration.calibration_id);
  const current={...reference,reference_id:"ref-current",camera_session_id:camera.session_id};assert.equal(live.selectSavedPreviewInputs({references:[reference,current]},calibrations,camera).reference.reference_id,"ref-current");
  const body=live.buildLivePreviewConfig(reference,source,camera);assert.equal(body.detector_mode,"saved_green_marker_preview_v1");assert.equal(body.source.calibration_json,raw);assert.deepEqual(body.source.calibration.homography_image_to_cm,calibration.homography_image_to_cm);assert.equal(Object.hasOwn(body,"approved"),false);assert.equal(body.detection_polygon_px.length,4);
  assert.throws(()=>live.selectSavedPreviewInputs({references:[]},calibrations,camera),/No intact saved/);assert.throws(()=>live.selectSavedPreviewInputs(references,{calibrations:[]},camera),/No approved historical/);assert.throws(()=>live.buildLivePreviewConfig(reference,source,{...camera,fresh:false}),/does not start/);
});
test("config rejects approval, changed mapping or missing historical green area provenance",()=>{
  for(const changes of[{approved_for_inference:true},{measured_flow_eligible:true},{current_alignment_verified:true},{calibration_id:calibration.calibration_id},{source_calibration_id:"cal-bbbbbbbbbbbbbbbb"},{homography_image_to_cm:[[1,0,0],[0,1,0],[0,0,1]]},{marker_area_source:null},{camera_session_id:"usb-other"}])assert.throws(()=>live.parseLivePreviewConfig({...configResponse(),...changes},source,reference,camera));
  assert.equal(config().policy_id,"saved_green_marker_preview_v1");
});
test("exact JPEG frame keeps raw box, translation estimate and conditional centimetres separate",()=>{
  const frame=parsedFrame();assert.equal(frame.point.pixel_x,100);assert.equal(frame.point.reference_pixel_x,73);assert.equal(frame.point.estimated_x_cm,7.3);assert.equal(frame.saved_foreground_status,"SCENE_CHANGED");
  const grid=live.livePreviewGrid(config(),frame);assert.ok(grid);assert.ok(grid.hull.some(([x])=>Math.abs(x-27)<1e-6));assert.deepEqual(config().homography_image_to_cm,calibration.homography_image_to_cm);
  const noRegistration=frameResponse();noRegistration.alignment=null;noRegistration.alignment_rejection="Too few static matches";for(const d of[noRegistration.point,...noRegistration.detections]){d.reference_pixel_x=null;d.reference_pixel_y=null;}noRegistration.point.estimated_x_cm=null;noRegistration.point.estimated_y_cm=null;
  const pixelOnly=live.parseLivePreviewFrame(noRegistration,config());assert.equal(pixelOnly.observed,true);assert.equal(pixelOnly.point.estimated_x_cm,null);assert.equal(live.livePreviewGrid(config(),pixelOnly),null);
});
test("stale, oversized, cross-session, mismatched or promoted frame data cannot reach overlay",()=>{
  for(const changes of[{sequence:6},{age_s:2.01},{camera_session_id:"usb-other"},{detector_mode:"foreground_surface_v2"},{approved_for_inference:true},{profile_id:"profile"},{jpeg_data_url:"https://other/frame.jpg"},{jpeg_data_url:"data:image/svg+xml;base64,PHN2Zz4="},{jpeg_data_url:"data:image/jpeg;base64,/9j/"+"a".repeat(854000)}])assert.throws(()=>live.parseLivePreviewFrame({...frameResponse(),...changes},config(),7));
  const mismatch=frameResponse();mismatch.point.estimated_x_cm=99;assert.throws(()=>live.parseLivePreviewFrame(mismatch,config()));
  const misaligned=frameResponse();misaligned.alignment.dx_px=26;assert.throws(()=>live.parseLivePreviewFrame(misaligned,config()));
  const tooFar=frameResponse();tooFar.alignment.dx_px=65;assert.throws(()=>live.parseLivePreviewFrame(tooFar,config()));
});

function deferred(){let resolve;const promise=new Promise(yes=>{resolve=yes;});return{promise,resolve};}
const settle=()=>new Promise(resolve=>setTimeout(resolve,0));
function harness({poll}={}){
  const jobs=[],calls=[];let pollCount=0,active=0,maxActive=0;
  const scheduler={set:(callback,ms)=>{const job={callback,ms,cleared:false};jobs.push(job);return job;},clear:job=>{job.cleared=true;}};
  const request=async(path,body,options)=>{calls.push({path,body,options});if(path==="/camera/detector-preview/references")return references;if(path==="/vision/calibrations")return calibrations;if(path.startsWith("/vision/calibrations/"))return source;if(path==="/camera/detector-preview/config")return configResponse();if(path==="/camera/detector-preview/preview-one"){const index=pollCount++;active++;maxActive=Math.max(maxActive,active);try{return await(poll?poll(index,options):frameResponse(7+index));}finally{active--;}}throw new Error(`unexpected ${path}`);};
  const controller=new live.LiveSavedDetectorController({request,camera,disabled:false},scheduler);
  return{controller,calls,jobs,request,get maxActive(){return maxActive;},get pollCount(){return pollCount;},runPoll(){const job=jobs.find(j=>!j.cleared&&j.ms===live.LIVE_DETECTOR_POLL_MS);assert.ok(job);job.cleared=true;job.callback();},expire(){const job=jobs.find(j=>!j.cleared&&j.ms>live.LIVE_DETECTOR_POLL_MS);assert.ok(job);job.cleared=true;job.callback();}};
}
test("construction is inert; explicit start reads only saved setup and the existing buffer",async()=>{
  const h=harness();assert.equal(h.calls.length,0);assert.equal(h.controller.getSnapshot(),live.INITIAL_LIVE_SAVED_STATE);await h.controller.start();assert.equal(h.controller.getSnapshot().phase,"live");assert.equal(h.controller.getSnapshot().frame.sequence,7);
  const configCall=h.calls.find(c=>c.path.endsWith("/config"));assert.equal(configCall.body.detector_mode,"saved_green_marker_preview_v1");assert.equal(configCall.body.source.calibration_json,raw);assert.ok(h.calls.every(c=>![/\/camera\/start/,/\/camera\/record/,/\/camera\/stop/,/\/camera\/reference$/].some(pattern=>pattern.test(c.path))));h.controller.stop();
});
test("polling waits125ms after completion, never overlaps, and clears stale boxes while a request hangs",async()=>{
  const pending=deferred(),h=harness({poll:index=>index===0?frameResponse():pending.promise});await h.controller.start();assert.equal(live.LIVE_DETECTOR_POLL_MS,125);h.runPoll();await settle();assert.equal(h.pollCount,2);assert.equal(h.maxActive,1);assert.equal(h.jobs.filter(j=>!j.cleared&&j.ms===125).length,0);await h.controller.start();assert.equal(h.pollCount,2);
  h.expire();assert.equal(h.controller.getSnapshot().phase,"error");assert.equal(h.controller.getSnapshot().frame,null);assert.equal(h.calls.at(-1).options.signal.aborted,true);pending.resolve(frameResponse(8));await settle();assert.equal(h.controller.getSnapshot().frame,null);h.controller.stop();
});
test("session changes and stop discard late responses and release timers",async()=>{
  const pending=deferred(),h=harness({poll:()=>pending.promise}),started=h.controller.start();await settle();h.controller.setContext({request:h.request,camera:{...camera,session_id:"usb-other"},disabled:false});assert.equal(h.calls.at(-1).options.signal.aborted,true);pending.resolve(frameResponse());await started;assert.equal(h.controller.getSnapshot().frame,null);assert.equal(h.controller.getSnapshot().phase,"error");h.controller.stop();assert.equal(h.controller.getSnapshot(),live.INITIAL_LIVE_SAVED_STATE);assert.ok(h.jobs.every(j=>j.cleared));
});

function componentExports(react=React){const require=createRequire(import.meta.url),mod={exports:{}};const compiled=ts.transpileModule(readFileSync(new URL("../app/components/live-saved-detector.tsx",import.meta.url),"utf8"),{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText;new Function("require","module","exports",compiled)(name=>{if(name==="react")return react;if(name==="./live-saved-detector-state.ts")return live;if(name.endsWith(".module.css"))return{__esModule:true,default:new Proxy({},{get:(_,key)=>String(key)})};return require(name);},mod,mod.exports);return mod.exports;}
function descendants(element){return!React.isValidElement(element)?[]:[element,...React.Children.toArray(element.props.children).flatMap(descendants)];}
test("server rendering requests no camera/API; matched frame displays cap box and estimated grid",()=>{
  const{LiveSavedDetector,LiveSavedDetectorFrame}=componentExports();let calls=0;const initial=renderToStaticMarkup(React.createElement(LiveSavedDetector,{request:()=>{calls++;},camera,disabled:false}));assert.equal(calls,0);assert.match(initial,/Show live detector with saved setup/);assert.doesNotMatch(initial,/<img|<video/);
  const html=renderToStaticMarkup(React.createElement(LiveSavedDetectorFrame,{config:config(),frame:parsedFrame()}));assert.match(html,/Exact local camera frame 7/);assert.match(html,/GREEN MARKER/);assert.match(html,/estimated tank 7.30, 10.00 cm/);assert.match(html,/Saved background changed; using green-marker preview/);assert.match(html,/same frame/);assert.match(html,/<output[^>]*aria-live="off"/);assert.doesNotMatch(html,/validated source|confidence 80|accuracy 100/);
});
test("pixel cap stays visible when image registration fails, with no grid or centimetre readout",()=>{
  const{LiveSavedDetectorFrame}=componentExports(),raw=frameResponse();raw.alignment=null;raw.alignment_rejection="No static translation";for(const d of[raw.point,...raw.detections]){d.reference_pixel_x=null;d.reference_pixel_y=null;}raw.point.estimated_x_cm=null;raw.point.estimated_y_cm=null;
  const html=renderToStaticMarkup(React.createElement(LiveSavedDetectorFrame,{config:config(),frame:live.parseLivePreviewFrame(raw,config())}));assert.match(html,/GREEN MARKER/);assert.match(html,/tank coordinates withheld/);assert.doesNotMatch(html,/data-live-layer="estimated-grid"|estimated tank/);
});
test("the visible cap-box toggle only changes its same-frame overlay",()=>{
  const values=[true,true,true];let cursor=0,tree;const{LiveSavedDetectorFrame}=componentExports({...React,useId:()=>"live-frame-test",useMemo:calculate=>calculate(),useState:initial=>{const i=cursor++;return[values[i]??initial,value=>{values[i]=value;}];}}),props={config:config(),frame:parsedFrame()};const render=()=>{cursor=0;tree=LiveSavedDetectorFrame(props);};render();assert.equal(descendants(tree).filter(e=>e.props["data-live-layer"]==="green-cap").length,1);descendants(tree).filter(e=>e.type==="input")[1].props.onChange({target:{checked:false}});render();assert.equal(descendants(tree).filter(e=>e.props["data-live-layer"]==="green-cap").length,0);assert.equal(descendants(tree).filter(e=>e.type==="img").length,1);
});
