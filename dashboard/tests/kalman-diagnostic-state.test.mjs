import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { validateKalmanReport } from "../app/components/kalman-diagnostic-state.ts";
import { readVectorResponse } from "../app/components/vector-diagnostic-state.ts";

// Actual frozen replay over the four already-viewed NOAA buoy-days. Mutations
// below exercise the display contract; they do not create scientific evidence.
const payload=readFileSync(new URL("./fixtures/kalman-diagnostic-report.json",import.meta.url),"utf8");
const frozen=JSON.parse(payload), fixture=()=>structuredClone(frozen);
const rejected=r=>assert.throws(()=>validateKalmanReport(r),/No result was accepted/);
function failedFixture(modelIndex=0) {
  const r=fixture(), track=r.groups[0].models[modelIndex];
  Object.assign(track,{status:"FAILED",reason_codes:["NUMERICAL_OR_LOCAL_DOMAIN_FAILURE"],forecast_anchor:null,parameters:{},metrics:null});
  track.predictions=track.predictions.map(p=>({horizon_hours:p.horizon_hours,time_utc:p.time_utc,status:"FAILED",reason_codes:["NUMERICAL_OR_LOCAL_DOMAIN_FAILURE"],...Object.fromEntries(["latitude_deg","longitude_deg","x_m","y_m","position_error_m","position_covariance_m2","observation_covariance_m2","ellipse_hits"].map(k=>[k,null]))}));
  r.status="INCOMPLETE_OUTCOMES";
  Object.assign(r.coverage,{scored_outcomes:114,failed_outcomes:6,common_acquired_cohort_complete:false});
  r.models.forEach((m,i)=>{m.metrics=null;m.reason_codes=["INCOMPLETE_COMMON_ACQUIRED_COHORT"];if(i===modelIndex)m.complete_groups=3;});
  r.uncertainty.fraction_ranges=null;
  if(modelIndex===4)Object.assign(r.uncertainty.per_drifter[0],{scored_count:0,nominal50_hit_count:null,nominal90_hit_count:null,nominal50_hit_fraction:null,nominal90_hit_fraction:null});
  return r;
}

test("actual fixed study preserves distinct observations, outcomes and filtered anchors",()=>{
  const r=fixture(), before=JSON.stringify(r);
  assert.equal(validateKalmanReport(r),r);
  assert.equal(JSON.stringify(r),before);
  assert.equal(r.coverage.unique_observed_intervals,24);
  assert.equal(r.coverage.attempted_outcomes,120);
  assert.equal(r.coverage.planned_outcomes,180);
  assert.deepEqual(r.models.map(m=>m.id),["stationary","last_drift","mean_drift","ridge_ar1","kalman_cv"]);
  assert.ok(r.groups.some(g=>Math.hypot(g.models[4].forecast_anchor.x_m-g.training_track[17].x_m,g.models[4].forecast_anchor.y_m-g.training_track[17].y_m)>0));
});

test("units, assumption changes and promotional or provider claims fail closed",()=>{
  for(const mutate of [
    r=>{r.coordinate_system.position_units="cm";},r=>{r.coordinate_system.velocity_units="cm/s";},
    r=>{r.coordinate_system.earth_mean_radius_m=6378137;},r=>{r.data_origin="UNSEEN_INDEPENDENT_TEST";},
    r=>{r.independent_evaluation=true;},r=>{r.physical_validation=true;},r=>{r.calibrated_probability=true;},
    r=>{r.parameter_fitting_performed=true;},r=>{r.automatic_model_promotion=true;},r=>{r.provider_calls=true;},
    r=>{r.camera_started=true;},r=>{r.store_written=true;},r=>{r.provenance.integrity_verified=false;},
    r=>{r.replay.verified_numeric_replay=false;},r=>{r.protocol_sha256="not-a-hash";},
    r=>{r.groups[0].models[4].parameters.position_std_m=10;},
    r=>{r.groups[0].models[4].parameters.forecast_start="RAW_LAST_TRAINING_POSITION";},
  ]){const r=fixture();mutate(r);rejected(r);}
});

test("missing drifters, repeated models and shifted observation clocks cannot relabel scores",()=>{
  for(const mutate of [
    r=>r.groups.pop(),r=>{r.groups[1].drifter_id=r.groups[0].drifter_id;},r=>r.groups[0].training_track.pop(),
    r=>r.groups[0].heldout_track.pop(),r=>r.groups[0].models[2].predictions.pop(),r=>{r.groups[0].models[4].id="last_drift";},
    r=>{delete r.groups[0].heldout_track[0].time_utc;},r=>{r.groups[0].models[0].predictions[0].time_utc=r.groups[0].models[0].predictions[1].time_utc;},
    r=>{r.groups[0].training_track[0].time_utc="2000-02-30T00:00:00Z";},
    r=>{r.groups[0].models[1].forecast_anchor.x_m+=100;},r=>{r.coverage.unique_observed_intervals=120;},
    r=>{r.provenance.sources[0].source_url="https://example.com/fake-noaa.csv";},
  ]){const r=fixture();mutate(r);rejected(r);}
});

test("ADE, FDE, motion errors and coordinates must reconstruct from every declared position",()=>{
  for(const mutate of [
    r=>{r.groups[0].models[4].metrics.ade_m+=10;},r=>{r.groups[0].models[4].metrics.fde_m+=10;},
    r=>{r.groups[0].models[4].metrics.vector_rmse_m_s=0;},r=>{r.models[4].metrics.ade_m+=10;},
    r=>{r.models[4].metrics.vector_rmse_m_s=0;},r=>{r.groups[0].models[4].predictions[0].position_error_m=0;},
    r=>{r.groups[0].heldout_track[0].x_m+=500;},r=>{r.groups[0].models[4].predictions[0].x_m+=500;},
    r=>{r.groups[0].coordinate_system.origin_latitude_deg+=1;},
  ]){const r=fixture();mutate(r);rejected(r);}
});

test("model spread must be finite positive covariance plus R, and hits must match it",()=>{
  for(const mutate of [
    r=>{r.groups[0].models[4].predictions[0].position_covariance_m2[0][0]=-1;},
    r=>{r.groups[0].models[4].predictions[0].position_covariance_m2[0][1]+=1;},
    r=>{r.groups[0].models[4].predictions[0].observation_covariance_m2[0][0]+=10000;},
    r=>{const h=r.groups[0].models[4].predictions[0].ellipse_hits;h.nominal90=!h.nominal90;},
    r=>{r.uncertainty.per_drifter[0].nominal50_hit_fraction=7/6;},
    r=>{r.uncertainty.fraction_ranges.nominal90.max=2;},
    r=>{r.groups[0].models[0].predictions[0].ellipse_hits={nominal50:true,nominal90:true};},
  ]){const r=fixture();mutate(r);rejected(r);}
  for(const n of [NaN,Infinity,-Infinity]){
    const r=fixture();r.groups[0].models[4].predictions[0].x_m=n;rejected(r);
  }
});

test("failed tracks remain in all denominators and withhold common aggregates",()=>{
  const r=failedFixture();validateKalmanReport(r);
  assert.equal(r.models.every(m=>m.metrics===null),true);
  assert.equal(r.coverage.scored_outcomes,114);
  for(const mutate of [
    r=>{r.coverage.scored_outcomes=120;},r=>{r.groups[0].models[0].predictions[0].x_m=0;},
    r=>{r.groups[0].models[0].predictions.pop();},r=>{r.models[1].metrics=frozen.models[1].metrics;},
    r=>{r.uncertainty.fraction_ranges=frozen.uncertainty.fraction_ranges;},
  ]){const v=failedFixture();mutate(v);rejected(v);}
});

test("failed Kalman uncertainty is unavailable rather than a fabricated zero-hit experiment",()=>{
  const r=failedFixture(4);validateKalmanReport(r);
  assert.equal(r.uncertainty.per_drifter[0].nominal50_hit_fraction,null);
  const v=failedFixture(4);v.uncertainty.per_drifter[0].nominal50_hit_fraction=0;rejected(v);
});

test("bounded response reader accepts actual report and rejects large, non-JSON or error bodies",async()=>{
  const actual=await readVectorResponse(new Response(payload),validateKalmanReport,500000);
  assert.equal(actual.coverage.scored_outcomes,120);
  await assert.rejects(readVectorResponse(new Response(payload,{headers:{"Content-Length":"500001"}}),validateKalmanReport,500000),/exceeds/);
  await assert.rejects(readVectorResponse(new Response("not JSON"),validateKalmanReport),/Unreadable/);
  await assert.rejects(readVectorResponse(new Response(JSON.stringify({detail:"Pinned study unavailable"}),{status:503}),validateKalmanReport),/Pinned study unavailable/);
});
