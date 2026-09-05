# Ticket B-05 - MeasurementContract and Score Pack authoring bindings

**Wave:** B active in bounded development scope
**Status:** `in_progress`
**Conditional target:** `done` only under the conditional completion gate below;
the bounded implementation candidate has not earned merged maturity
**Current phase:** final implementation/integration candidate prepared for
delivery review
**Activation receipt:** PR #86 comment `5548725328` completed B-01H's entire
delivery predicate and selected B-05 `in_progress but NOT STARTED` from exact
main `f1a429de37290b3c7615ca051661a1d727528f78`, tree
`3e25bd65508c5c11d8d67558f9bd699808fc57a9`
**Owner interposition:** `OWNER-DX-02` inserts B-01H after B-04 completion and
before this ticket
**Prior selection evidence:** PR #75's completed receipt selected B-05
`in_progress but NOT STARTED`; no B-05 contract, decision, plan, evidence,
runtime, test, or implementation work began before the interposition
**Depends on:** B-02C, B-04, B-01H
**Build Out:** C5 Wave B authoring seam
**Master questions:** MQ-005, MQ-006, MQ-007, MQ-008
**Authority:** `Scoring.md`; `SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md` §4
C13-C14 and §§7-8; `Miner_MCP_Wave_B_Research_Contract.md` §8.2;
`Compute_Optimization.md`
**Owner-approved integration:** `Design_Specs/Science_GTM_Wave_Integration_Plan.md` §4; `docs/context/SCIENCE_GTM_OWNER_DECISION_RECORD_2026-08-27.md`

PR #75 comment `5513643185` proves B-04's completed predicate and historical
selection of this ticket. `OWNER-DX-02` subsequently interposes B-01H while
preserving this ticket's Definition of Done unchanged. B-05 starts only after
B-01H's complete delivery predicate and exact pilot base are recorded. This
sequencing supplies no B-05 contract or runtime implementation and no human-
reserved measurement, uncertainty, scoring, reconstruction-evidence, or
qualification value.

PR #86 comment `5548725328` later satisfies that complete B-01H predicate:
reviewed head `a4e2e5645b565330273d0d0d0d6e28d797cc8261` normally merged as exact
activation base `f1a429de37290b3c7615ca051661a1d727528f78`, preserving reviewed
tree `3e25bd65508c5c11d8d67558f9bd699808fc57a9`, with required exact-head
gates, complete-diff review, distinct approval, and zero unresolved
findings/threads. Its exact-main run was canceled by owner direction after
exact-head delivery passed. Its `NEXT_SELECTED_TICKET` is B-05 `in_progress
but NOT STARTED`. The working contract, decisions, plan/evidence, and first
bounded slice begin only after that receipt; the historical conditional text
above is not rewritten into pre-receipt authority.

## Goal

Make measurements and their evidence-use roles explicit before A5 executes any production-shaped scoring policy.

## Definition of Done

- [ ] Begin the single-ticket PR with the working
      `Design_Specs/Measurement_and_ScorePack_Authoring_Contract.md`, material
      decisions, plan, and SciML/statistics/protocol notification; implement
      coherent vertical slices against that contract; then review the final
      contract, implementation, tests, and stable evidence together. Require
      applicable validation and exact-head `Merge gate`; obtain fresh read-
      only Codex/GPT review of the complete diff; repair or disposition every
      finding; require distinct non-author human approval carrying the closed
      receipt, successful `GPT review gate`, and zero unresolved review
      threads; and normally merge the exact reviewed tree. Any tree change
      requires rereview, and a separate contract PR
      requires an exception in `.agent/DELIVERY_PROTOCOL.md`. Notification is
      not ratification and silence is no gate. Real measurement, uncertainty,
      score-policy values, and scientific qualification remain human-owned and
      fail closed.
- [ ] Define exact `MeasurementContract` identity, scientific property claimed,
      required observables, coordinates/units, numerical operator,
      discretization, sampling/quadrature, normalization, aggregation,
      precision, reference and numerical floor, applicability, uncertainty,
      stratum/subpopulation applicability, known limitations, implementation
      refs, and intended mandatory/soft/diagnostic role.
- [ ] Bind measurement-qualification evidence by role, including analytic or
      manufactured verification, refinement/convergence, independent witness,
      limiting-case/invariance, and experimental or industrial validation where
      applicable. The evidence record must state what each source supports and
      what it cannot support.
- [ ] Prevent MMS or another implementation-verification result from satisfying
      customer-workload applicability, physical model validation, or an
      engineering context-of-use claim without separate evidence.
- [ ] Bind measurement outputs to Score Pack eligibility, admissibility, estimand, stratum, uncertainty, aggregation, ranking, and disclosure roles.
- [ ] Define the Score Pack `UncertaintyPolicy` bindings for independence and
      resampling units, common-case pairing, reconstruction-by-case and
      reconstruction-by-stratum interaction, joint reference uncertainty,
      representation/execution dependence, censoring, minimum evidence, and
      prospective stopping or evidence-extension rules. Bind a Dossier-
      qualified applicability test that the exact incumbent-challenger
      evidence must satisfy before any quadrature or zero-covariance shortcut.
- [ ] Own and bind the exact scientific `ReconstructionEvidencePolicy`,
      including Challenge/family-specific complete-base minimums of one or more
      builds, frozen-artifact reuse, nomination and promotion stages,
      coverage-qualified scientific stopping/extension, typed
      `EVIDENCE_DEFERRED`, heuristic-futility separation, stability-audit rate,
      and fail-closed outcome. Consume B-02C resource facts without giving its
      forecasts or receipts scientific authority. B-E1 owns the fixture
      coverage and false-elimination harness, not policy authorship.
- [ ] Preserve mandatory admissibility before soft aggregation.
- [ ] Reject partial, non-finite, inapplicable, reference-failed, numerical-
      floor-unresolved, and uncertainty-unresolved measurement material through
      typed paths.
- [ ] Keep A5 as deterministic engine and prevent it from inventing physical thresholds or weights.
- [ ] Add fixture authoring, hash/pin, role-confusion, MMS-verification-versus-
      validation, measurement-floor, stratum-applicability, forbidden-input,
      and fail-closed tests.

The first delivery-lifecycle item remains unchecked until its external
exact-head review, approval, normal merge, exact-main, and receipt facts exist.
No tracked file guesses those dynamic identities.

## Implemented bounded architecture

`carbon.measurement` now owns five canonical Challenge-bound authoring object
kinds, explicit unresolved scientific-value bindings, a closed evidence-role
claim matrix, dependence-aware uncertainty and reconstruction-evidence policy,
exact A5 Score Pack input-use bindings, and mandatory-first no-scalar failure
projection. A complete test-owned fixture graph composes every B-05 object,
exact canonical refs/digests/store round trips, B-02C deferral facts, and the
unchanged A5 pack-compatible scalar projection. It remains visibly synthetic,
fixture-origin, protected, non-LIVE, and scientifically unqualified.

No `ScoreInput`, scorer, resolved-plan consumer, reconstruction runner,
Dossier qualification issuer, coverage/power harness, official lifecycle,
frontier, network, treasury, settlement, weight, emission, product,
commercial, production, or LIVE implementation is present.

## Conditional completion and B-06 selection

Prepared B-05 `done` and B-06 `in_progress but NOT STARTED` become
authoritative only after one exact unchanged B-05 final head/tree passes every
scope-required check and `Merge gate`; fresh read-only Codex/GPT review covers
the complete diff with all findings closed; a distinct non-author human
approval carries the closed receipt; `GPT review gate` succeeds with zero
unresolved threads; normal expected-head merge preserves the reviewed tree;
fetched exact main passes `Merge gate`; and the completed normalized external
receipt is posted. Until that complete predicate passes, B-05 remains
`in_progress` and B-06 remains `todo` and unstarted.

## Human input

SciML/statistics/protocol owners approve real measurements, applicability,
gates, tolerances, transforms, strata, weights, reconstruction evidence stages,
and stopping/error control from Dossier evidence. SRE confirms exact B-02C
resource-field compatibility but does not make the scientific decision.

## Must not

Promote fixture thresholds, treat a diagnostic as a full PDE residual,
compensate a mandatory failure, assume covariance is zero without Dossier
evidence, combine uncertainty components mechanically, let MMS verification
stand in for physical validation or context of use, or allow
mock/prior/resource/product/commercial fields into score.
