# Ticket B-03 - Generator API and Burgers fixture

**Wave:** B candidate
**Status:** todo
**Depends on:** B-02A
**Build Out:** C3
**Master questions:** MQ-002, MQ-003
**Authority:** `Generator_Creation.md`, `Generator_Validation.md`, `Evidence_and_Envelope_Standards.md`

## Goal

Implement the generator interface and a mechanically fixture-only fixed-viscosity Burgers realization suitable for authoring and conformance tests.

## Definition of Done

- [ ] Before implementation, produce
      `Design_Specs/Generator_Runtime_Contract.md`, obtain independent
      SciML/statistics/protocol review and explicit human ratification, and
      merge that contract normally; record the exact contract commit in the
      implementation plan.
- [ ] Define deterministic generator request/result and typed generation/censoring failures over `CanonicalChallengeCase`.
- [ ] Bind exact distribution, SamplingPlan, generator, role, and fixture identities.
- [ ] Implement the Burgers fixture using explicit `HUMAN_INPUT` markers for unratified population/range values.
- [ ] Test determinism, role separation, distribution-support checks, degeneracy/collision detection, case equality, valid censoring, and no seed leakage.
- [ ] Preserve target population authority outside generator implementation.
- [ ] Make fixture output incapable of entering a LIVE qualification manifest.

## Human input

SciML/statistics owners provide the real population, proposal law, strata, exclusions, and conformance acceptance evidence.

## Must not

Use determinism as scientific validation, silently redefine the population, insert a production threshold, or treat the fixture generator as truth.
