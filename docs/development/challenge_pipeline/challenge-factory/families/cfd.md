# CFD kit — OpenFOAM

**PROPOSED versioned sub-kits, not one verified CFD image.** Cooling cell's
OpenCFD v2512 route and f17's proposed v2506 scalar transport differ. SU2 BFS
is not interchangeable with either. Reuse code-verification specs, public
cooling/micromixer readiness drafts and package locks only at matching versions;
accepted CFD image/applicability is not inferred here; current store presence
is UNKNOWN.

## Once per applicable sub-kit version

- Minimal law/output template: independently integrated signed inlet/outlet
  mass and enthalpy, boundary heat and two-sided conjugate interface flux;
  pressure drop, volume flow and hydraulic power on the **same cell basis**;
  bounded extrema and registered case-plane temperature/flux probes. A mixer
  additionally needs advective **and diffusive** scalar boundary flux/storage,
  unclamped concentration diagnostics and positive-flux-weighted outlet mixing.
- Pin density/c_p, native kinematic pressure→Pa conversion, control surfaces,
  normals, backflow policy and sampling. Echoed inlet flow or outlet temperature
  algebraically reconstructed from the heat balance is not independent evidence.
- Verify actual flow/pressure/thermal equations, wall and interface observables,
  mass/energy/scalar closure and mesh/order/convergence. A prescribed-velocity
  scalar analytic check does not verify a Navier–Stokes or RANS solution.
- Public kit: reuse interior-cell or full-channel generators/domain checks with
  their exact validity. Turbulence/closures and scaling are not supplied by a
  family name. All eight research provisions and disclosed limitations remain.
- Comparator: thermal/hydraulic networks and response maps for cooling/heat
  sinks; ASHRAE loss library + calibrated coarse-RANS map for duct fittings;
  verified advection/diffusion reduced routes for mixing. Paid library rights
  are separate; do not treat ASHRAE subscription data as open training data.
- Equal budget: count mesh, flow acquisition/reuse, scalar solves, all conditions,
  observer/refinement and reference checks. Reuse flow only after proving the
  scalar does not change it and matching every relevant cache-key field.

## Per Challenge / cooling-specific inputs

Geometry, fluid/material law, flow/heat service envelope, boundary/closure
validity, buyer limits, P/Q/w, question law and independent witnesses remain
specific. **Cooling stays interior-cell-only, no full plate/manifold.** The
85 °C proxy is lid-side TIM2 case temperature, not die/junction.

From RES-03 `operating-points.json`, all service choices are **DEVELOPMENT
ASSUMPTION**, not an adopted population: central B **40 °C / 1000 W /
1.50 L/min / 25 kPa**; A base **32 °C / 750 W / 1.125 L/min / 20 kPa**;
optional C base **45 °C / 1400 W / 2.80 L/min / 30 kPa**. Use the complete
inlet/power/flow-per-kW/pressure ranges in [retrospective.md](../retrospective.md),
not independent endpoints assembled into a fictitious approved case.
Lid characterization, post-spreader heat map, hydraulic allocation and
cheap-baseline value evidence are HUMAN_INPUT. The C physics draft does not
replace B or activate stress; adoption is the owner's. New material/observer
and CFD uncertainty/tolerance acceptance remain HUMAN_INPUT.
Sources: [register](../sources.md).
