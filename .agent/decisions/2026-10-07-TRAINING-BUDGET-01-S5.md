## 2026-10-07 — TRAINING-BUDGET-01 slice 5: the analysis, R2-R10 and the F3/F4 fits

**Authority.**
- **Scope.** TRAINING-BUDGET-01, scope item 4 (the analysis), under the frozen
  rules R1-R11.
- **Readings.** Where the frozen text leaves a reading open, the Test Lead's
  rulings of 2026-10-07 decide. The Test Engineer proposed each reading, and
  the Test Lead accepted it with additions.
  1. **Curves.** A curve is one recipe's ladder in one setting, scored by the
     median over seeds. A recipe's plateau is the largest of its curves'
     plateaus. A curve without a plateau is reported. If any of the three
     best recipes has a curve without a plateau, L is not proposed for that
     setting.
  2. **Units.** Plateaus are computed in every candidate unit. L is stated in
     the unit R5 adopts.
  3. **Best recipes.** The best recipes rank by median score at their plateau
     under the exam rule in force, with ties going to lower cost. Once the
     owner adopts a tuned score variant, R4 and R10 are rerun under it as a
     reported recheck.
  4. **Finalist verdicts.** Per-case predictions stay with the study sets on
     the producer host. The analysis receives finalist-rule verdicts and
     digests only.
  5. **Fits.** The F3/F4 fit is ordinary least squares per family, on Phases A
     and B only. It reports each family's residual spread and its share of
     points outside 1.5×.

**Decisions (engineering, within those rulings).**
- **"Doubling the budget".** Between consecutive points of a curve, the
  improvement is the score change per doubling, that is, divided by log2 of
  the budget ratio. On a ladder whose budget doubles exactly, this is the
  rule's own comparison. Phase B doubles the setting, which doubles the cost
  only for steps.
- **R3's rounding.** "Rounded up" means the next whole number in the unit.
- **R5's "simpler formula".** The caller lists the formulas simplest first;
  the spec's order is F3 before F4.
- **R10's survivors.** For each fraction, k is the smallest k that keeps every
  finalist on every seed. A k equal to the whole panel screens nothing, so it
  is not safe.
- **R9's data-binds test.** Data binds when D is the largest size the ceiling
  allows and the last doubling still gained at least half the margin.

**Tests.** `tests/cpu/test_training_budget_analysis.py` binds each rule to its
text by example:
- R5: 95% within 25%, any rebuild over 1.5×, and the simpler formula first;
- R6, R7 and R8, including the spec's "at 5 minutes, 288 a day";
- the OLS fit;
- plateaus, including uneven steps and lower-is-better scores;
- R2, R3 and its blocking curve, R9 binding and not binding, R4 and R10.
