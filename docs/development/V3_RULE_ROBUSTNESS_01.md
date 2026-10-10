# Battery v3 scoring: synthetic adversarial stress test

**Development recommendation only.** The approved rule remains the exact
registry-v4 `G-FEAS/A-Q@0.05` candidate (SHA-256
`44795679e04b62627b8ad396631eae0de8b54e97429012dcc014a29792e4f814`).
`A-Q` is the geometric mean of screening accuracy `a` and
`q = 1/(1 + mean Q3 regret)`; the scoring-set G-FEAS gate decides eligibility.
This analysis runs `score_tuning.score_member` and `gate_verdict` on invented
leg rows. It uses no real predictions, solver, hidden bank, or production rule.

Reproduce with `python -m scripts.dev.battery.v3_rule_robustness`. All values
below are synthetic and dimensionless; score gains are **not** measured miner
gains or estimates of attack success probability.

| Constructed behavior | Raw score gain | Synthetic decision-loss change | What v3 observes |
| --- | ---: | ---: | --- |
| Concentrate the same total regret in one of four questions | 0 | 0 mean; maximum regret 0.25 → 1 | `q` uses the mean, so it does not price the tail. |
| Abstain unnecessarily on one feasible opportunity while improving screening accuracy | +0.0380 | +0.2000 | The missed opportunity raises mean regret, but the accuracy gain more than offsets it. Correct `NONE_FEASIBLE` abstention is a distinct, valuable behavior. |
| One false-feasible prediction among 21 reference-infeasible screening cases | 0 | +1.0000 in a constructed off-quiz buyer case | 1/21 = 0.04762 is below 0.05, so the gate passes. The toy holds quiz regret and accuracy fixed; this is a coverage/severity diagnostic, not proof that a real model can hold them fixed. |
| Trade higher screening accuracy for higher Q3 regret | +0.0269 | +0.4274 | `a` rises 0.64 → 0.95 while `q` falls 0.90 → 0.65; geometric A-Q ranks the higher-regret model above the baseline. |

The gate cannot be traded away by a high soft score once it fails. Missing
G-FEAS is also a failed gate in the current scorer. The test additionally
shows that **exactly** 1/20 = 0.05 fails, while 1/21 passes. The owner record
describes ineligibility when the rate *exceeds* 0.05; the shared
`admissibility.verdict` code uses `>=`. This wording/code seam needs Validator
and owner review before anyone interprets a case exactly at the cutoff. This
PR only records the behavior; it does not alter the registered rule or
historical outcomes.

## Prospective rule probes for Test Lead and owner

1. **Tail and abstention:** retain mean Q3 regret and separately report
   per-question tail regret and missed feasible opportunities. Test a
   pre-registered tail condition or conditional missed-opportunity cap only
   after measuring reference resolution and correct `NONE_FEASIBLE` coverage.
2. **Feasibility edge:** report the numerator and denominator for G-FEAS and
   the worst registered boundary stratum, with confidence bounds. Test a
   prospective stratified condition or more boundary coverage; changing the
   current 0.05 cutoff is owner-reserved. Off-grid accuracy probes remain
   necessary for lattice-aware behavior.
3. **Accuracy/regret trade-off:** compare the approved geometric A-Q with a
   prospective Q3 floor or decision-first ordering, evaluated on held-out
   member predictions. Any weight or floor needs separate registration and
   owner adoption.

The public run-5 alignment audit measured v2 practice τ = −0.473 on eight
one-seed members, but their v3 inputs are absent. The adopted rule's separate
sealed tuning study reported positive τ = 0.227 on its own population. Neither
result validates these synthetic attacks or answers whether v3 fixes the
run-5 inversion. Development screening and settled Q3 references, plus
independent held-out outcomes, are required before a change can be preferred.
