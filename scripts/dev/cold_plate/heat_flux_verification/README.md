# Cold plate (#342): rung 2, heated-channel verification

**What this is.** The second check on the cold-plate reference toolchain. It
takes rung 1's channel flow, heats both walls with the same uniform flux, and
compares the result with two closed forms:
- the fully developed Nusselt number, a heat-transfer check;
- the bulk-temperature rise, an energy-conservation check.

**What it is not.**
- It is not the cold plate: there is no solid, no conjugate interface and no
  real coolant properties.
- It qualifies nothing and sets no tolerance.
- Its values are verification choices, not cold-plate design values. #342's
  scope remains a **proposed development design**, not a ratified production
  population.

## The case

- **Flow:** rung 1's laminar parallel-plate flow. H = 1 mm, length 100 mm,
  ν = 1e-6 m²/s, inlet U = 0.1 m/s, Re = 200. The pressure tolerance is 1e-9,
  after rung 1's finding.
- **Temperature:** `scalarTransportFoam` solves the steady temperature field on
  the converged flow.
  - DT = ν, so Pr = 1. The fully developed Nusselt number does not depend on
    Pr, and Pr = 1 keeps the thermal entrance short (about 20 mm).
  - Both walls carry a fixed wall-normal gradient G = q''/k = 1000 K/m. The
    Nusselt number does not depend on G.
- **Closed forms**, for fully developed flow with both walls at uniform flux:
  - Nu = h·2H/k = G·2H/(T_w − T_b) = **140/17 = 8.2353** (Shah & London);
  - dT_b/dx = 2·DT·G/(U·H) = **20 K/m**. This is energy conservation, and it is
    independent of the Nusselt number.
- **Measurement region:** x = 60–95 mm.
  - T_b is the velocity-weighted mean temperature of each cell column.
  - T_w is the wall cell's temperature plus G over half a cell: the same
    fixed-gradient relation the solver applies at the wall.
  - Nu is averaged over the columns.
- **Converged fields only.** The temperature solve runs 200 outer iterations,
  and the last initial residual is reported. Three iterations were not enough:
  `linearUpwind`'s deferred correction left the residual at 1.8e-3.

## Commands

```bash
scripts/dev/cold_plate/heat_flux_verification/run_case.sh NX NY OUTDIR
python3 scripts/dev/cold_plate/heat_flux_verification/analyze.py OUTDIR
```

The runner uses the same pinned image and isolation as rung 1: offline, the
invoking user, an owner-only output directory, and no overwrite. The analysis
reports and judges nothing.

## Result (2026-09-27, this host)

| Mesh | Flow converged | Last T residual | Wall time | Nu | Nu error | dT_b/dx error |
|---|---|---|---|---|---|---|
| 200 × 20 | yes | 9.6e-11 | 3 s | 8.249617 | +0.1739 % | 1.2e-10 |
| 400 × 40 | yes | 8.9e-11 | 17 s | 8.238914 | +0.0440 % | 1.6e-10 |
| 800 × 80 | yes | 9.7e-11 | 381 s | 8.236202 | +0.0110 % | −4.9e-10 |

- **Nusselt number.** The error falls by 3.96, then 3.99, per refinement:
  second-order convergence onto 140/17.
- **Energy balance.** The bulk-temperature gradient matches it to round-off
  (below 1e-9) on every mesh.
- **Tolerance.** The 800 × 80 run took 381 s, against 1,215 s in rung 1 at the
  same mesh. The raised tolerance removed the round-off stall rung 1 recorded.

## Next rung

Conjugate heat transfer: a solid plate with channels, using
`chtMultiRegionFoam`, with energy and mass balance checks. Material and
coolant properties are then real inputs, and a proposal for review, not
values chosen here. After that comes the #342 pilot (8 ordinary and 4
difficult cases with paired refinement), priced for owner approval before it
runs.
