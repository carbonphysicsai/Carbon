# Ticket B-02C - Research resource policy contract

**Wave:** B candidate
**Status:** in_progress
**Depends on:** B-02B, B-07R
**Build Out:** C9 construction and research resource-policy seam
**Master questions:** MQ-008, MQ-015, MQ-017, MQ-024
**Authority:** `Miner_MCP_Wave_B_Research_Contract.md` §§5, 7-8; `Compute_Optimization.md`; `JAX_Optimization.md`

**Current ticket:** selected after the exact B-02B implementation merge and
exact-main CI recorded in `.agent/evidence/wave_b/b-02b.md`.<br>
**Working contract:** `Design_Specs/Research_Resource_Policy_Contract.md`<br>
**Plan:** `.agent/plans/B-02C_resource_policy_contract.md`<br>
**Evidence:** `.agent/evidence/wave_b/b-02c.md`

## Goal

Define the immutable resource contract that manifest discovery, practice
execution, resource inspection, and forecasting all reference, without
inventing calibrated forecasts, prices, or production rails.

## Definition of Done

- [ ] Before implementation, produce
      `Design_Specs/Research_Resource_Policy_Contract.md`; record material
      engineering decisions; deliver applicable protocol, SRE, security,
      operations, and economics lead/domain notifications; pass applicable
      validation and exact-head CI; obtain exact-head Greptile correctness
      review; repair every valid finding with zero unresolved Greptile threads;
      normally merge the exact reviewed tree; require exact-main CI; and record
      the contract merge commit in the implementation plan. A documented
      invalid finding may be closed with rationale, and every tree change
      requires rereview. No affirmative human/domain response or silence gate
      applies to agent-authorized engineering choices.
- [ ] Define exact `ResearchResourcePolicy`, `ResearchResourcePolicyRef`,
      `ResourceClass`, `ResourceClassRef`, static construction dimensions,
      declared ceilings, enforcement points, kill semantics, and observed
      resource-receipt fields.
- [ ] Consume the immutable policy-agnostic static requirements and impact tags
      emitted in `ResolvedConstructionPlan`; determine policy support,
      admissibility, and enforcement without changing the plan hash or compiler
      semantics.
- [ ] Keep exact static constraints, calibrated forecasts, future binding
      execution quotes, and observed receipts nominally and epistemically
      separate.
- [ ] Bind policy meaning to exact Challenge, assembly, compiler, environment,
      hardware/resource class, and practice/official-shaped authority where
      applicable.
- [ ] Define typed unsupported, over-limit, policy-stale, enforcement,
      infrastructure, and cancellation outcomes without turning them into
      candidate physics evidence.
- [ ] Define receipt seams required by a later
      `ReconstructionEvidencePolicy`: complete-build identity, frozen-artifact
      reuse window, reconstruction replicate identity, observed cost/latency,
      evidence-stage label, and stop cause. These fields record resource facts
      only; they do not authorize scientific screening, ranking, or promotion.
- [ ] Define fail-closed, non-scientific seams for validator capacity,
      reconstruction funding, queueing, and evidence-budget availability.
      Missing operational commitments leave work `EVIDENCE_DEFERRED`; they do
      not lower the registered scientific evidence requirement or create a
      price, quota, score, or candidate-quality inference.
- [ ] Provide a bounded fixture policy with explicit non-production provenance;
      missing real rails leave production execution unavailable.
- [ ] Add canonicalization, stale/cross-Challenge ref, hostile-limit,
      enforcement, receipt, forecast/quote-confusion, authority, and
      installed-wheel tests.

## Human input and fail-closed boundary

SRE, protocol, security, operations, and economics owners supply or approve
real hardware classes, ceilings, enforcement rails, calibrated-forecast
eligibility, validator capacity, reconstruction funding, queueing,
evidence-budget availability, binding execution-quote/price semantics, quotas,
security acceptance, and future operational rails. Missing values stop only
the affected real behavior and leave it unavailable or `EVIDENCE_DEFERRED`;
bounded fixtures and typed fail-closed seams may proceed. Fixture values remain
structurally non-authoritative.

## Must not

Predict official quality, reveal protected evaluator topology or case volume,
invent a price or quota, let payment change scientific evidence, interpret a
forecast as authorization to execute, or let a partial build or resource screen
create scientific superiority.
