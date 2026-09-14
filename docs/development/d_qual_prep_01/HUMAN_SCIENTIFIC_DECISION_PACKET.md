# D-QUAL-PREP-01 human scientific decision packet

**Evidence role:** public DEVELOPMENT qualification-candidate evidence

**Authority:** no Wave D selection or qualification

**Recommendation:** `WAIT_FOR_D02_GENERATOR_CONFORMANCE`

**Accountable lead:** Physics/SciML scientific integration lead through issue
#42 (`@harshaa765`); reserved scientific selection/acceptance decisions defer to
the Carbon owner through issue #41.

**Packet state:** `EXPORTED_NOT_ACKNOWLEDGED_NOT_APPROVED`. Export or issue
notification is not proof that the owner received, accepted, or authorized a
run. The historical recommendation above is preserved; the independent restart
events below replace it as a universal blocking label.

**Evidence classification:** `EXPLORATORY_RETROSPECTIVE`. The protocol asserts
that it was frozen before execution, but retained Git history and artifacts do
not independently establish that ordering.

## Primary reference

**Available for review:** twelve-cell initial recovery and periodic closure;
512/1024/2048/4096 quadrature histories; stabilized-phi minima; mean drift;
and primary-to-ETDRK4 discrepancies, all bound to exact cases, settings,
implementation files and environment identity.

**Material finding:** the strongest conditioning-pressure case, cell 7, has
minimum stabilized phi `6.402823860950785e-09`. Its consecutive maximum change
increases from `1.6311709215982573e-07` at 1024-to-2048 to
`2.0598144549049957e-07` at 2048-to-4096. No qualified floor or convergence
claim follows.

**Owner decisions/inputs required:**

1. Authorize and define the alternate-precision and alternate-transform study,
   if these are required for D-03.
2. Define public limiting cases and conditioning/failure-boundary cases that
   are valid for the intended fixed-viscosity envelope.
3. Decide the applicable envelope, evidence sufficiency and uncertainty method
   after reviewing the new results; only the scientific owner may later select
   acceptance limits.

## Independent witness

**Available for review:** four-level joint grid/fixed-CFL histories; mean conservation;
SSPRK3 step counts; primary/witness discrepancy; and requested-time-partition
sensitivity. All 48 joint-refinement states completed and consecutive changes decreased
over the tested sample.

**Material dependencies:** the witness has distinct discretization, time
integration and representation, but shares the governing PDE, public generator,
validation cases, Python/NumPy environment and repository. Code independence is
partial; personnel independence is unknown.

**Owner decisions/inputs required:**

1. Decide whether this partial independence is adequate or commission an
   independently owned witness implementation and review.
2. Authorize a controlled CFL/time-refinement study without changing production
   runtime semantics.
3. Define valid nonconvergence/failure-boundary cases and the later scientific
   rule for interpreting conservation, refinement and primary/witness
   discrepancy evidence.

## Measurement

**Available for review:** accepted C-05 operator identities, unresolved result
semantics, exact two-recipe/three-replica/twelve-case campaign design and the
calibration harness's variance/rank calculations.

**Evidence status:** `EXECUTION_NOT_ESTABLISHED` for the accepted 72-result
matrix. All exact expected member IDs and the empty retained inventory are in
`measurement_floor_sensitivity.json`.

**Unavailable:** the accepted 72-result measurement matrix, measurements under
multiple reference resolutions/settings, D-02-qualified population strata,
stress evidence, censoring frequencies and any qualified uncertainty/floor.

**Owner decisions/inputs required after dependencies exist:**

1. Supply or authorize collection and retention of the exact 72-result matrix
   for both accepted recipes, including every failure and censored result.
2. Authorize a paired reference-resolution/settings measurement matrix.
3. After D-02/D-03/D-04 evidence is reviewed, decide applicability, floor and
   uncertainty policy, decision resolution, repeat sufficiency, rank-stability
   interpretation, censoring treatment and stopping rule. None is selected here.

## Generator

C-07 satisfies the bounded orchestration prerequisite, but D-02 itself is
unselected and unstarted. Before D-05 scientific qualification can proceed,
the owner needs a retained D-02 campaign for support/exclusions, marginals,
joints, conditionals, strata, duplicates, coverage, retry/censoring and
intended-versus-realized population, with exact manifests, seeds, exclusions,
failures, weights and coverage evidence.

The public source population, the 12-case realized readiness sample, the absent
qualified target population and the unsampled public stress population must
remain distinct in the decision.

## Workbench and activation

GOAL-WORKBENCH-04 supports exact C-05 request/result bytes, not this readiness
schema. Bind matching C-05 bytes through that reader and attach this packet via
the existing manual handoff/research-reference route. No native readiness import
is eligible. The Workbench cannot qualify a reference or measurement, activate
scoring, or select a Wave D ticket.

## Prospective bundled source-owner request

This is a request to prepare and decide four separable inputs. It does not
select a D ticket or authorize execution.

### Primary question — exact archived cell 7

**Question:** What explains the refinement/conditioning concern for public EVAL
cell 7, ordinal 0, build 0, case digest
`sha256:a2e8449f9e689af7340d4692e51e73b9e48fbea254a7e3e78de6f2eb356e1185`,
and which observable-specific conclusions can the current implementation
support?

**Competing hypotheses:** precision/conditioning pressure; quadrature or
transform sensitivity; output representation/query effects; or a material
implementation defect. None is diagnosed by the current label or curve.

**Preparation required before any run:** freeze the exact archived coefficients,
viscosity, domain, times `[0, 0.1, 0.25] t_c`, 64-point query and source revision
`ed6047d03cf60db6ce52f03e63040d95c1ea78e4`. The current implementation exposes
power-of-two Cole-Hopf internal grids from 64 through 4096; the archived
512/1024/2048/4096 diagnostic grid may be retained. Alternate precision and
transform are not exposed controls and require the smallest source-owner
extension if selected. Keep cell 7 and negative results; add a small declared
control case only if it distinguishes hypotheses.

**Outputs and discrimination:** retain field-difference quantities separately
from compression, dissipation, event-time or other observable-specific values;
record precision, grid, transform/quadrature path, output representation,
missingness, failures and raw/digest-bearing outputs. A changed effect under one
controlled factor discriminates that hypothesis only; it is not a qualified
error band. Execute only after an actual environment and compute allowance are
recorded. Stop after the frozen bounded grid, or at the first unsupported or
failed control; do not continue until a favorable result appears. This remains
fixed-case diagnosis/developmental evidence, not untouched confirmation.

**Restart event:** a source-owner-frozen protocol with exposed controls,
environment identity, actual allowance, failure handling and stop condition.

### Witness question — separate temporal from grid sensitivity

**Question:** Can time-step/CFL sensitivity be separated from grid sensitivity
for the same public cases and requested observables?

**Preparation required before any run:** keep one source-supported spatial grid,
scheme, case bytes, output points, requested times and max-absolute field
comparison fixed. Use accepted CFL 0.35 as the anchor; the implementation
supports `0 < CFL <= 0.5`, but the owner must select and freeze any additional
levels and compute allowance. Retain every actual time step or an explicit
absence, the advective-plus-diffusive rate, target-time clipping, step count,
failures and output digest. A nominal CFL change that produces the same effective
time-step sequence is not a refinement level. If the control cannot be exposed
without policy change, request the smallest source-owner extension.

**Outputs and discrimination:** report temporal changes separately from the
archived joint grid/fixed-CFL curve. The current decreasing differences are not
an isolated spatial error estimate. Stop after the frozen levels or unsupported
control; no acceptance tolerance or uncertainty coverage is selected. This is
fixed-case diagnosis and possible later calibration input, not confirmation.

**Restart event:** a frozen fixed-grid temporal protocol with owner-selected CFL
levels, verified effective time-step changes and actual allowance.

### Generator question

Does the scientific owner select D-02 and its population-conformance evidence?
Required outputs remain support/exclusion, marginal/joint/conditional, stratum,
duplicate, retry/censoring, intended-versus-realized and exact manifest/seed/
failure/weight/coverage evidence. D-02 blocks formal D-05 population claims, not
application delivery or fixed-public-case diagnosis.

**Restart event:** an explicit owner selection plus a retained D-02 protocol and
allowed resources, or an owner decision that formal D-05 remains unselected.

### Measurement-data question

Can the source owner recover execution receipts and canonical request/result
bytes for every member in the two-recipe × three-replica × twelve-case product
listed in `measurement_floor_sensitivity.json`? If not previously executed, does
the owner authorize a later bounded campaign and its six build prerequisites?
Required outputs are exact candidate build/source/environment/plan/replica
identities, paired reference request/artifact identities, all C-05 requests and
results including failures/censoring, dependency/environment records, commands,
logs, custody locators, byte counts and SHA-256 digests. No synthetic or duplicate
fill is permitted and no compute budget is invented here.

**Restart event:** either verified recovery of all 72 distinct members and
execution provenance, or a separately authorized execution protocol with actual
resources. Partial recovery must remain `PARTIAL_RETAINED` with exact members.

## One-study workflow state

- Assignment: accepted — close out the two existing deliveries without a new D
  campaign.
- Preparation: reviewable — exact historical source, questions, hypotheses,
  controls, missing artifacts and owner routes are named.
- Execution: awaiting evidence — only the four-call cell-7 spot-check was run in
  closeout; no new campaign was authorized.
- Decision: waiting on owners independently — primary/witness/source decisions
  through issue #42, reserved D-02/D-05 decisions through issue #41, and exact
  restart events above. S1 prepares the scientific interpretation; Engineering
  owns delivery and bounded source reproductions. H1 is used only if a named
  ambiguity cannot be resolved through those existing owners.
