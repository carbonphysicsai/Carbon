# Challenge training budget study: decision rules R1-R8 (frozen)

Frozen by OWNER-TRAINING-BUDGET-STUDY-01 (2026-09-29) before any rebuild.
The analysis applies these as written. Changing one needs a new owner decision
and a note in the report. The SHA-256 of this file is recorded in
`.agent/DECISIONS.md`; a test checks that it still matches.

1. **R1, determinism gate.** Every same-seed pair must match in weight and
   prediction digests, including the largest recipe and the shared-GPU runs.
   Any mismatch stops the study before Phase B, and no limit is chosen. If a
   model family can't be made bit-identical even with deterministic XLA flags,
   the owner may approve a fallback for that family: identical exam decisions
   within a tolerance set by a qualified procedure.
2. **R2, plateau.** A recipe's plateau budget is the smallest calculated cost
   beyond which doubling the budget improves its median score by less than half
   the Challenge's equivalence margin. Smaller gains sit inside seed noise, and
   the exam could not resolve them anyway.
3. **R3, limit level.** The proposed limit L is twice the largest plateau
   budget among the three best recipes, rounded up. The costliest recipe
   allowed at L must meet the sheet's time target and memory ceiling. If twice
   the plateau breaks either, the owner chooses between a higher target and a
   limit known to bind.
4. **R4, ranking stability.** On the confirmation set, compare the best
   configuration at 4L with the best at L using the Challenge's own finalist
   rule. If 4L's best is an IMPROVEMENT, L binds on quality: double L and
   repeat once, then escalate to the owner. If the winning recipe changes
   between L and 4L without a significant difference, report it as a warning.
5. **R5, unit of the limit.** Adopt a compute-cost limit if F3 or F4 predicts
   rebuild time within 25% for at least 95% of Phase C and F rebuilds, and no
   rebuild takes more than 1.5 times its prediction; use the simpler formula
   when both pass. Otherwise keep separate caps on each cost-driving setting,
   each set from R3.
6. **R6, stress fixes.** A Phase F recipe that takes more than 1.5 times its
   prediction gets a factor for that setting in the formula and is re-run. If
   no factor fixes it, that setting keeps its own cap.
7. **R7, time safety net.** The rebuild time limit becomes three times the
   predicted time of the costliest allowed recipe, so a recipe inside the limit
   never reaches it.
8. **R8, load.** Report rebuilds per GPU-hour at L, alone and with 2 and 4
   sharing one GPU. The time target sets the worst case: at 5 minutes, one GPU
   carries at least 288 worst-case rebuilds a day.
