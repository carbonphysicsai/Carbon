# Near-limit optimism admissibility gate: built, inactive (2026-10-03)

**Authority.** TRACK-B-STUCK-01 review outcome, 2026-10-03: the owner
reported the SciML/technical lead's approval and approved the
recommendation. Ranking stays on the deciding rule. A separate admissibility
gate is added for models that overstate safety margins near the limits.

**Code.** `carbon/battery/value/admissibility.py`.
- `near_optimism` measures SR-3's quantity: mean optimism in decision-band
  units over the published important region (`domain.is_important`).
- `verdict` / `gated`: INACTIVE while `THRESHOLD_BANDS is None`; once set, a
  model at or above it FAILs and scores 0 under every rule (no compensation,
  constitution §7.3). An unmeasured model fails a set gate.
- `THRESHOLD_BANDS = None` — **HUMAN_INPUT**, owned by the SciML/technical
  lead. No cutoff was given, so no score changes anywhere.
- Applies to value-study results only. Putting it into the testnet rule is
  its own approval.

**Evidence for setting the cutoff** (`optimism.json`, regenerate with
`python -m carbon.battery.value.admissibility --out <dir>`). Descriptive only.

| Panel | Real eligible members | Optimism min / median / max (bands) | At or above the boundary optimist (2.41) | Mean verification loss: at/above vs below |
|---|---|---|---|---|
| EV2 | 14 | 0.585 / 0.730 / 4.159 | 2 | 1.375 vs 0.344 |
| EV4 | 99 | 0.537 / 1.045 / 5.880 | 13 | 2.046 vs 0.553 |

Constructed controls: oracle, conservative and rank-preserving delay are at
0.0; localized sign error is at 0.457, below every real member.

**What this shows and does not show.**
- A cutoff near the boundary optimist's level would exclude real members
  whose verification decision loss is about 4x the rest, on both panels.
- Mean near-limit optimism **cannot** catch a localized sign error: that
  control sits below every real model. A different measurement would be
  needed for that failure; this gate does not claim it.
- Panels are development evidence, not a population claim. Any cutoff should
  be confirmed once on fresh conditions (EV5) before it binds anything.

**Unchanged.** The deciding testnet rule; Track A at Level 0 remains
INCONCLUSIVE; no historical result is rescored.
