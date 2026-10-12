# Public-array measurement protocol

**RES-06; DEVELOPMENT descriptive analysis, no qualification.** No executable,
runtime gate or raw input is delivered. This is the specification of the local
array arithmetic behind [measurements.json](measurements.json). Sources and
exact definitions are in [SOURCES.md](SOURCES.md).

## Evidence boundary

The owner supplied `codex-queue/inputs/ev4-public-proof/` read-only and explicitly
identified its contents as public development data without sealed cases. The
audit uses only prediction keys matching the original EV4 **development**
decision grid in R10. Other entries carried inside the same bundles are not
used. No WSL worker, reconstruction, solver, training, tuning-fold scoring,
hidden-material service or paid compute is invoked. Raw files and the queue
stay uncommitted. Bundle SHA-256 and reference SHA-256 identify the analyzed
copies; digests alone do not demonstrate provenance authenticity.

Take all original development input keys, then form a common law-audit case
mask containing only records with `status=OK` and outputs. A missing reference
is withheld, never made a model failure. Group these cases by the exact supplied
ambient-temperature/initial-SOC pair. Do not interpolate a stored prediction to
pretend that a model was queried at a new input.

Deduplicate overlapping input-folder copies only when the same filename has
identical compressed bytes. Refuse differing copies. Keep distinct original
members even when their predictions agree: numerical equivalence alone does
not establish independent builders or duplicate artifacts. Record recipe
digests when present for future cluster-aware inference. Reconstructed-member
labels present in historical EV4 identify a **CPU-rebuild cohort**, not the old
A40 artifact. Graphite, additional proof and adversarial rebuilds are separate
cohorts. Recreate the five labelled controls using exactly R12 on the supplied
OK public development references; controls are never real miners.

## Observable checks and residuals

For each valid case, require finite arrays of the R03/R05 shapes. Check existing
initial voltage against linear interpolation in R07, initial temperature
against ambient, voltage floor/ceiling and capacity positivity/inventory ceiling
using R06's **historical** tolerance values. Record both the number of failing
cases and whether a member has any failure. These are old checks on new public
artifacts, not newly approved tolerances.

For rest-period causality, at each common temperature/SOC condition and each
of `t={0,30,60,90}` seconds, calculate the maximum predicted value minus the
minimum over charging protocols. Take the largest span over times and
conditions, separately for voltage (V) and temperature (degC). The reference
rest is 120 s (R04); exclude the 120-s controller switch because endpoint
interpolation/algebraic discontinuity requires a separate measurement contract.
The continuous-time equations imply invariance to the inactive future CC
commands. Cached-reference spans only calibrate numerical representation.

Research sensitivity floor for each span:

`f_y = max(2 × largest reference span, 32 × float32_epsilon × scale_y)`.

Here `scale_V=4.2 V` and `scale_T=40 degC` reuse R05's old initial-gate numerical
scale convention. The factor 2 and float allowance follow the existing
calibration pattern; **their transfer to a pairwise gate is ASSUMPTION, not an
approved rule**. Examine multipliers `{0,1,10,100,1000}`. All multipliers, floors
and any allowed failing fraction are `HUMAN_INPUT` for adoption. Low/base/high
planning multipliers are ASSUMPTION `{1,10,100}`; zero and 1000 are stress endpoints.
The report publishes each curve so a tolerance cannot be selected invisibly
after seeing a preferred member.

Also record largest `max(ambient-min(T),0)` and `max(-273.15-min(T),0)`, and
largest positive capacity checkpoint increment. Temperature-above-ambient and
monotone fade are **diagnostics, not valid unconditional gates**. Apply no
physics-rejection verdict to them. The absolute-zero check assumes declared
degC units and uses BIPM's Celsius/Kelvin conversion. Signed plating margin is
never a model-physics failure.

## Decision association, freshly computed on the same artifacts

For each development condition, measure time from 120 s to the first 4.19-V
crossing by the R11 30-s linear interpolation. Model point predictions choose
the smallest time among the 35 R10 actions satisfying all R10 constraints;
ties use lower c1, then lower c2. No qualifying proposal means abstention.
Verify the selected action with the supplied references and R10's existing
bands (time 3.15 s, plating 0.00197 V, temperature 0.157 degC). A reference FAIL
dominates its UNRESOLVED calls; failed/missing reference means unavailable.

Retain every outcome kind. Unsafe-member flag means **at least one observed
SELECTED_INFEASIBLE development choice**, not a safety classification for the
whole model. Members with no observed unsafe pick can still have unresolved
choices, abstentions or poor feasible decisions. A flagged such member is
reported as "flagged without an observed unsafe choice", never as a proven
false rejection of a safe model.

Use the unchanged R10 descriptive loss: false acceptance 10, missed
opportunity 1, feasible regret `(chosen_time-best_feasible_time)/120`, correct
resolved abstention 0, and unresolved/unavailable loss missing. For each cohort,
compute mean loss on the intersection of its members' resolved conditions.
Report its mask size. This can be small and does not estimate the full target
population. Kendall tau-b relates residual magnitude to loss only on that mask;
positive tau means more inconsistency accompanies worse observed loss.

For each sensitivity cutoff give counts: flagged members with an observed
unsafe pick, flagged members without one, unsafe/no-observed-unsafe denominators,
and total flagged. Do not select a hard gate from tau alone. Data have shared
cases, repeated recipes/seeds and retrospective selection. There are no
independent-member confidence intervals or confirmatory p-values here.

## Arithmetic controls and limits

Check the reference-as-prediction control passes the historical checks and
pairwise-span floor. The plating-only sign control must preserve the oracle's
voltage/temperature/capacity residuals. Count each explicitly supplied matching
case once, prove duplicate folders do not increase the panel, and reconcile
every development decision's outcome count with the condition count. Inspect
raw-versus-summary cohort boundaries; never attach old EV4 loss to a new bundle.

Publish the full strict-`>` rejection curve at every observed residual
breakpoint, in addition to the fixed sensitivity multipliers. Observed
breakpoints are descriptive and do not supply acceptable physical tolerances.

One post-hoc synthetic bypass is evaluated: start with the public boundary
optimist, clamp every temperature to ambient and replace its four pre-charge
temperature samples with ambient. Leave voltage, plating and capacity fixed.
Check that all twelve decision outcome dictionaries remain exactly identical.
This bypass is reported separately, excluded from the original five-control
cohort and all real-member denominators. It tests whether satisfying the visible
checks can improve gate status without improving decision value.

Charge, lithium and energy conservation, probability calibration, repeat/order
tests requiring new evaluations, and unseen interpolation/extrapolation probes
remain **NOT_MEASURABLE** from these stored arrays. Their designed tests are in
REPORT.md. No apparent correlation establishes physics truth, safe operation,
causation, future shifted-question value or an adequate production exam.
