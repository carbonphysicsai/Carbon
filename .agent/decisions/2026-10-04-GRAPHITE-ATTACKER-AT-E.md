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
