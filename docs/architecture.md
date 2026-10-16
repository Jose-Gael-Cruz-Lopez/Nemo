# Version 3 architecture

The authoritative path is camera → permitted timestamped observations → measured
calibration/profile → forward ensembles from A/B/C → trajectory or retained-endpoint
likelihood → absolute fit, relative support and Unknown → immutable SQLite evidence.
Observed history survives a later stop. Retained-only observations count actual
modeled retention, never earlier passage. Submerged coral is not a surface barrier.

The profile stores waterline, source polygons, downstream observation region,
verified surface traps and a coarse measured flow grid with counts/dispersion.
Unsupported cells terminate particles. Boundary, obstacle and trap intersections
are checked along movement segments. Runtime currently uses piecewise-constant
flow; dispersion is retained for development inspection and a global diffusion
parameter must be tuned separately. It is not an ocean hydrodynamic model.

`apps/core/reeftrace_core/` owns contracts, simulation, evidence persistence,
authorization and the shared investigator. Existing `apps/api`, `dashboard`,
`apps/hardware` and `firmware` layouts are preserved. No duplicate server stack is
needed. One local API worker owns startup approval invalidation; acquisition is an
explicit camera CLI process. The API queues observation requests but does not
claim automatic fulfilment or live video streaming.

Agent tools retrieve the active case/source report, run a named sensitivity set,
queue one observation and propose one manual-net task. The JSON tool loop has call,
time and operation budgets. Only returned evidence IDs are permitted. Numerical
source tables bypass generated text. Free-text grounding remains a separate
quality/evaluation concern. Neither the agent nor inference API exposes truth.

Photon's explicit worker runs ingress, investigation and durable outbox separately.
Exact configured sender/agent mappings scope access. STOP/CANCEL/APPROVE parse
before normal conversation. Stable IDs deduplicate incoming events and outgoing
reply attempts. Accepted vendor sends are not claimed delivered. A persisted bounded
session start is rescanned to accommodate late indexing and restarts.

Manual proposals bind case/evidence/profile/operator/conversation/body hash/expiry.
Atomic approval inserts one unique response job. Fresh live evidence and a checked
rig are required. Confirmation records human recovery evidence and marks RECOVERING.
Rig changes/startup invalidate pending continuation; profile checks are explicit.
The optional water-sampler sketch/test client has no agent or API dispatch path.

Offline truth and raw full-frame evaluator archives remain outside API/agent query
interfaces. ReplayBackend exposes fixtures only; it has no camera, serial or physical
control imports. Scientific metrics distinguish coverage, answered accuracy, wrong
and Unknown, and reject synthetic/duplicate trials. Real tank validation, hosted
Chalk evaluation, sponsor device tests and ASUS measurements remain external gates.
