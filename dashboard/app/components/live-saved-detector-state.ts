/** Local display-only preview. Historical mappings never become current calibration. */
import { metricGrid, projectPoint, type Point, type WaterMapping } from "./camera-grid-state.ts";
import { estimatedTrayMapping, ESTIMATED_TRAY_BOUNDS, type RehearsalBounds } from "./estimated-tank-rehearsal-state.ts";
import { parseSavedCalibrationBundle, parseSavedCalibrationList, type SavedCalibrationBundle } from "./saved-calibration-state.ts";
import type { CameraStatus } from "./field-workflow-state.ts";

export const LIVE_DETECTOR_POLL_MS = 125;
export const LIVE_DETECTOR_MAX_AGE_S = 2;
export type PreviewRequest = <T>(path: string, body?: unknown, options?: { signal?: AbortSignal; independent?: boolean }) => Promise<T>;
export type SavedPreviewReference = { reference_id: string; camera_session_id: string; image_size_px: [number,number]; captured_at: number; detector: string; full_frame: true; policy_id?: string };
export type LiveDetectorMode = "foreground_surface_v2" | "saved_green_marker_preview_v1";
export type MarkerAreaSource = {report_id:string;clip_id:string;point_index:number;area_px:number;area_px_range:[number,number];source_policy_sha256:string};
export type LivePreviewConfig = { detector_mode:LiveDetectorMode;marker_area_source:MarkerAreaSource|null;preview_id: string; camera_session_id: string; image_size_px: [number,number]; reference_id: string; reference_camera_session_id: string; source_calibration_id: string; source_camera_session_id: string; homography_image_to_cm: number[][]; detection_polygon_px: number[][]; policy_id: "foreground_green_cap_v1" | "saved_green_marker_preview_v1"; policy_sha256: string; warnings: string[] };
export type PreviewDetection = { pixel_x: number; pixel_y: number; reference_pixel_x: number | null; reference_pixel_y: number | null; area_px: number; bbox_px: [number,number,number,number] };
export type LivePreviewFrame = { detector_mode:LiveDetectorMode;saved_foreground_status:"OK"|"SCENE_CHANGED"|"VIEW_OBSTRUCTED";saved_foreground_rejection:string|null;alignment_rejection:string|null;preview_id: string; camera_session_id: string; image_size_px: [number,number]; sequence: number; received_utc: string; received_mono_s: number; age_s: number; timestamp_kind: "host_receipt_not_exposure"; jpeg_data_url: string; observed: boolean; reason: string | null; scene_rejection: string | null; alignment: { method:"foreground_phase_translation_v1"|"orb_translation_estimate_v1";applied: boolean; dx_px: number; dy_px: number; confidence: number } | null; point: (PreviewDetection & { estimated_x_cm: number | null; estimated_y_cm: number | null }) | null; detections: PreviewDetection[]; candidate_count: number; rejected_count: number };
export type LiveSavedDetectorState = { phase: "off" | "configuring" | "live" | "error"; config: LivePreviewConfig | null; frame: LivePreviewFrame | null; error: string | null };
export const INITIAL_LIVE_SAVED_STATE: LiveSavedDetectorState = { phase: "off", config: null, frame: null, error: null };
const object = (v: unknown): v is Record<string,unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const text = (v: unknown, max=200): v is string => typeof v === "string" && v.length > 0 && v.length <= max;
const count = (v: unknown, max=1e9): v is number => Number.isInteger(v) && (v as number) >= 0 && (v as number) <= max;
const hash = (v: unknown): v is string => typeof v === "string" && /^[a-f0-9]{64}$/.test(v);
function fail(message="The live detector response did not match its display-only contract."): never { throw new Error(message); }
function dimensions(v: unknown): [number,number] { if (!Array.isArray(v)||v.length!==2||!v.every(n=>Number.isInteger(n)&&n>=2&&n<=4096))fail();return[v[0],v[1]]; }
function polygon(v: unknown, [w,h]:[number,number]): number[][] { if(!Array.isArray(v)||v.length<3||v.length>100||!v.every(p=>Array.isArray(p)&&p.length===2&&p.every(finite)&&p[0]>=0&&p[0]<w&&p[1]>=0&&p[1]<h))fail();return v.map(p=>[...p]); }
function fresh(camera: CameraStatus|null): asserts camera is CameraStatus & { session_id:string;width:number;height:number } {
  if(!camera?.running||!camera.fresh||!camera.session_id||!camera.width||!camera.height)fail("The local camera has no fresh frames. The detector does not start or restart the webcam.");
}
export function parsePreviewReferences(value:unknown): SavedPreviewReference[] {
  if(!object(value)||!Array.isArray(value.references)||value.references.length>20)fail("The saved background list was incomplete.");
  return value.references.map(v=>{if(!object(v)||!text(v.reference_id)||!text(v.camera_session_id)||!finite(v.captured_at)||v.captured_at<0||!text(v.detector)||v.full_frame!==true)fail("The saved background list was incomplete.");return{reference_id:v.reference_id,camera_session_id:v.camera_session_id,image_size_px:dimensions(v.image_size_px),captured_at:v.captured_at,detector:v.detector,full_frame:true,...(text(v.policy_id)?{policy_id:v.policy_id}:{})};});
}
export function selectSavedPreviewInputs(referenceResponse:unknown, calibrationResponse:unknown,camera:CameraStatus|null) {
  fresh(camera);
  const refs=parsePreviewReferences(referenceResponse).filter(r=>r.image_size_px[0]===camera.width&&r.image_size_px[1]===camera.height&&(r.detector==="foreground_reference_v1"||r.detector==="foreground_surface_v2"&&r.policy_id==="foreground_green_cap_v1"));
  const reference=refs.find(r=>r.camera_session_id===camera.session_id)??refs[0];
  if(!reference)fail("No intact saved full-frame background matches this camera resolution. The preview did not create a new background.");
  const cals=parseSavedCalibrationList(calibrationResponse).filter(c=>c.approved&&c.image_size_px[0]===camera.width&&c.image_size_px[1]===camera.height);
  const calibration=cals.find(c=>c.camera_session_id===reference.camera_session_id)??cals[0];
  if(!calibration)fail("No approved historical mapping matches this camera resolution. No coordinates were invented.");
  return{reference,calibration};
}
export function buildLivePreviewConfig(reference:SavedPreviewReference,source:SavedCalibrationBundle,camera:CameraStatus|null,bounds:RehearsalBounds=ESTIMATED_TRAY_BOUNDS) {
  fresh(camera);const bundle=parseSavedCalibrationBundle(source),mapping=estimatedTrayMapping(bundle,camera,bounds);
  if(!bundle.calibration.approved||reference.image_size_px.join()!==mapping.image_size_px.join())fail("The selected saved setup does not match this frame size.");
  return{reference_id:reference.reference_id,source:bundle,detection_polygon_px:mapping.mapping_polygon_px,detector_mode:"saved_green_marker_preview_v1" as const};
}
export function parseLivePreviewConfig(value:unknown,source:SavedCalibrationBundle,reference:SavedPreviewReference,camera:CameraStatus|null):LivePreviewConfig {
  fresh(camera);const old=parseSavedCalibrationBundle(source).calibration;
  if(!object(value)||value.schema_version!=="nemo_detector_preview_config_v1"||!text(value.preview_id)||value.camera_session_id!==camera.session_id
    ||value.data_origin!=="LOCAL_LIVE_DISPLAY_ESTIMATED_COORDINATES"||value.validation_status!=="UNVALIDATED"||value.current_alignment_verified!==false||value.approved_for_inference!==false||value.measured_flow_eligible!==false||value.calibration_id!==null||value.profile_id!==null||value.case_id!==null)fail();
  const size=dimensions(value.image_size_px);
  if(size[0]!==camera.width||size[1]!==camera.height||value.reference_id!==reference.reference_id||value.reference_camera_session_id!==reference.camera_session_id||value.source_calibration_id!==old.calibration_id||value.source_camera_session_id!==old.camera_session_id||!hash(value.source_content_sha256)||JSON.stringify(value.homography_image_to_cm)!==JSON.stringify(old.homography_image_to_cm))fail("The live display changed the saved setup or camera identity.");
  const mode=value.detector_mode;if(mode!=="foreground_surface_v2"&&mode!=="saved_green_marker_preview_v1")fail();
  if(!object(value.policy)||value.policy.policy_id!==(mode==="saved_green_marker_preview_v1"?"saved_green_marker_preview_v1":"foreground_green_cap_v1")||!hash(value.policy.policy_sha256)||!Array.isArray(value.warnings)||value.warnings.length>20||!value.warnings.every(w=>text(w,3000)))fail();
  let marker:MarkerAreaSource|null=null;
  if(mode==="saved_green_marker_preview_v1"){const m=value.marker_area_source;if(!object(m)||!text(m.report_id)||!text(m.clip_id)||!count(m.point_index)||!finite(m.area_px)||m.area_px<=0||!Array.isArray(m.area_px_range)||m.area_px_range.length!==2||!m.area_px_range.every(finite)||m.area_px_range[0]<=0||m.area_px_range[1]<=m.area_px_range[0]||!hash(m.source_policy_sha256))fail();marker={report_id:m.report_id,clip_id:m.clip_id,point_index:m.point_index,area_px:m.area_px,area_px_range:[m.area_px_range[0],m.area_px_range[1]],source_policy_sha256:m.source_policy_sha256};}
  else if(value.marker_area_source!==null)fail();
  return{detector_mode:mode,marker_area_source:marker,preview_id:value.preview_id,camera_session_id:camera.session_id,image_size_px:size,reference_id:reference.reference_id,reference_camera_session_id:reference.camera_session_id,source_calibration_id:old.calibration_id,source_camera_session_id:old.camera_session_id,homography_image_to_cm:old.homography_image_to_cm.map(row=>[...row]),detection_polygon_px:polygon(value.detection_polygon_px,size),policy_id:mode==="saved_green_marker_preview_v1"?"saved_green_marker_preview_v1":"foreground_green_cap_v1",policy_sha256:value.policy.policy_sha256,warnings:[...value.warnings] as string[]};
}
function detection(v:unknown,[w,h]:[number,number]):PreviewDetection {
  if(!object(v)||![v.pixel_x,v.pixel_y,v.area_px].every(finite)||(v.reference_pixel_x!==null&&!finite(v.reference_pixel_x))||(v.reference_pixel_y!==null&&!finite(v.reference_pixel_y))||(v.pixel_x as number)<0||(v.pixel_x as number)>=w||(v.pixel_y as number)<0||(v.pixel_y as number)>=h||(v.area_px as number)<=0||!Array.isArray(v.bbox_px)||v.bbox_px.length!==4||!v.bbox_px.every(finite))fail();
  const[x,y,bw,bh]=v.bbox_px;if(x<0||y<0||bw<=0||bh<=0||x+bw>w+1e-6||y+bh>h+1e-6)fail();
  return{pixel_x:v.pixel_x as number,pixel_y:v.pixel_y as number,reference_pixel_x:v.reference_pixel_x as number|null,reference_pixel_y:v.reference_pixel_y as number|null,area_px:v.area_px as number,bbox_px:[x,y,bw,bh]};
}
export function parseLivePreviewFrame(value:unknown,config:LivePreviewConfig,previousSequence:number|null=null):LivePreviewFrame {
  if(!object(value)||value.schema_version!=="nemo_detector_preview_frame_v1"||value.detector_mode!==config.detector_mode||value.data_origin!=="LOCAL_LIVE_DISPLAY_ESTIMATED_COORDINATES"||value.validation_status!=="UNVALIDATED"||value.approved_for_inference!==false||value.measured_flow_eligible!==false||value.calibration_id!==null||value.profile_id!==null||value.case_id!==null||value.preview_id!==config.preview_id||value.camera_session_id!==config.camera_session_id||dimensions(value.image_size_px).join()!==config.image_size_px.join()||!count(value.sequence)||previousSequence!==null&&(value.sequence as number)<previousSequence
    ||!text(value.received_utc)||!Number.isFinite(Date.parse(value.received_utc))||!finite(value.received_mono_s)||value.received_mono_s<0||!finite(value.age_s)||value.age_s<0||value.age_s>LIVE_DETECTOR_MAX_AGE_S||value.timestamp_kind!=="host_receipt_not_exposure")fail("The detector frame is stale or belongs to another camera session. The overlay was stopped.");
  if(!["OK","SCENE_CHANGED","VIEW_OBSTRUCTED"].includes(value.saved_foreground_status as string)||(value.saved_foreground_rejection!==null&&!text(value.saved_foreground_rejection,3000))||(value.alignment_rejection!==null&&!text(value.alignment_rejection,3000)))fail();
  if(typeof value.jpeg_data_url!=="string"||value.jpeg_data_url.length>853359||!/^data:image\/jpeg;base64,\/9j\/[A-Za-z0-9+/]*={0,2}$/.test(value.jpeg_data_url)||typeof value.observed!=="boolean"||(value.reason!==null&&!text(value.reason))||(value.scene_rejection!==null&&!text(value.scene_rejection))||!Array.isArray(value.detections)||value.detections.length>1000||!object(value.diagnostics)||![value.diagnostics.candidate_count,value.diagnostics.accepted_count,value.diagnostics.rejected_count].every(n=>count(n,100000)))fail();
  let alignment:LivePreviewFrame["alignment"]=null;
  if(value.alignment!==null){const a=value.alignment;if(!object(a)||typeof a.applied!=="boolean"||(a.method!=="foreground_phase_translation_v1"&&a.method!=="orb_translation_estimate_v1")||![a.dx_px,a.dy_px,a.confidence].every(finite)||Math.hypot(a.dx_px as number,a.dy_px as number)>(a.method==="orb_translation_estimate_v1"?64:8)||(a.confidence as number)<0)fail();alignment={method:a.method,applied:a.applied,dx_px:a.dx_px as number,dy_px:a.dy_px as number,confidence:a.confidence as number};}
  const detections=value.detections.map(d=>detection(d,config.image_size_px));
  if(value.diagnostics.accepted_count!==detections.length)fail();
  const [dx,dy]=alignment?.applied?[alignment.dx_px,alignment.dy_px]:[0,0];
  if(detections.some(d=>alignment?d.reference_pixel_x===null||d.reference_pixel_y===null||Math.abs(d.pixel_x-d.reference_pixel_x-dx)>1e-6||Math.abs(d.pixel_y-d.reference_pixel_y-dy)>1e-6:d.reference_pixel_x!==null||d.reference_pixel_y!==null))fail("The detector coordinate alignment does not match its exact JPEG frame.");
  let point:LivePreviewFrame["point"]=null;
  if(value.observed){if(!object(value.point)||detections.length!==1||value.reason!==null||value.scene_rejection!==null)fail();const d=detection(value.point,config.image_size_px);
    if(JSON.stringify(d)!==JSON.stringify(detections[0]))fail();
    if(alignment){if(!finite(value.point.estimated_x_cm)||!finite(value.point.estimated_y_cm)||d.reference_pixel_x===null||d.reference_pixel_y===null)fail();const projected=projectPoint(config.homography_image_to_cm,[d.reference_pixel_x,d.reference_pixel_y]);if(!projected||Math.abs(projected[0]-value.point.estimated_x_cm)>1e-6||Math.abs(projected[1]-value.point.estimated_y_cm)>1e-6)fail();}
    else if(value.point.estimated_x_cm!==null||value.point.estimated_y_cm!==null)fail();
    point={...d,estimated_x_cm:value.point.estimated_x_cm as number|null,estimated_y_cm:value.point.estimated_y_cm as number|null};}
  else if(value.point!==null||value.reason===null)fail();
  if(value.scene_rejection!==null&&detections.length)fail();
  return{detector_mode:config.detector_mode,saved_foreground_status:value.saved_foreground_status as LivePreviewFrame["saved_foreground_status"],saved_foreground_rejection:value.saved_foreground_rejection as string|null,alignment_rejection:value.alignment_rejection as string|null,preview_id:config.preview_id,camera_session_id:config.camera_session_id,image_size_px:[...config.image_size_px],sequence:value.sequence as number,received_utc:value.received_utc,received_mono_s:value.received_mono_s,age_s:value.age_s,timestamp_kind:value.timestamp_kind,jpeg_data_url:value.jpeg_data_url,observed:value.observed,reason:value.reason as string|null,scene_rejection:value.scene_rejection as string|null,alignment,point,detections,candidate_count:value.diagnostics.candidate_count as number,rejected_count:value.diagnostics.rejected_count as number};
}
/** Shift only the displayed grid into raw-frame pixels; the historical H remains unchanged. */
export function livePreviewGrid(config:LivePreviewConfig,frame:LivePreviewFrame) {
  if(frame.scene_rejection||!frame.alignment)return null;
  const mapping:WaterMapping={approved:false,estimated:true,plane:"estimated_water_surface",units:"cm",camera_session_id:config.camera_session_id,image_size_px:config.image_size_px,homography_image_to_cm:config.homography_image_to_cm,mapping_polygon_px:config.detection_polygon_px};
  const grid=metricGrid(mapping,config.camera_session_id,...config.image_size_px);if(!grid)return null;
  const[dx,dy]=frame.alignment.applied?[frame.alignment.dx_px,frame.alignment.dy_px]:[0,0];
  const shift=([x,y]:Point):Point=>[x+dx,y+dy];
  return{...grid,hull:grid.hull.map(shift),lines:grid.lines.map(line=>({...line,start:shift(line.start),end:shift(line.end)}))};
}

type Context={request:PreviewRequest;camera:CameraStatus|null;disabled:boolean;bounds?:RehearsalBounds};
type Scheduler={set:(callback:()=>void,ms:number)=>unknown;clear:(handle:unknown)=>void};
export class LiveSavedDetectorController {
  private state=INITIAL_LIVE_SAVED_STATE;private listeners=new Set<()=>void>();private context:Context;private version=0;private pending:AbortController|null=null;private timer:unknown=null;private expiry:unknown=null;private frameDeadline=0;private scheduler:Scheduler;
  constructor(context:Context,scheduler:Scheduler={set:(callback,ms)=>setTimeout(callback,ms),clear:handle=>clearTimeout(handle as ReturnType<typeof setTimeout>)}){this.context=context;this.scheduler=scheduler;}
  getSnapshot=()=>this.state;
  getServerSnapshot=()=>INITIAL_LIVE_SAVED_STATE;
  subscribe=(listener:()=>void)=>{this.listeners.add(listener);return()=>{this.listeners.delete(listener);};};
  private publish(state:LiveSavedDetectorState){this.state=state;for(const listener of this.listeners)listener();}
  private cancel(){this.version++;this.pending?.abort();this.pending=null;if(this.timer!==null)this.scheduler.clear(this.timer);this.timer=null;if(this.expiry!==null)this.scheduler.clear(this.expiry);this.expiry=null;this.frameDeadline=0;}
  setContext(next:Context){const old=this.context;this.context=next;const key=(c:Context)=>JSON.stringify([c.camera?.session_id,c.camera?.width,c.camera?.height,c.camera?.running,c.camera?.fresh,c.disabled,c.bounds??ESTIMATED_TRAY_BOUNDS]);if(old.request!==next.request||key(old)!==key(next)){this.cancel();if(this.state.phase!=="off")this.publish({phase:"error",config:null,frame:null,error:"Camera or operator context changed. The live detector was stopped; the saved measurements were kept."});}}
  stop=()=>{this.cancel();this.publish(INITIAL_LIVE_SAVED_STATE);};
  async start(){if(this.context.disabled||this.state.phase==="configuring"||this.state.phase==="live")return;this.cancel();const version=this.version,controller=new AbortController();this.pending=controller;const{request,camera,bounds}=this.context;this.publish({phase:"configuring",config:null,frame:null,error:null});const current=()=>version===this.version&&!controller.signal.aborted;try{fresh(camera);const[refs,cals]=await Promise.all([request<unknown>("/camera/detector-preview/references",undefined,{signal:controller.signal,independent:true}),request<unknown>("/vision/calibrations",undefined,{signal:controller.signal,independent:true})]);if(!current())return;const{reference,calibration}=selectSavedPreviewInputs(refs,cals,camera);const source=parseSavedCalibrationBundle(await request<unknown>(`/vision/calibrations/${encodeURIComponent(calibration.calibration_id)}`,undefined,{signal:controller.signal,independent:true}));if(!current())return;const body=buildLivePreviewConfig(reference,source,camera,bounds);const config=parseLivePreviewConfig(await request<unknown>("/camera/detector-preview/config",body,{signal:controller.signal,independent:true}),source,reference,camera);if(!current())return;this.pending=null;this.publish({phase:"live",config,frame:null,error:null});await this.poll(version,config);}catch(error){if(current()){this.cancel();this.publish({phase:"error",config:null,frame:null,error:error instanceof Error?error.message:"The saved live detector could not be configured."});}}}
  private async poll(version:number,config:LivePreviewConfig){if(version!==this.version||this.context.disabled)return;const controller=new AbortController();this.pending=controller;const started=Date.now();try{const raw=await this.context.request<unknown>(`/camera/detector-preview/${encodeURIComponent(config.preview_id)}`,undefined,{signal:controller.signal,independent:true});if(version!==this.version||controller.signal.aborted)return;const frame=parseLivePreviewFrame(raw,config,this.state.frame?.sequence??null);const now=Date.now(),deadline=now+Math.max(0,LIVE_DETECTOR_MAX_AGE_S-frame.age_s-(now-started)/1000)*1000;
      this.frameDeadline=this.state.frame?.sequence===frame.sequence?Math.min(this.frameDeadline,deadline):deadline;
      if(this.frameDeadline<=now)fail("The detector frame arrived too late. The overlay was stopped.");
      this.pending=null;this.publish({phase:"live",config,frame,error:null});
      if(this.expiry!==null)this.scheduler.clear(this.expiry);
      this.expiry=this.scheduler.set(()=>{if(version===this.version){this.cancel();this.publish({phase:"error",config:null,frame:null,error:"No fresh detector frame arrived in time. The old overlay was cleared."});}},this.frameDeadline-now);
      this.timer=this.scheduler.set(()=>{this.timer=null;void this.poll(version,config);},LIVE_DETECTOR_POLL_MS);}catch(error){if(version===this.version&&!controller.signal.aborted){this.cancel();this.publish({phase:"error",config:null,frame:null,error:error instanceof Error?error.message:"The live detector stopped after a read error."});}}}
}
