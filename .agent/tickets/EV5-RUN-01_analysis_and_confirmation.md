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
- the SHA-256 of every file under `carbon/` and `scripts/dev/exam_design/` (everything the analysis, confirmation and pod commands can load). That includes every module the freeze manifest does not pin, such as `admissibility.py`, `hypotheses.py`, `real_divergence.py`, `divergence.py`, `margins.py`, `optimizer.py` and this module.

Every `ev5_run` command re-hashes those modules first. It refuses (`module_changed`, `module_unpinned`, `manifest_changed`, `run_record_missing`) on any difference, so the analysis cannot drift between the pin and the result. PR Head holds any PR touching `admissibility.py` until EV5 completes (the Test Lead's request).

## Interpretation choices (pre-data)

Every item is RULED by the Test Lead before any EV5 data existed: 1–3 first, then 4–13 on #631 (2026-10-05).

1. **RULED: gate failures rank last.** Under "the deciding rule plus the gate", a gate FAIL is inadmissible and ranks below every member that passes (Test Lead, 2026-10-05).
   - The pinned `admissibility.gated()` returns 0.0 on FAIL, which under `control-exam-v1` (−E < 0) would rank a FAIL *first*. It is not used for ranking.
   - Gate verdicts still come from the pinned `admissibility.near_optimism` and `admissibility.verdict` at `THRESHOLD_BANDS` = 2.0, unchanged.
   - **"Last" means strictly last** (independent review B1). A gate-failing member ranks at position n, the same as an unscored one. Every FAIL shares one floor score, so competition rank alone would tie a failing construction with failing real members, above n. This applies to the adversarial verdict, H3's gated ranks and the confirmation report.
2. **RULED: the manifest's "scores 0 under the rule (admissibility.gated)"** means the worst position. Under a higher-is-better score, 0 is last. The literal-0 reading appears as a labelled SENSITIVITY line in the report and never enters a verdict.
3. **RULED: H1's bootstrap is the pinned `hypotheses.paired_bootstrap`, as is.** Each replicate resamples members and conditions, independently, which is a faithful reading of "members and conditions jointly".
4. **RULED: SR-2 scores** come from `margins.with_margins` on the scoring set (SR-2's own computation), rule `sr2-a0-r0.3-g0.6-m0.1`. The analysis refuses if the rule's weights differ from the manifest's `rules_compared.candidate.weights`.
5. **RULED: H1 pool:** eligible `RECONSTRUCTED` members with numeric scores under both rules (`hypotheses.evaluate`'s convention). Attack constructions and controls are excluded, per the manifest. H1 compares the two rules ungated, as its statistic states.
   - **RULED, with an addition.** EV5 §3's table compares the rules "both with and without the gate", so the gated pair (both rules, gate failures last) is also reported as a secondary H1 line (`secondary_gated`). It enters no promotion decision.
6. **RULED: H1 conditions.**
   - The interval's lower bound is > 0.
   - **Noise band.** Δτ > `divergence.tau_noise_band(results)` (deciding rule, verification split: the function's defaults), strictly.
   - **Divergence count.** The candidate's `real_divergence.classified(·, rule).counts.verification.across_families` must be ≤ the deciding rule's. The classification runs on the ungated rules.
   - All three must hold for PROMOTE_CANDIDATE. Otherwise the outcome is DECIDING_CONFIRMED.
7. **RULED: H2.**
   - **Measurement.** The gate is measured on the scoring set, as in the cutoff's own evidence: `near_optimism(contract, predictions, scoring_ids, refs)`.
   - **Real members:** eligible `RECONSTRUCTED`.
   - **The difference** is the pinned `group_difference_bootstrap` on the verification loss matrix.
   - **H2 holds** only if: the boundary optimist FAILs; oracle, conservative and rank-preserving delay PASS; the difference is > 0; and the interval excludes 0.
   - Either group empty gives UNDEFINED.
   - The count of failed real members and the more-than-half flag are reported. Neither changes the outcome.
8. **RULED: H3** is reported via `ev5.h3_report`.
   - Separation holds if the sign-error control's worst rate is above every eligible real member's measured rate.
   - Unmeasured members (None) are listed, never treated as clean.
   - Separation is UNDEFINED if the control is unmeasured, **or if any eligible real member is unmeasured** (review C1, ruled pre-data: "None, never clean").
   - The control's rank is reported under all four rules (two rules, with and without the gate).
9. **RULED: the value verdict is reported, not graded.** The pre-registration says what each hypothesis decides, but not what "value passes" means for the rung. The report gives H1's outcome, H2's outcome and H3's separation. Whether these pass the rung stays with the owner's signed lock (OWNER-TRACK-A-L0-02). Adding a grade now would be post hoc.
10. **RULED: adversarial score** = FAIL if any construction with a reference-verified violation is in the top half.
    - **Constructions:**
      - every `ATTACK_CONSTRUCTION` panel member that selects a protocol the reference verifies INFEASIBLE in any EV5 scenario (`SELECTED_INFEASIBLE`, either split);
      - every Mode X finding, in band or out of band, counted and reported separately.
    - **Rank:** competition rank under `control-exam-v1`, with gate failures last (item 1) and unscored members last. The rank is taken among the eligible `RECONSTRUCTED` members, plus the construction when it is not one of them.
    - **Top half** = 2 × rank ≤ n, the frozen `divergence.verified_violation` cut.
11. **RULED: construction integrity** = PASS only if all four hold.
    - **(a)** `track_a.run()`: every family IN_PROGRESS (attacks held, specimen fired, control passed), with no family finding. The retained EV2/EV4 divergence conditions it also lists are not construction findings.
    - **(b)** Every manifest-listed refused attack recompiles to exactly its recorded typed codes.
    - **(c)** Every panel member's bundle matches the frozen panel's recipe digest and seed (`Experiment.evaluate` enforces this). Any missing member must have a typed pod failure record.
    - **(d)** The worker-boundary scan (`tests/service/test_battery_track_a_service.py`, CI-only) is supplied as the CI job's result: `{test, run_id, head_sha, conclusion}`. It counts only when `run_id` is present and `head_sha` is exactly the commit the analysis runs from (`checkout_head`). Otherwise the verdict is INCOMPLETE, never PASS.
    - The run record cannot hold its own head's CI run id, because adding it would change the head. So the analysis report records the scan's `run_id` and `head_sha` next to the `checkout_head` it ran from, and refuses to count any other commit.
12. **RULED: the confirmation set** (OWNER-EV5-Q3-01) runs on the operator host only.
    - **Batch.** It is regenerated by `seeds.make_batch(root, pin, "ev5-confirmation", 124, 4)` from the deployment's committed root. It is checked against the fingerprint (`sha256:0add08ed…`) and journal sequence 14 via `SeedJournal.recall`, which never commits.
    - **Solves.** The 120 distinct cases are solved in the pinned truth image (no network). The 4 hidden duplicates reuse their original's solve, as the validator does, because they test prediction consistency. The pool store is never opened.
    - **Deviation from §5's cost estimate:** 124 solves were estimated and 120 are planned. This is recorded in the run record's `deviations`.
    - **Work directory.** Every `confirm-*` command refuses a `--work` directory inside the repository (review C3). Owner-only modes do not stop `git add`.
    - **Predictions.** Every panel member is rebuilt on the host CPU (`DirectBackend`), so predictions are not bit-identical to the A40 panel.
    - **Report** (descriptive, owner-only file):
      - each member's exam components and `control-exam-v1` score on the batch (the paired-repeat gate is exercised by its hidden duplicates);
      - gate optimism and near-limit false acceptance on the batch's important region, reported separately;
      - the adversarial check repeated on these scores.
    - It enters no verdict. The pre-registration assigns the batch no verdict role, so giving it one would be post hoc. Any publication of its aggregates waits for the Test Lead and owner (the L0 sheet's `fresh_attack_confirmation` expected result is HUMAN_INPUT).
13. **RULED: undefined values.** A reference failure or unresolved loss is excluded (NaN or None) as the pinned functions do. It is never a candidate failure.

## Runbook (exact tree)

1. **Exact tree.** After merge, main's tree differs from the reviewed head. EV5 therefore runs from a checkout of the **exact approved head commit** of this PR, never from main.
   - The run record's `execution` field says so.
   - Every analysis and confirmation output records `checkout_head` (`git rev-parse HEAD`).
   - `ev5_run verify` must pass in that checkout before each step.
   - Pods are dispatched from that same checkout.
2. **References and panel.**
   - Reference pods: `PC dispatch value_refs` with EV5's frozen plans.
   - Panel pod: `value_panel`.
   - Then `python -m carbon.battery.value import-references`, `import-predictions` and `evaluate` on the operator host's experiment root.
3. **Gate and selection.**
   - `ev5_run gate`, then `ev5_run select`.
   - Optimizer plans: `ev5.optimizer_plans`.
   - Optimizer pods; then `optimize import-references` and `optimize report`.
4. **Confirmation (host only, outside any live Graphite session).** `confirm-jobs` with the owner's deployment config, then `confirm-solve`, `confirm-predict` and `confirm-report`.
5. **Analysis.** `ev5_run analyse`, with the pod failure logs and the worker-boundary CI result at the exact head.

**Re-pin procedure** (after any change before the first solve, review B2):
1. `git rm docs/development/evidence/ev5-2026-10-03/run-record.json`.
2. `python -m carbon.battery.value.ev5_run pin`, then `python -m carbon.battery.value.ev5_run verify`.
3. Commit, and send the new head to the Test Lead and PR Head.

Once any EV5 solve has run, the record is never re-pinned. A change after that is a new run version.

## Validation

- `tests/cpu/test_battery_ev5_run.py` has known-answer fixtures for each verdict, passing and failing:
  - H1: PROMOTE and CONFIRMED, plus the gated secondary line, which never changes the outcome;
  - H2: HOLDS, DOES_NOT_HOLD and UNDEFINED;
  - H3: separation true and false;
  - adversarial: PASS and FAIL, including the last-ranked FAIL under negative scores and the literal-0 sensitivity line;
  - construction integrity: PASS, FAIL and INCOMPLETE, including a scan at another commit or with no run id;
  - the run record's refusals;
  - the confirmation batch check (fingerprint and sequence mismatch refused).
- The EV4 optimizer tests are unchanged and pass. A replay test (review C4) proves the edited optimizer reproduces EV4's committed member selection, verification jobs and report exactly.
- The review fixes have tests too: a gate-failing construction among mixed PASS/FAIL real members ranks strictly last (B1); a Mode X finding on a gate-failing member ranks last; H3 separation is UNDEFINED with an unmeasured real member (C1); a work directory inside the repository is refused (C3).
- Canonical `check_quality`.

## Maturity

IMPLEMENTED and TESTED (fixtures). Nothing is scientifically qualified. No LIVE, chain, reward or testnet-rule change.

## Hub impact

Primary `map_ref`: battery engineering value (EV5). This is engineering of an already-registered study, so the hub's purpose, placement, status and boundaries are unchanged.
