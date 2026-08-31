# Ticket B-03 - Generator API and Burgers fixture

**Wave:** B candidate
**Status:** todo
**Depends on:** B-02A
**Build Out:** C3
**Master questions:** MQ-002, MQ-003
**Authority:** `Generator_Creation.md`, `Generator_Validation.md`, `Evidence_and_Envelope_Standards.md`
**Owner-approved integration:** `Design_Specs/Science_GTM_Wave_Integration_Plan.md` §4; `docs/context/SCIENCE_GTM_OWNER_DECISION_RECORD_2026-08-27.md`

## Goal

Implement the generator interface and a mechanically fixture-only fixed-viscosity Burgers realization suitable for authoring and conformance tests.

## Definition of Done

- [ ] Before implementation, produce
      `Design_Specs/Generator_Runtime_Contract.md`; record material engineering
      decisions and notify SciML/statistics/protocol owners; pass applicable
      document validation and exact-head CI; repair every valid Greptile
      finding with zero Greptile threads unresolved; and normally merge the
      exact reviewed tree. A documented invalid finding may be closed with
      rationale, and any tree change requires rereview. Record the exact
      contract commit in the implementation plan. Notification is not
      ratification and silence is no gate. Real population/range values and
      scientific qualification remain human-owned and fail closed.
- [ ] Define deterministic generator request/result and typed generation/censoring failures over `CanonicalChallengeCase`.
- [ ] Bind exact distribution, SamplingPlan, generator, role, and fixture identities.
- [ ] Implement the Burgers fixture using explicit `HUMAN_INPUT` markers for unratified population/range values.
- [ ] Expose fixture conformance evidence hooks for support/exclusion checks,
      realized strata and tail allocation, marginal/joint/conditional summaries,
      duplicate and near-duplicate detection, deterministic replay, rejection
      attempts, invalid-case rate, and censoring by cause and stratum.
- [ ] Preserve the intended sampled population and realized-valid-evidence
      population as separate outputs. A retry or rejection path must remain
      visible and cannot silently replace a difficult case with an easier one.
- [ ] Provide typed outcomes that distinguish valid generation, registered
      exclusion, generator nonconformance, invalid construction, censored case,
      and infrastructure failure without converting any of them into candidate
      evidence.
- [ ] Test determinism, role separation, distribution-support checks, degeneracy/collision detection, case equality, valid censoring, no seed leakage, intended-versus-realized population reporting, and no silent retry.
- [ ] Preserve target population authority outside generator implementation.
- [ ] Make fixture output incapable of entering a LIVE qualification manifest.

## Human input

SciML/statistics owners provide the real population, proposal law, strata,
exclusions, conformance estimands, acceptance evidence, and censoring policy.
No implementation agent supplies production conformance thresholds.

## Must not

Use determinism as scientific validation, silently redefine the population,
hide generator failure through retries, insert a production threshold, treat a
fixture generator as truth, or use reference agreement as proof of distribution
conformance.
