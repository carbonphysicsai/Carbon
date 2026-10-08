## 2026-10-07 — BATTERY-L2-SPECMUON-BUILD-01: battery's Level-2 development variant, `optimizer.muon_spectral` (`specmuon-carbon-v1`, JAX)

**Authority.**
- **Review.** BATTERY-CLIMB-1-REVIEW (#757): `optimizer.muon_spectral` was
  accepted for a development-only Level 2.
- **Rulings.** The Test Lead's SpecMuon rulings, 2026-10-07:
  - a named, versioned Carbon interpretation;
  - D is SAV-standard;
  - μ = beta1 with no new field;
  - κ, k_r and η_sav are fixed constants;
  - non-matrix parameters keep base Muon's handling;
  - the extra forward pass uses the same minibatch and is counted;
  - base Muon is unchanged, plus a mode-wise RSAV correction on its output;
  - RSAV off reduces to base Muon byte for byte.

**Interpretation note: `specmuon-carbon-v1`.** It is never claimed to be the
algorithm of arXiv 2602.16167v1.
1. **Base.** The step is battery's base Muon (`optax.contrib.muon` as
   `training.optimizer` builds it), unchanged.
2. **Correction.** For each 2-D weight, Ĝ = G / (‖G‖_F + ε) is decomposed by
   SVD. Along its top k_r = min(8, rank) directions u_i v_iᵀ, Muon's own
   component c_i = u_iᵀ O v_i is rescaled by r̃_i / E. The other modes are
   Muon's.
3. **RSAV.**
   - E = √(f + κ), h_i = η_sav / σ_i, g_i = σ_i / E, and
     r̃_i = r_i / (1 + (h_i / 2) g_i²).
   - After the step, using f(Θ⁺) from one extra forward pass on the same
     minibatch: D_i = h_i⁻¹ ‖ΔW_i‖²;
     ξ_i = max{0, (−b − √(b² − 4ac)) / 2a}, clipped to [0, 1];
     r_i ← ξ_i r̃_i + (1 − ξ_i) E⁺.
   - The first step sets r_i = E.
4. **Constants:** κ = 1e-8, k_r = min(8, rank), η_sav = 0.2, ψ = 0.95.
5. **Departures from Algorithm 1:**
   - **Momentum (the main one).** It stays where base Muon has it, before
     orthogonalization, not on the RSAV output.
   - **Basis.** The rescaled directions are the normalized gradient's,
     applied to Muon's Newton–Schulz output, not to an exact-SVD
     orthogonalization.
   - **D.** D is the SAV-standard term, our reading of the paper's undefined
     D.

**Decisions.**
1. **The pattern of #611 and #761.**
   - **The variant:** `level2.py` builds the variant `battery-l2-spectral-v1`
     with one bool surface, default false. It is pinned, current at Level 2,
     and recorded as development record 0003.
   - **The trainer:** `level2_training.py` is `training.train` with four
     edits: its signature, its docstring, the optimizer wrap, and the update
     call passing `value` and `value_fn`. A drift test checks it.
   - **Staging:** `level2_worker.py` stages it.
   - **Pinned files:** `recipes.py` and `training.py` are untouched.
2. **Off is Level 0.** Without the field, or with it false, there is no
   record, and the staged files and program are Level 0's (tested).
3. **Guards.**
   - **Lane.** CPU_ONLY_DEV, because of the SVD. A non-CPU device is an
     environment failure. Built records say "rebuild: CPU-verified only".
   - **Cost.** The SVD (full matrix) and the extra forward pass are inside
     the compiled step, so the cost calculator's F4 counts them by
     construction.
   - **Divergence** is the candidate's own.
   - **Applicability.** The switch is refused unless the optimizer family is
     muon, with the plateau curve (which the wrapper does not drive), and on
     the PyTorch backend.
4. **Dispatch.** Level 2 has its own branch at each rebuild site, beside
   Level 3's. A shared dispatch helper is the next refactor, before pool
   selection lands.
5. **Pool selection** comes as a later version of this variant, with the
   Test Lead's ruling that PRACTICE stays out of every pool version.

**Tests.** `tests/cpu/test_battery_level2_specmuon.py` (15):
- the variant and its record, built from the code;
- miner surfaces refuse Level 2;
- the trainer drift test;
- RSAV off equals base Muon byte for byte;
- determinism and a loss decrease;
- off is Level 0 byte for byte;
- the refusals, the lane, the CPU label;
- mutations for the lane and the reduction.

`test_graphite_development_levels.py` now uses Level 4 as the unregistered
level, and expects the Attacker to refuse Levels 2 and 3 until their adapters
ship.

**Maturity.** Implemented and tested on CPU, development only. Not GPU
verified, not security qualified, and never served to miners.
