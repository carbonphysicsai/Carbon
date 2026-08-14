# Ticket A4 — Seeding domains + leakage tests

**Wave:** A  
**Goal:** Separate seed domains; enforce mock vs official; test no leakage into miner-visible surfaces.

**DoD:**
- [ ] Domains: mock, official_train, official_eval, official_stress, reference, dossier
- [ ] Domain separation helpers
- [ ] Mock path cannot derive official domain seeds
- [ ] Tests: leakage suite for card/leaderboard/MCP-shaped dicts

**Must not:** Log raw official seeds in info-level miner paths.

**Tests:** `pytest tests/test_seeding.py tests/test_no_leakage.py -q`
