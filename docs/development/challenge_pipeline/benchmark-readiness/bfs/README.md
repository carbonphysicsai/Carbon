# BFS readiness build — PUBLIC DEVELOPMENT only

BENCHMARK-READINESS-BUILD-BFS-01. No solver installation/build/run, paid
dispatch, hidden data, bank draw, activation or adoption. #1053 carries the
17 delegated decisions; its merge is required before authority-dependent
registration. This branch starts directly at main, not on #1053.

## Buyer and working reuse map

One recovery contour minimizes duty-weighted mean **total-pressure loss**
over a complete service brief. Every point must meet the drawn reattachment
requirement and show no exit reverse flow. The independent question is the
brief, not one field sample. Limits are not averaged away.

KEEP the neutral design-task judge and #994 decision/pointwise/screen-cost
reporting. WRAP them in `carbon/challenge_pipeline/benchmark_bfs.py` and
`carbon/development_comparison/bfs_baselines.py`. No new runtime Challenge ID.
The shared functions still receive a Challenge/family explicitly where
TRAIN, coverage or novelty depends on it.

## Implemented generator and measurement contracts

- `actions(registration, seed, count)`: monotone Bezier ordinates, registered
  DOFs, physical endpoints and precision. Uniform weakly ordered lattice
  vectors via a stars-and-bars bijection; sorting iid *discrete* ordinates
  would bias the action distribution. Deduplication rejects proposals only,
  not settled NONE_FEASIBLE questions. These are public rehearsal seeds.
- `conditions(..., proposal="P"|"Q")`: REPRESENTATIVE uniform joint
  supported Re_H/Mach/inlet-thickness envelope. Q is exactly 40/20/30/10;
  frontier/transition pools must already be public and registered. Counts
  must support the exact allocation; no fake enrichment or weight repair.
- `questions`: continuous requirements from a frozen, public-calibrated
  interval and one full service brief per draw. Duty weights are separately
  registered. NONE_FEASIBLE is retained, never redrawn; UNRESOLVED is not
  manufactured feasibility. E=1, while power-derived k/m/n/B stay closed.
- `calibration_check`: prospective per-stratum 20–80% pass-rate rule,
  meaningful **registered** margin spread, common feasible design, changing
  winners and five/five within two MUI bands. This does not reinterpret
  sealed evidence or narrow action menus after outcomes. Public calibration
  freezes requirement support before candidate evaluation.
- `deck`: source-pinned SU2 configuration draft, developed-inlet asset
  identity, explicit SST option and observer locations. It is deliberately
  **UNVERIFIED_DECK_DRAFT**, not a runnable/pinned reference package.
- `observe`: local ideal-gas stagnation pressure integrated with signed
  mass flux, loss in Pa and dynamic-pressure normalization, mass residual,
  explicit exit reverse flow and downstream signed-wall-shear roots.
  Reverse flux is not clipped out. The final negative-to-positive crossing
  through the registered window is reported; zeros, truncated bubbles or
  missing samples remain unresolved. Sampling coverage is explicitly
  finite-plane/wall coverage, not a proof of continuum no-backflow.

NASA's shifted surface Cp cannot replace total-pressure loss.
[NASA's case](https://tmbwg.github.io/turbmodels/backstep_val.html) uses
Re_H about 36,000, not the older 50,000 convention; the retained research
pin is 20a39f549dbff988a6accc421ac84dafc4487695.

### Remaining exact registration inputs — no invented numbers

The source proposal does not specify exact spline DOFs/precision or a Mach
interval; the nominal Mach 0.128 is only a source point. Nor does it finish
the edge-radius/expansion-to-mesh geometry mapping. These are explicit
registration/materialization gaps, not automatically covered by a generic
monotone spline. Data Collection must register the full geometry and
developed inlet/closure conventions before generating physical panel tuples.
The draft config requires mesh, inlet and model-audit hashes, but cannot
prove that the mesh implements its contour. Thermodynamic/viscosity laws,
boundary mapping, turbulence inlet format, wall resolution and sampling
quadrature must be verified in the package, not accepted from a flag.

## Code verification and reference adequacy

[Verification contract](verification.json) reuses SU2's pinned
`MMS_NS_UNIT_QUAD`. `manufactured_sources()` derives all four steady
compressible NS conservation sources with SymPy, constant viscosity/Prandtl
and exact boundary states. Unit-quad grids 17/33/65/129 give h-halving.
Expected smooth second-order FV convergence; [SU2's MMS study](https://su2code.github.io/vandv/MMS_FVM_Navier_Stokes/)
documents that behavior. Recommended order band 1.8–2.2 is **HUMAN_INPUT**,
not an adopted numerical criterion. Every conserved field needs volume-L2
and Linf errors, iteration-error separation and last-two-rung orders.
`observed_orders` rejects zero/nonfinite errors and insufficient ladders.

The pinned [config template](https://github.com/su2code/SU2/blob/bc15466602a687d6fb796d5df7a12ce3fde0949a/config_template.cfg)
supports MMS_NS_UNIT_QUAD and explicit SST variants. Laminar MMS does
**not** verify SST. Audit the actual equations/limiters against
[NASA SSTm](https://tmbwg.github.io/turbmodels/sst.html), then verify the
turbulence path, developed inlet and wall treatment. Passing a config text
test is not SU2 parser acceptance or convergence.

Data Collection runs headlessly in the pinned image, retains image/spec/
deck/observer/error identities and feeds #1046's evidence checker and
#1039 readiness item 3. Complete dependencies/image store inventory and
actual code/conservation/convergence evidence remain absent. Convergence:
last-two-rung decision observables differ by <0.5 MUI and pick/verdict stay
unchanged. MUI, conservation acceptance and accuracy band remain closed.
NASA reattachment agreement concerns only that observable, not all-field
physical validation or earned task credibility.

## Public novelty audit — actually run, honestly unresolved

Run (no solver):

```text
python -m carbon.challenge_pipeline.benchmark_bfs novelty --input docs/development/challenge_pipeline/benchmark-readiness/bfs/public-anchor-novelty-input.json
```

The retained anchor is **PUBLIC_ANCHOR_EXCLUDED**, never scored.
Variant decision novelty is **UNRESOLVED_NO_VARIANT_TRUTH**: the published
reattachment value alone is not a complete buyer decision or a cached
loss/separation map for variants. No fabricated public variant outcomes.

`decision_novelty` compares registered neutral-task picks and admissibility
when Data Collection supplies full public witnesses, shortcut predictions,
measured geometry threshold and audit identity. Geometry novelty is
mandatory; Re-only variants cannot rescue a copy. Missing reference,
shortcut coverage or measurement stays unresolved. A source-only distance
or producer Boolean does not qualify novelty. The full rights-audited
catalogue and measured component cutoffs remain registration holds.
The software computes distance against explicit normalized catalogue
descriptors; equivalent geometries must be registered in that catalogue.
Value-equivalent picks need the measured tie scale, not exact-pick equality.

## TRAIN, kit and cheap-method handoff

`train_plan` rejects physical duplicates with panel even at a different
refinement rung. It emits a **PLAN_NOT_TRAINED** public inventory, not solved
TRAIN or rights approval. `domain_coverage` checks explicit action/condition
support and all three decision observables; missing range or observable is
a named gap. Actual kit provisions, TRAIN registration and complete panel
coverage are still required.

The cached coarse-RANS comparator holds out complete physical geometries
across all sibling conditions; coarse/fine source identities must differ.
RBF interpolation uses registered coordinates, never IDs or fine truth;
outside support abstains. Reports include pointwise error, the neutral
verdict/pick/regret and unresolved coverage, measured fit/query times and
#994-style **candidate rankings + screening cost per query**. Acquisition,
refinement, startup, money and retained verification costs are unknown unless
the producer retains them explicitly. No matched Carbon arm means V4 remains
UNRESOLVED; do not call a synthetic interpolation result a value win.

Sudden-expansion loss is only an applicability-restricted correlation
control; it cannot predict reattachment or replace a contour RANS map.
Data Collection must provide applicable **planar diffuser/recovery**
correlations with source envelopes; a round-pipe rule must not silently cover
these geometries. Strong direct RANS/adjoint search remains a legitimate
competitor. The best applicable shortcut, not the weakest one, is required.

## Equal budget and future pilot

[Budget proposal](equal-budget-proposal.json) uses #1047's half/base/double
shape and complete-service-brief units, **ASSUMPTION**, not a run grant.
All arms pay acquisition/calibration, fit, screening, failed launches,
refinement and final all-condition verification. Current #1047's closed
four-family validator/engine needs a BFS extension; it is **not** claimed
implemented by this document or by a JSON proposal.

[EUR10 measurement pilot](measurement-pilot.json): three MMS rungs, three
non-scoring NASA anchor rungs, then four novel nominal/corner/frontier/
transition cost probes. Exact tuples remain closed until the missing
grammar/support/package/novelty inputs are registered and completed/
scheduled reuse checked. Ten launches are a plan, not bank adequacy.
Base 3.8 host-hours = EUR5.206 at the owner's ASSUMPTION EUR1.37/h.
High 8 host-hours = EUR10.96 **exceeds the cap**: stop, retain partial
evidence, report; do not transfer another family's cap. Maximum host time
7.29927 h; allocated 16-vCPU time 116.7883 CPU-h is not actual process CPU.
Record both. No process launched and no cost measured here.

Data Collection owns registration, package/image store, field extraction,
actual CPU/RAM/timing, verification and reuse returns. Test Lead owns MUI,
P calibration, novelty thresholds and power; optimizer owns the additive
equal-budget family route. PR Head owns merge. All seven readiness items
must pass (apart from outputs precisely approved for the pilot itself).
Native fixture tests earn engineering evidence only, never seven-item
readiness, solver adequacy, adoption or qualification.

## Readiness command return

#1039's tool at 98a236bf6d891d4383b85ec0f511949a31a5fbf7 was run against
fetched main f4c422bdcf5b410fe8da3045ce7203ed92f22452 at
2026-10-11T02:21:45Z: **0/7 YES**, all seven UNKNOWN because there is no
BFS public evidence binding yet. This is not seven demonstrated failures,
nor does this unmerged build make any item YES. Register the new binding
after #1039 and this PR merge, preserving the measured/image/kit/TRAIN
holds described above. The equal-budget proposal is digest-bound in #1047's
field shape, but its closed four-family validator still needs optimizer's
additive BFS route; it is not a spend grant or accepted registration.

Native tests: 57 passed (BFS, portfolio and #994 comparator regressions).
Black, Ruff, pipeline validation and diff whitespace checks passed locally;
canonical exact-head CI is the delivery gate, not native-host output.

Integration holds: the branch predates #1047's merged budget registration;
PR Head was asked for a base sync before the BFS registration/replay bridge.
The current neutral plain task aggregates a uniform mean. A nonuniform
per-brief duty-weighted objective needs an explicit matched task adapter;
the duty metadata in the law is not proof that this weighting is implemented
by that judge. Until then do not relabel a uniform-mean comparator as the
complete nonuniform buyer decision. Calibration also rejects a common
value-equivalent pick across all strata, not just identical raw winners.
