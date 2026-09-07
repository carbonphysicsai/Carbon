# OWNER-EVIDENCE-RESEARCH-01 — Official Evidence Intelligence and Agent Research Implementation Plan

**Status:** OWNER-APPROVED FUTURE IMPLEMENTATION PLAN  
**Selected now:** no — does not change the current Wave B selected ticket  
**Design authority:** `Design_Specs/Evidence_Intelligence_and_Agent_Research.md`  
**Sequencing authority:** `Design_Specs/Build_Out.md` + controlling wave board when each wave activates

## 1. Owner decision

Carbon will implement durable official evidence capture, launch-time agent communication, research-demand intelligence, staged paid research, and later advanced research intelligence as part of the repository's existing wave structure.

The plan must be structurally ready before real workloads generate evidence or launch-time agent demand that Carbon cannot recover later.

The implementation must preserve existing scientific, security, disclosure, rights, settlement, and LIVE boundaries.

## 2. Wave placement

### Wave C — capture + authenticated launch communication

Wave C owns the production-facing foundations required before first authenticated external miner launch.

#### C-EA0 — Evidence capture contract

Define production `EvidenceCaptureProfile`, archive states, custody, retention classes, source/attempt binding, required artifacts, missingness, and archive acknowledgement semantics.

**Depends on:** current official execution/evidence owners.  
**Done when:** source classes and durability preconditions are exact enough to implement without inventing scientific or rights policy.

#### C-EA1 — Durable evidence archive

Implement catalogue metadata, immutable artifact persistence, source/result references, availability manifests, idempotent attempt/event identity, and transactional outbox.

**Done when:** acknowledged required evidence survives the approved storage/recovery fault model and cannot be silently overwritten.

#### C-EA2 — Official orchestration integration

Integrate archive-before-finalization into the official execution path without creating a second submission/result lifecycle.

**Invariant:** completed official result finalization requires the approved archive commit.  
**Done when:** retries, crashes, duplicate delivery, and publication failure do not rerun science or lose required evidence.

#### C-EA3 — Recovery and evidence-availability qualification

Restore catalogue, objects, encryption/key access, manifests, and source bindings; reconcile admitted attempts and orphaned artifacts.

**Done when:** declared restore/fault drills pass and missing required evidence blocks finalization rather than degrading silently.

#### C-DC1 — Dialogue authority and authenticated protocol

Define a separately versioned agent-dialogue capability with bounded request/response classes, private thread identity, source policy, permissions, and rate/resource controls.

**Done when:** the service can coexist with existing official and research namespaces without gaining their authority.

#### C-DC2 — Durable threaded interaction store

Implement idempotent question intake, immutable message/response history, tenant/requester isolation, preferences, retention, subscriptions, and recovery.

#### C-DC3 — Launch Research Concierge

Implement intent classification, Approved Knowledge Layer retrieval, source-grounded reasoning, claim/source verification, explicit `INSUFFICIENT_EVIDENCE`, research-gap capture, feedback, and safe follow-up.

The model is replaceable. Deterministic code owns authentication, source authorization, persistence, tool permissions, disclosure policy, tenant isolation, and spend authority.

#### C-DC4 — Launch communication security / resource isolation

Test cross-tenant denial, prompt injection, repeated-query extraction, protected-state independence, dialogue kill switch, restart behavior, and saturation of shared DB/storage/network/KMS/queue/cache/telemetry resources.

**Hard gate:** dialogue load cannot cause required official evidence loss or change official scientific treatment.

### Wave D — LIVE activation boundary

Wave D does not build the archive or Concierge. It decides whether the exact Challenge and external surfaces meet their existing LIVE/Launch-Bar requirements.

For launch-time comms, Wave D additionally requires that C-DC1 through C-DC4 are in their required production-qualified state before the owner advertises the Concierge as a live miner research service.

Dialogue failure remains independent from scoring/evaluation failure.

### Wave E — Landscape intelligence + D12 + approved EvidenceBriefs

Wave E extends the existing Landscape lane.

#### E-EA4 — Scientific archive views

Create versioned research snapshots with provenance, executed/unexecuted masks, intervention differences, lineage/dependence, permissions, units/context, and contradictions.

#### E-EA5 — Landscape evidence learning

Build searchable evidence, failure atlas, comparable cohorts, transfer views, prospective predictive tools where qualified, and Port B/C/D consumers under existing Landscape authority.

#### E-EB1 — EvidenceBrief pipeline

Implement offline candidate construction, exact source lineage, eligibility, counterevidence, epistemic labels, disclosure/rights review, activation, withdrawal, and immutable serving.

The live Concierge reads only approved EvidenceBriefs, not private Landscape state.

#### E-D12 — Research Demand Ledger and Demand Graph

Implement permission-eligible coarse demand observations, `ResearchGap` lifecycle, clustering, manipulation controls, commercial-funnel distinctions, and demand-to-research lineage.

D12 is private by default and never a score/emission input.

#### E-EA6 — Release bridge

Bind Landscape-derived PriorPacks, EvidenceBriefs, and other approved derivatives to existing cumulative disclosure and release controls.

#### E-EA7 — Correction propagation

Maintain reverse dependency lineage from source evidence through claims, PriorPacks/EvidenceBriefs, Concierge responses, and customer deliverables. Corrections append; historical artifacts remain immutable.

#### E-RI1 — Guidance utility and predictive qualification

Prospectively evaluate Carbon guidance and learned research tools against relevant baselines on future held-out outcomes with correct dependence handling.

No model receives a stronger permitted role from offline fit quality alone.

### Wave F — Specialist Bank

No new product-qualification architecture is added.

Wave F consumes eligible evidence and D12 opportunity signals for candidate selection and repair loops. Research Concierge/Copilot outputs are not specialist qualification evidence by default. Specialist Bank retains fresh reconstruction and Product Battery authority.

### Wave G — paid Research Copilot + customer research

Wave G gains a parallel commercial research lane alongside customer bounds/sponsored challenges.

#### G-PR0 — Paid-pilot preregistration

Freeze utility, demand, economics, support, safety, and free-path-health measurements before implementing paid execution.

#### G-PR1 — Commercial entitlement + quote contract

Implement customer/organization plan, quotas, eligible source classes, exact quote scope, max cost, expiry, rights, cancellation, and authorization.

Interest or declared budget is not spend authority.

#### G-PR2 — Persistent campaign memory

Add tenant-authorized research goals, experiment history, customer context, answer lineage, and update/correction state.

#### G-PR3 — Isolated hosted non-official research

Execute permitted comparisons under a separate non-official evidence class and resource pool. No hosted research result can become official evidence by relabeling.

#### G-PR4 — Billing and spend control

Implement quote acceptance, reservation/debit, idempotent job binding, cancellation/refund semantics, and contribution accounting separate from official fees and settlement.

#### G-PR5 — Paid pilot + commercial decision

Run the preregistered pilot. Measure repeat paid demand, external-customer demand separately from miner-funded spend, research utility, direct contribution, support burden, and leakage/safety.

Expansion requires evidence; business design alone is not traction.

### Post-E/G advanced lane — Research Scientist

Do not pre-activate a new wave solely for this design. When existing sequencing reaches the appropriate post-E/G planning point, reserve bounded advanced tickets for:

- qualified transfer/applicability models;
- experiment-value modeling;
- research-portfolio optimization;
- automated ResearchGap synthesis;
- Port C proposal drafting;
- prospective closed-loop evaluation of Carbon's own research advice.

These capabilities remain planning/decision support and cannot mutate scientific authority.

## 3. Cross-wave value loops

### Demand-to-evidence loop

```text
agent question
-> ResearchGap
-> D12 aggregate demand
-> Port C proposal
-> approved experiment
-> evidence archive
-> Landscape
-> approved PriorPack / EvidenceBrief
-> better future answer
```

### Guidance-effectiveness loop

```text
approved guidance
-> researcher action
-> hosted/authorized measured outcome
-> archive
-> prospective guidance evaluation
-> improved approved guidance
```

### Customer-funded evidence loop

```text
customer gap
-> quoted non-official study
-> paid execution
-> customer result
-> rights-permitted reusable evidence
-> reviewed catalogue / EvidenceBrief
-> future customer value
```

## 4. Acceptance gates

### Capture gate

- every admitted official attempt is accounted for;
- required finalized evidence is retrievable after declared restore scenarios;
- infra/reference/science/early-stop semantics remain separate;
- archive failure cannot silently publish an unrecorded official result.

### Concierge gate

- grounded answer from approved sources;
- unsupported question returns explicit gap;
- private thread survives restart;
- cross-tenant and prompt-injection tests pass;
- protected-state changes do not alter permitted answer availability/content;
- dialogue overload does not affect official evidence guarantees.

### Landscape/D12 gate

- research snapshots preserve provenance, missingness, lineage, and permissions;
- EvidenceBriefs preserve counterevidence and epistemic limits;
- D12 opt-out works and bot volume does not masquerade as independent demand;
- demand cannot affect live scoring, exam depth, or official priority;
- correction propagation identifies affected downstream artifacts.

### Paid gate

- pilot scorecard is frozen first;
- payment cannot unlock protected official information;
- research execution is non-official and isolated;
- spend requires explicit bounded authorization;
- repeat paid demand and contribution are measured rather than inferred.

## 5. Sequencing invariant

This plan is **official future sequencing**, not current ticket selection.

Until `.agent/WAVE.md` activates the relevant wave and its controlling board selects one of these tickets:

- no C/E/G ticket above is active;
- no production/LIVE/commercial authority is granted;
- current Wave B work continues under `.agent/WAVE_B.md` unchanged.

## 6. Owner-reserved decisions

Humans retain final authority over:

- evidence retention/legal/IP terms;
- production durability profile and failure domain;
- LIVE activation;
- disclosure/security acceptance;
- EvidenceBrief public/paid release policy;
- scientific qualification and epistemic promotion criteria;
- Port C funding/economic priorities;
- pricing and commercial terms;
- customer data reuse rights;
- production model selection for Concierge/Copilot/Research Scientist.
