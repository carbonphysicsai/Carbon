# Ticket B-07F - Resolved-plan fixture-official construction adapter

**Wave:** B candidate
**Status:** todo
**Depends on:** B-02B, B-02C, B-03, B-04, B-05, B-07S, A7, A8, A9
**Build Out:** C2/C9/C11 fixture integration seam
**Master questions:** MQ-004, MQ-005, MQ-008, MQ-015, MQ-024
**Authority:** `Miner_MCP_Wave_B_Research_Contract.md` §§5-8; current A7/A8/A9 contracts

## Goal

Provide the missing semantically responsive fixture-official consumer of a
canonical `ResolvedConstructionPlan`, behind the unchanged Wave A submission
and result surface, so B-E4 and B-GATE do not invent integration during
closeout.

## Definition of Done

- [ ] Begin the single-ticket PR with the working
      `Design_Specs/Resolved_Plan_Fixture_Construction_Adapter_Contract.md`,
      material decisions, plan, and protocol/SciML/security notification;
      implement coherent vertical slices against that contract; then review
      the final contract, implementation, tests, and stable evidence together.
      Require applicable validation, exact-head `Merge gate` and Greptile,
      repair every valid finding with zero Greptile threads unresolved, and
      normally merge the exact reviewed tree. A documented invalid finding may
      be closed with rationale, any tree change requires rereview, and a
      separate contract PR requires an exception in
      `.agent/DELIVERY_PROTOCOL.md`. Notification is not ratification and
      silence is no gate. Scientific/security qualification, official data
      rights, `LIVE`, and production authority remain human-owned and fail
      closed.
- [ ] Implement a new fixture-only resolved-plan consumer rather than changing
      A8's frozen Strategy-insensitive stub semantics.
- [ ] Inject the consumer behind the existing A7/A8-shaped internal
      TrainEval/provider seam while preserving the exact Wave A v1 wire,
      submission store, lifecycle, error precedence, and result authority.
- [ ] Compile the submitted Strategy under the same exact catalog, assembly,
      compiler, training-support, `R_strategy`, and environment identities used
      by nominal practice; then bind and evaluate the resulting plan against
      the same exact resource-policy identity used by practice.
- [ ] Make at least one registered fixture lever measurably affect construction
      and held-out toy-physics behavior; a Strategy-insensitive path may remain
      only as an explicit plumbing fixture.
- [ ] Use only `FixtureOfficialEntropy` and fixture reference/measurement packs;
      reject mock, provider-origin official, LIVE, production, or cross-context
      rights.
- [ ] Return typed compilation, construction, resource, reference,
      measurement, and infrastructure outcomes without converting failures
      across authority classes.
- [ ] Produce exact reconstruction and result receipts sufficient for B-E4 and
      B-GATE parity checks, with no official scientific, leaderboard, frontier,
      network, or settlement authority.
- [ ] Add v1-compatibility, store/lifecycle uniqueness, plan-consumption,
      ignored-lever, practice-parity, entropy/context confusion, failure,
      leakage, resource, and installed-wheel tests.

## Human input

Protocol, SciML, and security owners approve the adapter boundary and the
semantically responsive toy fixture. Fixture behavior remains
non-authoritative.

## Must not

Mutate the Wave A v1 wire contract, reinterpret A8's existing stub, create a
second official store or lifecycle, accept arbitrary participant code, consume
provider-origin official material, or claim real reconstruction or scientific
qualification.
