# B-02A scientific authoring contracts — implementation execution plan

**Ticket:** B-02A, `Scientific authoring and canonical-case contracts`
**Phase:** working-contract implementation and final independent review
**Status:** `in_progress`; implementation authorized by merged delegated-decision governance
**Original contract base:** `e10107644d5fb0c7d69b153c0c3b8a03b93b19bb`
**Original base tree:** `0f6beb5b000e771fd7e050f150e1074ea2a6fb1f`
**Authoritative governance base:** `7bdf4971b7d0b3ee8ffde577595a49c6b5456961`
**Governance base tree:** `109bb59e117d25cbdfddcc4c4a8fe6e3f3f34cdb`
**Branch:** `agent/b-02a-contract-ratification` (name retained; no replacement branch)
**Worktree:** dedicated host-local B-02A worktree (absolute path redacted)
**Working contract:** `Design_Specs/Scientific_Challenge_Authoring_Contract.md` version 0.1, `AGENT-SELECTED WORKING CONTRACT`

This plan supersedes only the obsolete contract-ratification stop in the
earlier version of this file. It preserves the contract analysis, decisions,
branch history, human-reserved scientific boundaries, and final independent
review requirement. PR #61 authoritatively establishes that lead notification
is visibility rather than affirmative pre-implementation approval.

## 1. Exact governance incorporation

The preserved B-02A branch was clean at pre-merge head/tree:

```text
4d84786ec9335be71c75bb6bcfde17f18a362033
715413c6412595f3339f50dc7e82a779f0184c4a
```

Governance PR #61 was independently reviewed at exact head/tree
`fb220c14966aa3505d95b199ce168bf31064d1ba` /
`109bb59e117d25cbdfddcc4c4a8fe6e3f3f34cdb`, normally merged as
`7bdf4971b7d0b3ee8ffde577595a49c6b5456961`, and passed exact-main CI run
`33329693544`. The valid review finding required adding `AGENTS.md` to the
original three-file governance manifest so affected-scope blocking and
whole-ticket blocking are unambiguous.

Current main was then incorporated by a normal, non-rebase merge:

```text
merge commit: b94ffbd3caaa731f92b7e9ae59e9e204ee17f8bc
merge tree:   497770f7c2dcf0ea4d2343993d090c5d9ca6dd71
parents:      4d84786ec9335be71c75bb6bcfde17f18a362033
              7bdf4971b7d0b3ee8ffde577595a49c6b5456961
```

No reset, rebase, force-push, clean, stash, or replacement branch is used.

The initial implementation candidate was recorded in five normal, reviewable
commits without rewriting the preserved history:

```text
03e4d9fde97ac9ae5badb1348b7a85c6bd9e9bfd
tree 855a45d26f5a33025bb1a1d58da92fc20d114e8c
feat(a3): pin scientific authoring graph for live

c10da0df60afc84edf0e73729788507429f9198b
tree a7d60ec42ac94627f6931c67e8a5918aa99b7ed4
feat(b-02a): implement scientific authoring contracts

38903cd513ac432ee22d2eaa8c583967a4fd205e
tree acf2795f7ff4a91bcbf9316103b99d888ab16419
test(b-02a): expand scientific contract matrix

ccef2b97d1a384f081c9ba4e67ab1fe91644e87c
tree 7be47b129fb84ec64f86dae2089028df4486ef5a
style(b-02a): apply repository formatting

d6709507b793f4820c272cbb4ecd8054ff959eb0
tree 91f81fee6726de6ef786644716259c8f341a1cd3
fix(b-02a): preserve code-authority import callsite
```

The first commit is only the minimal A3-owned fail-closed verifier seam and
regression coverage required by B-02A-D8. It does not transfer authoring,
qualification, or activation ownership from A3.
The last commit restores an established authority-scanner callsite name after
the generalized package-import test added `carbon.authoring`; it changes no
runtime behavior or package surface.

The documentation/evidence candidate was then recorded normally as
`e72dca4110b763105d49e8e572c7831a3c809063`, tree
`6c2315f81c8c15840d3c57fc12ea76c17e45b500`. Exact-head GitHub run
`33337500366` found that A12's fixed crosswalk enumerated the new B-02A
invariant module as if it were one of A12's 12 dedicated rows. The narrow
repair `c255e519b01d8c4b0ecf67e3482888c3f99f338f`, tree
`65e564ba67173f9df9b1fa269aa552e23f57a8da`, scopes that enumeration to
`test_a12_*` while preserving the all-invariant anti-greenwashing scan and
adds the required module-level invariant marker to the B-02A suite.

The repair/evidence checkpoint `a512f2f577c1d3bc801994f5af579513369b249a`,
tree `7c286b90ded19924c37f3e61ff1babb38f19b5f8`, then passed all 37
invariants and all 2617 CPU tests in both GitHub lanes in run `33337819922`.
Its remaining failure was strict Black 26.5.1 quality debt on five B-02A files.
Normal style-only repair `6d6ee0714295816f8dd6b07afce33a2bbb0c86a5`,
tree `d3c153bc76a0203c8f04e10eecce5cc04a9c6877`, applies that exact pinned
formatter and changes no semantics.

## 2. Controlling authority and maturity

The implementation reads and applies the current versions of:

1. `CONSTITUTION.md` and `AGENTS.md`;
2. `.agent/INVARIANTS.md`, `.agent/WAVE.md`, and `.agent/WAVE_B.md`;
3. `.agent/WAVE_B_CODEX_HANDOFF.md` as historical/current handoff evidence;
4. `agent_pack/EXECUTION_PROTOCOL.md` and
   `.agent/DELEGATED_DECISION_PROTOCOL.md`;
5. the B-02A ticket, this plan, evidence, D1-D11, and working contract;
6. `.agent/CODE_AUTHORITY.toml` and the B-01E legacy-quarantine record;
7. the scientific canon, locked Challenge distribution architecture,
   constitutional overlay, and current physical/generator/evidence/data/
   scoring/trust/domain owners cited by the working contract;
8. current A3 registry identity, digest, store, and LIVE-gate code/tests;
9. current A4 exact-type, capability, protected-origin, and projection
   patterns; and
10. package, wheel, import-boundary, quality, and CI enforcement.

Bounded `IMPLEMENTED` and `TESTED` candidate evidence exists on the branch.
Authoritative repository acceptance remains pending exact-head review,
canonical CI, and normal merge. The ticket cannot earn scientific, security,
network, commercial, production, LIVE, launch, frontier, settlement, weight,
or emission authority.

## 3. MQ and conflict classification

| Seam | Classification | Controlling treatment |
|---|---|---|
| MQ-001 real physical job/values | `NEW_OWNER_DECISION_REQUIRED`, `DEFERRED_FAIL_CLOSED` | Implement exact types and validation only. No Burgers viscosity or other real value becomes a default. |
| MQ-002 real P/Q/w/design values | `NEW_OWNER_DECISION_REQUIRED`, `DEFERRED_FAIL_CLOSED` | Implement distinct roles and unavailable production construction. No population, count, allocation, weight, stopping rule, or threshold is selected. |
| Contract-first timing after PR #61 | `DOCUMENTATION_LAG` in the pre-merge B-02A branch | The merged ticket and delegated protocol control: implement from the working contract; final independent review remains pre-merge. |
| Missing B-02A code at the original base | `IMPLEMENTATION_LAG`, resolved by the candidate | This ticket owns the bounded implementation; final review/merge remain pending. |
| Retired `carbon/challenges`, `carbon/data`, `carbon/physics` suggestions | `DOCUMENTATION_LAG` | They remain forbidden by code authority. |
| A3 identity/digest grammar | `NO_CONFLICT` | Reuse public A3 primitives; create no competing Challenge or SHA grammar. |
| B-02A canonical binary profile | `IMPLEMENTATION_LAG` resolved by D1 | Implement a schema-local, versioned codec; do not reuse registry JSON or owner-private encoders. |
| Immutable history | `IMPLEMENTATION_LAG` resolved by D7 | Add an append-only exact-ref B-02A store; do not reuse A3's replaceable draft store. |
| A3 fixture/LIVE graph seam | `IMPLEMENTATION_LAG` resolved by D8 | A3 owns the gate and a configured verifier protocol; B-02A supplies the graph verifier without an A3-to-B-02A import. |
| Real rights, disclosure policy, opaque-handle security, qualification | `NEW_OWNER_DECISION_REQUIRED` | Exact refs and fail-closed states only; no value or approval is invented. |
| B-02B/B-03/B-04/B-05/B-06/B-07R/B-07S behavior | `NO_CONFLICT` | Preserve downstream seams and do not implement them. |

No unresolved engineering decision blocks the bounded implementation. Every
human-reserved value remains unavailable at the affected production seam.

## 4. Existing-code disposition

| Component | Decision | Use |
|---|---|---|
| A3 `ChallengeKey`, identifier/version validators, tagged SHA-256 validator, bounded verified reader | `KEEP` + `WRAP/COMPOSE` | Revalidate and reconstruct at B-02A boundaries. |
| A3 registry lifecycle and qualification ownership | `KEEP` | Add only the A3-owned verifier seam required to prevent fixture/unresolved authoring graphs from satisfying production LIVE. |
| A3 replaceable draft/fixture persistence | `KEEP` for A3; not reused | It is not B-02A immutable history. |
| A4 capability, redaction, and projection pattern | `KEEP` as pattern | No A4 private encoder, entropy, seed, or opaque-handle algorithm is imported. |
| A2/A5/A7/A8/A9 packages | `KEEP` | Downstream/adjacent owners remain unchanged except exact integration tests where required. |
| Retired/archive implementations | `MIGRATION_REQUIRED`, not selected | No archive inspection, copy, import, or revival. |
| Current canonical B-02A runtime at the original base | `REPAIR: none`, `REPLACE: none` | No prior implementation existed; the branch adds the first bounded candidate. |

## 5. Agent-selected implementation decisions

### D6 — package and export boundary

Add `carbon/authoring` as a new canonical role package. It imports only the
standard library and minimal public A3 primitives. Public root exports are an
ordered allow-list; protected case identity, origin issuers, storage internals,
and capability constructors are not convenience exports. Add the root to
`.agent/CODE_AUTHORITY.toml` and installed-wheel/import coverage. Do not change
`pyproject.toml` because `carbon*` already includes the package.

### D7 — append-only exact history and origin

Use a B-02A-owned, create-only filesystem store keyed by exact ref and bounded
canonical bytes. It has no evidence-bearing `latest`, no overwrite, and no
historical alias. Same-kind/same-Challenge/same-object-ID supersession is
prospective and cycle checked. Origin is stored separately but immutably per
exact ref; a fixture/unresolved origin cannot be upgraded by copying,
rehashing, superseding, or re-registering. Revocation is prospective and does
not rewrite historical bytes or evidence.

### D8 — cycle-safe A3 LIVE eligibility

A3 owns an exact `ScientificAuthoringVerifier` protocol and fail-closed reason
integration in every production eligibility/activation/revalidation path. A
missing, failing, or wrong-type verifier is ineligible. B-02A supplies a
store-backed exact verifier that joins the bound authoring graph and reports
eligible only for a complete registered, non-fixture graph matching the exact
`ChallengeKey`. A3 imports no B-02A module. Fixture-mode diagnostics remain
non-production and cannot activate LIVE.

### D9 — exact graph manifest and peer-root connectivity

Bind one complete exact node manifest rather than pretending the six authored
families form one directed ownership chain. Load `root_ref` and every sorted
`required_ref`; require all declared dependencies to be contained in that
manifest; reject omitted, injected, cross-Challenge, and disconnected nodes;
and require one component when dependency edges are viewed undirected. This
allows training support and official case/evidence contracts to remain peer
owners that connect through shared exact candidate/physical dependencies. The
graph fingerprint binds the exact root, complete ref set, joined origin,
origin evidence, and composition audit. It does not certify scientific
adequacy.

### D10 — exact SciML/statistics verification at cyclic semantic joins

Use separate configured exact-result providers for transient physical/candidate
equivalence and SamplingPlan/full-design/estimand/w compatibility. Provider
requests bind the complete exact objects and refs; results must be exact
nominal request echoes with closed authorization branches. Missing, stale,
wrong-type, Boolean, mapping, or mismatched results fail only the affected
graph closed. The results remain external composition evidence, so no mutual
content-addressed plan↔w cycle or scientific value enters authored bytes.

### D11 — external projection, evidence, and accounting authority

Raw projections, evidence bindings, and accounting inputs are authored claims,
not authority. Internal non-root adapters require exact echo records from
separately owned provider objects. Realized evidence requires both an exact
intended-unit manifest authorization and final authorization of the complete
canonical disposition set plus every loaded censoring record; historical load
rechecks the same exact composition. No callback, Boolean, label, nominal ref
alone, or reusable pre-final capability can create authority. Durable
registries, authentication, signatures, rights, and qualification remain later
owner inputs.

These decisions are delegated engineering choices. They are notified through
issue #42; affirmative response is not required. An observed `CHANGE`,
`BLOCKED`, or `REQUEST_CHANGES` pauses the affected change.

## 6. Implementation surface

The smallest coherent package provides:

- strict primitive validation, stable non-echoing errors, closed enums/unions,
  exact external owner refs, and applicability bindings;
- the six immutable identity families and six distinct refs required by the
  ticket;
- subordinate physical/candidate, population, training-support, SamplingPlan,
  canonical-case, disclosure, evidence, disposition, censoring, replacement,
  and origin records owned by B-02A;
- schema-local canonical bytes, decoding, digest/ref computation, and exact
  expected-ref verification;
- digest-first bounded loading and mutation-isolated loaded results;
- append-only exact historical retrieval, supersession, origin composition,
  and prospective revocation;
- controlled public/internal/protected projections;
- capability-created disposition, censoring, and realized-evidence records;
  and
- the A3 verifier seam and B-02A adapter described by D8.

Explicitly absent: `ResolvedTrainingSamplingPolicy`, `R_strategy` compiler,
candidate assembly, generators, reference policy/runners, measurements,
scoring, dossiers, service protocol, entropy/seeds, opaque-handle derivation,
real scientific values, and every later-ticket implementation.

## 7. Exact candidate manifest

Relative to authoritative governance main, the bounded candidate changes
exactly:

```text
M .agent/CODE_AUTHORITY.toml
M .agent/DECISIONS.md
M .agent/WAVE.md
M .agent/WAVE_B.md
M .agent/WAVE_B_CODEX_HANDOFF.md
A .agent/evidence/wave_b/b-02a.md
A .agent/plans/B-02A_scientific_authoring_contracts.md
M .agent/tickets/B-02A_scientific_authoring_contracts.md
A Design_Specs/Scientific_Challenge_Authoring_Contract.md
A carbon/authoring/__init__.py
A carbon/authoring/canonical.py
A carbon/authoring/cases.py
A carbon/authoring/errors.py
A carbon/authoring/evidence.py
A carbon/authoring/graph.py
A carbon/authoring/history.py
A carbon/authoring/loading.py
A carbon/authoring/model.py
A carbon/authoring/physical.py
A carbon/authoring/populations.py
A carbon/authoring/primitives.py
A carbon/authoring/refs.py
A carbon/authoring/sampling.py
A carbon/authoring/training_support.py
M carbon/registry/__init__.py
M carbon/registry/gate.py
M carbon/registry/model.py
M carbon/registry/store.py
A tests/cpu/test_b02a_canonicalization.py
A tests/cpu/test_b02a_contract_matrix.py
A tests/cpu/test_b02a_contract_models.py
A tests/cpu/test_b02a_exports_and_boundaries.py
A tests/cpu/test_b02a_graph_live_integration.py
A tests/cpu/test_b02a_loading_and_history.py
A tests/cpu/test_b02a_primitives_and_refs.py
M tests/cpu/test_mcp_skeleton.py
M tests/cpu/test_package_installation.py
M tests/cpu/test_registry.py
M tests/cpu/test_submission_fsm.py
M tests/invariants/test_a12_crosswalk.py
M tests/invariants/test_a12_invariants.py
A tests/invariants/test_b02a_scientific_boundaries.py
```

The handoff file is included only because its merged-main text still declared
B-02A unready and required an affirmative pre-implementation ratification gate,
an exact current-state contradiction after PR #61. Its historical evidence is
preserved; only the satisfied gate and delegated-governance interpretation are
updated.

Implementation/testing is limited to `carbon/authoring`, the minimal A3
verifier seam under `carbon/registry`, focused `tests/cpu` and
`tests/invariants` coverage, and package-installation/code-authority tests.
No dependency, lock, workflow, dev-container, script, README, archive, legacy
index, or retired namespace changes.

## 8. Definition-of-Done crosswalk

| DoD area | Implementation evidence required |
|---|---|
| Working contract and final review | D1-D11, current contract, exact final candidate, independent SciML/statistics/protocol review, resolved findings, green CI; first checkbox remains incomplete until its normal-merge clause is satisfied. |
| Six objects and refs | Exact final nominal immutable types, role/kind checks, canonical refs, loaders, and tests. |
| P/Q/w/support/R_strategy separation | Closed enums/matrices, exact expected-role refs, and confusion-rejection tests; no B-02B object. |
| Population/case/evidence distinctions | Exact bindings, source/state/campaign/censoring types, and negative tests. |
| Historical identity | Append-only store, exact retrieval, prospective supersession/revocation, no latest/overwrite. |
| Fixture cannot satisfy LIVE | Structural origin composition plus direct A3 production-gate tests. |
| Packaging | New canonical root, ordered exports, authority checks, clean wheel, outside-tree isolated imports. |

## 9. Test and validation route

Focused tests cover exact-type/subclass/coercion rejection; bool/int/float
separation; malformed IDs, Unicode, fields, enums, digests, and numerics;
positive zero; canonical golden vectors; hash pins; cross-kind refs; equality,
immutability, mutation isolation; historical identity; P/Q/w/support and role
confusion; query/observation/campaign binding; MMS non-transfer; scoped
censoring/replacement/accounting; projection non-disclosure; fixture taint;
and direct A3 LIVE rejection.

Repository gates:

```text
./scripts/dev/bootstrap.sh
./scripts/dev/doctor.sh
./scripts/dev/ci.sh
git diff --check
```

The native Windows host is non-canonical and may fail closed before tests.
Exact-head GitHub canonical and clean-image CI is authoritative. Evidence must
record both local diagnostics and exact CI counts/versions/durations.

## 10. Human-reserved inputs and fail-closed behavior

No implementation value is supplied for the first real physical Challenge,
governing values, envelope/claim, real P/Q/w, estimand, strata, population
law, production SamplingPlan, statistical objectives or sufficiency,
measurement/reference qualification, evidence weights, training material or
rights, hybrid evidence role, opaque-handle security, scientific/security/
network/commercial/production qualification, LIVE activation, launch,
economics, settlement, weight, or emission.

A required missing value makes that production object or operation
unconstructible or explicitly ineligible. It does not block independent exact
type, fixture, canonicalization, history, loader, and integration work.

## 11. Review route and stop condition

After a coherent implementation candidate is committed and pushed, request
independent review of the exact head/tree across:

- SciML/physics semantics;
- statistics and evidence-design semantics; and
- protocol/identity/security-boundary semantics.

Repair valid findings and rerequest exact-head review after material changes.
Issue #42 notification is lead visibility, not review credit. Stop before
merging PR #60. Do not begin B-02B or another ticket.
