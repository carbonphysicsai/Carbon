# Carbon Physics Intelligence System

**Status:** SPECIFIED — architecture-hardening contract; not evidence of implementation, testing, or production qualification  
**Scope:** cross-cutting semantics discovered through the scientific-reference canon audit  
**Applies with:** `Miner_MCP.md`, `Trustless_Verification.md`, `Landscape_Agent.md`, `Specialist_Bank.md`, `Scoring.md`, `Build_Out.md`, `Launch_Bar.md`

---

## 0. Purpose and authority

Carbon is designed as an **incentivized physics-intelligence system**:

```text
hypothesis generation
        ↓
protected independent evaluation
        ↓
structured experimental evidence
        ↓
experimental memory
        ↓
controlled learning
        ↓
better search / better experiments
        ↓
evidence-bounded qualification
```

This document adds six cross-cutting design requirements that were not fully explicit in the earlier specifications:

1. evaluation-information governance;
2. Challenge evaluation-health / exhaustion monitoring;
3. machine-readable epistemic types for Landscape;
4. Port C information-value experiments separated from performance scoring;
5. retention of scientifically informative failures;
6. qualification as a lifecycle with escalation evidence.

It also ratifies two system invariants:

> **Landscape proposes. Registered contracts decide. Independent experiments adjudicate.**

> **Do not collapse performance, novelty, information value, causal confidence, and commercial value into one score.**

### 0.1 Domain ownership

This document is **additive**. It does not replace the current semantic owners:

- `Miner_MCP.md` remains authoritative for miner-facing disclosure and free/paid loop behavior.
- `Trustless_Verification.md` remains authoritative for official hidden evaluation and seeding.
- `Scoring.md` remains authoritative for `S_combined`, hard gates, and forbidden score inputs.
- `Landscape_Agent.md` remains authoritative for the four-port intelligence layer.
- `Specialist_Bank.md` remains authoritative for commercial promotion and Product Battery semantics.
- `Build_Out.md` remains sequencing authority.

Where this document introduces a new cross-cutting requirement, downstream implementation must preserve the existing domain owner's semantics and add the new invariant rather than silently overriding the owner.

---

# 1. Scientific-system doctrine

Carbon's scientific object is not only the winning model. It is the **intervention-outcome record** produced by independently controlled evaluation.

The system should therefore optimize for three distinct outputs:

1. **Models** — performant, reproducibly trainable candidates.
2. **Evidence** — provenance-rich measurements of successes and failures.
3. **Intelligence** — accumulated understanding that improves future search, experiment selection, and qualification.

These outputs are related but must not be conflated.

### 1.1 Three nested loops

```text
LOOP 1 — DISCOVERY
agents → strategies → protected exam → reward

LOOP 2 — SCIENCE
experimental memory → uncertainty → targeted experiments → stronger knowledge

LOOP 3 — ENGINEERING
candidate → qualification → deploy / escalate → lifecycle evidence → reassess
```

All three may eventually contribute evidence to Landscape, subject to disclosure, privacy, scientific-validity, and provenance rules.

---

# 2. Evaluation information is a governed scientific resource

## 2.1 Rationale

Official evaluation is repeatedly queried by adaptive miners and agents. Even when no seed or sample is leaked, repeated scores, diagnostics, rankings, priors, and other outputs can cumulatively reveal information about the protected exam.

Therefore hidden-evaluation safety is not only a secret-management problem. It is also an **adaptive information-governance problem**.

## 2.2 Evaluation Information Budget

Each LIVE Challenge version must have a versioned **Evaluation Information Policy** describing the miner-visible and public information surfaces that may disclose information about official evaluation.

The policy must account for at least:

- EvaluationCard fields and precision;
- leaderboard fields and update cadence;
- failure tags / diagnostics;
- component-score granularity;
- prior-pack contents, noise, lag, and cadence;
- MCP tools that expose challenge-relative signals;
- mock-pack relationship to the official envelope;
- future Landscape Port A outputs;
- any public aggregate derived from official Model Cards.

The budget is a **policy and audit concept**, not a single universal scalar threshold.

No agent may invent a production information budget or leakage threshold. Human protocol/security owners set and approve the live policy.

## 2.3 Required semantics

1. Every public/miner-facing evaluation surface is allow-listed and versioned.
2. Raising granularity is an explicit policy revision, not an incidental API change.
3. New miner-facing Landscape outputs must be included in the Challenge's disclosure analysis before publication.
4. Raw official seeds, draw IDs, reversible identifiers, private per-case breakdowns, and other directly reconstructive fields remain forbidden regardless of budget.
5. Practice/free surfaces must remain scientifically honest inside their
   declared scope. Security review measures incremental inference of protected
   official realizations, mixtures, margins, and unresolved ordering after
   controlling for performance on evaluator-held shadow cases from the declared
   distribution. Transferable physics improvement is allowed.
6. Historical results remain bound to the disclosure/evaluation policy under which they were generated.

## 2.4 Audit object

The architecture should support an internal record such as:

```text
EvaluationInformationPolicy {
  policy_version,
  challenge_version,
  evaluation_card_tier,
  score_precision_policy,
  leaderboard_policy,
  prior_policy_version?,
  mock_policy_version,
  public_aggregate_policy?,
  landscape_port_a_policy?,
  approved_by,
  approved_at,
  notes
}
```

This is a governance/provenance object. Exact production fields may be refined during implementation.

---

# 3. Challenge evaluation health and exhaustion

## 3.1 Principle

A Challenge can remain physically valid while becoming less useful as a discriminating hidden exam because the participant population has adaptively specialized to information accumulated over time.

Carbon therefore distinguishes:

- **scientific validity** — the generator/envelope still represents the claimed physics;
- **evaluation health** — the protected exam still discriminates useful physics
  improvements while resisting incremental inference of its protected realized
  cases, mixtures, margins, and unresolved ordering.

## 3.2 Evaluation-health telemetry

The system may monitor evidence such as:

- score/rank saturation;
- population convergence;
- declining strategy diversity;
- declining discrimination between frontier strategies;
- incremental protected-realization inference after controlling for
  evaluator-held shadow-case physics performance;
- diagnostic / disclosure accumulation;
- suspiciously stable exploitation of known feedback surfaces;
- repeated Challenge-specific failure modes no longer separating methods.

These are **signals**, not automatic scientific truth.

## 3.3 Exhaustion state

A Challenge version may eventually be flagged internally as:

- `healthy`;
- `review_recommended`;
- `refresh_required`;
- `retired`.

No numeric transition rule is specified here. Production thresholds and transition authority require human protocol/scientific approval.

A refresh may include a new Challenge version, generator/version change, mock-policy change, disclosure-policy change, or other registered prospective change.

**Never silently mutate a live scientific contract.** Historical results remain attached to the original Challenge version.

---

# 4. Experimental memory retains failures, not only winners

## 4.1 Principle

The scientifically valuable dataset is not the leaderboard. It is the intervention-outcome graph.

A reproducibly weak or failed strategy can provide information about:

- brittle architecture/loss interactions;
- regime-specific collapse;
- rollout instability;
- conservation failure;
- sensitivity to training budget;
- Product Battery failure modes;
- dead or redundant search dimensions.

Therefore evidence retention must not be rank-biased.

## 4.2 Retention rule

Subject to storage/privacy policy, Launch-Bar eligibility, and evidence integrity, Landscape ingestion should preserve eligible official outcomes across the score distribution, including:

- successful frontier runs;
- ordinary passing runs;
- gate failures attributable to strategy/model behavior;
- reproducible training failures with scientific meaning;
- Product Battery promotion failures;
- later qualification/requalification failures.

Infrastructure failure remains distinct and must not be interpreted as negative scientific evidence.

## 4.3 Evidence quality

A failed result is not automatically useful. Landscape may assign evidence-quality metadata based on provenance completeness, reproducibility, execution validity, and sample support.

Failure retention does **not** create an emissions reward for failing. Scientific information value and subnet performance reward remain separate mechanisms.

---

# 5. Landscape requires an epistemic type system

## 5.1 Problem

Miner strategies are selected adaptively and non-randomly. Observational relationships in Model Card history can be predictive without being causal.

Landscape must therefore store and communicate the epistemic status of learned relationships.

## 5.2 Minimum epistemic types

Landscape knowledge objects should support at least:

| Type | Meaning | Permitted language |
|---|---|---|
| `observed` | Relationship exists in recorded history | "co-occurred", "associated" |
| `predictive` | Relationship predicts held-out outcomes under stated evaluation | "predicts", "associated with future outcome" |
| `causal_candidate` | Effect is plausible under stated identification assumptions | "candidate intervention", "estimated effect under assumptions" |
| `experimentally_supported` | Designed intervention provides stronger evidence | "supported by registered experiment" |

A future `mechanistically_supported` type may be added where an experimentally supported effect also has domain-scientific mechanistic evidence. It is not required for initial Landscape implementation.

## 5.3 Promotion rules

Epistemic status must never be upgraded solely because an effect is large, popular, commercially useful, or repeatedly published by Landscape.

Promotion between epistemic types requires explicit evidence criteria owned by the Landscape specification and, where scientific judgment is required, human approval.

## 5.4 Public-language invariant

No public or miner-facing system may present an `observed`, `predictive`, or `causal_candidate` object with gate-level certainty.

> **Carbon applies its own verification standard to its own intelligence layer.**

---

# 6. Performance market and information market are separate

## 6.1 Performance market

The ordinary subnet score/emissions mechanism rewards performance under the registered scientific contract.

`Scoring.md` remains authoritative. Information value, novelty, causal confidence, Landscape similarity, and commercial product value do **not** become implicit terms in `S_combined` unless Scoring is explicitly changed through governance.

## 6.2 Information-value experiments

Port C may eventually propose **targeted research bounties or Challenge variants whose purpose is information gain**, for example:

- discriminate between two plausible explanations of robustness improvement;
- populate a poorly covered strategy region;
- test whether an apparent effect transfers across regime or backbone;
- reproduce a high-value but low-support effect;
- investigate a recurring Product Battery failure mode.

The objective of such a bounty is not "score novelty". It is to purchase a registered experiment whose outcome reduces an important uncertainty.

## 6.3 Governance boundary

Landscape may rank or propose information-value opportunities. It may not autonomously:

- alter live scoring;
- create LIVE Challenge scientific thresholds;
- redirect production emissions without authorized governance;
- certify a causal claim because the proposed experiment was run.

> **Landscape proposes. Registered contracts decide. Independent experiments adjudicate.**

---

# 7. Diversity is valuable, but novelty is not a score term

Open competition creates value partly by exploring multiple hypotheses. Excessive population convergence can reduce the information content of the experimental record.

Carbon should therefore measure search diversity for scientific-system health, but should not casually reward novelty inside the official score.

Potential future uses of diversity evidence include:

- Port C bounty design;
- Challenge-health review;
- search-space coverage reporting;
- prioritization of reproduction experiments;
- identifying underexplored strategy families.

Similarity/novelty remains forbidden as a hidden scoring term under the current scoring design.

---

# 8. Reproducibility is a property of the method

Independent retraining is not only an anti-cheating device. It measures whether a submitted method's advantage survives transfer of execution authority.

The evidence layer should therefore preserve, where available:

- strategy hash and schema version;
- exact evaluation pin;
- environment/container digest;
- resource-limit snapshot;
- framework/dependency versions required by the execution contract;
- random-seed roles / run identifiers without exposing protected official seed material;
- repeated-run dispersion where a registered protocol performs multiple retrains.

A future registered protocol may use repeated independent retraining to measure dispersion/reliability of a strategy. No universal repeat count or variance threshold is specified here.

---

# 9. Qualification is a lifecycle, not a one-time certificate

## 9.1 Lifecycle

The commercial path should be modeled as:

```text
qualify
  ↓
deploy
  ↓
observe / escalate
  ↓
new evidence or material change
  ↓
reassess
  ↓
requalify / restrict / retire
```

The original Qualification Record remains immutable evidence of what was demonstrated under its original context of use.

## 9.2 Reassessment triggers

A specialist may require reassessment when, for example:

- model weights or training recipe materially change;
- deployment runtime/hardware changes in a qualification-relevant way;
- input/output interface changes;
- intended context of use expands;
- new failure evidence appears;
- customer operating distribution materially shifts;
- Product Battery policy changes prospectively;
- a security or reproducibility issue invalidates part of the evidence chain.

No universal trigger thresholds are specified here.

## 9.3 Escalation evidence

A qualified specialist should have an explicit route back to higher-fidelity truth or engineering review when its context-of-use boundary is reached.

Where customer contracts, privacy controls, and provenance permit, de-identified/authorized escalation outcomes may become lifecycle evidence for:

- context-of-use refinement;
- new stress categories;
- Product Battery evolution;
- requalification decisions;
- sponsored Challenge design.

Customer data or escalation telemetry must never be assumed available to Landscape. Collection requires explicit product/privacy policy and appropriate consent/contractual authority.

## 9.4 Product-status semantics

Recommended lifecycle states include:

- `candidate`;
- `qualified`;
- `restricted`;
- `requalification_required`;
- `retired`.

Exact state-machine implementation belongs to `Specialist_Bank.md` / product implementation tickets.

---

# 10. Intervention-outcome graph as the compounding asset

Carbon's durable experimental asset is intended to become a provenance-rich graph linking:

```text
strategy intervention
        ×
physical regime
        ×
execution environment
        ×
hidden physics/stress outcome
        ×
reproducibility evidence
        ×
product qualification outcome
        ×
optional authorized lifecycle evidence
```

This graph is not automatically causal. Its value comes from preserving enough provenance and epistemic status to support better predictions and to identify where controlled experiments are worth buying.

The graph is private by default. External publication follows the relevant disclosure tier and information policy.

---

# 11. Implementation ordering

This specification does **not** reorder the current Wave A/B/C/D sequence in `Build_Out.md`.

## 11.1 P0-compatible hooks

The following can be added without building full Landscape:

- versioned evaluation/disclosure policy identifiers on Challenge/EvaluationCard provenance;
- structured observability for disclosure policy and Challenge-health inputs;
- card-store retention semantics that do not discard scientifically valid failures merely because they rank poorly;
- schema space for epistemic status on future Landscape artifacts;
- explicit separation of infrastructure failure from negative scientific evidence.

These hooks must not block P0 unless the existing semantic owner already requires them.

## 11.2 Post-P0 Landscape work

- L0: ingest full eligible score distribution; evidence-quality metadata; disclosure lineage.
- L1: failure atlas and Challenge-health analytics.
- L2: epistemic type system, predictive/causal-candidate promotion criteria.
- L3: Port C information-value opportunity proposals; validator-private health signals under existing Port B floors.
- L4+: experimentally supported effects, Product Battery/lifecycle feedback, controlled information-market experiments.

## 11.3 Product work

Specialist implementation should add qualification lifecycle states, reassessment triggers, immutable historical Qualification Records, and optional authorized escalation-evidence ingestion.

---

# 12. Required tests and audits when implemented

Implementation tickets derived from this specification should include, where applicable:

1. miner-facing output cannot bypass the registered disclosure allow-list;
2. policy-version changes are explicit and historically attributable;
3. Challenge refresh never silently rescored historical results;
4. infrastructure failures never enter the negative scientific-evidence corpus;
5. low-ranked/gate-failed scientific results remain ingestible when provenance is valid;
6. epistemic type cannot be silently upgraded by publication/rendering code;
7. `causal_candidate` cannot render as "proven cause";
8. Port C information-value fields never enter `S_combined` or emission weight calculation;
9. Landscape cannot mutate a registered Score Pack or Challenge version;
10. qualification status changes do not mutate historical Qualification Records;
11. escalation telemetry is opt-in/authorized and cannot leak customer-sensitive data;
12. mock/free paths remain isolated from official protected evaluation.

---

# 13. Explicit non-claims

This design does not claim that:

- a universal evaluation-information budget is known;
- a universal Challenge-exhaustion threshold is known;
- diversity automatically improves scientific performance;
- Landscape observational estimates are causal;
- Port C can measure true information gain perfectly;
- decentralized search will outperform centralized research;
- qualification guarantees universal safety or correctness;
- customer escalation data will be available for learning;
- repeated retraining dispersion should already be an emissions term.

Those remain testable research/product questions, not ratified scientific truths.

---

# 14. Thesis

Carbon should preserve a clean separation of functions:

```text
Subnet score        → demonstrated scientific performance
Port C / bounties   → targeted information acquisition
Landscape           → private physics intelligence
Product selection   → commercial opportunity
Qualification       → bounded engineering credibility
Lifecycle evidence  → reassessment / future research input
```

Trying to compress all of these values into one score would weaken interpretability, create Goodhart surfaces, and blur scientific authority.

The intended compounding loop is instead:

> **Economic competition produces controlled experiments. Controlled experiments produce evidence. Evidence becomes physics intelligence. Physics intelligence improves what Carbon searches, tests, and qualifies next — while physics remains the external authority that no internal learning layer can vote away.**
