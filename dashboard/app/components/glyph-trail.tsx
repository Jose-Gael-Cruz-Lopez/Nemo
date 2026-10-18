"use client";

import { useEffect, useRef, useState } from "react";
import {
  createGlyphField, createGlyphFrameDriver, glyphCanAnimate, glyphLayout,
  glyphPackedColor, glyphPointer, type GlyphBrush, type GlyphFamily,
  type GlyphLayout, type GlyphTone,
} from "./glyph-trail-state";
import styles from "./glyph-trail.module.css";

/** Adapted from Justyna's actual Glyph Trail module; source receipt is retained. */
export type GlyphTrailProps = {
  className?: string;
  active?: boolean;
  image?: { src: string } | null;
  cellSize?: number;
  glyphs?: GlyphFamily;
  colors?: { background?: string; ink?: string; trail?: string };
  pattern?: "4" | "8";
  tone?: GlyphTone;
  trail?: GlyphBrush;
  speed?: number;
};

export function GlyphTrail({ className, active = true, image, cellSize = 14,
  glyphs = "mixed", colors, pattern = "8", tone, trail, speed = .15 }: GlyphTrailProps) {
  const root = useRef<HTMLDivElement>(null), canvas = useRef<HTMLCanvasElement>(null);
  const driver = useRef<ReturnType<typeof createGlyphFrameDriver> | null>(null);
  const resync = useRef<(() => void) | null>(null);
  const [renderer, setRenderer] = useState<"fallback" | "canvas">("fallback");
  const [loaded, setLoaded] = useState<{ src: string; image: HTMLImageElement | null } | null>(null);
  const src = image?.src || null;
  const imgEl = loaded?.src === src ? loaded?.image ?? null : null;
  const background = colors?.background ?? "#edf7fe", ink = colors?.ink ?? "#dbeaf4", trailColor = colors?.trail ?? "#c7e1f1";
  const contrast = tone?.contrast ?? .7, brightness = tone?.brightness ?? .12, invert = tone?.invert ?? false;
  const radius=trail?.radius ?? 50,strength=trail?.strength ?? .45,duration=trail?.duration ?? 1.6,spread=trail?.spread ?? .2,touch=trail?.touch ?? false,trailShape=trail?.shape ?? "beads";
  const live = useRef({ active, speed, brush: { radius, strength, duration, spread, touch, shape: trailShape } });

  useEffect(() => {
    live.current = { active, speed, brush: { radius, strength, duration, spread, touch, shape: trailShape } };
    resync.current?.(); driver.current?.invalidate();
  }, [active,speed,radius,strength,duration,spread,touch,trailShape]);

  useEffect(() => {
    if (!src) return;
    let mounted = true;
    const picture = new Image(); picture.crossOrigin = "anonymous";
    picture.onload = () => { if (mounted) setLoaded({ src, image: picture.naturalWidth > 0 && picture.naturalHeight > 0 ? picture : null }); };
    picture.onerror = () => { if (mounted) setLoaded({ src, image: null }); };
    picture.src = src;
    return () => { mounted = false; picture.onload = null; picture.onerror = null; };
  }, [src]);

  useEffect(() => {
    const mount = root.current, target = canvas.current;
    if (!mount || !target) return;
    const element: HTMLDivElement = mount, surface: HTMLCanvasElement = target;
    const ctx = surface.getContext("2d", { alpha: false });
    if (!ctx) return;
    let disposed=false,failed=false,shown=false,intersecting=false,time=0,usingImage=false;
    let layout: GlyphLayout | null=null, field: ReturnType<typeof createGlyphField> | null=null;
    let imageData: ImageData | null=null, buffer: Uint32Array | null=null;
    let pointer: { clientX:number;clientY:number } | null=null;
    const query=window.matchMedia("(prefers-reduced-motion: reduce)");
    const colorCanvas=document.createElement("canvas"); colorCanvas.width=1;colorCanvas.height=1;
    const colorCtx=colorCanvas.getContext("2d",{willReadFrequently:true});
    function packed(color:string,fallback:string) {
      if (!colorCtx) return glyphPackedColor(237,247,254,255);
      const token=/^var\([^,]+,\s*(.+)\)$/.exec(color.trim());
      colorCtx.clearRect(0,0,1,1);colorCtx.fillStyle=fallback;colorCtx.fillStyle=token?.[1] ?? color;colorCtx.fillRect(0,0,1,1);
      const [r,g,b,a]=colorCtx.getImageData(0,0,1,1).data;
      return glyphPackedColor(r,g,b,a);
    }
    const palette={background:packed(background,"#edf7fe"),ink:packed(ink,"#dbeaf4"),trail:packed(trailColor,"#c7e1f1")};
    function fail() { if(disposed||failed)return;failed=true;frames.dispose();setRenderer("fallback"); }
    function draw() {
      if(disposed||failed||!field||!buffer||!imageData)return;
      field.draw(buffer,palette);ctx!.putImageData(imageData,0,0);
      if(!shown){shown=true;setRenderer("canvas");}
    }
    const frames=createGlyphFrameDriver({
      requestFrame:callback=>window.requestAnimationFrame(callback),cancelFrame:id=>window.cancelAnimationFrame(id),
      render(dt) {
        if(disposed||failed||!field||!layout)return false;
        const current=live.current,point=pointer?glyphPointer(pointer.clientX,pointer.clientY,element.getBoundingClientRect(),layout):null;
        const result=field.step(dt,point,current.brush);
        const drift=Number.isFinite(current.speed)?Math.max(0,Math.min(5,current.speed)):0;
        if(drift>0&&!usingImage){time+=dt*drift;field.procedural(time);}
        if(result.dirty||drift>0&&!usingImage)draw();
        return result.alive||drift>0&&!usingImage;
      },onError:fail,
    });
    driver.current=frames;
    function activity() { return {active:live.current.active,hidden:document.hidden,reducedMotion:query.matches,intersecting}; }
    function sync() {
      if(disposed||failed)return;
      const state=activity();frames.update(state);
      if(!glyphCanAnimate(state)){pointer=null;field?.clear();if(!document.hidden)draw();}
      else frames.invalidate();
    }
    resync.current=sync;
    function sampleImage() {
      if(!imgEl||!layout||!field)return false;
      const off=document.createElement("canvas");off.width=layout.cols;off.height=layout.rows;
      try {
        const context=off.getContext("2d",{willReadFrequently:true});if(!context)return false;
        context.imageSmoothingEnabled=true;context.imageSmoothingQuality="high";
        const scale=Math.max(layout.cols/imgEl.naturalWidth,layout.rows/imgEl.naturalHeight),width=imgEl.naturalWidth*scale,height=imgEl.naturalHeight*scale;
        context.drawImage(imgEl,(layout.cols-width)/2,(layout.rows-height)/2,width,height);
        field.image(context.getImageData(0,0,layout.cols,layout.rows).data);return true;
      } catch { return false; } finally {off.width=1;off.height=1;}
    }
    function resize() {
      if(disposed||failed)return;
      const next=glyphLayout(element.offsetWidth,element.offsetHeight,cellSize);
      if(layout&&layout.width===next.width&&layout.height===next.height&&layout.cell===next.cell&&layout.scale===next.scale)return;
      try {
        layout=next;surface.width=next.width;surface.height=next.height;
        field=createGlyphField(next,{glyphs,trailShape,pattern,tone:{contrast,brightness,invert}});
        imageData=ctx!.createImageData(next.width,next.height);buffer=new Uint32Array(imageData.data.buffer);
        usingImage=sampleImage();if(!usingImage)field.procedural(time);
        draw();frames.invalidate();
      } catch {fail();}
    }
    function onMove(event:PointerEvent) {
      if(disposed||failed||!glyphCanAnimate(activity())||event.pointerType!=="mouse"&&!live.current.brush.touch)return;
      pointer={clientX:event.clientX,clientY:event.clientY};frames.invalidate();
    }
    const onLeave=()=>{pointer=null;frames.invalidate();};
    const rect=element.getBoundingClientRect();intersecting=rect.width>0&&rect.height>0&&rect.bottom>0&&rect.right>0&&rect.top<window.innerHeight&&rect.left<window.innerWidth;
    resize();
    const ro=new ResizeObserver(resize);ro.observe(element);
    const io=new IntersectionObserver(entries=>{if(disposed)return;intersecting=entries.some(entry=>entry.target===element&&entry.isIntersecting);sync();});io.observe(element);
    window.addEventListener("pointermove",onMove,{passive:true});document.addEventListener("pointerleave",onLeave);window.addEventListener("blur",onLeave);
    document.addEventListener("visibilitychange",sync);query.addEventListener("change",sync);sync();
    return()=>{
      disposed=true;frames.dispose();ro.disconnect();io.disconnect();
      window.removeEventListener("pointermove",onMove);document.removeEventListener("pointerleave",onLeave);window.removeEventListener("blur",onLeave);
      document.removeEventListener("visibilitychange",sync);query.removeEventListener("change",sync);
      if(driver.current===frames)driver.current=null;if(resync.current===sync)resync.current=null;
      field?.clear();field=null;buffer=null;imageData=null;pointer=null;surface.width=1;surface.height=1;colorCanvas.width=1;colorCanvas.height=1;
    };
  }, [imgEl,cellSize,glyphs,pattern,background,ink,trailColor,trailShape,contrast,brightness,invert]);

  return <div ref={root} className={`${styles.root}${className?` ${className}`:""}`} style={{backgroundColor:background}} aria-hidden="true" data-glyph-trail={renderer}><canvas ref={canvas} className={styles.canvas}/></div>;
}
export default GlyphTrail;
