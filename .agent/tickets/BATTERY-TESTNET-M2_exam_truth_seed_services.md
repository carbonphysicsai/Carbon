# BATTERY-TESTNET-M2 — Battery exam module, truth service and private-seed service

**Programme:** battery testnet hardening track (parent #341)
**Status:** `in_progress`, pending delivery in its PR
**Primary Hub map_ref:** `SYSTEM/AGENT-EXECUTION`
**Authority:** OWNER-BATTERY-TESTNET-01 (OD-1, OD-2, OD-3), OWNER-DX-03.
**Depends on:** BATTERY-TESTNET-M1 (per-Challenge contracts, battery vocabulary).

## Scope

Promote the exam-design campaign's battery exam into `carbon/battery/`:
- gates, score, screening pools and the frozen comparison;
- the pinned PyBaMM truth service;
- a private-seed service that replaces the container-local root;
- a shadow scorer that admits submissions through the battery contract.

No threshold is invented. OD-2's values are provisional DEVELOPMENT values. No
chain action, no spend, and no qualification.

## Definition of Done

- [x] `carbon/battery/exam.py` keeps the campaign's gates, score, pools and
      frozen rule and carries the OD-2 rule constants. The replay test shows:
  - identical outputs to the research modules on all 2,600 retained cases for
    the eight decision models;
  - every recorded verification decision (V1 to V7, R1) is reproduced.
- [x] Truth service (`reference.py`, `truth.py`):
  - the pinned configuration (SPEC equals the campaign's);
  - every ending typed: OK, solver failure, timeout or FAILED_INFRA;
  - a memory bound and a wall-clock deadline;
  - resume that retries only infrastructure failures.
- [x] Private-seed service (`seeds.py`):
  - an owner-only root;
  - the campaign's derivation, regenerated from the revealed root;
  - hidden duplicates with opaque ids in every private set;
  - commit-before-use by construction;
  - reveal only after retirement, verifiable against the commitment.
- [x] Shadow scorer (`shadow.py`):
  - admission through `compile_submission` with the contract digest;
  - pools built only from whole committed batches;
  - rotation retires in the journal;
  - an allow-listed public projection.
- [x] Tests:
  - campaign replay gives identical decisions;
  - no private field reaches a public projection (planted-value test);
  - a reference failure stays separate from a candidate failure.

## Known limits

- The truth service's real PyBaMM solve is not run in CI, because PyBaMM is
  pinned in the truth image's overlay lock, not in Carbon's environment. Its
  runner is tested with injected solvers. The pinned configuration is held
  equal to the campaign's.
- The truth and GPU images' security review is OD-3's packet in M4.
- The validator daemon (M3) wires the shadow scorer to chain commitments, and
  M6 publishes its projection.
