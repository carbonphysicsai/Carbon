# Ticket A10 — Leaderboard API (C14)

**Wave:** A  
**Build_Out:** C14  
**Depends on:** A6, A7  

**Goal:** Public leaderboard with allow-listed fields only.

**DoD:**
- [ ] `list(challenge_id) -> rows` and/or `get(submission_id)`
- [ ] Public fields only: hotkey (or anonymized id), score, challenge_id, challenge_version, timestamp, gate_pass summary
- [ ] No seeds, draw ids, fine margins, internal diagnostics, fee amounts as rank features
- [ ] Stub results with `emission_capable=False` excluded from official board (or board clearly `fixture` only in Wave A)
- [ ] Leakage test reuses A4 helpers

**Must not:** Rank on mock/estimate metrics for an “official” board.

**Tests:** `pytest tests/test_leaderboard.py -q`
