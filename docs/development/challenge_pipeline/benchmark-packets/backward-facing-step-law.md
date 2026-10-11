# Step-flow question law — owner proposal

DEVELOPMENT / SPECIFIED, not an executable law. All draws, densities, ranges,
buyer limits, weights, counts and acceptance are HUMAN_INPUT in the
[single decision inventory](backward-facing-step-owner-decisions.json).
Reuse the [packet](backward-facing-step.md) and [custody contract](contamination-contract.md).

## P: a complete service-and-requirement brief

One question asks for **one contour** meeting every mandatory condition in its
service bundle, or a settled NONE_FEASIBLE answer over its registered action
bank. Draw service Re_H/Mach, developed inlet-profile family and the buyer's
required flow/recovery/envelope values within an independently justified
reference support. P's exclusion of published anchors/copies is explicit.
NASA constants and research range hypotheses are not a registered P.

Recommendation: continuous buyer requirements inside accepted intervals, with
an auditable small endpoint/midpoint grid as a diagnostic baseline, not the
entire population. Requirement variation costs no new solves only when all
causal physical inputs and observations are already covered by the bank.
A changed flow or inlet profile needs its own reference tuple; no free unseen
scenario truth. Requirements cannot be conditioned on candidate outcomes.

## Q: diagnostics and near-limit enrichment

Separate nominal and supported envelope corners, separation/reattachment
regime transitions, tight loss/recovery/envelope requirements, copied-anchor
exclusion controls, and cheap-lookup/optimizer failure regions. Q density,
stratum allocations and rejection law are HUMAN_INPUT; choose prospectively.
Record coverage and weight/dependence assumptions, including regions with no
Q support. Diagnostic power comes from Q, **not** redraws that hide difficult
or NONE_FEASIBLE questions. Anchor controls themselves never enter scoring.

## w: buyer weighting versus diagnostic reporting

Buyer usage frequency and the agreed loss aggregation determine w. Recommend
retaining worst-stratum hard constraints, with a buyer-approved mean or worst
total-pressure-loss objective. Neither is selected here; Pa is the proposed
regret unit. Do not copy Q into P or use equal masses just because cases are
balanced. Statistical correction and commercial duty cycle are separate.

## Actions, counts and neutral task mapping

The action set is the packet's approved connected recovery-contour grammar,
discretized/canonicalized only under a registered precision and boundary-action
registration. Include shape/intersection/support validation and the novelty
predicate. The action count **m**, questions per batch **k**, independent
question/window count **n**, exposure **E** and bank **B** are all null.
Research's 32/64/128 *complete-case* planning counts do not choose any of them.

Future mapping to `carbon/design_search/tasks.py`:

| Task field | Required prospective binding |
| --- | --- |
| identity | challenge/contract/action-grammar, reference bank, observer, optimizer/query-budget identities; protected seed remains private |
| actions/candidates | frozen canonical contour bank and order/digest, complete scenario coverage |
| conditions/strata | each physical condition names a stratum; p, q and w are distinct accepted values |
| limits | quantity, Pa or dimensionless/unit contract, direction, buyer value and independently accepted reference band |
| objective | total-pressure loss, Pa, min; aggregate mean or worst remains HUMAN_INPUT |
| secondary/tie_rule | buyer-equivalence tolerance open; registered secondary then bank order for settled ties, not post hoc pick preference |

This is a mapping specification, not a runnable `carbon.design-task.v2` object.
Unknowns must not be replaced with zero to satisfy a schema.

## Frontier, answer diversity and uncertainty

T2(a) working rule: in each mandatory stratum/question family, at least **five
distinct feasible and five distinct infeasible designs within two accepted
refinement bands** on both sides. Numerical band widths are HUMAN_INPUT.
Add registered boundary resolution, never widen the band or prune the action
set to manufacture a pass rate. Overall pass rate is descriptive, not a gate.

Also show a full-scenario feasible answer, meaningful buyer-unit margin spread,
and changing best picks. For each law variant report distinct winners per
batch, frequency/entropy of winner identities, feasible/NONE_FEASIBLE mix,
unresolved/abstention coverage and refinement rate. Expected distinct winners
is NOT_DEMONSTRATED, not inferred from the number of grid combinations. For
a finite bank it is at most min(k, number of feasible winner designs); if the
law gives winner probabilities p_i, the independent-draw expectation is
sum_i [1 - (1 - p_i)^k]. The independence assumption must be justified. Count
NONE_FEASIBLE separately; it is not an extra physical winner.

Intervals overlapping any mandatory limit, close objective/tie regions,
multiple unresolved wall-shear crossings or uncertain scenario completeness
go to a predeclared refinement rung or UNRESOLVED. Counts, accepted error bands
and refinement budget are registered before outcomes. No favorable clipping.
NONE_FEASIBLE is valid **only when every eligible action is settled infeasible**
under the whole question; no redraw. Missing solve/support/novelty, reference
failure, infra failure or an unresolved action prevents that conclusion.

## Exposure, controls and diagnostic return

B = 10n is an existing planning suggestion, not an adopted law for this family;
B counts registered bank units, not automatically solver launches. E is open.
Threshold-only questions consume the original bank exposure and do not renew E
or create fresh evidence. Cross-window power must model reuse/dependence within E.

Four behavior-defined controls: edge-optimist ignores a loss/separation band;
over-cautious rejects resolved feasible contours; sign-error reverses loss or
Cf conventions; lookup/optimizer-aware exploits public maps and geometry/law
structure. They are diagnostic models, not branded straw men. Report (a)
scope/coverage, (b) near-boundary behavior, (c) design verdict/pick/regret,
(d) strata and answer diversity, (e) held-out/reference and cheap-baseline
robustness. Test Lead owns score use, power and every acceptance threshold.
No question/bank draw, reference run, campaign or spending is authorized.
