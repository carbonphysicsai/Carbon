## 2026-10-09 — LEVEL4-LOSS-OVERRIDE-01: battery's development Level 4 variant v3 admits a loss graph

**Authority.** The Test Lead's decision of 2026-10-09, relayed to the Level 4
engineer session:

- It rests on the owner's wave-3 rule that a development-only variant may
  widen to a drafted surface (OWNER-GRAPHITE-DEV-LEVELS-01 F1).
- It also rests on the owner's direction that Level 4 is always pursued.

The Test Lead reviews development variants (OWNER-GRAPHITE-TEST-WAVE-03 §1).
Recorded by the Level 4 engineer session.

**Decided.**
1. **The declaration.** Battery's development-only Level 4 variant declares
   `loss_override: graph`. A submitted per-case loss graph may replace
   battery's loss, under the G6 loss slot v1
   (`docs/development/graphite/level4/PHASE1_PLAN.md` §4.5,
   `carbon/level4/loss.py`):
   - Carbon maps the graph over the batch and takes the mean;
   - G7's exam is unchanged;
   - a non-finite loss is the candidate's own training failure.
2. **A new version.** It is registered as `battery-l4-graph-v3`, with
   development record 0006. v1 and v2 stay pinned in the registry as history.

**Unchanged.**
- **Frozen and live rules.** Battery's frozen and live rules declare no
  override, and the miner-facing contract is untouched; a test pins that it
  carries no `loss_override`. Adopting the override into any frozen rule is
  the owner's decision.
- **Not served to miners.** Development variants never are.
- **Values.** The aux limit (`loss.AUX_LIMIT`) stays `HUMAN_INPUT`, so no
  auxiliary output is admitted yet.
- **Training on a submitted loss is not yet built.** G6's battery path with
  `per_case_mean`, and the loss graph's F4 count, are the next slice.
