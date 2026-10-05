# Cooling reciprocal-score candidate — public DEVELOPMENT measurement

This is an unregistered proposal under CHALLENGE-AI-COOLING-11, **not** a
change to Cooling's frozen exam or a validator/mainnet score. It uses only
the digest-pinned public TRAIN/PRACTICE/calibration material for
`chip-cold-plate` v1.0. The 100 PRACTICE cases are fixed and adaptively
visible. No new CFD, hidden batch, sealed confirmation case, or paid reference
execution was run.

The proposed formula is `u(e) = 1 / (1 + e / 0.1)` for the existing complete,
gate-eligible raw mean TRAIN-normalized error `e`. The proposed `0.1` scale
is rounded from the learned scaffold's public PRACTICE mean `0.09876205614850035`,
so that scaffold sits near `0.5` on the unit interval. This is a transparent
DEVELOPMENT calibration proposal, not an approved scientific threshold.

| Public baseline | Existing raw error (lower better) | Proposed candidate (higher better) |
|---|---:|---:|
| Learned kernel-ridge scaffold | 0.09876205614850035 | 0.5031141352516869 |
| Closed-form baseline | 0.12005148015232563 | 0.454439115477784 |

Candidate digest: `sha256:57efaa04f4748aabbcd13d9f84ca0103007ab68161d9c40068d126ded1d8e569`.
Its identity also binds the normalized source bytes of the existing Cooling
exam and this candidate transform. A code change therefore changes the
candidate digest; it cannot silently reinterpret this measurement.
These scores are arithmetic transforms of the already recorded public
baselines, not new independent evaluations. The ordering is unchanged by
construction: the reciprocal is strictly decreasing in nonnegative raw
error. The displayed separation is about `0.048675`; two adaptively visible
baselines do not establish a useful scoring resolution, engineering decision
alignment, a population confidence interval, or an optimal scale.

Reproduce from the repository root in the pinned canonical environment:

```bash
./scripts/dev/canonical.sh python -m carbon.cold_plate.score_variant --root .
```

The result is nonpromotable even when numerically scored. Complete usable
evidence is required for a positive candidate score. Mandatory prediction
gates remain binary and noncompensable; missing/invalid reference or
infrastructure evidence yields no numeric score. A confirmed gate failure is
recorded even when another case is unavailable. Current Cooling practice and
validator paths continue publishing their existing lower-is-better raw error.

## Pending authority and next measurement

| Decision | Proposed policy | Owner | Required before |
|---|---|---|---|
| Adopt the `0.1` reciprocal scale or a different measured transform | Defer adoption until a broader, preregistered DEVELOPMENT construction panel is measured; this two-baseline check only verifies shape and ordering | Cooling science owner | Registering a published `[0,1]` variant through VALIDATOR-09 |
| Soft-physics estimand for a three-leg 45/30/25 Score Pack | `HUMAN_INPUT`; do not reuse hard-gate margin or derived energy-balance arithmetic as soft evidence | Cooling science owner | Any numeric full Score Pack comparison |
| Fresh paired promotion comparison and sampling/weighting | Separate Cooling ticket; require independently held common cases and typed unresolved/reference outcomes | Cooling science owner and operator | Winner eligibility or weights |

No protected EVAL/STRESS conditions, labels or seeds are included here. Any
future hidden confirmation remains operator-side; the candidate must be
preregistered on DEVELOPMENT data before that evidence is touched.
