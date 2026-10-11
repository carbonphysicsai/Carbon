# Battery v2 continuous-primary question law

**DEVELOPMENT / SPECIFIED.** Owner selects continuous requirements as the
primary variant; all numeric distributions, objective aggregation, bands,
weights and batch counts below remain HUMAN_INPUT recommendations. This
[v3 law sheet](battery-continuous-v3.json) supersedes only the Battery row's
recommendations in [v2](proposals-v2.json). No sampler, bank, score or task
registration is installed. Motor, Cooling and five-family laws stay unchanged.

## Buyer question and supported service conditions

I am the fleet charging calibrator: choose one protocol that satisfies the
charging safety limits at all five covered ambient conditions, and reduce my
expected session minutes for my stated service mix and starting SOC. There is
**no hard30-minute deadline**. A different mix describes a different buyer
question; it cannot excuse an unsafe low-frequency ambient condition.

HUMAN_INPUT proposal: draw a buyer ambient-mix vector from
Dirichlet(2,3,8,5,2) over5/15/25/35/40 C. Its mean is10/15/40/25/10%, a synthetic
fleet assumption, not measured deployment frequencies. Draw starting SOC
0.10/0.20/0.30 with50/30/20% mass. These are finite physical bank contexts,
**not** continuous interpolation of unsolved ambient/SOC truth. The primary
requirements, not all physical axes, are continuous.

`carbon/battery/reference.py` declares ambient5–40 C and soc0=0.05–0.50,
passes soc0 to PyBaMM and uses OKane2022 with a30-cycle programme. It has no
independent initial aged-state/SOH input. Current-support recommendation:
fresh OKane2022 initialization is a **point mass**, with ageing during the
programme preserved. Do not call a saved cycle10 trajectory an independently
initialized aged cell. Later extension requires a fixed common conditioning
history, restart-state/parameter digest, capacity basis, initialized thermal/
electrochemical states and prospective observer/reference support. Suggested
restart checkpoints10/30 cycles are investigation candidates only; they are
not active law mass or an authorization to solve.

The current reference's input bounds do not prove its output reductions cover
the buyer job: its first-hour traces and cycle1 plating minimum cannot certify
all-charge extrema or a session beyond that hour. New observer/bank coverage
must be pinned before using any of these questions as resolved truth.

Changing start SOC also changes the requested timing quantity. Recommendation:
**session-start SOC0→80% minutes**, including120-s initial rest, from the
registered current integral/capacity basis. The SOC0.10 slice is exactly v2's
10–80% anchor. SOC0.20/0.30 questions are not mislabeled10–80%; they compare
protocols only within that same task/start state. This extension is
**HUMAN_INPUT pending adoption**; unsupported crossings stay UNRESOLVED.
No time advantage is claimed by silently supplying preconditioning or an
already-aged, already-warm state for free.

## P, Q and w

Under proposed **P**, draw the ambient mix, supported SOC and two requirement
margins independently on one pinned cell/fresh initial state:

- thermal margin mT uniform0–2.5 K: hard charging maximum45−mT C;
- plating margin mEta uniform0–0.002 V: hard every-charge minimum0+mEta V.

At positive margins these are stricter than the buyer's45-C/0-V anchors;
continuous endpoints have zero probability, but the anchors remain explicit
audit controls. Retain programme voltage<=4.2 V and Q30/Q1>=0.99. Capacity is
fixed in this primary variant, not a newly relaxed requirement. Thermal
test-discharge/rest extrema remain diagnostics. Optional cooling has no
selected multiplier and is an action only when separately pinned and covered.

Proposed **Q**, separate from P:20% interior,50% thermal/plating edges and30%
objective near-ties/pick flips, derived from a separate public or retired pilot
bank. Edge/tie bands remain HUMAN_INPUT; do not leak a hidden bank through this
document. Q retains NONE_FEASIBLE; no redraws. Test Lead determines power and
score use. Diagnostic enrichment is not measured fleet frequency.

Proposed **w**: unit outer-question weights for P summaries with bank clustering;
Q summaries reported separately, not automatically official-score contributions
or importance weights. Buyer ambient-mix coefficients belong to the **objective**,
not evidence weights w and not hidden sampling Q. Any combined estimate needs
an expressly registered estimand and sampling correction.

Recommended primary objective is the buyer-mix weighted mean of the five
session times among protocols satisfying **all five** hard-condition sets.
This replaces v2's *proposed*, unadopted worst25/35 aggregation; the owner's
minimize-time decision is unchanged. Secondary capacity loss and frozen bank
order need registered resolution/ties. A weighted mean cannot rescue a hard
breach. Keep worst25/35 time as an audit diagnostic, not a covert time cap.

The **four-vector audit grid** is unchanged from v2:
charging Tmax {42.5,45 C} × capacity floor {0.99,0.995}, plating floor0 V,
SOC0.10 and the v2 worst25/35 objective. It is not the primary population or a
discretization of the new thermal/plating-margin law. Report its different
requirement/objective identity; never mix its results into a primary-law
estimate as if drawn from P. Continuous requirements cost no new reference
solves on an identically covered bank; changed physical contexts do.

## Expected answer diversity and refined edges

Expected distinct winners is **NOT_DEMONSTRATED**, not8 because k=8 and not
infinite because margins are continuous. On a complete public/eligible bank,
partition requirement/mix/SOC space by feasible set and reference-best pick.
Let p_j be P mass whose resolved winner is action j. For independent question
draws conditional on that bank,
`E[D_k] = sum_j (1 - (1 - p_j)^k)`.
Compute separately under Q; for stratified/dependent batches use actual joint
inclusion probabilities or a registered replay, not the iid formula blindly.
Report pilot sample size and uncertainty in the occupancy estimate. Shared-bank
question correlation still matters for score/power even with independent draws.

For k8, the universal bound is0–8 distinct best picks (also bounded by bank
size). All NONE_FEASIBLE gives **zero** winners and one abstention answer;
a dominant action can give one winner despite continuous margins. With two
equally likely winners and no abstention, the *synthetic occupancy example*
has expectation1.9921875, not eight. Recommendation for a pilot: investigate
at least two settled winning regions if they exist; this is not an earned
expectation, compulsory batch quota or a scoring gate.

Report distinct picks, resolved feasible/none-feasible/unresolved fractions,
answer-changing regions, close-call/refinement and residual unresolved rates,
by P/Q and underlying bank. Existing435 public feasibility solves do not
establish this five-ambient, three-SOC, phase-correct bank's winner masses.
No redraws of legitimate abstentions or unavailable references to improve the
reported mix. Power comes from diagnostic Q under Test Lead authority.

Margins close to a protocol's extrema, crossings with observer uncertainty,
and weighted-time near-ties require pinned refined truth for all relevant
comparators. An interval spanning a hard limit stays UNRESOLVED. For objective
ordering, overlapping time intervals stay unresolved for exact best/regret
unless the registered tie-resolution contract settles them; do not declare a
tie from a rounded display. Reference/infra problems are not candidate failure.

## Cost, task interface and quiz impact

Recommended scoping bank:100 protocols ×5 ambients ×3 SOC contexts ×one fresh
initial state = **1500 programme solves**, plus refinement. A question uses
one SOC panel of500 candidate-condition predictions; k8 nominally4000 calls
without an approved cache. Exact-cache reuse must bind model/context/observer
identity and counted-budget semantics, not assert free inference. Requirement
or ambient-mix re-draws add **zero** reference solves only when the entire
required physical bank is already settled; changing SOC/history adds truth.
The historical Battery quiz2684 solves ×about90 CPU-s ≈68 CPU-h remains
historical; revised bank costs are **UNMEASURED**, not1500 times that mean.
Every reused underlying case consumes the same E under #756/#760. A new
question ID/threshold/mix does not renew E. No hidden material is created here.

`tasks.py` now exists and has v1/v2 identities, condition strata p/q/w,
worst/mean/quantile objectives, one secondary and bank-order ties. It does not
interpret a buyer weighted mean from `strata.w`. Bind the outer law, drawn
mix/SOC, physical bank/reference/observer and exposure linkage in the owning
immutable contract manifest. Derive role-correct all-charge maxima/minima and
the mixture objective with a versioned observer/projection; do not change
generic task fields here or duplicate the Validator lane.

Battery **Q2 changes**: continuous thermal/plating margins and full-charge
scope, no30-minute boundary; start-SOC and ageing support explicitly gated.
**Q3 changes**: mix-weighted session objective and variable-SOC observer after
adoption; four-grid audit remains separately identified. Existing diagnostics
(a) optimizer stability, (b) lattice resolution, (c) power by k, (d) decision-
value agreement and (e) unresolved rate remain reported, with thresholds owned
by Test Lead. Refined-edge controls remain edge-optimist, over-cautious,
sign-error and optimizer/lattice-aware; current scores are not changed.
See the [v2 optimizer amendment](../optimizers/battery-ev-fast-charge-v2.md).
No forced change to Motor, Cooling or five-family question laws is identified.
