import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import { OCEAN_SOURCE_GROUPS as GROUPS, OCEAN_SOURCE_MODELS as MODELS, OCEAN_SOURCE_STUDY as STUDY, OCEAN_SOURCE_OBSERVATION as OBSERVATION, createOceanPipelinePlayback, createOceanSourceRequests, oceanPipelinePlot, oceanSourcePlot, oceanSourceQuestion, oceanSourceSegments, validateOceanSourceEnvelope, validateOceanSourceAnswer } from "../app/components/ocean-source-state.ts";
import { readVectorResponse } from "../app/components/vector-diagnostic-state.ts";

// A fabricated DISPLAY-CONTRACT fixture, not scientific data or a new result.
// No transport integrator, scorer, provider, device or saved study is invoked.
function fixture() {
  const when = seconds => new Date(Date.parse(OBSERVATION)-seconds*1000).toISOString().replace(".000Z","Z");
  const geo = (seconds,shift=0) => ({time_utc:when(seconds),latitude_deg:30-seconds*1e-7+shift,longitude_deg:-70-seconds*2e-7});
  const names = ["center","east","west","north","south"], biases = ["zero","east","west","north","south"];
  const groups = GROUPS.map(group_id => {
    const scenarios = names.flatMap((offset,oi) => biases.map((bias,bi) => ({scenario_id:`${offset}|${bias}`,endpoint_offset_east_north_m:oi === 0 ? [0,0] : [oi*10,0],current_bias_east_north_m_s:bi === 0 ? [0,0] : [bi*.001,0],status:"COMPLETED",reason_code:null,completed_lookback_s:21600,track:Array.from({length:73},(_,i) => ({...geo(i*300,(oi+bi)*.00001),lookback_s:i*300}))})));
    return {group_id,observed_endpoint:geo(0),penultimate_observation:geo(3600),candidates:MODELS.map((model_id,index) => ({model_id,status:"COMPLETED",reason_code:null,earlier_time_utc:when(21600),latitude_deg:index===2?geo(21600).latitude_deg:30-index*.001,longitude_deg:index===2?geo(21600).longitude_deg:-70-index*.001})),reverse_current:{nominal_scenario_id:"center|zero",scenarios,earlier_candidates:[1,3,6].map(lookback_hours => ({lookback_hours,time_utc:when(lookback_hours*3600),planned_scenarios:25,available_count:25,points:scenarios.map(scenario => {const p=scenario.track[lookback_hours*12];return {scenario_id:scenario.scenario_id,latitude_deg:p.latitude_deg,longitude_deg:p.longitude_deg}})})),coverage:{planned_scenarios:25,completed_scenarios:25,partial_scenarios:0,unsupported_scenarios:0}},numerical_closure:{status:"COMPLETED",reason_code:null,endpoint_distance_m:.001,forward_track:[]}};
  });
  const validation = {planned_model_rows:6,scored_model_rows:6,planned_distinct_earlier_positions:2,primary_complete:true,rows:groups.flatMap(group => group.candidates.map((candidate,index) => ({group_id:group.group_id,model_id:candidate.model_id,status:"SCORED",reason_code:null,earlier_target:geo(21600,.00002),predicted_earlier:{time_utc:when(21600),latitude_deg:candidate.latitude_deg,longitude_deg:candidate.longitude_deg},error_m:100-index*10}))),primary_mean_earlier_position_error_m:MODELS.map((model_id,index) => ({model_id,group_count:2,mean_error_m:100-index*10}))};
  return {artifact_identity:{schema_version:1,kind:"OCEAN_SOURCE_RESULT_IDENTITY",study_id:STUDY,identity_sha256:"a".repeat(64),report_sha256:"b".repeat(64),protocol_sha256:"c".repeat(64),forecast_file_sha256:"d".repeat(64),integrity_verified:true,external_result_pin_verified:true,numeric_replay_verified:false,externally_trusted_pin_required_for_publication:true,verification_scope:"SAVED_BYTES_AND_LINEAGE_NOT_NUMERIC_REPLAY"},report:{schema_version:1,kind:"OCEAN_SOURCE_EXPLORATORY_RESULT",study_id:STUDY,analysis_scope:"POST_OUTCOME_EXPLORATORY",previously_viewed_earlier_positions:true,protocol_sha256:"c".repeat(64),forecast_file_sha256:"d".repeat(64),flags:{provider_calls:false,physical_validation:false,source_attribution_validated:false,automatic_model_promotion:false},limitations:["Synthetic display fixture; no real measurement or validated source."],forecasts:{schema_version:1,kind:"OCEAN_SOURCE_BACKTRACKING_FORECASTS",study_id:STUDY,analysis_scope:"POST_OUTCOME_EXPLORATORY",previously_viewed_earlier_positions:true,observation_time_utc:OBSERVATION,earlier_time_utc:when(21600),forecast_sha256:"e".repeat(64),model_ids:[...MODELS],group_ids:[...GROUPS],lookback_hours:[1,3,6],planned_model_rows:6,planned_distinct_earlier_positions:2,scenarios_per_group:25,inference_uses_only_last_two_positions:true,earlier_truth_used:false,groups},validation}};
}
const reject = value => assert.throws(() => validateOceanSourceEnvelope(value),/No result was accepted/);

test("fixed two-group display contract accepts saved cases without changing evidence",() => {
  const f=fixture(),before=JSON.stringify(f);assert.equal(validateOceanSourceEnvelope(f),f);assert.equal(JSON.stringify(f),before);
  assert.equal(f.report.forecasts.groups.length,2);assert.equal(f.report.validation.planned_distinct_earlier_positions,2);
});

test("identities, source/validation separation, physical claims and denominators fail closed",() => {
  for(const mutate of [
    f=>{f.artifact_identity.integrity_verified=false},f=>{f.artifact_identity.numeric_replay_verified=true},f=>{f.report.protocol_sha256="f".repeat(64)},
    f=>{f.report.flags.source_attribution_validated=true},f=>{f.report.flags.physical_validation=true},f=>{f.report.forecasts.earlier_truth_used=true},
    f=>{f.report.forecasts.inference_uses_only_last_two_positions=false},f=>{f.report.previously_viewed_earlier_positions=false},f=>{f.report.analysis_scope="INDEPENDENT_TEST"},
    f=>{f.report.forecasts.scenarios_per_group=24},f=>{f.report.forecasts.groups.reverse()},f=>{f.report.validation.planned_distinct_earlier_positions=6},
  ]){const f=fixture();mutate(f);reject(f)}
});

test("real-time ordering, finite coordinates and scenario coverage are validated",() => {
  for(const mutate of [
    f=>{f.report.forecasts.groups[0].observed_endpoint.time_utc="2022-06-01T05:00:00Z"},
    f=>{f.report.forecasts.groups[0].reverse_current.scenarios[0].track[1].time_utc="2022-06-01T06:05:00Z"},
    f=>{f.report.forecasts.groups[0].reverse_current.scenarios[0].track[1].latitude_deg=NaN},
    f=>{f.report.forecasts.groups[0].reverse_current.scenarios[1].scenario_id="center|zero"},
    f=>{f.report.forecasts.groups[0].reverse_current.coverage.completed_scenarios=24},
    f=>{f.report.forecasts.groups[0].reverse_current.earlier_candidates[0].points[0].latitude_deg+=.001},
    f=>{f.report.forecasts.groups[0].candidates[2].latitude_deg+=.001},
    f=>{f.report.validation.rows[1].earlier_target.latitude_deg+=.001},
    f=>{f.report.validation.rows[1].predicted_earlier.longitude_deg+=.001},
    f=>{f.report.validation.rows[0].error_m=null},
  ]){const f=fixture();mutate(f);reject(f)}
});

function partialFixture() {
  const f=fixture(),group=f.report.forecasts.groups[0],scenario=group.reverse_current.scenarios[0];
  Object.assign(scenario,{status:"PARTIAL",reason_code:"SYNTHETIC_MASK",completed_lookback_s:3600,track:scenario.track.slice(0,13)});
  Object.assign(group.candidates[2],{status:"PARTIAL",reason_code:"SYNTHETIC_MASK",latitude_deg:null,longitude_deg:null});
  Object.assign(group.reverse_current.coverage,{completed_scenarios:24,partial_scenarios:1});
  for(const row of group.reverse_current.earlier_candidates.filter(row=>row.lookback_hours>1)){row.points=row.points.filter(p=>p.scenario_id!=="center|zero");row.available_count=24}
  Object.assign(f.report.validation.rows[2],{status:"FORECAST_UNAVAILABLE",reason_code:"SYNTHETIC_MASK",error_m:null,predicted_earlier:null});
  Object.assign(f.report.validation,{scored_model_rows:5,primary_complete:false,primary_mean_earlier_position_error_m:null});
  return f;
}
test("partial paths retain known lookback points and planned counts, with null errors",() => {
  const f=partialFixture();validateOceanSourceEnvelope(f);assert.equal(f.report.forecasts.groups[0].reverse_current.earlier_candidates[0].available_count,25);
  assert.equal(f.report.forecasts.groups[0].reverse_current.earlier_candidates[2].available_count,24);assert.equal(f.report.validation.rows[2].error_m,null);
  f.report.validation.primary_mean_earlier_position_error_m=[];reject(f);
});

test("projection is equal-scale in metres and fixed across hidden/displayed layers",() => {
  const f=fixture(),p=oceanSourcePlot(f,GROUPS[0]);assert.ok(p);assert.equal(p.observation.x_m,0);assert.equal(p.observation.y_m,0);
  assert.equal(p.scenarios.length,25);assert.equal(p.earlier.length,3);assert.ok(p.domain.span>=100);assert.equal(oceanSourcePlot(f,"unknown"),null);
  const longitude=1/6371008.8/Math.cos(30*Math.PI/180)*180/Math.PI,latitude=1/6371008.8*180/Math.PI;
  f.report.forecasts.groups[0].reverse_current.scenarios[0].track[1]={time_utc:"2022-06-01T05:55:00Z",lookback_s:300,latitude_deg:30+latitude,longitude_deg:-70+longitude};
  const projected=oceanSourcePlot(f,GROUPS[0]).scenarios[0].points[1];assert.ok(Math.abs(projected.x_m-1)<1e-8);assert.ok(Math.abs(projected.y_m-1)<1e-8);
});

test("missing or nonadjacent samples never create connected paths",() => {
  const points=[{lookback_s:0},{lookback_s:300},null,{lookback_s:900},{lookback_s:1200},{lookback_s:2100}];
  assert.deepEqual(oceanSourceSegments(points).map(row=>row.map(p=>p.lookback_s)),[[0,300],[900,1200],[2100]]);
  assert.deepEqual(oceanSourceSegments([{lookback_s:0},{lookback_s:300},{lookback_s:300}]).map(row=>row.length),[2,1]);
});

test("bounded operator question carries only selected evidence pins and no earlier truth",() => {
  const f=fixture(),body=oceanSourceQuestion("  Explain the assumptions.  ",f);
  assert.deepEqual(Object.keys(body).sort(),["identity_sha256","protocol_sha256","question","report_sha256"]);
  assert.equal(body.question,"Explain the assumptions.");assert.doesNotMatch(JSON.stringify(body),/latitude|earlier_target|token|Bearer/);
  assert.throws(()=>oceanSourceQuestion(" ",f));assert.throws(()=>oceanSourceQuestion("a".repeat(2001),f));
});

test("stale requests, retries and unmount cancellation cannot publish old responses",() => {
  const gate=createOceanSourceRequests(),old=gate.begin();assert.equal(gate.begin(),null);gate.cancel();assert.equal(old.controller.signal.aborted,true);
  const fresh=gate.begin();assert.equal(gate.current(old),false);gate.finish(old);assert.equal(gate.current(fresh),true);
  fresh.controller.abort();assert.equal(gate.current(fresh),false);assert.equal(gate.owns(fresh),true);gate.finish(fresh);
  const last=gate.begin();gate.dispose();assert.equal(last.controller.signal.aborted,true);assert.equal(gate.begin(),null);
});

test("HTTP errors, excessive payloads and invalid JSON stay errors",async()=>{
  const f=fixture();assert.equal((await readVectorResponse(new Response(JSON.stringify(f)),validateOceanSourceEnvelope,5_000_000)).report.study_id,STUDY);
  for(const status of [401,404,409,503])await assert.rejects(readVectorResponse(new Response(JSON.stringify({detail:"Saved ocean source report unavailable"}),{status}),validateOceanSourceEnvelope),/Saved ocean source report unavailable/);
  await assert.rejects(readVectorResponse(new Response("{}",{headers:{"content-length":"5000001"}}),validateOceanSourceEnvelope,5_000_000),/exceeds/);
  await assert.rejects(readVectorResponse(new Response("no json"),validateOceanSourceEnvelope),/Unreadable/);
});

const require=createRequire(import.meta.url),loaded=new Map();
function component(path){const file=resolve(path);if(loaded.has(file))return loaded.get(file).exports;const mod={exports:{}};loaded.set(file,mod);const js=ts.transpileModule(readFileSync(file,"utf8"),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
  new Function("require","module","exports",js)(name=>{if(name.endsWith(".module.css"))return{__esModule:true,default:new Proxy({},{get:(_,key)=>String(key)})};if(name==="next/link")return{__esModule:true,default:({children,...props})=>React.createElement("a",props,children)};if(name==="./operator-provider")return{useOperator:()=>({token:""})};if(name.startsWith(".")){const base=resolve(dirname(file),name),dep=[base,`${base}.ts`,`${base}.tsx`].find(existsSync);if(dep)return component(dep)}return require(name)},mod,mod.exports);return mod.exports;}
const {OceanSource,OceanSourceResults,OceanSourceFigure,OceanSourceReview,OceanPipelineFigure,OceanPipelineTutorial}=component("app/components/ocean-source.tsx");

test("initial render requests explicit loading and blocks unauthenticated Chalk",()=>{
  const initial=renderToStaticMarkup(React.createElement(OceanSource,{api:""}));assert.match(initial,/Load ocean earlier-location example/);assert.doesNotMatch(initial,/data-ocean-source-layer|data-validation-truth/);
  const review=renderToStaticMarkup(React.createElement(OceanSourceReview,{api:"",envelope:fixture(),token:""}));assert.match(review,/<button[^>]+disabled=""/);assert.match(review,/Connect local operator access/);
});

test("rendered inference hides earlier truth until explicit validation and keeps fixed axes",()=>{
  const f=fixture(),all={nominal:true,scenarios:true,candidates:true};
  const render=(visible,showValidation=false)=>renderToStaticMarkup(React.createElement(OceanSourceFigure,{envelope:f,groupId:GROUPS[0],lookback:6,visible,showValidation,onToggle(){}}));
  const inference=render(all),hidden=render({nominal:false,scenarios:false,candidates:false}),validation=render(all,true);
  assert.doesNotMatch(inference,/data-validation-truth|six-hour reconstruction/);assert.match(validation,/data-validation-truth="true"/);
  assert.equal(inference.match(/data-domain="([^"]+)"/)[1],hidden.match(/data-domain="([^"]+)"/)[1]);
  assert.equal(inference.match(/data-domain="([^"]+)"/)[1],validation.match(/data-domain="([^"]+)"/)[1]);
  assert.equal((inference.match(/data-ocean-source-layer="scenarios"/g)??[]).length,24);assert.doesNotMatch(hidden,/data-ocean-source-layer/);
  const result=renderToStaticMarkup(React.createElement(OceanSourceResults,{api:"",envelope:f,token:""}));assert.match(result,/Show validation evidence/);assert.doesNotMatch(result,/Separate earlier-position validation|100 m<\/td>/);assert.match(result,/not twenty-five independent trials/);
});

test("provider-disabled STOP keeps the saved report and refuses fabricated citations",()=>{
  const f=fixture(),pin=f.artifact_identity;
  const answer={schema_version:1,kind:"OCEAN_SOURCE_RESEARCH_INVESTIGATION",scope:"READ_ONLY_POST_OUTCOME_EARLIER_POSITION_DIAGNOSTIC",analysis_scope:"POST_OUTCOME_EXPLORATORY",previously_viewed_earlier_positions:true,action:"STOP",explanation:"Chalk is unavailable; the saved numerical report remains readable.",evidence_ids:[],trace:[],provider:"chalk",live_model_response:false,research_report:f.report,artifact_identity:pin,...oceanSourceQuestion("Explain",f),numeric_replay_verified:false,store_written:false,hardware_actuation:false,physical_validation:false,source_attribution_validated:false,automatic_model_promotion:false,failure_code:"NOT_CONFIGURED"};
  validateOceanSourceAnswer(answer,f);answer.evidence_ids=[`ocean-source-report:${pin.report_sha256}`];assert.throws(()=>validateOceanSourceAnswer(answer,f));
});

function tutorialFixture() {
  const f=fixture(),anchor="2022-06-01T03:00:00Z",when=hour=>`2022-06-01T${String(hour).padStart(2,"0")}:00:00Z`;
  const geo=hour=>({time_utc:when(hour),latitude_deg:30+hour*.001,longitude_deg:-70+hour*.001});
  const groups=GROUPS.map(group_id=>({group_id,status:"COMPLETED",reason_code:null,raw_observations:[1,2,3].map(geo),connected_path:[1,2,3].map(geo),filtered_states:[1,2,3].map((hour,index)=>({...geo(hour),east_m:index*100,north_m:index*100,eastward_m_s:index===0?null:.1,northward_m_s:index===0?null:.1,status:["POSITION_ONLY","INITIALIZED","UPDATED"][index],covariance:index===0?null:Array.from({length:4},(_,i)=>Array.from({length:4},(_,j)=>i===j?1:0))})),filtered_anchor:geo(3),formula:{equation:"dX/dt = u(X,t) + b",current_east_north_m_s:[.05,.05],filtered_velocity_east_north_m_s:[.1,.1],residual_bias_east_north_m_s:[.05,.05]},backward:{status:"COMPLETED",reason_code:null,completed_lookback_s:10800,track:Array.from({length:37},(_,index)=>({latitude_deg:30+(3-index/12)*.001,longitude_deg:-70+(3-index/12)*.001,lookback_s:index*300,time_utc:new Date(Date.parse(anchor)-index*300000).toISOString().replace(".000Z","Z")}))},forward:{status:"COMPLETED",reason_code:null,completed_horizon_s:10800,track:Array.from({length:37},(_,index)=>({latitude_deg:30+(3+index/12)*.001,longitude_deg:-70+(3+index/12)*.001,elapsed_s:index*300,time_utc:new Date(Date.parse(anchor)+index*300000).toISOString().replace(".000Z","Z")}))}}));
  f.report.pipeline_tutorial={kind:"THREE_FIX_BIDIRECTIONAL_RESEARCH_WALKTHROUGH",forecasts:{group_ids:[...GROUPS],observation_times_utc:[1,2,3].map(when),anchor_time_utc:anchor,earlier_truth_used:false,later_truth_used:false,position_std_m:100,acceleration_spectral_density_m2_s3:1e-6,stages:["raw","connected","filtered","formula","branches"].map(id=>({id,title:id,formula:"A synthetic saved formula description."})),groups,limitations:["Synthetic display fixture; branches are hypotheses, not verified sources or capture."]},validation:{planned_rows:8,scored_rows:8,physical_validation:false,statistical_independence:false,rows:groups.flatMap(group=>[0,4,5,6].map(hour=>({group_id:group.group_id,direction:hour===0?"backward":"forward",time_utc:when(hour),status:"SCORED",reason_code:null,observed:{...geo(hour),latitude_deg:geo(hour).latitude_deg+.00001},predicted:geo(hour),error_m:1})))}};
  f.report.forecasts.pipeline_tutorial=f.report.pipeline_tutorial.forecasts;
  return f;
}

test("walkthrough accepts only the three allowed fixes and separates reserved earlier/later truth",()=>{
  const f=tutorialFixture();validateOceanSourceEnvelope(f);assert.equal(f.report.pipeline_tutorial.forecasts.groups[0].filtered_states[0].eastward_m_s,null);
  for(const mutate of [
    f=>{f.report.pipeline_tutorial.forecasts.later_truth_used=true},f=>{f.report.pipeline_tutorial.forecasts.earlier_truth_used=true},
    f=>{f.report.pipeline_tutorial.forecasts.groups[0].raw_observations[0].time_utc="2022-06-01T00:00:00Z"},
    f=>{f.report.pipeline_tutorial.forecasts.groups[0].filtered_states[0].eastward_m_s=.1},
    f=>{f.report.pipeline_tutorial.forecasts.groups[0].forward.track[1].time_utc="2022-06-01T02:55:00Z"},
    f=>{f.report.pipeline_tutorial.validation.rows[1].predicted.latitude_deg+=.01},
    f=>{f.report.pipeline_tutorial.validation.scored_rows=7},
  ]){const changed=tutorialFixture();mutate(changed);reject(changed)}
});

test("walkthrough rejects disconnected anchors, inconsistent saved formulas and unsupported durations",()=>{
  for(const mutate of [
    f=>{f.report.pipeline_tutorial.forecasts.groups[0].forward.track[0].longitude_deg+=.001},
    f=>{f.report.pipeline_tutorial.forecasts.groups[0].filtered_anchor=null},
    f=>{f.report.pipeline_tutorial.forecasts.groups[0].filtered_states.pop()},
    f=>{f.report.pipeline_tutorial.forecasts.groups[0].formula.filtered_velocity_east_north_m_s=[.2,.1]},
    f=>{f.report.pipeline_tutorial.forecasts.groups[0].formula.residual_bias_east_north_m_s=[0,0]},
    f=>{f.report.pipeline_tutorial.forecasts.groups[0].formula.current_east_north_m_s=null},
    f=>{f.report.pipeline_tutorial.forecasts.groups[0].backward.status="UNSUPPORTED";f.report.pipeline_tutorial.forecasts.groups[0].backward.reason_code="MASK"},
    f=>{f.report.pipeline_tutorial.forecasts.groups[0].forward=null},
  ]){const changed=tutorialFixture();mutate(changed);reject(changed)}
});

test("five visual stages introduce observed, connected, filtered and hypothesis layers in order",()=>{
  const pipeline=tutorialFixture().report.pipeline_tutorial,visible={raw:true,filtered:true,branches:true};
  const frames=Array.from({length:5},(_,step)=>renderToStaticMarkup(React.createElement(OceanPipelineFigure,{pipeline,groupId:GROUPS[0],step,visible,showValidation:false,onToggle(){}})));
  assert.match(frames[0],/data-pipeline-layer="observed"/);assert.doesNotMatch(frames[0],/data-pipeline-layer="connected|data-pipeline-layer="filtered|data-pipeline-layer="hypotheses/);
  assert.match(frames[1],/data-pipeline-layer="connected"/);assert.doesNotMatch(frames[1],/data-pipeline-layer="filtered/);
  assert.match(frames[2],/data-pipeline-layer="filtered"/);assert.doesNotMatch(frames[3],/data-pipeline-layer="hypotheses/);
  assert.match(frames[4],/data-pipeline-branch="backward"/);assert.match(frames[4],/data-pipeline-branch="forward"/);
  assert.equal(new Set(frames.map(html=>html.match(/data-domain="([^"]+)"/)[1])).size,1);
  for(const html of frames)assert.doesNotMatch(html,/data-validation-truth/);
  const checked=renderToStaticMarkup(React.createElement(OceanPipelineFigure,{pipeline,groupId:GROUPS[0],step:4,visible,showValidation:true,onToggle(){}}));
  assert.equal((checked.match(/data-validation-truth="true"/g)??[]).length,4);
  assert.equal(checked.match(/data-domain="([^"]+)"/)[1],frames[0].match(/data-domain="([^"]+)"/)[1]);
  assert.ok(oceanPipelinePlot(pipeline,GROUPS[0]));
});

test("walkthrough initially waits for manual steps and discloses retrospective scope",()=>{
  const pipeline=tutorialFixture().report.pipeline_tutorial,html=renderToStaticMarkup(React.createElement(OceanPipelineTutorial,{pipeline}));
  assert.match(html,/Play walkthrough/);assert.match(html,/Next step/);assert.match(html,/aria-current="step"/);assert.match(html,/Step 1 of 5/);
  assert.doesNotMatch(html,/data-pipeline-branch|Separate walkthrough validation/);
});

test("branch scrub reveals saved points in both directions without changing the fixed domain or leaking truth",()=>{
  const pipeline=tutorialFixture().report.pipeline_tutorial,visible={raw:true,filtered:true,branches:true};
  const render=branchMinutes=>renderToStaticMarkup(React.createElement(OceanPipelineFigure,{pipeline,groupId:GROUPS[1],step:4,visible,showValidation:false,branchMinutes,onToggle(){}}));
  const frames=[0,60,180].map(render);
  assert.equal(new Set(frames.map(html=>html.match(/data-domain="([^"]+)"/)[1])).size,1);
  for(const [index,html] of frames.entries()){
    for(const direction of ["backward","forward"]){
      const branch=html.match(new RegExp(`<g data-pipeline-branch="${direction}">([\\s\\S]*?)</g>`))[1];
      if(index===0)assert.doesNotMatch(branch,/<polyline/);
      else assert.equal(branch.match(/points="([^"]+)"/)[1].split(" ").length,index===1?13:37);
    }
    assert.doesNotMatch(html,/data-validation-truth/);
  }
  const hidden=renderToStaticMarkup(React.createElement(OceanPipelineFigure,{pipeline,groupId:GROUPS[0],step:0,visible:{raw:false,filtered:true,branches:true},showValidation:false,onToggle(){}}));
  assert.match(hidden,/All currently available layers are hidden/);assert.doesNotMatch(hidden,/data-pipeline-layer/);
});

test("a partially supported branch retains available outputs without inventing the missing end",()=>{
  const f=tutorialFixture(),pipeline=f.report.pipeline_tutorial,group=pipeline.forecasts.groups[0];
  Object.assign(group,{status:"PARTIAL",reason_code:"SYNTHETIC_MASK"});
  Object.assign(group.forward,{status:"PARTIAL",reason_code:"SYNTHETIC_MASK",completed_horizon_s:3600,track:group.forward.track.slice(0,13)});
  for(const row of pipeline.validation.rows.filter(row=>row.group_id===GROUPS[0]&&["2022-06-01T05:00:00Z","2022-06-01T06:00:00Z"].includes(row.time_utc)))Object.assign(row,{status:"FORECAST_UNAVAILABLE",reason_code:"SYNTHETIC_MASK",error_m:null,predicted:null});
  pipeline.validation.scored_rows=6;validateOceanSourceEnvelope(f);
  const html=renderToStaticMarkup(React.createElement(OceanPipelineFigure,{pipeline,groupId:GROUPS[0],step:4,visible:{raw:true,filtered:true,branches:true},showValidation:false,branchMinutes:180,onToggle(){}}));
  const forward=html.match(/<g data-pipeline-branch="forward">([\s\S]*?)<\/g>/)[1];
  assert.equal(forward.match(/points="([^"]+)"/)[1].split(" ").length,13);
  assert.match(html,/Saved time: 2022-06-01T04:00:00Z/);
});

test("playback advances one bounded pass, pause/disposal reject old timer callbacks",()=>{
  let id=0;const callbacks=new Map(),cancelled=[],steps=[],statuses=[];
  const play=createOceanPipelinePlayback({schedule:callback=>{callbacks.set(++id,callback);return id;},cancel:id=>cancelled.push(id),onStep:index=>steps.push(index),onPlaying:playing=>statuses.push(playing)});
  assert.equal(play.start(0),true);assert.equal(play.start(0),false);const stale=callbacks.get(1);play.pause();assert.deepEqual(statuses,[true,false]);
  play.start(1);stale();assert.deepEqual(steps,[0,1]);assert.equal(callbacks.size,2);
  callbacks.get(2)();callbacks.get(3)();callbacks.get(4)();assert.deepEqual(steps,[0,1,2,3,4]);assert.equal(callbacks.size,4);assert.equal(statuses.at(-1),false);
  play.start(4);assert.equal(steps.at(-1),0);const old=callbacks.get(5);play.dispose();old();assert.equal(steps.at(-1),0);assert.equal(play.start(0),false);
  assert.ok(cancelled.includes(1));assert.ok(cancelled.includes(5));
});

test("walkthrough partial and missing-truth rows retain null errors and original denominators",()=>{
  const f=tutorialFixture(),tutorial=f.report.pipeline_tutorial,group=tutorial.forecasts.groups[0];
  Object.assign(group,{status:"PARTIAL",reason_code:"SYNTHETIC_MASK"});Object.assign(group.forward,{status:"PARTIAL",reason_code:"SYNTHETIC_MASK",completed_horizon_s:3600,track:group.forward.track.slice(0,13)});
  for(const index of [2,3])Object.assign(tutorial.validation.rows[index],{status:"FORECAST_UNAVAILABLE",reason_code:"SYNTHETIC_MASK",predicted:null,error_m:null});
  tutorial.validation.scored_rows=6;validateOceanSourceEnvelope(f);assert.equal(tutorial.validation.planned_rows,8);
  Object.assign(tutorial.validation.rows[0],{observed:null,predicted:null,error_m:null,status:"TRUTH_UNAVAILABLE",reason_code:"SYNTHETIC_MISSING_TRUTH"});tutorial.validation.scored_rows=5;validateOceanSourceEnvelope(f);
});

const savedDirectory=new URL("../../data/research/ocean-source-v1/",import.meta.url);
test("actual published saved artifacts render the complete walkthrough without rerunning science",{skip:!existsSync(new URL("evaluation.json",savedDirectory))},()=>{
  const json=name=>JSON.parse(readFileSync(new URL(name,savedDirectory),"utf8")),rawIdentity=json("identity.json");
  for(const [name,key]of [["evaluation.json","report_sha256"],["protocol.json","protocol_sha256"],["forecasts.json","forecast_file_sha256"],["pipeline-forecasts.json","pipeline_forecast_file_sha256"]])assert.equal(createHash("sha256").update(readFileSync(new URL(name,savedDirectory))).digest("hex"),rawIdentity[key]);
  const identityHash=createHash("sha256").update(readFileSync(new URL("identity.json",savedDirectory))).digest("hex");
  assert.equal(identityHash,readFileSync(new URL("identity.sha256",savedDirectory),"utf8").trim());
  const envelope={report:json("evaluation.json"),artifact_identity:{...rawIdentity,identity_sha256:identityHash,integrity_verified:true,external_result_pin_verified:true,numeric_replay_verified:false,verification_scope:"SAVED_BYTES_AND_LINEAGE_NOT_NUMERIC_REPLAY"}};
  validateOceanSourceEnvelope(envelope);assert.ok(envelope.report.pipeline_tutorial);
  const html=renderToStaticMarkup(React.createElement(OceanSourceResults,{api:"",envelope,token:""}));assert.match(html,/Step 1 of 5/);assert.match(html,/06:00 endpoint/);assert.doesNotMatch(html,/data-validation-truth/);
});
