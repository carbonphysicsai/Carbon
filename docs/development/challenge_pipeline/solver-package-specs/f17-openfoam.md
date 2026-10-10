# f17 — OpenFOAM full-channel flow and scalar package

Build recommendation; **SPECIFIED / not built / C1 UNMEASURED**. The
[buyer packet](../round1/f17-passive-micromixer.md) controls geometry,
synthetic material constants and selected DEVELOPMENT limits. No new
population, periodic-cell reframe or numerical acceptance is adopted.

## 1. Version and build surface

Recommend **OpenCFD OpenFOAM v2506**, upstream commit
`615aae61d7e95e110ca842ca105c799d10f59178`, from the
[official release tag](https://gitlab.com/openfoam/core/openfoam/-/tags/OpenFOAM-v2506).
OpenCFD v2506 is not Foundation OpenFOAM 13. Earlier route notes referencing
the latter do not establish a compatible executable; freeze this fork choice
with DC before implementation. The
[source directory](https://dl.openfoam.com/source/v2506/) identifies the
OpenFOAM and ThirdParty release archives; their checksums and actual selected
dependency versions are **HUMAN_INPUT: DC**. Use the shared exact Debian
base/snapshot in [README](README.md#1-pin-before-claiming-a-package) as a
compatibility candidate, not a tested port. Freeze wmake/compiler flags,
precision/label width, mesher and any MPI/SCOTCH dependency. Recommend double
precision, serial first; MPI is a distinct later proof/resource shape.

Required installed capabilities: deterministic 3D mesh generation/checking,
laminar incompressible flow, passive advection-diffusion, raw face-flux/field
exports and independent integral extraction. Pin `simpleFoam` with laminar
transport and `scalarTransportFoam`, not an unverified solver-name alias.
The [v2506 scalar source](https://api.openfoam.com/2506/scalarTransportFoam_8C_source.html)
evolves a scalar using velocity face flux and diffusivity. Its
[field definitions](https://api.openfoam.com/2506/solvers_2basic_2scalarTransportFoam_2createFields_8H_source.html)
use `T`, `U`, `DT` and `createPhi.H`. Here `T` represents **dimensionless
concentration c, not temperature**; `DT` has diffusivity units. DC must prove
the chosen steady/time-control configuration from this exact source.

**Required adapter work, not stock-solver claims:** validated CAD/patch naming;
cache identity and fail-closed loading; dimensional exports; flux-weighted
observer; total scalar-flux accounting. Incompressible OpenFOAM pressure is
[kinematic pressure](https://doc.openfoam.com/2312/tools/processing/solvers/algorithm-kinematic-pressure/),
so export Pa as `rho * delta(p)`, with rho pinned; similarly set `nu=mu/rho`.
The cited pressure guide is older documentation; confirm dimensions in the
frozen v2506 build rather than assume cross-release defaults.

## 2. Inputs and flow reuse

Retain the **full 10-mm 3D channel**: base section 300 × 100 µm, packet groove
grammar (20–40 µm depth, 50 µm width, 100–250 µm pitch and registered reversal
period), two equal-flow inlets c=0/1, no-slip walls with zero solute flux,
outlet pressure datum and prescribed total flow. Synthetic rho=998 kg/m³,
mu=0.001 Pa·s; Q=1/3/5 µL/min and D=0.5/1/2 ×10⁻¹⁰ m²/s. Geometry must
include fluid volume inside recessed grooves; no solid-side volume shortcut.
Freeze exact dimensions/BCs from the packet in each deck, not prose defaults.

For one design, solve three independently converged flows, one per Q. Retain
mesh, U, p and **phi face flux**, residuals and pressure/volume integrals.
Then run each of the three D values on each frozen flow. The cache key binds
geometry/mesh/patch hashes, Q, rho/mu, BCs, numerical schemes and flow-solver
image/settings. It may exclude D only after proving passive one-way coupling:
c does not change density, viscosity, forcing or flow. Never scale one flow
to three Q values or reuse a different mesh, even if bulk flow looks equal.

The loader must require the exact retained phi. If stock `createPhi.H` would
reconstruct phi from U when absent, fail before scalar execution instead;
prove which loaded field the solver actually uses. Pin scalar advection,
diffusion, relaxation/stopping and inlet/outlet treatment independently of
the flow. Do not silently recompute U/phi during the scalar solve.

**Launch accounting:** absent proven reuse, nine flow/scalar pairs are 18
solver starts. Proven reuse is **3 flow + 9 scalar = 12**, before controls,
repeats, refinements and failures. Meshing/extraction cost still counts.
Nine conditions are correlated outputs of one design, not nine questions.

## 3. Output contract and independent balances

At x=10 mm export raw outlet c and face geometry/area/orientation, phi and
flow-weighted mean/variance. Use positive axial advective flux to weight the
outlet, with inlet variance 0.25, and export
`M = 1 - sqrt(outlet_variance / 0.25)` **without clipping**. Backflow or a
non-positive normalization is observer-inapplicable pending a separately
approved definition; do not delete negative faces until an attractive answer
appears. Export c extrema/raw fields, Q, Δp in Pa, fluid volume and volume/Q
in seconds; volume/Q is not a measured residence-time distribution.

Conservation is a separate observer: integrate **advective plus diffusive
solute flux** on every boundary with outward signs, and storage change if
transient. Do not use the outlet mixing weight as the solute-balance formula.
Retain inlet/outlet/wall terms independently; zero wall flux is a tested BC,
not an imposed accounting identity. Integrate mass flux separately. Every
normalization, plane, sign and unit is pinned. **HUMAN_INPUT recommendation:**
normalize scalar imbalance by nonzero incoming solute flux and retain an
approved absolute floor for zero-solute controls; never divide by a tiny net
in-minus-out residual.

Retain the packet's selected DEVELOPMENT checks: mass and solute balance
≤0.5%; raw c range [-0.001, 1.001]; independent mesh change ΔM≤0.02 and
Δp≤5%. Buyer gates remain M≥0.8, Δp≤250 Pa, volume/Q≤20 s on all nine
conditions. These thresholds neither qualify the solver nor become new
production tolerances here. Bounded c alone does not prove low numerical
diffusion; demonstrate mesh/advection refinement on a high-Pe witness.

## 4. Smallest smoke ladder

Run only after separate build/run authority; no tests below ran here.

| Stage | Minimal retained proof | What would block the route |
| --- | --- | --- |
| Build | Version/binary hashes; required utilities; one deterministic checked 3D mesh | Missing/version-mismatched capability or invalid mesh |
| Flow/scalar analytic control | Straight duct with registered laminar inlet; analytical developed-flow pressure segment, uniform-c tracer conservation and separated c=0/1 tracer | Unit, patch, pressure or independent-flux mismatch |
| Task observer | One small full-length 3D grooved design, one Q and two D values on the same U/phi; raw outlet observer and actual recessed volume | Missing face flux, backflow-inapplicable observation or scalar-clipping artifact |
| Cache proof | Compare each reused scalar result with a fresh same-input flow/scalar pair; reject wrong mesh/Q cache deliberately | Cache alters the result or silently accepts a mismatched key |
| Diffusion/convergence | High-Pe witness at two independent meshes/schemes; D=0 diagnostic tracer, excluded from P, flags artificial mixing | A “good” M caused by numerical smearing, not transport |
| Repeat | Two clean same-shape repeats, including mesh and observer | Input identity or numerical reproducibility unsupported |

The analytic segment's fully developed assumptions must actually hold; a short
entrance-flow comparison is not a failed Poiseuille law. Uniform-c control
must have zero variance/M=1 analytically; this does not test mixing ability.
For D=0, true advective transport preserves the unmixed concentration
distribution; scheme/refinement sensitivity detects numerical mixing without
pretending D=0 belongs to the buyer population. **HUMAN_INPUT**: analytic
control error tolerance and zero-D numerical-mixing tolerance, recommend
unit-bearing bounds tighter than the packet decision band, approved before
inspection. Refinement must compare flux observers, not just residual logs.

## 5. Sizing hypothesis and adequacy HOLD

Full nine-condition design **CPU-hours UNMEASURED**. Carry the earlier route
panel hypothesis only as **HUMAN_INPUT / ASSUMPTION to test**: p50 0.75 CPU-h,
p95 4 CPU-h; peak RSS p50 4 GiB/p95 16 GiB. These originate in the
[reference-route panel](../round1/reference-route-panels.json), not measurement.
No p95 is established by a tiny
smoke or 5–10-case triage. These are not sizing facts or accepted run caps.
Cache/repeat/control work may increase them; allocated-hours ceilings are
not CPU measurements. DC returns complete-case and per-stage timings and
peak memory, at every mesh rung and resource shape, before bank cost sizing.

Tier 2 target remains matched COMSOL task witnesses and public micromixer
benchmarks under the [credibility contract](../round1/reference-credibility.md).
**HUMAN_INPUT recommendations:** |ΔM|≤0.02, Δp and volume/Q agreement ≤5%
with approved absolute near-zero floors; also compare feasibility/picks and
regret. Exact benchmark decks, material applicability and decision thresholds
need science/customer approval. No Tier is earned by building OpenFOAM.
