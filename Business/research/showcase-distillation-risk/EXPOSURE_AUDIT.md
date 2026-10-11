# Static audit of the registered public showcase

Source pin `43f664319e1c2f977908186d7a017f2eb0771251`. This audit inspected public
implementation and the **PUBLIC_SYNTHETIC development** contract only. It did
not fetch the live feed, invoke the incumbent or read hidden exam/operator state.
All source-derived counts here have fixed low/base/high values.

## What is actually emitted

`score_feed.SHOWCASE` selects EV4's development split. `showcase()` constructs
all its decision-case inputs, infers the retained incumbent, and returns its
projection in the signed `predictions` map. The browser then replays an optimizer
against that panel. The full map is an information surface even if a chart draws
only selected/visited candidates. Missing/unprojectable rows are omitted.
[Feed contract and publisher](https://github.com/carbonphysicsai/Carbon/blob/43f664319e1c2f977908186d7a017f2eb0771251/carbon/challenge_validator/score_feed.py#L67),
[replay consumer](https://github.com/carbonphysicsai/Carbon/blob/43f664319e1c2f977908186d7a017f2eb0771251/carbon/dashboard/showcase.py#L450).

| Exposure | Fixed low/base/high | Basis |
|---|---|---|
| Protocols per condition | 35 / 35 / 35 | 7 c1 values times 5 c2 values |
| Development conditions | 12 / 12 / 12 | 4 ambient-temperature values times 3 initial-SOC values |
| Maximum unique input vectors | 420 / 420 / 420 | 35 times 12, inputs `(c1,c2,t_amb_c,soc0)` |
| Continuous quantities per successful row | 3 / 3 / 3 | CV-onset time, plating margin, peak temperature |
| Maximum continuous scalar values | 1,260 / 1,260 / 1,260 | 420 times 3 |
| Maximum categorical reach values | 420 / 420 / 420 | One `reach_class` per row |
| Observed live emitted count | HUMAN_INPUT | Not measured; structural maximum is not a live observation |

[Public design variables and scenarios](https://github.com/carbonphysicsai/Carbon/blob/43f664319e1c2f977908186d7a017f2eb0771251/carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json),
[projection](https://github.com/carbonphysicsai/Carbon/blob/43f664319e1c2f977908186d7a017f2eb0771251/carbon/design_search/battery_q3_v8.py#L149).
An unreachable time has an internal sentinel and a separate reach class; it is
not an observed physical time. Do not train or report it as a finite charging
time without that mask. These are scalar summaries, not the model's raw field
or time-series output. Future field demos must count spatial/time samples and
channels as well as independent input cases.

The leaderboard's `precision=0.001` is used by `_sections/_round` for released
aggregate scores. The showcase prediction map does not call that rounding path.
Rounding in a chart or formatting a label is not information removal if the
underlying JSON still carries precise values. Signing protects provenance, not
confidentiality. [Separate projection paths](https://github.com/carbonphysicsai/Carbon/blob/43f664319e1c2f977908186d7a017f2eb0771251/carbon/challenge_validator/score_feed.py#L210).

## How many points might identify a simple surrogate?

**ASSUMPTION mathematical function-class scenario**, not a claim about the
incumbent: a scalar total-degree-d polynomial in p inputs has
`M = binomial(p+d,d)` coefficients. M exact, suitably independent equations can
identify its coefficients; arbitrary M points need not have full rank. Each
additional scalar output is a separate fit unless it shares structure.

With the source's fixed p=4 inputs, degree sensitivity low/base/high **1 / 2 / 3**
has coefficient counts **5 / 15 / 35**. Degree 4 is a separate high-complexity
stress scenario with 70 coefficients. A diagnostic on the public grid gives:

| Assumed degree | Coefficients | Public-grid design-matrix rank | Meaning |
|---|---|---|---|
| 1 | 5 | 5 | Exact affine hypothesis is identifiable from a full-rank subset |
| 2 | 15 | 15 | Exact quadratic hypothesis is identifiable from a full-rank subset |
| 3 | 35 | 34 | Only 3 SOC levels; not all cubic coefficients identifiable off grid |
| 4 | 70 | 64 | Limited SOC and temperature levels leave further dependencies |

All counts in this table are fixed low/base/high at their displayed value,
conditional on the stated degree. Rank was calculated from normalized public
coordinate levels, without prediction labels, model training or solver calls.
The structural rank depends on distinct levels, not their units. On a fixed
temperature/SOC slice, a quadratic in the two protocol rates has 6 coefficients
against 35 supplied grid points. This is a reason to test simple response-map
copying first; discontinuities, time masks and near-limit nonlinearity can defeat
that hypothesis. No off-grid accuracy is measured here.

Even rank deficiency does not protect the finite demo: a complete grid table
already reproduces its disclosed function at those coordinates. A neural
surrogate's parameter count is not a reliable bound on its needed label count;
public physics/data can supply much of its behaviour before any demo label.

## Cumulative exposure and delay

Count the union `U(model,family) = |union_t published_input_set_t|`, tied to the
artifact identity and lineage, across all routes, downloads and historical
versions. Repeated deterministic output on an identical fixed set adds no new
input points. A new model version provides new labels; repeated stochastic
outputs can reveal a better estimate of the expectation, so repetitions and
precision also need recording. A cosmetic version or hotkey must not reset the
publication budget.

Illustrative **ASSUMPTION**: 20 inputs per release, release count low/base/high
1 / 10 / 100. Disjoint sets expose **20 / 200 / 2,000** unique points; an
unchanged fixed set exposes **20 / 20 / 20**. This is arithmetic, not a proposed
cap, measured traffic or independence claim. Delaying those same releases changes
the time of access, not eventual point count. Dethronement removes the current
reign incentive but not the historical function information or its usefulness
for a related successor.

## “Errors only” information test

For a public reference y and prediction f:

- Signed error `e=f-y` reveals `f=y+e` exactly, at its published precision.
- Absolute error `a=|f-y|` leaves `f in {y-a,y+a}` for a scalar: at most two
  choices. Smoothness, neighbour outputs or a disclosed sign can resolve them.
- Squared error leaves the same sign ambiguity after taking a square root.
- A normalized error plus a known scale is likewise invertible or tightly
  constraining. Aggregate MAE/RMSE over a fixed sufficiently broad set does not
  identify each f, but repeated overlapping/subset aggregates can permit
  differencing attacks.

These are algebraic consequences under explicitly public-reference assumptions,
not measured attack success. Removing per-case values reduces demo detail. A
selected candidate plus its model-predicted numbers still supplies labels even
if the remaining map is hidden. Public-reference error publication never
authorizes hidden-reference disclosure.
