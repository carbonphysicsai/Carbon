# Ticket A3 — Challenge registry + LIVE gate (C1)

**Wave:** A  
**Build_Out:** **v1.4** C1 Challenge registry, **§8 LIVE qualification manifest**  
**Depends on:** A0  

**Goal:** File-backed registry of challenges; **cannot** transition to LIVE without qualification slots filled **and content hashes bound to the exact challenge version**.

**DoD:**
- [ ] Load/save registry (YAML or JSON) e.g. `carbon/registry/` + fixture under `tests/fixtures/`
- [ ] Challenge record fields: `challenge_id`, `version`, `status` (`draft`|`fixture`|`live`), content hash fields
- [ ] `can_go_live(challenge_id) -> bool` is **False** if:
  - any required qualification slot missing / `HUMAN_INPUT`, **or**
  - any required artifact hash is missing / does not match the bound challenge version artifacts
- [ ] Required slots (schema only; humans fill later): generator_envelope, generator_validation, dossier_level_1, score_pack, mock_incompleteness, train_backend, launch_bar, mcp_readiness (per Build_Out §8)
- [ ] Hashes are part of the gate — **non-null field labels alone are not sufficient**
- [ ] Default status is never `live`
- [ ] Tests: missing slot → blocked; mismatched hash → blocked; all slots present with dummy APPROVED hashes for that version → True only in fixture test mode (still do not ship live defaults)

**Must not:** Ship any challenge with `status=live` by default. Do not invent real scientific hashes.

**Tests:** `pytest tests/test_registry.py -q`
