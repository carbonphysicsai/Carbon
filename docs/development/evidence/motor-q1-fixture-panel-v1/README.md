# Motor Q1 fixture panel, v1

Does the motor score rank models by the quality of the design decisions they lead to? This is TRACK-B-HARNESS-01's Q1 test on motor, approved by the Test Lead on 2026-10-05.

Reproduce with `python -m scripts.dev.motor.q1_panel --out result.json`. It runs in seconds and uses public data plus the counted replay; nothing is solved or spent. `tests/cpu/test_motor_q1_panel.py` recomputes the whole result and compares it with `result.json`.

## Members

| Member | Kind | Construction |
| --- | --- | --- |
| `analytic-v1` | registered baseline | textbook surface-PM model |
| `learned-krr-v1` | registered baseline | KRR on 150 public TRAIN cases |
| `flat` | control | KRR's mean torque held constant (zero ripple) |
| `phase-shifted` | control | KRR curve rolled by a quarter period: same mean and peak-to-peak |
| `saturation-blind` | control | KRR on the 100 TRAIN cases at ≤ 10 A/mm², linear in current above that |

## How it is measured

**Score.** All five members are scored on the same source: the 30 public PRACTICE cases, with the registered TRAIN scales.
- The score is mean normalised error, so lower is better.
- Precheck: textbook and KRR reproduce their registered practice scores exactly.
- The private scores (textbook 0.463, KRR 0.214) are descriptive only and are not in the ranking.

**Decision.** Track B Q1 on the counted GetDP replay (study V2): fixed grid, 48 queries, with one-time costs excluded.

## Result

| Member | Practice score | Selection | Reference outcome | Exact regret |
| --- | --- | --- | --- | --- |
| learned-krr-v1 | 0.173 | d06 | feasible | 0.0192 |
| saturation-blind | 0.248 | d03 | **infeasible** (at the representative conditions) | n/a |
| flat | 0.417 | d01 | **infeasible**; TIE_DETERMINED (all 8 tie) | n/a |
| analytic-v1 | 0.500 | d01 | **infeasible**; TIE_DETERMINED (study rule picks d07, also infeasible) | n/a |
| phase-shifted | **0.583** | d06 | feasible | 0.0192 |

**Statistics.** Kendall τ-b = 0.0 and Spearman ρ = 0.0. These are descriptive (n = 5, deterministic members), with no band claim. Top-2 by score is {KRR, saturation-blind}; top-2 by decision is {KRR, phase-shifted}.

**SCORE_VALUE_DIVERGENCE** fires for analytic-v1, flat and saturation-blind. Each scores better than phase-shifted but makes an unsafe decision, while phase-shifted decides exactly as well as KRR.

**What the panel shows:**
- The motor score penalises decision-irrelevant phase error heavily: phase-shifted gets the worst score, yet makes KRR's decision.
- It under-penalises the errors that cause unsafe decisions:
  - hiding ripple (flat, textbook);
  - ignoring saturation (saturation-blind).

This is DEVELOPMENT fixture evidence on one registered finite decision. It is not a population claim, and it changes no scoring rule. Real Graphite constructions plus seeds are needed before any rule change is proposed.
