# VALIDATOR-31 publication options and acceptance plan

**OPTIONS_ONLY / PROPOSED_NOT_ADOPTED.** The owner's prompt supplies the
VALIDATOR-31 options; its draft was not in the checked public main tree or open
PR list. This is not an implementation review of that draft. Risk rankings below
are qualitative inferences, not measured extraction probabilities. No publication
cap, precision, delay or acceptable copy advantage is approved here.

## Compare the requested options

| Option | Copy-risk mechanism and remaining risk | Customer-demo value and loss | Research judgment |
|---|---|---|---|
| Fewer fixed public inputs | Less geometric coverage and fewer labels; even a small full-rank set identifies simple function classes. A rotating set restores cumulative coverage | Shows real inference and selected decisions; less freedom to explore the family, weaker evidence of broad applicability | Best first numerical-disclosure control when paired with cumulative accounting and no arbitrary-input route |
| Coarser predictions | Quantization reduces information per value; useful approximate fitting remains possible. Raw JSON, traces and downloads must have the same restriction | Trend/shape remains visible; small gains and near-limit feasibility may be obscured or reversed | Complementary control, not a standalone extraction defence |
| Delayed live publication | Denies immediate labels until release; eventual information and archived copies are unchanged. Repeated releases can still accumulate | Demo is stale; users cannot independently replay today's incumbent behaviour | Useful timing protection if the staleness is explicit; not permanent secrecy |
| Publish after dethronement | Holds the exact current panel back during its tenure; predecessor labels still seed copying/fine-tuning and public archives are permanent | Historical evidence is reproducible; loses the direct “try today's best” claim, possibly for a long reign | Stronger current-tenure protection, with lineage leakage and demo-latency cost disclosed |
| Per-case errors vs public truth | Signed/normalized residuals may reconstruct the prediction. Absolute or squared errors leave limited ambiguity. Feasibility/selected-design signs add information | Good explanation of error patterns and adverse cases; changes little if the prediction can be reconstructed | Do not call it protection without an invertibility audit |
| Fixed aggregate errors + decision outcomes | Many predictions contribute to a small summary; repeated overlapping aggregates and selected-point values still leak | Preserves regret, false-feasible findings, latency and limits; loses raw-response replay and spatial error inspection | Best public evidence-first option if aggregate groups are fixed and all route disclosures are counted |

Literature supports the direction, not these options' numeric safety:
[rounding and label-only attacks](https://www.usenix.org/system/files/conference/usenixsecurity16/sec16_paper_tramer.pdf),
[accuracy versus fidelity and auxiliary data](https://www.usenix.org/system/files/sec20-jagielski.pdf).
Carbon's actual projection and algebraic error reconstruction are in
[EXPOSURE_AUDIT](EXPOSURE_AUDIT.md).

## Recommended package for the owner to consider

Use a **fixed public decision replay** with a declared, cumulatively bounded
numerical trace; show solver-verified outcome, latency, aggregate prediction
error, false-feasible/adversarial findings and applicability limits. Do not send
the full live prediction map to the browser merely to draw a smaller chart.
Withhold broad live tables/fields until the chosen delay or dethronement stage.
Continue publishing honest adverse evidence in the dossier; withholding a
numerical training set is not permission to hide a failure.

A full numeric replay necessarily exposes its visited input/output pairs. To
offer unrestricted interactive exploration without increasing live-incumbent
exposure, use a deliberately open demo artifact/control and clearly name it.
The user sees a real workflow, but that does not demonstrate today's incumbent
on arbitrary new problems. A restricted public replay proves less; say so.

Publication policy must bind the artifact, lineage, Challenge family, public input
set, quantities, rounding/aggregation, timing and all download/API routes. Record
distinct input count, scalar/field count, repeat count and cumulative release
history. Per-IP rate limits or hiding a recipe do not erase downloadable labels;
Sybil identities can fetch the same public data without interacting with the
incumbent. Signing establishes provenance, not secrecy.

No numerical cap can be recommended as safe from these papers alone. The
choice depends on how much additional verified design value the demo gives a
copier and how much customer understanding each restriction loses.

## Quantization and delay sensitivities

For nearest-step quantization q, the disclosed scalar identifies an interval
of width q, with maximum rounding error q/2 (conditional on no clipping).
If q/2 exceeds a candidate's feasibility margin or the model difference being
demonstrated, a displayed feasibility/comparison claim can be wrong. Use the
solver-verified label and indicate ambiguous model predictions rather than
declaring safety from a rounded value. Units and q are Challenge-specific
HUMAN_INPUT; aggregate-score precision cannot be copied across different output
units.

Illustrative **ASSUMPTION** low/base/high numerical-display steps, in normalized
output units: **0.001 / 0.01 / 0.1**. Corresponding maximum rounding errors are
**0.0005 / 0.005 / 0.05**. No normalized output range or safe physical limit is
claimed. For a bounded normalized [0,1] scalar, at most
`log2(floor(1/q)+1)` bits encode its quantized bin; for the three steps this is
approximately **9.97 / 6.66 / 3.46** bits. These are representation bounds,
not independent information bits, an extraction-time estimate or a guarantee.
Smooth function structure can still be fitted from intervals.

Delay sensitivity **ASSUMPTION** low/base/high **1 / 7 / 30 days** merely shifts
the earliest label access by those amounts. Eventual distinct points and
information are unchanged if all releases arrive later. These are sensitivity
scenarios, not a rollout schedule. Publication-after-dethronement has an unknown
delay, so no numerical “base time” is invented. Rights to already published data
and contractual restrictions remain the owner's/counsel's decisions.

## Public-only experiment for a defensible policy choice

This is a design to hand to Validator / Test Engineer, **not a run performed by
research**. Freeze models, disclosure variants and public holdout splits before
measuring. Use a rights-cleared public stand-in incumbent, never the sealed
exam, AX42, the live model endpoint or its private retained state.

**Factor grid.** Hypothetical distinct-point counts low/base/high
**15 / 60 / 420**, all **ASSUMPTION** sensitivity, not safe caps; compare a fixed
set with disjoint releases having the same union size. Test raw projection,
unit-declared coarse bins, selected-only trace, signed residual, absolute error
and fixed aggregate summaries. The earlier quantization/delay scenarios are
optional factors. Match training effort, public auxiliary data and solver-alone
budget; include the no-demo model as a control. Add a full-table lookup control
to expose memory on repeated public points.

**Attacker families.** Simple polynomial/response-map, interpolation/kNN,
small neural regression, and public-reference model plus learned residual.
All use only the proposed disclosed surface. An adaptive oracle attack belongs
only to a variant that actually grants such an oracle. Predeclare construction
budgets and eligibility; do not give the copy unlimited work or confuse an
inadmissible lookup with an official miner. No attack implementation or training
is delivered by this PR.

**Measurements.** Report fidelity to the stand-in incumbent separately from
accuracy to public solver references; paired decision regret, best
verified-feasible value at matched verification budget, false feasibility, gate
recall and the resulting takeover verdict. Evaluate unseen public geometries/
conditions and near-limit strata, separately from the disclosed grid. Include
publicly declared novel variants without modifying P/Q/w or covertly choosing
easy holdouts. Resample independent source/question blocks and model-build
seeds as appropriate; do not count correlated scalar channels as independent
case evidence.

**Utility panel.** Record whether a reader can identify the engineering decision,
model-versus-reference mismatch, uncertainty, false feasibility and the next
verification action. Measure comprehension and replay fidelity; no user-study
results or customer conversion claims exist yet. Label staleness, development
scope and missing live-model evidence explicitly.

**Owner decision curve.** Plot marginal copier decision-value gain over the
no-demo control against demo comprehension/replay utility, across disclosure
variants and budgets, with uncertainty bands. All acceptable advantages,
minimum utility, noninferiority tolerances, alpha, sample sizes and publication
policy stay HUMAN_INPUT. If the upper bound on incremental copy value is not
resolved, mark protection unproven. The owner may deliberately accept copying
risk for an open demo; this research does not silently make that trade.

## Cheap detectors and their limits

Canonical digest priority rejects exact duplicate submissions; a private,
authorized audit can flag unusually close residual-pattern agreement on fresh
cases, demo-only accuracy and degradation on undisclosed public variants. These
are investigation signals. Two good models can agree because physics is the
same; a copier can improve reference accuracy while differing from the victim.
Similarity alone must not become an unsourced scientific failure or IP verdict.

No live query-pattern detector can stop someone fitting a static downloaded
dataset offline. Deliberately corrupting scientific demo labels or hidden
references as watermarks would require new explicit authority and is not
recommended here. Keep factual errors, adverse findings and qualification limits
honest. Do not publish a protected canary or hidden identifier for this study.
