## 2026-10-12 — OWNER-GRAPHITE-OPEN-SAFE-01-GRANTS: USD 86.71 for the L5 hunt and USD 44.85 for the L2–L4 Constructor pass

**Authority.** The owner, 2026-10-12, typed directly in the PR Head session:

> Approve GRAPHITE-OPEN-SAFE-01 grants: L5 hunt USD 86.71, plus L2–L4
> Constructor pass USD 44.85.

**The grants.** Two caps, not one pooled budget:
- **L5 hunt: USD 86.71** all in.
- **L2–L4 Constructor pass: USD 44.85** all in.
- **Together: USD 131.56.** Each is a ceiling for its own run; neither may be
  spent on the other.

They fund the plan in `docs/development/graphite/GRAPHITE_OPEN_SAFE_01_PLAN.md`
(#1159): making the construction ladder open for miners and safe for Carbon,
and a round of Graphite hunting at Level 5.

**What the owner should know about the weekly cap.** `OWNER-TESTNET-WEEKLY-
BUDGET-01` sets USD 150 across any rolling seven days, pods plus model
charges, enforced on the host ledger by #1067. USD 131.56 is **88% of that
cap**. Once reserved, the ledger will refuse any further launch that would
pass 150 with `weekly_budget_reached`, so other runs in the same rolling week
may be blocked by these two — including the public-dev-decisions run
(`OWNER-PUBLIC-DEV-DECISIONS-GRANT-01`, raised to USD 16 the same day) and the
sealed confirmation run (`OWNER-SCORE-PROOF-CONFIRM-02-GRANT`, USD 25). Those
three together are USD 172.56, which exceeds the weekly cap. The ledger
decides which proceed by order of launch, not by importance, and refuses the
rest. That ordering is the operator's to choose deliberately, not the
ledger's to settle by accident.

This record does not raise the weekly cap. Raising it would be a separate
owner decision.

**No miner compute is rented, stopped or billed by this.** The plan's many
references to miners are to the miner-facing surfaces — the miner door, the
signed parts, what a miner can legally build, and the refusal classification —
not to miner hardware. Carbon's own agents do the hunting on Carbon's own
compute, which is the standing rule: miners use any setup they like and Carbon
provides the wiring.

**Not authorized by this.**
- No overrun past either cap. An overrun needs its own owner acceptance, as
  the score-proof pod's did (`OWNER-SCORE-PROOF-RUNPOD-OVERRUN-01`).
- No third run, and no transfer between the two caps.
- Nothing scientific. A hunt result is not a qualification, a frontier event,
  or a product claim.

**Spend figures.** Actual hours and charges go in the operator's private
ledger. The public repository holds caps and rates, never spend totals.

**Maturity.** DEVELOPMENT spending authority only.
