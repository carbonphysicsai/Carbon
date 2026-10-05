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
  - the rotating pool and the practice decision set (required private
    priors). The seal fails closed until both files are supplied.
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

## Open

- **The practice decision set.** Its source and keying are pending the Test
  Lead's answer.
- **Rotating-pool batches prepared after the seal** are drawn from an
  independent root. A check that each new pool batch avoids the tuning set's
  cases is a follow-up.
- **Graphite runs through the hidden pool** need the phase-3 option, which
  follows after #642.

## Maturity

IMPLEMENTED and TESTED (DEVELOPMENT). Not a security audit.
