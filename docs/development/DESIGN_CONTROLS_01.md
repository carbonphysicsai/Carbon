# Design controls and power diagnostics (DEVELOPMENT)

This ticket adds behaviour-defined synthetic predictors to the registered
`design_search.tasks` interface. They are producer-side attacks used to test
whether a design-question distribution can distinguish particular wrong
behaviours from an exact-reference predictor. They are not miner submissions,
Challenge physics, score policy or qualification evidence.

## Working contract

The old battery `panel.py` stays unchanged. A neutral output-operation adapter
must reproduce all five historical battery controls exactly on the same
reference output records. This parity does not reinterpret past runs.

Task controls operate on a signed hard-limit margin: positive means passing,
negative means violating. Edge optimism mirrors near-negative margins to the
passing side; over-caution mirrors near-positive margins to the failing side;
localized sign error flips the margin within a predeclared action/stratum
region; and path or lattice awareness is accurate on registered search points
and optimistic elsewhere. Each severity and selected limit quantity is a
registered input. The path is obtained from a known-good run of the frozen
optimizer, never from a caller-supplied start.

`power-report` accepts one sealed bank containing task registrations and
reference panels for its internal question cases, two registered laws (grid
and continuous), registered controls and a registered exact-reference
predictor table. The producer supplies alpha, target power, simulation seed,
replicate count and maximum batch size. No statistical level or control
severity has a code default. Every model uses the same registered optimizer
and query budget per question. Unresolved questions remain in draw mass and
are reported, but do not count as resolved evidence.

The report provides separate P and Q views for each law. It gives aggregate
false-feasible, regret and abstention outcomes and a per-metric estimate of
the first batch size meeting the supplied target. The test is one-sided and
exact over **shared-bank clusters**: question-level differences are summed
within each bank before a sign-test p-value is calculated. The simulation
retains the registered question law and reports its replicate count and
Monte Carlo uncertainty. No combined acceptance verdict is inferred from
the three metrics. A control indistinguishable on the registered optimizer
path remains visibly undetected; this does not certify off-grid accuracy.

The CLI prints a closed aggregate schema. It never prints case identifiers,
bank identifiers, winners, reference quantities, control paths or task digests.
The input digests check integrity, not scientific adequacy or authorization.
Real bank construction, grid/continuous law, severity, alpha, target power,
power interpretation and score use remain Test Lead or owner decisions.
