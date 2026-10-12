# Electromagnetics kit — GetDP

**PROPOSED bundle with accepted linear discretisation evidence, not universal
magnetics validity.** Reuse `scripts/dev/motor/reference/` GetDP 3.5.0 / Gmsh
4.15.2 pins and the linear Form1P MMS. Historical accepted image:
`sha256:599521e79786ee0326a0754ba0545f51ee9665adff73c3515c8d4b8ba24c1c05`.
Accepted A/B convergence does not verify nonlinear B-H, remanence, hysteresis,
AC losses, axisymmetric force or end effects. Current store presence UNKNOWN.

## Once per applicable kit version

- Law/output template: signed torque/force versus registered angle/stroke/current,
  material-consistent coenergy and flux-linkage/inductance diagnostics. For motor,
  keep unaveraged slice torque/cogging, skew weights/phase offsets, and a closed
  cogging cycle with no duplicated endpoint. Check averaging exactly once and
  torque as coenergy derivative at fixed currents. Optional weighted airgap
  contour probes only if they detect an additional failure family.
- Minimal sufficient exports are compact curves/integrals, not B/H/J meshes.
  A solenoid needs force/virtual-work or stress-integral agreement; a transformer
  needs a complete excitation/inductance matrix, with reciprocity only where its
  constitutive assumptions permit it. Motor curves are not those observers.
- Observer verification: sign/unit/contour invariance, rotation registration,
  derivative/refinement uncertainty and an independent force/torque route.
  Material nonlinearity/saturation and new coordinates require native proofs.
- Public kit: revised 10p/12s grammar/domain checks and exact signed curves as
  templates only; the 8p/24s runtime adapter is not this development model.
  Include complete learner environment and refused out-of-envelope inputs.
- Comparator: reluctance/circuit models, Kriging/RBF full-curve maps, cached FE
  and geometry-aware local refinement. For solenoids use nonlinear force maps;
  for planar transformers analytical leakage + cached FE, not motor lookup.
- Equal budget: reuse motor ledger/adapters and registration shape. Count all
  current/stroke/angle/slice or winding excitations per complete decision.
  Changed geometry may invalidate factorisation reuse; measure it.

## Per Challenge / reuse invalidators

Geometry grammar, materials/temperature, current/current-density and winding
constraints, envelope, P/Q/w, buyer requirements, near-limit sampling, question
law and independent tool witnesses remain specific. Motor's 12 N·m peak is not
lowered for feasibility. Solenoid DC force is not a thermal-duty certification;
transformer inductance is not frequency-dependent loss/insulation safety.
Axisymmetry is permitted only for the unchanged buyer geometry, never a hidden
downscope of a 3D job. Tolerances and reference credibility remain HUMAN_INPUT.
Sources: [register](../sources.md), [priorities](../candidates.md).
