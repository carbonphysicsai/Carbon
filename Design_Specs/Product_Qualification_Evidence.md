# Carbon Product Qualification Evidence Specification

**Status:** Normative architecture extension — proposed for team review  
**Scope:** Post-subnet product evidence, Product Battery records, bounded qualification claims, specialist packaging, requalification lifecycle  
**Authority:** This document owns the product-plane evidence object model. `Specialist_Bank.md` continues to own candidate selection, Product Battery execution, banking, packaging, and commercial egress. `Evaluation_Evidence_and_Validator_Audit.md` owns official subnet execution evidence and EvaluationReceipts. Product qualification does not alter lean scientific scores or emissions.

---

## 1. Objective

Carbon's product path must turn independently evaluated scientific search into a complete, inspectable evidence trail without exposing the private knowledge, recipes, hidden draws, or reconstruction-sensitive material that constitute Carbon's security boundaries and commercial moat.

The product-plane evidence system therefore separates:

1. **measurement** — what was built and what happened when it was evaluated;
2. **job-shaped testing** — what happened when the product candidate faced the applicable Product Battery;
3. **qualification judgment** — the bounded engineering claim justified by that evidence; and
4. **commercial packaging** — the deployable artifact and private materials delivered under the applicable license/control boundary.

Core doctrine:

> **Carbon does not ask a buyer to trust the model. Carbon exposes the evidence for the bounded claim.**

And:

> **Every claim has an object. Every object has provenance. Every qualification has a scope. Every scope has an edge.**

This is an evidence architecture, not a regulatory-certification claim.

---

## 2. Product evidence object model

The canonical product lineage is:

```text
Winning / selected strategy
        ↓ candidate lineage only
Fresh controlled product retrain
        ↓
Product Candidate Model Card
        ↓
Product Battery execution
        ↓
Product Battery Record
        ↓
Qualification decision
        ↓
Qualification Record
        ↓
Qualified Specialist package
```

The competition Model Card is historical evidence about the subnet evaluation. It is never mutated into a product certificate.

### 2.1 One materially distinct trained artifact → one Model Card

A fresh product retrain creates a materially distinct trained artifact and therefore MUST create its own Model Card.

The Product Candidate Model Card:

- identifies the exact trained product candidate artifact;
- records lineage to the source strategy and relevant prior evidence;
- records the controlled retraining identity and applicable fresh scientific evaluation evidence;
- is immutable after finalization except through append-only correction/supersession semantics;
- MUST NOT overwrite or reinterpret the competition Model Card;
- is not itself proof that the candidate is commercially qualified.

`Product Candidate Model Card` is a role of the Model Card, not necessarily a separate schema family. Implementations SHOULD reuse the canonical Model Card schema with explicit artifact role, lineage, and product-evidence references where practical.

### 2.2 Product Battery Record

Every product qualification attempt MUST produce an immutable, versioned `ProductBatteryRecord`, including failed attempts.

The record commits to:

```text
product_battery_record_schema_version
product_battery_record_id
candidate_model_artifact_hash
product_model_card_id
source_strategy_hash / lineage references

product_battery_id
product_battery_version
product_battery_pack_hash
context_of_use_id / version
execution_profile_id / environment identity as applicable

module_results[]
mandatory_module_verdicts[]
overall_battery_status
known_failure_observations
started_at
finished_at
issuer / evaluator identity
signature / commitment
```

The exact scientific pass criteria remain owned by the applicable Product Battery / regime policy and require human scientific approval where the repository requires it. This specification defines evidence structure, not scientific thresholds.

Rules:

1. Failed Product Battery attempts are evidence and MUST NOT be deleted merely because a later attempt passes.
2. A new attempt creates a new record; historical records remain attributable to their original candidate, battery version, context of use, and execution identity.
3. Product Battery results never enter the lean subnet score or emissions calculation.
4. Reconstruction-sensitive Product Battery inputs may remain controlled. The record exposes only the disclosure tier authorized for the buyer/public surface.

### 2.3 Qualification Record

A `QualificationRecord` is the canonical machine-readable product-plane claim object.

It states that a **specific model artifact** satisfied a **specific versioned qualification policy/Product Battery** for a **specific declared context of use**, subject to explicit limitations and requalification conditions.

It references underlying evidence rather than duplicating or rewriting it.

Minimum semantic fields:

```text
qualification_record_schema_version
qualification_record_id

candidate_model_artifact_hash
product_model_card_id
product_battery_record_id
source_lineage_refs[]

context_of_use_id
context_of_use_version
intended_job_class
validity_envelope_ref
qualification_policy_id
qualification_policy_version

qualification_status
qualified_claims[]
known_limitations[]
escalation_conditions[]
requalification_triggers[]

evidence_refs[]
issued_at
issuer_identity
issuer_signature

supersedes_qualification_record_id   # optional
```

A Qualification Record MUST NOT claim more than the underlying evidence and context of use support.

It MUST NOT be called regulatory certification unless an applicable external certification process has actually been completed and the claim is legally/scientifically justified.

### 2.4 Qualified Specialist

A full commercial `Qualified Specialist` is a package, not merely a checkpoint.

Conceptually it contains or references:

```text
Qualified Specialist
├── deployable model artifact
├── deployment / I-O specification
├── Product Candidate Model Card
├── Product Battery Record
├── Qualification Record
├── supporting evidence references
├── version / dependency identity
└── license and delivery controls
```

Private recipe material, proprietary implementation detail, raw hidden draws, reconstruction-sensitive diagnostics, and other moat-bearing information need not be public merely because the qualification claim is transparent.

**Transparent evidence does not require transparent secret material.** Carbon exposes enough to audit the claim while preserving controlled evidence and commercial know-how behind explicit access boundaries.

---

## 3. Claim/evidence separation

Carbon MUST preserve the distinction between observations and judgments.

| Artifact | Primary question | Semantics |
|---|---|---|
| Model Card | What was built and what happened during evaluation? | Factual scientific/provenance record |
| Product Battery Record | What happened under the job-shaped qualification suite? | Factual qualification-test record |
| Qualification Record | What bounded claim is justified by those records? | Versioned qualification judgment |

This separation permits qualification policy to evolve without rewriting historical measurements.

If a future policy requires additional tests, historical Model Cards and Product Battery Records remain true records of what occurred. A new qualification decision references new evidence and may supersede an older Qualification Record without deleting it.

---

## 4. Qualification is bounded and revocable prospectively, not erasable historically

A qualification is never a permanent universal badge.

The qualification state machine MUST support explicit lifecycle semantics. The final enum is implementation-owned by the ratified schema, but it MUST be able to distinguish at least:

- a currently qualified claim;
- a failed/not-qualified attempt;
- a qualification that has been superseded by a newer record;
- a qualification requiring requalification before further qualified use;
- a qualification that is no longer current under its governing validity policy.

If `SUSPENDED`, `CONTESTED`, or other states are adopted, their semantics MUST be explicitly specified rather than inferred.

Historical qualification records remain immutable. A change in current status creates a new signed record or append-only status event linked to the original record; it does not rewrite the original decision.

---

## 5. Requalification triggers

Every qualification policy MUST declare which material changes require requalification. The exact triggers are context-dependent and human-owned where scientific judgment is required.

Trigger classes SHOULD cover, where applicable:

- model weights or trained parameters;
- model architecture or operator semantics;
- preprocessing or postprocessing affecting the scientific mapping;
- numerical precision or execution backend where qualification depends on it;
- deployment runtime/export path where parity is part of the claim;
- operating/physics envelope expansion;
- customer adaptation, fine-tuning, LoRA, calibration, or other parameter changes;
- Product Battery or qualification-policy changes designated as requalification-relevant;
- newly discovered failure modes that invalidate the current context-of-use claim;
- dependency or environment changes material to the qualified behavior.

A requalification trigger does not imply the prior evidence was false. It means the prior evidence no longer establishes the current artifact/claim without additional testing.

---

## 6. Escalation is part of the product claim

For engineering use, a validity envelope without an escalation rule is incomplete.

The Qualification Record MUST reference explicit escalation conditions appropriate to the context of use. These may identify conditions under which the surrounding workflow should:

- reject the surrogate query;
- request higher-fidelity simulation;
- require human review;
- switch to another qualified model/regime;
- or otherwise leave the surrogate path.

The exact conditions are Product Battery/context-of-use science and MUST NOT be invented by implementation agents.

Carbon's product claim is therefore not "this model is trustworthy." It is:

> **This artifact qualified for this bounded use under this versioned evidence, with these limitations, and these are the conditions under which that claim no longer applies.**

---

## 7. Disclosure tiers and moat preservation

Product transparency MUST follow allow-listed disclosure, not indiscriminate publication.

At minimum, the architecture distinguishes:

### Public / catalog surface

May expose a safe projection such as:

- specialist identity/version;
- broad context of use;
- qualification status and governing policy version;
- non-sensitive validity-envelope description;
- evidence/commitment identifiers;
- high-level limitations;
- qualification lineage sufficient to establish provenance without reconstructing protected exams.

### Buyer / controlled diligence surface

May expose additional evidence needed for engineering review under commercial/confidentiality controls, including richer Product Battery results, Model Card material, deployment parity evidence, and context-of-use detail.

### Private Carbon / authorized audit surface

May retain exact recipes, full internal Model Cards, raw or fine-grained Product Battery diagnostics, protected seeds/draw material, execution transcripts, proprietary Landscape outputs, and other reconstruction-sensitive or moat-bearing information.

No disclosure tier may expose official hidden evaluation material merely to make a marketing claim look more transparent.

The strategic principle is:

> **Open the claim and its provenance; disclose the evidence appropriate to the audience; keep the answer key and proprietary recipe controlled.**

---

## 8. Evidence commitments and append-only lineage

Product evidence SHOULD reuse Carbon's existing commitment/evidence primitives where practical.

Requirements:

- Model Card, Product Battery Record, Qualification Record, and deployable artifact identities must be cryptographically bindable to one another;
- qualification must reference exact evidence versions rather than mutable URLs or names alone;
- finalized qualification records should be append-only and suitable for inclusion in Carbon's evidence ledger/checkpoint system;
- corrections and supersession preserve historical records;
- public commitments MUST NOT make hidden draws or protected recipes reconstructable.

The product evidence graph should support a reviewer tracing:

```text
qualified claim
  → qualification policy/version
  → Product Battery Record
  → exact product candidate Model Card
  → candidate artifact
  → source strategy / prior evidence lineage
```

without requiring access to every private node in that graph.

---

## 9. Failure evidence is an asset

Failed qualification attempts are high-value scientific evidence.

They SHOULD feed the private Landscape/product evidence graph subject to decontamination and disclosure rules. Examples include:

- which Product Battery module failed;
- which context-of-use condition exposed the failure;
- adversarial hole classes;
- rollout failure classes;
- export/runtime parity failures;
- escalation-boundary discoveries.

Failure evidence MUST NOT silently change a live subnet Score Pack or retroactively alter historical scientific scores. It may inform future validated Challenge versions, future Product Batteries, search priors, and candidate selection.

---

## 10. Commercial and scientific independence

Qualification status, product purchase, buyer identity, commercial fees, and Specialist Bank status MUST NOT enter lean scientific scoring or Bittensor emissions.

Likewise, subnet rank MUST NOT bypass product qualification.

This preserves both directions of independence:

- commercial success cannot buy scientific score;
- scientific rank cannot buy a commercial qualification claim.

---

## 11. Required crosswalks

When this specification is ratified, the following documents should reference these semantics rather than redefining them independently:

- `Design_Specs/Specialist_Bank.md` — Product Battery pipeline and Qualified Specialist packaging;
- `Design_Specs/Evaluation_Evidence_and_Validator_Audit.md` — shared evidence/commitment primitives and separation from subnet EvaluationReceipts;
- `docs/context/Decisions.md` — ratified product-evidence decisions;
- `docs/context/Implemented_vs_Specified` — explicit implementation status;
- `Design_Specs/Build_Out.md` / protocol extension — implementation sequencing for schemas, signing, storage, disclosure projections, lifecycle, and tests;
- public litepaper — explanation only; never normative.

---

## 12. Non-negotiable invariants

1. **Competition Model Card ≠ product qualification.**
2. **Fresh product retrain → fresh Product Candidate Model Card.**
3. **Product Battery evidence is immutable and failed attempts remain evidence.**
4. **Qualification Record references evidence; it does not rewrite measurements.**
5. **Qualification is artifact-specific, context-of-use-specific, policy-version-specific, and bounded.**
6. **Material adaptation requires requalification when the governing policy says it does.**
7. **Qualification history is append-only; supersession does not erase prior records.**
8. **Product transparency follows disclosure tiers and never leaks hidden evaluation material or proprietary recipe material by default.**
9. **No rank/checkpoint bypasses Product Battery qualification.**
10. **No product/commercial signal enters lean scientific score or emissions.**
11. **No implementation agent invents scientific thresholds, contexts of use, or qualification criteria.**
12. **A Qualification Record is an evidence-backed bounded claim, not an unqualified assertion of safety, correctness, or regulatory certification.**
