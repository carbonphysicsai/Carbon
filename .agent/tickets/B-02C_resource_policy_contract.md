# Ticket B-02C - Research resource policy contract

**Wave:** B candidate
**Status:** todo
**Depends on:** B-02B, B-07R
**Build Out:** C9 construction and research resource-policy seam
**Master questions:** MQ-008, MQ-015, MQ-017, MQ-024
**Authority:** `Miner_MCP_Wave_B_Research_Contract.md` §§5, 7-8; `Compute_Optimization.md`; `JAX_Optimization.md`

## Goal

Define the immutable resource contract that manifest discovery, practice
execution, resource inspection, and forecasting all reference, without
inventing calibrated forecasts, prices, or production rails.

## Definition of Done

- [ ] Before implementation, produce
      `Design_Specs/Research_Resource_Policy_Contract.md`, obtain independent
      protocol/SRE/security review and explicit human ratification, and merge
      that contract normally; record the exact contract commit in the
      implementation plan.
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
- [ ] Provide a bounded fixture policy with explicit non-production provenance;
      missing real rails leave production execution unavailable.
- [ ] Add canonicalization, stale/cross-Challenge ref, hostile-limit,
      enforcement, receipt, forecast/quote-confusion, authority, and
      installed-wheel tests.

## Human input

SRE, protocol, and security owners approve real hardware classes, ceilings,
enforcement semantics, calibration eligibility, and future operational rails.
Fixture values remain non-authoritative.

## Must not

Predict official quality, reveal protected evaluator topology or case volume,
invent a price or quota, let payment change scientific evidence, or interpret
a forecast as authorization to execute.
