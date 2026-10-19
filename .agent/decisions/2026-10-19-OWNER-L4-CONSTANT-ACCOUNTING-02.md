# OWNER-L4-CONSTANT-ACCOUNTING-02: graph constants, counted by content; published material as kit inputs

**Owner:** Ryan, 2026-10-19 ("Yes to your miner fixes"), relayed to Launchpad by the Test Lead session the same day. It answers real miner feedback (Martin): graph constants were charged once per ensemble member and per repeated block, and published Challenge material had to be embedded as miner constants.

**Decision:**
1. **Count identical constants once, by content.** Constants with the same dtype, shape and bytes are charged one copy against the constant cap. This is constant accounting **v2** (`level4-constant-accounting-v2`).
2. **Published Challenge material enters a graph as a named kit input**, bound by the Challenge's published digest, not as miner-embedded constants. It doesn't count against the miner's constant budget.

**Unchanged:**
- the 16 KiB `constant_bytes` cap (OWNER-L4-VALUES-01);
- the other caps;
- every allowlist.

**Not adopted for now:** no per-constant cap and no flag for matching TRAIN.

**Versioning:** prospective.
- Verdicts admitted under v1 (every constant summed) keep their v1 meaning, and are never re-measured or reinterpreted.
- New verdicts record `constant_accounting` and carry both `constant_bytes` (the raw sum, as before) and `unique_constant_bytes` (what v2 caps).

**Boundary:** dedup doesn't widen what a graph can carry. An identical copy holds no new information, and every distinct byte is still charged. Kit inputs are Carbon's published, digest-bound material, never miner-supplied arrays.

**Implementation:**
- **Item 1:** `carbon/level4/graph.py` `unique_constant_bytes` and `allowlist.MEASURED_AS`, with tests in `tests/cpu/test_level4_graph.py`.
- **Item 2:** `validate.Interface.kit` and `KIT_PREFIX`, which `check_interface` admits only as registered (exact dtype and shape). The verdict records `kit` as `[name, digest]`. `train.prepare(kit=…)` binds by name inside `apply`, so `predict`, batched or isolated, never slices or pads a kit array, and graphs without kit inputs keep the old `apply`.
  - **Battery:** `level4_model.KIT_INPUTS` holds the OCV table (`kit/ocv_soc`, `kit/ocv_v`), plus, added 2026-10-19 under item 2 at the Test Lead's direction from Martin's case, the per-output mean and population standard deviation of the fixed public TRAIN targets (`kit/train_target_mean`, `kit/train_target_std`, 247 outputs). These are computed deterministically in float64 from TRAIN. A state carries them only when its graph reads them, because inference has no TRAIN. Physical-unit outputs on Carbon's side: not now. `published_kit` reads Carbon's public material on the host, or a kit source built from the TRAIN and OCV structure Carbon passes to the rebuild (or from the state at inference), so the staged worker loads no extra material. Digests are of the float64 bytes.
  - **Tests:** `tests/cpu/test_level4_kit_inputs.py`.

No scientific, security, LIVE or economic authority follows from this file.
