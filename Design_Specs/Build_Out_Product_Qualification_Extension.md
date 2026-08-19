# Build Out — Product Qualification Evidence Extension

**Status:** Additive implementation-planning extension — team review  
**Depends on:** `Product_Qualification_Evidence.md`, `Specialist_Bank.md`, `Evaluation_Evidence_and_Validator_Audit.md`  
**Sequencing rule:** This extension does not reorder the current P0 Wave A–C trust-path work. Product-plane implementation is post-P0/later-layer work unless a prerequisite schema/commitment primitive is intentionally shared earlier.

---

## Objective

Implement Carbon's product qualification evidence trail without collapsing competition evidence, Product Battery measurements, qualification judgment, and commercial packaging into one mutable artifact.

The implementation target is:

```text
fresh product retrain
  → Product Candidate Model Card
  → Product Battery Record
  → Qualification Record
  → Qualified Specialist package
```

with append-only lineage, tiered disclosure, explicit requalification semantics, and no path from product/commercial state into lean scientific score or emissions.

---

## Q0 — Schema authority and compatibility

**Deliverables**

- Canonical versioned schemas/interfaces for:
  - Product Candidate Model Card role/lineage fields;
  - `ProductBatteryRecord`;
  - `QualificationRecord`;
  - Qualified Specialist manifest/package references.
- Explicit identifiers/content hashes for exact candidate artifact, context of use, Product Battery pack/policy, and evidence references.
- Compatibility decision documenting which existing Model Card fields are KEEP/WRAP/REPAIR and which product-specific fields live only in product records.

**Acceptance**

- A product retrain cannot reuse the competition Model Card identity for a materially distinct trained artifact.
- Qualification cannot be constructed without exact candidate, Product Battery Record, context-of-use, and qualification-policy identities.
- No production scientific thresholds are introduced by schema defaults.

---

## Q1 — Product Battery Record persistence

**Deliverables**

- Immutable persistence for every Product Battery attempt, including failures.
- Version-bound module verdict/result representation.
- Evidence commitments/signing compatible with Carbon's existing evidence primitives where practical.
- Append-only correction/supersession behavior.

**Acceptance**

- A failed attempt remains queryable/auditable after a later passing attempt.
- Product Battery results cannot enter lean ScoreInput/emissions through any typed interface.
- Hidden/reconstruction-sensitive battery material is absent from public projections.

---

## Q2 — Qualification Record issuance

**Deliverables**

- Signed/versioned `QualificationRecord` issuance path.
- Required binding to exact model artifact, Product Candidate Model Card, Product Battery Record, context of use, qualification policy, validity-envelope reference, limitations, escalation conditions, and requalification triggers.
- Human-approval boundary for scientific/context-of-use qualification decisions where required.

**Acceptance**

- Implementation cannot issue a qualified record from rank/checkpoint alone.
- Implementation cannot issue a qualified record when mandatory Product Battery policy is unsatisfied.
- An agent/test fixture cannot autonomously substitute guessed qualification criteria for human-owned policy.

---

## Q3 — Qualification lifecycle

**Deliverables**

- Ratified status/event model for qualification lifecycle.
- Supersession and requalification-required semantics.
- Historical-state queries that preserve the original record and later state transitions.

**Acceptance**

- Current qualification state can change without mutating historical evidence.
- Material adaptation cannot silently inherit the predecessor's qualification.
- Status transitions are explicit, validated, and auditable.

**Human decision required before implementation:** ratify the exact lifecycle enum and transition policy. Do not infer it from prose.

---

## Q4 — Disclosure projections

**Deliverables**

- Allow-listed projections for:
  - public/catalog;
  - buyer/controlled diligence;
  - private Carbon/authorized audit.
- Leakage tests covering hidden exam material, protected Product Battery material, proprietary recipes, Landscape outputs, and reconstruction-sensitive identifiers.

**Acceptance**

- Public catalog can establish claim identity/provenance without exposing answer-key material or exact private recipe.
- Buyer surface exposes only explicitly authorized evidence.
- Private-only fields fail closed if projection policy is missing.

---

## Q5 — Qualified Specialist manifest/package

**Deliverables**

- Versioned specialist manifest binding:
  - deployable artifact hash;
  - deployment/I-O identity;
  - Product Candidate Model Card;
  - Product Battery Record;
  - Qualification Record;
  - supporting evidence commitments;
  - commercial/delivery version identity.
- Packaging verification that the delivered artifact matches the qualified artifact.

**Acceptance**

- A package whose artifact hash differs from the Qualification Record is rejected.
- A package missing required qualification evidence cannot be marked Qualified Specialist.
- Commercial metadata does not affect scientific score/emissions.

---

## Q6 — Requalification enforcement

**Deliverables**

- Policy-driven detection of declared material changes requiring requalification.
- Explicit invalidation/requalification-required workflow for adaptation, envelope expansion, runtime/export changes, or other policy-defined triggers.

**Acceptance**

- Fine-tune/LoRA/adaptation cannot silently retain qualification when policy requires requalification.
- Requalification creates new evidence records rather than overwriting prior records.
- Prior evidence remains historically attributable and auditable.

---

## Q7 — Evidence graph / Landscape ingest

**Deliverables**

- Private graph edges connecting qualification outcomes to source strategy/model lineage.
- Failure evidence ingestion for Product Battery module failures and qualification outcomes.
- Decontamination/disclosure controls preventing product evidence from becoming a live exam oracle.

**Acceptance**

- Landscape may learn from product outcomes but cannot satisfy gates or qualification itself.
- Product failures may inform future validated packs/policies but cannot silently rescore history.

---

## Q8 — Invariant CI

Add constitutional tests for at least:

1. competition Model Card cannot be mutated/promoted into product qualification;
2. fresh product artifact requires fresh Model Card identity;
3. failed Product Battery attempt remains preserved;
4. Qualification Record cannot issue without required evidence bindings;
5. qualification cannot bypass mandatory Product Battery policy;
6. product/commercial fields cannot enter lean score/emissions;
7. supersession/requalification preserves history;
8. public/buyer projections do not leak protected material;
9. delivered Qualified Specialist artifact must match qualified artifact hash;
10. fixture/mock qualification is structurally non-production-qualified.

---

## Definition of Done for this extension

This extension is not complete when schemas merely exist. It is complete only when the applicable product-plane implementation is IMPLEMENTED and TESTED, the required human scientific/security/operational qualification has occurred for a specific product/context, and no Carbon maturity label is advanced merely because the design is specified.
