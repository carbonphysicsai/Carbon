# Ticket B-07G - Research service integration and conformance

**Wave:** B candidate
**Status:** todo
**Depends on:** B-02B, B-07A, B-07B, B-07C, B-07D3, B-07E, B-07S, A9
**Build Out:** C9-C11 local research-service integration
**Master questions:** MQ-015, MQ-016, MQ-017, MQ-018, MQ-024, MQ-025, MQ-026, MQ-045
**Authority:** ratified `Miner_MCP_Wave_B_Service_Protocol.md`; `Miner_MCP_Wave_B_Research_Contract.md` §§6-11

## Goal

Implement the exact B-07S-ratified in-process research service by composing the
domain implementations owned by its dependencies, while leaving the separate
exact Wave-A official service unchanged. Exact service/version and operation
names come only from the merged B-07S protocol.

## Definition of Done

- [ ] Implement the exact service/version identity and closed operation set
      ratified by B-07S, without adding an alias or an unratified operation.
- [ ] Wire every operation by constructor dependency injection to its domain owner: B-07A owns Challenge discovery and manifests; B-07D3 owns prior retrieval and alignment; B-07C owns mock scaffold and practice execution; A2 remains the validation-semantics owner; B-02B owns compilation; B-07E owns resource inspection and forecasting; B-07B owns task lifecycle, records, and receipts. B-07G owns only service composition, dispatch, and conformance and does not duplicate those semantics, stores, or lifecycle state.
- [ ] Keep official submission and result capabilities absent from the research
      service. Agents and clients call the separately namespaced, unchanged
      Wave-A service; the research plane neither wraps nor delegates official
      operations and owns no official store.
- [ ] Enforce the ratified canonicalization, request/result bounds, nominal types, error precedence, safe projections, lifecycle/idempotency behavior, and resource accounting at the service boundary.
- [ ] Provide only the ratified local in-process/agent adapter. Open no listener, accept no credentials, charge no fees, and imply no remote or production service.
- [ ] Add a complete operation matrix covering owner/delegate, authority ceiling, disclosure class, resource class, errors, and prohibited cross-namespace behavior.
- [ ] Add conformance, namespace-collision, canonicalization, malformed/bounded
      input, idempotency, cancellation-race, concurrency, failure-isolation,
      resource-accounting, and installed-wheel tests for the complete
      B-07S-ratified operation set.
- [ ] Demonstrate that replacing a domain dependency with a conforming fixture changes only that domain behavior and that the service contains no duplicate compiler, provider, practice, forecasting, task, or record implementation.

## Must not

Change Strategy v1, alter the v1 tool vocabulary or official lifecycle, implement B-07F's fixture-official adapter, add network/authentication/signing/fee behavior, create scientific or economic authority, or repair a dependency's semantics inside the service layer.

## Maturity ceiling

This ticket may establish the local research service as `IMPLEMENTED / TESTED` against fixture contracts. Scientific, security, network, commercial, and production qualification remain `NO`.
