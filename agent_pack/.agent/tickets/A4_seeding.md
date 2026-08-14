# Ticket A4 — Seeding domains + leakage tests (C6)

**Wave:** A  
**Build_Out:** §7 Seeding (C6), invariant 1–2  
**Depends on:** A0, A1  

**Goal:** Enforce non-colliding seed domains and prove official material cannot leak to miner-visible surfaces.

**DoD:**
- [ ] Domain enum/constants: `mock`, `official_train`, `official_eval`, `official_stress`, `reference`, `dossier`
- [ ] Derivation helper stubs: `derive_seed(domain, challenge_version, role_key, master_secret)` — **master_secret never logged**
- [ ] Domain separation: mock path **cannot** call official_* derivation (hard guard)
- [ ] Leakage suite: given a fake InternalResult containing seeds/draw ids, miner-facing serializers strip them
- [ ] Tests cover: role split train≠eval≠stress; mock isolation; card/leaderboard/MCP-shaped dicts have no seed-like keys

**Must not:** Put official seeds in EvaluationCard, leaderboard, MCP responses, or info-level miner logs. Do not hardcode a “real” master secret in repo (env/test double only).

**Tests:** `pytest tests/test_seeding.py tests/test_no_leakage.py -q`

**Pin to Carbon:** Trustless eval depends on hidden official draws; leakage is a protocol failure, not a style issue.
