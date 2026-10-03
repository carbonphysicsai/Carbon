# Near-limit optimism admissibility gate (2026-10-03)

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
- `THRESHOLD_BANDS = 2.0` (OWNER-GATE-CUTOFF-01). The SciML/technical lead
  deferred the cutoff to the lead session, and the owner approved it. It is a
  provisional DEVELOPMENT value, confirmed once in EV5.
- Applies to value-study results only. Putting it into the testnet rule is
  its own approval.

**At the cutoff** (`at_cutoff` in `optimism.json`):

| Panel | Real members failed | Mean verification loss: failed vs passed |
|---|---|---|
| EV2 | 2 of 14 | 1.375 vs 0.344 |
| EV4 | 20 of 99 | 1.684 vs 0.512 |

The boundary optimist fails on both panels. Oracle, conservative and
rank-preserving delay pass. The localized sign error also passes; this gate
does not catch it (see below).

**Why 2.0.**
- It is a round, interpretable value: the model overstates its margins near
  the limits by twice the contract's own uncertainty band, on average.
- It is not fitted to the boundary optimist's 2.41, and it still fails that
  control.
- It fails fewer than half the real members on both panels, and the ones it
  fails decide about 3-4x worse.

**The optimism distribution** (`optimism.json`, regenerate with
`python -m carbon.battery.value.admissibility --out <dir>`):

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
