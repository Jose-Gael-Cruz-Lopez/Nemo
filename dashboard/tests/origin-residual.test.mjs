import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve, dirname } from "node:path";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import { ORIGIN_GROUPS, ORIGIN_MODELS, ORIGIN_PINS, createOriginRequestGate, originDisplacement, originPlot, originQuestion, originSegments, validateOriginAnswer, validateOriginEnvelope } from "../app/components/origin-residual-state.ts";
import { readVectorResponse } from "../app/components/vector-diagnostic-state.ts";

// Read the actual committed artifacts; never run a scorer, reader import or provider.
const directory = new URL("../../data/research/origin-residual-v1/",import.meta.url);
const json = file => JSON.parse(readFileSync(new URL(file,directory),"utf8"));
const saved = {report:json("evaluation.json"),forecasts:json("forecasts.json").forecasts,
  artifact_identity:{...json("identity.json"),identity_sha256:ORIGIN_PINS.identity_sha256,integrity_verified:true,external_result_pin_verified:true,numeric_replay_verified:false,verification_scope:"SAVED_BYTES_AND_LINEAGE_NOT_NUMERIC_REPLAY"}};
const fixture = () => structuredClone(saved);
const reject = value => assert.throws(() => validateOriginEnvelope(value),/No result was accepted/);

// Invented display-defence variants, not new scientific results. Stored numerical
// errors are never recomputed. The real backend would reject changed artifact bytes.
function gapFixture(target = false) {
  const f = fixture(), s = f.report.scores, group = s.groups[0];
  const affected = target ? [0,1,2,3] : [3];
  for (const index of affected) {
    const c = group.candidates[index], cell = c.cells[1];
    if (target) Object.assign(cell,{target_latitude_deg:null,target_longitude_deg:null,score_status:"TARGET_UNAVAILABLE",error_m:null});
    else {
      const forecast = f.forecasts.groups[0].candidates[index];
      Object.assign(forecast,{status:"PARTIAL",reason_code:"SYNTHETIC_GAP",available_count:5});
      Object.assign(forecast.cells[1],{forecast_status:"UNAVAILABLE",forecast_reason_code:"SYNTHETIC_GAP",latitude_deg:null,longitude_deg:null});
      Object.assign(cell,forecast.cells[1],{score_status:"FORECAST_UNAVAILABLE",error_m:null});
      Object.assign(c,{prediction_status:"PARTIAL",prediction_reason_code:"SYNTHETIC_GAP"});
    }
    Object.assign(c.metrics,{scored_count:5,coverage_complete:false,full_horizon_ade_m:null});
    Object.assign(s.models[index].metrics,{scored_count:11,coverage_complete:false,full_horizon_ade_m:null});
  }
  Object.assign(s,{scored_cell_count:48-affected.length,primary_common_cohort_complete:false,primary_equal_id_macro_results:null});
  for (const pair of s.paired_comparisons) {
    pair.analysis_scope="SECONDARY_COMMON_AVAILABLE_CELLS";
    if (affected.some(index => [pair.model_a,pair.model_b].includes(ORIGIN_MODELS[index]))) {
      pair.cells=pair.cells.filter(cell => cell.group_id!==ORIGIN_GROUPS[0]||cell.horizon_hours!==2);
      pair.common_scored_count=pair.cells.length;pair.coverage_complete=false;
    }
  }
  return f;
}

test("actual saved envelope retains four candidates, two groups and twelve already-viewed targets",()=>{
  for(const [file,pin] of [["evaluation.json","report_sha256"],["forecasts.json","forecast_file_sha256"],["protocol.json","protocol_sha256"],["identity.json","identity_sha256"]])
    assert.equal(createHash("sha256").update(readFileSync(new URL(file,directory))).digest("hex"),ORIGIN_PINS[pin]);
  const f=fixture(),before=JSON.stringify(f);assert.equal(validateOriginEnvelope(f),f);
  assert.equal(JSON.stringify(f),before);assert.equal(f.report.scores.scored_cell_count,48);
  assert.deepEqual(f.forecasts.model_ids,ORIGIN_MODELS);assert.deepEqual(f.forecasts.group_ids,ORIGIN_GROUPS);
  assert.equal(f.report.scores.planned_distinct_target_count,12);
  assert.equal(f.report.scores.primary_equal_id_macro_results[3].equal_id_macro_ade_m,1030.0494632017758);
  assert.equal(f.artifact_identity.numeric_replay_verified,false);
});

test("literal identities, scientific scope, planned denominators and chronology are required",()=>{
  for(const mutate of [
    f=>{f.artifact_identity.identity_sha256="f".repeat(64)},f=>{f.artifact_identity.report_sha256="f".repeat(64)},
    f=>{f.report.protocol_sha256="f".repeat(64)},f=>{f.forecasts.forecast_sha256=f.artifact_identity.forecast_file_sha256},
    f=>{f.artifact_identity.external_result_pin_verified=false},f=>{f.artifact_identity.numeric_replay_verified=true},
    f=>{f.report.analysis_scope="UNSEEN_HOLDOUT"},f=>{f.report.previously_viewed_target_outcomes=false},
    f=>{f.report.scores.automatic_model_promotion=true},f=>{f.forecasts.future_positions_used=true},
    f=>{f.report.scores.statistical_independence=true},f=>{f.report.scores.planned_cell_count=47},
    f=>{f.forecasts.groups[0].candidates[2].advection.plastic_motion_validated=true},
    f=>{f.report.scores.planned_distinct_target_count=48},f=>{f.report.scored_at_utc="2026-02-30T00:00:00Z"},
    f=>{f.report.scored_at_utc="2022-01-01T00:00:00Z"},f=>{f.report.source_artifact_pins={}},
  ]){const f=fixture();mutate(f);reject(f)}
});

test("swapped group/model/hour, forecast disagreement and inconsistent shared targets fail closed",()=>{
  for(const mutate of [
    f=>f.forecasts.groups.reverse(),f=>f.report.scores.models.reverse(),f=>f.forecasts.groups[0].candidates.reverse(),
    f=>{f.report.scores.groups[0].candidates[1].cells[0].model_id="stationary"},
    f=>{f.report.scores.groups[0].candidates[0].cells[0].horizon_hours=2},
    f=>{f.forecasts.groups[0].candidates[0].cells[0].latitude_deg+=.001},
    f=>{f.report.scores.groups[0].candidates[1].cells[0].target_latitude_deg+=.001},
    f=>{f.report.scores.groups[0].target_issues=[{}]},
    f=>{f.forecasts.groups[0].candidates[3].residual_units="cm/s"},
  ]){const f=fixture();mutate(f);reject(f)}
});

test("nonfinite, half-null, out-of-range coordinates and malformed stored metrics are rejected",()=>{
  for(const mutate of [
    f=>{f.report.scores.groups[0].candidates[0].cells[0].error_m=NaN},
    f=>{f.report.scores.groups[0].candidates[0].cells[0].error_m=-1},
    f=>{f.report.scores.groups[0].candidates[0].cells[0].target_latitude_deg=null},
    f=>{f.report.scores.groups[0].candidates[0].cells[0].target_longitude_deg=181},
    f=>{f.report.scores.models[0].metrics.available_cell_mean_error_m=Infinity},
    f=>{f.report.scores.groups[0].candidates[0].metrics.endpoint_fde_m=null},
    f=>{f.report.scores.primary_equal_id_macro_results[0].equal_id_macro_fde_m="42"},
    f=>{f.forecasts.groups[0].candidates[3].residual_east_north_m_s=[null,.2]},
  ]){const f=fixture();mutate(f);reject(f)}
});

test("forecast gaps keep available targets, final FDE and full planned denominator while withholding primary",()=>{
  const f=gapFixture();validateOriginEnvelope(f);const c=f.report.scores.groups[0].candidates[3];
  assert.equal(c.cells[1].score_status,"FORECAST_UNAVAILABLE");assert.ok(Number.isFinite(c.cells[1].target_latitude_deg));
  assert.equal(c.metrics.full_horizon_ade_m,null);assert.equal(c.metrics.endpoint_fde_m,saved.report.scores.groups[0].candidates[3].cells[5].error_m);
  assert.equal(f.report.scores.scored_cell_count,47);assert.equal(f.report.scores.planned_cell_count,48);
  assert.equal(f.report.scores.primary_equal_id_macro_results,null);
  for(const mutate of [x=>{x.report.scores.primary_common_cohort_complete=true},x=>{x.report.scores.primary_equal_id_macro_results=saved.report.scores.primary_equal_id_macro_results},x=>{x.report.scores.groups[0].candidates[3].metrics.full_horizon_ade_m=0}]){const p=gapFixture();mutate(p);reject(p)}
});

test("target gaps stay aligned across candidates and are never bridged by paths or arrows",()=>{
  const f=gapFixture(true);validateOriginEnvelope(f);const plot=originPlot(f,ORIGIN_GROUPS[0]);
  assert.equal(plot.series.recorded[2],null);assert.deepEqual(originSegments(plot.series.recorded).map(s=>s.map(p=>p.hour)),[[0,1],[3,4,5,6]]);
  assert.equal(originDisplacement(plot.series.recorded,2),null);assert.equal(originDisplacement(plot.series.recorded,3),null);
  assert.deepEqual(originDisplacement(plot.series.recorded,4).map(p=>p.hour),[3,4]);
  for(const hour of [0,NaN,.5,7])assert.equal(originDisplacement(plot.series.recorded,hour),null);
});

test("a failed twenty-four-row context stays unsupported without inventing a valid origin",()=>{
  const f=fixture(),fg=f.forecasts.groups[0],s=f.report.scores,g=s.groups[0];fg.context_count=24;fg.origin_position=null;
  for(let mi=0;mi<4;mi++){
    const raw=fg.candidates[mi],c=g.candidates[mi];Object.assign(raw,{status:"UNSUPPORTED",reason_code:"CONTEXT_COUNT_INVALID",available_count:0,completed_horizon_s:0});
    Object.assign(c,{prediction_status:raw.status,prediction_reason_code:raw.reason_code});
    for(let hour=0;hour<6;hour++){Object.assign(raw.cells[hour],{forecast_status:"UNAVAILABLE",forecast_reason_code:raw.reason_code,latitude_deg:null,longitude_deg:null});Object.assign(c.cells[hour],raw.cells[hour],{score_status:"FORECAST_UNAVAILABLE",error_m:null});}
    Object.assign(c.metrics,{scored_count:0,coverage_complete:false,available_cell_mean_error_m:null,full_horizon_ade_m:null,endpoint_fde_m:null});
    Object.assign(s.models[mi].metrics,{scored_count:6,coverage_complete:false,full_horizon_ade_m:null});
  }
  Object.assign(s,{scored_cell_count:24,primary_common_cohort_complete:false,primary_equal_id_macro_results:null});
  for(const pair of s.paired_comparisons){pair.cells=pair.cells.filter(cell=>cell.group_id!==ORIGIN_GROUPS[0]);Object.assign(pair,{analysis_scope:"SECONDARY_COMMON_AVAILABLE_CELLS",common_scored_count:6,coverage_complete:false});}
  validateOriginEnvelope(f);const plot=originPlot(f,ORIGIN_GROUPS[0]);assert.equal(plot.originAvailable,false);assert.equal(plot.series.stationary.filter(Boolean).length,0);assert.equal(plot.series.recorded.filter(Boolean).length,6);
  fg.origin_position=saved.forecasts.groups[0].origin_position;reject(f);
});

test("display projection preserves both groups and outlying saved targets without scientific re-scoring",()=>{
  const f=fixture(),before=JSON.stringify(f.report.scores);
  for(const group of ORIGIN_GROUPS){const p=originPlot(f,group);assert.equal(Object.keys(p.series).length,5);assert.ok(p.domain.span>100);assert.equal(p.series.recorded.length,7)}
  assert.equal(originPlot(f,"unrelated"),null);assert.equal(JSON.stringify(f.report.scores),before);
  for(const c of f.report.scores.groups[0].candidates)c.cells[5].target_latitude_deg=31.2;
  validateOriginEnvelope(f);assert.ok(originPlot(f,ORIGIN_GROUPS[0]).domain.span>130000);
  assert.equal(JSON.stringify(f.report.scores.primary_equal_id_macro_results),JSON.stringify(saved.report.scores.primary_equal_id_macro_results));
});

function answer(envelope=fixture()){
  const i=envelope.artifact_identity,r=envelope.report,s=r.scores,ids=[`origin-residual-report:${i.report_sha256}`,`origin-residual-protocol:${i.protocol_sha256}`];
  const keys=["model_a","model_b","planned_common_cell_count","common_scored_count","coverage_complete","analysis_scope","mean_delta_a_minus_b_m"];
  const compact={kind:r.kind,study_id:i.study_id,analysis_scope:r.analysis_scope,previously_viewed_target_outcomes:true,report_sha256:i.report_sha256,protocol_sha256:i.protocol_sha256,identity_sha256:i.identity_sha256,artifact_verification:i,source_artifact_pins:r.source_artifact_pins,source_acquisition_lineage:r.source_acquisition_lineage,method_source_sha256:r.method_source_sha256,
    coverage:{planned_group_count:2,planned_model_track_count:8,planned_cell_count:48,scored_cell_count:s.scored_cell_count,planned_distinct_target_count:12,primary_common_cohort_complete:s.primary_common_cohort_complete},models:s.models,primary_equal_id_macro_results:s.primary_equal_id_macro_results,
    groups:s.groups.map((g,gi)=>({group_id:g.group_id,target_issues:g.target_issues,candidates:g.candidates.map((c,mi)=>{const f=envelope.forecasts.groups[gi].candidates[mi];return{model_id:c.model_id,prediction_status:c.prediction_status,prediction_reason_code:c.prediction_reason_code,metrics:c.metrics,forecast_available_count:f.available_count,residual_east_north_m_s:f.residual_east_north_m_s??null,source_field_sha256:f.source_field_sha256??null,derived_field_sha256:f.derived_field_sha256??null}})})),
    paired_comparisons:s.paired_comparisons.map(row=>Object.fromEntries(keys.map(key=>[key,row[key]]))),
    model_definition:{residual_transport:"constant_local_east_north_components",current_depth_m:15,learned_parameters:0,solver:"unchanged bounded knot-aligned WGS84 RK4",source_study_changed:false},scientific_flags:Object.fromEntries(["statistical_independence","automatic_winner_selected","automatic_model_promotion","operational_forecast_skill_verified","physical_validation","heldout_tuning","global_training"].map(key=>[key,false])),limitations:s.limitations};
  return structuredClone({schema_version:1,kind:"ORIGIN_RESIDUAL_RESEARCH_INVESTIGATION",scope:"READ_ONLY_POST_OUTCOME_EXPLORATORY_DIAGNOSTIC",analysis_scope:r.analysis_scope,previously_viewed_target_outcomes:true,action:"REPORT",explanation:"This is descriptive development on previously viewed buoy positions. A new frozen cohort and independent measurements are needed.",evidence_ids:ids,trace:[{tool:"get_study_evidence",arguments:{},result:{ok:true,evidence_ids:ids,origin_residual_diagnostic:compact},read_origin:"model_requested"}],provider:"chalk",live_model_response:true,research_report:r,artifact_identity:i,report_sha256:i.report_sha256,protocol_sha256:i.protocol_sha256,identity_sha256:i.identity_sha256,numeric_replay_verified:false,store_written:false,hardware_actuation:false,physical_validation:false,automatic_model_promotion:false});
}

test("Chalk REPORT and a grounded live STOP bind the exact report/protocol/identity and compact trace",()=>{
  const f=fixture(),a=answer(f);assert.equal(validateOriginAnswer(a,f),a);
  a.research_report=Object.fromEntries(Object.entries(a.research_report).reverse());validateOriginAnswer(a,f);
  a.action="STOP";a.evidence_ids=[];validateOriginAnswer(a,f);
  assert.deepEqual(Object.keys(originQuestion("  Explain this  ",f)).sort(),["identity_sha256","protocol_sha256","question","report_sha256"]);
  assert.equal(originQuestion(" Explain this ",f).question,"Explain this");
  for(const question of [" ","x".repeat(2001)])assert.throws(()=>originQuestion(question,f));
});

test("stale, forged, action-capable or contradictory Chalk responses are rejected",()=>{
  for(const mutate of [
    a=>{a.identity_sha256="f".repeat(64)},a=>{a.report_sha256="f".repeat(64)},a=>{a.evidence_ids=[]},a=>{a.trace=[]},
    a=>{a.trace[0].tool="collect_plastic"},a=>{a.trace[0].arguments={group_id:ORIGIN_GROUPS[0]}},
    a=>{a.trace[0].result.origin_residual_diagnostic.coverage.scored_cell_count=47},
    a=>{a.trace[0].result.origin_residual_diagnostic.groups[0].candidates[3].residual_east_north_m_s[0]+=.1},
    a=>{a.trace[0].result.origin_residual_diagnostic.scientific_flags.physical_validation=true},
    a=>{a.trace[0].result.origin_residual_diagnostic.artifact_verification.numeric_replay_verified=true},
    a=>{a.research_report.scores.limitations.push("Changed after selection")},a=>{a.explanation="A model improved by 42 percent."},
    a=>{a.failure_code="NOT_CONFIGURED"},a=>{a.hardware_actuation=true},a=>{a.provider="direct_gemini"},
  ]){const a=answer();mutate(a);assert.throws(()=>validateOriginAnswer(a,fixture()),/No result was accepted/)}
});

test("disabled/provider STOP remains non-live, citation-free and separate from saved numerical evidence",()=>{
  const f=fixture(),a=answer(f);Object.assign(a,{action:"STOP",live_model_response:false,evidence_ids:[],trace:[],failure_code:"NOT_CONFIGURED",explanation:"Chalk is not configured; saved evidence remains available."});
  validateOriginAnswer(a,f);assert.equal(a.research_report.scores.scored_cell_count,48);
  a.evidence_ids=[`origin-residual-report:${ORIGIN_PINS.report_sha256}`];assert.throws(()=>validateOriginAnswer(a,f));
  a.evidence_ids=[];a.trace=answer(f).trace;a.failure_code="PROVIDER_HTTP_ERROR";a.provider_status_code=401;validateOriginAnswer(a,f);
});

test("request gates abort obsolete loads/reviews and prevent late results or duplicate submissions",()=>{
  const gate=createOriginRequestGate(),old=gate.begin();assert.equal(gate.begin(),null);gate.cancel();assert.equal(old.controller.signal.aborted,true);
  const current=gate.begin();assert.equal(gate.current(old),false);assert.equal(gate.current(current),true);gate.finish(old);assert.equal(gate.current(current),true);
  current.controller.abort();assert.equal(gate.current(current),false);assert.equal(gate.owns(current),true);gate.finish(current);
  const last=gate.begin();gate.dispose();assert.equal(last.controller.signal.aborted,true);assert.equal(gate.current(last),false);assert.equal(gate.begin(),null);
});

test("bounded real-payload reads retain HTTP failures and reject oversize or malformed responses",async()=>{
  const raw=JSON.stringify(fixture());assert.equal((await readVectorResponse(new Response(raw),validateOriginEnvelope,5_000_000)).report.scores.scored_cell_count,48);
  for(const status of [401,404,409,503])await assert.rejects(readVectorResponse(new Response(JSON.stringify({detail:"Pinned exploratory report unavailable"}),{status}),validateOriginEnvelope),/Pinned exploratory report unavailable/);
  await assert.rejects(readVectorResponse(new Response(raw,{headers:{"content-length":"5000001"}}),validateOriginEnvelope,5_000_000),/exceeds/);
  await assert.rejects(readVectorResponse(new Response("not json"),validateOriginEnvelope),/Unreadable/);
});

const require=createRequire(import.meta.url),loaded=new Map();
function component(path){const file=resolve(path);if(loaded.has(file))return loaded.get(file).exports;const mod={exports:{}};loaded.set(file,mod);const js=ts.transpileModule(readFileSync(file,"utf8"),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
  new Function("require","module","exports",js)(name=>{if(name.endsWith(".module.css"))return{__esModule:true,default:new Proxy({},{get:(_,key)=>String(key)})};if(name==="next/link")return{__esModule:true,default:({children,...props})=>React.createElement("a",props,children)};if(name==="./operator-provider")return{useOperator:()=>({token:""})};if(name.startsWith(".")){const base=resolve(dirname(file),name),dependency=[base,`${base}.ts`,`${base}.tsx`].find(existsSync);if(dependency)return component(dependency)}return require(name)},mod,mod.exports);return mod.exports;}
const {OriginResidualStudy,OriginResidualResults,OriginResidualFigure,OriginResidualReview}=component("app/components/origin-residual-study.tsx");

test("initial card is explicit-load only and unauthenticated Chalk has a disabled control",()=>{
  const initial=renderToStaticMarkup(React.createElement(OriginResidualStudy,{api:""}));assert.match(initial,/Load drift-offset study/);assert.doesNotMatch(initial,/1030|1,030|Recorded buoy/);
  const review=renderToStaticMarkup(React.createElement(OriginResidualReview,{api:"",envelope:fixture(),token:""}));assert.match(review,/<button[^>]+disabled=""/);assert.match(review,/Connect local operator access/);
  const lab=readFileSync("app/components/real-data-lab.tsx","utf8");assert.ok(lab.indexOf("<OriginResidualStudy")>lab.indexOf("<details className=\"card\"><summary>Research details"));
});

test("figure toggles retain a fixed equal-axis domain, five labeled layers and gap-safe arrows",()=>{
  const f=fixture(),all={recorded:true,stationary:true,last_drift:true,current_only:true,origin_residual_current:true};
  const render=visible=>renderToStaticMarkup(React.createElement(OriginResidualFigure,{envelope:f,groupId:ORIGIN_GROUPS[0],visible,hour:6,arrows:true,onToggle(){}}));
  const full=render(all),hidden=render(Object.fromEntries(Object.keys(all).map(id=>[id,false])));
  assert.equal(full.match(/data-domain="([^"]+)"/)[1],hidden.match(/data-domain="([^"]+)"/)[1]);assert.equal((full.match(/type="checkbox"/g)??[]).length,5);
  assert.equal((full.match(/data-origin-series=/g)??[]).length,5);assert.equal((hidden.match(/data-origin-series=/g)??[]).length,0);assert.match(full,/adjacent-endpoint displacement/);assert.match(hidden,/No paths selected/);
  for(const groupId of ORIGIN_GROUPS){const html=renderToStaticMarkup(React.createElement(OriginResidualFigure,{envelope:f,groupId,visible:all,hour:3,arrows:false,onToggle(){}}));assert.match(html,new RegExp(groupId));}
});

test("rendered results explain post-outcome scope and partial primary withholding without a winner claim",()=>{
  const full=renderToStaticMarkup(React.createElement(OriginResidualResults,{api:"",envelope:fixture(),token:""}));assert.match(full,/48 \/ 48/);assert.match(full,/12 reused processed NOAA positions/);assert.match(full,/outcomes already viewed/);assert.match(full,/1,030\.0?5?|1,030/);assert.doesNotMatch(full,/Best model|Operational winner/);
  const partial=renderToStaticMarkup(React.createElement(OriginResidualResults,{api:"",envelope:gapFixture(),token:""}));assert.match(partial,/47 \/ 48/);assert.match(partial,/Primary ADE and FDE are withheld/);assert.ok((partial.match(/Withheld/g)??[]).length>=8);
});
