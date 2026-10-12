# CONTROL-VARIATE-PREDICT-01: a first estimate of rho (METHOD-ONLY)

**This is not evidence about any member.** No qualified member can predict the battery v3 or 10p/12s motor cases, because their registered TRAIN sets are unsolved. On the Test Lead's decision, each case is instead predicted by a small fixed model fitted on the *other* pair cases. The result is a first estimate of rho for the control-variate lever in PROVEN-LEADERBOARD-03, section C. It is DEVELOPMENT only and makes no qualification, threshold or value claim.

**Data.** Data Collection's public two-rung pairs (`carbon.two-rung-pairs.v1`, `PUBLIC_DEVELOPMENT`), in `~carbon/shared/evidence/two-rung-pairs/`. The script refuses unless each file matches its `MANIFEST.json` digest:
- `battery-pairs.jsonl`: 136 cases, sha256 `56784fad7d867e06963ed9f36aecf5c85d2d4e7a2b6ca0968d1cef3e1144c00e`;
- `motor-pairs.jsonl`: 50 cases, sha256 `b7f23e79f79dc5a73b2b9bf107d24ed6234ff62a49d5b473e0cf04e4d1280c7d`.

**Method** (`scripts/dev/control_variate/loco_fit_on_pairs.py`, numpy only, deterministic, no random draws):
- Three fixed models, with hyperparameters set before any result was seen: RBF kernel ridge, 3-nearest-neighbour, and quadratic ridge.
- The fit target is the registered rung only (battery `standard`, motor rung 1), so a prediction does not depend on the rung it is judged against.
- Hold-outs: leave one case out (`loco`); for motor also leave the case's whole design out (`lodo`).
- rho: for each challenge and metric, the leader is the model with the lower mean error against the fine rung. For each other model, d = (e_leader - e_challenger) / mean(e_leader), and rho is the Pearson correlation over cases of d judged against the coarse rung and against the fine rung. The median over challengers is reported. A constant reference (battery `v_max_v`) is skipped.

**Result** (coarse = the registered rung; fine = rung 2 unless stated):

| Challenge | Metric | rho |
|---|---|---|
| battery (136) | charging_t_max_c | 1.000 |
| battery (136) | minutes | 1.000 |
| battery (136) | plating_min_v | 0.928 |
| battery (136) | q30_over_q1 | 0.746 |
| battery (136) | median over metrics | **0.964** |
| battery, rung 3 on 42 cases | median over metrics (plating_min_v 0.536, q30_over_q1 0.671) | 0.835 |
| motor (50), loco | mean_nm / pk_pk_nm | 1.000 / 0.997, median **0.998** |
| motor (50), lodo | mean_nm / pk_pk_nm | 1.000 / 0.997, median **0.998** |

**How to read it.**
- rho is high where the rung gap is tiny against the model's own error, because both references then rank the models the same way. It is lowest where the rung gap is largest (`plating_min_v`, `q30_over_q1`; the rung 3 subset).
- The models are weak and fitted to the same cases they are judged on, so this is a method estimate. A real member's rho may differ, mainly where its error is small against the rung gap.
- Section C's lever also needs the coarse rung to be about 10 times cheaper than the registered one. These pairs only have rungs finer than the registered one, so the cost side is not measured here.

The predictions (`loco-fit-on-pairs-*` and `lodo-fit-on-pairs-*`, one `.jsonl.gz` per method, every row labelled METHOD-ONLY) are on the shared host and are not committed.
