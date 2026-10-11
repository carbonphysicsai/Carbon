# Cost-bounded reference routes for five buyer decisions

**CHALLENGE-REFERENCE-ROUTES-01 / DEVELOPMENT / SPECIFIED.** Propose a
cheaper route, measure it, and ask whether it preserves the buyer's choice.
No reduced route is adopted or scientifically adequate by this document.
All new acceptance/grant choices are **HUMAN_INPUT with recommendations**.
Measured CPU time, memory, route agreement and Tier 2 evidence are
**UNMEASURED / NOT_DEMONSTRATED**. No solver was run or installed.

Basis: merged [#784](https://github.com/carbonphysicsai/Carbon/pull/784)
(`e1f48dbf37af6d8dd8f51433612acef1043aedf3`),
[#776](https://github.com/carbonphysicsai/Carbon/pull/776)
(`63d641b65a7e54ee547c1dd7b2aafece3b4d1366`) and
[#767](https://github.com/carbonphysicsai/Carbon/pull/767)
(`f46fad9e0b5933750af65a2e231270fde897d3f2`). KEEP the
[requirements](requirements.json), five packets and
[reference-credibility contract](reference-credibility.md). The
[panel sheet](reference-route-panels.json) contains proposed case recipes,
hypotheses, caps and unfilled package/evidence slots, **not a runner config**.
Cooling is out of scope; no full cold plate. Battery EV5, sealed journal
sequence 14 and live contract are untouched.

## Decision checks before reference adoption

Three different checks are needed; none substitutes for another:

1. **Numerical controls/convergence:** analytic controls and independently
   varied mesh, time, frequency, mode, PML and observation settings relevant
   to the family. Resolve the same physical problem at each rung.
2. **Reduced versus full-route witnesses:** compare complete buyer panels
   for matched designs, including near-limit contenders and interior controls.
   Compare all contenders in each declared witness bank, not only the reduced
   route's winner. A two-design witness validates only that two-design bank,
   not #776's 16/45/256-design optimum or the whole population.
3. **Tier 2 buyer-tool witnesses:** reproduce the packet's named published
   benchmarks and independently converged, matched customer-task decks in
   the buyer's tool. Same physics, boundaries, observer and normalization;
   self-convergence or agreement between two Carbon rungs is not Tier 2.

Report **pointwise and decision agreement** on the same witness bank: raw
curves/extrema, feasible/infeasible/UNRESOLVED verdicts per design and active
constraints, both best-in-bank picks under a frozen tie rule, and bidirectional
regret in buyer units when both tools accept both picks. A pick infeasible
under the other tool is a verdict mismatch, not finite regret. Neither
absent picks nor two UNRESOLVED verdicts establish agreement. Report
NONE_FEASIBLE and unresolved coverage without redraw; diagnostic Q may enrich
opportunities but never replaces P or invents w.

**Decision-agreement thresholds: HUMAN_INPUT.** Recommend zero *resolved*
feasibility flips on the diagnostic witness bank, and either the same pick
under the registered tie rule or a science-accepted regret allowance. Regret
allowances remain null: no automatic tie band derived from a curve tolerance.
Witness success is scoped evidence, not a guarantee over unsampled designs.
If numerical/error intervals overlap a buyer limit or competing objective,
refine every potentially deciding contender independently of model picks;
otherwise keep the affected verdict/optimum UNRESOLVED. An observed rung
difference is a convergence diagnostic, not a certified uncertainty bound.

Buyer-tool runs are outside producer custody. Witnesses use a **separate,
non-hidden draw from the same task distribution**, or **retired, published
bank cases** with verified release provenance. Never hidden EVAL, STRESS,
quiz or tuning cases, seeds, labels or their derivatives. Freeze diagnostic
Q strata/selection before comparisons, including near-limit and potential
decision-flip regions; retain every selection, failure and uncovered region.
No public surrogate screen inherits hidden answers. A systematic tool gap is
a **reference finding, never a candidate failure**: investigate and version a
reference revision for future batches. **Already-sealed results keep their
original reference identity and are not silently re-scored.**

## f02 — choose more burst energy without overheating

Buyer anchor: top-die spatial/temporal peak **≤95 °C over 120 s**, maximize
additional joules above 20 W; the existing stack, Robin boundaries, two source
patches, nine actions and 24 contexts are unchanged. [Packet](f02-burst-thermal.md).

**Cost rank, lowest first (hypothesis):**

1. One-/three-node RC or POD model: useful screening/control, **not reference
   truth** for local hotspot decisions without separate adequacy evidence.
2. **Recommended measurement route:** graded full-3D Elmer mesh; retain thin
   TIM/interface and patch-edge resolution, coarsen only smooth bulk regions.
   Event-aligned time stepping with internal maximum/crossing search; 0.5-s
   output sampling is not the peak search. Reuse assembly or steady baselines
   only under identical material/boundary identities, with their cost retained.
3. Full-3D finer mesh plus independent time-halving rung. This is the numerical
   witness/fallback, not permission to accept an unresolved coarse result.

Proposed starting meshes are ~30k–100k quadratic elements, then ~200k–800k
for witnesses; these are packaging targets, not known adequate counts. Preserve
layer/source geometry instead of homogenizing the TIM or averaging power.
Elmer's [heat/Helmholtz model manual](https://www.nic.funet.fi/index/elmer/doc/ElmerModelsManual.pdf)
supports the physics routes, not these cost or adequacy hypotheses.

**What can flip:** a coarse surface misses the hot patch, event lag or second
pulse; a schedule falsely passes 95 °C or displaces a truly better-J action.
At matched actions compare top-spatial maximum/curve, crossing/recovery and
joules, not just patch-center averages. Keep the packet's ≤0.5 °C peak and
≤0.5-s crossing refinement requirements and 1-°C unresolved band. Mesh and
time refinements are separate; missing recovery baseline means UNRESOLVED.

**Tier 2 route:** Icepak/Mechanical Power Resistor benchmark plus matched
three-layer rectangular/ramp/two-pulse decks, both Robin regimes and hot
initial state. Packet cross-tool recommendations remain HUMAN_INPUT: ≤0.5 °C
and ≤0.5 s, energy imbalance ≤1%, plus verdict/pick/J-regret reporting. The
independent buyer tool must retain the same synthetic capacities/contact law;
its tutorial settings are not empirical chip data.

## f06 — choose a manufacturing-tolerant 3D mask

Buyer anchor: every one of **9 vectors ×5 wavelengths** has coupling **≥0.30**
and reflection **≤0.10**; maximize fifth-ordered coupling (finite-panel p10).
Finite 8–12-µm width, lateral offsets and fixed taper remain in the problem.
[Packet](f06-grating-coupler.md).

**Cost rank, lowest first (hypothesis):**

1. **2D x/z cross-section FDTD**, 30/20/10-nm ladder, optional effective-index
   comparison: screen pitch/etch/duty/x-offset and nominate witnesses. It
   cannot independently resolve y-offset, finite aperture/taper diffraction or
   width ranking. Do not manufacture those labels with a Gaussian multiplier.
   “Periodic 3D spot checks” means **periodically scheduled 3D witnesses**,
   not periodic transverse boundaries replacing a finite grating. A periodic
   unit cell is another reduced problem, not a full-3D witness.
2. **Recommended full-task measurement route:** full finite-width 3D Meep at
   30 nm; 20 nm on the predeclared witness subset, and 10 nm only if needed,
   forecast to fit and separately authorized. Keep subpixel treatment, incident
   normalization, Gaussian overlap, TE0 reflection, all vectors and wavelengths.
   One broadband launch may cover five wavelengths **only after** source/
   monitor/decay convergence and extraction have been demonstrated.
3. Independently converged full-3D witnesses plus longer duration and doubled
   PML/padding tests. A 10-nm cap is not a proof of memory availability or
   required convergence, and skipping an unavailable rung earns no adequacy.

The [Ansys grating example](https://optics.ansys.com/hc/en-us/articles/360042305334-Grating-coupler)
uses 2D optimization followed by 3D work. That motivates a screen, not
agreement evidence for our finite-width tolerance panel. Meep's
[FAQ](https://meep.readthedocs.io/en/latest/FAQ/)
requires resolution/time/PML convergence, does not provide locally variable
spatial resolution, and gives **96 bytes/voxel as an empty-real-field lower
bound**, excluding PML/DFT and other storage. Its
[mode decomposition](https://meep.readthedocs.io/en/latest/Mode_Decomposition/)
uses unit-power normalization; that does not implement the packet's outgoing
fiber-overlap observer by itself.

For fixed physical domain, 10→30 nm reduces cells by 27 and idealized FDTD
update work by 81; 10→20 nm by 8 and 16, respectively. These are **geometric
work ratios, not measured speedups**; PML, monitor storage, decay and setup
change actual cost. The bare 573M–1.20B 10-nm cells imply **51–107 GiB** at
that 96-byte lower bound before omitted physical padding/PML/monitors. At 30 nm
the same bare-domain lower bound is ~1.9–4.0 GiB; at 20 nm ~6.4–13.4 GiB.
Do not size the machine from these lower bounds. Forecast the complete deck's
per-rank and aggregate RSS, monitors and padding before launching any rung.

**What can flip:** coupling floor, reflection cap or p10 winner due to
finite-width loss, ±1-µm y alignment, minimum-feature discretization or band
edge errors. Include narrow/wide, alignment-extreme, duty/etch/pitch and
low-coupling witnesses; compare every point and whole-panel verdict/pick.
On a diagnostic bank, **all contenders get full 3D**, not only 2D favorites.
Predeclare a periodic audit cadence (recommend each public production batch
and after geometry/deck changes; cadence HUMAN_INPUT). Until accepted
full-scope discrepancy bounds exist, 2D remains SCREENING_ONLY even if a
handful of 3D spots agree. No width/y-offset question is cheap truth by decree.

**Tier 2 route:** packet's published Lumerical 3D grating/inverse-design
project, frozen geometry, then matched finite-stack tolerance witnesses.
HUMAN_INPUT recommendations: absolute coupling/reflection differences ≤0.01,
spectral peak difference ≤2 nm on a refined spectral witness grid, and decision
agreement/regret in power fraction. Neither 2D parity nor five sampled
wavelengths alone establishes resolved spectral peak location.

## f08 — choose a light support without missing a resonance

Buyer anchor: mass **≤0.45 kg**, static compliance **≤0.03 mm/N**, worst-band
dynamic compliance **≤0.15 mm/N** over 80–600 Hz at all three modal damping
ratios; minimize worst dynamic response, then mass. [Packet](f08-resonance-structure.md).

**Cost rank, lowest first (hypothesis):**

1. Beam/low-mode ROM: screen, not a certified rib/relief reference.
2. **Recommended route:** mesh/assemble/static solve once per geometry,
   extract one reused modal basis, project the load/probes and evaluate all
   three damping conditions with adaptive resonance search. Start 12 modes,
   compare 24/48 and extend past 48 if still unresolved and explicitly authorized.
   Track stiffness, mass, static residual flexibility and force/probe modal
   participation. A cutoff above 600 Hz alone does not prove amplitude accuracy.
3. Independent fine-mesh/high-mode/full harmonic witnesses at the same load,
   probes and damping law; direct dynamic-stiffness solves are a cost comparator
   **only if they implement that same constant modal damping**.

For mass-normalized modes, the proposed response is
`u(omega)=sum(phi_j * (phi_j^T f)/(omega_j^2-omega^2+2i*zeta_j*omega_j*omega))`
under the packet's phase convention. This is a proposed linear calculation,
not proof that an acquired ccx build implements every required convention.
Do not substitute frequency-dependent Rayleigh damping for ζ={0.005,0.01,0.02}.
[CalculiX's official distribution](https://www.dhondt.de/) is the package
source; acquisition must demonstrate modal damping/output support or a pinned
projection implementation. If a same-law direct witness is unavailable, use
independently converged high-mode and Mechanical witnesses, report that gap,
and do not claim a direct/modal equivalence check occurred.

The packet already requests 12/24/48-mode rungs. Thus modal superposition may
already be the baseline: **no new modal speedup is claimed**. Measure existing
versus cached/projected implementations with identical outputs. Nominal
process count can fall from five studies to three (static/eigen/one combined
harmonic sweep) if batching is implemented; each damping/frequency evaluation,
factorization and projection remains charged work.

**What can flip:** truncated weakly coupled modes combine at a probe; wrong
modal damping suppresses peaks; coarse frequency sampling misses a narrow
resonance; the lighter support passes falsely or beats the robust one. Compare
static response, full complex FRFs, modal convergence and peak bracket/phase
at both damping extremes and all mandatory scenarios. Keep packet checks:
≤1% eigenfrequency shift, ≤5% peak shift, location ≤min(2 Hz,1% frequency),
≤5° phase at resolved nonzero response; spacing ≤0.1 half-power bandwidth.

**Tier 2 route:** NAFEMS P18.FV4, P18.FV73, R0016.5H plus matched rib/relief
Mechanical witnesses. Existing HUMAN_INPUT pointwise recommendations and
near-zero floors remain; report verdict/pick/regret in mm/N, not an invented
machine-positioning or settling-time claim.

## f13 — choose a compact silencer without hiding low-loss intervals

Buyer anchor: package **≤300 mm /≤140 mm**, interval-weighted band **p10 TL
≥5 dB** over 500–2500 Hz; maximize p10. Minimum TL is a diagnostic, not a
requirement that every frequency exceeds 5 dB. [Packet](f13-compressor-silencer.md).

**Cost rank, lowest first (hypothesis):**

1. Transfer-matrix/retained acoustic modes: screen and strong cost baseline;
   the off-axis neck and chamber modes need separately demonstrated coverage.
2. **Recommended first route:** one mesh and one Elmer Helmholtz process
   sweeping the full 201-point 10-Hz grid. Separate-frequency smoke parity
   at 500/1500/2500 Hz plus analytic port/power controls establishes batching
   equivalence before a full-curve claim. Cache geometry/sparsity/assembly only
   where valid; `A(omega)=K-omega^2 M+boundary(omega)` changes with frequency.
   No assumption that one LU factorization solves all 201 systems.
3. Once dense-sweep parity is demonstrated, propose adaptive sweep starting
   at 50-Hz intervals with mandatory midpoint probes, refining around low-TL
   intervals, narrow resonances, curvature and uncertain quantile mass.
   Dense 201-point and finer 401-point witnesses remain necessary; retain
   common-grid raw complex R/T, power/passivity and interval-width weighting.
   Adaptive may be cheaper than dense, but only measured savings count.
4. Fine mesh and dense independent quadrature/full-route witnesses where
   lower-cost rungs cannot resolve p10 or the winner.

Elmer's [Scanning mode](https://www.nic.funet.fi/pub/sci/physics/elmer/webinar/02-ElmerWebinar-Multiphysics.pdf)
supports parametric studies; its scalar Helmholtz module, ports and per-step
extraction still need a **task-specific batched-deck test**. Capability of a
different acoustic module is not a verified Helmholtz sweep package.

One verified dense sweep changes a 16-design bank from **3,216 process launches
to 16**, but leaves **3,216 frequency systems** before controls/refinement.
The eight-case pilot has 1,608 primary systems, not eight solves. A proposed
adaptive 81–161 samples/curve would mean 1,296–2,576 systems for 16 designs,
not an observed saving or guaranteed resolution. Cap at 601 points/curve in
the proposed grant; if the cap cannot resolve the curve, stop UNRESOLVED.
Warm starts can help or fail; setup, refactorization and extraction are timed.

**What can flip:** coarse/adaptive samples miss a low-attenuation interval,
wrong node weights bias p10, or a chamber mode shifts the best silencer.
Compare adaptive and dense/finer p10/mean/minimum, all lows and resonances,
same two-design witness-bank picks, and dB regret. Refine **unsampled intervals
too**, using midpoint/coverage checks, not just visible extrema. Finite sample
agreement is not proof against arbitrarily narrow hidden features. Preserve
ΔTL ≤0.5 dB at resolved mesh witnesses, resonance shift ≤10 Hz, and p10/mean
quadrature shift ≤0.25 dB. Deep notches need accepted absolute transmitted-power
floors/complex-transfer checks, not clipped dB. TL uses power, not amplitude.

**Tier 2 route:** COMSOL Absorptive Muffler's **unlined reactive** case,
straight duct/single-chamber controls and matched offset two-chamber whole
bands. HUMAN_INPUT cross-tool ≤1 dB and ≤10-Hz recommendations remain, with
verdict/pick/dB-regret. No mean flow, liner gain or noise-compliance extension.

## f17 — choose mixing performance without numerical smearing

Buyer anchor: all **3 flows ×3 diffusivities** have flux-weighted **M≥0.8**,
pressure **≤250 Pa**, volume/flow residence **≤20 s**; maximize worst M.
[Packet](f17-passive-micromixer.md).

**Cost rank, lowest first (hypothesis):**

1. Smooth-channel/network/transport ROM: strong baseline and controls, not
   the grooved-channel truth by declaration.
2. **Recommended route:** graded 3D mesh, retaining groove tips, near-wall
   and scalar-layer resolution; cache each geometry/flow velocity for its
   three diffusivities **only after one-way coupling is demonstrated**.
   Fixed geometry/fluid law implies three flow plus nine scalar jobs instead
   of nine plus nine; only the flow work is saved. Do not rescale one velocity
   field across different flows without a separate demonstrated law.
3. Independent mesh/transport refinement and independently resolved full
   flow+scalar witnesses at maximum Pe, all flow extremes and deciding
   competing grooves. Hold discretization changes separate from mesh changes.

Propose ~200k–600k graded cells then ~1M–3M witness cells, subject to geometry
and scalar-layer fit. Higher-order bounded transport is a candidate, not a
guarantee. The official [OpenFOAM finite-volume scheme guide](https://doc.cfd.direct/openfoam/user-guide-v13/fvschemes)
distinguishes transport discretizations; pin the acquisition package's actual
distribution/version rather than mixing incompatible forks or tutorial settings.

**What can flip:** numerical diffusion inflates M, groove coarsening changes
pressure/volume, and unverified velocity reuse contaminates scalar response.
Compare raw outlet c and positive-flux weighted mean/variance/M, pressure and
hydraulic residence under all nine conditions. Keep mass/solute residual ≤0.5%,
c in [−0.001,1.001], ΔM ≤0.02, pressure shift ≤5%, and a maximum-Pe scalar-layer
witness. **Boundedness alone does not prove low artificial diffusion**.
No clipping/renormalization; backflow invalidates the current observer.

**Tier 2 route:** COMSOL Split and Recombine Mixer and Micromixer benchmarks
plus matched herringbone/high-Pe witnesses. Recompute the packet's flux-weighted
observer from both tools, not tutorial area-weighted scores. HUMAN_INPUT
cross-tool |ΔM| ≤0.02 and pressure/residence differences ≤5% recommendations remain, with
absolute near-zero floors and verdict/pick/M-regret reporting.

## Acquisition packages and immutable pins

Coordination request: [#643 comment 6051116400](https://github.com/carbonphysicsai/Carbon/issues/643#issuecomment-6051116400).
At the inspected main/open-PR snapshot, no accepted task-specific package
PR/head/build/image/deck/extractor pins were available. These **proposed logical
package names are not runtime IDs**. Acquisition owns them; this PR consumes
their future manifest, not a second packaging implementation.

| Family | Required package / proposed release target to reconcile with acquisition | Required feature proof before cost test |
| --- | --- | --- |
| f02 | `f02-elmer-transient-stack`; Elmer `release-26.2.1` candidate | Thin stack/source events/Robin deck, internal peak and separate baseline observer |
| f06 | `f06-meep-grating-3d`; Meep `v1.32.0` candidate with pinned MPB/FFTW/HDF5/MPI | Normalization/fiber overlap, broadband five-wavelength output, 2D omissions, complete RSS forecast |
| f08 | `f08-ccx-modal-support`; ccx `2.23` candidate | Exact modal damping, mass-normalized projection, mode ladder, complex phase and batched damping/frequency outputs |
| f13 | `f13-elmer-helmholtz-sweep`; same Elmer source/build as f02 where compatible | Scalar Helmholtz scanning, identical per-frequency extraction, power/passivity and cold/separate parity |
| f17 | `f17-openfoam-grooved-transport`; acquisition's accepted OpenFOAM distribution | Exact version/fork, groove mesher, velocity/scalar convergence, demonstrated one-way reuse and outlet flux observer |

Release candidates are sourced from [Elmer releases](https://github.com/ElmerCSC/elmerfem/releases),
[Meep v1.32.0](https://github.com/NanoComp/meep/releases/tag/v1.32.0) and
[CalculiX distribution](https://www.dhondt.de/). They are recommendations, not
accepted source/build hashes or installations; no moving `latest` at dispatch.
Do not overwrite an acquisition owner's existing validated target just to use
these suggestions. Return package PR/exact head, immutable source/archive,
dependency lock and compiler/BLAS/MPI options, image digest, mesh generator,
deck/observer/comparison digests, license/rights and analytic smoke results.
The proposal sheet keeps accepted pins **null**. Any missing pin/feature
blocks dispatch; a version string or existing Cooling image is insufficient.

## Eight-case free-CPU panel and cost hypotheses

The sheet specifies **8 public recipe cases per family, 40 total**, deliberately
stratified cost triage Q, not population P or a statistically calibrated p95.
No realized geometry hashes, seeds, solved answers or selected hidden cases.
Acquisition freezes a valid exact deck manifest before observation; no clipping
invalid geometry or replacing slow/failed rows. Near-limit coverage not found
is reported as a gap, not fabricated by threshold changes.

Case units differ and must be retained: f02 one stack/context/waveform action;
f06 one geometry's complete 45-point panel; f08 one geometry's static/eigen/all
three damping-band curves; f13 one complete band curve; f17 one geometry's
complete nine-condition flow/scalar panel. Keep per-vector/frequency/job costs
alongside whole-case totals. Re-run costs, controls and witnesses are separate
from eight primary-case timings; failures and censored rows remain in the ledger.

| Family / primary measurement route | Hypothesized p50 / p95 **process-tree CPU-hours per complete case** | Hypothesized p50 / p95 peak aggregate RSS GiB | What must be measured |
| --- | --- | --- | --- |
| f02 graded 3D transient | 0.10 / 0.50 | 1 / 4 | Mesh/setup, event stepping, peak extraction, steady baseline and refinements separately |
| f06 30-nm full finite 3D, 45 points | 4 / 16 | 12 / 32 | Every normalization/vector, broadband validity, DFT/PML storage, duration and 20-nm witness fit |
| f08 cached modal full band | 0.15 / 0.80 | 2 / 8 | Static/eigen/projection, each damping curve, modal/frequency refinement; compare actual baseline |
| f13 one-process dense 201-frequency curve | 0.50 / 3 | 3 / 12 | Cold mesh/setup and all 201 systems/extractors; adaptive route separately hypothesized 0.30 / 2 CPU-h |
| f17 reused flow + 9 scalar panel | 0.75 / 4 | 4 / 16 | Three flow jobs, nine scalars, no-reuse comparator and high-Pe refinement |

**All numbers above are elicited engineering hypotheses to falsify, not facts,
vendor performance, quotes or measured costs.** They assume one CPU worker
on existing spare x86-64 capacity with at most 8 allocated logical CPUs; actual
CPU model, RAM, affinity and libraries must be recorded. CPU-hours sum user+
system time across all processes/ranks; they are not wall-hours. Node-hours
and allocated CPU-hours are charged independently, including idle/setup and
failures. No linear parallel speedup or conversion `CPU-h/8=wall-h` is assumed.
Use a pinned serial build or one coordinated MPI process group where needed,
with no nested oversubscription or simultaneous case jobs.

These proposed host profiles are cost triage, not the protocol's accepted
`runpod-cpu5c-16vcpu` timing profile. Keep their results in the measurement
ledger; do not populate canonical pipeline timing/rank fields or infer a
protocol-stage advance from these measurements.

Report cold/warm timing phases, process-tree CPU, monotonic wall time, allocated
CPU-time, sampled process-group RSS peak and total cgroup memory peak (separate
metrics; the latter includes charged non-RSS memory), disk/output volume, completed/attempted
condition/frequency counts, exit classification and all failures. A first
repetition to test warm setup is in the cap, not a discarded run. Stop-reason
and lower-bound consumed cost accompany a censored case; **do not compute p95
only from fast survivors**. With eight purposive rows report raw results,
range and descriptive quantiles/strata, not a supported deployment p95.
This is not the completed Foundation Plan **30-case** study. If viable, owner
may separately authorize expansion to that panel with measured estimates.

For the launch tables, **one charged solver launch** is one external solver
invocation, or one coordinated MPI solver process group; it is not one frequency
system and not a count of OS child processes. Record actual ranks/children and
their CPU/memory separately. Mesh/observer helpers consume the same wall/CPU/
memory allowance, even though they are not extra solver launches. Recommend
at most 16 simultaneously live OS processes in the isolated case group, with
all solver ranks still inside the 8-CPU cap; any package needing more must
return an amended proposal, not silently raise the limit. A batched f13 process
does not create permission for unlisted frequency systems.

## Grant proposal — $0 triage first; no automatic paid fallback

**Status: HUMAN_INPUT / NOT_APPROVED; approved allocation=null.** Recommend
the owner's existing AX42 spare CPU capacity if the operator confirms actual
host, scheduling permission and no interference with active reference production;
otherwise an existing laptop at the same explicit safety caps, with its own
non-comparable timing profile. No server order, licence purchase, GPU, RunPod
provisioning, package download/build job or solver dispatch follows from merge.
Package/build work requires its separate bounded ticket and authority.

| Family | Maximum allocated node-hours | Maximum allocated logical-CPU-hours (8 CPUs reserved) | Maximum charged solver launches | Separate work ceiling |
| --- | --- | --- | --- | --- |
| f02 | 2 | 16 | 32 | ≤4,800 internal steps per transient attempt; incomplete event/refinement search unresolved |
| f06 | 8 | 64 | 200 | 144 primary (8×9×[normalization+scatter]), 36 witness, 16 2D screen, 4 controls; no 10-nm free-CPU run |
| f08 | 2 | 16 | 58 | ≤40,000 harmonic frequency evaluations; count static/eigen/mode changes too |
| f13 | 4 | 32 | 20 | ≤7,000 frequency systems, ≤601 points per curve including adaptive additions |
| f17 | 4 | 32 | 132 | 96 primary (8×[3 flow+9 scalar]), 24 refined (2×12), 12 controls/parity |
| **Total, sequential non-transferable caps** | **20** | **160** | **442** | Not a budget for filling all five #776 banks |

Proposed all-in **additional cash cap $0**, one case worker/group at a time,
≤8 allocated logical CPUs and **≤24 GiB total cgroup memory**, including RSS,
charged cache and other memory; all work/setup/failures
included. Cap changes need prospective owner approval; unused allowance does
not transfer or renew. No retry after a failed attempt. Recommend **≤2 wall-hours
per complete-case attempt**, also bounded by remaining family allocation;
forecast mesh/grid memory before allocation and stop before 24 GiB. The f06
hypothesized 32-GiB RSS tail exceeds even this total-memory cap: expected possible refusal/censoring,
not a promise all rows/rungs fit. No swap-assisted completion or automatic
larger machine. Resource exhaustion is reference/infra evidence, never a
candidate fault or scientific infeasibility.

Runs requested: eight primary cases/family, applicable analytic controls first,
predeclared reduced/full-route comparisons, one cold/warm repeat per family
where the launch allowance permits, and refinement witnesses **only within
every cap**. f02's 32-launch plan reserves 8 primary, 16 independent mesh/time,
4 controls, 2 steady baselines, 1 cold repeat and 1 spare (not retry). f08's 58
reserves 40 primary unbatched studies, 10 witness studies (two full five-study
panels) and 8 controls/repeat.
f13's 20 reserves 8 primary curves, 2 fine curves, 2 controls, 1 repeat, 3 separate
frequency smoke runs and 4 adaptive continuations; primary/refined curves share
the 601-point ceiling across continuations, while controls/repeat are also
counted in 7,000 systems.
The f06/f17 decompositions in the table reserve all jobs before evidence;
reuse can save launches but cannot create new unlisted runs. Unsupported
features, exhausted caps or missing controls can leave the panel incomplete.

The sheet freezes the cost-triage witness labels: f02's eight actions (independent
mesh/time checks), f06's nominal narrow/wide pair, f08's long-flexible/relieved-tall
pair, f13's large-offset/clearance-boundary pair and f17's deep-dense/deep-sparse
pair. These are cost/geometry-stratum choices, not known near-limit designs.
If they supply no deciding opportunity, report that support gap; a new near-limit
witness draw needs its own predeclared manifest and available authorization.
For f17, the 12 control/parity launches reserve four flow/scalar pairs (8) and
four reused scalar repeats (4), not another complete no-reuse 18-job panel.
Full-panel no-reuse comparison is not funded here; per-condition parity alone
does not establish reuse adequacy over the whole population.

Buyer-tool Tier 2 execution is **not** in this $0 grant: licences, independently
held benchmark decks and operator access need their own authority. Reduced/full
numerical witnesses here can expose errors, not earn Tier 2 by themselves.
If f06 needs 20/10-nm/high-memory witnesses that cannot fit, return **one exact
conditional grant request**: host CPU/RAM capacity and availability, immutable
deck/rung/list of vectors plus normalization/PML runs, quoted all-in price,
measured/forecast wall/allocated CPU/RSS limits and retained output/ledger plan.
Recommendation for that future request: CPU-only high-memory node, **≤$60
incremental all-in**, ≤12 node-hours on ≤16 allocated CPUs (≤192 CPU-hours),
≤256 GiB total cgroup memory and ≤36 process launches, using the earlier f06 ceilings only as
an *upper proposal*, not unspent/replenished permission. Exact platform/quote,
run manifest, approval and available remaining old allowance are HUMAN_INPUT;
no fallback dispatch until the owner expressly grants this new request.

Before any free or paid dispatch, acquisition/operator must freeze exact
package/deck/panel/observer pins; confirm existing protocol **stage authority**
(the Battery-led protocol remains DEFINING); implement fail-closed wall/CPU/RSS/
launch/system caps and no-retry scheduling; verify capacity/placement, $0 or
quote/spend enforcement, retained artifacts and ledger. A prose cap is not
an enforced runner. This proposal neither moves the family queue nor activates
runtime IDs, changes score weights or authorizes counted/fresh confirmation.

## Owner and science decisions

Smallest next decision: approve or amend the **separate $0 40-case triage
allocation above**, conditional on accepted acquisition pins, enforced caps,
host placement and stage permission. This can measure affordability without
approving any reduced reference as adequate. Science separately accepts route
applicability, convergence/interval policy, witness support, pointwise and
decision thresholds. Missing values remain null and dispatch/adoption fail
closed; independent specification/packaging work may continue.

Deliverables from the acquisition/data team: exact manifests and evidence
ledger; per-case timings/memory/censored results; reduced/full pointwise and
verdict/pick/regret tables with explicit small-bank scope; coverage/failure
gaps; measured proposal for the 30-case stage or the smallest resource grant.
Do not infer capacity for all eight from a successful nominal solve. After
accepted Tier 2 evidence the claim is **“matches the reference simulator”**
for the named settings and envelope, never **“matches reality”** without Tier 3.
PR Lead owns engineering acceptance/merge; owner and science own adoption.
