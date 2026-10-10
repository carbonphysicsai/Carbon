# Strong cheap baselines for the eight buyer decisions

**DEVELOPMENT / SPECIFIED.** Owner-approved documents-only task
[CHALLENGE-CHEAP-BASELINES-01](../../../../.agent/tickets/CHALLENGE-CHEAP-BASELINES-01.md).
These are comparator specifications, not implementations, adequate references,
execution grants or demonstrated savings. Baseline timings, decision quality
and end-to-end leverage are **NOT_MEASURED** in this package. Numeric acceptance
and buyer-latency budgets are **HUMAN_INPUT**; preserve existing hard limits.

Use [#857's analysis](../value-cost/analysis.md) without mistaking conditional
annual **buyer-decision value** for surrogate leverage or a KEEP ranking.
The ranking ranges overlap and C2/C3 receipts remain incomplete. The buyer
question is: **does Carbon improve my decision or workflow compared with the
best inexpensive method I can already use?** A cheap method answering it well
is a useful finding, not a reason to manufacture a harder task.

| Card | Buyer decision | First strong inexpensive comparator to measure |
| --- | --- | --- |
| [Battery v3](battery.md) | Five-band safe charging/cooling map | Exact precomputed per-band decision map; conservative output interpolation for covered new conditions |
| [Motor](motor.md) | Precision-joint geometry and command shortlist | Full-curve response surface / Kriging or RBF with harmonic representation, against exact bank lookup |
| [Cooling cell](cooling-cell.md) | Cell thermal/hydraulic shortlist | Cached thermal/hydraulic output map and ordinary response surface under identical buyer maps |
| [f02](f02.md) | Most extra burst joules within thermal limits | Fixed-stack multi-input thermal impulse-response / small ROM, compared with exact schedule lookup |
| [f06](f06.md) | Supported coupler design step | Industry two-stage 2D optimizer plus retained 3D checks; not a 2D certificate for the original 3D job |
| [f08](f08.md) | Lightweight support within static/dynamic limits | Geometry-specific cached modal library, retained-mode sweep and static solve reuse |
| [f13](f13.md) | Packaging-compliant full-band acoustic choice | Transfer matrices where applicable; multimode/reduced Helmholtz sweep for offset chambers |
| [f17](f17.md) | Groove geometry with genuine mixing and manageable pressure | Ordinary CFD-trained RBF/response surface, with flow reuse and finite scalar transport comparator |

The candidate set is deliberately small. Choose the strongest applicable
method using permitted fit/calibration data **before** inspecting independent
witness outcomes; no winner selection on the final witness. Measure all
declared arms or report missing arms, rather than claiming strongest-baseline
success from a convenient weaker control.

## 1. Two different information arms

**CLOSED_BANK:** every eligible action/condition is already solved and lawfully
available to the buyer. Cache the complete decision-relevant outputs and their
uncertainty, not just yesterday's winning design. Reapply requirement draws
and select under the current objective/tie rule. This is the correct strong
baseline for repeated finite-menu decisions; it can equal the reference-best
answer without learning. Charge the original bank/refinement acquisition and
storage once and amortize over a stated number of compatible decisions.
If the bank is incomplete or undecided, exact lookup is incomplete or undecided.
No invented optimum, missing-row pass or exposure renewal.

**NEW_SUPPORTED:** both cheap and Carbon prediction arms receive the same
permitted fit data, not the independent witness outcomes. Hold out whole
geometries or complete physical condition/action panels as appropriate;
angles, frequencies, timesteps and reused conditions are not independent
holdouts. Fit ordinary interpolators/ROMs and freeze all hyperparameters,
support checks and uncertainty policy before witness access. Compare identical
held-out action menus using the same optimizer, query budget and stopping
rule. Report retained reference verification separately from prediction-only
decisions. A partial-bank interpolation result is not the CLOSED_BANK oracle.

If the question concerns arbitrary off-grid action search, give every arm the
same prospective action grammar and independent coverage. A finite bank can
only establish best-in-that-bank, not a global continuous optimum. Do not
introduce new action/support permission just to make this comparison harder.
Unsupported inputs refuse/fallback; they never receive an interpolated safety
pass. A fallback solve requires its own execution authority and is charged.

## 2. Matched decision, not a convenient scalar

Freeze packet/law/task/observer/action/reference identities; service conditions,
hard limits, P, diagnostic Q, evidence weights w and buyer value aggregation;
finite action order, optimizer/query budget and equivalent-set/tie policy.
Reuse [question laws](../question-laws/README.md),
[optimizer contracts](../optimizers/README.md) and existing
`carbon/design_search/tasks.py`, indexed tasks and registered panel adapter.
This document adds no new task schema or producer export API.

For every question and required stratum report:

- Pointwise field/curve/observable errors and extrema, with unit-bearing
  absolute floors near zero; no clipping, favorable normalization or hidden
  averaged safety breach.
- Resolved feasible/infeasible and UNRESOLVED counts, false-feasible and
  false-infeasible decisions, abstentions and denominator/coverage. Two
  unresolved answers do not constitute agreement.
- Both picks, feasible equivalent sets, exact-pick agreement and regret in
  buyer units. Evaluate both picks on the same reference; an infeasible pick
  gets its violation, not finite compensating regret. If the reference cannot
  settle the best/equivalence, report UNRESOLVED. A settled empty feasible set
  stays NONE_FEASIBLE with no redraw.
- Per-stratum contested-boundary coverage, meaningful margin spread,
  complete feasible-answer existence and changing winners/equivalent sets.
  The [current value-cost framework](../value-cost/README.md)'s five feasible
  and five near-limit infeasible designs is a HUMAN_INPUT working criterion;
  global pass fraction is reported, not gamed into a gate.

An observed convergence difference is not a certified uncertainty bound.
Refine every contender that could decide feasibility or ordering under the
registered policy, not just a favored model's winner. New acceptance thresholds
remain HUMAN_INPUT; Test Lead owns power, score use and KEEP/reframe/replace.

## 3. Public witnesses and credibility

Fit/calibration data and independent witnesses are separately identified,
rights-cleared **public draws or retired, published cases** with release
provenance. Freeze selection toward near-limit, decision-flipping, interior
and supported off-grid regions before comparisons; retain all failures and
uncovered regions. An exact fitted-row replay tests lookup/arithmetic only;
it is not generalization evidence. Protected EVAL, STRESS, quiz, tuning,
seeds and labels never enter this baseline work or its public exports.

Follow [#767's credibility contract](../round1/reference-credibility.md).
Buyer-tool witnesses are independently held outside producer custody;
pointwise and decision agreement are both required. Self-convergence and
agreement of a ROM with its training solver do not earn Tier 2. Targets remain
targets; no physical or Tier 3 claim. A systematic reduced/full/buyer-tool gap
is a reference finding, not candidate failure. Revise references prospectively;
already-sealed results retain their original identities and interpretation.

## 4. Total cost and the buyer's actual latency

For each arm return cold/warm and batch CPU time, elapsed wall time, peak RAM,
hardware, thread count, solver systems and process launches. Count a complete
curve/panel as the buyer evaluation, not every frequency/time node. Keep
unique systems, processes and whole decisions as three separate counts.

Separate reference acquisition/refinement, fitting/calibration, compilation,
storage/load, model/lookup evaluations, optimizer bookkeeping and retained
verification/fallback. Include failed attempts. For a compatible reuse count M,

`CPU per decision = (acquisition + fitting + compilation) / M + load + queries + search + retained verification + failures`.

Setup terms include their own failed attempts; the final failures term is only
per-decision failed work not already charged in another term. Never double-count
one failed acquisition as both setup and incremental failure cost.

Charge a genuinely shared acquisition once to each counterfactual deployment,
not zero to Carbon and full cost to the incumbent (or twice within one arm).
Report cold M=1 and sensitivity to evidence-backed reuse; pending that, M=10
and 100 are **ASSUMPTION sensitivity points**, not measured customer volume.
Wall time is measured separately, never equated to CPU time or divided by
core count without scheduling evidence. Use actual licensed-tool/runtime
costs and named currency/rate; no dollar savings from an unquoted CPU-hour.

Report decision-quality-matched cost and latency, plus what extra *supported*
search the saved time enables. Do not monetize an unevidenced quality lift
or reuse #857's gross V2 as measured compute savings. If the strong baseline
already meets the buyer's accepted latency at equal quality and no other
incremental value is demonstrated, report **no demonstrated V4 advantage**.
That is not an automatic portfolio verdict by this document.

## 5. Next handoff, no dispatch

The later owner-authorized implementation is documented in
[ready comparators](ready-comparators.md): one offline command for cooling,
f02, f08 and the scoped f13 control, using public solved panels and pinned
companion materials. It does not adopt the proposed methods or earn V4.

[Data Collection return checklist](data-collection-return.md) is the next
measurement specification. Inventory/reuse existing public outputs first;
any fitting, timing, new reference, buyer-tool or paid work requires the
owning lane's separate authority. No runs, downloads, training or spend occur
in this ticket. Missing solver/deck/extractor/baseline pins are HUMAN_INPUT,
not invented package versions. Cooling is cell-only; Battery EV5, sealed
journal sequence 14 and live contract are untouched. The Hub stays frozen.
