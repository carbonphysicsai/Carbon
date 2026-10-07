# Challenge training budget study: decision rules R9-R11 (frozen)

Frozen by OWNER-TRAINING-BUDGET-STUDY-02 (2026-10-06) before any Phase G or H
rebuild. They extend R1-R8 (`DECISION_RULES.md`), which stay unchanged. The
analysis applies these as written. Changing one needs a new owner decision and
a note in the report. The SHA-256 of this file is recorded in
`.agent/decisions/2026-10-06-OWNER-TRAINING-BUDGET-STUDY-02.md`; a test checks
that it still matches.

9. **R9, data plateau.** Phase G trains the three best recipes on nested
   study TRAIN sets of increasing size. A recipe's data plateau is the smallest
   TRAIN size beyond which doubling the size improves its median score by less
   than half the Challenge's equivalence margin, the same resolution R2 uses.
   The recommended TRAIN size D is the largest data plateau among the three
   best recipes, rounded up to the next tested size. If D is the largest size
   the sheet's generation ceiling allows and the last doubling still improved
   by at least half the margin, the report says data binds and the owner
   chooses between more generation spend and a TRAIN size known to bind. If D
   differs from the Challenge's current TRAIN size, Phase B is repeated for the
   three best recipes at D and R2 and R3 are applied again, so L is proposed
   at D. The report states, at L and D, how many times training passes over
   each TRAIN case; it is reported, never a threshold.
10. **R10, screening budget.** Phase H scores the study panel at fractions of
    L (1/64, 1/32, 1/16, 1/8 and 1/4) and at L, on every Phase H seed. A
    screen at fraction f with k survivors is safe when, on every seed, every
    recipe that is a finalist at L under the Challenge's own finalist rule is
    among the k best at f. The screening budget s is the smallest safe f, with
    its k. If no tested fraction is safe, there is no screen: every submission
    is rebuilt at L, and R11 sizes capacity with t_s = 0 and k = N. A screen never
    decides a reward; it only orders which submissions are rebuilt at L.
11. **R11, cadence capacity.** The GPUs one validator needs to rebuild every
    submission are G = (N · (t_s + t_e) + k · (t_L + t_e)) / (τ · u), where N
    is submissions per tempo, τ the tempo, u the sheet's target utilization,
    t_s and t_L the measured rebuild times at s and at L (Phase E, alone on one
    GPU), and t_e the measured grading time per submission. Report G at the
    worst case the owner set (N = 256, every registered miner once per tempo;
    τ = 72 minutes) and at the sheet's expected participation. If G exceeds the
    sheet's GPU ceiling, the owner chooses between more GPUs, a lower
    submission rate and a higher submission fee. L and D are never lowered
    below their plateaus to fit capacity.
