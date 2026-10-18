/**
 * Glyph Trail by Justyna (https://justbuilt.it), adapted from the supplied Framer
 * module. Exact source and attribution: docs/research-evidence/glyph-trail-source/.
 * Original masks, Bayer lookup, wave field, stamping and diffusion math retained.
 * Budgets and lifecycle guards are local additions. This is decorative only.
 */
export const GLYPH_BAYER4 = [0,8,2,10,12,4,14,6,3,11,1,9,15,7,13,5].map(value => (value + .5) / 16);
export const GLYPH_BAYER8 = [0,32,8,40,2,34,10,42,48,16,56,24,50,18,58,26,12,44,4,36,14,46,6,38,60,28,52,20,62,30,54,22,3,35,11,43,1,33,9,41,51,19,59,27,49,17,57,25,15,47,7,39,13,45,5,37,63,31,55,23,61,29,53,21].map(value => (value + .5) / 64);
export const GLYPH_MAX_PIXELS = 600_000;
export const GLYPH_MAX_DIMENSION = 1600;
export const GLYPH_MAX_STAMPS = 192;
export const GLYPH_FPS = 24;

type Shape = (u: number, v: number, thickness: number) => boolean;
const disc = (r: number): Shape => (u,v) => u*u + v*v < r*r;
const ring = (r: number,w: number): Shape => (u,v,t) => Math.abs(Math.sqrt(u*u + v*v) - r) < Math.max(w,t);
const plus = (len: number,w = 0): Shape => (u,v,t) => { const h = Math.max(w,t); return Math.abs(u)<h && Math.abs(v)<len || Math.abs(v)<h && Math.abs(u)<len; };
const cross = (len: number,w = 0): Shape => (u,v,t) => { const h = Math.max(w,t)*1.4; return Math.abs(u)<len && Math.abs(v)<len && (Math.abs(u-v)<h || Math.abs(u+v)<h); };
const diamond = (r: number): Shape => (u,v) => Math.abs(u)+Math.abs(v)<r;
const square = (r: number): Shape => (u,v) => Math.abs(u)<r && Math.abs(v)<r;
const hollowSquare = (r: number): Shape => (u,v,t) => Math.max(Math.abs(u),Math.abs(v))<r && Math.max(Math.abs(u),Math.abs(v))>r-Math.max(.2,t*2);
const diagonal = (w: number): Shape => (u,v,t) => Math.abs(u+v)<Math.max(w,t);
const either = (...shapes: Shape[]): Shape => (u,v,t) => shapes.some(shape => shape(u,v,t));
const INK_SETS = {
  mixed:[disc(.26),plus(.6),cross(.6),ring(.58,.12),diamond(.95),square(.8)],
  circles:[disc(.2),disc(.34),disc(.48),disc(.62),disc(.76),disc(.92)],
  lines:[diagonal(.1),diagonal(.22),diagonal(.36),diagonal(.52),diagonal(.7),diagonal(.95)],
  crosses:[plus(.3),plus(.55),plus(.8),plus(.85,.2),plus(.9,.34),plus(.95,.5)],
};
const TRAIL_SETS = {
  beads:[disc(.22),ring(.5,.12),disc(.6),disc(.85)],
  stars:[disc(.2),plus(.55),either(plus(.75),cross(.6)),either(plus(.9,.14),cross(.75,.1))],
  frames:[square(.2),hollowSquare(.55),hollowSquare(.85),either(hollowSquare(.9),square(.4))],
};
export type GlyphFamily = keyof typeof INK_SETS;
export type TrailFamily = keyof typeof TRAIL_SETS;
export type GlyphTone = { contrast?: number; brightness?: number; invert?: boolean };
export type GlyphBrush = { radius?: number; strength?: number; duration?: number; spread?: number; shape?: TrailFamily; touch?: boolean };
export type GlyphLayout = { cols: number; rows: number; width: number; height: number; cell: number; scale: number };
const bounded = (value: number | undefined, fallback: number, min: number, max: number) => Number.isFinite(value) ? Math.max(min,Math.min(max,value!)) : fallback;
export const glyphClamp01 = (value: number) => value < 0 ? 0 : value > 1 ? 1 : value;

/** Render the original CSS-pixel algorithm at a bounded backing resolution. */
export function glyphLayout(width: number,height: number,requestedCell = 14): GlyphLayout {
  const w = bounded(width,1,1,100_000), h = bounded(height,1,1,100_000);
  const scale = Math.min(1,GLYPH_MAX_DIMENSION/Math.max(w,h),Math.sqrt(GLYPH_MAX_PIXELS/(w*h)));
  const cell = Math.max(4,Math.round(bounded(requestedCell,14,4,32)*scale));
  const cols = Math.max(1,Math.floor(w*scale/cell)), rows = Math.max(1,Math.floor(h*scale/cell));
  return { cols,rows,width:cols*cell,height:rows*cell,cell,scale };
}
export function glyphMasks(family: GlyphFamily | TrailFamily,cell: number,trail = false): Uint8Array[] {
  if (!Number.isInteger(cell) || cell<4 || cell>32) throw new Error("Invalid glyph cell");
  const shapes = trail ? TRAIL_SETS[family as TrailFamily] ?? TRAIL_SETS.beads : INK_SETS[family as GlyphFamily] ?? INK_SETS.mixed;
  const t = 1.1/cell;
  return shapes.map(shape => {
    const mask = new Uint8Array(cell*cell);
    for (let y=0;y<cell;y++) for (let x=0;x<cell;x++) mask[y*cell+x] = shape((x+.5)/cell*2-1,(y+.5)/cell*2-1,t) ? 1 : 0;
    return mask;
  });
}
export function glyphPackedColor(r: number,g: number,b: number,a: number): number { return (a<<24|b<<16|g<<8|r)>>>0; }
export function glyphPointer(clientX: number,clientY: number,rect: { left: number;top: number;width: number;height: number },layout: GlyphLayout): {x:number;y:number} | null {
  if (![clientX,clientY,rect.left,rect.top,rect.width,rect.height].every(Number.isFinite) || rect.width<=0 || rect.height<=0) return null;
  const x = (clientX-rect.left)/rect.width, y = (clientY-rect.top)/rect.height;
  return x<0 || x>1 || y<0 || y>1 ? null : {x:x*layout.cols,y:y*layout.rows};
}

export function createGlyphField(layout: GlyphLayout,options: {glyphs?: GlyphFamily;trailShape?: TrailFamily;pattern?: "4"|"8";tone?: GlyphTone} = {}) {
  const {cols,rows,width:W,height,cell,scale} = layout;
  if (![cols,rows,W,height,cell,scale].every(Number.isFinite) || ![cols,rows,W,height,cell].every(Number.isInteger) || cols<1 || rows<1 || cell<4 || cell>32 || W!==cols*cell || height!==rows*cell || W*height>GLYPH_MAX_PIXELS || W>GLYPH_MAX_DIMENSION || height>GLYPH_MAX_DIMENSION || scale<=0 || scale>1) throw new Error("Glyph layout exceeds budget");
  const dark = new Float32Array(cols*rows);
  let field = new Float32Array(cols*rows), next = new Float32Array(cols*rows), alive = false;
  let previous: {x:number;y:number}|null = null;
  const matrix = options.pattern === "4" ? GLYPH_BAYER4 : GLYPH_BAYER8;
  const mSize = options.pattern === "4" ? 4 : 8, mMask=mSize-1, half=mSize>>1;
  const inkMasks=glyphMasks(options.glyphs ?? "mixed",cell), trailMasks=glyphMasks(options.trailShape ?? "beads",cell,true);
  const contrast=bounded(options.tone?.contrast,.7,0,3), brightness=bounded(options.tone?.brightness,.12,-1,1), invert=options.tone?.invert ?? false;
  const shape = (d: number) => { let value=(d-.5)*contrast+.5-brightness; if(invert)value=1-value; return glyphClamp01(value); };
  function procedural(time: number) {
    const t=Number.isFinite(time)?time:0, h=Math.max(1,rows*cell/scale);
    for(let y=0;y<rows;y++) for(let x=0;x<cols;x++) {
      const px=x*cell/scale,py=y*cell/scale;
      dark[y*cols+x]=shape(.4+.14*Math.sin((px+py)*.006+t*.3)+.1*Math.sin((px*.4-py)*.009-t*.2)+.06*Math.sin((px+py*1.3)*.017+t*.25)+py/h*.12);
    }
  }
  function image(pixels: Uint8ClampedArray) {
    if(pixels.length!==cols*rows*4)throw new Error("Image sample dimensions differ");
    for(let i=0;i<cols*rows;i++) {
      const a=pixels[i*4+3]/255,r=pixels[i*4]*a+255*(1-a),g=pixels[i*4+1]*a+255*(1-a),b=pixels[i*4+2]*a+255*(1-a);
      dark[i]=shape(1-(.2126*r+.7152*g+.0722*b)/255);
    }
  }
  function stamp(x:number,y:number,r:number,strength:number) {
    const r2=r*r,x0=Math.max(0,Math.floor(x-r)),x1=Math.min(cols-1,Math.ceil(x+r)),y0=Math.max(0,Math.floor(y-r)),y1=Math.min(rows-1,Math.ceil(y+r));
    for(let yy=y0;yy<=y1;yy++)for(let xx=x0;xx<=x1;xx++) {
      const d=((xx-x)*(xx-x)+(yy-y)*(yy-y))/r2;
      if(d>=1)continue;
      const value=strength*(1-d)*(1-d),index=yy*cols+xx;
      if(value>field[index])field[index]=value;
    }
  }
  function clear() { field.fill(0);next.fill(0);alive=false;previous=null; }
  function step(elapsed:number,pointer:{x:number;y:number}|null,brush:GlyphBrush = {}) {
    const dt=bounded(elapsed,0,0,.05), radius=Math.max(1,bounded(brush.radius,50,10,300)*scale/cell),strength=bounded(brush.strength,.45,0,1.5),duration=bounded(brush.duration,1.6,.1,10),spread=bounded(brush.spread,.2,0,1);
    let stamps=0,dirty=false;
    const point=pointer && [pointer.x,pointer.y].every(Number.isFinite) && pointer.x>=0 && pointer.x<=cols && pointer.y>=0 && pointer.y<=rows ? pointer : null;
    if(point) {
      if(!previous) { stamp(point.x,point.y,radius,strength);stamps=1; }
      else if(point.x!==previous.x || point.y!==previous.y) {
        const dx=point.x-previous.x,dy=point.y-previous.y,steps=Math.min(GLYPH_MAX_STAMPS,Math.max(1,Math.ceil(Math.hypot(dx,dy)/(radius*.3))));
        for(let s=1;s<=steps;s++)stamp(previous.x+dx*s/steps,previous.y+dy*s/steps,radius,strength);
        stamps=steps;
      }
      if(!previous || previous.x!==point.x || previous.y!==point.y) {alive=true;dirty=true;}
      previous={...point};
    } else previous=null;
    if(alive) {
      const decay=Math.pow(.03,dt/duration),s=Math.min(1,spread*dt*60*.5);let max=0;
      for(let y=0;y<rows;y++)for(let x=0;x<cols;x++) {
        const i=y*cols+x,c=field[i],l=x>0?field[i-1]:c,r=x<cols-1?field[i+1]:c,up=y>0?-cols:0,down=y<rows-1?cols:0;
        const value=(c+((l+r+field[i+up]+field[i+down])*.25-c)*s)*decay;
        next[i]=value;if(value>max)max=value;
      }
      const swap=field;field=next;next=swap;
      if(max<.004){field.fill(0);alive=false;}
      dirty=true;
    }
    return {dirty,alive,stamps};
  }
  function draw(buffer:Uint32Array,palette:{background:number;ink:number;trail:number}) {
    if(buffer.length!==W*height)throw new Error("Canvas buffer dimensions differ");
    buffer.fill(palette.background);
    const blit=(cx:number,cy:number,mask:Uint8Array,color:number)=>{let offset=cy*cell*W+cx*cell,m=0;for(let y=0;y<cell;y++){for(let x=0;x<cell;x++)if(mask[m++])buffer[offset+x]=color;offset+=W;}};
    for(let y=0;y<rows;y++)for(let x=0;x<cols;x++) {
      const i=y*cols+x,threshold=matrix[(y&mMask)*mSize+(x&mMask)],other=matrix[((y+1)&mMask)*mSize+((x+half)&mMask)];
      const trailLevel=Math.min(trailMasks.length,Math.floor(glyphClamp01(field[i])*trailMasks.length+other-.25));
      if(trailLevel>0){blit(x,y,trailMasks[trailLevel-1],palette.trail);continue;}
      const inkLevel=Math.min(inkMasks.length,Math.floor(dark[i]*inkMasks.length+threshold));
      if(inkLevel>0)blit(x,y,inkMasks[inkLevel-1],palette.ink);
    }
  }
  procedural(0);
  return {procedural,image,step,draw,clear,snapshot:()=>({dark:dark.slice(),field:field.slice(),alive})};
}

export type GlyphActivity = {active:boolean;hidden:boolean;reducedMotion:boolean;intersecting:boolean};
export function glyphCanAnimate(state:GlyphActivity) { return state.active&&!state.hidden&&!state.reducedMotion&&state.intersecting; }
export function createGlyphFrameDriver(options:{requestFrame:(callback:(time:number)=>void)=>number;cancelFrame:(id:number)=>void;render:(dt:number)=>boolean;onError?:()=>void}) {
  let state:GlyphActivity={active:false,hidden:false,reducedMotion:true,intersecting:false},pending:number|null=null,last:number|null=null,disposed=false,generation=0;
  function schedule(){if(!disposed&&glyphCanAnimate(state)&&pending===null){const current=generation;pending=options.requestFrame(time=>{if(disposed||current!==generation)return;tick(time);});}}
  function tick(time:number){pending=null;if(disposed||!glyphCanAnimate(state))return;if(!Number.isFinite(time)){schedule();return;}if(last!==null&&time-last<1000/GLYPH_FPS){schedule();return;}const dt=last===null?0:Math.min(.05,Math.max(0,(time-last)/1000));last=time;try{if(options.render(dt))schedule();}catch{disposed=true;options.onError?.();}}
  return {
    update(next:GlyphActivity){if(disposed)return;const was=glyphCanAnimate(state);state={...next};if(!glyphCanAnimate(state)){generation++;if(pending!==null)options.cancelFrame(pending);pending=null;last=null;}else if(!was)schedule();},
    invalidate:schedule,
    dispose(){if(disposed)return;disposed=true;generation++;if(pending!==null)options.cancelFrame(pending);pending=null;last=null;},
  };
}
