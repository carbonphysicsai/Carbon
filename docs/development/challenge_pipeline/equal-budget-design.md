# Equal-budget design replay — battery v3, motor and f02

**DEVELOPMENT tooling, not a measured Carbon advantage.** This replay extends
[`track_b.py`](../../../carbon/design_search/track_b.py)'s reference and charge
separation to the owner-approved three-arm comparison. The reference solver is
the referee: every reported design value comes from its settled full-condition
result. Models and cheap methods only order which candidates to verify.

Run a supplied, digest-bound panel:

```text
python -m carbon.design_search.equal_budget PANEL.json --bootstrap-replicates 2000 --confidence 0.95 --seed 17
```

The flags above illustrate an analysis run, not an adopted confidence policy.
`equal_budget.seal(body)` computes `panel_digest` over the full JSON body.
The report contains aggregates and registration identities, without job IDs,
design IDs, picks or reference values. It gives one curve point per registered
wall/core budget pair. Every point reports conditional mean best verified value
and raw regret in the objective unit, feasible-pick fraction, and the paired
fraction where model+solver strictly improves on solver-alone. The percentile
bootstrap resamples whole `cluster_id` banks. One bank has no interval.
VALUE-BAR-V1 also consumes `paired_verified_value_delta`: the mean
model-screen-then-verify minus solver-alone verified value on the same jobs,
with a 95% cluster-bootstrap interval when requested at 0.95 confidence.
It is null if either arm lacks a verified feasible pick on any job at that
budget. The count of complete pairs is reported so a conditional subset
cannot be mistaken for the whole buyer-job population. The objective
direction determines which side of zero favours Carbon.

The closed input schema is `carbon.design-search.equal-budget-panel.v1`:

- `evidence_class: DEVELOPMENT`; `challenge: battery-v3|motor|f02`;
  `source_digest`, `decision_rule_id`, `cost_basis: MEASURED|ASSUMPTION`;
  `execution_plan: SERIAL_COMPLETE_PANELS` (one candidate's full mandatory
  condition panel completes before the next starts; wall time is additive);
  `registrations` for `solver_search`, `model_screen`, `baseline_screen` and
  `cost_plan`;
- `objective` has `direction: min|max` and `unit`. Battery v3 also requires
  registered `index_weights` for exactly `5,15,25,35,40`, positive and summing
  to one. The replay checks weighted values from every per-band result;
- `budgets` are positive `{wall_s, core_s}` pairs;
- each job has a bank `cluster_id`, a preregistered `solver_order`, complete
  `candidates`, and amortized per-decision `screen_cost` for model and baseline;
- each candidate has a settled `reference` (`FEASIBLE`, `INFEASIBLE` or
  `UNRESOLVED`, with value only if feasible), measured `solve_cost`,
  independently registered `planning_bound` no smaller than measured cost,
  and unique `screen_rank` for model and baseline. Battery references also
  carry all five `per_index` verdict/value pairs. One infeasible band defeats
  the map; an unresolved band prevents a feasible map claim.

Screening cost includes inference and the registered amortized acquisition and
fit cost. The solver arm pays no screen cost. Both resources are hard limits:
the replay stops before an unaffordable complete solve and reports a screen
that cannot fit the budget as over-budget before search. It never uses a
candidate's reference value to choose the next solve. An external registration
must establish that search orders and ranks were fixed before reference
access; a digest computed afterward cannot establish timing on its own.

## Current evidence and what is still needed

The committed [motor counted v2 replay](../evidence/track-b-replay/motor-counted-v2.json)
contains whole-case GetDP cost and reference outputs for one historical
synthetic decision. It is not the revised motor S3 buyer job and provides only
one bank cluster. The battery [Track B adapter](../../../carbon/battery/value/design_search_adapter.py)
addresses an older EV2/EV4 search contract; it is not the five-band v3 bank.
The f02 [buyer packet](round1/f02-burst-thermal.md) registers the objective and
limits but does not provide a complete solved CCX63 bank here. Thus **no real
battery v3, motor S3 or f02 equal-budget curve is claimed by this PR**. The toy
tests exercise all three contract shapes and both objective directions.

Data Collection can use the same schema as soon as CCX63 exports arrive, but
must supply settled whole-programme values, three independently registered
search orders/rankings, measured per-candidate and screen costs, and at least
two independent bank clusters for a bootstrap interval. A single panel gives
a descriptive curve only. If any candidate could still change true best, the
whole report says `UNRESOLVED_PANEL` and prints no curve. Challenge-specific
objective/limit choices, buyer weights and value-equivalence remain with their
registered domain owners. This analysis cannot assert a model is more accurate
than the solver or establish buyer value by itself.
