# Ticket A8 — TrainEvalAPI stub

**Wave:** A  
**Goal:** Shared TrainEvalAPI interface with deterministic stub; emission_capable=False.

**DoD:**
- [ ] `run(strategy, batches, mode, limits, pin) -> RunResult`
- [ ] Status classes: success, invalid_strategy, timeout, resource_violation, numerical_failure, train_failure, infra_failure, incomplete_metrics
- [ ] mode=mock refuses non-mock packs
- [ ] Stub returns fake metrics; `emission_capable=False`
- [ ] Tests for mode guard and stub flag

**Must not:** Wire stub into any emission/weight writer.

**Tests:** `pytest tests/test_traineval_stub.py -q`
