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

## Producer input and command

The sealed bank retains the `carbon.design-search.sealed-bank.v1` format from
`diversity-report`. Its additional private `power_cases` rows contain
`case`, `support_case`, a registered runnable v2 `task`, and a complete
`reference` panel. Each panel row gives `candidate`, `condition`, and numeric
`values`. Every `support_case` must occur in the bank's exposure ledger.
Cases sharing one support case must bind the same candidate bank and reference
panel; changing a requirement may change the task while reusing those solves.
The bank's aggregate case state and winner are checked against its reference
panel. Questions must share the same objective quantity, unit and direction
before regret can be aggregated. The bank is resealed after these rows are
added.

The known-good predictor file has schema
`carbon.design-search.reference-predictor.v1`, `cases` rows containing `case`
and `predictions` panels, and a `registration_digest` over the other fields.
This first implementation requires the known-good table to equal the full
reference panel exactly. It is an oracle control for the diagnostic, not a
claim that any learned model is perfect. A missing or altered row is refused.

The control file has schema `carbon.design-search.controls.v1`, a `controls`
list and a `registration_digest`. Each control declares schema
`carbon.design-search.control.v1`, a private `name`, `kind`, positive finite
`severity`, and `limit_quantities`. A localized sign error also declares a
nonempty `region` with `action` selectors and `strata`; the awareness control
declares `scope: registered_search_path` or `registered_lattice`.
`register_controls` and `register_good_predictor` construct the two digests.
The report outputs a control index and kind, never its private name.

```text
python -m carbon.design_search power-report \
  --bank sealed-bank.json \
  --grid-law grid-law.json \
  --continuous-law continuous-law.json \
  --controls controls.json \
  --good-predictor good-predictor.json \
  --alpha <Test-Lead-supplied> \
  --power-target <Test-Lead-supplied> \
  --simulation-seed <producer-supplied> \
  --replicates <producer-supplied> \
  --max-questions <producer-supplied>
```

The two laws must use the same sealed bank and registered batch size. P and Q
are separate views. Power uses an exact one-sided sign test after summing
paired loss differences within each shared bank. False-feasible, missed
opportunity and regret use separate tests; regret only uses questions priced
for both predictors. The first reported question count meets the supplied
target at that count and every larger simulated count through the supplied
maximum. It is a Monte Carlo estimate with a reported standard error, not a
qualified sample-size guarantee. Continuous-law integration error is stated
separately as a conservative draw-probability bound. Exposure limits cap the
largest simulated batch; a report can return no detectable batch size.
