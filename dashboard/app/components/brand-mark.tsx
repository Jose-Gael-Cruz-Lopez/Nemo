import type { SVGProps } from "react";
import { WAVE_MARK_PATH } from "./brand";

/** The same filled wave is used across the landing page, login and workspace. */
export function BrandMark(props: SVGProps<SVGSVGElement>) {
  return <svg width="38" height="32" viewBox="0 0 160 128" fill="currentColor" aria-hidden="true" focusable="false" {...props}><path d={WAVE_MARK_PATH} /></svg>;
}
