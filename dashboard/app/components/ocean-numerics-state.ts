/** Numerical self-comparisons only. The fine path is never observed truth. */
export type ForcingStatus = "COMPLETED" | "PARTIAL" | "UNSUPPORTED";
export type ForcingCounts = Record<ForcingStatus, number>;
export type NumericalForcing = { forcing_status:ForcingStatus; forcing_reason_code:string|null; requested_horizon_s:number; completed_horizon_s:number };
export type IntegrationComparison = { status:"COMPARED"|"NO_COMMON_POSITIVE_TIME"; common_positive_time_count:number; last_common_elapsed_s:number|null; max_separation_m:number|null; rms_separation_m:number|null; last_common_separation_m:number|null; both_completed:boolean; reference_completed_horizon_s:number; reference_forcing_status:ForcingStatus; reference_forcing_reason_code:string|null };
export type IntegrationRelease = NumericalForcing & { release_id:string; comparison:IntegrationComparison };
export type IntegrationLevel = { solver_step_s:number; output_step_s:300; release_count:6; forcing_status_counts:ForcingCounts; releases:IntegrationRelease[]; max_separation_m:number|null; comparable_release_count:number };
export type EventOutcome = NumericalForcing & { release_id:string; status:"ENTERED_PROTECTED_ZONE"|"IDEALIZED_INTERCEPTION"|"NO_ENTRY_WITHIN_HORIZON"|"UNRESOLVED"; event_kind:"PROTECTED_ZONE_ENTRY"|"IDEALIZED_CAPTURE"|null; segment_id:string|null; event_elapsed_s:number|null; track_end_elapsed_s:number|null; comparison_status:"MATCHED_EVENT"|"MATCHED_NO_EVENT"|"CHANGED_OUTCOME"|"UNRESOLVED"; event_time_difference_s:number|null };
export type NumericalSummary = { release_count:6; entered_count:number; intercepted_count:number; no_entry_count:number; unresolved_count:number; protected_entry_count_bounds:[number,number]; protected_entry_fraction_bounds:[number,number]; denominator_policy:"all_fixed_releases_including_missing_forcing_and_partial_paths" };
export type NumericalLayout = { id:string; label:string; summary:NumericalSummary; outcomes:EventOutcome[] };
export type NumericalRecommendation = { status:"BEST_LAYOUT"|"TIE"|"INDETERMINATE"; best_layout_id:string|null; reason:string; comparison_basis:"strict_nonoverlap_of_model_protected_entry_count_bounds" };
export type EventLevel = { chord_interval_s:number; release_count:6; baseline:NumericalLayout; layouts:NumericalLayout[]; recommendation:NumericalRecommendation; comparison_to_finest:{ recommendation_agrees:boolean; matched_event_count:number; matched_no_event_count:number; changed_outcome_count:number; unresolved_comparison_count:number; outcome_comparison_count:18; max_matched_event_time_difference_s:number|null } };
export type OceanNumericalSensitivity = {
  schema_version:1; kind:"OCEAN_NUMERICAL_SENSITIVITY"; release_count:6;
  scope:"separate_diagnostic_reruns_do_not_replace_main_decision_paths";
  physical_validation:false; independent_truth_used:false; model_parameters_tuned:false; diagnostic_advection_runs_per_release:4;
  integration:{ output_step_s:300; reference_solver_step_s:75; comparison_metric:"fixed_scenario_frame_Euclidean_separation_m"; positive_time_matching:"exact_common_accepted_output_times_only"; levels:IntegrationLevel[] };
  events:{ solver_step_s:75; reference_chord_interval_s:75; same_fine_tracks_downsampled:true; terminal_accepted_partial_point_retained:true; forcing_status_counts:ForcingCounts; levels:EventLevel[] };
  summary:{ integration_max_separation_m:number|null; event_recommendation_agrees_at_all_levels:boolean; all_integrations_completed:boolean; meaning:"numerical sensitivity only; no physical accuracy or ML skill established" };
  limitations:string[];
};
export type NumericalContext = { releases:{id:string;horizon_s:number}[]; scenario:{horizon_s:number;releases:{id:string;horizon_s:number}[]}; baseline:{id:string}; layouts:{id:string;segments:{id:string}[]}[] };

const object = (v:unknown):v is Record<string,unknown> => v !== null && typeof v === "object" && !Array.isArray(v);
const finite = (v:unknown):v is number => typeof v === "number" && Number.isFinite(v);
const text = (v:unknown,max=2000):v is string => typeof v === "string" && v.length>0 && v.length<=max;
const count = (v:unknown,max=6):v is number => Number.isInteger(v) && (v as number)>=0 && (v as number)<=max;
const near = (a:number,b:number) => Math.abs(a-b)<=1e-8*Math.max(1,Math.abs(a),Math.abs(b));
const exactKeys = (v:Record<string,unknown>,keys:string[]) => Object.keys(v).length===keys.length && keys.every(k=>Object.hasOwn(v,k));
const maximum = (values:(number|null)[]) => { const present=values.filter((v):v is number=>v!==null);return present.length?Math.max(...present):null; };
const sameNullable = (a:unknown,b:number|null) => b===null ? a===null : finite(a)&&near(a,b);
const statuses:ForcingStatus[]=["COMPLETED","PARTIAL","UNSUPPORTED"];
const steps=[300,150,75];
function bounded(value:unknown,depth=0,budget={nodes:0}):boolean {
  if(++budget.nodes>20000||depth>14)return false;
  if(Array.isArray(value))return value.length<=100&&value.every(v=>bounded(v,depth+1,budget));
  if(object(value))return Object.keys(value).length<=40&&Object.values(value).every(v=>bounded(v,depth+1,budget));
  return value===null||typeof value==="boolean"||finite(value)||typeof value==="string"&&value.length<=8000;
}
function forcing(v:Record<string,unknown>,horizon:number,prefix="") {
  const status=v[`${prefix}forcing_status`],reason=v[`${prefix}forcing_reason_code`],completed=v[`${prefix}completed_horizon_s`];
  return statuses.includes(status as ForcingStatus)&&finite(completed)&&completed>=0&&completed<=horizon&&
    (status==="COMPLETED"?reason===null&&completed===horizon: text(reason,100)&&(status==="PARTIAL"?completed>0&&completed<horizon:completed===0));
}
function statusCounts(v:unknown,rows:{forcing_status:ForcingStatus}[]) {
  return object(v)&&exactKeys(v,statuses)&&statuses.every(s=>count(v[s])&&v[s]===rows.filter(r=>r.forcing_status===s).length);
}
function integrationRow(v:unknown,release:{id:string;horizon_s:number}):v is IntegrationRelease {
  if(!object(v)||!exactKeys(v,["release_id","forcing_status","forcing_reason_code","requested_horizon_s","completed_horizon_s","comparison"])||v.release_id!==release.id||v.requested_horizon_s!==release.horizon_s||!forcing(v,release.horizon_s)||!object(v.comparison))return false;
  const c=v.comparison,horizon=release.horizon_s,completed=v.completed_horizon_s as number;
  if(!exactKeys(c,["status","common_positive_time_count","last_common_elapsed_s","max_separation_m","rms_separation_m","last_common_separation_m","both_completed","reference_completed_horizon_s","reference_forcing_status","reference_forcing_reason_code"])||!forcing(c,horizon,"reference_")||!count(c.common_positive_time_count,2049)||c.both_completed!==(v.forcing_status==="COMPLETED"&&c.reference_forcing_status==="COMPLETED"))return false;
  const commonEnd=Math.min(completed,c.reference_completed_horizon_s as number);
  if(c.status==="NO_COMMON_POSITIVE_TIME")return c.common_positive_time_count===0&&c.both_completed===false&&["last_common_elapsed_s","max_separation_m","rms_separation_m","last_common_separation_m"].every(k=>c[k]===null);
  return c.status==="COMPARED"&&c.common_positive_time_count>0&&c.common_positive_time_count<=Math.ceil(commonEnd/300)+1&&finite(c.last_common_elapsed_s)&&c.last_common_elapsed_s>0&&c.last_common_elapsed_s<=commonEnd&&
    ["max_separation_m","rms_separation_m","last_common_separation_m"].every(k=>finite(c[k])&&(c[k] as number)>=0&&(c[k] as number)<=300000)&&
    (c.rms_separation_m as number)<=(c.max_separation_m as number)+1e-9&&(c.last_common_separation_m as number)<=(c.max_separation_m as number)+1e-9&&
    (!c.both_completed||c.common_positive_time_count===horizon/300&&c.last_common_elapsed_s===horizon);
}
function eventLayout(v:unknown,layout:{id:string;segments:{id:string}[]},releases:NumericalContext["releases"]):v is NumericalLayout {
  if(!object(v)||!exactKeys(v,["id","label","summary","outcomes"])||v.id!==layout.id||!text(v.label,200)||!Array.isArray(v.outcomes)||v.outcomes.length!==6||!object(v.summary))return false;
  const counts={entered_count:0,intercepted_count:0,no_entry_count:0,unresolved_count:0};
  for(const [i,row]of v.outcomes.entries()){
    const release=releases[i];
    if(!object(row)||!exactKeys(row,["release_id","status","event_kind","segment_id","event_elapsed_s","forcing_status","forcing_reason_code","requested_horizon_s","completed_horizon_s","track_end_elapsed_s","comparison_status","event_time_difference_s"])||row.release_id!==release.id||row.requested_horizon_s!==release.horizon_s||!forcing(row,release.horizon_s)||!(row.track_end_elapsed_s===null||finite(row.track_end_elapsed_s)&&row.track_end_elapsed_s>=0&&row.track_end_elapsed_s<=(row.completed_horizon_s as number)))return false;
    if(row.status==="ENTERED_PROTECTED_ZONE"||row.status==="IDEALIZED_INTERCEPTION"){
      if(!finite(row.event_elapsed_s)||row.event_elapsed_s<0||row.event_elapsed_s>(row.completed_horizon_s as number)||row.track_end_elapsed_s!==row.event_elapsed_s)return false;
      if(row.status==="ENTERED_PROTECTED_ZONE"){
        if(row.event_kind!=="PROTECTED_ZONE_ENTRY"||row.segment_id!==null)return false;counts.entered_count++;
      }else{if(row.event_kind!=="IDEALIZED_CAPTURE"||!layout.segments.some(s=>s.id===row.segment_id))return false;counts.intercepted_count++;}
    }else{
      if(row.event_kind!==null||row.segment_id!==null||row.event_elapsed_s!==null)return false;
      if(row.status==="NO_ENTRY_WITHIN_HORIZON"){
        if(row.forcing_status!=="COMPLETED"||row.track_end_elapsed_s!==release.horizon_s)return false;counts.no_entry_count++;
      }else if(row.status==="UNRESOLVED"){
        if(row.forcing_status==="COMPLETED"||row.forcing_status==="PARTIAL"&&row.track_end_elapsed_s!==row.completed_horizon_s)return false;counts.unresolved_count++;
      }else return false;
    }
  }
  const s=v.summary,lo=counts.entered_count,hi=lo+counts.unresolved_count;
  return exactKeys(s,["release_count","entered_count","intercepted_count","no_entry_count","unresolved_count","protected_entry_count_bounds","protected_entry_fraction_bounds","denominator_policy"])&&s.release_count===6&&Object.entries(counts).every(([k,n])=>s[k]===n)&&Array.isArray(s.protected_entry_count_bounds)&&s.protected_entry_count_bounds.length===2&&s.protected_entry_count_bounds[0]===lo&&s.protected_entry_count_bounds[1]===hi&&Array.isArray(s.protected_entry_fraction_bounds)&&s.protected_entry_fraction_bounds.length===2&&sameNullable(s.protected_entry_fraction_bounds[0],lo/6)&&sameNullable(s.protected_entry_fraction_bounds[1],hi/6)&&s.denominator_policy==="all_fixed_releases_including_missing_forcing_and_partial_paths";
}
function recommendation(value:unknown,layouts:NumericalLayout[]):value is NumericalRecommendation {
  if(!object(value)||!exactKeys(value,["status","best_layout_id","reason","comparison_basis"])||!text(value.reason)||value.comparison_basis!=="strict_nonoverlap_of_model_protected_entry_count_bounds")return false;
  const [a,b]=layouts.map(l=>l.summary.protected_entry_count_bounds),best=a[1]<b[0]?layouts[0].id:b[1]<a[0]?layouts[1].id:null;
  const status=best?"BEST_LAYOUT":a[0]===a[1]&&a[0]===b[0]&&a[0]===b[1]?"TIE":"INDETERMINATE";
  return value.status===status&&value.best_layout_id===best;
}

export function validateOceanNumerics(value:unknown,context:NumericalContext):OceanNumericalSensitivity {
  const fail=():never=>{throw new Error("The ocean numerical check has incompatible levels, outcomes, coverage or scientific scope. No result was accepted.");};
  // Bind every diagnostic duration to the authoritative frozen scenario, not
  // merely a duration repeated consistently across the diagnostic levels.
  const frozen=context.scenario;
  if(!object(frozen)||!finite(frozen.horizon_s)||frozen.horizon_s<=0||!Array.isArray(frozen.releases)||frozen.releases.length!==6||!frozen.releases.every((release,i)=>object(release)&&release.id===context.releases[i]?.id&&release.horizon_s===frozen.horizon_s&&release.horizon_s===context.releases[i]?.horizon_s))return fail();
  if(!object(value)||!bounded(value)||!exactKeys(value,["schema_version","kind","release_count","scope","physical_validation","independent_truth_used","model_parameters_tuned","diagnostic_advection_runs_per_release","integration","events","summary","limitations"])||value.schema_version!==1||value.kind!=="OCEAN_NUMERICAL_SENSITIVITY"||value.release_count!==6||context.releases.length!==6||new Set(context.releases.map(r=>r.id)).size!==6||context.layouts.length!==2||context.baseline.id!=="no-interceptor"||value.scope!=="separate_diagnostic_reruns_do_not_replace_main_decision_paths"||value.physical_validation!==false||value.independent_truth_used!==false||value.model_parameters_tuned!==false||value.diagnostic_advection_runs_per_release!==4||!object(value.integration)||!object(value.events)||!object(value.summary)||!Array.isArray(value.limitations)||value.limitations.length<1||value.limitations.length>20||!value.limitations.every(v=>text(v,8000)))return fail();
  const integration=value.integration,events=value.events;
  if(!exactKeys(integration,["output_step_s","reference_solver_step_s","comparison_metric","positive_time_matching","levels"])||integration.output_step_s!==300||integration.reference_solver_step_s!==75||integration.comparison_metric!=="fixed_scenario_frame_Euclidean_separation_m"||integration.positive_time_matching!=="exact_common_accepted_output_times_only"||!Array.isArray(integration.levels)||integration.levels.length!==3)return fail();
  for(const [index,level]of integration.levels.entries()){
    if(!object(level)||!exactKeys(level,["solver_step_s","output_step_s","release_count","forcing_status_counts","releases","max_separation_m","comparable_release_count"])||level.solver_step_s!==steps[index]||level.output_step_s!==300||level.release_count!==6||!Array.isArray(level.releases)||level.releases.length!==6||!level.releases.every((row,i)=>integrationRow(row,frozen.releases[i])))return fail();
    const rows=level.releases as IntegrationRelease[];
    if(!statusCounts(level.forcing_status_counts,rows)||level.comparable_release_count!==rows.filter(r=>r.comparison.status==="COMPARED").length||!sameNullable(level.max_separation_m,maximum(rows.map(r=>r.comparison.max_separation_m))))return fail();
  }
  const levels=integration.levels as IntegrationLevel[],reference=levels[2];
  for(const level of levels)for(const [i,row]of level.releases.entries()){
    const ref=reference.releases[i],c=row.comparison;
    if(c.reference_forcing_status!==ref.forcing_status||c.reference_forcing_reason_code!==ref.forcing_reason_code||c.reference_completed_horizon_s!==ref.completed_horizon_s||level.solver_step_s===75&&c.status==="COMPARED"&&[c.max_separation_m,c.rms_separation_m,c.last_common_separation_m].some(v=>v!==0))return fail();
  }
  if(!exactKeys(events,["solver_step_s","reference_chord_interval_s","same_fine_tracks_downsampled","terminal_accepted_partial_point_retained","forcing_status_counts","levels"])||events.solver_step_s!==75||events.reference_chord_interval_s!==75||events.same_fine_tracks_downsampled!==true||events.terminal_accepted_partial_point_retained!==true||!Array.isArray(events.levels)||events.levels.length!==3)return fail();
  const expectedLayouts=[{id:context.baseline.id,segments:[]},...context.layouts];
  for(const [index,level]of events.levels.entries()){
    if(!object(level)||!exactKeys(level,["chord_interval_s","release_count","baseline","layouts","recommendation","comparison_to_finest"])||level.chord_interval_s!==steps[index]||level.release_count!==6||!eventLayout(level.baseline,expectedLayouts[0],frozen.releases)||!Array.isArray(level.layouts)||level.layouts.length!==2||!level.layouts.every((l,i)=>eventLayout(l,expectedLayouts[i+1],frozen.releases))||!recommendation(level.recommendation,level.layouts as NumericalLayout[])||!object(level.comparison_to_finest))return fail();
  }
  const eventLevels=events.levels as EventLevel[],fine=eventLevels[2],fineRows=[fine.baseline,...fine.layouts];
  if(!statusCounts(events.forcing_status_counts,fine.baseline.outcomes))return fail();
  for(const level of eventLevels){
    let matched=0,noEvent=0,changed=0,unresolved=0;const differences:number[]=[];
    for(const [layoutIndex,layout]of [level.baseline,...level.layouts].entries())for(const [i,row]of layout.outcomes.entries()){
      const ref=fineRows[layoutIndex].outcomes[i],forcingRef=fine.baseline.outcomes[i];
      if(row.forcing_status!==forcingRef.forcing_status||row.forcing_reason_code!==forcingRef.forcing_reason_code||row.completed_horizon_s!==forcingRef.completed_horizon_s)return fail();
      const resolved=row.status!=="UNRESOLVED"&&ref.status!=="UNRESOLVED",same=row.status===ref.status&&row.event_kind===ref.event_kind&&row.segment_id===ref.segment_id;
      const expected=!resolved?"UNRESOLVED":same&&row.event_kind!==null?"MATCHED_EVENT":same?"MATCHED_NO_EVENT":"CHANGED_OUTCOME";
      const difference=expected==="MATCHED_EVENT"?Math.abs(row.event_elapsed_s!-ref.event_elapsed_s!):null;
      if(row.comparison_status!==expected||!sameNullable(row.event_time_difference_s,difference))return fail();
      if(expected==="MATCHED_EVENT"){matched++;differences.push(difference!);}else if(expected==="MATCHED_NO_EVENT")noEvent++;else if(expected==="CHANGED_OUTCOME")changed++;else if(expected==="UNRESOLVED")unresolved++;
    }
    const c=level.comparison_to_finest,agrees=level.recommendation.status===fine.recommendation.status&&level.recommendation.best_layout_id===fine.recommendation.best_layout_id;
    if(!exactKeys(c,["recommendation_agrees","matched_event_count","matched_no_event_count","changed_outcome_count","unresolved_comparison_count","outcome_comparison_count","max_matched_event_time_difference_s"])||c.recommendation_agrees!==agrees||c.matched_event_count!==matched||c.matched_no_event_count!==noEvent||c.changed_outcome_count!==changed||c.unresolved_comparison_count!==unresolved||c.outcome_comparison_count!==18||!sameNullable(c.max_matched_event_time_difference_s,differences.length?Math.max(...differences):null))return fail();
  }
  const s=value.summary,allCompleted=levels.every(l=>l.forcing_status_counts.COMPLETED===6)&&(events.forcing_status_counts as ForcingCounts).COMPLETED===6;
  if(!exactKeys(s,["integration_max_separation_m","event_recommendation_agrees_at_all_levels","all_integrations_completed","meaning"])||!sameNullable(s.integration_max_separation_m,maximum(levels.map(l=>l.max_separation_m)))||s.event_recommendation_agrees_at_all_levels!==eventLevels.every(l=>l.comparison_to_finest.recommendation_agrees)||s.all_integrations_completed!==allCompleted||s.meaning!=="numerical sensitivity only; no physical accuracy or ML skill established")return fail();
  return value as OceanNumericalSensitivity;
}
