## 2026-10-03 — GRAPHITE-MINER-S1: the research loop's stages, finish tool, miner policy, tunable limits and context compaction

**Authority.** Delegated engineering decisions (executor, slice S1 of the
Graphite miner edition), within OWNER-GRAPHITE-MINER-01 (items 1, 2 and 6:
one engine, two editions; the miner edition's roles; "generous and tunable
limits", money and time as the limits, and explicit, recorded context
compaction as a versioned rule for new runs), OWNER-LAUNCHPAD-PROD-01 (its
boundaries and LP-PROD-A's loop rules) and OWNER-LAUNCHPAD-PROD-02 (decision
1: only a cap the miner sets binds, the miner's economics being the miner's
choice; decision 4: `PARALLEL_CALLS_V2`). Nothing here changes a scientific
value, threshold, gate or tolerance, live economics, a chain write or weight,
an authority boundary, a grant, or what reaches a miner. Results stay
DEVELOPMENT.

**Why it is needed.** The miner edition runs a Planner session and a
Constructor session inside one epoch of the miner's campaign, ends the
Planner with its own terminal tool, runs closed roles with a Challenge under
the rules Carbon's autonomous agent has, and must not be held to 48 model
calls and 8 trials when the miner's own money and time are the limits. A long
session must also go on past the context ceiling without dropping history
silently. The research loop (`research_loop.run_epoch`) supported none of
this.

**Decisions.**

1. **Default-off and versioned.** `run_epoch` gains `stage`, `finish`,
   `limits` and `compaction`, each defaulting to None, and the policy value
   `GRAPHITE_MINER`. With every default, plans, prompts, requests,
   identities, journals and outcomes are byte-identical to the Launchpad
   wiring head (9bfd9add): pinned in `test_research_loop_limits` for no rule,
   v1, v2 with a Challenge and the miner's messages, and an internal Graphite
   role (omitted or passed as None), and in `test_agent_operating_rules` for
   every v1 and v2 prompt, binding and shared rule text. The shared rule
   texts became unit-parametrised functions (`argument_limits`,
   `selection_rule`, `free_text_rule`, `context_rule`,
   `capture_limits_rule`) whose epoch default is the historical text.

2. **Stages.** A stage is a closed name, `[a-z][a-z0-9_]{0,31}`, never
   `provider`, `tool` or `compact` (they name identity kinds), so an identity
   parses one way. A staged session's folder is `epoch-N/<stage>/`, its
   identities `epoch-N-<stage>-provider-NNN`, `epoch-N-<stage>-tool-NNN[-KK]`
   and `epoch-N-<stage>-compact-NNN[-KK]`, and its start operation
   `research-epoch-N-<stage>` reserves no epochs unit, so several sessions
   share one epoch. A session's outcome counts only its own turns
   (`session_turns`); the unstaged epoch now excludes staged turns, a no-op
   for every earlier campaign, whose turns are all `epoch-N-provider-NNN`.
   The two finite epochs are unchanged. A staged selection writes
   `epoch-N/<stage>/selected-recipe.json`, not the epoch's.

3. **A caller's finish tool.** `finish = {tool, validate, status}` is a role's
   own local terminal tool. Its result is computed before its intent is
   journalled, like the selection: the accepted record (`status`, `tool`,
   `arguments`, `authority_granted: false`, `final_evidence: false`) ends the
   session, or the validator's own REJECTED_BEFORE_DISPATCH refusal (or
   `finish_invalid`) is answered and the session goes on. A finish status is
   its own uppercase code, never one of the loop's. A replay reads the
   journal and does not ask the validator again.

4. **The Graphite miner policy** (`carbon.autoresearch.agent-policy.
   graphite-miner.v1`). It runs a role's own instructions and tools, with or
   without a Challenge, and only under `PARALLEL_CALLS_V2`. As for Carbon's
   autonomous agent: results reach the model as `model_view` shows them, a
   selection needs a completed practice (`practice_check`), the stop tool
   ends the session when the role offers it, one free-text reminder is given
   and renewed by any tool call, and the miner's messages may be read (the
   reply tool is added). The loop states its operating rules after the
   role's instructions (`graphite_miner_prompt`): every number from the value
   that enforces it. The reminder names only the ways to continue or end the
   role offers. The plan's policy binding records the full prompt's digest,
   the instructions' own digest, the stop tool and the reminder's digest.

5. **The miner's messages in a staged session.** `miner_guidance` reads and
   verifies records named for the unstaged epoch, and is not this slice's
   file. The loop therefore gives staged records the same semantics itself:
   one campaign-wide cursor over every record, the same record shape and
   chain, carry-forward from every other session, and replies to any message
   delivered (`guidance_step`, `guidance_verify`, `guidance_reply`,
   `guidance_cursor`, `guidance_delivered`). A campaign with no staged
   session still runs on `miner_guidance` itself, byte for byte.

6. **Tunable limits** (`LIMITS_V2`). The per-epoch model-call and
   research-trial caps are optional; unset leaves only the campaign ledger's
   ceilings (provider spend, provider calls, research trials, elapsed time).
   The loop stays finite through the ledger: a session with no call cap
   needs a finite provider_attempts ceiling, or a provider_nanodollars
   ceiling with a priced selection, and refuses to start otherwise, before
   anything is written. Under the rule the agent sees, before each turn, the
   optional caps and what the campaign ledger still holds
   (`turn-status.v2`), and is told to finish when the calls the budget is
   sure of reach `FINISH_NOTICE_CALLS`. A plain ledger refusal propagates as
   it always did; a ledger that refuses with the new `CeilingReached` (the
   miner edition's stage ledger, `research_share_reached`) ends the session
   STOPPED with that code, nothing of the refused call reserved. A plan
   without the rule keeps 48 and 8 exactly. Limits, compaction and finish are
   a role's only; Carbon's autonomous epoch is unchanged.

7. **Context compaction** (`COMPACTION_V1`: trigger 0.85, keep the last 6
   turns, both from the agreed design). When a turn's request would pass 85%
   of the admission ceiling while the conversation holds more than 6 turns,
   the loop asks for a compaction with one model call, journalled and
   metered like any other (`epoch-N[-<stage>]-compact-NNN`). The compaction
   request is an append to the last request - the same instructions and
   tools, the history, then a note - so its admission bound stays exact; the
   compaction tool is therefore offered from the first turn, and refused
   (`compaction_not_requested`) whenever it was not asked for. The summary is
   a closed schema of five text fields. With a valid summary the history
   becomes the initial observation, the summary - labelled as the model's
   own, naming the turns that left - and the last 6 turns unchanged; the
   record (`epoch-N[-<stage>]-compact-NNN.json`) names the turns summarised
   and kept, the dropped items' count and digest, the summary and the
   message. The compacted request is admitted under the compaction request's
   reported tokens plus the summary's bytes, a sound bound because it is a
   subsequence of that request plus the summary. Compaction calls count
   against a set per-epoch call cap. With no valid summary after a second,
   firmer request the session stops typed (`compaction_failed`), and a
   request that cannot fit even so stops typed (`context_ceiling`); nothing
   is ever dropped silently. A replay recomputes the same decision from the
   recorded turns and the journal refuses a differing record.

8. **Operational bounds chosen here** (engineering values, not science or
   economics): a tunable cap is at most 100,000; a summary holds at most
   12,000 characters in all, so it fits the headroom the 85% trigger leaves;
   a compaction makes at most 2 requests.

**Handoffs.**
- S3 (driver, provider plan): pass `agent_policy=GRAPHITE_MINER`,
  `parallel_calls=PARALLEL_CALLS_V2`, the frozen `limits`/`compaction`, a
  `stage` per session and the Planner's `finish`; freeze the role prompt and
  tool manifest digests knowing the loop appends its operating rules
  (`graphite_miner_prompt`) and the finish, reply and compaction tools
  (`session_tools`). A StageLedger proxy must forward `root`, `reserve`,
  `_reserve`/`finish`, `status` (with `budget`), `checkpoint`, `note`,
  `admission`, `clock`, `check_storage` and `db()` (`practice_check` reads
  it), raise `research_loop.CeilingReached("research_share_reached",
  dimension=...)` from `reserve` past the share and never refuse an identity
  it already admitted. A staged Constructor's selection is
  `epoch-N/<stage>/selected-recipe.json`; the shared
  keep-unevaluated-candidate helper must read it there.
- S4 (views): staged miner-guidance reads are visible through
  `research_loop.guidance_delivered`, not `miner_guidance.delivered`.
- S6 (internal Graphite): `limits=LIMITS_V2` replaces `max_provider_calls`
  (both together are refused), and `compaction=COMPACTION_V1`; the internal
  ledger's provider_attempts or money cap satisfies the finite-ledger rule.
  `limits_rule` and `compaction_rule` give the texts for its own prompts.

**Unchanged.** The boundaries OWNER-LAUNCHPAD-PROD-01 lists; every
scientific value, threshold and gate; no hidden-test access, no chain writes,
no weights; every frozen plan replays byte-identically.
