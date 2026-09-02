# B-04 plan — reference and TruthAsset contracts

**Ticket:** B-04 — ReferencePolicy, TruthAsset, and reference runners<br>
**Status:** final single-ticket runtime candidate; B-04 `done` and B-05
selection remain conditional<br>
**Branch:** `agent/b-04-reference-truth`<br>
**Worktree:** dedicated local worktree; absolute host path intentionally not recorded<br>
**Exact base commit:** `7161fe3c4a04821b7f676ab006bd5d313d0442d2`<br>
**Exact base tree:** `619e366dead2288ccfd312f54ad09f17f86a1c62`<br>
**Working contract:** `Design_Specs/Reference_and_TruthAsset_Contract.md`<br>
**Evidence:** `.agent/evidence/wave_b/b-04.md`

This plan retains the completed PR #72 contract phase and records the completed
bounded runtime candidate begun after PR #73 satisfied `OWNER-DX-01`. The B-01F
receipt at PR #73 comment `5497405775` selects B-04 from the exact base above.
B-04-D11 froze the executable v1 schema before the first runtime model; issue
#42 comment `5497811877` delivered its non-gating lead notification.

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
- `KEEP` the reserved `carbon.evaluation` package as B-04's implemented package
  owner, with only the exact D11 public allow-list at its root.
- `KEEP` `carbon.generators`, `carbon.scoring`, registry lifecycle, seeding,
  audit, and qualification boundaries unchanged; B-04 neither imports the
  generator package nor owns measurement, scoring, LIVE, or qualification.
- `WRAP` low-level B-02A canonical primitives under the B-04-owned,
  versioned canonical profile and domain header. Do not widen B-02A's closed
  schema registry and do not reuse the generator canonical profile.
- `REPLACE / EXCLUDE` any generic truth mode, solver-by-reputation authority,
  self-cross-check, implicit fallback, nominal-tolerance truth, or direct
  solver path from authoritative use.
- `MIGRATION_REQUIRED` for any later deliberate legacy or Julia adapter; B-E2
  owns Julia/service adapters and expanded runtime/failure injection, while
  B-04 retains its bounded minimal deterministic fixture runners and failure
  tests. The archive was not read or revived.
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
5. The contract phase reserved B-04-D11 for the pre-runtime exact v1 record
   field/type/order registry, outcome/reason compatibility matrices, and exact
   ordered `carbon.evaluation.__all__` tuple. The runtime phase recorded and
   notified that decision before the first model; no pre-D11 executable-byte or
   root-surface claim was made.
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
- Require exact-head canonical and clean-container CI, fresh complete-diff
  Codex/GPT review, distinct non-author human approval carrying the closed
  receipt, successful `GPT review gate`, and zero unresolved review threads.
  Every tree change requires fresh CI and review.

## 6. Completed bounded runtime slices

PR #73 satisfied the exact B-01F predicate and selected this branch from the
base recorded above. The runtime work then completed these coherent slices:

1. D11 exact enums, subordinate and standalone models, nominal refs, one-to-one
   canonical registry, hostile-input reconstruction, and exact ordered package
   root;
2. policy entry/composition/manifest construction with same-Challenge,
   same-policy, exact-inventory, semantic-duplicate, primary/witness
   disjointness, MMS-role, and no-authority-transfer enforcement;
3. distinct primary and witness request/grant/resolution/run interfaces with
   one-use capabilities, closed outcome/reason/absence matrices, typed
   infrastructure/reference failures, and no generic fallback;
4. comparison, provenance, support/applicability, conditioning, uncertainty,
   and complete categorical dependency-correlation disclosure without invented
   scientific thresholds;
5. distinct `ReferenceArtifact`, non-LIVE `FixtureReferenceAsset`, and
   positive-only `TruthAsset` admission with structural issuance separated from
   substantive admission; and
6. protected/public projections plus minimal deterministic standard-library
   fixture runners for supported, conditioning, disagreement, numerical,
   malformed/provenance, infrastructure, correlation, and no-fallback paths.

B-04-D12 keeps the admission callback boundary at-most-once: complete graph
and authority validation precede the atomic claim, while the one-use grant is
consumed immediately before the saved external callback and is never rolled
back after callback start. Non-`Exception` provider control signals are replaced
outside the provider context by a fixed protected, nonpickleable control signal
without changing the release-before-claim or burn-after-callback transition.
This clarifies the ratified one-attempt/no-retry and protected-disclosure
contract without changing D11 bytes or adding a production retry/cancellation
policy.

The implementation preserves one-way explicit imports from current B-02A
submodules and does not import `carbon.generators`, scoring, registry lifecycle,
seeding, or any later owner. Julia, Cole–Hopf, production solvers/services,
stores, transport, measurement, score, Dossier, qualification, and later-ticket
interfaces remain excluded.

## 7. Exact non-Hub candidate manifest

The runtime implementation paths are exactly:

```text
carbon/evaluation/__init__.py
carbon/evaluation/admission.py
carbon/evaluation/assets.py
carbon/evaluation/canonical.py
carbon/evaluation/comparison.py
carbon/evaluation/disclosure.py
carbon/evaluation/enums.py
carbon/evaluation/errors.py
carbon/evaluation/execution.py
carbon/evaluation/fixtures.py
carbon/evaluation/model.py
carbon/evaluation/policy.py
carbon/evaluation/refs.py
carbon/evaluation/runners.py
```

The focused and boundary test paths are exactly:

```text
tests/cpu/test_b04_admission_contract.py
tests/cpu/test_b04_canonical_contract.py
tests/cpu/test_b04_disclosure_contract.py
tests/cpu/test_b04_execution_contract.py
tests/cpu/test_b04_failure_and_disclosure.py
tests/cpu/test_b04_fixture_runtime.py
tests/cpu/test_b04_matrix_contract.py
tests/cpu/test_b04_noncanonical_carrier_regressions.py
tests/cpu/test_b04_policy_contract.py
tests/cpu/test_b04_public_surface.py
tests/cpu/test_code_authority.py
tests/cpu/test_package_installation.py
tests/invariants/test_b04_reference_truth_boundaries.py
```

The durable decision path is exactly:

```text
.agent/DECISIONS.md
```

The conditional authority snapshot paths are exactly:

```text
.agent/WAVE.md
.agent/WAVE_B.md
.agent/WAVE_B_CODEX_HANDOFF.md
.agent/evidence/wave_b/b-04.md
.agent/plans/B-04_reference_truth_contracts.md
.agent/tickets/B-04_reference_truth_contracts.md
.agent/tickets/B-05_measurement_scorepack_authoring.md
```

B-04-D11 and its Decision Console record were committed before the first model.
The final Development Hub commit separately pins this authority snapshot and
contains only required Hub source plus renderer-determined outputs.

## 8. Engineering validation and independent audits

Fresh corrected-candidate results are required after the D12 coverage and
current-main synchronization settle. The earlier numeric ledger is superseded
and is not evidence for the final candidate:

| Scope | Result |
|---|---|
| focused B-04 CPU + invariant matrix | PENDING final-candidate rerun |
| affected B-02A/B-03/A3/A4/A5 and boundary regressions | PENDING final-candidate rerun |
| full invariant suite | PENDING final-candidate rerun |
| package, wheel, outside-tree, and code-authority scope | PENDING final-candidate rerun |
| strict Ruff, strict Black, compilation, and diff hygiene | PENDING final-candidate rerun |
| full CPU suite | PENDING final-candidate rerun |

The prior scientific/epistemic and canonical/identity/provenance/disclosure/
capability audits predate D12 and are not final-candidate evidence. The old
grant-consumption finding is `PARTIALLY_VALID / CLARIFIED`; fresh independent
audits are required after synchronization, and no provider failure is treated
as an admission decision.

Local Darwin results are diagnostic only. Exact candidate acceptance still
requires the repository-selected `RUNTIME_FULL` canonical Linux scope,
Delivery preflight, Canonical environment, Clean dev-container, Development
Hub, exact-head `Merge gate`, fresh complete-diff Codex/GPT review, distinct
non-author human approval, and `GPT review gate`.

## 9. Conditional closeout and next-ticket transition

The prepared B-04 `done`, bounded `IMPLEMENTED`/`TESTED`, and B-05
`in_progress` states remain inert until the exact final head/tree passes every
scope-required exact-head check and `Merge gate`; fresh read-only Codex/GPT
review covers the complete exact-head diff with every finding repaired or
dispositioned; a distinct non-author human approval carries the closed
exact-head/tree receipt; `GPT review gate` succeeds with zero unresolved review
threads and no applicable block; a normal expected-head merge preserves
ordered second-parent and reviewed-tree identity; the reviewed head is
ancestral to fetched exact main; exact-main `Merge gate` and every push-only
requirement succeed; and the completed normalized external receipt is posted.

That receipt alone records the final reviewed head/tree, CI/check identities,
Codex/GPT review receipt, human approval review, `GPT review gate`, and thread
count; merge/parents/tree; exact-main results; final bounded maturity; and
B-05's exact starting main/tree. If any predicate fails,
the prior merged B-04 `in_progress` / B-05 `todo` state remains controlling.
No recursive evidence-only commit is required, and no B-05 contract or runtime
work begins in this session.

```text
SPECIFIED: YES — BOUNDED ENGINEERING CONTRACT
RATIFIED_ENGINEERING_CONTRACT: YES
IMPLEMENTED: YES only after the complete conditional predicate, and only for
             the exact bounded merged fixture runtime
TESTED: YES only after that predicate, and only for the exact recorded
        engineering acceptance scope
REFERENCE_QUALIFIED: NO
OPERATIONS_APPROVED: NO
SECURITY_QUALIFIED: NO
NETWORK_QUALIFIED: NO
SCIENTIFICALLY_QUALIFIED: NO
COMMERCIALLY_VALIDATED: NO
PRODUCTION_QUALIFIED: NO
LIVE: NO
```
