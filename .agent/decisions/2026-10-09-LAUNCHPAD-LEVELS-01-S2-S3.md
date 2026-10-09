## 2026-10-09 — LAUNCHPAD-LEVELS-01-S2-S3: construction levels chosen at launch, compiled in a child process, served only where listed

**Authority.** OWNER-LADDER-THROUGH-LAUNCHPAD-01 (and its amendment of
OWNER-GRAPHITE-TEST-WAVE-03 §1 for the development-ladder deployment);
OWNER-LEVEL4-GRAPH-ONLY-01; LAUNCHPAD-LEVELS-01 §S2, §S3; the Level 4
staging contract (`docs/development/graphite/level4/LEVEL4_STAGING_CONTRACT.md`).
The Carbon Validator confirmed the intake field on 2026-10-09:
`served_contracts: [{level, variant?, digest}]`, shipping in VALIDATOR-25
slice 2. These are engineering decisions within the ticket's delegated
scope; nothing here sets a bound, gate, score or value.

**Decisions.**

1. **One generic mechanism.** `carbon/development_session/construction_level.py`
   holds every rule; `scripts/dev/miner_launchpad/levels.py` only maps its
   closed codes onto both doors from the one operations table. No Challenge
   or level has code of its own. A campaign opts in with
   `ChallengeCampaign.construction_levels` (battery only today); any other
   campaign refuses a level above 0 (`construction_level_not_offered_for_challenge`)
   rather than silently run it at Level 0.
2. **The binding is registry data, frozen in the manifest.** A launch with
   `construction_level: N` (and `arm`) resolves the level's current
   registered variant from `development_variant_registry()`, the document
   checked against its pin, and the manifest freezes
   `construction_level: {level, arm, variant, digest, scope: DEVELOPMENT,
   challenge}`. The manifest's own `contract_digest` stays the base
   contract's, so every existing reader is unchanged. Level 0 (omitted, null
   or 0) is stripped before the launch identity is computed, so a Level 0
   launch and manifest are byte-for-byte what they were.
3. **The compile runs in a child process.** No miner surface may import the
   variant module (`tests/invariants/test_development_variants_unreachable.py`,
   unchanged). A level campaign's compile therefore runs
   `python -m carbon.reconstruction.development_level_cli`, a development-door
   module beside `dev_submit`, which calls `development_variants.variant` and
   `compile_development` and answers JSON. The Launchpad and campaign
   processes never hold the variant module. This is the same isolation the
   campaign already uses for practice (a carrier). **For review:** a reviewer
   may judge that a child process the Launchpad starts still "reaches" the
   module in the invariant's spirit; if so, the alternative is to move the
   level compile behind the validator's development service, and this seam
   is the one place to change.
4. **Practice trains the Level 0 base, and says so.** Practice compiles the
   recipe at the level (bounds and Carbon's reconstruction of each widened
   value), then trains the recipe less its widened fields; the result carries
   `construction_level: {..., widened_trained: false, note}`. Training a
   widened capability in the miner's practice carrier needs the level workers
   staged into that carrier, which is outside this ticket. Practice remains
   intentionally incomplete (invariant 12); only the validator's rebuild runs
   the level.
5. **Levels need agent `none`.** Graphite's agent and its tools do not
   construct at levels yet; a level launch with another agent is refused
   `construction_level_needs_own_selection`. Any MCP agent drives a level
   campaign through the miner's own door.
6. **Freeze and commitment.** A level freeze writes the record
   `research_loop.candidate_record` writes, from the level's compile, with
   the variant's digest as `contract_digest` and the binding beside it.
   `battery.campaign.frozen_commitment` commits
   `daemon.commitment_digest(challenge, variant digest, strategy hash)`, the
   strategy hash recomputed by the level's compile at commit time: the
   commitment schema is unchanged.
7. **Served, before anything is signed.** Commit and submit read the target
   intake's public facts (through the campaign's own intake check) and
   refuse `level_not_served_by_target` unless `served_contracts` has an entry
   for the binding's level whose `variant` is its registry version name and
   whose `digest` is its digest. While the field is absent every level above
   0 is refused. An unreadable target is `intake_unreachable`, never served.
   A frozen variant that is no longer its level's current one is
   `level_not_registered`. `campaign.submit_through_intake` keeps
   `development_variant_not_served` for every target whose facts do not list
   the digest, and lifts it only where they do (the owner's amendment).
8. **The ladder's own codes stay the validator's.** `ladder_hotkey_not_listed`,
   `ladder_variant_not_accepted`, `ladder_level_not_accepted` and
   `ladder_level_4_not_open` and their next steps arrive with VALIDATOR-25
   (#895); this change does not define them.
9. **Level 4: the miner supplies the lowered directory.** The Launchpad does
   not run the lowering CLI: lowering imports the miner's own model code,
   which the Launchpad never runs. `freeze_candidate` takes
   `level4_directory`; the development door reads it
   (`staging.read_directory`), checks the strategy's Level 4 field names the
   submission, the checkout's allowlist equals the variant's pin, runs
   `submission.verify` against the Challenge and the recipe's interface
   (`<adapter>.interface(base).digest()`), and checks the forward graph's
   batch (`validate.check_interface`) equals `<adapter>.training_batch(base)`.
   The envelope (`staging.envelope`) is kept beside the frozen record and
   read back unchanged (`staging.from_envelope`); nothing re-serializes the
   submission's bytes.
10. **Level 4 size bound.** `max_bytes` is the variant's pinned
    `caps.document_bytes` (1 MiB in `battery-l4-graph-v2`). Where a variant
    pins none, or `HUMAN_INPUT`, the freeze is refused
    `level4_size_bound_not_set`; no bound is chosen here.
11. **Level 4 transport fails closed.** No intake carries the envelope yet
    (VALIDATOR-25's upload, slice 4), so commit and submit at Level 4 are
    refused `level4_envelope_transport_unavailable` before anything is
    signed, and the campaign's own send path refuses the same after checking
    the kept envelope.

**Open, for the Carbon Validator.**
- The ladder's admission today computes the expected commitment from the
  development compiler's result (`CompiledDevelopment.contract_digest` is the
  *base* contract's digest). The Launchpad commits the *variant's* digest, as
  the ticket specifies; the ladder must compute the same, or every level
  submit there is refused `commitment_required`.
- The commitment's strategy hash is the base construction's, so it binds the
  level (through the variant digest) but not the widened values; the
  admission's `widened_digest` binds those.

**Unchanged.** Every level's bounds, gates and scoring; the variant
registry; validator and intake code; the commitment schema; Level 0.
