# Ticket B-07E - Prior alignment and resource-estimation seams

**Wave:** B candidate
**Status:** `done`
**Completed delivery:** PR #96 accepted head
`4fe739995db6d5e5c84fa02bff47d9e179e4dc56` after run `34087649083` and
normally merged it as `5dc41eef62025a0114ee11bb98db3f9b877b247d`
**Depends on:** B-02B, B-02C, B-07A, B-07B, B-07C, B-07D3, B-07S
**Build Out:** C9 research estimation
**Master questions:** MQ-008, MQ-017, MQ-024
**Authority:** `Miner_MCP_Wave_B_Research_Contract.md` §§7-8; current `Miner_MCP.md` §7

## Goal

Separate public prior matching, exact static resource analysis, calibrated forecasts, binding quotes, and observed receipts so the interface never implies unsupported performance prediction.

## Definition of Done

- [x] Preserve current A9 `estimate` exactly as v1 structural-prior alignment.
- [x] Consume B-07D3's B-07S-ratified deterministic public prior-alignment
      capability with no private provider input.
- [x] Consume B-07A's B-07S-ratified exact static-resource-inspection response
      type without redefining it; implement exact plan-derived dimensions and
      declared resource constraints.
- [x] Consume B-07A's B-07S-ratified calibrated-resource-forecast response type
      without redefining it; implement model identity, calibration window,
      hardware/resource scope, uncertainty interval, support state, and
      `UNRESOLVED` fallback. Without approved fixture calibration it always
      returns `UNRESOLVED`.
- [x] Define the boundary to the future Wave C binding-execution-quote
      capability and the final observed resource receipt without implementing
      production prices.
- [x] Ensure no resource response reveals protected case count, stress composition, strong-anchor frequency, evaluator topology, or official quality prediction.
- [x] Add unsupported-distribution, stale-model, miscalibration, exact/static-vs-forecast, quote-confusion, leakage, forbidden-score, and installed-wheel tests.

## Delivered bounded behavior

`carbon.research.resource_estimation` resolves static requests through the
existing B-02B compiler, delegates admissibility and declared ceilings to
B-02C, and projects exact plan-derived public resource facts through B-07A's
ratified result type. The ordinary forecast provider accepts no calibration
material and deterministically returns `UNRESOLVED` after static validation.
A nominally separate TEST_ONLY provider exercises explicit synthetic model,
calibration-window, distribution, policy, compiler, resource-class,
environment, horizon, uncertainty, stale, mismatch, and miscalibration
mechanics without creating a production calibration path.

Decision `B-07E-D1`, plan `.agent/plans/B-07E_estimation_resources.md`, stable
evidence `.agent/evidence/wave_b/b-07e.md`, and the focused CPU/invariant and
installed-wheel tests record the exact scope. B-07F subsequently became
eligible and is owned by its separate ticket. Scientific, security,
production-calibration, quote/admission,
economic, qualification, scoring, settlement, and LIVE authority remain
unearned.

## Human input

SRE/statistics owners provide calibration data and support criteria; operations/economics provide future quote and quota values. No model values are invented in this ticket.

## Must not

Return official score/rank/gate/winner probability, silently turn a forecast into a quote, or let any estimate enter A5 or settlement.
