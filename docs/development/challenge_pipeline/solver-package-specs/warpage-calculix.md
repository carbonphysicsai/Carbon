# D016 — CalculiX full-3D material/process-history extensions

**SPECIFIED / not built / complete-case C1 UNMEASURED**. Keep the
[current packet](../discovery/warpage-packet/PACKAGE_WARPAGE_DESIGN_PACKET.md)
and #941's scope alignment. The job is an approved underfill/solder-stack
choice over complete manufacture/reflow/service history in **full 3D**.
It is not f08's metal cantilever or a thermoelastic snapshot. The Challenge
and its panel have not been adopted/authorised by this specification.

## 1. Reuse and exact candidate pins

KEEP f08's inspected acquisition recipe at
`0f12834226f65cdb317e7407e1e83e68c135801b`, paths
`scripts/dev/reference_packages/calculix/{Dockerfile,build.sh,sources.lock.json}`.
These artifacts are inspectable at that commit but **not present on this
ticket's main base**. Reuse the source recipe, not an assumed available image.

| Item | Recorded candidate identity / limitation |
| --- | --- |
| ccx | [CalculiX 2.23](https://www.dhondt.de/); source `https://www.dhondt.de/ccx_2.23.src.tar.bz2` |
| ccx archive SHA-256 | `9c88385c10fb04f5dc6c4e98027a51bebdd8aee3920e05190d6c1dd08357d6e7`; acquired source-lock identity, not independent publisher authentication |
| SPOOLES | 2.2, SHA-256 `a84559a0e987a1e423055ef4fdf3035d55b65bbe4bf915efaa1a35bef7f8c5dd` from the same inspected lock |
| ARPACK / compiler libraries | Inspected recipe names ARPACK 3.9.1 and snapshot BLAS/LAPACK; exact installed package versions and ABI inventory must be frozen by DC |
| Base | Exact shared Debian digest/snapshot in [README](README.md); platform child digest remains HUMAN_INPUT |
| Runtime shape | Serial SPOOLES; `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `CCX_NPROC_EQUATION_SOLVER=1`; no implicit MPI/parallel equivalence |
| New warpage image | HUMAN_INPUT/null; no full-history binary, observer or material implementation identity yet |

The recipe carries compiler compatibility flags for older C/Fortran sources.
Record each flag and warning, and test numerical controls under the actual
toolchain; suppressing a compiler error is not numerical or security proof.
Replace unbounded build parallelism with explicit authorised build concurrency
when DC implements its new recipe. Do not execute or alter the f08 build here.
WRAP its Gmsh/full-3D region and ledger patterns with a new multilayer mesh;
pin the actual Gmsh version/checksum. Do not transfer its modal projection,
elastic cantilever material or damping proof as warpage truth.

## 2. Feature matrix: what must be implemented/proved

The upstream [2.23 manual](https://www.dhondt.de/ccx_2.23.pdf) and exact source
must be retained with the package. Stock keywords alone are not proof of the
buyer history. The author's [material routine interface](https://github.com/Dhondtguido/CalculiX/blob/master/src/umat_user.f)
illustrates initial/current state arrays; the moving master example is not
evidence that the frozen 2.23 procedure implements the selected law. Inspect
that exact archive and prove each procedure/state export before using it.

| Required capability | Implementation obligation / blocking input | Small feature proof |
| --- | --- | --- |
| Anisotropic, temperature-dependent elasticity/CTE | Calibrated correlated material curves, orientations and reference state; match ccx expansion convention to supplied data | Oriented free body and bonded laminate compared with analytic thermal strain/curvature |
| Cure/shrinkage and relaxation | Rights-cleared kinetic/shrinkage and viscoelastic laws, calibration/domain, consistent tangent and integration-point state; custom compiled law if stock route insufficient | Prescribed cure schedule and relaxation history against independently computed material-point solution |
| Solder plasticity/creep | Named alloy, calibrated temperature/rate law, activation/reference state, integration and state export | Material-point load/hold/unload showing plastic/creep evolution and non-negative dissipation where the law requires it |
| Joint formation/phase transitions | Approved physical treatment of molten/solidifying joint and stress-free formation; preserve surrounding residual state | Reflow/formation/cool-down cycle with approved independent benchmark and explicit state-transfer audit |
| Complete history/restart | No resetting cure, inelastic strain or residual stress between steps; identity/time continuity and restart support proven for selected procedure | Uninterrupted versus interrupted/restarted full history, compare all state fields and observables |
| Thermal input/coupling | Qualified prescribed spatial histories or solved heat equation; mapping/interpolation and feedback as required | Analytic heat/temperature control and mapped-field parity; coupled iteration proof if acceptance depends on feedback |
| Local outputs/contact | Full asymmetric solids/interfaces/supports; appropriate element, integration-point and contact implementation | Twist/asymmetric full-3D fixture, force/moment equilibrium and unsmoothed region outputs |

All customer geometry/ranges, material/history laws, stress-free temperatures,
phase/cure/activation times, supports/contact, moisture/delamination relevance,
thermal feedback, benchmark rights and applicable tolerances are
**HUMAN_INPUT: customer/process/material and science/reference owners**.
Recommend obtaining a complete matched supplier/customer law+history set,
not independent min/max CTE/modulus knobs. No fictitious elastomer/solder
constants are prescribed as buyer truth. Clearly isolated synthetic laws may
test code integration only and cannot populate a graded package bank.

**No silent substitutes:** stock plasticity is not cure/viscoelasticity; a
tiny elastic modulus is not a qualified molten-solder treatment; zeroing
state at each temperature is not process history. If the selected phase,
state or material formulation is unsupported, return ROUTE_UNSUPPORTED/HOLD
as a report finding. A different solver or reduced job needs prospective
owner/science review; do not narrow this packet to 2D or omit history.

## 3. Inputs, state and output contract

Input manifest binds rights-cleared full-3D CAD/regions/action (underfill,
gap/fillet and compatible solder-stack), mesh/element types, every material
law/hash, coordinate/units convention, complete ordered process and service
history, supports/contact, thermal source and mapping, initial residual
state, all mandatory limits and the observer definition. Existing symbolic
W01–W10/S1–S3 slots are **not executable registrations** or three snapshots.
Joint activation and state-transfer maps must have exact time/region identity.
Case serialization and public allow-list remain HUMAN_INPUT, not new IDs.

Export the packet's full time-indexed nodal displacement/temperature and
surface shape; signed external warpage/profiles in mm; named-region
**integration-point** stress tensors in MPa and strain tensors dimensionless;
typed individual limit margins/action outcome. Pin Cauchy/other stress and
total/mechanical/inelastic strain definitions. Also retain coordinates,
undeformed/deformed geometry, orientation, datum/best-fit plane and
rigid-motion transform, integration weights, material-point identifiers,
time/step and relevant cure/phase/plastic/creep/viscoelastic state. Export raw
native results needed to independently reproduce the measurement.

Local stress peaks may not be replaced with smoothed FRD nodal stresses.
Grade-relevant corners/interfaces need an approved finite measurement domain
and uncertainty policy; a singular maximum is UNRESOLVED, not smoothed into
feasibility. Spatially prescribed temperatures are labelled **inputs**, not
predicted thermal performance. Track temporal extrema over ramps/dwells and
formation events, not only step endpoints. Any dissipation/strain-energy
observable is labelled with its constitutive definition and units.

## 4. Independent convergence, conservation and reproducibility

Refine 3D mesh and time/integration increments separately; then vary mapping,
contact resolution and observer surfaces. Repeat the same case/resource shape
in clean directories. Compare final and history extrema **and state fields**;
same final warpage can hide different residual state. Complete-history restart
agreement is mandatory if restart/chunking is used. Approval of a fine
elastic control does not prove an inelastic/history route.

Retain independently integrated reactions and applied forces/moments, heat
inputs/losses/storage if the thermal equation is solved, and mechanical
work/strain energy/dissipation as appropriate to the chosen law/procedure.
For externally prescribed temperatures, report imposed-field consistency and
mechanical equilibrium; do not invent a closed thermal energy balance for a
thermal problem that was not solved. Pin signs, surfaces/time intervals,
units and normalization; include proper absolute floors for unloaded controls.
Never assign a residual term to force closure, normalize by near-zero net
reaction or make one balance imply all the others. f13's extraction mistake
is the reason raw independent integrals are part of the build proof.

**HUMAN_INPUT recommendations**, to approve before inspection: observable
repeat/convergence errors smaller than one verified decision-refinement band;
analytic thermal-strain and equilibrium checks with unit-bearing relative
and absolute tolerances; strict restart-state parity appropriate to each
state variable. No uncalibrated universal 1% threshold is selected. A result
can converge numerically to an inadequate material model; scientific
calibration and Tier 2 remain separate. All selected failures are retained.

## 5. Smallest smoke ladder

1. BUILD_OK: ccx/version/dependency hashes and a serial tiny elastic cube.
   This tests compilation only.
2. FEATURE_PROOF: free thermal expansion, oriented bonded bilayer, material
   point cure/relaxation and solder load/hold/unload. Use analytical/reference
   fixtures; record unsupported state outputs rather than guess them.
3. STATE_PROOF: asymmetric multi-region 3D stack through formation/cure/reflow/
   cooling and service history, uninterrupted versus restarted. Independent
   state transfer and full observer parity. A synthetic fixture proves only
   implementation; physical-task use still awaits calibrated laws.
4. TASK_OBSERVER_PROOF: one approved W/S instance over its complete history,
   full packet exports, separate mesh/time rungs and independent checks. This
   step is **blocked by current customer/material inputs**, not licensed by
   the earlier elastic cube. No feasibility or credibility tier is earned.

These are the minimum feature stages, not a claim that four starts suffice:
repeat/refinement/independent witnesses are additional counted work. DC
pre-registers exact tiny meshes/laws/control answers and per-stage resources
before execution. Time spent compiling a custom law and extracting/verifying
it belongs in total package/case cost, not an invisible setup allowance.

## 6. Cost hypothesis and owner/DC return

The existing panel's **ASSUMPTION 0.03 / 0.12 / 0.45 node-hours low/base/high**
per complete history is preserved. These are **not measured CPU-hours** or
p50/p95. The high 151-equivalent bank scenario already exceeds €100; no new
specification cures that. See the packet's complete ledger and exclusions.

**New HUMAN_INPUT sizing recommendation, ASSUMPTION only:** initial full-task
memory scenarios 2 / 8 / 32 GiB peak RSS, to replace with a forecast from the
actual full-3D mesh, DOFs, nonlinear/contact state and solver factorization.
Do not treat the 24-GiB f08 ceiling as proven for warpage. Complete CPU time
is **UNMEASURED / hypothesis HUMAN_INPUT** until an approved material/history
deck exists. With one active thread, node wall time still includes idle/I/O
and helpers; measure both rather than relabel node-hours as CPU-hours. The
build itself, custom law integration, refinements, cutbacks and retained
failed attempts are additional measured work, not retries granted here.

Return which features pass, which need custom source, source/deck/observer
pins, licence/calibration gaps, complete case times/memory and each remaining
HOLD. Tier 2 needs the packet's independently sourced benchmark and matched
Ansys/Abaqus buyer-tool histories with pointwise **and decision** agreement;
all unit-bearing agreement thresholds remain HUMAN_INPUT. Full history
integrity is required before that comparison. No manufacturing yield,
fatigue lifetime or hardware reliability claim follows from compilation.
