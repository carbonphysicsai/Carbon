## 2026-10-07 — LAUNCHPAD-LEVELS-01-S1: the ladder view reads the variant registry as data

**Authority.** OWNER-LADDER-THROUGH-LAUNCHPAD-01; LAUNCHPAD-LEVELS-01 §S1. This
is an engineering decision within the ticket's delegated scope.

**Decisions.**
1. **No variant-module import.** `tests/invariants/
   test_development_variants_unreachable.py` holds that no Launchpad or MCP
   module reaches `development_variants`. The owner's amendment widens what
   the development-ladder deployment may be sent. It does not lift that
   invariant, and S1 sends nothing. So the view, in
   `scripts/dev/miner_launchpad/ladder_view.py`, reads the variant documents
   as data:
   - the registry, through `capability_registry.development_variant_registry()`;
   - each document's digest, checked against its pin
     (`expansion_record.digest_of`);
   - each document's base, checked against the live contract and its newest
     expansion record, as `check_base` does.
   A document that fails is shown by name with `development_variant_altered`,
   `_malformed` or `_base_stale`, and nothing it widens is shown.
   - The variant module's level range (1-3), scope and refusal codes are
     copied as constants.
   - `tests/cpu/test_launchpad_ladder_view.py` holds them equal to the module's
     own, and holds every identity equal to `development_variants.variant()`.
2. **The deployment's own level is not named yet.** No deployment declares
   its level today. The `ladder` operation therefore builds with
   `deployment_level=None`, and no level is labelled `DEVELOPMENT`. That is
   fail closed: `MINER_FACING` is only the record's `chosen` level, and
   everything else is `NOT_OFFERED`.
   - `ladder_view(challenge, deployment_level=N)` labels every level above N
     `DEVELOPMENT`. S2 supplies N from the target intake's public facts.
3. **The campaign's level is 0.** A Launchpad campaign compiles only against
   the Challenge's registered contract (`CONTRACTS`), which is construction
   Level 0. Every miner-facing door refuses a variant digest. So the Contract
   view's `construction_level` gives `level: 0` and `status: DEFINED` where a
   pipeline record places the Challenge on the ladder.
   - It adds `text`, `state`, `audience` and `ladder`. The original keys
     `level`, `status` and `basis` stay.
   - With no record it stays `NOT_YET_DEFINED`, and when the data cannot be
     read it is `UNAVAILABLE`. It is never inferred.
4. **Capabilities merge by id.** A level's rows are its accepted proposal's
   capabilities, in the proposal's order, as `{id, summary, proposal: {adds,
   bounds}, widened: [...]}`. Each shown variant's widened entries, the
   level's own and its arms', attach to the row with the same id. A widened
   id the proposal lacks is added after them with `proposal: null`. Examples
   are `optimizer.muon_spectral` at L2 and `numerics.*` at L3.
5. **The compute budget is the base contract envelope's.** Variant documents
   carry no envelope, so every level shows the base contract's
   `compute_budget`, or `{"status": "NOT_SET"}`.
