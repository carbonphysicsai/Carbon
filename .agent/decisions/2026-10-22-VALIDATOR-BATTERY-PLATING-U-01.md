# VALIDATOR-BATTERY-PLATING-U-01: Battery plating reference uncertainty U = 0.23 mV (mesh 160)

Date: 2026-10-22
Status: DECIDED by the Carbon Validator. U records are measured, not chosen, and are the Validator's to register (U records rule: round up, never below the measured band).
Scope: DEVELOPMENT reference quality for the sealed Battery exam's QA (`battery-dual-sealed-batch-8-v1`). This is not scientific qualification, and it makes no LIVE claim.
Record: `docs/development/evidence/battery-reference-uncertainty-20261022/battery-reference-uncertainty.json`, sha256 `4d2963889a95aafa75a222308184a0c6678197b06abf7a70b08ccbe4c78cc797`.

## Measured

Four public ev4 cases were solved at mesh 80 / 160 / 320 in the pinned truth image and overlay (rtol 1e-6, cycle 1, alone on the AX42 custody host). The run was the Test Lead's, from Data Collection's payload.

| Case | m160 (mV) | p | Roache e160 (V) | Source sha256 |
|---|---|---|---|---|
| ev4:D-0000:c1=0.75,c2=0.6:0 (probe-2) | 0.834 | 1.039 | 1.740e-4 | `3310a8302410bd68721add5f30469194e0888a9254fe9919a015db8aed337c23` |
| ev4:D-0067:c1=0.75,c2=1:0 | −0.611 | 0.994 | 2.215e-4 | `3fe55c4531630054cd5285a461ded97be0ae9b3726c54c969df9fd29fd71765f` |
| ev4:D-0121:c1=1.75,c2=1:0 | −0.733 | 1.045 | 2.275e-4 | `cc31dd940e1879d4cc466bfa49eafc845a74207572a1eebd975459bb3c46e568` |
| ev4:D-0091:c1=1.5,c2=0.8:0 | −0.588 | 0.993 | 1.901e-4 | `2ac5d9df0068b818835de1e127dd6782fe9c3ded8dcae44851dc359f0e575b32` |

- The panel summary is `u-panel.json`, sha256 `2c88e5f40412989276e53f1bf908ad760fa84fa87520066f7e68fbeae863b537`.
- Every case is monotone, with p ≥ 0.5, so the §6 stop rule did not trip.
- The Validator recomputed p and e160 from the margins independently. The values match the panel's.

## U

- **U(plating_margin_m160_v) = 0.00023 V**: the largest e160, 2.2749e-4 V, rounded up at two significant figures.
- **Consequence:** convergence is first order. U is 28–39 % of these near-onset margins, so a case with |m160| ≤ U counts on neither side of the plating straddle (VALIDATOR_BATTERY_SEALED_RULINGS_20261022 §8–9).
- A mesh-320 spot solve differing from mesh 160 by more than U, or flipping the v2 label, stops the batch (fail closed). U is never widened to pass a batch.
- **Applies to:** the plating v2 reference at mesh 160 only. A new mesh, image, overlay or tolerance needs a new record.
