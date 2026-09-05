# Ticket B-05 - MeasurementContract and Score Pack authoring bindings

**Wave:** B active in bounded development scope
**Status:** `todo`; no B-05 contract, decision, plan, evidence, runtime, test,
or implementation has started
**Conditional handoff:** first-pilot `in_progress` selection occurs only in the
completed B-01H external receipt after its entire delivery predicate passes
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
