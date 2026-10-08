# Training budget study: the Challenge sheet template

**Authority.** OWNER-TRAINING-BUDGET-STUDY-01, -02 and OWNER-COMPUTE-BUDGET-01.
Every Challenge runs the same study (Phases A-H, rules R1-R11) with the same
code. What differs between Challenges lives in two places only: this **sheet**
(values the owner sets) and the Challenge's **adapter** (things its existing
records already define). A Challenge with a missing sheet value or adapter
item cannot start the phase that needs it; the value stays `HUMAN_INPUT` and
the harness fails closed.

## The sheet: values the owner sets per Challenge

| Field | Used by | Notes |
|---|---|---|
| `challenge_id`, `challenge_version` | All | One registered version per study |
| `gpu_model`, `image_digest` | All | The validator's pinned GPU and image |
| `spend_ceiling` | Stop rules | Pod time and generation, in the track budget's unit |
| `study_seed_root` | Data | Separate from the live root |
| `study_contract_ranges` | B, C, F | Raised study-only ranges; never registered live |
| `rebuild_time_target`, `memory_ceiling` | R3 | The costliest recipe at L must meet both |
| `study_time_limit` | All | The study worker's limit, above R7's |
| `seeds_per_setting` | B, C, G, H | At least 3; Phase D uses 5 |
| `study_recipes` | A-C | The starting configurations, spanning every rebuildable family |
| `train_size_ladder` | G | Defaults to 1/4, 1/2, 1, 2, 4 and 8 times the current TRAIN size |
| `generation_ceiling` | G, R9 | The largest study TRAIN set the spend allows |
| `minimum_panel_size` | H | Study panel population |
| `target_utilization` | R11 | Headroom so a queue never builds |
| `gpu_ceiling` | R11 | GPUs one validator can have |
| `expected_participation` | R11 | Submissions per tempo, besides the worst case |
| `study_eval_size` | A-C, E-H | The study evaluation set's size (drawn on the producer, #738) |
| `confirmation_size` | D | The sealed confirmation set's size, used once in Phase D |

A sheet also states its `status` and, per value, a one-line `rationale`.
No production sheet exists yet: a sheet's status names what its values are
for (today only `TEAM_PROPOSED_OWNER_APPROVED_FOR_TESTING`).

The cadence worst case is network-wide, not per sheet: 256 submissions per
72-minute tempo (OWNER-TRAINING-BUDGET-STUDY-02).

## The adapter: what each Challenge's records already define

| Item | Used by | Source today |
|---|---|---|
| The construction contract and its cost-driving settings | B, C, F, cost | `carbon/reconstruction/capability_registry.py` |
| The rebuild worker and backends (JAX, PyTorch) | All | The Challenge's validator worker |
| The exam code: gates, error, key-region score | Scoring | The Challenge's scoring module |
| The equivalence margin | R2, R9 | The Challenge's exam rule |
| The finalist rule | R4, R10 | The Challenge's exam rule |
| The public generator and truth service | Data, G | The Challenge kit |
| The legitimate admission panel | H | Admission Track A |
| The current TRAIN size | G | The contract envelope (`train_cases`) |

A second Challenge supplies a sheet file and these adapter items. It adds no
code to the shared harness, cost calculator or capacity calculation.
