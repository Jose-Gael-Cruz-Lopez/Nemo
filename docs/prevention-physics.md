# Conditional prevention comparison

`apps.estimation.reeftrace_estimation.prevention.compare_layouts` compares two
already frozen profiles. It does not move hardware, fit a field, select scenarios,
infer source frequencies, or record a physical outcome. The API must retrieve
registered immutable profiles and authorize the request before calling it.

Both layouts must declare the same tank bounds, token class, source IDs and source
polygons, and the same data origin (`SYNTHETIC` or `MEASURED_TANK`). Their separately
measured flow fields and validated absorbing pocket positions can differ. Moving
a pocket can change flow; this code does not predict that hydrodynamic change.
Measured profiles must pass their frozen independent drift-validation gate.
The numerical function cannot independently certify a profile's physical provenance.

## First passage, not a final-position count

Particles start uniformly inside each source at time zero. The existing forward
Euler-Maruyama simulator moves them using that layout's field, declared drift
discrepancy and constant dispersion, with reflecting tank walls. Source priors
and source-estimation release-age priors are intentionally unused. All declared
sources and all matching declared scenarios are evaluated separately; source
support scores never become prevention weights.

For each layout/source/scenario the same simulator runs twice with identical
initial random seed, particle count and precomputed time step:

1. Actual absorbing pockets only, preserving later motion/capture history.
2. Those same pockets plus the protected zone as a competing absorbing polygon.

The second run identifies which event happens first: pocket contact or protected
zone entry. It reuses the engine's segment-polygon intersections and wall-reflected
subsegments, so thin zones crossed between time nodes are counted. Taking a chord
between reflected step endpoints would be incorrect. The common time step prevents
the two runs from silently using different noise increments. Initial positions and
the free trajectory agree until the protected-zone event. Absorption only in the
second run is a measurement device for first passage, not proposed physical hardware.

Protected-zone contact counts as entry. Source/zone, source/pocket, pocket/zone and
pocket/pocket overlap or touching is rejected to avoid ambiguous initial states or
capture/entry ties. Polygons can be concave but must be simple, finite and inside the
tank. Capture after zone entry is not prevention, even if both events occur within
the same numerical time step. Stored event times are time-node upper bounds with
the reported step resolution; the competing simulation establishes event order.

Retention is perfectly absorbing: no escape, partial capture, clogging, submergence,
coral injury or ecological response is modeled. The protected polygon is a surface
receiving-zone proxy, not a coral damage model.

## Denominators and conservative withholding

For every source/scenario:

`simulated arrival fraction = first protected-zone entries / ALL released particles`

`benefit = baseline arrival fraction - intervention arrival fraction`

A particle with any unsupported time node before its first event (or the horizon)
remains in every denominator. The report also bounds its outcome as unknown:

`arrival lower bound = supported zone entries / ALL particles`

`arrival upper bound = (supported zone entries + unsupported particles) / ALL particles`

Benefit bounds subtract the unfavorable combination of arrival bounds. Their
overall minimum/maximum span every source and declared scenario. These bounds
address missing support, not Monte Carlo sampling uncertainty or field uncertainty
outside the predeclared scenarios. Node-based support is a finite-step diagnostic,
not proof of continuous spatial coverage between nodes.

For this prototype, ANY unsupported particle in ANY layout/source/scenario withholds
a recommendation, even if the source profile's recorded minimum coverage is lower.
Both that declared gate and the stricter comparison gate appear in the report.
With complete support, intervention is recommended only if every lower benefit
bound is strictly positive; baseline only if every upper bound is strictly negative.
Otherwise the result is `NO_ROBUST_RECOMMENDATION`. Robustness means agreement over
the declared experiment, not calibrated confidence or universal optimality.

## Bounds, outputs and physical evaluation

Requests allow 2-5 sources, a 1-20 second horizon, 20-200 particles per source and
nominal plus at most two predeclared sensitivity variants. Both complete scenario
ID sets must match; an oversized set is rejected, never selectively dropped.
The common time-step preflight caps each ensemble at 2,000 steps and the whole
comparison at 6,000,000 particle-time states across both layouts and both passes.
Profiles and the returned JSON must be finite and bounded. At most six illustrative
nominal paths per source/layout, decimated to at most 80 points, support UI display;
decimation is never used to calculate the metrics.

Reports include immutable input hashes, IDs, full source/scenario counts and
fractions, conservative benefit range, explicit assumptions, scope and failure
reasons. `physical_validation:false` is always returned, including when inputs
are `MEASURED_TANK`. A measured-input simulation is not a measured intervention.

Choose a layout on development trials, freeze it, then compare new randomized
physical baseline/intervention releases at the same declared horizon and source
mixture. Count first arrivals, captures, escapes, unresolved/missed observations
and released/recovered token inventory. Keep source labels in the evaluation
ledger. A lower count of detections alone is not proof of lower arrival. Report
real physical counts separately; never convert simulated tokens into corals saved.

This extends established observation-to-intervention practice, not a claim of
new source-inference mathematics. Primary precedents include [The Ocean Cleanup's
baseline and downstream monitoring](https://theoceancleanup.com/updates/the-ocean-cleanups-end-to-end-river-system/)
and [SeaClear2's site-specific prevention and impact assessment](https://www.seaclear2.eu/project-overview/).
