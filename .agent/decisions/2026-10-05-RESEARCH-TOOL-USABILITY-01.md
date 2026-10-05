## 2026-10-05 — RESEARCH-TOOL-USABILITY-01: dry_validate answers with the Challenge's submission compile, and new plans read a practice "null" as JSON null

**Authority.** The Test Lead approved this small usability PR after the
Graphite phase-4 session 1 triage, test side, under
OWNER-GRAPHITE-TEST-WAVE-03 (maximize discovery). The Test Lead chose the fix
for finding 1 ("dry_validate actually runs validate_for_challenge plus the
contract compile ... preferred over adding a label") and for finding 2
("accept the string "null" for practice's action and arguments under the
same frozen rule"). Engineering decisions within that approval, recorded by
the executor. No scientific value, threshold, gate, tolerance or economic
parameter changes.

**Found.** Graphite phase-4 session 1 (lessons entry
`2026-10-05-research-tool-usability`).

### D1. dry_validate runs the named Challenge's submission compile

**Observed.** `research.A2ValidationProvider.dry_validate` ran only Strategy
schema 1.0's structural check (`carbon/schema/strategy.py`, `dry_validate`).
It answered `valid` for kNN `neighbours: -5`, for family settings nested
under the family name, for a value-wrapped parameter and for excluded or
not-yet-rebuildable fields, all of which the real compile refuses.

**Decision.**

1. **One answer:** `research_service.submission_issues(strategy, challenge)`
   returns every issue `challenge_contracts.compile_submission` refuses the
   strategy with - structural validation, the named Challenge's contract
   (`validate_for_challenge`), then that Challenge's own compiler and backend
   rules - with the same code and path. A strategy naming another Challenge
   is refused as the B-02B compiler refuses it
   (`strategy.challenge_mismatch` at `/challenge_id`), never compiled under
   the other contract.
2. **Served by the composition:** `ChallengeContractValidation` replaces
   `A2ValidationProvider` in the shared DEVELOPMENT composition
   (`compose_research_service`) for every Challenge's parts. The GPU
   practice composition keeps A2 (`ChallengeParts.contract_validation=False`):
   its recipes are its own catalogue's, not Challenge submissions.
3. **A dry run.** It compiles in memory. It dispatches, admits, scores,
   charges, notes and stores nothing. Everything it needs is in the
   repository; nothing is fetched.
4. **Not versioned.** No frozen plan or tool text records dry_validate's
   behaviour: its description is unchanged ("Call authenticated
   dry_validate ...") and the protocol's operation matrix and result shape
   are unchanged. So there is no frozen record to replay, and this applies
   to every campaign from now on. A recorded verdict keeps its own digest.

### D2. argument-normalisation.v2 reads a practice "null" as JSON null

**Observed.** `start_research_task` with `kind=practice` and `action` sent as
the string `"null"` was refused at the miner door
(`miner_mcp/standard.py`, `_arguments`) with a bare `INVALID_ARGUMENT` and no
correction. Graphite's miner path passes `action` through unchanged, so the
model never saw how to fix it.

**Decision.**

1. **A new frozen version, v1 kept:**
   `research_tools.ARGUMENT_NORMALISATION_V2 =
   "carbon.autoresearch.argument-normalisation.v2"`. It reads everything v1
   reads (a workspace `strategy_json` `"null"`), and also a practice call's
   `action` and `arguments_json` sent as `"null"`, each as JSON null
   (`normalised_task_arguments`, `practice_null_fields`). A practice
   `strategy_json` `"null"` is still refused: practice needs a recipe. v1
   stays registered and unchanged, so a campaign that froze it reads it as
   before; an unknown rule is still refused.
2. **New plans freeze v2:** `battery.campaign.graphite_plan` and
   `challenge_registry.agent_plan.graphite_plan`. A new plan with v1 in
   place of v2 is byte for byte the plan the base commit froze (pinned).
3. **The request is the one real null builds; the ledger binds what was
   sent.** The SDK normalises a copy before it builds the request; the
   operation-id binding and journal keep the arguments as sent. The miner
   door lets a v2 `"null"` through unchanged to the SDK for the same reason.
4. **Older plans refuse as before, now with a correction.** Under no rule or
   v1 the door still refuses with `INVALID_ARGUMENT`, nothing dispatched,
   the SDK never reached and nothing bound. The `AdapterFailure` now carries
   the SDK's registered correction for the same request
   (`practice_recipe_required`, the field, the tool and, for `"null"`, that
   null means JSON null) in object terms. Graphite's miner path returns it
   (`correction_code`, `field`, `correction`). The MCP tool and the Tasks
   start name the field in their refusal line (`field=`). Each practice
   refusal at the door carries it, not only `"null"`.

**Versioning.** No tool text or role digest changes: `TOOLS` and
`TOOLS_V2` are byte for byte the base commit's (pinned), so Graphite's roles
and #610's tool-text record are untouched. The only versioned change is the
normalisation rule, v1 to v2, prospectively through the plan.

**Unchanged.** No scientific value, gate, threshold or tolerance. No economic
parameter. Nothing reaches a chain. No public interface field is removed. The
refusal line gains its existing optional `field=` part where a correction
names one. This is engineering evidence, not a security audit.

**Tests.** `tests/cpu/test_research_tool_usability.py` and its mutation
checks in `tests/cpu/test_research_tool_usability_mutations.py`;
`tests/cpu/test_battery_graphite_plan.py` now expects v2 in a new plan.
