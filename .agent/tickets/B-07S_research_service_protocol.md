# Ticket B-07S - Exact miner research service protocol

**Wave:** B candidate
**Status:** todo
**Depends on:** B-07R, B-02A, B-02B, B-02C
**Build Out:** C9-C11 exact Wave B service gate
**Master questions:** MQ-015, MQ-016, MQ-017, MQ-018, MQ-024, MQ-025, MQ-026, MQ-045
**Authority:** `Miner_MCP_Wave_B_Research_Contract.md` §§4-11

## Goal

Ratify the exact bounded wire and lifecycle contract for the local Wave B
research service after B-07R is authoritatively completed under its review/
merge/CI gate and before any service-facing implementation begins.

## Definition of Done

- [ ] Produce and ratify one normative `Design_Specs/Miner_MCP_Wave_B_Service_Protocol.md` that owns every wire-visible v2 operation, request/result/error/resource type, lifecycle, bound, canonical encoding, provider protocol, and safe projection.
- [ ] Freeze the exact underscore-style operation vocabulary: `get_challenge_info`, `get_interaction_manifest`, `get_prior`, `get_mock_scaffold`, `dry_validate`, `compile_strategy`, `inspect_prior_alignment`, `inspect_resources`, `forecast_resources`, `start_research_task`, `get_research_result`, and `cancel_research_task`.
- [ ] Keep official `submit` and `get_submission_result` exclusively on the unchanged Wave A v1 service with one store, lifecycle, error model, and authority path.
- [ ] Ratify two distinct local service identities/namespaces, `carbon_protocol_v1` and `carbon_research_v2`; duplicate operation names remain qualified and no merged unqualified alias exists.
- [ ] Define exact nominal request/result/resource/error types, canonical encoding and hashing, field and collection bounds, provider protocols, constructor dependencies, error precedence, and safe projections.
- [ ] Define the exact public `TrainingSupportContractRef` and
      `TrainingSamplingPolicyRef` wire bindings, with no field for raw/custom
      data, a path/URI, miner seed, or official `P`, `Q`, `w`, stress,
      reference, gate, or scorer control.
- [ ] Ratify the closed task-state machine, terminal states, idempotency identity/conflict behavior, cancellation cutoff/races, infrastructure retry ownership, terminal receipts, polling limits, and task-state versus scientific-outcome separation.
- [ ] Define `get_prior` exact versus active-channel lookup, atomic index snapshot, historical retrieval, and run-level exact-pack pinning; define one canonical genesis previous-index sentinel and require the proposed transition digest to exclude both the publication receipt and the resulting-index reference so the content-addressed graph cannot cycle.
- [ ] Reserve `quote_execution`, authenticated transport, real identity linkage, and production signing/key custody for later waves with explicit unavailable seams.
- [ ] Define local-only agent-adapter conformance without a network listener or credentials.
- [ ] Define nominal `ExternalPublicResearchContext` and
      `FixtureResearchContext` constructor/provider capabilities. Only the
      latter may inject `TestOnlyPriorProvider` and advertise
      `TEST_ONLY_FIXTURE_PRIOR`; callers cannot select or relabel context on the
      wire.
- [ ] Define the exact fixture result binding for a test-only authorization-
      receipt reference and the mandatory
      `TEST_ONLY / NOT_UTILITY_QUALIFIED` ceiling without treating that receipt
      as a public `PriorPublicationReceipt`.
- [ ] Define `PriorPack` canonical bytes without an embedded self-hash or
      `PriorPackRef`; define `PriorPackRef.content_hash` as SHA-256 of those
      canonical bytes, outside the hashed preimage, and reject reciprocal or
      self-referential identities.
- [ ] Ratify the operation-to-domain ownership matrix used by B-07G: B-07A
      implements the shared nominal wire primitives once and owns
      discovery/manifest data, B-07D3 prior retrieval/alignment, B-07C
      scaffold/practice execution, A2 validation semantics, B-02B compilation,
      B-07E resource analysis/forecasting, and B-07B task lifecycle/records.
      B-07G owns only service composition, dispatch, and conformance.
- [ ] Add an operation-by-operation authority, disclosure, failure, and resource test matrix.
- [ ] Record the material exact-protocol decisions and applicable domain-lead notifications; pass document validation and exact-head CI; repair every valid Greptile finding with zero Greptile threads unresolved; and normally merge the exact reviewed tree before B-07A, B-07B, B-07C, B-07D1, B-07D2, B-07D3, B-07E, B-07F, or B-07G implementation. A documented invalid finding may be closed with rationale, and any tree change requires rereview. Notification is not approval and silence is no gate. Human-reserved scientific values, security acceptance, rights/legal policy, economics, qualification, LIVE, launch, and production authority remains unavailable.

## Must not

Implement code, duplicate the official lifecycle, accept a generic execution mode, invent security/economic values, imply a forecast is a quote, or claim architecture prose is a wire contract.

## Maturity ceiling

This ticket can make the exact Wave B research protocol `SPECIFIED / RATIFIED`. Implementation and every qualification state remain `NO`.
