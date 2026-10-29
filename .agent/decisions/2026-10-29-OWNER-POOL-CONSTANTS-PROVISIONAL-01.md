# OWNER-POOL-CONSTANTS-PROVISIONAL-01: the three launch versions get Motor 1.5's pool constants, PROVISIONAL, testnet only

- **Received by:** the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae), directly from the owner in chat, 2026-10-29.
- **Owner's words:** "Yes approve." This answers the Lead's recommendation built on codex-queue/reports/OWNER_POOL_CONSTANTS_SHEET_20261029.md.
- **Decided:**
  - Cooling 1.6, F08 1.7 and F02 2.5 take Motor 1.5's registered pool-constant row: query budget, step, honesty scale, A multiplier, A_gen scales and rule.
  - c_rule is computed per Challenge as min, following the owner's D = min(V, C).
  - The values are labelled PROVISIONAL and apply to testnet only.
  - Purpose: open practice and the end-to-end rehearsal on the launch versions.
- **Guard:**
  - Each version's scoring grid then runs on its final sealed pools, in custody.
  - A version whose provisional row fails the guard goes back to RESERVED.
- **Bounds:**
  - These are not final values. The owner picks the final per-Challenge values from the grids before the registered recalibration on the validator host.
  - Nothing here applies to mainnet.
  - Flags for the owner's final pick: Cooling's sealed set has 4 targets, not 6; F08 has 17–19 beyond-training points per target, under 20.
