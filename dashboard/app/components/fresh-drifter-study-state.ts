// One frozen acquisition design; accept no upgraded scientific claims at the UI boundary.
export const FRESH_MODELS=["stationary","last_drift","mean_drift","ridge_ar1","kalman_cv"] as const;
export type FreshPoint={status?:string;reason_codes?:string[];time_utc:string;latitude_deg:number;longitude_deg:number;x_m:number;y_m:number};
export type FreshUnavailable={time_utc:string;latitude_deg:null;longitude_deg:null;x_m:null;y_m:null;status:"UNAVAILABLE";reason_codes:string[]};
type Metrics={ade_m:number;fde_m:number;vector_rmse_m_s:number};
type Covariance=[[number,number],[number,number]];
export type FreshPrediction={horizon_hours:number;time_utc:string;status:"SCORED"|"FAILED"|"UNFILLED";reason_codes:string[];latitude_deg:number|null;longitude_deg:number|null;x_m:number|null;y_m:number|null;position_error_m:number|null;observed_velocity_m_s:[number,number]|null;predicted_velocity_m_s:[number,number]|null;residual_velocity_m_s:[number,number]|null;position_covariance_m2:Covariance|null;observation_covariance_m2:Covariance|null;ellipse_hits:{nominal50:boolean;nominal90:boolean}|null};
export type FreshModel={id:string;label:string;status:string;reason_codes:string[];forecast_anchor:{time_utc:string;x_m:number;y_m:number}|null;predictions:FreshPrediction[];metrics:Metrics|null};
export type FreshGroup={block_id:string;slot:number;drifter_id:string|null;wmo:string|null;status:string;reason_codes:string[];coordinate_system:null|{origin_latitude_deg:number;origin_longitude_deg:number;projection:string;position_units:string;velocity_units:string};training_track:FreshPoint[];heldout_track:(FreshPoint|FreshUnavailable)[];models:FreshModel[]};
export type FreshStudy={schema_version:1;kind:"FRESH_NOAA_DRIFTER_STUDY";design_status:string;study_id:string;report_id:string;protocol_sha256:string;status:"NOT_ACQUIRED"|"ACQUISITION_BLOCKED"|"PARTIAL_COVERAGE"|"COMPLETED";protocol:{pre_outcome_amendment?:{parent_protocol_sha256:string;parent_manifest_sha256:string;parent_selection_sha256:string;parent_model_outcomes:0;parent_trajectory_payloads:0;reason:string[];exposure:string};frozen_at_utc:string;assignment:Record<string,unknown>;models:Record<string,unknown>;selection:{blocks:{id:string;start_utc:string;end_utc:string}[]};exclusions:{reserved_gdp_id_count:number;snapshot_sha256:string};source:{provider:string;metadata_url:string;license_url:string}};coverage:{target_groups:number;selected_groups:number;downloaded_groups:number;scored_groups:number;models:number;horizons:number;planned_outcomes:number;attempted_outcomes:number;scored_outcomes:number;failed_outcomes:number;unfilled_outcomes:number;unique_observed_intervals:number;unique_observed_positions:number;common_target_cohort_complete:boolean};groups:FreshGroup[];models:{id:string;label:string;status:string;complete_groups:number;metrics:Metrics|null;reason_codes:string[]}[];replay:{verified_numeric_replay:boolean;reference_report_sha256:string|null};flags:Record<string,unknown>;provenance:{integrity_verified:true;hashes:Record<string,string|null>;[key:string]:unknown};limitations:string[]};
export type FreshAnswer={schema_version:1;kind:"FRESH_DRIFTER_RESEARCH_INVESTIGATION";scope:"READ_ONLY_FRESH_STUDY";action:"REPORT"|"STOP";explanation:string;evidence_ids:string[];trace:{tool:string;arguments:Record<string,unknown>;result:Record<string,unknown>}[];provider:"chalk";live_model_response:boolean;research_report:FreshStudy;snapshot_report_sha256:string;protocol_sha256:string;failure_code?:string;provider_status_code?:number};
const object=(v:unknown):v is Record<string,unknown>=>v!==null&&typeof v==="object"&&!Array.isArray(v);
const finite=(v:unknown):v is number=>typeof v==="number"&&Number.isFinite(v);
const nonnegative=(v:unknown):v is number=>finite(v)&&v>=0;
const integer=(v:unknown):v is number=>nonnegative(v)&&Number.isInteger(v);
const hash=(v:unknown):v is string=>typeof v==="string"&&/^[a-f0-9]{64}$/.test(v);
const near=(a:number,b:number)=>Math.abs(a-b)<=1e-6*Math.max(1,Math.abs(b));
const strings=(v:unknown):v is string[]=>Array.isArray(v)&&v.every(x=>typeof x==="string"&&x.length>0);
function bounded(v:unknown,depth=0,budget={nodes:0}):boolean {
 if(++budget.nodes>65_000||depth>24)return false;
 if(Array.isArray(v))return v.length<=1024&&v.every(x=>bounded(x,depth+1,budget));
 if(object(v))return Object.keys(v).length<=300&&Object.values(v).every(x=>bounded(x,depth+1,budget));
 return v===null||typeof v==="boolean"||finite(v)||typeof v==="string"&&v.length<=12_000;
}
function utc(v:unknown):number|null {
 if(typeof v!=="string"||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(v))return null;
 const n=Date.parse(v);return Number.isFinite(n)&&new Date(n).toISOString().replace(".000Z","Z")===v?n:null;
}
function point(v:unknown):v is FreshPoint&Record<string,unknown> {
 return object(v)&&utc(v.time_utc)!==null&&finite(v.latitude_deg)&&Math.abs(v.latitude_deg)<=90&&finite(v.longitude_deg)&&Math.abs(v.longitude_deg)<=180&&finite(v.x_m)&&finite(v.y_m)&&Math.hypot(v.x_m,v.y_m)<=Math.PI*6_371_008.8;
}
function projection(p:FreshPoint,o:Pick<FreshPoint,"latitude_deg"|"longitude_deg">):boolean {
 const rad=Math.PI/180,a=o.latitude_deg*rad,b=p.latitude_deg*rad,dl=(p.longitude_deg-o.longitude_deg)*rad;
 const e=Math.cos(b)*Math.sin(dl),n=Math.cos(a)*Math.sin(b)-Math.sin(a)*Math.cos(b)*Math.cos(dl),dot=Math.sin(a)*Math.sin(b)+Math.cos(a)*Math.cos(b)*Math.cos(dl);
 const norm=Math.hypot(e,n),distance=Math.atan2(norm,dot)*6_371_008.8;
 return distance<=Math.PI*6_371_008.8&&(distance<1e-9?near(p.x_m,0)&&near(p.y_m,0):near(p.x_m,e*distance/norm)&&near(p.y_m,n*distance/norm));
}
function distance(a:FreshPoint,b:FreshPoint):number {
 const r=Math.PI/180,p=a.latitude_deg*r,q=b.latitude_deg*r;
 const s=Math.sin((q-p)/2)**2+Math.cos(p)*Math.cos(q)*Math.sin((b.longitude_deg-a.longitude_deg)*r/2)**2;
 return 2*6_371_008.8*Math.asin(Math.sqrt(Math.min(1,Math.max(0,s))));
}
function covariance(v:unknown):v is Covariance {
 if(!Array.isArray(v)||v.length!==2||!v.every(r=>Array.isArray(r)&&r.length===2&&r.every(finite)))return false;
 const [[a,b],[c,d]]=v;return a>0&&d>0&&near(b,c)&&a*d-b*c>0;
}
const vector=(v:unknown):v is [number,number]=>Array.isArray(v)&&v.length===2&&v.every(finite);
const metrics=(v:unknown):v is Metrics=>object(v)&&[v.ade_m,v.fde_m,v.vector_rmse_m_s].every(nonnegative);
export function freshStudyIdentity(v:FreshStudy):string { return JSON.stringify(canonical(v)); }
function canonical(v:unknown):unknown { return Array.isArray(v)?v.map(canonical):object(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,canonical(v[k])])):v; }
export function validateFreshStudy(value:unknown):FreshStudy {
 const fail=():never=>{throw new Error("The new GDP-ID study has incompatible protocol, evidence, coverage or scores. No result was accepted.");};
 if(!object(value)||!bounded(value)||value.schema_version!==1||value.kind!=="FRESH_NOAA_DRIFTER_STUDY"||typeof value.study_id!=="string"||!/^noaa-fresh-gdp-id-study-v[1-9]\d?$/.test(value.study_id)||value.report_id!==value.study_id||!hash(value.protocol_sha256)||value.design_status!=="FROZEN_NEW_GDP_ID_GROUP_EVALUATION_WITH_KNOWN_ALIAS_EXCLUSIONS"||!["NOT_ACQUIRED","ACQUISITION_BLOCKED","PARTIAL_COVERAGE","COMPLETED"].includes(value.status as string)||!object(value.protocol)||!object(value.coverage)||!object(value.flags)||!object(value.provenance)||value.provenance.integrity_verified!==true||!object(value.provenance.hashes)||value.provenance.hashes.protocol_sha256!==value.protocol_sha256||!Object.values(value.provenance.hashes).every(x=>x===null||hash(x))||!strings(value.limitations)||!value.limitations.length||!Array.isArray(value.groups)||value.groups.length!==6||!Array.isArray(value.models)||value.models.length!==5)return fail();
 const p=value.protocol,c=value.coverage,f=value.flags;
 if(p.study_id!==value.study_id||p.design_status!==value.design_status||typeof p.frozen_at_utc!=="string"||!Number.isFinite(Date.parse(p.frozen_at_utc))||!object(p.assignment)||p.assignment.global_training!==false||p.assignment.heldout_tuning!==false||!object(p.models)||!Array.isArray(p.models.ids)||p.models.ids.join(",")!==FRESH_MODELS.join(",")||p.models.position_std_m!==100||p.models.acceleration_spectral_density_m2_s3!==1e-6||p.models.kalman_noise_fitting!==false||!object(p.exclusions)||p.exclusions.reserved_gdp_id_count!==223||!hash(p.exclusions.snapshot_sha256)||!object(p.selection)||!Array.isArray(p.selection.blocks)||p.selection.blocks.length!==3)return fail();
 if(!object(p.preprocessing)||p.preprocessing.earth_mean_radius_m!==6_371_008.8||p.preprocessing.maximum_local_position_m!==50_000||p.preprocessing.projection!=="spherical_azimuthal_equidistant"||p.preprocessing.interpolation!==false||!object(p.origin)||p.origin.training_count!==18||p.origin.heldout_count!==6||p.origin.cadence_s!==3600||p.models.all_model_tracks_before_any_future_coordinate!==true||p.acquisition_or_scores_computed!==false)return fail();
 if([f.physical_validation,f.calibrated_probability,f.automatic_model_promotion,f.provider_calls,f.camera_started,f.store_written,f.operational_causality,f.statistical_independence,f.global_training,f.heldout_tuning].some(x=>x!==false)||typeof f.new_acquisition!=="boolean")return fail();
 for(const [key,n]of Object.entries({target_groups:6,models:5,horizons:6,planned_outcomes:180}))if(c[key]!==n)return fail();
 if(![c.selected_groups,c.downloaded_groups,c.scored_groups,c.attempted_outcomes,c.scored_outcomes,c.failed_outcomes,c.unfilled_outcomes,c.unique_observed_intervals,c.unique_observed_positions].every(integer))return fail();
 if(!object(value.replay)||typeof value.replay.verified_numeric_replay!=="boolean")return fail();
 if(value.replay.verified_numeric_replay===true) {
  if(!hash(value.replay.reference_report_sha256)||value.replay.reference_report_sha256!==value.provenance.hashes.reference_report_sha256||![value.provenance.hashes.implementation_receipt_sha256,value.provenance.hashes.forecast_receipt_sha256].every(hash))return fail();
 }else if(value.replay.reference_report_sha256!==null||value.provenance.hashes.reference_report_sha256!==null||(c.scored_outcomes as number)>0)return fail();
 const report=value as unknown as FreshStudy;
 let selected=0,completeGroups=0,scored=0,failed=0,unfilled=0,unique=0,observedPositions=0;
 const receipts=value.provenance.source_receipts;
 if(!Array.isArray(receipts)||receipts.length>11)return fail();
 const downloadIds=new Set<string>();
 const frozen=Date.parse(p.frozen_at_utc as string), times=value.provenance.acquisition_timestamps;
 if(!object(times))return fail();
 if(times.started_at_utc!==null&&(typeof times.started_at_utc!=="string"||!Number.isFinite(Date.parse(times.started_at_utc))||Date.parse(times.started_at_utc)<frozen))return fail();
 if(times.finished_at_utc!==null&&(typeof times.finished_at_utc!=="string"||typeof times.started_at_utc!=="string"||!Number.isFinite(Date.parse(times.finished_at_utc))||Date.parse(times.finished_at_utc)<Date.parse(times.started_at_utc)))return fail();
 for(const r of receipts) {
  if(!object(r)||typeof r.role!=="string"||typeof r.status!=="string"||typeof r.started_at_utc!=="string"||!Number.isFinite(Date.parse(r.started_at_utc))||Date.parse(r.started_at_utc)<frozen||!integer(r.bytes)||typeof r.source_url!=="string"||!r.source_url.startsWith("https://erddap.aoml.noaa.gov/gdp/erddap/")||typeof r.finished_at_utc!=="string"||!Number.isFinite(Date.parse(r.finished_at_utc))||Date.parse(r.finished_at_utc)<Date.parse(r.started_at_utc))return fail();
  if(r.sha256===null) {
   if(r.status!=="FETCH_FAILED"||r.http_status!==null||r.response_complete!==false||r.raw_path!==null||r.bytes!==0||typeof r.reason!=="string"||!r.reason.length)return fail();
  }else if(!hash(r.sha256)||typeof r.raw_path!=="string"||!r.raw_path.startsWith("raw/")||r.raw_path.includes("..")||!Number.isInteger(r.http_status)||(r.http_status as number)<100||(r.http_status as number)>599)return fail();
  if(r.role.startsWith("trajectory:")&&r.status==="DOWNLOADED") {
   const id=r.role.slice(11);
   if(!/^[1-9]\d{0,17}$/.test(id)||downloadIds.has(id)||r.http_status!==200||r.response_complete!==true)return fail();
   downloadIds.add(id);
  }
 }
 const downloaded=downloadIds.size;
 if(f.acquisition_attempted!==(times.started_at_utc!==null)||typeof f.new_gdp_id_group_evaluation!=="boolean"||f.new_gdp_id_group_evaluation!==((c.scored_outcomes as number)>0)||value.provenance.excluded_gdp_id_count!==223)return fail();
 const amend=p.pre_outcome_amendment;
 if(amend!==undefined&&(!object(amend)||!hash(amend.parent_protocol_sha256)||!hash(amend.parent_manifest_sha256)||!hash(amend.parent_selection_sha256)||amend.parent_model_outcomes!==0||amend.parent_trajectory_payloads!==0||!strings(amend.reason)||!amend.reason.length||typeof amend.exposure!=="string"))return fail();
 if(value.study_id!=="noaa-fresh-gdp-id-study-v1"&&!object(amend))return fail();
 const alias=value.provenance.aliases;
 if(!object(alias)||alias.reserved_gdp_id_count!==223||alias.statistical_independence!==false||!integer(alias.unresolved_reserved_alias_count)||!Array.isArray(alias.unresolved_reserved_alias_ids)||alias.unresolved_reserved_alias_ids.length!==alias.unresolved_reserved_alias_count||alias.physical_alias_resolution_verified!==(alias.unresolved_reserved_alias_count===0)||f.physical_alias_resolution_verified!==alias.physical_alias_resolution_verified)return fail();
 const ids=new Set<string>(),wmos=new Set<string>();
 for(const [i,g]of report.groups.entries()) {
  const block=p.selection.blocks[Math.floor(i/2)];
  if(!object(g)||!object(block)||g.block_id!==block.id||g.slot!==i%2+1||utc(block.start_utc)===null||utc(block.end_utc)!==utc(block.start_utc)!+23*3_600_000||!strings(g.reason_codes)||!Array.isArray(g.training_track)||!Array.isArray(g.heldout_track)||!Array.isArray(g.models)||g.models.length!==5||!["UNFILLED","FAILED","SCORED"].includes(g.status))return fail();
  if(g.drifter_id===null) {if(g.wmo!==null||g.status!=="UNFILLED"||g.training_track.length||g.heldout_track.length||!g.reason_codes.length)return fail();}
  else {if(!/^[1-9]\d{0,17}$/.test(g.drifter_id)||ids.has(g.drifter_id)||alias.unresolved_reserved_alias_ids.includes(g.drifter_id)||typeof g.wmo!=="string"||!/^[1-9]\d{0,17}$/.test(g.wmo)||wmos.has(g.wmo)||g.status==="UNFILLED")return fail();ids.add(g.drifter_id);wmos.add(g.wmo);selected++;}
  const hasPrefix=g.training_track.length===18;
  const origin=g.coordinate_system&&finite(g.coordinate_system.origin_latitude_deg)&&Math.abs(g.coordinate_system.origin_latitude_deg)<=90&&finite(g.coordinate_system.origin_longitude_deg)&&Math.abs(g.coordinate_system.origin_longitude_deg)<=180?{latitude_deg:g.coordinate_system.origin_latitude_deg,longitude_deg:g.coordinate_system.origin_longitude_deg}:null;
  if(g.coordinate_system!==null&&(!origin||g.coordinate_system.position_units!=="m"||g.coordinate_system.velocity_units!=="m/s"||g.coordinate_system.projection!=="spherical_azimuthal_equidistant"))return fail();
  if(g.training_track.length!==0&&!hasPrefix)return fail();
  if(hasPrefix) {
   if(!g.training_track.every(point)||!g.training_track.every((pt,j)=>Math.hypot(pt.x_m,pt.y_m)<=50_000&&utc(pt.time_utc)===utc(block.start_utc)!+j*3_600_000&&projection(pt,g.training_track[0])))return fail();
   if(!object(g.coordinate_system)||g.coordinate_system.position_units!=="m"||g.coordinate_system.velocity_units!=="m/s"||g.coordinate_system.projection!=="spherical_azimuthal_equidistant"||g.coordinate_system.origin_latitude_deg!==g.training_track[0].latitude_deg||g.coordinate_system.origin_longitude_deg!==g.training_track[0].longitude_deg)return fail();
  }
  if(g.heldout_track.length!==0&&g.heldout_track.length!==6)return fail();
  let preceding=hasPrefix;
  for(const [j,pt]of g.heldout_track.entries()) {
   if(!object(pt)||utc(pt.time_utc)!==utc(block.start_utc)!+(18+j)*3_600_000)return fail();
   if(point(pt)) {
    if(!origin||pt.status!=="OBSERVED"||!strings(pt.reason_codes)||pt.reason_codes.length||!projection(pt,origin))return fail();
    observedPositions++;if(preceding)unique++;preceding=true;
   }else {
    if(pt.status!=="UNAVAILABLE"||!strings(pt.reason_codes)||!pt.reason_codes.length||[pt.latitude_deg,pt.longitude_deg,pt.x_m,pt.y_m].some(x=>x!==null))return fail();
    preceding=false;
   }
  }
  const completeTruth=g.heldout_track.length===6&&g.heldout_track.every(point);
  let complete=0;
  for(const [j,m]of g.models.entries()) {
   if(!object(m)||m.id!==FRESH_MODELS[j]||typeof m.label!=="string"||!m.label.length||!strings(m.reason_codes)||!Array.isArray(m.predictions)||m.predictions.length!==6||!["SCORED","FAILED","UNFILLED"].includes(m.status))return fail();
   if(m.status!=="SCORED") {
    const status=g.drifter_id===null?"UNFILLED":"FAILED";
    if(m.status!==status||m.metrics!==null||m.forecast_anchor!==null&&(!hasPrefix||!object(m.forecast_anchor)||!finite(m.forecast_anchor.x_m)||!finite(m.forecast_anchor.y_m)||Math.hypot(m.forecast_anchor.x_m,m.forecast_anchor.y_m)>50_000||m.forecast_anchor.time_utc!==g.training_track[17].time_utc)||!m.reason_codes.length)return fail();
    for(const [k,r]of m.predictions.entries())if(!object(r)||r.status!==status||r.horizon_hours!==k+1||utc(r.time_utc)!==utc(block.start_utc)!+(18+k)*3_600_000||!strings(r.reason_codes)||!r.reason_codes.length||[r.latitude_deg,r.longitude_deg,r.x_m,r.y_m,r.position_error_m,r.observed_velocity_m_s,r.predicted_velocity_m_s,r.residual_velocity_m_s,r.position_covariance_m2,r.observation_covariance_m2,r.ellipse_hits].some(x=>x!==null))return fail();
    if(status==="UNFILLED")unfilled+=6;else failed+=6;continue;
   }
   if(!hasPrefix||!completeTruth||!metrics(m.metrics)||!object(m.forecast_anchor)||!finite(m.forecast_anchor.x_m)||!finite(m.forecast_anchor.y_m)||Math.hypot(m.forecast_anchor.x_m,m.forecast_anchor.y_m)>50_000||m.forecast_anchor.time_utc!==g.training_track[17].time_utc||m.reason_codes.length)return fail();
   const raw=g.training_track[17];
   if(j!==4&&(!near(m.forecast_anchor.x_m,raw.x_m)||!near(m.forecast_anchor.y_m,raw.y_m)))return fail();
   let previousPrediction=m.forecast_anchor,previousObservation=raw,totalError=0,squared=0;
   for(const [k,r]of m.predictions.entries()) {
    if(!point(r)||r.status!=="SCORED"||r.horizon_hours!==k+1||r.time_utc!==g.heldout_track[k].time_utc||!strings(r.reason_codes)||r.reason_codes.length||!nonnegative(r.position_error_m)||Math.hypot(r.x_m,r.y_m)>50_000||!projection(r,g.training_track[0])||!vector(r.observed_velocity_m_s)||!vector(r.predicted_velocity_m_s)||!vector(r.residual_velocity_m_s))return fail();
    const actual=g.heldout_track[k] as FreshPoint;
    if(!near(r.position_error_m,distance(r,actual)))return fail();
    const o=[(actual.x_m-previousObservation.x_m)/3600,(actual.y_m-previousObservation.y_m)/3600],pr=[(r.x_m-previousPrediction.x_m)/3600,(r.y_m-previousPrediction.y_m)/3600];
    for(let axis=0;axis<2;axis++)if(!near(r.observed_velocity_m_s[axis],o[axis])||!near(r.predicted_velocity_m_s[axis],pr[axis])||!near(r.residual_velocity_m_s[axis],pr[axis]-o[axis]))return fail();
    if(j===4) {
     if(!covariance(r.position_covariance_m2)||!covariance(r.observation_covariance_m2)||!object(r.ellipse_hits)||typeof r.ellipse_hits.nominal50!=="boolean"||typeof r.ellipse_hits.nominal90!=="boolean")return fail();
     const a=r.position_covariance_m2,b=r.observation_covariance_m2;
     if(!near(b[0][0],a[0][0]+10000)||!near(b[1][1],a[1][1]+10000)||!near(b[0][1],a[0][1])||!near(b[1][0],a[1][0]))return fail();
     const ex=actual.x_m-r.x_m,ey=actual.y_m-r.y_m,det=b[0][0]*b[1][1]-b[0][1]*b[1][0],d=(b[1][1]*ex*ex-(b[0][1]+b[1][0])*ex*ey+b[0][0]*ey*ey)/det;
     if(r.ellipse_hits.nominal50!==(d<=-2*Math.log(.5))||r.ellipse_hits.nominal90!==(d<=-2*Math.log(.1)))return fail();
    }else if([r.position_covariance_m2,r.observation_covariance_m2,r.ellipse_hits].some(x=>x!==null))return fail();
    totalError+=r.position_error_m;squared+=r.residual_velocity_m_s[0]**2+r.residual_velocity_m_s[1]**2;previousPrediction=r;previousObservation=actual;
   }
   if(!near(m.metrics.ade_m,totalError/6)||!near(m.metrics.fde_m,m.predictions[5].position_error_m!)||!near(m.metrics.vector_rmse_m_s,Math.sqrt(squared/6)))return fail();
   scored+=6;complete++;
  }
  if(complete===5)completeGroups++;
  if((g.status==="SCORED")!==(complete===5))return fail();
 }
 if(c.selected_groups!==selected||c.downloaded_groups!==downloaded||c.scored_groups!==completeGroups||c.attempted_outcomes!==selected*30||c.scored_outcomes!==scored||c.failed_outcomes!==failed||c.unfilled_outcomes!==unfilled||scored+failed+unfilled!==180||c.unique_observed_intervals!==unique||c.unique_observed_positions!==observedPositions||[...downloadIds].some(id=>!ids.has(id))||c.common_target_cohort_complete!==(scored===180)||f.new_acquisition!==(downloaded>0)||value.status==="COMPLETED"&&scored!==180||scored===180&&value.status!=="COMPLETED")return fail();
 if(value.status==="NOT_ACQUIRED"&&(selected||downloaded||scored)||value.status==="ACQUISITION_BLOCKED"&&(downloaded||scored))return fail();
 for(const [j,m]of report.models.entries()) {
  const tracks=report.groups.map(g=>g.models[j]).filter(t=>t.status==="SCORED");
  if(!object(m)||m.id!==FRESH_MODELS[j]||typeof m.label!=="string"||m.complete_groups!==tracks.length||!strings(m.reason_codes))return fail();
  if(scored!==180) {if(m.metrics!==null||!m.reason_codes.length)return fail();}
  else if(!metrics(m.metrics)||!near(m.metrics.ade_m,tracks.reduce((s,t)=>s+t.metrics!.ade_m,0)/6)||!near(m.metrics.fde_m,tracks.reduce((s,t)=>s+t.metrics!.fde_m,0)/6)||!near(m.metrics.vector_rmse_m_s,Math.sqrt(tracks.reduce((s,t)=>s+t.metrics!.vector_rmse_m_s**2,0)/6)))return fail();
 }
 const uncertainty=value.uncertainty;
 if(!object(uncertainty)||uncertainty.kind!=="UNCALIBRATED_OBSERVATION_PREDICTIVE_ELLIPSE_HITS"||uncertainty.comparison_covariance!=="position_covariance_plus_assumed_R"||!object(uncertainty.chi2_thresholds)||!finite(uncertainty.chi2_thresholds.nominal50)||!near(uncertainty.chi2_thresholds.nominal50,-2*Math.log(.5))||!finite(uncertainty.chi2_thresholds.nominal90)||!near(uncertainty.chi2_thresholds.nominal90,-2*Math.log(.1))||!Array.isArray(uncertainty.per_drifter))return fail();
 const evaluated=report.replay.verified_numeric_replay;
 const selectedRows=report.groups.filter(g=>g.drifter_id!==null);
 if(uncertainty.per_drifter.length!==(evaluated?selectedRows.length:0))return fail();
 for(const [i,row]of uncertainty.per_drifter.entries()) {
  const track=selectedRows[i].models[4],rows=track.predictions.filter(r=>r.status==="SCORED"&&r.ellipse_hits!==null);
  if(!object(row)||row.drifter_id!==selectedRows[i].drifter_id||row.scored_count!==rows.length)return fail();
  for(const key of ["nominal50","nominal90"]as const) {
   const count=rows.filter(r=>r.ellipse_hits![key]).length;
   const fraction=row[`${key}_hit_fraction`];
   if(rows.length?row[`${key}_hit_count`]!==count||!finite(fraction)||!near(fraction,count/rows.length):row[`${key}_hit_count`]!==null||fraction!==null)return fail();
  }
 }
 return report;
}
export function validateFreshAnswer(value:unknown,expected:FreshStudy):FreshAnswer {
 const fail=():never=>{throw new Error("Chalk returned unrelated or invalid research evidence. The deterministic study remains available.");};
 if(!object(value)||!bounded(value)||value.schema_version!==1||value.kind!=="FRESH_DRIFTER_RESEARCH_INVESTIGATION"||value.scope!=="READ_ONLY_FRESH_STUDY"||!["REPORT","STOP"].includes(value.action as string)||value.provider!=="chalk"||typeof value.live_model_response!=="boolean"||[value.store_written,value.physical_validation,value.hardware_actuation].some(v=>v!==false)||value.protocol_sha256!==expected.protocol_sha256||!hash(value.snapshot_report_sha256)||typeof value.explanation!=="string"||!value.explanation.trim()||value.explanation.length>1200||/[\p{Number}]/u.test(value.explanation)||!Array.isArray(value.evidence_ids)||!value.evidence_ids.every(v=>typeof v==="string")||!Array.isArray(value.trace)||value.trace.length>1)return fail();
 const current=validateFreshStudy(value.research_report);
 if(freshStudyIdentity(current)!==freshStudyIdentity(expected))return fail();
 const ids=[`fresh-study:${value.snapshot_report_sha256}`,`fresh-protocol:${expected.protocol_sha256}`];
 if(new Set(value.evidence_ids).size!==value.evidence_ids.length||!value.evidence_ids.every(v=>ids.includes(v as string)))return fail();
 const modelKeys=["id","label","status","metrics","reason_codes","complete_groups"];
 const pick=(v:Record<string,unknown>,keys:string[])=>Object.fromEntries(keys.filter(k=>Object.hasOwn(v,k)).map(k=>[k,v[k]]));
 const expectedModels=expected.models.map(m=>pick(m as unknown as Record<string,unknown>,modelKeys));
 const expectedGroups=expected.groups.map(g=>({...pick(g as unknown as Record<string,unknown>,["block_id","slot","drifter_id","wmo","status","reason_codes"]),models:g.models.map(m=>pick(m as unknown as Record<string,unknown>,modelKeys))}));
 for(const row of value.trace) {
  if(!object(row)||row.tool!=="get_study_evidence"||!object(row.arguments)||Object.keys(row.arguments).length||!object(row.result)||row.result.ok!==true||!Array.isArray(row.result.evidence_ids)||row.result.evidence_ids.length!==2||new Set(row.result.evidence_ids).size!==2||!row.result.evidence_ids.every(v=>ids.includes(v as string))||!object(row.result.study))return fail();
  const study=row.result.study;
  if(study.snapshot_report_sha256!==value.snapshot_report_sha256||study.protocol_sha256!==expected.protocol_sha256||study.kind!==expected.kind||study.design_status!==expected.design_status||study.status!==expected.status)return fail();
  for(const [key,ref]of Object.entries({coverage:expected.coverage,models:expectedModels,groups:expectedGroups,provenance:expected.provenance,flags:expected.flags,model_definitions:expected.protocol.models,pre_outcome_amendment:expected.protocol.pre_outcome_amendment??null,limitations:expected.limitations}))if(JSON.stringify(canonical(study[key]))!==JSON.stringify(canonical(ref)))return fail();
 }
 if(value.action==="REPORT"&&(value.live_model_response!==true||value.evidence_ids.length!==2||value.trace.length!==1))return fail();
 if(value.evidence_ids.length&&value.trace.length!==1)return fail();
 if(value.live_model_response===false&&(value.action!=="STOP"||typeof value.failure_code!=="string"||!/^[A-Z_]{1,80}$/.test(value.failure_code)))return fail();
 if(value.provider_status_code!==undefined&&(!Number.isInteger(value.provider_status_code)||(value.provider_status_code as number)<100||(value.provider_status_code as number)>599))return fail();
 return value as unknown as FreshAnswer;
}
