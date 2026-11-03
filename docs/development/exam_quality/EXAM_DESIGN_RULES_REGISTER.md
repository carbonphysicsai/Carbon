# Exam design rules register (adopted rules only)

Owner, 1 Nov 2026, in the Lead session: "lock all these new updates into something solid and make sure they're incorporated into the new exams".

**How to read it**
- Each entry is ONE adopted rule. It gives:
  - the owner record id;
  - the commit that added the record;
  - the stage it binds, from EXAM_QUALIFICATION_SYSTEM.md (S0 evidence · S1 physics + DOWN gate · S2 scoring dry run · S3 reference/U/edge · S4 mining + mix FREEZE (S4a separation read) · S5 learning necessity · S6 solve · S7 QA + disclosure + recal · S8 register/cutover/watch);
  - the check that proves a version follows it.
- Commits are on the lead-records branch (`lead/owner-battery-launch-version`) unless marked "main".
- Proposals, directions not yet turned into rules, and open values are NOT listed. Every number shown is the owner's or measured. Open values stay HUMAN_INPUT.
- Scope: every NEW exam version (Burst Thermal 3.0, Ribbed Bracket 2.0, Motor 1.6/1.7, Cooling 1.7/1.8 and later). Nothing graded is rescored. Every change ships only as a new version.

Rev 9 (2 Nov ~14:00 CST): adds R38 (TRAIN data adequacy card). Rev 8 (2 Nov ~11:35 CST): adds R37 (physics hardness card). Rev 7.1 (2 Nov ~10:35 CST): section G bound to OWNER-STRONG-CHECKS-GENERALIZATION-AXES-01 (9515dd60). Rev 7 (2 Nov ~04:25 CST): adds section G (generalization axes G1–G9). Rev 6 (2 Nov ~04:00 CST): R33 amendment 2 (three cheap checks; the tuned S4a read optional). Rev 5 (1 Nov ~21:05 CST): adds R36 (graph forward compile). Rev 4 (1 Nov ~17:35 CST): adds the RB 2.0 solver re-pin record. Rev 3 (1 Nov ~16:25 CST): adds R35 (early TRAIN + practice release) and the BT 3.0 95 °C peak-limit record. Rev 2 (1 Nov ~16:00 CST): adds the Motor next-version shortcut record. Maintainer: Exam Quality. Every edit needs the Validator's receipt. A new owner record adds a row here in the same step it is written into the system.

## A. Process

| # | Rule (one line) | Owner record · commit | Binds | Proving check |
|---|---|---|---|---|
| R1 | Every new version passes the Exam Qualification System (S0–S8); live versions are audited through it too | EXAM-QUALIFICATION-SYSTEM-ADOPT-01 · b577bff6e8 | all | per-version qualification record with each stage's Validator receipt |
| R2 | Live exams stay until each replacement cuts over; audits feed case mining for the next versions | LIVE-EXAMS-KEEP-01 · 2aea7bb751 | S0, S4, S8 | live version unchanged until its cutover record; S4 mining sources cite the audits |
| R3 | Nothing graded is rescored; changes ship only as new registered versions (add-only overlay, zero-downtime cutover) | EXAM-VALUE-PICKS-01 · df0a4201b7 (bounds), repeated in every rule below | S8 | registry overlay add-only; the prior version's regrade stays bit-exact |
| R4 | Probe before the wave (≈ 10 cases per target, stop if < 2 feasible); sizing measured per host class, never fixed | EXAM-DATA-PLAYBOOK-ADOPT-01 · c88e97f541 | S6 | probe record precedes each wave's claim |
| R5 | A guard that blocks iteration must name the harm it prevents (exam/grading integrity, containment, keys, money, disclosure), else it becomes a warning | STOP-RULES-THAT-BLOCK-ITERATION-01 · 353de0e551 | all | each new guard's spec names its harm |

## B. Population, coverage and cases

| # | Rule | Owner record · commit | Binds | Proving check |
|---|---|---|---|---|
| R6 | Extended region: up to 25 % of each TRAIN range beyond each edge, plus condition values TRAIN never used; capped by solver reliability; failed sides are cut | HEADROOM-REGIONS-01 · 204dd4679a | S3 | signed region file + edge-check record |
| R7 | New versions include extended out-of-distribution targets; Burst Thermal and Ribbed Bracket use off-lattice draws | MAINNET-VERSIONS-OOD-ASAP-01 · f87d7bef30; TESTNET-ALL-FOUR-CROWNS-MAINNET-NEW-VERSIONS-01 · eb90855dfa | S4 | coverage map of the draft pool shows the extended classes |
| R8 | Coverage gate: every class in the signed region has ≥ N = 3 hidden targets, each with ≥ 2 feasible designs (one top-up) | COVERAGE-GATE-N-DELEGATED-01 · 3c87c2cdee | S4, S7 | COVERAGE_MAP_REV2 on the draft and final pool |
| R9 | Mined cases beyond the N floor ≤ 1/3 of a version's new cases, inside the existing caps | CASE-MINING-SHARE-01 · 0f773d8d65 | S4 | frozen-mix digest counts by source |
| R10 | Sealed accuracy batches are placed draws, about 1/3 on each side of each limit; placement estimates are never labels (batch-draw versions) | COOLING-EXAM-DRAW-01 · 8a9af15ea4; MOTOR-EXAM-DRAW-01 · 7436debe00; F02-F08-EXAM-DRAW-01 · e9260504c0 | S4 | straddle QA per batch |
| R11 | Every graded submission faces the version's full active sealed bank (temporary one-batch exception at the testnet launch) | FULL-EXAM-BANK-01 · 8a24c94e65; ONE-BATCH-AT-LAUNCH-01 · 2c1f7bd373 | S8 | served pack set = all active QA-passed batches |
| R12 | Rotation: 90-day maximum plus the weekly fresh-draw overfit check | CADENCE-AND-ROTATION-02 · ccbe2be148 | S8 (watch) | weekly overfit read recorded |

## C. Disclosure and practice

| # | Rule | Owner record · commit | Binds | Proving check |
|---|---|---|---|---|
| R13 | Publish what is tested: each gate and physics requirement with its pass condition, the score formula, and the part minimums (hidden cases stay protected) | PUBLISH-WHAT-IS-TESTED-01 · 5e37f26048 | S7 | "how you are tested" record passes the Validator's exam-safety check |
| R14 | Practice applies the same registered part minimums as the sealed grade | PRACTICE-SHOWS-MINIMUMS-01 · 4457218605 | S7 | practice scorer reads the registered minimums |
| R15 | Public practice bank: N = 40 per Challenge, ≥ 0.10 (normalised max-norm) from every sealed point, inner half of the band only | PRACTICE-BANK-PICKS-DELEGATED-01 · 25f2d4b850 | S7 | the single "all N satisfy the rule" boolean + bank digest |
| R16 | Per-part feedback to the miner, at a granularity proven by the feedback-leak attack | DOOR-LOOKUPS-AND-PART-FEEDBACK-01 · 005839c700 | S7 | leak-attack receipt before feedback serves |
| R35 | Each new version's TRAIN set and practice bank are PUBLISHED as soon as they are frozen and checked, ahead of its board opening | TRAIN-PRACTICE-EARLY-RELEASE-01 · d9c8883c42 | S7 (publication right after the freeze/check) | the TRAIN digest + practice bank digest published before the board-open record |

## D. Physics gates

| # | Rule | Owner record · commit | Binds | Proving check |
|---|---|---|---|---|
| R17 | Each Challenge's physics gates run on EVERY pool answer, in and out of range (A_gen included); any violation is GATE_FAILED | GATES-ON-POOL-3A-01 · main 8ba3b3f271 | S7 | truths-pass-gates per case; grader applies the gates to all rows |
| R18 | Physics law checks are hard gates, never score terms | PHYSICS-CONTRACT-BUILD-01 · 95675127f0; restated in MAKE-EXAMS-WORK-01 · d826351298 | S1, S7 | no law term in the score formula |
| R19 | Every sign gate passes a truth check on solver truth before it is used (else it is dropped) | COOLING-HOTSPOT-GATE-DROP-01 · 1465eff4d7 | S1, S3 | truth-sign check record per sign gate |
| R20 | Mandatory closed-form + cheap-method adversary (DOWN) gate before pools: STOP if a cheap method comes within margin_N of the oracle | EXAM-VALUE-PICKS-01 · df0a4201b7; PAYOUT-V5-AND-F02-V3-THRESHOLDS-01 · 4f7c7274aa (item 2) | S1 | adversary verdict on a never-graded probe pool |

## E. Scoring

| # | Rule | Owner record · commit | Binds | Proving check |
|---|---|---|---|---|
| R21 | Headroom: Carbon's good reference scores ≤ 0.75 on the sealed exam; the default sits ≥ max(0.10, 5 × the KOTH margin) below it; 1.0 means never wrong on remotely similar problems | SCORE-SCALE-MEANING-01 · 2c55146505; SCORE-GOOD-TARGET-01 · 6500c7c50d; SCORE-HEADROOM-REQUIRED-01 · 14c85f7dfe | S2, S7 | proof-suite target check |
| R22 | Design value is an optimisation test (Carbon's fixed optimiser queries the model under a fixed budget; the solver verifies) and must be as hard as accuracy | D-IS-OPTIMIZATION-01 · e56cc44173; GEN-SCOPE-AND-HARD-D-01 · f98d8a48c1 | S2 | the D definition in the version record |
| R23 | Top-k design scoring, k = 3 | EXAM-VALUE-PICKS-01 · df0a4201b7 (item 2) | S2, S8 | `pick_rule {"kind":"top_k","k":3}` in the version record |
| R24 | Balanced per-region scoring: D = mean over region classes of the class-mean d (and per-class A_gen, R31) | EXAM-VALUE-PICKS-01 · df0a4201b7 (item 3) | S2, S8 | `d_aggregate balanced_region_mean`; every target carries a registered region_class |
| R25 | Strict design honesty scale: s_h = 0.25 × the baseline's median pick error, measured on the version | EXAM-VALUE-PICKS-01 · df0a4201b7 (item 4) | S7 | s_h with its measurement digest |
| R26 | Leg minimums = the registered baseline's legs (catalog KRR, registered settings), measured through the miners' path | LEG-MINIMUM-BEST-AGENT-01 · edff2dbe1a; BASELINE-CATALOG-KRR-01 · 03f3ddaef1 | S7 | baseline graded via measure_pool (E8) |
| R27 | The first crown must beat the baseline total by the registered margin | FIRST-CROWN-BEATS-BASELINE-01 · 4313e52fe4 | S7, S8 | baseline floor in the pack |
| R28 | KOTH margin ≥ max(rebuild noise, 2 × SD of seed totals), measured at the registered recal; crowns by a multi-rebuild average and a bit-identical repeat grade | KOTH-TAKEOVER-RULE-01 · f5d96a76a1; KOTH-MARGIN-SEED-SPREAD-01 · 54ca06d7a8; CROWN-MARGIN-2SD-01 · 19ade6ade6; CROWN-MULTI-REBUILD-AVERAGE-01 · a322dea43c; CROWN-GRADE-REPEAT-01 · fa6b39ebc4 | S7 | margins recal record per version |
| R29 | Proof suite uses accuracy-matched gaming controls: each biased copy of the honest model scores ≤ the honest model | PROOF-ACCURACY-MATCHED-CONTROLS-01 · d8eae6862f | S7 | paired gaming result |
| R36 | The 4 new versions open on a worker image with the loop-body cache fix (all versions, bit-identical) + a versioned compiled forward used identically in practice, trainer predictions and judge inference (opt-in versions only; live versions stay eager; no rescore). A ship condition per version | GRAPH-FORWARD-COMPILE-NEW-VERSIONS-01 · 33c68843ad | S8 (worker image), S7 (practice / judge parity) | the version's worker image digest carries both; a bit-identical eager-vs-compiled parity record |

## F. Learning-model direction (1 Nov)

| # | Rule | Owner record · commit | Binds | Proving check |
|---|---|---|---|---|
| R30 | Learning-necessity gate A: tuned catalog learners must beat the best cheap method by > margin_N. HARD for Burst Thermal 3.0, Ribbed Bracket 2.0, Cooling 1.8; report-only for Motor 1.6, Cooling 1.7; never delays a version. A TRAIN-kernel reference row is reported | LEARNING-NECESSITY-GATE-01 · a60d14bf6d | S5 | LN record (grid digest, folds, UP vs DOWN, TRAIN-kernel row) |
| R31 | Separation read before big solves: tuned TRAIN-kernel vs the best tuned catalog operator per region class, with nearest-TRAIN distances; mining favours classes where the fit loses (class-level, sampler only) — since amendment 2 (0318421a) the TUNED read is OPTIONAL evidence, not a gate (R33 checks (1)–(3) decide) | SEPARATION-READ-ADOPT-01 · 6c24fbb582 | S4a | SEP-READ record per version |
| R32 | Design value vs the engineer's shortcut: D's zero point = the registered cheap method screen-then-verify at budget B (B = HUMAN_INPUT per version); off-step / shell-edge design targets where the fit loses; weight unchanged | DESIGN-VALUE-ENGINEER-BASELINE-01 · 5328e97cb7 | S2, S3, S4, S7 | DV-CURVE record; the owner's B pick; the disclosed zero point |
| R33 | Accuracy = min(in-range, balanced per-class out-of-range), with more cases where the fit loses and per-class floors REPORTED. AMENDED twice: strict A = min(in, out) applies when (1) the registered fits / formula / engineer shortcut score poorly OUT of range, (2) the noise ceiling sits well above them, and (3) ONE DEFAULT trained model (no tuning search) beats them in range, or the training set provably covers the OOD physics. "Poorly" and "well above" are owner values: report the measured gaps, never invent a bar; else `mean` and a TRAIN-COVER card for the next version. Milder fallback if the noise dry run fails | ACCURACY-OOD-MIN-01 · 497b5817c5; amendment 1 · c1f57f0ac0; amendment 2 · 0318421aa4 | S2, S4a, S7 | the three checks' measured gaps (shortcut OOD score, noise ceiling, default model in range) + ACC-NOISE |
| R34 | Each side of every new version is designed to make fits and formulas lose (accuracy: OOD / generalisation / off-grid; design: R32) | OOD-GENERALIZATION-DIRECTION-01 · 03f4c68f99 | S0, S4 | the S4a read and the Q9 rows show fits lose on both sides |
| R37 | Every new version carries a PHYSICS HARDNESS CARD (nonlinearity, coupling, regime switches / onsets, history / transients, field / high-dim inputs, realistic distributions: present / shown / missing); a version the R33 shortcut panel scores well on goes back to design with harder physics, while staying learnable | HARD-REAL-PHYSICS-DIRECTION-01 · 0ea04b3db8 | S0 (card), S1 (re-design trigger) | the version's card, owner-confirmed, + the R33 check (1) result |
| R38 | Every new version carries a TRAIN DATA ADEQUACY CARD before its freeze: TRAIN size vs input dimension; richness (scalars only vs the fields / traces the solver already computes); regime coverage (the G4 label table); learning-curve evidence (G6); whether the interface allows auxiliary supervision | TRAIN-DATA-ADEQUACY-CHECK-01 · 3b42c19c2b | S0 / S4 (before the freeze) | the version's card, owner-confirmed, Validator-receipted |

## G. Generalization axes (STRONG_CHECKS_SPEC_20261102.md). ADOPTED: OWNER-STRONG-CHECKS-GENERALIZATION-AXES-01, lead-records 9515dd60d9ce8a3806f2aef076d745b1ba9f432c (owner: "Love that... Lock them all in.")
Freeze-binding for the 4 new versions: G1, G2, G3, G7, G8, G9. Report-only: G4, G5, G6. Most map onto rules above; the axis is the owner-facing lens.

| # | Axis | Maps to | Binds | Proving check |
|---|---|---|---|---|
| G1 | Extrapolation past the TRAIN range | R7, R33 (amendment 2 checks) | S4 (freeze) | extended / outer-shell classes present + R33 checks (1)–(3) |
| G2 | Interpolation holes inside the range | R8 (inner band), R15 distance rule | S4 | inner-band cases at max-norm distance ≥ the registered threshold (owner value; rec 0.10) from every TRAIN point |
| G3 | Hard regimes (near-zero torque, mode crossings / band edges, nonlinearity onset, applicability edges) | R9, R31 | S4 | mined regime classes, per-class floors reported |
| G4 | Leave-regime-out | — | report | the default model with one regime held out, scored on it |
| G5 | Nearby variants | (neighbour tasks) | report | a registered variant set, scored separately |
| G6 | Learning curve | — | report | default model + best shortcut at 25 / 50 / 100 % of TRAIN |
| G7 | Seed robustness | R28 | S4 / S7 | rebuild noise across the registered seeds; a win exceeds it |
| G8 | No leakage | R10, R15, invariant 1 | S4 | distance audit exam vs TRAIN and vs published practice; lattice draws skip published cases; sealed seeds |
| G9 | Physical validity everywhere | R17, R19 | S4 / S7 | every physics gate on every OOD case (truths pass gates) |

## Version-specific owner records (bound in each version's plan, not general rules)
- **Burst Thermal 3.0:** OWNER-F02-V3-PEAK-LIMIT-95C-01 · 57ea32d880 (3.0 keeps the 95 °C peak limit as its REGISTERED peak limit); F02-NEXT-VERSION-DIRECTION-01 · 9f04949119; F02-V3-BOX-CUT-01 · 2e39fb5dcb; F02-V3-LEAKAGE-NONLINEARITY-01 · 50d84f937e; F02-V3-PICKS-01 · 9b27ddb0a2; F02-V3-TABLES-SIGNED-01 · 80196692aa; the thresholds in PAYOUT-V5-AND-F02-V3-THRESHOLDS-01 · 4f7c7274aa.
- **Ribbed Bracket 2.0:** F08-V2-VALUES-01 · 72c789da81; F08-V2-ALLOYS-SIGNED-01 · fe7f6c19a9; OWNER-RB20-SOLVER-REPIN-PASTIX-01 · 4b2327944c (re-pin the F08 reference solver to 64-bit PaStiX after its checks, with the deck migration; the image is never distributed outside Carbon; the per-case memory limit is raised only after the measured figure goes back to the owner).
- **Motor 1.6 / 1.7:** MOTOR-16-17-SPLIT-01 · b729d703ee.
- **Motor next version (after 1.7):** OWNER-MOTOR-NEXT-SHORTCUT-COARSE-MESH-01 · 47bf1946e8: a coarse-mesh run is registered as Motor's engineer shortcut for R32 (the Validator sets the rung after a $0 ladder check), with the formula as a cross-check. Motor 1.7 keeps the R32 part-2 fallback.
- **Cooling 1.7 / 1.8:** EXAM-VALUE-PICKS-01 item 5 (fairness: Option B or TRAIN refit); IMAGE-MOVE-REGISTRY-OVERLAY-01 · bcf47faeb9.
