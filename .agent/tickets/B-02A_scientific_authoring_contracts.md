# Ticket B-02A - Scientific authoring and canonical-case contracts

**Wave:** B candidate
**Status:** todo
**Depends on:** B-01
**Build Out:** C3 and Wave B scientific contract objects
**Master questions:** MQ-001, MQ-002
**Authority:** `SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md` §§5-6; `Build_Out_Constitutional_Overlay.md` §8

## Goal

Implement versioned identities and fixture schemas for the physical job before a generator is allowed to define it by accident.

## Definition of Done

- [ ] Before implementation, produce
      `Design_Specs/Scientific_Challenge_Authoring_Contract.md`, obtain
      independent SciML/statistics/protocol review and explicit human
      ratification, and merge that contract normally; record the exact contract
      commit in the implementation plan.
- [ ] Define exact immutable references for `PhysicalSystemSpec`,
      `CandidateOutputContract`, `InstanceDistributionContract`,
      `SamplingPlan`, `TrainingSupportContract`, and
      `CanonicalChallengeCase`.
- [ ] Keep target population `P(x)`, official proposal/sampling `Q(x)`, evidence weighting `w(x)`, and Challenge-bounded training support semantically separate. Define the training support's membership, invariants, and data-rights semantics. Reserve `R_strategy` for the canonical `ResolvedTrainingSamplingPolicy` object and ref materialized by the later compiler; it cannot redefine `P`, `Q`, or `w`.
- [ ] Bind candidate causal inputs, outputs, representation, units, geometry/domain, time semantics, and claim scope without setting unapproved Burgers values as LIVE truth.
- [ ] Define valid-case, censored-case, excluded-case, and generation-failure states.
- [ ] Content-address every contract with explicit canonicalization/version identity.
- [ ] Add exact-type, malformed-input, hash/pin, equality, supersession, fixture-origin, and installed-wheel tests.
- [ ] Ensure no fixture identity can satisfy the LIVE qualification gate.

## Human input

SciML and statistics owners supply the first real target population, official envelope, strata, SamplingPlan, evidence weighting, and permitted training support. Missing values leave production authoring unavailable.

## Must not

Treat a generator as the population, merge `P`, `Q`, `w`, or `R_strategy`, let a training policy alter the official exam, expose protected case identity, or claim scientific qualification.
