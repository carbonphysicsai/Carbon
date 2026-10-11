# MG readiness build — full-vector 3D, PUBLIC DEVELOPMENT only

BENCHMARK-READINESS-BUILD-MG-01; one independent PR from main. #1053's
delegated decision record is a merge dependency, not a stacked base.
No solver installation/build/run, hidden material, bank draw, activation or
spend. Source pins and syntax tests are not installed or qualified references.

## Buyer and reuse

The buyer chooses a silicon/air pattern and finite thickness for one fixed
x/y-period hardware brief, maximizing worst required **total desired
order efficiency** while every condition meets reflection and unwanted-power
limits. Desired-order efficiency includes both polarizations; its co-only
component and cross-polarization are separately reported. There is no invented
polarization penalty or new hard limit. A polarization-preserving buyer
variant needs an explicit prospective contract, not silently a new grade.
No claim of dispersion,
fabrication performance or measured commercial advantage.

KEEP `carbon.design_search.tasks`, #994's neutral pointwise/decision reports
and screening-cost/candidate-ranking export. WRAP with `benchmark_mg`,
`metagrating_decks`, `metagrating_baselines` and the additive
`metagrating_budget` comparison registration. No new runtime Challenge ID.
Shared TRAIN, coverage, novelty and comparison paths receive the family.

## Generators and closed physical inputs

- `actions`: explicitly registered two-direction binary tiled mask, reflection
  convention, exact canonical grid, minimum run-width and thickness lattice.
  Finite z and full x/y/z fields are retained; not a stripe or effective-index
  substitute. Tile construction limits freeform action freedom and is itself
  a registration choice, **not silently the approved physical population**.
  Both phases' periodic orthogonal widths are checked; corner/curvature/etch
  constraints require an additional fabrication rule. Source pixel size is
  never treated as a manufacturing minimum.
- `briefs`: P is REPRESENTATIVE joint supported hardware and continuous
  requirement draws. Hardware period changes *between* briefs, never within
  one pattern's service conditions. The retained source is normal-incidence
  Ex at 1050 nm, ideal nSi=3.45 and substrate n=1.45, Py=525 nm.
  The 40–60 degree **outgoing** deflection proposal sets Px from the source
  grating relation; it is not an incident-angle or broadband support claim.
  Q=40/20/30/10 exactly; counts must be multiples of twenty to implement
  the additional 5% total library-failure diagnostics. Public frontier and
  transition pools must be preregistered, not discovered from candidate results.
  w is buyer frequency under P, never diagnostic allocation. E=1; k/m/n/B
  remain closed until public power and cost measurements. NONE_FEASIBLE is
  retained with no redraw, while missing truth remains UNRESOLVED.
- `calibration_check`: each complete matched stratum needs 20–80% resolved
  designs passing under the prospective delegated rule, five feasible/five
  infeasible within two MUI bands, registered margin spread, a common feasible
  action and changing winners. It calibrates public requirements before P is
  frozen; it does not filter exam draws or reinterpret sealed history.

Exact mask DOFs/precision/minimum feature and measured requirement/MUI
intervals are absent from the source proposal. The functions require them;
fixtures are explicitly SYNTHETIC_FIXTURE and cannot establish these values.
Physical panel generation remains closed, not completed from guessed numbers.

## Meep and S4 decks / measurement contract

`meep_deck` emits a CPU Python script with full 3D periodic x/y cell,
z-only PML, substrate-side Ex Gaussian excitation, homogeneous-substrate
normalization, incident-field subtraction on reflection, finite-thickness
binary silicon blocks and separate R/T mode monitors. Explicit time,
resolution, PML and separation controls are package inputs. Each propagating
order is decomposed into both orthogonal polarizations, not band-number guesses.
[Meep's mode documentation](https://meep.readthedocs.io/en/latest/Python_Tutorials/Mode_Decomposition/)
explains the 3D diffracted-planewave basis; the two polarization extractions
are necessary. No unrecorded symmetry halves the cell or normalization.

`s4_deck` emits the matched 2D-periodic, finite-z **full-vector layered 3D**
RCWA script, not a 2D field model. Binary pixels materialize as non-overlapping
rectangles. It retains `GetBasisSet` and `GetPowerFluxByOrder`, checks every
propagating order is present, and Fourier-projects outgoing homogeneous-plane
E/H into co/cross powers. Incident fields are subtracted using a homogeneous
normalization simulation. Normalization uses the matching E/H flux density,
not an assumed unit-cell-area factor; integrated plane-flux ratios are an
independent check. [S4's API](https://web.stanford.edu/group/fan/S4/python_api.html)
defines its flux conventions and field-grid return. Sampling axis, incident
phase, modal direction, factorization and field normalization still require
real analytic tests in the exact image.

`observe` requires **every** propagating R/T order exactly once and both
polarization powers. It reports desired efficiency, total R/T, unwanted T,
cross-polarization, energy residual and order-sum versus plane-flux differences.
Internal power fractions and explicit percentage-point outputs are both
reported; the registered task must use one declared unit consistently.
Negative values are flagged, never clipped/renormalized. Missing or grazing
channels are reference holds, not candidate failures or zero powers.
Refinement and adopted numerical bands are required before acceptance.

Source pins: Meep b08d226ba311a04e59c984e97f3e88dd82bc56d1,
S4 7fd00a231610bff51f5c7de5f723e3956eab7453. Dependency locks, image digest,
operator-store observation, parser/API smoke and matched-material verification
are **not supplied by those pins**. Decks say UNVERIFIED_DECK_DRAFT and are
non-dispatchable. Data Collection owns the runnable package and actual tests.

## Code verification / adequacy

[verification.json](verification.json) follows CODE-VERIFICATION-MMS-01.
`verification_decks(case, controls)` generates both headless solver scripts
and analytic expected values for a normal-incidence lossless Fresnel slab
and zero-contrast periodic grating. Run each requested rung in the pinned
image, capture stdout/actual CPU/RSS/identities and compare every zero/nonzero
order, co/cross channel, plane flux and energy residual. These verify layering,
normalization and order extraction; they are **not exact efficiency truth for
nontrivial silicon patterns**. The y-mirror cross-polarization symmetry check
is another limited analytic constraint, not a complete reference.
`verify_analytic_output` compares retained numerical channels and energy
against exact values and explicit supplied acceptance bands; missing channels
cannot become a pass. Its return states what remains unchecked (image,
convergence, independent plane-flux closure and acceptance authority).

Meep's smooth/interface-treated slab recommendation is second-order with a
1.8–2.2 order band, **HUMAN_INPUT**, excluding roundoff and temporal/PML error
floors. [Subpixel smoothing](https://meep.readthedocs.io/en/latest/Subpixel_Smoothing/)
does not guarantee that order at sharp corners. Record the actual averaging
setting in the image/deck; native syntax tests do not establish it. S4's exact
uniform-layer algebra has no spatial-grid convergence order; patterned Fourier
truncation has **no universal algebraic order**. Its acceptance band stays null,
requiring a harmonic ladder, all-order conservation and matched Meep witnesses.
It would be dishonest to invent a second-order S4 target.

Final solution evidence: last two rungs differ by <0.5 measured MUI and make
the same admissible/value-equivalent decision; independent-route pointwise
and pick/verdict/regret measures are both retained. Cross-tool and conservation
bands, MUI and tie values remain unmeasured/closed. Rebuild/re-pin invalidates
the old image's code-verification applicability, not sealed historical results.

## Public decision novelty — actually run, unresolved

```text
python -m carbon.challenge_pipeline.benchmark_mg novelty --input docs/development/challenge_pipeline/benchmark-readiness/mg/public-anchor-novelty-input.json
```

The three masks at NanoComp testbed a06518872de6ec82bb4511190e544211539f55f1
are PUBLIC_ANCHOR_EXCLUDED. Published desired-order answers lack full matched
variant limits/order truth and a decision-return witness: result
**UNRESOLVED_NO_VARIANT_TRUTH**, not a novelty success.
Freeze the entire rights-audited catalogue (including subsequently published
devices); source pins are not permission to omit known reconstructable masks.

`mask_distance` compares canonical physical occupancy under periodic
translations and only explicitly valid y reflection. It does not admit x
mirroring that flips the desired order. Resampling requires canonical physical
material mapping; a changed grid, period/thickness-only variant or a producer
"novel" Boolean does not rescue a mask copy. FFT cyclic correlation avoids
translation-by-pixel quadratic work. Mandatory measured mask cutoff **and**
a full public reference/shortcut decision comparison are required. Value-
equivalent cached picks still fail decision novelty; abstention is unresolved,
not evidence that the shortcut loses. No hidden/tuning/quiz witness is used.

## Public TRAIN, coverage and cheap competitor

`train_plan` requires explicit public/fixture custody and a registered
`allow_y_reflection` convention. It deduplicates physical action/hardware/
condition (ignoring rung/labels), excludes translated or registered-y-mirrored
copies of the panel, and refuses mixed canonical grids until their physical
material mapping is supplied. X mirroring is not an equivalence. Synthetic
rows retain their synthetic label; a planner does not promote their custody.
It returns PLAN_NOT_TRAINED; rights, registered main tuples, retained/scheduled
reuse and actual solved TRAIN are absent. `domain_coverage` checks registered
mask/feature grammar identity, thickness/period/wavelength ranges and **all**
decision/order/conservation observables. Actual kits and complete coverage
must be supplied by Model Kits/Data Collection; geometry alone is insufficient.

`metagrating_baselines.measure(export, material=..., method=...)` runs library
lookup or a full-output RBF library/map, leaving out entire canonical pattern
groups across conditions. Coordinates are physical descriptors, not IDs;
separate cache/fine sources and full decision quantities are mandatory.
Library support radius is registered; unsupported queries abstain. Holdout
fine truth never enters the fit or ranking. Source efficiency-only retrieval
cannot fabricate reflection/unwanted outputs. Direct converged RCWA/adjoint
search remains a legitimate solver-alone competitor, not a deliberately weak
library substitute.

The #994 reports include pointwise error, feasibility/pick agreement, buyer-unit
regret, unresolved/abstention coverage, actual fit/query timings, retained/unknown
costs and equal-budget candidate rankings/query cost. V4 remains unresolved
without a matched Carbon arm and retained final verification; no positive
advantage is claimed from toy fixtures.

## Budget route and measurement pilot

[equal-budget-proposal.json](equal-budget-proposal.json) is a digest-bound
additive DEVELOPMENT MG registration in #1047's form, with half/base/double
ASSUMPTION caps. `metagrating_budget.validate` reuses #1047 tier/cap accounting;
the neutral equal-budget replay accepts MG and this registration. Historical
EQUAL-BUDGET-V1 remains unchanged and rejects this extension. All arms charge
screening/construction, every failed attempt, all service points/refinements,
normalization and final reference verification; a complete brief is the unit.
This comparison capability is **not runtime activation or spend authority**.

[measurement-pilot.json](measurement-pilot.json) proposes at most 24 counted
solver calls/cases including normalization, on one CPU host, EUR10 all-in.
Base hypothesis 4.2 host-hours = EUR5.754 at the owner ASSUMPTION EUR1.37/h;
high 10 host-hours = EUR13.70 **does not fit**. Enforce the earlier money/time/
RAM cap, retain partial and failures, no retries/budget transfers. Process CPU
and allocated-vCPU hours are distinct. Exact pins/decks/cases/quote/ledger and
the operator grant must precede execution; none occurred here.

`memory_hypothesis` reports actual declared-cell grid arithmetic and explicit
96/192/384 bytes/cell storage assumptions, not measured RSS. DFT/PML/material/
MPI and S4 harmonic overhead are unmeasured. Do not import f06's fine-grid
memory numbers as a measurement of this distinct metagrating cell.

## Delivery/readiness ceiling and next owners

Fixture checks demonstrate software arithmetic and generated Python syntax,
not real solver/parser execution, adequate reference or a tested Challenge.
No native Meep or S4 module was found installed; therefore no smoke solve ran.
Data Collection owns exact registration, packages/images, verification,
public variant truth, TRAIN and cost pilot returns; Model Kits owns complete
coverage; Test Lead owns measured MUI, calibrated P, novelty and power; PR Head
owns merge. No spend unless seven prerequisites are satisfied, apart from
precisely granted pilot outputs. The #1039 readiness count is reported with
its tool/main identity separately; missing public adapter cannot imply YES.

[Readiness return](readiness-return.json): #1039 tool at
98a236bf6d891d4383b85ec0f511949a31a5fbf7, inspected main
cfb60d3d5fdc7c83ecb5ff779470dc5a0856335c, 2026-10-11T02:42:52Z:
**0/7 YES**, all UNKNOWN because no MG public adapter is configured there.
This unmerged branch does not update main's count. Register the new binding
after #1039 and this build merge; do not substitute planned evidence for YES.
