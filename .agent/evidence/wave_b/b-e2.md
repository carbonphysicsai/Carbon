# B-E2 evidence — Julia and reference failure boundary

**Tracked evidence class:** Python contract implementation and deterministic
fixture tests
**Starting main:** `c484fd308d866d4b05a2765a984ec014dd96386e`
**Starting tree:** `fadd82c3cfe6d604f7a068a93886d534ea9cd077`
**Primary Hub map_ref:** `WAVE-B/B-E2`
**Maturity ceiling:** bounded SPECIFIED / IMPLEMENTED / TESTED only

## B-E1 reconciliation

PR #99 normally merged accepted B-E1 head
`831a34598d6779d369f01de3523c3d8ee0385d18` as
`c484fd308d866d4b05a2765a984ec014dd96386e`. Accepted CI run `34124228848`
passed its applicable jobs and Merge gate. The stale candidate/pending wording
in the B-E1 plan, evidence, and current maturity ledger is documentation/status
lag only. Historical candidate evidence remains intact; present-tense status is
reconciled to bounded `done` in SPECIFIED / IMPLEMENTED / TESTED scope.

## Implemented behavior

`carbon.evaluation.service_boundary` wraps, and does not redefine, B-04's
exact primary/witness requests, one-use grants, resolution records, run records,
role types, identity refs, applicability, conditioning, uncertainty,
provenance, artifact binding, resource receipt, and terminal outcome/reason
matrix. A registered in-process provider receives only the already-authorized
request/grant. Its response is hostile until every exact binding matches.

The adapter rejects or types partial, stale, substituted, cross-case,
cross-Challenge, cross-role, wrong-policy/version, wrong-implementation,
wrong-environment/configuration, malformed-provenance, and duplicate material.
Provider timeouts, unavailable dependencies/services, transport loss, process
failure, malformed replies, numerical failure, unresolved conditioning or
uncertainty, unsupported/non-applicable cases, and identity/provenance failures
remain their exact B-04 terminal classes. Only a structurally complete success
may bind an artifact, and the B-E2 artifact is always `FIXTURE_ONLY`.

`ReferenceServiceAttemptHistory` retains each exact attempt. A fixture retry
after dependency loss uses distinct request/grant/resolution/run refs while
preserving idempotency and the complete scientific execution context. It keeps
the original infrastructure failure and the later fixture success as separate
facts. Duplicate or drifted attempts reject; the history has no aggregate
success, truth, score, or fallback projection.

The deterministic fixture graph also carries B-04's exact
`CONTESTED_DISAGREEMENT` comparison and one
`MANUFACTURED_SOLUTION_VERIFICATION` / `VERIFICATION_ANCHOR` entry. The anchor
cannot enter a primary/witness runner or acquire validation authority without a
new, separately registered identity and policy graph.

## Failure and non-authority proof

- Every failure run has typed artifact absence and cannot construct a
  `ReferenceArtifact`, `TruthAsset`, candidate score, rank, promotion,
  settlement, weight, or emission.
- A provider response has no callable/import path, command, filesystem path,
  URL, credential, mode, seed, protected case payload, or candidate-result
  field. Arbitrary mappings/bytes are malformed and never executed.
- The adapter imports no scoring, leaderboard, TrainEval, MCP, qualification,
  generator, seeding, network, Julia, or retired runtime owner.
- A duplicate invocation is rejected before a second provider call. A stale
  response on a fresh attempt becomes `VERSION_OR_IDENTITY_MISMATCH` and gains
  no artifact.
- Reference disagreement remains contested and is never averaged. Service or
  reference failure never becomes negative candidate evidence.

## Verification

The canonical wrapper was attempted once and failed closed because Docker is
unavailable. Native CPython 3.11.16 diagnostics currently report:

```text
55 focused B-E2/direct B-04 invariant tests passed
420 affected B-04/B-E1/B-E2 tests passed
4539 complete repository tests passed; 2 expected skips
Ruff 0.16.3 and Black 26.5.1 pass the changed Python files
```

The complete invariant, package/wheel/outside-tree, quality-ratchet, and Hub
results are recorded in the ready PR/CI. GitHub's pinned environment is the
shipping authority.

## Decisions and conditional completion

Working decisions B-E2-D1 through B-E2-D3 are recorded in
`.agent/DECISIONS.md` and routed to issue #42 comment `5572204359` for
technical/SciML awareness.
B-E2 bounded completion becomes authoritative only after the unchanged ready
revision passes applicable automated acceptance and normally merges. B-E4 is
the next dependency-ready board ticket but remains `todo` and unstarted until
that merge.

## Explicit unresolved gaps

Archived Julia is not restored. Julia runtime availability/integration,
Project/Manifest supply-chain evidence, a real SciML service, MMS or analytic
implementation evidence, method applicability/conditioning/uncertainty,
scientific qualification, production security/operations, retry/fallback
policy, protected data handling, and LIVE reference authority all remain
absent and human-owned.

## Successor repair evidence — B-E2-R1

PR #100 accepted head `69620f76397c3e72b58ee0d59faf70505963fce1`
in run `34137457116` and normally merged as
`602628d3c62f01524336db888da8fcfc7ed379d7`. Those facts remain historical;
the successor repair does not amend or relabel the original acceptance.

Installed-repository runner reproduction confirmed that an otherwise valid
response whose `component_bindings` tuple contained a synthetic object could
reach tuple equality before element validation. Synthetic `SystemExit` and
`KeyboardInterrupt` values escaped at both the primary and witness runner
boundaries. The provider had already been invoked, while the hostile element's
equality callback supplied the escaping control flow.

`carbon.evaluation.service_boundary` now reconstructs the complete
`ReferenceServiceResponse`, including every nested component carrier and the
closed reason tuple, before any equality, identity, provenance, assessment,
artifact, or terminal comparison. Invalid nested values cannot enter accepted
result construction. A malformed failure run uses only the trusted registered
context, and the one-use attempt remains burned. The existing fixed protected
control-signal normalization also covers any control signal still arising in
post-provider response processing.

Native noncanonical CPython 3.11.16 diagnostics after the repair report:

```text
55 focused B-E2 runner tests passed
439 affected B-04/B-E1/B-E2 CPU and invariant tests passed
Ruff 0.16.3 and Black 26.5.1 pass the changed Python files
```

GitHub's pinned environment remains shipping acceptance. The successor PR
records its exact CI and merge identity externally under OWNER-DX-03. The
repair changes no B-04 terminal precedence, retry history, comparison, MMS,
artifact-origin, qualification, or maturity semantics. B-E4 remains `todo`
and unstarted.
