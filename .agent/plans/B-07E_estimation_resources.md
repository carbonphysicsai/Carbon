# B-07E implementation plan — resource inspection and forecast seam

**Starting main:** `258a35d91f45a1125879123bddccc52428d003b2`
**Ticket:** `.agent/tickets/B-07E_estimation_resources.md`
**Decision:** `B-07E-D1`
**Delivery:** one branch and pull request under OWNER-DX-03

## Ordered implementation

1. Reuse B-02B compilation and B-02C static assessment; project exact public
   plan requirements through the existing B-07A/B-07S inspection types.
2. Add an ordinary forecast provider that cannot accept calibration and fails
   closed to `UNRESOLVED` while human-owned calibration authority is absent.
3. Add a structurally separate TEST_ONLY synthetic provider to verify explicit
   model, calibration, scope, uncertainty, stale, mismatch, and invalid-output
   behavior without creating production calibration authority.
4. Verify disclosure, scoring, receipt, quote, lifecycle, installed-wheel, A9,
   B-07D3, and B-02B/B-02C ownership boundaries.
5. Reconcile stable evidence, current status, Wave/Hub state, then run the one
   applicable ready-head acceptance and normal expected-head merge.

## Reuse classification

- **KEEP:** A9 `estimate`, B-07D3 alignment, B-07B terminal observed-resource
  receipts, B-07A wire types, B-02B compiler, and B-02C policy assessment.
- **WRAP:** exact B-02B/B-02C results behind the B-07A inspection provider
  interface.
- **REPAIR:** none required in the reused owners.
- **REPLACE:** none.

## Explicit boundary

This plan adds no quote, admission, capacity, price, quota, reservation,
settlement, scoring, qualification, production calibration, B-07G dispatcher,
or LIVE path. Real model data and support criteria remain human-reserved and
the ordinary forecast stays fail closed.
