# EQUAL-BUDGET-REGISTRATION-01 — prospective development budgets

**Owner assignment:** 2026-10-10. **Base:** merged `origin/main`
`fb47eb5725338a7733f6074650e58271c355006b`. **Authority:** Test Lead
under the owner's 2026-10-10 value-bar delegation, as relayed in this task.
**Maturity ceiling:** registered DEVELOPMENT assumptions and tested accounting;
not a measured buyer budget, Challenge value PASS, solver adequacy or LIVE rule.

## Contract

Register one complete-decision budget per Challenge for battery v3, revised
motor 10p/12s, f02's adopted nine-action menu, and original offset f13. A
solver evaluation means one *complete mandatory condition panel* for one
candidate, including refinement; a battery map includes all five ambient bands,
a motor geometry includes all commands/angles/skew, and f13 includes the full
frequency curve. Count infeasible attempts and failed attempts too. Each arm
receives the same cap on complete-panel attempts, elapsed wall seconds and CPU
core-seconds. Charge acquisition, fitting, screening, optimizer overhead,
startup, retries, refinement and final verification under the same convention.
An arm stops before an unaffordable complete panel and cannot claim a value
from an incomplete panel.

The registered `half`, `base`, and `double` tiers are prospectively fixed in a
digest-bound development JSON file. Wall/core limits scale exactly 0.5/1/2;
integer solver evaluations use ceiling at the half tier. The `base` tier alone
governs VALUE-BAR-V1 item 5; the other two are reported sensitivity diagnostics.
Every tier is an `ASSUMPTION`, with source anchors and rationale. Published
method examples are not measurements of Carbon's buyer-job spend. Missing
current per-panel costs remain explicit; an observed panel can exhaust a
registered cap but cannot trigger retrospective enlargement.

## Work

- Reuse #1003 VALUE-BAR-V1 and #998 equal-budget replay. Add a common typed
  registry/cap that both existing and later adaptive policies must consume.
- Bind three replay curves and the item-5 evidence to the same registration
  digest; reject mismatched Challenge, tier, evaluation cap, time/compute cap,
  or a post-hoc extra budget.
- Present base PASS/FAIL/INSUFFICIENT_EVIDENCE and all three tier outcomes in
  the owner page. Unsettled references or incomplete pairs remain insufficient.
- Extend the neutral f13 toy contract, without adding acoustics or solver work.

Primary map ref `WAVE-C/EQUAL-BUDGET-REGISTRATION-01`. The Development Hub is
retired under `OWNER-WORKFLOW-SPEED-01`; no Hub output is regenerated.

## Acceptance and boundary

Toy fixtures only. Test prospective registry digest, half/base/double arithmetic,
equal caps for direct/model/ordinary-surrogate paths, attempt charging, budget
exhaustion, three-tier report, f13 identity, and VALUE-BAR-V1 base-versus-
sensitivity interpretation. No hidden/AX42 data, solver execution, spend or
LIVE change. One PR to main and exact-head handoff to PR Head after CI is green;
do not merge it here.
