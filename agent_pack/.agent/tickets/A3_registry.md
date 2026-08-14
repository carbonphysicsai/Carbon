# Ticket A3 — Challenge registry

**Wave:** A  
**Goal:** File-backed challenge registry with hashes; LIVE cannot enable without qualification manifest slots.

**DoD:**
- [ ] Registry load/save (YAML or JSON)
- [ ] Challenge status includes non-live by default
- [ ] `can_go_live(challenge_id) -> False` if qualification incomplete or HUMAN_INPUT remains
- [ ] Tests for blocked LIVE

**Must not:** Default any challenge to LIVE.

**Tests:** `pytest tests/test_registry.py -q`
