## 2026-10-06 — OWNER-TRAINING-BUDGET-STUDY-02: the training budget study also sets TRAIN data size and validator capacity

**Authority.** The owner, 2026-10-06: "Add this analysis to testing so we can
determine data size and allowed resource time per challenge." Recorded by a
Claude session. It amends OWNER-TRAINING-BUDGET-STUDY-01 prospectively.

1. **The study decides two more things per Challenge:** its TRAIN data size,
   and the GPUs one validator needs to rebuild every submission at the
   Challenge's cadence. It adds questions 8-10, Phases G (data size) and H
   (screening fidelity), and the cadence-capacity calculation
   (`docs/development/CHALLENGE_TRAINING_BUDGET_STUDY.md`, "Extension: data
   size, screening and cadence").
2. **Rules R9-R11 are frozen** in
   `docs/development/training_budget_study/DECISION_RULES_R9_R11.md`, SHA-256
   `1dcbbcbf45e4b19f679d8b3791577778eedbb9e23c23ca569e17ac30431be088`.
   `tests/cpu/test_training_budget_study_rules.py` checks it.
3. **Cadence worst case** (owner, same conversation): 256 miners, one
   submission each per 72-minute tempo.

**Unchanged.**
- R1-R8 and their recorded digest.
- The study stays off-chain development evidence: no live hidden batches, exam
  rule, chain transaction, miner submission or payout.
- The Battery sheet is still not in the repository; nothing that needs its
  values runs before it is supplied. The sheet now also sets the generation
  ceiling, target utilization, GPU ceiling, expected participation and
  minimum panel size.
- A change to a Challenge's TRAIN size or registry ranges is a pull request
  opened only after the owner's decision on the study result.
