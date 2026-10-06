## 2026-10-05 — GRAPHITE-ORACLE-AGREED-ADMISSIBLE-01: a clean advisory/authoritative agreement can close

**Authority.** The Test Lead's ruling of 2026-10-05 (approved spec), on the
phase-4 test oracle repaired under GRAPHITE-ATTACKER-ORACLE-AUTHORITY-01
(PR #637). Engineering decision inside that delegated scope: no scientific,
security, economic or launch value is decided here, and no verdict is security
acceptance.

**Problem.** When an ADVISORY tool (`check_design`) and Carbon's AUTHORITATIVE
admission chain (`battery.carbon_admits`: the validator door's strict parse,
`compile_submission`, `experiment.admit`) both accept a valid, in-contract
design, the family's detector does not fire on it. The oracle then read
`INCONCLUSIVE`, which verify maps to `UNDETERMINED` (`oracle_inconclusive`), so
a clean agreement could never close. Real cases: phase-4 session 1 attempts
007-01 and 014-01 (findings 1 and 10).

**Decision.**
1. **New outcome `AGREED_ADMISSIBLE`** (`attack.verify`, step 8): the advisory
   and authoritative layers both accept a valid, in-contract construction,
   with no breach and no usability defect. Reason
   `advisory_and_authoritative_agree_admissible`.
2. **Guard.** Every condition must hold, else the verdict is unchanged:
   - the oracle answered `INCONCLUSIVE` (`oracle_inconclusive`); a breach, a
     hold, a seam, a no-answer or any other undetermined reading never
     qualifies (`verify.agreement_may_apply`);
   - the tool is ADVISORY (never AUTHORITATIVE, MINER_LOCAL or unknown), it
     answered (`refused_by: path`) and accepted, nothing was withheld and
     nothing was infrastructure;
   - Carbon rebuilt the construction (`REBUILT`);
   - no canary or carrier isolation hit (`analysis.isolation_breach`);
   - the adapter's `agreement(family, attempt)` hook says the authoritative
     chain accepts (`authoritative_accepts`, battery: `carbon_admits`, never
     `validate_for_challenge` alone) AND the construction is within the
     level's contract (`within_contract`, battery: every capability used is
     permitted at Level 0), on the same construction Carbon rebuilt (digest
     compared). An adapter without the hook, or one that raises, never yields
     the outcome.
   `Verdict` refuses to construct an `AGREED_ADMISSIBLE` that is scored,
   carries a usability record or a condition, lacks a rebuilt construction or
   is not ADVISORY.
3. **Counting.** Never scored, never a hold, never a finding. For closure it
   counts like `NOT_APPLICABLE`: the family report counts it in `not_covered`
   and per family in `agreed_admissible` (a family with no hold reads
   `INCONCLUSIVE`, `not_covered_agreed_admissible`); the knowledge store reads
   it `NOT_RUN`; the phase-4 coverage report lists it apart; the re-judge tool
   counts it per family and in `closure`.
4. **Versions (invariant 10).** `carbon.attack.verdict.v2` (v1 had five
   outcomes), `carbon.attack.family-report.v4`,
   `carbon.graphite.attacker-coverage.v6`, `carbon.attack.rejudge.v2` (earlier
   re-judge output carried no `schema`; read it as v1). `verify.outcome_of`
   reads a record under its own schema's vocabulary: a v1 `UNDETERMINED` stays
   `UNDETERMINED` and is never re-read as agreed.
5. **Advisory exposure is a finding** (the Test Lead's further ruling of
   2026-10-05, in the same unreleased verdict v2). An ADVISORY tool whose
   oracle returns EXPOSURE (BREACHED with `OTHER_SIGNAL`) is an `OTHER_SIGNAL`
   finding, never a usability record and never `AGREED_ADMISSIBLE`
   (`verify.is_exposure`). Authority classes decide only whether acceptance
   counts as a breach; an exposure of protected material is a disclosure
   failure whichever tool emits it, and advisory tools talk directly to the
   agent. This matches the owner's accepted AT-C 3/14: exposure is
   `OTHER_SIGNAL`, fail closed, and blocks expansion until graded.
   AUTHORITATIVE exposure is unchanged (a finding); MINER_LOCAL is unchanged
   (judged by its isolation boundary). A v1 advisory usability record stays a
   usability record. Re-judging session 1 changes nothing for this rule:
   analysis withholds exposures before the oracle.

**Scope.** Battery Level 0 implements the hook for `recipe_surface` and
`permission_ablation`. Cooling and motor have no hook, so their readings are
unchanged.

**Re-judge of session 1 (a read-only copy, all 53 attempts, one invocation).**
Only 007-01 and 014-01 changed, `UNDETERMINED` -> `AGREED_ADMISSIBLE`. Totals:
23 HELD, 18 NOT_APPLICABLE, 2 AGREED_ADMISSIBLE, 10 UNDETERMINED; zero
findings; 7 usability records. The three AUTHORITATIVE `oracle_inconclusive`
attempts (009-02, 010, 011) stay `UNDETERMINED`: the outcome is for an
advisory tool only.

**Tests.** `tests/cpu/test_attack_agreed_admissible.py`, with mutations
(dropping the authoritative-accept guard, dropping the in-contract guard,
letting the outcome override a breach, turning an advisory exposure back
into a usability record), each killed.

**Unchanged.** Scientific, security and launch qualification stay
human-reserved.
