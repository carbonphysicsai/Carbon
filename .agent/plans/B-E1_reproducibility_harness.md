# B-E1 implementation plan — R0/R1/R2 reproducibility harness

**Starting main:** `527877bdd132c33569ac64c11b0a4360f5a08718`
**Ticket:** `.agent/tickets/B-E1_reproducibility.md`
**Delivery:** one branch and pull request under OWNER-DX-03
**Primary Hub map_ref:** `WAVE-B/B-E1`
**Implementation state:** accepted and normally merged as second parent
`831a34598f3f28ad8c05490244a4e0509473ac41` of main
`c484fd308d866d4b05a2765a984ec014dd96386e`

## Authority and start state

Current `origin/main` is the normal B-07G merge named in the owner request.
The merged `.agent/WAVE.md` and `.agent/WAVE_B.md` select B-E1 as the next
eligible ticket. B-02A, B-02B, B-02C, B-04, and B-05 are present in their
recorded bounded scopes. B-E2 and every later ticket remain outside this work.

The local canonical wrapper was invoked once and failed closed because Docker
is unavailable. Native Python 3.11 diagnostics passed 56 focused B-E1/direct
boundary tests and 1112 affected B-02A/B/C/B-04/B-05/B-E1 tests. GitHub's
pinned environment remains the shipping acceptance authority.

## Reuse classification

- **KEEP:** B-02A case/population identities; B-02B resolved-plan identity;
  B-02C build, replicate, frozen-reuse, resource-stop, and receipt facts; B-04
  reference outcomes and provenance; B-05 `UncertaintyPolicy`, qualified
  shortcut, `ReconstructionEvidencePolicy`, typed material, and staged outcome
  vocabularies.
- **WRAP:** those exact upstream identities in a separate fixture-only
  reproducibility graph and injected decision-procedure boundary.
- **REPAIR:** current post-B-07G board, maturity-ledger, and Hub presentation
  lag; no dependency runtime repair is presently indicated.
- **REPLACE:** none.

## Working engineering decisions

1. Add a standard-library-only `carbon.reproducibility` package with one-way
   imports from public upstream types. It owns B-E1 fixture evidence and
   comparison mechanics only; upstream packages do not import it.
2. Keep R0, R1, and R2 as nominal result types. R0 compares exact registered
   identity. R1 and R2 require injected, identity-bound procedures and return
   unresolved when required authority or applicability is absent.
3. Model evidence as an exact crossed reconstruction-by-whole-case graph with
   explicit arm, stratum, reconstruction, reference realization,
   representation, execution, training/hardware roles, missing/censoring
   state, and shared-dependency declarations. Canonical ordering must not
   erase the crossed interaction structure.
4. Keep reference variability, primary/witness disagreement,
   measurement/reference floors, generator/reference discrepancy,
   reconstruction variability, and finite-case sampling variation as separate
   evidence factors. Only an injected qualified procedure may combine them.
5. Prefer an applicable qualified joint procedure, then an applicable
   conservative-bound procedure. A quadrature/independence/zero-covariance
   shortcut is callable only when the exact B-05 shortcut, exact incumbent and
   challenger evidence sets, case/stratum scopes, applicability-test result,
   and Dossier qualification all match. Otherwise return a typed unresolved
   result.
6. Reuse B-05 reconstruction assessment for complete-base and resource/failure
   truth, and add an audit trail for static admission, base completion,
   repeat-promotion evidence, frozen reuse, stability audits, and qualified
   scientific sequential decisions. Pre-base or heuristic stopping returns
   only `EVIDENCE_DEFERRED`; it cannot invoke winner/ranking/frontier logic.
7. Make fixture policies structurally `TEST_ONLY` and non-production. Synthetic
   tolerances, coverage/power parameters, and procedures live only in tests.
   Runtime code contains no numeric scientific default or convenient epsilon.

These are material but reversible engineering selections inside B-E1. Record
them durably as B-E1-D1 through B-E1-D7 and notify issue #42 mentioning
`@harshaa765`. Human scientific values remain unavailable and fail closed.

## Ordered implementation

1. [x] Write the B-E1 working contract, public enums/errors/identities, and exact
   identity manifest used by R0.
2. [x] Implement immutable crossed evidence cells, factor observations, dependency
   declarations, graph validation, deterministic canonical bytes, and exact
   evidence-set refs for incumbent and challenger.
3. [x] Implement injected R1 numerical comparison and R2 decision procedures,
   exact qualification/applicability checks, joint/conservative/shortcut
   selection, typed contested outcomes, and no-frontier result surface.
4. [x] Implement reconstruction-stage audit plumbing around exact B-05 policy and
   resource facts, including scientific sequential continuation/stopping,
   random stability audit records, heuristic deferral, and failure precedence.
5. [x] Add deterministic fixture replay plus null, coverage, power, correlation,
   heteroscedasticity, interactions, pairing, missing/censored, disagreement,
   floor/discrepancy, manufactured-anchor, ordering, hardware, hostile-input,
   provenance-mismatch, and every failure-class test.
6. [x] Add invariant tests for dependency direction, absence of embedded science,
   TEST_ONLY isolation, exact-match R0-only semantics, no false elimination,
   and no ranking/frontier/score/settlement side effect.
7. [x] Reconcile ticket/board/evidence/maturity and Hub source, regenerate Hub
   outputs, run focused/affected/full diagnostics, then ship through one ready
   candidate acceptance and normal expected-head merge.

## Explicit boundary and maturity ceiling

The harness may earn bounded `SPECIFIED`, `IMPLEMENTED`, and `TESTED` for
fixture engineering. It supplies no real backend profile, tolerance, sample
size, dependence model, applicability criterion, coverage/power rule,
stopping/error-control rule, audit rate, scientific qualification, security
qualification, production authority, LIVE state, ranking, frontier event,
network intent, settlement, weight, or emission.
