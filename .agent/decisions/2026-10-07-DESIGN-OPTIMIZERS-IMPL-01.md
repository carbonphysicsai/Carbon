# DESIGN-OPTIMIZERS-IMPL-01 — registered development optimizer execution

**Authority.** User ticket DESIGN-OPTIMIZERS-IMPL-01, #759's specified-only
optimizer contract, and #764's design-task interface. Scope is #764 missing
items 1, 4 and 7. This decision chooses no Challenge geometry, budget,
population, threshold, scoring policy, qualification or LIVE behavior.

**Working decisions.**

1. Preserve the existing `carbon.design-task.v1` interface for historical
   precomputed fixtures. Runnable registrations use `carbon.design-task.v2`.
   A v2 task cannot enter the old `commit` path, which cannot count failed or
   invalid attempts.
2. The producer registration contains the typed grammar, canonical bank
   actions, optimizer class/version, hidden start IDs, seed and budget. The
   local-search v1 rule visits registered variables in order and the lower
   neighbor before the upper, using first strict improvement. Seeded hashes
   order the registered starts. Execution accepts only a prediction callback
   and model ID; no caller start, gradient or reference input exists.
3. One attempted condition prediction costs one query. An invalid neighbor
   costs one query without calling the model. A model error costs the attempted
   query. The runner checks affordability before beginning each complete
   condition panel. Exhaustive coverage is true only after all bank panels
   complete successfully.
4. The audit runs a second registered optimizer on the same decision and
   budget. It reports path sensitivity separately and cannot replace the
   primary commitment.
5. Cross-model comparison requires explicit `reference_resolved=True` on
   every model's outcome for a question. The mask lists missing or unresolved
   questions for each model and computes diagnostics on the common subset.

**Boundary.** All tests use a hand-made toy bank. Test Lead owns score use,
attacks and statistical power. Challenge-specific grammar, starts, query
budgets and reference banks remain human/producer registrations.
