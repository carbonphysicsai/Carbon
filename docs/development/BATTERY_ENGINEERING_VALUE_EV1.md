# EV1: does Carbon's scoring select models that make better engineering decisions?

**Status:** public synthetic DEVELOPMENT evidence.

- It is off-chain. The approved battery exam, pool rotation, commitments,
  Phase A publication, winner authority, fees and rewards are unchanged.
- New scoring rules stay DEVELOPMENT evidence until the owner approves a
  prospective rule change.
- Decisions: BATTERY-EV1 (EV1-D1 to D8) in `.agent/DECISIONS.md`.
- Ticket: `.agent/tickets/BATTERY-EV1_engineering_value_decision.md`.

**First success condition.** Carbon can compare several models on the same
engineering decision, and show whether its scoring prefers models that
select better reference-verified designs.

## 1. The decision

The contract is `carbon/battery/value/contracts/ev1-charge-protocol-selection.v1.json`
(schema `carbon.engineering-value-contract.v1`).

- **Candidates:** a fixed set of 16 two-stage fast-charge protocols. The
  first stage is c1 ∈ {0.75, 1.25, 1.75, 2.0} C until 4.0 V; the second is
  c2 ∈ {0.4, 0.6, 0.8, 1.0} C until 4.2 V.
- **Scenarios:** frozen sets of operating conditions (ambient temperature,
  initial SOC). There are three development scenarios (temperate, warm,
  cool) and three verification scenarios (mild, hot, cold). A protocol must
  qualify in every condition of its scenario.
- **Objective:** minimize the worst-case time to constant-voltage onset (the
  first 4.19 V crossing after the 120 s rest).
- **Constraints:**
  - onset reached inside the window;
  - cycle-1 plating margin ≥ 0 V;
  - first-hour peak temperature ≤ 45 °C.
- **Baseline:** 0.75 C / 0.6 C, a conservative default declared before any
  evaluation.
- **Tie rule:** the lower c1 wins, then the lower c2.
- **Minimum useful improvement:** 120 s.
- **Mistake costs:** a false acceptance costs 10, a missed opportunity 1 and
  regret 1 per 120 s. These are provisional.
- **Reference uncertainty:** the maximum refinement shift. A value within the
  band is UNRESOLVED.

## 2. Capability inventory

| Capability | State |
|---|---|
| Reference generator, truth service and resumable records | exists (reused) |
| Battery reconstruction, from recipe and seed through the worker backend | exists (reused) |
| Exam gates and components on a scoring set | exists (reused) |
| Retained campaign references for the scoring set (1588 cases) | exists (reused) |
| Retained trained weights | **absent**: only digests were kept, so members are reconstructed |
| Charging time to a target SOC | **absent**: needs the extension in §7 |
| A defensible battery physics score | **absent**: not invented |
| Zero-weight scoring semantics | implemented (`carbon.development-weight-profile.v1`) |
| Decision measurement, selector, verification and metrics | implemented (`carbon/battery/value/`) |
| Operator run, status, resume and export | implemented (`python -m carbon.battery.value`) |
| Workbench import and read-only view | implemented (`carbon/scientific_tasks/workbench_value.py`) |
| Container isolation for reconstruction | exists (the M3 carrier backend); EV1's local run uses the in-process backend and is labelled so |
| GPU execution | not needed: EV1 is CPU work |

Mocks are not numerical acceptance. The end-to-end test uses a labelled
analytic fixture solver and a fixture backend. The authentic run uses
pinned PyBaMM and real reconstructions.

## 3. Operator commands

```bash
# the pinned PyBaMM runtime (see BATTERY_TESTNET_HOST_HANDOFF.md §2.2)
export PYTHONPATH=/srv/carbon/battery/truth-overlay:.
uv run --locked python -m carbon.battery.value run    --root /srv/carbon/ev1 --workers 4
uv run --locked python -m carbon.battery.value status --root /srv/carbon/ev1
uv run --locked python -m carbon.battery.value resume --root /srv/carbon/ev1 --workers 4
uv run --locked python -m carbon.battery.value export --root /srv/carbon/ev1 --out /srv/carbon/ev1-export
# references solved elsewhere (the truth container) are ingested, never trusted blindly:
uv run --locked python -m carbon.battery.value import-references --root /srv/carbon/ev1 --records records.jsonl
```

- Without the pinned runtime, `run` writes the jobs file and the exact
  truth-container command, and reports `MISSING_PREREQUISITE`.
- One runner holds each root at a time.
- Nothing already solved or reconstructed is repeated.

## 4. Run plan and cost

| Step | Units | Measured / expected | Paid |
|---|---|---|---|
| Decision references | 384 PyBaMM solves (16 × 4 × 6) | measured: about 65 s each, 4 workers, about 1.2 h of solving; the wall time was longer because two container restarts interrupted it and the run resumed each time | no |
| Reconstructions | 11 (7 recipes, 1 to 3 seeds each) | measured: about 2 min for all 11 on CPU | no |
| Predictions, selection and scoring | 16 members × (1588 + 384) cases | seconds | no |

OD-5 is not used: no RunPod pod and no model-provider call is needed. The
track ceiling is untouched.

## 5. Results (run of 2026-09-25)

Public synthetic DEVELOPMENT evidence. It changes no testnet rule, claims no
qualification and claims no optimal weight ratio.

**Retained evidence** is in `docs/development/evidence/ev1-2026-09-25/`:
- the frozen manifest, contract digest `sha256:292c0473…d0f9`;
- `results.json` and `report.md` in full;
- the 384 decision references (gzipped) with their SHA-256;
- the SHA-256 of each member's predictions. The predictions themselves
  (43 MB) are regenerable from the manifest.

**How it ran.**
- 384 pinned-PyBaMM reference solves (`pybamm==26.8.0.0` from the
  hash-locked overlay), run locally: **384 OK**, 0 failed, 0 timed out.
- 11 reconstructed members plus 5 labelled synthetic controls.
- Selection used model predictions only. The references were read only
  for verification.
- Cost: USD 0. OD-5 is untouched.

### 5.1 What the reference says about the decision

| Scenario | Split | Feasible / infeasible / unresolved | Best in tested set | Main failing constraints (candidate × condition, of 64) |
|---|---|---|---|---|
| D1-temperate | development | 3 / 12 / 1 | c1 1.25, c2 0.8 | CV not reached 18, plating 18, temperature 4 |
| D2-warm | development | 1 / 15 / 0 | c1 0.75, c2 1.0 | temperature 32, CV not reached 19, plating 4 |
| D3-cool | development | 0 / 15 / 1 | none | plating 50, CV not reached 14 |
| V1-mild | verification | 0 / 15 / 1 | none | plating 26, CV not reached 17 |
| V2-hot | verification | 0 / 16 / 0 | none | temperature 34, CV not reached 22 |
| V3-cold | verification | 0 / 16 / 0 | none | plating 51, CV not reached 16 |

The baseline (c1 0.75, c2 0.6) is infeasible or unresolved in every
scenario, so "improvement over baseline" is never measurable.

**Finding 1: the tested design set is too narrow for most scenarios.** The
objective is the worst case over each scenario's four conditions, so a
protocol must be feasible in all of them. In the tested set:
- the gentlest protocols do not reach CV within the window;
- the faster protocols plate in the cold scenarios or overheat in the hot
  one.

As a result, **no verification scenario has a feasible protocol**. On the
verification split, a member can only be told apart by whether it avoids
selecting an infeasible protocol, a false acceptance. Regret and missed
opportunity are not exercised there.

### 5.2 Do the scoring rules prefer models that decide better?

| Rule | τ development | τ verification | τ development incl. controls | Top member (8/8 leave-one-batch-out) |
|---|---|---|---|---|
| control-exam-v1 (approved rule) | 0.341 | **0.165** | 0.000 | mlp_ens3-s0 |
| p45-r30-a25 | not measurable: the physics leg has no measurement for battery | — | — | — |
| p0-r30-a70 | 0.341 | 0.110 | 0.149 | mlp_ens3-s0 |
| p0-r20-a80 | 0.341 | 0.110 | 0.025 | mlp_ens3-s0 |
| p0-r40-a60 | 0.341 | 0.110 | 0.149 | mlp_ens3-s0 |

- **The rule chosen on development is the control.** All measurable rules
  tie at τ 0.341, and ties go to the control by the frozen rule. On
  verification, the control's τ is 0.165, against 0.110 for every
  reweighted profile.
- **Answer to the EV1 question.** Carbon can compare several models on the
  same engineering decision, and the frozen scoring rule shows a **weak
  positive** preference for models that select better reference-verified
  designs (τ 0.17 on verification).
  - The panel is small.
  - The reconstruction seeds are repetitions of a recipe, not independent
    models.
  - The verification split measures only false acceptance (Finding 1).
  - So this is **indicative, not established**.
- **No reweighting beats the approved rule.** Moving weight between
  robustness and accuracy does not improve decision alignment on
  verification. This gives no reason to change the testnet rule, and none is
  proposed.

**Finding 2: error-based scores can rank a dangerous model highly.** The
synthetic controls expose a blind spot that the reconstructed panel alone
would hide:
- `boundary_optimist` has small errors but always leans toward feasibility.
  It selects an infeasible protocol in 5 of 6 scenarios (loss 10), yet it
  scores better than every reconstructed member under the control rule
  (-0.046, against -0.051 to -0.171).
- With the controls included, the control rule's τ falls to 0.000.
  Robustness-weighted profiles hold at 0.149, but no rule ranks
  `boundary_optimist` last.
- This is the case for §8's decision-aware robustness component.

**Finding 3: gates and decision quality are separate.** `mlp_raw-s0` fails
a mandatory exam gate and is ineligible under every rule, yet its decisions
match the best members'. That is the intended "admissibility before
ranking" behaviour, not a scoring error. It is reported, not rescued.

**Stability.** The top member (`mlp_ens3-s0`) is unchanged in 8 of 8
leave-one-batch-out subsets, under every measurable rule.

## 6. How to read the comparison

- The **decision loss** per member and scenario is 0 for the best tested
  feasible protocol. It rises with regret (gap to the best, per 120 s), a
  missed opportunity costs 1 and selecting an infeasible protocol costs 10.
  Unresolved or unavailable outcomes are excluded, not scored.
- For each rule, **Kendall τ** is the correlation between the rule's score
  and decision quality (lower loss) across the reconstructed members.
  τ > 0 means the rule prefers models that decide better.
- The rule is chosen on the development scenarios (the highest τ; ties go
  to the control), frozen, and then reported on the verification scenarios.
- **"Best"** means best in the tested candidate set, never a global optimum.
- With a small panel, τ is indicative, and no optimal weight ratio is
  claimed.

## 7. Prepared: the charging-time-to-target-SOC extension

This is not needed for EV1. The objective would become time to 80% SOC.

- **Target:** SOC = 0.80, where SOC(t) = soc0 + (charge throughput since the
  start of step 1) / nominal capacity.
- **Events:**
  - the start is the beginning of cycle-1 step 1, after the 120 s rest;
  - the end is the first SOC crossing of 0.80 (by linear interpolation) on
    the stored time grid, or a recorded step-event time.
- **Unit:** s.
- **Unreached:** NOT_REACHED if the charge phase ends first, with a declared
  censoring rule. It is never the phase length.
- **Reference change:** extract "Discharge capacity [A.h]" (already in
  `STORED_VARIABLES`) or current on the grid, plus the cycle-1 step start and
  end times. This changes `solve_case` outputs, so it is a new reference
  version (`carbon.battery.reference.v2`).
- **Surrogate change:** a new output `time_to_soc80_s` (a scalar) or an SOC
  trajectory. This is a new construction-contract version with new SHAPES.
- **Versioning:**
  - TRAIN v2, practice and pool references are re-solved: about 1,200
    solves at about 70 s each;
  - v1 recipes, data and results are preserved unchanged, and nothing is
    reinterpreted.

## 8. Next scoring experiment (recommended)

1. **EV2: a decision set that exercises every outcome.** Freeze a new
   contract version before any run. EV1's contract and results stay
   unchanged, and nothing is re-scored.
   - Widen the candidates so that every scenario, verification included,
     has feasible protocols: gentler first steps that still reach CV, and
     intermediate c2 values.
   - Or make the decision per condition instead of worst-case per scenario.
   - Declare either choice in advance. Never choose it by looking at EV1's
     verification results.
2. **A decision-aware robustness component**, as a separate factor: error
   weighted by distance to the declared constraint boundaries (plating
   margin and peak temperature). Test whether it ranks `boundary_optimist`
   below the members that decide correctly (Finding 2), on the same panel.
3. **Independent models:** add recipes that differ in more than their seed,
   so that τ rests on more than repetitions of a recipe.
4. Add the time-to-SOC objective once §7 lands.

## 9. Remaining work for a continuous model-guided design loop

- An optimizer that proposes new protocols. EV1 only selects from a fixed
  set.
- A verification budget per iteration.
- An acquisition rule that uses model uncertainty. Current members give
  point predictions only.
- A reference-verification queue that keeps fresh verification cases
  separate from the cases the loop sees.
- A Workbench flow for a private client objective, through the private
  execution route only.
