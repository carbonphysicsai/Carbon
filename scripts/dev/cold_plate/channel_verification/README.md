# Cold plate (#342): rung 1, channel-flow verification

**What this is.** The first check on the cold-plate reference toolchain. Before
any heat transfer or conjugate physics, it asks whether the pinned OpenFOAM
image turns geometry into a mesh, a solution and outputs that reproduce a
closed-form answer, and whether the error shrinks as it should when the mesh is
refined.

**What it is not.**
- It is not the cold plate.
- It does not qualify the solver as truth for any cold-plate case.
- It sets no tolerance.

The dimensions are an engineering choice for a laminar check, not a cold-plate
design value.

## The case

- **Flow:** steady, laminar, incompressible flow between parallel plates. 2D,
  one cell thick, with `empty` front and back.
- **Geometry and fluid:** gap H = 1 mm, length 100 mm, water (ν = 1e-6 m²/s).
- **Inlet:** uniform U = 0.1 m/s, so Re = U·2H/ν = 200 (laminar).
- **Closed form**, for fully developed plane Poiseuille flow:
  - pressure gradient dp/dx = −12 ν U / H² = −1.2 (kinematic, m/s²);
  - peak velocity u_max = 1.5 U.
- **Measurement region:** x = 60–95 mm, well past the entrance length (about
  0.05·Re·2H = 20 mm). dp/dx is a least-squares slope over it; u_max is taken
  at the last cell column inside it.

## Commands

```bash
scripts/dev/cold_plate/channel_verification/run_case.sh NX NY OUTDIR   # geometry -> mesh -> solve -> cell centres
python3 scripts/dev/cold_plate/channel_verification/analyze.py OUTDIR  # compare with the closed form
```

`run_case.sh`:
- copies the case into a new owner-only `OUTDIR` and refuses an existing one;
- sets the resolution;
- runs `blockMesh`, `simpleFoam` and `postProcess -func writeCellCentres` in
  `opencfd/openfoam-default@sha256:33fb575a…f319` (OpenFOAM v2512), with
  `--network none`, as the invoking user.

`analyze.py` reads the ASCII fields on the host (the image has no Python) and
reports errors. It judges nothing.

## Result (2026-09-26, this host, 20 CPUs)

| Mesh (NX × NY) | SIMPLE iterations | Wall time | dp/dx error | u_max error |
|---|---|---|---|---|
| 200 × 20 | 197 | 2 s | −0.4975 % | −0.4975 % |
| 400 × 40 | 180 | 42 s | −0.1248 % | −0.1248 % |
| 800 × 80 | 478 | 1,215 s | −0.0312 % | −0.0312 % |

- **Convergence.** Every run met its residual control ("SIMPLE solution
  converged").
- **Error ratio.** Between successive meshes the ratio is 3.99, then 4.00: the
  second-order convergence the discretisation should give, onto the closed
  form. The geometry → mesh → solve → output chain is therefore consistent for
  this flow.
- **Finding.** The 800 × 80 wall time is dominated by the pressure solver
  hitting its 1,000-iteration cap on every outer iteration. `fvSolution` sets
  tolerance 1e-12, near round-off. That is kept here so the three meshes stay
  comparable. The next rung should use a tolerance well above round-off.

## Next rungs

1. **Heat transfer.** Uniform wall heat flux in the same channel, compared
   with the fully developed Nusselt number for parallel plates with both
   walls heated.
2. **Conjugate heat transfer.** A solid plate with channels, using
   `chtMultiRegionFoam`, with energy and mass balance checks.
3. **The #342 pilot.** 8 ordinary and 4 difficult cases, with paired
   refinement. It is priced and approved by the owner before it runs.
