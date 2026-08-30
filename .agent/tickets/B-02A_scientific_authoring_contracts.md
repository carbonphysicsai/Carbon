# Ticket B-02A - Scientific authoring and canonical-case contracts

**Wave:** B candidate
**Status:** in_progress (contract-ratification candidate; implementation not started)
**Depends on:** B-01E
**Build Out:** C3 and Wave B scientific contract objects
**Master questions:** MQ-001, MQ-002
**Authority:** `SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md` §§5-6; `Build_Out_Constitutional_Overlay.md` §8
**Owner-approved integration:** `Design_Specs/Science_GTM_Wave_Integration_Plan.md` §4; `docs/context/SCIENCE_GTM_OWNER_DECISION_RECORD_2026-08-27.md`
**Plan:** `.agent/plans/B-02A_scientific_authoring_contracts.md`
**Evidence:** `.agent/evidence/wave_b/b-02a.md`

> This status transition is proposed branch content until normally merged.
> Every Definition-of-Done checkbox below remains unchecked. The present phase
> may propose and review the authoring contract only; it may not implement the
> B-02A runtime objects or tests.

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
- [ ] Represent target/workload, official sampling/proposal, stress,
      practice, product-qualification, deployment, and realized-valid-evidence
      populations as distinct typed identities when applicable. No population
      role may be inferred from a shared support, generator, seed family, case
      representation, or PDE name.
- [ ] Bind query/observation population, evidence-campaign identity, and
      censoring provenance so a verification campaign cannot be relabeled as
      the target or deployment population.
- [ ] Represent manufactured-solution cases through a distinct verification
      population or evidence-campaign identity. An MMS identity may support
      implementation verification but cannot satisfy target-population,
      workload-prevalence, physical-validation, context-of-use, or product-
      qualification semantics.
- [ ] Bind candidate causal inputs, outputs, representation, units, geometry/domain, time semantics, and claim scope without setting unapproved Burgers values as LIVE truth.
- [ ] Define valid-case, censored-case, excluded-case, and generation-failure states.
- [ ] Ensure one canonical physical case can bind analytic, manufactured,
      numerical, experimental, industrial, and later hybrid reference evidence
      without transferring authority between those evidence roles.
- [ ] Content-address every contract with explicit canonicalization/version identity.
- [ ] Add exact-type, malformed-input, hash/pin, equality, supersession, fixture-origin, population-role-confusion, MMS-relabeling, and installed-wheel tests.
- [ ] Ensure no fixture identity can satisfy the LIVE qualification gate.

## Human input

SciML and statistics owners supply the first real target population, official envelope, strata, SamplingPlan, evidence weighting, and permitted training support. Missing values leave production authoring unavailable.

## Must not

Treat a generator as the population, merge `P`, `Q`, `w`, or `R_strategy`, let a training policy alter the official exam, expose protected case identity, promote MMS or another verification population into customer-workload evidence, or claim scientific qualification.
