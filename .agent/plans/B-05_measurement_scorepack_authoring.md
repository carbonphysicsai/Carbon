# B-05 plan — measurement contract and Score Pack authoring

**Ticket:** B-05  
**Status:** in progress; working-contract and first-slice phase  
**Branch:** `agent/b-05-measurement-scorepack`  
**Worktree:** dedicated worktree; absolute host path intentionally not tracked  
**Exact base commit:** `f1a429de37290b3c7615ca051661a1d727528f78`  
**Exact base tree:** `3e25bd65508c5c11d8d67558f9bd699808fc57a9`  
**Working contract:** `Design_Specs/Measurement_and_ScorePack_Authoring_Contract.md`  
**Evidence:** `.agent/evidence/wave_b/b-05.md`

## 1. Activation and startup

1. Fetch without pull and require exact `origin/main` at the base above.
2. Verify the external B-01H completion receipt at PR #78 comment
   `5548725328`: reviewed head `a4e2e564…`, normal merge `f1a429d…`, exact
   reviewed/merge tree preservation, required checks/review/approval, and
   `NEXT_SELECTED_TICKET: B-05 in_progress but NOT STARTED`.
3. Preserve every pre-existing worktree. Create this ticket's dedicated branch
   and worktree from the exact selected base; do not pull, reset, rebase,
   amend, clean, force-push, or reuse another ticket's checkout.
4. Read authority in the ticket-specified order and inspect current B-02A,
   B-02C, B-04, and A5 seams before selecting a package boundary.
5. Verify the HoH B-05 requirements manifest maps the exact ticket blob and
   SHA-256, then run the installed-Codex projection probe. Record fail-closed
   unavailability separately from contract/runtime correctness.

## 2. Selected engineering decisions

- **B-05-D1:** add standard-library-only `carbon.measurement`, with one-way
  imports from public upstream types and a separate canonical domain. Leave
  A5's closed fixture schema and executor unchanged.
- **B-05-D2:** freeze a Challenge-bound `MeasurementContract` and explicit
  evidence-role/claim matrix. MMS and implementation evidence structurally
  cannot support physical validation, workload applicability, or context of
  use.
- **B-05-D3:** author a complete measurement-output-to-A5-key binding; enforce
  mandatory admissibility before scalar projection and reject raw, resource,
  mock/prior, product, chain, or commercial inputs.
- **B-05-D4:** make dependence, resampling, censoring, interaction, and
  shortcuts exact policy bindings. Any shortcut needs exact Dossier-qualified
  applicability to the incumbent/challenger evidence being compared.
- **B-05-D5:** own scientific reconstruction stages separately from B-02C
  resource facts; distinguish nomination/promotion, scientific stopping,
  heuristic futility, and typed `EVIDENCE_DEFERRED`.
- **B-05-D6:** use closed typed non-complete outcomes with no scalar payload;
  reserve real values and qualification outcomes to humans and B-06.

These are reversible engineering selections within the active ticket. Post
the required issue #42 notification mentioning `@harshaa765`; silence is not
approval and does not block bounded work. Any observed `CHANGE`, `BLOCKED`,
`REQUEST_CHANGES`, or owner deferral pauses only the affected scope.

## 3. Contract-first slices

### Slice 1 — measurement identity and evidence claims

Implement exact enums, unresolved scientific-value and stratum-applicability
bindings, `MeasurementContract`, `MeasurementQualificationEvidence`, nominal
refs, canonical bytes/hash, and a bounded in-memory fixture store. Add tests
for exact identity, round-trip, cross-Challenge rejection, role/claim matrix,
MMS-versus-validation confusion, floors, strata, fixture origin, and root
exports. This is the first coherent implementation slice.

### Slice 2 — uncertainty policy

Implement complete policy identities for estimand, independence/resampling
unit, pairing, reconstruction interactions, reference/representation/execution
dependence, censoring, minima, stopping/extension, error control, and exact
Dossier shortcut applicability. Keep all scientific choices ref-bound or
explicitly unresolved.

### Slice 3 — reconstruction evidence

Implement Challenge/family-scoped complete-base, reuse, nomination,
extension, promotion, coverage, stability-audit, deferred, and fail-closed
policy records. Consume only public B-02C resource facts and refs. Do not
modify B-02C decisions or make receipts scientifically authoritative.

### Slice 4 — Score Pack authoring and projection

Implement exact mapping from complete qualified measurement outputs to every
expected A5 input key. Validate numeric/Boolean kind, estimand, stratum,
uncertainty, aggregation/ranking/disclosure use, mandatory-first admissibility,
and forbidden inputs. Expose no public way to instantiate A5 `ScoreInput` or
invoke the engine; B-07F owns the official adapter.

### Slice 5 — fixture integration and review candidate

Compose a visibly synthetic fixture across all B-05 objects; run focused and
affected tests, invariants, package/wheel checks, strict formatting/linting,
canonical CI, Hub validation, and a complete-diff review. Repair every valid
finding and preserve the delivery protocol's exact-head requirements.

## 4. Human-reserved inputs

The implementation must not select real properties, formulas, observables,
units, precision, floors, applicability, measurements, strata, uncertainty or
dependence assumptions, evidence minima, build counts, stopping/error control,
stability rates, thresholds, transforms, weights, or qualification outcomes.
Unresolved values remain typed and fail closed. Fixture values are synthetic
and carry exact fixture origin.

## 5. HoH pilot disposition

The B-01H manifest `agent_pack/executors/hoh/manifests/b05.requirements.v1.json`
matches the exact B-05 ticket identity but declares no evidence commands.
Therefore it is a requirements/navigation map only; it cannot mark a B-05
requirement verified.

The installed Codex surface (`codex-cli 0.151.0-alpha.7.2`) fails the B-01H
projection-only write-profile preflight. `hoh.py probe-codex` exits 2 and the
harness remains unavailable before receiving private role context. Do not
weaken or modify the harness in B-05. Continue ordinary single-agent ticket
execution and report harness status separately from implementation evidence.

## 6. Validation plan

- Canonical wrapper is authoritative. If Docker is absent, record
  `PAUSED_INFRA` and rely on GitHub canonical CI before merge.
- Native Python 3.11 runs are diagnostic only and use exact locked/test-tool
  versions without changing the repository lock.
- Run the dedicated B-05 matrix plus affected B-02A/B-02C/B-04/A5 tests after
  every slice.
- Run `tests/cpu/test_code_authority.py`, package/wheel/outside-tree imports,
  all invariant tests, strict Ruff/Black, and diff hygiene before review.
- Regenerate Hub output from source and verify markers, route coverage,
  deterministic render, and smoke tests whenever authority state changes.

## 7. Commit and Hub shape

Use one ticket branch and one eventual PR. The first authority commit **A**
contains the contract, decisions, plan/evidence, selected-ticket state, and
first coherent runtime slice. The Hub commit **H** follows with only Hub source
and renderer-determined output, pinning `meta.authority_snapshot_commit` to
**A**. Later slice commits may advance the candidate, but no final evidence or
maturity claim is made until the exact final tree is tested and reviewed.

## 8. Explicitly deferred work

B-06 Dossier qualification; B-07F official plan and A5 input construction;
B-E1 statistical coverage/failure harness; B-E2 expanded solver/runtime
failure work; candidate/reference execution; real scientific values; ranking,
frontier, chain, settlement, product, commercial, production, and LIVE work
remain deferred.
