# C1 real-vertical dependency graph after C-EA1

**Decision:** `OWNER-C1-CONTRACTS-01`
**Status:** authoritative planning checkpoint after merge
**Primary Hub map_ref:** `WAVE-C`
**Implementation selection:** C-02 only, as a bounded DEVELOPMENT adapter for
the owner-supplied immutable JAX source/interface bundle after completed C-EP3;
no later real-vertical or Variant-B implementation ticket is selected

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
            └─> C-02(selected bounded DEVELOPMENT adapter)
                    └─> C-03(blocked C-02 + MQ-015)
                            └─> C-04
C-02 + C-04 ─> C-05 ─> C-06 ─> C-07 ─> C-08
                    C-07 + real archive profile + C-EA1 ─> C-EA2
A10 boundary + C-06 + C-07 + C-EA2 ─> C-09
G2(exact standard localnet only) + C-09 + C-EA2 + real signed C1 evidence ─> C-W1
NET-3 + C-01 + A4-A8 ─> C-EP1(done, DEVELOPMENT fixture only)
C-EP1 ─> C-EP2(done measurement/replay only; no sharing runtime)
C-EP2 + C-AUTH1 ─> C-EP3(done input acquisition/public component probe)
C-EP3 + supplied immutable JAX bundle ─> C-02(selected bounded DEVELOPMENT adapter)
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
| C-02 | selected, bounded DEVELOPMENT adapter in progress | ticket, exact source/interface bundle and frozen repeat capability sufficient for this slice | B-02B, B-03, B-E1, C-01 and C-EP3 satisfied as bounded foundations | owner-selected repeated-build policy, isolated resource enforcement and real backend/scientific qualification remain reserved | C-03 isolation and later qualified science inputs | selected by owner-supplied bundle and continuation assignment | **yes, bounded adapter only** |
| C-03 | `future_reserved`, unselected, blocked | ticket materialized here; sufficient | C-02; MQ-015 security/threat model | exact real limits, enforcement profile and security acceptance | C-02 authorized JAX/runtime identity | materialized by this checkpoint | **no** |
| C-04 | `future_reserved`, unselected, blocked | ticket exists; sufficient | B-04, B-E2 satisfied only as bounded fixtures; C-03 missing | qualified primary/witness, applicability, uncertainty and access policy | real protected reference implementations/assets | no missing contract work identified | **no** |
| C-05 | `future_reserved`, unselected, blocked | ticket exists; sufficient | B-05 bounded foundation; C-02 and C-04 missing | qualified measurements, floors, uncertainty and Score Pack inputs | real reconstruction/reference outputs | no missing contract work identified | **no** |
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
that adapter, not a prerequisite for C-03 and not a production count. C-03
can compose the validated adapter only after selection and MQ-015 security
inputs; its registered envelope remains necessary for full C-02 completion.
Production source selection, isolation, protected execution and
scientific/security qualification remain unresolved.

## Selection disposition

C-EP1 through C-EP3 are complete in their bounded DEVELOPMENT scopes. C-02
alone is selected for the supplied unqualified JAX adapter; no later
real-vertical ticket is dependency-ready or selected. C-EA2 and C-W1 remain
unselected. This graph authorizes no sharing implementation, protected
reference, official science, public-network operation, archive operating
threshold, production qualification or LIVE state.
