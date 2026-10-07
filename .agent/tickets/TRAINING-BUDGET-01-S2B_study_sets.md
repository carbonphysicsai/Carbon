# TRAINING-BUDGET-01 slice 2b: study-set creation on the producer

**Owner decisions:** OWNER-COMPUTE-BUDGET-01 (2026-10-06, PR #727), under
OWNER-TRAINING-BUDGET-STUDY-01 and -02.
**Specs:** `docs/development/CHALLENGE_TRAINING_BUDGET_STUDY.md` (Environment
and test data; runbook steps 4 and 10); the Test Engineer's proposal of
2026-10-07 for the interface.
**Status:** implemented and tested on CPU with synthetic roots; not run on
the producer host.
**Owner:** the Carbon Validator (producer-side, security adjacent).

## Scope

- `carbon/challenge_validator/study_sets.py`: the study root, the study
  journal, the three sets, the overlap check, references, the public
  manifest (`carbon.training-budget.study-set.v1`), the export and the
  one-time confirmation release. VM-only CLI.
- `interface.STUDY_ROLES` (`study-train`, `study-eval`, `study-confirm`)
  added to `RESERVED_SEED_ROLES`, so no pool path can prepare them.
- `confirmation_sources.BatterySource` gains `study_root`, `study_seed_pin`,
  `study_draws` and `study_solve_command`. The shared module carries no
  Challenge literal. A source without these methods is refused.
- Tests: `tests/cpu/test_challenge_validator_study_sets.py`.
- Runbook: `docs/development/training_budget_study/STUDY_SETS_RUNBOOK.md`.

## Interface choices beyond the proposal

- The spec also takes an `approval` record, checked as the producer checks
  its own (`producer.require_approval`). The spec's approval table reserves
  a new study seed root to the owner.
- The harness journal's first event must be `opened` for the same
  Challenge.
- The confirmation release carries the confirmation set's references as
  well as its inputs, so the pod can score Phase D.
- Each TRAIN ladder position has its own prefix fingerprint, references
  digest and withdrawn count in the manifest.
- A ladder size that is not a whole number of cases, or a ladder that is not
  strictly increasing, is refused, never rounded or sorted.

## HUMAN_INPUT

Each of these is `null` or `HUMAN_INPUT` until the owner supplies it, and
the commands that need it refuse until then:
- `approval`: the owner's record approving the study seed root;
- `train_size`: the current TRAIN size (the sheet, R9);
- `train_size_ladder`: the sheet's ladder;
- `generation_ceiling`: the sheet's ceiling;
- `eval_cases` and `confirm_cases`: the study set sizes;
- `private_priors`: the files for the live pool, the tuning and confirmation
  sets and EV5, which the operator exports on the producer host.

Whether the study runs on the Hetzner producer host is the Validator's and
the Test Lead's decision.

## Not in this slice

- Spend accounting. Generation is bounded by `generation_ceiling`, but solve
  time is not metered against the sheet's spend ceiling.
- Coverage reporting (key-region case counts). That belongs to the harness
  and analysis slices.
- Running any of it on a real host. No real root, deployment or EV5 batch was
  read.

## Non-claims

DEVELOPMENT only. No score, weight, reward, qualification, security
acceptance or LIVE authority. The tests are not a security audit.
