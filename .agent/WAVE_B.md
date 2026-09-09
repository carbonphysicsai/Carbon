# Carbon Wave B Board

> **OWNER-DX-03 delivery override (2026-09-06):** Follow the current
> `.agent/DELIVERY_PROTOCOL.md` for engineering delivery. No mandatory human
> reviewer, GPT receipt, repeated full-diff review, or post-merge full-CI gate
> applies. Older process descriptions below are superseded; ticket scope,
> historical evidence, and human-reserved scientific/security authority remain.

**Status:** active in bounded development scope only when the merged `.agent/WAVE.md` names Wave B and this file as its controlling register. This file does not self-activate.
**Version:** 4.5
**Activation gate:** Wave A is closed in bounded engineering scope; PR #54 independently reviewed, passed CI, and normally merged the version 0.4 governance tree; and `.agent/WAVE.md` names Wave B and this board as controlling. B-01's independently reviewed correction head `ea1d11f76db419775803e268b39eaa8b789eef29`, tree `9f767ea16ffb7185ab64acff2542c7a8dcc2e339`, passed exact-head CI `33308009899`, normally merged in PR #57 as `4ee58d56862d0441d5d151d79db1fe3036f1025d` with the exact reviewed tree preserved, and passed exact-main CI `33308165189`; B-01 is authoritatively `done`. Version 0.5 inserted the owner-directed B-01E infrastructure ticket. Version 0.6 recorded B-02A closeout and B-07R's delegated conditional transition. Version 0.7 recorded the satisfied B-07R predicate and selected B-02B. Version 0.8 recorded B-02B's exact reviewed normal merge and exact-main CI and selected B-02C. Version 0.9 recorded B-02C's repaired exact reviewed normal merge and exact-main CI and selected B-03. Version 1.0 recorded B-03's exact reviewed-tree-preserving normal merge and exact-main CI, selected B-04 `in_progress` for working-contract authoring only, and withheld runtime until the exact contract tree normally merged and exact-main CI succeeded; PR #72 subsequently satisfied that historical gate. No multi-role approval bundle, exact-byte activation approval, or separate activation closeout is required before bounded development. B-07S still owns exact-protocol ratification before service-facing implementation.
**B-01E implementation evidence:** independently reviewed head `2025e235c83a994ed4f16c9a3a9d3c2766700061`, tree `4a506a1ae46cfcbf180eb5dbf68ed50caa0f1e09`, normally merged in PR #58 as `b4744a435e8bc7220c7dc03e6a993bb0a54c16a5` with the exact reviewed tree preserved; exact-main push run `33319267255` passed.
**B-02A closeout:** PR #60 normally merged reviewed head `f285399138ecfe95352d429bc26051b0a5fecbcf`, tree `61a4463ac459f7fe96545f2746511d6940246f57`, as `58ea866de52e3853b0b45e3217ee0625302aa663` with the same tree. Exact-head CI `33341717012`, Greptile 5/5 with no blocking failure and zero unresolved threads, and exact-main CI `33342015346` passed. B-02A is `done` only in bounded engineering scope.
**B-07R closeout:** PR #62 normally merged exact reviewed head `038aa3ffe51aaafe99803553380c396429144977` as `6e2a2640a6bd26755064acb0616382c8dcc0ba37` with exact reviewed/merge tree `5cf1aaf1fd11ef4775c170dd938c3190fa14145b`. Exact-head CI `33347664046`, Greptile 5/5 with zero unresolved threads, and exact-main CI `33347826166` passed. Issue #42 comment `5472621851` records completion. B-07R is authoritatively `done` in bounded engineering-architecture scope.
**B-02B closeout:** PR #64 normally merged exact reviewed head `68189e7068715a5d8054f0f7e64dc981ae1c37aa` as `b10b6e74fb3f8ab8a7427a6763c7db4f41341083`, with ordered parents `1c012468545f448aa758daf7dec17e409bb13bbc`, `68189e7068715a5d8054f0f7e64dc981ae1c37aa` and exact reviewed/merge tree `45273c527684b94afeb2f01b66a774b5426b6e0e`. Exact-head CI `33362051770`, Greptile 5/5 on exact-head check `99413062552` with zero unresolved threads, and exact-main CI `33368352662` passed. B-02B is authoritatively `done` in bounded engineering scope.
**B-02C closeout:** PR #66 normally merged repaired exact reviewed head `a30865d2349f1cc6e725f1ea15e923f8d7893e4c` as `1dc41288e2d0e516de21d05dc168b188791c39f5`, with ordered parents `319a765860ac6e93018124bd57a84bfd6679672e`, `a30865d2349f1cc6e725f1ea15e923f8d7893e4c` and exact reviewed/merge tree `eb9b0c9b899cc4be9c8e9b22c16a5a3a48406a12`. Repaired exact-head CI `33388174967`, Greptile 5/5 on exact-head check `99475440630` with zero comments, annotations, or unresolved threads, and exact-main CI `33388595061` passed. B-02C is authoritatively `done` in bounded engineering scope.
**B-03 closeout:** PR #69 normally merged exact reviewed head `702bf274b1a0c4bfefa075d8da08d3e7217a53d1` as `d5d1372f1311132ed9d60e10e36c4fb7d43a2473`, with ordered parents `b86daa5d8b0f8b3e86bb82c2661f405747a200df`, `702bf274b1a0c4bfefa075d8da08d3e7217a53d1` and exact reviewed/merge tree `65dc9f5da4368482ad8ece155a63ff24ef46bf24`. Exact-head CI `33452836347`, Greptile on exact-head check `99686337091` with all 36 files reviewed and zero comments, annotations, or unresolved threads, and exact-main push CI `33460078744` passed. Issue #42 closeout comment `5487728238` records the immutable evidence. B-03 is authoritatively `done` only in bounded merged engineering scope.
**B-04 contract / B-01F transition:** PR #72's external completion receipt
records the dynamic exact-head review/check, normal reviewed-tree-preserving
merge, and exact-main facts that ratified B-04's bounded engineering contract.
`OWNER-DX-01` inserts B-01F before runtime and queues B-01G as non-blocking
`todo`. Version 1.1 prepared B-01F `done` and B-04 runtime selection subject to
the exact B-01F candidate passing exact-head `Merge gate` and Greptile,
normally merging with reviewed-tree preservation, passing exact-main `Merge
gate`, and having its completed normalized external receipt posted. PR #73's
normalized receipt at comment `5497405775` satisfied that exact predicate:
reviewed B-01F head
`56093b3abe9e62e89d8aa0b5bf034e02d7d0ad97` normally merged as
`7161fe3c4a04821b7f676ab006bd5d313d0442d2` with exact tree
`619e366dead2288ccfd312f54ad09f17f86a1c62`; exact-main run `33532472507`
and `Merge gate` check `99944337076` succeeded. Version 1.2 therefore records
B-01F `done` and B-04's bounded runtime phase active from that exact main.
**B-04 runtime conditional closeout:** Version 1.3 prepares B-04 `done` and
B-05 `in_progress` only after B-04's exact unchanged final head passes every
scope-required check and `Merge gate`; fresh read-only Codex/GPT review of the
complete exact-head diff with every finding repaired or dispositioned; a
distinct non-author human approval carrying the closed exact-head/tree receipt;
successful `GPT review gate` and zero unresolved review threads; no applicable block; normal
expected-head merge with ordered second-parent/reviewed-tree equality; fetched
exact-main ancestry plus `Merge gate` and every push-only requirement; and a
completed normalized external receipt. Before that full predicate, B-04 remains
the authoritative selected `in_progress` ticket and B-05 remains `todo`. This
session starts no B-05 work.
**Delivery review migration:** `GOV-REVIEW-01-D1` preserves historical
Greptile receipts but replaces live/prospective review with fresh read-only
Codex/GPT complete-diff review, a distinct non-author human approval carrying
the exact-head/tree receipt, and the protected `GPT review gate`. It changes no
Wave-B ticket order, runtime semantics, or maturity.
**B-01H interposition:** PR #75's normalized receipt established B-04's full
completion predicate and selected B-05 `in_progress but NOT STARTED` at main
`650b035dae5629ae75b9e3f549b289f28cdbb9ba`. `OWNER-DX-02` now inserts
B-01H before B-05 as a bounded development-system ticket. B-05 returns to
`todo` without changing its Definition of Done and remains the next scientific
ticket and first planned harness pilot. B-01G remains todo and non-blocking.
**B-01H conditional closeout:** Version 1.6 prepares B-01H `done` in bounded
development-tooling scope and B-05 `in_progress` as its first pilot only after
the exact B-01H final head passes scope-required checks and `Merge gate`, fresh
complete-diff Codex/GPT review, finding closure, distinct non-author approval
with the closed receipt, successful `GPT review gate`, zero unresolved threads,
normal reviewed-tree-preserving expected-head merge, exact-main `Merge gate`,
and the completed external receipt. Before that predicate B-01H remains the
authoritative selected `in_progress` ticket and B-05 remains `todo` and not
started. The transition supplies no B-05 science or later authority.
**B-01H completed / B-05 selected:** PR #86's normalized receipt at comment
`5548725328` satisfies the complete Version-1.6 predicate. Reviewed B-01H head
`a4e2e5645b565330273d0d0d0d6e28d797cc8261` normally merged as
`f1a429de37290b3c7615ca051661a1d727528f78` with exact tree
`3e25bd65508c5c11d8d67558f9bd699808fc57a9`; required exact-head and
exact-main gates, complete-diff Codex/GPT review, distinct approval, and zero
unresolved findings/threads passed. The receipt selects B-05 `in_progress but
NOT STARTED` from that exact main. Version 1.7 records B-01H `done` in bounded
development-tooling scope and B-05 active in working-contract/first-slice
phase. Historical conditional text remains evidence of the earlier gate, not
the current state.
**B-05 bounded conditional closeout:** Version 1.8 prepares B-05 `done` in its
bounded engineering scope and B-06 `in_progress but NOT STARTED` only after
the exact B-05 final head passes every scope-required check and `Merge gate`,
fresh complete-diff Codex/GPT review, finding closure, distinct non-author
approval carrying the closed receipt, successful `GPT review gate`, zero
unresolved threads, normal reviewed-tree-preserving expected-head merge,
exact-main `Merge gate`, and the completed external receipt. Before that full
predicate B-05 remains the authoritative selected `in_progress` ticket and
B-06 remains `todo` and unstarted. The transition supplies no scientific,
qualification, security, production, network, economic, frontier, settlement,
emission, or `LIVE` authority.
**B-06 owner-directed transition:** Version 1.9 records the repository owner's
narrow direction to begin B-06 from merged PR #87 at main
`2500e51042f39a31f5056c74ce2ac5065657ec2a`, tree
`89763523576cef09f40fd8a205aa86d169d679de`. That merged B-05 implementation
is owner-accepted as B-06's dependency even though the ordinary Version-1.8
delivery predicate is not declared complete. B-05 therefore remains
`in_progress` as a factual delivery-record state with no active B-05 work;
B-06 is the selected `in_progress` ticket. This supersedes Version 1.8 only
for the B-05-to-B-06 advancement decision, requires no retrospective review,
changes no future delivery rule, and grants no scientific, security,
qualification, production, network, economic, review, merge, or `LIVE`
authority.
**B-06 completion / B-E3 closeout:** PR #88 normally merged B-06 as
`300bac5c7647f09d8ffd511d898a55bf3b8fa1e9` after its accepted head passed
`Merge gate`; completion comment `5560216570` selected B-E3. Version 2.2 is
the B-E3 shipping snapshot: after this snapshot's applicable acceptance and
normal merge, B-E3 is `done` in bounded structural engineering scope and B-07S
is the next eligible `todo` ticket. B-07S has not started and remains the exact
protocol gate before B-07 service implementation. No scientific adequacy,
standards compliance, security acceptance, qualification, production, or LIVE
authority is created.
**B-07S conditional closeout / B-07A next:** Version 2.3 is the B-07S shipping
snapshot. After its final unchanged revision passes applicable automated
acceptance and `Merge gate` and normally merges with the expected-head guard,
B-07S is `done` in bounded `SPECIFIED / RATIFIED` protocol scope and B-07A is
the next eligible `todo` ticket. The exact protocol keeps v1/v2 namespaces
disjoint, freezes every v2 request/result/error/resource/provider/bound and
task/prior/context rule, and preserves single domain ownership. It implements
no B-07 runtime and grants no scientific, security, network, production,
qualification, rights, economic, launch, or LIVE authority.
**B-07A conditional closeout / B-07B next:** Version 2.4 is the B-07A shipping
snapshot. After its final unchanged revision passes applicable automated
acceptance and `Merge gate` and normally merges with the expected-head guard,
B-07A is `done` in bounded `IMPLEMENTED / TESTED` shared-core and discovery
scope and B-07B is the next eligible `todo` ticket. B-07A adds the exact shared
v2 nominal wire vocabulary, canonicalization, `ChallengeInfo`, the sole
`InteractionManifest` schema, immutable historical discovery, and a local-only
two-operation adapter. The other ten operations remain explicitly unavailable
and owned by their assigned tickets. No dispatcher, task lifecycle, domain
provider/store, network, credential, qualification, production, or LIVE
authority is added.
**B-07B conditional closeout / B-07D1 next:** Version 2.5 is the B-07B shipping
snapshot. After its final unchanged revision passes applicable automated
acceptance and `Merge gate` and normally merges with the expected-head guard,
B-07B is `done` in bounded `IMPLEMENTED / TESTED` local lifecycle, private
record, and receipt scope and B-07D1 is the next eligible `todo` ticket. B-07C
remains todo because B-05's ordinary delivery record is incomplete and the
B-06-D0 exception was narrow. No practice execution, prior publication,
dispatcher, official score/submission, scientific/security/rights/network/
production qualification, or LIVE authority is added.
**Combined B-05 reconciliation / B-07C conditional closeout:** Version 2.6
records `OWNER-B05-B07C-01`: the owner selects current B-05 verification and
prospective closeout followed by B-07C, in one candidate and delivery, ahead of
B-07D1. The historical ordinary delivery predicate is superseded prospectively
by OWNER-DX-03. The audit confirms B-05's substantive measurement-authoring scope is
implemented and focused-tested; no measurement runtime repair is required.
The candidate implements B-07C's four exact task kinds with mock-only packs,
role-separated fresh draws, a non-champion scaffold, B-07B lifecycle/record/
receipt ownership, bounded registered findings, and resource-facts-only
calibration. After the unchanged ready revision passes applicable automated
acceptance and `Merge gate` and normally merges with the expected-head guard,
B-05 and B-07C are `done` only in their bounded engineering and in-process
fixture scopes. B-07D1 remains next, `todo`, and unstarted. Real scientific
values, practice populations, uncertainty/disclosure policy, security and
rights acceptance, qualification, production, network, commercial, and LIVE
authority remain unavailable.
**B-05/B-07C completion / grouped prior start:** PR #94 normally merged its
accepted head `5c1f2551aaf3f3d23ed838050db19cd98bf95dd3` as
`3d48b3569a8ecc68e15f8b4a151a10c804896f52` after run `34069874204` passed
Delivery preflight, Development Hub validation, Canonical environment, and
Merge gate. Version 2.7 therefore records B-05 and B-07C `done` in their bounded
engineering/fixture scopes and `OWNER-B07D123-01`: implement B-07D1 -> B-07D2
-> B-07D3 on one branch and PR, retaining separate Definitions of Done and
evidence. B-07D1 is active; D2/D3 remain dependency-gated until predecessor
tests pass. B-07E and later work remain todo and unstarted.

**Grouped prior conditional closeout / B-07E handoff:** Version 2.8 records
that the ordered D1, D2, and D3 implementation slices and their focused,
cross-ticket, invariant, and wheel checks passed in one candidate. Each ticket
retains its own Definition of Done and stable evidence. Their bounded `done`
states become authoritative only when the unchanged candidate passes applicable
automated acceptance and normally merges under OWNER-DX-03. B-07E is next
eligible, `todo`, and unstarted. No public pack activation, real record
ingestion, scientific/security/rights qualification, production signing,
B-07G dispatch, official scoring, production, or LIVE authority is granted.
**Grouped prior completion / B-07E conditional closeout:** PR #95 normally
merged accepted head `0b5e62728cd922e494116aaf9b3096346e1b7bb2` as
`258a35d91f45a1125879123bddccc52428d003b2` after run `34078606840`
passed applicable acceptance and Merge gate, making B-07D1/D2/D3 `done` in
their separate bounded scopes. Version 2.9 implements and tests B-07E exact
static inspection through B-02B/B-02C and the B-07A/B-07S response, plus an
ordinary forecast provider that remains `UNRESOLVED` without authorized
calibration and a distinct synthetic TEST_ONLY validation path. B-07E bounded
`done` and the B-07F handoff become authoritative only after the unchanged
candidate passes applicable acceptance and normally merges. B-07F stays
`todo`, unstarted, and outside this delivery. No quote, admission, price,
quota, capacity, observed-receipt ownership, scoring, settlement,
qualification, production-calibration, or LIVE authority is granted.
**B-07E completion / B-07F conditional closeout:** PR #96 normally merged
accepted head `4fe739995db6d5e5c84fa02bff47d9e179e4dc56` as
`5dc41eef62025a0114ee11bb98db3f9b877b247d` after run `34087649083`
passed applicable acceptance and Merge gate, making B-07E `done` in its
bounded scope. Version 3.0 specifies, implements, and tests B-07F's separate
fixture-only resolved-plan adapter through B-02B compilation, B-02C static
admissibility, FixtureOfficialEntropy, fixed B-03/B-04/B-05 fixture refs,
unchanged A5 scoring, and the existing A7/A8-shaped lifecycle. B-07F bounded
`done` and the B-07G handoff become authoritative only after the unchanged
candidate passes applicable acceptance and normally merges. B-07G stays
`todo`, unstarted, and outside this delivery. The A8 stub and v1 wire remain
unchanged; no arbitrary code, real reconstruction, qualification, production,
ranking, frontier, network, settlement, emission, or LIVE authority is granted.
**B-07F completion / B-07G conditional closeout:** PR #97 normally merged
accepted head `fd1b4483866630a04e5e53a4969f9eee24d6af65` as
`46874bf682ac6e465324631f982e1120652b21b1` after run `34099462304`
passed applicable acceptance and Merge gate, making B-07F `done` in bounded
TEST_ONLY engineering scope. Version 3.1 composes and tests the exact twelve
B-07S v2 operations through their single domain owners, preserves distinct
external-public and fixture constructor graphs, enforces canonical boundary,
error, disclosure, and TEST_ONLY rules, and leaves v1 and B-07F separate.
B-07G bounded `done` and the B-E1 handoff become authoritative only after the
unchanged candidate passes applicable acceptance and normally merges. B-E1
stays `todo`, unstarted, and outside this delivery. No listener, authenticated
transport, quote/admission, real training, scientific/security/rights
qualification, production, network, commercial, or LIVE authority is granted.
**B-E1 completion / B-E2 delivery and successor repair:** PR #98 normally merged
accepted head `7b88bc4aa1138d264aaa3f98d35f5a79a318c655` as
`527877bdd132c33569ac64c11b0a4360f5a08718` after run `34109277665`
passed applicable acceptance and Merge gate, making B-07G `done` in bounded
local composition/conformance scope. PR #99 accepted B-E1 head
`831a34598d6779d369f01de3523c3d8ee0385d18` passed run `34124228848`,
including `Merge gate`, and normally merged as the second parent of main
`c484fd308d866d4b05a2765a984ec014dd96386e`. PR #100 then accepted B-E2 head
`69620f76397c3e72b58ee0d59faf70505963fce1` in run `34137457116` and
normally merged it as `602628d3c62f01524336db888da8fcfc7ed379d7`.
Version 3.4 preserves that historical bounded `done` state and records the
B-E2-R1 successor repair: every untrusted nested response carrier is
reconstructed before comparison. The repair becomes complete after its
unchanged candidate passes applicable acceptance and normally merges. B-E4
stays `todo`, unstarted, and outside this delivery. No Julia repair,
scientific/security qualification, production backend, ranking, frontier,
network, settlement, emission, or LIVE authority is granted.
**B-E2 repair / B-E4 engineering, preregistration, and readiness:** PR #102 normally
merged the B-E2-R1 accepted head. PR #103 then merged B-E4's first fail-closed
engineering harness and shared semantic-toy work as
`ad1bd923beea8dcf469992e0e4f1bf4b2a32c0a8`. PR #105 normally merged the
bounded validation repair as `5932ed7870e8684f1c2532f129e5ed42c597d77f`,
tree `1a3d6330bf2272c249105d142f5a3dd366702b88`, after exact-head run
`34160811984`; post-merge smoke `34162168445` passed. PR #106 normally merged
the analysis-only v2 design checkpoint as
`a37b1058ea0b65ba28144b6d919714a1a5ad8a2f`, tree
`e0ece9eb4581468917003eb536b7aad5b1edf33f`, after exact-head run
`34171914557`; post-merge smoke `34173602520` passed. Version 3.8 records the
bounded execution-readiness checkpoint: three causal registered toy families,
an exploratory private TEST_ONLY pack, five fixed data-only drivers, preflight
accounting, canonical intervention identities, and fail-closed readiness
carriers. B-07F's exact historical sampling-only identities remain unchanged;
only the three-family extension uses prospective identity v2. The centralized
arm factory provides non-qualifying preflight surrogates only; the required
GENERIC domain-neutral workflow artifact and exact v1 `PrivatePriorProjection`
remain unmaterialized. The v3 proposal is `STILL_BLOCKED` because complete B-07C practice/
feedback/final selection is absent, four profiles lack an identifiable v2
treatment contrast, candidate-bound fixture seeds remain unresolved,
fixed-proposal diversity is zero only under a non-authoritative task-to-run
mapping, and the recorded analyzer fails closed. Trusted endpoint receipts/Q
transforms, exact preflight-result/request correlation, retained-reserve
binding, complete artifact manifests, attack/leakage evidence, ratification,
and qualifying-evidence integrations remain unavailable. Driver configuration/
policy digests do not bind executable source bytes. The separate bounded
TEST_ONLY official-shaped association binds only a preflight slot/proposal to
an A7 receipt under its own no-qualification ceiling; it does not bind
requester/session, trusted B-07S origin/request-to-result correlation, or full
lifecycle/final-slot policy. Exact shadow-case count/profile allocation is
unpinned, and `636` blocks/profile is
conditional on an unvalidated cross-profile ICC assumption of `rho=0`. Every
value and statistical assumption remains `PROPOSED`. B-E4 remains
`in_progress`; B-GATE is `todo` and unstarted. No design proposal,
simulation, dry run, or engineering test is a utility, leakage, scientific,
security/privacy, production, qualification, or LIVE result.
Version 3.9 prospectively supersedes that readiness snapshot for the first
non-qualifying lifecycle delivery. PR #107 normally merged the readiness base
as `ffbb621c76acc73b8e27911df50ad607e0b5193c`. The current successor candidate
materializes the exact domain-neutral GENERIC workflow and existing private v1
projection, binds installed driver source, and executes the 5-profile x 4-arm x
1-block deterministic integration matrix through B-07S, B-07B/B-07C paired
practice, public aggregate-only feedback, final selection, and unchanged A7/A8
fixture evaluation. It adds private B-07F held-out/transfer endpoint binding
and complete-run attempt/work/service/resource/wall enforcement without
changing public wire contracts or granting qualification. Authoritative
campaign evidence/correlation and frozen full-lifecycle calibration remain the
next engineering deliveries. The deterministic population is not yet accepted
as representative autonomous agents, and utility identifiability, diversity,
shadow dependence/allocation, leakage/attack evidence, authenticated
ratification, one-use authorization, and all eight reserved values remain
blocked. B-E4 stays `in_progress`; B-GATE stays `todo` and unstarted.
Version 4.0 records that PR #108 normally merged that complete lifecycle as
`d4a496b6b43d5139fc636428556822e6a5ec82e6`, tree
`5eed5ec6980625a097bb936c1a66e87145b4ae24`, after exact-head acceptance run
`34205242845`; post-merge main smoke `34207883089` passed. The current successor
candidate adds private-factory rehearsal manifests and run/campaign evidence,
exact successful/rejected B-07S request/reply correlation, B-07B task/run and
execution provenance, requester/session/final-candidate/A7/A8/private-endpoint
binding, canonical v2 lineage, transcript/provenance clusters, and prospective
same-profile reserves restricted to retained infrastructure/reference failures.
All such evidence remains non-qualifying with no promotion path. Frozen full-
lifecycle calibration is next. Representative autonomous-agent scope, utility
identifiability, diversity, shadow allocation/dependence/leakage, trusted
attacks, authenticated owner verification, one-use authorization, and all
reserved approvals remain blocked. B-E4 stays `in_progress`; B-GATE stays
`todo` and unstarted.
Version 4.1 records that PR #109 normally merged the rehearsal-evidence stage
as `8c907181b7f63b5c0153e2fa097ce28ec647ebb5`, tree
`c16a1bd8274d1ffb8573f7b95aff2be660d5f17f`, after exact-head acceptance run
`34212480037`; post-merge main smoke `34215206763` passed. The current
successor candidate preserves an aborted zero-row calibration attempt, records
one fresh frozen 25-block/100-run full-lifecycle calibration, and issues v4
only because work/wall caps and transfer-margin content changed. Deterministic
repeats have zero paired SD, v2 is non-positive, three family identities
collapse to three lineage roots, the failure upper bound exceeds the proposed
ceiling, and no shadow dependence evidence exists. V4 is therefore
`STILL_BLOCKED`; all eight values remain `PROPOSED`. Representative autonomous-
agent scope, seed design, stochastic/dependence and leakage calibration,
trusted attacks, five-role ratification, one-use authorization, and qualifying
evidence remain unavailable. B-E4 stays `in_progress`; B-GATE stays `todo` and
unstarted.
Version 4.2 records that PR #110 normally merged accepted calibration head
`4412f546338f7d0a58594b577d952b759bcbef9e` as
`b693bbe2e23774c93303d24416f55ebdd5f6c0e9` after applicable acceptance. The
current successor candidate makes policy-controlled work/wall/fixture
exhaustion and ambiguous timeout attribution nonreplaceable, retains exact
resource observations, and limits reserves to eligible external failures
issued from exact existing-owner outcomes. Conditional on historical baseline
means, the registered endpoint maximum cannot clear the proposed primary floor;
that diagnostic is not a population bound or utility decision. No pilot,
shadow, attack, or qualifying campaign ran. V4 remains `STILL_BLOCKED`, all
eight values remain `PROPOSED`, B-E4 stays `in_progress`, and B-GATE stays
`todo` and unstarted.
Version 4.3 records that PR #111 normally merged accepted correctness head
`c325843a1ea2383567e044e0f4c352e5b9add435` as
`47677572e72795338236a283eb588357a25dbda2`, preserving tree
`2f963557fb0210358558b17227184013d173f10a`. Policy exhaustion and ambiguous
timeouts are now nonreplaceable, exact resource evidence is retained, and
conditional headroom remains explicitly non-qualifying. The current separate
candidate adds `.agent/preregistrations/B-E4_autonomous_agent_pilot_v1.json` as
`ENGINEERING_ACCEPTED / OWNER_UNAPPROVED / PILOT_NOT_AUTHORIZED`: one common
Terra model, five policies, 12 prospective task cells, four attempts, 280
primary plus 20 reserve runs, and a `$98.304` hard ceiling. Its four grouped
owner decisions remain `PROPOSED`; it has no provider or execution path. No
inference, pilot, shadow, attack, or qualifying campaign ran. V4's eight
qualification values remain `PROPOSED`, B-E4 remains `in_progress`, and B-GATE
remains `todo` and unstarted.
Version 4.4 records that PR #112 normally merged pilot-v1 main
`c6d6c1dc257b00be06d24f5736f7159e68849b04`, tree
`b211adf15751d5a54205eaa978ed2c82c79caf8a`. The current correction binds
eligible failures to one exact pre-execution campaign/run/session and prevents
reuse of failed sources or reserves. Prospective resource observations separate
predicted, reserved, confirmed, and unreconciled use, admit complete paired
practice, preserve completed work through later failure, and retain ambiguous
in-flight reservations. Pilot v2 strictly validates the complete nested
proposal and adds offline-only interaction, payload, exact 12-cell task, and
bounded inclusion-audit helpers. It proposes 40 development, 240 calibration,
and 20 reserve runs under the unchanged `$98.304` spending ceiling; an all-
input-cache-write `$108.1344` maximum is an owner-unapproved alternative. Its
five grouped decisions remain `PROPOSED`, and no provider adapter, permission,
approval, authorization, inference, or campaign exists. V4 stays
`STILL_BLOCKED`, B-E4 stays `in_progress`, and B-GATE stays `todo` and
unstarted.
Version 4.5 records that PR #113 normally merged the exact failure-association,
prospective resource-accounting, and strict pilot-v2 correction as
`f5f6a82a1dfd8193c4eafa73ad5370076e8ee10b`. The current successor candidate
implements one sequential `5-profile x 4-arm x 2-task` DEVELOPMENT runner over
the existing B-07S/B-07B/B-07C and A7/A8 TEST_ONLY paths, a strict Responses
adapter that cannot obtain an admission, a deterministic offline transport, a
durable intent/result journal, exact source/prompt/corpus/treatment/task/seed-
commitment identities, and a `$14.42` owner-review request under the unchanged
proposed `$98.304` pilot ceiling. Its canonical offline artifact completes all
40 fixture-service slots with zero provider inference and zero spend. The five
pilot decisions remain `PROPOSED`; no authenticated approval, one-use
authorization, credential, provider call, calibration, shadow, attack, or
qualifying campaign exists. V4 stays `STILL_BLOCKED`, B-E4 stays
`in_progress`, and B-GATE stays `todo` and unstarted.
**Mission:** make one scientific exam authorable and make the miner research loop executable with fixtures, without claiming that the exam, practice signal, prior, backend, or network path is qualified.
**Primary contract:** `Design_Specs/Miner_MCP_Wave_B_Research_Contract.md`
**Codex entry point:** `.agent/WAVE_B_CODEX_HANDOFF.md`
**Program crosswalk:** `launch/Carbon_Testnet_to_Mainnet_Launch_Path_v1.0.4.md`
preserves this board unchanged and begins its Bittensor roadmap only after
Wave B. This board remains the controlling ticket register.

Authority comes from the merged active `.agent/WAVE.md`, selected ticket, and
merged delegated-decision protocol, not this file alone or prior role
approval. B-01, B-01E, B-01F, B-02A, B-07R, B-02B, B-02C, and B-03 are
authoritatively `done` in their recorded bounded scopes. B-01F's predicate is
satisfied, and PR #75's receipt establishes B-04's bounded completed state.
B-01H's complete conditional predicate has passed at the identities above.
Under B-06-D0, merged B-05 is the owner-accepted dependency while its ordinary
delivery record remains `in_progress`. PR #88 completed B-06 in bounded merged
engineering scope and selected B-E3. This merged snapshot completes B-E3's
crosswalk, validation, canonicalization, and audience-safe reporting scope.
Version 2.3 ratified B-07S through its completed shipping predicate. This
Version 2.4 completed B-07A as above. Version 2.5 completed B-07B. This
Version-2.6 combined shipping snapshot conditionally reconciles B-05 and
completes B-07C while leaving B-07D1 next, `todo`, and unstarted.
Campaign-specific acquisition/result
manifests and all other machine-implementable B-06 features are present. The five historical
complete-diff reviews found nine actionable defects, all repaired; their
receipts and approvals apply only to the pre-integration tree and are not
current merge predicates under OWNER-DX-03. The integrated ready revision
passed its applicable automated acceptance and normal expected-head merge.
Working engineering decisions may proceed after durable record and applicable
notification without affirmative lead response. A human-reserved value
remains unavailable and blocks its affected behavior, not unrelated bounded
work.

---

## 1. Wave B outcome

Wave B closes only when Carbon can demonstrate this fixture-only chain:

```text
public scientific contracts
        ↓
ChallengeInteractionManifest
        ↓
Strategy + ParameterCatalog
        ↓
ResolvedConstructionPlan
        ↓
nominal practice task on mock-only rights
        ↓
ExperimentRecord + ResearchReceipt
        ↓
resolved-plan fixture-official reconstruction through unchanged v1 lifecycle
        ↓
PriorPack TEST_ONLY build; v2-backed public v1 projection remains unavailable
        ↓
Dossier / qualification manifest remains fail closed for LIVE
```

Wave B does not include real miner training, production reconstruction, authenticated remote transport, official scientific evidence, LIVE activation, network weights, or learned public priors from official outcomes.

---

## 2. Decisions this board is designed to ratify

1. Wave B remains declarative. It accepts no arbitrary participant code.
2. Strategy v1 remains the input envelope; a public Challenge-bound `ParameterCatalog` and deterministic compiler supply executable semantics, including only registered `R_strategy` training policies inside Challenge-owned support.
3. Unknown, unused, coerced, silently defaulted, or silently clamped parameters fail closed.
4. Practice and official execution use separate nominal types and authority paths.
5. Paired practice comparison uses common fresh public cases and returns bounded aggregate evidence.
6. Research tasks are asynchronous, idempotent, lineage-bearing, and receipt-producing.
7. Structural prior alignment, resource forecasting, operational quote, and measured practice remain distinct.
8. Carbon publishes no official-score, rank, gate, or winner prediction.
9. Priors are immutable Challenge-level artifacts with identical bytes for every miner; personalization happens miner-side.
10. Wave B prior handling is mechanically limited to private `TEST_ONLY`
    staging and reviewed public-publication schemas/negative tests. Public-class
    activation and qualified learned publication remain later and fail closed.
11. A distinct test-only prior authorization receipt (exact type owned by
    B-07S) carries `TEST_ONLY / NOT_UTILITY_QUALIFIED`, permits only private
    exact-ref fixture retrieval, and cannot substitute for a public
    `PriorPublicationReceipt`.
12. The catalog may expose Challenge-owned, versioned, reconstructible
    structure-preserving components as optional construction levers. A
    component label or claimed invariant never satisfies a scientific gate;
    the reconstructed output remains subject to the same measurements and
    hidden stress evidence as every other candidate.
13. Resource-saving admission checks, staged reconstruction, and sequential
    evidence allocation may conserve compute, but no partial build, forecast,
    proxy, or screen can create `SUPERIOR`. Promotion-grade evidence preserves
    reconstruction-by-case dependence and fails closed when it cannot resolve
    the claim.

---

## 3. Ticket board

Statuses on this board use only `todo`, `in_progress`, `done`, and `blocked`.

| ID | Deliverable | Status | Evidence | Driver | Accountable reviewer | Depends on | Master questions | Effort | Target |
|---|---|---|---|---|---|---|---|---|---|
| B-01 | Wave B orientation, exact authority pin, conflict ledger, and baseline evidence | done | `.agent/evidence/wave_b/b-01.md` | Codex / protocol lead | Tech lead | merged A11, merged A12, `.agent/WAVE_A_REPORT.md`, explicit Wave B activation | MQ-018 | S | WB-0 |
| B-01E | Canonical development environment, deterministic dependency lock, local/CI command parity, machine-enforced code-authority boundary, and legacy executable quarantine | done | `.agent/evidence/wave_b/b-01e.md` | Codex + SRE | Tech lead + SRE | B-01 | MQ-018 | L | WB-0/1 |
| B-01F | Development throughput hardening: delivery hygiene, canonical wrapper, path-aware gates, live PR validation, bounded Hub fan-out, external receipts, and stable Merge gate | done | `.agent/evidence/wave_b/b-01f.md`; PR #73 receipt comment `5497405775` records the satisfied predicate and bounded merged scope | Codex + SRE | Tech lead + SRE | B-01E, ratified B-04 engineering contract | MQ-018 | L | WB-1/2 |
| B-01G | Deterministic checked-in static schema-codegen shadow proof | todo | — | Codex | Tech lead + domain owners | B-01F; non-blocking for B-04 | MQ-018 | S | future tooling |
| B-01H | Carbon-native iterative Planner/Developer/Tester harness, identity-bound resume, and B-05 pilot manifest | done | `.agent/evidence/wave_b/b-01h.md`; PR #86 comment `5548725328` (bounded merged development-tooling scope; installed Codex remains fail-closed incompatible) | Codex | Tech lead + SRE + security | B-01F, completed B-04 predicate | MQ-018 | L | development tooling |
| B-02A | Physical task, candidate output, population, SamplingPlan, and canonical-case identities | done | `.agent/evidence/wave_b/b-02a.md` (PR #60 exact reviewed/merge tree, Greptile, exact-head and exact-main CI recorded; bounded engineering scope only) | Codex + SciML | SciML + statistics + protocol | B-01E | MQ-001, MQ-002 | L | WB-1 |
| B-02B | Candidate assembly, ParameterCatalog, optional structural-component refs, StrategyCompiler, and resolved-plan contracts | done | `.agent/evidence/wave_b/b-02b.md` (PR #64 exact reviewed/merge tree, Greptile, exact-head and exact-main CI recorded; bounded engineering scope only) | Codex + SciML | Protocol + SciML + security | B-02A, B-07R, A2 | MQ-005, MQ-008, MQ-015, MQ-024 | L | WB-2 |
| B-02C | ResearchResourcePolicy, resource classes, ceilings, reconstruction-stage receipt seams, enforcement, and receipts | done | `.agent/evidence/wave_b/b-02c.md` (PR #66 repaired exact-head review, normal exact-tree-preserving merge, and exact-main CI recorded; bounded engineering scope only) | Codex + SRE | Protocol + SRE + security + operations + economics | B-02B, B-07R | MQ-008, MQ-015, MQ-017, MQ-024 | M | WB-2 |
| B-03 | Generator API and fixed-viscosity Burgers fixture implementation | done | `.agent/evidence/wave_b/b-03.md` (PR #69 exact reviewed-tree-preserving normal merge, exact-head CI/Greptile, exact-main CI, and issue #42 closeout recorded; bounded engineering scope only) | Codex + SciML | SciML + statistics + protocol | B-02A | MQ-002, MQ-003 | L | WB-1/2 |
| B-04 | ReferencePolicy, TruthAsset, primary/witness runner interfaces, and typed reference failure | done | `.agent/evidence/wave_b/b-04.md` (PR #75 satisfied the exact-head review, distinct approval, normal reviewed-tree-preserving merge, exact-main gates, and receipt predicate; bounded fixture runtime is `IMPLEMENTED` and `TESTED`, while every scientific/security/production qualification remains unearned) | Codex + SciML | SciML + statistics + protocol + independent reviewer | B-02A; B-01F satisfied for runtime | MQ-004 | L | WB-1/2 |
| B-05 | MeasurementContract, ReconstructionEvidencePolicy, dependence-aware UncertaintyPolicy, and Score Pack authoring bindings | done | PR #94 accepted/merged the current verification and prospective OWNER-DX-03 reconciliation with no runtime repair; `Design_Specs/Measurement_and_ScorePack_Authoring_Contract.md`; `.agent/evidence/wave_b/b-05.md` | Codex + SciML | SciML + statistics + protocol + SRE | B-02C, B-04, B-01H | MQ-005, MQ-006, MQ-007, MQ-008 | L | WB-2 |
| B-06 | D1-D12 Dossier, interval-coverage evidence, and qualification-manifest machinery | done | `Design_Specs/Validation_Dossier_Manifest_Contract.md`; `.agent/plans/B-06_validation_dossier_manifest.md`; `.agent/evidence/wave_b/b-06.md`; PR #88 completion comment `5560216570` | Codex | SciML + statistics + protocol + security + independent reviewer | B-02A, B-03, B-04, B-05, A3; merged predecessor dependency is owner-accepted by the recorded decision | MQ-003 through MQ-008, MQ-018 | M | WB-2/3 |
| B-07R | Ratify the miner research architecture and authority boundaries | done | `.agent/evidence/wave_b/b-07r.md` (PR #62 exact reviewed/merge tree, Greptile, exact-head and exact-main CI recorded; bounded architecture only) | Protocol lead + Codex | Protocol + science + security + rights | B-01, B-02A | MQ-015 through MQ-018, MQ-024 through MQ-026, MQ-045, MQ-051 | M | WB-1 |
| B-07S | Ratify the exact v2 wire, lifecycle, error, canonicalization, bound, and local-adapter contract | done | `Design_Specs/Miner_MCP_Wave_B_Service_Protocol.md`; `.agent/plans/B-07S_research_service_protocol.md`; `.agent/evidence/wave_b/b-07s.md`; `tests/invariants/test_b07s_research_service_protocol.py` | Protocol lead + Codex | Protocol + science + security + rights/counsel | B-07R, B-02A, B-02B, B-02C | MQ-015 through MQ-018, MQ-024 through MQ-026, MQ-045 | M | WB-2 |
| B-07A | Shared v2 protocol primitives, InteractionManifest, and public research-capability discovery | done | `carbon/research`; `.agent/plans/B-07A_interaction_manifest.md`; `.agent/evidence/wave_b/b-07a.md`; `tests/cpu/test_b07a_protocol_core.py`; `tests/cpu/test_b07a_discovery_adapter.py`; `tests/invariants/test_b07a_research_discovery_boundaries.py` | Codex | Protocol + security | B-02A, B-02B, B-02C, B-05, B-07R, B-07S, A3, A9 | MQ-005, MQ-006, MQ-015, MQ-016, MQ-017, MQ-024 | L | WB-3 |
| B-07B | ResearchTask, ExperimentRecord, ResearchReceipt, evidence classes, and lineage | done | `carbon/research/lifecycle.py`; `carbon/research/records.py`; `.agent/plans/B-07B_research_records.md`; `.agent/evidence/wave_b/b-07b.md`; `tests/cpu/test_b07b_research_task_lifecycle.py`; `tests/invariants/test_b07b_research_task_boundaries.py` | Codex | Protocol + science + security + rights/counsel | B-02B, B-07R, B-07S, B-07A, A11 | MQ-016, MQ-026, MQ-045 | M | WB-3 |
| B-07C | Nominal mock/practice service, practice pack, scaffold, rehearsal, and paired comparison | done | PR #94; `Design_Specs/Mock_Practice_Execution_Contract.md`; `.agent/plans/B-07C_mock_practice.md`; `.agent/evidence/wave_b/b-07c.md`; `carbon/practice` | Codex + SciML | Science + statistics + security | B-02C, B-03, B-05, B-07A, B-07B, B-07S, A4, A8, A9 | MQ-002 through MQ-005, MQ-015, MQ-016 | L | WB-3/4 |
| B-07D1 | PriorPack schema, immutable store/index, estimands, receipts, and offline compatibility projection | done | `.agent/plans/B-07D1_D2_D3_prior_delivery.md`; `.agent/evidence/wave_b/b-07d1.md`; `carbon/research/prior_store.py`; `carbon/prior_compat.py` | Codex + Landscape | Science + security + protocol | B-07A, B-07B, B-07S, A6, A9, A11 | MQ-016, MQ-018, MQ-025, MQ-026, MQ-045, MQ-051 | L | WB-3/4 |
| B-07D2 | TEST_ONLY publisher and persistent cumulative-disclosure ledger | done | `.agent/evidence/wave_b/b-07d2.md`; `carbon/research/prior_publisher.py` | Codex + Landscape | Science + statistics + security + protocol + rights | B-07D1, B-07B | MQ-016, MQ-018, MQ-025, MQ-026, MQ-045, MQ-051 | L | WB-4 |
| B-07D3 | Static exact/active provider, historical retrieval, and deterministic prior alignment | done | `.agent/evidence/wave_b/b-07d3.md`; `carbon/research/prior_provider.py` | Codex + Landscape | Protocol + security | B-07D1, B-07D2, B-07S, A9 | MQ-016, MQ-017, MQ-025, MQ-026 | M | WB-4 |
| B-07E | Static resource analysis, calibrated forecast seam, and receipt separation | done | `.agent/plans/B-07E_estimation_resources.md`; `.agent/evidence/wave_b/b-07e.md`; `carbon/research/resource_estimation.py`; `tests/cpu/test_b07e_resource_estimation.py`; `tests/invariants/test_b07e_resource_estimation_boundaries.py` | Codex + SRE | Protocol + SRE + statistics | B-02B, B-02C, B-07A, B-07B, B-07C, B-07D3, B-07S | MQ-008, MQ-017, MQ-024 | M | WB-4 |
| B-07F | Resolved-plan fixture-official construction adapter behind unchanged v1 lifecycle; exact historical sampling-only identity preserved while three-family use receives prospective identity v2 | done | `.agent/plans/B-07F_fixture_official_construction_adapter.md`; `.agent/evidence/wave_b/b-07f.md`; `Design_Specs/Resolved_Plan_Fixture_Construction_Adapter_Contract.md`; `carbon/traineval/resolved_fixture.py`; `tests/cpu/test_b07f_resolved_fixture_adapter.py`; `tests/invariants/test_b07f_resolved_fixture_boundaries.py` | Codex + SciML | Protocol + science + security | B-02B, B-02C, B-03, B-04, B-05, B-07S, A7, A8, A9 | MQ-004, MQ-005, MQ-008, MQ-015, MQ-024 | L | WB-3/4 |
| B-07G | Research-service composition, B-07S-ratified closed-operation dispatch, and conformance | done | `.agent/plans/B-07G_research_service_integration.md`; `.agent/evidence/wave_b/b-07g.md`; `carbon/research/service.py`; `tests/cpu/test_b07g_research_service.py`; `tests/invariants/test_b07g_research_service_boundaries.py` | Codex | Protocol + science + security | B-02B, B-07A, B-07B, B-07C, B-07D3, B-07E, B-07S, A9 | MQ-015 through MQ-018, MQ-024 through MQ-026, MQ-045 | L | WB-4/5 |
| B-E1 | R0/R1/R2 reproducibility, dependence-aware reconstruction × whole-case interval, staged-evidence audit, and typed contested-outcome harness | done | `Design_Specs/Reproducibility_Harness_Contract.md`; `.agent/plans/B-E1_reproducibility_harness.md`; `.agent/evidence/wave_b/b-e1.md`; `carbon/reproducibility`; `tests/cpu/test_be1_reproducibility_harness.py`; `tests/invariants/test_be1_reproducibility_boundaries.py` | Codex + SciML | Statistics + SciML | B-02A, B-02B, B-02C, B-04, B-05 | MQ-007, MQ-008 | L | WB-2/3 |
| B-E2 | Julia/reference failure contract | done | `.agent/plans/B-E2_reference_failure.md`; `.agent/evidence/wave_b/b-e2.md`; `carbon/evaluation/service_boundary.py`; `carbon/evaluation/service_fixtures.py`; `tests/cpu/test_be2_reference_failure_boundary.py`; `tests/invariants/test_be2_reference_failure_boundaries.py` | Codex + SciML | SciML | B-04 | MQ-004 | M | WB-2 |
| B-E3 | Credibility crosswalk and evidence manifest | done | `Design_Specs/Credibility_Crosswalk_Contract.md`; `.agent/plans/B-E3_credibility_crosswalk.md`; `.agent/evidence/wave_b/b-e3.md` | Codex + SciML | Independent reviewer | B-06 | MQ-003 through MQ-008 | S | WB-3 |
| B-E4 | Autoresearch workflow, utility, leakage, poisoning, and aligned-cheating gauntlet | in_progress | `.agent/plans/B-E4_agent_gauntlet.md`; `.agent/evidence/wave_b/b-e4.md`; `.agent/evidence/wave_b/b-e4-development-offline-integration-v1.json`; `.agent/evidence/wave_b/b-e4-preflight-calibration-v1.json`; `.agent/evidence/wave_b/b-e4-full-lifecycle-calibration-v1.json`; `.agent/preregistrations/B-E4_development_execution_request_v1.json`; `.agent/preregistrations/B-E4_full_lifecycle_calibration_v1.json`; historical `.agent/preregistrations/B-E4_recommended_design_v2.json` and `docs/context/B_E4_PREREGISTRATION_OWNER_DECISION_PACK_2026-09-08.md`; historical `.agent/preregistrations/B-E4_recommended_design_v3.json`; `.agent/preregistrations/B-E4_recommended_design_v4.json`; historical `.agent/preregistrations/B-E4_autonomous_agent_pilot_v1.json`; `.agent/preregistrations/B-E4_autonomous_agent_pilot_v2.json`; `docs/context/B_E4_EXECUTION_READINESS_OWNER_DECISION_PACK_2026-09-08.md`; `carbon/gauntlet`; `scripts/dev/generate_be4_full_lifecycle_calibration.py`; `scripts/dev/run_be4_development_pilot.py`; `tests/cpu/test_be4_development_pilot.py`; `tests/cpu/test_be4_full_lifecycle_calibration.py`; `tests/cpu/test_be4_nonqualifying_lifecycle.py`; `tests/cpu/test_be4_rehearsal_evidence.py`; `tests/cpu/test_be4_readiness_proposal.py`; `tests/cpu/test_be4_autonomous_pilot_proposal.py`; `tests/invariants/test_be4_gauntlet_boundaries.py` | Codex + research + security | Research + security + science + statistics + protocol | B-07A, B-07B, B-07C, B-07D1, B-07D2, B-07D3, B-07E, B-07F, B-07G, B-07S, B-E1, A12 | MQ-005, MQ-015, MQ-016, MQ-024, MQ-025, MQ-026 | L | WB-5 |
| B-GATE | Fixture integration, invariant proof, closeout report, and no-placeholder-LIVE audit | todo | — | Codex | Tech lead + science + protocol + security + rights | B-01, B-01E, B-01F, B-02A, B-02B, B-02C, B-03, B-04, B-05, B-06, B-07R, B-07S, B-07A, B-07B, B-07C, B-07D1, B-07D2, B-07D3, B-07E, B-07F, B-07G, B-E1, B-E2, B-E3, B-E4; B-01G explicitly non-blocking | MQ-001 through MQ-008, MQ-015 through MQ-018, MQ-024 through MQ-026, MQ-045, MQ-051 | M | WB-5 |

Effort uses the launch-plan scale: S is at most one primary-lane day, M is two to three, and L is four to seven. Including the owner-directed B-01E insertion, the decomposed board totals roughly **76-127 primary-lane days if executed serially**. With two qualified non-overlapping implementation lanes and timely reviews, the dependency spine is approximately **49-83 elapsed engineering days (10-17 working weeks)**. A single lane is approximately **16-26 working weeks**. These are planning estimates, not calendar commitments; scientific/security/rights decisions, review queueing, and later qualification are additional.

Those historical launch estimates predate the owner-directed B-01F insertion
and do not include future non-blocking B-01G. B-01F hardens delivery rather than
rebaselining scientific-ticket duration; a later launch-planning update may
revise estimates prospectively.

`WB-0` through `WB-5` are dependency phases, not calendar promises: activation/orientation; scientific foundations; semantic and wire contracts; core research implementations; prior/practice/resource integration; gauntlet and closeout. Launch v1.0.4 preserves the Wave-B decomposition and records the post-Wave-B network path; calendar dates remain unresolved until staffing is approved.

---

## 4. Dependency order

```text
B-01 → B-01E → B-02A
B-04 bounded engineering contract → B-01F → B-04 runtime
B-01F → B-01G (future non-blocking tooling lane)
B-04 completed runtime → B-01H → B-05 first harness pilot
B-02A → B-03
B-02A → B-04
B-02A → B-07R
B-02A + B-07R + A2 → B-02B → B-02C → B-07S
B-02C + B-04 → B-05
B-02B + B-02C + B-07R + B-07S → B-07A → B-07B
B-07A + B-07B + B-07S → B-07D1 → B-07D2 → B-07D3
B-02C + B-03 + B-05 + B-07A + B-07B + B-07S → B-07C
B-02B + B-02C + B-07A + B-07B + B-07C + B-07D3 + B-07S → B-07E
B-02B + B-02C + B-03 + B-04 + B-05 + B-07S + A7/A8/A9 → B-07F
B-02B + B-07A + B-07B + B-07C + B-07D3 + B-07E + B-07S + A9 → B-07G

B-02A + B-02B + B-02C + B-04 + B-05 → B-E1
B-04 → B-E2
B-02A + B-03 + B-04 + B-05 + A3 → B-06 → B-E3
B-07A/B/C/D1/D2/D3/E/F/G/S + B-E1 + A12 → B-E4
all required Wave B tickets except non-blocking B-01G, including B-01H → B-GATE
```

B-03, B-01F, B-04, and B-01H are closed in their bounded merged scopes. PR
#75's normalized receipt satisfied B-04's full completion predicate and
selected B-05 `in_progress but NOT STARTED`; `OWNER-DX-02` subsequently
interposed B-01H. PR #86 comment `5548725328` proves B-01H's complete
predicate and selected B-05 from exact main `f1a429de…`. PR #87 then merged
B-05 at the exact main/tree recorded above. B-06-D0 applies the owner's narrow
advancement exception: B-05 retains an incomplete `in_progress` delivery
record with no active work. PR #88 completed B-06 and selected B-E3; this
merged snapshot completed B-E3 and selected B-07S. Version 2.3 completed
B-07S's exact protocol ratification. Version 2.4 completed the bounded B-07A
shared core and discovery implementation. Version 2.5 conditionally completed
B-07B's bounded local task, private-record, and receipt scope. PR #94 then
completed B-05/B-07C and selected the grouped prior delivery. PR #95 completed
B-07D1/D2/D3 after applicable acceptance. PR #96 then completed B-07E after
applicable acceptance and normal merge. PR #97 completed B-07F, and PR #98
completed B-07G, after applicable acceptance and normal merge. B-E1 accepted
head `831a34598d6779d369f01de3523c3d8ee0385d18` then passed run
`34124228848`, including `Merge gate`, and normally merged as the second parent
of main `c484fd308d866d4b05a2765a984ec014dd96386e`. PR #100 accepted and
normally merged B-E2 as `602628d3c62f01524336db888da8fcfc7ed379d7`.
PR #102 normally merged the B-E2-R1 successor. PR #103 and PR #105 then merged
B-E4's initial harness and validation repair, and PR #106 merged its
analysis-only preregistration-design checkpoint. Version 3.8 keeps B-E4
selected and `in_progress`, records bounded preflight/readiness engineering and
the `STILL_BLOCKED` v3 recommendation, and leaves qualifying execution blocked
on the exact remaining integration, assumption-validation, and human-
ratification requirements above. B-GATE remains `todo` and unstarted.
B-06's five historical complete-diff reviews found nine actionable defects;
CR-001 through CR-009 are repaired. Those reviews and approvals remain
historical evidence for the pre-integration tree. OWNER-DX-03 requires no
replacement review, receipt, or approval ceremony: the integrated ready
revision passed applicable automated acceptance and normal expected-head merge.
B-01G blocks neither transition. B-02C owns the resource-policy prerequisite; B-07E only
inspects or forecasts against it. B-07A
implements the ratified shared v2 nominal primitives once; downstream domain
tickets consume rather than redefine them. B-07F owns resolved-plan fixture-
official integration so B-E4 and B-GATE do not implement a hidden adapter.
B-07G owns final research-service composition and conformance without absorbing
domain or official-v1 authority. B-07D1/D2/D3 deliberately separate the prior's
data contract, offline publisher, and request-time provider. The default
repository execution rule remains one bounded ticket per implementation lane.

### Legacy launch-roadmap crosswalk

| Retired launch v1.0.1 umbrella | Controlling Wave B decomposition |
|---|---|
| `B-01` | B-01 |
| — owner-directed 2026-08-30 infrastructure insertion | B-01E |
| — owner-directed 2026-09-01 throughput insertion | B-01F; B-01G queued separately and non-blocking |
| `B-02` | B-02A, B-02B, B-02C |
| `B-03` through `B-06` | B-03 through B-06 |
| `B-07` | B-07R, B-07S, B-07A, B-07B, B-07C, B-07D1, B-07D2, B-07D3, B-07E, B-07F, B-07G |
| `B-E1` through `B-E3` | B-E1 through B-E3 |
| Wave B integration/acceptance | B-07G, B-E4, B-GATE |

---

## 5. Human inputs do not block fixture schemas

Agents implement mechanisms, placeholders that fail closed, test fixtures, and evidence collection. Humans supply or approve the following before the corresponding real/public capability activates.

| Input | Owner | Required before | Fail-closed behavior |
|---|---|---|---|
| Named lane staffing and launch calendar rebaseline | Launch + tech lead | Any current testnet/mainnet date claim | Dependency phases only; dates unresolved |
| Burgers v1 physical identity and claim | SciML + protocol | Real Challenge authoring | Fixture-only identity |
| Target population, official SamplingPlan, strata, evidence weighting, and permitted training support | SciML + statistics | Qualified generator/exam and real compiler catalog | No LIVE manifest or production training policy |
| Primary/witness reference adequacy and uncertainty | SciML + independent reviewer | TruthAsset authority | Reference unavailable |
| Measurements, gates, transforms, and weights | SciML + protocol | Production Score Pack | Pack not ready |
| Executable catalog values, hybrid assembly, and allowed `R_strategy` policies | SciML + protocol + security | Real compiler catalog | Fixture catalog only |
| Structure-preserving component assumptions, exact implementations, applicability, and limitations | SciML + protocol + security | Any real structural-component catalog entry or prior guidance | Component unavailable; no architectural preference inferred |
| Runtime ceilings, hardware/resource classes, and enforcement rails | SRE + protocol + security | Real reconstruction | Fixture resource policy only |
| ReconstructionEvidencePolicy, family-specific complete-base evidence, scientific stopping/extension, typed deferral, heuristic-futility error control, and stability-audit rate | Statistics + SciML + protocol | Real scientific ranking or frontier promotion | Nomination/promotion unavailable or `INDETERMINATE` (`INSUFFICIENT_EVIDENCE`) |
| Validator capacity, reconstruction funding, queueing, and operational evidence budget | SRE + operations + economics | Operational availability of registered evidence | `EVIDENCE_DEFERRED`; no scientific outcome |
| Resource forecast calibration and unsupported-input rule | SRE + statistics | Any calibrated forecast claim | `UNRESOLVED` forecast |
| Practice scope, omissions, and disclosure policy | Science + statistics + security | External practice | In-process fixture only |
| Prior estimands, cohorts, lag, cadence, granularity, diversity metric/floor, and first content | Landscape + science + statistics + security | Any external prior activation | `TEST_ONLY` / unavailable |
| Prior release approvers, rights, and future signer/key custody | Governance + business + counsel + security | External activation/signing | Test-only seam / unavailable |
| Preregistered Wave B agent profiles, budgets, utility estimand/effect floor, uncertainty rule, diversity floor, and conditional-leakage limit | Research + science + statistics + security + protocol | B-E4 execution and any public agent claim | B-E4 blocked; gauntlet unresolved |
| Strategy/evidence reuse rights | Business + counsel | Unrestricted learned ingestion | Exclude evidence |
| Remote quotas, fees, and congestion policy | Operations + economics | Charged remote service | No remote charged path |

No ticket may invent these values to make a test pass.

---

## 6. Core acceptance invariants

Every applicable Wave B ticket must preserve and test:

- mock, practice, prior, scaffold, forecast, and structural-research outputs cannot enter A5 score or the A7 official lifecycle. A fixture-official result may exercise the unchanged A5/A7/A8-shaped fixture path only through B-07F, with fixture provenance and no LIVE, economic, or scientific authority;
- no public output contains official seed, draw, case, hidden mixture, exact margin, or protected reference material;
- the research service exposes exactly the B-07S-ratified closed operation set,
  delegates each operation to one named domain owner, and contains no
  official-v1 operation, lifecycle, or store;
- the same Strategy and compiler identities resolve to the same construction semantics in practice and official-shaped reconstruction;
- unsupported or unused parameters fail rather than disappear;
- a structural-component declaration, implementation test, or prior tag cannot
  satisfy a scientific gate or enter score as evidence; only registered
  measurements of reconstructed outputs can do so;
- only registered training sampling/curriculum/augmentation levers may resolve
  to `R_strategy`; raw/custom data, miner seeds, and official `P`, `Q`, `w`,
  stress, reference, gate, and scorer controls fail closed;
- reference or infrastructure failure cannot become candidate physics failure;
- no pre-base quality check, partial build, forecast, or screen can deny the
  registered complete base reconstruction or create any scientific outcome;
  uncompleted work is `EVIDENCE_DEFERRED`, never negative evidence;
  reconstruction × whole-case dependence, stratified by stress design, is
  preserved in every decision-resolution fixture and unresolved evidence
  remains indeterminate;
- a `TEST_ONLY` prior cannot be externally activated or rendered as bootstrap/learned guidance, and no v2-backed projection can enter the public v1 provider;
- a test-only authorization receipt cannot satisfy a public publication gate, and
  the exact pack/receipt remains frozen across B-E4 v2-prior replicates;
- the prior provider serves only approved stored bytes and never performs a private-data query;
- identical PriorPack reference produces identical bytes for every requester;
- public prior alignment is deterministic and uses no private evidence;
- per-requester and near-duplicate lineage disclosure accounting is composable across surfaces; Wave B related-requester resolution is fixture-only and makes no live Sybil-resistance claim;
- no Wave B artifact creates scientific, security, network, commercial, production, frontier, weight, emission, or settlement authority.

---

## 7. Ticket execution requirements

### Development decisions and lead notification

Development authorization comes from the active wave and selected ticket, not
from prior multi-role approval. A material decision changes or selects:

- architecture or domain ownership;
- a contract or invariant;
- a public interface or persisted schema;
- a scientific assumption or evidence interpretation;
- a security or disclosure boundary;
- a rights or data-use policy;
- an operational or resource policy;
- Wave or ticket sequencing; or
- a `KEEP`, `WRAP`, `REPAIR`, or `REPLACE` disposition with cross-ticket
  impact.

Routine implementation details within an already recorded working contract do not need
a separate lead notification. For every material-decision-affecting pull
request, record the durable decision in `.agent/DECISIONS.md` or the applicable
ticket, plan, or specification; include a pull-request section titled
`Lead notification` naming the decision ID or heading, affected ticket and
files, selected approach, alternatives rejected, invariant/interface/
sequencing effects, reversibility and migration effect, and notification
issue/comment; and post or update issue #42 mentioning designated SciML /
Technical Lead Harshdeep Sharma (`@harshaa765`).

Notification is evidence of delivery, not approval. No affirmative response,
reaction, approval, or waiting period is required. A lead `REQUEST_CHANGES`
review or explicit `BLOCKED` direction pauses the affected change but not
unrelated work. After merge, an adjustment uses a new bounded branch and later
normally merged repository decision; historical evidence is marked superseded,
not rewritten. Current merged repository authority controls until then.

The Accountable reviewer column remains technical/domain consultation and
notification routing. It creates no pre-implementation approval or silence
gate. OWNER-DX-03 requires applicable automated acceptance and `Merge gate`
for the ready revision, followed by normal expected-head merge. Independent
review is optional, and no human/GPT receipt or approval is a merge predicate.
Engineering delivery grants no reserved scientific, security, rights,
economic, qualification, `LIVE`, launch, deployment, or production authority.

This non-blocking development rule does not allow an agent to invent or approve
scientific truth, thresholds, tolerances, population or SamplingPlan claims,
qualification, security acceptance, rights/legal policy, live economics,
launch or deployment authority, or production, `LIVE`, frontier, product,
settlement, chain, weight, or emission authority. An unresolved reserved human
decision leaves the affected capability stopped, explicit, bounded, and fail
closed; it does not block unrelated fixture, schema, interface, test, or
infrastructure development.

Use one ticket branch/worktree and one pull request by default. Put the working
contract, decisions, plan, and start state first; add coherent vertical
implementation/test slices; and review the final contract, implementation,
tests, and stable evidence together. A separate contract PR requires one of
the concrete exceptions in `.agent/DELIVERY_PROTOCOL.md`; ticket size alone is
not one.

Before each ticket begins:

1. read `CONSTITUTION.md`, `AGENTS.md`, `.agent/INVARIANTS.md`, the active `.agent/WAVE.md`, this candidate board, and the ticket;
2. read the ticket's domain-owner specifications in full;
3. pin the current commit and authority set;
4. classify touched components `KEEP`, `WRAP`, `REPAIR`, `REPLACE`, or stop for `NEW_OWNER_DECISION_REQUIRED`;
5. run and record the ticket-specific baseline;
6. create a detailed `.agent/plans/` file for every multi-module ticket before implementation;
7. create and record the ticket's working contract before implementation when
   the ticket defines a new public or security boundary; implement against it
   in the same PR by default; and run applicable automated acceptance and
   `Merge gate` on the ready revision before normal expected-head merge, while
   human-reserved values remain fail closed; and
8. on macOS, Windows, or noncanonical Linux, run validation through
   `./scripts/dev/canonical.sh` and never call native-host output canonical.

Each ticket writes `.agent/evidence/wave_b/<ticket-id>.md` using the evidence
README and links that record from its ticket file and board row before `done`.
The tracked record contains stable scope, authority, base, decisions,
contracts, expected manifest, commands, invariants, and maturity ceiling. A
ticket candidate may coordinate its own bounded `done` and the next-ticket
selection after its ready revision passes applicable automated acceptance and
`Merge gate`, normally merges with the expected-head guard, and receives a
brief completion confirmation. Do not require a recursive closeout PR, review
receipt, approval, evidence-seal commit, validation retrigger, or post-merge
full-CI wait. An affirmative human reviewer or lead response is not required.

Ticket completion must separately report:

```text
SPECIFIED
IMPLEMENTED
TESTED
SCIENTIFICALLY_QUALIFIED
SECURITY_QUALIFIED
NETWORK_QUALIFIED
COMMERCIALLY_VALIDATED
PRODUCTION_QUALIFIED
```

No later state is inferred from an earlier one.

---

## 8. Wave B closeout

`B-GATE` may propose this board `done` only after:

- every required ticket except explicitly non-blocking B-01G has merged
  evidence and checked acceptance criteria;
- full CPU, focused, invariant, quality, and installed-wheel tests pass;
- the fixture autoresearch gauntlet completes end to end without undocumented repository knowledge;
- the preregistered B-E4 utility decision passes and the conditional-leakage
  decision does not find a protected-realization shortcut; a failed or
  indeterminate decision blocks closeout rather than being relabeled success;
- B-E1 demonstrates dependence-aware interval coverage on fixture scenarios
  with reconstruction-by-case interaction, heteroscedastic stress strata,
  exact-pair applicability checks, missing or censored cells, qualified
  scientific stopping, and heuristic deferral; unsupported independence or
  unresolved coverage fails closed;
- mock/practice isolation and protected-field canaries pass;
- a Strategy parameter cannot be accepted yet ignored by the compiler;
- the semantically responsive fixture-official consumer uses the same exact
  resolved-plan identity as practice while preserving separate rights and the
  unchanged v1 lifecycle;
- a prior fixture cannot be promoted above `TEST_ONLY`, and no v2-backed projection can enter the public v1 provider;
- the TEST_ONLY fixture-ledger append and private authorization-receipt/snapshot
  update are atomic and exact-ref reproducibility passes; the stronger public
  receipt/index graph passes schema and negative tests while public-class
  activation remains unavailable and fail closed;
- the Dossier and qualification manifest remain incomplete/fail closed for LIVE;
- `.agent/WAVE_B_REPORT.md` records exact evidence and remaining human inputs;
- the complete exact-head review, normal-merge, exact-main, and external-
  receipt predicate in `.agent/DELIVERY_PROTOCOL.md` passes. Human-reserved
  qualification and activation
  remain separate and fail closed; no affirmative closeout-response or silence
  gate applies to bounded engineering completion.

Wave C remains unauthorized until `.agent/WAVE.md` moves prospectively.
