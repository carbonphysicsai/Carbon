## 2026-10-13 — VALIDATOR-PLATING-REF-V2-01: battery-plating-ref-v2 parameters, transition rule and stop-condition record (under OWNER-PLATING-REFERENCE-01 D3)

**Authority.** OWNER-PLATING-REFERENCE-01 D3 (the owner approved re-referencing near-onset cases at a fine mesh, "with the screening window and the band set from D2's panel"). The Carbon Validator set the values below on that evidence, and the Test Lead independently checked them. Evidence:
- PLATING-CONVERGENCE-01 (#1280; `summary.json` sha256 `43117f86…`);
- the D2 across-box panel (`d2-signed.json`, 40 cases);
- the D2 Validator-spec panel (`D2_REPORT.json` sha256 `cb4fd05f…`, 35 cases, 140 solves).

**1. The reference version.** `battery-plating-ref-v2`: a mesh-160 plating-margin re-solve (cycle 1 only) for near-onset cases. **Every plating label in v2 carries `plating_reference: {version, rule}`.**

**2. The transition rule** (m20 = the standard mesh-20 plating margin):

| m20 | Label in v2 | `rule` |
|---|---|---|
| ≥ +3.5 mV | FEASIBLE (mesh 20) | `m20-above-window` |
| in (−1.97, +3.5) mV, re-solved | FEASIBLE if m160 ≥ 0.6 mV; INFEASIBLE if m160 < 0; otherwise UNRESOLVED | `m160-d3` |
| in (−1.97, +3.5) mV, not yet re-solved (including new cases) | UNRESOLVED; never usable as FEASIBLE | `pending-m160` |
| ≤ −1.97 mV | INFEASIBLE (mesh 20) | `m20-below-window` |

**3. Where the values come from:**
- **Coefficient c = 1.6:** mesh 160's own error ≈ (m80 − m160)/(2^p − 1). At the lowest observed order p = 0.7 that's 1.6 × the max residual 0.359 mV = 0.574, rounded up to a band of 0.6 mV.
- **Window upper edge +3.5:** the worst near-onset bias on positive FEASIBLE cases is 2.46 mV. 2.46 + 0.6 = 3.06, and 3.5 adds a margin for unsampled cases.
- **Lower edge −1.97:** inside the window the bias is positive in every measured case (59/59), so m160 < m20 there and no INFEASIBLE case can become FEASIBLE.
- **The claim applies only for |m20| < 15 mV.** Outside it, no band is claimed.

**4. The stop condition fired and was stood down, with reasons.** The pre-registered stop rule was "any negative mesh20 − mesh160 difference → a symmetric band is wrong; escalate INFEASIBLE labels to the owner". It fired on 2 of 40 across-box cases: D-0013 (−1.09 mV) and D-0147 (−0.31 mV).
- **It was not triggered for escalation.** Both are deep in plating (m20 = −35.6 and −54.0 mV), so no label can change. In the decision window every bias is positive.
- **D-0013 and D-0147 are recorded as limits on extrapolation, not explained away.** Any band for deep plating needs its own evidence.
- **The box-wide worst, +3.08 mV, lies outside the window.**

**5. D1 is replaced explicitly.** The Test Lead's interim (D1: safe only above about 2.6 mV plus a cushion) applies to new work **only until v2 is cut**, and is then replaced by §2 for every case in v2. No mesh-20-only FEASIBLE label exists inside the window.

**6. Never backwards (invariant 10).** The band ships with v2 only. EV4, EV5, the score proofs and earlier banks keep their recorded labels under their own band, annotated per OWNER-PLATING-REFERENCE-01 D4.

**7. The re-derivation trigger.** D3 also solves a 10 % stratified subsample at mesh 80. If any m80 − m160 exceeds 0.359 mV, or a FEASIBLE case lands at m160 < 0.73 mV, the band is re-derived before v2 is sealed. It's never kept by default.

**8. What v2 is expected to change:**
- few or no safe → unsafe flips (0 of 31 in the panel; the lowest m160 was 0.73 mV);
- mostly, in-band UNRESOLVED cases getting decided labels.

Its value is an adequate near-onset reference. **A consequence:** from v2 on, every in-window action × condition needs a mesh-160 solve (about 237 CPU-s, 6.3 GB) before it has a usable label. Bank sizing includes it (BANK_SPEC §5, #1287).

**Not decided here:** the sealed bank's re-reference (the owner's, with his figure); any band for deep plating.
