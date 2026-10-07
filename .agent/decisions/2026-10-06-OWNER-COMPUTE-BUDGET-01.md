## 2026-10-06 — OWNER-COMPUTE-BUDGET-01: one fixed compute budget per Challenge, and one Challenge-neutral budget study

**Authority.** The owner, 2026-10-06, in a Claude chat: "Should we make the
training resources a fixed and budgeted toggle set to a certain level for each
challenge. Is that hard. That way every model had the same resources too no
matter what they chose as their ratio", then: "Add it. And all these things
you're adding. 727 too. Make them generalizable so all challenges can run the
same study". Recorded by a Claude session. It builds on
OWNER-TRAINING-BUDGET-STUDY-01 and -02 and changes neither's frozen rules.

1. **Target: one compute budget per Challenge.** Each Challenge's training
   limit is to be a single compute budget, calculated from the recipe and
   checked at submission, the same for every recipe. A miner spends it in any
   ratio: width, depth, steps, batch or ensemble members. It is a ceiling, not
   an amount that must be spent. The Challenge's per-setting ranges remain only
   as sanity bounds.
2. **R5 still decides when a Challenge can switch.** A Challenge adopts the
   compute budget once its study shows the cost formula meets R5. Until then,
   or if it never does, that Challenge keeps per-setting caps set by R3. The
   budget's level comes from R3 at the TRAIN size R9 sets.
3. **Compute, never time.** The budget counts compute from the compiled
   recipe on the validator's pinned image. Training never stops on a clock;
   the R7 time limit stays only as a safety net.
4. **Miners can check cost before submitting.** Each Challenge's research
   environment offers the same cost calculator the validator uses, under the
   "train" provision (OWNER-RESEARCH-ENVIRONMENT-01).
5. **Generalizable by construction.** The study (Phases A-H, R1-R11), the
   cost calculator, the capacity calculation and the contract's budget check
   are Challenge-neutral code that takes the Challenge as a parameter. Each
   Challenge supplies only its sheet and its adapter
   (`docs/development/training_budget_study/SHEET_TEMPLATE.md`). Battery is
   the first instance, never the design; a battery-only literal in shared code
   is a defect (the GRAPHITE-ADMISSION-01 standing rule).

**Work:** `.agent/tickets/TRAINING-BUDGET-01_challenge_neutral_study_and_compute_budget.md`.

**Unchanged.**
- R1-R11 and their recorded digests.
- No live contract changes here. Switching a Challenge to its compute budget
  is a registry change opened only after the owner's decision on that
  Challenge's study result, with tech-lead review.
- No production value is chosen here: every budget, ceiling and margin comes
  from a Challenge's sheet or study.
