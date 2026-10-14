## 2026-10-13 — VALIDATOR-L3-EMPTY-PARAMETERS-01: L3 empty-parameters trigger is an ORACLE_GAP; the defect underneath is level inflation, fixed by labelling, not refusal

**Authority.** The Carbon Validator's gate-comprehensiveness ownership (the owner, 2026-10-05). The Test Lead routed the triage here. The owner's ruling of 2026-10-13: **the level is descriptive, not a permission.** Miners never pick levels, Carbon derives them, and admission depends only on scope and rebuildability.

**The finding.** `attack-failing-trigger-9b718c6438cabfe8-0`, family `l3_cross_level_fields`: a `compile_strategy` with **empty parameters**, accepted by the path, the L3 and L2 variant gates and the miner contract gate. The Graphite Testing Manager triaged it as ORACLE_GAP.

**The ruling.**
1. **Legitimate, not a hole. ORACLE_GAP stands.**
   - `parameters: {}` uses no widened field. It compiles to the registered defaults: the Level-0 construction.
   - The family tests for cross-level fields, and there are none. The oracle fired on the absence of what it tests for.
   - There's no admission or scoring advantage: scores are computed on the rebuilt model, and dedup by rebuilt artifact digest makes it the same model as an L0 default submission.
   - There's no unprotected capability, so **no removal candidate.**
2. **The real defect is level inflation.** On the development ladder the submission is recorded as L3 while being an L0 construction. That overstates the ladder evidence used to judge construction progress.
3. **The fix is the label, not admission.**
   - A variant submission that uses none of its level's widened fields is **recorded with derived label 0** and admitted.
   - It is **not** refused (`development_variant_unused` is rejected as an option): refusing would make the level gate admission, contrary to the owner's ruling.
   - PLT-16's derived change set is the structural fix; PLT-16c follows.
4. **The oracle (OPT-14)** passes this case as NOT_APPLICABLE, not BREACHED.

**The general rule for gate triage.** "Every gate accepts it" is evidence for both an oracle gap and a shared gate miss. The deciding question is always whether the input is legitimate on that path. That judgement belongs to the Carbon Validator (gate comprehensiveness), not to a classification alone.
