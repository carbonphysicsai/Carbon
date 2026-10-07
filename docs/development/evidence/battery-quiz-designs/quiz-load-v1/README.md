# Quiz producer load: fixed-quiz risk and coarse-then-refine Q3 (analysis memo)

This is an analysis memo on the public stand-in only. It is not a registration, chooses no threshold, and is never a gate. Reproduce it with `scripts/dev/battery/quiz_load.py` (`probe`, `coarse_refine`).

## 1. A long-lived quiz (`probe.json`)

**Model.**
- **Pool.** The scoring set's near-limit pool: 392 cases within 4 bands, 217 of them infeasible.
- **Quiz.** 80 random pool cases. The panel split is not modelled.
- **Attacker.** A miner whose model is accurate everywhere except where it chooses to be `boundary_optimist`.
- **Feedback.** One gate bit per submission: pass when the quiz shows no false-feasible (tau = 0; a tau above 0 only helps the attacker).
- **Probing.** The miner splits input space into equal cells and probes by adaptive binary splitting: be optimistic on a group of cells, then read pass or fail. Once it has learned the quiz, it is optimistic in every clean cell.

**Q2.** "Gain" is the attacker's false-feasible on fresh near-limit cases while it still passes the fixed quiz.

| Cells (c1, c2, T, SoC) | Probes, median (p90) | Gain |
|---|---|---|
| 2^4 (16 occupied) | 24 (28) | 7 % |
| 3^4 (61) | 67 (76) | 24 % |
| 4^4 (141) | 108 (123) | 38 % |
| 6^4 (277) | 148 (170) | 52 % |
| 8^4 (348) | 162 (188) | 55 % |

**Q3.** The 8 scenario conditions are uniform over the envelope. The attacker avoids every quiz condition's cell.

| Cells (T, SoC) | Probes, median (p90) | Free share of conditions |
|---|---|---|
| 4^2 | 22 (25) | 56 % |
| 8^2 | 43 (49) | 88 % |
| 16^2 | 66 (73) | 97 % |
| 32^2 | 91 (98) | 99 % |

**Budget.** One scored submission per tempo is 20 a day per hotkey at Bittensor's default tempo (360 blocks of 12 s).
- **A day:** one hotkey gets about 20 probes, enough for coarse Q3 cells (56 % of conditions free). Four hotkeys get the Q2 3^4 attack (24 %).
- **A week:** one hotkey gets about 140 probes. That covers Q3 at 32^2 (99 % free) and Q2 at about 4^4–6^4 (38–52 %).

**Caveats.**
- The model assumes a clean per-gate bit. Bundled or noisy verdicts, or other gates that also fail, make probing slower.
- It assumes a well-calibrated base model. A worse model learns less.
- The panel split concentrates Q2 cases, so fewer cells are defective and probing gets easier.

**Benefit of a shared quiz.** Two nested optimists (pool false-feasible 0.567 vs 0.396) are ordered correctly 100 % of the time on a shared quiz and 96.5 % on independent quizzes. Pairing removes quiz-draw variance between miners. The nesting makes the paired figure 1 by construction, so it is an upper bound. For a single hotkey, a fixed quiz adds no new cases over time, so pooling across batches gains power only when the quiz rotates.

**Cheap detector (canary).**
- Score every submission, unreported, on a disjoint near-limit canary of the same size.
- Flag a submission when the quiz shows clearly fewer false-feasibles than the canary (one-sided Fisher test, alpha 0.01 as an example; the alpha is HUMAN_INPUT).
- With 44 infeasible cases each: honest members at 5 % and 20 % false-feasible are flagged 0.05 % and 0.55 % of the time; the fitted attacker (3^4 cells) 92 % of the time.
- The rotation-drop signal Test Lead suggested is the same comparison, available only when the quiz rotates. The canary gives it every batch, at the cost of the canary's solves.

## 2. Option 4: coarse-then-refine Q3 lattice (`coarse-refine.json`)

**Method.**
- Solve EV4's 35 points first. Then refine to the 117-point lattice around these anchors:
  - the coarse oracle optimum, re-anchored on the refined optimum until it stops moving;
  - every panel pick, using the other 25 members as a leave-one-out panel;
  - the coarse points within 1 band of a limit.
- **Data.** quiz-diagnostics-v1 (b): 9 scenarios, 26 members. Both judged scenarios have the full 117 references.

| Radius | Solves per condition, mean (max) | Pick coverage (LOO, 234) | Judged verdict match | Judged optimum match |
|---|---|---|---|---|
| ±1 lattice step | 52 (71) of 117 | 99.6 % | 52 / 52 | 52 / 52 |
| ±1 coarse step | 62 (84) of 117 | 100 % | 52 / 52 | 52 / 52 |

**Reading.**
- Coarse-then-refine cuts Q3 solves by about 45–55 %, and on this stand-in it never changes a verdict or the optimum.
- An uncovered pick (1 of 234 at ±1 lattice step) needs one evaluation-time solve or falls to quiz-registry-v8's pessimistic backstop.
- **Caveats:**
  - The leave-one-out panel is 25 related EV4 members. A novel miner may pick outside the refined set more often.
  - Only 2 scenarios have full references.
