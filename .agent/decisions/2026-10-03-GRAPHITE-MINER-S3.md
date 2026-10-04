## 2026-10-03 — GRAPHITE-MINER-S3: the miner edition's driver, edition table, stage budget and plan

**Authority.** Delegated engineering decisions (executor, slice S3 of the
Graphite miner edition), within OWNER-GRAPHITE-MINER-01 (recorded beside this
file), OWNER-LAUNCHPAD-PROD-01 and OWNER-LAUNCHPAD-PROD-02. No scientific
value, threshold, gate or tolerance is set here; no chain write, no weights,
no hidden-test access.

**What the slice adds.**
- `carbon/agent_campaign/graphite/miner/` (`edition`, `toolbox`, `budget`,
  `plan`, `driver`): the published edition `carbon.graphite.miner-edition.v1`
  with the Reader, Planner and Constructor; the role toolbox; the research
  share; the miner plan `carbon.graphite.miner-plan.v1`; and
  `driver.run(prepared)` for RESEARCH, BUILD and FULL.
- `research_campaign.execute` hands `agent == "graphite"` to
  `run_graphite` (the driver). `run_agent` and `run_graphite` share one
  keep-unevaluated-candidate helper, `submit_or_retain`, whose note and
  return are `run_agent`'s, byte for byte.
- `battery.campaign.provider_plan(agent="graphite", ..., graphite=block)`
  (`graphite_plan`), `manifest_document(..., graphite=)` and
  `prepare_battery`'s acceptance of a Graphite campaign;
  `product_campaign.AGENTS` gains `graphite`.

**Decisions.**
1. **Default-off and versioned.** The autonomous and agent-less plans, the
   autonomous agent's run and every frozen campaign are unchanged: the
   autonomous plan's digest at the base commit (9bfd9add) and at this head is
   pinned equal in `tests/cpu/test_battery_graphite_plan.py`. `autonomous`
   stays in `AGENTS` so recorded and queued launches still build and frozen
   campaigns still run `run_agent`; refusing a new `autonomous` launch
   (`autonomous_agent_replaced`) is the launch doors' (S4).
2. **The edition is frozen by digest.** `edition.EDITION.plan_record()`
   digests every role prompt (Reader extraction and triage, Planner,
   Constructor), every tool manifest and workspace allowlist, the local tool
   schemas (`lit_search`, `lit_card`, `graphite_record_plan`) and the plan
   schema; the provider plan freezes `edition` and `edition_digest`. An id
   this code does not publish, or a published id whose record no longer has
   the frozen digest, is refused `graphite_edition_unknown` before any model
   call. The v1 digest is pinned in the mutation tests; a change is a new
   edition id. The prompt texts are literal in `edition.py`, so a later edit
   of the engine's or the internal edition's text never changes a published
   miner edition. The miner-facing prompts describe Graphite as Carbon's
   research agent running for the miner, on the miner's model, key, budget
   and compute.
3. **Roles and tools.** The Attacker, Writer and Optimizer researcher, the
   proposal runner (`graphite_run_proposal`) and the next-level store
   (`graphite_propose_next_level`) cannot be built into a miner role
   (`MinerRole` refuses them) and are refused by the toolbox's manifest gate.
   Next-level ideas are ordinary `capability_request` workspace actions.
   The Planner holds `lit_search`, `lit_card`, `get_challenge_info`,
   `get_interaction_manifest`, `start_research_task` (workspace only:
   public_material, inventory, read_file, check_design, roadmap,
   capability_request, notebook, run_python), `get_research_result`, the
   finishing tool `graphite_record_plan`, the stop tool and the
   miner-guidance reply. The Constructor holds the internal Constructor's
   research tools less the proposal runner and next-level store, `lit_card`,
   the selection, the stop and the reply; it may practise and start every
   development workspace action, run_julia where the campaign offers authored
   Julia. The research task tool's `kind` and `action` choices are narrowed
   to the role's allowlist in the schema the model is offered, and the
   toolbox refuses anything else (`REFUSED_NOT_IN_STAGE`). Escalation is
   frozen `[]` (no seam in v1).
4. **The research share is a ledger proxy keyed by identity namespace.**
   `budget.StageLedger` refuses, before reserving or sending, a new
   reservation that would take the research stages' provider spend past
   `floor(research_share x ceiling)` for `provider_nanodollars` and
   `provider_attempts`, raising `ResearchShareReached` (a RuntimeError, so no
   stage mistakes it for an answerable request), code
   `research_share_reached`. The stages' spend is read from the ledger by
   identity prefix (`graphite-reader-`, `epoch-1-plan-`), so it survives a
   restart; an identity the ledger already holds is never refused. The share
   is the exact decimal the miner chose (`Fraction(repr(share))`). Only FULL
   applies it; RESEARCH and a BUILD whose Planner runs first are bound by the
   campaign ceilings alone. The money share counts settled charges, so in
   practice attempts are usually the binding dimension. A share reached in
   the hunt ends the research stage without starting the Planner.
5. **Stage layout and replay.** The Planner runs as the engine's stage `plan`
   of epoch 1 (S1: `epoch-1/plan/`, identities `epoch-1-plan-*`, no epochs
   unit); the Constructor runs the campaign's own epochs (`epoch-N/`), so the
   campaign's submit and an attach read its selection where they always
   have. Each stage records itself once under `<campaign>/graphite/stages/`;
   a finished stage never runs again, so a resume makes no hunt, arXiv or
   model call for it. An epoch already evaluated
   (`permitted-final-feedback.json`) is never submitted again.
6. **Frozen launch inputs.** At the first preparation
   (`driver.freeze_launch`), the miner's launch fields are validated, the
   miner's library is read once - its curation (pins and bans), its private
   snapshot digest and the chosen plan (which must be this Challenge's and
   pass `plan.validate_plan`) - and the curation and plan are written once to
   `<campaign>/graphite/launch.json`, bound to the frozen block by digest. A
   record left by a preparation that stopped before its manifest froze is
   replaced; once the manifest exists, a different record is refused. The
   miner's later pins, bans and edits reach a later campaign, never this
   one. The library root is the runner's `args.graphite_library`; a Graphite
   campaign without one is refused (fail closed) rather than given a
   campaign-local library.
7. **Launch fields** (`edition.launch_fields`). `mode` RESEARCH, BUILD or
   FULL (default FULL); `research_share` 0-1 (default 0.10, recorded in every
   mode, applied by FULL); `plan` a plan digest, BUILD only; `hunt` null or
   `{queries?, max_records?}` (default 200, no Carbon cap; at most 8 queries
   of at most 6 terms of `[A-Za-z0-9-]`, no raw query syntax), not in BUILD;
   `limits` `{calls_per_epoch?, trials_per_epoch?, planner_calls?}`, each a
   positive integer or absent (absent: only the campaign ceilings bind, no
   Carbon upper bound). Refusal codes: `graphite_launch_invalid`,
   `graphite_mode_invalid`, `research_share_invalid`, `plan_invalid`,
   `plan_not_found`, `card_not_found`, `card_banned`, `hunt_query_invalid`,
   `graphite_limits_invalid`. The engine limits frozen are
   `limits.plan = LIMITS_V2(planner_calls, trials_per_epoch)` and
   `limits.build = LIMITS_V2(calls_per_epoch, trials_per_epoch)`, with
   `compaction = COMPACTION_V1`; the constants come from the engine where it
   defines them, else from the agreed interface values.
8. **The plan.** `plan.from_arguments` builds the plan from the Planner's
   `graphite_record_plan` call (ranked hypotheses with hypothesis, expected
   effect, stopping rule, optional recipe as a JSON string, cites
   `{card_id, origin}`; and `pins_considered` `{card_id, consideration}`).
   `validate_plan` refuses a banned cite (`card_banned`), an unknown card
   (`card_not_found`), a cite under another origin than the card's own, a
   left-out pin or a malformed plan (`plan_invalid`), and an unknown parent
   (`plan_not_found`). The Planner's plan is checked against exactly the
   literature it was served (the stage's `lit_card`). Shape bounds (8
   hypotheses, 12 cites, 64 pins, 2,000 characters per text field, a 16 KiB
   recipe) keep a plan one readable tool call; they are not research
   limits. A miner edit is `plan.new_version` (new digest, parent named).
9. **The Reader** (`driver.MinerReader`) makes one closed, tool-less call per
   request on the miner's selection, metered by `request_model` under
   identity `graphite-reader-<digest of the closed request>`: the same
   paper's request is one call, replayed thereafter. Its instructions must be
   one of the edition's Reader prompts; a partial request is completed from
   the selection; a foreign prompt, an offered tool or another model is
   refused before anything is sent.
10. **Learning signal.** After each Constructor epoch the plan's cited cards
    are recorded with `MinerLibrary.record_outcome(cards, improved,
    evidence)`, `improved` meaning the epoch ended in a practised selection.
    It reads the epoch's own outcome only, never evaluation feedback, scores
    or hidden-test conditions. It is recorded at least once per epoch
    (`evidence.outcome_id` is stable, for the library to de-duplicate).
11. **Policy acceptance.** `prepare_battery` accepts a Graphite campaign
    prepared under the autonomous policy (what the Launchpad passes for every
    agent campaign) or the miner edition's own; the roles always run under
    the edition's policy, which the plan records.

**Open (handoffs, not owner decisions).** The engine (S1) must carry the
finishing call's arguments in its PLANNED outcome (`arguments`) or keep the
finishing call's intent journal (the driver reads either). The literature
slice (S2) builds Reader requests with the edition's prompts
(`MinerReader.prompts`) and de-duplicates `record_outcome` by `outcome_id`.
The Launchpad slice (S4) passes `args.graphite` and `args.graphite_library`,
patches `research_campaign.run_graphite` in its journey fixture, and adds the
codes above to its refusal catalog.
