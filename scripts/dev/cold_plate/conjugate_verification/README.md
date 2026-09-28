# Cold plate (#342): rung 3, conjugate heat-transfer verification

**What this is.** The first conjugate check on the cold-plate reference
toolchain. Heat enters through a solid, crosses a solid–fluid interface and is
carried away by the flow. It uses `chtMultiRegionSimpleFoam` in the pinned
OpenFOAM v2512 image.

**What it is not.**
- It is not the cold plate: no plate geometry, channels or real materials.
- It qualifies nothing and sets no tolerance.
- The property values below are verification choices, not a coolant or a
  plate material. #342's scope remains a **proposed development design**.

## The case

- **Geometry.** A 1 mm channel between two 0.5 mm solid slabs, 100 mm long,
  2D.
  - Built as three `blockMesh` cell zones and split into regions with
    `splitMeshRegions`.
  - The interfaces use `compressible::turbulentTemperatureCoupledBaffleMixed`
    on both sides.
- **Fluid.** Laminar, U = 0.1 m/s, Re = 200 (as in rungs 1–2). Constant
  properties with ν = 1e-6 m²/s and Pr = 1, so k_f = 4.181 W/m·K. There is no
  buoyancy.
- **Solids.** k_s = 10 W/m·K. At steady state, only k matters.
- **Heating.** Each slab's outer face takes a uniform flux of q = 10⁴ W/m²
  (`externalWallHeatFluxTemperature`). The slab ends are insulated.
- **Closed forms**, for fully developed flow:

  | Quantity | Expected |
  |---|---|
  | Temperature drop across each slab | q·t/k_s = 0.5 K (1D conduction) |
  | Nusselt number | q·2H/(k_f·(T_w − T_b)) = 140/17 |
  | Interface temperature | the same from the solid side and the fluid side |
  | Bulk-temperature gradient | 2q/(ρ·c_p·U·H) = 47.835 K/m |

- **Measurement.** Wall and interface temperatures come from the cell next to
  the face plus the imposed flux over half a cell, on each side. Values are
  averaged over x = 60–95 mm.

## Commands

```bash
scripts/dev/cold_plate/conjugate_verification/run_case.sh NX NYF NYS OUTDIR
python3 scripts/dev/cold_plate/conjugate_verification/analyze.py OUTDIR
```

The runner uses the same pinned image and isolation as rungs 1–2: offline,
the invoking user, an owner-only output directory, and no overwrite. The
analysis reports and judges nothing.

## Result (2026-09-27, this host)

| Mesh (x × fluid × each solid) | Iterations analysed | Last residuals (h / U / p_rgh) | Solid drop error | Nu error | Interface gap | dT_b/dx error |
|---|---|---|---|---|---|---|
| 200 × 20 × 10 | 4,000 | 9e-12 / 1e-10 / 2e-9 | −1.6e-8 | +0.1739 % | 1.2e-7 K | −4.6e-9 |
| 400 × 40 × 20 | 8,000 | 1e-11 / 2e-10 / 4e-9 | −2.0e-8 | +0.0440 % | 7.7e-8 K | −1.1e-8 |

- **Conduction, the interface and energy are exact to round-off** on both
  meshes. The solid–fluid coupling adds no error.
- **The Nusselt error equals rung 2's on the same fluid mesh**, to every
  printed digit (+0.1739 % and +0.0440 %). It falls by 3.96, the second
  order of the fluid discretisation alone.
- **Iteration convergence was checked, not assumed.** At 4,000 iterations the
  refined case still had an energy residual of 8e-8, which moved Nu to
  +0.0503 % and the balances to about 1e-5. It was continued to convergence
  before being reported.
- **Cost.** 702 s coarse; 2,921 s plus 6,037 s refined, on local CPU. The
  pressure solver again hits its iteration cap near a 1e-9 tolerance, the
  same round-off stall rung 1 found. A future rung should use a looser
  pressure tolerance for the fluid region.

## Next

The cold plate itself: a plate with parameterized straight or serpentine
channels, per #342's bound (not arbitrary topology). Material and coolant
identity become real inputs for domain review, not values chosen here. Then
comes the #342 pilot (8 ordinary and 4 difficult cases with paired
refinement), priced for owner approval before it runs.
