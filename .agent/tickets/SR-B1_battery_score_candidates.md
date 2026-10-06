# SR-B1 — battery score-candidate study (registered before computing)

**Status:** REGISTERED. These definitions are committed and pushed before any candidate is computed on any panel.

**Authority:** the Test Lead's assignment of 2026-10-05, under OWNER-GRAPHITE-TEST-WAVE-01. DEVELOPMENT evidence only. Adopting any rule stays with the science owner.
- **EV5 is never touched.** Its contract, conditions, plan, sealed batch and frozen modules are imported read-only where needed and never edited, and never run on EV5's conditions.
- Anything that survives is a candidate for a *future* battery confirmation under a new EV version.

**Motivation:** #609 (Graphite run 5).
- The practice score is anti-aligned with decisions.
- 23 of 24 DeepONet rebuilds pick a reference-infeasible protocol in D-T24-S0.12.
- The bundled winner has the worst near-limit false acceptance, yet passes the near-limit gate (2.0 bands), and the SR-2 candidate stays negative.

## Panels (both on EV4 DEVELOPMENT conditions, previously used)

1. **`graphite-run5`:** 9 recipes, with p-fa70c075f903 aliased to p-69268f1b74ec, so 8 recipes and 27 rebuilds. These are the committed CPU rebuilds from #609.
2. **`ev4`:** EV4's 100 members (80 recipes: 61 MLP, 12 DeepONet, 7 kNN, 1–3 seeds each), plus EV4's 5 synthetic controls.
   - EV4's original prediction bundles are not on any host, so every member is **rebuilt on the operator host's CPU** by `Experiment.panel` with `DirectBackend`. There is no spend.
   - CPU rebuilds are not bit-identical to EV4's A40 bundles. Every candidate is scored and decided on the same rebuilt artifacts. EV4's committed results are not reinterpreted.

**Decision value** for every member is the mean development decision loss on that panel's common resolved scenario mask. Reference failure is never a candidate penalty.

## Building blocks (per member, on the 1588-case scoring set unless stated)

- **Legs a, r, g:** `ratios.legs`, i.e. a = 1/(1+E), r = 1/(1+E_important), g = decision score.
- **Leg m:** SR-2's margin leg (`margins.margin_component`).
- **Leg p (new): proximity-weighted near-limit optimism.**
  - For each scoring case and each constraint (plating, thermal), take the true margin t and the predicted margin s in contract band units (`margins._margins`).
  - Optimism is o = max(0, s − t), so only optimism is charged.
  - The proximity weight is w = 1/(1 + |t|).
  - P = Σ w·o / Σ w, and p = 1/(1 + P).
- **Geometric-mean rule** with weights (w_a, w_r, w_g, w_m, w_p): exp(Σ w log leg) over positive weights. This is `margins.score`'s convention, extended to leg p.
- **Stability S(rule):** every member of a recipe gets the mean of that rule's scores over the recipe's seeds, so one lucky seed cannot win.
- **Gates.** A gated rule scores 0 when the gate FAILs.
  - **G1:** `admissibility.near_optimism` on `near.near_cases`, with cutoff **1.0** band instead of 2.0.
  - **G2:** the same optimism measure, restricted to near-limit scoring cases whose inputs lie inside the EV4 decision envelope (c1 ∈ [0.5, 2.0], c2 ∈ [0.2, 1.0], t_amb_c ∈ [5, 34], soc0 ∈ [0.12, 0.48]), with cutoff **1.0** band. No decision-case reference is used, so the gate never sees the evaluation set.

## Candidates (registered)

| Id | Rule |
| --- | --- |
| CE | baseline: `control-exam-v1` |
| SR2 | baseline: `sr2-a0-r0.3-g0.6-m0.1` |
| P1 | weights r 0.3, g 0.6, p 0.1 (SR-2 with m replaced by p) |
| P2 | weights r 0.3, g 0.4, p 0.3 |
| S-CE | S(CE) |
| S-SR2 | S(SR2) |
| S-P1 | S(P1) |
| P1+G1 | P1, gated by G1 |
| S-P1+G1 | S(P1), gated by G1 |
| S-P1+G2 | S(P1), gated by G2 |
| S-SR2+G1 | S(SR2), gated by G1 |
| CE+G1 | CE, gated by G1 |

No candidate will be added after the computation without a new registration recorded as such.

## Statistics and reporting (registered)

For each candidate and panel:
- **Correlation.** Kendall τ-b and Spearman ρ of the rule score (higher is better) against decision value (lower is better), on one-seed and all-seed views.
- **Seed band.** τ over one-seed-per-recipe panels. Use all of them when the product is at most 20,000, otherwise 2000 sampled panels (seed 0).
- **Paired Δτ** against CE and against SR2 over the same seed panels: the 2.5–97.5% interval. "Progress" is claimed only when the interval excludes 0.
- The SCORE_VALUE_DIVERGENCE count.
- **On `graphite-run5`:**
  - the bundled winner's (p-1d4aaff5d292, scored seed) rank and gate verdict;
  - for the D-T24-S0.12 infeasible pickers, how many are gated out and their mean rank.

Everything is descriptive. Members are not independent, and the panels were seen before this registration. **Nothing is promoted.**

## Scope

New modules only: `carbon/battery/value/score_candidates_b1.py`, a script, tests and evidence. No frozen or pinned file is edited, and EV5 is untouched.
