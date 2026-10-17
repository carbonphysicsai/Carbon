# BATTERY-GUARDED419-CV-SCALE-01

Status: IN_PROGRESS, implementation. Root selects this narrow repair before
SCORELAB-GUARDED419-FULL-CAL-01. Original base main45fb4b7409165445d7e11509ca26588c9ae19b12.
After PR1393 merged, Root transferred sole writer ownership of the worker,
guard and active producer pins to this ticket and reconciled mainbc0b8a0181b62ea53627c0d27be27d889bd82f11
into this branch as bf7d4581fd16deab74d9959f052c6ba90bb3dbc5.

## Concrete defect and unchanged boundaries

Actual original guarded G0 retained three solver-OK30-cycle rows, raw SHA256
a545394478b64e31612abd6b6eb6dfc91215f41980268e7e8c41cd0fb930f1db.
Its original failed calibration receipt remains immutable at SHA256
dc791c2e8fc88e390636314e67102ce9895838ec11d5e69ab22bf63c964b3eaf.
The numerical reduction is compatible. All three trackers stop at first CV,
checked_phases3/181, with CV_EQUATION_TRACKING.

Each saved CV equation is in model.algebraic and its printed form displays a
scaled voltage relation, beginning0.2*(V-4.19). The pinned library creates the current variable
with scale=param.Q and divides processed equations by their variable scale.
Actual nominal capacity is5.0. The extractor compares against unscaled V-target,
and the guard currently compares the scaled equation residual as though in V.

KEEP exact raw4.2, adopted4.19 target, separate1e-6V tracking,30cycles/181phases,
actual algebraic mode, source/input identities, numerical conjunction and all
later-stage gates. REPAIR symbolic scale and residual-unit handling only.
No regex/string acceptance, fitted factor, zero/wrong equation, arbitrary
proportionality, gate relaxation, solver change or historical relabelling.

## Minimum proof and implementation

Authenticate a finite positive constant scale from the actual pinned model,
prove symbolic equivalence of its operative algebraic equation to the registered
voltage relation under that scale, and report/test the residual in volts. Retain
the original normalized residual and source/equation fingerprints separately.

First determine whether a Root-owned pinned-model reconstruction without a
new reference trajectory can honestly bind the saved data. All90 saved CV text
representations are untruncated, but their sparse-matrix display omits numerical
coefficients; text fingerprints are cross-checks, not lossless structural hashes.
Old terminal-state digests cannot replay unavailable states. Reconstruction must
bind the original source, inputs, immutable image/overlay, supported environment
evidence and parameter processing, and establish complete symbolic identity
including matrix entries, domains, indices and dependencies. Map every
row/cycle/phase occurrence to its authenticated rebuilt context and scale.
Matching strings or today's wheel alone cannot establish historical structure.
The actual scale proof is not in the old rows; nominal capacity alone is not
a new PASS. Preserve historical unverified fields. Convert only covered saved
finite residuals by r_V=scale*r_scaled, retaining sign and the normalized value;
apply the same1e-6V threshold without claiming unavailable-state reevaluation.
If essential bindings cannot be established, state the missing witness and use
only a separately source-bound bounded first-triple rerun under Root authority.

Any offline result is a distinct versioned reanalysis that binds original raw
and failed receipt hashes, original execution source, new observer/code/source
and reconstruction evidence. Never overwrite or silently upgrade old records.
T9/CAL/EVAL admission requires authentic compatible evidence under its explicit
new receipt contract; software existence is not release authority.

Expected manifest: existing feasibility02.py, guarded_reference.py and
corresponding producer pins; tests/cpu/test_battery_cv_scale_witness.py;
tests/cpu/test_battery_guarded_reference.py; tests/fixtures/guarded419_t9.py;
this ticket and decision. Fixtures are released with PR1393. Reuse the existing
solver, collector and package; no new execution harness/provider or automatic
historical reanalysis admission is added by the source repair.
Root records the exact build entry point and initialization/algebraic work;
model assembly alone is not proof that no time integration occurred.

The initial PR1396 runtime normalization witness was carbon.battery.cv-equation-normalization.v1.
It requires the actual algebraic key's constant finite positive scale to match
the operative model's nominal-capacity parameter, then compares the processed
equation to (processed Voltage [V] - actual target) / scale with PyBaMM symbol
identity. This includes matrix contents, unlike printed text. Retain the raw
normalized residual; separately multiply by scale for the signed voltage residual
and evaluate the voltage expression at the actual state. The v2 tracking/reduction
report requires both voltage residuals within the unchanged 1e-6 V criterion.
Old rows without this witness remain unresolved; no old receipt is rewritten.

## Validation and maturity

### Actual R4 follow-up: preserve current-key processing context

PR1396 merged as8a86fae7 with all six canonical shards and focused157 PASS;
exact-main integration smoke38840299687 also passed. These are software checks,
not an actual CV interoperability result. Actual R4 stdout6185eabab868494541c1233c3d1e393f09d593fbb266abb6526b04f1c018f31f
built all three models and observed scale/nominal capacity5, but native equation
identity failed on all three. Overloaded division distributes the factor into
the matrix/constant. The public voltage also has current-collector domains;
the actual current-key residual is scalar-broadcast during discretisation.

Prospective amendment: use the independently defined original model voltage,
resolve its coupled variables exactly as the pinned public accessor does,
and require independently reprocessing that voltage to reproduce the public
processed voltage. Process raw voltage minus actual target through the actual
model SymbolProcessor under the operative current key. This reproduces parameter
substitution, scalar broadcast, domains, discretisation and scale in original
order; compare full native identity including matrix data. Never borrow the
operative equation's child/factor, clear domains, fit a ratio, simplify arbitrary
expressions or use approximate equality. The actual scale/parameter and both
voltage residual requirements remain unchanged.

Normalization witness advances to v2 and tracking/reduction reports to v3.
Synthetic controls model both overloaded distribution and the domain mismatch;
wrong coefficients, factor, target, raw/public voltage definition and scales
remain refused. Root's actual pinned-model R6 probe corroborated this exact
construction on all three meshes: complete nine-node native inventories matched,
independent raw-to-public voltage processing matched, scale/capacity were5, and
all30CV/181descriptors per rung were present. Receipt SHA256
a37ce5329452686cfd0d26282d93ef9c8a946414894e842552b9c9ff99bc2dd7;
stdout dd3dee766f85761d542ce018488664fd0cc4ece891efd144fa000144a4e7fb65.
This diagnostic did not run the production observer or an experimental trajectory;
current focused tests and a fresh source-bound full-tracking G0 remain required.
Existing ticket and managed worktree are reused for the bounded follow-up.
The old G0 and R2/R3/R4 actual failures remain unchanged. A new source-bound G0
and matching-source T9 are still required; old8a86 G0 preparation is superseded
until the corrected source is reviewed, checked and merged under Root ownership.

Baseline: exact actual G0 raw/receipt/source inspection and pinned wheel source,
plus retained #1392 canonical65 focused/all-six CI success. No author application
imports, model construction, tests, solver or provider calls. Root runs a finite
canonical reconstruction and focused controls before a ready CI push.
The focused command is ./scripts/dev/canonical.sh pytest -q
tests/cpu/test_battery_cv_scale_witness.py
tests/cpu/test_battery_guarded_reference.py
tests/cpu/test_battery_feasibility02_voltage_contact.py
tests/cpu/test_score_lab_guarded419_t9.py, plus the active producer pin checks.
Controls must include actual positive nonunit scale, wrong/zero/nonfinite or
state-dependent scale, wrong equation with zero residual, RHS-only control,
physical-unit threshold boundaries, source/raw/hash drift and no old-row mutation.
Include same printed matrix shape/different coefficients, a missing fresh
occurrence in the full30-cycle record, wrong multiply/divide conversion and
honest missing-state representation. Any historical reuse separately requires
complete90-occurrence mapping; no such admission is implemented here.
Research R1 receipt4e339f7b81bb1af5c8a6e0d21f764ba0e1add7961f92bfeb27aef0f1fe3a60d7
is incorporated; it supplies no runtime proof or accepted reanalysis.

Completion is conditional on actual scoped tests, exact-head checks and Root
merge; any accepted reanalysis or new G0 is separate actual scientific evidence.
Maturity remains PUBLIC_DEVELOPMENT; no continuous physical certificate,
scientific/security/production/LIVE qualification. Historical map_ref
SYSTEM/AGENT-EXECUTION; Hub retired under current delivery authority.
