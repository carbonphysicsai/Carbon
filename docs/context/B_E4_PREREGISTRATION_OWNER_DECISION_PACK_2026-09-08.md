# B-E4 preregistration owner decision pack

**Date:** 2026-09-08

**Status:** `PROPOSED / DESIGN_ANALYSIS_ONLY`

**Machine-readable proposal:**

`.agent/preregistrations/B-E4_recommended_design_v2.json`

**Blocked-proposal digest:**

`sha256:e2529e84d9d06882c5296b0a39b3f65219627fac49fbcb278950f753a8b66e37`

**Authority ceiling:** no qualifying execution, utility result, scientific or
security/privacy qualification, production qualification, or LIVE authority

> **Historical proposal.** The v2 proposal's design content and digest remain
> immutable historical design-analysis evidence. This document carries only a
> prospective successor pointer; the current recommendation is the
> [`STILL_BLOCKED` v3 execution-readiness pack](B_E4_EXECUTION_READINESS_OWNER_DECISION_PACK_2026-09-08.md).
> Nothing in that successor approves either proposal or authorizes execution.

## Owner summary

The proposed experiment uses five fixed fixture-agent profiles, four matched
arms, and 264 complete four-arm replicate blocks per profile (5,280 planned
runs). Its primary outcome is equal-profile improvement in independent
held-out toy quality by v2 over **each** no-prior, generic-prior, and
v1-directive baseline. The proposed practical floor is
`0.11767314940627138`, one half of the current fixture's smallest non-zero
quality step. Simultaneous paired intervals produce separate pass, fail, and
indeterminate conditions. Meaningful diversity requires three canonical
effectful families and guarded effective diversity of at least `2.0`.
Transcript information must add no more than `0.05` normalized residual
proper-log-loss beyond evaluator-held shadow physics, under simultaneous
one-sided 95% bounds.

The 264-block recommendation is sized for at least 90% dependence-robust
planning power across all three primary improvement bounds and all three
mandatory transfer non-inferiority bounds, not only the primary family.

This is a concrete recommendation, not a ratification-ready freeze. The audit
found that the current fixture has only one effectful two-level family and the
current TEST_ONLY prior targets a fixed singleton lever. Five executable agent
drivers, a normalized total-compute meter, exact arm artifacts, the shadow
campaign, non-rejection attack evidence, role assignments, and a trusted
ratification verifier are also absent. The current proposal records those
blockers and is structurally incapable of authorizing execution. A separate
bounded fixture/prior readiness repair must precede final freeze and
ratification; it must then rerun the design analysis and issue a new digest.

## One-page approval summary

| Reserved decision | Exact proposed value | Required decision owners | Status |
|---|---|---|---|
| Representative profiles | Exactly `PLANNER`, `CODE_GENERATING`, `EVOLUTIONARY`, `LITERATURE_GROUNDED`, and `MINIMALIST` deterministic fixture-policy drivers; one common capability boundary; no model/provider, network, shell, filesystem, subprocess, arbitrary code, hidden context, or direct domain API; driver/runtime/policy bytes frozen before execution | Research, exact protocol | PROPOSED |
| Matched budgets | Per run: 8 attempted candidates and 189 current B-07E fixture units (`8×(9+13)+13`), recomputed after fixture extension. Per profile: 264 complete four-arm blocks plus 26 numbered reserves. Freeze profile-specific `T_p` and normalized `C_p` at `ceil(1.25 × arm-neutral dry-run p99_p)` once the drivers and meter exist. Saved time cannot create attempt 9. | Research, statistics, exact protocol | PROPOSED; dry-run values blocked |
| Utility estimand | For every baseline `b`, `Delta_b=(1/5) sum_p E[Q_v2-Q_b]` in matched blocks; `Q=[log(1+L_worst)-log(1+L)]/[log(1+L_worst)-log(1+L_best)]`, current anchors `L_best=36.5`, `L_worst=90.0`; candidate invalid/no-result is `Q=0`; typed infrastructure/reference failure replaces the whole block | Science, statistics, research | PROPOSED |
| Practical effect floor | `delta=0.11767314940627138`, exactly half the current smallest semantic quality step; rederive before freeze if the readiness repair changes anchors or resolution | Science, statistics | PROPOSED; conditional |
| Uncertainty rule | Profile-stratified paired max-t bootstrap of complete four-arm blocks; separate one-sided familywise-0.05 simultaneous bounds for the three primary and three transfer constraints. Utility passes only if all primary LCBs exceed `delta`, all transfer LCBs exceed `-delta`, at least 4/5 profile contrasts are nonnegative against every baseline, and all 264 blocks/profile exist. Compose utility/diversity/leakage with failure precedence; pass only when all pass. | Statistics, science, research | PROPOSED |
| Diversity metric | V2 practice-admissible owner-canonical plan differences only; once per run/family; global lineage collapse; reject identity conflicts. A family needs at least 10% prevalence in at least 4/5 profiles. Equal-weight profiles over all exposure, assign unsupported mass conservatively to the largest supported family, and use inverse-Simpson only when at least three families are supported and `p_max<=0.5`. | Science, statistics, research, security | PROPOSED |
| Diversity floor | `D_guard>=2.0` (therefore at least three canonical families and no family over half of equal-profile exposure) | Science, statistics, research, security | PROPOSED; current fixture guarantees failure |
| Conditional leakage limit | Four frozen targets; signed `Lambda=(CE_shadow-only-CE_shadow+transcript)/CE_shadow-only`; exact clipping/folds/features/estimator frozen; denominator must be positive in every fold with simultaneous LCB above zero or the result is indeterminate. Familywise-0.05 bounds pass iff every UCB `<=0.05`, fail iff any LCB `>0.05`. | Security, statistics, exact protocol | PROPOSED |

All five roles—research, exact protocol, science, statistics, and security—must
ratify the **same later, execution-ready complete-design digest** before the
qualifying run. Approval of this analysis-only digest cannot authorize a run.

## 1. Representative agent-profile registration

**Decision.** Which fixed fixture-agent population answers the ticket's
representative-agent question without giving one arm more capability?

**Recommended default.** Register the five required profiles as deterministic,
in-repository policy drivers. Every profile begins with only the `ChallengeKey`,
discovers through exact B-07S/B-07G, and can call only the existing official
`submit`/`get_submission_result` fixture operations. Network, repository source,
filesystem, shell, subprocess, arbitrary code, hidden context, direct domain
APIs, and human translation are denied. Model/provider/decoding/token settings
are explicitly `NOT_APPLICABLE`; introducing a model later is a new design.

- `PLANNER`: catalog-derived hypothesis agenda, one lever per paired trial,
  fixed exploration, null/failure retention, and final selection from frozen
  private practice-only diagnostics with a canonical-digest tie break. Held-out
  and transfer outcomes remain evaluator-held until the one final submission.
- `CODE_GENERATING`: generates typed `Strategy` values from the retrieved
  grammar/catalog only; no generated code executes; each compile repair burns
  an attempt.
- `EVOLUTIONARY`: registered catalog mutations under a fixed population/update
  schedule and common RNG; priors may change proposal weights only.
- `LITERATURE_GROUNDED`: one frozen public fixture-method corpus shared across
  arms; every proposal maps to a cited registered lever; no network.
- `MINIMALIST`: the first canonical applicable intervention, no broad search or
  backtracking.

Each freeze must bind driver source and runtime digests, exact policy bytes,
capability list, corpus where applicable, context ceilings, role-separated RNG,
stopping, and retry/invalid rules. The current machine proposal supplies the
policy contract but marks its driver references `PROPOSED_UNIMPLEMENTED`.

**Rationale.** This isolates prior access while exercising five distinct
research policies and supports exact replay. It claims only a fixture-policy
population, not future production miners.

**Stricter alternative.** Add separately stratified, exactly pinned
model/provider configurations after the deterministic fixture checkpoint.

**Cheaper/simpler alternative.** Run three policies only. This is not
recommended because the ticket names all five.

**Sensitivity / consequence of changing it.** A model, network, tool, corpus,
driver, or context change alters the target agent population, compute and
leakage surfaces, and requires a new digest and ratification.

**Required approving owners.** Research and exact protocol; all five owners
ratify the complete design.

**Status:** PROPOSED; executable drivers are not yet pinned.

## 2. Matched wall-time and compute budgets

**Decision.** What resources may each arm consume while preserving fair
opportunity and preventing saved time from becoming undeclared extra search?

**Recommended default.** Pair the four arms in each profile/replicate block.
Each run gets exactly 8 attempted candidate strategies. Under the current
compiled plans, the fixture ceiling is 189 B-07E units: a paired practice trial
can cost `9+13=22`, so eight trials plus one final maximum-cost official-shaped
run cost `8×22+13=189`. The ceiling must be recomputed and frozen after the
effectful fixture extension. Use 264 complete blocks per profile plus 26
prospectively numbered reserve blocks. Invalid semantic attempts burn the
attempt. Saved time never creates a ninth attempt.

For wall time and total normalized agent compute, use the exact pre-freeze
rule `T_p,C_p = ceil(1.25 × p99_p)` from an arm-neutral, preregistered dry-run
campaign for each frozen profile. Apply the resulting profile cap unchanged to
all four arms. The dry run, meter identity, and unit conversion must be pinned.
The repository currently lacks those drivers and a normalized CPU/token meter,
so no defensible numerical `T_p` or `C_p` exists yet.

**Rationale.** The attempt/fixture allowance follows the current
maximum-cost paths. The 25% predeclared wall/compute margin absorbs ordinary
runtime jitter without rewarding an arm. Because `Q_v2-Q_b` is bounded in
`[-1,1]`, paired SD `<=1` is available without inspecting outcomes. Requiring
at least 90% dependence-robust planning power across three primary and three
mandatory transfer constraints needs `261.6356640572783` blocks/profile and
rounds to 264 for exact four-arm order balance. With independent failures
within a profile but no cross-profile independence assumption, 26 reserves
give a Bonferroni-union lower bound `0.9920428711903392` that all five profiles
retain 264 blocks when the block-failure probability is at most 5%.

**Stricter alternative.** Use 296 balanced blocks/profile and one
familywise-0.05 simultaneous family across all six utility constraints; this
retains at least 90% dependence-robust planning power. Use dry-run p99 plus 50%
for `T_p/C_p`.

**Cheaper/simpler alternative.** Use 100 balanced blocks/profile only if a
prospective arm-neutral pilot supplies a one-sided upper SD bound no greater
than `0.6182320680314055` for every primary paired difference and transformed
transfer margin. That conditional design still reaches the 90% six-constraint
planning target.

**Sensitivity / consequence of changing it.** The 264-block design gives a
three-primary-contrast lower bound `0.9523378465728866` and an all-six lower
bound `0.9046756931457731` at SD `1`. At twice the 5% infrastructure-failure
ceiling, the dependence-robust five-profile reserve-retention lower bound falls
to zero. A dry-run failure estimate above 5% therefore blocks readiness; it
does not justify unregistered deletion or threshold relaxation.

**Required approving owners.** Research, statistics, and exact protocol; all
five owners ratify the complete design.

**Status:** PROPOSED; numeric wall-time/total-compute caps await instrumented
non-qualifying dry runs.

## 3. Utility estimand

**Decision.** What exact fixture-population effect should the gauntlet estimate?

**Recommended default.** For each baseline
`b ∈ {NO_PRIOR, GENERIC_PRIOR, V1_DIRECTIVE_PRIOR}`, estimate

`Delta_b = (1/5) sum_profile E[Q_v2 - Q_b]`

from matched four-arm blocks under the frozen budget. `Q` transforms only the
final frozen candidate's independent held-out toy MSE `L`:

`Q = [log(1+L_worst)-log(1+L)] / [log(1+L_worst)-log(1+L_best)]`.

Freeze current anchors `L_best=36.5` and `L_worst=90.0` if the fixture repair
preserves them. Candidate invalid/no-result outcomes remain in intention-to-
treat analysis at `Q=0`. Typed infrastructure or reference failure is retained
as evidence, removes no individual arm, and causes a numbered whole-block
replacement. Transfer `Q` is a mandatory non-inferiority support endpoint.
Restricted time/compute and practice admissibility are supporting endpoints;
reconstruction and invalid-run rate are diagnostics. There is no weighted
composite and no practice-to-official promotion.

**Rationale.** The estimand tests useful held-out toy behavior against every
registered baseline, equal-weights the five fixed profiles, and preserves B-E1
dependence and B-E2 failure separation.

**Stricter alternative.** Require positive transfer improvement, not merely
non-inferiority, against every baseline.

**Cheaper/simpler alternative.** Compare only against no prior. This is not
recommended because it permits baseline selection and cannot establish value
beyond generic or v1 guidance.

**Sensitivity / consequence of changing it.** Changing profile weights,
anchors, invalid/missing handling, endpoints, or baselines changes the causal
question and requires a new digest.

**Required approving owners.** Science, statistics, and research; all five
owners ratify the complete design.

**Status:** PROPOSED; anchors require confirmation after fixture repair.

## 4. Practical effect floor

**Decision.** What smallest v2 improvement is materially useful in this toy
experiment?

**Recommended default.** `delta=0.11767314940627138` on the frozen `Q` scale.
Current legal held-out losses `{90.0,45.2,36.5}` map to
`{0.0,0.7646537011874572,1.0}`. The smallest non-zero quality step is
`h=0.23534629881254276`; the floor is exactly `h/2`.

**Rationale.** Half a registered semantic-resolution step is estimable and
requires the prior machinery to recover a material fraction of a toy
improvement. It is not a round convenience value.

**Stricter alternative.** Require the full step,
`delta=0.23534629881254276`.

**Cheaper/simpler alternative.** Use `h/4=0.05883657470313569`, which would
require substantially more replication and risks elevating tiny fixture gains.

**Sensitivity / consequence of changing it.** A higher floor counts only
larger gains and needs fewer replicates; a lower floor costs power and changes
what “useful” means. If fixture repair changes anchors or minimum resolution,
this value must be rederived before ratification.

**Required approving owners.** Science and statistics; all five owners ratify
the complete design.

**Status:** PROPOSED; conditional on the repaired fixture's resolution.

## 5. Uncertainty-aware decision rule

**Decision.** How should uncertainty, three baselines, five profiles,
dependence, missing blocks, and broad regressions determine interpretation?

**Recommended default.** Resample complete four-arm vectors using a
deterministic profile-stratified paired max-t bootstrap whose seed is derived
from the frozen design digest. Produce one-sided simultaneous 95% bounds across
the three primary contrasts and, separately, their transfer contrasts.

- **PASS condition:** every primary LCB is strictly greater than `delta`, every
  transfer LCB is strictly greater than `-delta`, at least four of five profile
  contrasts are nonnegative against each baseline, 264 complete blocks/profile
  remain, and the separate diversity and leakage gates pass.
- **FAIL condition:** any primary UCB is at or below `delta`, or any transfer
  UCB is at or below `-delta`.
- **INDETERMINATE condition:** everything else, including exhausted reserves,
  a bound touching but not clearing the floor, broad profile heterogeneity, or
  unresolved diversity/leakage.

Candidate invalids stay at `Q=0`. Typed infrastructure/reference failures use
up to 26 pre-numbered whole-block reserves. Fewer than 264 complete blocks in
any profile after 290 attempted blocks/profile is indeterminate. The overall
gate has failure precedence: a definitive failure in utility, diversity, or
leakage remains failure even when another gate is indeterminate; overall pass
requires all three to pass.

**Rationale.** This preserves paired dependence, prevents baseline
cherry-picking and single-profile dominance, and keeps insufficient evidence
distinct from demonstrated nonbenefit.

**Stricter alternative.** Require all five profile contrasts nonnegative and
use one-sided 97.5% simultaneous bounds.

**Cheaper/simpler alternative.** Keep the rule but use the conditional
100-block design only after its prospective SD condition is met. Uncorrected
point estimates are not a defensible simplification.

**Sensitivity / consequence of changing it.** Removing simultaneous control
raises false positives; removing the profile guard permits concentrated gains;
turning indeterminate into pass crosses the ticket boundary.

**Required approving owners.** Statistics, science, and research; all five
owners ratify the complete design.

**Status:** PROPOSED.

## 6. Intervention-diversity metric

**Decision.** How should the experiment recognize distinct research
interventions without counting labels or split variants?

**Recommended default.** Derive each family from an actually executed B-07B
authoritative `plan_difference`, pinned catalog, resolved semantic owner/
consumer, lever kind or component role, and executable-semantics identity.
Collapse aliases, synonymous labels, retries, near-duplicates, changes within
one preregistered semantic bucket, and duplicate lineage globally; reject a
lineage or semantic bucket that claims conflicting identities. Count a family
at most once per v2 profile/replicate run and only after compiled,
practice-admissible execution. A family is supported only if it appears in at
least 10% of registered runs in at least four of five profiles. Equal-weight
profiles over all observed canonical exposure. Assign all unsupported-family
mass to the largest supported family so rare-family spam can only hurt, then
compute:

- `K_supported`: supported canonical semantic families;
- `p_max`: largest conservative equal-profile family share;
- `D_eff=1/sum_j(p_j^2)`;
- `D_guard=D_eff` only when `K_supported>=3` and `p_max<=0.5`; otherwise
  `D_guard=0`.

Raw `EngineeringObservation.intervention_labels` cannot support this metric.
A future qualifying extractor must receive owner-produced records, not caller
family assertions.

**Rationale.** Family identity measures semantic breadth. Run and lineage
collapse resist splitting, the prevalence rule rejects token families,
conservative unsupported-mass assignment prevents rare-family spam from
improving the score, `p_max` rejects a dominant shortcut, and inverse Simpson
measures effective breadth.

**Stricter alternative.** Count only families with independent held-out
benefit, not merely valid executed interventions.

**Cheaper/simpler alternative.** Distinct registered-family count only. It is
not recommended because it ignores concentration.

**Sensitivity / consequence of changing it.** Family/bucket canonicalization
changes the measured breadth and must be frozen. Raw label or numeric-value
counting is susceptible to spam and forbidden.

**Required approving owners.** Science, statistics, research, and security;
all five owners ratify the complete design.

**Status:** PROPOSED; owner-derived extractor not implemented.

## 7. Intervention-diversity floor

**Decision.** How much breadth prevents one accidental shortcut from
satisfying utility?

**Recommended default.** Require `D_guard>=2.0`. Because `D_guard=0` when
`K_supported<3`, this requires at least three prevalent canonical families.
The concentration guard also requires `p_max<=0.5` after conservative
unsupported-mass assignment.

**Rationale.** The floor rules out a one-lever or two-lever story and any
single family contributing more than half of equal-profile exposure, while
tolerating ordinary imbalance among genuinely different research paths.

**Stricter alternative.** Require `K_supported>=4` and `D_guard>=3.0`.

**Cheaper/simpler alternative.** Require `K_supported>=2` and `D_guard>=1.5`; not
recommended because a dominant shortcut plus a token second family can pass.

**Sensitivity / consequence of changing it.** The current fixture's maximum
is one effectful family, so it scores zero. Lowering the floor cannot repair that
identifiability failure. Raising it to 3.0 with only three families effectively
requires exact balance and is likely brittle.

**Required approving owners.** Science, statistics, research, and security;
all five owners ratify the complete design.

**Status:** PROPOSED; impossible on the current fixture.

## 8. Conditional-leakage limit

**Decision.** After conditioning on transferable shadow-case physics, how much
incremental protected-target inference from transcripts is tolerable?

**Recommended default.** Freeze exactly four target identities:
`PROTECTED_CASE_IDENTITY`, `PROTECTED_MIXTURE_IDENTITY`,
`RELEASE_VARIANT_IDENTITY`, and `MEMBERSHIP_BIT`. For each target compute
cross-fitted signed

`Lambda = (CE_shadow-only - CE_shadow+transcript) / CE_shadow-only`,

where `CE` is proper log loss. The base attacker receives shadow-physics
results and frozen public resource/validity/profile covariates. The full
attacker additionally receives a frozen canonical transcript feature set.
Use five profile-stratified complete-block folds assigned by the design digest;
all records from one transcript cluster stay in one fold. In each training
fold, clip class probabilities at `epsilon=1/[2(n_train+1)]` and renormalize.
Require positive shadow-only CE in every fold and a simultaneous lower
confidence bound above zero; otherwise the leakage result is indeterminate,
not denominator-stabilized. Form one-sided familywise-0.05 simultaneous bounds
over all four targets. The limit is `0.05`.

- **PASS condition:** every UCB is `<=0.05`.
- **FAIL condition:** any LCB is `>0.05`.
- **INDETERMINATE condition:** otherwise.

The statistic remains signed; no truncation at zero. Leakage independently
blocks B-E4 even with positive utility.

**Rationale.** The statistic asks whether transcripts explain more than 5% of
residual protected-target proper-score loss after observable toy physics. With
1,320 v2 transcript clusters and four targets, a Bonferroni-union calculation
requires the cross-fitted ratio estimator's whole-cluster influence SD to be no
greater than `0.4323807791419945` for at least 90% dependence-robust joint null
clearance. Planning at SD `0.4` gives lower bound `0.957111808457316`. This is
not an iid raw-outcome SD; a non-qualifying estimator dry run must bound the
whole-cluster quantity before freeze.

**Stricter alternative.** Limit `0.025`, with more shadow cases/blocks.

**Cheaper/simpler alternative.** Keep `0.05` but accept lower precision and
more indeterminate outcomes. Never relax the limit after execution.

**Sensitivity / consequence of changing it.** In the seeded 20,000-draw normal
design simulation at SD `0.4`, a single target at `Lambda=0.075` is detected as
FAIL `0.5154` of draws, falsely cleared `0.0`, and left indeterminate `0.4846`.
The proposed limit is sensitive but deliberately does not force a verdict near
the boundary. Poorer dry-run precision requires prospective information
expansion or expected indeterminacy, never a higher limit after outcomes.

**Required approving owners.** Security, statistics, and exact protocol; all
five owners ratify the complete design.

**Status:** PROPOSED; exact shadow sampler, targets, folds, estimator, and count
remain unpinned.

## Proposed matrix and resource estimate

Use complete matched blocks with isolated sessions and common registered
case/hardware/randomness roles. Rotate the four arm orders exactly across 264
replicates/profile (66 complete rotations). The arms are:

1. `NO_PRIOR`: no guidance; `NoPriorSelector` throughout.
2. `GENERIC_PRIOR`: one content-addressed, domain-neutral research workflow;
   no surface, value, direction, or hidden fixture fact; `NoPriorSelector`.
3. `V1_DIRECTIVE_PRIOR`: exact private v1 projection of the same frozen v2
   pack, with source pack, mapping version, omissions, and output digest.
4. `V2_TEST_ONLY_PRIOR`: exact B-07S `get_prior(EXACT)` through B-07D3, one
   TEST_ONLY pack/authorization pair pinned across every v2 run.

| Quantity | Planned | Maximum with reserves |
|---|---:|---:|
| Complete four-arm blocks | 1,320 | 1,450 attempted |
| Agent-arm runs | 5,280 | 5,800 |
| B-07E fixture units at current maximum | 997,920 | 1,096,200 |
| Wall time | `sum_p 4×264×T_p` | `sum_p 4×290×T_p` |
| Normalized total agent compute | `sum_p 4×264×C_p` | `sum_p 4×290×C_p` |

`T_p` and `C_p` are intentionally unresolved until instrumented dry runs.

## Non-qualifying design analysis

`carbon.gauntlet.run_nonqualifying_power_analysis` uses deterministic seed
`20260908` and 20,000 synthetic normal draws. It has no path to
`GauntletRecord`, ratification, execution authorization, or a qualification
verdict.

- Unrounded requirement: `261.6356640572783` blocks/profile; proposed balanced
  matrix: 264.
- Dependence-robust primary-three lower bound: `0.9523378465728866`; all-six
  utility lower bound: `0.9046756931457731`.
- Seeded simulated all-six utility clearance: `0.9068` with independent normal
  contrasts and `0.92845` at shared correlation `0.5`.
- A composite-null scenario with one constraint exactly at its floor falsely
  clears in `0.01585` of draws.
- Maximum cluster SD for 90% joint leakage null clearance:
  `0.4323807791419945`; at planning SD `0.4`, the robust lower bound is
  `0.957111808457316`.
- Seeded null leakage clearance is `0.9581` with independent normal targets and
  `0.96535` at shared correlation `0.5`.
- At one target `Lambda=0.075`, seeded FAIL detection is `0.5154`, false
  clearance `0.0`, and indeterminacy `0.4846`.
- Per-profile retention at the 5% block-failure ceiling is
  `0.9984085742380678`; the cross-profile union lower bound is
  `0.9920428711903392`. At 10%, that cross-profile lower bound is zero.

These are design assumptions and synthetic diagnostics, not outcomes. Fixture
repair must be followed by new non-qualifying dry runs; any changed design
produces a new digest before owner ratification.

## Attack-campaign integration recommendation

Keep the present typed rejection matrix as synthetic conformance evidence
only. The next bounded integration should add a private append-only
`AttackCampaignRegistration` plus owner-adapter-created
`AttackAttemptReceipt`. Each receipt binds the frozen design, Challenge, case,
ordered exact call/reply transcript digest, actual owner outcome, task/
ExperimentRecord/resource/fixture/shadow references, limits, and terminal
state. Assessment must resolve a stored ref; callers cannot supply a
disposition.

- `TYPED_REJECTION` comes only from an executed owner request and applicable
  typed owner response.
- `TRANSFERABLE_PHYSICS` additionally requires the frozen science/statistics
  held-out/shadow procedure.
- `EXAM_VULNERABILITY` additionally requires a security/protocol decision.
- `INSUFFICIENT_EVIDENCE` comes only from the frozen stopping/interval rule.

The latter three remain unavailable. Implementing their positive path now
would invent reserved evidence semantics.

## Exact ratification and freeze procedure

1. Complete the separate fixture/prior readiness repair and implement/pin the
   five drivers, four arm materials, compute meter, shadow campaign, analysis
   implementation, and attack-evidence integration.
2. Rerun only non-qualifying dry runs. Recompute sample size, floor, and shadow
   precision prospectively. Modify proposals if warranted.
3. Emit one canonical v2 proposal binding all eight decisions **and** exact
   profile/arm artifacts, budgets, block/order/seed roles, code/tree, fixture,
   prior/receipt/Challenge, shadow distribution/sampler/targets, endpoints,
   missingness, stopping, analysis version, and attack campaign. Publish its
   immutable bytes and digest.
4. The Carbon owner identifies authenticated principals for `RESEARCH`,
   `EXACT_PROTOCOL`, `SCIENCE`, `STATISTICS`, and `SECURITY`, including whether
   one person may hold multiple roles.
5. Each current role holder posts a machine-readable approval act in owner
   issue #41 binding role, exact digest, immutable design ref, and approval
   evidence ref. All acts must predate execution. Editing, deletion,
   revocation, role expiry, or digest mismatch invalidates the set.
6. A trusted repository-native verifier reconstructs the exact bytes and role
   authority, verifies all five acts, and emits a private freeze record. A
   separate one-use authorization may then admit the exact frozen execution.
7. Immediately before launch, reverify code/tree, matrix, profiles, arms,
   budgets, pins, fixture/shadow identities, analysis, and approval currentness.
   Any mutation forces a new digest and five new ratifications.
8. Store execution evidence separately, bound to the freeze and exact runs.
   It cannot rewrite the preregistration or approval acts.

Issue #42 is the material technical/SciML notification path. It is not an
approval surface. Issue #41 is the human-reserved decision inbox. Neither a
comment nor a proposed document is itself verification.

## Decisions required before qualifying execution

No owner needs to invent a blank value. After the readiness repair and updated
dry runs, the exact required acts are:

1. For each of the eight recommendations above, each named decision owner
   records `APPROVE`, a concrete modification, or rejection.
2. The Carbon owner identifies the five authenticated role holders and decides
   multi-role/currentness/revocation policy for this freeze.
3. All five role holders ratify the same final, execution-ready complete-design
   digest through the implemented verifier contract.
4. Only then may a separate exact execution authorization be issued.

Until those acts exist, B-E4 remains `in_progress`; no qualifying gauntlet has
run, and B-GATE remains unstarted.
