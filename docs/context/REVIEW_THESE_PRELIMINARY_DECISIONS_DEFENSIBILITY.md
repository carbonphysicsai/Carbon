# Review These Preliminary Decisions — Defensibility

**Status:** OWNER-REVIEW QUEUE.  
**Purpose:** isolate the remaining decisions that materially affect Carbon's ability to withstand scientific, security, economic, legal, enterprise, and investor diligence.

---

## DQ-001 — First LIVE Challenge identity

**Question:** Do we formally ratify the first authoritative Challenge as fixed-viscosity 1D viscous Burgers with the repaired causal-input/truth architecture?

**Current recommendation:** yes, subject to the Validation Dossier and exact population/measurement decisions.

**Decision:** `OPEN`

## DQ-002 — First Challenge target population

**Question:** What exact target population, strata, query distribution, exclusions, and SamplingPlan are claimed?

**Owner:** Physics/SciML.

**Decision:** `OPEN`

## DQ-003 — First Challenge truth hierarchy

**Question:** Do we ratify Cole–Hopf as primary truth and a separately qualified high-resolution numerical solver as corroborating witness for the declared regime?

**Decision:** `OPEN`

## DQ-004 — Scientific resolution policy

**Question:** What empirical evidence is required to say a candidate is meaningfully superior rather than within reconstruction/evaluation uncertainty?

**Deliverable:** minimum resolvable improvement / rank-stability policy.

**Decision:** `OPEN`

## DQ-005 — LeaderReplacementPolicy v1

**Question:** What exact common-exam, superiority, tie, multiple-contender, retry, and `INDETERMINATE` semantics create a `FrontierAdvanceEvent`?

**Decision:** `OPEN`

## DQ-006 — Production randomness path

**Question:** Which future-chain/randomness source, finality delay, domain separation, and fallback policy will be qualified for official exams?

**Owner:** Protocol/security.

**Decision:** `OPEN`

## DQ-007 — Validator disagreement policy

**Question:** What quorum, reproducibility tolerance, retry, contested state, and quarantine procedure applies when honest-looking validators disagree?

**Decision:** `OPEN`

## DQ-008 — P0 execution threat model

**Question:** What exact strategy capability surface and sandbox controls are permitted for the first real TrainEval backend?

**Current recommendation:** declarative bounded strategies only; no arbitrary miner code.

**Decision:** `OPEN`

## DQ-009 — Disclosure security acceptance

**Question:** What adaptive-query/red-team result is sufficient to approve the A9/A10/A11 miner-visible disclosure surface?

**Decision:** `OPEN`

## DQ-010 — Treasury custody model

**Question:** Which controller/vault/multisig architecture should hold and release scientific settlement obligations?

**Decision:** `OPEN`

## DQ-011 — Treasury recovery and censorship policy

**Question:** What happens if custody is unavailable, an authorized signer refuses, an admin attempts to censor a valid entitlement, or a duplicate payout is attempted?

**Decision:** `OPEN`

## DQ-012 — Governance authority matrix

**Question:** Which named roles/keys can approve Challenge qualification, Score Packs, security readiness, treasury actions, emergency pauses, commercial qualification, and production launch?

**Decision:** `OPEN`

## DQ-013 — Dispute/finality architecture

**Question:** What is appealable, by whom, for how long, and under what evidence for scientific disputes, operational incidents, and payment disputes?

**Decision:** `OPEN`

## DQ-014 — Network-vs-centralized falsification experiment

**Question:** What controlled comparison will establish whether the subnet improves method diversity, frontier performance, time-to-improvement, or cost per useful hypothesis versus centralized search?

**Decision:** `OPEN`

## DQ-015 — First direct Alpha utility

**Question:** Which first commercial/network behavior should create genuine Alpha/network utility without adding enterprise friction?

**Current recommendation:** sponsor-funded network-backed discovery/reward activity before more speculative token-native services.

**Decision:** `OPEN`

## DQ-016 — Evidence Audit commercial package

**Question:** What exactly is included in Standard, Advanced, and Enterprise Audit tiers, what is the default timebox, and what constitutes customer acceptance?

**Decision:** `OPEN`

## DQ-017 — First pricing hypotheses

**Question:** What three pricing bands should be tested against measured delivery cost and buyer willingness to pay?

**Decision:** `OPEN`

## DQ-018 — Customer data/evidence rights

**Question:** What rights does Carbon request by default for customer data, generated evidence, anonymized aggregates, method-level learning, and publication?

**Owner:** Business lead + counsel.

**Decision:** `OPEN`

## DQ-019 — Participant/miner IP

**Question:** What default rights model applies to submitted strategies, generalized methods, reconstructed artifacts, winning methods, sponsor licenses, exclusivity, and assignment?

**Owner:** Business/economic + counsel.

**Decision:** `OPEN`

## DQ-020 — Product Qualification legal language

**Question:** What exact bounded claim language differentiates Carbon Qualification from certification, warranty, regulatory approval, or final engineering authority?

**Owner:** Product + counsel.

**Decision:** `OPEN`

## DQ-021 — Liability and insurance

**Question:** What MSA/SOW warranty, indemnity, limitation-of-liability, insurance, and customer-authority structure is acceptable for evidence and qualification products?

**Decision:** `OPEN`

## DQ-022 — First private deployment topology

**Question:** Do we formally prioritize customer-hosted truth RPC before VPC and air-gap productization?

**Current recommendation:** yes.

**Decision:** `OPEN`

## DQ-023 — Enterprise security roadmap

**Question:** Which security/compliance requirements are actually necessary for the first target customers and at what stage (e.g. SOC 2, ISO 27001, export-controlled workflows, customer-specific controls)?

**Decision:** `OPEN`

## DQ-024 — Lifecycle/requalification triggers

**Question:** Which changes to artifact, training/data, solver, runtime, hardware, envelope, coupling, or use automatically invalidate or reopen qualification?

**Decision:** `OPEN`

## DQ-025 — Multiphysics/system qualification

**Question:** What system-level evidence is required before individually qualified components may be trusted as a coupled physical-decision system?

**Decision:** `OPEN`

## DQ-026 — Physics Intelligence proof standard

**Question:** What prospective decision task and baseline will be required before Carbon may sell Physics Intelligence as more than descriptive evidence analysis?

**Decision:** `OPEN`

## DQ-027 — Landscape leakage/Goodhart policy

**Question:** What information can Landscape expose to miners/agents, with what delay/coarsening/decontamination, before it becomes a surrogate for the hidden exam?

**Decision:** `OPEN`

## DQ-028 — Bottom-up market model

**Question:** Which named account universe, program density, buyer budget, ACV assumptions, and overlap controls should underpin SAM/SOM?

**Decision:** `OPEN`

## DQ-029 — Productization success threshold

**Question:** What custom-hours, gross-margin, recurring-share, and platform-conversion evidence must Carbon achieve before claiming it has escaped consulting economics?

**Decision:** `OPEN`

## DQ-030 — Publication release gate

**Question:** What exact claim audit, source-control, citation, maturity, and executive approval gates must v3.1 papers pass before external release?

**Decision:** `OPEN`

---

# Immediate closure order

Recommended sequence:

```text
SCIENCE
DQ-001 → 005

SECURITY / PROTOCOL
DQ-006 → 009

GOVERNANCE / TREASURY
DQ-010 → 013

NETWORK ECONOMICS
DQ-014 → 015

FIRST CUSTOMER
DQ-016 → 023

LIFECYCLE / SCALE
DQ-024 → 029

PUBLIC RELEASE
DQ-030
```

> **The goal is not to answer every question immediately. The goal is to ensure every unanswered question has a named owner, a bounded decision, and a proof path before Carbon relies on the claim.**
