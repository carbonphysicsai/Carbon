# Ticket A8 — TrainEvalAPI stub (shared contract)

**Wave:** A  
**Build_Out:** §5 TrainEvalAPI, Wave A stub policy  
**Depends on:** A2  

**Goal:** Shared train/eval interface with a **deterministic stub** that is never emission-capable.

**DoD:**
- [ ] Interface: `run(strategy, batches, mode, limits, pin) -> RunResult`
- [ ] `mode` includes at least `mock` and `official` (official may be unimplemented except stub)
- [ ] Status classes: `success`, `invalid_strategy`, `timeout`, `resource_violation`, `numerical_failure`, `train_failure`, `infra_failure`, `incomplete_metrics`
- [ ] `mode=mock` **refuses** non-mock packs / official seed domains (raises or status)
- [ ] Stub returns deterministic fake metrics for CI
- [ ] `emission_capable=False` on stub backend; any weight-writer must refuse stub results
- [ ] Pin object records env_digest / backend id placeholders
- [ ] Tests: mock isolation, emission_capable flag, deterministic twice-run equality

**Must not:** Wire stub metrics into emission/weight writers or LIVE leaderboard ranks.

**Tests:** `pytest tests/test_traineval_stub.py -q`

**Pin to Carbon:** Wave C swaps real backend (or PoC Burgers promote) behind the same interface; Wave A proves plumbing only.
