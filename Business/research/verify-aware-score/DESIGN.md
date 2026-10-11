# VERIFY-AWARE-SCORE-01 — score the delivered design search

**Research recommendation, public DEVELOPMENT evidence only.** No solver,
training, reconstruction, payment, hidden data or deployment was used. The
owner chooses k, budget, normalisation, mandatory gates and adoption. The
recommendation is **VERIFY-R as a selection-fold candidate**, with accuracy
reported separately. Its one-verification public result does **not** establish
superiority. The full top-k experiment remains an evidence gap.

## Product contract and score

One question fixes the buyer decision, action family, complete mandatory
condition panel, objective direction/unit, reference route, limits and bands.
The model supplies an ordered list of at most k distinct in-family designs.
Ordering sees predictions and public inputs only. The list, selector version,
model identity and timing receipt are committed before reference access. A
historical-compatible selector orders predicted-feasible designs by predicted
objective, then c1, c2 and public action ID. A future selector that deliberately
tests predicted-infeasible designs needs its own registration; the public
bounds below do not apply to it. Abstention produces an empty list.

The verifier attempts the frozen prefix under **all** registered caps: maximum
complete-panel attempts, elapsed wall time and CPU core time. One attempt is
one design's entire mandatory panel, including its predeclared bounded
refinement. Charge startup, inference/search, retries and reference attempts;
use independent planning bounds before admitting an attempt. A rejected or
band-unresolved proposal spends its slot. No reordering after learning a
reference result, free retries, duplicates, free extra conditions, post-hoc
budget expansion, or model-supplied verdicts. Verify every affordable action
in the frozen prefix and keep the best verified feasible design, rather than
stopping at the first feasible design. Unspent budget is recorded, not silently
transferred into unregistered search. Adaptive search is a separate policy.

Let V(m,q;k,B) be the attempted designs for member m and question q whose
**entire** reference panel is FEASIBLE under the unchanged reference contract.
Let f*(q) be the best reference-feasible objective in the registered action
bank; this is a finite-bank optimum, never a global physical optimum. For a
minimization question, define the proposed bounded service regret:

```text
r(m,q;k,B) = 1                                      if V is empty
r(m,q;k,B) = min(1, max(0, (min_V f_ref - f*) / u_q)) otherwise
v(m) = 1 / (1 + sum_q w_q r(m,q;k,B) / sum_q w_q)
VERIFY-R(m) = v(m)
```

For maximization reverse the objective gap. The full-regret constant 1 is a
mathematical convention for the owner's requested NONE-verified outcome;
u_q > 0 in objective units is **HUMAN_INPUT**. Capping at full regret trades
resolution among poor but feasible designs for a bounded loss; the sensitivity
below shows that normalisation affects rank. Retain uncapped objective gaps,
verified return rate and buyer-unit values alongside the scalar. No arbitrary
finite full-regret penalty should be reported as money.

**Settled NONE_FEASIBLE remains in the question population.** Under the
owner's requested no-return convention it contributes full *service* regret
even for a correct abstention. Record correct abstention separately; this is
not an unsafe model label or a physically defined optimality gap. If every
action is unresolved and no feasible optimum is known, report no return but
do not claim a physical regret. Historical EV4/EV5 gave correct abstention
zero decision_loss; that history remains unchanged. VALUE-BAR item 2 leaves
settled NONE_FEASIBLE unpriced, so the new scalar cannot replace that item.

**Unresolved and failed references stay typed.** A completed reference inside
a fixed uncertainty band cannot certify a return. If no list action can be
returned, full service loss applies; this does not turn UNRESOLVED into
INFEASIBLE. Missing/failed reference output or missing model output withholds
the numerical scientific score (`INSUFFICIENT_REFERENCE` / incomplete leg),
and keeps the offered question/failure ledger. Authorized infrastructure
retry/refund semantics remain separate. The public service calculation treats
already published band-unresolved outcomes as observed non-returns; it does
not assert they were physically bad. Reference uncertainty elsewhere in the
bank makes its best resolved feasible design a **best-known comparator**,
not a proven full-bank optimum. A definitive equal-budget claim needs the
whole registered reference bank settled to the governing standard.

P owns the buyer population. Q owns proposal/question sampling. w owns evidence
weighting. None is changed to improve return rate. Questions with feasible
opportunities, settled NONE_FEASIBLE and unresolved families are reported
separately. The public uniform weights below describe the offered EV panels;
they are not customer-frequency weights or the current battery-v3 question
law. Importance weights cannot recover a missing reference or missing list.

Delivery admissibility precedes value ranking: an unverified design **never**
escapes the verifier. A rejected *proposal* can be a useful screening policy
if its remaining budget finds a better verified feasible design. That changes
the product-use contract, not the mandatory scientific laws. Existing model
eligibility/qualification gates cannot be removed by this research. A model
qualified only for screen-then-verify is not qualified for direct control,
unverified engineering decisions, charging safety or deployment.

## What the public records identify

The [public EV5 README](https://github.com/carbonphysicsai/Carbon/blob/7b8e89c34ca78711883b7157a3cd8225c618aa29/docs/development/evidence/ev5-2026-10-03/README.md)
explicitly says prediction bundles stay on the operator host. Committed
EV4/EV5 `decisions[member][question].outcome` identifies the single chosen
protocol and its verified status/objective gap. `agreement` has aggregate
classification and rank information, not a ranked list. The public optimizer
exports have single Mode-D choices and Mode-X boundary probes, whose ordering
targets constraint margin across different conditions. They are **not** a
top-k objective shortlist for one buyer question. No private bundle was read.

Consequently:

- One-verification service loss, returns and D-score/V-value agreement can
  be measured for real members.
- Real k > 1 regret, top-k rank agreement and measured wall/core affordability
  are **NOT_IDENTIFIABLE**. Counts permit bounds, not hidden rankings.
- Actual registry Q3/A-Q and scoring-set joint G-FEAS cannot be recreated from
  these summaries. G-PLATE's EV5 near-plating measurement is available.
- Public EV4/EV5 are older one-condition protocol decisions, not the current
  five-ambient-band v3 cooling/protocol map. Reusing recipes and prior public
  studies also prevents treating them as fresh independent confirmation.

## Measured one-verification results

Every observation below comes from the hash-bound [source manifest](SOURCES.md)
and [results.json](results.json); deterministic counts have low=base=high equal
to the observed count. Forecast ranges and policy constants are labelled
ASSUMPTION. Confidence intervals are uncertainty summaries, not forecast bands.

There are **99 construction-eligible real members / 79 recipes in each panel**.
The service leg is calculable on all **12 development and 12 verification
questions** for those real members; this retains all 99 for screening research,
without certifying any model for independent design approval. At k=B=1 the
solver would reject every publicly labelled infeasible proposal and withhold
every unresolved proposal. This is an outcome replay, not a measured solver
execution or proof of a physically safe product.

| Verification events, 99 × 12 | EV4 | EV5 |
| --- | ---: | ---: |
| Verified FEASIBLE return | 749 | 605 |
| Rejected INFEASIBLE proposal | 69 | 161 |
| Selected band-UNRESOLVED, no return | 117 | 193 |
| Missed opportunity / correct abstention / unresolved abstention | 8 / 245 / 0 | 5 / 206 / 18 |
| Return fraction, all offered member-questions | 63.047% | 50.926% |
| Return fraction where a known feasible bank action exists | 749/891 = 84.063% | 605/792 = 76.389% |
| Settled NONE_FEASIBLE questions / known-opportunity questions | 3 / 9 | 3 / 8 |

The score uses **development** losses and is compared with **verification**
service losses. It is not a correlation of a score with the same observations
that define it. Accuracy CE is a monotone transform of -E, preserving its ranks.
The blended comparator is `sqrt(a*v)`, matching the form, not the semantics,
of historical A-Q. The research unit is 120 s, with 60/120/240 s sensitivity
(**ASSUMPTION**; 120 s is the historical minimum-useful-improvement unit).

| D rule → V service value, all 12 questions each side | EV4 tau-b | EV5 tau-b |
| --- | ---: | ---: |
| VERIFY-R | 0.331 | 0.151 |
| A-VERIFY-R, equal-weight geometric comparator | 0.337 | 0.246 |
| CE accuracy rank | 0.235 | 0.475 |

Recipe × verification-temperature-block percentile sensitivity intervals for
VERIFY-R are **[0.114, 0.425]** in EV4 and **[-0.045, 0.325]** in EV5. The
analysis uses 2,000 paired replicates, seed 20261011 (public analysis seed),
whole recipe resampling with seeds together, and separately resampled whole
V temperature blocks. There are only four V blocks per panel. D scores/gates
stay frozen. Recipe-only intervals and paired deltas for every comparator are
in results.json. These are descriptive **ASSUMPTION: exchangeable public
recipe/block sensitivity**, not coverage guarantees for nonlinear tau or
future v3 panels. The choice of public rule/normalisation is exploratory;
there is no multiplicity-adjusted superiority declaration. The public rank
results do **not** demonstrate VERIFY-R beats the existing candidates.

### Matched comparison with gate/A-Q candidates

To compare on identical evidence, use historical numeric masks: EV4 D6/V8,
EV5 D5/V8. Construct `D_PROXY_A-Q_NOT_Q3 = sqrt(a/(1+mean_D historical
decision_loss))`. It is **not actual registry Q3**. Its scoring-set G-FEAS
leg remains missing. The proxy G-FEAS below is explicitly a disjoint
**development decision-grid joint false-feasible rate**, not a registered
scoring-set gate. Cutoffs 0.005/0.01/0.02/0.05 are sourced registry diagnostic
grid points; both `>=` and strict `>` comparators are measured. No cutoff is
selected here. G-PLATE uses the published EV5 near-plating false-acceptance
measurement; EV4 has no corresponding supplied measurement.

| EV5 matched-mask diagnostic | Passing real members | tau with V service value |
| --- | ---: | ---: |
| VERIFY-R, same D5/V8 mask | 99 | 0.295 |
| D proxy A-Q, ungated | 99 | 0.363 |
| G-PLATE >0.005 / D proxy A-Q | 20 | 0.225 |
| G-PLATE >0.02 / D proxy A-Q | 46 | 0.321 |
| G-PLATE >0.05 / D proxy A-Q | 73 | 0.412 |
| D-grid G-FEAS proxy >0.005 or >0.01 / D proxy A-Q | 0 | undefined |
| D-grid G-FEAS proxy >0.02 / D proxy A-Q | 3 | 0.082 |
| D-grid G-FEAS proxy >0.05 / D proxy A-Q | 98 | 0.363 |

The all-member tau treats gate failures as a tied floor below every passing
member; it is not a survivor-only correlation. Paired crossed intervals for
G-PLATE-minus-VERIFY-R are [-0.329,+0.207] at >0.005,
[-0.188,+0.247] at >0.02, and [-0.044,+0.246] at >0.05. Missing exact Q3/G-FEAS
legs mean **no exact current-rule comparison is claimed**. Test Engineer must
run the actual candidates on a complete prospective selection panel.

### Known-bad, benign and adversarial placement

On the full EV5 D12 service score, **95 real members strictly beat the
boundary-optimist control, one ties it**; **93 strictly beat localized sign
error, one ties it**. Thus their possible placements among the real members
plus that control are 96–97 and 94–95 respectively. They are outside the top
half. Conservative never returns a design here and has all 99 real members
above it. On the matched D5 mask, sign error's wide tie group gives placements
71–92, still outside the top half; the ungated D proxy A-Q places it 23rd.
The strict G-PLATE examples reject both known-bad controls rather than ranking
them. This distinction stays visible in the raw result.

EV4 controls have missing outputs on some D questions, so full-D placement is
**WITHHELD**, not a pass. Its D6 matched mask places boundary optimist below
all 99 real members and sign error below 95. EV5's named oracle is not a
band-aware verified-search oracle: it chooses SELECTED_UNRESOLVED on D-T16-S0.10
and D-T35-S0.10. The historical prediction selector uses zero-band predicted
feasibility; the verifier uses uncertainty bands. On D12, 12 real members
strictly beat that oracle, five tie it. On the matched D5 mask it ties for
first with 29 real members. Do not silently repair this adverse benign-control
finding or mistake its label for a mathematical oracle.

The nine eligible EV5 rebuild-identity adversaries remain in the report. Under
full-D VERIFY-R, `width_b` has five real members above it and four ties
(possible positions 6–10); `steps_b` has 43 above and ten ties (44–54).
Unsafe proposals can coexist with useful verified returns. Therefore a
screen-then-verify score cannot be claimed to purge every formerly unsafe
construction, nor can its high-ranked adversaries be relabelled benign.
Record their out-of-budget, no-return and verified-value behaviour on the
future selection/confirmation folds.

There are also **measured D/V inversions**: `width_b` scores at least as high
as four real members with better V service value (maximum loss gap 0.0833);
`steps_b` does so against 27 (maximum gap 0.1667). These are raw point
diagnostics with no adopted value-noise threshold, not a significance claim
or a new causal attack. Boundary optimist and sign error retain one and three
such comparisons respectively despite their low overall placements. Thus
low known-bad rank does not prove absence of all score/value divergence.

## k, attempt and normalisation sensitivity

All production k and budgets are **HUMAN_INPUT**. Illustrative low/base/high
are k=1/3/5 and complete-panel attempts=1/3/5 (**ASSUMPTION**); additional
diagnostic caps are 2, 10 and the sourced historical 35-action menu. For a
fixed, historical-compatible order and constant per-panel costs, effective
list length is min(k,attempts). CPU/wall caps can shorten it. No measured
candidate-level cost is supplied here, so none of these counts is a priced
budget or an equal-budget result.

Counts bound the unknown shortlist: known reference-feasible actions admitted
by a model = F − false_rejections. Known non-feasible admitted actions =
false_acceptances; at most U unresolved/unavailable actions can also precede
them. A prefix longer than false_acceptances+U must hit a known feasible action
when at least one is admitted. If the first pick is already feasible the
lower bound is one. An empty historical list cannot recover merely by raising
k. These are conservative **partial-identification bounds**, not bootstrap
intervals, expected performance estimates or fabricated trained predictions.

| EV5 V12, constant-cost historical-order extension | Feasible-return fraction bounds | Mean service regret bounds, unit 120 s |
| --- | ---: | ---: |
| Effective attempts 1, measured | 0.5093–0.5093 | 0.5266–0.5266 |
| 2, bounds | 0.5236–0.6608 | 0.3392–0.5165 |
| 3, bounds | 0.5412–0.6608 | 0.3392–0.5095 |
| 5, bounds | 0.5816–0.6608 | 0.3392–0.5072 |
| 10, bounds | 0.6608–0.6608 | 0.3392–0.4997 |
| 35, bounds | 0.6608–0.6608 | 0.3392–0.3936 |

Regret bounds exploit the first verified return as an upper bound and zero as
an optimistic lower bound when an admitted feasible action could improve it.
If all reference-feasible actions are admitted and the prefix necessarily
exhausts them, the best-known comparator is included and regret is zero.
Otherwise a feasible hit does not identify which feasible objective is hit.
The 35-attempt line saturates the published menu and says nothing about a
finer design space. No rank/tau bounds for real top-k are claimed. EV4 bounds
and all low/base/high normalisation calculations are in results.json.

At normalisation 60/120/240 s, full-panel VERIFY-R tau is respectively
0.331/0.331/0.267 (EV4) and 0.170/0.151/0.119 (EV5). These are **ASSUMPTION
sensitivity choices**, not chosen scientific tolerances. Freezing a larger k
or changing units after inspecting V would consume V as development evidence.

## Resistance to score up without verified value up

For fixed questions, weights, action order, budget and reference outcomes,
VERIFY-R is invariant to every numerical prediction change that leaves the
attempted list and verified return unchanged. It rewards neither whole-field
accuracy nor a guessed objective after verification. A controlled
counterfactual retaining 0/0.5/1 of each real member's E (**ASSUMPTION
low/base/high error sensitivity**, unchanged public lists) increases
A-VERIFY-R at half-error for **99/99 real members in both panels**, with no
verified-value change. On the matched masks its maximum score-only gains are
0.0391 (EV4) and 0.0338 (EV5); pure VERIFY-R gains zero. This is an analytic
counterfactual, not a newly trained attacker or empirical attack success.

The standalone tests also check unsafe decoy padding, order/budget truncation,
best-of-verified selection, duplicate refusal, no-return/full-loss and typed
reference failure. Synthetic values are fixtures only. Do not count those
tests as adversarial scientific qualification. A real attack panel should
include numerically improved predictions with identical lists; false
feasibility promoted to the prefix; conservative empty lists; correlated
near-duplicates; manipulated costs/timing; reference-band exploitation;
family-ID spoofing; and selection-fold overfitting. Every rejected proposal,
no-return and adverse reference result remains reported.

VERIFY-R's invariance is **conditional on the evidence contract**. It is not
a strictly proper score for predictive distributions and does not prove honest
probabilities, calibrated uncertainty or globally accurate fields. The
[proper-scoring-rule literature](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf)
concerns truthful probabilistic forecasts; many different models induce the
same finite-budget action list here. [Predict-then-optimize](https://arxiv.org/abs/1710.08005)
motivates measuring decisions rather than prediction errors, but its results
do not automatically certify this nonlinear thermo-electrochemical policy.
[Fixed-budget identification](https://proceedings.mlr.press/v49/carpentier16.html)
motivates terminal recommendation value; its stochastic bandit bounds are not
Carbon power guarantees. [Crossed bootstrap](https://arxiv.org/abs/0712.1111)
motivates dependence sensitivity rather than counting recipe seeds and related
conditions as independent observations.

## Relationship to VALUE-BAR-V1 and equal-budget search

VERIFY-R grades the **same operational object** as VALUE-BAR-V1 item 5: a
screened list followed by independent solver verification, with terminal
best-verified-feasible value at a fixed budget. It is a within-Challenge policy
ranking score, not a replacement for the buyer-value comparison. The
[equal-budget contract](https://github.com/carbonphysicsai/Carbon/blob/7b8e89c34ca78711883b7157a3cd8225c618aa29/docs/development/challenge_pipeline/equal-budget-design.md)
charges measured screen and complete-panel solve costs to every arm. The
[VALUE-BAR-V1 evaluator](https://github.com/carbonphysicsai/Carbon/blob/7b8e89c34ca78711883b7157a3cd8225c618aa29/docs/development/challenge_pipeline/value-bar-evaluator.md)
requires an owner-registered wall/core budget, measured costs and complete
paired **buyer-unit** verified values, with independent bank clusters and
the paired interval strictly in Carbon's favour. Failure to return a verified
feasible design in either arm blocks that priced comparison; no-return=1 in
this research score does not convert it into a value-bar PASS.

EQUAL-BUDGET-V1's published battery-v3 half/base/double allowances are
12/24/48 complete five-band panels, 4/8/16 wall hours and 12/24/48 core hours,
explicitly **ASSUMPTION** buyer-search budgets. They cannot be inherited as
per-question k defaults for old one-condition EV4/EV5. The new score policy
needs a prospective, matching budget identity; its total inference/search/
amortized construction cost plus verified attempts must fit the same ledger
as solver-alone and the strongest cheap baseline. Include competent adaptive
solver-alone and ordinary surrogate search when their registered arms and
measured evidence exist; public fixed-order replay alone does not establish
an advantage over industry practice. If a cached library already wins at
matched admissibility and budget, report that result.

## Test Engineer handoff

[candidates.json](candidates.json) is a **research envelope**, deliberately not
a parseable addition to registry-v5. Current `q` means Q3 single-design regret;
the new `v` means budgeted verified-list service regret. Extending parser,
member legs, versioned question/reference-use contract and independent product
value target is required before prospective registration. This PR edits none
of those runtime files. Preserve historical receipts and the current owner
rule until a new owner record adopts a replacement.

For #1044's next selection fold, freeze k, complete-panel attempt cap, wall/core
caps, units, list policy, refinement/failure handling and P/Q/w first. Measure
actual full G-PLATE/A-Q and tighter scoring-set G-FEAS/A-Q beside VERIFY-R;
include A-VERIFY-R as a score-only-gain control. Use common members/questions
and identical verifier/budget across candidates. Keep recipe seeds clustered,
register temperature/scenario blocks, and report paired tau deltas, return
rate, buyer-unit terminal regret, bad/benign/adversarial placement, top-policy
value, costs and typed failures at every level. Withhold incomplete legs.

Freeze the selected rule and budget before untouched confirmation. Multiple
candidate/budget choices on the selection fold require an explicit familywise
or simultaneous-interval plan there; confirmation must not be used to choose
the winner. Thresholds, minimum practical gain, accuracy eligibility, rejection
allowance and adoption are **HUMAN_INPUT**. A public-format exporter can return
aggregate results without exposing hidden list IDs, references or seeds. No
hidden exporter or owner command is executed by research.

The smallest missing evidence is committed **public** member-specific ordered
lists, complete-panel reference statuses/objectives and measured wall/core
costs, plus the actual Q3 and scoring-set G-FEAS legs. Existing host-only raw
predictions are outside this ticket. The research result is a specified policy
and tested offline diagnostics; no qualified exam, physical validation,
commercial value, launch readiness or live economics follows.
