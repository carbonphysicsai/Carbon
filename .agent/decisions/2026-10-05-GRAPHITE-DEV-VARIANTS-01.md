## 2026-10-05 — GRAPHITE-DEV-VARIANTS-01: development-only construction-contract variants, refused on every miner door, and W2's review items

**Authority.**
- OWNER-GRAPHITE-TEST-WAVE-03 (`.agent/decisions/2026-10-04-OWNER-GRAPHITE-TEST-WAVE-03.md`,
  carbonphysicsai/Carbon#574) §1 and §2. Approved by the owner on 2026-10-04
  for this W1 foundation.
- OWNER-GRAPHITE-DEV-LEVELS-01 (`.agent/decisions/2026-10-04-OWNER-GRAPHITE-DEV-LEVELS-01.md`):
  "Drafted surfaces OK" and "Declarative menu only".
- The Test Lead's review of W2 (GRAPHITE-CONDITIONAL-EXPLORATION-01, #577),
  items 2 and 6 and the climb nit. They are required here.

Everything below is an engineering choice within that delegated authority.
No scientific value, threshold, gate, score or tolerance changes, and no
miner-facing contract widens. There are no weights, no chain writes, no live
run and no spend. This is W1 of the test wave. It builds on W2 (#577): its
development ledger and `record_development_expansion`.

**Decisions.**

1. **A variant is a registered, versioned policy, `carbon.construction-development-variant.v1`.**
   - **Where.** `carbon/reconstruction/development_variants.py`. It is stdlib
     only at import.
   - **The policy files.** One document per version in
     `carbon/reconstruction/development_variant_policies/<version>.json`, plus
     a `registry.json` that pins each version's digest and names the current
     version of each (challenge, level). This follows Graphite's attribution
     policies (#573) and `battery/exam.py` RULES.
   - **What a document names.**
     - the Challenge and the level;
     - the base contract's digest and the expansion record that pins it;
     - each widened capability with its catalog surface and its stated bounds;
     - the Test Lead's review record;
     - `participant_code: false`.
   - **Its digest.** The digest is the sha256 of the document's canonical
     JSON, which is the rule `expansion_record.digest_of` uses.
   - **Change control.**
     - A document whose digest is not the pinned one is refused
       (`development_variant_altered`).
     - Every lookup re-reads the pinned registry. `DEV_VARIANTS[(challenge, level)]`
       is a read-through mapping, not a snapshot taken at import.
     - A version, once registered, is never removed, so the miner doors keep
       refusing it. A superseded version stays refused to miners and no
       longer runs.
   - **Shipped empty.** This PR ships the mechanism and an empty registry.
     Fixture variants (`FIXTURE_NOT_PRODUCTION`) exist only in test temporary
     directories. Loading one from the shipped directory is refused
     (`development_variant_fixture_in_shipped_registry`).

2. **The owner's bounds, enforced when a document loads.**
   - **Levels.**
     - Only Levels 1–3 are allowed.
     - Level 0 is the miner-facing contract itself
       (`development_variant_level_invalid`).
     - Levels 4–5 wait for the security owner's isolation acceptance
       (`development_variant_level_requires_isolation`, WAVE-03 §3).
   - **No participant code at any level**
     (`development_variant_participant_code_refused`).
   - **Level 3 (F2).** Every widened surface at Level 3 is a fixed `choice`
     menu (`development_variant_level3_is_a_declarative_menu`). Numeric and
     boolean surfaces are refused there.
     - This is the narrowest reading of "a fixed bounded menu as data". The
       Test Lead may widen it to bool or bounded integers as a later version.
   - **Every widened surface is bounded and new.**
     - It is a catalog surface (`uint`, `float`, `bool`, `choice`) with finite,
       ordered bounds, or no surface plus a stated bounds object.
     - It names a capability the base contract does not already rebuild
       (`development_variant_widens_nothing`) and a field name the contract
       does not already have.
   - **Staleness.** A variant's base must be the live contract and the
     expansion record that pins it. A stale base is refused where the variant
     is used (`development_variant_base_stale`), so one stale variant does not
     disable the rest.

3. **Development expansion records: `expansions/<token>/dev/NNNN.json`.**
   - **Schema.** `carbon.construction-development-expansion-record.v1`.
   - **What each record binds.**
     - the variant's digest and its full document;
     - the base contract record (its sequence and digest);
     - a statement of what widened.
   - **Separate from Level 0.** `expansion_record.records` reads only the
     4-digit files beside the folder, so the Level 0 trail is unchanged.
   - **Checks.** `dev_problems` checks the trail is append-only and bound to
     a real base record. `dev_unrecorded` names each current variant that no
     record pins.
   - **The CLI.**
     `python -m carbon.reconstruction.development_variants record|check`.
   - **What a run constructs under.** `recorded_variant(v)` returns the
     binding a development run constructs under. It refuses a variant without
     a record (`development_variant_unrecorded`). That is the climb
     procedure's expansion record for the development variant.

4. **Every miner-facing door refuses a variant by name: `development_variant_not_served`.**
   - **How the doors know a variant.**
     - The doors never import the variant module. They read the registry as
       data through `capability_registry.is_development_variant`, which knows
       every registered version's name and digest.
     - A missing or malformed registry raises, so the doors fail closed.
       `pyproject.toml` ships the registry as package data.
   - **The doors:**
     - `capability_registry.contract` (and so `public_registry`,
       `catalog_surfaces` and every other lookup) raises
       `DevelopmentVariantNotServed`, a subclass of `UnknownChallenge`, so
       existing callers still catch it.
     - `challenge_contracts.validate_for_challenge` takes an optional
       `contract_digest` and flags a variant digest, or a variant named as
       the Challenge. `check_contract_digest` and `compile_submission` refuse
       it.
     - The validator (`challenge_validator/dispatch.py`):
       - `Validator.evaluate` refuses the digest, and records the refusal;
       - `Validator.outcome` refuses it;
       - `Adapters` refuses an adapter that would serve one.
     - The battery daemon refuses the digest at admission, before compiling.
       `identities()` refuses to bind a variant as its served contract.
     - The intake refuses the digest before queuing it (HTTP 400). The code
       has a plain explanation in `intake_client.REFUSALS`.
     - The Challenge registry's `_find` refuses a variant named as a
       Challenge or a version. That covers the miner MCP `describe` tool and
       the Launchpad's launch (`RunnerAdapter._challenge`).
     - The Launchpad's submit path (`battery.campaign.submit_through_intake`)
       sends nothing for a variant digest.
   - **Tests.** Each door has a behavioural test. Each door's own check is
     also switched off once and its test shown to fail, because the generic
     refusal behind it would otherwise hide a missing check.
   - **The static invariant.**
     `tests/invariants/test_development_variants_unreachable.py` shows that
     no miner surface, the validator, the intake or its daemon, or the
     Challenge registry can import the variant module.
     - It reuses the attack-store invariant's AST walk and its runtime
       import check, with numpy stubbed where it is absent.
     - Two specimens are planted: one found by the static check and one by
       the runtime check.

5. **`compile_development(strategy, variant)` is a development-only compile path.**
   - **How it compiles.**
     - It accepts only a registered variant with a fresh base.
     - It checks each widened value against its bounds.
     - It compiles the rest through `compile_submission`, against the base
       digest.
     - It rebuilds each widened value with Carbon's registered reconstruction,
       `RECONSTRUCTIONS[(challenge, capability)]`.
   - **No reconstruction, no compile.** A variant whose capabilities lack a
     reconstruction never compiles (`development_reconstruction_missing`).
     This is OWNER-GRAPHITE-02's reconstruction rule. `RECONSTRUCTIONS` is
     empty in this PR.
   - **The binding.**
     - The compiled result carries `development`: the variant's digest, its
       level and a digest of the widened values with their reconstruction.
       Two widened values never share one binding, even though their base
       recipe does.
     - Battery's scoring is split into `built_record` (compile, then build)
       and `built_from` (build from an already compiled construction). The
       build adds `development` to a built record only when the construction
       has one. The validator package never imports the variant module.
   - **Its only callers.**
     - Graphite's experiment (`experiment.admit(..., variant=)`);
     - the pod phase (`pod_phase.development_built_record`, chosen when the
       job names `development_variant`);
     - the synthetic pods;
     - the bundle's clean rebuild.
   - **The rebuild check** also compares `development`. Level 0 calls
     `compile_submission` unchanged, and its pod job configuration is byte
     for byte the same.

6. **`--level` for phase 3 and phase 4.**
   - **Level 0, the default.** It behaves exactly as before: the same
     profile, profile digest, brief and job configuration.
   - **A level above 0.**
     - It resolves the registered variant from `DEV_VARIANTS`. An
       unregistered level is refused (`development_variant_unregistered`)
       before anything runs.
     - The session's permission profile is the variant itself: its document,
       pinned by its digest.
     - `recorded_level`/`recorded_variant` read the level back from the run's
       task.
     - The brief's `construction_contract` is `recorded_variant`.
     - `run_session` records the variant on the controller as a development
       expansion before it launches.
   - **Phase 4.**
     - It resolves the variant first, then the attack adapter registered under
       (challenge, level). A missing adapter is
       `no_attack_adapter_for_challenge_level`.
     - A development-level adapter must attack its variant: its contract
       digest is the variant's digest.

7. **Test Lead item 2: "development" is registered, never declared.**
   - **Recording.** `record_development_expansion` accepts only a
     permissions digest that `DEV_VARIANTS` currently registers for that
     Challenge, with a development record. Anything else is
     `development_variant_unregistered` (or `_unrecorded`). The entry's
     `version` names the development record and the variant.
   - **Launch.** A spec whose profile names any registered variant, or that
     matches the development profile, must be the newest development
     expansion and still registered now. This holds even when the campaign
     was registered under that digest, which closes the route where a
     campaign registered under a variant launches with no development
     expansion.

8. **Test Lead item 6: a LOCK binds more than the study's ledgers.**
   - **Why stripping worked.** Item 7 means every development entry's
     permissions digest is a registered variant's. A development entry with
     `kind` and its tags stripped therefore still names one.
   - **Static check.** `admission._expansions` refuses such an entry
     (`admission_development_expansion_refused`). This applies at every
     validation, the LOCK included.
   - **Cross-check.** `CampaignController.check_lock(block, challenge_id, repository=)`
     validates the block, then checks it against the controller's own
     ledgers:
     - a study expansion whose permissions the controller recorded as
       development is refused;
     - a controller finding the study omits, or records with another
       condition or evidence, is refused
       (`admission_lock_finding_omitted`).
     - The cross-check catches a variant the registry no longer names.

9. **The climb nit: a development climb continues and tags.**
   - **The plan.** `ClimbPlan.development_variant` names a registered variant
     at the plan's level, or None.
   - **A development climb.**
     - It runs every step past a finding.
     - Each in-climb finding gets an id (`climb-finding-NNN`).
     - Every run recorded after it carries `conditional_on` with it and with
       the controller's open findings.
     - The report's status is `COMPLETED_CONDITIONAL`, and the report itself
       is tagged.
   - **The LOCK path is unchanged.** A plan with no variant stops exactly as
     before. Its report has the same keys and values; findings get no ids.
   - **Supersedes.** This supersedes GRAPHITE-CONDITIONAL-EXPLORATION-01's
     "Not wired: the climb harness's own internal stop rule" for development
     plans only.

**Tests.**
- `tests/cpu/test_development_variants.py`: the mechanism, the owner's
  bounds, the records and the compile path.
- `tests/cpu/test_development_variant_refusals.py`: each door, with one
  mutation per door.
- `tests/cpu/test_development_variant_daemon_intake.py`: the daemon and the
  intake, each with its mutation.
- `tests/cpu/test_development_variant_controller.py`: items 2 and 6 and the
  climb, with one mutation per guard.
- `tests/cpu/test_graphite_development_levels.py`: phase 3 and phase 4
  `--level`, and a full dry-run session at a development level, with
  mutations.
- `tests/invariants/test_development_variants_unreachable.py`: the static
  and runtime invariant, with planted specimens.
- W2's tests now record development expansions under fixture variants, and
  W2's LOCK-ledger mutation also switches off the new permissions check.

**Maturity.** Implemented and tested against synthetic fixtures. Not
scientifically or security qualified. No real Level 1–3 surface exists yet.

**Open for the Test Lead.**
- The first real Level 1–3 surfaces, each with its bounds and its
  reconstruction, for review before registration.
- Whether Level 3's menu rule should also admit bool or bounded integer
  menus. That would be a later version.
- Battery's Level 1 draft (`carbon/battery/level1_draft.py`) is a natural
  first variant. Its expression surface has no catalog `Surface`, so it would
  register with a bounds object and a reconstruction that wires the trainer.
