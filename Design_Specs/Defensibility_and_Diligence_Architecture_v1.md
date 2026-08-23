# Carbon Defensibility and Diligence Architecture v1

**Status:** OWNER-RECOMMENDED diligence architecture.  
**Purpose:** define how Carbon converts claims into auditable, challengeable, evidence-backed positions across science, security, economics, business, governance, and public communication.

---

# 1. Principle

> **A defensible system does not need an affirmative answer to every question. It needs a truthful answer, the correct authority boundary, and a visible path from uncertainty to evidence.**

Carbon therefore treats diligence as an evidence architecture rather than a communications exercise.

---

# 2. DefensibilityCard

Every material claim should be representable as:

```text
DefensibilityCard {
  claim_id
  claim_text
  domain
  authority_owner
  mechanism_refs[]
  implementation_state
  qualification_state
  evidence_refs[]
  known_failure_modes[]
  falsification_tests[]
  maturity_state
  explicit_non_claims[]
  open_decisions[]
  required_next_proof[]
  last_reviewed_at
}
```

A claim without an authority owner or next-proof path is not diligence-ready.

---

# 3. Domains

```text
SCIENCE
STATISTICS
SECURITY
EXECUTION
PROTOCOL
VALIDATOR
MINER
BITTENSOR
TREASURY
GOVERNANCE
PRODUCT_QUALIFICATION
BUSINESS
GTM
FINANCE
NETWORK_ALPHA
PRIVACY_DATA
IP_RIGHTS
LEGAL_LIABILITY
REGULATORY
OPERATIONS
PUBLICATIONS
```

No single team owns all defensibility.

---

# 4. Evidence ladder

Scientific/technical:

```text
DESIGN
IMPLEMENTED
TESTED
SCIENTIFICALLY_QUALIFIED
SECURITY_QUALIFIED
NETWORK_QUALIFIED
PRODUCTION_QUALIFIED
```

Commercial:

```text
BUSINESS_DESIGN
CUSTOMER_DISCOVERY
PAID_PILOT
REPEATABLE_SERVICE
EXPANSION
RECURRING_REVENUE
PLATFORMIZATION
NETWORK_LEVERAGE
```

Legal/regulatory:

```text
ISSUE_IDENTIFIED
POLICY_DRAFTED
COUNSEL_REVIEWED
CONTRACTED
OPERATIONALLY_ENFORCED
AUDITED
```

Do not collapse ladders into a generic “validated” label.

---

# 5. Claim classes

## C1 — Constitutional claim

Example: `Admissibility precedes ranking.`

Defense requires canonical authority and no contradictory implementation path.

## C2 — Mechanism claim

Example: `A7 refunds bounded FAILED_INFRA cases.`

Defense requires implementation + tests.

## C3 — Scientific performance claim

Example: `This Challenge resolves a frontier advance of magnitude X.`

Defense requires qualified experiment evidence.

## C4 — Security claim

Example: `Miner code cannot access official exam secrets.`

Defense requires threat model, implementation, adversarial testing, and qualified deployment scope.

## C5 — Economic claim

Example: `Network discovery is cheaper than centralized search.`

Defense requires comparative measured data.

## C6 — Business claim

Example: `Evidence Audit has repeatable demand.`

Defense requires customer evidence, not architecture.

## C7 — Legal/regulatory claim

Example: `Carbon may license a winning method.`

Defense requires contractual rights/counsel, not technical design.

---

# 6. Mandatory external-diligence package

Before serious institutional diligence, Carbon should be able to produce controlled versions of:

1. Constitution and authority map.
2. Current implementation/maturity ledger.
3. First Challenge qualification package.
4. Score Pack / measurement rationale.
5. Security threat model and qualification status.
6. Reproducibility / validator-disagreement evidence.
7. Randomness/secrecy architecture.
8. Frontier and treasury mechanism specification.
9. Governance / approval authority map.
10. Product qualification/non-claim policy.
11. Commercial product/SOW/rights/privacy model.
12. Unit-economics and business maturity evidence.
13. Network-vs-centralized experiment plan/results.
14. Alpha value-accrual statement with explicit non-claims.
15. Publication claim audit.

Audience projections may differ; underlying authoritative evidence should remain traceable.

---

# 7. Stop-ship diligence failures

Do not make a strong external claim if:

- the authority owner is unclear;
- implementation contradicts canon;
- the claimed evidence was produced under incompatible versions;
- a scientific threshold lacks qualified provenance;
- a security assertion rests only on unit tests;
- a customer/revenue assertion rests only on planned pricing;
- an IP assertion assumes rights not granted;
- an Alpha assertion assumes OpCo revenue transfer not actually implemented;
- a regulatory statement implies certification/approval not received;
- a production claim is based on fixture/testnet evidence only;
- failure/falsification conditions cannot be stated.

---

# 8. Review cadence

Defensibility review should happen:

- before each LIVE Challenge;
- before testnet/mainnet economic changes;
- before first paid customer engagement of a new product class;
- before a new privacy/deployment topology;
- before material investor/publication updates;
- after security/scientific incidents;
- after material protocol version changes.

---

# 9. Diligence rule

> **Carbon should never answer a question at a stronger maturity level than the evidence supports.**

A clear `not yet established` with a registered proof path is a valid defensibility state.
