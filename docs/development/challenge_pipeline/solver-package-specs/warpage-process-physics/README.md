# Warpage: full-history physics and open-data feasibility

`WARPAGE-PROCESS-PHYSICS-01`; **SPECIFIED**, no solver/build/spend or protected
data. KEEP the [full-3D buyer packet](../../discovery/warpage-packet/PACKAGE_WARPAGE_DESIGN_PACKET.md)
and [package contract](../warpage-calculix.md). This does not adopt warpage,
approve a panel or change its cost prior. [Sources and grades](sources.md)
and the [gap matrix](assessment.json) are documentary, not executable inputs.

**Finding:** implementable open model forms and partial calibration exist.
An honest Tier-2 reference for the **complete customer decision** is **not
demonstrated** by combining those sources. A full matched material/process
set and independent buyer-tool history are HUMAN_INPUT. This is a concrete
data/adequacy HOLD, not a claim that no open route can ever work.

## 1. What can be reused now, and what it does not establish

| Physics needed | Open model / calibration lead | Usable purpose and blocking gap |
| --- | --- | --- |
| Cure evolution | NIST-hosted Phansalkar et al. (2025), dual-reaction kinetics; Tao et al. (2026), diffusion-controlled late cure and linked public dataset | Material-point verification and a source-bound underfill example; not the packet's chosen supplier/lot, shrinkage or mechanical cure law |
| Cure shrinkage and gelation | Cheng et al. (2021) reports manufacturer-supplied EMC shrinkage and ordered fabrication history; NIST cure-stress programme | Public vehicle anchor, not a calibrated generic underfill shrinkage/gel law. Buyer formulation's dilatometry/rheology/cure stress needed |
| Post-cure relaxation | Chowdhury's Auburn dissertation, measured underfill relaxation, Prony shear/bulk and WLF tables | Research material-point relaxation benchmark; cannot mix with a different NIST formulation or extrapolate through cure/reflow |
| Solid solder deformation | Published SAC305 Anand equation/parameter set; independent identifiability study | Candidate viscoplastic solid-alloy control; same nominal alloy is not identical microstructure/history. No liquid or joint-formation law follows |
| Joint formation and residual state | Published process-aware package vehicle; explicit formation/state implementation required | No complete open, buyer-matched formation/calibration dataset found. Liquid/solid reference state and surrounding residual stress need separate proof |

Do not confuse **openly readable** with **openly licensed machine data**.
The ledger records which numeric tables/raw assets were actually located.
The NIST data catalogue supplies file identities; no workbook was downloaded
or calibrated here. Rights-cleared use, full data verification and independent
transcription remain package obligations. Author parameters are source-bound
observations, not adopted buyer constants or uncertainty distributions.

## 2. Proposed constitutive/state contract

The following is an implementation recommendation for science approval, not
new physical truth. Every material family must be coherent, with named
identity, test history, domain, units, fit uncertainty and held-out observations.

**Cure:** integrate the source's actual one/two-reaction system at material
points. For an appropriate fitted autocatalytic form,
`dα_i/dt = k_i(T)*α_i^m_i*(1-α_i)^n_i` with weighted conversion; the 2026
source includes additional diffusion control. Do not conflate these different
laws or initialise an autocatalytic state at zero without handling induction
as the chosen law prescribes. Freeze initial conversion, reaction enthalpy,
gel transition and vitrification model. Heat release needs a coupled thermal
source when consequential, not merely a prescribed final conversion.

**Shrinkage and evolving stiffness:** require measured volumetric chemical
strain versus conversion and temperature, the gel point and modulus evolution.
Convert volumetric to isotropic linear eigenstrain only under the approved
small-strain/isotropy convention (one third is not a universal finite-strain
conversion). Distinguish pre-gel flow from load-bearing stress development.
EMC's reported shrinkage cannot stand in for the action-set underfill. Cure
temperature, Tg and stress-free state are different concepts.

**Relaxation:** generalized Maxwell shear and bulk relaxation, e.g.
`G(t)=G∞+ΣG_i exp(-ξ/τ_i)`, with reduced time `ξ=∫dt/a_T(T,α)` only over
supported thermorheologically simple conditions. Pin WLF/Arrhenius convention,
reference temperature, absolute versus normalized Prony coefficients, shear
versus Young/bulk modulus and positivity/passivity. A single constant Poisson
ratio is a model restriction, not a consequence of a shear table. Post-cure
TTS cannot be assumed valid through an evolving cure state; cure-dependent
relaxation needs its own data and evolution rule.

**Solder:** a calibrated solid-state Anand or approved creep/plasticity law,
with internal deformation resistance/inelastic strain and consistent tangent.
The observed alloy, grain/orientation scale, ageing, thermal/rate range and
loading history must match. Published SAC305 sets can verify an implementation;
they do not validate a buyer's microjoints or fatigue life. A fitted tension
curve alone may not identify all parameters; test load/hold/unload and thermal
cycling on independent curves. Never combine stock creep and Anand in a way
that double-counts the same inelastic mechanism.

**Formation/reflow:** pin alloy solidus/liquidus and a calibrated stress-bearing
transition, wetting/joint geometry, constraint/contact and stress-free joint
configuration at formation. Solid Anand is not molten solder. Numerical weak
stiffness or element birth is only an approximation to be independently checked;
it cannot acquire credibility by converging. At formation, only the physically
justified new joint state is initialized. Existing substrate/die/polymer
stress, conversion and relaxation state **must not reset**. Re-melting may
erase some joint stress, not the entire assembly's history. If a liquid-flow
or intermetallic mechanism changes the grade, omission needs evidence or HOLD.

**Retained state:** record α/gel/cure strain, branch stresses/strains and reduced
time, solder inelastic strain/resistance and phase/activation, reference
configuration, temperature and residual stress at each material point. Keep
step/time/point identities and coordinate frames. Prove uninterrupted versus
restarted equivalence for all state fields and graded extrema; an identical
final warpage alone is insufficient. Output remains full-3D displacements,
warpage, integration-point stress/strain and temperature over complete history.

## 3. Open solver routes: rated by reuse, not by promises

**KEEP/WRAP CalculiX 2.23** at the #947 source/base pins. Its compiled user
material interface/state-variable path is a possible vehicle for cure,
Maxwell and solder laws with consistent tangents and time integration. Inspect
the exact archive: callable arguments, thermal-strain treatment, state output,
cutback/restart and element/procedure support. It is not an Abaqus UMAT drop-in
by assumption. A supported time-dependent procedure is needed for inelastic
evolution. f08's deck does not implement any of these additions. Nothing was
built, and missing keyword/feature support remains ROUTE_UNSUPPORTED/HOLD.

**Alternative integration anchor: MOOSE.** Its versioned
[GeneralizedMaxwellModel documentation](https://mooseframework.inl.gov/releases/moose/2024-11-11/source/materials/GeneralizedMaxwellModel.html)
describes branch updates and required manager/stress pairing. This is useful
open implementation evidence, not a package cure/formation solution. Custom
kinetics, evolving moduli, solder/phase, material activation and verified restart
still need engineering and calibrated data. Freeze an actual source/dependency
revision and build if selected; none is adopted here.

**Independent material-point control: FEniCS tutorial.** Its
[viscoelastic implementation](https://comet-fenics.readthedocs.io/en/latest/demo/viscoelasticity/linear_viscoelasticity.html)
supplies analytical relaxation/creep/recovery checks. The illustrated 2D
test is only a verification control; **not a scope reduction of the full 3D
job**. It supplies neither customer material data nor complete cure/reflow.
No alternative is asserted cheaper, runnable or Tier-2 adequate without proof.

## 4. Calibration and credibility gate

**Public research route:** independently reconstruct a published vehicle with
its coherent materials, full process and observables; verify table/figure
transcription and rights, fit/calibrate only on declared training curves and
reserve independent schedules. Obtain a matched Ansys/Abaqus vehicle run
outside producer custody. Public paper figures without a matched deck and
observer do not prove open-solver parity. Open models enable a prospective
route; they have not earned even this limited Tier 2 here.

**Customer route:** public sources do not supply a complete modern accelerator
package's underfill, solder, orthotropic substrate, supports, spatial history,
activation and approved local limits. Request **one matched, rights-cleared
material + history + witness package** from buyer/process/material owners:

- Named formulations/lots and constituent regions; DSC conversion/enthalpy
  across ramps and isothermal holds, gel/cure-shrinkage and modulus evolution.
- DMA/relaxation and shear/bulk/CTE across cure, temperature, time and ageing;
  uncertainty and held-out schedules, not only a fitted master curve.
- Solder solid-state tests, actual formation/reflow/cooling history, transition
  treatment and reference configuration; full assembly residual-state anchors.
- Complete geometry/support/thermal histories and buyer-tool settings;
  matched warpage profiles and local stress/strain definitions/limits.

This is the smallest **coherent data decision**, not a request to invent four
missing scalar constants. Buyer-supplied confidential data requires rights and
custody approval; it never goes into public research/pods automatically.

Credibility target remains Tier 2, earned **NOT_DEMONSTRATED**. Freeze unit-
bearing pointwise and feasibility/pick/regret tolerances (HUMAN_INPUT) before
witness selection. Witnesses are separate non-hidden draws or provenance-
verified published retired cases, never hidden EVAL/STRESS/quiz/tuning, and
buyer-tool runs are outside producer custody. Numerical convergence and
material fit are necessary, not independent Tier 2. Historical sealed results
keep original reference identity. A systematic disagreement is a reference
finding and prospective revision, not a candidate penalty. Claims remain
“matches the reference simulator”; local stress, fatigue or reality claims
need their own applicable experimental Tier 3 evidence.

## 5. Smallest verification work to register later

No runs are requested or permitted now. Once lawful laws/data exist, DC should
register: (1) cure integration versus independent schedules; (2) thermal/
chemical free expansion and bonded bilayer; (3) Maxwell relaxation/creep/
recovery with separate bulk/shear controls; (4) solder load/hold/unload;
(5) reflow/formation/cooling with audited state transfer; (6) uninterrupted/
restarted asymmetric 3D stack; (7) the matched public vehicle and buyer-tool
decision witnesses. Refine time, 3D mesh and observer independently; retain raw
states, equilibrium/energy terms and failure/resource ledgers.

All tolerances, exact decks, data/image hashes, fit uncertainty, applicability
and cost remain HUMAN_INPUT/UNMEASURED. The package's 0.03/0.12/0.45 node-hour
prior is not evidence for custom full-history physics, and calibration,
implementation and independent witness labour are not free. Full-task
feasibility dispatch remains HOLD until these gates are satisfied. The owner
can commission coherent buyer data or keep warpage as a research candidate;
neither option grants adoption, spend or physical qualification.
