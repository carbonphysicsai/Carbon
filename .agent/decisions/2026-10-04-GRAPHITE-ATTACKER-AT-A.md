## 2026-10-04 — GRAPHITE-ATTACKER-AT-A: the attack engine's neutral core, adapter interface, suite and Challenge record

**Authority.** OWNER-GRAPHITE-ATTACKER-01 item 1 (a Challenge-neutral attack
engine with one adapter per Challenge and per construction level; the eight
shared Track A checks, each with an attack example and a valid control;
higher-level families declared NOT_RUN) and item 3 (evidence rules). These are
engineering working decisions inside that authority. No scientific value,
threshold, gate, grant, sealed material or LIVE state is chosen or changed.

**Scope.** Slice AT-A of the general Graphite attack engine:
`carbon/agent_campaign/attack/{__init__,engine,adapter}.py`,
`carbon/battery/track_a.py` (consumes the engine only), the test suite v1
and Graphite's pipeline-stage ledger from CHALLENGE-PROTOCOL-03/04
(`origin/agent/challenge-protocol-04b` at be61e7435) adapted to main, and the
Graphite Challenge record. Base: 2363950db (origin/main at slice start).

**Seam classification.** NO_CONFLICT with the owner decision. The reuse branch's
call cap (`session_turns: 34`) and its STEP4 grant are IMPLEMENTATION_LAG
against OWNER-GRAPHITE-ATTACKER-01 item 5 (money and time bind, never call
caps) and are not carried over.

### Decisions

- **AT-A-D1. Extraction, byte for byte.** The Family engine (track_a.py
  465-600 on 2363950db) moves to `attack/engine.py`. `track_a` keeps its
  public names (`Family`, `FAMILIES`, `run_family`, `findings`,
  `family_state`, `HELD`...) as thin wrappers, and keeps `family_id` and
  `attacks()` for EV5's `value.panel.harness_constructions`. Before editing,
  the harness's three outputs on 2363950db were hashed twice (deterministic)
  and are pinned in `tests/cpu/test_attack_engine.py`: coverage.json
  `0dbac5d8...`, attempts.jsonl `5cd7ccb6...`, conditions.json `ba50297a...`.
  They are unchanged after the extraction.
- **AT-A-D2. Family state is stricter, never weaker.** FINDING on a breach or
  a wrongly refused control. INCONCLUSIVE when there is no evidence: no attack
  attempted (a zero budget included), no control, an attack without its
  specimen, a silent specimen, or a boundary that did not answer. Otherwise
  IN_PROGRESS. Battery's real families are unaffected (all IN_PROGRESS); only
  synthetic partial row sets that were vacuously IN_PROGRESS now read
  INCONCLUSIVE. The cross-slice interface lists `HELD` as a family state; the
  engine never emits it, because HELD is an attack's verdict and a clean
  family must stay IN_PROGRESS (acceptance is a reviewed LOCK, and battery's
  report must stay byte-identical). `FAMILY_STATES` lists the three it emits.
- **AT-A-D3. A boundary that does not answer.** `InfrastructureFailure` is
  FAILED_INFRA, `TimeoutError` TIMEOUT, any other exception CRASHED. Each is
  recorded with the exception's type only, is never a pass and never a
  finding (invariant 7), and leaves the family INCONCLUSIVE.
- **AT-A-D4. The budget.** `run_family(family, *, budget)` counts attacks
  attempted, in the family's order; the specimen and the control are detector
  diagnostics, not attempts. A FamilyRun records `budget`, `available`,
  `attempted` and `exhausted`, so a truncated run reports what it left.
- **AT-A-D5. Held-out controls.** `run_family` refuses any control whose split
  is not `trained` (`HeldOutControlRefused`); `adapter.run_adapter` asks the
  adapter for its trained controls only. `adapter.held_out_outcomes` and
  `wrongful_rejection` evaluate held-out controls for the wrongful-rejection
  rate and feed nothing back into a run.
- **AT-A-D6. A control must say it was accepted.** A control is evaluated by
  its own `check()` or by the boundary's boolean `accepted`. A boundary that
  only reports breaches cannot show a wrongful refusal, so such a control
  answers nothing (CRASHED) rather than passing. Battery's `control_from`
  (formerly `_control_passes`) keeps its exact semantics.
- **AT-A-D7. The adapter interface.** `Adapter` protocol: `challenge_id`,
  `level` (0-5, `ladder.LEVELS`), `contract_digest`, `families()`
  (`FamilyDef`), `controls(split)` (`Control`, versioned), `oracle(family,
  attempt)` (`OracleResult`), `rebuild(construction)` (`Rebuilt` or
  `Unrebuildable` with a code from `UNREBUILDABLE_CODES`), `level_families()`
  (`SeamFamily`, always NOT_RUN). `validate` refuses an adapter that leaves
  one of the eight checks unsupplied, or a run family without a trained and a
  held-out control. `DeclaredAdapter` is the common declarative shape.
- **AT-A-D8. The registry.** `ADAPTERS[(challenge_id, level)]`. Built-in
  adapters register themselves from `carbon.agent_campaign.attack.adapters`,
  imported once on the registry's first read or registration; a clash is
  refused.
- **AT-A-D9. Permission ablation reuses the climb unchanged.**
  `adapter.ablation_family` turns a `climb.ClimbPlan` into the
  baseline_and_permission_ablation family: every item that needs a new
  permission, run under the profile without it, must come back REFUSED. The
  climb refuses Level 0 plans, so at Level 0 an adapter cites the climb's
  evidence instead.
- **AT-A-D10. The suite, verbatim.** `suite.py`, `suite_v1.json` and
  battery's suite map land as on be61e7435, so their digests are the
  committed coverage report's. Added without changing either digest: the
  suite loader refuses a suite whose vectors do not map exactly the eight
  admission checks, and `vectors_by_check()` maps each check to its vectors.
  `SUITE_V1_BATTERY_COVERAGE.json` lands verbatim with its own provenance: it
  ran on e880a4f96, a branch commit outside main's history. It is the pinned
  report for this suite and map, not a fresh run on main; a canonical re-run
  on main (all five dependency groups) is a follow-up.
- **AT-A-D11. "Stage" renamed for pipeline stages.** Graphite's permission
  ledger now says `pipeline_stages` and `graphite_may(pipeline_stage, role)`
  (schema `graphite-ledger.v2`), because a research session's `stage`
  (`research_loop.run_epoch(stage=)`) is a different thing. The ledger cites
  `Design_Specs/Challenge_Roadmap.md` (the branch's PROTOCOL_DRAFT.md is not
  on main). The frozen run admits no role, enforced by the loader.
- **AT-A-D12. The Graphite Challenge record, v2.** `graphite/challenge.py`
  keeps the branch's pattern (record, adapter, pipeline record) with the
  adapter now the attack adapter registered for the Challenge at its
  recorded level, carrying the session surface a Graphite session needs. The
  record's campaign has no call cap and no second copy of a ceiling; its
  grant names an id and that id's file. Battery's record names
  GRAPHITE-GRANT-PHASE4 (the file is slice AT-E's).

### Not done here

- The reuse branch's `graphite/stage.py` (stage profile) is not landed: it is
  outside this slice's files. Whoever wraps it should use the renamed
  `pipeline_stages` ledger.
- The `python -m carbon.challenge_pipeline suite` subcommand (branch
  `__main__.py`) is outside this slice's files; `suite.run()` is callable.

**Maturity.** IMPLEMENTED and TESTED (DEVELOPMENT, in-process, synthetic and
battery Level 0). No security acceptance, no qualification, no LIVE state.
