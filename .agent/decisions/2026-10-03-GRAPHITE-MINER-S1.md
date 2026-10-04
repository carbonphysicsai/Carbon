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
   its own uppercase code, never one of the loop's, and it ends the session
   only as the finish tool's own result: another tool's result that carries
   the same status does not. A replay reads the journal and does not ask the
   validator again. The validator reads model-written arguments after the
   reply is journalled, so nothing it does is raised: an exception is
   answered `finish_invalid` naming the exception's type (malformed
   `plan_json`, for example), and a verdict outside `(ok, refusal)` or a
   refusal that is not a JSON REJECTED_BEFORE_DISPATCH record is answered
   `finish_invalid` with `checked: false`, saying the fault is not the
   model's. Either way the session goes on and every resume replays it.

4. **The Graphite miner policy** (`carbon.autoresearch.agent-policy.
   graphite-miner.v1`). It runs a role's own instructions and tools, with or
   without a Challenge, and only under `PARALLEL_CALLS_V2`. As for Carbon's
   autonomous agent: results reach the model as `model_view` shows them, a
   selection needs a completed practice (`practice_check`), the stop tool
   ends the session when the role offers it, one free-text reminder is given
   and renewed by any tool call, and the miner's messages may be read (the
   reply tool is added). The loop states its operating rules after the
   role's instructions (`graphite_miner_prompt`): every number from the value
   that enforces it. A miner role therefore states its call cap in `limits`
   (`limits_v2(calls_per_epoch=...)`) and `max_provider_calls` is refused
   for it, so the prompt can never state 48 while the loop enforces another
   cap. The reminder names only the ways to continue or end the role
   offers. The plan's policy binding records the full prompt's digest, the
   instructions' own digest, the stop tool and the reminder's digest.

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
   STOPPED with that code, nothing of the refused call reserved.
   `CeilingReached` is raised only from the reservation of a model call
   (provider_attempts or provider_nanodollars); a research trial's own
   reservation is the tool's to refuse, because raised inside a tool
   dispatch, after its intent is journalled, it would leave the dispatch for
   reconciliation. A plan without the rule keeps 48 and 8 exactly. Limits,
   compaction and finish are a role's only; Carbon's autonomous epoch is
   unchanged.

7. **Context compaction** (`COMPACTION_V1`: trigger 0.85, keep the last 6
   turns, both from the agreed design). When a turn's request would pass 85%
   of the admission ceiling while the conversation holds more than 6 turns,
   the loop asks for a compaction with one model call, journalled and
   metered like any other (`epoch-N[-<stage>]-compact-NNN`). The compaction
   request is an append to the last request - the same instructions and
   tools, the history, then a note - so its admission bound stays exact; the
   compaction tool is therefore offered from the first turn, and refused
   (`compaction_not_requested`) whenever it was not asked for. The summary is
   a closed schema of five text fields in one bounded JSON object (the
   16,384-byte tool-argument bound). With a valid summary the history
   becomes the initial observation, the summary - labelled as the model's
   own, naming the turns that left - and the last 6 turns unchanged; the
   record (`epoch-N[-<stage>]-compact-NNN.json`) names the turns summarised
   and kept, the dropped items' count and digest, the summary, the message,
   the sizes asked for and the admission (bound, spare, anchor). Compaction
   calls count against a set per-epoch call cap. With no valid summary after
   a second, firmer request the session stops typed (`compaction_failed`),
   and a compaction request that cannot fit stops typed (`context_ceiling`);
   nothing is ever dropped silently. A replay recomputes the same decision
   from the recorded turns and the journal refuses a differing record.

   *Sizing (corrected after independent review).* The first version
   admitted the compacted request under the compaction request's tokens plus
   the summary's bytes and allowed 12,000 characters regardless of the
   context left. That bound counts the dropped turns at full weight, and at
   the default 65,536-token model the 85% trigger leaves about 9,216 tokens,
   so a long summary was accepted, paid for, and then refused at the
   ceiling: the session stopped with no turn after it. Now:
   - the compacted request is admitted under the least of three bounds,
     each sound on three assumptions (a token covers at least one byte, as
     the loop has always held; a request's tokens are at most an earlier
     request's reported tokens plus the bytes appended to it, the loop's
     existing anchor rule; removing items from a request never adds
     tokens): its bytes; the compaction requests' least token bound plus
     the summary message's bytes; and the least input tokens a turn of the
     session reported plus the bytes after the initial observation (every
     request starts with the same instructions, tools and initial
     observation);
   - each request states the summary size the context left holds, at two
     request bytes a character, never more than 12,000; a summary is
     accepted only when the compacted request plus 1,024 tokens of spare
     (the next turn's status note) plus the miner's messages for that turn
     fits under the ceiling;
   - a summary that does not fit, or breaks the argument bound, is asked
     for again at the size its own bytes a character show will fit, with a
     tenth to spare; the second request is the conversation and the note
     again, not the refused reply, so it is admitted whenever the first was;
   - when no summary of at least 1,000 characters has room, or no model call
     would be left for the turn after the compaction, none is asked for or
     paid for (`compactions_deferred` in the outcome), and the session goes
     on as it would without the rule, stopping typed at the ceiling if it
     gets there;
   - the miner's messages for a step are read before its compaction, left
     out of the compaction request, counted in the spare and placed after
     the summary, so a new message is never summarised away unread; the
     compaction note asks the model to keep in `constraints` every earlier
     message of the miner's that still applies, and its replies. If the
     session ends during that compaction, that step's messages count as
     read, as they already do when a request stops at the ceiling.
   Checked on a scripted model at 65,536 tokens with 2,000 to 12,000-byte
   results and summaries in plain, JSON-heavy, accented and astral text, and
   at 131,072 tokens: every run that obeys the stated size continues after
   each compaction. Where the six kept turns alone nearly fill the context
   (a 16,384-token model with 1,500-byte results at two bytes a token, or
   one token a byte), compaction is deferred or a later compaction request
   cannot fit, and the session stops typed at the ceiling.

8. **Operational bounds chosen here** (engineering values, not science or
   economics): a tunable cap is at most 100,000; a summary holds at most
   12,000 characters in all and is asked for at the size the context left
   holds, planned at 2 request bytes a character; a compaction needs room
   for at least 1,000 characters and leaves 1,024 tokens spare beyond the
   miner's messages for the next turn; a compaction makes at most 2
   requests.

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
  dimension=...)` from `reserve` past the share - only for a reservation
  that carries provider_attempts or provider_nanodollars, never a research
  trial's - and never refuse an identity it already admitted. The Planner's
  finish validator (the `plan.validate_plan` wrapper) should answer every
  input with `(ok, refusal)` and never raise; the loop contains it if it
  does, but a refusal of its own is clearer to the model. A miner role's
  call cap goes in `limits`, never `max_provider_calls`. A staged
  Constructor's selection is `epoch-N/<stage>/selected-recipe.json`; the
  shared keep-unevaluated-candidate helper must read it there.
- S4 (views): staged miner-guidance reads are visible through
  `research_loop.guidance_delivered`, not `miner_guidance.delivered`. A
  session outcome under the compaction rule carries `compactions` and
  `compactions_deferred`.
- S6 (internal Graphite): `limits=LIMITS_V2` replaces `max_provider_calls`
  (both together are refused), and `compaction=COMPACTION_V1`; the internal
  ledger's provider_attempts or money cap satisfies the finite-ledger rule.
  `limits_rule` and `compaction_rule` give the texts for its own prompts.

**Unchanged.** The boundaries OWNER-LAUNCHPAD-PROD-01 lists; every
scientific value, threshold and gate; no hidden-test access, no chain writes,
no weights; every frozen plan replays byte-identically.
