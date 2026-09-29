# Cold plate (#342): rung 4, a straight-channel plate cell

**What this is.** The first check with plate geometry on the cold-plate
reference toolchain. It is #342's "first concrete task": a reproducible,
simple channel baseline, with the commands from geometry to mesh to solve to
output written down before the design family grows.
- The case is one repeating cell of a plate with parallel straight channels:
  half a channel and half a fin, between two symmetry planes.
- The base is heated; the lid is adiabatic.
- It is 3D and conjugate, using `chtMultiRegionSimpleFoam` in the pinned
  OpenFOAM v2512 image, as rung 3 did.
- The geometry is parameterized.

**What it is not.**
- It is not a cold-plate design. The properties, velocity and flux are
  rung 3's verification choices, not a coolant, a plate material or a heat
  load. **Material and coolant identity stay open for domain review.**
- It covers straight channels only. Serpentine channels, manifolds and a
  full plate are later rungs.
- It qualifies nothing and sets no tolerance. #342's scope remains a
  **proposed development design**.

## The case

`generate.py` writes the case from six dimensions, given in millimetres. The
defaults are a verification geometry:

| Parameter | Default |
|---|---|
| `--length` | 50 |
| `--channel-width` | 1 |
| `--channel-height` | 2 |
| `--fin-width` | 1 |
| `--base-thickness` | 1 |
| `--lid-thickness` | 0.5 |

`--resolution r` multiplies every cell count. At r = 1 the mesh is:
- 50 cells along the flow;
- 5 + 5 across the channel and fin;
- 5 + 10 + 3 up through the base, channel and lid.

The cross-section is drawn in `generate.py`'s docstring.

**The model.**
- **Fluid:** laminar, with a uniform inlet at U = 0.1 m/s and 300 K. Its
  properties are rung 3's: ν = 1e-6 m²/s, Pr = 1, ρ = 1000 kg/m³ and
  c_p = 4181 J/kg·K. D_h = 1.33 mm and Re = 133.
- **Solid:** rung 3's k_s = 10 W/m·K.
- **Boundaries:**
  - the base takes a uniform flux of q = 10⁴ W/m²;
  - the lid, the plate ends and both symmetry planes are adiabatic;
  - the outlet is at 1e5 Pa, with zero-gradient T.
- **Pressure tolerance:** 1e-7, looser than rungs 1–3. It follows rung 3's
  note that the solver stalls near 1e-9.

**What is compared, and against what.**

| Quantity | Reference |
|---|---|
| Mass balance | Exact: inlet mass flow equals outlet mass flow |
| Energy balance | Exact at steady state: ṁ c_p (T_b,out − T_b,in), plus the heat conducted out through the fixed-temperature inlet, plus the change in kinetic-energy flux, equals q·A_heated |
| Fully developed pressure gradient | Exact series for a rectangular duct (Shah & London; White eq. 3-48), 1,749.16 Pa/m here, measured on section-averaged pressure over 60–95 % of the length |
| Peak and mean heated-face temperature, outlet bulk temperature, pressure drop | No closed form: reported under mesh refinement only |

**Iteration convergence.** Every quantity is reported at the half-way and the
final write, and compared between them.

## Commands

```bash
scripts/dev/cold_plate/plate_channel/run_case.sh OUTDIR [--resolution R] [--iterations N] [geometry options]
python3 scripts/dev/cold_plate/plate_channel/analyze.py OUTDIR
```

The runner uses the same pinned image and isolation as rungs 1–3: offline,
the invoking user, an owner-only output directory, and no overwrite. It also
caps the container at two CPUs, because the host is shared. The analysis
reports and judges nothing.

## Result (2026-09-28, this host)

Both runs are serial and CPU-capped. The final write is shown; the half-way
write agrees with it to about 2e-9 relative in every quantity, so both are
iteration-converged.

| Resolution (cells) | Iterations | Wall | Last residuals (h / U / p_rgh) | Mass imbalance | Energy: advection only | + inlet conduction | + kinetic energy (complete) | dp/dx error vs exact |
|---|---|---|---|---|---|---|---|---|
| 1 (9,000) | 4,000 | 37 s | 4e-11 / 6e-10 / 5e-8 | −1.6e-9 | −3.31e-4 | −8.9e-7 | **−4.5e-10** | −3.960 % |
| 2 (72,000) | 8,000 | 392 s | 8e-12 / 6e-10 / 2e-7 | +6.0e-9 | −4.47e-4 | −9.9e-7 | **+4.4e-9** | −1.046 % |

Under refinement, where there is no closed form:

| Quantity | r = 1 | r = 2 | Change |
|---|---|---|---|
| Peak heated-face temperature | 303.3770 K at x = 49.5 mm | 303.3835 K at x = 49.75 mm | +6.5 mK |
| Mean heated-face temperature | 302.6743 K | 302.6864 K | +12.1 mK |
| Outlet bulk temperature | 301.19549 K | 301.19535 K | −0.14 mK |
| Pressure drop, inlet to outlet | 89.52 Pa | 93.14 Pa | +4.0 % |

- **Mass is conserved to round-off** on both meshes.
- **The pressure gradient converges to the exact duct value at second
  order.** The error falls by 3.78 between meshes, an observed order of 1.92.
  The pressure drop's 4 % change is mostly this same fully developed error,
  with the entrance region added.
- **Energy is conserved to round-off once every boundary term is counted.**
  - Advection alone misses by −3.3e-4 and −4.5e-4.
  - The fixed-temperature inlet conducts heat back out of the warmed fluid
    (0.17 and 0.22 mW). Counting it leaves about 1e-6 on both meshes.
  - That 1e-6 is the kinetic-energy term. The solver's enthalpy equation
    carries `div(phi, K)`, and the uniform inlet developing into the duct
    profile raises the flux of K by 0.44 and 0.50 µW. Counting it closes the
    balance to −4.5e-10 and +4.4e-9.
  - **How this was attributed.** `wallHeatFlux`, run through the solver's
    `-postProcess` mode on the coarse case, shows the heated base delivering
    exactly 0.5 W. The interface passes it on to within 3e-9. That placed
    the gap in the fluid, where the kinetic-energy flux matched it to 0.3 %
    on r = 1.
- **The hottest point is at the outlet end of the base**, in the last cell
  column. That is expected with adiabatic plate ends and fluid warming along
  the channel. It moves with the mesh only because it is always the last
  column.
- **Cost:** 37 s and 392 s of wall time on local CPU, capped at two CPUs.
  No pod and no paid compute.

## Next

1. **Widen the straight-channel family inside #342's bound**, still with
   verification properties. Vary the channel aspect ratio, the fin width and
   the base thickness, and preserve every failed geometry rather than
   dropping it.
2. **Serpentine channels and a whole plate with inlet and outlet headers.**
   These are the first rungs where the symmetric cell no longer represents
   the plate.
3. **Owner and domain inputs this family now needs:**
   - material and coolant identity;
   - the flow and heat-load ranges, which decide whether the envelope stays
     laminar (#342 asks for this to be confirmed first);
   - the thermal-interface assumption.

   None of these is chosen here.
4. **Then the #342 pilot:** 8 ordinary and 4 difficult cases with paired
   refinement, priced for owner approval before it runs.
