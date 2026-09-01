# B-04 plan — reference and TruthAsset contracts

**Ticket:** B-04 — ReferencePolicy, TruthAsset, and reference runners<br>
**Status:** `in_progress`; contract phase complete and ratified, runtime phase
paused behind B-01F<br>
**Branch:** `agent/b-04-reference-truth-contract`<br>
**Worktree:** dedicated local worktree; absolute host path intentionally not recorded<br>
**Exact base commit:** `74ef837deed20b8fb9f0a5137086b15fc82bf820`<br>
**Exact base tree:** `325022d9b43b119235af50214152ad269fa3cb6a`<br>
**Working contract:** `Design_Specs/Reference_and_TruthAsset_Contract.md`<br>
**Evidence:** `.agent/evidence/wave_b/b-04.md`

This plan records the completed PR #72 contract phase. Its external completion
receipt records the final reviewed-tree, checks, merge topology, and exact-main
facts. `OWNER-DX-01` now pauses runtime behind B-01F without altering the
contract. No B-04 implementation is authorized in the B-01F session.

## 1. Completed contract startup and closeout gate

1. Fetch `origin` without pull and record exact main commit/tree.
2. Require B-03 merge `d5d1372f1311132ed9d60e10e36c4fb7d43a2473`
   to remain ancestral and verify PR #69, its ordered parents, reviewed/merge
   tree equality, exact-head CI and Greptile, exact-main CI, and issue #42
   closeout comment.
3. Inspect every commit after that merge. The fetched branch base had advanced
   only through merged PR #70, Development Hub v2.1; it did not select another
   ticket, introduce B-04 capability, or conflict with the B-03-to-B-04
   transition.
4. Read fetched-base authority in the required order and record its startup
   state as B-03 `in_progress`, B-04 `todo`, with no competing transition.
5. Check issues #42 and #41 for an applicable `CHANGE`, `BLOCKED`,
   `REQUEST_CHANGES`, or `DEFER_TO_OWNER`. Silence is not approval; issue #41
   is used only if an explicit owner deferral appears.
6. Preserve the existing B-03 branch/worktree. Do not reset, rebase, amend,
   clean, force-push, remove, or reuse it.

PR #72's external completion receipt verifies exact-head canonical,
clean-container, Hub, and Greptile success; normal merge with exact reviewed-
tree preservation; and exact-main canonical, clean-container, and Hub success.
The contract gate is satisfied without copying those dynamic identities into
the tracked tree.

## 2. Authority and disposition

Apply `KEEP → WRAP → REPAIR → REPLACE` to the exact current repository:

- `KEEP + WRAP` `carbon.authoring` canonical Challenge, case, graph,
  evidence-kind, provenance, disclosure, use-restriction, and owner-ref
  primitives. B-04 does not redefine case identity.
- `KEEP` the reserved `carbon.evaluation` package as B-04's future package
  owner. It currently provides only a location and no B-04 capability.
- `KEEP` `carbon.generators`, `carbon.scoring`, registry lifecycle, seeding,
  audit, and qualification boundaries unchanged; B-04 neither imports the
  generator package nor owns measurement, scoring, LIVE, or qualification.
- `WRAP` low-level B-02A canonical primitives under a future B-04-owned,
  versioned canonical profile and domain header. Do not widen B-02A's closed
  schema registry and do not reuse the generator canonical profile.
- `REPLACE / EXCLUDE` any generic truth mode, solver-by-reputation authority,
  self-cross-check, implicit fallback, nominal-tolerance truth, or direct
  solver path from future authoritative use.
- `MIGRATION_REQUIRED` for any later deliberate legacy or Julia adapter; B-E2
  owns Julia/service adapters and expanded runtime/failure injection, while
  B-04 retains its bounded minimal deterministic fixture runners and failure
  tests. The archive is not read in this contract session.
- `NEW_OWNER_DECISION_REQUIRED` for every real method, viscosity, support,
  tolerance, mesh, timestep, precision, conditioning, uncertainty,
  disagreement, fallback, correlation, resource, security, qualification, or
  LIVE value.

## 3. Contract phase

1. Reconcile B-03 as `done` only in bounded merged engineering scope, with
   exact reviewed head/tree, CI/Greptile, merge/parents/tree, exact-main CI,
   and issue closeout evidence.
2. Select B-04 `in_progress` in contract phase consistently across candidate
   Wave, board, handoff, ticket, plan, evidence, decision, and Hub source.
3. Define a Challenge-bound, positive-admission answer-key contract covering:
   policy, composition, execution-target, and asset identities; orthogonal
   evidence-kind, authority-function, and source-class roles; nominal
   primary/witness grants and runners; closed resolution/run/comparison/
   admission outcomes; exact same-policy target/component containment,
   canonical semantic duplicate rejection across entry/composition/witness-
   target inventories, scope cross-binding, and expanded primary/witness
   disjointness;
   applicability, conditioning, uncertainty, independence/correlation,
   disagreement, closed failure reasons/precedence, positive admission
   decisions including artifact absence/ineligibility; structural-only grant
   issuance; no fabricated event for bare issuer/authority absence;
   provenance, caching, disclosure, and historical
   interpretation.
4. Record B-04-D1 through B-04-D10 with recommendation, rationale, rejected
   alternatives, interfaces/invariants, downstream owners, reversibility,
   exact paths, and reserved inputs.
5. Reserve B-04-D11 for the later pre-runtime exact v1 record field/type/order
   registry, outcome/reason compatibility matrices, and exact ordered
   `carbon.evaluation.__all__` tuple. The fixed profile, framing, primitive
   semantics, decoder ceilings, and ref inventory do not claim executable
   canonical bytes or an exact root surface before D11.
6. Keep `ReferenceArtifact`, positive-only `TruthAsset`, and
   `FixtureReferenceAsset` distinct. Execution success or artifact presence
   never grants truth authority.
7. Keep B-05 measurement/scoring, B-06 qualification, B-07F fixture
   composition, and B-E2 Julia/service adapters plus expanded runtime/failure
   injection as explicit downstream consumers/owners. B-04 owns only its
   bounded minimal deterministic fixture execution and failure tests.

## 4. Completed Development Hub reconciliation

Merged Development Hub v2.1 makes `WAVE-B/B-04` a primary mapped reference.
Use the required two-commit history:

1. authority commit **A** contains only the eleven requested Markdown
   governance/contract paths;
2. Hub commit **H** updates only Hub source plus deterministic renderer output,
   with `meta.authority_snapshot_commit` pinned to **A**;
3. append an immutable B-03-closeout/B-04-transition change event;
4. regenerate outputs using the repository renderer; never hand-edit generated
   files; and
5. validate Hub source, source markers, routes, renderer determinism, and
   browser smoke behavior.

The final manifest therefore expands beyond eleven paths only as required by
the merged Hub authority. The PR declares `HUB_UPDATE_REQUIRED` for
`WAVE-B/B-03` and `WAVE-B/B-04`.

## 5. Completed contract validation and independent review

- Record the canonical-environment guard on Darwin as an expected rejection,
  not a test pass.
- Run existing B-02A case/authoring, B-03 generator/failure, A3 fixture/LIVE,
  A4 randomness/leakage, A5 failure/scoring, package, code-authority, and
  invariant baselines without adding B-04 tests.
- Run changed-link, heading/table, privacy, self-identity, manifest,
  whitespace, and repository diff-hygiene checks.
- Run all required Development Hub render/check/validation/route/smoke checks.
- Obtain two read-only audits: one scientific/epistemic and one canonical/
  provenance/package/security/cross-ticket audit. Repair every valid finding.
- Open a draft PR titled `B-04: define reference and TruthAsset contract`, post
  the decision notification to issue #42 mentioning `@harshaa765`, then move
  ready only when the tree and local validation settle.
- Require exact-head canonical and clean-container CI, successful Greptile
  correctness review, and zero unresolved review threads. Every tree change
  requires fresh CI and review.

## 6. B-01F pause and runtime resumption boundary

The contract PR is merged and ratified. Runtime remains paused until B-01F's
exact final candidate passes scope-required exact-head checks and `Merge gate`,
exact-head Greptile with every valid finding repaired and zero unresolved
threads, normal exact-expected-head merge with reviewed-tree preservation, and
exact-main `Merge gate`. Only then create a fresh
`agent/b-04-reference-truth` branch from the verified exact main. Do not
implement a runtime, reference method, solver, fixture runner, Julia service,
Cole–Hopf routine, store, transport, measurement, score, Dossier, or later-
ticket interface in B-01F.

```text
SPECIFIED: YES — BOUNDED ENGINEERING CONTRACT
RATIFIED_ENGINEERING_CONTRACT: YES
IMPLEMENTED: NO
TESTED: CONTRACT/DOCUMENT AND EXISTING-BASELINE VALIDATION ONLY
REFERENCE_QUALIFIED: NO
OPERATIONS_APPROVED: NO
SECURITY_QUALIFIED: NO
NETWORK_QUALIFIED: NO
SCIENTIFICALLY_QUALIFIED: NO
COMMERCIALLY_VALIDATED: NO
PRODUCTION_QUALIFIED: NO
LIVE: NO
```
