# BATTERY-GUARDED419-CV-SCALE-01

Status: IN_PROGRESS, read-only diagnosis and contract. Root selects this narrow
repair before SCORELAB-GUARDED419-FULL-CAL-01. Base main45fb4b7409165445d7e11509ca26588c9ae19b12.
PR1393 retains the shared worker/guard/producer until Root transfers ownership;
this ticket does not edit those files before that event.

## Concrete defect and unchanged boundaries

Actual original guarded G0 retained three solver-OK30-cycle rows, raw SHA256
a545394478b64e31612abd6b6eb6dfc91215f41980268e7e8c41cd0fb930f1db.
Its original failed calibration receipt remains immutable at SHA256
dc791c2e8fc88e390636314e67102ce9895838ec11d5e69ab22bf63c964b3eaf.
The numerical reduction is compatible. All three trackers stop at first CV,
checked_phases3/181, with CV_EQUATION_TRACKING.

Each saved CV equation is in model.algebraic and equals a scaled voltage
relation, beginning0.2*(V-4.19). The pinned library creates the current variable
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
new reference trajectory can honestly bind the saved data: all90 CV equations
are complete/untruncated, with one exact expression SHA per rung, signed
residuals and independent raw voltage observations. Reconstructed symbolic
equations and source/parameters must match every saved fingerprint. The actual
scale proof is not in the old rows; nominal capacity alone is not a new PASS.
If reconstruction cannot establish it, state the exact missing witness and use
only a separately source-bound bounded first-triple rerun under Root authority.

Any offline result is a distinct versioned reanalysis that binds original raw
and failed receipt hashes, original execution source, new observer/code/source
and reconstruction evidence. Never overwrite or silently upgrade old records.
T9/CAL/EVAL admission requires authentic compatible evidence under its explicit
new receipt contract; software existence is not release authority.

Expected manifest after ownership transfer: existing feasibility02.py,
guarded_reference.py and corresponding producer pins; exclusive CV-scale tests;
one small witness/reanalysis helper if necessary; this ticket and decision.
Update affected synthetic fixtures only after their writer is released. Reuse
the existing solver, collector and package; no new execution harness/provider.

## Validation and maturity

Baseline: exact actual G0 raw/receipt/source inspection and pinned wheel source,
plus retained #1392 canonical65 focused/all-six CI success. No author application
imports, model construction, tests, solver or provider calls. Root runs a finite
canonical reconstruction and focused controls before a ready CI push.
Controls must include actual positive nonunit scale, wrong/zero/nonfinite or
state-dependent scale, wrong equation with zero residual, RHS-only control,
physical-unit threshold boundaries, source/raw/hash drift and no old-row mutation.

Completion is conditional on actual scoped tests, exact-head checks and Root
merge; any accepted reanalysis or new G0 is separate actual scientific evidence.
Maturity remains PUBLIC_DEVELOPMENT; no continuous physical certificate,
scientific/security/production/LIVE qualification. Historical map_ref
SYSTEM/AGENT-EXECUTION; Hub retired under current delivery authority.
