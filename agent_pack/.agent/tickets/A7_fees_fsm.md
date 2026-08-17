# Ticket A7 — Fees + submission FSM (C13 + Wave A FSM skeleton)

**Wave:** A  
**Build_Out:** **v1.4** §5–§6 submission_id + fees, C13  
**Depends on:** A2 (validate before accept)  

**Goal:** Every submit gets a permanent `submission_id`; state machine matches v1.4; fee never enters score.

**DoD:**
- [ ] Happy path states: `RECEIVED → VALIDATED → QUEUED → RUNNING → SCORED → PUBLISHED`
- [ ] Exceptional states: `REJECTED`, `FAILED_INFRA`, `FAILED_STRATEGY`, **`CANCELLED`**
- [ ] `submit(hotkey, challenge_id, strategy) -> submission_id`
- [ ] Idempotency: duplicate `strategy_hash + hotkey + challenge version` returns existing open `submission_id` (Build_Out §6.2 default)
- [ ] Fee ledger stub: record fee event; **fee amount not passed into ScoreEngine**
- [ ] Invalid strategy → `REJECTED` without fee charge (or explicit policy documented)
- [ ] **`FAILED_INFRA`:** refund or retry credit path; **must not** produce physics gate results or emission blame
- [ ] **`CANCELLED`:** policy-defined terminal state present in enum/FSM
- [ ] Unit tests: happy path transitions, idempotent resubmit, reject path, FAILED_INFRA ≠ physics fail, fee≠score assertion, CANCELLED reachable/documented

**Must not:** Use fee as a score feature. Must not emit weights from FSM alone. Must not score FAILED_INFRA as strategy/physics failure.

**Tests:** `pytest tests/test_submission_fsm.py -q`

**Pin to Carbon:** Fee is anti-spam / cost recovery only; scoring integrity is independent. Infra faults are operational, not scientific.
