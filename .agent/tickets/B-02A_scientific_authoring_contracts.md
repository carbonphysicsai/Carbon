# Ticket B-02A - Scientific authoring and canonical-case contracts

**Wave:** B candidate
**Status:** todo
**Depends on:** B-01E
**Build Out:** C3 and Wave B scientific contract objects
**Master questions:** MQ-001, MQ-002
**Authority:** `SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md` §§5-6; `Build_Out_Constitutional_Overlay.md` §8; `.agent/DELEGATED_DECISION_PROTOCOL.md`
**Owner-approved integration:** `Design_Specs/Science_GTM_Wave_Integration_Plan.md` §4; `docs/context/SCIENCE_GTM_OWNER_DECISION_RECORD_2026-08-27.md`

## Goal

Implement versioned identities and fixture schemas for the physical job before a generator is allowed to define it by accident.

## Definition of Done

- [ ] Produce `Design_Specs/Scientific_Challenge_Authoring_Contract.md` before runtime implementation. Treat it as the ticket's working contract: record material agent-recommended decisions, notify the applicable lead inboxes, and continue implementation under `.agent/DELEGATED_DECISION_PROTOCOL.md` unless an explicit `BLOCKED` / `REQUEST_CHANGES` direction or a genuinely human-reserved value prevents correct bounded work. Independent SciML/statistics/protocol review must cover the final contract/implementation merge candidate before normal merge. No pre-implementation affirmative approval or silence gate applies to agent-authorized engineering decisions.
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

SciML and statistics owners supply the first real target population, official envelope, strata, SamplingPlan, evidence weighting, and permitted training support. Missing values leave production authoring unavailable, but they do not block unrelated schema, fixture, validation, canonicalization, or fail-closed implementation work.

Material engineering decisions made inside this ticket follow `.agent/DELEGATED_DECISION_PROTOCOL.md`: the agent records its recommended approach, implementation location, alternatives, downstream impact, and exact supersession path; issue #42 notifies `@harshaa765` for SciML / Technical Lead decisions; Harsh may use `DEFER_TO_OWNER <decision-id>: <question or recommendation>` to route the decision to owner issue #41.

## Must not

Treat a generator as the population, merge `P`, `Q`, `w`, or `R_strategy`, let a training policy alter the official exam, expose protected case identity, promote MMS or another verification population into customer-workload evidence, or claim scientific qualification.
