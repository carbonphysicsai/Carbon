# AI package warpage rehearsal #2

**REPRESENTATIVE / DEVELOPMENT / SPECIFIED. Not a customer result.** No builds,
solvers, paid execution, protected or AX42 data. One PR against main; no new
runtime Challenge. KEEP [activation kit](../activation-kits/warpage.md),
[full-3D packet](../discovery/warpage-packet/PACKAGE_WARPAGE_DESIGN_PACKET.md)
and [intake model](../../../../Business/research/intake-spec-and-quote-model/INTAKE_AND_QUOTE.md).

## Buyer job and sourced rehearsal inputs

A package/OSAT engineer chooses an approved material/stack, standoff/fillet
and lid/stiffener design that controls coplanarity and stresses throughout
manufacture and service. Its pairing with the cooling Challenge is a shared
AI-package problem, **not** coupled evidence or a claim of customer traction.

| Input | Representative basis | Customer replacement / readiness test |
| --- | --- | --- |
| W01, I02/I05: full 3D architecture | [Amkor's published 63×63-mm ASIC + six-HBM HDFO case](https://amkor.com/blog/thermal-simulation-of-dsmbga-coupled-thermal-mechanical-simulation-of-large-body-hdfo/) connects package deformation to TIM bondline and thermal design. The source does not publish a complete mesh/CAD or all thicknesses. `architecture()` uses this topology; its 0.5-mm substrate, 0.2-mm interposer, die sizes, placements and heights are **ASSUMPTION** for drafting, not Amkor dimensions. | Watertight full assembly, pad/joint arrays, underfill/fillet Boolean geometry, actual layer stack, anisotropy and lid adhesive/contact/fixture; check material-region volumes, connected interfaces, non-overlap and approved actions. No quarter-symmetry restriction for asymmetric service. |
| W02, I06: underfill | [Henkel UF 9000AE TDS, Nov 2024](https://datasheets.tdx.henkel.com/LOCTITE-ECCOBOND-UF-9000AE-en_GL.pdf): below/above-Tg CTE 23/85 ppm/K; DMA storage modulus 13,500 MPa at 25°C and 136 MPa at 250°C. These are source observations, **not** a static elasticity or Prony law. Tg depends on test method. | Same formulation/lot CTE, E/G/K, Poisson/anisotropy, cure kinetics, gel/shrinkage, cure-dependent stiffness, shear/bulk relaxation and shift with units, uncertainty and calibrated domain. A catalogue-only law fails W02. |
| W02, I06: substrate/interposer/die/lid | [Cheng et al.'s process-aware FCPoP study](https://pmc.ncbi.nlm.nih.gov/articles/PMC8432544/) supplies source-bound example properties and process sequencing, but for a **different package**. Nominal Si/Cu/organic labels do not define this package's laws. Numeric production laws remain HUMAN_INPUT. | Supplier stack/directional CTE/moduli and thermal data with matched tests and domain; no transplantation of the FCPoP material calibration as the Amkor case. |
| W02/W03, I06: viscoelastic and solder state | [Open-data assessment](../solver-package-specs/warpage-process-physics/README.md) identifies NIST cure datasets, underfill relaxation tables and solid SAC305 models as **separate** source-bound controls. It finds no complete coherent full-history family. | Coherent cure/shrinkage/relaxation, solid solder and liquid-to-solid joint-formation laws; executable state variables, calibration, restart and applicability. Do not splice unrelated formulations, or replace molten solder by a small modulus. |
| W04, I07/I04: temperature/history | `histories()` follows the TDS's 15/90/15/120-minute recommended cure ramp/holds, then adds **ASSUMPTION** cool-down, 250°C reflow peak/timing and 85°C service with a +20°C asymmetric ASIC case. The TDS's 260°C capability is not an actual customer profile, stress-free temperature or safety limit. | Measured/approved spatial T(t), initial conversion, stress-free/prestress state, joint formation, fixture release, dwell and residual-state continuity. No resetting all regions at reflow. |
| W05, I03/I10: decision/measurement | Applicable metrology zone and signed least-squares datum from the packet; no generic JEDEC limit adopted. | Warpage/coplanarity/stress/temperature limits, allowed zone/aggregation, objective, uncertainty and method acceptance. HUMAN_INPUT; every history must satisfy every hard limit. |
| W06, I08/I09/I11: credibility and baseline | The package specification records f08's CalculiX source-recipe observation; the proposed `reference_packages` lock path is not a main-tree package receipt. Full-history image/UMAT feature proof and independent matched buyer-tool evidence do not exist here. | Current store image observation, immutable law/mesh/observer pins, accepted code verification, convergence, state/balance tests, independent Ansys/Abaqus witnesses and strongest cached FE/response-surface comparator. Tier 2 is a target, NOT_DEMONSTRATED. |

Geometry ranges are **rehearsal assumptions**, low/base/high standoff
0.04/0.06/0.10 mm, fillet 0.1/0.3/0.6 mm, lid 0.8/1.2/2.0 mm. They are not a
customer distribution. Material substitution stays closed until coherent laws.
P/Q/w, deployment mix, thresholds, k, E and B are HUMAN_INPUT, not inferred
from these six diagnostic actions or three histories. Questions are entire
design choices; time increments and regions are not independent questions.

## One-command preparation (prints, never dispatches)

```text
python -m carbon.challenge_pipeline.warpage_rehearsal panel
python -m carbon.challenge_pipeline.warpage_rehearsal decks
python -m carbon.challenge_pipeline.warpage_rehearsal train
python -m carbon.challenge_pipeline.warpage_rehearsal pilot
```

Panel: six actions × three complete histories × two mesh/time rungs = 36
**proposed** tuples. No retained/scheduled index was supplied, so reuse remains
UNKNOWN; deduplication alone is not registration. TRAIN: two different actions
at the same three histories, excluded by physical action/history regardless
of rung/name. No TRAIN set is solved or registered. `kit_domain_check` requires
all panel coordinates, observables **and** eight full-history features; a
geometry-only model kit cannot pass. Public rehearsal identifiers are not
hidden case IDs. No input invents official data.

`deck_draft` names CalculiX's proposed source-lock path and outputs an intentionally
incomplete include/step contract, region layout, units and observer mapping.
The draft is not executable full-package CAD, a fitted UMAT or a proved
process-history reference. `history_hold` keeps dispatch disabled even when
documentary law fields have been supplied: science/operator acceptance remains
separate. Data Collection supplies conforming full 3D CAD/mesh, law routines,
formation state and approved procedures, then retains exact image and state
proofs. Reusing f08's executable does not earn those capabilities.

## Observers, verification and strongest ordinary competitor

`surface_observer` retains signed z residuals after a least-squares rigid
datum plane and reports peak-to-valley mm at the registered surface nodes.
It rejects non-finite, duplicate or collinear support. Use the same registered
zone/sampling at every time increment; retain profiles/sign, time, undeformed
coordinates and worst-history extrema. Coplanarity uses a separately approved
zone, not an arbitrary synonym across surfaces. Local stress is integration-
point history in MPa; no smoothed FRD maximum or unapproved singular corner
becomes truth. Temperature is supplied T(t) unless a coupled model is proved.

[verification.json](verification.json) supplies free-expansion, bimetal/Stoney,
3D manufactured displacement and material-history/restart tests. Toy analytic
tests exercise equations and observers only; no solver has run. The
[CalculiX manual](https://www.dhondt.de/ccx_2.23.pdf) documents the source route,
not this package's feature coverage. Repeat verification after any image/law
re-pin. Prescribed-temperature mechanics does not prove thermal energy balance.

`laminate_estimate` implements scalar A/B/D force-and-moment balance for an
elastic free strip. Equal-layer bimetal and identical-CTE controls have exact
answers. It explicitly cannot predict the 3D ASIC/HBM process history, twist,
contact, cure or viscoelastic response. `comparator_ranking` exports screening
cost/query and ranking for equal-budget consumers, but abstains on full-history
decisions. V4 remains open until a **strong** cached full-history FE / response
surface comparator is supplied and assessed on whole-geometry/history-held-out
folds: pointwise/sign errors, feasibility agreement, pick agreement, regret
in mm or the accepted buyer objective, unresolved/abstention coverage, setup,
fit, queries and retained verification costs. No beating a weak bimetal screen
is advertised as beating the real buyer workflow.

## Budget, pilot and readiness

`package-warpage` is an entry in the existing `BENCHMARK_ROUTES` dispatch
table, with route kind **REPRESENTATIVE_REHEARSAL**, not a published benchmark
or a customer result. It uses `route = BENCHMARK_ROUTES[family]`, preserving
the BFS/MG routes and their main-inspection checks. The elastic strip screen
does not earn a full-history comparator YES; that prerequisite stays PLANNED.

`warpage_budget.proposal()` uses #1047's half/base/double provenance and
time/compute/evaluation caps for direct, model and ordinary-screen arms.
It is a new representative registration identity, preserving EQUAL-BUDGET-V1.
`equal_budget.compare` routes it to its own validator. Proposed comparison
caps (4/8/16 complete-history evaluations; 2/4/8 wall hours; 32/64/128 CPU-h)
are **ASSUMPTION capacity**, neither a measurement nor a grant.

Pilot: analytic/material-point controls plus one complete package history at
two rungs; five equivalent starts, ASSUMPTION 1/4/8 node-hours =
€1.37/5.48/10.96 at the owner's €1.37/node-hour. The high hypothesis **does not
fit €10**, before tax/storage/setup; full cost is NOT_QUOTABLE until physics
inputs exist. Do not truncate a physical history to fit. Owner/DC must freeze
the exact ≤€10 all-in allocation, quote and enforced before-attempt reserve,
stop/refund policy, pins and feature proof; no retries or dispatch from this
proposal. A control-only pilot cannot be priced or claimed as full-task C1.

Readiness: items 1–5 PLANNED (no registration/image/adequacy/kit/TRAIN receipts),
6 PLANNED (screen ready, strongest full-history method missing), 7 comparison
software prepared, with immutable-main inspection determining YES only after
merge. **No claim of 7/7, tested customer result, qualification or launch.**
Next owner/input action: supply a coherent full-history representative material
family and approved package/joint/fixture model; Data Collection owns integration
and eventual verification. Follow [delivery-measurement.json](delivery-measurement.json)
to record actual queue, preparation, verification, baseline, training, independent
test and dossier effort/cost. All actuals are null, never estimated completion.
