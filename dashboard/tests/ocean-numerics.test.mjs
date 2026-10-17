import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync,readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname,resolve } from "node:path";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import { validateOceanNumerics } from "../app/components/ocean-numerics-state.ts";
import { validateOceanPrevention } from "../app/components/ocean-prevention-state.ts";

// Snapshot of actual pinned-forcing diagnostic output. It is a schema/regression
// fixture, not observed truth, measured reef performance or new independent data.
const numerical=JSON.parse(readFileSync("tests/fixtures/ocean-numerics-report.json","utf8"));
const bundle=JSON.parse(readFileSync("showcase/ocean-reports.json","utf8"));
const original=JSON.parse(bundle.reports["downstream-corridor-v2"].forecast_snapshot.report_json);
const clone=v=>structuredClone(v), max=values=>{const found=values.filter(v=>v!==null);return found.length?Math.max(...found):null;};
const reject=n=>assert.throws(()=>validateOceanNumerics(n,original),/No result was accepted/);
function fresh(){return clone(numerical);}
function canonical(value){return Array.isArray(value)?`[${value.map(canonical).join(",")}]`:value!==null&&typeof value==="object"?`{${Object.keys(value).sort().map(key=>`${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`:JSON.stringify(value);}
function resign(report){const payload={...report};delete payload.report_sha256;report.report_sha256=createHash("sha256").update(canonical(payload)).digest("hex");return report;}

// Construct coherent censored alternatives; these are explicitly synthetic test
// scenarios, not modifications to the committed model or real forcing snapshot.
function rebuild(n){
  for(const level of n.integration.levels){
    level.forcing_status_counts=Object.fromEntries(["COMPLETED","PARTIAL","UNSUPPORTED"].map(s=>[s,level.releases.filter(r=>r.forcing_status===s).length]));
    level.comparable_release_count=level.releases.filter(r=>r.comparison.status==="COMPARED").length;
    level.max_separation_m=max(level.releases.map(r=>r.comparison.max_separation_m));
  }
  const last=n.events.levels[2],all=l=>[l.baseline,...l.layouts];
  for(const level of n.events.levels){
    for(const layout of all(level)){
      const count=s=>layout.outcomes.filter(r=>r.status===s).length,e=count("ENTERED_PROTECTED_ZONE"),u=count("UNRESOLVED");
      layout.summary={release_count:6,entered_count:e,intercepted_count:count("IDEALIZED_INTERCEPTION"),no_entry_count:count("NO_ENTRY_WITHIN_HORIZON"),unresolved_count:u,protected_entry_count_bounds:[e,e+u],protected_entry_fraction_bounds:[e/6,(e+u)/6],denominator_policy:"all_fixed_releases_including_missing_forcing_and_partial_paths"};
    }
    const [a,b]=level.layouts.map(l=>l.summary.protected_entry_count_bounds),best=a[1]<b[0]?level.layouts[0].id:b[1]<a[0]?level.layouts[1].id:null;
    level.recommendation={status:best?"BEST_LAYOUT":a[0]===a[1]&&a[0]===b[0]&&a[0]===b[1]?"TIE":"INDETERMINATE",best_layout_id:best,reason:"Synthetic censored test accounting",comparison_basis:"strict_nonoverlap_of_model_protected_entry_count_bounds"};
  }
  for(const level of n.events.levels){
    const counts={MATCHED_EVENT:0,MATCHED_NO_EVENT:0,CHANGED_OUTCOME:0,UNRESOLVED:0},times=[];
    all(level).forEach((layout,j)=>layout.outcomes.forEach((row,i)=>{
      const ref=all(last)[j].outcomes[i],resolved=row.status!=="UNRESOLVED"&&ref.status!=="UNRESOLVED",same=row.status===ref.status&&row.event_kind===ref.event_kind&&row.segment_id===ref.segment_id;
      row.comparison_status=!resolved?"UNRESOLVED":same&&row.event_kind!==null?"MATCHED_EVENT":same?"MATCHED_NO_EVENT":"CHANGED_OUTCOME";
      row.event_time_difference_s=row.comparison_status==="MATCHED_EVENT"?Math.abs(row.event_elapsed_s-ref.event_elapsed_s):null;
      counts[row.comparison_status]++;if(row.event_time_difference_s!==null)times.push(row.event_time_difference_s);
    }));
    level.comparison_to_finest={recommendation_agrees:level.recommendation.status===last.recommendation.status&&level.recommendation.best_layout_id===last.recommendation.best_layout_id,matched_event_count:counts.MATCHED_EVENT,matched_no_event_count:counts.MATCHED_NO_EVENT,changed_outcome_count:counts.CHANGED_OUTCOME,unresolved_comparison_count:counts.UNRESOLVED,outcome_comparison_count:18,max_matched_event_time_difference_s:max(times)};
  }
  n.events.forcing_status_counts=Object.fromEntries(["COMPLETED","PARTIAL","UNSUPPORTED"].map(s=>[s,last.baseline.outcomes.filter(r=>r.forcing_status===s).length]));
  n.summary.integration_max_separation_m=max(n.integration.levels.map(l=>l.max_separation_m));
  n.summary.all_integrations_completed=n.integration.levels.every(l=>l.forcing_status_counts.COMPLETED===6)&&n.events.forcing_status_counts.COMPLETED===6;
  n.summary.event_recommendation_agrees_at_all_levels=n.events.levels.every(l=>l.comparison_to_finest.recommendation_agrees);
  return n;
}
function censored(all=false){
  const n=fresh(),indices=all?[0,1,2,3,4,5]:[5];
  for(const [j,level]of n.integration.levels.entries())for(const i of indices){
    const row=level.releases[i],completed=all?0:j===2?40:30;
    Object.assign(row,{forcing_status:all?"UNSUPPORTED":"PARTIAL",forcing_reason_code:"SYNTHETIC_TEST_COVERAGE_END",completed_horizon_s:completed});
    row.comparison={status:!all&&j===2?"COMPARED":"NO_COMMON_POSITIVE_TIME",common_positive_time_count:!all&&j===2?1:0,last_common_elapsed_s:!all&&j===2?40:null,max_separation_m:!all&&j===2?0:null,rms_separation_m:!all&&j===2?0:null,last_common_separation_m:!all&&j===2?0:null,both_completed:false,reference_completed_horizon_s:all?0:40,reference_forcing_status:all?"UNSUPPORTED":"PARTIAL",reference_forcing_reason_code:"SYNTHETIC_TEST_COVERAGE_END"};
  }
  for(const level of n.events.levels)for(const layout of [level.baseline,...level.layouts])for(const i of indices)Object.assign(layout.outcomes[i],{status:"UNRESOLVED",event_kind:null,segment_id:null,event_elapsed_s:null,track_end_elapsed_s:all?null:30,forcing_status:all?"UNSUPPORTED":"PARTIAL",forcing_reason_code:"SYNTHETIC_TEST_COVERAGE_END",completed_horizon_s:all?0:30});
  return rebuild(n);
}

test("the finalized real-forcing diagnostic contract validates without rewriting any evidence",()=>{
  const n=fresh(),before=JSON.stringify(n);assert.equal(validateOceanNumerics(n,original),n);assert.equal(JSON.stringify(n),before);
  assert.deepEqual(n.integration.levels.map(l=>l.solver_step_s),[300,150,75]);
  assert.equal(n.events.levels[0].layouts[0].summary.entered_count,2);assert.equal(n.events.levels[0].layouts[1].summary.entered_count,4);
});
test("legacy ocean/showcase reports remain readable but a malformed optional field is refused",()=>{
  const legacy=clone(original);delete legacy.numerical_sensitivity;validateOceanPrevention(legacy);
  validateOceanPrevention({...legacy,numerical_sensitivity:fresh()});
  for(const field of [null,{},undefined,"passed",{...fresh(),physical_validation:true}])assert.throws(()=>validateOceanPrevention({...legacy,numerical_sensitivity:field}),/No result was accepted/);
});
test("physical-validation, tuning, independent-truth and alternate-method claims cannot enter the check",()=>{
  for(const mutate of [n=>{n.physical_validation=true;},n=>{n.independent_truth_used=true;},n=>{n.model_parameters_tuned=true;},n=>{n.scope="main_decision_replaced";},n=>{n.diagnostic_advection_runs_per_release=3;},n=>{n.events.same_fine_tracks_downsampled=false;},n=>{n.events.terminal_accepted_partial_point_retained=false;},n=>{n.integration.positive_time_matching="interpolated_missing_times";},n=>{n.extra_physical_accuracy=true;}]){const n=fresh();mutate(n);reject(n);}
});
test("fixed levels, complete release identities and horizons are mandatory",()=>{
  for(const mutate of [n=>{n.integration.levels.reverse();},n=>{n.events.levels[1].chord_interval_s=100;},n=>{n.integration.levels[0].output_step_s=150;},n=>{n.events.solver_step_s=300;},n=>{n.integration.levels[0].releases.pop();},n=>{n.integration.levels[0].releases[1].release_id="release-1";},n=>{n.events.levels[1].layouts[0].outcomes.reverse();},n=>{n.integration.levels[0].releases[0].requested_horizon_s=100;},n=>{n.events.levels[1].layouts[0].outcomes[0].completed_horizon_s=21601;}]){const n=fresh();mutate(n);reject(n);}
});
test("coordinated internally consistent horizons remain bound to the frozen scenario",()=>{
  for(const experiments of [["integration"],["events"],["integration","events"]]){
    const n=fresh();
    if(experiments.includes("integration"))for(const level of n.integration.levels)for(const row of level.releases){
      row.requested_horizon_s=row.completed_horizon_s=24000;
      row.comparison.reference_completed_horizon_s=row.comparison.last_common_elapsed_s=24000;
      row.comparison.common_positive_time_count=80;
    }
    if(experiments.includes("events"))for(const level of n.events.levels)for(const layout of [level.baseline,...level.layouts])for(const row of layout.outcomes)row.requested_horizon_s=row.completed_horizon_s=24000;
    assert.equal(n.release_count,6);assert.ok(original.scenario.releases.every(r=>r.horizon_s===21600));reject(n);
    const report=resign({...clone(original),numerical_sensitivity:n});
    // Even a caller supplying a fresh report digest cannot replace the frozen
    // experiment with internally agreeing diagnostic-only durations.
    assert.throws(()=>validateOceanPrevention(report),/No result was accepted/);
  }
  const context=clone(original);for(const release of context.releases)release.horizon_s=24000;
  assert.throws(()=>validateOceanNumerics(fresh(),context),/No result was accepted/);
});
test("integration coverage, censored metrics and common-time references cannot be fabricated",()=>{
  for(const mutate of [n=>{n.integration.levels[0].forcing_status_counts.COMPLETED=5;},n=>{n.integration.levels[0].comparable_release_count=5;},n=>{n.integration.levels[0].max_separation_m=NaN;},n=>{n.integration.levels[0].releases[0].comparison.last_common_elapsed_s=21601;},n=>{n.integration.levels[0].releases[0].comparison.common_positive_time_count=73;},n=>{n.integration.levels[0].releases[0].comparison.reference_forcing_status="UNSUPPORTED";},n=>{n.integration.levels[0].releases[0].comparison.rms_separation_m=1;},n=>{n.integration.levels[2].releases[0].comparison.max_separation_m=0.1;},n=>{n.integration.levels[0].releases[0].comparison.status="NO_COMMON_POSITIVE_TIME";}]){const n=fresh();mutate(n);reject(n);}
  const n=censored();n.integration.levels[0].releases[5].comparison.max_separation_m=0;reject(n);
});
test("event identities, times, bounds and recommendation summaries must agree with the rows",()=>{
  for(const mutate of [n=>{n.events.levels[0].layouts[0].outcomes[2].segment_id="unknown-line";},n=>{n.events.levels[0].baseline.outcomes[0].event_elapsed_s=21601;},n=>{n.events.levels[0].layouts[0].summary.protected_entry_count_bounds=[0,0];},n=>{n.events.levels[0].layouts[1].summary.release_count=5;},n=>{n.events.levels[0].recommendation.best_layout_id="flanking";},n=>{n.events.levels[0].comparison_to_finest.matched_event_count=17;},n=>{n.events.levels[0].comparison_to_finest.matched_no_event_count=1;},n=>{n.events.levels[0].layouts[0].outcomes[2].comparison_status="CHANGED_OUTCOME";},n=>{n.events.levels[0].layouts[0].outcomes[2].event_time_difference_s=100;},n=>{n.events.levels[0].comparison_to_finest.max_matched_event_time_difference_s=null;},n=>{n.summary.event_recommendation_agrees_at_all_levels=false;}]){const n=fresh();mutate(n);reject(n);}
});
test("partial and entirely unsupported checks retain all six denominators and are not complete success",()=>{
  const partial=censored(),unsupported=censored(true);validateOceanNumerics(partial,original);validateOceanNumerics(unsupported,original);
  assert.equal(partial.summary.all_integrations_completed,false);assert.equal(partial.integration.levels[0].comparable_release_count,5);
  assert.deepEqual(partial.events.levels[0].layouts[0].summary.protected_entry_count_bounds,[2,3]);
  assert.equal(unsupported.summary.integration_max_separation_m,null);assert.equal(unsupported.summary.event_recommendation_agrees_at_all_levels,true);
  for(const level of unsupported.events.levels){assert.equal(level.recommendation.status,"INDETERMINATE");assert.deepEqual(level.layouts[0].summary.protected_entry_count_bounds,[0,6]);assert.equal(level.comparison_to_finest.unresolved_comparison_count,18);}
  unsupported.summary.all_integrations_completed=true;reject(unsupported);
});
test("no-event and changed-event comparisons withhold time differences instead of inventing zero error",()=>{
  const n=fresh();for(const level of n.events.levels)for(const layout of [level.baseline,...level.layouts])Object.assign(layout.outcomes[0],{status:"NO_ENTRY_WITHIN_HORIZON",event_kind:null,segment_id:null,event_elapsed_s:null,track_end_elapsed_s:21600});
  rebuild(n);validateOceanNumerics(n,original);assert.equal(n.events.levels[0].comparison_to_finest.matched_no_event_count,3);
  n.events.levels[0].baseline.outcomes[0].event_time_difference_s=0;reject(n);
  const changed=fresh();Object.assign(changed.events.levels[0].layouts[0].outcomes[0],{status:"NO_ENTRY_WITHIN_HORIZON",event_kind:null,segment_id:null,event_elapsed_s:null,track_end_elapsed_s:21600});
  rebuild(changed);validateOceanNumerics(changed,original);
  assert.equal(changed.events.levels[0].comparison_to_finest.changed_outcome_count,1);
  assert.equal(changed.events.levels[0].layouts[0].outcomes[0].event_time_difference_s,null);
  changed.events.levels[0].layouts[0].outcomes[0].event_time_difference_s=0;reject(changed);
});

const require=createRequire(import.meta.url),loaded=new Map();
function component(path){
  const file=resolve(path);if(loaded.has(file))return loaded.get(file).exports;
  const mod={exports:{}};loaded.set(file,mod);
  const compiled=ts.transpileModule(readFileSync(file,"utf8"),{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText;
  new Function("require","module","exports",compiled)(name=>{
    if(name.endsWith(".module.css"))return {__esModule:true,default:new Proxy({},{get:(_,key)=>String(key)})};
    if(name==="next/link")return {__esModule:true,default:({children,...props})=>React.createElement("a",props,children)};
    if(name.startsWith(".")){const base=resolve(dirname(file),name);return component([base,`${base}.tsx`,`${base}.ts`].find(existsSync));}
    return require(name);
  },mod,mod.exports);return mod.exports;
}
const {OceanNumerics}=component("app/components/ocean-numerics.tsx"),{OceanResults}=component("app/components/ocean-prevention.tsx"),{OperatorProvider}=component("app/components/operator-provider.tsx");
const render=n=>renderToStaticMarkup(React.createElement(OceanNumerics,{report:n,layouts:original.layouts}));
test("the numerical disclosure is closed, explains both experiments and adds no overlapping graph or success badge",()=>{
  const html=render(fresh());assert.match(html,/<details class="details-panel" aria-label="Ocean numerical sensitivity"><summary>Does a smaller time step change the result/);
  assert.doesNotMatch(html,/<details[^>]*\bopen[ =>]|<svg|PASS|physical accuracy established/);
  for(const text of [/two estimated midpoints/,/300, 150 and 75/,/same fine trajectory/,/not observed truth/,/Numerical precision is not physical accuracy/,/4 km \/ three-hour/,/does not establish fourth-order/])assert.match(html,text);
  assert.match(html,/2 \/ 6/);assert.match(html,/4 \/ 6/);
  const uncertain=render(censored(true));assert.match(uncertain,/Some forcing is partial or unavailable/);assert.match(uncertain,/Indeterminate/);assert.match(uncertain,/0–6 \/ 6/);assert.match(uncertain,/Not comparable/);
});
test("shared ocean results preserve the main two-versus-four comparison while optionally adding one closed numerical disclosure",()=>{
  const make=n=>renderToStaticMarkup(React.createElement(OperatorProvider,null,React.createElement(OceanResults,{report:{...original,...(n?{numerical_sensitivity:n}:{numerical_sensitivity:undefined})},api:"",readOnly:true})));
  const legacy=make(null),updated=make(fresh());assert.doesNotMatch(legacy,/Does a smaller time step/);
  assert.equal((updated.match(/Does a smaller time step/g)??[]).length,1);assert.equal((updated.match(/<svg/g)??[]).length,(legacy.match(/<svg/g)??[]).length);
  assert.match(updated,/2 of 6/);assert.match(updated,/4 of 6/);assert.match(updated,/Chalk unavailable in public showcase/);
});
