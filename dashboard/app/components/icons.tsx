import type { ReactNode, SVGProps } from "react";

export type IconName = "overview" | "cases" | "camera" | "settings" | "arrow" | "search" | "chevron" | "check" | "key" | "close" | "plus" | "clock" | "agent" | "wave" | "file" | "play" | "stop" | "help";

const paths: Record<IconName, ReactNode> = {
  overview: <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>,
  cases: <><rect x="5" y="5" width="15" height="16" rx="2" /><path d="M16 5V3H3v14h2M9 10h7M9 14h7M9 18h4" /></>,
  camera: <><rect x="3" y="6" width="13" height="12" rx="2" /><path d="m16 10 5-3v10l-5-3" /></>,
  settings: <><path d="M4 6h16M4 12h16M4 18h16" /><circle cx="8" cy="6" r="2" fill="var(--surface)" /><circle cx="16" cy="12" r="2" fill="var(--surface)" /><circle cx="10" cy="18" r="2" fill="var(--surface)" /></>,
  arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
  search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4.5 4.5" /></>,
  chevron: <path d="m9 5 7 7-7 7" />,
  check: <path d="m5 12 4 4L19 6" />,
  key: <><circle cx="8" cy="9" r="4" /><path d="m11 12 9 9m-3-3 3-3m-6 0 3-3" /></>,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  plus: <path d="M12 5v14M5 12h14" />,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  agent: <><rect x="4" y="7" width="16" height="13" rx="3" /><path d="M12 3v4M8 12h.01M16 12h.01M9 16h6M1 11v5m22-5v5" /></>,
  wave: <><path d="M3 8c3-5 6 5 9 0s6 5 9 0M3 14c3-5 6 5 9 0s6 5 9 0M3 20c3-5 6 5 9 0s6 5 9 0" /></>,
  file: <><path d="M14 3H5v18h14V8zm0 0v5h5M8 12h8m-8 4h6" /></>,
  play: <path d="m8 4 12 8-12 8z" />,
  stop: <rect x="5" y="5" width="14" height="14" rx="2" />,
  help: <><circle cx="12" cy="12" r="9" /><path d="M9.5 9a2.5 2.5 0 1 1 4 2c-1 .6-1.5 1-1.5 2M12 17h.01" /></>,
};

export function Icon({ name, ...props }: SVGProps<SVGSVGElement> & { name: IconName }) {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name]}</svg>;
}
