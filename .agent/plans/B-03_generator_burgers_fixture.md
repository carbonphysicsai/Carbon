# B-03 plan — generator runtime contract and Burgers fixture

**Ticket:** B-03 — Generator API and fixed-viscosity Burgers fixture
**Status:** `done` in bounded merged engineering scope
**Contract branch:** `agent/b-03-generator-contract`
**Contract worktree:** dedicated local worktree; absolute host path intentionally not recorded
**Exact contract base:** `1dc41288e2d0e516de21d05dc168b188791c39f5`
**Exact base tree:** `eb9b0c9b899cc4be9c8e9b22c16a5a3a48406a12`
**Working contract:** `Design_Specs/Generator_Runtime_Contract.md`
**Implementation branch after the contract gate:** `agent/b-03-generator-burgers-fixture`
**Exact reviewed contract head/tree:** `139d491c8cf9d144f472e38aa14a4721ed0d8870` /
`71a3754f520411b599152c8788dacdce0f987b9f`
**Contract merge commit/tree:** `b86daa5d8b0f8b3e86bb82c2661f405747a200df` /
`52c3e5f130f771ccd21f96ea8f422f3e96106302`
**Exact implementation base/tree:** `b86daa5d8b0f8b3e86bb82c2661f405747a200df` /
`52c3e5f130f771ccd21f96ea8f422f3e96106302`
**Implementation worktree:** dedicated local worktree; absolute host path intentionally not recorded

## 1. Dependency and selection gate

B-03 depends on B-02A. That dependency is authoritatively `done` in bounded
merged engineering scope at the identities recorded by the Wave-B board. The
new contract workspace was created from fetched exact `origin/main` only after
B-02C PR #66 normally merged repaired reviewed head
`a30865d2349f1cc6e725f1ea15e923f8d7893e4c` as
`1dc41288e2d0e516de21d05dc168b188791c39f5`, preserved tree
`eb9b0c9b899cc4be9c8e9b22c16a5a3a48406a12`, and exact-main CI
`33388595061` passed. The contract branch closed B-02C and selected only B-03;
it did not implement runtime code.

## 2. Authority and disposition

Read the repository/agent constitutions, execution and delegated-decision
protocols, invariants, Wave/Wave-B board and handoff, B-03 and B-02A tickets,
B-02A contract, generator creation/validation, challenge distribution,
evidence/envelope, data-management, B-07R architecture, relevant Build Out,
constitutional overlay, Master Plan, MQ-002/MQ-003, and current B-02A/A3/A4
code/test/package boundaries. No archived implementation is selected or read.

Disposition:

- `KEEP + WRAP` B-02A exact authoring objects, refs, case identity, graph
  validator, replacement/censoring/disposition, and disclosure seams;
- `KEEP + WRAP` A4 fixture-only context/provider/derivation without a second
  entropy owner or public raw-material interface;
- `KEEP + WRAP` A3 structural fixture provenance and LIVE fail-closed gate;
- `NEW` standard-library-only `carbon.generators` and
  `carbon.generators.burgers` fixture implementation;
- `DEFERRED_FAIL_CLOSED` every MQ-002/MQ-003 population, range, threshold,
  adequacy, qualification, production, and LIVE input; and
- `DO NOT REUSE` retired or illustrative generator runtime code.

## 3. Contract phase

1. Reconcile B-02C's repaired exact-head review, normal merge, tree
   preservation, and exact-main CI into ticket/plan/evidence and Wave-B state.
2. Mark B-02C `done` only in its bounded engineering scope and select B-03
   `in_progress` consistently across wave, board, handoff, ticket, plan, and
   evidence records.
3. Define exact B-03 ownership; request, descriptor, role/replay/attempt,
   generation-event, result, public-projection, and canonical boundaries;
   closed outcomes; A4 material handling; B-02A case construction; attempt and
   intended-realized accounting; authority echoes; conformance facts; and the
   fixed-viscosity structural fixture.
4. Record B-03-D1 through B-03-D8 with recommendation, rationale,
   alternatives, downstream impact, migration/supersession, and reserved
   inputs.
5. Run applicable document/link/scope/diff validation and noncanonical
   targeted baseline tests; record native Darwin rejection rather than calling
   it canonical CI.
6. Open one contract PR titled `B-03: define generator runtime contract` with
   the required `Lead notification` section. Notify issue #42 mentioning
   `@harshaa765`; notification is non-blocking. Route only an explicit owner
   deferral to issue #41.
7. Require exact-head GitHub Linux CI and ready-state Greptile correctness
   review. Repair every valid finding, require zero unresolved threads, and
   rereview every changed tree.
8. Normally merge only the exact reviewed head with an exact-head guard;
   verify ordered parents and exact tree preservation; then require exact-main
   CI. Do not create a recursive closeout PR.

## 4. Implementation phase after the contract gate

All contract gates passed on exact reviewed head
`139d491c8cf9d144f472e38aa14a4721ed0d8870`: PR #67 passed exact-head CI,
received a 5/5 Greptile review with zero comments or unresolved threads, and
normally merged as `b86daa5d8b0f8b3e86bb82c2661f405747a200df`. Exact-main CI then passed,
so implementation began from that exact merge and no earlier tree.

Implementation sequence:

1. fetch without pull and create fresh branch
   `agent/b-03-generator-burgers-fixture` in a dedicated worktree from the new
   exact `origin/main`; record base SHA/tree and exact merged contract commit;
2. repeat baseline doctor/CI and affected B-02A/A3/A4 tests without mutating a
   noncanonical environment or recording Darwin as canonical;
3. implement the smallest `carbon.generators` public surface and
   `carbon.generators.burgers` structural fixture described by the merged
   contract, with no future-ticket placeholders;
4. update only code authority, package-installation, outside-tree,
   reverse-dependency, and no-leakage inventories required by the new package;
5. add focused model/canonical/outcome/attempt/conformance/fixture/disclosure/
   LIVE/public-surface/invariant tests and the affected B-02A/A3/A4 matrix;
6. run focused, affected, invariant, full CPU, package/wheel/outside-tree,
   authority, quality, and diff hygiene checks;
7. open one draft PR titled
   `B-03: implement generator API and Burgers fixture`, notify issue #42,
   move ready only for routine review, obtain exact-head CI and Greptile,
   repair every valid finding with rereview, and require zero unresolved
   threads; and
8. stop before merging the implementation PR. Do not start B-04, B-05,
   B-07S, or a later ticket.

The bounded implementation package consists of exactly these eleven modules:

```text
carbon/generators/__init__.py
carbon/generators/accounting.py
carbon/generators/authorities.py
carbon/generators/burgers.py
carbon/generators/canonical.py
carbon/generators/conformance.py
carbon/generators/disclosure.py
carbon/generators/errors.py
carbon/generators/model.py
carbon/generators/refs.py
carbon/generators/service.py
```

Validation covers focused B-03 CPU and invariant suites; affected B-02A, A3,
and A4 boundaries; full CPU and invariant suites; package installation,
wheel/outside-tree import, public-surface and code-authority checks; formatting,
lint, compilation, repository quality, and diff/privacy hygiene. The tracked
candidate records its base/tree, manifest, commands, and local results without
claiming its own recursive commit identity. After push, the implementation PR,
exact-head Linux CI, and Greptile metadata supply final immutable head/tree and
review facts. Any tree change invalidates those facts and requires fresh CI and
Greptile rereview.

## 5. Verification matrix

- exact immutable model/ref fields and semantic ref recomputation;
- Challenge, primary/selection/plan (including P/Q/w only when the official
  plan binds them), role, generator, environment, replay, attempt, fixture, and
  loaded-graph bindings;
- closed role-to-A4 fixture-domain mapping and fail-closed unavailable roles;
- deterministic canonical replay and B-02A case identity;
- exact six-outcome taxonomy with strict disposition-facing case matrix and
  protected post-case infrastructure-artifact retention;
- nominal per-population support/exclusion, censoring, accounting, and near-
  duplicate authority echoes;
- one derivation per attempt, no silent retry, exact replacement lineage, and
  intended-versus-realized denominator preservation;
- fact-only support/strata/tail/summary/duplicate/degeneracy/censoring hooks
  without thresholds;
- periodic fixed-viscosity fixture shape, explicit unavailable production
  values, and no PDE/reference/score result;
- zero seed/context/provider/protected identity/stratum/payload/reversible
  input leakage;
- structural fixture-origin propagation and A3 LIVE rejection; and
- standard-library wheel/import/code-authority/one-way dependency boundaries.

## 6. Closeout and maturity ceiling

PR #69 normally merged exact reviewed head
`702bf274b1a0c4bfefa075d8da08d3e7217a53d1`, tree
`65dc9f5da4368482ad8ece155a63ff24ef46bf24`, as
`d5d1372f1311132ed9d60e10e36c4fb7d43a2473` with ordered parents
`b86daa5d8b0f8b3e86bb82c2661f405747a200df` and
`702bf274b1a0c4bfefa075d8da08d3e7217a53d1`. The merge tree is exactly the
reviewed tree. Exact-head run `33452836347` passed canonical job
`99686330212` and clean-container job `99686330328`; Greptile check
`99686337091`, summary `5486024114`, reviewed all 36 files with zero comments
or unresolved threads. Exact-main push run `33460078744` passed canonical job
`99708199542` and clean-container job `99708199446`. Issue #42 closeout comment
`5487728238` records the immutable evidence.

```text
SPECIFIED: YES — BOUNDED ENGINEERING CONTRACT ONLY
RATIFIED_ENGINEERING_CONTRACT: YES
IMPLEMENTED: YES — BOUNDED MERGED IMPLEMENTATION
TESTED: YES — EXACT-HEAD AND EXACT-MAIN CI
GREPTILE_REVIEWED: YES — EXACT REVIEWED HEAD
MERGED: YES
GENERATOR_CONFORMANCE_QUALIFIED: NO
OPERATIONS_APPROVED: NO
ECONOMICS_APPROVED: NO
SECURITY_QUALIFIED: NO
NETWORK_QUALIFIED: NO
SCIENTIFICALLY_QUALIFIED: NO
COMMERCIALLY_VALIDATED: NO
PRODUCTION_QUALIFIED: NO
LIVE: NO
```

Every real population, range, method, threshold, adequacy, qualification,
security, operations, production, economics, and LIVE input remains reserved
and unavailable.
