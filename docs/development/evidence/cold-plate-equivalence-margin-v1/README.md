# Cooling practice equivalence margin, v1

**For testing only:**
- OWNER-GRAPHITE-TEST-WAVE-06 §1.
- The method is the Test Lead's delegated decision of 2026-10-05.

The committed value is `equivalence_margin_rel` in `result.json`, which is **0.1316**. Codex wires it into cooling's compare, alongside battery's unit-free settings: n_min 30, n_boot 4000, alpha 0.05, important_min 10.

Reproduce with:

    python -m scripts.dev.cold_plate.equivalence_margin --out result.json

This is CPU-only work on public data: TRAIN has 400 OK cases and PRACTICE has 100. A run takes about 25 minutes. `result.json` binds the input files by SHA-256.

## Method

- **Battery's documented rule (OD-2):** 2 × the largest seed-to-seed relative SD (ddof 1) of the large-sample score. Battery's recipes were stochastic MLPs.
- **Cooling's reference construction** is the registered KRR (length 8, ridge 1e-6). It is deterministic and has no seed. Applied literally, the rule gives **0**, and that result is recorded. A zero margin would count every difference as real.
- **Primary measurement:**
  - Seed s draws a bootstrap of public TRAIN, with replacement, at the full n = 400.
  - KRR is refitted on that sample and scored on all 100 PRACTICE cases, with the registered TRAIN scales fixed.
  - 30 seeds. The margin is 2 × SD / mean of those scores, which is battery's definition.
- **Precheck:** a full-TRAIN fit must reproduce the registered practice score exactly. It does: 0.0987621.
- **Stochastic recipes:** only `kernel_ridge` is a rebuildable cooling family, so no OD-2 analogue applies. The bootstrap value is used, and a test fails if a stochastic family is ever registered.

## Results

| Seed definition | Mean practice score | SD | Relative margin (2 × SD / mean) |
| --- | --- | --- | --- |
| Literal OD-2 (KRR has no seed) | 0.09876 | 0 | **0** |
| **Bootstrap, full n, with replacement (primary)** | 0.1477 | 0.00972 | **0.1316** |
| Subsample 0.8, without replacement | 0.1168 | 0.00625 | 0.1070 |
| Subsample 0.9, without replacement | 0.1069 | 0.00345 | 0.0645 |
| Subsample 0.95, without replacement | 0.1026 | 0.00294 | 0.0574 |

For comparison, battery's OD-2 margin is 0.0570.

## Read before use

- **The bootstrap degrades the fit.** Resampling with replacement leaves about 63% unique cases, and KRR on duplicated points scores about 50% worse: a mean of 0.148, against 0.099 for the full fit. Battery's rule divides by the mean of the seed scores, which gives 0.1316. The same absolute spread relative to the full-fit score would be **0.197**. The committed value follows battery's definition. Whether to use the full-fit denominator is a Test Lead call.
- **Subsamples understate the variance**, as the Test Lead expected. The margin falls from 0.107 to 0.057 as the overlap rises from 80% to 95%.
- **The important-region score varies more.** Its relative SD is 0.105 under the bootstrap.
- **Scope.** These are DEVELOPMENT testing values only: not a production threshold, not qualification, and not used for any payment.
