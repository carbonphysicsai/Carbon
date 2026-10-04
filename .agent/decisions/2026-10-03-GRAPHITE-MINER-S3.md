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
   digests every role prompt (Reader, Planner, Constructor), every tool
   manifest and workspace allowlist, the local tool schemas (`lit_search`,
   `lit_card`, `graphite_record_plan`), the plan schema and the hunt's part
   of the research share (decision 13); the provider plan freezes `edition`
   and `edition_digest`. An id this code does not publish, or a published id
   whose record no longer has the frozen digest, is refused
   `graphite_edition_unknown` before any model call. The v1 digest is pinned
   in the mutation tests; after merge a change is a new edition id. The
   prompt texts are literal in `edition.py`, so a later edit of the engine's
   or the internal edition's text never changes a published miner edition.
   The Planner and Constructor prompts describe Graphite as Carbon's research
   agent running for the miner, on the miner's model, key, budget and
   compute; the Reader's says it runs for a miner, on the miner's model and
   budget. The research loop appends its own operating rules to a role's
   instructions (S1's `graphite_miner_rules`: calls per turn, arguments,
   budget, reminder, ending, compaction, each from its enforcing value), so
   the role prompts state only the role's own terms and point to those
   rules, never a second copy that could drift from them.
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
   reservation that would take a research stage's provider spend past its
   cap for `provider_nanodollars` and `provider_attempts`, raising
   `ResearchShareReached`, code `research_share_reached`. Where the engine
   defines `research_loop.CeilingReached` (S1), `ResearchShareReached` is
   one, so the research loop itself ends the Planner's session STOPPED with
   that code, journalled; otherwise it is a RuntimeError. The stages' spend
   is read from the ledger by identity prefix (`graphite-reader-` for the
   hunt's Reader calls, the name the Launchpad's view reads, and
   `epoch-1-plan-` for the Planner, compaction calls included), so it
   survives a restart; an identity the ledger already holds is never
   refused. The share is the exact decimal the miner chose
   (`Fraction(repr(share))`). Only FULL applies it; RESEARCH and a BUILD
   whose Planner runs first are bound by the campaign ceilings alone. The
   money share counts settled charges, so in practice attempts are usually
   the binding dimension.
5. **Stage layout and replay.** The Planner runs as the engine's stage `plan`
   of epoch 1 (S1: `epoch-1/plan/`, identities `epoch-1-plan-*`, no epochs
   unit); the Constructor runs the campaign's own epochs (`epoch-N/`), so the
   campaign's submit and an attach read its selection where they always
   have. Each stage records itself once under `<campaign>/graphite/stages/`;
   a finished stage never runs again, so a resume makes no hunt, arXiv or
   model call for it. An epoch already evaluated
   (`permitted-final-feedback.json`) is never submitted again. The hunt runs
   under one hunt id per campaign (a digest of the campaign id and the
   frozen block), so a hunt interrupted by a pause, a stop or a provider
   failure resumes as the same hunt, with the queries it started with; its
   stage record keeps the report's counts, where the Launchpad's view reads
   them. A research stage that ends without its product (the share, a
   refusal, arXiv FAILED_INFRA, a loop stop with a code) is also noted in
   the campaign ledger (`kind: decision`, `{graphite_stage, status, stop}`),
   where the miner's views and agent read it.
6. **Frozen launch inputs.** At the first preparation
   (`driver.freeze_launch`), the launch fields are validated (the hunt also by
   the hunt's own `validate_hunt`, so a launch the hunt would refuse never
   freezes), the shared card pack is copied write-once into the campaign
   root (`pack.freeze_into`), the miner's library is read once - the
   curation the Launchpad admitted the launch with
   (`args.graphite_curation_digest`, resolved by
   `MinerLibrary.curation_state`, never re-read from the current state; the
   current curation only for a launch naming none), its private
   snapshot digest and the chosen plan (which must be this Challenge's, id
   and version, and pass `plan.validate_plan` against that curation) - and
   the curation and plan are written once to `<campaign>/graphite/launch.json`,
   bound to the frozen block by digest. A record left by a preparation that
   stopped before its manifest froze is replaced; once the manifest exists, a
   different record is refused. The miner's later pins, bans and edits reach
   a later campaign, never this one. A run serves the campaign's own pack
   copy (`pack.load_frozen`), so a Carbon update that ships another pack never
   changes a running campaign; a missing copy is made again only from the
   very pack it froze, and a missing or damaged pack is refused
   `literature_pack_missing`. The library is opened over that frozen pack, so
   dedup and served cards read it, and the served ranking takes the miner's
   own hunt queries as its focus terms. The library root is the runner's
   `args.graphite_library`; a Graphite campaign without one is refused (fail
   closed) rather than given a campaign-local library.
7. **Launch fields** (`edition.launch_fields`) are the design's names, which
   the Launchpad's `LaunchChoice.apply` sends (claude/gm-launchpad
   9b9e00b0): `args.graphite = {mode, research_share, plan, hunt, limits}`,
   each optional, with the admitted curation digest beside them
   (`args.graphite_curation_digest`); any other key, an earlier S4 head's
   `edition`, `plan_digest` or `curation_digest` included, is refused
   `graphite_launch_invalid` (one shape, both slices agreed). The edition is
   the campaign's to name (v1). `mode` RESEARCH, BUILD or FULL (default
   FULL); `research_share` FULL only, 0-1 (default 0.10; any other mode
   freezes None and refuses a value); `plan` a plan digest, BUILD only;
   `hunt` null or `{queries?, max_records?}`, never with a plan (no Planner
   would read it), queries in the hunt's own grammar (at most 8, each 1-200
   characters of `[A-Za-z0-9 -]`, at most 6 whitespace-separated terms of at
   most 40 characters, starting with a letter or digit, never `and`, `or`,
   `not` or `andnot`), `max_records` 1 to 5,000 (the arXiv client's own
   bound, default 200); `limits` `{calls_per_epoch?, trials_per_epoch?,
   planner_calls?}`, each absent or an integer 1 to 100,000 (the engine's
   `MAX_TUNABLE_CAP`); the curation digest a digest. Values of the wrong
   type are refused, never read as empty. Refusal codes:
   `graphite_launch_invalid`, `graphite_edition_unknown`,
   `graphite_mode_invalid`, `research_share_invalid`, `plan_invalid`,
   `plan_not_found`, `card_not_found`, `card_banned`, `hunt_query_invalid`,
   `graphite_limits_invalid`, `curation_not_found`, `too_many_pins` and
   `literature_pack_missing`. The engine limits frozen are
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
   limits. Because every pin must be named, a launch whose Planner would
   have to consider more than 64 pins is refused `too_many_pins` before it
   freezes, instead of a Planner that could never record a plan. A miner
   edit is `plan.new_version` (new digest, parent named, hypotheses ranked
   by their order in the edit).
9. **The Reader** (`driver.MinerReader`) makes one closed, tool-less call per
   request on the miner's selection, metered by `request_model` under
   identity `graphite-reader-<digest of the closed request>`: the same paper's
   request is one call, replayed thereafter. The edition has one Reader
   prompt, byte for byte the literature slice's `hunt.READER_PROMPT` (the
   prompt every hunt request actually carries; an integration test pins the
   two equal); the hunt's first pass on title and abstract is local and free
   (`focus.triage`), so the earlier triage prompt was removed before merge.
   A request carrying any other prompt, an offered tool, another model or no
   input, and a call the research share refuses, are refused before anything
   is reserved or sent, raised as the hunt's own `hunt.ReaderNotSent` with
   the code, so the hunt releases the paper's claim and stops typed.
10. **Learning signal (a proxy; flagged).** After each Constructor epoch,
    before its selection is submitted, the plan's cited cards (best-ranked
    hypothesis first, at most 64, the library's own bound) are recorded with
    `MinerLibrary.record_outcome(cards, improved, evidence, challenge=)`,
    bound to the campaign's Challenge and version, `improved` meaning the
    epoch ended in a practised selection. It reads the epoch's
    own outcome only, never evaluation feedback, scores or hidden-test
    conditions. This is a weaker signal than the design's "cards cited by a
    plan whose practice improved": under the practice rule almost every
    selection is practised, so it mostly separates epochs that selected from
    epochs that stopped. A practice-improvement signal needs a per-Challenge,
    Challenge-neutral practice metric and direction, which nothing public
    states today; choosing one would be a scoring decision, so it is left to
    the lead (see Open). A library refusal (an unknown card, an outcome it
    cannot hold) is recorded SKIPPED with its code and never holds a submit:
    a ranking hint must not stop a paid campaign.
11. **Policy acceptance.** `prepare_battery` accepts a Graphite campaign
    prepared under the autonomous policy (what the Launchpad passes for every
    agent campaign) or the miner edition's own; the roles always run under
    the edition's policy, which the plan records.
12. **Hunts in BUILD.** A BUILD launch that names no plan may hunt: its
    stages are hunt, Planner, build, on the campaign ceilings alone. The
    Launchpad (9b9e00b0) admits no hunt with BUILD; the driver runs one if a
    door ever sends it, and never with a plan.
13. **The hunt's part of the FULL research share.** In FULL the hunt may
    spend at most half the research share (`edition.HUNT_PART_OF_SHARE`,
    frozen in the edition record), counted over its own Reader calls; the
    Planner may spend the whole share, counted over every research call, so
    it always has at least the other half. Without it, a default hunt (200
    records, 10% share) usually spent the whole share and the build ran with
    no plan. The Planner always runs: with nothing left, its first call is
    refused and it stops typed having sent nothing.
14. **Typed stage ends.** A hunt ends DONE, DONE `literature_fetch_failed`
    (arXiv FAILED_INFRA; the Planner proceeds), or STOPPED with the code that
    stopped it (the share, `hunt.HuntRefused`'s own code); a pause, a stop, a
    provider failure or an unknown outcome propagates and resumes the same
    hunt. The Planner ends PLANNED, STOPPED `research_share_reached`, or with
    the research loop's own status and code.
15. **The miner edition's import closure.** No miner module imports a grant,
    pod, experiment, delivery, triage, next-level, ladder, provider, model or
    controller module (AST check), and importing every miner module in a
    fresh interpreter loads none of them - when the internal package's own
    `__init__` is not executed. That `__init__` (not this slice's file)
    eagerly imports the internal provider and with it the grant, ladder and
    model; making it lazy is an integration step (see Open).

**Integration evidence.** The tests that need the engine (S1, claude/gm-engine
2b0f8ab2) and literature (S2, claude/gm-literature babc1c83) slices skip on
this branch and were run in a throwaway detached worktree holding this
branch's files with those slices' and the Launchpad's (S4, 9b9e00b0) files
beside them: the real hunt reading through `MinerReader` (one Reader call
carrying the edition's prompt, the pack's paper never read, replay with no
arXiv or model call), a share-stopped hunt releasing its claim, 8a's
RESEARCH flow on the real pack, library, hunt and research loop, the loop
stopping the Planner typed at the share, and the loop's own practice check
on a miner selection; and every S1, S2 and S4 Graphite test there. S4's
journey stages 8a-8d also ran there through this driver once four test-data
lines in that journey were corrected locally (see Open); 8e stops at S1's
compaction request (see Open).

**Open (handoffs, not owner decisions).**
- Lead: whether the learning signal (decision 10) must become a
  practice-improvement signal; that needs a per-Challenge practice metric
  and direction, which is a scoring choice this slice does not make.
- Integration: make `carbon/agent_campaign/graphite/__init__.py` lazy (a
  module `__getattr__`, or no re-exports), then add a plain fresh-interpreter
  import test without the package stub.
- S2: take `READER_PROMPT` from `edition.READER_EXTRACTION_PROMPT` so the
  text has one source (the integration test pins them equal meanwhile);
  imports are extracted only by a hunt, so a launch with no hunt leaves
  queued imports for a later hunting launch. `MinerLiterature(context=)`
  could be frozen per campaign later; the driver does not freeze it yet.
- S4: `args.graphite`, `args.graphite_curation_digest` and
  `args.graphite_library` as 9b9e00b0 sends them; refuse `max_records`
  above 5,000 and limits above 100,000 at the door (this driver refuses them
  before the manifest freezes); add NEXT_ACTIONS for
  `graphite_launch_invalid`, `graphite_edition_unknown`,
  `research_share_invalid`, `graphite_limits_invalid`, `curation_not_found`
  and `too_many_pins`. In the journey: `battery_prepare` must freeze the
  block with `driver.freeze_launch(args, root, challenge=...)`, not pass
  `args.graphite` as the block; the Planner's finish call sends
  `recipe_json` (a JSON string or null), not `recipe`; a RESEARCH campaign's
  view shows the Planner's plan digest (as S4's own projection reads it);
  `plan_edit` documents name pins as `{card_id, consideration}` and rank
  their hypotheses (or the door builds the edit with `plan.new_version`,
  which ranks by order); and S1's compaction request carries the session's
  tools, so the scripted model must answer it with the compaction tool, not
  as a closed call.
