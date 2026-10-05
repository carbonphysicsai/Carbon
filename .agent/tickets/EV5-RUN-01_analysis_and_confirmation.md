# EV5-RUN-01: EV5's analysis, verdicts and sealed confirmation path

**Status:** IN REVIEW. This must be built, reviewed and merged before any EV5 solve.

**Authority.**
- **Run:** OWNER-EV5-GO-01, the owner's direct go on 2026-10-05.
- **Freeze and inputs:** OWNER-EV5-FREEZE-01 (the frozen pre-registration), OWNER-EV5-CAP-01 (spend), and OWNER-EV5-Q1-01..Q4-01.
- **Delegation:** the Test Lead's EV5-RUN-01 assignment (OWNER-GRAPHITE-TEST-WAVE-06/-07 delegation).
- **Rulings:** the Test Lead's pre-data rulings below.

**Why this exists.** EV5 froze on 2026-10-03 (`docs/development/evidence/ev5-2026-10-03/freeze-manifest.json`). Its pods were runnable, but two things were never built:
- the pre-registered analysis: H1, H2, H3, the adversarial-score verdict and the construction-integrity verdict;
- the host-only path for the sealed confirmation batch.

Without them, the analysis would be written after seeing data. This ticket builds both before any solve and pins the code by digest.

## Scope

**New:**
- `carbon/battery/value/ev5_run.py`;
- `tests/cpu/test_battery_ev5_run.py`;
- `docs/development/evidence/ev5-2026-10-03/run-record.json`;
- this ticket and the OWNER-EV5-GO-01 decision record.

**Edited, minimally:** `carbon/battery/value/optimizer.py`.
- Its host-side steps refused any contract but EV4's.
- `run_select` never passed EV5's candidate scores or gate verdicts, so EV5 selection could not run.
- It now accepts EV5's contract and passes both through to the existing `select_members` and `select`, which already implement EV5's spec. EV4 behaviour is unchanged.

**Not edited:**
- every file the freeze manifest pins (the pre-registration, the study sheet, `false_acceptance.py`, the contract and the plans);
- `admissibility.py`;
- `ev5.py`'s outputs.

## The run record (pinned before the first solve)

`python -m carbon.battery.value.ev5_run pin` writes the run record. It records:
- the freeze manifest's SHA-256;
- the contract digest;
- the SHA-256 of every `carbon` module the analysis and confirmation commands load. That includes every module the freeze manifest does not pin, such as `admissibility.py`, `hypotheses.py`, `real_divergence.py`, `divergence.py`, `margins.py`, `optimizer.py` and this module.

Every `ev5_run` command re-hashes those modules first. It refuses (`module_changed`, `module_unpinned`, `manifest_changed`, `run_record_missing`) on any difference, so the analysis cannot drift between the pin and the result. PR Head holds any PR touching `admissibility.py` until EV5 completes (the Test Lead's request).

## Interpretation choices (pre-data)

Items 1–3 are RULED by the Test Lead. The rest are this ticket's proposed working decisions, for the Test Lead to rule on in review. Each is fixed before any EV5 data exists.

1. **RULED: gate failures rank last.** Under "the deciding rule plus the gate", a gate FAIL is inadmissible and ranks below every member that passes (Test Lead, 2026-10-05).
   - The pinned `admissibility.gated()` returns 0.0 on FAIL, which under `control-exam-v1` (−E < 0) would rank a FAIL *first*. It is not used for ranking.
   - Gate verdicts still come from the pinned `admissibility.near_optimism` and `admissibility.verdict` at `THRESHOLD_BANDS` = 2.0, unchanged.
2. **RULED: the manifest's "scores 0 under the rule (admissibility.gated)"** means the worst position. Under a higher-is-better score, 0 is last. The literal-0 reading appears as a labelled SENSITIVITY line in the report and never enters a verdict.
3. **RULED: H1's bootstrap is the pinned `hypotheses.paired_bootstrap`, as is.** Each replicate resamples members and conditions, independently, which is a faithful reading of "members and conditions jointly".
4. **SR-2 scores** come from `margins.with_margins` on the scoring set (SR-2's own computation), rule `sr2-a0-r0.3-g0.6-m0.1`. The analysis refuses if the rule's weights differ from the manifest's `rules_compared.candidate.weights`.
5. **H1 pool:** eligible `RECONSTRUCTED` members with numeric scores under both rules (`hypotheses.evaluate`'s convention). Attack constructions and controls are excluded, per the manifest. H1 compares the two rules ungated, as its statistic states.
6. **H1 conditions.**
   - The interval's lower bound is > 0.
   - **Noise band.** Δτ > `divergence.tau_noise_band(results)` (deciding rule, verification split: the function's defaults), strictly.
   - **Divergence count.** The candidate's `real_divergence.classified(·, rule).counts.verification.across_families` must be ≤ the deciding rule's. The classification runs on the ungated rules.
   - All three must hold for PROMOTE_CANDIDATE. Otherwise the outcome is DECIDING_CONFIRMED.
7. **H2.**
   - **Measurement.** The gate is measured on the scoring set, as in the cutoff's own evidence: `near_optimism(contract, predictions, scoring_ids, refs)`.
   - **Real members:** eligible `RECONSTRUCTED`.
   - **The difference** is the pinned `group_difference_bootstrap` on the verification loss matrix.
   - **H2 holds** only if: the boundary optimist FAILs; oracle, conservative and rank-preserving delay PASS; the difference is > 0; and the interval excludes 0.
   - Either group empty gives UNDEFINED.
   - The count of failed real members and the more-than-half flag are reported. Neither changes the outcome.
8. **H3** is reported via `ev5.h3_report`.
   - Separation holds if the sign-error control's worst rate is above every eligible real member's measured rate.
   - Unmeasured members (None) are listed, never treated as clean.
   - Separation is UNDEFINED if the control is unmeasured.
   - The control's rank is reported under all four rules (two rules, with and without the gate).
9. **The value verdict is reported, not graded.** The pre-registration says what each hypothesis decides, but not what "value passes" means for the rung. The report gives H1's outcome, H2's outcome and H3's separation. Whether these pass the rung stays with the owner's signed lock (OWNER-TRACK-A-L0-02).
10. **Adversarial score** = FAIL if any construction with a reference-verified violation is in the top half.
    - **Constructions:**
      - every `ATTACK_CONSTRUCTION` panel member that selects a protocol the reference verifies INFEASIBLE in any EV5 scenario (`SELECTED_INFEASIBLE`, either split);
      - every Mode X finding, in band or out of band, counted and reported separately.
    - **Rank:** competition rank under `control-exam-v1`, with gate failures last (item 1) and unscored members last. The rank is taken among the eligible `RECONSTRUCTED` members, plus the construction when it is not one of them.
    - **Top half** = 2 × rank ≤ n, the frozen `divergence.verified_violation` cut.
11. **Construction integrity** = PASS only if all four hold.
    - **(a)** `track_a.run()`: every family IN_PROGRESS (attacks held, specimen fired, control passed), with no family finding. The retained EV2/EV4 divergence conditions it also lists are not construction findings.
    - **(b)** Every manifest-listed refused attack recompiles to exactly its recorded typed codes.
    - **(c)** Every panel member's bundle matches the frozen panel's recipe digest and seed (`Experiment.evaluate` enforces this). Any missing member must have a typed pod failure record.
    - **(d)** The worker-boundary scan (`tests/service/test_battery_track_a_service.py`, CI-only) is supplied as the CI job's result on the run's exact commit. Without it the verdict is INCOMPLETE, never PASS.
12. **The confirmation set** (OWNER-EV5-Q3-01) runs on the operator host only.
    - **Batch.** It is regenerated by `seeds.make_batch(root, pin, "ev5-confirmation", 124, 4)` from the deployment's committed root. It is checked against the fingerprint (`sha256:0add08ed…`) and journal sequence 14 via `SeedJournal.recall`, which never commits.
    - **Solves.** The 124 cases are solved in the pinned truth image (no network). The pool store is never opened.
    - **Predictions.** Every panel member is rebuilt on the host CPU (`DirectBackend`), so predictions are not bit-identical to the A40 panel.
    - **Report** (descriptive, owner-only file):
      - each member's exam components and `control-exam-v1` score on the batch (the paired-repeat gate is exercised by its hidden duplicates);
      - gate optimism and near-limit false acceptance on the batch's important region, reported separately;
      - the adversarial check repeated on these scores.
    - It enters no verdict. Its role and any publication of its aggregates wait for the Test Lead and owner (the L0 sheet's `fresh_attack_confirmation` expected result is HUMAN_INPUT).
13. **Undefined values.** A reference failure or unresolved loss is excluded (NaN or None) as the pinned functions do. It is never a candidate failure.

## Validation

- `tests/cpu/test_battery_ev5_run.py` has known-answer fixtures for each verdict, passing and failing:
  - H1: PROMOTE and CONFIRMED;
  - H2: HOLDS, DOES_NOT_HOLD and UNDEFINED;
  - H3: separation true and false;
  - adversarial: PASS and FAIL, including the last-ranked FAIL under negative scores and the literal-0 sensitivity line;
  - construction integrity: PASS, FAIL and INCOMPLETE;
  - the run record's refusals;
  - the confirmation batch check (fingerprint and sequence mismatch refused).
- The EV4 optimizer tests are unchanged and pass.
- Canonical `check_quality`.

## Maturity

IMPLEMENTED and TESTED (fixtures). Nothing is scientifically qualified. No LIVE, chain, reward or testnet-rule change.

## Hub impact

Primary `map_ref`: battery engineering value (EV5). This is engineering of an already-registered study, so the hub's purpose, placement, status and boundaries are unchanged.
