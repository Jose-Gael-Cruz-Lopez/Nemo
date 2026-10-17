import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { freshStudyIdentity,validateFreshStudy,validateFreshAnswer } from "../app/components/fresh-drifter-study-state.ts";
import { readVectorResponse } from "../app/components/vector-diagnostic-state.ts";

// Actual verified offline response captured after the v2 acquisition and before
// its first frozen numerical evaluation. No successful model outcomes invented.
const text=readFileSync(new URL("./fixtures/fresh-drifter-pending-report.json",import.meta.url),"utf8"), frozen=JSON.parse(text);
const fixture=()=>structuredClone(frozen), reject=r=>assert.throws(()=>validateFreshStudy(r),/No result was accepted/);
function chalkFixture(report=fixture()) {
 const digest="a".repeat(64),ids=[`fresh-study:${digest}`,`fresh-protocol:${report.protocol_sha256}`];
 const pick=(v,keys)=>Object.fromEntries(keys.filter(k=>Object.hasOwn(v,k)).map(k=>[k,v[k]])),modelKeys=["id","label","status","metrics","reason_codes","complete_groups"];
 const study={snapshot_report_sha256:digest,protocol_sha256:report.protocol_sha256,kind:report.kind,design_status:report.design_status,status:report.status,coverage:report.coverage,models:report.models.map(m=>pick(m,modelKeys)),groups:report.groups.map(g=>({...pick(g,["block_id","slot","drifter_id","wmo","status","reason_codes"]),models:g.models.map(m=>pick(m,modelKeys))})),provenance:report.provenance,flags:report.flags,model_definitions:report.protocol.models,pre_outcome_amendment:report.protocol.pre_outcome_amendment??null,limitations:report.limitations};
 // Mocked gateway conclusion only; the underlying deterministic study is the
 // actual pending snapshot, not a synthetic success or a live provider claim.
 return {schema_version:1,kind:"FRESH_DRIFTER_RESEARCH_INVESTIGATION",scope:"READ_ONLY_FRESH_STUDY",action:"REPORT",evidence_ids:ids,explanation:"Acquisition receipts are available, while the frozen evaluation remains pending. These data do not establish physical benefit.",trace:[{tool:"get_study_evidence",arguments:{},result:{ok:true,evidence_ids:ids,study:structuredClone(study)}}],provider:"chalk",live_model_response:true,research_report:report,snapshot_report_sha256:digest,protocol_sha256:report.protocol_sha256,store_written:false,physical_validation:false,hardware_actuation:false};
}

test("actual pending acquisition preserves six downloaded groups and all unscored target outcomes",()=>{
 const r=fixture(),before=JSON.stringify(r);assert.equal(validateFreshStudy(r),r);assert.equal(JSON.stringify(r),before);
 assert.equal(r.study_id,"noaa-fresh-gdp-id-study-v2");assert.equal(r.coverage.selected_groups,6);assert.equal(r.coverage.downloaded_groups,6);
 assert.equal(r.coverage.scored_outcomes,0);assert.equal(r.coverage.failed_outcomes,180);assert.equal(r.coverage.planned_outcomes,180);
 assert.equal(r.coverage.unique_observed_positions,0);assert.equal(r.models.every(m=>m.metrics===null),true);
 assert.ok(r.groups.every(g=>g.models.every(m=>m.reason_codes.includes("EVALUATION_NOT_FROZEN"))));
});

test("amendment lineage retains the original zero-outcome attempt and correct temporal order",()=>{
 const r=fixture();assert.equal(r.protocol.pre_outcome_amendment.parent_trajectory_payloads,0);assert.equal(r.protocol.pre_outcome_amendment.parent_model_outcomes,0);
 assert.ok(Date.parse(r.provenance.acquisition_timestamps.started_at_utc)>Date.parse(r.protocol.frozen_at_utc));
 for(const mutate of [
  r=>{r.protocol.pre_outcome_amendment.parent_model_outcomes=1;},r=>{r.protocol.pre_outcome_amendment.parent_trajectory_payloads=1;},
  r=>{r.protocol.pre_outcome_amendment.parent_protocol_sha256="bad";},r=>{delete r.protocol.pre_outcome_amendment;},
  r=>{r.protocol.frozen_at_utc=r.provenance.acquisition_timestamps.finished_at_utc;},
  r=>{r.provenance.source_receipts[0].finished_at_utc="2000-01-01T00:00:00Z";},
 ]){const v=fixture();mutate(v);reject(v);}
});

test("known exclusions, alias limitations, fixed physics and no-tuning flags cannot be promoted",()=>{
 for(const mutate of [
  r=>{r.flags.physical_validation=true;},r=>{r.flags.statistical_independence=true;},r=>{r.flags.operational_causality=true;},
  r=>{r.flags.calibrated_probability=true;},r=>{r.flags.automatic_model_promotion=true;},r=>{r.flags.heldout_tuning=true;},
  r=>{r.flags.global_training=true;},r=>{r.flags.camera_started=true;},r=>{r.flags.provider_calls=true;},
  r=>{r.flags.physical_alias_resolution_verified=true;},r=>{r.protocol.exclusions.reserved_gdp_id_count=0;},
  r=>{r.protocol.models.position_std_m=10;},r=>{r.protocol.models.acceleration_spectral_density_m2_s3=0.001;},
  r=>{r.protocol.models.all_model_tracks_before_any_future_coordinate=false;},r=>{r.protocol.preprocessing.projection="tank_cm";},
  r=>{r.protocol.assignment.global_training=true;},r=>{r.provenance.hashes.protocol_sha256="b".repeat(64);},
 ]){const v=fixture();mutate(v);reject(v);}
});

test("whole GDP identities and all slot/model/horizon cells remain explicit",()=>{
 for(const mutate of [
  r=>r.groups.pop(),r=>{r.groups[1].drifter_id=r.groups[0].drifter_id;},r=>{r.groups[1].wmo=r.groups[0].wmo;},
  r=>{r.groups[0].slot=2;},r=>{r.groups[0].block_id="another-region";},r=>r.groups[0].models.pop(),
  r=>r.groups[0].models[0].predictions.pop(),r=>{r.groups[0].models[0].predictions[0].time_utc=r.groups[0].models[0].predictions[1].time_utc;},
  r=>{r.groups[0].models[0].predictions[0].x_m=0;},r=>{r.groups[0].models[4].id="last_drift";},
 ]){const v=fixture();mutate(v);reject(v);}
});

test("raw download receipts cannot become measured positions or successful model scores",()=>{
 for(const mutate of [
  r=>{r.coverage.downloaded_groups=5;},r=>{r.coverage.unique_observed_intervals=36;},
  r=>{r.coverage.unique_observed_positions=36;},r=>{r.coverage.scored_outcomes=180;},
  r=>{r.coverage.failed_outcomes=0;},r=>{r.status="COMPLETED";},r=>{r.flags.new_acquisition=false;},
  r=>{r.models[0].metrics={ade_m:0,fde_m:0,vector_rmse_m_s:0};},
  r=>{r.provenance.source_receipts.find(x=>x.role.startsWith("trajectory:")).response_complete=false;},
 ]){const v=fixture();mutate(v);reject(v);}
});

test("nonfinite or excessive response structures fail before plotting or rendering",()=>{
 for(const v of [NaN,Infinity,-Infinity]){const r=fixture();r.coverage.scored_outcomes=v;reject(r);}
 const large=fixture();large.limitations.push("x".repeat(12001));reject(large);
 const unsupported=fixture();unsupported.groups[0].training_track=[{time_utc:"2021-02-30T00:00:00Z",x_m:0,y_m:0,latitude_deg:0,longitude_deg:0}];reject(unsupported);
});

test("mock Chalk review binds to the exact loaded snapshot and its two research citations",()=>{
 const r=fixture(),a=chalkFixture(r);assert.equal(validateFreshAnswer(a,r),a);
 const reordered=structuredClone(a);reordered.research_report=Object.fromEntries(Object.entries(reordered.research_report).reverse());
 assert.equal(freshStudyIdentity(reordered.research_report),freshStudyIdentity(r));validateFreshAnswer(reordered,r);
 for(const mutate of [
  a=>{a.evidence_ids.pop();},a=>{a.evidence_ids[0]="case:unrelated";},a=>{a.trace=[];},
  a=>{a.trace[0].result.evidence_ids=[a.evidence_ids[0],a.evidence_ids[0]];},a=>{a.trace[0].result.study.coverage={...a.research_report.coverage,scored_outcomes:180};},a=>{a.trace[0].tool="request_collection";},a=>{a.trace[0].arguments={case_id:"unrelated"};},
  a=>{a.trace[0].result.study.protocol_sha256="b".repeat(64);},a=>{a.research_report.limitations.push("Changed after this report was loaded.");},
  a=>{a.explanation="This proves 99% accuracy.";},a=>{a.physical_validation=true;},a=>{a.hardware_actuation=true;},
  a=>{a.store_written=true;},a=>{a.provider="direct_gemini";},a=>{a.live_model_response=false;},
 ]){const answer=chalkFixture();mutate(answer);assert.throws(()=>validateFreshAnswer(answer,r),/invalid research evidence|No result was accepted/);}
});

test("Chalk configuration or provider STOP keeps deterministic evidence without fabricated live success",()=>{
 const r=fixture(),a=chalkFixture(r);Object.assign(a,{action:"STOP",evidence_ids:[],trace:[],live_model_response:false,failure_code:"NOT_CONFIGURED",explanation:"Chalk is not configured; the verified research report remains available."});
 validateFreshAnswer(a,r);assert.equal(a.research_report.coverage.downloaded_groups,6);
 const bad=structuredClone(a);bad.action="REPORT";assert.throws(()=>validateFreshAnswer(bad,r),/invalid research evidence/);
 const stale=structuredClone(a);stale.research_report.groups[0].reason_codes.push("REPORT_CHANGED");assert.throws(()=>validateFreshAnswer(stale,r),/invalid research evidence/);
});

test("fresh-report and Chalk HTTP errors remain errors, and response bytes are bounded",async()=>{
 const r=await readVectorResponse(new Response(text),validateFreshStudy,1000000);assert.equal(r.coverage.scored_outcomes,0);
 await assert.rejects(readVectorResponse(new Response(text,{headers:{"Content-Length":"1000001"}}),validateFreshStudy,1000000),/exceeds/);
 await assert.rejects(readVectorResponse(new Response(JSON.stringify({detail:"Operator access required"}),{status:401}),v=>validateFreshAnswer(v,fixture()),2000000),/Operator access required/);
 await assert.rejects(readVectorResponse(new Response(JSON.stringify({detail:"Snapshot integrity changed"}),{status:409}),validateFreshStudy),/Snapshot integrity changed/);
});

// The following fixture is the actual post-freeze, verified numerical replay.
const scoredText=readFileSync(new URL("./fixtures/fresh-drifter-report.json",import.meta.url),"utf8");
const completed=()=>JSON.parse(scoredText);
function failedCompleted(modelIndex=1,missingTruth=false) {
 const r=completed(),g=r.groups[0],affected=missingTruth?g.models:[g.models[modelIndex]];
 for(const m of affected) {
  Object.assign(m,{status:"FAILED",reason_codes:[missingTruth?"HELDOUT_TRUTH_UNAVAILABLE":"MODEL_FORECAST_UNAVAILABLE"],metrics:null});
  if(!missingTruth)m.forecast_anchor=null;
  m.predictions=m.predictions.map(p=>({horizon_hours:p.horizon_hours,time_utc:p.time_utc,status:"FAILED",reason_codes:["INCOMPLETE_MODEL_TRACK"],...Object.fromEntries(["latitude_deg","longitude_deg","x_m","y_m","position_error_m","observed_velocity_m_s","predicted_velocity_m_s","residual_velocity_m_s","position_covariance_m2","observation_covariance_m2","ellipse_hits"].map(k=>[k,null]))}));
 }
 g.status="FAILED";g.reason_codes=["INCOMPLETE_GROUP"];
 const failures=affected.length*6;
 Object.assign(r.coverage,{scored_outcomes:180-failures,failed_outcomes:failures,scored_groups:5,common_target_cohort_complete:false});r.status="PARTIAL_COVERAGE";
 for(const [i,m]of r.models.entries()){m.metrics=null;m.reason_codes=["INCOMPLETE_TARGET_COHORT"];if(missingTruth||i===modelIndex)m.complete_groups=5;}
 if(missingTruth) {
  const time=g.heldout_track[2].time_utc;
  g.heldout_track[2]={time_utc:time,status:"UNAVAILABLE",reason_codes:["HELDOUT_TRUTH_UNAVAILABLE"],latitude_deg:null,longitude_deg:null,x_m:null,y_m:null};
  r.coverage.unique_observed_positions=35;r.coverage.unique_observed_intervals=34;
 }
 if(missingTruth||modelIndex===4)Object.assign(r.uncertainty.per_drifter[0],{scored_count:0,nominal50_hit_count:null,nominal90_hit_count:null,nominal50_hit_fraction:null,nominal90_hit_fraction:null});
 return r;
}

test("actual scored cohort reconstructs all five models over six new GDP groups and thirty-six observed intervals",()=>{
 const r=completed();assert.equal(validateFreshStudy(r),r);assert.equal(r.status,"COMPLETED");assert.equal(r.coverage.scored_outcomes,180);
 assert.equal(r.coverage.unique_observed_intervals,36);assert.equal(r.coverage.unique_observed_positions,36);
 assert.equal(r.replay.verified_numeric_replay,true);assert.equal(r.flags.automatic_model_promotion,false);
 const model=id=>r.models.find(m=>m.id===id).metrics;
 assert.ok(Math.abs(model("last_drift").ade_m-1573.423238)<.01);
 assert.ok(Math.abs(model("kalman_cv").ade_m-1655.662069)<.01);
 assert.equal(new Set(r.groups.map(g=>g.drifter_id)).size,6);
 assert.ok(r.groups.every(g=>g.heldout_track.length===6&&g.heldout_track.every(p=>p.status==="OBSERVED")));
});

test("actual scored geometry, hourly clock, raw/filtered starts and aggregate scores cannot drift",()=>{
 for(const mutate of [
  r=>{r.groups[0].models[4].metrics.ade_m+=1;},r=>{r.groups[0].models[4].metrics.fde_m+=1;},
  r=>{r.groups[0].models[4].metrics.vector_rmse_m_s=0;},r=>{r.models[1].metrics.ade_m=0;},
  r=>{r.models[1].metrics.vector_rmse_m_s=0;},r=>{r.groups[0].models[1].forecast_anchor.x_m+=10;},
  r=>{r.groups[0].models[4].predictions[1].position_error_m=0;},
  r=>{r.groups[0].models[4].predictions[1].x_m+=10;},r=>{r.groups[0].heldout_track[1].longitude_deg+=.01;},
  r=>{r.groups[0].models[4].predictions[1].residual_velocity_m_s[0]*=-1;},
  r=>{r.groups[0].models[4].predictions[0].time_utc=r.groups[0].models[4].predictions[1].time_utc;},
  r=>{r.groups[0].heldout_track[0].time_utc="2021-02-30T18:00:00Z";},
  r=>{r.replay.verified_numeric_replay=false;},r=>{r.provenance.hashes.forecast_receipt_sha256=null;},
 ]){const v=completed();mutate(v);reject(v);}
});

test("actual Kalman covariance distinguishes latent position from observation variance and uncalibrated hits",()=>{
 for(const mutate of [
  r=>{r.groups[0].models[4].predictions[0].position_covariance_m2[0][0]=-1;},
  r=>{r.groups[0].models[4].predictions[0].position_covariance_m2[0][1]+=10;},
  r=>{r.groups[0].models[4].predictions[0].observation_covariance_m2[1][1]+=10000;},
  r=>{const p=r.groups[0].models[4].predictions[0];p.ellipse_hits.nominal90=!p.ellipse_hits.nominal90;},
  r=>{r.uncertainty.per_drifter[0].nominal50_hit_count=6;},r=>{r.uncertainty.per_drifter[0].nominal90_hit_fraction=0;},
  r=>{r.uncertainty.chi2_thresholds.nominal90=2;},
 ]){const v=completed();mutate(v);reject(v);}
});

test("contract-failure mutations of actual data preserve target counts and withhold every common aggregate",()=>{
 // These injected failures test display semantics; they are not new NOAA outcomes.
 for(const index of [1,4]) {
  const r=failedCompleted(index);validateFreshStudy(r);assert.equal(r.coverage.scored_outcomes,174);assert.equal(r.coverage.unique_observed_intervals,36);
  const invented=structuredClone(r);invented.models[0].metrics=completed().models[0].metrics;reject(invented);
  const zero=structuredClone(r);zero.groups[0].models[index].predictions[0].x_m=0;reject(zero);
 }
});

test("an unavailable truth position remains explicit and never becomes a bridged motion interval",()=>{
 const r=failedCompleted(4,true);validateFreshStudy(r);
 assert.equal(r.coverage.unique_observed_positions,35);assert.equal(r.coverage.unique_observed_intervals,34);
 assert.equal(r.coverage.failed_outcomes,30);assert.equal(r.groups[0].heldout_track.length,6);
 const bridge=structuredClone(r);bridge.coverage.unique_observed_intervals=35;reject(bridge);
 const hidden=structuredClone(r);hidden.groups[0].heldout_track.splice(2,1);reject(hidden);
});

test("a Chalk review of actual scored evidence cannot substitute the earlier pending snapshot",()=>{
 const r=completed(),a=chalkFixture(r);validateFreshAnswer(a,r);
 const stale=chalkFixture(fixture());assert.throws(()=>validateFreshAnswer(stale,r),/invalid research evidence/);
});

function noResponseFixture(count) {
 // Inject transport failures into the actual pre-score acquisition snapshot.
 // No received payload or successful model outcome is invented by this test.
 const r=fixture(),downloads=r.provenance.source_receipts.filter(x=>x.role.startsWith("trajectory:"));
 for(const receipt of downloads.slice(0,count))Object.assign(receipt,{status:"FETCH_FAILED",reason:"ConnectTimeout",http_status:null,response_complete:false,raw_path:null,bytes:0,sha256:null});
 r.coverage.downloaded_groups=6-count;r.flags.new_acquisition=count<6;
 r.status=count===6?"ACQUISITION_BLOCKED":"PARTIAL_COVERAGE";
 return r;
}

test("honest no-response transport failures remain visible in blocked and partial acquisition reports",()=>{
 for(const count of [1,6]) {
  const r=noResponseFixture(count);validateFreshStudy(r);
  assert.equal(r.coverage.downloaded_groups,6-count);assert.equal(r.coverage.failed_outcomes,180);assert.equal(r.coverage.scored_outcomes,0);
  assert.equal(r.provenance.source_receipts.filter(x=>x.role.startsWith("trajectory:")&&x.sha256===null).length,count);
 }
 for(const mutate of [
  receipt=>{receipt.status="DOWNLOADED";},receipt=>{receipt.response_complete=true;},receipt=>{receipt.raw_path="raw/claimed.csv";},
  receipt=>{receipt.bytes=1;},receipt=>{receipt.http_status=200;},receipt=>{receipt.reason=null;},
 ]){const r=noResponseFixture(1),receipt=r.provenance.source_receipts.find(x=>x.sha256===null);mutate(receipt);reject(r);}
});

test("Chalk tool evidence must retain the exact pre-outcome amendment beside its matching study",()=>{
 const r=completed(),answer=chalkFixture(r);validateFreshAnswer(answer,r);
 for(const mutate of [
  a=>{delete a.trace[0].result.study.pre_outcome_amendment;},
  a=>{a.trace[0].result.study.pre_outcome_amendment=null;},
  a=>{a.trace[0].result.study.pre_outcome_amendment.reason=["Different acquisition history."];},
  a=>{a.trace[0].result.study.pre_outcome_amendment.parent_protocol_sha256="b".repeat(64);},
 ]){const a=chalkFixture(completed());mutate(a);assert.throws(()=>validateFreshAnswer(a,r),/invalid research evidence/);assert.equal(freshStudyIdentity(a.research_report),freshStudyIdentity(r));}
});
