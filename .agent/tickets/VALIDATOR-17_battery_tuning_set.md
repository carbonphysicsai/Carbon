# VALIDATOR-17: battery's sealed tuning set

**Status:** implemented (tooling); sealing is an operator action.

**Authority:**
- OWNER-GRAPHITE-TEST-WAVE-08 §1 (#647);
- the Test Lead's queue item 1, 2026-10-05.

**Executor:** the Carbon Validator session. Branch
`claude/validator-17-tuning-set`, from main `1e99ad120`.

## What

- **The role.** `graphite-tuning-v1` is registered in
  `confirmation_sets/`, pinned by digest, and reserved in
  `interface.RESERVED_SEED_ROLES` (`BATTERY_TUNING_ROLE`).
  - **Size:** 200 cases plus 4 hidden duplicates.
  - **Population:** the Level 0 study sheet's (`battery-published-box-uniform-v1`).
  - **Strata:** `NONE_UNIFORM_LAW`.
  - **Custody:** sealed in the testnet deployment's journal, so EV5 and
    `graphite-confirmation-v1` are overlap-checked by regeneration.
- **Overlap.** The seal refuses any overlap with:
  - EV5 and `graphite-confirmation-v1` (required prior roles);
  - published cases, which include TRAIN and PRACTICE;
  - every committed engineering-value study's decision cases
    (`public_decision`);
  - the rotating pool (a required private prior).
- **The operator module.** `challenge_validator/tuning.py`:
  - `export-pool`: the hidden pool's inputs, as the prior file;
  - `jobs`: regenerate and recall the batch, never commit;
  - `solve`: the pinned truth image;
  - `predict`: host CPU rebuilds;
  - `score`: per-member components plus per-case rows, for re-scoring without
    retraining.

  Every file is owner-only and outside the repository.
- **Graphite's protected markers** gain the tuning set's names
  (`exam_material`), so a request or result naming it is withheld from an
  agent.
- **The operator runbook:**
  `docs/development/graphite/HIDDEN_POOL_AND_TUNING_RUNBOOK.md`.

## The practice decision set (B4)

The Test Lead, 2026-10-05: B4 is PRACTICE-SAFETY-01's practice decision set,
which is public and not yet committed.
- It is not a prior, so it does not block the seal.
- When it is committed, `tuning recheck` compares the sealed set against it.
  On any overlap B4 is reselected, never the sealed set.

**Re-check record:** none yet. Each entry gives the date, the B4 file's
SHA-256, the verdict and the count.

## Open

- **Rotating-pool batches prepared after the seal** are drawn from an
  independent root. A check that each new pool batch avoids the tuning set's
  cases is a follow-up.
- **Graphite runs through the hidden pool** need the phase-3 option, which
  follows after #642.

## Maturity

IMPLEMENTED and TESTED (DEVELOPMENT). Not a security audit.

## Prospective amendment: a near-limit quiz stratum (VALIDATOR-19 slice Q)

The owner, 2026-10-06: "Yes make the quiz questions maximally effective."

- `graphite-tuning-v1` is unsealed. It is superseded before any seal by
  `graphite-tuning-v2`, registered as a new document version, which adds a
  near-limit quiz stratum: oversample, solve, keep the near-limit cases on
  both sides.
- The quiz's size is set with Data Collection. Its margin is HUMAN_INPUT
  (swept).
- The tuning set's accuracy rows exclude quiz cases. The quiz feeds G-FEAS,
  G-PLATE and false-infeasible only.
- v1 is never sealed.

**Data Collection's size proposal (2026-10-06; proposed, not adopted).**
- **Selection:** 40 quiz cases, selected by Q2 from a near-limit pool of 160
  (4x oversample).
  - Q2 means the cases within 4 bands where the public panel splits most
    evenly on feasibility.
  - **Bounds:** below n=20 the false-infeasible rate exceeds 0.13; above 40,
    detection dilutes.
- **Draw size:** about 25% of cases fall within 4 bands, so about 640 drawn
  cases yield 160 near-limit cases. Near-limit oversampling at draw time is
  the alternative.
- **Definitions** are in #686: `score_tuning.near_limit` (the minimum
  |margin| on plating and peak temperature, in contract bands) and
  `false_infeasible_rate`.
- **Caveat:** no design reached the registered bar (p05 AUC >= 0.9). The
  quiz helps, but alone it does not expose decision-level failures.
- **Still HUMAN_INPUT:** the margin (swept) and the sizes, until the owner
  adopts them.
