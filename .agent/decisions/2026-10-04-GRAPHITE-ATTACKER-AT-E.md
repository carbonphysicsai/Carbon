## 2026-10-04 — GRAPHITE-ATTACKER-AT-E: the phase-4 Attacker session driver, its grant and records

**Authority.** OWNER-GRAPHITE-ATTACKER-01
(`.agent/decisions/2026-10-04-OWNER-GRAPHITE-ATTACKER-01.md`), recorded again
as OWNER-GRAPHITE-TEST-WAVE-01 §2 (carbonphysicsai/Carbon#556). Everything
below is an engineering choice within slice AT-E's delegated authority. No
scientific value, threshold or gate changes, no weights, no chain writes, and
no live run happens in this work.

**Scope.** This slice is the phase-4 session driver
(`carbon/agent_campaign/graphite/phase4.py`), the Attacker role's prompt
wording (`roles.py`), the live grant `GRAPHITE-GRANT-PHASE4` and its README
derivation, the owner decision record (copied verbatim), the phase-4 doc
section, the lessons, the ticket's phase-4 section and the two test files. The
challenge-neutral attack engine (`carbon.agent_campaign.attack`) is built by
the other slices; this driver calls their published interfaces.

**Decisions.**

1. **`AttackerProvider(Phase3Provider)`.** The Attacker session reuses #504's
   phase-3 harness, so it inherits the v2 session-limits rule (no session-turn
   cap and no per-role call cap; the grant's money cap and elapsed limit bind),
   the recorded context compaction and the parallel-call rule. It overrides
   what an Attacker does differently: the Attacker-only `start` guard with an
   adapter brief check, the `graphite-phase4` manifest tag, an experiment with
   no baseline, the frozen session record, and an `_epoch` that wires
   `AttackerTools` and runs no delivery, bundle or stall escalation.

2. **`start` goes to the base provider.** `Phase3Provider.start` refuses any
   non-Constructor brief and checks battery's baseline. After the
   Attacker-only check and the adapter brief check
   (`check_attacker_observation`: identity, contract token and digest, level,
   families and code-run allowance must be the adapter's; no baseline),
   `AttackerProvider.start` calls `GraphiteProvider.start`. Recorded as a
   lesson.

3. **No call cap; money and time bind.** The session carries no operator call
   cap. The one in-session resource rule is the code-run wall allowance from
   the adapter (`code_run_seconds`), enforced by `AttackerTools` before
   dispatch. The frozen session record states what the Attacker does:
   `pods_per_session: 0`, `verify_pod_rebuild: NOT_RUN`,
   `code_run_seconds_at_most`, `on_limit_stop: record_attempts_only`, and none
   of the Constructor's pod-admission, stall or bundle fields.

4. **The budget is six verify pods.** The grant's worst case budgets six verify
   pods (`ATTACKER_VERIFY_PODS`), so the driver rebuilds #504's budget at six
   pods: USD 1.48 of pods and USD 1.93 of tokens, the session's model-call
   money cap. Recorded as a lesson.

5. **`GRAPHITE-GRANT-PHASE4`, as proposed and approved.** Ceiling USD 10.50,
   cleanup USD 0.25, worst-case run cost USD 3.41, three runs, one concurrency,
   15,600 s runtime, expiring 2026-12-31, account `Carbon-Account`,
   `granted_by` owner. The token share is the run cost less the pods
   (3.41 − 1.48 = 1.93, about 40 glm-5.2 calls); 3 × 3.41 + 0.25 = 10.48 ≤
   10.50. The dry run copies this grant under a synthetic identity.

6. **Carbon's side through the published engine.** `carbon_side` calls:
   `analysis.attempts` → `analysis.map_to_families` → `verify.verify(attempt,
   adapter, pods=None, family=..., specimen_dir=<store>/specimens)` per
   attempt → for a finding, `verify.record` (which calls
   `controller.record_finding` and returns the finding ids) →
   `knowledge.AttackStore.add_attempt` / `add_near_miss` / `add_finding` with
   their keyword fields → `report.attacker_runs` and `report.family_report`
   (with `adapter.held_out_outcomes` rows and `adapter.level_families()`
   seams) → `benchmark.b2(attacker_runs, adapter.run_adapter(adapter,
   budget=8), store_snapshot=<pinned digest>, ...)`.

7. **A finding is the published Verdict's.** A verdict is a finding exactly
   when `outcome == BREACHED`, and then its `conditions` are non-empty; a
   verdict where the two disagree is refused (`verdict_breach_and_conditions_
   disagree`), never read as a pass. Every id `verify.record` returns is
   recorded.

8. **Store outcomes.** Every verdict is written with its own outcome:
   `BREACHED`; `UNREBUILDABLE`; `HELD` (the path's own hold); `NOT_RUN` for
   Graphite's own refusal, `UNDETERMINED` and `NOT_APPLICABLE`; `TIMEOUT` or
   `CRASH` for `INFRA`. A near miss is written only when the verdict says
   `near_miss`. A finding's `rebuilt` is True unless the construction was
   unrebuildable (an attempt that carried no construction was re-run by
   Carbon's own oracle as given), so the store refuses, typed, a finding on an
   unrebuildable construction while the controller still records it. A family
   boundary the store's sealed or held-out markers refuse is stored under the
   family name. Every store refusal is listed in the coverage report.

9. **The store snapshot is pinned before the session.** The driver snapshots
   the store before a session opens and records the digest under
   `pins/session-N.json` (a resume reuses it). The brief carries the digest
   and the per-family counts (`priors(challenge)["by_family"]`, without
   boundary text); B2 records the same digest; Carbon's side checks the pinned
   view still replays whole. This is how the engine improves as it goes: a
   later session's brief carries what earlier ones taught.

10. **B2's deterministic side is the adapter's own engine runs.** The driver
    uses `attack.adapter.run_adapter(adapter, budget=ATTACK_BUDGET)`, which is
    Challenge-neutral; for battery its families wrap `track_a`'s boundaries
    plus the adapter's added families. `benchmark.track_a_baseline()` is the
    literal `track_a.run()` alternative if the Test Lead prefers it.

11. **Seam: Carbon's verify-pod rebuild is NOT_RUN.** No pod is launched in
    phase 4 and `verify` receives no pod build records, so an attempt the path
    says ran on a pod is `UNDETERMINED`. The live runner uses `NoVerifyPods`,
    which refuses a launch before any provider write; it needs no RunPod key.
    The grant keeps the pods' share reserved. Wiring the pod rebuild is a
    later change.

12. **Neutral session surface.** The brief, identity, wall allowance and the
    dry run's refused recipe come from the adapter
    (`public_identity`, `code_run_seconds`, `recipe_outside_contract`); a
    missing one is refused `adapter_session_surface_missing: <name>`. The
    driver never substitutes battery's values. Seams are listed in the brief by
    name only, since the Track A check name `fresh_attack_confirmation` trips
    the protected filter.

13. **The live runner's safety.** The live path checks the checkout is this
    HEAD, pushed and clean (`phase3.check_code_ref`), installs #504's
    SIGINT/SIGTERM cancel handler, and adds `cancel` and `status`
    subcommands. With no pod there is nothing to reconcile.

14. **A live run is not executed here** (OWNER-GRAPHITE-ATTACKER-01 §5). The
    live path is implemented and tested with fakes; it runs only after the
    engine merges and the scripted dry run passes.

15. **Every Track A check is named in the coverage report** (integration
    round 1). The integrated dry run showed every NOT_RUN seam row with
    `check: None`, because the engine's report keeps only a seam's name and
    reason. Battery's `fresh_attack_confirmation` is covered only by seams, so
    no row named it. The report fix belongs to AT-C (`report.seam_names` /
    `summarize` must carry `SeamFamily.check`). The driver's own coverage
    output (schema bumped to `carbon.graphite.attacker-coverage.v3`) adds a
    per-check view, `checks`. It takes each family's check from the adapter's
    declarations and never from a report row. It lists all eight checks,
    names checks nothing declares (`undeclared`), and lists rows that lost
    their check (`report_rows_without_check`). It refuses a row whose check
    disagrees with the adapter (`report_check_disagrees_with_adapter`). The
    engine-path tests assert that all eight checks appear, that every report
    and B2 row names its check, and that nothing is undeclared. They fail at
    the integration head until AT-C's fix lands, and pass once it does
    (checked with a simulated fix in a probe).

**Tests.** The session-side tests use a stand-in adapter and stub Carbon's
side. The engine-path tests use the real modules with a synthetic second
Challenge and battery's Level 0 adapter, and skip until the modules are
importable. Each boundary this slice owns has a mutation that turns a named
test red: a call cap in the dry run or in the loop arguments; a lifted
`code_run_seconds`; a real Verdict read as no finding; infrastructure stored as
a hold; a near miss for every non-finding; battery's identity substituted for a
missing surface; an unchecked brief; B2 without the pinned snapshot; the
Constructor's stall rule frozen into the record; a per-check view that ignores
the adapter's seams. Allowing expansion after a
finding turns the breach test red through the controller.

**Unchanged.** The phase-3 Constructor path and its grant, every role but the
Attacker's prompt, the miner edition's digests, EV5 and sealed material, and
every existing plan, digest and replay.

### 2026-10-04 — Repairs after Test Lead review (#563)

The Test Lead's review of the integrated head 47baa0db5 found five defects
that must be fixed and one item needed before the first live run. Each repair
below is an engineering choice within the slices' delegated authority. None
changes a scientific value, threshold or gate, EV5 or sealed material, the
live construction contract or the expansion records, and battery's
`track_a` output stays byte-identical (its digest test still pins it).

1. **M1: every finding reaches the controller.** Before, only the Attacker's
   verdicts were recorded (`verify.record`). Now a held-out control the
   boundary wrongly refused (from the family report) goes through
   `verify.record_control`, and a breach or refused trained control in the
   deterministic baseline run (B2's other side) goes through
   `verify.record_engine_findings`. Both use the same
   `controller.record_finding` path, so any of them stops expansion. The
   coverage report lists findings by source (`findings_by_source`; coverage
   schema v4). Every finding is bound to digest evidence. Report findings
   now carry an `evidence_digest`, and a control finding names the control's
   registered identity, its input digest and its outcome (report schema
   v2). An engine control record on the adapter path binds the same three
   fields. `engine.findings` binds a control finding with
   `control_evidence`, never `digest(passed)`. The `valid_control` record of
   battery's own harness keeps its bytes, so the track_a pin holds.
2. **M2: the suite version pins the store.** `challenge_pipeline.suite.run`
   takes the store pin (`ReadOnlyView.suite_pin()`) and records
   `attack_knowledge_digest` in the run's record (suite-run schema v2). A
   malformed pin is refused. The driver's replay guard
   (`phase4.replay_guard`) checks the pinned view against the session's
   independently recorded pin file through `ReadOnlyView.replay_recorded`,
   never against itself. A resume refuses a missing pin
   (`session_pin_missing`). A pin whose schema, session number, digest or
   keys are wrong is refused (`session_pin_malformed`). Nothing re-snapshots
   silently.
3. **M3: grant amounts are pinned at runtime.** `check_committed_grant`
   refuses a live run unless the grant file's canonical digest equals the
   committed `GRAPHITE-GRANT-PHASE4.json`'s
   (`grant_differs_from_the_committed_phase4_grant`). The check covers every
   field, so a raised ceiling is refused before the credential is read.
4. **M4: a refusal at the rebuild step is not held coverage.** An attempt
   Carbon could not rebuild that is not a breach is counted
   `refused_at_rebuild` and excluded from its family's `held`. Alone, it
   leaves the family INCONCLUSIVE (`refused_at_rebuild_only`).
5. **M5: held-out controls are real and reported.**
   - Wrongful rejection is a rate (`rate`, `status`), with held-out reported
     apart from trained, per family and in total.
   - An empty held-out set is `NOT_MEASURED` with rate None. So is a family
     that only cites evidence; it is never skipped.
   - The driver's coverage report carries `adapter.wrongful_rejection` per
     family.
   - Battery's held-out controls for `practice_disclosure` and
     `mandatory_failure` were canonically identical copies of the trained
     values. They are replaced with genuinely different valid inputs: the
     public PRACTICE references at single precision, rounded to six
     decimals, and two different probes in one session. Each passes the
     real boundary. `CONTROLS_VERSION` moves to v2.
   - `adapter.validate` refuses any held-out control that is canonically a
     trained one.
   - The engine refuses held-out controls by registered identity (the
     family and the input digest; not the name, version or split). A
     relabelled held-out control is therefore still refused. Identities are
     registered when an adapter is validated or measured; the engine's run
     still never reads the held-out split.
6. **F1: protected detection by registered identity.**
   - `knowledge.SEALED_IDENTITIES` lists only public identities already
     committed, each with its source record:
     - the EV5 confirmation fingerprint, journal sequence 14 and the
       `ev5-confirmation` role;
     - the motor private-pool commitment `sha256:5ec0222…`;
     - the `graphite-confirmation-v1` role;
     - cooling's final decision-evaluation condition ids (`rep-01` to
       `rep-04`, `boundary-01`, `boundary-02`).
   - Nothing sealed is read.
   - Matching runs after NFKC, invisible-character removal, casefolding and
     separator normalisation. A digest matches by its hex, whole or by a
     prefix of seven or more characters as its own token.
   - The store's protected rule (`knowledge.protected`) keeps Graphite's
     markers and the deny fragments that name sealed or confirmation
     material (`ev4`/`ev5` at a token start, `confirmation`, `canary`).
   - It no longer uses `.env`, `secret`, `credential`, `tests/`,
     `carbon/agent_campaign/`, `.agent/` or `docs/development/evidence/`.
     Those name attack targets, not material, and the store holds attack
     inputs and digests, never results.
   - A real sandbox-escape breach therefore keeps its FAILING_TRIGGER
     condition and its regression specimen in the operator-side store.
     `verify`'s specimen bundling uses the same rule.
   - Graphite's live request filter (`graphite.tools.protected`) is
     unchanged.
7. **Owner addition (OWNER-GRAPHITE-TEST-WAVE-02).** AT-B-D5 is accepted as
   designed. An attempt withheld because it names protected material
   (battery's `PROTECTED_WITHHELD`) now carries that reading through the
   oracle (`OracleResult.reading`) into the verdict
   (`oracle_protected_withheld`). The report counts it under `not_covered`
   and `protected_withheld`, never as held or covered, and lists the family
   under `not_covered`.

**Tests.** Each repair has its own tests, and each boundary has a mutation:
- a wrongly refused held-out control blocks the next expansion;
- a baseline breach is recorded;
- a deleted pin refuses the resume;
- a mismatched digest refuses the replay;
- a tampered grant copy is refused;
- a refused-at-rebuild attempt is never held;
- a protected-withheld attempt is not covered;
- an empty held-out set is NOT_MEASURED;
- a relabelled held-out control is refused;
- held-out and trained battery controls are canonically distinct;
- sealed identities match after case, separator and Unicode variants;
- a real breach keeps its condition and specimen;
- the over-broad fragments no longer misclassify.

**Follow-up (separate PR).** The review's follow-up list is not done here.
Seen during this repair and left for the same follow-up PR:
- `attack.analysis` and `verify.finding_body` still use Graphite's full
  request filter. A session result that names an attack target is still
  read as an exposure (`OTHER_SIGNAL`) at the analysis step.
- The held-out identity registry is process-wide and only grows.
- Unicode confusables beyond NFKC (for example Cyrillic look-alikes) are not
  folded.
- A check-only control that declares no input is identified by its family
  and name.
- `SUITE_V1_BATTERY_COVERAGE.json` is a suite-run v1 record with no store
  digest. It should be regenerated canonically.
