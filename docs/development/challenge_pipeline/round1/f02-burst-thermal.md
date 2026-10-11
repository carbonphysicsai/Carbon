# f02 — burst-power thermal envelope, customer round 1

Authority and core numeric sheet: [round-one index](README.md),
[requirements.json](requirements.json). New transient scope; the original
Cooling periodic-cell CFD evidence is not its reference.

## 1. Engineering job

Hypothetical accelerator thermal architect: choose one of nine peak-power /
on-time actions for a known cooling regime, initial temperature, spatial split
and waveform family. Maximize extra delivered joules above the 20-W base while
the top-die spatial maximum stays at or below **95 °C over 120 s**. A wrong
choice causes throttling or breaches the buyer's development limit. No chip
reliability, controller, workload throughput, fluid solve or autonomous actuation.

## 2. Physical system

Fixed silicon-surrogate 20×20×0.5 mm, TIM-surrogate 20×20×0.2 mm and copper-surrogate
30×30×2 mm, centered in x/y and stacked in z. Constant isotropic k/rho/cp are
selected synthetic values in the sheet, not empirical package characterization.
Perfect layer continuity; remaining exposed surfaces insulated; whole underside
Robin cooling. Two 8×8-mm top patches centered at x=−5/+5 mm, y=0. Total power
split 50/50 or 80/20, with the left patch taking the larger share.

Cooling pairs are (30 °C, 2,500 W/m²K) and (40 °C, 1,500 W/m²K); uniform initial
T is 40 or 55 °C. Base 20 W throughout. Burst starts at 20 s. Rectangular: peak
for D seconds; ramp: rise linearly from base to peak over D seconds then return
to base; two-pulse: two rectangles of D/2 separated by 10 s. Peak={80,110,140} W,
D={5,10,20} s. No causal future observation is available to the construction.

## 3. Population P, Q and w

`P_dev,decision` is uniform over 24 exogenous strata (2 cooling×2 initial×2
split×3 families); nine schedules are actions, not random customer states.
`P_dev,reference` is uniform over all 216 condition/action pairs. This is an
experiment law, not deployment frequency. Q is 24 cases, one per stratum using
110 W/10 s, plus six warm/55 °C/80:20 boundary cases: every family at80 W/5 s
and its nearest-limit action under the frozen one-node RC screen. Exclude the
nominal and low action from the latter; minimize absolute RC-peak distance to
95 °C, ties by lower peak power then shorter on-time. The screen ignores
spreading and imbalance. A nearest peak more than5 °C from95 °C is an explicit
boundary-coverage gap, not a passed near-limit test. Persist this selection
before Elmer access. Uniform stratum weights apply only to a later complete decision
comparison; Q diagnostic rows are reported individually without a P estimate.

The offline selection is rectangular80 W/10 s (RC peak99.406 °C), ramp80 W/20 s
(94.136 °C), two-pulse140 W/5 s (97.392 °C), all for the warm/55 °C screen.
These are preregistered probe actions, **not safe schedule recommendations**.
Elmer must test actual spatial/time response; no RC value is imported as truth.

### Prospective population of buyer design questions — `HUMAN_INPUT`

The 24 cooling/initial/split/waveform scenarios are correlated conditions of
the current package, but each can ask for its own schedule. A future `P_job`
can vary supported scenario requirements, such as a temperature ceiling or
minimum extra-energy need, against the same fully solved schedule/scenario
bank. A package engineer recognizes these questions from workload power
traces, thermal operating policy and cooling fixture limits. Requirement
variation costs no new Elmer solve when the bank records spatial peak and
energy for every eligible action; it must be checked for different right
answers. New die stacks, contact laws or cooling regimes are optional axes
requiring new reference support. Timestep samples and schedule order are not
fresh questions.

**Size recommendation, not a selected law:** catalogue eight distinct
scenario/requirement questions for a development scoping pilot and preserve
their common-package cluster. `HUMAN_INPUT`: eligible limits and conditions,
`P_job`, protected `Q_job`, weights, answer diversity, bank exposure and
power-justified hidden `n`. The existing 50-launch grant cannot create the
full 216-solve physical bank; reusing a later solved bank does not reset `E`.

## 4. Case contract

Canonical case includes complete stack, SI dimensions/materials, patch source,
cooling pair, T0 and waveform events. Reject malformed/negative parameters,
patch overlap/out-of-die patches and events beyond horizon. Bind case/deck,
solver and extractor digests. Public own-seed cases are separate from any later
protected draw; no protected ID is encoded in a public digest.

## 5. Reference policy

Use Elmer solid transient heat conduction, not CFD. The
[official model manual](https://www.nic.funet.fi/index/elmer/doc/ElmerModelsManual.pdf)
and [source](https://github.com/ElmerCSC/elmerfem) support this candidate route;
they do not establish Carbon adequacy. Build/image/license, mesher, time scheme
and verified flux/continuity implementation must be pinned before dispatch.

Four control launches: zero-source equilibrium at coolant temperature, two
analytical 1D slab step/pulse controls and uniform-source energy accounting.
Require equilibrium drift≤0.05 °C; slab error≤max(0.25 °C, 1% of temperature
rise); energy residual≤1%. Six boundary cases receive independent mesh- and
time-halving launches (12 refinements). Require peak shift≤0.5 °C and crossing
shift≤0.5 s; resolved peak within 1 °C of the limit is decision-unresolved.
If a crossing exists at one rung but not the other, it is unresolved. Allowance:
30 primary+4 controls+12 refinements+4 steady baselines=50 attempts, zero retry;
node-hour, RAM and spend caps are unchanged. Baselines cover the2 cooling×2
source-split regimes; initial temperature does not affect this linear steady
problem. Incomplete checks at any cap remain unresolved.

### Reference credibility target

**Buyer tool:** Ansys Icepak/Mechanical transient thermal workflow, a
mock-customer assumption, not verified market share. **Carbon reference:**
proposed Elmer transient solid conduction, **not the same tool**; its task
image/deck/extractor is not yet a demonstrated runnable reference. Tier 1
requires the buyer's exact model/settings, not similar thermal equations.

**Target tier:** Tier 2 for offline burst-envelope simulation decisions.
Tier 3 calibrated heater/stack sensor evidence is needed before real package
thermal-limit or hardware-control reliance. No chip/hardware actuation is
included. **Credibility evidence: NOT_DEMONSTRATED** for this buyer job.

**Benchmark cases:** the published IcepakFEA
[Transient Thermal Solution — Power Resistor](https://ansyshelp.ansys.com/public/Views/Secured/Electronics/v261/en/Subsystems/IcepakFEA/Content/GettingStarted/IcepakFEAGettingStartedGuides.htm)
case and the packet's analytic slab step/pulse and equilibrium controls.
The vendor tutorial intentionally changes heat capacities for instructional
speed; freeze those values for reproducing it, not as empirical package laws.
That example does not establish the two-patch stack response. Add matched
three-layer rectangular/ramp/two-pulse witnesses, hot initial state and both
Robin-cooling conditions in Elmer and the buyer tool, with identical source
power/area and contact assumptions.

**Acceptance tolerance: HUMAN_INPUT.** Recommend maximum temperature-curve/
top-spatial-peak difference ≤0.5 °C, first 95-°C crossing and recovery-time
differences ≤0.5 s, and integrated energy imbalance ≤1%. A crossing or recovery
found by only one tool is UNRESOLVED, not a finite zero error. These recommendations
preserve the buyer's near-limit decision resolution; they do not certify the
synthetic material law or replace the selected numerical controls above.

**Claim boundary:** [common credibility contract](reference-credibility.md).
After accepted Tier 2 evidence, “matches the reference simulator” for the
specified stack/excitations; never “matches reality” or a safe silicon power
rating without the appropriate Tier 3 and separate deployment authority.

## 6. Output and measurement contract

Both patch-center temperatures and top-die spatial maximum at t=0:0.5:120 s,
plus every source event. Retain internal peak/crossing search, not just sampled
maxima; report peak and its time, first 95 °C crossing or NOT_REACHED, and
recovery after the last burst to within 1 °C of the separately computed 20-W
steady baseline or NOT_RECOVERED. The four baseline attempts are explicitly
reserved; if they fail or hit the other caps, recovery is UNRESOLVED, not a
successful recovery claim.
Energy is the integral of the declared waveform minus base, not peak×D for
the ramp. Missing reference rows never become favorable feasibility.

## 7. Construction contract

Prepared Level-0 target: declarative deterministic thermal ROM/interpolation
recipes from allowed public TRAIN only, complete rebuild identity and bounded
runtime. Exact vocabulary/data pins/training limits are not registered here.
No access to future test responses or hidden state; no arbitrary evaluator code.

## 8. Research kit

Provide geometry/waveform docs, own-seed generator/reference, public incomplete
practice, and RC one-node/three-node and POD baselines. Reuse custody, authoring
and reconstruction machinery; build new transient outputs and public kit.
No hidden EVAL/STRESS, seeds or labels in the kit/pods.

## 9. Evidence plan

Run controls before volume. Later comparisons hold out whole waveform families,
not timesteps, and commit schedules before independent reference access. Compare
RC/ROM/learned arms with identical permitted-data/query budgets, including setup
and failure costs. Fresh confirmation, experimental heater/plate observations
and training-budget study are separate, not covered by this feasibility grant.

## 10. Readiness and claim record

Current prospective T2: [buyer value/cost scorecard](../value-cost/f02.md)
and [owner framework](../value-cost/README.md). Require at least five feasible
and five distinct near-limit infeasible actions per mandatory stratum. Report
the overall fraction; it is not a gate. Other value checks still require
evidence. Refinement/acceptance remains HUMAN_INPUT; no new runtime authority.
The original fraction-based observations below retain their historical meaning.

**Before any new hidden bank:** the owner-selected [four-check value prerequisite](../question-laws/value-check-v1.md)
requires per-stratum discrimination and meaningful buyer-unit spread, one
complete feasible action, and changing best/equivalent answers. Numeric
thresholds remain HUMAN_INPUT recommendations; receipt **NOT_DEMONSTRATED**.
For this buyer, report energy spread in J across admissible burst actions; a complete scenario-indexed
schedule is allowed, not a newly imposed single schedule across all contexts.
No favorable redraw, exposure reset, solver grant or qualification follows.


Requirements selected under owner delegation; offline thermal screen only.
Transient reference, numerical adequacy, reconstruction and kit are NOT_DEMONSTRATED.
Next: exact f02 case/deck/observer packaging and controls in an authorized ticket.
No real-chip safety, physical qualification, customer acceptance or launch claim.
