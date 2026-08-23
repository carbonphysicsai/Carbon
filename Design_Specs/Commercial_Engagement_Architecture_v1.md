# Carbon Commercial Engagement Architecture v1

**Status:** OWNER-RECOMMENDED v1 for commercial/technical/legal review.  
**Purpose:** Define how customer/sponsor work binds to Carbon's scientific Challenge, evidence, qualification, privacy, IP, delivery, and payment layers without allowing commercial terms to rewrite scientific truth.

---

# 1. Core rule

> **Commercial terms may choose the job, privacy mode, deliverables, rights, and funding model; they may not silently redefine the scientific evidence required to support a claim.**

Carbon's commercial architecture sits around the scientific core rather than inside the judge.

```text
CUSTOMER / SPONSOR NEED
        ↓
CommercialEngagementSpec
        ↓
qualified Challenge / Evidence / Qualification program
        ↓
DeliverableContract
        ↓
CustomerAcceptancePlan
```

---

# 2. Commercial engagement modes

## CE1 — Discovery Challenge

Purpose: discover better model-construction approaches.

Scientific output:
- Challenge-bound candidate evidence;
- frontier promotion where relevant;
- ExperimentRecords;
- selected candidate(s).

Commercial output:
- sponsor report;
- candidate rights/delivery according to contract;
- optional follow-on qualification.

## CE2 — Independent Evidence Program

Purpose: evaluate a customer-supplied model, method, or system.

No miner competition is required unless the customer wants comparative search.

## CE3 — Model Development Program

Purpose: use Carbon search plus controlled reconstruction to deliver a strong candidate artifact.

Candidate delivery does not itself imply Product Qualification.

## CE4 — Product Qualification Program

Purpose: determine whether one exact artifact/system has sufficient evidence for one exact context of use.

Outputs bind exact artifact identity, Product Qualification Pack, Product Battery Record, Qualification Record, limitations, answerability/escalation, and requalification triggers.

## CE5 — Lifecycle / Physics-Intelligence Program

Purpose: improve future decisions using accumulated evidence.

Permitted claims depend on demonstrated prospective lift for the specific decision role.

## CE6 — Sponsored Frontier Bounty

Purpose: fund progress on a registered scientific frontier.

Sponsor economics are separate from the base subnet performance reward unless a prospective contract explicitly combines them.

---

# 3. CommercialEngagementSpec

Conceptual object:

```text
CommercialEngagementSpec {
  engagement_id
  customer_or_sponsor_id
  engagement_mode
  scientific_program_refs
  requested_claim
  privacy_profile
  truth_access_mode
  participant_visibility
  customer_disclosure_policy
  commercial_rights_policy
  deliverable_contract_ref
  customer_acceptance_plan_ref
  customer_payment_policy_ref
  sponsored_reward_policy_ref | null
  publication_policy
  support_and_lifecycle_policy
  termination_policy
  governing_approvals
}
```

The engagement spec is not a Score Pack and may not add score-bearing science by itself.

---

# 4. TruthAccessMode

A commercial Challenge may obtain reference/truth evidence through different operational arrangements.

Recommended modes:

```text
CARBON_OPERATED_REFERENCE
CUSTOMER_HOSTED_SOLVER_SERVICE
CUSTOMER_PRECOMPUTED_DATASET
THIRD_PARTY_REFERENCE_SERVICE
EXPERIMENTAL_DATA_SOURCE
HYBRID_MULTI_FIDELITY
AIR_GAPPED_CUSTOMER_TRUTH
```

For every mode the Validation Dossier must establish adequacy, provenance, uncertainty, failure policy, and applicability.

A customer saying "this is our ground truth" does not bypass scientific qualification.

---

# 5. Privacy profiles

Recommended starting profiles:

## PUBLIC_RESEARCH

Challenge semantics and appropriate evidence are public; protected official realizations remain hidden.

## PRIVATE_SPONSOR

Customer data/truth/material may be visible only to authorized Carbon/evaluation infrastructure and customer-designated auditors. Miner-facing surfaces are disclosure-limited.

## CUSTOMER_CONTROLLED_TRUTH

Carbon sends authorized cases/queries to a customer-operated truth service. Raw solver implementation/data remain customer-side.

## AIR_GAPPED

Scientific/economic machinery is deployed into an isolated customer environment or another explicitly qualified offline topology.

Exact topology is implementation/security work, not implied by this v1.

---

# 6. CustomerDisclosurePolicy

Audience classes should be explicit:

```text
PUBLIC
MINER
SPONSOR
CUSTOMER_DILIGENCE
INDEPENDENT_AUDITOR
CARBON_PRIVATE
```

A single evidence object may have multiple projections.

Rules:
- public transparency does not require public customer IP;
- customer auditability does not require miner access;
- hidden-evaluation reconstruction material remains protected even from broader customer surfaces unless operationally necessary;
- disclosure changes are versioned and prospective where they can alter adaptive-evaluation leakage.

---

# 7. CommercialRightsPolicy

A production engagement must explicitly assign or license rights for at least:

```text
customer input data
customer solver access / API
Challenge semantics
miner-submitted strategy / construction program
generalized construction method
reconstructed/trained candidate artifact
model weights / source / recipe
ExperimentRecords and evidence metadata
derived aggregates / Landscape knowledge
publication / benchmark rights
exclusive vs non-exclusive use
reuse across customers
customer-specific confidential derivatives
```

No default assumption should silently convert customer data into public/shared training material or miner IP into Carbon-owned commercial IP.

The legal implementation requires counsel; this document defines the required semantic slots.

---

# 8. DeliverableContract

Conceptual object:

```text
DeliverableContract {
  deliverable_id
  engagement_id
  artifact_refs[]
  representation / deployment_format
  runtime_identity
  included_source_or_weights
  included_construction_recipe
  evidence_package_refs[]
  qualification_status_ref | null
  known_limitations
  answerability_escalation_policy
  customer_disclosure_bundle
  support_sla
  lifecycle_update_terms
  requalification_triggers
  acceptance_plan_ref
}
```

Core rule:

> **The deliverable is not just the model file. It is the artifact plus the evidence, identity, limitations, and rights that make the customer claim intelligible.**

---

# 9. CustomerAcceptancePlan

Commercial acceptance is separate from Carbon scientific admissibility or qualification.

It may include:
- file/package delivery checks;
- integration/API tests;
- latency/resource checks;
- customer security review;
- customer-side replication;
- installation/on-prem acceptance;
- documentation delivery;
- procurement milestones;
- customer V&V handoff.

A commercial acceptance failure must not silently rewrite an already-finalized scientific result.

---

# 10. Customer payment policy

Customer payment and subnet performance reward are different economic layers.

Possible customer commercial models:

```text
fixed program fee
cost-plus / compute pass-through
sponsored bounty pool
milestone payment
success fee
subscription / retainer
qualification fee
lifecycle monitoring fee
license / usage fee
enterprise support fee
```

Rules:
- customer spend never enters scientific score;
- a higher-paying sponsor does not receive an easier exam;
- sponsor-funded bounty conditions are frozen prospectively;
- treasury miner payouts and Carbon/customer invoices are separately accounted;
- no-pay/no-win commercial terms must not pressure the scientific contract to manufacture a winner.

---

# 11. Sponsored reward policy

A sponsor may fund additional scientific reward above the base subnet mechanism.

Conceptually:

```text
SponsoredRewardPolicy {
  sponsor
  challenge_id/version
  reward_pool
  eligible_event_type
  payout_schedule
  expiry
  carry_forward_policy
  refund/reversion policy
  treasury/custody route
}
```

Default recommendation:
- bind payment to `FrontierAdvanceEvent` or another explicitly registered scientific event;
- keep information-value bounties typed separately from performance rewards;
- do not allow sponsor discretion after result observation to redefine success.

---

# 12. Private Challenge security boundary

Private Challenges are a major commercial feature and a major security risk.

Before production, specify and test:
- data ingress/egress;
- miner-visible schema vs hidden customer semantics;
- query leakage;
- customer-hosted truth authentication;
- execution isolation;
- logging/redaction;
- storage retention;
- key/secret management;
- validator access policy;
- audit access;
- incident response;
- deletion/retention commitments;
- model/strategy exfiltration policy.

A private Challenge may need a smaller trusted evaluator cohort or customer-hosted execution. That changes deployment architecture, not the scientific need for independent evidence.

---

# 13. Representation and integration adapters

Scientific model-family neutrality does not automatically provide commercial interoperability.

A practical adapter registry may include:

```text
GRID_FIELD_V1
UNSTRUCTURED_MESH_V1
POINT_CLOUD_V1
GRAPH_GEOMETRY_V1
PARAMETRIC_CAD_V1
TIME_SERIES_SENSOR_V1
SCALAR_QOI_V1
FIELD_QOI_V1
ONNX_RUNTIME_V1
CONTAINER_SERVICE_V1
PYTHON_API_V1
CPP_API_V1
FMU_V1
CUSTOMER_SOLVER_RPC_V1
```

Every adapter that materially changes physical representation requires qualification appropriate to its role.

---

# 14. Engagement lifecycle

Recommended lifecycle:

```text
LEAD / PROBLEM DISCOVERY
        ↓
FEASIBILITY
        ↓
SCIENTIFIC AUTHORING
        ↓
COMMERCIAL CONTRACT + RIGHTS + PRIVACY
        ↓
CHALLENGE / EVIDENCE PROGRAM QUALIFICATION
        ↓
EXECUTION
        ↓
RESULT / FRONTIER / CANDIDATE
        ↓
DELIVERY OR PRODUCT QUALIFICATION
        ↓
CUSTOMER ACCEPTANCE
        ↓
DEPLOYMENT / LIFECYCLE / REQUALIFICATION
```

No step implies the next automatically.

---

# 15. Commercial feasibility gate

Before accepting a program, Carbon should answer:

1. Is the customer question scientifically well-defined?
2. Is there a valid candidate input/output contract?
3. Is a defensible target population available/authored?
4. Is an adequate truth/reference path accessible?
5. Can confidentiality/IP obligations be technically and contractually satisfied?
6. Can a meaningful deliverable be defined?
7. Can Carbon state what qualification claim, if any, will be attempted?
8. Are time/compute/budget compatible with the evidence burden?
9. Is the requested model family currently reconstructable or does the engagement include adapter development?
10. Are customer expectations compatible with Carbon's non-claims?

If any mandatory answer is no, the engagement is blocked, narrowed, or redirected.

---

# 16. Commercial constitutional invariants

1. **Commercial pressure does not rewrite scientific truth.**
2. **Customer payment never enters scientific score.**
3. **Customer-provided truth still requires provenance and adequacy review.**
4. **Private does not mean scientifically opaque; evidence can be disclosed to authorized reviewers without being public.**
5. **A subnet winner is not automatically the customer's deliverable or qualified product.**
6. **Artifact, evidence, rights, and deployment identity are separate contractual objects.**
7. **Customer acceptance and scientific qualification are different states.**
8. **Commercial settlement and miner frontier settlement are separate accounting layers.**
9. **No customer receives a stronger scientific claim than its registered evidence supports.**
10. **Material deployment/model/context change may trigger requalification.**

---

# 17. Recommended implementation priority

1. `CommercialEngagementSpec` + feasibility checklist.
2. `CommercialRightsPolicy` with legal counsel.
3. `CustomerDisclosurePolicy` / private Challenge projections.
4. `TruthAccessMode` adapters, starting with customer-hosted solver RPC and precomputed dataset mode.
5. `DeliverableContract`.
6. private Challenge security architecture.
7. customer-facing evidence/report bundle.
8. initial representation/integration adapter registry.
9. sponsored reward policy.
10. lifecycle monitoring/requalification interfaces.

---

# 18. Final statement

> **Carbon's commercial architecture should let customers choose what problem, privacy, deliverable, and funding model they need while keeping scientific authority, qualification, and evidence boundaries unchanged.**
