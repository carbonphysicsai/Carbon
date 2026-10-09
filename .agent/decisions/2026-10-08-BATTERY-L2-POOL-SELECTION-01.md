## 2026-10-08 — BATTERY-L2-POOL-SELECTION-01: battery Level 2 v2 adds `training_data.pool_selection`

**Authority.**
- **The requirement.** The owner required Level 2 to propose
  `data.pool_selection` (2026-10-07). The Test Lead accepted the design the
  same day, with PRACTICE dropped from every pool, `overlap_check` refusing
  it, and pool v1 being TRAIN v1 only.
- **The scheduling.** The Test Lead's overnight queue of 2026-10-08 put it
  next.
- **The scope.** Development only: F1 acceptance rests with the Test Lead.

**Decision.**
- **A new variant version, `battery-l2-v2`,** now the current Level 2
  variant (dev record 0006). It widens:
  - `optimizer.muon_spectral`, exactly as v1;
  - `training_data.pool_selection`.

  `battery-l2-spectral-v1` stays registered, and its document and digest are
  unchanged (`602b9ce0…`).
- **Pools** (`carbon/battery/pools.py`, `carbon/battery/pools/`):
  - **The manifest.** A pool version is a content-addressed manifest
    (`carbon.battery-public-pool.v1`). It holds its parts, each part's pinned
    source and case-id digest, the refusal list, its parent and the overlap
    verdict. Its digest is its identity.
  - **Pool v1 is TRAIN v1 only:** 400 cases, digest `e3de28b9…`. Its
    overlap check is recorded as not run, because v1 is exactly the set
    Level 0 already trains on. `overlap_check` binds every later version on
    the producer, which is the Validator's work.
- **The recipe field** is
  `{pool_version, strata: {part: weight in [0, 2]}, box?: {input: [lo, hi]}, cases}`:
  - a recipe never names a case;
  - PRACTICE is refused by name (`pool.practice_refused`);
  - each malformed field is refused with its own code.
- **The draw is Carbon's, from the recipe alone.**
  - **Counts:** per-stratum counts come from the normalised weights by
    largest remainder, so they sum to `cases`.
  - **Order:** within the box, cases are ranked by
    `sha256(seed + ":" + case_id)`, where the seed is the canonical digest of
    the recipe's `pool_selection`, and the first `n_s` are kept. Every
    validator gets the same subset, and no random-number library is used.
- **The rebuild.**
  - **Staging:** the Level-2 record carries the drawn case ids (TRAIN case
    ids are public). The worker program restricts the staged TRAIN v1 to them
    before the fit, and refuses a mismatch.
  - **The trainer** is Level 0's unless SpecMuon is also on; then both apply.
  - **Level 0 is untouched:** a recipe without a selection is Level 0 byte
    for byte, and a SpecMuon-only record is v1's record byte for byte.
- **Every family and both backends.** Pool selection changes only the
  training data, so it applies to kNN, MLP, DeepONet and FNO, on JAX and
  PyTorch (backend parity). SpecMuon keeps its own limits.
- **Cost.** `cases` is the recipe's effective TRAIN size (`train_cases`,
  TRAINING-BUDGET-02).

**Tests.** `tests/cpu/test_battery_level2_pool_selection.py`, 30 passed:
- v2 is current and recorded, and v1 is unchanged;
- miner doors refuse a selection;
- pool v1's manifest is the builder's;
- 17 typed refusals, PRACTICE among them;
- the draw is deterministic, inside the box and exactly sized;
- no selection is Level 0 byte for byte;
- a selection alone keeps Level 0's trainer;
- SpecMuon and a selection compose;
- every family may select;
- the in-process rebuild repeats and differs from Level 0;
- the staged program trains on exactly 120 cases.

`test_battery_level2_specmuon.py` now finds its widened entry by id.

**Not claimed.**
- **No bank part yet.** Later pool versions need the Validator's
  publication path and `overlap_check`.
- **No attack adapter coverage.** The Level 2 attack adapter's
  pool-overfitting, weighted-repetition and combined-permission families are
  not added here.
- **No proof the selection helps.** A selection only gives a recipe the
  choice; the climb measures whether it helps.
