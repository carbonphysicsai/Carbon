# D-QUAL-PREP-01 human scientific decision packet

**Evidence role:** public DEVELOPMENT qualification-candidate evidence

**Authority:** no Wave D selection or qualification

**Recommendation:** `WAIT_FOR_D02_GENERATOR_CONFORMANCE`

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

**Available for review:** four-level spatial histories; mean conservation;
SSPRK3 step counts; primary/witness discrepancy; and requested-time-partition
sensitivity. All 48 spatial states completed and consecutive changes decreased
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

GOAL-WORKBENCH-04 is not merged into the observed main revision. No Workbench
import is eligible. Even after merge, the Workbench may display this evidence
and missing decisions only; it cannot qualify a reference or measurement,
activate scoring, or select a Wave D ticket.
