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
| Decision references | 384 PyBaMM solves (16 × 4 × 6) | about 62 s each, 4 workers: about 2 to 3.5 h wall on the 4-core sandbox, depending on contention | no |
| Reconstructions | 11 (7 recipes, 1 to 3 seeds each) | minutes each on CPU | no |
| Predictions, selection and scoring | 16 members × (1588 + 384) cases | seconds | no |

OD-5 is not used: no RunPod pod and no model-provider call is needed. The
track ceiling is untouched.

## 5. Results

The results are in the EV1 PR's completion comment and in
`results/report.md` under the experiment root. See §6 for how to read them.

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

Add a **decision-aware robustness component** as a separate factor: error
weighted by distance to the declared constraint boundaries (plating margin
and peak temperature). Compare it with the important-region definition on
the same panel. Then add the time-to-SOC objective once §7 lands.

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
