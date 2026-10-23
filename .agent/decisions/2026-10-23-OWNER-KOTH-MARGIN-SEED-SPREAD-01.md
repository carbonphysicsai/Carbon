# OWNER-KOTH-MARGIN-SEED-SPREAD-01: the KOTH takeover margin covers seed-to-seed spread, not only same-recipe rebuild noise

Date: 2026-10-23
Status: APPROVED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae). Offered A ("margin at least the measured seed-to-seed spread") or B ("several secret seeds, averaged"), the owner replied: "A".
Amends: the KOTH margin source (koth_rebuild_noise.json). KOTH otherwise stays frozen simple: best score wins by the margin, ties keep the king, and the first crown must beat Carbon's baseline.

## Decided

- Each Challenge's takeover margin is at least the larger of: (a) same-recipe rebuild noise; (b) the measured seed-to-seed score spread. Both are measured on the registered RTX 4090 class at the one registered recalibration, over the Carbon-tested entries.
- The official rebuild stays one reconstruction with Carbon's fixed public seed. No multi-seed averaging.
- The statistic used for "spread" (for example, the maximum or a high percentile over seeds) is the Validator's to define and record at recalibration. It is never invented and never chosen below the measured value.
- Until it is measured, the margin stays unset, so every takeover is UNAVAILABLE (fail closed).

## Why

- A miner pointed out that a margin built from rebuild noise alone lets near-identical variants keep the luckiest seed's sealed grade. A margin of at least the seed spread closes that, with no extra compute per submission. The per-miner submission cap and the submission fee (to be decided) add to it.
