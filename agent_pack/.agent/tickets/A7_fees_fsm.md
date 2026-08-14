# Ticket A7 — Fees + submission FSM (C13 + Wave A FSM skeleton)

**Wave:** A  
**Build_Out:** §5–§6 submission_id + fees, C13  
**Depends on:** A2 (validate before accept)  

**Goal:** Every submit gets a permanent `submission_id`; state machine; fee never enters score.

**DoD:**
- [ ] States: `RECEIVED → VALIDATED → QUEUED → RUNNING → SCORED → PUBLISHED` plus `REJECTED`, `FAILED_INFRA`, `FAILED_STRATEGY`
- [ ] `submit(hotkey, challenge_id, strategy) -> submission_id`
- [ ] Idempotency: duplicate `strategy_hash + hotkey + challenge version` returns existing open `submission_id` (Build_Out default)
- [ ] Fee ledger stub: record fee event; **fee amount not passed into ScoreEngine**
- [ ] Invalid strategy → `REJECTED` without fee charge (or explicit policy documented)
- [ ] Infra failure path does not invent physics gate results
- [ ] Unit tests: happy path transitions, idempotent resubmit, reject path, fee≠score assertion

**Must not:** Use fee as a score feature. Must not emit weights from FSM alone.

**Tests:** `pytest tests/test_submission_fsm.py -q`

**Pin to Carbon:** Fee is anti-spam / cost recovery only; scoring integrity is independent.
