# Full 3D periodic metagrating — customer design packet

> **Prospective 2026-10-11 adoption:** [Test Lead's owner-delegated decisions](../../../../.agent/decisions/2026-10-11-BENCHMARK-TEST-LEAD-DECISIONS.md)
> and the family owner-decision JSON supersede the original proposal's
> HUMAN_INPUT statements **for selected DEVELOPMENT rules only**. Both
> inventories now contain 17 DECIDED_DEVELOPMENT rules. Q = 40/20/30/10;
> E = 1; BFS uses duty-mean loss and MG worst-case efficiency. P's 20–80%
> per-stratum calibration is a prospective delegated rule, not an earned
> result or reinterpretation of sealed data. Tie = 0.5 × minimum useful
> improvement; frontier band = that improvement. Their numerical values,
> novelty cutoffs, power-derived k/m/n/B, complete package pins, exact
> absent grammar details, rights/reuse and acceptance evidence remain
> closed until measured or registered. No dispatch, spend, qualification,
> runtime activation or adoption is conferred. The text below records the
> original specification/recommendations; do not execute stale placeholders.

BENCHMARK-PACKETS-01 · DEVELOPMENT / SPECIFIED. Proposed family label, not a
runtime ID or f06 substitution. [Research basis](../../../../Business/research/benchmark-challenge-briefs/METAGRATING_3D.md);
[owner decisions](metagrating-3d-owner-decisions.json). No reference solve ran.

## 1. Engineering job

**Mock buyer:** a diffractive-optics R&D engineer choosing a manufacturable
silicon mask and thickness for a specified transmitted diffraction order.
Choose one physical device across a complete incidence/wavelength/fabrication
brief, maximizing desired-order efficiency while meeting unwanted-order,
reflection and manufacturing limits. Limits and scenario aggregation are
HUMAN_INPUT; an optimized source mask is not a buyer's accepted design.

The [Corning/Harvard design study](https://doi.org/10.1038/s41377-024-01629-5)
and [Ansys order-resolved grating workflow](https://optics.ansys.com/hc/en-us/articles/360042088813-Diffraction-grating)
support adjacent industrial R&D and commercial simulation practice. They do
not demonstrate demand, value or deployment for this exact proposed task.
Buyer role/tool preference is ASSUMPTION. Relevant value units: delivered
optical power, efficiency percentage points and rejected fabrication/design
iterations. Laser power, assembly efficiency, iteration cost, annual volume,
latency and low/base/high money value require customer inputs; no inflated
commercial value is claimed. A wrong choice can send power into the wrong
order while a scalar average error looks small.

Keep the **full 3D electromagnetic job**: binary masks vary in both x and y,
with finite thickness and vector fields in x/y/z. An extruded mask is not a
2D field solve. A 1D stripe competitor is legitimate, but narrowing the task
to its geometry to reduce cost needs a separate owner reframe, not this packet.

## 2. Physical system

The pinned [NanoComp setup](https://github.com/NanoComp/photonics-opt-testbed/blob/a06518872de6ec82bb4511190e544211539f55f1/Metagrating3D/README.md)
uses silicon/air patterns on silica, normal TM incidence from the substrate,
wavelength 1050 nm, thickness 325 nm, indices 3.45 and 1.45, deflection 50°,
Px = 1050/sin(50°) nm and Py = 525 nm. These are idealized nondispersive,
lossless **anchor constants**, not approved deployment/material support.
The angle is the desired outgoing direction, not an incident angle.

Research's ASSUMPTION low/base/high alternatives: nominal deflection
40/50/60° and thickness 250/325/400 nm. Keep the proposed nominal wavelength
and Py relation only if accepted; dispersion, loss, process bias, feature
size and mask grammar are HUMAN_INPUT. A fabricated action fixes its physical
Px/Py and thickness across all operating scenarios. Do **not** recompute Px
for each wavelength in a scenario bundle: that would test different hardware.
Define mask-to-permittivity, subpixel averaging and physical fabrication law
explicitly. Resampling/interpolation is not automatically a binary device.

## 3. Population P, Q and w

[Optics law](metagrating-3d-law.md) separates service/requirement P, diagnostic Q
and buyer/evidence w. Nominal design angle/period can vary between briefs;
fabricated geometry cannot vary between conditions of the same question.
No wavelength/angle/material range is ratified. Supported population excludes
published anchors and equivalents under the adopted policy, not merely files
with matching hashes. Independent units, density and weights are HUMAN_INPUT.

## 4. Case contract

An eventual case binds binary periodic mask/physical contour, periods,
thickness/material laws, incident wavevector/polarization, desired order,
fabrication perturbation, measurement/reference identity and rung. Invalid or
unsupported input is not an infeasible optical design. Record unit cell,
reciprocal-lattice and origin conventions, port locations and source direction.

Recommend periodic occupancy distance `integral |chi_a - chi_b| du dv`, minimized
over an **accepted** translation/symmetry group, with separate normalized
period/thickness/material and excitation components. Physical contours, not
pixel counts, carry distance. Compare all known reconstructable source masks,
interpolations, stripes and derivatives in the frozen catalogue. Require mask
novelty as well as supported condition difference. A mirror that exchanges the
wanted order is not a free equivalence. Uniform scaling is equivalent only
with matched nondispersive physics. Quadrature, group, normalizers, weights
and acceptance remain HUMAN_INPUT; no novelty threshold is selected here.

## 5. Reference policy

Research's proposed Meep source is
`b08d226ba311a04e59c984e97f3e88dd82bc56d1` (GPL-2.0-or-later); independent
S4 RCWA candidate is `7fd00a231610bff51f5c7de5f723e3956eab7453`.
Dependency locks, built image digests, port/order adapter and complete deck
are absent. Source results using RETICOLO can be cited; redistribution of that
executable is not assumed authorized. Keep source and dependency notices.

Verify Maxwell components with analytic plane-wave/waveguide tests, then
perform independent spatial, time/decay and PML/domain ladders, all-order
power balance and S4 harmonic convergence. Neither a working image nor energy
closure establishes decision adequacy. Propagating cutoffs/grazing orders
require refinement or UNRESOLVED, not arbitrary clipping or a false zero.
Matched numerical/error criteria and full-route RAM/CPU remain HUMAN_INPUT.

**Credibility target: Tier 2, NOT_DEMONSTRATED.** Mock buyer workflow assumption:
Ansys Lumerical FDTD/RCWA, subject to confirmation. Meep is not automatically
the buyer's own tool/settings. Published numerical anchor comparisons and
matched independent non-hidden novel task witnesses must meet both pointwise
and verdict/pick/regret criteria. Tolerances in absolute efficiency points,
relative power with a nonzero floor, and decision agreement are HUMAN_INPUT.
Unrelated experimental devices do not confer Tier 3 on these masks. Claims
are agreement with an identified simulator, never matches reality.

## 6. Output and measurement contract

Return desired-order efficiency and **all propagating reflected/transmitted
order powers**, with a frozen incident-power normalization, R/T totals,
absorption if supported, energy residual and uncertainty. For general masks,
account for co- and cross-polarization, not just a convenient field component.
Retain order indices, ports, flux signs and complex amplitude phase conventions
where used. Do not conflate field amplitude with power or direction with
efficiency. Grating kinematics alone cannot rank efficiency.

Source scripts/results do not supply the complete proposed output contract.
New reductions need verification. Fabrication, minimum-feature, reflection and
unwanted-order limits are buyer inputs; accepted observable error is a science
input. Mandatory constraints precede ranking; missing/uncertain power cannot
be filled favorably. Full-scenario failure cannot be averaged away by w.

## 7. Construction contract

No new family capability or runtime permission is registered. Recommend reuse
of existing bounded TrainingStrategy, authoring/case disclosure and rebuild
identity patterns, with approved public TRAIN only. Model vocabulary, output
representation, training domain, resources, reconstruction and third-party
rights require their owners. A simulator research wrapper is not an official
grader or permission for unrestricted participant execution.

## 8. Research kit

Existing: attributed source descriptions and proposed routes. Needed: legal
source catalogue, accepted mask/units, public own-seed generator, reference
wrapper, training kit, domain checks and intentionally incomplete practice.
Public anchors stay labelled diagnostics, never scored examples. Third-party
license coverage is audited per asset; an open solver does not license all
vendor data. Hidden cases, fingerprints and derived labels remain operator-only.

## 9. Evidence plan

[Panel plan](metagrating-3d-panel.md) stages code verification, non-scoring
source anchors, exclusion controls, then independent novel full 3D designs
across complete hardware-consistent scenarios and edge refinement. Compare
held-out masks/geometry families, not random rows of one mask.

Strongest cheap methods: published-mask lookup, cached response maps, converged
S4 RCWA with shape optimization and competent direct/adjoint Meep search.
RCWA can be the better method; it is not penalized for being non-neural. Charge
conversion, setup, harmonics, queries, failed attempts, fitting/training and
full-route final verification on equal budgets. Four behavioral controls are
edge-optimist, over-cautious, sign-error and optimizer/library-aware. Measure
decision disagreement, efficiency-point regret, abstention and cost. Statistical
power belongs to Test Lead; final fresh evidence requires a separate grant.

## 10. Readiness and claim record

Exists: research/source records, historic generic drafts and this specification.
Ran: document/arithmetic tests only; no full 3D witness or novelty acceptance.
Missing: approved buyer/law/mask/novelty contract, image/adapter/deck pins,
reference adequacy, registered panel/TRAIN/kit, actual memory/time and empirical
cheap-baseline/equal-budget value. No reference tier or tested stage is earned.

Next: owner/Test Lead settle [one decision inventory](metagrating-3d-owner-decisions.json),
then Data Collection can register an exact public panel under approved support.
The panel's high startup hypothesis exceeds EUR 100; f06's prior memory figures
cannot be transferred to this different domain/grid as a measurement. Reframe
or replace, if necessary, belongs to the owner; no automatic 2D substitution.
Portfolio adoption, protected bank and launch remain closed.
