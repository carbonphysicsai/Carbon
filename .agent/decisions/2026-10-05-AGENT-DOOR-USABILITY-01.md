## 2026-10-05 — AGENT-DOOR-USABILITY-01: every new plan freezes argument-normalisation.v2, the MCP door agrees with it and corrects instead of dumping, phase-3 sessions drop the unmetered trial line, and an unserved-backend refusal lists the served backends

**Authority.** An owner request relayed by the Graphite Test executor on
2026-10-05 (findings A1, A2, A5, A6 and A7 of the Graphite Launchpad findings
list): the owner wants an application that is friendly to both humans and
agents. For A5 the Test Lead approved the versioned rule (the pinned pre-D34
replay keeps v1 bytes; new phase-3 sessions record v2). Engineering decisions
within that request, recorded by the executor. No scientific value,
threshold, gate, tolerance or economic parameter changes. Nothing caps a
miner campaign.

### D1. Every new plan freezes argument-normalisation.v2 (A1)

**Observed.** Only the Graphite plan builders froze
`ARGUMENT_NORMALISATION_V2` (RESEARCH-TOOL-USABILITY-01). An agent-none plan
(the miner's own agent, through the miner MCP door) and an autonomous plan
froze no rule, so a practice `action` or `arguments_json` sent as the string
`"null"` was refused there.

**Decision.** Both plan builders (`battery.campaign.provider_plan` and
`challenge_registry.agent_plan.provider_plan`, which cold plate and motor
use) freeze v2 in the agent-none and autonomous plans too. These are every
builder of a campaign run plan: the Burgers campaign records a model
selection under `provider`, not a run plan, and no tools rule either; it stays
the historical campaign. A plan already recorded keeps its rule (none, v1 or
v2): the rule is read from the frozen manifest, never from the builder. The
autonomous plan without the new key is byte for byte the plan the base
commit froze (pinned digest).

### D2. The MCP door's argument model follows the frozen rule (A2)

**Observed.** `carbon_research_v2__start_research_task` on the miner MCP door
refused `action: "null"` in the schema library (`literal_error`) before the
adapter, which already reads it under v2, was reached; and every schema
refusal was the library's dump, which repeats what was sent.

**Decision.**

1. **Schema by rule.** The door reads the bound campaign's frozen rule
   (`ResearchToolAdapter.argument_normalisation`; an unknown rule is described
   as none). Under v2 the start schema admits the string `"null"` for
   `action` and `arguments`; the call reaches the adapter, which passes it to
   the SDK as sent, so the request is the one real null builds and the ledger
   binds what was sent (RESEARCH-TOOL-USABILITY-01 D2.3). Under no rule or
   v1 the published tools are byte for byte the base commit's (pinned
   digests). This is the prospective, versioned change: the version is the
   normalisation rule the plan froze, not a new tool text, so no role or
   tool-text digest moves (#610's records are untouched).
2. **A typed correction, never a dump.** Every schema refusal on this door's
   research tools, and on the Tasks start, is now `INVALID_ARGUMENT`, nothing
   dispatched, the declared field (`field=`, only a name this server
   declared), the fixed next action, and a registered correction
   (`correction_code=`, `correction=`) appended last
   (`standard_server.validation_refusal`). The code agrees with the SDK's
   for the same request (`practice_recipe_required`,
   `workspace_recipe_forbidden`, `workspace_action_unknown`,
   `json_object_required`, `tool_text_bounded`, `tool_value_invalid`,
   `tool_field_missing`, `tool_field_unexpected`). A key that is the SDK's
   name for an object field (`strategy_json`, `arguments_json`) is answered
   with the field this server takes (`object_field_named`, door-only text).
   A key the caller invented is never named back. A value is only compared
   with `"null"`, never repeated.
3. **hypothesis and expected_effect.** Both are declared top-level fields of
   this door's start schema and of the SDK's (`research_tools.FIELDS`), and
   the service takes them; nothing to add. The `extra_forbidden` pair in the
   finding cannot come from them on the current door; the likeliest source
   is an SDK-shaped call (`strategy_json`, `arguments_json`), which D2.2 now
   answers by name.

**Public interface.** The start schema of a campaign that froze v2 gains
`"null"` in `action`'s enum and as a value of `arguments`. The refusal line
gains two optional trailing parts (`correction_code=`, `correction=`) on a
schema refusal only; every earlier part reads as before, and an adapter
refusal's line is unchanged. No field is removed or renamed.

### D3. Phase-3 sessions record budget-status.v2 (A5)

**Observed.** Every phase-3 turn status said "0 of 0 research trials left in
the campaign budget": the run ledger meters no research trials (its budget
is 0); a phase-3 experiment runs on pods, bounded by the run's money cap and
pod limit. #637 made dropping the line opt-in (`omit_unmetered_trials`) and
set it for the Attacker.

**Decision.** `phase3.BUDGET_STATUS_V2 = "carbon.graphite.budget-status.v2"`.
A new phase-3 session records it in its session-open record
(`budget_status`, through the provider's new `opening_rules` hook) and runs
with `omit_unmetered_trials=True`. A session whose record names no rule -
every one opened before, including the pinned pre-D34 session - keeps the v1
status bytes on replay and on resume; an unknown rule resumes nothing
(`budget_status_unknown`). The Attacker records no rule: it already omits the
line unconditionally, so its records are unchanged. The pre-D34 replay test's
emulation of the old opener now also opens with no rule, as that code did;
its pinned digests are unchanged.

### D4. Trials left are visible; a miner-set agent reserve is proposed (A6)

**Checked.** The turn status already names the trials left on every turn
wherever the ledger meters them: `budget_status` (LIMITS_V2 sessions:
Graphite's miner edition and Graphite's own roles) names the campaign's
research trials left and any per-epoch slot cap the miner set; `turn_status`
(the v2 autonomous agent) names its slots, clamped to the miner's own
research-trial budget. Neither invents a count where none is set. Tests now
pin this. The miner MCP door (agent none) has no per-turn status: the miner's
own agent drives itself there, and adding a budget to a tool result would
change a public result shape, so it is left for a separate decision.

**Proposal, not implemented.** A launch field `agent_trial_reserve`
(optional, default none) by which the miner reserves research trials of
their own campaign ceiling from Carbon's agent: the agent's trial limit would
be the ceiling minus the reserve, recorded in the frozen plan, and the miner
keeps the rest for their own follow-up or the operator. It would never be a
Carbon default: a miner only ever runs out of a budget they set themselves.
Graphite's launch already lets the miner set `limits.trials_per_epoch`, which
covers it per epoch there. It touches the Launchpad launch schema, so it
waits for an owner decision.

### D5. An unserved-backend refusal lists the served backends (A7)

**Observed.** A phase-3 proposal on a backend the pods do not serve (FNO with
`backend: pytorch`) was refused `backend_not_served:pytorch` with no list of
what would be accepted. The SDK's practice refusal (`backend_not_served`)
already lists the served backends, and the autonomous and Graphite miner
observations already list `practice_backends`.

**Decision.** The phase-3 refusal record carries `served_backends`, the
Challenge scoring record's public `served_backends`, and the agent's
feedback view passes it through. A result recorded before has none and is
read as it was. A recipe the contract refuses (`recipe_rejected`) already
returns each issue's code and path. No hidden or sealed material is read.

**Unchanged.** No scientific value, gate, threshold or tolerance. No economic
parameter and no Carbon-side cap. Nothing reaches a chain. This is
engineering evidence, not a security audit.

**Tests.** `tests/cpu/test_agent_door_usability.py`; updated pins in
`tests/cpu/test_battery_graphite_plan.py`, `tests/cpu/test_lp_prod_wiring.py`,
`tests/service/test_battery_mcp_research.py` and the pre-D34 emulation in
`tests/cpu/test_graphite_phase3.py`.
