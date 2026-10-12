# Acoustics kit — Elmer Helmholtz

**PROPOSED bundle; sharing the Elmer image does not share heat MMS acceptance.**
Reuse Elmer 26.2.1 source lock, f13 sweep/de-embedding workers and
`scripts/dev/code_verification/elmer_helmholtz.py`. Its prepared linear-hex MMS
does not verify f13's quadratic tetrahedra, radiation or port observers.
Store presence/applicable Helmholtz acceptance remain UNKNOWN here.

## Once per applicable kit version

- Minimal physics/output template: complex R/T or scattering matrix, incident,
  reflected and transmitted **independent** powers, TL from their declared power
  ratio and uncertainty, reverse excitation when reciprocity applies. Pin
  exp(+iωt), pressure/power normalisation, coordinate/reference planes and
  de-embedding. Above cut-on include **every propagating mode**; scalar R/T is
  inadequate. Do not assert reflection symmetry for an asymmetric device.
- Compact frequency curves/integrals first. A speaker needs angular far-field
  directivity and radiated/source power, not f13's duct TL renamed. Full interior
  fields are unnecessary unless justified by decision or law coverage.
- Verification: analytic matched duct/expansion chamber, complex MMS on actual
  elements, conservation and port mesh/refinement, exterior radiation/convergence
  for a baffle. The reported ≤0.02% f13 power residual with 60-mm stubs is a
  conservation finding, not blanket adequacy or Helmholtz code verification.
- Public kit: reuse quiescent rigid lossless sweep grammar and observers only
  within their validity. Flow, liners, absorption and nonlinear acoustics need
  new physics and cannot be sold as covered by this kit.
- Comparator: plane-wave transfer matrices **plus multimode/reduced Helmholtz
  sweep** for f13; modal/BEM and cached field/directivity bases for speakers.
  Numerical launch count must include frequency and forward/reverse right-hand
  sides. Factorisation reuse is a measured opportunity, not zero-cost assumption.
- Equal budget: reuse f13 registration shape and saved-integral return discipline,
  measuring one complete frequency/angular decision, not one frequency as one
  buyer question. Include mesh, sweep, factorisation, refinement and verification.

## Per Challenge / reuse invalidators

Geometry, medium/loss/flow validity, supported frequency and cut-on, terminations,
ports/radiation, source/receiver directivity, tolerance strata, buyer limits,
P/Q/w and question law are per job. Baffle radiation requires a new exterior
route; a solver supporting Helmholtz does not prove that deck works. Keep
independent Tier-2 buyer-tool and decision-agreement witnesses. All new
tolerances, launch bounds and adoption remain HUMAN_INPUT.
Sources: [register](../sources.md), [pilot](../winnability-pilot.md).
