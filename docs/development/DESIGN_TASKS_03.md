# Indexed design decisions (DEVELOPMENT)

`design_search.tasks.indexed_task` registers one decision made of one
mandatory sub-choice for each index value. Battery v3's proposed ambient
charge map motivates the shape: one protocol and cooling level at each of
5, 15, 25, 35 and 40 °C. This implementation supplies only the neutral
contract and toy tests. It registers no battery v3 bank, physics, weights,
tolerance, solver or score use.

## Registration and execution

Each `indices` row gives `index_value`, `buyer_weight`, and a runnable v2
`task`. The subtask owns its action grammar, ordered candidate bank,
conditions, hard limits, optimizer, hidden starts and seed. All subtasks
share objective quantity, unit and direction. Buyer weights are finite,
nonnegative and sum to one. They are a separate measure from the per-subtask
stratum P, Q and evidence weights. Even a zero-weight index remains mandatory
for feasibility.

The parent `query_budget` equals the sum of the subtasks' registered budgets.
`fixed_registered_quotas_in_index_order.v1` visits indices in order and
never lends unused quota between them. Each child optimizer already counts
invalid actions and model failures and stops before an unaffordable full
condition panel. Parent accounting sums those attempts, reports each index,
and claims exhaustive coverage only when every child does. The predictor
receives `(index_value, canonical_action, condition)`; it cannot provide a
start, seed or optimizer path. `run_indexed_optimizer` records all child
commitments and one parent digest before `judge_indexed` receives references.

Hard limits are judged within each index. A failed selected band makes the
whole map `SELECTED_INFEASIBLE`; a weighted objective cannot rescue it.
Missing or uncertain reference truth stays explicit. A weighted mean of
selected and reference-best objectives is available only for a fully
reference-resolved, feasible map. Every index result is retained even when
the whole map fails.

`value_equivalence` requires the objective `quantity`, `unit`, a finite
nonnegative `tolerance`, and rule
`zero_within_absolute_objective_delta.v1`. A per-index or aggregate objective
difference at or below the tolerance has regret zero. A greater difference
has regret equal to the full difference in objective units. Equivalence is
not an uncertainty band: objective near-ties stay resolved when the
reference itself is resolved. Battery's suggested roughly 0.5 minute value
is **HUMAN_INPUT** and has no code default.

## Disclosure and power

`miner_projection` reveals an indexed schema, challenge/contract versions,
index axis and count, public objective, and each subtask's existing public
action/condition/limit projection. The allow-list excludes index values,
buyer weights, task and bank digests, candidate order and IDs, starts, seeds,
reference values and protected identifiers. The producer retains the full
registration.

The existing `power-report` command accepts a sealed bank with
`indexed_power_cases`. Each case has an indexed task and complete ordered
reference panels, one panel per index. Its registered good predictor must
match those panels exactly. The bank also has the ordinary exposure ledger,
case summaries, and registered grid and continuous laws. The report runs
all four behaviour controls through each subtask's hard-limit quantities,
keeps each shared solved bank as one statistical cluster, and returns
aggregate and `index_position` views for P and Q separately. It emits no
case ID, winner, reference value, protected index value or digest pre-image.
Alpha, power target, simulation budget and control severities remain explicit
inputs. This diagnostic grants no score or scientific qualification.

The code freeze includes `indexed.py` and `indexed_power.py`. Historical
runnable v2 task and battery v8 results are not reinterpreted. Test Lead owns
the battery v3 buyer mix, tolerance, question law and power decision before
any real bank can use this development interface.
