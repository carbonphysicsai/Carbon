# Carbon Evidence Intelligence and Agent Research System

**Version:** 1.1
**Status:** OWNER-APPROVED IMPLEMENTATION DESIGN; not runtime implementation, qualification, public release, commercial traction, or LIVE authority  
**Owner decision:** `OWNER-EVIDENCE-RESEARCH-01`  
**Applies with:** `Evaluation_Evidence_and_Validator_Audit.md`, `Physics_Intelligence_System.md`, `Landscape_Agent.md`, `Miner_MCP_Wave_B_Research_Contract.md`, `Specialist_Bank.md`, `Build_Out.md`, and Business canon.

Focused normative companions provide implementation detail without duplicating source-owned runtime protocols:

- [Evidence Archive, Custody, and Availability](./Evidence_Archive_and_Custody.md) owns future capture, persistence, custody, recovery, and archive-view semantics.
- [Research Concierge, Demand, and Correction](./Research_Concierge_Demand_and_Correction.md) owns future dialogue, private thread, purpose-permission, D12, EvidenceBrief, release, and correction semantics.
- [Paid Research and Opportunity Evaluation](./Paid_Research_and_Opportunity_Evaluation.md) owns future paid-pilot, entitlement, campaign, hosted-research, billing, and evaluation semantics.
- [Requirements traceability and handoff](../.agent/plans/OWNER_EVIDENCE_RESEARCH_01_TRACEABILITY.md) maps every requirement to the 21 passive future tickets, dependencies, acceptance, and human decisions.

The full `Carbon_Evidence_Archive_Design_v0.3.zip` was read during integration. Its architecture, dialogue and demand designs, commercial proposal, buildout/handoff, opportunity register, acceptance matrix, source/reconciliation notes, starter schemas, examples, manifest, report, and validation script were treated as design input. Repository protocol and domain owners remain controlling. The ZIP itself and its permissive/stale starter schemas and package validator are not committed or promoted to runtime authority.

## 1. Objective

Carbon will build two compounding assets from real network activity:

1. **Evidence memory** — durable, provenance-rich records of official evaluation and other eligible experiments.
2. **Research-demand memory** — permission-aware records of what miners, agents, and customers are trying to understand.

A bounded **Carbon Research Concierge** gives agents launch-time two-way communication with Carbon. It can classify questions, retrieve approved sources, reason over them, preserve private threads, return grounded answers or explicit evidence gaps, and record demand. It is not a scientific judge.

The maturity path is:

```text
Research Concierge -> Research Copilot -> Research Scientist
```

Capability may expand. Scientific authority does not.

> **Agents propose and reason. Registered contracts and independent experiments decide.**

## 2. System architecture

```text
OFFICIAL EXECUTION
      |
      v
DURABLE EVIDENCE ARCHIVE
      |
      +--> protected evidence vault
      +--> controlled scientific views
      |
      v
LANDSCAPE
  D1-D11 evidence intelligence
  D12 research-demand graph
      |
      +--> Port A: search / research
      +--> Port B: operations only
      +--> Port C: experiment / future-policy proposals
      +--> Port D: products / evidence services

MINER / AGENT
      |
      v
CARBON RESEARCH CONCIERGE
  classify -> retrieve approved sources -> reason -> respond
      |
      +--> private thread history
      +--> ResearchGap / demand ledger
      +--> later paid research workflow
```

## 3. Durable official evidence rule

Carbon must durably retain the required evidence for every admitted official execution attempt, including successful evaluations, scientific failures, legal early stops, interruptions, retries, reference/generator/measurement failures, and infrastructure incidents.

Private miner experiments that never enter a Carbon-controlled research or official execution path remain outside mandatory collection.

For finalized official results:

```text
execute -> capture required evidence -> verify durable archive commit -> finalize official result
```

A result cannot be finalized if its required evidence has not reached the approved durability boundary. Landscape ingestion may lag and may fail independently; it cannot authorize loss of source evidence.

The archive must preserve source-owned identities, exact method/strategy references, resolved construction identity, physical context, measurements, execution coverage, provenance, dependence/lineage, permissions, and required retained artifacts. Infrastructure failure must never become negative scientific evidence.

## 4. Approved Knowledge Layer

The live Concierge never queries protected official evidence, raw private Model Cards, unreleased Landscape state, validator-private operational state, or another tenant's data.

It reasons only over an **Approved Knowledge Layer**, including where authorized:

- public Challenge and interaction contracts;
- ParameterCatalogs and construction rules;
- public scaffolds and practice resources;
- approved PriorPacks;
- approved `EvidenceBrief` artifacts;
- curated public science included in the serving corpus;
- eligible non-exam commercial evidence;
- the requester's authorized thread and research context.

Protected evidence may contribute to an `EvidenceBrief` only through an offline, versioned eligibility, aggregation, rights, leakage, approval, and release process.

## 5. EvidenceBrief

`EvidenceBrief` is the preferred rich grounding object for interactive Carbon research assistance.

Conceptual fields:

```text
EvidenceBrief {
  brief_id,
  topic,
  public_scope,
  supported_question_classes,
  interventions,
  outcome_families,
  evidence_origin,
  epistemic_status,
  support_band,
  uncertainty_band,
  counterevidence,
  transfer_limits,
  resource_context,
  falsification_options,
  source_release_refs,
  permitted_audiences,
  supersedes?
}
```

The Concierge may explain and combine approved briefs but cannot strengthen their epistemic status.

## 6. Launch Research Concierge

At first authenticated external miner launch, Carbon should support a separately versioned dialogue capability that lets agents:

- ask a natural-language research question;
- continue a persistent private thread;
- request comparison of approved evidence;
- request explanation of a known failure class;
- ask for a permitted public-practice falsification step;
- submit a hypothesis or research proposal;
- record an experiment request or paid-interest signal;
- report whether guidance was used and what happened;
- subscribe to approved topic/thread updates.

The service terminates requests through explicit outcomes such as:

```text
GROUNDED_ANSWER
APPROVED_RESOURCE_POINTER
PUBLIC_PRACTICE_SUGGESTION
INSUFFICIENT_EVIDENCE
RESEARCH_GAP_RECORDED
FOLLOWUP_NEEDED
EXPERIMENT_REQUEST_RECORDED
UNAVAILABLE
POLICY_RESTRICTED
```

`INSUFFICIENT_EVIDENCE` is a valid and valuable result. The system must not fill unsupported scientific gaps with plausible prose.

The Concierge may reason, synthesize, compare, ask for context, and propose non-authoritative next steps. It cannot access protected cases, predict official score/rank/gate margins, alter a Challenge, commission research, spend funds, or change official treatment.

## 7. Response lineage and corrections

Every substantive response must retain internal source and policy lineage sufficient to determine:

```text
request / thread
approved source refs and versions
requester-authorized context refs
reasoning runtime / model identity
claim-support mapping
uncertainty / known gaps
recommended action
response policy version
correction state
```

Corrections are append-only. Carbon must maintain reverse dependency lineage:

```text
ArchiveEntry
 -> ResearchSnapshot
 -> KnowledgeClaim
 -> EvidenceBrief / PriorPack
 -> ConciergeResponse
 -> CustomerReport
```

A corrected or withdrawn source triggers impact assessment of dependent guidance and customer deliverables. Historical responses remain preserved; corrected versions link to them. Customer notification follows the applicable service entitlement.

## 8. D12 — Research Demand Graph

Landscape gains **D12 Research Demand Graph** as a private planning and commercial-intelligence product.

D12 records what researchers want to know; it does not establish scientific truth.

Permission-eligible signals may include:

- question class and public physical scope;
- unresolved `ResearchGap`;
- requested intervention comparison;
- experiment request;
- quote interest;
- voluntarily supplied coarse budget intent;
- follow-up depth;
- feedback;
- paid quote / campaign facts from the commercial ledger;
- gap-to-experiment-to-release lineage.

Carbon must keep these distinct:

```text
question
!= independent customer demand
!= budget intent
!= quote request
!= accepted quote
!= paid campaign
!= repeat paid campaign
```

This prevents request volume from masquerading as commercial demand.

## 9. Value flow through Landscape

### Port A — Research

Use approved evidence and demand to improve public resources, PriorPacks, EvidenceBriefs, diagnostics, explanations, practice resources, and later paid research workflows. Competition does not require purchase.

### Port B — Operations

Use aggregate resource and demand facts for capacity planning, safe prefetch, storage planning, and research-service provisioning. Questions, spend, novelty, or prior alignment never change official exam depth, scientific evidence, queue entitlement, or score.

### Port C — Research allocation

D12 and evidence gaps may inform proposals for replication, transfer tests, disambiguation experiments, coverage work, or future Challenge evolution.

A conceptual planning objective may combine:

```text
scientific uncertainty
+ expected decision value
+ validated research demand
+ transfer breadth
+ reusable evidence value
- total cost
```

Human/governance owners approve live priorities, funding, and any future Challenge changes. Demand is never an emissions or score term.

### Port D — Product and commercial value

Use evidence plus demand to identify Evidence Audit work, sponsored studies, Specialist Bank opportunities, customer programs, and later research-product opportunities. Product qualification remains independent.

## 10. Commercial progression

### Free — Research Concierge

Approved-source reasoning, private threads, evidence gaps, feedback, and approved updates.

### Paid — Research Copilot

After commercial and security qualification, add persistent campaign memory, customer-authorized context, richer approved evidence synthesis, experiment planning, hosted non-official comparisons, quotes, spend ceilings, and campaign reports.

### Later — Research Scientist

After prospective qualification of Landscape models, add transfer/applicability predictions, experiment-value modeling, research-portfolio optimization, and Port C proposal drafting.

Paid value must come from permitted analysis, workflow, research execution, customer context, eligible non-exam evidence, and service quality. Payment cannot unlock protected official evidence or change official grading.

## 11. Runtime source protection

Do not expose raw archive downloads, arbitrary SQL, unrestricted row queries, protected object locators, or request-time private-Landscape access.

Assume any answer received by a client can be cached or copied. Security and disclosure review must therefore survive a miner storing the entire permitted transcript and combining it with public priors, EvaluationCards, leaderboards, versions, prices, errors, and timing.

## 12. Resource isolation

Official evidence capture receives reserved resources and independent failure protection.

Qualification must saturate shared infrastructure across:

- database pools and locks;
- object-store throughput;
- network quotas;
- queue capacity;
- KMS/key service;
- CPU/GPU pools;
- caches;
- observability backends.

Dialogue, analytics, or paid-research overload must not cause required official evidence loss. Where guarantees cannot be preserved, non-essential planes degrade first or official finalization fails closed.

## 13. Paid-pilot preregistration

Before implementing the paid execution workflow, freeze pilot measurements for:

- research utility versus a relevant matched-spend baseline;
- time and total cost to useful research decisions;
- quote-to-purchase conversion;
- repeat campaigns;
- miner-funded versus external-customer demand;
- direct contribution after compute, truth/reference, storage, inference, curation, payment, and support;
- leakage/security results;
- effect on the health of the free research path.

Do not select success criteria after observing pilot results.

## 14. Value-maximization loops

The architecture should support these compounding loops:

```text
questions -> gaps -> funded experiments -> evidence -> approved guidance -> better answers

guidance -> action -> measured outcome -> guidance evaluation -> better guidance

customer-funded study -> reusable rights-approved evidence -> catalogue/brief -> future revenue

repeated failure demand -> Port A resource / Port C study / Port D product opportunity
```

The long-run strategic asset is:

```text
WHAT CARBON HAS LEARNED
+
WHAT RESEARCHERS NEED TO LEARN
+
WHICH INTERVENTIONS HELP THEM LEARN IT
```

## 15. Authority and maturity

This specification creates implementation direction only. It does not establish scientific qualification, security acceptance, launch readiness, customer rights, pricing, paid traction, production deployment, LIVE authority, frontier status, settlement, weights, or emissions.

Implementation sequencing is owned by `Build_Out.md` and the owner-approved wave plan under `.agent/plans/`.

## 16. Timing and dependency rulings

1. `C-DC2/3` capture purpose-permitted question/demand observations at launch; `E-D12` later aggregates, clusters, protects against manipulation, and routes planning.
2. `C-DC2/3/4` include source versions, response dependencies, withdrawal rechecks, and linked correction/update delivery. `E-EA7` later adds transitive source-to-model-to-deliverable propagation.
3. The launch Concierge uses approved bootstrap/public resources and authorized PriorPacks. Learned official-derived EvidenceBriefs remain behind `E-EB1`/`E-EA6`; there is no circular launch dependency on Landscape.
4. Real execution evidence is captured before qualification and preserves its original status. Retention is not conditional on later learning/release eligibility.
5. Learned release candidates are frozen and tested privately against prospective evidence under `E-RI1` before activation; approval evidence does not require an unapproved public release.
6. C0/C1/C2 and D→H→I remain the launch-critical network/science/economic sequence. E/F/G proceed later in parallel and do not gate H/I.

## 17. Change log

- **2026-09-08 / v1.1:** materialized the 21 passive implementation tickets; integrated the full v0.3 package into exact archive, dialogue/demand/correction, paid-research, traceability, acceptance, owner-decision, and handoff contracts; recorded package-to-repository mappings and packaging conflicts. No runtime or active selection changed.
