# LAUNCHPAD-LEVELS-01: construction levels in the Launchpad, from data

**Authority:**
- OWNER-LADDER-THROUGH-LAUNCHPAD-01 (2026-10-07);
- OWNER-LEVEL4-GRAPH-ONLY-01;
- OWNER-GRAPHITE-TEST-WAVE-03 §1, as amended by the first.

**Status:** S1 IMPLEMENTED (on main). S2 and S3 IMPLEMENTED and TESTED with
fixture intakes and registry fixtures (2026-10-09; decisions in
`.agent/decisions/2026-10-09-LAUNCHPAD-LEVELS-01-S2-S3.md`). Real-run
acceptance (plan §3.8, cells L1–L4) is pending VALIDATOR-25 slice 2's
`served_contracts` and the ladder deployment for `carbon-rehearsal-minerC`.
S4 (Level 4's envelope sent in signed parts to a target whose `tools` list
them; decisions in `.agent/decisions/2026-10-10-LAUNCHPAD-LEVELS-01-S4.md`)
is IMPLEMENTED and TESTED with a fixture ladder intake. It follows
LAUNCHPAD-ACCEPT-04 (#778).

## What exists (origin/main df26107c2)

- **The ladder.** `carbon/challenge_pipeline/ladder.py` defines the six
  level texts, the states OPEN, TESTED and FROZEN, and `LAUNCH`.
  - A pipeline record carries `{challenge, level, chosen, levels[...]}`.
  - Only battery's record (`records/f05.json`) has a block: level 0,
    `chosen: null`.
- **The proposals.**
  `carbon/challenge_pipeline/proposals/battery-fastcharge-ageing-development-v1/level-0..5.json`
  are all ACCEPTED.
  - Their capabilities are prose (`id`, `adds`, `bounds`, `rationale`, …).
  - They are validated by `carbon/challenge_pipeline/proposals.py`.
- **The development variants.** These are the machine-readable part.
  - The registry: `capability_registry.development_variant_registry()`.
    It currently holds battery L1 `battery-l1-loss-expressions-v1` (plus arm
    `signed`), L2 `battery-l2-spectral-v1` and L3 `battery-l3-numerics-v1`.
  - Each variant document lists `widened[{id, summary, surface, applies_to,
    bounds}]` against a pinned `base_contract`.
  - `development_variants.variant(challenge, level, arm)` gives the current
    variant, and `compile_development` checks a recipe against it.
  - `development_variants.LEVELS = (1, 2, 3)`.
- **Binding.** A variant has its own contract digest. The commitment digest
  is `{challenge, contract_digest, strategy_hash}`, so it already binds the
  level and variant once the frozen recipe carries the variant's digest.
  **No commitment schema change is needed.**
- **What a deployment declares.** Nothing, today, about which levels or
  variants it serves:
  - `development_only` admits variant digests only for `graphite-dev:`
    hotkeys, through an injected compiler;
  - it requires `require_commitment: false`.
- **The compute budget.** `check_compute_budget` reads the contract
  envelope's `compute_budget`. Battery's envelope has none, so the view shows
  "not set" and invents nothing.
- **The slot to fill.** `campaign_view.py` has `construction_level:
  {level: None, status: NOT_YET_DEFINED}` (RSURF-D10), never inferred.

## Slices

**S1: levels shown from data, read-only, on both doors.**
- A generic `ladder_view(challenge)` reads the ladder record, the proposals
  and the variant registry. For each level it gives:
  - its ladder text and its state;
  - **miner-facing** (the chosen or launch level) or **DEVELOPMENT** (every
    level above the target deployment's own);
  - its capabilities: id and summary from the proposal, and, where a
    registered variant widens them, the machine surface and bounds from the
    variant document (`optimizer.muon_spectral`, `numerics.*`, …);
  - its variant identity: name, digest and arm, or none;
  - its compute budget from the contract envelope, or "not set".
- It fills `construction_level` in the Contract view with the campaign's
  level.
- A read operation `ladder` sits in `OPERATIONS`, so both doors serve it.
- Tests: fixture ladders for levels 0–3 render with no per-level code, and
  an empty level shows its `left_out` reason.

**S2: choose a level at freeze, commit and submit.**
- A campaign may be launched at a level, `construction_level: N` with an
  optional `arm`, which binds the level's current variant digest into the
  manifest.
  - Practice compiles with `compile_development` for N ≥ 1.
  - Freeze records the variant digest as the recipe's `contract_digest`.
  - The commitment then binds it unchanged.
- **Before signing**, submit refuses with closed codes:
  - `level_not_served_by_target`: the target intake's public facts do not
    list the frozen digest among the digests it serves;
  - `level_not_registered`: no current variant for the level or arm.
- This needs the Carbon Validator to advertise the served contract digests
  in the intake's public facts, which is a validator-domain interface. Until
  that exists, every N ≥ 1 submit is refused `level_not_served_by_target`
  (fail closed). Level 0 is unchanged.
- The refusal in `campaign.py` (`development_variant_not_served`) stays for
  every target that does not list the digest.
- Door parity, so Graphite and any MCP agent can drive it.

**S3: the Level 4 slot.** *Built (2026-10-09) against the Level 4 staging
contract, which superseded the design-note plan below: freeze verifies the
lowered directory and keeps its staging envelope; submit fails closed until
an intake carries it.*
- A design note for a graph-artifact submission, in the format of
  `scripts/dev/level4_spike/graph.py` (`carbon.development.level4-graph.v0`)
  and its allowlist, from #746.
- It covers what the frozen recipe would carry (the graph digest) and how
  the commitment binds it.
- It is built when Level 4's Phase 3 starts.
- Plus acceptance-matrix cells, L-N for each level's Launchpad pass (plan
  §3), each needing real runs on the development-ladder deployment.

## Boundaries

- No level's bounds, gates or scoring change. The Launchpad shows and binds;
  the validator decides.
- No level is offered as miner-facing unless the ladder record says so.
- Exploration and attacks stay on the development door.
- Levels 4 and 5 stay refused until the security owner accepts isolation.
- The development-ladder deployment is the Carbon Validator's to build, and
  it is never mainnet until the owner locks a level.
