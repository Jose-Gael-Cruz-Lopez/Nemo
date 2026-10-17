# Public ocean showcase

The Vercel preview is a **read-only ocean comparison**, separate from the full local experiment application. It reuses the same combined graph, layer checkboxes, release selector, changing-current arrows, scenario controls and scientific disclosures. It serves checked numerical snapshots without Python, a camera, local SQLite or provider credentials.

## Deployment target

- Vercel root directory: `dashboard`, framework: Next.js, build: `npm run build`.
- Set only `TIDEWARD_PUBLIC_SHOWCASE=true` in that preview environment. No Chalk, Photon, xAI or local operator keys are needed or authorized for this deployment.
- `/demo` is the public page. In showcase mode `/`, `/workspace` and `/login` temporarily redirect there. The local API rewrite is disabled in that mode; an unimplemented local API returns unavailable rather than contacting a visitor’s computer.
- Local development with the flag absent preserves all existing routes and the localhost FastAPI rewrite. `/demo` is also available locally for preview testing.
- Do not point `NEXT_PUBLIC_API_BASE_URL` at the team’s local API or upload a private `.env`.

## Exact data boundary

`python -m scripts.export_ocean_showcase` reads the pinned PacIOOS snapshot and executes the existing ocean comparison for both fixed scenarios. It acquires no new data, reads no provider credentials and starts no runtime, camera or worker. It exports canonical JSON strings under `dashboard/showcase/ocean-reports.json` with byte digests, report identities, method/source checkpoint provenance and an export timestamp. Each report passes the same backend identity and scientific-boundary checks as the local API.

Each scenario includes two freshness representations with independently recomputed canonical report hashes: `forecast_snapshot` and `archived_forecast_snapshot`. Only the mode and its resulting full-report digest differ. Paths, outcomes, scenario and method remain identical. The server chooses archived only after the forcing’s valid end time, with the same boundary as the Python factory; it never edits a report while retaining an old digest. A forecast snapshot is model forcing captured earlier, never a live measurement.

`GET /showcase/api/v1/research/ocean-prevention` defaults to `downstream-corridor-v2`. It accepts one `scenario_id` equal to that ID or `initial-proxy-v1`, rejects duplicate or unknown query fields with 422, verifies bytes/canonical report identity and the frontend scientific schema, and returns `Cache-Control: no-store`. Failed checks return 503. POST returns 405; there is no provider investigation or experiment-write route under this public prefix. Public outputs contain no credentials, contacts, private tank records or recorded conversation.

## Chalk and physical validation

Chalk is explicitly unavailable in the showcase. A disabled control explains that authorized live investigation is part of the full local software. No saved explanation is presented as a live response. The local app’s Chalk workflow remains unchanged.

Both layouts have 2,000 m of ideal absorbing line. The downstream illustration gives six no-interception entries, two central-layout entries and four flanking-layout entries under the frozen assumptions. That proxy was chosen after previewing the paths and is not independent performance evidence or a mapped reef. The original zero-entry proxy remains available and yields a tie. Real capture efficiency, barrier effects on flow, matched tank trials and ecological protection remain unmeasured. The public page describes the calibration, held-out drift and measured intervention trials still required.

## Verification

Python checks verify export identity, unchanged paths across freshness variants, the preserved control tie and absence of network/provider requests. Frontend checks exercise the actual Next handlers, mode selection at the UTC boundary, byte/report tampering, query rejection, blocked writes, local/cloud routing and the read-only result rendering. After deployment, verify the public page, both scenarios, checkboxes, release selector and current arrows in a browser. This verification demonstrates software behavior, not physical effectiveness.
