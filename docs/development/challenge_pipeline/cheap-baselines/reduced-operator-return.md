# Stronger f08/f13 comparator arms: Data Collection return

COMPARATOR-CROSS-GEOMETRY-MULTIMODE-01 / DEVELOPMENT tooling. No new reference
solves, fitting on physical panels, builds or spend in this ticket. KEEP the
[shared return checklist](data-collection-return.md) and #994 controls. This
adds a cross-geometry structural ROM and a reduced Helmholtz modal-port arm.
It **does not establish the strongest adequate industry baseline** or a V4
result. The actual projected operators and independent witnesses are not yet
supplied. No completed four-family panel is inferred from aggregate summaries.

## Method and supported buyer decision

For **f08**, interpolate projected stiffness K, mass M, damping C, load B and
observation L in a shared generalized-coordinate basis. Compute
`H(omega) = L (K - omega² M + i omega C)^-1 B` and static compliance, not an
interpolated peak or a held-out geometry's modal cache. B is one unit-force
load; outputs are displacement per force (m/N, converted to mm/N when the
registered observer requires it). Geometry varies in the registered coordinates;
clamps, load/output definitions and material/damping conditions stay in the
same context. Every held geometry is removed across all conditions before
forming the interpolation hull. Basis construction must exclude it too.

[Amsallem and Farhat's parametric ROM paper](https://epubs.siam.org/doi/abs/10.1137/100813051)
describes aligning generalized coordinates before interpolating operators and
addresses mode veering. This implementation is a **bounded engineering member
of that method class**, not its complete matrix-manifold algorithm: convex
simplex weights preserve positive M/K and semidefinite C where the supplied
aligned operators have those properties. Alignment/applicability is a producer
and reference-owner obligation, not proved by a matching hash. Common-basis
provenance, independent whole-geometry FRFs, mode/basis enrichment and frequency
peak refinement must determine whether it is adequate for the actual packet.
No contact/nonlinear, strength/fatigue or unsupported geometry claim is added.

For **f13**, use a pressure-acoustic Galerkin Helmholtz model retaining
interior/chamber modes and modal traces at both ports. Offset geometry is
permitted in the projected operators; it is not replaced with a coaxial pipe.
The online algebra reuses these operators across the frequency band. Port
vectors must come from the same projection as the interior basis, with matched
mode orientation and L2-orthonormal surface shapes. All propagating modes and
the necessary evanescent modes must be retained, with their cutoffs.

[COMSOL's official modal-port explanation](https://www.comsol.com/blogs/using-the-port-boundary-condition-in-acoustic-waveguide-models)
distinguishes amplitude scattering from power, includes higher/degenerate
modes, and defines TL from incident power and **all** outgoing outlet-mode
power. That is the comparator measurement basis, not a claim Carbon matches
COMSOL or experiments. Our explicit no-flow, real-basis, affine-loss algebra
is a restricted implementation; frequency-dependent wall/porous losses,
nonorthogonal lined-port modes, mean flow or missing modal coverage need a
different accepted operator contract, not a silently weakened comparison.

With `exp(+i omega t)`, let `kz = sqrt((omega/c)² - cutoff²)` use nonnegative
real and **nonpositive imaginary** parts (outgoing evanescent decay). The
implemented weak reduced system is:

```text
A = K - omega² M + i omega C + i V diag(kz/rho) Vᵀ
A u = 2 i V diag(kz/rho) a_in
a_out = Vᵀ u - a_in
P_mode = Re(kz) |a|² / (2 rho omega)
TL = 10 log10(P_incident / sum(P_outlet modes))
P_absorbed = u* C u / 2
closure = (P_in - P_out - P_reflected - P_absorbed) / P_in
```

K and M must use the density/sound-speed scaling consistent with this weak
form; V maps pressure coordinates to orthonormal port amplitudes. This formula
is the specified implementation convention, not inherited from a pressure
ratio in an old extractor. Evanescent modes affect A but carry no propagating
power. Incident evanescent/cutoff waves are unsupported. Zero transmitted power
abstains instead of introducing an arbitrary dB floor. The existing packet's
**1% reference energy-closure requirement remains unchanged**; toy closure
does not qualify the basis, physical reference or frequency discretization.

## Closed, prospective sidecar

Use `carbon.development-reduced-operators.v1`, made with `seal_operators`.
Examples are synthetic-only in `tests/cpu/test_reduced_baselines.py`.
No external data are downloaded by this command.

Top-level fields: schema, family (`f08`/`f13`), scope (PUBLIC_DEVELOPMENT or
SYNTHETIC_FIXTURE), exact neutral `export_digest`, ordered `coordinate_fields`,
complete quantity/unit/kind `reducers`, `rows`, `costs`, `operators_digest`.
Hash sealing establishes byte identity, **not** adequacy, rights or public
release permission. Data Collection must return the receipt/pins behind every
source hash and obtain the lane's actual acceptance before interpreting results.

Exactly one row per deduplicated candidate/condition (reused threshold questions
do not create new observations):

- Candidate/condition and literal registered physical coordinates.
- Context hash including boundary/material/fluid/damping/load conventions,
  observer version and common basis hash. No runtime IDs are activated here.
- Independent calibration, query-input, basis-source and response-witness
  SHA256 identities. None of the first three may be a witness artifact hash.
  Provide source bytes/rights/release provenance to the lane owner, not a hash
  invented to pass this syntax check.
- `basis_training_coordinates`: all geometry coordinates contributing to a
  data-derived basis, including geometry mapping/alignment construction.
  Empty means a documented geometry-independent/analytic basis, **not**
  undisclosed training. Any basis containing the held geometry is excluded
  from that fold. A POD basis built from the full test bank is not independent.
- Model: bounded real symmetric K/M/C; f08 additionally B/L; f13 additionally
  V (`ports`), cutoff wavenumbers, inlet/outlet modal ordering, rho and c.
  Common basis/fluid/modal/output layout and provenance must match within a
  context. Producer supplies any congruence transformations, not sorted mode
  labels. Mass is positive definite; acoustic K may be semidefinite.
- Query: increasing positive `frequency_hz`, independently known input scalars;
  f13 also complex incident-mode amplitudes and zero mean flow. Known scalars
  are analytically supplied geometry/material inputs (for example mass/volume),
  never witness-derived dynamic peaks, TL or another output hidden as input.
  State each input's formula/source, units and preparation cost in its receipt.
- Witness: f08 complex compliance curves plus static compliance; f13 full TL
  curve. Witness reduction must match registered neutral observer quantities.
  These arrays enter validation/diagnostics only, never interpolation fitting.

Numeric bounds (128 reduced dimensions, 1,024 rows, 12 geometry coordinates,
4,096 frequency nodes) are implementation resource limits, not science values.
Unsupported larger models HOLD or need an explicitly reviewed implementation
change. Missing full-band/frequency/basis witnesses are not cured by these caps.

## Whole-geometry folds and measurement

Fit/interpolate only same-context, same-basis calibration operators from other
geometries. Scaled simplex interpolation is inside the calibrated convex hull;
insufficient/rank-deficient support, different layouts, singular systems or
outside-hull actions abstain. Boundary holdout abstention is reported, not
discarded. A prescribed independent calibration set beyond the test-panel
edges is needed for full coverage; this ticket does not draw or solve it.

Report exact-lookup replay separately, sampled complex-curve/TL errors,
pointwise quantities, feasible-set and committed-pick agreement, false-feasible
decisions, buyer-unit regret, unresolved coverage and abstention. Task/law and
reference-resolution semantics remain #759/#786's; no scoring/power threshold
is selected. Point predictions are an unqualified cheap screen, not safety
certificates. Same frequency-grid agreement cannot rule out missed narrow
peaks/notches: Data Collection returns independently refined witnesses and
mode/basis/frequency convergence **before** Test Lead accepts the method.

For f08 witness mode crossings, static/mass boundaries, both probes and every
damping condition. For f13 witness original offset extremes, cut-on regions,
degenerate modes, narrow notches and near-5-dB p10 picks. Compare both curve
tolerances and decisions per #767. Unresolved reference findings block affected
truth judgments; do not make candidate failures from them or alter old seals.

## Command and full cost

```text
python -m carbon.development_comparison.reduced_baselines \
  --panel <approved-public-export.json> --expected-sha256 <bytes-sha256> \
  --operators <approved-operator-sidecar.json> --operators-sha256 <bytes-sha256> \
  --output <new-report.json>
```

The command never discovers input directories or launches a reference solver;
output creation refuses overwrites. Only approved public DEVELOPMENT files,
not hidden, tuning, AX42 or protected material. Current ticket runs fixtures
only. Missing operators return HOLD with no fake costs/rankings.

Keep #994's `carbon.development-cheap-screen.v1` per-query CPU/wall timing,
fit cost and candidate ranking for optimizer #998. No optimizer API is changed.
Report source-loading/validation/measurement time separately. Supply actual
original acquisition, operator assembly/projection, basis alignment, reference
refinement, retained verification, RAM and money costs; null is NOT_MEASURED,
not zero. Query/fit cost does not include off-line matrix creation. Charge any
library licence, source preparation, search, failures and reference fallback
as in the shared full-cost contract. No free pre-built ROM for the cheap arm
and no free bank/training for Carbon. Native fixtures do not estimate C2/C3.

A frequency curve still requires one reduced system per frequency, despite one
process and reused matrices. Sixteen 201-node curves are **3,216 reduced
frequency systems**, not sixteen physical reference launches; adaptive nodes
add work. This implementation proves neither a 201× speedup nor a €100 bank.
Test Lead accepts strongest applicable method and adequacy; optimizer runs
matched budgets; owner decides keep/reframe/replace. V4 remains UNRESOLVED
without a matched Carbon arm and full cost/coverage evidence.
