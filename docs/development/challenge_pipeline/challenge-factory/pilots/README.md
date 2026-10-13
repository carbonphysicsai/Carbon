# Eight public winnability run plans — SPECIFIED, no execution grant

WINNABILITY-PILOT-RUN-PLANS-01 / PKT-09; design-only handoff to Data Collection,
Optimizer and Carbon Validator. [plans.json](plans.json) records counts,
source snapshot, assumptions, dependency holds and costs; each row has its
[family runbook](#conditional-order). These are operational specifications,
**not eight executable packages**. None is runnable end-to-end on the inspected
main without further inputs/receipts/grants. No solves, training, builds,
spend, protected material, AX42 or official bank draw occur in this ticket.
The owner, not this ranking, selects Challenge #2 after real results.

## Conditional order: expected information per dollar

| Rank | Pilot | CPU-h hard proposal | Whole-pod wall cap h | Conditional all-in USD cap | Preparation discount L/B/H (ASSUMPTION) | Information/$ base |
|---|---|---:|---:|---:|---|---:|
| 1 | [Burst thermal](f02.md) | 6 | 8 | 10.00 | 0.5/1/1 | 0.300000 |
| 2 | [Solenoid pole](solenoid-pole.md) | 24 | 30 | 36.40 | 0.1/0.5/0.8 | 0.041209 |
| 3 | [AI-chip cooling cell](cooling-cell.md) | 32 | 40 | 48.40 | 0.1/0.5/0.8 | 0.030992 |
| 4 | [Precision robot-joint motor](motor.md) | 56 | 64 | 77.20 | 0.1/0.5/0.9 | 0.019430 |
| 5 | [Bolted joint](bolted-joint.md) | 48 | 56 | 67.60 | 0.05/0.25/0.5 | 0.011095 |
| 6 | [Seal gland](seal-gland.md) | 32 | 40 | 48.40 | 0.02/0.1/0.5 | 0.006198 |
| 7 | [Planar transformer](planar-transformer.md) | 40 | 48 | 58.00 | 0.01/0.1/0.4 | 0.005172 |
| 8 | [Connector contact spring](connector-contact-spring.md) | 40 | 48 | 58.00 | 0.01/0.05/0.3 | 0.002586 |

Index =3 descriptive questions (learnable/advantage/headroom) x a transparent
preparation discount / proposed **worst-case cash cap**. The discount is a
reversible planning judgment, not a probability, measured readiness count,
scientific score or forecasted ROI. Recompute at both discount endpoints;
ranges overlap. **Actual information/$ floor is zero for all eight** while
inputs/reference/route/grant are missing. f02 can cheaply falsify the advantage
hypothesis because the task is linear; solenoid has a plausible nonlinear
residual but a new axisymmetric-reference gap. Motor is reuse-first because a
new full-role bank is costly. Seal/spring depend on material/buyer sourcing;
transformer3D costs are unknown. These costs are NOT bank startup C2 acceptance.

## Hard lifecycle bound, conditional on a grant and tested enforcement

One RunPod Secure Cloud CPU pod,32 vCPU/64 GB; no GPU, no network volume,
<=20 GB combined temporary disks,<=2 GB retained compressed public output.
USD0.96/h is the **historical owner console quote** recorded in
[pilot-caps](../../pilot-caps/README.md), not a verified current offer.
Require an inclusive current compute/tax/payment quote <=USD1.20/h and all
other lifetime charges <=USD0.40. These are proposed quote ceilings, not a tax
assertion or a provider guarantee. If memory/fees/quote exceed them, HOLD;
do not silently switch to256 GB, transfer another family's cap or borrow an
existing sealed-run grant.

Compute bill upper bound:
`ceil(100 * ceil(seconds/60) * 60 * 1.20/3600)/100 +0.40 USD`.
Charge **allocation to confirmed termination**, including setup, transfer,
idle, fits, probes, failed attempts, export and provider-deletion latency.
Allocated vCPU-h is32 x wall-cap; actual aggregate user+system CPU across
children has its own smaller hard cap. Never divide USD by used cores.
Expected wall =scenario CPU-h +1 setup/export hour under a conservative serial
hypothesis, not measured throughput or an execution guarantee.

Use whole-minute upward rounding despite [RunPod's documented per-second
billing](https://docs.runpod.io/pods/pricing) (checked2026-10-13); storage and
stopped resources can still bill. [Terminate, do not stop](https://docs.runpod.io/pods/manage-pods),
after export to the already approved public store; confirm absence by the
deadline. Current availability, invoice terms, complete native-tree transport,
host-key checks and **independent allocation-to-termination expiry enforcement**
are mandatory release holds. A killed solver/local timer/balance auto-stop is
not enforcement. No launcher/provider credential inspection is added here.
These are new grant PROPOSALS only: #1217's free-CPU-only cap and all earlier
non-transferable feasibility grants stay unchanged. Reuse-only analysis may
need no rental at all; the priced host is a ceiling for a separately approved
next execution ticket, not a request to rent all eight now.

For each row, the timing probe is the first new coarse **complete atomic reference
case**: full history/curve/excitation set for that geometry/condition, not a
free extra/control or a single matrix/stroke. A motor atomic unit is one whole
signed angle sweep, explicitly NOT its full eleven-sweep buyer bundle; cooling
is one complete cell/map, not all three service maps. Report this partial-cost
scope, then sum all mandatory atomic units when charging a buyer decision.
Never substitute one-condition C1 for full-action verification. Probe lifecycle is30 min
(USD1.00 cap) or90 min for motor/cooling (USD2.20 cap), inside the same family
wall/cash/attempt ledger. Setup<=5 min; export/confirmed deletion reserve10 min;
safety5 min; solver remainder10/70 min. A timeout yields INCOMPLETE_TIMING,
not measured C1. After a complete same-host/profile/core-count probe, each
follow-on watchdog is2 x measured complete-case wall x declared complexity
ratio; this is a hypothesis, not a p95 estimate. Start only if its entire
watchdog, remaining CPU/attempt allowance and deletion tail fit. If reallocation
is necessary, its additional lifecycle/fees must fit the same cap. No retries.
Within a pod: one case/process at a time, solver threads1 (motor<=2), fit<=4;
aggregate CPU accounting includes all child processes and BLAS threads.

## Freeze-before-truth sequence: what Data Collection returns

Counts are conditional targets, not registered draws. For each new family,
freeze 16 TRAIN and 12 held-out action coordinates before labels, using the
source grammar's valid normalized support (or supplied absolute bounds).
Use a pinned public low-discrepancy sequence with public seed0; bounded grammar
rejection may exclude invalid geometries before reference access, never outcomes.
Solenoid/transformer holdouts include S01-S10/T01-T10 plus two registered
interior actions; the source proposals are not absolute anchor approval.
Bolts use the existing81-action/four-condition grammar. The exact 28 actions,
predeclared reserved diagnostic tuples and all rungs must be emitted and audited
by Data Collection; this document cannot invent missing seal/spring bounds.
Declare12 potential edge refinements before truth: four per stratum (three for
each of the four bolt strata), ranked by smallest signed margin/registered
uncertainty distance, ties canonical action order. Freeze that predicate first.
If more deciding cases need refinement than fit, mark the remainder UNRESOLVED;
do not cherry-pick a complete feasible bank. The four failure-cost reserve slots
are conservative accounting, not retries or favorable replacements. A failed
reference remains in its original question; unused reserves stay unused.
Reuse-first families acquire no new corpus merely because a source is absent.

1. **Binding (no spend):** approve source-confirmed unchanged buyer question,
   absolute drawing/material/history/rights, supported ranges and hard limits;
   exact image/source/native-tree/deck/mesh/extractor pins, applicable accepted
   code verification plus convergence/conservation/observer uncertainty.
   GetDP motor linear MMS and Elmer heat MMS are not universal family acceptance.
   Current image-store presence is UNKNOWN until a dated sanitized receipt.
   The stock ubuntu:24.04/native-tree-over-SSH pattern requires an exact base
   digest, binary/library/source/compiler/thread identities and reviewed
   equivalence evidence. No Docker-in-pod assumption. Copying files from an
   accepted image does not carry its MMS acceptance to a changed ABI/environment;
   a rebuild/re-pin needs new native checks and applicable acceptance before
   execution. Packaging authoring labour is separate and HUMAN_INPUT, not hidden
   inside CPU cost. These pilot caps do not fund buyer-tool licences or experiments.
   Apply the central seven-item evidence-readiness spending rule: all seven
   prerequisites must be supported, except outputs explicitly named as produced
   by this exact run in its owner/operator grant. Missing kit/comparator/route
   code or human acceptance is not a data-produced exception. No automatic
   waiver, protocol-stage advance or transferable grant is created here.
2. **Public registration:** exact action x condition x rung tuples, all
   planned controls/refinements, complete retained AND scheduled inventory,
   physical reuse/disjointness audit and query-policy identities. Public pilot
   identifiers/seeds are owned research metadata, never protected exam entropy.
   No official EVAL/STRESS/quiz/tuning, EV5, journal14 or AX42 sources.
3. **Dataset contract:** TRAIN/support/calibration folds and independent
   PUBLIC_HELDOUT geometries; register the finite eligible menu and k question
   draws, P/Q/w separately. New candidate proposals use16 whole-geometry TRAIN
   and12 whole-geometry holdouts; bolts retain four strata, not three.
   Candidate-only normalized ranges do not replace missing absolute anchors.
   Material/stratum/history/rung siblings never cross the geometry split.
   Multiple curves, skew variants, repeated thresholds and seeds do not become
   independent buyer clusters. If heldout labels were used during earlier
   development, disclose it and register new independent witnesses before
   positive confirmation. This triage cannot supply S10/qualified power.
4. **Arm preparation:** all arms use the same permitted TRAIN acquisition.
   Fit plain L0 via existing defaults, seeds0/1/2, no label-tuned recipe.
   Baseline selects strongest analytical/map/ROM/FE method using TRAIN-only
   grouped calibration folds; no heldout fit or truth-table screening.
   **Solve acquisition cost is never free because records already exist.**
   Preserve original measured cash/wall/core receipts, shared benchmark costs
   and sunk acquisition separately; return M=1/10/100 served-decision sensitivities.
   New solve counts describe this proposed acquisition, not three extra solves
   per replayed verification. Every physical failure/refinement counts once
   in acquisition and is charged at its measured cost in each simulated workflow.
5. **Same-budget search:** precommit the strong direct/adaptive solver policy
   (physics/known objective ordering, no hindsight optimum) and model/cheap
   ranks before referee outcomes. Direct search may exploit public equations,
   monotonicity and known objective values. Equal budget means registered
   wall/core/evaluation limits for **complete mandatory-condition decisions**,
   not one cheap role while omitting others. Record query/fit/calibration,
   attempted/action verification/refinement and failed-call costs.
6. **Return:** exact export/sidecar/kit/TRAIN/reference-cost ledgers, complete
   signed curves/history/required quantities, outcomes and unresolved intervals,
   measured p50/p95 only when enough full cases exist, peak RSS, every excitation,
   refs/policy/rights hashes, allocation/deletion receipts and all-in invoice.
   No success inferred from a missing body or PASS Boolean.

The8/12-question k values and small TRAIN counts are **PROPOSED ASSUMPTION**,
not accepted laws or sample-size power. Too-small/collinear training or only
one independent buyer cluster makes the result INDETERMINATE; do not widen
the menu/safety bands to manufacture learning or statistical resolution.
Retain forward NONE_FEASIBLE without redraw only when every eligible action
has settled mandatory failure; otherwise UNRESOLVED. Report each stratum's
five-pass/five-fail-near boundary counts under the **two-refinement-band**
Test Lead working rule, with adopted task-specific bands or HUMAN_INPUT.
Overall pass fraction is descriptive, never the old20-80% gate.

## Actual OPT-12 bridge, not a new harness

The [merged input/report contract](../winnability-harness.md) and
`carbon.design_search.winnability_pilot.evaluate` consume precomputed data;
they perform **no acquisition, inference, fitting or solver execution**.
Supported routes today: motor,f02,cooling-cell,bolted-joint (among other
existing families). Solenoid,seal,spring,transformer have **no route**:
Optimizer must implement and register exact family adapters before replay.
Never alias them to motor/f08. The L0 CLI's actual kits are motor,f02,battery-v3;
cooling and all five candidates still need their own covered kit/arm producer.

For motor/f02 only, after the grant/preflight, the existing producer CLI shape is:

```text
python -m carbon.development_comparison.carbon_arm FAMILY --export PUBLIC_EXPORT.json --export-sha256 EXPORT_SHA --train PUBLIC_TRAIN.jsonl --train-sha256 TRAIN_SHA --scope PUBLIC_DEVELOPMENT --backend pytorch --seed 0 --output-dir NEW_OUTPUT
# motor additionally requires --material PUBLIC_CURVE_SIDECAR.json --material-sha256 MATERIAL_SHA
```

Repeat public seeds1/2 within the SAME fit cap; receipts bind exact code/env
and data. These commands are instructions for later authorized execution,
not commands executed by this ticket. CPU device and thread limits must be
enforced by that runner. Do not pass unsupported kit family names to the CLI.

Optimizer assembles each seed's closed input:
`schema=carbon.design-search.winnability-pilot-input.v1`,
`evidence_class=DEVELOPMENT_PUBLIC`, digest-bound `equal_budget` panel +
matching complete budget `registration`, exact method roles
PLAIN_L0_MLP / STRONGEST_APPLICABLE_CHEAP / REGISTERED_ADAPTIVE_SOLVER,
`question_law={P,Q,w,panel_use:PUBLIC_HELDOUT}`, measured
`preparation_cost={model,baseline}` with wall_s/core_s,
`served_decisions=[1,10,100]`, one closed `learning` row per job,
`learning_unit` and `cost_record_digest`. Freeze real identities first;
HUMAN_INPUT strings are not substitutes for approved laws/receipts.

Each job binds job_id/cluster_id/stratum, complete candidate reference intervals,
actual solve_cost and planning_bound, precommitted solver_order and screen_rank,
and screen_cost. Family budget registration supplies half/base/double tiers;
the1/3/5 verification-count sensitivity requires separately compatible
registrations, not arbitrary edits to a closed budget or free refinements.
Bolted panel additionally carries REPRESENTATIVE/customer_result=false.
f02 uses EQUAL-BUDGET-V2-F02-MENU; other existing proposals are not grants.
The strongest-baseline claim and adaptive-policy fidelity require owner review
of the actual producer traces; merely setting those role labels proves neither.

```text
python -m carbon.design_search.winnability_pilot evaluate PILOT_INPUT.json --bootstrap-replicates 2000 --confidence 0.95 --seed 0
```

Bootstrap settings above are reproducibility recommendations, not adopted
scientific confidence/power. This no-execution replay may run only after its
real input exists. Returned scientific decision remains UNDECIDED.

| Question | Exact read from report | External evidence still needed |
|---|---|---|
| Learnable | learnable[stratum]: mean_pointwise_error, decision_agreement_fraction, false_feasible_count, missed_feasible_count, abstention_count, resolved/none_feasible/unresolved counts | Unit-specific raw maxima/curves, coverage denominator, per-design margins, useful-error/false-feasible limits HUMAN_INPUT |
| Advantage | advantage_and_headroom[M].model_vs_cheap[tier].paired: paired_model_minus_cheap_improvement, p_model_strictly_beats_cheap; paired_bootstrap_ci; equal_budget curves/cost results | Positive/negative full-cost latency/value evidence against the ACTUAL strongest incumbent; min gain/confidence HUMAN_INPUT |
| Headroom | advantage_and_headroom[M].finite_bank_headroom[tier]: finite_bank_mean_mlp_regret_conditional, mlp_feasible_pick_fraction, unit | Best resolved finite-bank alternatives and interval overlap, not a proven global optimum; contestability floor HUMAN_INPUT |

Do not emit PASS/PARK automatically. Reference failure blocks replay/grades;
missing input/cost/independence is not model failure. Portfolio park/adoption is
the owner's later decision. Keep data and limits unchanged to test buyer value,
not to make a learned model win.
