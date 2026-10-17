# Lavender workspace and local operator sign-in

The root URL is ReefTrace's public introduction, using lavender glass surfaces and an illustrative vector contour landscape. The Observe/Trace/Prevent controls describe the workflow; their terrain is decorative, not measured geography. Lower cards link to working product views.

- `/login` verifies the existing local operator token with `GET /api/v1/operator/session` before granting operator state.
- `/workspace` retains all existing source, prevention, camera, research and configuration functions. It can be explored read-only without an operator token.
- Legacy links such as `/#investigations?case=case-…` redirect to `/workspace#investigations?case=case-…`. Only recognized view names and bounded, encoded case IDs are retained.
- The token is held in the shared React tree for this browser tab only. Navigation using Next links keeps it in memory; reloading clears it. No localStorage, sessionStorage, token URL, auth cookie, provider key or fabricated email account is introduced.
- Local sign-in is shared operator authorization for actions. It is **not** an individual account system or a new privacy perimeter for existing locally public evidence reads.

## Local API path

The default browser API base is empty. Next rewrites `/api/v1/:path*` to the fixed loopback FastAPI listener at `http://127.0.0.1:8000/api/v1/:path*`. Request bodies, query strings, status codes and the caller's Authorization header are preserved. The proxy does not inject an operator token or provider credentials and cannot select an arbitrary upstream. A 120-second proxy timeout accommodates the existing bounded Chalk request. The API reference link opens port8000 directly. Both dev services still bind to loopback.

This avoids browser private-network CORS preflights in the default local flow. Failed POSTs are never automatically retried: a network error may have happened after an observation or trial was persisted. API unavailability still produces an actionable error.

## Visual decisions

Lavender canvas, translucent sidebar/header/cards, dark plum primary text, solid-enough table and chart surfaces, visible status colors, focus rings, responsive navigation, reduced motion and reduced transparency. The contour illustration is implemented in SVG and never calls a media-generation service. The scientific graph line colors and synthetic/physical distinctions remain readable and distinct.

## ML handoff in the same release

Data Lab includes the frozen four-drifter study, an explicitly exploratory transfer diagnostic, and an acquisition-readiness report. The new transfer model's negative result is retained; no model is silently promoted. New NOAA acquisition failed, so zero new drifters are reported. See `grok-ml-next-study.md` for the actual Grok-assisted protocol, results and next dataset requirements.
