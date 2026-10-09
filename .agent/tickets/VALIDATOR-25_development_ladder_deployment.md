# VALIDATOR-25: a testnet development-ladder deployment on valV2

**Status:** slice 1 implemented (2026-10-09). The plan was approved by the
Test Lead on 2026-10-07, and its prerequisites have landed: #772
(`development_rebuild`) and OWNER-LADDER-THROUGH-LAUNCHPAD-01. The Test Lead
made it top priority on 2026-10-09, because it blocks Graphite ladder testing.

## Design revisions (2026-10-09, under delegated engineering authority)

1. **No per-level rule.** A rule change moves the rule digest. A producer
   package imports only into a validator whose rule digest matches, so a
   `v2-ladder-lN` rule could not share the main deployment's live windows,
   which the Test Lead settled. Instead, the ladder runs the main
   deployment's rule, and carries its level and its accepted variants in the
   deployment configuration (`ladder: {level, hotkeys, variants}`).
2. **A ladder kind of development deployment.** This is for the owner to
   confirm: the record leaves "development_only, or a new kind" to this
   design.
   - **What stays as for any `development_only` deployment:** its weights are
     refused, and its outcomes carry the development label.
   - **What differs:** a plain `development_only` deployment must have no
     chain commitment. The ladder is reached through the Launchpad, so it
     requires the commitment, on Carbon's testnet only (an allow-list:
     `testnet`, netuid 567).
   - Only the `ladder` key lifts that exclusion.

## Slices

1. **Admission (this slice).**
   - `deployment.ladder_for` validates the configuration. It refuses with
     `evaluation_config_ladder`, `_testnet_only`, `_level_4_not_open` and
     `_variant`.
   - The daemon admits only listed hotkeys (`ladder_hotkey_not_listed`, before
     anything) and only listed variants of its level
     (`ladder_level_not_accepted`, `ladder_level_4_not_open`,
     `ladder_variant_not_accepted`). The level is read from the registry as
     data (`capability_registry.development_variant_document`, with its digest
     rechecked). The variant module is never imported.
   - A listed variant still fails closed (`development_variant_not_served`)
     until the service injects the compiler.
   - Every new code has its miner text (`intake_client.REFUSALS`) and its
     Launchpad step.
2. **The door and the service.**
   - The neutral screen passes the deployment's declared variants, routed to
     the base contract's adapter (registry data only).
   - The intake advertises the variants it serves, for the Launchpad.
   - `carbon.development_ladder.service` wraps the intake and daemon and
     injects the development compiler and rebuild. It is a declared
     development surface in the invariants.
3. **The owner's operator steps** on valV2:
   - the deployment file;
   - the service unit on a second loopback port;
   - the tunnel;
   - minerC's Launchpad profile.
4. **The Level 4 slot and upload,** refusing until Level 4 Phase 3 (below).

Security-sensitive (AGENTS.md §13): it admits development variants through a
real door. It needs a dedicated review. It ships in a producer and validator
tag after `producer-code-r2`.

**Authority:**
- OWNER-LADDER-THROUGH-LAUNCHPAD-01 (owner, 2026-10-07, relayed by the Test
  Lead; the record arrives with the Launchpad's PR);
- OWNER-GRAPHITE-DEV-LEVELS-01;
- OWNER-GRAPHITE-TEST-WAVE-03 §1;
- OWNER-LEVEL4-GRAPH-ONLY-01;
- OWNER-REHEARSAL-CPU-CLASS-01;
- OWNER-BANK-ARCHITECTURE-01.

**Executor:** the Carbon Validator session.

## Design

1. **A separate deployment** (`battery-dev-ladder`), beside valV2's main
   battery deployment, which stays Level 0 and unchanged.
   - It is under `carbon-val` on the AX42 (OWNER-REHEARSAL-CPU-CLASS-01),
     with its own state, root, journal and loopback intake port.
   - Its config carries `"ladder": {"level": N}`, which requires
     `development_only: true`.
   - The same AX42 tunnel reaches it, on a second port.
2. **One versioned rule per level** (`exam.RULES`). *Superseded by design
   revision 1: the level and its variants are deployment configuration, and
   the rule is the main deployment's.* The original plan was:
   - `v2-ladder-l1`: Level 1;
   - `v2-ladder-l2`: `muon_spectral` (#765) and `pool_selection`;
   - `v2-ladder-l3`: `numerics.*`.

   Each names its level and the exact accepted development-variant digests,
   pinned from `development_variant_policies/registry.json`. Scoring is v2's,
   unchanged.

   **Admission** refuses before any rebuild, by closed code:
   - `ladder_level_not_accepted`: a submission naming another level's
     variant;
   - `ladder_variant_not_accepted`: a variant digest the rule does not list;
   - `ladder_level_4_not_open`: any Level 4 graph artifact.
3. **Who submits.** Only the hotkeys listed in the deployment's
   registered config (`ladder_hotkeys`, public SS58s). That is the Launchpad
   path with real hotkeys, chain commitments and the signed intake.
   - The first entry is `carbon-rehearsal-minerC`, registered 2026-10-08 as
     UID 7 on 567, hotkey `5E49MhzFLBv35AbSPgtwrutCd6yvDm6GK9EC5ocmJ3Czb48N`.
     Adding minerD later is a config change.
   - **Never minerA or minerB.** A hotkey's on-chain commitment is one per
     tempo per netuid. Our intake reads it per chain hotkey, and freshness
     per deployment store. A hotkey shared between the main deployment
     (Level 0) and the ladder would therefore have the two take each other's
     slots.
   - The `graphite-dev:` prefix test is replaced, for this deployment only,
     by membership in that list.
   - Any other hotkey is refused (`ladder_hotkey_not_listed`). A level tested
     here is still never opened to miners (OWNER-GRAPHITE-DEV-LEVELS-01).
4. **Rebuilds through #772.** Admission compiles through the injected
   `development_compiler`, and the rebuild routes through
   `development_rebuild`.
   - Both are supplied by a separate service entry point,
     `carbon.development_ladder.service`, which wraps the intake and daemon.
   - So `carbon/battery/intake.py`, `daemon.py` and `carbon/challenge_validator`
     still never import the variant module, and the unreachable invariants
     hold unchanged.
   - The new entry point is added to the invariants as a declared development
     surface: it may reach the variant module, but no miner surface may reach
     it.
5. **Isolation:**
   - **Weights:** none. `testnet_winner_publication` and `battery_promotion`
     refuse a ladder deployment (`WEIGHT_SOURCE_DEVELOPMENT`), as they refuse
     `development_only` today. Scores are evidence only. I see no reason to
     weight testnet from it: it would mix development variants into the
     incentive signal the main deployment rehearses.
   - **Labels:** every outcome and record carries `evidence:
     DEVELOPMENT_LADDER`, the level and the variant digest. Nothing promotes
     or settles from it.
   - **Shared answer key, one exposure account.** It imports the same
     packages as the main deployment and holds no bank of its own.
     - Bank exposure is counted per drawn window, not per validator
       deployment, so a window both deployments score on is one appearance,
       counted once at the producer.
     - Any separate draw for the ladder goes through the same `BankLedger`, so
       E counts every appearance.
     - A test pins both.
   - **Mainnet:** never, until the owner locks a level. Its rules are refused
     on a mainnet chain context (`ladder_not_on_mainnet`).
6. **The Level 4 slot.** `v2-ladder-l4` is reserved: a graph artifact
   (Phase 1's interpreter and allowlist) gets a typed admission path, which
   is refused with `ladder_level_4_not_open` until Level 4 Phase 3. Opening
   it is a later rule version.

### The Level 4 artifact and its transport (agreed with the Level 4 engineer, 2026-10-08)

- **The format** is single-sourced in `carbon/level4/submission.py` (#790,
  LAUNCHPAD-LEVELS-01): one manifest, `carbon.development.level4-submission.v0`,
  plus documents named by the sha256 of their canonical bytes. The
  submission digest is `digest(manifest)`.
- **Checks** are `carbon/level4/intake.py` (#794): G0 sizes and G3
  (isolated parse, then verify), then `validate.validate_submission` (G4).
  - An unset bound is `IntakeBlocked`, which this slot maps to
    `ladder_level_4_not_open`.
  - A worker that cannot start is `IntakeInfraFailure`, which maps to
    `FAILED_INFRA`.
- **Transport: option (a), agreed.** A graph exceeds the request body
  bound (`MAX_BODY`, 64 KiB), so documents get a separately bounded upload,
  keyed by document digest. The constraints:
  - it is `btauth/1`-signed per upload for the deployment's receiver, from a
    listed ladder hotkey only;
  - each document's sha256 is verified on receipt;
  - documents are held owner-only and pre-admission, and expire when no
    admitted manifest names them;
  - they are never served back, and never reach another deployment;
  - the manifest still travels in the normal signed submission, and
    admission refuses unless every named document is present and verified;
  - the per-document and per-submission size bounds are **HUMAN_INPUT**.
    While unset, the upload refuses (`ladder_upload_bound_unset`).
- **Receiver steps** follow the Level 4 staging contract (#807,
  `carbon/level4/staging.py`; spec
  `docs/development/graphite/level4/LEVEL4_STAGING_CONTRACT.md`; the
  Launchpad gets the same spec):
  1. the transport bound above, then `staging.from_envelope`;
  2. the declared submission digest must equal the strategy's Level 4 field;
  3. `intake.intake` (G0, G3), then G4;
  4. store the bytes as received, keyed by submission digest;
  5. at rebuild, `staging.workspace(...)` beside the record.

  **Failure ownership:** a refusal before G0 is the candidate's; a corrupt
  workspace in the worker is `StagingCorrupt`, which is FAILED_INFRA and
  Carbon's.
  - It is built with the Level 4 slot. Until Level 4 Phase 3 (and D3), the
    slot and the upload both refuse; every Level 4 rebuild fails closed.

## Tests

- **Refusals, each before any rebuild:**
  - per level: another level's variant, an unlisted digest, a Level 4
    artifact;
  - an unlisted hotkey.
- **Isolation:**
  - the weights publisher and `battery_promotion` refuse the ladder
    deployment;
  - the main deployment's weights are unchanged by any ladder score.
- **Exposure:** a window imported by both deployments counts one appearance;
  a ladder draw through the ledger counts toward the same E.
- **A rebuild through #772 per level** (fixture recipe per variant), and the
  development label on every outcome.
- **The invariants:** the validator and intake still never reach the
  variant module.

## Settled (Test Lead, 2026-10-07)

- **Shared live windows: yes.** That is mainnet-shaped, needs no extra
  producer solving, and keeps one exposure account.
- **Hotkeys:** a registered config list, starting with minerC (§3).
- **The record:** OWNER-LADDER-THROUGH-LAUNCHPAD-01's wording comes with the
  Launchpad's PR.

## Maturity ceiling

IMPLEMENTED and TESTED. Development evidence only. No weight, settlement,
promotion or mainnet authority.
