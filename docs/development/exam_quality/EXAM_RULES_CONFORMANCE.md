# Exam rules conformance: rule × version (against EXAM_DESIGN_RULES_REGISTER.md)

Status at Sun 1 Nov 2026, evening CST (Exam Quality). Every cell is one of:
- ✅ **applied** (with its evidence);
- **N/A** (with the reason);
- ⏳ **pending** (with what it waits on).

**HARD STEP** (EXAM_QUALIFICATION_SYSTEM rev 2.8): a version's column must be Validator-receipted at two points.
- **Before its S4 mix freeze:** every rule binding S0–S4a must be ✅ or N/A. Rules binding S5–S8 must name an owner and a date.
- **Again before its S6 big solves:** the S5 row must also be ✅ or N/A.
- A ⏳ in a freeze-binding row blocks that version's freeze. Under the owner's lightweight rule, the version may instead ship the rule's registered fallback, recorded as N/A-with-reason and receipted. It never silently skips the rule.

Abbreviations: C1.7 = Cooling 1.7 · M1.6 = Motor 1.6 · M1.7 = Motor 1.7 · C1.8 = Cooling 1.8 · RB2.0 = Ribbed Bracket 2.0 · BT3.0 = Burst Thermal 3.0.
C1.7 and M1.6 are scoring/fairness versions on unchanged exam material, already built and gated in image-move3d. Rules that change cases or physics are N/A for them; their replacements are M1.7 / C1.8.

| Rule | C1.7 (~4 Nov) | M1.6 (~7 Nov) | M1.7 (~8 Nov) | C1.8 (~9 Nov) | RB2.0 (~10 Nov) | BT3.0 (~9–10 Nov) |
|---|---|---|---|---|---|---|
| R1 qualification system | ⏳ S7/S8 (image-move3d → M3) | ⏳ S3 ext-U + S7 | ⏳ S4 draft | ⏳ S3 ext-U → S4 | ⏳ S1/S3 | ⏳ S1 (leakage sizing CUT-03) |
| R2 live kept to cutover | ✅ 1.6 live | ✅ 1.5 live | ✅ | ✅ | ✅ 1.7 live | ✅ 2.5 live |
| R3 no rescore / add-only | ✅ overlay | ✅ dispatch hook keeps the 1.1–1.5 producer digest (92130234 rejected) | ⏳ registration | ⏳ registration | ⏳ registration | ⏳ registration |
| R4 probe before wave | N/A no new solves | N/A no new solves (ext-U panel: smoke first ✅) | ✅ cov17 probe 6 first | ⏳ COOL18 probe 6 | ✅ runner smoke first (stopped at the 9 GiB limit, TE fix) | ✅ smoke first (LEAK-SMOKE PASS) |
| R5 guards name a harm | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| R6 extended region + edge check | N/A same material | N/A same material | ✅ signed region (held sides stay held) | ✅ signed region aa56f4ed… | ⏳ UEDGE edge check → region signature | ⏳ box signature (after CUT-03) → edge |
| R7 extended OOD targets / off-lattice | N/A (0 OOD cases; disclosed, E6 line 97ff4bf6) | N/A same material | ✅ inner band + current-angle-high side | ✅ planned inner band + outer shell | ⏳ off-lattice = the 2.0 domain/region choice | ⏳ inner band + side classes after the box |
| R8 coverage N = 3 per class | N/A (audit gap; fixed by C1.8) | N/A (fixed by M1.7) | ⏳ 84 designs (COV17-WIDE) | ⏳ 96 designs (COOL18-COV) | ⏳ after the region | ⏳ after the box |
| R9 mined ≤ 1/3 | N/A | N/A | ⏳ MINE-MOT17 rev 2 (+ Q6 ≤ 24 shared) | ⏳ MINE-COOL18 | ⏳ MINE-F08-20 (+ audit off-step/edge classes) | ⏳ MINE-F02-30 (E10: 90 °C check) |
| R10 placed batch draws | N/A same material | N/A same material | ⏳ Val: applicability to pool versions | ⏳ same | ⏳ same | ⏳ same |
| R11 full bank served | ⏳ week-1 item 12 | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| R12 rotation + overfit check | ⏳ at cutover | ⏳ at cutover | ⏳ at cutover | ⏳ at cutover | ⏳ at cutover | ⏳ at cutover |
| R13 publish what is tested | ⏳ S7 (incl. the E6 line) | ⏳ S7 | ⏳ S7 | ⏳ S7 (+ the A rule) | ⏳ S7 (+ the D zero point, A rule) | ⏳ S7 (+ the D zero point, A rule) |
| R14 practice shows minimums | ⏳ S7 | ⏳ S7 | ⏳ S7 | ⏳ S7 | ⏳ S7 | ⏳ S7 |
| R15 practice bank rule | ⏳ per Challenge (probes done for Motor/F08; Cooling solving) | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| R16 per-part feedback after leak attack | ⏳ | ⏳ (Motor 1.5 binding proven) | ⏳ | ⏳ | ⏳ | ⏳ |
| R17 gates on every pool answer | ✅ grader | ✅ | ✅ | ✅ | ✅ | ✅ |
| R18 laws = hard gates | ✅ | ✅ | ✅ | ✅ | ✅ (stress ≤ Fty/1.5 not used until its U + Kirsch pass, E4) | ✅ (bounds law a gate only once proven) |
| R19 sign gates truth-checked | ✅ hotspot gate dropped | ⏳ Val confirm | ⏳ Val confirm | ⏳ Val confirm | ⏳ Val confirm | ⏳ Val confirm |
| R20 DOWN adversary gate | ⏳ desk + COOL-ADV-01 (E7) | ✅ desk (physics unchanged) | ✅ desk (physics unchanged) | ⏳ full gate | ⏳ GO/NO-GO 2 | ⏳ GO/NO-GO 2 (provisional 2.5 margin_N, E3) |
| R21 headroom target | ⏳ S7 proof | ⏳ S7 | ⏳ S7 | ⏳ S7 | ⏳ S7 | ⏳ S7 |
| R22 D = optimisation test | ✅ pool grader | ✅ | ✅ | ✅ | ✅ | ✅ |
| R23 top-3 | ✅ in image-move3d | ✅ overlay | ⏳ registration | ⏳ | ⏳ | ⏳ |
| R24 balanced regions | ✅ 2-class rule (one class present) | ✅ 2-class | ⏳ multi-class build (TE, one build for D + A_gen) | ⏳ same | ⏳ same | ⏳ same |
| R25 strict honesty scale | ⏳ s_h calibration after M3 | ⏳ s_h calibration | ⏳ | ⏳ | ⏳ | ⏳ |
| R26 minimums via the miners' path | ✅ baseline through measure_pool (7f636fff) | ⏳ baseline regrade | ⏳ GO/NO-GO 3 (E8) | ⏳ | ⏳ E8 | ⏳ E8 |
| R27 first crown beats baseline | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| R28 margins + crown average + repeat | ⏳ M7 recal | ⏳ recal | ⏳ | ⏳ | ⏳ | ⏳ |
| R29 accuracy-matched controls | ⏳ S7 | ⏳ S7 | ⏳ S7 | ⏳ S7 | ⏳ S7 | ⏳ S7 |
| R30 LN gate | ⏳ report-only | ⏳ report-only | ⏳ report-only | ⏳ HARD | ⏳ HARD | ⏳ HARD |
| R31 S4a separation read | N/A (built before 6c24fbb5; in-range bank cannot separate; informational row only) | N/A (same) | ⏳ ~3 Nov | ⏳ ~4–5 Nov | ⏳ ~5–6 Nov (UEDGE, PROVISIONAL until the region is signed) | ⏳ ~6 Nov+ |
| R32 D vs the engineer shortcut | N/A (built and gated before 5328e97c; from the next version) | N/A (same) | ⏳ shortcut = cheap adversary; DV-CURVE | ⏳ coarsest r or COOL-ADV; DV-CURVE | ⏳ h = 3 rung; DV-CURVE (first) | ⏳ modal-sum; DV-CURVE |
| R33 A = min (amended) | N/A (same; no OOD cases) | N/A (same) | ⏳ S4a decides min vs mean; ACC-NOISE | ⏳ same | ⏳ same | ⏳ same |
| R34 fits lose on both sides | N/A (proved by the next version) | N/A | ⏳ via R31–R33 | ⏳ | ⏳ | ⏳ |

**For the Validator to confirm on receipt:**
1. the C1.7 / M1.6 N/A reasons for R31–R33 (they were built before the 1 Nov rules, and the never-delay rule applies);
2. R10's applicability to pool versions;
3. R19 per Challenge.
