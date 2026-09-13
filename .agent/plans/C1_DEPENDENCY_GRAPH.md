# C1 real-vertical dependency graph after PR #151

**Decision:** `OWNER-C1-CONTRACTS-01`
**Status:** authoritative planning checkpoint after merge
**Primary Hub map_ref:** `WAVE-C`
**Implementation selection:** PR #151 accepted C-03 prerequisite hardening;
C-04's engineering/public qualification-candidate slice is selected

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
C-01(done) ─┬─> C-AUTH1(done) ─> C-EA0(done) ─> C-EA1(done, synthetic only)
            └─> C-02(merged DEVELOPMENT adapter prerequisite; full ticket open)
                    └─> C-03(PR #149 capability + PR #151 hardening)
                            └─> C-04(selected engineering + D-03/D-04 prerequisite harness)
C-02 + C-04 ─> C-05 engineering + D-02/D-05 prerequisite harness
             ─> C-06 ─> C-07 ─> C-08
                    C-07 + real archive profile + C-EA1 ─> C-EA2
A10 boundary + C-06 + C-07 + C-EA2 ─> C-09
G2(exact standard localnet only) + C-09 + C-EA2 + real signed C1 evidence ─> C-W1
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
| C-EA1 | done only for `carbon.synthetic-evidence-archive.dev.v1` | ticket exists; sufficient for that profile | C-EA0 and synthetic owner decision satisfied | every real/production archive policy remains reserved | none for synthetic scope | complete | already implemented/tested only for synthetic scope |
| C-EP1 | done, bounded DEVELOPMENT fixture implementation | ticket/evidence complete | NET-3, C-01 and A4-A8 bounded fixtures satisfied | all production entropy, custody, archive, science, security and comparison policy remains reserved | none for closed fixture scope | complete in PR #143 | already implemented/tested only in DEVELOPMENT scope |
| C-EP2 | done, bounded DEVELOPMENT measurement and detached replay | ticket/evidence complete | C-EP1 satisfied | reference compatibility, acceptable delay, B overhead, science/security criteria remain reserved or unknown | authorized real reconstruction/reference backend and representative workload remain missing | complete in PR #144 | already implemented/tested only in DEVELOPMENT scope |
| C-EP3 | done, bounded DEVELOPMENT input acquisition and detached public probe | ticket/evidence complete | C-EP2 and C-AUTH1 satisfied | reference qualification, comparison meaning, and every real security/science input remain reserved | supplied JAX bundle resolves only the reconstruction-source input | complete in PR #145 | already implemented/tested only in DEVELOPMENT scope |
| C-02 | bounded DEVELOPMENT adapter merged; full ticket in progress | ticket, canonical lab source/interface, v3 exact dependency profile, Foundax pin and frozen repeat capability sufficient for C-03 | B-02B, B-03, B-E1, C-01 and C-EP3 satisfied as bounded foundations | production repeated-build policy, protected execution and real backend/scientific qualification remain reserved | described v0.2 `carbon_jax_research` source is absent/unverified but deferred | adapter prerequisite merged in PR #148; isolated composition is separate | **yes, as C-03 prerequisite only** |
| C-03 | PR #149 bounded DEVELOPMENT capability and PR #151 hardening accepted; full ticket open | exact profile, implementation/evidence/report and accepted Linux service lanes | C-02 adapter capability, C-01, B-02B, B-02C and A4 satisfied for the bounded worker | protected threat acceptance and independent security review remain open | none for the merged public-development slices | bounded slices complete; broader ticket open | **already usable by C-04 in bounded mode** |
| C-04 | `in_progress`, selected public qualification-candidate slice | ticket, plan, role-explicit runtime and D-03/D-04 prerequisite harness candidate | accepted C-03 capability/hardening, B-04 and B-E2 satisfied | qualified primary/witness, tolerances, applicability, uncertainty and protected access acceptance remain open | required changed-source Linux service run pending | no missing contract work for bounded slice | **yes, current slice; not protected/official** |
| C-05 | `todo`, sequential after C-04 engineering merge | current ticket/spec sufficient for engineering and public qualification-candidate evidence | B-05 bounded foundation plus C-02/C-04 engineering; D-02/D-05 prerequisite harness under its owners | qualified measurements, floors, uncertainty and Score Pack admission remain open | real protected reference/evaluation inputs absent | no missing contract work for bounded slice | **yes only after C-04 bounded merge** |
| C-06 | `future_reserved`, unselected, blocked | ticket exists; sufficient | C-01, C-02, C-04, C-05 | signer authorization, key/custody, retention and disclosure policy | real official evidence chain | no missing contract work identified | **no** |
| C-07 | `future_reserved`, unselected, blocked | ticket exists; sufficient | C-01 through C-06 | registered real orchestration policies and scientific inputs | real implementations/results from predecessors | no missing contract work identified | **no** |
| C-08 | `future_reserved`, unselected, blocked | ticket materialized here; sufficient | NET-2 satisfied in bounded scope; C-07 missing; A9 retained | real budgets/quotas and production auth/security approval | real validator orchestration endpoint/path | materialized by this checkpoint | **no** |
| C-EA2 | `future_reserved`, unselected, blocked | ticket exists; sufficient | C-EA1 plus selected real C-02–C-07 path | real artifact, rights, retention, custody/KMS, topology, durability, recovery and security policies | eligible real archive service/acknowledgement | already materialized; do not select | **no** |
| C-09 | `future_reserved`, unselected, blocked | ticket materialized here; sufficient | A10 boundary, C-06, C-07, C-EA2 | qualified provenance and Challenge-local publication/disclosure policy | signed real receipt/result and eligible real archive acknowledgement | materialized by this checkpoint | **no** |
| C-W1 | `future_reserved`, unselected, blocked | ticket exists; sufficient | exact G2 scope plus C-09, C-EA2 and real signed C1 evidence | public network identity, eligibility window, sink/custody and security/economic activation | actual real C1 proof chain and public testnet access | already materialized; do not select | **no** |

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
worker capability; and PR #151 accepted its prerequisite hardening. Under
`OWNER-C1-BURGERS-ALPHA-01`, C-04 is now the selected engineering/public-
candidate ticket without another selection ceremony.
C-EA2 and C-W1 remain unimplemented and ineligible. This graph authorizes no
protected reference, official science, public-network operation, real archive
acknowledgement, production qualification or LIVE state.
