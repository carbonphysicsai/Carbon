# PRACTICE-SAFETY-01: decision-value safety metrics in practice feedback (spec)

**Status:** FINAL. The Test Lead ruled on it on 2026-10-05 (B4 set and bands). The Test Engineer builds it.

**Authority:** owner decision A8, relayed by the Test Lead on 2026-10-05: show decision-value safety metrics next to the practice score in practice feedback. The Test Lead set rules 1–4 below.

**Motivation:** Graphite run 5 (#609). The winner had the best practice score but a thermal false acceptance at the limit: in D-T24-S0.12, `c1 = 2 C` runs about 0.49 °C over 45 °C. The practice score measures average error, so it cannot show the *direction* of error at a limit. These metrics make that direction visible to the participant.

## Hard rules (every metric)

1. **Feedback only.** A metric enters NO score, gate, ranking, promotion, frontier event or settlement. Every computed field carries `"feedback_only": true`.
2. **Public practice material only.**
   - **Allowed:** each Challenge's committed practice cases and their committed reference records.
   - **Also allowed (PRACTICE-QUIZ-01, the Test Lead's rulings of 2026-10-06):** a hidden batch Carbon has retired and released into the training data pool (`CARBON_COMMIT_TO_TRAINING_POOL`), which is public once released; and committed TRAIN cases in the practice quiz's public near-limit set.
   - **Never read:** scoring sets, hidden or private pools, sealed or confirmation batches, the EV decision conditions (EV1/2/4/5 and the protected grids), or the motor and cooling counted-study points.
3. **No Track B data.**
   - A decision-level metric uses a separate **practice decision set**. It is registered before use and drawn from public practice conditions.
   - It must be disjoint from every Track B set. A test enforces this (see *Disjointness*).
4. **Disclosure is allow-listed.**
   - Allowed: aggregate rates, counts and signed means per constraint.
   - Never: per-case values, case ids or per-case PASS/FAIL. These would let a participant fit the limit boundary case by case.
   - The computation must refuse any other field.
5. **Missing data is never clean.**
   - A missing prediction makes the metric `null` (`UNMEASURED`).
   - A reference that fails validity, or that falls within its band of a limit, is `UNRESOLVED` and excluded.
   - Both counts are reported.

## Metrics

Shared terms used throughout:
- "Reference FAIL" and "model PASS" use the same constraint check as the Challenge's decision code.
- The **reference** call uses the committed uncertainty band where one exists.
- The **model** call uses no band.
- A false-feasible (false-acceptance) rate is `#(reference FAIL and model PASS) / #(reference FAIL)`. It is `null` when no case is a reference FAIL.

### Battery (`battery-fastcharge-ageing-development-v1`)

**Practice material:**
- `docs/development/evidence/exam-design-2026-09-24/refs-a-part2/out/records.jsonl`;
- the 200 PRACTICE cases (`carbon/battery/practice.py`: `PRACTICE_SOURCE_PATH`, sha256 pinned as `PRACTICE_SOURCE_SHA256`);
- unrefined records only.

**B1. Near-limit false acceptance per constraint (plating, thermal).**
- **Definition:** `carbon/battery/value/false_acceptance.component(contract, predictions, near_cases(store, practice_ids), refs)`, applied to the practice store.
  - The contract supplies the constraints and bands (EV4's).
  - `near_cases` is the published important region (`carbon/battery/domain.is_important`).
- **Report:** per constraint, `false_acceptance`, `reference_fail`, the rate, and the worst constraint.
- **Why both constraints:** run 5's winner failed on thermal, while its 9.5 % plating rate was one seed's.

**B2. Near-limit optimism (bands).**
- **Definition:** `carbon/battery/value/admissibility.near_optimism(contract, predictions, practice_ids, refs)`, the same measure the EV5 gate uses, on practice cases.
- **Report:** the value only. Do **not** show the gate's PASS or FAIL, and do not mention the cutoff, so feedback does not invite gaming the cutoff.

**B3. Signed near-limit margin error (per constraint).**
- **Definition:** the mean of `(predicted margin − reference margin)` in band units over the important practice cases (`margins._margins`). Positive means optimistic.
- This is the direction signal that the average error hides. Recommended, and cheap.

**B4. Feasible-choice rate on the practice decision set.**
- **APPROVED** by the Test Lead (2026-10-05). It is built once Data Collection commits the set. Until then the metric reports `"BLOCKED: practice decision set not committed"`.
- **Definition:** over the registered practice decision scenarios, the share where the model's chosen protocol is reference-feasible (`decision.decide`/`evaluate` with the EV4 contract's grid, costs and tie rule). Abstentions are reported separately.
- **Needs new public reference solves.** A practice case is one protocol at one condition; a decision needs the full 35-protocol grid at a condition.
- **The set (ruled):**
  - 6 conditions × EV4's 35-candidate grid = 210 public solves, on the operator host's CPU, with no spend. They run outside the EV5 and Attacker host windows.
  - Every condition lies inside the published box, at least **2 °C in t_amb AND 0.03 in soc0** from every EV1/EV2/EV4/EV5 condition and from EV4's protected optimizer grid.
  - 4 conditions are representative and 2 are near-limit (low t_amb, high soc0).
- **Selection rule:** Data Collection writes and commits it before any solve.
- **Status after publication:** the references are committed as public practice material, and the 6 conditions become **permanently practice-only**. They can never enter Track B or a confirmation set.

### Cooling (`ai-accelerator-cooling` cold plate)

**Practice material:** `docs/development/evidence/cold-plate-pools-v1/practice.jsonl` (100 cases, `carbon/cold_plate/challenge.py: PRACTICE_PATH`), committed reference outputs.

**Limits:** the study's synthetic scenario (`docs/development/studies/AI_ACCELERATOR_COOLING_SYNTHETIC_V1.json` → `scenario.die_limit_c` = 100.0, `scenario.hydraulic_limit_w` = 0.25).

**Quantities:** `carbon/cold_plate/customer_decision.quantities` (die peak from `peak_c`; hydraulic power from the pressure drop and flow), as Track B uses them. They are computed for reference and model alike at each practice case's own inputs.

- **C1. Die-limit false-feasible rate:** reference die peak > limit, model ≤ limit.
- **C2. Hydraulic-power false-feasible rate:** reference > limit, model ≤ limit.
- **C3 (recommended). Signed die-peak error:** mean (model − reference) °C over cases whose reference die peak is within 10 °C of the limit.

**Band (ruled):** an exact comparison against the limit, with no band. Every cooling metric is labelled `"no uncertainty band applied"` in the feedback, so a miner reads it as indicative.

### Motor

**Practice material:** `docs/development/evidence/motor-pools-v1/practice.jsonl` (30 cases, `carbon/motor/challenge.py: PRACTICE_PATH`).

**Limits:** §6 of `docs/development/studies/MOTOR_SYNTHETIC_DECISION_V2.json` → `scenario.min_mean_torque_nm` = 4.0, `scenario.max_ripple_fraction` = 0.30.

**Quantities:** the reference `derived.mean_nm` and `ripple_pk_pk_nm`. Ripple fraction is `ripple_pk_pk / |mean|` (`carbon/motor/customer_decision`'s definition). The model's come from the same function on its predicted torque series.

- **M1. Ripple-fraction false-feasible rate:** reference > 0.30, model ≤ 0.30.
- **M2. Mean-torque false-feasible rate:** reference < 4.0 N·m, model ≥ 4.0.
- **M3. Signed mean-torque bias at J ≥ 10 A/mm²:** mean (model − reference) `mean_nm` over practice cases with `current_density_a_mm2` ≥ 10. Positive means optimistic.

**Small sample.** With 30 cases, report the counts next to every rate and say "n = 30".

**Band (ruled):** an exact comparison with no band. Every motor metric is labelled `"no uncertainty band applied"`.

## Disjointness (the test the Test Engineer adds)

`tests/cpu/test_practice_safety_disjoint.py` asserts that no practice input point coincides with any Track B or EV point, after rounding to the generator's precision (4 dp):
- the battery practice cases against the EV1, EV2, EV4 and EV5 decision conditions, EV4's protected grids and EV5's optimizer grids;
- the B4 practice decision set against the same, at the ruled distance: at least 2 °C in t_amb AND 0.03 in soc0 from every listed condition;
- the cooling practice cases against the cooling study's designs × conditions;
- the motor practice cases against `MOTOR_SYNTHETIC_DECISION_V2.json` designs × conditions.

It also asserts that the metric code imports no scoring-set, pool-store, seed-journal or study-campaign module (an import-graph check).

## Output shape (allow-listed)

```json
{"schema": "carbon.practice-safety-feedback.v1", "challenge": "...", "feedback_only": true,
 "metrics": {"B1": {"no_plating_onset": {"false_acceptance": 2, "reference_fail": 74, "rate": 0.027}, "peak_temperature": {...}, "worst": "..."},
             "B2": {"near_optimism_bands": 1.02}, "B3": {...}, "B4": "BLOCKED: practice decision set not registered"},
 "unmeasured": 0, "unresolved": 3, "material": {"path": "...", "sha256": "..."}}
```

## Not in scope

- Any change to the practice score, rule v1/v2, gates or the EV5 study.
- Showing these metrics on hidden-batch results.
