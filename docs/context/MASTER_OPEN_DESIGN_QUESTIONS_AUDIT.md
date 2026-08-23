# Master Open Design Questions — Coverage Audit

**Status:** reconciliation audit  
**Canonical queue:** [`MASTER_OPEN_DESIGN_QUESTIONS.md`](./MASTER_OPEN_DESIGN_QUESTIONS.md)  
**Purpose:** verify that the previously separate open-question registers are represented in the canonical master queue and that every master item contains an architect recommendation and proof path.

---

## Source coverage

The master register reconciles three prior queues:

- `docs/context/Open_Questions.md` — 15 `OQ-*` items;
- `Business/Design_Questions.md` — 32 `BQ-*` items;
- `docs/context/REVIEW_THESE_PRELIMINARY_DECISIONS_DEFENSIBILITY.md` — 30 `DQ-*` items.

Total source question IDs accounted for: **77**.

The master de-duplicates those into **51 `MQ-*` questions**. Every source ID appears in the source crosswalk in `MASTER_OPEN_DESIGN_QUESTIONS.md`; one source question may map to more than one master question where the older item bundled distinct decisions.

---

## Recommendation completeness rule

Every `MQ-*` entry contains, at minimum:

1. the unresolved question;
2. one or more source aliases where applicable;
3. an **Architect recommendation**;
4. rationale/constraints or explicit `Do not` guidance where material;
5. an owner;
6. the proof/evidence/review required before Carbon may rely on the answer;
7. a status distinguishing ratification readiness from evidence/security/counsel needs.

Where a responsible numeric/legal/security answer cannot be chosen from architecture alone, the recommendation specifies the **decision method** rather than inventing a value.

Examples:

- scientific thresholds are derived from the qualified dossier and measurement uncertainty, not guessed;
- reproducibility bands are measured from repeated runs rather than assigned generically;
- pricing bands are derived from measured delivery cost and buyer willingness to pay;
- security certification priorities are derived from target-buyer requirements rather than badge collecting;
- legal/IP/liability positions have an architect recommendation but remain `COUNSEL_REQUIRED` for enforceable language.

---

## Domain coverage

The master contains explicit decisions/recommendations for:

- first LIVE Challenge, population, SamplingPlan, generator dossier, truth, measurements, Score Pack and finite-evidence resolution;
- frontier promotion, baseline, portfolio allocation and scientific disputes/finality;
- randomness, validator disagreement, execution capability, disclosure security, fees/rate limits;
- governance authority, treasury custody, recovery/censorship/double settlement;
- network-vs-centralized falsification, Alpha/network utility and workload migration;
- agentic construction expansion, Landscape leakage/Goodhart control and Physics Intelligence proof;
- Product Qualification, qualification-vs-certification language, lifecycle and multiphysics composition;
- Evidence Audit, Sponsored Discovery, pricing, productization, verticals, design partners, pilots, platform and hiring;
- customer/evidence rights, miner IP, liability, private deployment and enterprise security;
- TAM/SAM/SOM, fundraising/capital planning and publication release control.

---

## Remaining meaning of `OPEN`

An item being open no longer means Carbon lacks a view. It means one of the following remains unfinished:

```text
human ratification
empirical evidence
security qualification
counsel review
commercial validation
```

The master therefore supports two defensible responses to diligence:

> **This is the ratified/qualified answer, and here is the evidence.**

or:

> **This is not established yet. Here is Carbon's current recommended design, the owner, the failure mode it avoids, and the exact proof required before we rely on it.**

---

## Maintenance rule

When a master question is resolved:

1. record the decision in the relevant domain decision/specification/canon;
2. preserve the evidence/review commit;
3. update the `MQ-*` status and link to that authority;
4. do not delete the historical source question merely to make the queue look smaller.

When a new material question is discovered, add it directly to the master queue (and to a domain-specific working queue only if that deeper queue is useful). No new parallel open-question register should become authoritative.
