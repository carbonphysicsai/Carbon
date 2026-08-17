# Ticket A5 — Scoring engine + fixture Score Pack (C5)

**Wave:** A  
**Build_Out:** C5, Scoring.md semantics; weights live in pack not engine  
**Depends on:** A0, A1  

**Goal:** Deterministic score engine that loads a **fixture** Score Pack, fails closed on hard gates, and rejects forbidden inputs.

**DoD:**
- [ ] `ScoreEngine.score(metrics, pack) -> InternalResult`
- [ ] Fixture pack YAML under `tests/fixtures/score_packs/` with:
  - hard gate fields that may be `null` / `BLOCKED_FOR_LIVE_UNTIL_SET` / `HUMAN_INPUT`
  - continuous weights as **pack fields** (e.g. accuracy/physics/robustness) — not engine constants
- [ ] Gate fail → non-emitting path (`eligible_for_emission=False` or combined score 0 per Scoring.md)
- [ ] Forbidden inputs ignored or rejected if present on metrics: prior similarity, `estimate`/`light_*`, exam fee, mock-only metrics
- [ ] Pack loaded by path or content hash stub
- [ ] Unit tests: pass path, gate fail path, forbidden input present, HUMAN_INPUT gate does not invent pass

**Must not:** Hardcode production τ thresholds as truth. Do not mark fixture packs as LIVE-qualified.

**Tests:** `pytest tests/test_scoring_engine.py -q`
