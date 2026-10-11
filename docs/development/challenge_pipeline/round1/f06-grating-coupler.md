# f06 — manufacturing-tolerant grating coupler, customer round 1

Authority and numeric source: [index](README.md), [sheet](requirements.json).
The old symmetric supermode coupler keeps its historical meaning; this is not
a rename of that reference.

## 1. Engineering job

Hypothetical silicon-photonics designer: choose a fixed-stack 3D TE grating
mask maximizing the finite tolerance-panel 10th-percentile fiber coupling over
1530–1570 nm. Buyer targets: every declared condition coupling≥0.30 and reflected
guided power≤0.10. Poor choices waste mask/assembly work. These are development
targets to test, not feasible performance guaranteed in advance or fabrication yield.

## 2. Physical system

220-nm Si on 2-µm silica BOX and semi-infinite Si substrate, air above;
synthetic lossless nondispersive indices Si=3.48, silica=1.44, air=1. Rectangular
straight grating: 12–20 integer periods, pitch580–680 nm, unetched duty0.35–0.65,
etch70–130 nm, width8–12 µm; fixed 500-nm input TE0 guide and 10-µm linear taper.
Optical absorption is zero by the fixture law, not by experimental observation.
Fiber overlap: Gaussian MFD10.4 µm, waist at z=2 µm above grating top, axis10°
from surface normal in x/z; x/y offsets relative to grating center. Time/phase,
overlap surface and coordinate conventions must be pinned in the deck.

## 3. Population P, Q and w

Actions: valid geometry within that grammar; draw/reference-input geometry law
is uniform independent parameters conditioned on valid line/space≥180 nm.
Exogenous `P_dev` is uniform over nine tolerance vectors, each reporting five
equally weighted wavelengths. Vector order is (pitch nm,etch nm,duty,dx µm,dy µm):
(0,0,0,0,0), (−10,−10,−0.03,0,0), (+10,+10,+0.03,0,0),
(0,0,0,−1,0), (0,0,0,+1,0), (0,0,0,0,−1), (0,0,0,0,+1),
(−10,+10,+0.03,−1,+1), (+10,−10,−0.03,+1,−1).
This finite synthetic panel is not a process/alignment distribution. Q for
feasibility: four geometry/vector cases selected before solves, plus controls
and refinements within cap; no P-wide outcome from those four. For a later
complete panel, w=1/45 per geometry, and p10 is the fifth ordered coupling
value (nearest-rank rule). Wavelengths within a run are not independent trials.

### Prospective population of buyer design questions — `HUMAN_INPUT`

The nine tolerance vectors and five wavelengths are one mask/package
robustness panel. A future `P_job` can vary supported coupling and reflection
requirements or the required tolerance/wavelength service subset while
reusing a full-wave bank that covers the whole panel. A photonics buyer
recognizes each question from its link budget, fiber alignment and PDK
acceptance sheet. Requirement re-evaluation needs no new solve if the bank
stores all relevant coupling/reflection outputs and the best admissible mask
really changes. Different process stacks, PDKs or package laws are optional
axes requiring new qualified 3D truth. Wavelengths and offsets themselves
are correlated measurements, not separate questions.

**Size recommendation, not a selected law:** catalogue eight distinct
condition/requirement questions for a development scoping pilot on a
reference-covered bank. `HUMAN_INPUT`: eligible requirements and service
subsets, `P_job`, protected `Q_job`, weights, answer diversity, clustering,
exposure and hidden `n` after power and full-wave cost studies. Re-drawing an
offset or seed without changing the buyer question is not freshness.

## 4. Case contract

Apply tolerances to the geometry before validating features and positive residual
Si thickness. Reject invalid geometry rather than clipping it. Bind physical
deck, perturbation, source, monitor planes, units and full material law. Keep
public development cases separate from operator-side future protected material.

## 5. Reference policy

Meep 3D full-wave FDTD, independent incident-power normalization, TE0 guided
mode reflection and outgoing fiber overlap. Pin build/image/license, PML and
padding, stopping test, subpixel geometry, mesh and extractor before dispatch.
[Meep's mode decomposition](https://meep.readthedocs.io/en/latest/Mode_Decomposition/)
provides unit-power mode coefficients; its
[PML](https://meep.readthedocs.io/en/latest/Perfectly_Matched_Layer/) and
[interface guidance](https://meep.readthedocs.io/en/latest/Subpixel_Smoothing/)
motivate independent checks, not proof of this task's adequacy.

30/20/10-nm rungs; straight-guide and zero/low-coupling controls; double PML
thickness/padding and simulation duration separately. Require Δcoupling≤0.02,
Δreflection≤0.01 absolute, PML/time change≤0.01 and power residual≤0.03.
No double-counting fiber-coupled power and total upward radiation in energy
closure. Complex phase is retained diagnostically, not scored. No surrogate
replaces unresolved full-wave evidence. Every normalization/control/refinement
launch counts toward36 attempts and the CPU/RAM/$ caps. At10-nm uniform3D
spacing, bare minimum/maximum supported dimensions already require about
573 million/1.20 billion cells before substrate depth, air padding and PML.
This is a cell-count lower-bound screen, not measured Meep memory. Require a
deck-specific cell/memory forecast before even reserving a fine rung; the old
coupler's memory is not transferable. If it cannot fit, this round is coarse
feasibility only, with fine-rung adequacy unresolved. Insufficient memory
or time means UNRESOLVED, not permission to skip the fine rung or buy a GPU.

### Reference credibility target

**Buyer tool:** Ansys Lumerical FDTD is the assumed silicon-photonics design
workflow; this is a role-play choice, not an adoption statistic. **Carbon
reference:** proposed Meep full-3D FDTD/mode overlap, **not the same tool**.
The old symmetric supermode reference is not this grating reference. Tier 1
would need the buyer's actual tool and exact stack/source/mesh/settings.

**Target tier:** Tier 2 for simulator-matched mask shortlisting. Tier 3 measured
coupling/reflection plus fabrication metrology is required only before physical
device-performance reliance; yield additionally needs a real process law and
its own evidence. **Credibility evidence: NOT_DEMONSTRATED** for this task.

**Benchmark cases:** Ansys's published
[Grating coupler](https://optics.ansys.com/hc/en-us/articles/360042305334-Grating-coupler)
**3D** project and [Inverse design of grating coupler — 3D](https://optics.ansys.com/hc/en-us/articles/1500000306621-Inverse-design-of-grating-coupler-3D).
Freeze one published geometry and source in both tools; independently
optimized masks are not matched benchmarks. The tutorial's 2D stage alone
cannot establish 3D parity. Add packet-stack band-edge, alignment-offset,
etch/pitch and low-coupling witnesses using identical fiber mode, overlap
plane and non-overlapping power normalization, not incomparable port metrics.

**Acceptance tolerance: HUMAN_INPUT.** Recommend per-condition absolute
coupling-power fraction difference ≤0.01 and reflected-guided-power fraction
difference ≤0.01 (one percentage point each), spectral peak location difference
≤2 nm on a refined wavelength grid. Apply to every declared perturbation and
the same interval/p10 definition; five samples alone cannot locate a narrow
peak. Near-zero reflection uses absolute fraction error, not relative percent.
These allocate decision error around 0.30/0.10 buyer limits, not process yield.

**Claim boundary:** [common credibility contract](reference-credibility.md).
After accepted Tier 2 evidence, “matches the reference simulator” for this
stack, geometry, spectral band and perturbations; no “matches reality”,
fabricated-device or manufacturing-yield claim without corresponding evidence.

## 6. Output and measurement contract

Five wavelengths: coupled fiber power / incident guided power, reflected guided
power, upward/downward/outward flux with non-overlapping surfaces, absorbed
power and residual; complex TE0 amplitudes with pinned planes/orientation.
Report full tolerance panel, minimum coupling and p10. No average can hide a
mandatory reflection/coupling failure. Reference failures do not count as zero
coupling or a candidate fault. Scalar score/soft-physics leg remains unadopted.

## 7. Construction contract

Prepared Level-0 target: deterministic declarative spectral/tolerance surrogate
trained on permitted public data; reconstruct with exact material/geometry
conventions and finite capability grammar. No runtime permission is registered
here. Training caps require this Challenge's budget study, not Battery's cap.

## 8. Research kit

New grating generator, public normalization/overlap docs and own-seed reference;
coupled-mode/effective-index, permitted-data interpolation and direct/adjoint
search baselines at equal charged query/compute budgets. Assess fdtdx later as
an acceleration/witness route; existing GPU coupler evidence is not transfer
qualification. Protected material never reaches research/pods.

## 9. Evidence plan

Controls and memory feasibility first, then commit selected masks before a
separately registered complete tolerance-panel comparison. Park the scope if a
cheap baseline makes the same decisions adequately. Fresh protected cases,
fabrication/metrology, real process law, GPU spend and training-budget study are
separate. No final hidden-data tuning or yield/reliability inference.

## 10. Readiness and claim record

Current prospective T2: [buyer value/cost scorecard](../value-cost/f06.md)
and [owner framework](../value-cost/README.md). Require at least five feasible
and five distinct near-limit infeasible actions per mandatory stratum. Report
the overall fraction; it is not a gate. Other value checks still require
evidence. Refinement/acceptance remains HUMAN_INPUT; no new runtime authority.
The original fraction-based observations below retain their historical meaning.

**Before any new hidden bank:** the owner-selected [four-check value prerequisite](../question-laws/value-check-v1.md)
requires per-stratum discrimination and meaningful buyer-unit spread, one
complete feasible action, and changing best/equivalent answers. Numeric
thresholds remain HUMAN_INPUT recommendations; receipt **NOT_DEMONSTRATED**.
For this buyer, report coupling/reflection margin intervals on the complete tolerance/wavelength panel,
not a 2D screen or old supermode timing.
No favorable redraw, exposure reset, solver grant or qualification follows.


Requirements and a minimum-feature screen only. Reference adequacy NOT_DEMONSTRATED;
the 256-GiB ceiling is not measured memory demand or available-profile proof.
Next: exact source/port/overlap and build/memory feasibility under stage permission.
No customer demand, fabricated device, process yield or CPO-system claim.
