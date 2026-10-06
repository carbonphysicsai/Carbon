## 2026-10-05 — GRAPHITE-ATTACKER-STOP-RULE-01: a phase-4 Attacker session ends through a finish tool once every reachable family has two attempts

**Authority.**
- The Test Lead approved this design on 2026-10-05, after triaging phase-4
  session 1 (`graphite-5dba40abea97545a`). It sits inside the owner-approved
  Graphite test wave (OWNER-GRAPHITE-TEST-WAVE-03 to -07) and is tied to
  GRAPHITE-D35, the Attacker's whole-context decision.
- It is a versioned test-side policy. It changes no construction contract,
  scientific value, gate, score, reward, settlement or miner-facing surface,
  and it involves no live run and no spend.

**Why.** Session 1 ended on a free-text turn after reaching only three
families, and two of its turns were cut off at 2,048 output tokens.

**Decision.**
1. **Versioned opt-in: `carbon.graphite.attacker-stop-rule.v1`.**
   - `AttackerProvider(stop_rule=STOP_RULE_V1)` freezes the rule into the
     session's `session_limits` record (`stop_rule`). `live_provider` and the
     dry run pass it, and so does prelive through `live_provider`.
   - `_expected_limits` and `offered_tools` follow the record. A session
     opened without the rule resumes without it, byte-identically. A session
     opened with it resumes only under the registered v1 record.
   - The brief must carry the rule exactly when the provider freezes it.
2. **Finish tool: `finish_attack_session`.**
   - It is a local terminal tool through `run_epoch`'s existing `finish`
     mechanism, and its accepted status is `ATTACK_FINISHED`.
   - It is refused (`finish_coverage_incomplete`, with the live coverage table
     and the families still short) until every reachable family has at least
     k = 2 counted attempts.
   - It is also accepted once the campaign ledger's money and provider-call
     ceilings can be sure of no more than `FINISH_NOTICE_CALLS` (2) model
     calls. That bound is computed as `budget_status` computes it, from money
     only and never the clock, so a replay recomputes the same answer.
   - Counted attempts are journalled tool calls mapped to a family by
     `analysis.family_of`. The loop's own answers to malformed calls (a
     `REJECTED_BEFORE_DISPATCH` with a loop refusal code) are not counted.
     Refusals made by the research path count as attempts.
   - The finish call itself probes nothing. Carbon's side and
     `attack_rejudge.py` leave it out of the attack attempts.
3. **Continue reminder (`carbon.autoresearch.continue-reminder.v1`, in
   `research_loop`, opt-in).**
   - A free-text turn gets the registered reminder, at most 2 in a row, and any
     tool call renews them.
   - The next free-text turn stops the session STOPPED with
     `stopped_no_tool_use`.
   - The plan records the rule only when it is set, so every earlier plan is
     unchanged. The legacy autonomous and Graphite-miner policies refuse it,
     because they keep their own reminder.
4. **Attacker output cap: 4,096 tokens (`ATTACKER_MAX_OUTPUT_TOKENS`).**
   - The loop admits a request only under `max_input_tokens` minus
     `CONTEXT_RESERVE_TOKENS` (4,096), so a request plus 4,096 output tokens
     still fits the model's context. That makes 4,096 the largest cap that
     leaves D35's whole input window unchanged.
   - The glm-5.2 reservation becomes 184,401,920 nano. That still allows 10
     full reservations in the USD 1.93 token allowance.
   - The Constructor keeps D34's table, and recorded sessions keep their
     frozen selection.
5. **Coverage table and labels.**
   - **The table.** The brief carries the table at 0 attempts, and every
     refused finish returns the live table. Reachable families are computed by
     probing `analysis.family_of` over every `kind`/`action` shape the offered
     tools' enums allow. Each row names its doors.
   - **Reachable families.** At Level 0 these are the same for battery,
     chip-cold-plate and motor: permission_ablation, practice_disclosure,
     recipe_surface, resource_accounting and staged_bytes. `staged_bytes` is
     reached by the workspace file, inventory, public-material and notebook
     actions.
   - **Labels.** Every other adapter family carries a label, never a silent
     NOT_RUN (Test Lead, 2026-10-05):
     - `mandatory_failure` and `recipe_forgery`: "not participant-reachable at
       this level". The deterministic harness (track_a) still covers both as
       Carbon-internal checks. Re-assess `mandatory_failure` at Levels 4–5.
     - `rebuild_identity`: "queued: cross-attempt identity oracle (WAVE-04
       §1)".
     - `rebuild_report`: "deferred: POD_REBUILD_SEAM not run".
     - Any other family no offered tool reaches, such as cooling's and
       motor's Challenge-specific families: "not participant-reachable at this
       level". This generic default was proposed to the Test Lead, and any
       family can be given its own label in `FAMILY_LABELS`.
   - **B2 scope.** B2 compares the Attacker only on reachable families, and
     the table says so.

**Unchanged.** Scientific, security and launch qualification stay
human-reserved. No verdict here is security acceptance.

**Addendum (2026-10-06): rule v2, deterministic coverage.** The Test Lead
ruled on 2026-10-05, under the owner's delegation, that three filter-stopped
Attacker items stay parked and that their risks are covered by deterministic,
boundary-side tests instead, recorded as "covered deterministically" and never
as a silent NOT_RUN. `carbon.graphite.attacker-stop-rule.v2` records this:
- `rebuild_identity` is labelled "covered deterministically: the no-op
  capability audit (#619) and the WAVE-04 artifact-identity tests (#607)";
- the coverage table and the frozen record list `hidden_outcome_channel`
  (#642's non-leak differential), `rotation_exhaustion` (#642's tempo and
  rotation tests) and the v2 practice safety block (#652's allow-list tests)
  as covered deterministically.
New sessions freeze v2. A session recorded under v1 resumes under its own v1
record, with the v1 labels and no deterministic list (invariant 10).
