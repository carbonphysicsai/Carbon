# SR-B1: battery score candidates, v1

This is **descriptive DEVELOPMENT evidence on EV4's development conditions (previously used)**.
- **Nothing is adopted.** Adopting a rule stays with the science owner.
- **EV5 is untouched.** Frozen modules are imported, never edited.
- Anything that survives is a candidate for a future confirmation under a new EV version.

**Registration.** The candidates, panels and statistics were committed and pushed in `.agent/tickets/SR-B1_battery_score_candidates.md` (commit `7c355f2f`, 12:13Z) before anything was computed.

**Reproduce.**
1. Run `python -m scripts.dev.battery.srb1_ev4_rebuild --out DIR` to rebuild EV4's panel on CPU, about 40 minutes.
2. Run `python -m scripts.dev.battery.srb1 --run5 RUN5_DIR --ev4 DIR --out result.json`, about 15 minutes.

The prediction bundles (about 650 MB) stay on the operator host.

## Panels

- **graphite-run5:** 8 recipes and 27 CPU rebuilds (#609).
- **ev4:** EV4's 100 members (80 recipes) plus its 5 synthetic controls, so 105 members and 85 recipes.
  - Every member was **rebuilt on the operator host's CPU** against EV4's checksum-verified reference grid. EV4's A40 bundles are not retained on any host.
  - CPU rebuilds are not bit-identical to EV4's, so these numbers are not EV4's committed results and do not reinterpret them.
- **Both panels** score decision value as the mean development decision loss on the panel's common resolved mask (6 of 12 scenarios on each).
- **Seed bands:** graphite-run5 uses all 13,122 one-seed-per-recipe panels. ev4 has 786,432 possible panels, so it uses the registered 2000 samples (seed 0).

## Results

See `result.json` for every candidate, panel, interval and divergence count.

**EV4 panel (105 members).**
- **No candidate beats the deciding rule beyond the band.**
  - CE has τ-b 0.22 (band 0.18–0.26).
  - Every paired Δτ against CE either includes 0 or is negative.
- **CE itself ranks better than the SR-2 candidate here:** Δτ(CE − SR2) is [0.002, 0.026]. P2 and S-P1 edge past SR-2 by about the same amount, but not past CE.
- **The tighter gate G1 (1.0 band) significantly hurts ranking.** Its Δτ against CE is about −0.05 to −0.12, with intervals excluding 0, because it fails many good deciders.
- The decision-envelope gate G2 is neutral.

**Graphite run 5 (8 recipes).**
- **No candidate shows progress over CE or SR-2.** Every paired interval includes 0.
- **No candidate both demotes the bundled winner and spares the baseline** (`catch` in `result.json`).
  - **G1 (1.0 band)** fails 23 of 27 rebuilds. That includes the bundled winner, the baseline (the best decider) and 19 of the 23 D-T24-S0.12 infeasible pickers.
  - **G2 (decision envelope)** fails 6 of 27: 6 infeasible pickers, but neither the winner nor the baseline.
  - Ungated, the winner ranks 1st of 8 under CE, S-P1 and S-SR2 (3rd under S-CE).

## Reading

- **None of the registered fixes for #609's failure mode works on these panels.** That covers proximity-weighted optimism, seed-mean stability, and a tighter or envelope-restricted gate.
- The run-5 failure is a shared, confidently wrong decision in one high-C-rate, near-limit plating scenario. Near-limit optimism measured on the scoring set does not separate it from the baseline.
- That points to the score's population and weighting, not its gate. The decision-sensitivity diagnosis (next) tests this directly.

## Method notes

- **Gate failures rank last.** A gate FAIL ranks below every passing member (inadmissible). `admissibility.gated`'s literal 0.0 would rank a failure first under CE's negative scores (see #617).
- **Divergence count.** It is computed directly: X diverges when some Y has value(Y) + band < value(X) and score(X) ≥ score(Y), using the recipe-level value band. `score_value.alignment`'s exhaustive τ band is intractable on EV4's recipe product, and the registered sampled seed band replaces it.
- **Limits.** Members are not independent. The panels were seen before registration. EV4's panel is a CPU rebuild. **Nothing is promoted.**
