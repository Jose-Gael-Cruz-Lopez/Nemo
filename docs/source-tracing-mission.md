# Nemo starts with the source question

**Mission:** use observed floating-object movement to assess where it could have
come from, then predict its movement, compare interventions and test the result.
Source tracing is the starting question. Prevention extends it into a decision;
it does not replace origin inference.

## What is implemented

Open **Overview → Start software demo → Open source trace**, or use
**Investigations**. A saved synthetic trajectory supports a candidate ranking;
the retained-endpoint example can remain **Unknown**, and an invalid mapping
produces **Invalid**. These are examples of software behavior, not measured
source-recovery accuracy.

The [estimator](../apps/estimation/reeftrace_estimation/estimator.py) compares
**two to eight declared candidate tank entry regions**. It simulates particles
forward from each candidate under a supplied drift field, spreading, candidate
priors, release-age prior and retention assumptions. It compares those possible
histories with an observed trajectory or supported retained endpoint. It does
not recover a unique past by reversing a velocity arrow.

The accepted output depends on observation quality, calibration and token-class
validity, spatial flow support, absolute model fit, separation between candidates
and predeclared sensitivity variants. If the leading candidate or result status
changes across those variants, or another gate fails, an apparent leader can remain
**Unknown**. A relative-support bar describes compatibility within the declared
candidate/model assumptions. It is not a calibrated geographic origin or
polluter-identity probability.

The current tank model uses a supplied spatial drift field and bounded
advection–diffusion simulation. The separate geographic RK4 engine samples
changing ocean currents. An ocean forecast is not automatically an ocean
source-inference engine, and no RK4 ocean field has been silently substituted
for measured tank centimetres.

## What the other features contribute

| Feature | Contribution to the source-first project | What it does not establish |
| --- | --- | --- |
| Camera and calibration | Measure a controlled token's surface positions and drift | General plastic recognition or a source label |
| Source investigation | Compare candidate release histories with an observation | An arbitrary worldwide source search |
| NOAA / current-model research | Check how motion models describe historical buoy movement | Where the pollution was released or who caused it |
| Prevention | Compare possible interventions after movement/source assumptions are declared | Proof that the source estimate is correct |
| Trial ledger and 3D replay | Preserve predicted and separately recorded outcomes | New measurements created by animation |
| Chalk | Explain the exact saved evidence and uncertainty | An independent scientific measurement or authority to force a source ranking |

Tracking where a real object actually originated needs source-labelled evidence.
Historical NOAA buoy positions help test movement models, but a first recorded
buoy fix is not a verified pollution-release event. Lower forward forecast error
does not by itself prove better source identification, particularly when objects
can be retained, observed late or transported by an imperfect flow model.

## Next source-recovery validation work

The following is a **proposal**, not an executed experiment or frozen protocol.
It must be reviewed and fixed before collecting outcome data.

1. Measure the water-surface mapping and obtain separate drift-fitting and
   drift-validation recordings for a fixed rig condition. Do not fit the field
   to source-test releases or choose parameters from their outcomes.
2. Freeze candidate regions, token class, priors, release-age assumptions,
   transport/noise settings, gates, sensitivity variants and permitted observation
   windows. Retain all planned source/repeat slots.
3. Have an evaluator record each actual release region and time separately.
   Those labels are evaluation truth: they must not be passed to the estimator
   through filenames, metadata, case notes or input features. Excluding the label
   does not mean hiding the scientifically necessary measured positions/times.
4. Run new known-source releases in a predeclared balanced order. Use the same
   observation admission rules for every source; preserve tracking gaps, missing
   releases, invalid inputs and Unknown outcomes. Do not rerun until a desired
   source wins or select an easier video segment after seeing its ranking.
5. Save the complete evidence/report before revealing the evaluator's source
   label for scoring. Compare accepted rankings against that label and inspect
   failures without retuning on the same trials.
6. Report every denominator: planned slots, acquired observations, invalid
   inputs, Unknown results, accepted rankings, correct accepted rankings and
   wrong accepted rankings. Show correct/accepted and wrong/accepted together
   with accepted/planned and correct/planned. A high score obtained by accepting
   only a few easy cases is not broad source coverage.

Here **accepted** means `status=ranked` with a non-null `ranked_source`.
`Unknown` is abstention even when `leading_source` or conditional support bars
exist. A fraction with zero accepted/planned denominator is unavailable, not an
invented zero or perfect score. Identical candidate models can be ambiguous;
partially overlapping source polygons alone do not guarantee Unknown.

Separate trajectory and retained-endpoint results. A retained endpoint may be
uninformative even when several source histories reach it. Test supported
retention and ambiguity without demanding a forced classification.

A synthetic regression suite can check these rules, missing-data behavior and
known manufactured examples before the rig is ready. Simulating test paths with
the identical model that performs inference is an internally consistent software
exercise; it is not independent evidence of physical accuracy. New measured
releases and validated drift remain the missing bridge.

## A later ocean source feature

Ocean-scale attribution would require an explicitly different method and scope:
declared geographic candidate regions and release-time distributions, observation
uncertainty, appropriate object/current/retention behavior, sensitivity checks,
and source-labelled validation. Reverse advection alone cannot supply those.
This feature is **not implemented or validated** by the current ocean layout
comparison or origin-residual forecast diagnostic. A future version must keep
unknown regions and model mismatch visible rather than assert an exact polluter.

The current product sequence remains:

**Observe → assess possible origin → predict movement → compare interventions →
record what actually happened.**

## Primary research references checked for this direction

[BAKTRAK: backtracking drifting objects using an iterative algorithm with a
forward trajectory model](https://arxiv.org/abs/1111.0756) describes origin search
using forward simulations and selection against an observation, particularly
where nonlinear object changes complicate naive reversal. This is relevant
research precedent, not an implementation or validation claim for Nemo: the
current fixed-candidate estimator does not implement BAKTRAK's iterative search.

[OpenDrift's official introduction](https://opendrift.github.io/) describes a
Python framework with purpose-specific drift models, environmental forcing and
backward-time support. It is a candidate reference for a later geographic
workflow; it is not an installed or commissioned Nemo backend. Choosing a
framework does not supply source labels, correct object physics or uncertainty
validation.

The previously shared [Aegean floating-litter
paper](https://www.frontiersin.org/journals/marine-science/articles/10.3389/fmars.2017.00191/full)
studies transport from assumed source regions and dates. Its introduction
discusses other backward studies; it should not be represented as direct proof
that Nemo can uniquely identify the origin of a retained object.
