# Graphite run 5: battery Q1 score-to-value, v1

This is the first Q1 test on real Graphite constructions. Does Graphite's practice score rank its battery constructions by decision quality?

**Authority:** the Test Lead's approval of 2026-10-05, under OWNER-GRAPHITE-TEST-WAVE-01. CPU only on the operator host, no spend.

**Status:** DEVELOPMENT evidence on **EV4 development conditions (previously used)**. There is no confirmation claim; confirmation comes later on graphite-confirmation-v1, after the panel and analysis freeze. EV5's conditions, plan and sealed batch, and graphite-confirmation-v1, were never read.

## What was run

- **Panel `graphite-run5`.** Graphite phase-3 run 5 (`graphite-d90a8ccfd603cf6a`, REF fa1cba64).
  - Members: its baseline MLP and 8 scored DeepONet proposals.
  - Each recipe is rebuilt by Carbon on CPU from its pinned strategy. All 9 recipe digests equal Graphite's.
  - Each is rebuilt at its scored seed plus two declared extra seeds: 27 rebuilds in all.
  - No pod weights were used.
- **Score and decision come from the same artifact.** Each rebuild is scored on the 200 public PRACTICE cases with battery rule v2's practice scoring (`practice-summaries.json`). The same trained state predicts EV4's decision inputs.
  - The CPU practice ranks equal the pod's exactly (rank drift 0).
- **Decisions.** The EV4 charge-protocol contract (`graphite-run5-charge-protocol-selection.v1.json`: EV4 with only identity changed). References come from EV4's committed reference grid, after checking it against EV4's `references.sha256`. No new solves.
- **Identity aliasing** (`aliasing.json`):
  - `p-fa70c075f903` and `p-69268f1b74ec` differ only by `capacity_fade_head: true`. Rebuilt at the same seed, they give **byte-identical predictions**, so they are one recipe (n = 8).
  - `p-1d4aaff5d292` and `p-4fd7fb870d2b` are distinct (`basis_functions` 20 vs 30).
- **Prediction bundles** (130 MB) stay on the operator host and are listed in `predictions.sha256`.

**Reproduce:** run `python -m scripts.dev.battery.graphite_run5_alignment` with, in order, `predict`, `alias-check`, `analyse` and `followup`, each with `--out DIR`. `predict` takes about 25 minutes of CPU; the other steps take minutes.

## Findings

1. **Anti-alignment.** On the common resolved mask:
   - one seed (n = 8): Kendall τ-b **−0.47**, Spearman ρ −0.54;
   - all 27 rebuilds: τ −0.11, inside the seed-panel band of [−0.87, +0.26].

   Top-1 by score is the bundled winner `p-1d4aaff5d292`. Top-1 by decision is the **baseline MLP**.
2. **A shared unsafe decision.** In scenario D-T24-S0.12, **23 of 24 DeepONet rebuilds** select `c1=2, c2=1`, which the reference shows **infeasible**; the best feasible is `c1=1.75, c2=1`. **No baseline rebuild does.** EV4-native development decision loss is 0.001 for the baseline against 1.1–2.5 for the DeepONets.
3. **Near-limit false acceptance.** The bundled winner has the worst rate, **9.5%** (plating), against the baseline's 1.5%.
4. **Seed-luck promotion.** The aliased pair's pod scores, 0.05938 and 0.05755, differ only by seed, yet Graphite counted the step as an improvement. Recipe-level practice spread across seeds reaches 0.029. Rule v2's paired comparison bootstraps over cases, not seeds.
   - Across seeds, the bundled recipe still beats the baseline on practice (0.0562–0.0610 against 0.0740–0.0766).
   - Its *decisions* are worse.
5. **Battery's planned defences would not have caught the winner** (`defences.json`).
   - The near-limit optimism gate (cutoff 2.0 bands) **passes** the bundled winner, at 1.02 bands. Only two seeds of the regression recipe fail it.
   - Under the SR-2 candidate rule `sr2-a0-r0.3-g0.6-m0.1`, τ is −0.18 (one seed) and −0.16 (all), still negative. SR-2's top-1 is `p-4fd7fb870d2b`, another DeepONet that makes the unsafe D-T24 choice.
   - This is evidence for EV5's question, not a substitute for EV5.

## Conditions

`conditions.json` is a `carbon.admission-conditions.v1` report with four `SCORE_VALUE_DIVERGENCE` conditions: anti-alignment, shared infeasible decision, near-limit false acceptance and seed-luck promotion.
- Each is bound by SHA-256 to the committed evidence files.
- The campaign controller's operator records them with `CampaignController.consume_conditions`. This study never writes to a campaign store.
- Under W2 (GRAPHITE-CONDITIONAL-EXPLORATION-01), findings block LOCK, not exploration.

## Coverage: the common resolved mask is 6 of 12 scenarios

Six development scenarios are excluded because some member's selection lands on a reference candidate the contract cannot resolve. Reference failure is never a candidate penalty.

| Scenario | UNRESOLVED (all on plating, within the contract band) | REFERENCE_SOLVER_FAILED |
| --- | --- | --- |
| D-T14-S0.12 | 2 | 0 |
| D-T14-S0.48 | 2 | 0 |
| D-T24-S0.48 | 6 | 0 |
| D-T34-S0.33 | 3 | 0 |
| D-T5-S0.33 | 1 | 0 |
| D-T5-S0.48 | 1 | 5 (c1 = 2 with c2 ∈ {0.2, 0.4, 0.6, 0.8, 1.0}) |

Every candidate is inside EV4's grid. None is missing.

**What closing them would take:**
- **Re-solving the 5 failures** costs about 6 core-minutes; a standard solve is about 66 s on one core. All 5 failed with the same `EmptySolution` extraction error, so they would very likely fail again with the same settings.
- **Refining the 15 UNRESOLVED** (40-point mesh, tighter tolerances) costs about 1–3 core-hours on the operator host, which is under 20 minutes of wall time with 8–12 workers. **It would not change any status under current code:**
  - the bands are fixed in the contract;
  - refined records are dropped on import and by the scoring set.

  Closing the mask therefore needs a decision on refined references, not more compute.

Nothing was run for coverage.
