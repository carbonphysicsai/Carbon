# BASELINE-AGREEMENT-01 — offline comparators, no official judge changes

Owner selects implementation and bounded local fitting/timing on existing
development panels. This supersedes #864's no-fitting restriction for this
ticket only, not any solver, paid, protected or qualification boundary.

Working engineering decision: reuse design_search task/optimizer/assessment
functions without editing their score/power contracts; add descriptive
comparators under development_comparison. Separate CLOSED_BANK arithmetic
from cross-validation; withhold whole geometry/protocol clusters. All model
settings are fixed before held-out measurement. Gaussian-kernel regression
is a simple fixed ordinary-Kriging-style comparator, not a tuned optimum.

Rejected: treating candidate IDs as geometry, training across skew siblings
of a held-out geometry, five copies of a protocol as independent examples,
selecting hyperparameters from final fold errors, interpreting unresolved
truth or a missing Carbon model as agreement, and zero-cost reference repair.

Missing curve/coordinate/settlement inputs HOLD the affected arm. Diagnostic
interpolation uncertainty is not a certified physical bound. No new limits,
uncertainty floors, exposure, law, security or deployment authority. New
acceptance values stay HUMAN_INPUT. Science/Test Lead retain disposition.

Changes are reversible by removing this isolated comparator module, its tests
and evidence. Leads may supersede this decision/BASELINE-AGREEMENT-01 ticket
and report prospectively; old evidence remains bound to its original inputs.
