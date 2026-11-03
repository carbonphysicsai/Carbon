# Exam rules conformance: rule × version (against EXAM_DESIGN_RULES_REGISTER.md)

Status at Sun 1 Nov 2026, evening CST (Exam Quality), **v9** (2 Nov ~04:25 CST). Every cell is one of:
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
| R1 qualification system | ⏳ NOT A PRIORITY (owner 1 Nov); rides the image move | ⏳ NOT A PRIORITY; rides the image move | ⏳ S4a stage 1 recorded PROVISIONAL, verdict null (Validator 03:10); S4 mix next | ⏳ S3/S4: region rev2 f501d622bf0d93044128e1b6f8a70f411b101b5c6a0215a9929eee8ac9cacc3d RECEIPTED (applicability rule C); cov18 + COOL-EXTU solving | ⏳ S1/S3: solver RE-PINNED to v2 PaStiX LDLT (OWNER-RB20-SOLVER-REPIN-PASTIX-01 4b232794); C2 + C4 + C7 PASS on v2; per-case limit 28 GiB (OWNER-RB20-REFERENCE-MEMORY-28GIB-01); C1 / C5 / inertia pending → UEDGE | ⏳ S3 DONE: Stage-2 8 signed sets + 63 edge all OK, merged + verified, truths USABLE (Validator 03:10) → S4a / GO/NO-GO 2 |
| R2 live kept to cutover | ✅ 1.6 live | ✅ 1.5 live | ✅ | ✅ | ✅ 1.7 live | ✅ 2.5 live |
| R3 no rescore / add-only | ✅ overlay | ✅ dispatch hook keeps the 1.1–1.5 producer digest (92130234 rejected) | ⏳ registration | ⏳ registration | ⏳ registration | ⏳ registration |
| R4 probe before wave | N/A no new solves | N/A no new solves (ext-U panel: smoke first ✅) | ✅ probe first: cov17 probe shard-s6000.tgz 411c53dcca55601d5b14bd3cd20627219c82d91395695ff73468163679fb0851 (fetched, verified); verdict (≥ 5/6 OK) ⏳ | ✅ COOL18 probe 6/6 PASS, shard s6000 c3507a82249bf64f053ceccb61447d2b545e8a68614317b74e352e98644e6fb6 | ✅ smoke first; C7 on v2: 0033 12.7 GiB + 0000 21.9 GiB OK, 0 pivots (RESULTS 3c8435926037bae3f18bd0a895e16d9df4e0ca6e5c852a428b41641f84073b82 / df0c97e66ad414330763112d578ac7285255825e64361f0dc7e920b70e95f678) | ✅ smoke first (LEAK-SMOKE PASS) |
| R5 guards name a harm | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| R6 extended region + edge check | N/A same material | N/A same material | ✅ signed region extended-electric-motor-magnetics.json file c3e41b52242f476ecc7252869b092b142d4112f06281bad1bd3d1817c806bfcd (canonical 248460a61ec806ea6756b1a453e5e15890e69f4a6bc30814b11c6d53686a8b4c); held sides stay held | ✅ signed region aa56f4edbb1701d55affaac0bfddf2a0b1a606158303d1f211ea852516ec5fa7, final region rev2 f501d622bf0d93044128e1b6f8a70f411b101b5c6a0215a9929eee8ac9cacc3d (applicability rule C) | ⏳ UEDGE edge check → region signature (+ the off-step owner choice) | ⏳ box C6 SIGNED (7f81edddbe69acd15647af4c623cc7e0477f8b4a); edge 63/63 OK (S3 evidence); the signed EXTENDED region = owner pick after the edge verdict; 90 °C check met (E10) |
| R7 extended OOD targets / off-lattice | N/A (0 OOD cases; disclosed, E6 line 97ff4bf6) | N/A same material | ✅ inner band + current-angle-high side | ✅ planned inner band + outer shell | ⏳ off-lattice = the 2.0 domain/region choice | ⏳ inner band + side classes after the box |
| R8 coverage N = 3 per class | N/A (audit gap; fixed by C1.8) | N/A (fixed by M1.7) | ⏳ 84 designs (COV17-WIDE) | ⏳ 96 designs (COOL18-COV) | ⏳ after the region | ⏳ after the box |
| R9 mined ≤ 1/3 | N/A | N/A | ⏳ MINE-MOT17 rev 2 (+ Q6 ≤ 24 shared) | ⏳ MINE-COOL18 | ⏳ MINE-F08-20 (+ audit off-step/edge classes) | ⏳ MINE-F02-30 (E10: 90 °C check) |
| R10 placed batch draws (by MATERIAL, Val) | ✅ inherited launch batch 6a0b9a4a9f287f5a06a79606c0aaacf0086d8c5f0ba5327616793e444bd660db | ✅ inherited launch batch 2273774f74492723fe4e573ed2c987fbd85e1de3db1a72a16967d19415002a61 | ✅ inherited batch 2273774f74492723fe4e573ed2c987fbd85e1de3db1a72a16967d19415002a61; any NEW limit-straddling accuracy batch ⏳ follows R10; OOD class draws follow R24/R31/R33 | ✅ inherited batch 6a0b9a4a9f287f5a06a79606c0aaacf0086d8c5f0ba5327616793e444bd660db; NEW straddling batches ⏳ follow R10; OOD class draws follow R24/R31/R33 | ⏳ new accuracy batches follow R10 (~1/3 each side, truths only, straddle QA) | ⏳ same as RB2.0 |
| R11 full bank served | ⏳ week-1 item 12 | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| R12 rotation + overfit check | ⏳ at cutover | ⏳ at cutover | ⏳ at cutover | ⏳ at cutover | ⏳ at cutover | ⏳ at cutover |
| R13 publish what is tested | ⏳ S7 (incl. the E6 line) | ⏳ S7 | ⏳ S7 | ⏳ S7 (+ the A rule) | ⏳ S7 (+ the D zero point, A rule) | ⏳ S7 (+ the D zero point, A rule) |
| R14 practice shows minimums | ⏳ S7 | ⏳ S7 | ⏳ S7 | ⏳ S7 | ⏳ S7 | ⏳ S7 |
| R15 practice bank rule | ⏳ per Challenge (probes done for Motor/F08; Cooling solving) | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| R16 per-part feedback after leak attack | ⏳ | ⏳ (Motor 1.5 binding proven) | ⏳ | ⏳ | ⏳ | ⏳ |
| R17 gates on every pool answer | ✅ grader | ✅ | ✅ | ✅ | ✅ | ✅ |
| R18 laws = hard gates | ✅ | ✅ | ✅ | ✅ | ✅ (stress ≤ Fty/1.5 not used until its U + Kirsch pass, E4) | ✅ (bounds law a gate only once proven) |
| R19 sign gates truth-checked | ✅ hotspot gate dropped (1465eff4d7); pool gates: truths-pass-gates (tool 076daaf7) on Cooling 1.6: PASS rows 394, gates [face_above_inlet, peak_bounds_profile, pressure_drop_positive, schema_finite], 0 fail, no STOP, record 688bbed8434f2af33bd9743af05f1eb2ba42f735afbdce291fdf5fc8ce8edfde; A-bank native sign gates ⏳ | ✅ pool gates: route (b) at 38b664f1 on Motor 1.5: PASS rows 540, gates [motoring_mean_nonnegative, schema_finite], 0 fail, record 19f1064adc890b714439d64ca4ed163de70714c6671ae042071c7506e4ad68b8; parity re-read with tool 076daaf7: record 355883e8a049a2096e79869a0bb3133f26d39610a653fd9c3529ef00b1ff1313; A-bank native sign gates ⏳ | ✅ inherited bank: route (b) at 38b664f1 on Motor 1.5: PASS rows 540, gates [motoring_mean_nonnegative, schema_finite], 0 fail, record 19f1064adc890b714439d64ca4ed163de70714c6671ae042071c7506e4ad68b8; parity re-read with tool 076daaf7: record 355883e8a049a2096e79869a0bb3133f26d39610a653fd9c3529ef00b1ff1313; the new 1.7 cases need their own read at their pack build ⏳; A-bank native sign gates ⏳ | ✅ inherited bank: truths-pass-gates (tool 076daaf7) on Cooling 1.6: PASS rows 394, gates [face_above_inlet, peak_bounds_profile, pressure_drop_positive, schema_finite], 0 fail, no STOP, record 688bbed8434f2af33bd9743af05f1eb2ba42f735afbdce291fdf5fc8ce8edfde; the new 1.8 cases need their own read ⏳; A-bank native sign gates ⏳ | ⏳ cite the pack build + NEW stress / damping-order sign laws need their own truth-sign check | ⏳ cite the pack build + NEW peak / leakage sign laws need their own truth-sign check |
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
| R31 S4a separation read | N/A ✔Val (built before 6c24fbb5; in-range bank cannot separate; informational row only) | N/A ✔Val (same) | OPTIONAL evidence (amendment 2): ⏳ stage 1 PROVISIONAL, verdict NULL: K + O GATE_FAILED; no registered A_gen scales for 1.6 → none until Motor 1.7's own calibration build registers them; 12 inner-band cases carried unchanged into stage 2 | OPTIONAL evidence (amendment 2): ⏳ ~4–5 Nov | OPTIONAL evidence (amendment 2): ⏳ ~5–6 Nov (UEDGE, PROVISIONAL until the region is signed) | OPTIONAL evidence (amendment 2): ⏳ DRY until the owner signs the extended region (edge cells allowed as OOD classes, Validator 16:35) |
| R32 D vs the engineer shortcut | N/A ✔Val (built and gated before 5328e97c; from the next version) | N/A ✔Val (same) | ⏳ shortcut = cheap adversary; DV-CURVE | ⏳ coarsest r or COOL-ADV; DV-CURVE | ⏳ h = 3 rung; DV-CURVE (first) | ⏳ modal-sum; DV-CURVE |
| R33 A = min (amended) | N/A ✔Val (same; no OOD cases) | N/A ✔Val (same) | ⏳ amendment 2: checks (1)-(3) (Evidence re-plans FIRST: stage 1 had no verdict); measured gaps → owner bars | ⏳ amendment 2: checks (1)-(3) (Graphite re-plans) | ⏳ amendment 2: checks (1)-(3) on the UEDGE OOD cases: h3 shortcut + DOWN adversary OOD score, noise ceiling, ONE default catalog model in range | ⏳ amendment 2: checks (1)-(3) (DC re-plans; modal-sum = the shortcut) |
| R34 fits lose on both sides | N/A ✔Val (proved by the next version) | N/A ✔Val | ⏳ via R31–R33 | ⏳ | ⏳ | ⏳ |
| R35 publish TRAIN + practice early | N/A ✔ not a priority version (rides the image move) | N/A ✔ not a priority version | ⏳ step after the freeze/check | ⏳ step after the freeze/check | ⏳ step after the freeze/check | ⏳ step after the freeze/check (+ the 95 °C registered peak limit, 57ea32d8, bound in the plan) |
| R36 graph forward compile in the worker image | N/A (live, stays eager) | N/A (live, stays eager) | ⏳ head te/graph-infer-once 58447e05cf3b8e3ef65914ee51e8c12619800816 tier-2 GREEN (gate120 1,834/0); lands + this version's opt-in registration after a JIT-vs-eager parity test | ⏳ head te/graph-infer-once 58447e05cf3b8e3ef65914ee51e8c12619800816 tier-2 GREEN (gate120 1,834/0); lands + this version's opt-in registration after a JIT-vs-eager parity test | ⏳ head te/graph-infer-once 58447e05cf3b8e3ef65914ee51e8c12619800816 tier-2 GREEN (gate120 1,834/0); lands + this version's opt-in registration after a JIT-vs-eager parity test | ⏳ head te/graph-infer-once 58447e05cf3b8e3ef65914ee51e8c12619800816 tier-2 GREEN (gate120 1,834/0); lands + this version's opt-in registration after a JIT-vs-eager parity test |
| R37 physics hardness card | N/A (live) | N/A (live) | ✅ card owner-CONFIRMED (Evidence 11:41, with corrections: Brauer saturation PRESENT, not SHOWN) | ✅ card owner-CONFIRMED (Graphite 11:43, with notes) | ⏳ card drafted (EQ) | ⏳ card drafted, DC to confirm |
| R38 TRAIN data adequacy card (freeze-binding) | N/A (live) | N/A (live) | ⏳ card skeleton; owner fill (16:00 answers) | ⏳ card skeleton; owner fill | ⏳ card skeleton (EQ) | ⏳ card skeleton; owner fill |
| G1 extrapolation (freeze) | N/A (live) | N/A (live) | ⏳ MOT-EXTU shell running; R33 checks | ⏳ outer shell held for COOL-EXTU; R33 checks | ⏳ UEDGE → region signature; R33 checks | ⏳ extended region signature (owner); R33 checks |
| G2 interpolation holes (freeze) | N/A (live) | N/A (live) | ⏳ cov17 84/84 solved (inner band); probe-set min distance 0.201 ≥ 0.10; full-pool audit at the mix | ⏳ cov18 inner band solving (OOA rule C) | ⏳ after the region | ⏳ after the region |
| G3 hard regimes (freeze) | N/A (live) | N/A (live) | ⏳ near-zero torque: a mined class in MINE rev 5 (EQ view 04:1x) | ⏳ applicability edges (OOA rates per class) | ⏳ band-edge / mode-crossing + off-step / shell-edge classes (MINE-F08-20) | ⏳ leakage-onset / nonlinearity classes (MINE-F02-30 rev 3) |
| G4 leave-regime-out (report) | N/A | N/A | ⏳ report | ⏳ report | ⏳ report | ⏳ report |
| G5 nearby variants (report) | N/A | N/A | ⏳ report (no neighbour tasks in 1.7) | ⏳ report | ⏳ report (2.0 nearby tasks) | ⏳ report (3.0 nearby tasks) |
| G6 learning curve (report) | N/A | N/A | ⏳ report | ⏳ report | ⏳ report | ⏳ report |
| G7 seed robustness (freeze) | ⏳ recal | ⏳ recal | ⏳ recal (R28) | ⏳ recal (R28) | ⏳ recal (R28) | ⏳ recal (R28) |
| G8 no leakage (freeze) | N/A (live) | N/A (live) | ⏳ full distance audit at the mix | ⏳ full distance audit at the mix | ⏳ + the off-step lattice decision | ⏳ full distance audit at the mix |
| G9 physical validity (freeze) | ✅ gates on every pool answer (R17) | ✅ (R17) | ⏳ new-case truths-pass-gates read | ⏳ new-case read | ⏳ + new stress / damping-order sign laws | ⏳ + peak / leakage sign laws |

**v11 (2 Nov ~14:00 CST):** adds row R38 (OWNER-TRAIN-DATA-ADEQUACY-CHECK-01, 3b42c19c), freeze-binding for the 4 new versions.

**v10 (2 Nov ~11:35 CST):** adds row R37 (physics hardness card, OWNER-HARD-REAL-PHYSICS-DIRECTION-01 0ea04b3d).

**v9 (2 Nov ~04:25 CST):** adds generalization axes G1–G9 (register section G; freeze-binding G1–G3 + G7–G9, report-only G4–G6). BOUND (v9.1): OWNER-STRONG-CHECKS-GENERALIZATION-AXES-01, lead-records 9515dd60d9ce8a3806f2aef076d745b1ba9f432c ("Lock them all in").

**v8.1 (2 Nov ~04:00 CST):** R33 amendment 2 (0318421a): the gate is checks (1)–(3); R31 (tuned S4a) is OPTIONAL evidence in every new column.

**v8 (2 Nov ~03:45 CST):** overnight evidence: BT 3.0 Stage-2 merged + verified; RB 2.0 re-pin + C2/C4/C7 on v2 + the 28 GiB owner limit; Motor 1.7 S4a stage 1 null; Cooling region rev2; R36 head green.

**v7 (1 Nov ~21:05 CST):** adds row R36 (OWNER-GRAPH-FORWARD-COMPILE-NEW-VERSIONS-01, 33c68843).

**v6 (1 Nov ~16:25 CST):** adds row R35 (OWNER-TRAIN-PRACTICE-EARLY-RELEASE-01, d9c8883c), plus the BT 3.0 95 °C peak-limit record (57ea32d8) in R35's BT cell. The N/A cells for C1.7/M1.6 are EQ's reading (not yet Validator-confirmed).

**v5 (1 Nov ~15:10 CST):** R4 C1.8 full probe digest placed (TL 15:01; Validator 15:07). Only the C1.8 column changed.

**v4 (1 Nov ~15:00 CST, Exam Quality):** FIXES a column-shift defect introduced in v3 by my cell-editing script (flagged by Graphite and Data Collection): rows R1, R4, R6, R10 and R19 were shifted one column right (and R1/R6 got a 7th cell). They are rebuilt with exactly 6 cells. Also adds the R19 Cooling 1.6 PASS record 688bbed8… and the Motor parity record 355883e8…, and marks C1.7/M1.6 as not priorities. Every other row was checked: 6 cells.

**v3 (1 Nov, Exam Quality):** full digests filled in from TL custody records (R10 inherited batches; R19 pack-build records; M1.7 R6 region, R4 probe shard). R19 "truths pass gates" is NOT shown by the pack-build records. **Validator ruling:** R19 evidence per live pack is (a) the proof-grid run record showing check_truths_pass_gates {rows, gates} with no TruthCheckStop (by sha), else (b) a $0 TL custody read at 38b664f1 (attach_raw → check_truths_pass_gates, read-only; {rows, gates}, revision, output sha, fail 0). A-bank native sign gates: their registration truth-sign records, else the same read on the sealed grader's reference truths. Asked of the TL.

**v2 (1 Nov, Exam Quality):**
- R10 (by material) and R19 (truths-pass-gates per pack build; new sign laws need their own check) are filled in from the Validator's rulings.
- R31–R34 N/A for C1.7 / M1.6 are marked ✔Val (confirmed).
- v1 91dff4bf… is receipted and landed in PR Head's docs head 3a655a4d.
- From v2 on, each version's column is receipted separately (the §3d HARD step).
