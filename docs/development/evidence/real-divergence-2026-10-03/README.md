# Score-value divergence by who diverges (2026-10-03, prospective)

**Why.** TRACK-B-STUCK-01 found that the pre-registered divergence count
mixes constructed controls, models of one family ordering among themselves,
and real models of different families, so it cannot show a real-model gain.
The review approved reporting these separately. **Prospective only:** every
frozen study keeps its outcome; nothing is rescored or reinterpreted.

**Code.** `carbon/battery/value/real_divergence.py`. It classes each pair in
a SCORE_VALUE_DIVERGENCE condition (X scores at or above Y although Y
decides better by more than the loss band):
- `control`: X or Y is a constructed control;
- `within_family`: X and Y are real models of the same family (mlp, knn,
  deeponet);
- `across_families`: real models of different families.

A condition takes its worst pair (across, then within, then control). The
rule scores are the ones the studies define, recomputed from components
already committed (SR-2 margin, SR-3 near-limit). The classed totals equal
every study's committed counts; a test enforces this.

Regenerate: `python -m carbon.battery.value.real_divergence --out <dir>`.

## Verification split

| Rule | EV2 (14 real): across / within / control | EV4 (99 real): across / within / control |
|---|---|---|
| Deciding (`control-exam-v1`) | 1 / 0 / 2 | **1** / 4 / 2 |
| SR-1 candidate `sr-a0.5-r0.1-g0.4` | 1 / 0 / 2 | 1 / 4 / 2 |
| SR-2 candidate `sr2-a0-r0.3-g0.6-m0.1` | 1 / 0 / 2 | **5** / 3 / 2 |
| SR-3 candidate `sr3-a0-r0-g0.8-n0.2` | 1 / 0 / 2 | **6** / 2 / 2 |

## What it shows

1. **The deciding rule has one real across-family divergence on EV4
   verification:** `deeponet_t1500_w512_d3-s0` scores at or above three
   25%-TRAIN MLPs that decide better. The other six conditions are controls
   or within-family ties.
2. **The margin-aware candidates make real-model divergence worse, not
   better.** SR-2 and SR-3 trade the boundary-optimist condition for 4-5
   more across-family ones. Mostly these are 25%-TRAIN MLPs scoring above
   `deeponet_t1500_w256_d3-s0`. This supports the review's decision to keep
   the deciding rule for ranking.
3. **Under SR-2 and SR-3 the conservative control rises.** Its condition
   now covers 43 and 74 real members it scores at or above. Under the
   deciding rule its control condition does not appear on EV4 verification.
4. **The localized sign-error control scores at or above nearly every real
   member under every rule** (95-98 of 99 on EV4). It is a failure no rule
   here and no mean-optimism gate catches; recorded, not suppressed
   (OWNER-CHALLENGE-ADMISSION-01 §6.2). It needs its own measurement, which
   is a science decision.

**Recommendation for future studies (EV5 onward).** Pre-register
`across_families` on real members as the divergence criterion. Report the
other classes alongside it. Keep the existing count, for continuity.

**Class.** Public synthetic DEVELOPMENT evidence. The testnet rule is
unchanged.
