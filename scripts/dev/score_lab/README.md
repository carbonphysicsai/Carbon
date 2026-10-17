# Scorelab (OPT-15)

## Current model-versus-solver receiver (DEVELOPMENT)

`solver_benchmark.register` and `solver_benchmark.compare` accept one
digest-bound attempted roster, one common reference panel, and complete
per-model rows. The producer measures solver and model runs; the receiver runs
neither. It reports registered mean absolute error in output units, mandatory
gate failures, complete-query timing (preprocess, export, inference and
postprocess), per-query min/median/p95/max latency for model and solver
(nearest-rank p95), observed serial throughput, peak model memory, separately
reported build time and paired solver/model speedup. `P` and `Q` have separate
results. Missing references or infrastructure failures withhold affected
aggregates; an invalid model output or mandatory gate failure cannot disappear
by dropping a case. Cached reference lookup and cached predictions are refused
as timing sources. Only complete `P` results with passing mandatory gates
receive a descriptive Pareto label;
there is no adopted scalar, winner, physical qualification or LIVE result.

The registration also carries the **full versioned Challenge-owned physics
definition** as `physics_contract: {version, definition}`. The definition is
Challenge-specific data; this receiver does not impose a universal equation
schema or decide its scientific adequacy. Its canonical digest must match on
each resolved reference row and each model row. The result exposes only the
version and digest, which the prospective Score Pack binds along with the
registration digest. Reusing the same gate names with a changed governing
relation, condition, unit, applicability statement or acceptance rule therefore
refuses old evidence. Missing contract material refuses the registration;
missing reference evidence stays indeterminate, never a candidate gate fail.
The trusted Challenge/evaluation owner supplies and registers the definition
and pack; miner-supplied declarations do not establish physics authority.

This receiver is an internal ScoreLab interface, not a miner disclosure
projection. Its registration is a binding for supplied development evidence,
not proof that a solver result is physically adequate. The optional prospective
`carbon.scoring.solver_benchmark_v3` pack binds the same Challenge, gate IDs,
full physics-definition identity, output metric/unit, explicit accuracy ceiling
and performance objective. When
the ceiling is absent, it is unready and ranks nobody. ScoreLab and a validator
caller use the same `ScoreEngine.score_solver_benchmark_v3` method; A5/v1 score
bytes and meanings are unchanged. No physical threshold or production scalar
is adopted by this development code.

The physics-bound receiver uses registration/result schema **v2** for serial
batch-one queries, and a prospective registration **v3** for whole-batch
queries. V3 binds input and output shapes, batch size, and an explicit
engineering-reference kind. It charges the full measured time of each batch;
it never divides wall time by the sample count or calls a saved label lookup a
reference run. V3 permits `peak_memory_bytes: null` only when peak memory was
not measured, and reports the corresponding aggregate as null. A saved model
with no measured construction time likewise reports `build_seconds: null` in
v3; that value is never inferred from inference time. V2 retains its
numeric-memory and build-time requirements and exact historical meaning. Both registration
versions use the Score Pack/result schema **v3**. Earlier development benchmark v1 and pack v2 records
remain historical; this path refuses them rather than implying that they
carried the new physics binding.

The producer can call the pure receiver or run
`python -m scripts.dev.score_lab benchmark --input EVIDENCE.json --out RESULT.json`.
The default `--help` shows only `benchmark` and `legacy`; historical commands
are available through the explicit `legacy` route. The input contains
`registration`, `references`, `models` and optionally
`score_pack`; both files stay in producer custody. The command prints only the
model count. The older value/N1 and menu commands below remain historical
diagnostics and are not prerequisites for this path. The first tests use
synthetic complete references only; a real Challenge must supply its existing
registered job, TRAIN identity, output/gate contract and adequate measured
reference evidence. The v2 profile supports one output quantity and serial
batch size 1. The v3 profile supports a registered complete batch with one
output quantity and the same mean-absolute-error metric. Other output metrics
or units need another explicit registration version.

`bundle_benchmark.benchmark_saved_entry` binds an independently retained v5
public bundle entry and custody receipt to the trusted Challenge job, complete
benchmark registration, measured model rows, and common reference rows before
calling the same `ScoreEngine`. Custody alone yields `NOT_READY`; a complete
measurement with no registered accuracy ceiling yields `PACK_NOT_READY`. The
Challenge owner supplies the physics and the producer supplies actual measured
rows. This development reducer does not run a model, reference, or solver.
`bundle_benchmark.measurement_from_saved_inference` accepts a trusted Platform
v2 timed worker result for one registered complete-batch query. It checks the
retained fixture, recipe, state and prediction digests, output shape and timing
scope before mapping the worker's four timing phases to the measured-model row.
The caller still supplies Challenge-owned gate verdicts and independently
measured same-batch reference rows; a retained prediction or label is never a
timing measurement.

## OPT-16: V2 bank producer workflow

`bank-plan` consumes a registered V2 definition, a digest-bound committed draw
from the Challenge's P law, and a committed block-split seed. It does not draw
P, invent a reference policy, or run a solver. Its `--out` file contains the
full contexts, split, every action-by-condition requirement and the distinct
physical reference jobs: keep it on the **producer**, never publish or upload
the full plan. `--jobs-out` emits a separate producer-worker projection without
question IDs or development/confirmation assignment. It is physical work
input, not a custody authorization: the owner decides whether any confirmation
contexts may leave the producer. Never feed either output to a miner. A draw
supplies `physical_context` separately from buyer
requirements, so objective/limit-only neighbours reuse the same solve.
Reusing one physical case across blocks is refused, and reused records must
carry the same solve digest. The command prints
only question and job counts. Data Collection owns the Challenge drawer and
reference launcher; their outputs are registered inputs, not built here.
The registration declares `objective_sense`. This version supports
`minimize` and refuses `maximize` with `bank_objective_sense_unsupported`;
it cannot silently apply battery's minimization arithmetic to a maximizing
Challenge.

```sh
python -m scripts.dev.score_lab legacy bank-plan \
  --registration REGISTRATION.json --draws COMMITTED_DRAWS.json \
  --definition docs/development/value-metric-v2/definition.v2.json \
  --split-seed-file PRODUCER_SEED.txt --out PRODUCER_PLAN.json \
  --jobs-out PRODUCER_WORKER_JOBS.json
python -m scripts.dev.score_lab legacy bank-cost \
  --plan PRODUCER_PLAN.json --registration REGISTRATION.json \
  --draws COMMITTED_DRAWS.json --split-seed-file PRODUCER_SEED.txt \
  --definition docs/development/value-metric-v2/definition.v2.json \
  --policy REFERENCE_COST_POLICY.json \
  --coarse COARSE_MARGIN_RECORDS.json --jobs-out PRODUCER_REFINEMENT_JOBS.json
python -m scripts.dev.score_lab legacy bank-solved-check \
  --plan PRODUCER_PLAN.json --registration REGISTRATION.json \
  --draws COMMITTED_DRAWS.json --split-seed-file PRODUCER_SEED.txt \
  --records PRODUCER_SOLVED.jsonl \
  --definition docs/development/value-metric-v2/definition.v2.json
```

`bank-cost` without `--coarse` reports the total cost as
`UNKNOWN_UNTIL_COARSE` when refinement is required. With complete coarse
records, it uses the bank's actual in-window action-condition share and the
registered per-rung CPU/wall costs; `--jobs-out` is producer-only. The
registered status rule names its reference ID, positive-feasible margin,
coarse/fine rungs, bands and screening window. A coarse in-window case cannot
receive a decided label before the fine rung. A different refinement ladder
needs its own registered cost adapter; it is refused here rather than silently
priced as a single fine solve. `bank-solved-check`
and `bank-cost` first rebuild the plan from the registered producer inputs and
refuse a serialized plan with changed actions, requirements, jobs or split.
`bank-solved-check`
requires every question, action and condition, verifies their planned job IDs,
image and overlay lock, classifies by reference alone, enforces whole-block
halves and the alpha block minimum, and prints aggregate counts. Exhausted
reference failures remain reported as INCOMPLETE; they do not by themselves
invalidate a bank whose registered SCORED-share condition still holds. Its
development-half diagnostic reuses `bank-check`; owner thresholds remain
HUMAN_INPUT. Without those inputs the aggregate status is
`INSUFFICIENT_EVIDENCE`, even if `structural_ready` is true; supplied
development evidence (`--cheap`, `--reference-model`, `--learnability`,
`--cap`, `--kappa`, `--unit`, `--ceiling-threshold`) may yield a winnable or
not-winnable diagnostic. Neither
result qualifies the bank or authorizes
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
The optional `value_definition` lever compares `v2_shortlist` (the default)
with `legacy_one_pick` on those same scoring questions. It is a toy comparison
of buyer-loss definitions and never reinterprets historical evidence.

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
python -m scripts.dev.score_lab legacy physics \
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
python -m scripts.dev.score_lab legacy prepare-ev4 \
  --public-dir codex-queue/inputs/ev4-public-proof \
  --repository . --out /tmp/scorelab-ev4-public.json.gz
python -m scripts.dev.score_lab legacy physics \
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
python -m scripts.dev.score_lab legacy synthetic \
  --candidates codex-queue/inputs/score-lab-candidates/candidates.py \
  --value-workflow v2-shortlist --buyer-cap 3 --buyer-unit 1.0 \
  --out /tmp/scorelab-all-ten.json

# A registry-v9 single-leg example. This executes score_tuning's candidate.
python -m scripts.dev.score_lab legacy synthetic \
  --registry docs/development/evidence/battery-score-tuning/registry-v9.json \
  --candidate A --out /tmp/scorelab-v9-a.json

# Old in-force family, on analytic toys only. No historical rescore.
python -m scripts.dev.score_lab legacy synthetic \
  --registry docs/development/evidence/battery-score-tuning/registry-v5.json \
  --candidate 'G-FEAS/A-Q>@0.05' --out /tmp/scorelab-old.json

# Prospective VALUE-METRIC-V2 rev 2. Every number below is an ASSUMPTION
# for sensitivity, not an owner-selected value. The gate is explicit.
python -m scripts.dev.score_lab legacy synthetic \
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

OPT-15c can compose four optional toy-only score components over a candidate:
`crps_weight` (Gaussian distribution error), `gradient_weight` (finite-difference
sign on registered score-side probes), `cvar_tail_fraction` (worst question
scores) and `cheap_margin_weight` (candidate score above the bilinear arm on
the same scoring questions). `--components` accepts a JSON object of these
explicit settings; the example file contains **ASSUMPTION** values only.
The raw file digest is written to the report. The fixed composition order is
CRPS, gradient, CVaR, then cheap margin. Missing uncertainty or cheap-arm
coverage returns an unscored diagnostic. Public EV4 replay refuses these toy
wrappers; it continues to use exact registered scorers unchanged.
CVaR retains the strictest gate and FLOOR tier from the whole-panel rule and
every question, so a clean tail cannot restore primary eligibility. A missing
whole-panel or question score refuses the decomposition.

`campaign-plan` creates deterministic Latin-hypercube shards of the existing
analytic physics configuration. Every axis is an explicit toy assumption;
choices, linear ranges and log ranges are supported. The command writes
configurations and their digests, and performs no evaluation or holdout read.
The example axes exercise part of the campaign lever space; they do not stand
in for the remaining §2 settings or a completed campaign verdict.
`campaign-axes-broad-example.json` exercises 25 existing toy grammar axes,
including buyer loss, verification cost, neighbourhood, coverage, member
traits and physics settings. It still omits the §2 dimensions and other task
families that the present one-dimensional toy does not implement.

`campaign-stress` measures five named, explicitly limited scenarios using the
same toy panel evaluator. The example names are analogies to a grid, boundary,
large shift, path gamer and tiny bank; they are not Challenge simulations.
The implementation ledger in
`Business/research/score-lab-campaign-01/LEVER_COVERAGE.md` names every §2
group still missing from the toy grammar; no partial sample is a campaign
verdict.

```sh
python -m scripts.dev.score_lab legacy campaign-stress \
  --base-config scripts/dev/score_lab/physics-example.json \
  --scenarios scripts/dev/score_lab/campaign-stress-example.json \
  --candidates codex-queue/inputs/score-lab-candidates/candidates.py \
  --out /tmp/scorelab-stress-toy.json
```

`campaign-run` evaluates one such shard on the analytic toy. Its output binds
each measured row to the plan and candidate digests and records the sampled
axis values. Rows are diagnostics, not a final score-rule ranking.

```sh
python -m scripts.dev.score_lab legacy campaign-run \
  --plan /tmp/scorelab-campaign-plan.json \
  --candidates codex-queue/inputs/score-lab-candidates/candidates.py \
  --candidate N1-DECISION-RELEVANCE-ERROR \
  --out /tmp/scorelab-campaign-results.json
```

`campaign-atlas` requires every index exactly once across one or more
digest-matched result shards. It reports target, shifted, extrapolated and
neighbourhood-blend summaries per candidate and physics switch, plus sampled
axis median splits or category medians for the OFF switch as exploratory
associations. Its worst
tenth is a descriptive sample tail; Sobol indices and final rule selection
remain unset in this LHS atlas because those profiles do not supply a
pick-and-freeze design.
The `campaign-run --plan` and `campaign-atlas --result` readers accept plain
JSON or deterministic `.json.gz` evidence files.

```sh
python -m scripts.dev.score_lab legacy campaign-atlas \
  --result /tmp/scorelab-campaign-results.json \
  --out /tmp/scorelab-atlas.json
```

For variance-based sensitivity, use the separate `campaign-sobol-*` path.
It makes independent deterministic LHS A/B matrices and one A/B hybrid per
axis, then requires all matched rows before computing raw Saltelli first-order
and Jansen total-order estimators. An unresolved toy tau makes the estimate
`INSUFFICIENT_EVIDENCE`; small-sample estimates may be negative or above one
and are never clipped. A complete run costs `(2 + axes) * count` toy profiles.

```sh
python -m scripts.dev.score_lab legacy campaign-sobol-plan \
  --base-config scripts/dev/score_lab/physics-error-example.json \
  --axes scripts/dev/score_lab/campaign-axes-error-example.json \
  --count 4 --seed 97 --switch-index 0 --scope neighbourhood_blend \
  --out /tmp/scorelab-sobol-plan.json
python -m scripts.dev.score_lab legacy campaign-sobol-run \
  --plan /tmp/scorelab-sobol-plan.json \
  --candidates codex-queue/inputs/score-lab-candidates/candidates.py \
  --candidate N1-DECISION-RELEVANCE-ERROR \
  --out /tmp/scorelab-sobol-results.json
python -m scripts.dev.score_lab legacy campaign-sobol-atlas \
  --result /tmp/scorelab-sobol-results.json \
  --out /tmp/scorelab-sobol-atlas.json
```

`campaign-goodhart` searches the analytic toy member-trait grammar twice:
once for a candidate's score on scoring questions only, and separately for
true buyer value as an offline oracle. Both use fixed random starts plus
coordinate hill climbing. The reported value gap uses an approximate oracle;
a signed negative gap means it missed a better point. Every search range and
effort setting is an explicit toy assumption, not a Challenge rule.
`goodhart-robust-search-example.json` changes only the buyer-value scope to
the worst loss across target, neighbour and extrapolated toy tasks at each
question index. Per-task minima do not establish its exact min-max oracle, so
this scope is supported by the sampled Goodhart comparison only.

`campaign-feedback` runs a separate toy score-only search. Its callback
returns only the rounded score of the selected synthetic scoring-question
grain; buyer value is computed only after each search. `aggregate` uses all
synthetic scoring questions and `prefix:N` uses the first N. These grains,
rounding precisions and probe allowances are diagnostic assumptions, not a
claim about the actual Launchpad disclosure contract. A gated or unscored
probe leaves that candidate `INSUFFICIENT_EVIDENCE`.
Goodhart and feedback receipts include `component_spec` and its canonical
`component_spec_sha256` (both explicit None when absent), plus `recipe_sha256`
binding configuration, search, candidate-file digest, selected candidate IDs,
components and feedback disclosure. These fields are present on measured,
unscored and aggregate receipts. Earlier saved no-component artifacts remain
historical bytes with their component absence annotated in the readout.

`physics-error-example.json` is a separate explicit-default toy config for
the optional error-structure knobs: heteroscedasticity and its region,
cross-design correlation, rare-tail rate and size, and reported uncertainty
scale. `campaign-axes-error-example.json` varies those knobs. The earlier
25-axis input is retained unchanged so its saved exploratory results remain
reproducible. These settings alter synthetic model errors, not analytic truth.

`physics-shape-example.json` and `campaign-axes-shape-example.json` separately
vary analytic truth: explicit 1/3/10 wells, single/weighted/robust objective
forms, roughness and interior/boundary placement. The exact reference is the
best offered action; these examples do not establish a multidimensional
continuous optimum or a real Challenge objective.

`physics-vector-example.json` and `campaign-axes-vector-example.json` add
two-to-eight dimensional offered sets from bounded deterministic Halton
coordinates, with a fixed fallback and configurable coupling of the two hard
margins. A vector `small-grid` is a sampled finite lattice; vector
`continuous` means sampled continuous-coordinate offers. Both use an exact
reference on the offered set, not a global continuous optimum.

```sh
python -m scripts.dev.score_lab legacy campaign-feedback \
  --config scripts/dev/score_lab/physics-example.json \
  --search scripts/dev/score_lab/feedback-search-example.json \
  --disclosure scripts/dev/score_lab/feedback-disclosure-example.json \
  --candidates codex-queue/inputs/score-lab-candidates/candidates.py \
  --out /tmp/scorelab-feedback-toy.json
```

```sh
python -m scripts.dev.score_lab legacy campaign-goodhart \
  --config scripts/dev/score_lab/physics-example.json \
  --search scripts/dev/score_lab/goodhart-search-example.json \
  --candidates codex-queue/inputs/score-lab-candidates/candidates.py \
  --candidate N1-DECISION-RELEVANCE-ERROR \
  --out /tmp/scorelab-goodhart-toy.json
```

```sh
python -m scripts.dev.score_lab legacy campaign-plan \
  --base-config scripts/dev/score_lab/physics-example.json \
  --axes scripts/dev/score_lab/campaign-axes-example.json \
  --count 8 --seed 17 --shard 0 --shards 2 \
  --out /tmp/scorelab-toy-lhs-shard0.json
```

```sh
python -m scripts.dev.score_lab legacy synthetic \
  --candidates codex-queue/inputs/score-lab-candidates/candidates.py \
  --components scripts/dev/score_lab/components-example.json \
  --quick --out /tmp/scorelab-components-toy.json
```

The printed verdict says whether the exploratory 95% τ interval is positive
on every tested profile, or which profiles fail/remain unresolved. The JSON
contains τ and its crossed member/question bootstrap interval, top-1 regret,
known-bad/adversarial top-half placement, always-abstain and cheap-baseline
ranks, and one row per knob profile. It is a diagnostic, not a pass criterion.

## Toy robustness score levers (OPT-20)

`campaign-robustness` compares one baseline with robustness as a weighted
score term, a sweep of hard gate limits, and a score-side uncertainty-honesty
term. It freezes one finite proposal slate before evaluating any arm, so each
arm gets exactly the same candidate score-call budget. The value side is
measured afterward on target, shifted, extrapolated and blended nearby tasks.
The finite-slate value oracle is approximate; differing wrapper CPU costs
are not equalized. `NO_OBSERVED_DIFFERENCE_ON_SLATE` reports an exact tie in
this toy slate, with no statistical-power claim.

```sh
python -m scripts.dev.score_lab legacy campaign-robustness \
  --config scripts/dev/score_lab/physics-shape-example.json \
  --search scripts/dev/score_lab/robustness-search-example.json \
  --levers scripts/dev/score_lab/robustness-levers-example.json \
  --candidates codex-queue/inputs/score-lab-candidates/candidates.py \
  --uncertainty-abstention-threshold 0.08 \
  --out /tmp/scorelab-robustness-toy.json.gz
```

Every numerical input in that command is an `ASSUMPTION` for the analytic
toy. The candidate file is trusted local Validator input and is not copied
into the repo. The command reads no real reference, protected bank, or
independent holdout, and adopts no score rule or gate threshold.

## Public EV4 replay, no new solves

The owner's explicitly public copy at `codex-queue/inputs/ev4-public-proof/`
is local and untracked. `prepare-ev4` checks the RES-08 public source digest,
all 100 member bundle digests and the EV4 public contract, then writes a local
compact cache. It uses EV4 development cases for scoring and EV4 verification
cases for decision value. Their historical use makes this **retrospective**.
The cache is never committed.

```sh
python -m scripts.dev.score_lab legacy prepare-ev4 \
  --public-dir codex-queue/inputs/ev4-public-proof \
  --repository . --out /tmp/scorelab-ev4-public.json.gz
python -m scripts.dev.score_lab legacy replay \
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

## Synthetic value-reference availability (experiment plan section E)

Only the `synthetic` command accepts `--value-reference-failures <JSON>`.
The JSON must provide every field below; these are toy ASSUMPTION inputs,
not a registered production failure policy or adopted rate:

```json
{"schema":"carbon.dev.score-lab-value-reference-failures.v1","label":"ASSUMPTION: illustrative toy outages only","fraction":0.05,"seed":42,"policy":"EXCLUDE_COMMON"}
```

Use the option with the existing `synthetic --function ...` or `--candidates ...`
workflow. `fraction` is within the experiment plan's 0-5% range. A keyed hash
of the seed and value question ID selects `floor(fraction * offered_questions)`
whole-question outages before scoring, independently of member predictions,
losses and order. Small panels can realize zero outages; both requested and
realized fractions are reported. Score-side reference failures are not modeled.

`REQUIRE_COMPLETE` leaves the entire value measurement unscored on any unresolved
question and invokes no scorer. `EXCLUDE_COMMON` uses the same common resolved
mask across every member, including controls, via the unchanged `core.analyze`.
Its estimand is conditional on that mask, not recovered population value.
An empty mask also leaves the measurement unscored without invoking the scorer.
Injected, preexisting, overlapping and total unavailable counts are distinct;
missing outcomes are neither zero losses nor candidate scientific failures.

`value_reference_measurement` in each output row binds the input panel, spec
and common-mask digests and reports offered/available/scored counts. It is not
passed to score callbacks. Scoring references, predictions, metadata, candidate
gates and the original panel remain unchanged. With no flag the existing CLI
path is unchanged. Public replay has no such option, and the library refuses
`PUBLIC_DEVELOPMENT` panels. No real/hidden reference is opened or reinterpreted.

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
