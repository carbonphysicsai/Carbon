# OPT-07: public EV4 score-leg audit

**Status: partial DEVELOPMENT evidence.** [The machine-readable audit](score-leg-audit-public-v1.json) uses the committed public synthetic EV4 results at SHA-256 `3bd9b954f4bace5f0299b6cbe9301e27407cb846dd51e5793bd5b5f6f33b0371`. No reference solver, model rebuild, sealed tuning directory or hidden material was used. This is the six-question common resolved **development** mask, 98 primary real members, and the registered controls as ranking probes. All real members are Level 0, so “pooled” equals L0; L1–L4 are not measurable here. These historical EV4 aggregates are not the later `ev4-dev-proof-v1` panel's sealed selection or confirmation results.

The script reuses `score_tuning.decision_values` for the common mask, `ratios.legs` for the recoverable score legs, and `score_proof` for Kendall τ-b, crossed recipe × question bootstrap and the SCORE-CEILING-01 estimator. The recipe bootstrap keeps a recipe's seeds together; the score side is fixed. The 500-draw 95% intervals are **descriptive**. A missing raw measure for any primary member withholds that pool's τ; it never silently changes the comparison population. Positive τ means the measure ranks lower decision loss higher (rates/errors are reversed first).

| Measure | L0 / pooled τ-b | Descriptive 95% interval | Registered known-bad in its top half | Registered adversarial in its top half |
| --- | ---: | ---: | --- | --- |
| `a` accuracy | 0.188 | [−0.091, 0.466] | boundary optimist, localized sign error | 2 |
| `r` important-region accuracy | 0.183 | [−0.095, 0.469] | localized sign error | 2 |
| `g` decision agreement | 0.017 | [−0.203, 0.336] | none | 1 |
| Selected infeasible share (lower is better) | 0.723 | [−0.046, 0.913] | none | 2 |
| Missed opportunity share (lower is better) | 0.071 | [−0.147, 0.297] | both | none |

On that common mask, **10.54%** of primary member × question outcomes are `SELECTED_INFEASIBLE`, and **0.34%** are `MISSED_OPPORTUNITY`. The SCORE-CEILING-01 estimator uses six informative questions and gives τ ceiling **0.041**, descriptive question-bootstrap interval **[0.000, 0.451]**. This is a noisy model-based reliability estimate, not a hard upper bound on an observed τ. Its wide interval is the useful result: six questions cannot support a precise ceiling estimate here.

**Unmeasured:** `p`, `m`, `n`, and `q` have no committed member-level inputs in this result. The `feasibility`, `plating_fa`, `envelope`, and `near` gate measures are absent. `error` is withheld on the full primary pool because at least one member lacks a valid eligible error; a complete-population comparison may not drop it. No Level 1–4 member has both a public EV4 value and score legs. The requested `score_proof_postmortem` implementation is not on main; this audit reuses the available `score_proof` and `score_tuning` functions and does not recreate sealed postmortem logic. Filling the gaps requires a separately registered, genuinely public member-level leg/gate export and matching public decision outcomes. **No threshold, score version, gate or adoption decision follows from this audit.**

Reproduce with `python -m scripts.dev.battery.score_leg_audit_public`; it reads only the committed EV4 aggregate result and member-role manifest and writes the JSON beside this page. The output records the source digest. Toy tests assert deterministic output, a common mask, refusal of non-public evidence, and explicit missing-measure behavior.
