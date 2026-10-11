# SCORE-PROOF-DESIGN-01 — owner summary

**Research proposal, 2026-10-10. No experiment run; no score, gate, reward or qualification changed.**

A score needs independent decision evidence before Carbon can claim it prefers useful models. The proposed proof pairs each rule's ranking with reference-verified decisions on separate cases, then reports rank agreement, deployment regret and safety outcomes together. A high correlation cannot excuse a false-feasible winner.

The [statistics design](STATISTICAL_DESIGN.md) gives the Test Engineer the estimands, recipe-and-question bootstrap, paired comparisons, control tests, fold plan and adversarial test. It pins the actual [rescore route](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/scripts/dev/battery/tuning_rescore.py) and [registry-v4](https://github.com/carbonphysicsai/Carbon/blob/fb47eb5725338a7733f6074650e58271c355006b/docs/development/evidence/battery-score-tuning/registry-v4.json); it implements neither. There are **129 expanded rules**, hence **128** contrasts against CE if all are compared. The current seed band measures seed sensitivity, not a population confidence interval. The open Test Engineer [#1044](https://github.com/carbonphysicsai/Carbon/pull/1044) now uses v5 (130 rules); the design includes that integration seam.

For the owner's requested tau interval half-width **0.1** and rule difference **0.05**, illustrative planning at **95% confidence and 80% power (ASSUMPTION)** gives:

| Planning question | Low / base / high |
| --- | --- |
| One tau, fixed decision cases; independent recipes | 77 / 171 / 385 |
| Paired delta-tau, fixed cases; independent recipes | 140 / 559 / 1,396 |
| Paired delta-tau, both recipes and questions sampled | 280 / 1,117 / 2,791 recipes **and** 63 / 628 / 3,140 complete questions |

These are calculations under declared variance assumptions, **not sufficient-sample guarantees**. Ties, case effects and selection can increase requirements. The exact untied independence-null check is 175 recipes; it is not a general alternative-hypothesis formula. Counts per construction level, case stratum and illustrative quality band are in the design. Existing battery data cannot identify the required population variances without a public-data planning audit.

Recommend freezing one development-selected rule and CE for independent confirmation. If all rules receive confirmatory comparisons, control familywise error; do not select the best observed tau and reuse its interval as proof. Keep score-input and decision-outcome cases disjoint, including the Q3-derived q leg.

All acceptance thresholds remain **HUMAN_INPUT**. The evidence remains reference-relative and tied to the battery contract actually measured; EV4 does not supply the missing v3 SOC/cooling-map measurements. [Sources](SOURCES.md) and [machine-readable planning record](planning.json) accompany the proposal.
