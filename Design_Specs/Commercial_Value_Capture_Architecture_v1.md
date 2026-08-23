# Carbon Commercial Value-Capture Architecture v1

**Status:** OWNER-RECOMMENDED v1 for founder/product/economic/legal/technical review.  
**Purpose:** define how Carbon monetizes its scientific infrastructure across services, software, usage, qualification, licensing, sponsored research, and network-native activity while preserving scientific independence.

---

# 1. Core business principle

> **One scientific infrastructure should support multiple products and multiple revenue events without turning commercial payment into scientific authority.**

Commercial value capture sits outside the judge:

```text
CUSTOMER NEED
      ↓
CommercialEngagementSpec
      ↓
scientific program
      ↓
scientific result / deliverable
      ↓
commercial acceptance / license / support / lifecycle
```

Payment terms do not alter the Challenge, measurements, admissibility, ranking, or qualification claims after those scientific contracts are frozen.

---

# 2. Product families

## CV1 — Evidence Audit

Customer brings an existing candidate.

Carbon sells:
- problem/exam authoring;
- truth integration;
- independent evaluation;
- failure/stratum evidence;
- diligence report;
- optional remediation program.

No miner competition is required.

## CV2 — Discovery Program

Customer brings a defined problem/truth path.

Carbon sells:
- Challenge authoring/qualification;
- competitive search;
- sponsored reward administration;
- evaluation;
- candidate selection;
- downstream qualification option.

## CV3 — Qualified Model Program

Customer wants a deployable bounded-use artifact/system.

Carbon sells:
- candidate development;
- Product Battery;
- Qualification Record;
- deployment package;
- support/lifecycle terms;
- optional license.

## CV4 — Model Lifecycle

Customer operates a qualified artifact/system.

Carbon sells:
- lifecycle registry;
- drift/change intake;
- requalification;
- envelope expansion;
- evidence updates;
- support/escalation.

## CV5 — Enterprise Evidence Platform

Customer internal teams use Carbon infrastructure repeatedly.

Carbon sells:
- private Challenge/evidence workspace;
- qualification registry;
- usage/evaluation capacity;
- truth adapters;
- audit/export APIs;
- VPC/on-prem deployment;
- support.

## CV6 — Frontier Market

Sponsors fund qualified scientific frontiers.

Carbon sells:
- Challenge authoring;
- marketplace/program operation;
- reward custody/settlement administration;
- scientific evaluation;
- downstream rights/delivery/qualification services.

## CV7 — Evidence/OEM Rail

External engineering platforms generate models; Carbon provides independent evidence/qualification infrastructure.

Commercial models:
- annual platform/API license;
- per-evaluation usage;
- OEM royalty;
- enterprise support.

## CV8 — Physics Intelligence

Later product family, only after prospective decision lift is demonstrated.

Possible outputs:
- method recommendations;
- transfer prediction;
- experiment allocation;
- failure-risk prediction;
- qualification-candidate prioritization.

---

# 3. Revenue rail taxonomy

Every commercial charge should be typed so bundled deals remain economically inspectable.

```text
AUTHORING_FEE
TRUTH_INTEGRATION_FEE
PROGRAM_PLATFORM_FEE
EVALUATION_USAGE_FEE
SPONSORED_REWARD_POOL
SPONSORED_REWARD_ADMIN_FEE
MODEL_DEVELOPMENT_FEE
QUALIFICATION_FEE
DEPLOYMENT_INTEGRATION_FEE
SOFTWARE_SUBSCRIPTION
ON_PREM_LICENSE
MODEL_LICENSE
METHOD_LICENSE
OEM_ROYALTY
SUPPORT_SLA_FEE
LIFECYCLE_SUBSCRIPTION
REQUALIFICATION_FEE
PHYSICS_INTELLIGENCE_FEE
```

A bundle may contain several rails, but internal accounting preserves each rail.

---

# 4. CommercialEconomicsRecord

Commercial economics are not scientific evidence.

Conceptual record:

```text
CommercialEconomicsRecord {
  engagement_id
  product_family
  revenue_rails[]
  contracted_value
  collected_value
  recurring_value
  direct_labor_cost
  truth_cost
  evaluation_compute_cost
  network_incentive_cost
  sponsor_reward_pass_through
  integration_cost
  support_cost
  gross_contribution
  network_activity_class
  evidence_reuse_class
  renewal_or_expansion_state
}
```

Rules:
- never enters Score Pack or qualification science;
- no customer pricing advantage can create scientific advantage;
- science/infra failure may have contractual refund/retry effects without altering evidence semantics.

---

# 5. Margin architecture

Carbon should intentionally migrate work from bespoke labor to reusable infrastructure.

```text
BESPOKE EXPERT WORK
Challenge authoring / first adapter / first truth integration
        ↓ reusable template
REPEATABLE SERVICES
standard engagement + qualified adapters
        ↓ productized workflows
SOFTWARE / USAGE
platform + APIs + automated evidence pipeline
        ↓ network liquidity / supply
MARKETPLACE
sponsored discovery + scalable external research supply
```

Metrics should track the share of each engagement executed through reusable components versus custom expert effort.

---

# 6. Land-and-expand architecture

Recommended customer expansion sequence:

```text
LAND
Independent Evidence Audit or feasibility/Challenge design
        ↓
EXPAND 1
Discovery / remediation / model development
        ↓
EXPAND 2
Qualification / deployment
        ↓
RECUR
Lifecycle / requalification / support
        ↓
PLATFORM
enterprise multi-program license / OEM
        ↓
COMPOUND
physics intelligence / experiment allocation
```

The customer does not have to traverse every stage.

---

# 7. Scientific-value / commercial-value separation

Examples:

```text
Scientific state: VALID_RANKED
Commercial state: invoice unpaid
```

These are independent.

```text
Scientific state: FRONTIER_ADVANCE_CONFIRMED
Commercial state: sponsor reward pending settlement
```

Still independent.

```text
Scientific state: PRODUCT_QUALIFIED
Commercial state: customer acceptance failed due deployment packaging
```

Qualification remains scientifically historical; packaging issue creates a commercial remediation state.

---

# 8. Network-activity classification

Each commercial activity receives one of:

```text
OFFCHAIN_ONLY
NETWORK_ELIGIBLE
NETWORK_REQUIRED
```

Purpose: preserve enterprise flexibility during early product maturity while creating a deliberate migration path toward useful subnet execution.

Default examples:

- sales/feasibility workshop: OFFCHAIN_ONLY;
- Challenge authoring: OFFCHAIN_ONLY / NETWORK metadata later;
- public sponsored Challenge: NETWORK_REQUIRED;
- private Challenge before confidential network topology is qualified: OFFCHAIN_ONLY;
- private Challenge after qualified topology: NETWORK_ELIGIBLE or NETWORK_REQUIRED by product version;
- Product Battery: separate product plane unless explicit registered market exists;
- information-value experiments: separate bounty mechanism.

---

# 9. Customer payment policy

Enterprise UX should permit conventional payment rails.

Supported commercial abstractions may include:

```text
FIAT_INVOICE
FIAT_PREPAID_CREDITS
USAGE_COMMIT
SPONSOR_REWARD_DEPOSIT
NETWORK_NATIVE_PAYMENT
```

The payment rail does not alter scientific service level except where a customer explicitly purchases more cases/replicates/compute under a prospectively defined engagement. More evidence is a different registered experiment, not a private easier grader.

---

# 10. Sponsored reward economics

A sponsored scientific reward should have two distinct economic components:

```text
Carbon service/platform revenue
+
sponsor-funded participant reward
```

Do not treat the participant reward pool as Carbon gross revenue when analyzing margin.

A sponsor-funded frontier payout should be bound to a prospective scientific event identity and may settle through the Carbon treasury/network once that path is qualified.

---

# 11. Rights as revenue architecture

Revenue depends on which rights Carbon retains.

Every engagement should explicitly address:

```text
CUSTOMER_DATA
CUSTOMER_SOLVER
CHALLENGE_SEMANTICS
MINER_STRATEGY
GENERALIZED_METHOD
RECONSTRUCTED_ARTIFACT
MODEL_WEIGHTS
EVIDENCE_METADATA
AGGREGATED_EVIDENCE
LANDSCAPE_DERIVATIVES
PUBLICATION
MODEL_LICENSE
METHOD_LICENSE
CROSS_CUSTOMER_REUSE
```

Commercial optimization must not assume Carbon owns reusable methods/evidence unless the rights policy actually grants that use.

---

# 12. Evidence reuse classes

Recommended rights-aware evidence classes:

```text
CUSTOMER_EXCLUSIVE
CUSTOMER_CONFIDENTIAL_AGGREGATABLE
ANONYMIZED_AGGREGATABLE
METHOD_LEVEL_REUSABLE
PUBLIC_RESEARCH
CARBON_INTERNAL_ONLY
NO_REUSE
```

The evidence flywheel should operate only over data permitted by contract and security policy.

---

# 13. Customer concentration and portfolio risk

Commercially optimal architecture should avoid dependence on one industry or one mega-customer.

Track revenue/evidence by:
- industry;
- engagement mode;
- truth-access mode;
- deployment topology;
- product family;
- recurring vs project;
- network-connected vs offchain-only.

Shared architecture should make aerospace, energy, manufacturing, mobility, electronics, materials, and other physics-intensive sectors possible without requiring the business to support all simultaneously.

---

# 14. Pricing governance

Pricing is commercial authority, not scientific authority.

A pricing policy may use:
- labor burden;
- expected truth/evaluation compute;
- scarcity/congestion;
- contract risk;
- rights/exclusivity;
- support SLA;
- deployment topology;
- economic value to customer.

It may not use customer willingness to pay to weaken evidence requirements for the same stated claim.

---

# 15. Product maturity states

```text
CONCEPT
DESIGN_SPECIFIED
INTERNAL_PILOT
PAID_PILOT
REPEATABLE_SERVICE
PRODUCTIZED
ENTERPRISE_QUALIFIED
SCALE_READY
```

Do not market a design-specified revenue rail as a live product.

---

# 16. Business stop-ships

Block or narrow a commercial offering if:
- gross contribution is structurally negative without a deliberate subsidized acquisition rationale;
- customer rights make promised deliverables impossible;
- security/privacy promises cannot be technically enforced;
- scientific claim requested exceeds evidence path;
- product bundles unlimited expensive truth/evaluation without pricing protection;
- Alpha/network integration materially damages customer UX with no compensating value;
- company and network accounting are indistinguishable;
- recurring product depends on manual bespoke work at every renewal;
- a license promises rights Carbon does not own.

---

# 17. Recommended initial commercial portfolio

## First sell

1. `Carbon Evidence Audit`
2. `Carbon Challenge Design / Feasibility`
3. `Carbon Sponsored Discovery Pilot`
4. customer-hosted truth integration as paid implementation

## Next attach

5. `Carbon Qualified Model Program`
6. `Carbon Model Lifecycle`
7. deployment integration / support

## Then scale

8. Enterprise Evidence Platform
9. Evidence API / OEM rail
10. Frontier Market
11. qualified model/method licenses where rights permit

## Later moat

12. Physics Intelligence
13. experiment allocation
14. evidence-bearing construction-method library

---

# 18. Final rule

> **Commercial optimization means maximizing the number of valuable things Carbon can sell from one coherent scientific infrastructure, while ensuring each revenue rail has an honest deliverable, an honest cost model, clear rights, and no authority to rewrite the science.**
