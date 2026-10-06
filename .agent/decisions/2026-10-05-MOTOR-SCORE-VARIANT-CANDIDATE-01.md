## 2026-10-05 — MOTOR-SCORE-VARIANT-CANDIDATE-01

**Ticket:** CHALLENGE-MOTOR-06. **Status:** agent-recommended DEVELOPMENT
working candidate; scientific adoption `HUMAN_INPUT`.

**Problem.** Motor's existing provisional rule publishes a lower-is-better
raw error; OWNER-TESTNET-WEIGHTS-01 directs future Challenge scores toward
one. The neutral registry and hidden-batch path are other owners' work.

**Recommendation.** Propose the reciprocal unit-interval transform of the
unchanged Motor exam mean, scale `tau = 0.17`, rounded from the public learned
PRACTICE baseline `0.17300702981329621`. Implement it only as an unregistered
candidate in `carbon/motor/score_variant.py`, pinned to exact public material
and source bytes. Require complete evidence; never turn reference or infra
failure into zero or success. Do not publish through the validator or weights
before science-owner adoption.

**Why not A2 now.** SR-M1 found A2's phase-invariant ripple candidate barely
improved widened-panel Kendall τ over F0 (paired 95% difference interval
`[0.002, 0.153]`), but its top-three overlap with decision value was zero.
The 16 members are related and adaptively constructed. This does not establish
that A2 is the right replacement. Transforming F0 is a format proposal, not a
decision-value fix; a later preregistered comparison can study A2 or a new
candidate before fresh confirmation.

**Alternatives.** Linear rescaling requires clipping and can escape `[0,1]`;
a sigmoid introduces another unapproved sharpness value. Making A2 or a
three-leg 45/30/25 pack authoritative would overread DEVELOPMENT evidence and
invent an absent soft-physics measurement.

**Boundaries and reversibility.** No shared/miner-facing interface changes.
The Motor science owner controls transform adoption, soft-physics estimands,
fresh-case comparison and any population/weighting. Carbon Validator controls
registry and protected evaluation. Deleting the unused candidate reverses
this ticket; a later adopted variant needs a new exact identity and cannot
rescore historical evidence silently. To supersede, update this record,
candidate code, tests and measurement note.
