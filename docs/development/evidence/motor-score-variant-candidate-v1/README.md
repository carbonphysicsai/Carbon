# Motor reciprocal-score candidate — public DEVELOPMENT measurement

CHALLENGE-MOTOR-06 proposes an unregistered `[0,1]` transform of Motor's
unchanged public PRACTICE rule. This is not validator/mainnet scoring, a
promotion result or a three-leg Score Pack. Only digest-pinned public
TRAIN/PRACTICE/calibration material was read; the 30 PRACTICE cases are fixed
and adaptively visible. No new GetDP, hidden batch, fresh confirmation, pod
run or paid reference execution was performed.

The proposed formula is `u(e) = 1 / (1 + e / 0.17)` for the existing complete,
gate-eligible raw mean TRAIN-normalized error. The `0.17` scale is rounded
from the learned public PRACTICE baseline `0.17300702981329621`, putting that
scaffold near `0.5`. It is a DEVELOPMENT calibration proposal, not an
approved production threshold.

| Public baseline | Existing raw error (lower better) | Candidate score (higher better) |
|---|---:|---:|
| Learned kernel-ridge scaffold | 0.17300702981329621 | 0.49561666445300995 |
| Closed-form baseline | 0.5002085857247547 | 0.2536523757244385 |

Candidate digest: `sha256:da5d35985aad65f1db9564f213c7260a41e2d2b4d5d566a17cbcd54b7a93f741`.
It binds the public material and normalized Motor exam/candidate source bytes.
The two scores are arithmetic transforms of registered public summaries, not
new independent evaluations. The ranking is exactly unchanged; a monotone
transform offers no new decision-value alignment or scientific resolution.

Reproduce from the repository root in the pinned canonical environment:

```bash
./scripts/dev/canonical.sh python -m carbon.motor.score_variant --root .
```

The separate preregistered [SR-M1 Motor score-candidate study](../motor-score-candidates-v1/README.md)
examined 16 related DEVELOPMENT members. Its phase-invariant A2 candidate
had Kendall τ-b `0.409` versus frozen F0's `0.369`, with paired case-bootstrap
τ-difference interval `[0.002, 0.153]`; **A2's top-three overlap with
decision value was zero**. Those members and controls are not independent or
fresh confirmation. This reciprocal F0 transform leaves F0's ranking and
divergences untouched. The study does not justify silently adopting A2 or
claiming the new `[0,1]` scale improves decisions.

Complete usable evidence is required before a positive candidate score. A
confirmed mandatory prediction-gate failure is noncompensable. Missing or
invalid reference, infrastructure failure, or incomplete coverage gives no
numeric score; known gate failures remain visible even alongside unavailable
cases. Every result is `official_eligible: false` and `promotable: false`.

## Pending authority

| Decision | Recommended next step | Owner | Required before |
|---|---|---|---|
| Adopt the reciprocal `0.17` scale or another measured transform | Compare preregistered candidate profiles on a broader DEVELOPMENT panel and measure score spacing and decision-value errors; do not adopt from two public baselines | Motor science owner | Prospective `[0,1]` registry/publication |
| Replace F0 with A2 or another score-bearing rule | Treat SR-M1 as a hypothesis only; include top-k decision value and false-safe outcomes in a frozen future comparison | Motor science owner | Rule replacement |
| Soft-physics metric for a 45/30/25 Score Pack | `HUMAN_INPUT`; torque-curve output alone is not a field or Maxwell residual | Motor science owner | Numeric full Score Pack comparison |
| Fresh paired promotion and P/Q/w | Separate Motor ticket, common independently held cases, reference/infra failure typing and an owner-approved comparison rule | Motor science owner and operator | Winner eligibility or weights |

No protected EVAL/STRESS condition, seed or label is committed here. A future
hidden confirmation must stay operator-side and be used only after the
candidate comparison and analysis are preregistered on DEVELOPMENT evidence.
