# RES-10: battery question families and surrogate headroom

**DEVELOPMENT / NOT REGISTERED. Reviewer: Carbon Validator.** This research
uses only the owner's public EV4 predictions and existing public references.
No solver, model execution, reconstruction, training or new reference solve
was performed. Existing Challenges, runtime code and other lanes are untouched.
The ranked shortlist is an investigation order, not a selected bank or launch
decision. The supplied draft lacks the queue's §8.12; bank ownership follows
the queue's explicit Carbon Validator routing without inventing that section.

## Finding

**There are plausible advantage signals worth a public completion/value panel,
but no new full-grammar, reference-complete battery family is established as
ready.** RES-09's zero-win result was on a strict bank of two nominal and one
shifted questions. It was not a theorem that no learned member can outperform
a cheap method anywhere on EV4. Four further fallback-feasible shifted
questions contain unresolved action references. Their measured verified-return
diagnostics show substantial potential headroom but cannot yet become a V2 bank.

All deterministic counts/arithmetic are **MEASURED** on these fixed public
panels (low=base=high). Grids, preferences, panel sizes and extrapolation
choices are **ASSUMPTION / HUMAN_INPUT**. Public percentile ranges describe
observations, not guaranteed future bounds. Bootstrap intervals are explicitly
exploratory. [source-pin](source-pin.json), [measurements](measurements.json),
[results](results.json) and [WORKING_CONTRACT](WORKING_CONTRACT.md) give the basis.

## 1. Evidence and method reuse

The study reuses the exact [RES-07 executable](../value-metric-audit/res07-analyze.py.txt)
and merged RES-08/09 adapters. Original case indexing, CV-onset measurement,
plating/temperature/reach checks, reference uncertainty bands, D interpolation
node selection and complete-prefix verification remain unchanged. The raw
public inventory/cohort is checked by the inherited hash guards: 148 unique
bundles, 21 duplicate copies, 100 real CPU rebuilds and 80 recipe labels.
Only the authorized 840 EV4 case keys enter measurement; 835 references are OK.

The new wrapper builds **165** question variants across **14** groups and
reports **840** family/scope/cap/cost profiles. It uses the existing fallback
c1=0.75, c2=0.6 and the historical CV-onset unit of 120 seconds. Caps
1–5 and κ=0.05/0.1/0.25/0.5 per condition-solve are exploratory choices.
The display anchor k=3, κ=0.1 is not recommended or registered.

This is the old first-hour 4.19 V CV-onset proxy on a 30-cycle simulation,
not time to target SOC, validated lifetime or real-cell safety. Existing
outputs do not record SOC/current trajectories; plating margin is a cycle-1
minimum. No heat-transfer design variable or multi-stage control input is
present in the four-input public prediction grid. New physical questions
would require a new packet/measurement law and evidence, not relabelled EV4.

Hard limits remain the historical contract's reach-CV, plating and 45 C
peak-temperature constraints, with the original bands. No physical limit
was relaxed. Predictions form a unique frozen shortlist of predicted-feasible
actions that beat the predicted fallback. Every listed action is verified
and charged for all mandatory conditions. Only reference-FEASIBLE returns
can earn gain; the buyer retains a better fallback. U is verified gain minus
κ times condition tokens. The original verifier's old gain/loss fields are
discarded; only its return and accounting are reused.

## 2. What each axis can actually test

| Axis / family | Design space and representation | Coupled constraints | Conditions / trade-offs | References per offered question | Evidence status |
|---|---|---|---|---:|---|
| Nominal or shifted two-stage | 2 action coordinates; 9, 20 or 35 **existing grid** actions | Same 3 constraints | One operating condition; time objective | 9 / 20 / 35 | Measured; nominal is D-map resubstitution, V is held out from map construction |
| Warm robust common protocol | Same 35 actions; one action must work in all conditions | 3 per condition, jointly mandatory | 2 / 3 / 4 temperature/SOC conditions; worst CV time | 70 / 105 / 140 | Measured compositions, not independent fresh questions |
| Time–temperature preference | Same 35 actions | Same 3 constraints | CV time plus peak rise preference; one condition | 35 | Measured hypothetical preference, not sourced buyer utility |
| Denser or continuous two-stage | More than 35 tested points or a continuous interval | Existing constraints need re-evidence | New c1/c2 coordinates | Number tested; unbounded exhaustive continuum | No off-grid reference/prediction pairs here; advantage **HUMAN_INPUT**, not estimated numerically |
| More protocol stages | More independent control coordinates | Reach, plating, thermal, any new ageing constraints | Longer control history and time/lifetime objectives | Registered finite action count × conditions | Literature plausibility only; current members cannot be assessed on new inputs |
| Protocol + cooling/material uncertainty | Added cooling/parameter coordinates | More joint operating constraints | Thermal/electrochemical interaction, parameter shifts | Actions × independent condition scenarios | Literature/model-route plausibility; current data varies neither cooling nor material parameters |

The 9-action mask uses c1={0.75,1.25,2}, c2={0.2,0.6,1}; the 20-action
mask uses c1={0.75,1,1.5,2} and all five c2 values. These subsets are **not
nested**, so action identity and count are confounded. They diagnose sensitivity
and reference coverage, not a causal effect of increasing design-space size.
No buyer requirement presently justifies choosing either restricted grammar.

Warm compositions enumerate all 2-, 3- and 4-element sets from the declared
six-point rectangle T={19,29,38} C × SOC={0.22,0.40}, before looking at
member results. There are 15/20/15 offered compositions. One condition has
an infeasible fallback, leaving 10/10/5 priced compositions. All have unresolved
actions; none is strict-bank-ready. The wider original robust-SOC and
robust-temperature families have no fallback-feasible questions.

The trade-off is `max_i(time_i/120 + β × (peak_T_i − ambient_T_i)/1 C)`.
β=0/0.25/1/4 is **ASSUMPTION / HUMAN_INPUT**. The units are an explicit
research normalization, not energy, price, thermal damage or a buyer valuation.
Scalarization is evaluated only after the unchanged hard constraints. It
cannot buy permission to fail them. Comparing raw U across different β laws
does not create a common commercial value scale.

## 3. Stronger cheap competition

Every map uses the same public D references, action grammar, selectors,
verification caps, κ, fallback and question denominator as each member.
V reference answers never enter its prediction construction. Compare:

1. **Bilinear scalar D map**, inherited from RES-07: interpolates measured
   quantities and omits a stencil if a node has no measurable CV time.
2. **Nearest scalar D map**, also inherited.
3. **Bilinear trace D map**, retaining the same coordinate stencils/weights:
   interpolates voltage and temperature traces and plating margins, then
   applies the unchanged measurement helper. It can handle valid node traces
   that do not individually reach CV. Failed/missing source nodes are still
   omitted. These are cheap *predictions*, never synthetic reference truth.
4. Four explicitly limited **solver-alone fixed orders**: ascending current,
   descending current, c2-up neighbours of the fallback, and c1-up neighbours
   of the fallback. Their lists exclude the known fallback, use no V answers,
   charge every attempted condition and retain the same reference feasibility
   rule. They are controls, not a claim of industry-optimal solver search.
5. Known fallback/abstention and every prefix length up to k.

The **retrospective cheap budget envelope** chooses the best observed net
mean among those options. It is an answer-informed diagnostic upper envelope
over this limited class, not a legitimately frozen onboarding winner.
Passing it is necessary evidence of headroom against these controls, not
sufficient against the strongest cheap competitor. The original scalar-only
comparisons and trace comparisons remain separately reported.

Acquisition, inference and model construction costs are not matched. Model
G-FEAS eligibility on these new questions is unknown and is not inferred
from design feasibility. A GP/RBF, analytic charging estimate, adaptive
Bayesian/gradient solver-alone search, early-abort verification and proper
onboarding cheap-arm selection still need the prospective equal-budget panel.
The [Attia study](https://web.mit.edu/braatzgroup/Attia_Nature_2020.pdf) combines
early-life prediction with Bayesian experiment selection; that supports taking
adaptive cheap competitors seriously, not comparing only with exhaustive search.

## 4. Measured comparison at the display anchor

Envelope columns include trace interpolation and shortened prefixes.
“Best margin” selects the best observed real member after seeing this public
panel; it is not a prospective winner estimate. Gains are historical benefit
units, except the expressly hypothetical time–heat law.

| Family / scope | Questions | Scalar bilinear ceiling capture | Trace bilinear capture | Real members above cheap budget envelope | Best real net margin |
|---|---:|---:|---:|---:|---:|
| Nominal full 35, strict | 2 | 100% | 100% | 0 | −0.100 |
| Shifted full 35, strict | 1 | 100% | 100% | 0 | −0.200 |
| Shifted full 35, priced but incomplete | 5 | 34.56% | 52.37% | 96 | +4.191 |
| Shifted 20-action subset, strict | 3 | 32.27% | 32.27% | 92 | +3.783 |
| Shifted 20 actions, matched full-35 bank | 1 | 100% | 100% | 0 | −0.200 |
| Shifted 9-action subset, strict | 4 | 39.45% | 39.45% | 92 | +0.891 |
| Warm robust, 2 conditions, incomplete | 10 | 16.03% | 41.59% | 93 | +5.023 |
| Warm robust, 3 conditions, incomplete | 10 | 8.36% | 33.74% | 92 | +5.293 |
| Warm robust, 4 conditions, incomplete | 5 | 0% | 16.96% | 92 | +5.317 |
| Time–heat β=4, strict | 1 | 0% | 0% | 71 | +0.200 |

**Coverage, not merely design count, is decisive.** The 20-action strict
bank includes V-T29-S0.22 and V-T38-S0.40 as well as the full-35 bank's
V-T29-S0.40. Removing uncertain actions admits those conditions. On the
common full-35 strict mask the apparent coarse-grammar advantage disappears.
That is not permission to remove difficult actions or conditions to manufacture
a good score. It is a reason to settle references and test the intended P.

At full-35 shifted priced scope, the point-best member's gross gain is 9.498
units versus 5.247 for the budget-envelope arm; mean condition tokens are
2.6 versus 2.0. It is a gross-gain signal, not just fewer verifications.
Across k/κ, 92–97 members beat this limited envelope there. The subset
reference-complete 20-action bank has 92–95 point winners across the grid,
but only three questions and no buyer-backed grammar receipt.

For warm robust families, point-best gross gains are 9.078/8.712/8.692 versus
3.775/2.939/2.895 for the envelope arm. Conditions multiply costs; the selected
cheap prefixes sometimes contain fewer actual proposals because of their
prediction-derived screening. All costs use the registered-style complete
condition accounting, not optimistic free rejection or early stopping.

For β=4 on the single strict question, both the point-best member and cheap
envelope achieve exactly the same gross gain, 1.000742 units. The real member
uses one condition token and the cheap order uses three: **the +0.2 margin
is entirely verification savings at κ=0.1**. At β=0.25 and 1, no member
beats the envelope on that strict question. On the five incomplete questions,
trace interpolation reduces the β=4 envelope winners to 25; it must not be
omitted in a future comparison.

Nominal 9-action cost-only wins over verification-heavy fixed maps disappear
against shorter cheap prefixes. Nominal response-map reuse is not a worthwhile
new bank on this evidence. Denser two-dimensional grids may improve a cheap
interpolator too; there is no evidence that adding points alone creates headroom.

## 5. Ranked shortlist: hypotheses to test, not bank adoption

### 1 — Shifted feasible-frontier single-condition protocol selection

Keep the intended full two-stage grammar and sample fresh operating conditions,
with a declared feasible fallback and complete reference answers. The strongest
current signal is on the additional interleaved boundary conditions, not the
nominal cache grid. Start by investigating the eleven unresolved action-condition
records across the five public fallback-feasible V questions. A finer solve
may still lie in the same uncertainty band; completion is not guaranteed.
Do not silently shrink the grammar or relax a physical/reference limit.

Hypothesis: a learned member can rank feasible protocols across a nonlinear
constraint boundary better than a frozen inexpensive response map at small
verification budgets. Required falsifier: a stronger fixed GP/RBF/trace map
or adaptive solver-alone arm matches it at the same admitted scope and full cost.
Reference requirement: 35 solves per offered single-condition question;
fresh 16/32/64-question panels need 560/1,120/2,240 condition-solves.

### 2 — A common protocol robust over warm SOC and temperature conditions

Use independent future condition sets rather than repeatedly combining the
same six old conditions. Specify whether the engineering job is worst-case
over a finite prescribed set or probabilistic robustness; these are different
P/measurement laws. The common-action intersections and condition costs are
already testable in public data, but all current priced compositions remain
reference-incomplete and share case errors.

Hypothesis: constraint intersections make a few single-condition cheap-map
verifications insufficient, while a learned conditional model screens a
robust common action more effectively. The large point-gain signal survives
trace interpolation, but no independent CI or bank-ready claim follows.
Reference requirement: 70/105/140 solves per offered 2/3/4-condition question.
The illustrative low/base/high panels need 1,120/3,360/8,960 solves.

[Kim et al.](https://arxiv.org/abs/2405.01681) study fast-charge constraint
violations under ambient and parameter uncertainty, using polynomial-chaos
and Monte Carlo methods. This supports the engineering motivation and also
identifies a serious inexpensive structured competitor. Its cell, parameter
uncertainties and risk choices are not adopted as Carbon bounds.

### 3 — A buyer-declared time–thermal preference, with the existing hard gates

A requirement-specific trade-off can change the ranking frontier without
adding a new solver input. It is inexpensive to test once the cases are
solved. The strict evidence is weak: only one question and a verification-cost
advantage at a heat-heavy assumed preference. β is not chosen from this sweep.
Request a real intended-use preference before authoring a new question law;
otherwise report a Pareto set without claiming a monetary utility.

Hypothesis: fast multi-objective screening reduces verified search effort.
Required falsifier: a cheap thermal/charging heuristic, response surface or
adaptive solver arm chooses the same design in one verification. Reference
requirement: 35 solves per offered condition; reuse references across β;
the low/base/high fresh panel counts are 560/1,120/2,240, not four times that.

## 6. Longer-range possibilities and honest unknowns

The [Attia paper](https://web.mit.edu/braatzgroup/Attia_Nature_2020.pdf) tests
224 six-step policies parameterized by three independent rates, with a fixed
charging-time relation, on LFP/graphite cells. It demonstrates that richer
protocol/lifetime search is a real experimental job. It does not prove a
Carbon member beats GP/Bayesian competitors or that its high-rate limits
apply to Carbon's old chemistry. The associated
[author repository](https://github.com/chueh-ermon/battery-fast-charging-optimization)
contains policy-generation and optimization code; its stochastic lifetime
simulator is not a qualified physical reference. No external data/code was
imported or executed, and public availability alone is not a data-rights receipt.

PyBaMM's [thermal-model documentation](https://docs.pybamm.org/en/pybamm-v26.9.0.0/source/examples/notebooks/models/thermal-models.html)
provides a route for coupled protocol/cooling studies through heat-transfer
coefficient, area and volume. It does not validate a chosen material range,
cooling design family, package model or cost. None of those variables varies
in this public data. Continuous schedules, thermal controls, ageing histories
and material-parameter uncertainty have **unmeasured cheap-map and learned
verified gains**: low/base/high remain HUMAN_INPUT, not invented percentage
advantages. They require new input/output/reference credibility contracts.

These are reserves behind the measured shortlist. It would be premature to
reject battery as a whole from the three-question RES-09 bank; equally,
the signals above do not justify building a large V2 bank or selecting a
winner before the cheap arm, references, population and buyer objective are settled.

## 7. Dependence, adverse evidence and next evidence

P is the prospective decision family, Q is the existing D/V grid or enumerated
composition, and w is uniform over the retained public questions within a
profile. Masks are identical for all arms. Priced-but-incomplete scope is
explicitly **not admissible under rev 2**; UNKNOWN is never relabelled safe,
and reference failure is never assigned to a candidate. Unpriced rescue
questions do not receive fabricated gain. Empty means are gaps.

Single-condition intervals resample temperature blocks, paired between member
and a specified fixed map, with 2,000 draws and numerical seed 20261013
(ASSUMPTION). They are pointwise percentile diagnostics, not simultaneous
selection inference. A singleton interval is null. No independent interval
is computed for overlapping robust compositions. Published per-member CIs
are retained at the display anchor; all profiles retain descriptive counts
and source measurements. The inherited full-35 strict comparisons reproduce
RES-09's exact question IDs and cheap U, rather than rewriting that history.

Best-observed member/policy selection, reused public models and cases, limited
condition blocks, reference uncertainty, unknown active-gate eligibility and
unmatched construction/acquisition costs prevent a VALUE-BAR-V1 pass. No
round-level takeover significance or safety qualification is claimed. Models
with prior adverse findings remain in the raw panel; no previous finding is
erased by a new objective. Buyer volume and the economic value of saved tokens
remain unmeasured. Freeze the intended family, fallback, objective and cheap
arm before a new public development panel; sealed confirmation is a separate
owner-controlled activity outside this research session.

The [reference-budget note](REFERENCE_BUDGETS.md) supplies offered-question
budgets and limitations. [README](README.md) gives raw and clean aggregate replay.
The analysis/tests earn bounded research implementation/test evidence only.
Canonical CI on the PR remains the delivery gate; no scientific, security,
commercial, network, production or launch qualification is earned.
