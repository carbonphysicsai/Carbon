## 2026-10-11 — OWNER-BATTERY-V3-FINALS-01: how the registered score is used — accuracy final plus the gate, and v2's important-region guard kept

**Authority.** The owner, 2026-10-11, directly in the Carbon Validator session.
Two questions were asked while building VALIDATOR-26.

1. Asked:
   > Under the registered score (A-Q with the G-FEAS gate), how should a
   > final decide whether the challenger beats the incumbent? A-Q has no
   > per-case breakdown, and finalist batches carry no quiz today.

   the owner chose **"Accuracy final + gate"**, whose description read:
   > Nomination uses the registered A-Q score (q measured on the screening
   > windows' quizzes). The final keeps v2's paired per-case bootstrap on
   > accuracy on the fresh finalist batch, and the challenger must also pass
   > the G-FEAS gate there. Buildable now: no producer change. Q3 counts at
   > nomination, not in the final.
2. Asked:
   > v2's nomination also refuses a challenger whose important-region cases
   > regress beyond the margin (important_score). Keep that check under v3's
   > nomination?

   the owner chose **"Keep it"**, whose description read:
   > v3 nominates only if A-Q improves beyond the margin, the G-FEAS gate
   > passes, and the important-region accuracy does not regress, as in v2. A
   > guard that already protects the frontier stays.

**Applies** OWNER-BATTERY-SCORE-RULE-01. The gate's reading is "exceeds":
exactly 0.05 passes, as the owner confirmed for #972. That is registry v5's
`G-FEAS/A-Q>@0.05`.

**Decided:**
- **The term comes from the deployment.** A rule naming a registered score
  (`v3-bank-sched`) takes its term (`registry`, `registry_sha256`,
  `candidate`) from the deployment's configuration. The rule's digest binds
  the term, so a different registered candidate (the score proof's winner)
  enters as a new deployment configuration, with no code change.
- **Screening:**
  - the score is the candidate's own (`score_tuning`'s `member_legs`,
    `score_member`, `gate_verdict`), higher is better;
  - q is the Q3 decision regret on the active windows' design questions,
    pooled over them;
  - eligibility needs v2's gates and the candidate's gate.
- **Nomination:** the registered score beats the incumbent's by v2's margin,
  and the important-region guard holds.
- **Finals:** v2's paired accuracy comparison on the finalist batch, and the
  challenger must pass the candidate's gate there.
- **Failures:**
  - a missing score, missing design questions, or a reference failure is
    infrastructure (FAILED_INFRA, retried), never a miner penalty;
  - the candidate's own failure on the questions makes it ineligible.

**Not decided here:** security acceptance (the paid path changes), and any
mainnet value.
