# Scorelab (OPT-15)

## OPT-16: V2 bank producer workflow

`bank-plan` consumes a registered V2 definition, a digest-bound committed draw
from the Challenge's P law, and a committed block-split seed. It does not draw
P, invent a reference policy, or run a solver. Its `--out` file contains the
full contexts, split, every action-by-condition requirement and the distinct
physical reference jobs: keep it on the **producer**, never publish it or feed
it to a miner. A draw supplies `physical_context` separately from buyer
requirements, so objective/limit-only neighbours reuse the same solve.
Reusing one physical case across blocks is refused, and reused records must
carry the same solve digest. The command prints
only question and job counts. Data Collection owns the Challenge drawer and
reference launcher; their outputs are registered inputs, not built here.

```sh
python -m scripts.dev.score_lab bank-plan \
  --registration REGISTRATION.json --draws COMMITTED_DRAWS.json \
  --definition docs/development/value-metric-v2/definition.v2.json \
  --split-seed-file PRODUCER_SEED.txt --out PRODUCER_PLAN.json
python -m scripts.dev.score_lab bank-cost \
  --plan PRODUCER_PLAN.json --policy REFERENCE_POLICY.json \
  --coarse COARSE_MARGIN_RECORDS.json --jobs-out PRODUCER_REFINEMENT_JOBS.json
python -m scripts.dev.score_lab bank-solved-check \
  --plan PRODUCER_PLAN.json --records PRODUCER_SOLVED.jsonl \
  --definition docs/development/value-metric-v2/definition.v2.json
```

`bank-cost` without `--coarse` reports the total cost as
`UNKNOWN_UNTIL_COARSE` when refinement is required. With complete coarse
records, it uses the bank's actual in-window action-condition share and the
registered per-rung CPU/wall costs; `--jobs-out` is producer-only. `bank-solved-check`
requires every question, action and condition, verifies their planned job IDs,
image and overlay lock, classifies by reference alone, enforces whole-block
halves and the alpha block minimum, and prints aggregate counts. Its
development-half diagnostic reuses `bank-check`; owner thresholds remain
HUMAN_INPUT. A structural result does not qualify the bank or authorize
opening the confirmation half. The full solved records and confirmation half
remain in custody. The toy fixture in `test_score_lab_bank_builder.py` exercises
the commands without Challenge physics or protected material.

An offline **DEVELOPMENT** diagnostic for score/value alignment. It runs
without a model reconstruction, reference solver, network call, hidden bank or
AX42 access. Analytic surfaces have exact reference values; their shapes,
error populations and verification costs are assumptions, not Challenge
physics. No result changes a registered score or qualifies an exam.

## OPT-15b: physics and task neighbourhoods

`physics` runs the same ten trusted Validator candidate functions over analytic
toy questions. All levers are in a versioned JSON config; the checked-in
`physics-example.json` is labelled **ASSUMPTION** and is not a proposed
Challenge rule. It sets problem shape and difficulty, four model traits,
population mix, task-shift size and directions, coverage, k, verification cost,
abstention and unsafe-pick losses, neighbourhood weights, physics switches,
and a one-factor sensitivity sweep. The four toy traits are law-violation rate
and size, rollout drift, robustness to small input changes, and extrapolation
error. `law_violations` passed to the Validator's wrapper is the product of
the configured rate and size; the two source knobs remain separate in the
config. B15/B9/B16 values on toys are explicit diagnostic proxies. Nothing in
this config is a physical law or an adopted tolerance.

The lab keeps scoring and value questions disjoint. True value is computed
from analytic references on in-range targets, four kinds of slightly changed
tasks (objective weight, constraint limit, operating context, boundary), and
extrapolated contexts. The neighbourhood blend is `(1-rho) * target + rho *
mean(neighbours)` on a matched question index. The "exact oracle" for this
extension is exact enumeration of the offered actions, including when the
underlying analytic surface is sampled densely. The Score Lab does not claim
a continuous-domain optimum from that enumeration.

The candidate adapter forwards only scoring-side neighbour questions and
member physics traits. It preserves the Validator wrapper's GATE/FLOOR/BLEND
results. FLOOR ranks lexicographically by `(tier ascending, score descending)`;
its original score is unchanged. Missing measurements fail closed where the
Validator wrapper says they do. OFF is a mandatory baseline. Every rule and
switch reports target, shifted, extrapolated and blended Kendall tau with
exploratory bootstrap intervals, known-bad/gamer placement, and false
exclusions among the configured top fraction of true-value members. A
one-factor table reports which candidate positions change at each switch.

```sh
python -m scripts.dev.score_lab physics \
  --config scripts/dev/score_lab/physics-example.json \
  --candidates codex-queue/inputs/score-lab-candidates/candidates.py \
  --out /tmp/scorelab-physics-toy.json
```

Tier 2 optionally joins PLT-01's digest-bound **public development** B15 and
B16 paired residuals for 142 real members to the separate public B9
below-ambient diagnostic for the same 142 IDs. B9 is a diagnostic card metric,
not a valid hard law. The compact EV4 replay has score/value records for 100
of those members; it has no shifted or extrapolated real references. The
three candidate families with exact public registry IDs are attempted, and
those missing score legs remain `INSUFFICIENT_EVIDENCE`. An independent exact
registry anchor such as v9 `A` can be supplied to measure the effect of the
observed traits without relabelling that anchor as one of the ten candidates.
The source hashes and coverage appear in JSON. Every real trait limit and
blend weight in the example remains an uncalibrated **ASSUMPTION**.

```sh
python -m scripts.dev.score_lab prepare-ev4 \
  --public-dir codex-queue/inputs/ev4-public-proof \
  --repository . --out /tmp/scorelab-ev4-public.json.gz
python -m scripts.dev.score_lab physics \
  --config scripts/dev/score_lab/physics-example.json \
  --candidates codex-queue/inputs/score-lab-candidates/candidates.py \
  --public-cache /tmp/scorelab-ev4-public.json.gz \
  --plt-readings codex-queue/reports/plt01-calibrated-readings.json \
  --b9-measurements docs/development/evidence/physics-consistency-gates-01/measurements.json \
  --tier2-registry docs/development/evidence/battery-score-tuning/registry-v9.json \
  --tier2-candidate A --out /tmp/scorelab-physics-public.json
```

In the example run, synthetic FLOOR improved N2's point tau from -0.694 to
0.276 in-range and from -0.309 to 0.690 on extrapolated questions, while
wrongly excluding one of the configured good members. The public EV4 v9 `A`
anchor instead changed from tau 0.334 OFF to 0.337 under the assumed B15
gate, 0.229 under the assumed B9/B16 floor, and 0.263 under the assumed
three-trait blend. These are descriptive, retrospective point estimates, not
evidence that a switch should be adopted. The public panel has no real
off-distribution reference outcomes, and the toy population is constructed.
No owner value, scientific gate or score rule is selected here.

## One-command synthetic loop

From the repository root, run through `./scripts/dev/canonical.sh` on a
noncanonical host. The default grid is 32 profiles: small-grid/continuous,
single/multiple optima, loose/tight coupled constraints, nominal/shifted
conditions and two assumed verification costs. `--quick` runs four smoke
profiles. Every profile has unbiased-low/medium/high members, boundary bias,
rare tails, a toy physics-law violator, overconfident uncertainty, a bilinear
lookup, always-abstain, an edge optimist and a score-path gamer. Model
predictions on score and value questions are disjoint.

```sh
# All ten Validator candidates in eight families, from the owner's read-only
# local copy. This file is not committed to the Score Lab PR.
python -m scripts.dev.score_lab synthetic \
  --candidates codex-queue/inputs/score-lab-candidates/candidates.py \
  --value-workflow v2-shortlist --buyer-cap 3 --buyer-unit 1.0 \
  --out /tmp/scorelab-all-ten.json

# A registry-v9 single-leg example. This executes score_tuning's candidate.
python -m scripts.dev.score_lab synthetic \
  --registry docs/development/evidence/battery-score-tuning/registry-v9.json \
  --candidate A --out /tmp/scorelab-v9-a.json

# Old in-force family, on analytic toys only. No historical rescore.
python -m scripts.dev.score_lab synthetic \
  --registry docs/development/evidence/battery-score-tuning/registry-v5.json \
  --candidate 'G-FEAS/A-Q>@0.05' --out /tmp/scorelab-old.json

# Prospective VALUE-METRIC-V2 rev 2. Every number below is an ASSUMPTION
# for sensitivity, not an owner-selected value. The gate is explicit.
python -m scripts.dev.score_lab synthetic \
  --v2-definition docs/development/value-metric-v2/definition.v2.json \
  --kappa 0.1 --cap 3 --unit 1.0 \
  --value-workflow v2-shortlist --verification-costs 0.1 \
  --gate-json '{"measure":"feasibility","cutoff":0.05,"comparison":"exceeds"}' \
  --out /tmp/scorelab-v2.json
```

The V2 definition path is supplied by PR #1253. Until that PR merges, pass a
read-only copy of its `definition.v2.json`; Scorelab does not change or copy
the definition. A missing definition, missing cost input or missing active
gate leaves V2 unscored. A custom trusted local score rule can be passed as
`--function path/to/rule.py:function_name`; it receives exactly
`(score_predictions, score_references, score_metadata)`, never the value
questions. That is local developer execution only, not a miner-facing plugin.
`--value-workflow v2-shortlist` matches the value calculation to the V2
shortlist and solve charge; `--verification-costs` selects explicit assumed
costs. The default one-pick buyer workflow is a separate stress test and
must not be read as a matched V2 score-to-value result.
The candidate-file rules run as **proxies** on synthetic data. The three
registry families use `score_tuning`'s exact scorer on public EV4 when the
corresponding registry id exists. Other candidate families remain unmeasured
there because EV4's compact replay does not contain the per-action margin
contract they require. The candidate file is trusted local developer code.

The printed verdict says whether the exploratory 95% τ interval is positive
on every tested profile, or which profiles fail/remain unresolved. The JSON
contains τ and its crossed member/question bootstrap interval, top-1 regret,
known-bad/adversarial top-half placement, always-abstain and cheap-baseline
ranks, and one row per knob profile. It is a diagnostic, not a pass criterion.

## Public EV4 replay, no new solves

The owner's explicitly public copy at `codex-queue/inputs/ev4-public-proof/`
is local and untracked. `prepare-ev4` checks the RES-08 public source digest,
all 100 member bundle digests and the EV4 public contract, then writes a local
compact cache. It uses EV4 development cases for scoring and EV4 verification
cases for decision value. Their historical use makes this **retrospective**.
The cache is never committed.

```sh
python -m scripts.dev.score_lab prepare-ev4 \
  --public-dir codex-queue/inputs/ev4-public-proof \
  --repository . --out /tmp/scorelab-ev4-public.json.gz
python -m scripts.dev.score_lab replay \
  --cache /tmp/scorelab-ev4-public.json.gz \
  --registry docs/development/evidence/battery-score-tuning/registry-v9.json \
  --candidate A --out /tmp/scorelab-ev4-a.json
```

`replay` also accepts any registry member set in the same
`carbon.dev.score-lab-panel.v1` cache shape. A future
`2026-10-12 public-dev-decisions` adapter may produce that shape when its
public files are fetched. The real EV4 public copy has no Q3 leg and no
full-output bilinear score bundle. A/Q-based rules and a bilinear score rank
are therefore **UNMEASURED** on that replay; the lab does not manufacture
them from value-side answers. EV4's CV-onset proxy is not battery v3's EV
buyer-job value.

## V2 bank check

`bank-check` accepts a V2 manifest, development-half JSONL records and the
exact `definition.v2.json` bytes. It refuses any confirmation-half record,
definition mismatch or inconsistent per-question class. It reports class
counts and the scored share before evaluating a development-only winnability
diagnostic: cheap-arm ceiling capture, a paired block-bootstrap net margin of
a reference development model over the cheap arm, always-abstain U = 0 and
the supplied TRAIN-size learnability evidence. The cheap-arm registration,
TRAIN separation, reference image and MMS linkage must be present.
For this prototype, the manifest must explicitly register
`objective_aggregation: worst_case`; other buyer objective aggregations refuse
until an adapter is written. It also requires declared neighbour tasks and
reports a missing neighbour stratum as insufficient evidence. These checks
follow #1253's amended BANK_SPEC; they do not inspect the sealed half.

For the winnability calculation pass `--cheap`, `--reference-model`,
`--learnability` JSON files, plus explicit `--cap`, `--kappa`, `--unit` and
`--ceiling-threshold`. These are lab assumptions. Without them the status is
`INSUFFICIENT_EVIDENCE`, never PASS. It cannot open or qualify the sealed
confirmation half. The owner/Validator chooses the actual V2 values and
bank acceptance after separate evidence.

## Reuse and measurement limits

- Registry candidates use `carbon.battery.value.score_tuning.load_registry`,
  `score_member` and `gate_verdict` unchanged.
- τ and crossed recipe/question uncertainty use `score_proof`'s existing
  methods; public EV4 decision values use `decision`'s original selection,
  reference assessment and outcome code.
- RES-07/08/09's public EV4 cohort and bundle manifest supply the real replay
  identity; V2's shortlist/cost/strict-bank concepts follow their committed
  research and PR #1253's prospective definition. Synthetic `a/r/p/q` rows
  are toy analogues, not battery measurements.
- A positive τ here is descriptive. The synthetic population is constructed;
  the public EV4 panel was previously inspected. Fresh sealed confirmation
  remains the only final gate under the owner's process.
