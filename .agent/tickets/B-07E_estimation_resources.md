# Ticket B-07E - Prior alignment and resource-estimation seams

**Wave:** B candidate
**Status:** todo
**Depends on:** B-02B, B-02C, B-07A, B-07B, B-07C, B-07D3, B-07S
**Build Out:** C9 research estimation
**Master questions:** MQ-008, MQ-017, MQ-024
**Authority:** `Miner_MCP_Wave_B_Research_Contract.md` §§7-8; current `Miner_MCP.md` §7

## Goal

Separate public prior matching, exact static resource analysis, calibrated forecasts, binding quotes, and observed receipts so the interface never implies unsupported performance prediction.

## Definition of Done

- [ ] Preserve current A9 `estimate` exactly as v1 structural-prior alignment.
- [ ] Consume v2 `inspect_prior_alignment` from B-07D3 as deterministic public pack/catalog matching with no private provider input.
- [ ] Consume B-07A's B-07S-ratified `inspect_resources` response type without
      redefining it; implement exact plan-derived dimensions and declared
      resource constraints.
- [ ] Consume B-07A's B-07S-ratified `forecast_resources` response type without
      redefining it; implement model identity, calibration window,
      hardware/resource scope, uncertainty interval, support state, and
      `UNRESOLVED` fallback. Without approved fixture calibration it always
      returns `UNRESOLVED`.
- [ ] Define the boundary to future Wave C `quote_execution` and the final observed resource receipt without implementing production prices.
- [ ] Ensure no resource response reveals protected case count, stress composition, strong-anchor frequency, evaluator topology, or official quality prediction.
- [ ] Add unsupported-distribution, stale-model, miscalibration, exact/static-vs-forecast, quote-confusion, leakage, forbidden-score, and installed-wheel tests.

## Human input

SRE/statistics owners provide calibration data and support criteria; operations/economics provide future quote and quota values. No model values are invented in this ticket.

## Must not

Return official score/rank/gate/winner probability, silently turn a forecast into a quote, or let any estimate enter A5 or settlement.
