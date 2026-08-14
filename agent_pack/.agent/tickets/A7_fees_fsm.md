# Ticket A7 — Fees + submission FSM

**Wave:** A  
**Goal:** submit returns permanent submission_id; state machine; fee≠score.

**DoD:**
- [ ] States: RECEIVED → VALIDATED → QUEUED → RUNNING → SCORED → PUBLISHED (+ REJECTED, FAILED_INFRA, FAILED_STRATEGY)
- [ ] Idempotent behavior documented/tested for duplicate strategy_hash+hotkey
- [ ] Fee ledger stub; fee not passed into ScoreEngine inputs
- [ ] Unit tests for transitions and reject path

**Must not:** Charge fee into scoring formula.

**Tests:** `pytest tests/test_submission_fsm.py -q`
