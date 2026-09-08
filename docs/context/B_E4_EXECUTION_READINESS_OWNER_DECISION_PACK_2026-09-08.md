# B-E4 execution-readiness owner decision pack

**Current through:** 2026-09-09

**Current status:** `B-E4 in_progress / PILOT PROPOSED / OWNER_UNAPPROVED /
PILOT_NOT_AUTHORIZED`

**Current pilot contract:**
`.agent/preregistrations/B-E4_autonomous_agent_pilot_v2.json`

**Current pilot digest:**
`sha256:f836433a10fc654cfa884e125189d655500959a55d1711123562eda8ca11eaa5`

**Current qualification proposal:**
`.agent/preregistrations/B-E4_recommended_design_v4.json`, `STILL_BLOCKED`

**Authority ceiling:** proposal validation and offline synthetic design analysis
only. No provider inference, autonomous-agent run, pilot, shadow campaign,
attack campaign, qualifying execution, approval, ratification, scientific or
security/privacy qualification, production, or LIVE authority.

## Current owner summary

### 1. Current implemented engineering

The rehearsal layer now binds a prospective manifest slot to the exact
campaign, profile, block, arm, run plan, exact local session instance, and
requester/session correlation before the lifecycle starts. A later block
failure can be recorded only from that
factory-issued binding and the exact existing-owner failure subjects produced
by the bound run. Campaign validation rejects reused failure sources, reused
reserve destinations, cross-campaign/profile/session evidence, and multiple
replacement mappings for one failed block. Partial arm evidence is retained,
while the entire failed four-arm block is excluded from analysis. Outstanding
or unreconciled resource use cannot purchase a retry.

Lifecycle resources are prospectively versioned into predicted requirement,
reserved/admitted amount, confirmed consumption, and unknown/unreconciled
consumption. The complete scaffold-plus-candidate practice pair is inspected
and admitted before execution. Completed practice remains counted if a later
operation fails; rejected preflight/final work is not reported as consumed;
and an ambiguous dispatched operation retains a conservative reservation until
verified reconciliation. The frozen historical calibration remains unchanged
and keeps its original accounting interpretation.

The pilot validator now checks the complete closed, versioned nested contract,
including owner sets, profile behavior, interaction transitions, tasks and
inclusion bounds, seed visibility, stage separation, model/service/pricing/
cache consistency, all resource ceilings, data egress, and proposal-versus-
approval-versus-authorization boundaries. It rejects missing, extra, duplicate,
wrong-type, unsupported, or internally contradictory content even after a
caller recomputes the digest. Validator success means only that a proposal is
well formed. An offline-only state machine, payload allow-list checker, twelve-
cell task recipe, and bounded inclusion audit exist; there is no provider
client or campaign executor.

### 2. Current blocked v4 qualification proposal

The eight B-E4 qualification inputs remain exactly those proposed in v4 and
remain `PROPOSED / STILL_BLOCKED`. Deterministic calibration did not establish
a representative autonomous-agent population, sufficient endpoint headroom,
stochastic/dependence behavior, intervention-diversity prevalence, shadow-case
allocation, conditional leakage, or trusted non-rejection attack evidence.
Nothing in this pilot checkpoint changes v4's numerical values or turns them
into approved qualification criteria.

### 3. Current owner-unapproved pilot proposal

V2 recommends one common `gpt-5.6-terra` Responses model across the five
required policy profiles, with medium reasoning, low verbosity, no built-in
tools or external network, `store=false`, isolated arm/run conversations, and
requested/returned model, service-tier, and timestamp recording. The provider
currently advertises an undated Terra alias rather than a distinct immutable
snapshot; availability, behavior, and prices must therefore be reverified at
the later freeze.

Adaptive profiles receive up to four proposal-generating calls and one
separately metered selection-only call after the fourth available practice
result. The selection call may choose an existing practice-admissible ancestor
or stop; it cannot create or evaluate another candidate. This is recommended
over a frozen deterministic selector because it preserves the intended
profile-policy reasoning question without granting an unmetered fifth research
attempt. A deterministic selector is cheaper and more replayable, but would
remove that final policy-dependent choice. `MINIMALIST` receives exactly one
proposal attempt and no model selection call; an invalid first proposal ends
the run.

The proposed 12-cell distribution crosses three exact resource regimes, two
training-only deterministic Rademacher noise amplitudes, and two transfer
covariate shifts. The agent-visible target alternates between `y=x` and
`y=x^2`; evaluator-held seeds, realized signs, held-out/transfer realizations,
references, and scorer internals remain hidden. One realization per cell gives
coverage and diagnostics only—it does not identify within-cell task variation,
provider randomness, or a future qualifying sample size.

### 4. Exact decisions requested now

| Pilot-direction decision | Recommended default | Required owners | Status |
|---|---|---|---|
| Population and interaction | One common Terra model; five frozen arm-neutral policies; four adaptive proposal calls plus one bounded selection-only call; minimalist one attempt then stop; isolated transcripts; no arbitrary code/network | Research, exact protocol, security | PROPOSED |
| Task fixture, seeds, and analysis | Exact 3 x 2 x 2 synthetic distribution; hidden domain-separated evaluator seeds; four arms paired within each profile/task block; bounded structural inclusion; one realization/cell is diagnostic only | Research, exact protocol, science, statistics, security | PROPOSED |
| Resources, cost, and stopping | 40 development + 240 calibration + 20 prospective reserve runs; the exact nested call/token/service/fixture/time limits below; `$98.304` current proposed spend ceiling; no unknown-use retry | Research, exact protocol, statistics | PROPOSED |
| Provider egress and retention | Exact payload allow-list, forbidden-field canary tests, `store=false`, no extended caching, and a security-owner choice among applicable account-level retention controls | Exact protocol, security | PROPOSED |
| Staged evidence use | Development retained but never pooled into calibration; calibration proceeds on implementation integrity, not positive v2 performance; neither stage may qualify B-E4 or substitute for attack/shadow evidence | Research, exact protocol, science, statistics, security | PROPOSED |

Approval of pilot direction is not approval of later source/corpus/task/
implementation manifests. Those exact artifacts do not yet exist and require a
successor freeze, exact-proposal approval evidence, and separate one-use
execution authorization.

### 5. Remaining implementation and execution prerequisites

Before any pilot call, Carbon still needs an approved provider adapter; frozen
system/profile prompts and literature corpus; exact task-generator and
evaluator artifacts; prospective development/calibration/reserve manifests;
model/price/retention reverification; authenticated approval evidence for the
exact successor digest; a cost-reserving admission owner; and separate bounded
execution authorization. Before any qualifying B-E4 execution it additionally
needs approved v4-or-successor eight-value preregistration, five-owner
ratification, shadow/leakage and trusted attack integrations, and qualifying
evidence storage. B-GATE remains unstarted.

## Current v2 pilot contract

### Interaction and stopping

Valid, invalid, malformed, refused, truncated, and output-budget-exhausted
model responses each consume their registered request and, except a verified
external provider failure, their research attempt. A verified external
provider failure permits at most one retry inside the original call/run/stage/
campaign deadline. An ambiguous timeout consumes the attempt, terminates the
run, and retains its in-flight billing reservation. Practice success or failure
updates only the same run's state. Explicit stop and budget exhaustion are
terminal. Before each call, admission uses the minimum remaining call, run,
stage, and campaign time; no retry receives a fresh run deadline.

### Concrete task distribution and bounded audit

| Factor | Exact proposed levels |
|---|---|
| Resource | `DATA_SCARCE`: training x `[1,2]`, candidate/pair units `11/22`; `BALANCED`: `[1,2,3,4]`, `17/34`; `COMPUTE_SCARCE`: `[1,2,3,4]`, feature-cost-only change, `29/58` |
| Training noise | Domain-separated SHA-256 Rademacher additive signs with amplitude `1` or `4`, mean zero, training only |
| Transfer | `NEAR_TRANSFER` x `[5,6]`; `FAR_TRANSFER` x `[9,12]`; target law and measurement fixed |
| Candidate space | Three binary registered families, exactly eight direct candidates; held-out x `[3,4]` |

Each of 12 cells permits at most four generator attempts and eight candidate
checks/attempt: at most 48 task generations and 384 checks, bounded separately
at 7,680 fixture units and 43,200 seconds. Failure to produce every required
eligible cell stops the stage. Rejected identities/reasons are retained and
audit outputs remain invisible to agents. The checks require all candidates to
reconstruct, each family to change constructed state, nonzero held-out and
transfer ranges, no single candidate to dominate all cells, arm-neutral
baselines, and saturation diagnostics. They never select for v2 superiority.

The deterministic offline audit exercised the 12 recipes against all eight
candidates (96 checks; 1,824 fixture units): all reconstructed, all three
families were causally active, endpoint ranges were nonzero, the explicit
linear/quadratic/single-lever baselines were present, per-cell unique endpoint
counts were recorded as `7/8/8/8/7/8/8/8/8/8/8/8`, and no candidate dominated
every cell. This is fixture design analysis, not evidence about model agents or
utility.

### Exact proposed budget and cost

| Quantity | Proposed ceiling |
|---|---:|
| Development / calibration / reserve runs | `40 / 240 / 20` |
| Maximum runs | `300` |
| Maximum provider request attempts | `2,520` |
| Billable input / output-plus-reasoning tokens | `19,660,800 / 4,915,200` |
| Research-service calls | `19,200` |
| Fixture units | `78,300` |
| Call / run deadline | `120 / 900` seconds |
| Development / calibration / reserve stage wall | `57,600 / 345,600 / 28,800` seconds |
| Campaign wall | `432,000` seconds |
| Current proposed monetary ceiling | `$98.304` |

Official prices reverified on 2026-09-09 are `$2.00`/million uncached input,
`$2.50`/million cache-write input, `$0.20`/million cached input, and
`$12.00`/million output. `max_output_tokens` includes visible and reasoning
tokens, so the output ceiling includes both. The per-run input ceiling includes
repeated conversation history, and retry admission re-reserves applicable
input rather than treating it as free. The `$27.52512` value is only a
60%-token, no-retry, uncached scenario—not an expectation. At all-input-cache-
write treatment, the full token maxima would cost about `$108.1344`; that is a
separate owner-unapproved alternative request, not spending authority. To keep
the current `$98.304` ceiling, cache-write input admission is capped at
15,728,640 tokens. Each request reserves the worst applicable input, output,
cache, and in-flight amount before dispatch. Taxes, independently billed
infrastructure, and the separately reported task audit are excluded.

### Provider payload and stages

Only the frozen system/profile policy, agent-visible synthetic task,
current-arm permitted prior, current-run permitted practice feedback, public
resource facts, and current-run existing candidate identities may leave
Carbon. Evaluator seeds, hidden cases, private references, shadow data, scorer
internals, credentials, unrelated private records, and other arms/runs'
transcripts are forbidden. `store=false` controls Responses application-state
storage but is not a promise of zero abuse-monitoring retention; security must
choose and approve the applicable account-level control. Proposal validity
grants neither network nor disclosure permission.

Development comprises 40 retained public-task runs and can expose defects.
After any revision, freeze a new version before the 240 disjoint private
calibration runs; never pool incompatible versions or development rows.
Calibration may begin only after implementation integrity and interpretable
evidence are established, not because v2 looks positive. Twenty reserves are
prospective and one-use. Calibration approval and execution authorization are
not issued here.

# Historical qualification and pilot design material

The sections below preserve v2/v3/v4 qualification analysis and autonomous
pilot v1 as history. Their stale blocker inventories and summaries are not the
current front matter. Historical content and digests are not rewritten.

## Historical execution-correctness update

The successor runtime repair makes policy-controlled attempt, service,
normalized-compute, fixture-unit, and wall-time exhaustion nonreplaceable.
Ambiguous timeouts and caller-labelled failures are also nonreplaceable. A
prospective reserve can be used only when an exact existing B-07B/B-07C or
A7/A8 outcome proves one of the closed eligible external infrastructure or
reference classes. Every early stop retains its exact normalized-compute,
fixture-unit, and wall observation. This is rehearsal-record integrity only;
it does not validate the proposed failure model or authorize any run.

The historical calibration is immutable and remains bound to its original
runtime. Conditional on its recorded no/generic baseline mean
`0.8300554565022396`, a perfect v2 endpoint has only
`0.16994454349776045` Q improvement headroom; conditional on the recorded v1
mean `0.8`, it has `0.2` Q. Both are below the proposed strict primary floor
`0.4017350715246475`. These sample-conditional calculations are not population
bounds, v2 outcomes, or a utility decision. They instead require the owner-
unapproved autonomous-agent pilot proposal to treat estimand feasibility as an
explicit decision and prevent any post-outcome floor adjustment.

## Historical v3 owner summary

The earlier one-family fixture blocker is repaired: sampling count,
curriculum reprioritization/retained-observation weighting, and feature degree
are now distinct registered synthetic construction families. Curriculum level
2 changes the all-level-1 scaffold under both tested seed parities. An exact
private TEST_ONLY pack can expose exploratory
`EXPLORE` / `COMPARE` / `MIXED` material over those families through the
ordinary B-07D2/B-07D3 path. Five deterministic data-only fixture drivers,
preflight plan binding, semantic-work accounting, canonical intervention
identity, evaluator-held shadow registration, and fail-closed attack/execution/
ratification carriers also exist.
B-07F's historical sampling-only asset/reconstruction/result identities remain
byte-for-byte unchanged. Only the three-family path uses prospective identity
v2, whose asset digest is
`sha256:1d92c7d8e3ae0e9dbfe36731860a4a892788464fa5215b855180e8ce14d20c36`.
The centralized artifact factory constructs exact non-qualifying preflight
surrogates only. It does not materialize the required GENERIC domain-neutral
workflow with no surface/direction or the exact v1 `PrivatePriorProjection`.

That work does not make the gauntlet executable end to end. The current runner
stops after B-07S discovery/compile/dry-validation/resource preflight. It does
not run paired B-07C practice, return practice feedback, select the final
candidate from practice, or enforce resources across practice plus final
evaluation. The design-analysis drivers also produce fixed binary proposal
lineages that would collapse to zero supported and guarded diversity under an
assumed task-to-run mapping; the recorded analyzer instead fails closed because
no authoritative B-07B-task-to-B-E4-profile/replicate binding exists. Trusted
non-rejection attack assessment, simultaneous leakage inference, authenticated
five-role verification, and a qualifying evidence store remain unavailable.
Four profiles also expose the same v2 candidate set under the current fixed
policy, so their primary v2 treatment contrast is not yet identifiable. The
candidate-bound fixture-seed design remains unresolved.
A trusted receipt pipeline for the primary and transfer endpoints and their
frozen v3 Q transforms is absent. The untrusted execution draft accepts only
unreplaced complete matrices and does not bind profile-specific reserves, the
retained analysis set, or complete five-driver/four-arm artifact manifests.
The normal preflight factory invokes exact services and transcript-binds their
returned carriers, but current B-07S outcomes—especially rejected compile—do
not all expose exact proposal/request correlation. A prepared candidate cannot
independently prove that mapping.
Prepared ingress now canonical-roundtrips its header and candidate results,
re-derives ordered successful-reply digests, and rechecks discovery, v2,
Challenge, resource, compute, and cap relationships; repeated same-session
submission fails after metered work advances. Separately, a bounded integration
can submit a factory-produced prepared Strategy through the unchanged TEST_ONLY
A7/A8 fixture path and read its result under a distinct no-qualification
ceiling. Its domain-separated association binds the preflight slot, selected
proposal, and A7 receipt. These guards do not bind requester/session identity,
prove trusted service origin or exact request-to-result correlation, enforce
full lifecycle/final-slot policy, or create qualifying evidence.
The declared driver runtime/policy/corpus digests bind configuration and prose,
not the exact executable source bytes. The proposed `636` blocks/profile also
assumes unvalidated exchangeable cross-profile transcript-cluster ICC `rho=0`.
Both remain independent freeze blockers.

The revised numerical recommendation is therefore concrete but not ready for
ratification. Every reserved decision below remains `PROPOSED`, and several
statistical assumptions remain unvalidated.

## Historical v3 proposed approval table

| Reserved decision | Exact v3 recommendation | Required decision owners | Status |
|---|---|---|---|
| Representative profiles | Exactly five versioned deterministic fixture-policy drivers: `PLANNER`, `CODE_GENERATING`, `EVOLUTIONARY`, `LITERATURE_GROUNDED`, `MINIMALIST`; model/provider `NONE_DETERMINISTIC_FIXTURE_POLICY`; only exact B-07S/B-07G plus unchanged submit/result envelopes; no external I/O, arbitrary code, hidden context, or evaluator state | Research, exact protocol | PROPOSED; full practice lifecycle blocked |
| Matched budgets | 8 attempted candidates/run; 223 fixture units/run; policy-work caps `35/35/39/39/20`; wall caps `1/1/1/1/1` seconds; 636 complete blocks/profile plus 52 reserves; saved time creates no ninth attempt | Research, statistics, exact protocol | PROPOSED; preflight-derived only |
| Utility estimand | Equal-profile v2-minus-each-baseline contrasts on independent held-out toy MSE transformed by `LOG1P_FROZEN_ANCHOR_QUALITY_Q/v1`, `Q=(log1p(90)-log1p(L))/(log1p(90)-log1p(0))`; loss anchors `0.0/90.0`; invalid candidate `Q=0`; whole-block replacement only for typed infrastructure/reference failure. Mandatory transfer endpoint `TRANSFER_TOY_MSE_Q` uses the same contrasts, raw-MSE anchors `0.0/650.0`, the same transform identity, and invalid candidate `Q=0` | Science, statistics, research | PROPOSED; trusted endpoint receipt/Q pipeline absent |
| Practical effect floor | Parity-robust feature-degree reference step `h*=0.803470143049295`; `delta=h*/2=0.4017350715246475` on the frozen Q scale | Science, statistics | PROPOSED |
| Uncertainty rule | Paired profile-stratified simultaneous one-sided familywise-0.05 bounds across three primary and three transfer constraints; all primary LCBs strictly exceed delta; all transfer LCBs strictly exceed `-margin_q`, where `margin_q=delta=0.4017350715246475`; at least 4/5 profiles nonnegative against each baseline; equality is not pass; incomplete or overlapping evidence is indeterminate; 636 complete blocks/profile only under unvalidated cross-profile ICC `rho=0` | Statistics, science, research | PROPOSED; cross-profile dependence is unresolved |
| Diversity metric | B-07B-record-derived canonical semantic families only; once/run/family; global task/lineage collapse; conflicts rejected; 10% prevalence in at least 4/5 profiles; equal-profile exposure; unsupported mass assigned conservatively; guarded inverse-Simpson | Science, statistics, research, security | PROPOSED; recorded analyzer blocked on authoritative task-to-run binding |
| Diversity floor | At least three supported families, `p_max<=0.5`, and `D_guard>=2.0` | Science, statistics, research, security | PROPOSED; not demonstrated |
| Conditional leakage limit | Four frozen targets; signed cross-fitted normalized proper-log-loss gain Lambda; five whole-transcript profile-stratified folds; registered clipping; invalid denominator is indeterminate; familywise-0.05 PASS iff all UCBs are `<=0.05`, FAIL iff any LCB is `>0.05` | Security, statistics, exact protocol | PROPOSED; trusted interval campaign absent |

All five roles—`RESEARCH`, `EXACT_PROTOCOL`, `SCIENCE`, `STATISTICS`, and
`SECURITY`—must later ratify one exact complete execution-ready successor
design. No approval should target this `STILL_BLOCKED` proposal.

## Change from v2

| Decision | v2 proposal | v3 recommendation | Why it changed |
|---|---|---|---|
| Profiles | Five unimplemented policy descriptions | Five declared versioned data-only driver configuration identities | The drivers and common policy-work vocabulary now exist through preflight, but the declared digests do not bind executable source bytes |
| Budgets | 189 fixture units; 264 blocks + 26 reserves; wall/compute unresolved | 223 fixture units; 636 blocks + 52 reserves; proposed profile caps above | Added catalog resource facts and leakage-detection planning change the ceiling and sample size |
| Utility | Primary anchors `36.5/90.0`; minimum step `0.23534629881254276`; transfer role named but endpoint transform underbound | Primary anchors `0.0/90.0`; minimum resolution `0.02002402490929653`; practical reference `0.803470143049295`; transfer `TRANSFER_TOY_MSE_Q` with `0.0/650.0` raw-MSE anchors and frozen `log1p` Q | The complete three-family/parity grid changes the legal outcome geometry, and the transfer constraint now binds the exact endpoint rather than only its role |
| Effect floor | `0.11767314940627138` | `0.4017350715246475` | Half the parity-robust registered feature-degree step is more defensible than half an incidental finest spacing |
| Uncertainty | 264 blocks/profile, utility-driven | Utility aggregate constraints need 24; leakage planning gives 636 only under unvalidated cross-profile ICC `rho=0` | The matrix is conditionally sized for proposed leakage sensitivity; cross-profile dependence remains unresolved |
| Diversity metric | Specified, extractor absent | B-07B-record semantic extractor and collapse rules implemented; recorded analyzer fail-closed | Raw labels and duplicate lineage are mechanically excluded, but task-to-run identity still needs an authoritative binding |
| Diversity floor | `D_guard>=2.0`, impossible with one family | Same floor, three families registered | Structural achievability improved, but current fixed binary proposal lineages still score zero |
| Leakage | Limit `0.05`, point/inference machinery absent | Same limit and statistic; registration and point mechanics exist | Simultaneous denominator/influence inference and trusted evidence remain absent |

## 1. Representative agent-profile registration

**Decision.** Which fixed fixture-agent population answers the ticket's
representative-agent question without giving one arm more capability?

**Recommended default.** Freeze the five deterministic in-repository drivers
below. All start from the same allowed Challenge context, discover through the
exact B-07S/B-07G service, and use only the unchanged official-shaped submit/
result envelopes. Model/provider and decoding settings are not applicable.

| Profile | Driver identity | Policy-work cap | Wall cap | Special frozen material |
|---|---|---:|---:|---|
| PLANNER | `be4_planner_fixture_driver/2.0` | 35 | 1 s | One-factor agenda, then canonical selection |
| CODE_GENERATING | `be4_code_generating_fixture_driver/2.0` | 35 | 1 s | Typed Strategy data only; generated text never executes |
| EVOLUTIONARY | `be4_evolutionary_fixture_driver/2.0` | 39 | 1 s | Common registered mutation RNG |
| LITERATURE_GROUNDED | `be4_literature_grounded_fixture_driver/2.0` | 39 | 1 s | One frozen fixture-only corpus |
| MINIMALIST | `be4_minimalist_fixture_driver/2.0` | 20 | 1 s | First canonical applicable proposal |

Declared runtime, policy, and corpus digests live in the canonical v3 proposal.
They bind canonical configuration/prose identities but do not bind the exact
executable Python source bytes. A future freeze must bind a verified executable
implementation artifact and regenerate every affected identity if behavior
changes. The capability policy is
`B07S_PLUS_SUBMIT_RESULT_NO_EXTERNAL_IO_OR_CODE_EXECUTION`.

**Rationale.** The fixed policies are replayable and isolate arm material
without adding a model/provider confound. They represent only this synthetic
fixture population.

**Stricter alternative.** Add separately stratified, pinned model/provider
agents after this deterministic checkpoint and treat them as a new design.

**Cheaper alternative.** Use fewer profiles; not recommended because B-E4
names all five.

**Consequence of modification.** Changing driver, corpus, capability, context,
retry, RNG, or stopping behavior changes the experimental population and
requires a new proposal and ratification.

**Required owners / status.** Research and exact protocol. `PROPOSED`;
complete practice lifecycle integration remains blocked.

## 2. Matched wall-time and compute budgets

**Decision.** What resources may each arm consume under a matched opportunity?

**Recommended default.** Give each run eight attempted candidates and no
saved-time conversion to attempt nine. The proposed complete-run B-07E ceiling
is `223 = 8 x (11 + 15) + 15` fixture units. Use the profile-specific policy-
work and wall caps in the table above unchanged across all four arms. Use 636
complete four-arm blocks/profile plus 52 pre-numbered reserves.

| Quantity | Planned | Maximum with reserves |
|---|---:|---:|
| Complete four-arm blocks | 3,180 | 3,440 attempted |
| Agent-arm runs | 12,720 | 13,760 |
| Policy-work units | 427,392 | 462,336 |
| Wall seconds | 12,720 | 13,760 |
| B-07E fixture units | 2,836,560 | 3,068,480 |

The 5% block-infrastructure-failure value is a planning/readiness ceiling, not
a demonstrated full-lifecycle rate. Current wall and work measurements cover
preflight only.
The canonical calibration's frozen per-profile p99 ceiling gives a one-second
cap for every profile.
Those wall and policy-work values were measured with the non-qualifying
GENERIC/v1 surrogates. Materializing the required domain-neutral GENERIC
workflow and exact v1 `PrivatePriorProjection` must trigger a fresh arm-neutral
and full-lifecycle non-qualifying calibration plus a new proposal/digest before
ratification; the current caps are not final for changed treatment artifacts.
Under the proposed independent binomial block-failure model, `R=51` gives
retention lower bound `0.988334132478569`, while `R=52` gives
`0.9926266466108926`; 52 is therefore the smallest reserve count above the
proposed 99% retention target. That failure model remains unvalidated for the
complete lifecycle.

**Rationale.** Work units are deterministic and arm-neutral; B-07E resource
facts and wall time remain separate. The fixture ceiling follows the largest
registered paired practice and final plans.

**Stricter alternative.** Increase prospective margin and reserves after a
complete-lifecycle calibration, without changing attempt count.

**Cheaper alternative.** Size only for the six aggregate endpoint constraints
at 24 blocks/profile. This neither powers the four-of-five profile guard nor
meets the current leakage objective.

**Consequence of modification.** Attempts, meters, caps, reserves, or failure
handling change fairness, precision, or cost and require a new digest.

**Required owners / status.** Research, statistics, and exact protocol.
`PROPOSED`; complete-lifecycle calibration and enforcement remain blocked.

## 3. Utility estimand

**Decision.** What exact fixture-population effect should B-E4 estimate?

**Recommended default.** For every baseline in `NO_PRIOR`, `GENERIC_PRIOR`,
and `V1_DIRECTIVE_PRIOR`, estimate the equal-profile paired mean of
`Q_v2-Q_baseline`. Transform only the final candidate's independent held-out
toy MSE `L` using loss anchors `L_best=0.0` and `L_worst=90.0`. Candidate
invalid/no-result remains `Q=0`. The primary transform is exactly
`LOG1P_FROZEN_ANCHOR_QUALITY_Q/v1`,
`Q=(log1p(90)-log1p(L))/(log1p(90)-log1p(0))`. A typed infrastructure/reference failure
replaces the numbered whole block. Transfer is mandatory non-inferiority
support: its endpoint is `TRANSFER_TOY_MSE_Q`, its contrast is equal-profile v2
minus each baseline, and its raw-MSE anchors are `0.0` and `650.0`. It applies
`LOG1P_FROZEN_ANCHOR_QUALITY_Q/v1`,
`Q=(log1p(650)-log1p(L))/(log1p(650)-log1p(0))`, with invalid candidate
`Q=0`. Time, compute, practice admissibility, reconstruction, and invalid-run
rate remain supporting or diagnostic rather than an arbitrary weighted score.

**Rationale.** This preserves all three baselines, equal profile weight, B-E1
dependence, B-E2 failure separation, and the practice/official boundary.

**Stricter alternative.** Require positive transfer improvement against every
baseline rather than non-inferiority.

**Cheaper alternative.** Compare only with no prior; rejected because it
permits baseline selection.

**Consequence of modification.** Changing anchors, profiles, baseline set,
missingness, or endpoint changes the causal question.

**Required owners / status.** Science, statistics, and research. `PROPOSED`.
The candidate-bound fixture-seed design and the current four-profile v2
contrast identifiability defect must be resolved before freeze.

## 4. Practical effect floor

**Decision.** What smallest v2 improvement is materially useful in this toy
experiment?

**Recommended default.** Use the parity-robust feature-degree quality step
`h*=0.803470143049295` as the practical reference and set
`delta=h*/2=0.4017350715246475`. The minimum legal grid spacing
`0.02002402490929653` remains a resolution diagnostic, not the definition of
material usefulness.

**Rationale.** Half an intended registered causal step is interpretable across
seed parity. Half the finest incidental spacing would count a small interaction
artifact and greatly increase cost.

**Stricter alternative.** Require the full parity-robust step `h*`.

**Cheaper alternative.** Use half the finest spacing; rejected because it is a
weaker usefulness claim despite a much larger sample requirement.

**Consequence of modification.** A larger floor demands larger improvements;
a smaller floor changes usefulness and power requirements.

**Required owners / status.** Science and statistics. `PROPOSED`.

## 5. Uncertainty-aware decision rule

**Decision.** How should dependence, multiple baselines, transfer, profile
heterogeneity, and missing blocks determine PASS, FAIL, or INDETERMINATE?

**Recommended default.** Preserve profile-stratified paired simultaneous
one-sided familywise-0.05 bounds separately across three primary contrasts and
three transfer constraints. PASS requires every primary LCB strictly above
delta, every transfer LCB strictly above `-margin_q`, with
`margin_q=delta=0.4017350715246475`, nonnegative profile
contrasts in at least four of five profiles against every baseline, all 636
complete blocks/profile, and separate diversity/leakage passes. FAIL occurs
when a registered UCB resolves at or below the utility/transfer boundary.
Everything else is INDETERMINATE. Equality does not pass. Definitive component
failure has precedence; overall PASS requires all components to pass.

At paired SD bound `1`, the six aggregate utility/transfer constraints need 24
blocks/profile. The proposed matrix uses 636 only under the conditional leakage
assumptions below.

The non-qualifying sensitivity helper used seed `20260908` and `20,000`
synthetic Gaussian planning draws. Utility's continuous requirement is
`22.447718245989485`, balanced to `24`; the analytic aggregate-constraint power
diagnostic at 24 is `0.9308748005864085` and the seeded simulation is `0.93095`.
At 636, both aggregate diagnostics are `1.0`. These values cover only the three
primary and three transfer constraints; they omit the four-of-five profile
nonregression guard and therefore do not establish full-rule power or a unique
heterogeneity-aware N. At `N=636`, seeded full-rule scenarios pass for
homogeneous profile effects `0.803470143049295` at rate `1.0` and for four
effects `1.0` plus one `-0.1` (equal-profile mean `0.78`) at rate `1.0`, but fail
at rate `0.0` for three effects `1.0` plus two `-0.1` even though their equal-
profile mean `0.56` exceeds delta. The scenarios demonstrate the guard; they do
not power it. For leakage at 636 under the
conditional `rho=0` model, the
analytic null-clearance union lower bound is `0.999996943921504` and the
simulation is `1.0`; one-target detection at the proposed `0.075` adverse
alternative is `0.9002654032997404` analytically and `0.90045` in simulation.
The simulated null result means zero failures in 20,000 design-only draws, not
certainty. These are planning-model diagnostics under the unvalidated
assumptions, not observed gauntlet power or qualification evidence.

**Stricter alternative.** Require all five profiles nonnegative and one joint
family across all six utility constraints.

**Cheaper alternative.** Use 24 blocks/profile only after owners remove or
separately resource the leakage objective and resolve how to power the profile
guard; doing so changes the design.

**Consequence of modification.** Removing simultaneous control, pairing,
profile guards, or indeterminate status raises false-positive or masking risk.

**Required owners / status.** Statistics, science, and research. `PROPOSED`;
the leakage-driven sample calculation uses unvalidated assumptions.

## 6. Intervention-diversity metric

**Decision.** What counts as meaningful research breadth?

**Recommended default.** Derive family identity only from B-07B owner records,
resolved executed plan differences, registered semantic owner/consumer, lever
kind, and executable semantics. Count once/run/family; collapse duplicate task
and lineage globally; reject conflicting claims. Require at least 10%
prevalence in four of five profiles, equal-weight profiles, assign unsupported
mass to the largest supported family, and use guarded inverse-Simpson only when
at least three families are supported and no family exceeds half the exposure.
Raw labels never count.

The semantic extractor is implemented, but B-07B task identity is not yet
authoritatively bound to a B-E4 profile/replicate. The recorded analyzer
therefore fails closed instead of trusting caller-provided run labels. The zero
reported for fixed binary proposals is an independent enumeration under an
assumed, non-authoritative mapping, not a trusted recorded result.

**Rationale.** This resists aliases, tiny perturbations, duplicate lineages,
and label spam.

**Stricter alternative.** Count only families with independent held-out
benefit.

**Cheaper alternative.** Count distinct registered family IDs; rejected
because concentration and lineage splitting would be hidden.

**Consequence of modification.** Canonicalization or prevalence changes alter
the breadth claim and require a new digest.

**Required owners / status.** Science, statistics, research, and security.
`PROPOSED`; recorded analysis is blocked, while the non-authoritative fixed-
proposal enumeration yields zero supported/guarded values.

## 7. Intervention-diversity floor

**Decision.** How much breadth prevents a single shortcut from passing?

**Recommended default.** Require at least three supported families,
`p_max<=0.5`, and `D_guard>=2.0`.

**Rationale.** Registration now makes this structurally possible while still
rejecting one-family dominance. It is not demonstrated: fixed binary proposal
lineages collapse globally and yield zero only in the stated non-authoritative
enumeration; the recorded analyzer fails closed.

At `N=636`, the proposed 10% prevalence rule requires
`ceil(0.10 * 636)=64` distinct globally retained roots per supported family in
at least four profiles. Three supported families therefore require at least
`3 * 4 * 64=768` profile-family occurrences. The current fixed binary drivers
produce supported-family count `0` and `D_guard=0` after global lineage
collapse only in that non-authoritative enumeration, so diversity remains an
execution-readiness blocker rather than a recorded result.

**Stricter alternative.** Require four supported families and
`D_guard>=3.0`, which needs another causal family and new design.

**Cheaper alternative.** Allow two families and `D_guard>=1.5`; rejected
because one dominant shortcut plus a token second family could pass.

**Consequence of modification.** Lowering the floor changes the protection
against narrow utility; raising it changes fixture and sample requirements.

**Required owners / status.** Science, statistics, research, and security.
`PROPOSED`; design readiness currently fails this recommendation.

## 8. Conditional-leakage limit

**Decision.** After conditioning on transferable shadow physics, how much
incremental protected-target inference may transcript information supply?

**Recommended default.** Freeze the four registered targets and signed
cross-fitted
`Lambda=(CE_shadow-only-CE_shadow+transcript)/CE_shadow-only`. Use five
profile-stratified whole-transcript folds, registered public feature sets,
cluster retention, and probability clipping. Invalid or unresolved shadow-only
denominators are INDETERMINATE. Form one-sided familywise-0.05 simultaneous
bounds. PASS iff every UCB is `<=0.05`; FAIL iff any LCB is `>0.05`; otherwise
INDETERMINATE.

The planning calculation assumes whole-cluster influence SD `0.4`, limit
`0.05`, adverse alternative `0.075`, four targets, and 90% detection for one
adverse target. Its continuous requirement is `3,177.268979614933` independent
transcript clusters total, or `635.4537959229866` per profile before balancing.
Rounding gives `636` blocks/profile only under the explicitly unvalidated
exchangeable cross-profile ICC assumption `rho=0`, where five profile blocks
contribute `5N` effective clusters. Four-arm-balanced sensitivity for
`rho=0/.25/.5/.75/1` is `636/1,272/1,908/2,544/3,180` blocks/profile. The cross-
profile dependence and other planning assumptions have not been validated by a
trusted shadow campaign and remain blockers. Exact shadow-case count and
case-to-profile allocation are unpinned; `636` is conditional planning N, not a
qualifying shadow allocation.

**Rationale.** Leakage can independently block B-E4 even when fixture utility
is positive, while negative signed estimates are not truncated.

**Stricter alternative.** Use limit `0.025` and prospectively increase shadow
information.

**Cheaper alternative.** Retain `0.05` with fewer blocks and accept greater
indeterminacy; do not relax the limit after outcomes.

**Consequence of modification.** Limit, targets, estimator, fold, clipping,
features, or precision assumptions change the security/statistical question.

**Required owners / status.** Security, statistics, and exact protocol.
`PROPOSED`; simultaneous trusted inference remains blocked.

## Engineering readiness summary

### Successor checkpoint: lifecycle delivery

The first of three authorized successor deliveries now completes a 20-run
non-qualifying integration demonstration over five deterministic fixture
profiles and four exact arms. It materializes the GENERIC workflow and exact
v1 private projection, binds installed driver source, executes B-07C paired
practice and permitted feedback-based selection, runs the selected Strategy
through A7/A8, records B-07F-held raw primary/transfer endpoints, applies the
proposed Q transforms only for design analysis, and enforces complete-run
attempt/work/service/resource/wall bounds.

This removes those mechanics from the readiness blocker list. It does not
approve v3 or show v2 benefit. The five profiles still describe deterministic
fixture policies, not a human-approved representative autonomous-agent
population. Authoritative campaign correlation/evidence and frozen full-
lifecycle calibration are the next two engineering deliveries. Cross-profile
dependence, exact shadow allocation, utility identifiability, diversity,
leakage/attack evidence, owner-role verification, one-use execution authority,
and all eight reserved approvals remain blocked.

| Component | State | Exact remaining seam |
|---|---|---|
| Fixture and prior | READY for bounded fixture design analysis | Exact sampling-only B-07F historical identities are preserved; only the three-family path uses prospective identity v2; no utility or authorization claim follows from pack consistency |
| Fixed drivers | PARTIAL | Declared runtime/policy digests do not bind exact executable source bytes; no B-07C practice feedback/final selection; four profiles expose the same v2 candidate set, so their primary v2 contrast is not identifiable; not an arbitrary-code sandbox |
| Arm artifacts | PARTIAL | `build_nonqualifying_preflight_arm_artifacts` centralizes exact design-analysis surrogates only; `GENERIC_DOMAIN_NEUTRAL_WORKFLOW_ARTIFACT_UNMATERIALIZED` and `V1_PRIVATE_PRIOR_PROJECTION_ARTIFACT_UNMATERIALIZED` remain blockers |
| Meter/calibration | PARTIAL | Preflight only; no complete-run wall/resource enforcement or failure calibration |
| Diversity identity | PARTIAL | Semantic extraction exists, but authoritative B-07B task-to-B-E4 run binding is absent and recorded analysis fails closed; a non-authoritative fixed-proposal enumeration yields zero |
| Shadow campaign | PARTIAL | Cross-profile transcript-cluster dependence is unvalidated; exact shadow-case count/profile allocation is unpinned; trusted simultaneous denominator and influence-interval integration unavailable |
| Attack evidence | BLOCKED | Trusted owner execution/assessment adapters unavailable |
| Ratification verifier | BLOCKED | Authenticated current-role trust root and policy unavailable |
| Qualifying execution evidence | BLOCKED | Trusted primary/transfer receipt and v3-Q pipeline, profile-specific reserve/retained-set binding, complete driver/arm manifests, exact preflight-result-to-proposal/request binding, and trusted constructor/store unavailable; the official-shaped association is factory/digest-consistent but does not bind requester/session or trusted endpoint correlation and does not enforce full lifecycle/final-slot policy; untrusted draft accepts only unreplaced complete matrices |

After driver-transcript-v2 hardening invalidated the earlier transcript
identities, the deterministic non-qualifying calibration was rerun over 125
complete four-arm profile blocks and 500 preflights with zero typed
infrastructure failures. Its canonical manifest has raw-manifest content digest
`sha256:616267e476c5f1709fee427cc3535033010048bcf333f77e156c875a9c56a9bf`,
ordered preflight-transcript-set digest
`sha256:ad56a4105532a61fa2eb5fc48b1ee3122719d4b076c7f27ce683f593ea60d0a3`,
and replay-stable digest
`sha256:da03b0cf89c5542b2c90ca84c6fcd1485abfab65e5bcce0417673e962bdff97f`.
The generator reconstructs the current fixture graph and rejects mismatched
declared design, configuration, driver, or arm identities. This check does not
bind executable source bytes or make surrogate treatment artifacts final.
The replay-stable digest does not bind wall-time observations; the p99 values
below are separate descriptive diagnostics.
The p99 wall/compute/resource triplets for planner, code-generating,
evolutionary, literature-grounded, and minimalist are respectively
`.493625417/28/37`, `.589078917/28/37`, `.640862833/31/37`,
`.499347959/31/37`, and `.22612375/16/15`. These are descriptive preflight
diagnostics—not a measured full-lifecycle failure rate or qualifying evidence—
because the calibration ran neither practice nor final evaluation. The
separate TEST_ONLY official-shaped integration diagnostic retains its distinct
no-qualification ceiling and is not part of this calibration.
Final current-code replay preserved the ordered transcript/replay-stable
digests, zero block-infrastructure failures, and compute/resource p99s, but host
wall p99s were
`.747780750/1.054919875/.837789875/.866410250/.524846667`, implying replay-only
caps `1/2/2/2/1`. Its wall-dependent raw digest
`sha256:0eaef4daa3c47db455d7255f178e891a2a54cf69a16758336420d02fa6fd7454`
is not stored canonical evidence. This sensitivity leaves the v3 digests
unchanged and reinforces that its wall caps are tentative preflight-run-
specific planning values pending fresh full-lifecycle calibration.

## Exact ratification and freeze procedure

1. Complete and test the paired B-07C practice/feedback/final-selection runner,
   exact executable-source-byte binding for every driver, candidate-bound
   fixture-seed design, identifiable
   v2 treatment behavior across the registered profiles, full-run budget
   enforcement/calibration, diversity proposal behavior, trusted attack
   assessment, simultaneous shadow inference, authoritative B-07B-task-to-B-E4-
   run binding, trusted primary/transfer receipt and v3-Q transformation,
   profile-specific reserve/retained-set binding, and complete driver/arm
   manifests, plus exact request/proposal correlation in every retained
   preflight result.
2. After the final GENERIC workflow and exact v1 `PrivatePriorProjection` are
   materialized, rerun arm-neutral and full-lifecycle non-qualifying calibration.
   Validate or revise every planning assumption prospectively, including cross-
   profile transcript-cluster dependence, exact shadow-case count, and exact
   case-to-profile allocation; issue a new proposal/digest and do not inspect
   qualifying outcomes.
3. Issue a new complete execution-ready proposal and immutable digest binding
   the eight decisions plus exact code/tree, profiles, arms, matrix, budgets,
   fixture/prior/receipt, shadow, attack, analysis, and evidence integrations.
4. The Carbon owner identifies authenticated current principals for
   `RESEARCH`, `EXACT_PROTOCOL`, `SCIENCE`, `STATISTICS`, and `SECURITY` and
   records multi-role, currentness, expiry, and revocation policy.
5. Each role holder records an immutable approval act for the same exact
   complete-design digest before execution.
6. A trusted repository-native verifier reconstructs the bytes and verifies
   role authority and all five acts. Any mismatch, expiry, revocation, edit, or
   design mutation invalidates the freeze.
7. A separate one-use authorization admits only that exact frozen execution.
   Execution evidence is stored separately and cannot rewrite the design or
   approvals.

Issue #41 is the human-reserved decision inbox. Issue #42 is technical/SciML
notification and is not approval.

## Exact owner decisions still required

1. Each named decision owner approves, modifies, or rejects every one of the
   eight proposed values above after the engineering blockers are cleared and
   assumptions revalidated.
2. The Carbon owner identifies the five authenticated role holders and decides
   multi-role/currentness/expiry/revocation policy.
3. All five roles ratify one later exact complete execution-ready digest.
4. A separate one-use qualifying execution is authorized only after successful
   verification.

Until then, B-E4 remains `in_progress`; no qualifying gauntlet has run, and
B-GATE remains unstarted.

## Rehearsal-evidence successor checkpoint

The complete lifecycle is now wrapped by a candidate immutable rehearsal
manifest and campaign record. Exact successful/rejected research-service
request/reply correlations, B-07B tasks and receipts, practice provenance,
driver/treatment/proposal/selection, requester/session, A7/A8/private endpoint,
resources, and canonical v2 intervention lineage are bound together. The 20-run
development demonstration forms a complete descriptive development campaign;
it is not qualifying evidence.

Prospective reserves are fixed before a campaign and may replace only a
retained typed infrastructure/reference failure in the same profile. Failed
and replacement records remain visible. Candidate failures, duplicates,
cross-profile reserves, and forged slot metadata cannot create completeness.

This closes the engineering correlation, campaign-evidence, and typed-reserve
seams listed above. It does not settle any of the eight decisions or the agent-
population scope. Current-role verification, revocation, exact-design approval,
and one-use authorization remain unavailable. The recommended repository-native
integration is:

1. an immutable approval act binds author/principal, one of the five required
   roles, role-registry snapshot, validity interval, revocation snapshot, exact
   complete-design artifact manifest, and its reconstructed digest;
2. revocation is append-only and invalidates the freeze rather than mutating an
   approval;
3. a trusted verifier reconstructs the exact bytes and verifies all five
   current acts; and
4. a separate atomic one-use authorization binds that verified design, the
   frozen campaign manifest, and a unique nonce before qualifying execution.

Carbon has no current trust contract that can prove those facts. This checkpoint
therefore implements none of the positive verification or authorization path.
Fresh frozen full-lifecycle calibration is the next bounded engineering stage.
All v3 values remain `PROPOSED / STILL_BLOCKED`; B-E4 remains `in_progress` and
B-GATE remains unstarted.

## Frozen calibration update and v4 recommendation

**Outcome.** A prospectively frozen, fresh, non-qualifying campaign completed
25 primary four-arm blocks (five/profile), or 100 full-lifecycle runs. All 100
were practice-admissible and reconstructed; none used a reserve. The campaign
consumed 89.107146586 observed host seconds, 3,465 normalized work units, 7,220
fixture units, and 1,625 service calls. The canonical artifact is
`.agent/evidence/wave_b/b-e4-full-lifecycle-calibration-v1.json` with content
digest
`sha256:1b34500736b08a3e8f049fa94230bbe64e4a528bf48310fb3a6601ba8e71997e`.
It is design-analysis evidence only.

**Integrity.** The first attempt stopped before storing observations because a
wall-field implementation defect was discovered. That zero-row event is
retained separately. The repaired generator and freeze received new digests,
and the full campaign restarted with fresh designated blocks. No observations
were pooled. Attack, shadow, qualifying, approval and authorization call counts
remain exactly zero.

**Revised one-page proposed approval table.**

| Reserved input | V4 recommended default | Status / owner action |
|---|---|---|
| Representative profiles | The same five source-bound deterministic fixture policies only for integration/calibration; require an explicit owner decision on a separately pinned autonomous-agent population before treating the ticket's agent-population requirement as met | PROPOSED; Research + exact protocol |
| Matched budgets | 8 attempts; work caps `49/49/53/53/27`; wall caps `2/2/2/2/1` seconds; 223 fixture units/run; 636 complete blocks/profile plus 52 reserves remain conditional | PROPOSED; Research + statistics + exact protocol |
| Utility estimand | Equal-profile v2-minus-each-of-three-baselines held-out Q ITT, with transfer as mandatory separate non-inferiority support | PROPOSED; Science + statistics + research |
| Practical effect floor | `0.4017350715246475` held-out Q on frozen `0/90` anchors | PROPOSED; Science + statistics |
| Uncertainty rule | Simultaneous interval rule, all three primary contrasts, all three transfer constraints, at least four of five profiles non-regressing, equality not pass, indeterminate distinct | PROPOSED; Statistics + science + research |
| Diversity metric | Supported-family equal-profile inverse Simpson with canonical experiment/lineage collapse | PROPOSED; Science + statistics + research + security |
| Diversity floor | At least 3 supported families in at least 4 profiles, prevalence >= 0.10, effective diversity >= 2.0, maximum family share <= 0.50 | PROPOSED; Science + statistics + research + security |
| Conditional leakage | Lambda <= 0.05 for all four protected targets under the registered cross-fitted estimator; 636 remains conditional on unvalidated cross-profile ICC zero | PROPOSED; Security + statistics + exact protocol |

**Primary and transfer are now separate.** The primary floor remains half the
parity-robust held-out feature step, `0.4017350715246475` Q on the `0/90`
transform. Reusing that number on the `0/650` transfer transform would permit a
different raw-loss geometry. V4 recommends transfer margin
`0.2797202700265491` Q, which preserves the same multiplicative `loss + 1`
factor under the transfer anchors. It is stricter than v3's copied Q margin and
remains a proposal, not an approved scientific tolerance.

**What calibration falsified or left unknown.** Observed work/wall p99 exceeded
v3 caps, hence the revisions above. Zero typed failures only bounds the failure
rate above by 11.2928 percent at one-sided 95 percent confidence and cannot
validate the proposed 5 percent model or 52 reserves. Repeated blocks have zero
within-profile paired SD because the policies are deterministic; 636 repeats
would not supply stochastic population evidence. V2 ties all baselines in four
profiles and is worse than no/generic for the minimalist. Three canonical
families collapse to three global lineage roots, so repetition cannot meet the
diversity prevalence floor. No shadow campaign means cross-profile dependence,
leakage precision and exact shadow allocation remain unknown. Aggregate-only
power calculations still do not establish power for the complete rule.

**Smallest decisions before the next engineering checkpoint.** Research and
exact-protocol owners must decide whether B-E4 requires separately pinned
autonomous research agents (recommended: yes) and approve their capability and
seed design. The five domain owners must then approve, modify or reject the
eight v4 values before any execution-ready freeze. A next bounded engineering
checkpoint may perform only non-qualifying stochastic/dependence and shadow
calibration under that approved population design. Trusted non-rejection attack
assessment, authenticated five-role ratification, exact-design verification,
and a separate one-use execution authorization remain later gates.

V4 design digest:
`sha256:038eecfa8c17ae5bb309e9417f9397777168ddeaf281c9601ca35402b5caf836`.
V4 proposal digest:
`sha256:faffff8e9d7f4c6748d76c84cfc0cd26f19eb996ece96d9705b89362d86d4f37`.
Status remains `STILL_BLOCKED / DESIGN_ANALYSIS_ONLY`; no item above is
approved. B-E4 remains `in_progress`; B-GATE remains unstarted.

## Autonomous-agent pilot proposal v1

**Status:** `ENGINEERING_ACCEPTED / OWNER_UNAPPROVED / PILOT_NOT_AUTHORIZED`

The canonical machine-readable proposal is
`.agent/preregistrations/B-E4_autonomous_agent_pilot_v1.json`, digest
`sha256:8ca1a79a9cd9866d54f52c797baf0ea392087c4652a1439017339a66610469f3`.
It is an immutable design proposal, not an approval, authorization, model call,
campaign record, qualification design, or substitute for v4's eight reserved
decisions. No autonomous inference or pilot, shadow, attack, or qualifying
campaign ran while preparing it.

### Recommended pilot

**Research question.** Can one common model, differentiated only by five
frozen research policies and four prior-information arms, use the exact
permitted B-07S/B-07B/B-07C research path and public practice feedback to
produce reconstructable strategies under matched ceilings, while revealing
nondegenerate task, profile, failure, resource, and dependence behavior needed
to design a later qualifying experiment?

**Population.** Use the exact listed OpenAI API model ID `gpt-5.6-terra` for
all five policies, through Responses with medium reasoning, low verbosity,
`store=false`, no built-in tools, no temperature/top-p override, and 32,768
input plus 8,192 output tokens/run. The provider currently advertises no
distinct dated Terra revision and Responses documents no seed input. Therefore
the future freeze must reverify the listed model and pricing and retain the
resolved response/model identity; it must not claim exact output replay.

This common-model design tests policy/interface behavior without adding a
model-comparison confound. `gpt-5.6-luna` is the cheaper hosted alternative,
but weaker capability could make a negative pilot less interpretable.
Separately pinned models may better resemble heterogeneous miners but confound
policy and model effects. Local `gpt-oss-20b` offers open weights and greater
runtime control, but Carbon presently has no approved inference adapter,
hardware calibration, or cost model for it.

The frozen policies are:

| Profile | Arm-neutral behavior | Capability boundary |
|---|---|---|
| PLANNER | Maintain a hypothesis table and choose the next proposal by expected information gain from permitted feedback | Declarative Strategy only |
| CODE_GENERATING | Emit and revise typed Strategy data | Generated text is never executed |
| EVOLUTIONARY | Record parent-child mutations and select survivors using permitted feedback | No hidden fitness signal |
| LITERATURE_GROUNDED | Cite a frozen public-safe synthetic-method corpus and revise hypotheses | No network; corpus digest required before execution |
| MINIMALIST | Make one proposal, inspect one practice result, then stop | Saved budget creates no extra attempt |

All arms receive the same system/capability policy, context ceiling, starting
information, network isolation, tool restrictions, retry rule, stopping rule,
and transcript/artifact recording. Only the registered prior material differs.

**Adaptation.** Adaptive profiles receive at most four iterations of
proposal -> B-07C practice -> permitted feedback -> next proposal. Feedback is
limited to practice admissibility, public observed ranges, typed protocol
rejections, and public resource facts. Invalid/rejected proposals consume an
attempt. Held-out, transfer, shadow, protected-realization, private reference,
and scorer information remain hidden. The final Strategy must descend from a
practice-admissible recorded ancestor. There is no v2-specific branch and ties,
negative effects, unchanged trajectories, and failure to find a candidate are
valid results.

**Task/search distribution.** Retain the existing three binary registered
construction families, hence eight direct candidates, but allow only four
attempts/run. Prospectively generate 12 task cells from three resource regimes
(data-scarce, balanced, compute-scarce), two registered observation-noise
levels, and two registered transfer shifts. One frozen calibration realization
per cell/profile is shared across all four arms; two public development blocks
per profile are excluded from calibration.

Before any model output, retain a task only if all eight candidates reconstruct,
each registered family is causally active, the endpoint has nonzero range, and
no candidate dominates every cell. Retain rejected task identities and
structural reasons. Never search for a favorable v2 effect. Any task change
requires a new prospective version and disjoint future qualifying namespace.
This makes final quality a real limited-search question while retaining time,
attempt, compute, and service use as supporting efficiency endpoints.

**Pairing and experimental unit.** One experimental unit is a
profile-by-frozen-task-realization block containing all four arms. The arms
share task and evaluator realization. The task is also shared across profiles,
so profile observations are crossed/dependent. Task, practice, candidate
construction, held-out/transfer, and future shadow seeds remain under their
existing owners and are separately derived for their roles; evaluator-held
material is not agent-visible. Provider randomness is a prospective recorded
draw ordinal, not seed-paired. Distinct hashes do not establish independence,
and common provenance alone does not prove a statistical cluster. The pilot
estimates descriptive crossed task/profile nuisance variation; it does not set
the final qualifying N. No shadow cases are allocated by this proposal.

**Size and resources.** The primary design is
`5 profiles x 4 arms x (2 development + 12 calibration) = 280 runs`.
One prospectively numbered reserve block/profile across four arms permits at
most 20 replacement runs, for a hard maximum of 300 runs. Each run has at most
four successful model turns and two provider attempts/turn, where the second
attempt is allowed only after verified external provider failure. This yields
hard ceilings of 2,400 provider request attempts, 19,660,800 billable input
tokens, 4,915,200 billable output tokens, 19,200 research-service calls,
35,700 fixture units, 270,000 aggregate run-wall seconds, and 432,000 seconds
campaign wall time.

At the official standard text prices verified on 2026-09-08 ($2/million input,
$12/million output), the retry-inclusive financial ceiling is **$98.304**.
Primary runs at 60% token utilization and no retries are estimated at
**$27.52512**. These exclude any future taxes, rate changes, or separately
priced features; built-in tools are disabled. Reverify before freeze.

Policy exhaustion, invalid candidates, and ambiguous timeout causes are not
replaceable. A reserve may replace only an exact retained external
infrastructure/reference failure established through the closed existing-owner
mapping. Partial, failed, rejected, and billed attempts remain evidence.
Exhausting the campaign without usable calibration is permitted and is recorded
as insufficient pilot evidence.

**Evidence use.** Pilot evidence may diagnose interface/schema defects,
token/latency/failure distributions, task/profile variance, baseline endpoint
and headroom, adaptation/lineage, and resource/cost calibration. Development
rows are excluded from calibration. Pilot evidence may not qualify B-E4,
approve or tune post-hoc thresholds, count as shadow/attack evidence, or earn
scientific, security/privacy, production, qualification, or LIVE maturity.

### Endpoint feasibility retained as proposed

V4's primary held-out equal-profile v2-minus-baseline Q estimand and separate
transfer non-inferiority support remain proposed; this pilot does not replace
them. Conditional on the historical no/generic mean `0.8300554565022396`, a
perfect v2 result can gain at most `0.16994454349776045` Q; conditional on the
v1 mean `0.8`, at most `0.2` Q. Both fall below the proposed strict primary
floor `0.4017350715246475`. These are empirical-configuration headroom facts,
not population bounds or reasons to lower the floor after observing outcomes.

The proposed transfer margin `0.2797202700265491` implies, for one paired
comparison at the boundary, `(loss_v2 + 1)/(loss_baseline + 1) <=
651^0.2797202700265491`, approximately `6.123724356957948`. Across averaged
log-quality contrasts it constrains the corresponding geometric mean, not
every run. Matching transform geometry alone is not a scientific justification
for accepting that deterioration; science/statistics owners must approve or
replace it.

### Four decisions required before pilot execution

| Decision | Recommended default | Material alternative / consequence | Required owners | Status |
|---|---|---|---|---|
| Population and capabilities | One common `gpt-5.6-terra` model with the five frozen, arm-neutral policies and closed capabilities above | Luna reduces spend but weakens interpretability; separate/local models add model or infrastructure confounds | Research, exact protocol, security | PROPOSED |
| Task, adaptation, seeds and evidence | Twelve prospectively included cells; four attempts; paired four-arm task blocks; crossed-profile dependence; hidden evaluator roles; permitted diagnostics only | Fewer cells/one-shot policies are cheaper but cannot calibrate heterogeneity/adaptation; more search risks saturation | Research, science, statistics, exact protocol, security | PROPOSED |
| Pilot resources, cost and stopping | 280 primary, 20 reserve, 300 maximum; exact ceilings and nonreplacement policy above; $98.304 hard ceiling | Smaller campaigns cost less but may not reveal stable nuisance/failure structure; larger work is unjustified before calibration | Research, statistics, exact protocol | PROPOSED |
| Permitted pilot evidence use | Design/engineering calibration only; no qualification, shadow/attack substitution, threshold approval, or post-hoc tuning | Broader use risks circularity and leakage into the future qualification design | Research, science, statistics, exact protocol, security | PROPOSED |

Owner approval must bind the exact proposal digest (or a prospectively revised
successor), frozen model/source/corpus/task/implementation manifests, resource
ceilings, and permitted evidence use through the repository-native approval
contract. Only then may a separate one-use pilot authorization be considered.
Approval of these four decisions does not approve v4's eight qualification
values, owner ratification, shadow/attack execution, or a qualifying campaign.

**Next step if all four decisions are approved:** implement and verify the
provider adapter, frozen corpus, prospective task generator/inclusion audit,
and exact pilot campaign manifest; reverify model availability/pricing; bind
the approved digest and approval evidence; obtain separate bounded pilot
authorization; then execute only the non-qualifying pilot. Until then the
proposal remains owner-unapproved and pilot execution is unavailable. B-E4
remains `in_progress`; B-GATE remains unstarted.
