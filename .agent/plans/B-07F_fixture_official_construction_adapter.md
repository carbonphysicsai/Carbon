# B-07F implementation plan — resolved-plan fixture construction adapter

**Starting main:** `5dc41eef62025a0114ee11bb98db3f9b877b247d`
**Ticket:** `.agent/tickets/B-07F_fixture_official_construction_adapter.md`
**Decision:** `B-07F-D1`
**Delivery:** one branch and pull request under OWNER-DX-03
**Implementation state:** contract and implementation complete; acceptance and normal merge pending

## Ordered implementation

1. Establish the working adapter contract and notify protocol, SciML, and
   security owners of the reversible fixture-only decision.
2. Add a distinct nominal provider behind the existing A7 envelope/A8 outcome
   seam; compile exclusively through B-02B and assess exclusively through
   B-02C.
3. Consume the registered `fixture_sampling_level` from canonical R_strategy,
   construct the bounded toy model under FixtureOfficialEntropy, measure on a
   separate fixture reference asset, and score only through A5.
4. Add exact private reconstruction/result receipts and separate typed
   compilation, resource, construction, reference, measurement, and
   infrastructure outcomes.
5. Verify A7/A8/v1 compatibility, practice parity, adversarial authority and
   leakage boundaries, installed-wheel behavior, and relevant regressions.
6. Reconcile ticket/evidence/Wave/status/Hub, run the applicable acceptance,
   and normally merge the unchanged accepted head.

## Reuse classification

- **KEEP:** A7 store/lifecycle/result authority, A8 legacy stub, A5 scoring,
  B-02B compiler/plan/R_strategy, B-02C policy assessment, B-03/B-04/B-05 refs,
  and B-07C/B-07E providers.
- **WRAP:** exact existing values behind one private B-07F TrainEval provider.
- **REPAIR:** superseded ticket delivery wording and post-B-07E status lag only.
- **REPLACE:** none.

## Explicit boundary

The toy mechanism is deterministic fixture plumbing, not real training,
scientific evidence, production reconstruction, isolation, rights approval,
qualification, ranking, emission, frontier, network, settlement, or LIVE.
