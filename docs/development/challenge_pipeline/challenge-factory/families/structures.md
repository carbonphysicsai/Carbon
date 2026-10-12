# Structures kit — CalculiX

**PROPOSED bundle; source-locked build is not a verified nonlinear foundation.**
Reuse `scripts/dev/reference_packages/calculix/` (ccx 2.23, SPOOLES 2.2,
ARPACK/compiler/library checksums and serial settings). The prepared axial-rod
and oscillator code checks have narrower coverage than customer structures;
no broad owner acceptance is asserted; current operator image availability is
UNKNOWN.

## Once per applicable kit version

- Physics/output template: displacement/warpage/coplanarity and stress/strain at
  registered regions; independently extracted external work, strain energy and
  dissipation when appropriate; support reactions and load resultants; compact
  contact-force/slip/separation/preload histories. State small/large-deformation,
  material, load-history and work sign conventions. Energy positivity is not a
  universal statement about every nonlinear potential/material path.
- Prefer integral reactions/energy plus decision extrema/probes. A peak stress
  at a singular corner is not automatically a buyer allowable; stress measure,
  gauge/averaging domain and mesh uncertainty need agreement. No full mesh field
  export merely to make a nominal PDE residual possible.
- Observer/native checks: rod/beam/bimetal exact cases as applicable, mesh/element
  order, reaction balance, rigid-body constraints and energy, plus contact patch
  and preload tests. Mode convergence is not verification of friction,
  hyperelasticity, nonlinear shells, cure kinetics, viscoelasticity or solder
  formation/history. Each new feature gets its own applicability record.
- Public kit: reuse f08 and bolted/warpage rehearsal generators/domain hooks,
  labelling REPRESENTATIVE data; customer material curves/rights remain inputs.
- Comparator: cached **cross-geometry** modal reduction for f08, VDI-style
  compliance/contact-aware maps for bolts, handbook + calibrated contact FE for
  seals, elastica/beam maps for springs, nonlinear shell FE caches for bottles.
  Keep the strongest applicable method, not just linear hand calculations.
- Equal budget: same ledger interfaces, including preprocessing, modal basis,
  contact/Newton failures, material fitting and full histories. A load step is
  not a complete decision; cached factors are reusable only on matching systems.

## Per Challenge / reuse invalidators

Geometry, supported topology/contact/load histories, calibrated material laws,
manufacturing scatter, safety allowables, P/Q/w, question law, solver applicability
and independent witnesses remain specific. Warpage retains **full 3D process
history**; its high-cost discovery scenario exceeds €100 and open calibration
is missing. Do not drop ~80% of the original buyer job to fit a cheap plate model.
Bolts retain preload/contact; seals retain extrusion/contact and calibrated
elastomer laws; bottles retain required nonlinear load histories. These are
feature gaps, not free reuse. Tolerances/qualification remain HUMAN_INPUT.
Sources: [register](../sources.md), [rank caveats](../candidates.md).
