# Ticket A5 — Scoring engine + fixture pack

**Wave:** A  
**Goal:** Score engine loads a fixture Score Pack; hard gates fail-closed; thresholds may be HUMAN_INPUT nulls.

**DoD:**
- [ ] ScoreEngine API: metrics + pack -> InternalResult
- [ ] Fixture pack YAML with `BLOCKED_FOR_LIVE_UNTIL_SET` or null thresholds where needed
- [ ] Forbidden inputs ignored if present (prior, fee, light_*)
- [ ] Gate fail => non-emitting / combined score zero path
- [ ] Unit tests with fixture metrics

**Must not:** Hardcode production τ as “truth”; 45/30/25 only as fixture proposal if used.

**Tests:** `pytest tests/test_scoring_engine.py -q`
