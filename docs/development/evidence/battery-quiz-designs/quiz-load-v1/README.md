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

## 3. Random draws from a pre-solved bank (`bank.json`, `quiz_bank.py`)

**Owner's objective, 2026-10-07.** "A path to all 8 challenges that DRIVES the miners at learning the full distribution." So B (bank size) and E (appearances before retirement) are chosen so that the cheapest way to score well is to learn the registered population P(x), not the bank.

**Model.**
- **Bank.** Every quiz and pool batch is a fresh draw of n from a bank of B.
- **Stand-in bank.** Bootstrapped from the public scoring set, with 2 % input jitter. Each copy keeps its parent's verdict and the boundary-optimist's damage flag. The Q3 bank is uniform conditions.
- **Attacker.** The same splitting attacker as in section 1. A pass is now noisy (a draw can simply miss its damage), so a cell is believed clean only after r passes in a row. r gives 95 % confidence and is about 3B/n.
- **Gain.** The attacker's false-feasible on fresh P cases. "Ceiling" is the gain from perfect knowledge of the bank.
- **Coverage.** The P mass of the input cells the live bank occupies (4^4 cells stand in for registered strata).

**Fit-the-bank vs learn-P gap.**

| B/n | Q2 ceiling | Q2 coverage of P | Probes (hotkey-days at 20/day) | Gate fails while exploiting | Pool (n 120) ceiling | Pool coverage |
|---|---|---|---|---|---|---|
| 1 (fixed) | 34.7 % | 52 % | 104 (5) | 0 % | 15.7 % | 40 % |
| 2 | 21.8 % | 73 % | 375 (19) | 50 % | 12.4 % | 64 % |
| 5 | 9.0 % | 91 % | 1,062 (53) | 20 % | 6.8 % | 89 % |
| 10 | 3.3 % | 97 % | 2,019 (101) | 9 % | 3.3 % | 99 % |
| 20 | 1.3 % | 99 % | 3,842 (192) | 0 % | 1.3 % | 100 % |

**Reading.**
- As B/n grows, the bank covers P's support. "Learning the bank" then converges to learning the physics near the limit: at B ≥ 10n the bank-fitting payoff is at most 3 % false-feasible, for 100 or more hotkey-days of probing.
- A noisy pass also makes the attacker fail the gate in 9–50 % of batches while it exploits at B 2–10n.
- **Q3 conditions need stratified banks.** Uniform scenarios cover only 46 % of 16^2 condition cells at B = 20n, though probing then costs 428 hotkey-days and fails the gate 27 % of the time.
- So the Q3 bank should stratify over the registered condition strata at coarser cells (for example 8^2: 160 scenarios cover about 92 %), with the steering reported per stratum.

**Power.**
- The test: a subtle optimist (false-feasible 6.6 %) against an honest member (5.4 %), as P(pooled bad > good).
- On a fixed quiz it stays at about 0.6 for every W (0.64, 0.60, 0.62, 0.56, 0.61 for W 1–16). The same cases add no evidence.
- With fresh draws it rises with W: 0.61, 0.65, 0.71, 0.78 and 0.85 for W 1, 2, 4, 8 and 16.

**Exposure and retirement.**
- At one draw per validator per tempo (20 a day), a case appears on average 20·n/B times a day: 2 a day at B = 10n.
- The share of the bank seen after N draws is 1 − (1 − n/B)^N. At B = 10n that is 41 % after 5 draws and 88 % after 20.
- **Rule:** retire a case after E appearances and publish it to training. Steady state then needs n/E new cases per batch.
- Turnover per validator is E·B/(n·20) days: 5 days at B = 10n, E = 10. That is far shorter than the about 100 days a bank-fitting attack needs, so the attack chases a moving target. Retired cases are published to everyone, so knowing them gives no advantage.

**Recommendation per Challenge class.** B and E are HUMAN_INPUT; these are the stand-in's suggestions. The pool bank is a faithful draw from P (Q = P). Quiz banks are steered strata with their own reporting. Coverage is reported per registered stratum and refreshed as cases retire.

| Class | Example | B/n | E | Replenish per batch | One-time bank |
|---|---|---|---|---|---|
| Cheap (CPU-minutes per case) | battery pool n 120, Q2 n 80 | 20 | 5 | 24 / 16 cases | 2,400 / 1,600 cases |
| Cheap, decision tasks | battery Q3 n 8 (117 or 52–62 solves each) | 20, stratified | 5 | 1.6 scenarios (about 190 solves; about 90 with coarse-then-refine) | 160 scenarios |
| Motor-like (about 0.6–1 core-h per point) | motor pool n 60 | 10 | 10 | 6 cases | 600 cases (about 500 core-h) |
| Motor-like, decision tasks | motor Q3, 8 candidates × 6 conditions | 10, shared geometry bank | 10 | about 1 geometry × 6 conditions | about 160 geometries × 6 |
| CFD-class (core-hours per case) | cooling pool n 60 | 5 | 20 | 3 cases | 300 cases |

- At B = 5n (CFD-class), the bank-fitting ceiling is still 7–9 %. Pair it with section 1's canary detector there.
- Replenishment per day scales with the registered cadence (batches per day), and with the number of validators when they share a bank.
