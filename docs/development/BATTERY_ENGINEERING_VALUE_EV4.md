# EV4 and Problem C: pre-registration

**Status.** DRAFT. The lead sets FROZEN when it freezes the experiment root
with the contract below, before any EV4 reference solve or reconstruction.
Nothing here has run. Anything changed after the first solve is reported as a
change, never silently applied.

- **Contract:** `carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json`,
  digest `sha256:fedd753c0e7aa69d2fd4d6efbf3d877ac8eeb211859d9f32d76a61f38bbe38d1`
  (pinned by `test_ev4_contract_digest_is_the_preregistered_one`).
- **Code:** `carbon/battery/value/` (`experiment.py`, `hypotheses.py`,
  `optimizer.py`, `panel.py`), the pod phases in
  `scripts/dev/exam_design/value_phases.py` and the plans in
  `docs/development/evidence/ev4-2026-10-01/plans/`.

**Authority.** On 2026-10-01 the owner wrote: "I approve runpod use for EV4
and I approve your choice on the optimizer. Whatever is the most valuable and
tangible use case to test and show." The owner chose budget option C: a hard
cap of USD 15 in total for EV4 and the optimizer, on RunPod A40 pods at no
more than USD 0.49 per hour, with up to 3 pods in parallel. The engineering
choices below were delegated to the lead session.

**Scope.** Public synthetic DEVELOPMENT evidence only:
- no chain action, reward or weight change;
- no change to the testnet rule (`carbon.battery.exam.v1` stays deciding);
- no qualification claim;
- "best" means best in the tested set, never a global optimum.

## 1. The question

EV2 found that the decision-aware rule `dar-p0-r100-a0` catches the
boundary-optimist control and the deciding rule does not (H2). It could not
say which rule ranks real models better: with 14 eligible members, Kendall τ
on verification was 0.202 for the proposed rule and 0.298 for the deciding
rule, and the standard error at that size is about 0.2
(`BATTERY_DECISION_AWARE_PROPOSAL.md`, "EV4").

EV4 asks the same question with enough members to answer it: **on a panel
built to separate decision quality, does the proposed rule rank real models by
reference-verified decision quality better or worse than the deciding rule?**

Problem C asks the question an engineer would ask: **when each model picks
one two-step fast-charge protocol for the whole 5-40 °C range, is that
protocol actually safe, and how fast is it?**

## 2. What changes from EV2, and what does not

**Unchanged** (the contract copies EV2's sections exactly; a test holds it):
- the objective: time from charge start to the 4.19 V crossing, minimized;
- the constraints: reach CV within the window, plating margin ≥ 0 V, peak
  temperature ≤ 45 °C;
- the uncertainty bands (3.15 s, 0.00197 V, 0.157 °C);
- the mistake costs (false acceptance 10, missed opportunity 1, regret 1 per
  120 s) and the minimum useful improvement (120 s);
- the baseline (c1 0.75 C, c2 0.6 C) and the tie rule (lower c1, then c2);
- the candidate grid: c1 0.5-2.0 in steps of 0.25 (7) × c2 0.2-1.0 in steps of
  0.2 (5) = 35;
- the reference (PyBaMM 26.8.0.0, DFN, OKane2022, 30 cycles), the models
  section, the scoring set (refs-b, 1588 cases), every weight profile and
  decision-aware profile, their components and aggregation, and the data
  scope;
- the rule-selection procedure: choose on development by Kendall τ, ties to
  the control, then report its verification τ.

**Changed:**

| | EV2 | EV4 |
|---|---|---|
| Conditions | 8 development + 8 verification | **12 + 12, fresh** (§4) |
| Reference solves | 560 | **840** (24 conditions × 35 candidates) |
| Panel | 15 members | **100 members** (§3) |
| Primary hypothesis | τ of the development-chosen rule, no significance claim | **paired Δτ between the proposed and deciding rules, with a bootstrap interval** (§5) |
| Compute | local CPU, USD 0 | **RunPod A40 pods, shared USD 15 cap** (§8) |

## 3. The panel: 100 members

All 15 EV2 members keep their ids. 85 are added: **70 distinct recipes** and
**15 second seeds** of added recipes. Every recipe compiles through Carbon's
construction contract (`test_every_ev4_recipe_compiles`); the panel holds 80
distinct recipes in all. Member ids are `<recipe>-s<seed>`, and each added
recipe's label names its settings.

| Group | Recipes | Members | What varies |
|---|---|---|---|
| EV2's panel | 10 | 15 | unchanged |
| MLP grid | 30 | 30 + 9 second seeds | steps {500, 1500, 3000, 6000} × width {64, 128, 256, 512} × depth {2, 3}, less the two EV2 already holds (6000/256/3 and 6000/512/2) |
| Less training data | 9 | 9 + 1 | train_fraction 0.25 or 0.5 on chosen MLPs |
| Weight decay | 4 | 4 + 1 | 1e-5, 1e-4, 1e-3 |
| Feature path | 4 | 4 | Arrhenius features, PCA trajectory heads (8, 16) |
| Important-region weight | 4 | 4 + 1 | 0.03, 0.1, 0.3, 3.0 |
| Ensembles | 3 | 3 | 2, 3 or 4 members sharing the step budget |
| DeepONet | 11 | 11 + 3 | steps {500-6000} × width {128, 256, 512} × depth {2, 3} |
| kNN | 5 | 5 | neighbours {1, 3, 10, 25, 40} |
| **Total** | **80** | **100** | |

By family: 77 MLP members, 16 DeepONet and 7 kNN. The report shows members,
eligible members and the verification-loss range per family. Seeds repeat a
recipe; they are never separate families.

**Why this panel.** Training budget, width, depth, data and regularization are
varied on purpose, so that decision losses spread instead of tying. The
proposal estimated a τ standard error of about 0.07 at n = 100.

## 4. Conditions

Each scenario holds one condition, as in EV2. Fixed before any EV4 solve; no
condition repeats an EV1 or EV2 condition (`test_ev4_conditions_are_fresh_and_as_registered`).

- **Development:** t_amb {5, 14, 24, 34} °C × soc0 {0.12, 0.33, 0.48}: 12.
- **Verification:** t_amb {9, 19, 29, 38} °C × soc0 {0.06, 0.22, 0.40}: 12.

A verification condition with no feasible protocol is reported as such, never
replaced.

## 5. Hypotheses, fixed before any solve

- **H1 (primary, paired).** Δτ = τ(`dar-p0-r100-a0`) − τ(`control-exam-v1`).
  - Each τ is Kendall tau-b between the rule's scores of the **eligible
    reconstructed members** and their decision loss (lower is better), mean
    over the **12 verification conditions**.
  - **Interval:** 95 % percentile bootstrap. Each replicate draws members and
    conditions with replacement, jointly and independently. A member's loss in
    a replicate is its mean over the drawn conditions where its loss is
    defined. B = 10000 replicates, RNG `numpy.random.default_rng` seeded
    20261001.
  - **Undefined values are reported, never imputed.** A member with no defined
    loss in a replicate is left out of that replicate for both rules. A
    replicate where either τ is undefined is skipped and counted. A member
    whose score under either rule is not numeric is excluded and named.
  - **Decision:** an interval that excludes 0 decides H1 in its sign's
    direction (`PROPOSED_RANKS_BETTER` or `DECIDING_RANKS_BETTER`). Otherwise
    H1 is **UNRESOLVED**, which never means "no difference".
- **H2.** As EV2: `dar-p0-r100-a0` scores the labelled boundary-optimist
  control below every eligible reconstructed member. Reported for every rule.
- **H3 (real-model blind spot).** The number of eligible reconstructed members
  that select a protocol the reference verifies INFEASIBLE on any verification
  condition (a false acceptance), and each such member's competition rank
  (1 = best) under both rules.
- **Continuity.** EV2's rule-selection procedure is kept: the
  development-chosen rule and its verification τ are reported.

The code is `carbon/battery/value/hypotheses.py`; `Experiment.evaluate` adds
its output to `results.json` and the report.

## 6. Problem C: one protocol for 5-40 °C

**Use case.** "One two-step fast-charge protocol that is safe across 5-40 °C
ambient": EV3's problem C, the most tangible customer demonstration, needing
no new build. The optimizer is `carbon/battery/value/optimizer.py`; its modes
are those of `DESIGN_OPTIMIZER_SCOPE.md` §1, and the decisions below fill that
document's §4 gaps for this study only.

**Grids.**
- **Designs:** c1 0.50-2.00 C in steps of 0.05 (31) × c2 0.200-1.000 C in
  steps of 0.025 (33) = 1023.
- **Model conditions** (where a model searches): t_amb {5, 10, 15, 20, 25, 30,
  35, 40} °C × soc0 {0.05, 0.20, 0.35, 0.50} = 32.
- **Verification conditions** (reference truth): t_amb = linspace(5, 40, 18)
  × soc0 = linspace(0.05, 0.50, 5) = 90.

**Mode D (robust design).** For each selected member, from its own
predictions only: the design predicted feasible at **all 32** model
conditions (all three constraints, point predictions, no band) with the lowest
worst-case predicted time to CV. Ties go to lower c1, then lower c2. If no
design qualifies, the member ABSTAINS.

**Verification of Mode D.** Every committed design, and the contract baseline,
is solved at all 90 verification conditions. Reported per design:
- verified feasible at every point (with the contract's bands);
- the number of violating points per constraint;
- worst-case and mean verified time to CV;
- the speed-up against the baseline verified on the same 90 points (seconds
  saved and ratio, worst case and mean).

**Mode X (adversarial).** For each selected member, over all 1023 designs ×
32 model conditions: the points the member predicts feasible, ranked by the
smallest constraint margin, each margin divided by that constraint's
uncertainty band. The top **K = 50** distinct points are verified. A verified
constraint FAIL at such a point is a **finding** with the divergence
detector's schema (`carbon.admission-condition.v1`):
`SCORE_VALUE_DIVERGENCE` if the member is in the top half of the eligible
members under the deciding rule (2 × rank ≤ eligible), otherwise
`OTHER_SIGNAL`. UNRESOLVED and unavailable references are reported, never
counted as violations.

**Members, chosen by rule.** Applied to EV4's evaluated results, after the
evaluation and **before any verification solve**; the selection is written
once and never redone (`optimize select`):
1. the best eligible member under the deciding rule;
2. the best under the proposed rule;
3. the median eligible member under the deciding rule (position
   ⌊(n − 1)/2⌋ in its descending order);
4. the best kNN member under the deciding rule;
5. the eligible member with the lowest EV4 verification decision loss.

Ties within a criterion go to the lower member id. When a role's first choice
is already selected, it takes the next member in its own order (for the
median, the next lower-ranked member). The baseline protocol is always in the
verification set.

**Prediction source.** Grid predictions come from the same reconstructed
models as EV4's panel, on the pod, before EV4 is evaluated; selection only
chooses which members' predictions are searched.

## 7. What it cannot show

- **A single safe protocol may not exist.** EV2's references found no feasible
  protocol in its grid at 7 °C (soc0 0.08 and 0.28) or at 40 °C with soc0
  0.18: fast protocols plate or overheat, and slow ones do not reach CV
  within the window. The 5-40 °C × soc0 0.05-0.50 envelope contains those
  conditions. An accurate model may therefore ABSTAIN in Mode D, and only an
  optimistic one commits a design. That outcome is reported as it is: a
  correct abstention is a result, and an unsafe committed design is a
  finding. No condition or threshold is relaxed to produce a design.
- **Not a global optimum.** Mode D searches 1023 grid designs; a better design
  between grid points is not found. Mode X misses violations between its
  model conditions or beyond its top 50.
- **A search that finds nothing is not a safety bound.**
- **The reference's own errors look like agreement.** A common-mode error in
  the pinned solver is invisible here.
- **GPU numerics.** The panel is reconstructed on an A40 GPU. The exam-design
  campaign found GPU and CPU reconstructions not bit-identical, with
  unchanged exam decisions (`EXAM_DESIGN_CAMPAIGN_RESULT.md` §5). EV2's
  members were reconstructed on CPU, so EV4's 15 continuing members are
  comparable to EV2's in recipe, not bit for bit.
- **Bootstrap scope.** The interval treats members as exchangeable; members
  share recipes and seeds, so it is an approximation, reported as such.
- **No lifetime, warranty, cell-qualification or charging-to-SOC claim.** The
  objective is time to CV onset, as in EV1 and EV2.

## 8. Budgets, compute and money

- **Reference solves:** EV4 840; Mode D at most 6 designs × 90 = 540; Mode X
  at most 5 × 50 = 250; **at most 1630**. The job builders refuse to exceed
  each maximum (`test_verification_plans_refuse_to_exceed_the_maxima`).
- **Reconstructions:** 100.
- **Money:** hard cap USD 15 for EV4 and the optimizer together, recorded in
  the campaign ledger (`docs/development/evidence/ev4-2026-10-01/accounting/ledger.jsonl`)
  at `start`. Every dispatch refuses if the committed spend (every live pod to
  its full deadline) plus the new pod's full-deadline cost plus a USD 0.25
  reserve would exceed it, or if the A40 rate is above USD 0.49 per hour, or
  if 3 pods already run.
- **Projection** (measured rates from the exam-design campaign: about 74 s per
  30-cycle solve, 7 workers per A40 pod; GPU fits of tens of seconds):
  - EV4 references: 2 pods × about 85 min;
  - panel: 1 GPU pod, about 60-90 min (not yet measured for DeepONet and
    width-512 members);
  - optimizer verification: up to 3 pods × about 50 min;
  - about 7 pod-hours, **about USD 3.5**. The dispatch deadlines below commit
    at most about USD 5 against the cap.

## 9. How it runs

`ROOT` is the experiment root (outside the repository). `REF` is a pushed
commit that holds the plans.

```text
# once: the campaign ledger and its cap
python -m scripts.dev.exam_design.runpod.pod_control --campaign ev4 start --cap-usd 15

# freeze BEFORE any dispatch (then set this document to FROZEN)
python -m carbon.battery.value freeze --root ROOT \
  --contract carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json

# EV4 references (2 pods) and the panel (1 GPU pod), in parallel
python -m scripts.dev.exam_design.runpod.pod_control --campaign ev4 dispatch value_refs \
  --plan docs/development/evidence/ev4-2026-10-01/plans/ev4-refs-shard0-of2.json \
  --minutes 120 --export-minutes 10 \
  --overlay scripts/dev/exam_design/locks/battery-overlay.lock.json --max-pods 3 --ref REF
#   (the same for ev4-refs-shard1-of2.json)
python -m scripts.dev.exam_design.runpod.pod_control --campaign ev4 dispatch value_panel \
  --plan docs/development/evidence/ev4-2026-10-01/plans/ev4-panel-shard0-of1.json \
  --minutes 150 --export-minutes 10 --jax-platform cuda,cpu --pinned-xla \
  --max-pods 3 --ref REF

# watch, fetch (file by file, hash-checked), terminate
python -m scripts.dev.exam_design.runpod.pod_control --campaign ev4 poll --pod POD
python -m scripts.dev.exam_design.runpod.pod_control --campaign ev4 fetch DEST --pod POD
python -m scripts.dev.exam_design.runpod.pod_control --campaign ev4 terminate --pod POD

# import (write-once; inputs and recipe digests checked) and evaluate
python -m carbon.battery.value import-references --root ROOT --records DEST/out/records.jsonl
python -m carbon.battery.value import-predictions --root ROOT --source DEST/out/predictions
python -m carbon.battery.value optimize import-grid --root ROOT --source DEST/out/grid
python -m carbon.battery.value status --root ROOT
python -m carbon.battery.value evaluate --root ROOT

# Problem C: select (once), build and commit the verification plans, verify, report
python -m carbon.battery.value optimize select --root ROOT
python -m scripts.dev.exam_design.value_plans verify --jobs ROOT/optimizer/jobs.json --shards 3
#   commit and push the plans, then for each shard i of 3:
python -m scripts.dev.exam_design.runpod.pod_control --campaign ev4 dispatch value_refs \
  --plan docs/development/evidence/ev4-2026-10-01/plans/optimizer-verify-shard<i>-of3.json \
  --minutes 75 --export-minutes 10 \
  --overlay scripts/dev/exam_design/locks/battery-overlay.lock.json --max-pods 3 --ref REF2
python -m carbon.battery.value optimize import-references --root ROOT --records DEST/out/records.jsonl
python -m carbon.battery.value optimize report --root ROOT
```

A pod that stops admitting before its deadline leaves its remaining jobs
unsolved. A resume pod skips every case already solved OK
(`--skip-from DEST/out/records.jsonl`). `FAILED_INFRA` is never imported as a
reference.

**Code on the pod.** `dispatch` ships the `carbon/` package, the pod tooling,
the plan and every file the plan names, each pinned by the sha256 of
`git show REF:<path>`. The pod fetches each file from GitHub at `REF` and
verifies every hash before writing any file or importing anything. The
dispatch refuses a `REF` that is on no remote branch.
