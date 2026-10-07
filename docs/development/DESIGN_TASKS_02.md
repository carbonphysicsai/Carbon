# Design-task disclosure and producer diagnostics (DEVELOPMENT)

`carbon.design_search.task_projection.miner_projection` constructs the
miner-visible task summary from a positive field list. It includes the buyer's
objective and hard-limit values, but omits the task digest, candidate and
condition IDs, bank contents/order, seed, starts, search order, reference data
and all unlisted registration fields. It is not a commitment identity. A
Challenge's separately approved public action/condition contract supplies
the inputs miners may see; a private task record is never serialized directly.

`task_measures.per_stratum_measures` accepts judged **job-stratum** outcomes,
registered P mass, diagnostic Q mass, evidence weight w and a registered
quantile probability. It reports each stratum plus separate P and Q views.
Each stratum's mass is divided over its observed jobs, so uneven diagnostic
sample counts do not silently change P. Rates show their all/resolved/priced
mass denominators. `UNRESOLVED` reference states are retained even when a
particular selected action is known feasible. Quantiles use the left-continuous
weighted inverse CDF with no interpolation. This computes diagnostics only;
Test Lead owns score use and power.

The producer runs:

```text
python -m carbon.design_search diversity-report --bank sealed-bank.json --law registered-law.json
```

The bank input uses schema `carbon.design-search.sealed-bank.v1`, `sealed: true`,
`exposure_limit`, `exposures_used`, and `cases`. Each case has internal `case`,
`state` (`FEASIBLE_EXISTS`, `NONE_FEASIBLE`, or `UNRESOLVED`), `winner` (only for
a fully settled feasible best-in-bank result), `close_call`, and
`refinement_demand`. The producer's integrity digest is `seal_digest` over the
remaining canonical JSON. This digest detects alteration; it does not prove
reference adequacy or confer a trust signature.

The law input uses schema `carbon.design-search.question-law.v1`, `kind`
(`grid` or `continuous`), `draw_model: iid_with_replacement`, `batch_size`,
`bins`, `mass_l1_error_bound` and `registration_digest`. Each bin maps to an
internal bank case and has `p_mass` and `q_mass`; each mass set sums to one.
For a grid, bins are enumerated question cells and the integration-error bound
is zero. For a continuous law, bins are disjoint outcome-homogeneous regions
whose masses have already been integrated under the registered P and Q
densities; `integration_evidence` is required. The report does not infer a
continuous law from discrete grid atoms. Actual values, density, supported
requirements, observer and refinement rules remain producer registration
decisions under #776 and are `HUMAN_INPUT` here.

For each law, the report sums winner masses by bank action and computes
`sum_a [1 - (1 - mass_a)^batch_size]` independently under P and Q. It reports
the feasible/NONE_FEASIBLE/UNRESOLVED mix and close-call/refinement-demand
probabilities over **all draws**. When bank exposure remaining is below the
registered batch size, it reports the shortage and leaves expected batch
diversity null. The L1 mass-error bound yields a conservative `k × bound`
error bound for the winner expectation. The output is a closed aggregate
schema: no case IDs, winners, requirement vectors, reference values, law
digest or protected identity is printed. It is a producer-side diagnostic,
not a qualified population estimate or permission to draw a batch.

`task_freeze.with_design_task` wraps a `SearchAdapter` with the task digest
and all new code paths. Calling the existing `experiment.freeze` and `pilot`
with that wrapped adapter pins and rechecks the code. Legacy Motor V2 and
cooling adapter paths remain unchanged, preserving their historical freeze
identities. `query_cost.QueryCostRecorder` appends one measured
allocated-core-seconds charge per attempted optimizer query, including invalid
actions and model failures; it reconciles against the deterministic query
counter. Hardware route and allocated cores are producer inputs. No USD rate
or solver/query conversion is invented.
