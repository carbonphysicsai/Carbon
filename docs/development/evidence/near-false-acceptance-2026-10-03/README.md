# Near-limit false acceptance: a localized measurement (2026-10-03)

**Class.** Public synthetic DEVELOPMENT evidence. Descriptive only: no
cutoff, no gate, no score change. The testnet rule is unchanged.

**Authority.** OWNER-EXEC-APPROVALS-01 (2026-10-03): the owner commissioned a
measurement for the named gap that
`docs/development/evidence/real-divergence-2026-10-03/` recorded under
OWNER-CHALLENGE-ADMISSION-01 §6.2. Under every tested rule, the localized
sign-error control scores at or above 95–98 of EV4's 99 real members. The mean
near-limit optimism gate (`carbon/battery/value/admissibility.py`) puts it at
0.46 bands, below every real member.

## The measurement

`carbon/battery/value/false_acceptance.py`. It looks only at the published
important region, the same cases SR-3 and the optimism gate use. For no
plating onset and for peak temperature:

- **Reference verdict:** taken with the decision contract's bands. A value
  inside a band is UNRESOLVED and is not counted.
- **Model verdict:** taken without bands, as the selector reads it.
- **False-acceptance rate:** of the cases the reference resolves as FAIL, the
  share the model calls PASS.

The localized figure is the **worst constraint's rate**. An error confined to
one band is not averaged away by the cases the model gets right. Every
verdict, constraint and band comes from the contract.

## Constructed controls on the scoring set

The scoring set has 1588 cases, 311 of them in the important region. The
controls are built from committed references, so no member predictions are
needed. The figures are in `controls.json`, produced by
`python -m carbon.battery.value.false_acceptance --out <this directory>`.

| Control | Plating: false acceptances / resolved FAILs | Temperature | Worst rate |
|---|---|---|---|
| oracle | 0 / 74 | 0 / 67 | 0.00 |
| conservative | 0 / 74 | 0 / 67 | 0.00 |
| rank-preserving delay | 0 / 74 | 0 / 67 | 0.00 |
| boundary optimist | 74 / 74 | 16 / 67 | 1.00 |
| **localized sign error** | **70 / 74** | 0 / 67 | **0.95** |

The sign-error control waves through 70 of the 74 plating failures the
reference resolves near the limit. The mean optimism measure misses it.

## What this does not show

- **Real members are not measured here.** EV2's and EV4's panel predictions
  are not retained in the repository. Whether real models sit well below
  0.95, which is what separation needs, is unknown until a run with
  predictions, proposed as EV5's H3.
- **No cutoff.** Turning this into a gate needs a cutoff, which is a science
  value (HUMAN_INPUT). Until one is set, it is reported, not applied.
- **One contract.** The figures use EV4's charge-protocol contract and the
  frozen scoring set.
