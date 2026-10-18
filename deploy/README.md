# Native Nemo deployment package

This packages the complete **software demo**, not a completed deployment. One
container runs production Next.js on public `PORT` (default 8080) and one FastAPI
worker on `127.0.0.1:8000`. Next proxies `/api/v1/*` to that private API. It uses
`reeftrace_api.cloud:create_cloud_app --factory`, which isolates cloud demo data
from private local evidence and disables camera/Photon/voice operations.
Next uses its production **standalone** `server.js` and traced dependencies;
the image separately includes `public` assets and `.next/static`. Its baked-in
same-origin API rewrite is unchanged. This avoids compiling TypeScript config on
startup; it is not a guarantee that every workload fits a 512 MB hosting limit.
The Next child has a fixed 128 MiB V8 old-space limit; it cannot inherit arbitrary
Node options. This bounds one part of its heap, not Python or total container
memory, and can increase garbage collection. Qualify the complete hosted flow
under the selected plan before calling its capacity sufficient.

## Build and run after the complete change is committed

Use a clean reviewed checkout. Building from Git's committed archive also excludes
untracked files; `.dockerignore` separately denies dotenv files, local recordings,
private directories, databases and generated dependencies. No provider key is
needed during the image build. The build downloads Node/Python dependencies.

```sh
git archive --format=tar HEAD | docker build \
  --build-arg SOURCE_REVISION="$(git rev-parse HEAD)" --tag nemo:reviewed -
docker volume create nemo-data
docker run --rm --name nemo --publish 8080:8080 \
  --mount source=nemo-data,target=/data/nemo \
  --env REEFTRACE_LOCAL_TOKEN \
  nemo:reviewed
```

Before running, set `REEFTRACE_LOCAL_TOKEN` privately to a strong random value of
at least 32 characters in the hosting platform's secret store or your shell.
`--env NAME` reads that existing variable without putting its value into the
command. Do not copy `data/local`, local SQLite, or `.env` into the image/volume.
The cloud wrapper marks a new demo directory and rejects nonempty unmarked data.
Mount paths must be writable by UID/GID 10001. Docker named volumes initialize
ownership from the image; provision equivalent permissions for host bind mounts.

Open `http://localhost:8080/`. Configure HTTPS at the hosting proxy before sharing
operator access. The operator token is entered privately in the app; it is not a
public login/account system. The public port can be changed with `--env PORT=...`
and a corresponding port mapping. Port 8000 is reserved and is never published.

For an explicitly requested live Chalk review, pass these **runtime secrets** to
the Python service via the platform secret store (or additional `--env NAME`
arguments): `CHALK_ENABLED=true`, `CHALK_ROUTER_BASE_URL`,
`CHALK_ROUTER_API_KEY`, `CHALK_ENV_ID`, `CHALK_MODEL`. The Next child receives none
of those variables. Startup and health checks do not invoke a provider. No key or
billing is provisioned by this package. Photon replies and xAI remain disabled,
including when contrary values were inherited accidentally.

### Optional read-only Photon project connection

With the operator’s approval, store the existing project credential in Render’s
server environment as `PHOTON_READONLY_API_KEY` and `PHOTON_READONLY_PROJECT_ID`.
These application variable names select the read-only verifier; they do not
reduce the permissions of the underlying provider key. They reach only Python,
never the Next child or browser. Do not use `NEXT_PUBLIC_` variables for secrets.

In **Settings → Photon**, connect operator access and choose **Verify Photon
connection**. The cloud-only `POST /api/v1/integrations/photon/verify` checks one
project GET through the pinned official SDK, with a five-second total deadline,
one attempt and ten-second cooldown. It returns only a result code, check time
and authentication scope. Upstream authentication failures do not sign the app’s
operator out. Startup, health and ordinary status polling make no Photon call.

Successful project authentication does **not** establish phone pairing or message
delivery. The hosted reply runtime stays disabled, with empty legacy credentials
and routes, no worker and no inbox/outbox writes. This endpoint cannot send a
message, list conversations or enable automatic replies. A future messaging
rollout requires separate authorization and a reviewed hosted transport design.

The image also prepares a public synthetic demo bundle during the build, using
an empty temporary store and a scrubbed environment with all providers disabled.
It caches only the three existing labeled synthetic source examples; **it does
not run an ocean first-score, acquire data, open a camera or contact a provider**.
The two read-only files in `/opt/nemo-public-seed` bind the public fixture and
method bytes. On the first empty owned cloud store, the wrapper validates and
imports them so loading the source demo avoids recomputing those examples during
a free service's cold start. An existing store is retained unchanged. Setting
`REEFTRACE_CLOUD_SEED_DIR` to an empty value disables this optional import.

## Data and readiness

The image includes committed public NOAA/HYCOM fixtures, research result files,
method source, referenced tests and exact metadata receipts. Saved result readers
verify those bytes and external pins; **do not regenerate, first-score, or refresh
the frozen artifacts during build/startup**. A frozen matched-current dependency
indirectly resolves Git HEAD even during a saved ocean-source read. The image
therefore creates a **new sanitized Git checkpoint of the allowlisted shipped
source, tests, data and provenance bytes**. It contains no original Git history,
remotes, developer configuration, provider credentials or Node dependencies.
This image checkpoint is not the historical protocol checkpoint and does not
replace any frozen file/result pin. The optional OCI source-revision label records
the original reviewed revision separately. Check `git log --oneline` and
`git remote -v` inside the image: there is one generated commit and no remotes.
Shipped scientific source, fixtures, provenance, tests and the Git checkpoint
have write permission removed after checkpoint creation. This is file-level
protection, not a completely read-only filesystem: Next's runtime/cache directory
and the separate `/data/nemo` volume remain writable.
The ocean-source example is retrospective exploratory buoy
earlier-position recovery, not proven pollution release attribution or a live
NOAA feed. Physical tank validation remains separate and local.

The supervisor waits for the API before starting Next, then checks the landing
page and proxied API health. If either process exits, both are stopped; SIGTERM
and SIGINT are forwarded to both process groups with bounded kill fallback.
Transient macOS group-teardown permission errors are accepted only after a
bounded existence probe proves the group has disappeared; persistent permission
errors fail rather than hiding a live process.
Configure the hosting platform's external HTTP health check to
`/api/v1/health` on the public port; Next forwards it to the existing API process.
The image explicitly disables Docker health-check subprocesses, avoiding an extra
Python interpreter within a 512 MB memory budget. Startup readiness still checks
both servers. `python deploy/start.py --check` remains a manual diagnostic for an
environment with spare memory; it never runs automatically or calls Chalk.
Check `/api/v1/status` and `/api/v1/research/ocean-source`, and verify unauthorized
operator requests fail before running a private, explicitly requested Chalk demo.
Verify a saved trial survives a container restart before claiming durable use.

## Cloudflare, Azure and persistence

### No-cost Render demo

The root `render.yaml` declares exactly one **Free** Docker web service, with no
paid disk, database, preview or worker. It generates a new private operator token;
Chalk starts disabled until its runtime configuration is entered privately.
Automatic deployment is off. Select the reviewed `main` revision for an explicit
deployment and verify the plan is still **Free** in Render before submitting.
For a Blueprint import, also set **Blueprint Settings → Auto Sync → No**:
Blueprint synchronization is separate from the service's auto-deploy switch.
The manual public-repository service form does not create a Blueprint.

[Render Free](https://render.com/docs/free) supports this kind of software demo,
but sleeps after 15 idle minutes. New trial records and SQLite changes are lost
on sleep, restart or redeployment; bundled frozen NOAA reports remain in the
image. Download trial exports instead of using this service as the only copy of
experiment evidence. The 512 MB resource limit must be smoke-tested against the
actual Linux image; a free plan does not promise production capacity or uptime.
If Render asks for payment, stop rather than selecting an upgrade. A paid card
already on an account can permit overage charges; do not enable billing for this
demo. This file alone does not create a Render service or establish a live URL.

Cloudflare Containers can run this native image behind a Worker, but require the
[Workers Paid plan](https://developers.cloudflare.com/containers/platform/pricing/).
Their [disk is ephemeral by default](https://developers.cloudflare.com/containers/concepts/architecture/):
after sleep a fresh image is used. This package does **not** add automatic durable
Cloudflare storage, snapshots, a D1 adapter, or a deployment Worker. Without that
work, label the container's experiment state disposable. Do not treat an R2 FUSE
mount as a drop-in SQLite volume: [SQLite WAL does not work over network filesystems](https://sqlite.org/wal.html).

For minimal code change and durable evidence, run one instance on a Linux host
with a persistent local/block volume, for example an Azure VM with an
[attached managed data disk](https://learn.microsoft.com/azure/virtual-machines/linux/add-disk),
and optionally put Cloudflare in front. Azure Files/SMB is not an unchanged WAL
storage solution. Horizontal replicas need a deliberate database/storage design.
The existing Vercel read-only showcase remains a different deployment target.

## Offline packaging checks

```sh
python -m unittest discover -s deploy -p 'test_*.py' -v
python -m ruff check deploy
```

These checks use fake child processes and private temporary directories, without
starting the app, camera, provider, Docker daemon, or frozen scientific evaluator.
An actual Linux image build and hosted smoke test are still required.
