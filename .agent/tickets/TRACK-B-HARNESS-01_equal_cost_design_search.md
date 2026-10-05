# TRACK-B-HARNESS-01 — challenge-neutral equal-cost design-search harness

**Status:**
- PR 1, the harness, merged as #582.
- PR 2 is the AI cooling adapter with its counted-CFD replay.
- The motor adapter follows in its own PR. It waits on the owner's decision about the counted motor import: the registered importer rejects successful runs whose solver logs are empty.

**Authority:**
- OWNER-GRAPHITE-TEST-WAVE-01 §5 (the equal-budget rule) and §1 (test suite v1).
- The Test Lead's assignment of 2026-10-04 to the Data Collection session.

This is DEVELOPMENT work with no paid compute, no LIVE path, and no change to any scoring rule, gate or tolerance.

**Primary map ref:** `carbon/design_search` (Track B of Challenge Admission).

## Outcome

Add a challenge-neutral harness that answers one question: at the same decision budget, measured in compute cost, which construction and search arm reaches the best design decision? The arms include running the solver itself.

The harness reports three labelled views:
- **Equal cost.** This is the deciding view.
- **Equal query count.** Diagnostic only.
- **Amortised break-even.** The number of decisions after which an arm's one-time cost undercuts the solver arm's per-decision cost. It is computed, never assumed.

It also exposes a score-to-value hook. This relates each panel member's challenge score to the decision quality the harness measures:
- Kendall τ-b and Spearman ρ;
- a seed-noise band;
- SCORE_VALUE_DIVERGENCE conditions.

Motor and AI cooling are the first two adapters.

## Constraints found at ticket start (main 17babfc0)

- **Frozen files stay untouched.** The motor V1 and cooling V1 study freezes pin `carbon/design_search/methods.py`, `experiment.py`, `aggregate_methods.py`, `campaign.py`, `reference_comparison.py`, every adapter's code paths, and `uv.lock`.
  - The harness lives in new modules only and adds no dependency.
  - Editing a pinned file would invalidate the committed study freezes. It would also invalidate the counted motor campaign, which is running now.
- **`experiment.pilot` is reused only in parts.** It counts model queries only. It has no solver arm, cost, cache or shared verification. The harness calls its neutral pieces (`methods.run`, `reference_comparison`) and does not change `pilot`.
- **No approved USD rate exists in the repository** for the operator host or for `runpod-cpu5c-16vcpu`. USD views therefore return `NO_APPROVED_RATE` until a rate decision supplies one. Core-second views are computed and labelled with their hardware route.
- **No Spearman ρ exists in `carbon/`.** Kendall τ-b exists in `carbon/battery/value/decision.py`. The neutral package does not import battery code. It reimplements both statistics and tests them against the battery function.

## Working contract

### Arms

An arm is a (predictor, search method) pair over the challenge's registered finite design set and conditions.

**Predictors:**

| Predictor | Prediction source | Charged one-time cost | Charged per decision |
| --- | --- | --- | --- |
| `solver` | the reference itself, through a case-keyed cache | none | each cache miss at its record's allocated core-seconds; a hit costs its measured lookup |
| `analytical` | the challenge's registered analytical model | none | measured inference |
| `interpolation` | nearest-neighbour over the public TRAIN pool | TRAIN data generation (recorded solve cost) | measured inference |
| `learned:<id>` | a registered learned model (KRR now; Graphite constructions later) | TRAIN data generation, fitting and selection | measured inference; the fallback, if used |

**Search methods:**
- `fixed_grid`;
- registered `screen_then_confirm` and `coarse_to_fine` (`methods.run`);
- `random_subset`, a seeded uniform sample of designs that are then fully evaluated. Its seed is declared before the run, and several seeds give the noise band.

A Latin-hypercube sample over a finite 2³ grid degenerates to random selection, so it is not registered separately.

### Cost ledger (`carbon/design_search/cost.py`)

Every charge is one entry:
- arm;
- category: `training_data_generation`, `fitting`, `inference`, `in_search_solve`, `cache_lookup` or `fallback`;
- hardware route;
- core-seconds;
- basis: `MEASURED_CPU` or `ALLOCATED_CPU_X_WALL`.

The rules:
- **One unit per view.** A view prices an arm only in one unit: USD at an approved rate for every route it touches, or core-seconds when all its entries share one route.
- **Mixed hardware.** An arm whose entries span routes with no approved rates is `UNPRICED_MIXED_HARDWARE`. The exception is a declared, evidence-cited paired-timing conversion (for example motor-timing-2026-10-04), which is labelled `CONVERTED_BY_PAIRED_TIMING`.
- **Verification is a separate line.** It is charged to no arm and is identical for all arms.

### Two questions, two budget rules

The Test Lead's delegated working decision under OWNER-GRAPHITE-TEST-WAVE-01 §5 (2026-10-04) refines §5 into two questions. One cost view never decides both.

**Q1: score-to-value alignment.** Does the challenge score rank models by decision quality?
- Models are compared at an equal search budget: the same method and the same query and verification allowance.
- One-time training and data costs are excluded, so they don't swamp model quality.
- Outputs: τ-b and ρ with the seed-noise band, SCORE_VALUE_DIVERGENCE, top-k and regret. This is the alignment verdict.

**Q2: economic value against solvers.** Is a fast model worth it?
- Every arm, including the solver arm, gets an equal total cost per decision, B. One-time costs are charged in full.
- The view is reported over the registered decision-count ladder N ∈ {1, 10, 100, 1000}. At ladder point N, an arm's one-time cost is amortised as one-time / N, and its search may spend B − one-time / N.
- During search, the arm stops when its next planned charge would exceed what remains. It then commits what it has: a proposal or `ABSTAIN`.
- An arm whose amortised one-time cost alone exceeds B at some N is `OVER_BUDGET_BEFORE_SEARCH` at that N. This is a typed outcome; the arm is never dropped.
- The break-even N is computed, never assumed.
- Each challenge's ladder of B values is proposed in the adapters PR as k × the median measured solve cost, k ∈ {6, 12, 24, 48}. It also includes the anchor where the solver arm can evaluate the full finite set, where search adds nothing. The Test Lead confirms the ladder.
- Stopping uses each point's pre-declared planning charge, because a live run cannot know a solve's cost in advance. The ledger records the actual measured or allocated cost.

Representative and boundary-stress groups stay separate in every view.

### Custody

The order is:
1. Every arm writes an immutable, digest-addressed commitment (O_EXCL) before verification exists.
2. Verification starts only after all commitments are present.

The solver arm's in-search reference access is part of its own search. It goes only through its cache, which no model arm can reach.

### Metrics, per arm and per condition group

Representative and boundary-stress groups are reported separately and never combined.
- **Feasible:** the proposal's classification.
- **False-feasible:** predicted feasible, but the reference shows it infeasible.
- **Missed-feasible:** reference-feasible designs the arm predicted infeasible.
- **Regret** against the finite comparator, from `reference_comparison`.
- **Abstention** and **unresolved** counts.
- **Cost to a correct decision:** the arm's cost when its regret is defined and zero; `null` otherwise.

### Score-to-value (`carbon/design_search/score_value.py`)

- **Inputs:** panel members, each with a challenge score, a decision-quality value from this harness (lower is better, for example regret or a loss), and per-seed replicates where they exist.
- **Outputs:**
  - Kendall τ-b and Spearman ρ of score against −value;
  - the noise band: τ over every one-seed-per-recipe panel, and the per-member value spread;
  - conditions, following `carbon.battery.value.divergence`: SCORE_VALUE_DIVERGENCE fires for X when some eligible Y has value(Y) + band < value(X) and score(X) ≥ score(Y), and GATE_ANOMALY fires for ineligible members.

## Delivery

1. **PR 1, the harness:**
   - `cost.py`, `track_b.py` and `score_value.py`;
   - a synthetic toy adapter;
   - tests: equal-cost stopping, the cache, custody order, the views, break-even, group separation, and τ/ρ against the battery function.
2. **PR 2, the adapters:**
   - motor and cooling Track B adapters, with compact replay tables (per-case quantities, wall time, CPU limit and source-record SHA-256) derived from their counted records;
   - no-cost replay tests against those tables.

Raw records stay outside Git.

## Maturity ceiling

SPECIFIED, IMPLEMENTED and fixture/replay-TESTED. This is not scientific, security or production qualification. No USD figure is produced without an approved rate.

## Human input required

- **The USD rate** for each hardware route used in a deciding view. Until then, core-seconds by route.
- **Each challenge's registered decision budget B and its ladder.** The adapters PR proposes values derived from measured solve costs, and the Test Lead confirms them.

## Findings during PR 1

- On a two-level grid such as the motor and cooling 2×2×2 design sets, the registered `coarse_to_fine` with its smallest stride (2) samples only the first design. If that design is infeasible, the method abstains. This is method behaviour, not a harness defect. The adapters PR reports it rather than registering a new stride.
- The solver arm's case-keyed cache serves repeat queries. A repeat is charged its lookup and still counts as an evaluation. Model arms may not repeat a point, as in the motor and cooling oracles.
- `decision_value` orders outcomes as a declared working policy: a defined regret, then abstention, then an unsafe (reference-infeasible) selection. Unresolved evidence ranks nothing. The Test Lead may supersede this order.

## PR 1 validation (WSL native)

- `pytest tests/cpu/test_design_search_track_b.py tests/cpu/test_design_search_pilot.py tests/cpu/test_admission_divergence.py tests/cpu/test_motor_decision_study.py`: 71 passed.
- `scripts/check_quality.py --base origin/main`: passed.
- No file pinned by any study freeze changed. Only new modules were added.

## PR 2: AI cooling adapter (replay of the counted CFD)

- `carbon/cold_plate/track_b.py` (new) wraps the registered cooling study.
  - Predictors: the analytical model, the KRR reconstruction, a nearest-neighbour TRAIN baseline, and the solver through the replay.
  - The registered B ladder is proposed as k × the median measured solve, k ∈ {6, 12, 24, 48}. k = 48 is the full-set anchor.
- `docs/development/evidence/track-b-replay/ai-cooling-counted-v1.json` is a compact table derived from the 48 counted records, which stay outside Git. It carries the source records' SHA-256.
- Replay tests reproduce the counted comparator from `completion.json`: complete finite set, 2 feasible and 6 infeasible designs, best d03, with worst hydraulic power matching.

Open decisions for the Test Lead:
1. **Mixed-hardware one-time cost.** The TRAIN pools ran on the operator host and on RunPod CPU pods whose flavor was not recorded. A host-only unit therefore reports the learned and interpolation arms as UNPRICED_MIXED_HARDWARE in Q2, and their break-even is NOT_COMPUTABLE. A rate for both routes, or a cited paired-timing conversion, resolves this.
2. **The planning charge for stopping.** The solver arm stops by the median solve cost. At B = 12 × median, its actual cost on the replay ran about 21% over B, and that run is flagged `actual_cost_exceeds_budget`. Should the planning charge be the median, the p95 or the timeout?
