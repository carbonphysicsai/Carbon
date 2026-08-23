# Carbon Commercial Operating Model v1

**Status:** OWNER-CANONICAL operating architecture.  
**Purpose:** define the commercial objects, rights/privacy boundaries, engagement lifecycle, and delivery controls required to turn the business plan into repeatable enterprise execution.

---

# 1. Commercial object model

Every customer program should be represented by a bounded commercial engagement record separate from scientific authority.

Conceptual structure:

```text
CommercialEngagementSpec {
  customer
  product_family
  requested_outcome
  scientific_program_refs
  privacy_profile
  truth_access_mode
  rights_policy
  deliverable_contract
  customer_acceptance_plan
  payment_policy
  sponsored_reward_policy | null
  publication_policy
  support_lifecycle_policy
  termination_policy
}
```

Commercial terms may choose the job, deployment, rights, funding, and deliverables. They may not silently redefine scientific evidence requirements.

---

# 2. Truth-access modes

Supported architecture classes:

```text
CARBON_OPERATED_REFERENCE
CUSTOMER_HOSTED_SOLVER_SERVICE
CUSTOMER_PRECOMPUTED_DATASET
THIRD_PARTY_REFERENCE_SERVICE
EXPERIMENTAL_DATA_SOURCE
HYBRID_MULTI_FIDELITY
AIR_GAPPED_CUSTOMER_TRUTH
```

Each mode still requires scientific adequacy/provenance review.

Priority commercial extension:

> **Customer-hosted solver service** — the proprietary solver remains customer-side while Carbon sends authorized cases and receives controlled reference outputs.

---

# 3. Privacy profiles

```text
PUBLIC_RESEARCH
PRIVATE_SPONSOR
CUSTOMER_CONTROLLED_TRUTH
CUSTOMER_VPC
AIR_GAPPED
```

A product may only be sold under a profile that has been technically and contractually qualified.

Audience-specific disclosure should distinguish:

```text
PUBLIC
MINER / EXTERNAL PARTICIPANT
CUSTOMER
CUSTOMER_DILIGENCE
INDEPENDENT_AUDITOR
CARBON_PRIVATE
```

Private does not mean scientifically unauditable. It means evidence is exposed only to authorized audiences.

---

# 4. Commercial rights policy

Every program must explicitly address rights in:

```text
CUSTOMER_DATA
CUSTOMER_SOLVER / API
CHALLENGE_SEMANTICS
SUBMITTED_STRATEGY / METHOD
GENERALIZED_CONSTRUCTION_METHOD
RECONSTRUCTED_ARTIFACT
MODEL_WEIGHTS
SOURCE / RECIPE
EXPERIMENT_RECORDS
EVIDENCE_METADATA
AGGREGATED_EVIDENCE
PHYSICS_INTELLIGENCE DERIVATIVES
PUBLICATION
CROSS_CUSTOMER_REUSE
EXCLUSIVITY
MODEL / METHOD LICENSE
```

No default assumption should give Carbon rights it does not contractually possess.

Recommended evidence reuse classes:

```text
CUSTOMER_EXCLUSIVE
CUSTOMER_CONFIDENTIAL_AGGREGATABLE
ANONYMIZED_AGGREGATABLE
METHOD_LEVEL_REUSABLE
PUBLIC_RESEARCH
CARBON_INTERNAL_ONLY
NO_REUSE
```

---

# 5. Deliverable contract

A commercial deliverable is more than a model file.

Conceptual bundle:

```text
DeliverableContract {
  artifact_refs
  deployment_format
  runtime_identity
  source_or_weights_included
  construction_recipe_included
  evidence_package_refs
  qualification_status
  known_limitations
  answerability_escalation
  disclosure_bundle
  support_sla
  lifecycle_terms
  requalification_triggers
  customer_acceptance_plan
}
```

Core rule:

> **Artifact, evidence, rights, deployment identity, and qualification status are separate contractual dimensions.**

---

# 6. Customer acceptance

Commercial acceptance may include:

- agreed report/package delivery;
- API/container installation;
- latency/resource acceptance;
- customer-side replication;
- security review;
- documentation handoff;
- procurement milestone completion.

Commercial acceptance failure does not retroactively rewrite a finalized scientific result.

---

# 7. Engagement lifecycle

```text
LEAD
        ↓
DISCOVERY
        ↓
TECHNICAL FEASIBILITY
        ↓
COMMERCIAL QUALIFICATION
        ↓
RIGHTS / PRIVACY / SECURITY
        ↓
SOW / CONTRACT
        ↓
PROGRAM EXECUTION
        ↓
DELIVERABLE / EVIDENCE
        ↓
CUSTOMER ACCEPTANCE
        ↓
EXPANSION
        ↓
LIFECYCLE / RENEWAL
```

No stage implies the next automatically.

---

# 8. SOW structure

Every SOW should define:

1. customer problem and intended decision;
2. exact product family;
3. customer inputs and dependencies;
4. truth/reference access;
5. privacy/security mode;
6. evidence scope;
7. deliverables;
8. included evaluation/compute capacity;
9. exclusions;
10. commercial acceptance;
11. pricing and payment schedule;
12. change-order rules;
13. rights/IP;
14. publication/confidentiality;
15. support/lifecycle;
16. what happens if evidence is negative or no frontier advance occurs.

---

# 9. Business stop-ships

Do not contract the program if:

- the requested claim is not scientifically supportable;
- truth/reference access is inadequate;
- customer confidentiality cannot be technically enforced;
- IP/rights are ambiguous for promised deliverables;
- requested deployment topology is unqualified;
- budget/timeline cannot support the evidence burden;
- unlimited truth/evaluation cost is bundled without protection;
- a success fee would pressure the scientific result;
- Carbon is promising a license to rights it does not own;
- the engagement has no coherent deliverable or acceptance condition.

---

# 10. Operating principle

> **Productize the commercial wrapper as aggressively as the scientific engine: standardized intake, rights, disclosure, truth adapters, deliverables, acceptance, evidence bundles, and lifecycle should become reusable infrastructure rather than reinvented contract-by-contract.**
