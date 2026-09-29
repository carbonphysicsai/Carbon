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
3. **The owner and domain inputs are now set, provisionally,** in
   `../DESIGN_BASIS.md` (owner-delegated, 2026-09-29):
   - a copper C11000 plate cooled by PG25;
   - the 1 kW accelerator class, at 1.25-2.0 L/min per kW and a 30-45 °C
     inlet, which is laminar across the family;
   - the TIM as a uniform resistance added after the solve.

   Rung 5 uses these instead of the verification properties.
4. **Then the #342 pilot:** 8 ordinary and 4 difficult cases with paired
   refinement, priced for owner approval before it runs.

---

# Rung 5: the same cell at the design point

**What changed from rung 4.**

1. **Named property sets.** `generate.py --properties design` uses the
   provisional design basis (`../DESIGN_BASIS.md`):
   - PG25 at 40 °C (CoolProp 6.8.0, `INCOMP::MPG[0.25]`) on copper C11000;
   - 1 kW over a 30 × 30 mm footprint;
   - 1.5 L/min per kW through 50 channels of 0.3 × 2 mm;
   - so U = 0.833 m/s, q = 1.11 MW/m², Re ≈ 325 and Pr = 11.05.

   `--properties verification` (the default) is rung 4's set. Its generated
   dictionaries differ from rung 4's only in number formatting (for example
   `1000` against `1000.0`).
2. **Energy converges in far fewer iterations.** Two solver settings
   changed:
   - the solid enthalpy solve runs to its absolute tolerance (`relTol 0`);
   - enthalpy is not under-relaxed (`h 1.0`, in both regions).

   With rung 4's settings, copper's high conductivity left the energy balance
   95 % open after 400 iterations. With these, it closes within 200.
   - **Checked on rung 4's own case:** rung 4's coarse case, rerun under the
     new settings, reproduces every reported quantity to the printed digit.
   - Its complete energy balance tightens from −4.5e-10 to +1.4e-9.
3. **The analyzer reads its properties from `case.json`.** A rung-4 case
   directory has no property set recorded, and is read as `verification`.

**The case.** The geometry is `--length 30 --channel-width 0.3 --fin-width
0.3 --channel-height 2 --base-thickness 1 --lid-thickness 0.5`. The runs
were 2,000 iterations at resolution 1 and 4,000 at resolution 2.

## Result (2026-09-29, this host)

Both runs are iteration-converged: the half-way and final writes agree to
the printed digit.

| Resolution (cells) | Wall | Mass imbalance | Energy balance, complete | dp/dx (exact 166,029 Pa/m) | dp/dx error |
|---|---|---|---|---|---|
| 1 (9,000) | 21 s | −9e-10 | −1.1e-7 | 157,713 Pa/m | −5.01 % |
| 2 (72,000) | 442 s | +1e-10 | −1.6e-8 | 163,272 Pa/m | −1.66 % |
| 3 (243,000) | 2,757 s | +5e-11 | −1.3e-9 | 164,716 Pa/m | −0.79 % |

| Quantity, no closed form | r = 1 | r = 2 | r = 3 |
|---|---|---|---|
| Peak heated-face temperature, last cell column | 350.801 K | 350.871 K | 351.063 K |
| Mean heated-face temperature | 344.188 K | 343.865 K | 343.895 K |
| Outlet bulk temperature | 323.1299 K | 323.1297 K | 323.1295 K |
| Pressure drop, 30 mm | 4,972 Pa | 5,188 Pa | 5,249 Pa |

**Conservation.**
- **Mass and energy are conserved to round-off** on both meshes.
- **The coolant rise is 9.98 K,** which is exactly Q/(ṁ·c_p) for 10 W per
  half-cell. This matches OCP's 10 °C design rule at 1.5 L/min per kW.

**The pressure gradient converges toward second order; the coarse mesh is
pre-asymptotic.** Each error is measured against the exact duct series, so
every pair of meshes gives an order directly.
- Error: −5.01 %, then −1.66 %, then −0.79 %.
- Observed order: **1.59** from r = 1 to 2, and **1.83** from r = 2 to 3.
- The order is approaching the scheme's second order. The coarse mesh has 5
  cells across a 0.15 mm half-channel.

**Temperatures.** The mean and the outlet converge. The local base
temperatures do not.
- **The mean** base temperature changes by −0.32 K from r = 1 to 2, then by
  +0.03 K from r = 2 to 3. **It converges.**
- **The outlet bulk temperature is converged** to 0.4 mK.
- **The local base temperatures are not mesh-converged.**
  - The peak rises by +0.07 K from r = 1 to 2, then by +0.19 K from r = 2
    to 3.
  - Measured on the heated patch's own face temperatures, the maximum
    restricted to x ≤ 0.9 L goes 350.312 → 350.399 → 350.599 K (+0.09, then
    +0.20). The increment does not shrink.
    *(Corrected: an earlier version quoted 0.2-0.25 K from raw cell-centre
    values. Those omit the half-cell flux correction, which shrinks with
    refinement.)*
  - **This is not a measurement artefact.** The heated patch's own face
    temperatures, written by the solver, agree with the analyzer's
    extrapolated values to 0.1 mK.
  - **Not the plate-end corner** either: the non-convergence appears away
    from the end.
  - **Hypothesis, untested:** at Pr = 11, the thermal boundary layer is thin
    and still developing over the whole 30 mm plate, since the thermal entry
    length is about 90 mm. Uniform meshes of 5-15 cells across the 0.15 mm
    half-channel may not resolve it.
  - **No local or peak temperature here is claimed as converged.**

**The die temperature, under the design basis's interface assumption.** The
nominal R″ = 0.05 cm²·K/W adds q″·R″ = 5.56 K. **This offset is exact.** A
die temperature built on the peak inherits the lack of convergence in the local
base temperatures: it is about 83 °C at a 40 °C inlet on these meshes.
- This is a derived number, not a design verdict.
- No temperature limit is set here.

**Cost.** 21 s, 442 s and 2,757 s of wall time on local CPU, capped at two
CPUs. No pod was used.

## Next

1. **Resolve the thermal boundary layer.** Done in rung 5b (below): with
   wall grading, the local base temperatures converge.
2. **The straight-channel family sweep,** within the design basis's ranges:
   - channel width, fin width and depth;
   - flow, from 1.25 to 2.0 L/min per kW;
   - inlet temperature, from 30 to 45 °C;
   - preserving every failed geometry.
3. **Temperature-dependent viscosity.** It falls about 40 % between 30 and
   50 °C, so whether the reference needs it is a reference-qualification
   question. The sweep can measure its effect.
4. **Serpentine channels and a whole plate with headers.**


---

# Rung 5b: wall-graded meshes at the design point

**The change.** `generate.py --wall-grading G` makes cells shrink by up to a
factor G toward every solid-fluid wall:
- in y, toward the channel wall, per column;
- in z, toward the channel floor and ceiling, per row.

Blocks that share edges get the same grading. `G = 1`, the default, is the
uniform mesh of rungs 4 and 5.

**The analyzer now weights each cell by its volume** when the case writes
`V`. `run_case.sh` now does. Axial spacing is uniform, so a cell's volume is
proportional to its cross-section face. This applies to:
- the section-averaged pressure;
- the inlet conduction;
- the outlet kinetic-energy flux;
- the mean heated-face temperature.

A uniform r = 1 case that writes `V` reproduces rung 5's unweighted r = 1
values to round-off.

**The run.** It is the design point of rung 5, with `--wall-grading 4`.
`checkMesh` reports every mesh OK, fully orthogonal, maximum aspect ratio
45.

## Result (2026-09-29, this host)

All three meshes are iteration-converged.

| Resolution (cells) | Wall | Mass imbalance | Energy balance, complete | dp/dx error | Peak heated face | Mean heated face | Pressure drop |
|---|---|---|---|---|---|---|---|
| 1 (9,000) | 17 s | +1.2e-8 | +7.2e-8 | −4.25 % | 351.572 K | 344.304 K | 5,068 Pa |
| 2 (72,000) | 315 s | +5e-10 | −1.1e-8 | −1.09 % | 351.295 K | 343.983 K | 5,243 Pa |
| 3 (243,000) | 2,031 s | −2e-10 | −1.1e-9 | −0.48 % | 351.263 K | 343.940 K | 5,280 Pa |

**The pressure gradient converges at second order:** an observed order of
1.96, then 2.03. The uniform meshes gave 1.59 and 1.83.

**The local base temperatures now converge,** measured on the solver's face
temperatures:

| Heated-face maximum | Uniform, r = 1 → 2 → 3 | Graded G = 4, r = 1 → 2 → 3 |
|---|---|---|
| x ≤ 0.5 L | 344.867 → 344.729 → 344.839 | 345.176 → 344.974 → 344.963 |
| x ≤ 0.9 L | 350.312 → 350.399 → 350.599 | 351.048 → 350.814 → 350.796 |
| whole face | 350.801 → 350.871 → 351.063 | 351.572 → 351.295 → 351.263 |

**What this shows.**
- **On graded meshes, every local maximum converges monotonically,** and
  the step shrinks, from about 0.2-0.3 K to about 0.01-0.03 K.
- **The finest uniform mesh underestimates the peak by about 0.2 K.**
- **This supports the hypothesis:** the uniform meshes under-resolved the
  thermal boundary layer at Pr 11. It does not prove it.

**The design-point peak.**
- **Measured: 351.26 K (78.1 °C)** on the finest graded mesh. The last
  refinement step changed it by 0.03 K.
- **Extrapolated: about 351.24 K,** assuming p = 2 from the pressure order.
  This is an estimate, not a bound.
- **The die temperature**, with the design basis's R″ = 0.05 cm²·K/W
  (+5.56 K, exact), is **about 356.8 K (83.6 °C) at a 40 °C inlet.** That is
  a derived number, not a design verdict. No temperature limit is set.

**Cost:** 17 s, 315 s and 2,031 s on local CPU, capped at two CPUs.

## Next

1. **Use graded meshes (G = 4, r ≥ 2) for the straight-channel family
   sweep** within the design basis's ranges. Preserve every failed geometry.
2. **Temperature-dependent viscosity.** Measure its effect on the converged
   peak.
3. **Serpentine channels and a whole plate with headers.**


---

# Rung 6: the straight-channel family, one factor at a time

**What it is.** A first look at how the design basis's straight-channel
parameters move the answers. It varies one factor at a time around the
nominal design point.
- It is **not** a design optimization, a population or a dataset.
- It sets no threshold, and ranks nothing as acceptable.

**The change.** `generate.py --flow-lpm-per-kw F` (design set only) derives
the inlet velocity:
- the plate's flow (1 kW × F) is shared equally by the ⌊30 mm / (channel +
  fin)⌋ channel periods that fit across the footprint;
- the nominal geometry reproduces the fixed design-set velocity (0.833 m/s,
  50 channels);
- `case.json` records the flow and the channel count.

**How every case ran:**
- resolution 2, `--wall-grading 4`, 4,000 iterations;
- 30 mm plate, 1 mm base, 0.5 mm lid;
- PG25 at 40 °C on copper C11000.

**Why resolution 2 is enough here.** Rung 5b measured the nominal case from
r = 2 to r = 3: the peak changed by 0.03 K and the pressure-gradient error
by 0.6 points (−1.09 % to −0.48 %).

## Result (2026-09-29, this host)

**All nine cases ran; none failed.**
- Mass and energy are conserved to about 1e-8 or better.
- The peak is iteration-converged to about 1e-7 K.
- Each case took 294-354 s on local CPU, capped at two CPUs.

**The columns.**
- **Peak and mean** are measured on the heated face.
- **The rise** is outlet bulk minus inlet.
- **Δp** is over the 30 mm of channel, with no headers.
- **Hydraulic power** is Δp × the plate's total flow.

| Case | Channels | U (m/s) | Re | Peak base (K) | Mean base (K) | Coolant rise (K) | Δp (Pa) | Hydraulic power (W) |
|---|---|---|---|---|---|---|---|---|
{table}

**What the sweep shows,** within this model, one factor at a time:
- **Narrower channels** (0.2 mm): **9.7 K cooler** peak than nominal, at
  **2.7×** the pressure drop.
- **Wider channels** (0.5 mm): **18.6 K hotter**, at about a third of the
  pressure drop.
- **Thinner fins** (0.2 mm) are cooler *and* lower in pressure drop than
  nominal. More channels fit, so each carries less flow.
- **Thicker fins** (0.5 mm) are hotter *and* higher in pressure drop.
- **Deeper channels** (3 mm) are cooler at lower pressure drop.
- **Shallower channels** (1 mm) are hotter at 2.4× the pressure drop.
- **More flow** lowers the peak and the rise, and raises Δp roughly in
  proportion to the flow.
- **Every case is laminar:** Re 226-574. The design basis's laminar check is
  borne out at these points.

**The coolant rise.** It is exactly Q/(ṁ·c_p) when the channel period
divides 30 mm (9.98 K at 1.5 L/min per kW).
- It is 9.81-9.85 K where it does not: for example, 59 × 0.5 mm covers
  29.5 mm, and 9.98 × 29.5/30 = 9.81 K.
- This is the periodic-cell model: the heated area it represents is the
  channels' span. It is not a numerical error.

**What this rung does not cover:**
- **Interactions between factors.** Each case changes one.
- **Inlet temperature.** The design basis tabulates properties at 30, 40 and
  50 °C only; the 45 °C end is not evaluated here.
- **Headers, manifolds, serpentines, spreading at the plate edges, and
  non-uniform heat maps.**
- **Temperature-dependent viscosity.**
- **The TIM,** which adds a uniform 5.56 K at the nominal R″.

## Next

1. **Two-factor interactions** where the one-factor results trade against
   each other: channel width against depth, and fin width against flow.
2. **Temperature-dependent viscosity,** and the inlet-temperature axis, once
   properties at 45 °C are recorded in the design basis.
3. **Serpentine channels and a whole plate with headers.**
4. **The #342 pilot proposal,** priced for owner approval before it runs.
