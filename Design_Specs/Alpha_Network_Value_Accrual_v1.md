# Carbon Alpha / Network Value Accrual Architecture v1

**Status:** OWNER-RECOMMENDED research architecture for economic/legal review; not a token-price promise or production policy.  
**Purpose:** define how genuine commercial use of Carbon can increase economic utility of the Carbon subnet and its Alpha token without allowing token economics to control scientific truth.

---

# 1. Core distinction

Carbon operates two related but distinct economic systems:

```text
CARBON COMMERCIAL ECONOMY
customer contracts / subscriptions / licenses / services

CARBON NETWORK ECONOMY
Alpha emissions / staking / sponsor rewards / miner and validator work / scientific treasury
```

> **Commercial revenue creates Alpha value only through explicit, useful economic bridges. Revenue and token value are not synonyms.**

---

# 2. Current Bittensor context

Current Bittensor architecture gives each subnet its own Alpha token and TAO/Alpha pool. Alpha is emitted to subnet participants and can be acquired by staking TAO into that subnet's pool. Subnet emission allocation is influenced by demand/price mechanics at the network layer.

This supports a general business conclusion:

> **The most defensible route to Alpha relevance is to make the subnet perform work people genuinely want to fund and participate in.**

Carbon should not rely on artificial financial engineering as a substitute for network utility.

All chain details remain subject to current Bittensor runtime/docs and future upgrades.

---

# 3. Value-accrual ladder

## L0 — Issuance-only network

Alpha exists because the chain emits it.

No meaningful external customer demand reaches the subnet.

**Commercial alignment: weak.**

## L1 — Useful work demand

Commercial Challenges/evidence jobs create real demand for miners and validators to perform useful work.

**Alignment: foundational.**

## L2 — Externally funded network reward

Sponsors fund additional scientific rewards tied to registered events.

**Alignment: strong.**

## L3 — Network-native service utility

Certain protocol-native services consume or require Alpha/Alpha-backed credits, collateral, or deposits without affecting scientific merit.

**Alignment: potentially strong.**

## L4 — Marketplace / ecosystem utility

Alpha participates in a broader market for Challenge sponsorship, scientific work, qualified methods/models, or network-native evidence services.

**Alignment: potentially compounding.**

## L5 — Financial distribution mechanisms

Buyback/burn/revenue-sharing/dividend-like policies.

**Alignment: legally/economically sensitive; not ratified here.**

---

# 4. Preferred value bridges

## AVB1 — Commercial work routed to the subnet

A growing share of eligible customer discovery/evidence work executes through Carbon's network once privacy/security/product maturity permit it.

Track:

```text
commercial_network_jobs
externally_funded_evaluation_value
participant_compute/work
scientific outcomes
```

This is the primary bridge.

## AVB2 — Sponsored Frontier Rewards

Customer pays a conventional invoice/deposit; a defined reward budget is allocated to a registered scientific event such as `FrontierAdvanceEvent`.

Possible settlement forms after review:

```text
fiat-funded / fiat-settled
fiat-funded / Alpha-settled
Alpha-funded / Alpha-settled
hybrid
```

The science is invariant across payment rails.

A fiat-to-Alpha conversion gateway is commercially preferable to forcing enterprise procurement teams to interact directly with crypto infrastructure.

## AVB3 — Network evaluation credits

A future protocol service may price network-native evaluation/search capacity using Alpha-denominated or Alpha-backed credits.

Customer-facing UX may remain fiat.

Examples:
- sponsor Challenge activation;
- network evaluation batches;
- bounty escrow;
- protocol-native Challenge deposits.

Paying for additional authorized evidence buys more work, not a different scientific standard.

## AVB4 — Role collateral / deposits

Alpha may have collateral/commitment roles where Bittensor and Carbon economics justify them.

Potential research examples:
- sponsor commitment deposit;
- Challenge-author anti-spam bond;
- evaluator/operator collateral;
- network API abuse deposit.

Stop-ship: stake/collateral cannot grant authority to define scientific truth or bypass evidence.

## AVB5 — Alpha-denominated marketplace assets

Later ecosystem possibilities:
- scientific bounties;
- method/model licenses;
- reproducibility rewards;
- information-value experiments;
- ecosystem service fees.

Each requires independent rights, pricing, custody, and legal design.

---

# 5. Fiat-first / network-native dual rail

Recommended principle:

> **Do not make customers become crypto operators in order to buy Carbon.**

Preferred UX:

```text
CUSTOMER
USD / conventional contract
        ↓
Carbon commercial payment layer
        ↓
service revenue + pass-through budgets
        ↓ where policy requires
network gateway / treasury
        ↓
Alpha/network settlement
```

This preserves enterprise sales while enabling commercial activity to fund network demand.

The gateway must publish/account for:
- amount customer funded;
- Carbon service revenue;
- compute pass-through;
- sponsor reward budget;
- conversion cost/slippage;
- Alpha acquired/used if applicable;
- participant payout;
- unused/reverted funds.

---

# 6. Scientific firewall

The following are forbidden scientific inputs:

```text
Alpha price
customer contract size
sponsor bounty size
miner stake size, unless a separate non-scientific consensus rule requires it
commercial revenue
customer importance
```

They may influence:
- whether a program is funded;
- how much authorized evidence is purchased;
- participant reward size;
- capacity/congestion decisions;
- business priority outside the live exam.

They may not change what counts as scientifically correct after the scientific contract is frozen.

---

# 7. Token/network value metrics

Do not evaluate network success solely using spot Alpha price.

Preferred metrics:

## Utility
- number/value of externally funded network jobs;
- sponsor-funded scientific reward;
- serious participating miners/agents;
- validator work generated by customer demand;
- paid network evaluations;
- repeat sponsor activity.

## Scientific productivity
- verified frontier advances;
- authoritative experiments;
- cost per useful advance;
- downstream qualification success.

## Economic sustainability
- customer revenue supporting network work;
- network rewards versus delivered value;
- treasury runway/cost;
- reward concentration;
- participant retention.

## Alpha market health (observational, not product KPI)
- liquidity;
- slippage for required settlement sizes;
- stake participation;
- concentration;
- volatility;
- moving price/emission effects under current Bittensor mechanics.

---

# 8. Commercial activity conversion ratio

Introduce an internal metric:

```text
NetworkUtilityConversion
=
commercial value associated with useful network-executed work
/
total eligible commercial value
```

This is not a scientific metric and not a token valuation metric.

Purpose: detect the failure mode where the operating company prospers while the subnet is not materially used.

A low value may be legitimate during early private/offline product development. The roadmap should increase it as confidential/network infrastructure matures.

---

# 9. Sponsor reward accounting

Sponsored rewards should use a separate ledger from:
- base Alpha emissions;
- Carbon OpCo revenue;
- product qualification fees;
- customer pass-through compute;
- general treasury capital.

Conceptually:

```text
SponsorRewardLedger {
  engagement_id
  sponsor_id
  scientific_event_ref
  committed_budget
  asset/funding_rail
  conversion_policy
  custody_ref
  payable_state
  paid_amount
  refund/reversion_state
}
```

One reward may not be represented simultaneously as both Carbon revenue and participant pass-through when measuring economics.

---

# 10. Treasury inventory policy

If the treasury accumulates Alpha from emissions or sponsored conversions, holding inventory is not itself proof of value creation.

A production treasury policy must define:
- operational reserve;
- participant reward reserve;
- custody limits;
- concentration limits;
- liquidity/slippage considerations;
- conversion authority;
- accounting/valuation;
- incident procedures;
- prohibited self-dealing/manipulation;
- governance approvals.

This is economic governance, not scientific governance.

---

# 11. Rejected shortcuts

## "All customer invoices must be paid in Alpha"

Rejected as default because it adds procurement, volatility, accounting, and UX friction without improving the scientific product.

## "Company revenue automatically makes Alpha valuable"

Rejected. No causal bridge exists without network demand/utility.

## "Use Alpha price as the scientific success metric"

Rejected. Market price does not establish physical truth.

## "Give token holders scientific governance over gates"

Rejected. Economic stake cannot vote physical law into existence.

## "Promise buybacks/revenue share now"

Rejected from this architecture stage. Requires dedicated legal/economic analysis.

---

# 12. Dedicated future gauntlets

Before ratifying Alpha-specific commercial mechanics, run:

1. **Sponsor Reward Gateway Gauntlet** — fiat → custody → Alpha sourcing → payout → refund, including liquidity/slippage.
2. **Alpha Utility Gauntlet** — what network-native services, credits, deposits, or collateral genuinely improve the system.
3. **Treasury Market-Operations Gauntlet** — inventory, swaps, limits, conflicts, manipulation, accounting.
4. **Legal/Regulatory Review** — especially any buyback, revenue-sharing, financial return, or investment-linked claims.
5. **Unit-Economics Gauntlet** — ensure externally funded network work is sustainable.

---

# 13. v1 laws

1. **Commercial revenue and Alpha value are distinct until an explicit useful bridge connects them.**
2. **Useful network work is the preferred source of Alpha relevance.**
3. **Enterprise customers may remain fiat-native.**
4. **Sponsored rewards must not alter scientific success criteria.**
5. **Alpha/stake/price never defines physical truth.**
6. **Company and network accounting remain separate and reconcilable.**
7. **Pass-through participant rewards are not automatically operating-company revenue.**
8. **Treasury Alpha inventory is not itself evidence of commercial demand.**
9. **Network utility should rise as privacy/security infrastructure allows more commercial work to execute through the subnet.**
10. **Financial-engineering mechanisms require separate legal/economic ratification.**

---

# 14. Final statement

> **Carbon should create Alpha value by making the subnet economically necessary to valuable scientific work — funded Challenges, independent evaluation, frontier rewards, and eventually network-native evidence services — while keeping enterprise UX simple and scientific authority independent of token economics.**
