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
section, two lessons, the ticket's phase-4 section and the two test files. The
challenge-neutral attack engine (`carbon.agent_campaign.attack`) is built by
the other slices; this driver codes against their interfaces.

**Decisions.**

1. **`AttackerProvider(Phase3Provider)`.** The Attacker session reuses #504's
   phase-3 harness, so it inherits the v2 session-limits rule (no session-turn
   cap and no per-role call cap; the grant's money cap and elapsed limit bind),
   the recorded context compaction, the parallel-call rule and the pods. It
   overrides only what the Attacker needs: the Attacker-only `start` guard, the
   `graphite-phase4` manifest tag, and an `_epoch` that wires `AttackerTools`
   and runs no delivery, bundle or stall escalation (an Attacker proposes no
   construction).

2. **`start` goes to the base provider.** `Phase3Provider.start` refuses any
   non-Constructor brief. After the Attacker-only check, `AttackerProvider.start`
   calls `GraphiteProvider.start`, not `super().start`, so the Attacker role
   opens. Recorded as a lesson.

3. **No call cap; money and time bind.** The session carries no operator call
   cap (`max_calls_per_run` is None). The one in-session resource rule is the
   code-run wall allowance from the adapter (`code_run_seconds`), enforced by
   `AttackerTools` before dispatch; a code run with no allowance or one over
   the ceiling is refused `REJECTED_BEFORE_DISPATCH`, and a timeout at the
   allowance is `FAILED_INFRA`, never a pass. The branch's 34-call cap and its
   per-session code-run count cap are dropped.

4. **The budget is six verify pods.** The Attacker's worst case rebuilds up to
   six attack constructions on their own pods (`ATTACKER_VERIFY_PODS`), so the
   driver rebuilds #504's budget at six pods. For `GRAPHITE-GRANT-PHASE4` that
   gives the owner-approved split: USD 1.48 of pods and USD 1.93 of tokens, the
   session's model-call money cap. Money, not a pod count, binds the run.
   Recorded as a lesson.

5. **`GRAPHITE-GRANT-PHASE4`, as proposed and approved.** Ceiling USD 10.50,
   cleanup USD 0.25, worst-case run cost USD 3.41, three runs, one concurrency,
   15,600 s runtime, expiring 2026-12-31, account `Carbon-Account`,
   `granted_by` owner. Derivation in `grants/README.md`
   (3 × 3.41 + 0.25 = 10.48 ≤ 10.50). The dry run copies this grant under a
   synthetic identity, changing only `grant_id`, `account`, `granted_by` and
   `expires_at`.

6. **Carbon's side through the engine.** The driver reads the session's journal
   (`attack.analysis`), maps attempts to families through the adapter,
   re-verifies and rebuilds on the pods (`attack.verify`), records a verified
   breach on the controller as a `FAILING_TRIGGER` (`controller.record_finding`,
   which stops expansion and refuses any condition outside the CONDITIONS
   vocabulary), writes attempts, findings and near-misses to the knowledge
   store, and produces the per-family report and B2 (`attack.report`,
   `attack.benchmark`). The coverage report claims neither security acceptance
   nor a grade.

7. **A live run is not executed here** (OWNER-GRAPHITE-ATTACKER-01 §5). The
   live path is implemented and tested with fakes; it runs only after the
   engine merges and the scripted dry run passes.

**Cross-slice dependency.** The driver codes against the interfaces published
for AT-A (`attack.engine`), AT-B (`attack.adapter`, battery Level 0, including
`code_run_seconds`, `recipe_outside_contract` and a baseline), AT-C
(`attack.analysis`, `attack.verify`, `attack.report`, `attack.benchmark`) and
AT-D (`attack.knowledge.AttackStore`). It reaches them only through
`phase4.attack_modules`, which the tests replace with fakes, so the slice
passes before those modules merge; integration wires the real ones.

**Unchanged.** The phase-3 Constructor path and its grant, every role but the
Attacker's prompt, the miner edition's digests, EV5 and sealed material, and
every existing plan, digest and replay.
