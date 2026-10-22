# OWNER-MINER-LIMITS-GO-01: the owner's "go" on removing every miner limit that does not protect the exam

Date: 2026-10-22
Status: APPROVED by the owner.
- First said to the Lead ("go on the limits"; the Lead's note `OWNER_GO_LIMITS_20261022.md`).
- Then confirmed directly in the Carbon Validator's session, when asked whether the whole sheet was approved: "Yes, the whole sheet".

Authority: the owner, under OWNER-MINER-LIMITS-EXAM-ONLY-01 ("maximum miner freedom while keeping the exam safe").
Scope: new plans and new Challenge versions only. Old campaigns replay exactly as recorded, and nothing is rescored.
Maturity: an engineering-limits decision. **No security or containment acceptance is created** (containment stays CONTAINMENT-ACCEPT-TESTNET-01, testnet/rehearsal only, and OWNER-WORKER-RESOURCES-LARGE-MODELS-01, conditional on its real-lane test).

## The sheet approved

`LAUNCHPAD_LIMITS_FOR_OWNER.md` (Launchpad, 2026-10-22), sha256 `fa8f27cf6dd15a6fb41d98d19bc777a42e776b94c5fa4251e1069f5a41fcd39e`. It is held in the team's working notes, outside the repository. Its content, row numbers as in the combined limits table of LAUNCHPAD_REFUSAL_AUDIT_20261021:

**Going away:**
- #12: old 1 MiB / 4 MiB caps on v7 paths. The version's own intake bounds apply instead.
- #5, #6: training step, iteration, batch and learning-rate maxima for Battery and the F08/F02 graph trainer. Only structural validity stays; the rebuild time limit binds.
- #7: Motor fixed menus. A new Motor version takes open numbers; Motor 1.3 is unchanged.
- #8, #9: model input/output/timeout maxima on a miner's selection. Provider-published limits are the defaults; only representation bounds remain (tokens ≤ 2**53 − 1, timeout ≤ 2**31 − 1 s).
- #4: recipe shape counts.
- #14: the 256 direct-task count.
- #23: the 100,000 tunable cap.

**Becoming defaults the miner can change (a warning, never a stop):** #1–#3 and #17 (read sizes and argument sizes, scaled to the context window); #15 and #18–#20, #22 (practice time, smoke steps, export sizes, remote time, hunt/plan settings, retry and compaction knobs).

**Staying (exam, grade, machine or keys, or an outside fact):**
- #25: final exam epochs.
- #10, #24: the rebuild wall and determinism. The rebuild wall is 1,800 s interim until measured (OWNER-REBUILD-TIME-LIMIT-01). The 600 s productive deadline is not kept as a training bound.
- #11: container limits, with the larger v7 profile.
- #16, #21: parser and message guards, resized for v7 documents.
- #13: the from-scratch rule's 16 KiB constant cap (NO-MODEL-SIZE-CAP-01); the compile deadline comes from a measured compile.
- The RunPod environment bound (OWNER-A40-POD-ENV-PROVIDER-BOUND-01).

No row was held back.

## How it is applied

- Each change still lands through PR Head with its Validator receipt (miner-visible), in the sheet's order: #12, then #5–#7, then the defaults, then #8/#9 and #4/#14/#23.
- The KEEP rows are co-signed in VALIDATOR_REFUSAL_AUDIT_COSIGN_20261021.
