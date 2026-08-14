# Ticket A3 — Challenge registry + LIVE gate (C1)

**Wave:** A  
**Build_Out:** C1 Challenge registry, §8 LIVE qualification manifest  
**Depends on:** A0  

**Goal:** File-backed registry of challenges; **cannot** transition to LIVE without qualification slots filled.

**DoD:**
- [ ] Load/save registry (YAML or JSON) e.g. `carbon/registry/` + fixture under `tests/fixtures/`
- [ ] Challenge record fields: `challenge_id`, `version`, `status` (`draft`|`fixture`|`live`), content hashes placeholders
- [ ] `can_go_live(challenge_id) -> bool` is **False** if any required qualification slot missing or still `HUMAN_INPUT`
- [ ] Required slots (schema only; humans fill later): generator_envelope, generator_validation, dossier_level_1, score_pack, mock_incompleteness, train_backend, launch_bar, mcp_readiness (per Build_Out §8)
- [ ] Default status is never `live`
- [ ] Tests: missing slot → blocked; all slots present with dummy APPROVED hashes → True **only in fixture mode** (still OK to require signed flag false for Wave A)

**Must not:** Ship any challenge with `status=live` by default. Do not invent real scientific hashes.

**Tests:** `pytest tests/test_registry.py -q`

**Pin to Carbon:** Registry is the LIVE kill-switch; scoring/MCP must consult it before treating a challenge as emission-eligible later.
