# C1/C2 dependency graph: C-W1-D4 finite miner autoresearch

**Decision:** `OWNER-C1-CONTRACTS-01`
**Status:** authoritative planning checkpoint after merge
**Primary Hub map_ref:** `WAVE-C`
**Implementation selection:** C-W1-D4 only under OWNER-C-W1-D4-AUTORESEARCH-01. PR #202 merged balanced-v2 scoring and measurement v3. The new owner direction authorizes bounded public/synthetic research implementation and one finite off-chain campaign after accepted delivery. Scientific mathematics stays fixed; no chain transaction or qualification is authorized.

## Authority resolution

Launch v1.0.3 is retained only for the C-03/C-08/C-09 identifiers and their
bounded responsibility seeds. Launch v1.0.4 supersedes its sequencing and owns
the current C1 real-vertical/C2 separation. V1.0.5 changes only the B-E4 and
Research Concierge dependency rules. V1.0.6 changes only payment routing and
does not weaken C1 isolation, scientific provenance, archive, receipt,
publication or C-W1 eligibility gates. Current tickets, Build Out, constitutional
overlay, evidence contracts and owner decisions further narrow each node.

Historical shorthand making C-04 depend only on B-03/B-04 is superseded by the
current C-04 ticket's C-03 isolation dependency. Historical C-09 reliance on
A10 cannot promote A10's fixture board; C-09 needs a separate real provider and
the newer C-EA2 archive-before-finalization gate. Historical "paid/free MCP"
language supplies no fee value or payment authority; C-08 preserves registered
budget/resource controls and fail-closed missing policy.

## Exact graph

```text
C-01(done) ─┬─> C-AUTH1(done) ─> C-EA0(done) ─> C-EA1(synthetic + alpha preparation + unprovisioned AWS v1/v2 accepted; deployment deferred)
            └─> C-02(merged DEVELOPMENT adapter prerequisite; full ticket open)
                    └─> C-03(PR #149 capability + PR #151 hardening)
                            └─> C-04(PR #154 engineering + D-03/D-04 prerequisite harness)
C-02 + C-04 ─> C-05(PR #157 engineering + D-02/D-05 prerequisite harness)
             ─> C-06(PR #161 DEVELOPMENT receipt) ─> C-07(PR #163 DEVELOPMENT orchestration) ─> C-08(PR #167 DEVELOPMENT composition)
                    C-06 + C-07 ─> C-10(PR #173 bounded DEVELOPMENT re-execution)
                    C-07 + real archive profile + C-EA1 ─> C-EA2
A10 boundary + C-06 + C-07 + C-EA2 ─> C-09
G2(exact standard localnet only) + C-09 + C-EA2 + real signed C1 evidence ─> C-W1
NET-2 + C-03 + C-06/C-07/C-08 + C-10 + checked publisher ─> C-W1-D1(public/synthetic DEVELOPMENT only)
C-05 + C-06/C-07/C-08 + C-10 + C-REWARD ─> C-W1-D2(non-paying descriptive comparison only) ─> C-W1-D3(delegated DEVELOPMENT scoring; no paying/network path)
B-07 research + C-02/C-03 containment + C-08 auth + C-W1-D3 ─> C-W1-D4(real public research, fresh final comparisons, finite campaign; in progress)
NET-3 + C-01 + A4-A8 ─> C-EP1(done, DEVELOPMENT fixture only)
C-EP1 ─> C-EP2(done measurement/replay only; no sharing runtime)
C-EP2 + C-AUTH1 ─> C-EP3(done input acquisition/public component probe)
C-EP3 + supplied immutable JAX bundle ─> C-02(merged DEVELOPMENT adapter prerequisite)
```

## Node audit

| Node | Status | Ticket / contract | Implementation dependencies | Missing human inputs | Missing external inputs | Contract-only now | Implementation-ready |
|---|---|---|---|---|---|---|---|
| C-01 | done, bounded | ticket exists; sufficient | A7, B-GATE satisfied | none for closed scope | none | complete | already implemented/tested |
| C-AUTH1 | done, bounded public development | ticket exists; sufficient | C-01 satisfied | real scientific/reference/archive decisions remain outside scope | none for closed scope | complete | already implemented/tested only in closed scope |
| C-EA0 | done contract | ticket exists; sufficient | C-01, C-AUTH1, B-GATE satisfied | all real archive policy families remain reserved | none | complete | not an implementation ticket |
| C-EA1 | synthetic/alpha preparation and unprovisioned AWS v1/v2 packages accepted; AWS deployment deferred | ticket, D2 profile/config/preflight and PRs #168/#177/#180 | C-EA0 satisfied | actual provider recovery/security/deployment/signer acceptance remain open | provider/account/custody/full-watermark observation absent | no real ack; Hippius preferred but unverified | no, not selected |
| C-EP1 | done, bounded DEVELOPMENT fixture implementation | ticket/evidence complete | NET-3, C-01 and A4-A8 bounded fixtures satisfied | all production entropy, custody, archive, science, security and comparison policy remains reserved | none for closed fixture scope | complete in PR #143 | already implemented/tested only in DEVELOPMENT scope |
| C-EP2 | done, bounded DEVELOPMENT measurement and detached replay | ticket/evidence complete | C-EP1 satisfied | reference compatibility, acceptable delay, B overhead, science/security criteria remain reserved or unknown | authorized real reconstruction/reference backend and representative workload remain missing | complete in PR #144 | already implemented/tested only in DEVELOPMENT scope |
| C-EP3 | done, bounded DEVELOPMENT input acquisition and detached public probe | ticket/evidence complete | C-EP2 and C-AUTH1 satisfied | reference qualification, comparison meaning, and every real security/science input remain reserved | supplied JAX bundle resolves only the reconstruction-source input | complete in PR #145 | already implemented/tested only in DEVELOPMENT scope |
| C-02 | bounded DEVELOPMENT adapter merged; full ticket in progress | ticket, canonical lab source/interface, v3 exact dependency profile, Foundax pin and frozen repeat capability sufficient for C-03 | B-02B, B-03, B-E1, C-01 and C-EP3 satisfied as bounded foundations | production repeated-build policy, protected execution and real backend/scientific qualification remain reserved | described v0.2 `carbon_jax_research` source is absent/unverified but deferred | adapter prerequisite merged in PR #148; isolated composition is separate | **yes, as C-03 prerequisite only** |
| C-03 | PR #149 bounded DEVELOPMENT capability and PR #151 hardening accepted; full ticket open | exact profile, implementation/evidence/report and accepted Linux service lanes | C-02 adapter capability, C-01, B-02B, B-02C and A4 satisfied for the bounded worker | protected threat acceptance and independent security review remain open | none for the merged public-development slices | bounded slices complete; broader ticket open | **already usable by C-04 in bounded mode** |
| C-04 | bounded public qualification-candidate slice accepted in PR #154; broader ticket open | ticket, plan, role-explicit runtime and D-03/D-04 prerequisite harness | accepted C-03 capability/hardening, B-04 and B-E2 satisfied | qualified primary/witness, tolerances, applicability, uncertainty and protected access acceptance remain open | none for merged public slice | bounded slice complete | **already usable by C-05 in bounded mode** |
| C-05 | bounded public qualification-candidate slice accepted in PR #157; broader ticket open | ticket, plan, measurement runtime and D-05 prerequisite harness | B-05 bounded foundation plus C-02/C-04 engineering satisfied | qualified measurements, floors, uncertainty, decision-resolution target and Score Pack admission remain open | none for accepted public slice; protected inputs absent | bounded slice complete | **already usable by C-06 in bounded mode** |
| C-06 | done in bounded non-official DEVELOPMENT scope; PR #161 accepted | ticket, plan, canonical receipt, Ed25519 signer, append-only ledger and allow-listed projections | C-01 and accepted C-02/C-04/C-05 engineering capabilities satisfied | official signer authorization, key/custody, retention, scientific/security acceptance remain open | real official evidence chain absent | bounded slice complete | **already usable by C-07 in bounded mode** |
| C-07 | done in bounded non-official DEVELOPMENT scope; PR #163 accepted | ticket, plan, thin C-01/C-06 composition, typed source-result intake and report projections | C-01 through C-06 bounded engineering capabilities satisfied | protected/scientific/security/official signer and archive acceptance remain open | eligible protected inputs and real archive acknowledgement absent | bounded slice complete | **already usable by C-08 in bounded mode** |
| C-08 | done in bounded authenticated DEVELOPMENT scope; PR #167 accepted | ticket, C-08-D1 implementation/evidence and accepted worker image | NET-2, C-07 and A9 bounded capabilities satisfied | real budgets/quotas and production auth/security approval remain open | public listener/deployment and protected inputs absent | bounded slice complete | **already usable by alpha preparation in bounded mode** |
| C-10 | done in bounded DEVELOPMENT re-execution scope; PR #173 accepted | ticket, C-10-D1 plan/evidence and C-01 relation/C-06/C-07 composition | C-06 and C-07 bounded engineering capabilities satisfied | qualified scientific comparison and independent security acceptance remain open | independent administration and protected evidence absent | bounded slice complete | **already usable as DEVELOPMENT evidence only** |
| C-EA2 | `future_reserved`, unselected, blocked | ticket exists; sufficient | C-EA1 plus selected real C-02–C-07 path | real artifact, rights, retention, custody/KMS, topology, durability, recovery and security policies | eligible real archive service/acknowledgement | already materialized; do not select | **no** |
| C-09 | `future_reserved`, unselected, blocked | ticket materialized here; sufficient | A10 boundary, C-06, C-07, C-EA2 | qualified provenance and Challenge-local publication/disclosure policy | signed real receipt/result and eligible real archive acknowledgement | materialized by this checkpoint | **no** |
| C-W1 | official path `future_reserved`; C-W1-D1 historical row verified | ticket and PR #196 recovery | official: G2+C-09+C-EA2+real C1 | official science/security and future transaction authority remain open | subnet 567, publisher UID 0, miner UID 1 and WSL Docker host observed | current all-burn profile unchanged | **no** |
| C-W1-D2 | done in PR #201 | authentic descriptive comparison | C-05, C-06, C-07, C-08, C-10, C-REWARD | historical no-acceptance-rule disposition preserved | none | no paying/network path | already delivered |
| C-W1-D3 | selected; implementation and verification complete, delivery pending | balanced-v2 and derived measurement v3 | C-W1-D2, C-05, C-06, C-07, C-08, C-10, C-REWARD | delegated DEVELOPMENT choices resolved; official qualification reserved | fresh training/model authority absent | no paying/network path | **yes, C-W1-D3 only** |

## Exact C-02 source resolution and remaining boundary

C-02 required an authorized JAX repository/source, immutable commit/revision,
reproducible dependency/build identity, actual training and inference entry
points, signatures, parameter/state structures, input/output shapes and dtypes,
batching/layout rules, PRNG/RNG ownership, checkpoint/artifact format,
JIT/sharding expectations and failure/error semantics. The owner-supplied
permission-cleared bundle resolves those inputs for the bounded DEVELOPMENT
slice only. Carbon adapts the actual interface and does not require upstream
function renaming. The delivered repeat runner is an optional composition over
that adapter, not a production count. `OWNER-C03-DEV-ISOLATION-01` supplies the
exact public-development threat and resource inputs needed for this first
isolated composition. Required service evidence and broader MQ-015 security
acceptance remain separate; neither full ticket is closed.
The owner-directed v3 profile adds exact Python-3.11 CPU dependency locks,
physical scaling and a source-pinned Foundax implementation. The separately
described v0.2 `carbon_jax_research` file set was not received and remains
unverified; the older `carbon_jax_lab` bundle is not substituted or relabeled.
Production source selection, protected isolation/execution and
scientific/security qualification remain unresolved.

## Selection disposition

C-EP1 through C-EP3 are complete in their bounded DEVELOPMENT scopes, PR #148
provides C-02's adapter prerequisite; PR #149 provides accepted bounded C-03
worker capability; PR #151 accepted its prerequisite hardening; PR #154
accepted C-04's bounded public reference slice; PR #157 accepted C-05's bounded
public measurement slice; PR #161 accepted C-06's signed non-official
DEVELOPMENT evidence; PR #163 accepted C-07's durable non-official
DEVELOPMENT orchestration; and PR #167 accepted C-08's authenticated
DEVELOPMENT composition; PR #168 accepted C-EA1's separately versioned
private-alpha preparation without implementing real acknowledgement; and PR
#173 accepted C-10's bounded DEVELOPMENT re-execution; and PR #177 accepted
C-EA1-D3's concrete unprovisioned AWS deployment package. The repository owner
PR #183 accepted the C-W1-D1 foundation after AWS deployment was deferred and
Hippius recorded as an unverified future storage preference. The repository
owner selects only C-W1-D3's delegated non-paying DEVELOPMENT scoring path. C-EA2 and official C-W1 remain
unimplemented/ineligible. Public execution is still gated by exact observed
network identity/capability and transaction authorization. This graph
authorizes no protected reference, official science, real archive
acknowledgement, production qualification or LIVE state.
