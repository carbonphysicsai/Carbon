# RES-09: VALUE-METRIC-V2 rev-2 public curves

**DEVELOPMENT / NOT REGISTERED. Reviewer: Carbon Validator. No values chosen.**
The owner requested five parameter curves against the supplied rev-2 draft,
using the same public EV4 data as merged #1218. The comparison is retrospective
and exploratory. It cannot establish current battery-v3 value, safety,
qualification, a takeover or a payout. [WORKING_CONTRACT](WORKING_CONTRACT.md)
records the bounded protocol and assumptions; [source-pin](source-pin.json)
binds the evidence. All finite-panel numbers below are **MEASURED**, with
low = base = high; intervals estimate sampling uncertainty under the stated
assumptions. Grids, units inherited for this historical replay and inferential
choices are **ASSUMPTION / HUMAN_INPUT**, never adopted values.

## 1. What was preserved, and what changed

The immutable [RES-07 executable](../value-metric-audit/res07-analyze.py.txt)
provides the original question construction, measured quantities, reference
assessment, map interpolation and frozen-prefix verification functions.
RES-08's preparation and block-bootstrap helpers are reused. No submitted
model is run, reconstructed or trained; no reference solver is run.

The rev-2 wrapper checks the new draft digest before reusing preparation.
It removes exactly the original preparation function's rev-1 draft assertion
in a local AST copy; every other source, reference, contract, cohort and
prediction-bundle identity check remains. The old cache is used for cohort
metadata and inventory only. **All rev-2 shortlists are recomputed from public
predictions**, including their fallback predictions; old cached shortlists
are never substituted. The old source file is unchanged. The original map
function's quantity-construction body is reused without changing interpolation.

Rev-2 changes applied: strict scored-bank admission (§8.1), positive net U
and cheap-margin diagnostics (§8.2), condition-solve tokens (§8.3),
validator-derived predicted-improvement shortlists (§8.4), exact-U safety
tie-break (§8.6), zero reuse weighting (§8.7), absolute-margin and paired
test options (§8.8), and a fixed cheap policy (§8.9). Rev 1's measured
results are archived by identity and immutable links in
[REV1_ARCHIVE](REV1_ARCHIVE.md). There is no silent historical rescore.

**Objective limitation (§8.5):** the supplied public data measures the old
4.19 V CV-onset proxy, with historical u = 120 seconds. It does not measure
battery-v3 target-SOC charge time or ageing. These curves test the rev-2
workflow structurally on EV4; a v3 economic calibration remains HUMAN_INPUT.

## 2. The scored bank is three questions, not twelve

Admission requires a reference-FEASIBLE declared fallback and every action
settled FEASIBLE or INFEASIBLE. A band-UNRESOLVED action is an unknown result
under the literal §8.1 rule. It is **not** a failed solve or an unsafe design.
The question is excluded for every actor, including cheap and abstention.

| Public family | Offered | Fallback FEASIBLE | Strict scored | Exact strict questions |
|---|---:|---:|---:|---|
| Nominal D | 12 | 7 | 2 | D-T14-S0.33, D-T34-S0.48 |
| Interleaved V | 12 | 5 | 1 | V-T29-S0.40 |
| Question-uniform D/V union | 24 | 12 | 3 | All three above |
| Edge (subset of V) | 6 | 1 | 0 | Gap |
| Robust SOC | 4 | 0 | 0 | Gap |
| Robust temperature | 3 | 0 | 0 | Gap |

The full [coverage ledger](results.json) preserves all reference-status counts,
including the five failed reference records in D-T5-S0.48. They remain
reference failures. Robust families reuse underlying V cases and are not
independent reuse evidence. Empty banks have no mean, rank or CI: they are
not scored zero and not reported as successful cheap-arm comparisons.

P_V2 is the conditional target population option. Q is the existing finite
public grid, not a new random draw. w is uniform over retained questions;
the union weights nominal/shifted 2/3 and 1/3, not 1/2 each. No new P, Q or w
is registered. If the Validator intended “complete” to permit unresolved
bands, that requires an explicit clarification; these primary curves do not
silently relax the draft.

## 3. Selector, costs and comparator

For each question, the validator-style research selector assesses the model's
own predictions for every action, keeps only predicted-feasible actions
whose predicted objective strictly improves on its predicted fallback,
orders by predicted objective and the unchanged c1/c2/id tie key, and takes
the unique frozen prefix of at most k. Missing predicted fallback objective
means an empty list. Every listed action consumes all required condition
tokens even if it fails verification. Best reference-FEASIBLE attempted
design returns only if better than the reference fallback; otherwise gain
is zero. U = gain_seconds/120 − κ × condition_tokens. Abstention U is exactly zero.

The surviving questions each have one condition, so token and action counts
coincide here. Robust three/four-condition accounting is implemented through
the unchanged RES-07 verifier but has no scored public observations. The
unit regression checks it; there is no measured multi-condition rank claim.
Startup, bank acquisition, inference and construction costs remain separate,
not measured whole-workflow costs or a matched-budget VALUE-BAR-V1 pass.

The fixed bilinear D map is the illustrative comparator, using the same
rev-2 selector, k, κ and questions. Nearest D is reported as another control.
The map uses D reference quantities, clamps outside the D interpolation
rectangle and never uses V responses to construct predictions. **Nominal D
is its training/cache grid**; only V is held out from map construction. The
three-question union therefore mixes resubstitution and held-out evidence.
It is not a fresh held-out value test. The public map's acquisition budget
is not matched to model construction, and GP/RBF alternatives are untested.
“Fixed” here means the policy is unchanged during this sweep, not that this
retrospective study establishes a registered strongest-cheap-arm receipt.

### A specification seam that matters

§8.4 does not say whether the fallback comparison uses its model prediction
or a separately known reference objective. Primary curves use the prediction
to keep selection wholly model-derived. The known-reference-objective
sensitivity changes **70 of 100** union U values at the display anchor;
Kendall tau between those U rankings is **0.809**. At κ=0.5 it is **0.121**.
Neither interpretation produces a point winner over the corresponding cheap
arm in any joint-grid setting. Registration must freeze this interpretation.

The predicted-improvement grammar also removes the fallback itself: it cannot
strictly beat itself. Thus the fallback-only control abstains and has U=0;
rev 1's unconditional fallback proposal spent a slot. Rev-2 §4.5 retains that
older wording. The Validator should reconcile it with §8.4 rather than
introducing an exception or charging a nonexistent proposal.

## 4. The five curves and joint cross-check

The [owner chart sheet](charts/owner-five-curves.svg) contains one chart for
each value. Individual charts: [population](charts/population.svg),
[cost](charts/kappa.svg), [cap](charts/k.svg), [margin](charts/delta.svg),
[error budget](charts/alpha.svg). The complete grids and the arbitrary display
anchor are in WORKING_CONTRACT and results.json. There are 25 one-factor
profiles plus 60 nominal/shifted/union k×κ profiles, including repeated anchors.

**No real member beats the fixed cheap arm at any of the 60 nonempty joint
settings.** There are zero positive paired lower bounds and zero illustrative
test passes. At the display anchor, the union cheap U is **7.06555** historical
benefit units; **37** real members tie it exactly and none exceed it. All union
real members have positive U. Always-abstain ranks **101/101** in all union
joint settings; shifted k=1 can put it **98/101**. Neither rank is an adoption
criterion. Empty-family rows remain gaps rather than “zero wins”.

| Union k at κ=0.1 | Exact U-tie pairs / 4,950 | Pairs separated by unsafe-count tie-break | Lexicographic tau to k=3 anchor |
|---:|---:|---:|---:|
| 1 | 282 | 0 | 0.592 |
| 2 | 828 | 51 | 0.820 |
| 3 | 1,548 | 67 | 1.000 |
| 4 | 2,901 | 211 | 0.704 |
| 5 | 3,193 | 220 | 0.682 |

The κ curve at k=3 leaves the union order unchanged over 0.05–0.5;
the cap and population curves change it. Shifted versus union lexicographic
tau is **0.280** at the anchor. Across the full joint grid, minimum tau to the
union anchor is **−0.006**, essentially no agreement, not evidence of a large
systematic reversal. Δ_min and α leave U and all tie orders unchanged by
construction; they affect an acceptance test only.

Exact arithmetic ties use exact float equality. A separate 12-decimal
numerical-tie count is descriptive, not a registered epsilon. Safety orders
exact U ties by fewer INFEASIBLE proposals, then fewer unresolved proposals;
remaining ties stay tied because chain commitment times are absent. The
charts' no-op/control ranks use the inherited numerical diagnostic; tau in
their tables uses exact-U lexicographic ranks. Both variants are in results.

## 5. Paired uncertainty and takeover limitations

Reuse RES-08's **2,000** paired temperature-block bootstrap draws, numerical
seed **20261012** (ASSUMPTION), with its D/V stratified weights, identical
weights and denominator for member and cheap arm, and conditional-bank
denominators. Empty resamples are omitted and never zero-filled. Intervals
are **95% pointwise percentile diagnostics** under a block-exchangeability
assumption; two nominal blocks and three union blocks cannot demonstrate
coverage. The singleton shifted interval is null, not a zero-width certainty.
Per-member paired intervals are published for every nonempty profile.
No simultaneous coverage or fresh-population inference is claimed.
See the [SciPy bootstrap documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html)
for paired resampling and interval/degeneracy limitations.

For an illustrative §8.8 option, test paired per-question differences minus
Δ_min using an exact sign flip shared within each condition block. The
statistic remains the question-weighted mean: block sums, not equal-weight
block averages. Symmetry of independent block differences under the shifted
null is **ASSUMPTION**, not established by these deterministic grids. Ties
and zero differences count as at least as extreme. This is a candidate test
design, not a calibrated mean-inference guarantee for arbitrary distributions.
[SciPy's paired permutation documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html)
explains the paired swaps/sign flips, exhaustive enumeration and tail count.

With one, two and three independent blocks, the smallest possible one-sided
p-values are **0.5, 0.25 and 0.125**, respectively. None reaches the α grid
0.001–0.05. For this exact test, α=0.01 requires at least seven independent
blocks even to have nonzero rejection probability; this is an arithmetic
granularity floor, not a power calculation. A looser α is not recommended.
If another parametric or bootstrap test is registered later, its validity
and calibration must be established separately; the zero counts here are
not a theorem about every possible test.

“Test pass” in the charts requires positive U, point margin > Δ_min and
one-sided p≤α **against the cheap arm**. No incumbent is identified in this
public cohort, so these are cheap-margin acceptance diagnostics, not simulated
crown changes. The file also reports the stricter α/100 Bonferroni diagnostic
for a family of 100 comparisons (also zero); a per-comparison α is not a
round-level false-takeover guarantee. Grid/member selection, repeated rounds,
adaptive construction and carry-forward multiplicity are not calibrated here.

## 6. Safety, adverse findings and gaming

All 100 real CPU rebuilds (80 recipe labels) are reported, **not certified
eligible**. Mandatory G-FEAS must precede ranking. The draft cites registry v5,
while later public score-candidate work has evolved; this research does not
choose a new gate, infer a new-bank verdict or relax one. Gate binding and
new-bank evaluation remain gaps for the Validator.

The union anchor has **five unsafe proposals** across real members. Safety
separates **67** exact-U tied pairs but leaves **1,481** residual tied pairs.
This shows a limited tie-break, not a safety guarantee. Previously adverse
`mlp_raw-s0` ties the cheap arm here at U=7.06555, with zero unsafe proposals
on these three questions. Its historical RES-06 voltage violations are not
erased, and such a high raw U is not an eligibility or physics receipt.

The ten public adversarial rebuilds are separate reported rows. Two tie the
cheap arm at the union anchor; the others score below it. A reference-informed
oracle with the same frozen-improvement cap also ties the cheap arm. This
oracle is an answer-informed control, not a permissible model or optimal
stopping policy. Fallback-only and always-abstain score exactly zero. No
zero-gain control acquires positive U. Keeping fewer unhelpful predicted
improvements can legitimately improve net U; models can still manipulate
predicted fallback values to shorten lists. The selector sensitivity exposes
that seam, but this study does not measure a trained adaptive attack or copy
resistance. Gates, audit and fresh evidence remain necessary.

Excluding a question globally prevents member-specific abandonment of
unpriced rescues from changing the scored denominator. It also narrows
the claim and removes most of this public panel's boundary decisions. Rescue,
NONE and reference gaps must remain visible in the coverage ledger.

## 7. Replay, checks and remaining decisions

See [README](README.md) for clean aggregate/chart replay from the committed
public measured summaries and optional raw public-input replay. All source
identities, the original bundle inventory and both draft revisions are in
[source-pin](source-pin.json) / REV1_ARCHIVE. The original rev-1 Markdown
bytes are not present in the supplied folder; its digest and committed
protocol/results/code are preserved. A byte-identical source copy is a
separate archive gap, never reconstructed text presented as the original.

Local semantic tests exercise strict admission, validator-only list formation,
exact safety ties, paired denominators, shared-block sign flips and condition
cost rescaling. Aggregate replay must be byte-identical and historical RES-08
results must keep their original hash. Black **26.5.1** and Ruff **0.16.3**
are pinned local checks; canonical CI on the PR supplies acceptance, and
native checks never stand in for it. SVGs were rendered and visually inspected.

Owner input stays **HUMAN_INPUT** for P_V2, κ, k, Δ_min and α. Further gaps:
fallback-comparison interpretation and §4.5 reconciliation; exact active gate
binding; registered strongest cheap arm and matched acquisition budget; fresh
v3 questions, reference settlement, condition-block dependence and test power;
buyer benefit/compute calibration. No solver run, spend, sealed-data access,
AX42 action, qualification or live policy was performed.
