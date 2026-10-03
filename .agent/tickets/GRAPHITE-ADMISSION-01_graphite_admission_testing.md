# GRAPHITE-ADMISSION-01: Graphite in Carbon's internal admission testing

**Owner decisions:** OWNER-GRAPHITE-06 (`.agent/DECISIONS.md`, 2026-10-02),
under OWNER-CHALLENGE-ROADMAP-03, OWNER-GRAPHITE-02 and
OWNER-CHALLENGE-ADMISSION-01 as amended 2026-10-01.
**Handoff:** `docs/development/graphite/ADMISSION_TESTING_HANDOFF.md`, the
owner's Mira handoff of 2026-10-01 re-issued on 2026-10-02 with Graphite in
Mira's place. The file is the handoff as the owner issued it.
**Primary map_ref:** SYSTEM/AGENT-EXECUTION; affects
SYSTEM/DEVELOPMENT-SEQUENCING.
**Supersedes for this work:** MIRA-ADMISSION-01, which stays paused. Its built
controller, boundaries, study sheet and design-search commitment layer (#475)
are reused here, not rebuilt.
**Status:** implementation. Bounded engineering completion is conditional on
required CI and a normal merge under OWNER-DX-03.

## Two standing rules (owner, 2026-10-02)

- **Generalizable by construction.** "Make sure everything we have is a
  generalizable test and design protocol that can be adapted to any challenge
  and improved as we go." Battery is the first instance, never the design.
  Shared code takes the Challenge as a parameter and reads its specifics from
  that Challenge's own records or adapter. A battery-only literal in shared
  code is a defect. Each slice below states what is Challenge-neutral, what is
  the battery adapter, and what a second Challenge must supply.
- **Lessons after every execution.** "Note lessons learned after every
  execution." Every test run, validation, campaign session, pod run, ladder
  climb, optimizer pilot, coverage run or stage gate appends one entry to
  `carbon/challenge_pipeline/lessons/` (schema
  `carbon.challenge-pipeline.lesson.v1`, PR 498) before the work is reported
  done. A lesson that should change the protocol is filed as a proposed
  revision and never applied silently.

**Graphite proposes every level's capabilities** (owner, 2026-10-02: "I want
graphite to propose capabilities for every construction level"). For every
Challenge and every level 0-5, Graphite writes a PROPOSED level proposal
(`carbon/challenge_pipeline/proposals.py`). The construction contract owner
accepts or declines it. Graphite never writes the contract, an expansion
record, or an ACCEPTED or DECLINED status.

## Scope

In order, one reviewable slice per commit:

1. **Working contract.** This ticket, OWNER-GRAPHITE-06, the handoff copy, the
   Mira supersession notes and the Hub event.
2. **Reconciliation** (handoff §2):
   `docs/development/graphite/ADMISSION_RECONCILIATION.md`.
3. **Slice A, the study sheet and ladder map generalized.**
   `carbon/agent_campaign/study.py` takes a Challenge; each Challenge's
   capability-to-level map lives with that Challenge.
4. **Slice P, Graphite's level planner.** A provider-independent session that
   writes a PROPOSED proposal for every level 0-5 of one Challenge.
5. **Slice B, battery Level 1 (bounded loss expressions).** An engineering
   draft, Carbon's reconstruction for it, and the handoff §8 climb harness,
   with fake runs. No expansion record and no change to a live contract.
6. **Slice C, Graphite's Optimizer researcher** (handoff §11-12). A
   Challenge-neutral design-search request and result over
   `search_commitment`, with a battery adapter and a freeze manifest. Fake runs
   only. Concrete K and grid choices are priced for the owner, not chosen.
7. **Slice D, customer rebuild** (handoff §13). Planned below; it waits until
   PR 504 merges.

**Out of scope.** Live model calls, pods, spend and vendor contact. Any change
to EV4, its contract, its panel or `optimizer.py`. Any change to a live
construction contract or expansion record. Opening any level to Graphite's
live campaigns or to miners. The files owned by PR 498
(`Design_Specs/Challenge_Roadmap.md`, `carbon/challenge_pipeline/*.py`,
`carbon/challenge_pipeline/records/`, `docs/development/challenge_pipeline/`,
`docs/development/CHALLENGE_PIPELINE.md`), by PR 504, by the step 4 rebuild
(`carbon/agent_campaign/graphite/{stage,attack,phase4,provider}.py`, the step 4
grant) and by link-only compute (`carbon/compute/`,
`scripts/dev/miner_launchpad/`).

**Bindings kept.** The step 4 work binds
`carbon.agent_campaign.study.permission_inventory()`. That no-argument call
keeps returning exactly today's battery result.

## Definition of done

- Each slice has tests that pass on the canonical workflow, ruff check and
  ruff format are clean on changed Python, and the Hub validates and renders
  current.
- Slice A: battery's study sheet and permission inventory are byte-for-byte
  unchanged; a synthetic second Challenge works; an unmapped capability is
  refused, not defaulted.
- Slice P: every emitted proposal passes `proposals.validate`; tests with
  battery and a synthetic second Challenge; every capability cites sources
  that resolve to the session's brief; a level that cannot be justified has no
  capabilities and says why in `left_out`; levels 4-5 state the isolation and
  reconstruction they would need; battery's Level 0 records its difference
  from today's contract. No generated battery proposal is committed as if a
  live Graphite session had made it.
- Slice B: the Level-1 surface is a draft shaped like a level proposal;
  Carbon rebuilds it in tests; the matched-comparison, ablation and
  interaction harness runs on fake runs; the miner-facing contract is
  unchanged and refuses the draft surface.
- Slice C: a proposed method runs at equal queries against the fixed grid on
  development models only; EV4's protected conditions are refused; commitment
  precedes reference access; the freeze manifest pins the comparison; fake
  runs only.
- A lessons entry for every execution.

## Human-reserved values (HUMAN_INPUT; each fails closed)

- Accepting or declining each level proposal: the construction contract owner
  (the technical owner, `protocol.json` `owners.technical`).
- Opening any level, to Graphite's live campaigns or to miners; locking a
  level.
- A live Graphite session for any role: it needs an owner spending grant
  (provider `graphite`) and the owner's authorization of that run.
- Reconstruction tolerances and permitted hardware beyond the CPU worker
  envelope; the study population; the attack, confirmation and money budgets;
  approval of the attacker model; isolation acceptance.
- Every value that changes scoring, a threshold or a tolerance.
- PB-INV and PB-ADV acceptance policies; PB-ADV's K beyond EV4; the Mode X
  condition grid; the design grid resolution.

## Maturity ceiling

SPECIFIED, IMPLEMENTED and TESTED against fake providers, fake runs and
scripted models. Nothing here is scientific, security, network or production
qualification. No level is opened, no expansion is recorded, and no live
Graphite session runs under this ticket.

## Deferred edits (after PR 504 merges)

These touch files PR 504 changes, so they wait:

- `docs/development/GRAPHITE_TESTING_AGENT_PLAN.md`: replace the Mira bake-off
  comparator with Graphite-against-baseline comparisons, and point the plan's
  admission-testing section at this ticket and handoff.
- `.agent/tickets/GRAPHITE-01_in_house_testing_agent.md`: cross-reference this
  ticket as the admission-testing lane.
- `carbon/agent_campaign/graphite/roles.py`: register the level-planning and
  method-proposal tasks in the role records, if the closed-call tasks of
  slices P and C should appear in the role manifest.

## Slice D plan: customer rebuild (handoff §13), after PR 504 merges

PR 504 brings the Constructor's PR-ready delivery bundle and its clean
rebuild. Slice D adds, Challenge-neutral, with battery as the first adapter:

1. A second-operator rebuild: a separate process, workspace and credential set
   rebuilds from the actual delivery package only, without Graphite's state,
   and records the package digest, the operator identity and every rebuilt
   artifact digest.
2. Fresh-seed repeats within the declared tolerance. The tolerance is
   HUMAN_INPUT; until it is set the comparison is reported, not judged.
3. Continued training where the recipe promises it: train on from the
   delivered state, and evaluate the changed model under a new artifact
   identity. Old evidence stays bound to the old artifact (invariant 10).
4. A transparency report stating concretely what the customer receives and
   can rebuild, and that Graphite's reasoning is logged but not claimed
   reproducible.
5. Tests with fake rebuilds: a package with an undeclared dependency fails;
   a tampered package is refused; a continued-training run gets a new
   identity.

## Working decisions

Delegated engineering decisions, recorded under
`.agent/DELEGATED_DECISION_PROTOCOL.md`. A lead may supersede any of them.

- **GA-D0, the pipeline view is regenerated, never edited.** Every lessons
  entry changes the count that `docs/development/CHALLENGE_PIPELINE.md`
  prints, and `tests/cpu/test_challenge_pipeline.py` fails while that view is
  stale. So each slice that adds a lesson re-renders the view with
  `python -m carbon.challenge_pipeline render`. The view is PR 498's file and
  is never edited by hand. The lesson
  `2026-10-02-lessons-regenerate-pipeline-view` proposes keeping the count out
  of the view, so that an entry changes no other committed file.
- **GA-D1, battery's map places every dimension of its contract.** The map
  moved from `study.py` to `carbon/battery/admission_study.py` with its ten
  historical labels unchanged. It adds `hybrid` and `prediction` at Level 4,
  as new model forms behind the constrained inference interface, because the
  level planner (slice P) refuses a contract dimension the map does not place.
  Battery has no rebuildable capability in either dimension, so the inventory
  and sheet are unchanged. The labels are planning labels; the owner may
  change them.
- **GA-D2, the study adapter is registered in one hook.** `study._studies()`
  maps a Challenge token to its adapter, as `challenge_registry.campaigns`
  does for campaigns. Adding a Challenge is adding its adapter there. A test
  or an unregistered Challenge passes a `ChallengeStudy` directly.
- **GA-D3, the level planner is a Planner task, not a new role.** It runs on
  the Planner's rung with its own prompt (by digest), as the Reader's card
  extraction runs on the Reader's rung. So `roles.py`, which PR 504 changes,
  is untouched, and `proposed_by.role` is `planner`.
- **GA-D4, Carbon checks the Level 0 difference; it does not write it.** The
  difference is computed from the contract and the map. A Level 0 reply must
  cite every rebuildable capability labelled above 0, name every excluded
  capability, and name every empty level, or the level is rejected.
- **GA-D5, the Level-1 draft lives outside the registry.** The registry holds
  one contract per Challenge token, and the miner path validates every
  submission against it, so registering the draft would open it to miners.
  Its surface kinds (uint, float, bool, choice) also cannot describe an
  expression. The draft, its operation set and its development profile are
  therefore plain data outside `capability_registry`. Battery's
  `objective.loss_expressions` stays excluded, and tests hold the miner path's
  refusal. This leaves one owner decision, below.
- **GA-D6, the draft's bounds are proposed engineering bounds.** Depth 4,
  16 nodes, add arity 8, scale 0-10 (the registered weights' range), exponent
  0.5-2 and epsilon 1e-6 (`training.case_loss`'s). They bound a construction
  surface and change no score, threshold or tolerance. They are accepted or
  changed with the Level-1 proposal.

## Open owner decisions

- **How a level is served to Graphite's development campaigns without
  reaching miners** (slice B; handoff §8: "A level opened for Graphite's
  development campaigns is never opened to miners"). The registry cannot hold
  a development-only variant today. The smallest decision: either (a) approve
  a development-only contract variant held outside
  `capability_registry.CONTRACTS`, pinned by its own digest and read only by
  Carbon's proposal runner, never by the miner MCP server, the validator or
  the intake; or (b) keep each new level out of Graphite's live campaigns
  until it is accepted and recorded for everyone. Until then, nothing at
  Level 1 runs live. The lesson `2026-10-02-battery-level1-draft` files (a) as
  a proposed revision.
- **Accept or decline battery's level proposals** when a live level-planning
  session has produced them (technical owner), and authorize that session.

## Slices delivered

- **Reconciliation:** `docs/development/graphite/ADMISSION_RECONCILIATION.md`.
  It lists the commits, what exists and is missing per handoff section, the
  affected tests, and every battery literal in shared code with its
  disposition.
- **Slice A, study sheet and ladder map.**
  - Challenge-neutral: `carbon/agent_campaign/study.py`. `ChallengeStudy`,
    `study_for`, `planning_level`, and `permission_inventory`, `scope_pins`,
    `study_sheet`, `write` taking a Challenge; `drift` reads the Challenge
    from the written sheet; the CLI takes `--challenge`. A rebuildable
    capability whose dimension the map does not place is refused
    (`capability_not_on_ladder_map`), never defaulted. The adapter is checked:
    its contract's token, a map of dimensions to levels 0-5, exactly the
    Challenge-specific pins, one specimen per check, its sheet text.
  - Battery adapter: `carbon/battery/admission_study.py`. Battery's map, its
    pin sources, its eight specimens and the sheet text naming rule v2, moved
    unchanged.
  - A second Challenge supplies: a registered construction contract, a map
    placing every dimension it uses, its pin sources (generator, reference,
    score, environment, decision contract, feedback; budget and population
    stay None until the owners set them), one specimen and control per check,
    its feedback text and permitted hardware.
  - Evidence: the battery sheet and inventory written before and after the
    change are byte-identical, and equal the committed
    `docs/development/mira/level0/` files. `permission_inventory()` with no
    argument returns them unchanged.
  - Tests: `tests/cpu/test_agent_campaign_study.py`, and two mutation checks
    in `tests/cpu/test_graphite_admission_mutations.py`.
- **Slice P, Graphite's level planner.**
  - Challenge-neutral: `carbon/agent_campaign/graphite/closed_task.py` (one
    closed, tool-less, metered call per item under a grant, the phase-2
    pattern generalized) and `carbon/agent_campaign/graphite/level_planner.py`
    (the brief, the per-level rules, the reply checks, the session and a live
    runner).
  - Battery adapter: none of its own. The planner reads battery through its
    construction contract and its slice A study adapter.
  - A second Challenge supplies: a registered construction contract and a
    study adapter whose map places every dimension of the contract. The
    session then needs only a literature index and any permitted development
    results.
  - What Carbon checks, outside the model: a closed reply shape; sources that
    resolve to the brief; a card or result behind every capability above
    Level 0; a reason for an empty level; isolation and reconstruction at
    Levels 4-5; Level 0's difference from today's contract; then
    `proposals.validate`. A rejected level is recorded with its code. The
    planner never writes a contract, an expansion record, an ACCEPTED or
    DECLINED status, or anything in the repository.
  - Battery's Level 0 difference, computed: the rebuildable capabilities the
    map labels 1 (`objective.*` weights), 2 (`batching`, `optimizer`,
    `schedule`, `stages`, `training_data`) and 5 (declarative `inference.*`);
    `objective.loss_expressions` among the excluded; Level 3 empty.
  - No battery proposal is committed. The live session needs the owner's
    authorization and a grant:
    `python -m carbon.agent_campaign.graphite.level_planner --challenge battery-fastcharge-ageing-development-v1 --root DIR --snapshot SNAPSHOT --grant GRANT --credential-env ENGY_API_KEY`.
    It writes under a root outside the repository. Committing a proposal, and
    accepting or declining it, are people's acts.
  - Tests: `tests/cpu/test_graphite_level_planner.py`, and six mutation
    checks.
- **Slice B, battery Level 1 (bounded loss expressions), engineering only.**
  - Challenge-neutral: `carbon/reconstruction/loss_expressions.py`, the
    bounded operation set (add, mul, div, scale, pow, log1p, sqrt over a
    Challenge's non-negative per-case terms), its canonical form, digest,
    rebuild from pinned bytes and evaluation with any array namespace; and
    `carbon/agent_campaign/climb.py`, the handoff §8 harness: valid
    constructions under the previous and expanded profiles, matched attack
    budgets, ablation per new permission, combined-permission interactions and
    clean rebuilds of promising results, with typed findings that stop the
    climb.
  - Battery adapter: `carbon/battery/level1_draft.py`. Battery's operation
    set and terms (computed as `training.case_loss` computes them), the
    expression restating a registered menu setting, the draft shaped like a
    level proposal, the development profile's identity and battery's climb
    plan.
  - A second Challenge supplies: its non-negative per-case terms and their
    computation, its operation-set bounds, its menu restatement, and its
    panel, attacks, budget and promising rule for the climb.
  - Evidence: from its pinned bytes alone, a clean process trains to
    bit-identical parameters. The menu restatement computes the registered
    objective to 1e-12. Battery's contract, expansion records and every miner
    path are unchanged; a strategy naming `loss_expressions` is refused as
    `parameter.not_rebuildable`.
  - Not done, by design: no expansion record, no contract change, no trainer
    change. Those follow the owner's acceptance of a Level-1 proposal.
  - Tests: `tests/cpu/test_loss_expressions.py`,
    `tests/cpu/test_agent_campaign_climb.py`, and four mutation checks.
- **Slice C, Graphite's Optimizer researcher.**
  - Challenge-neutral: `carbon/design_search/` (`methods.py`: the registered
    methods `screen_then_confirm` and `coarse_to_fine` with closed, bounded
    parameters, each selecting by the baseline's rule; `experiment.py`: the
    neutral request, the `SearchAdapter` a Challenge supplies, the freeze
    manifest and the equal-query pilot) and
    `carbon/agent_campaign/graphite/optimizer_research.py` (the Optimizer
    researcher's closed method-proposal task).
  - Battery adapter: `carbon/battery/value/design_search_adapter.py` over
    `search_commitment`, used unchanged (development material, EV4's
    conditions refused, commitment before reference access, the fixed grid as
    baseline), and `design_search_pricing.py` with
    `docs/development/graphite/OPTIMIZER_CHOICES.md`.
  - A second Challenge supplies a `SearchAdapter`: its variables, its
    commitment engine (request, budgeted oracle, commit, verify), its fixed
    baseline, its feasibility, objective and margin readings, the code a
    freeze pins, its tie policy, and its own priced choices. A test runs the
    neutral methods and the pilot on a synthetic second Challenge.
  - Evidence: on the synthetic cell, screen-then-confirm returns the fixed
    grid's design with fewer model queries; coarse-to-fine never beats the
    grid's optimum; every reference call follows a commitment.
  - Priced, not chosen: K of 50 (EV4's), 100 and 200; design grids of 272,
    1023 and 3965 designs; Mode X condition grids of 32 (EV4's, entirely
    protected), 21 (offset, usable) and 150 (contains all 32 protected).
  - Tests: `tests/cpu/test_design_search_pilot.py`, and three mutation
    checks.

## Lessons

- `2026-10-02-graphite-admission-contract`
- `2026-10-02-lessons-regenerate-pipeline-view` (PROPOSED revision)
- `2026-10-02-graphite-admission-reconciliation`
- `2026-10-02-study-sheet-takes-a-challenge`
- `2026-10-02-graphite-level-planner`
- `2026-10-02-battery-level1-draft` (PROPOSED revision)
- `2026-10-02-optimizer-researcher-pilot`
- `2026-10-02-graphite-admission-regression`

## Engineering verification

On the canonical workflow
(`CARBON_UV_GROUPS="chain archive science-jax science-torch mcp" ./scripts/dev/canonical.sh python -m pytest <paths> -q -p no:cacheprovider`),
the handoff §14 list with this ticket's suites passed: 728 tests. The list is
admission, readiness, engineering value (EV1, EV2, EV4, audit), divergence,
expansion record, capability registry, battery construction contract, MCP
connection (CPU and service), protected material, rule v2, intake, B02b
boundaries, the Graphite and agent-campaign suites, design-search commitment
and pilot, loss expressions and the pipeline. The quality ratchet passed with
every changed Python file clean, diff hygiene passed, and the Hub validates
and renders current. Native-host results are diagnostics; canonical CI is
acceptance.
