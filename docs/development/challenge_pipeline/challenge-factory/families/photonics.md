# Photonics kit — Meep

**PROPOSED bundle; no general verified Meep foundation asserted.** Reuse
`solver-package-specs/f06-meep.md`, package-specs.json (Meep 1.32.0 candidate,
exact upstream revision, no accepted image digest), MG readiness drafts and
analytic code-verification routes. Vacuum Bloch-mode verification is not a
dielectric/subpixel/fibre-overlap or 3D device proof. Store presence UNKNOWN.

## Once per applicable kit version

- Minimal output template: complex power-normalised target-mode/order amplitudes,
  reflected/transmitted propagating-order powers, cross-polarisation where
  relevant, independent incident/radiated/absorbed power and energy residual.
  Define reference planes, Bloch phase, finite target aperture and normalisation.
  Upward flux alone is not fibre coupling; target power is not added twice to
  total upward power. Export compact spectra/probes, not full E/H volumes.
- Verify slab/waveguide modes, target overlap, PML/port placement, energy and
  mesh/time convergence on the actual materials and dimensions. S4/RCWA can be
  a witness where applicable, not interchangeable FDTD acceptance.
- Public kit: reuse geometry/domain checks and train/public generation only at
  their exact scope. Registered manufacturing covariance is not independently
  sampled corner tolerances. Full 3D finite-width f06 is not the old cheap
  symmetric directional-coupler model.
- Comparator: strongest 2D optimisation + 3D checks where decision agreement
  permits, RCWA/pattern library, cached scattering maps and multimode methods.
  A nominal-only comparator is too weak for a tolerant broadband buyer job.
- Equal budget: count mesh/state memory, all wavelengths/tolerance vectors,
  sources, convergence/witnesses, training and pattern acquisition. Reuse a
  broadband solve only after parity with the registered outputs is shown.

## Per Challenge / reuse invalidators

Geometry, fabrication/material/dispersion law, wavelengths/angles, target modes,
full 3D versus a separately approved 2D screen, buyer limits, P/Q/w, question law
and independent buyer-tool credibility remain specific. Subpixel smoothing may
improve convergence but cannot declare the coarsest adequate grid. A memory
estimate is not a timing measurement or a cap pass: the f06 10-nm witness risk
is **51–107 GiB before overheads** in the retained package analysis. No grid
relaxation, CPU/GPU comparison, new optical job or cheaper downscope is adopted.
Tolerances, adequate resolution, actual memory/cost and image acceptance remain
HUMAN_INPUT. Don't fill this candidate list with an unproved optics winner to
force seven-family coverage; improve/measure the existing optical job first.
Sources: [register](../sources.md), [pilot](../winnability-pilot.md).
