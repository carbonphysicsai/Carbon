# Review These Preliminary Decisions — Commercial Architecture

**Status:** owner/architect preliminary decisions after the 2026-08-22 Commercial Gauntlet.  
**Related:** `COMMERCIAL_GAUNTLET_SIMULATION_2026-08-22.md`, `Commercial_Engagement_Architecture_v1.md`, `Customer_Request_and_Deliverable_Taxonomy_v1.md`.

Review model:

```text
C1 ACCEPT / MODIFY / REJECT
...
C16 ACCEPT / MODIFY / REJECT
```

---

# C1 — Carbon should expose multiple commercial engagement modes

### Preliminary decision: ACCEPT

Use a common scientific core with separate commercial modes:

- Discovery Challenge;
- Independent Evidence Program;
- Model Development Program;
- Product Qualification Program;
- Lifecycle / Physics-Intelligence Program;
- Sponsored Frontier Bounty.

Do not force every customer into "buy a trained model."

Confidence: **Very high**.

---

# C2 — Independent evaluation of an existing customer model should be an early offer

### Preliminary decision: ACCEPT

This uses Carbon's strongest near-term capability without requiring the subnet to discover/train the customer's artifact first.

Confidence: **Very high**.

---

# C3 — CommercialEngagementSpec should be a first-class object

### Preliminary decision: ACCEPT

It binds customer mode, privacy, truth access, rights, deliverables, payment, publication, and lifecycle to the scientific program without becoming scientific authority.

Confidence: **High**.

---

# C4 — Private Challenge architecture is a major commercial priority

### Preliminary decision: ACCEPT

Customer-hosted solver/truth, Carbon-hosted sealed evaluation, VPC, and later air-gapped modes should be designed explicitly rather than implied by generic disclosure rules.

Confidence: **Very high**.

---

# C5 — Customer-hosted truth service should be the first private truth integration target

### Preliminary decision: ACCEPT

It can preserve proprietary solver/data custody while still allowing Carbon to issue authorized physical queries and obtain reference outputs.

Security and information-leakage qualification remain required.

Confidence: **High**.

---

# C6 — CommercialRightsPolicy is a stop-ship before serious private industry engagements

### Preliminary decision: ACCEPT

The engagement must explicitly address customer data, solver access, miner method IP, generalized methods, reconstructed artifacts, evidence, Landscape derivatives, publication, exclusivity, and reuse.

Legal counsel owns final language.

Confidence: **Very high**.

---

# C7 — DeliverableContract should define what the customer actually receives

### Preliminary decision: ACCEPT

A commercial deliverable is more than a model file. It should bind artifact/runtime identity, source/weights/recipe rights, evidence bundle, qualification state, limitations, support, and requalification terms.

Confidence: **Very high**.

---

# C8 — Customer acceptance must remain separate from scientific qualification

### Preliminary decision: ACCEPT

Installation, security review, API integration, latency, documentation, and procurement acceptance may fail even when a scientific result is valid. Neither state should silently rewrite the other.

Confidence: **Very high**.

---

# C9 — Customer payment economics remain separate from subnet frontier economics

### Preliminary decision: ACCEPT

Fixed fees, subscriptions, licenses, sponsored pools, success fees, and compute pass-through may coexist, but customer spend never changes scientific score or exam difficulty.

Confidence: **Very high**.

---

# C10 — Sponsored frontier bounties should bind prospective scientific events

### Preliminary decision: ACCEPT

Prefer `FrontierAdvanceEvent` or another exact registered event as the payout condition. Sponsor discretion after results are observed must not redefine success.

Confidence: **Very high**.

---

# C11 — Customer/auditor evidence tiers should be richer than public/miner disclosure

### Preliminary decision: ACCEPT

Recommended audience classes:

```text
PUBLIC
MINER
SPONSOR
CUSTOMER_DILIGENCE
INDEPENDENT_AUDITOR
CARBON_PRIVATE
```

Transparency should be scoped by authority and confidentiality rather than equated with universal publication.

Confidence: **Very high**.

---

# C12 — Build a representation/integration adapter registry rather than special-casing each customer

### Preliminary decision: ACCEPT

Start with high-value interfaces such as grids, unstructured meshes, parametric geometry, customer solver RPC, ONNX/container, Python API, and later C++/FMU as demanded.

Every material representation transformation remains subject to qualification.

Confidence: **High**.

---

# C13 — Carbon should explicitly decline universal safety/certification claims

### Preliminary decision: ACCEPT

Carbon may issue bounded evidence/qualification records under a defined context of use. Customer, regulator, or governing engineering authority retains final deployment/approval authority.

Confidence: **Very high**.

---

# C14 — Earliest commercial sequencing should favor low-new-infrastructure modes

### Preliminary decision: ACCEPT

Recommended order:

1. existing-model Independent Evidence Program;
2. sponsored non-sensitive Discovery Challenge;
3. private Discovery Challenge with customer-controlled truth;
4. controlled candidate delivery;
5. Product Qualification Program;
6. private/air-gapped qualification;
7. lifecycle/physics-intelligence services.

Confidence: **High**.

---

# C15 — IP/privacy/truth accessibility should be part of commercial feasibility, not discovered after sale

### Preliminary decision: ACCEPT

No engagement should move to execution before Carbon can state the physical job, truth path, privacy topology, rights model, exact deliverable, and bounded claim.

Confidence: **Very high**.

---

# C16 — Commercial architecture should feed papers/deck only after review

### Preliminary decision: ACCEPT

Do not immediately overload public materials with object names or promise private/air-gapped capabilities that are not implemented. The commercial gauntlet should first guide design, GTM packaging, partner qualification questions, and roadmap prioritization.

Public message can remain simple:

> **Carbon can run discovery, independent evidence, and qualification programs around a defined physical modeling job; the depth of evidence and privacy increases with the use case.**

Confidence: **Very high**.

---

# Owner conclusion

> **The commercial gauntlet does not expose a missing scientific foundation. It exposes the need to productize the boundary around that foundation: privacy, truth access, rights, deliverables, integration, customer acceptance, and customer-specific economics.**
