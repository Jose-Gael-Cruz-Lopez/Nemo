# Ocean source research and the five-step trajectory walkthrough

Nemo's main question remains **where a floating object could have come from**. The geographic prototype adds bounded earlier-position reconstruction using real saved HYCOM currents. It does not identify a verified pollution release or a polluter anywhere in the world.

The tank's forward candidate-source estimator remains unchanged. Ocean calculations use geographic degrees and metres; tank experiments need their own measured centimetre field and source-labelled releases. The [README formula guide](../README.md#scientific-formulas-explained-through-the-tank-experiment) and [actual dataset inventory](../README.md#datasets-what-nemo-actually-uses) explain both systems.

## Why reverse both direction and time

For a deterministic current-driven object,

$$
\frac{dX}{dt}=u(X,t).
$$

Starting at an observed time $T$, define increasing lookback age $\tau=T-t$:

$$
\frac{dY}{d\tau}=-u(Y,T-\tau),\qquad Y(0)=X_{observed}.
$$

**Simple meaning:** at each earlier time, consult the current that belongs to that time and follow its opposite direction. Negating today's velocity while advancing through the original chronological snapshots is incorrect when currents change. A divergence-free field is not required for this local deterministic ODE reversal, and Nemo does not claim its interpolated field is divergence free.

The new adapter copies the current arrays and masks, reverses their time order, negates both velocity components and supplies increasing pseudo-times to the existing positive-time WGS84 RK4. Returned points are labelled with their actual decreasing UTC. Original current bytes and the pinned forward solver remain unchanged. Existing domain, speed, mask, time and step-budget checks remain in force.

This reverses the declared deterministic model, not every physical process. Diffusion cannot be undone with negative diffusivity; capture, beaching and retention can erase history. Convergent flow can amplify reverse uncertainty. A forward/backward round trip tests numerical consistency, not recovery of the true ocean past.

## Open the source-first feature

In **Investigations**, select **Ocean source research**, then explicitly load the saved study. Tank source tracing remains the initial environment and keeps its independent Ranked/Unknown/Invalid contract. Loading the ocean study reads saved results only; it does not acquire currents, train a model, run the numerical study, write a trial or contact a provider.

The report uses both fixed GDP groups: `300234066836710` and `300534061292930`, with the saved HYCOM fifteen-metre field for **1 June 2022, 00:00/03:00/06:00 UTC**. These groups and positions were already viewed in prior research. The new study is explicitly **post-outcome exploratory**.

### A simple control sequence

1. Open **Investigations → Ocean source research → Load ocean earlier-location example**. This loads the saved report; no live current API request or new forecast runs.
2. Choose either **Historical buoy**. Start at step **1**, then use **Next step** through the observed dots, connected estimate, filtered state and saved equation. **Play walkthrough** advances those same five saved stages once; **Pause walkthrough** stops it.
3. At step **5**, inspect the purple backward and teal forward branches. Move **Reveal saved branch time** from zero to 180 minutes to reveal saved five-minute outputs. This changes visibility, not the computation.
4. Toggle **Observed positions**, **Filtered state** and **Modeled hypotheses** to separate overlapping layers. The equal-scale axes stay fixed.
5. Select **Show reserved comparison positions** to reveal the orange recorded positions and the stored errors. These positions were excluded from the tutorial calculation, but were already viewed during project development.
6. Expand **06:00 endpoint: earlier-location sensitivity and source-model validation** for the separate six-hour experiment. Choose a buoy, lookback and layers; use its own **Show validation evidence** checkbox to compare its three models with the known 00:00 position.
7. With local operator access, explicitly choose **Ask Chalk about earlier locations** for a bounded explanation of the saved report. This is the only provider-request action in this feature. Loading, changing steps, scrubbing and revealing validation do not call Chalk.

## Watch each stage, without inventing observations

| Stage | What appears | What it means |
| --- | --- | --- |
| 1. Scattered observations | Three actual processed NOAA positions at 01:00, 02:00 and 03:00 UTC | The permitted measured-data input; not synthetic training points or raw GPS fixes |
| 2. Connected observed path | A line joining those same positions | A drawing of the observed sequence, not newly measured intermediate points |
| 3. Kalman-filtered path | Causal position/velocity estimates from the three permitted fixes | A separate small filter example using declared noise; not a future-informed smoother or a calibrated trash detector |
| 4. Physics rule | The current field plus a constant initial motion offset | The explicit equation that connects the filtered state with changing current-driven movement |
| 5. Backward and forward branches | A possible earlier position at 00:00, and predicted movement through 06:00 | Conditional reconstruction and a future position that could inform interception planning; no proven source or guaranteed capture |

Stage/playback/group/layer controls change the drawing only. They do not fit a new model, alter saved errors, change group denominators or ask Chalk. Equal east/north scale and the domain remain fixed as layers are hidden. Missing paths retain gaps and reasons. An explicit validation control reveals the separately held earlier/later positions and error table.

The three-fix tutorial uses the same constant-velocity state, continuous-white-acceleration covariance and Joseph update described in the README, with declared $\sigma_p=100$ m and $q=10^{-6}$ m²/s³. It initializes velocity at the second fix, then predicts/corrects the third. It is **separate from the frozen eight-or-more-fix Kalman benchmark**, whose implementation and outcomes are unchanged. Three fixes and assumed noise do not establish reliable uncertainty or a learned environmental response.

At the filtered 03:00 state, the tutorial computes

$$
b_{03}=v_{filtered,03}-u_{HYCOM}(X_{filtered,03},03{:}00),
$$

$$
\frac{dX}{dt}=u_{HYCOM}(X,t)+b_{03}.
$$

The east/north offset stays constant; it is not identified windage or a trained correction. The same corrected copied field drives both directions. For the backward branch, negate **the whole corrected field** while reversing its time; the forward branch uses increasing actual UTC. Neither branch resets to an evaluation position.

The future endpoint can be discussed as a **candidate interception rendezvous at the stated time**. It is not an optimized boom location, a safe deployment instruction, an accessible coast point or a measured capture result. Use the separate Prevention feature to compare explicitly declared interceptor geometry and retain its own evidence boundaries.

## Inspect the earlier-position sensitivity experiment

A separate diagnostic uses the 06:00 endpoint. Its last-drift baseline may read only the immediately preceding 05:00 fix. The current-only reverse path does not receive the 00:00 evaluation position or the old initial-residual model's origin context.

Each group retains **25 declared cases**: five endpoint offsets (centre and ±100 m east/north) crossed with five constant forward-current biases (zero and ±0.05 m/s east/north). Candidate earlier points are shown at one, three and six hours of lookback.

These settings were fixed before this method's first score, but they have no empirical probability calibration. The dots form a **conditional sensitivity envelope**, not a 90% confidence region, probability map or exhaustive source area. Unsupported cases remain in the denominator. The renderer does not draw a convex hull across unsupported gaps. If no case reaches an age, that earlier-location result is unsupported; it is not a forced origin.

The six-hour lookback is an explicit earlier-time hypothesis. It does not infer the object's release time, and an earlier buoy position is not necessarily its release location. The current field supports a specific region, depth and time interval. An arbitrary worldwide location or missing interval must not be filled with a plausible-looking trajectory.

## Separate three kinds of checking

1. **Numerical consistency:** forward-integrate the nominal recovered earlier point through the same field to the endpoint. A small closure distance can coexist with a large actual earlier-position error. Preserve both results.
2. **Retrospective location recovery:** compare stationary, last-drift backward and current-only backward against the recorded 00:00 buoy positions. The base experiment retains six planned model/group rows on two distinct earlier positions. The bidirectional tutorial has its own earlier/later targets and denominator; do not pool model cells into independent experiments.
3. **Real source validation:** independently documented pollution releases or blind known-source tank releases. This evidence is still missing. A source labelled by a person after viewing the model output is not independent truth.

The execution has **two distinct forecast receipts**, because the two calculations have different permitted observations:

1. **Tutorial receipt first:** decode only the 01:00/02:00/03:00 coordinates needed by the three-fix tutorial. Compute both groups' backward and forward branches, then write, hash and read back [pipeline-forecasts.json](../data/research/ocean-source-v1/pipeline-forecasts.json). At this boundary, no 05:00/06:00 coordinates have been numerically decoded. The tutorial forecasts are fixed before those later coordinates can enter the separate endpoint calculation.
2. **Endpoint receipt second:** the six-hour experiment may now decode its permitted 05:00/06:00 observations. Compute all endpoint candidates, sensitivity paths and closure checks, then write, hash and read back [forecasts.json](../data/research/ocean-source-v1/forecasts.json), including the already-frozen tutorial forecast and its receipt hash. Only after this second readback do the evaluators decode 00:00 truth and score the endpoint experiment and the tutorial's 00:00/04:00/05:00/06:00 targets. The latter 05:00/06:00 positions are validation for the tutorial but permitted inputs for the separate endpoint experiment; they are not described as globally undecoded until scoring.

The raw source payloads and timestamp/string records exist before both receipts; the boundaries concern numeric coordinate decoding and which values each inference function receives. This code-level input firewall cannot erase the team's prior exposure to these historical outcomes or NOAA's upstream interpolation/HYCOM assimilation. Failure cells remain saved; there are no replacement groups or retuning after this result.

## Saved first-score results

The reviewed method was committed as **`f239213ea128ef29f74539cae1abb70ea5adfab9`** before its first score. The saved forecast receipt is dated **17 October 2026, 21:33 EDT** (**18 October 2026, 01:33 UTC**). No new trajectories were acquired and no provider requests were made by this scoring run. The complete [evaluation](../data/research/ocean-source-v1/evaluation.json), [protocol](../data/research/ocean-source-v1/protocol.json), [exclusive attempt](../data/research/ocean-source-v1/attempt.json) and [identity record](../data/research/ocean-source-v1/identity.json) are retained.

**Five-stage three-fix walkthrough:** both groups use only recorded processed positions at **01:00/02:00/03:00 UTC on 1 June 2022**. The 01:00 state is position-only, 02:00 initializes position/velocity, and 03:00 receives the one causal prediction/measurement update. The same filtered 03:00 anchor and fixed current offset drive the negative-time and positive-time branches. The earlier 00:00 position and later 04:00/05:00/06:00 positions are excluded from tutorial inference. Both tutorial forecasts are saved and read back before any numeric 05:00/06:00 decode; those two coordinates then become permitted inputs to the separate endpoint experiment, as described above.

| GDP group | Backward error at 00:00 | Forward error at 04:00 | Forward error at 05:00 | Forward error at 06:00 |
| --- | ---: | ---: | ---: | ---: |
| `300234066836710` | **403.531 m** | **205.459 m** | **497.903 m** | **860.020 m** |
| `300534061292930` | **389.248 m** | **246.223 m** | **609.918 m** | **1,023.657 m** |

All **8/8 planned rows** scored: two distinct earlier targets and six distinct later targets. Rounded to centimetres, the separate three-hour earlier-position misses are **403.53 m** and **389.25 m**; the three-hour forward endpoint misses at 06:00 are **860.02 m** and **1,023.66 m**. These are eight processed positions from two previously viewed GDP groups, not eight independent pollution-source experiments. The backward point means a conditional earlier location under the declared three-hour lookback. The forward endpoint means a possible future rendezvous; there was no collector, protected reef, observed interception or optimized deployment in this calculation. No calibrated uncertainty or model superiority follows from this small post-outcome tutorial, which has no matched baseline comparison of its own.

**Separate six-hour current-only reconstruction:** this starts from the recorded **06:00** endpoint and evaluates the **00:00** position. The last-drift candidate additionally receives only the recorded 05:00 fix. It is a different input/horizon contract from the three-fix tutorial; do not compare their errors as a controlled improvement experiment.

| Backward method | Mean earlier-position error over both GDP groups |
| --- | ---: |
| Stationary endpoint | **6,069.353 m** |
| Last observed drift, extrapolated backward | **2,197.726 m** |
| Reversed changing HYCOM current, without a fitted residual | **8,696.822 m** |

All **6/6 planned model/group rows** scored on **two distinct earlier positions**. This base result is unfavorable to the current-only model: its mean error is **8,696.82 m**, compared with **6,069.35 m** stationary and **2,197.73 m** last-drift. It was worse than both simple baselines. The smaller three-hour tutorial errors do **not** demonstrate an improvement over these six-hour results: the anchor, permitted inputs, horizon and motion rule all differ, and no matched tutorial baseline was scored.

All **25/25 declared sensitivity paths per group** completed. Forward/backward numerical closure distances were about **1.18×10⁻⁷ m** and **5.38×10⁻⁸ m**; that near-perfect numerical round trip coexists with kilometre-scale errors against the recorded past. It establishes solver consistency, not a correct release location. The negative result is preserved without retuning, choosing replacement groups or promoting a model.

The two studies reuse some previously viewed positions and the same historical forcing. Their evaluation counts must remain separate. Neither establishes physical/statistical independence, issue-time forecast availability, calibrated source uncertainty, surface-plastic response or true release-source accuracy. **Physical tank source/interception trials remain zero.**

## Read the saved study without running it again

From the repository root, the normal read-only module command is:

```sh
.venv/bin/python -m scripts.evaluate_ocean_source
```

This checks saved artifact bytes, detached hashes, source lineage and result consistency. It does not run scientific inference/scoring, fetch data, train, contact Chalk or message Photon. Numerical replay verification is explicitly false for this reader; byte/lineage verification is not a fresh mathematical or physical validation.

The **historical one-time execution command** was:

```sh
.venv/bin/python -m scripts.evaluate_ocean_source --first-score
```

Execution requires reviewed committed method bytes, the frozen matching protocol and an unused attempt directory. The existing study refuses to execute again or overwrite its exclusive attempt. Do not delete that directory or create a replacement attempt to search for a better outcome. Use the module form shown above so repository imports resolve correctly.

The published saved identity is **`947ce44bb75f3e52c3f9ec5d59d5efc5303325c316f6924cb230a3c74048eb20`**. It binds protocol **`1fd45e36997481c2943c3e632952a29cefe0e0b7aea018294071423b7f874831`**, full forecast file **`a5ec302012b9d2b1f5c5772162c215334134ec75b75558ef39d5e3f6b1326993`**, tutorial forecast file **`357426821c85280616cec738f08e8a6b9f52088936c358f863a2c6e5f5ae04b8`** and report **`3d9f0faed305a41b7fa0c85bf3c7c82a3a525b742799fae90e1e6f00906fa474`**. A separately committed literal result pin is required by the public reader; self-consistent rewritten hashes are insufficient.

## Chalk and the API boundary

`GET /api/v1/research/ocean-source` is public, read-only and `no-store`. It requires the separately pinned saved artifacts and returns `{report, artifact_identity}`; it never runs inference or scoring. Missing results, corrupted identities and unavailable readers remain explicit errors.

`POST /api/v1/research/ocean-source/investigate` requires local operator access and exactly `question`, `report_sha256`, `protocol_sha256` and `identity_sha256`. Chalk receives one bounded read-only evidence tool and at most two model calls. A REPORT must cite the exact report/protocol; the snapshot is checked again afterward. Disabled or failed providers preserve a STOP/no-live-response state. There are no acquisition, case/trial write, camera, pump or messaging tools.

Artifact verification confirms saved bytes and lineage against a separately committed literal pin. It does not independently rerun the mathematics or validate physical source accuracy. A mocked end-to-end REPORT tests the contract; only a separately authorized real provider request could establish live connectivity for this feature.

## How this connects to the actual tank

The same observed→estimated→filtered→predicted explanation can help the team inspect camera tracks. It must preserve the tank's measured centimetres, real timestamps, token behaviour and independent map/flow checks. The geographic hundred-metre noise and fifteen-metre ocean depth do not transfer into that experiment.

The current tank source engine already handles explicit candidate polygons with forward particles and relative-support gates. Keep that method for known-source testing, particularly when retention makes an endpoint ambiguous. Fit/check each layout's field from separate recordings, freeze the source protocol and save reports before revealing release labels. Do not claim that a reversible ocean animation has validated the physical source estimator.

## Better next step for geographic attribution

Declare geographic release cells and a release-time window before scoring. Seed them forward with the existing solver, compare endpoint/track agreement under explicit object/forcing assumptions, retain unsupported candidates and disclose the source prior. Backward paths can propose search areas, but forward candidate comparison is better suited to explicitly modelling retention or changes in drift behaviour. Calibrated uncertainty needs its own independent tests. No exact geographic polluter is identified by this first prototype.

Primary research reviewed with Grok: [BAKTRAK](https://arxiv.org/abs/1111.0756), [Parcels backward-time support](https://docs.oceanparcels.org/en/latest/reference/parcels/ParticleSet.html), [forward marine-plastic source inference](https://www.frontiersin.org/journals/marine-science/articles/10.3389/fmars.2022.925437/full), and [numerical biases in backward particle tracing](https://doi.org/10.1029/2025MS005470). These references support method choices; they do not establish that those frameworks are installed or that Nemo has validated ocean pollution attribution.
