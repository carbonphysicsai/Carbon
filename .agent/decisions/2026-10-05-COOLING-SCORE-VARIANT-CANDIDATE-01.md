## 2026-10-05 — COOLING-SCORE-VARIANT-CANDIDATE-01

**Ticket:** CHALLENGE-AI-COOLING-11. **Status:** agent-recommended working
DEVELOPMENT candidate; scientific adoption `HUMAN_INPUT`.

**Problem.** Cooling's provisional exam publishes lower-is-better raw error,
while OWNER-TESTNET-WEIGHTS-01 directs future Challenge scores toward one.
The neutral registry is being built separately in VALIDATOR-09. A full
45/30/25 Score Pack cannot be evaluated because no approved soft-physics
measurement exists for these outputs.

**Recommendation.** Measure the reciprocal transform of the unchanged raw
exam mean with proposed scale `tau = 0.1`, rounded from the public learned
scaffold's registered PRACTICE error `0.09876205614850035`. Implement it as
an unregistered DEVELOPMENT-only candidate in `carbon/cold_plate/score_variant.py`.
Complete valid evidence is required before a positive candidate score;
mandatory gate failures remain inadmissible. Do not wire it into the
validator, Graphite, or weights until science-owner adoption and prospective
registration. Historical raw-error evidence retains its rule.

**Alternatives.** A linear rescale can leave the unit interval and requires
clipping. A sigmoid requires another unapproved sharpness parameter. Reusing
hard-gate margins as a soft physics leg would reward a different and possibly
less accurate model, so is rejected. The reciprocal is monotone and simple,
but cannot improve ranking or engineering decision alignment by itself.

**Affected boundaries.** Challenge-specific candidate code and public
measurement only; no shared or miner-facing interface. The owner controls
the scale's adoption, soft physics estimand, population/weights, and promotion
rule. Carbon Validator controls the neutral registry and protected evidence
path. Reversal is deletion of this unused candidate module; a future adopted
variant must receive a new exact identity, not reinterpret historical results.

**If changed:** supersede this record, update the Cooling candidate module,
tests, and public measurement. No existing official score needs migration.
