# RK4 and numerical quality in Tideward

Development checkpoint: 17 October 2026. This is a numerical-method improvement
and sensitivity experiment on the existing pinned PacIOOS field. It is not a new
NOAA buoy skill study, a trained plastic detector, or a physical tank result.

## What RK4 means

The ocean model supplies eastward and northward water velocity at grid locations
and times. Tideward follows a hypothetical passive particle through that field:
`dX/dt = u(X,t)`. RK4 samples the current at the start, at two estimated midpoint
positions, and at an estimated endpoint, then uses their weighted average to
advance the particle. It samples again at the new position and time on the next
step; a change in speed alone need not bend the path.

For state `z=(latitude,longitude)` in degrees and elapsed seconds `t`, the
derivative is `f(z,t)=(northward/m_latitude, eastward/m_longitude)`, using the
latitude-dependent WGS84 metres-per-degree factors. The four stages are:

```text
k1 = f(z, t)
k2 = f(z + h*k1/2, t + h/2)
k3 = f(z + h*k2/2, t + h/2)
k4 = f(z + h*k3,   t + h)
z_next = z + h*(k1 + 2*k2 + 2*k3 + k4)/6
```

East/north m/s are never added directly to geographic degrees. The tank uses
separately measured cm and cm/s; ocean currents do not calibrate it.

## The issue that was fixed

Linear interpolation between supplied current timestamps changes slope at each
timestamp. An RK4 step crossing that break can introduce a numerical inconsistency.
The solver now ends steps at forcing timestamps, as well as output times, the
requested horizon and its existing speed/cell/maximum-step limit. It uses all
supported time through the final current timestamp before reporting an unsupported
remainder. Positive time is always accompanied by integration of position; there
is no time-only snap. Unrepresentable progress fails explicitly, and extra knot
splits count toward the bounded step budget.

Only contributing interpolation corners may be read. Missing masks, unsupported
geography and unavailable time still stop the path. An exactly valid timestamp
does not authorize interpolation into a masked future interval.

The independently derived regression uses uniform eastward velocities
`[0,1,0] m/s` at absolute times `[0,650,1400] s`, at the equator. Integrating the
piecewise-linear current from zero to 1,000 seconds gives `1780/3 m`, approximately
593.333 m. The old unsplit calculation returned approximately 589.744 m. A request
continuing to 1,800 seconds now retains the supported prefix through 1,400 seconds;
the previous implementation stopped at 1,200 seconds. Exact rational trapezoid
areas generate the test expectations, including different start offsets and
horizon meanings.

The original snapshot has three-hour forcing knots aligned with its five-minute
default steps. Its six track arrays and every release outcome in both scenarios
were checked against a saved pre-patch reference and remained exactly unchanged.
Method hashes change with source bytes; historical receipts are not relabelled.

## Two different sensitivity checks

**Integration sensitivity** reruns the fixed releases with maximum solver steps of
300, 150 and 75 seconds, with the same 300-second output schedule. Position
separations are compared only at shared supported positive times against the
75-second numerical run. Missing common times, partial paths and changed forcing
statuses remain explicit. The finest run is a numerical reference, not truth.

**Contact-interval sensitivity** integrates one finest path with 75-second solver
and output intervals, then derives 300-, 150- and 75-second contact chords by
downsampling that same path. A terminal partial point is retained. The existing
first-contact geometry evaluates each representation. This isolates contact
localization from independently changing the integrated trajectory. Event types,
collector identities, unresolved outcomes, counts, recommendations and comparable
event-time differences are retained for all releases.

The main decision still evaluates all layouts against one common default path
per release. Additional diagnostic reruns are separate and never promote a model,
retune a completed study or replace the default decision.

## What this proves and what it does not

Agreement across these settings is evidence of stability under those particular
numerical choices. It is not a calibrated uncertainty band, independent truth,
observed fourth-order convergence, or proof that waste follows the current. A
small solver difference cannot resolve errors in the underlying roughly 4 km,
three-hour current field, collector efficiency, windage, waves, object response
or real protected-area geometry.

The same hash-bound comparison and compact numerical summary are available to
Chalk. Its explanation must retain those distinctions. Data Lab and Prevention
show the check behind a closed disclosure, keeping the main combined trajectory
plot and conditional layout comparison concise. Older exported reports without
the optional numerical field remain readable as historical snapshots.

## Primary guidance and implementation evidence

- [Nordam and Duran, Numerical integrators for Lagrangian oceanography](https://gmd.copernicus.org/articles/13/5935/2020/index.html): time-cell boundaries and interpolation affect numerical integration; stopping at known temporal boundaries can avoid crossing a derivative break.
- [OceanParcels timestep/integrator tutorial](https://docs.oceanparcels.org/en/latest/user_guide/examples/tutorial_dt_integrators.html): compares timestep choices and integrators; a finer numerical reference is distinct from an exact trajectory.
- [Current solver](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/apps/ocean/reeftrace_ocean/advection.py) and [analytic forcing-knot regressions](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/tests/unit/test_advection_time_knots.py).
- [Grok contribution and correction ledger](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-contribution-ledger.md): actual prompts, static responses, rejected arithmetic/time snapping and local verification are preserved separately.
