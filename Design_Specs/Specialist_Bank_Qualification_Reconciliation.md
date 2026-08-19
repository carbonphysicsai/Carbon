# Specialist Bank — Product Qualification Evidence Reconciliation

**Status:** Normative reconciliation companion — proposed for team review  
**Scope:** Reconciles legacy Specialist Bank shorthand with `Product_Qualification_Evidence.md` without changing Product Battery science or lean-emission semantics.

## Authority

`Specialist_Bank.md` continues to own candidate selection, Product Battery execution, banking, commercial packaging, and dual egress. `Product_Qualification_Evidence.md` owns the product-plane evidence object model and qualification lifecycle. Where `Specialist_Bank.md` uses older shorthand such as `product-battery certs`, `certified artifact`, `PB report`, or `Model Card + PB`, interpret that shorthand through the canonical evidence chain in this document.

This reconciliation does not invent Product Battery thresholds, contexts of use, scientific acceptance criteria, or regulatory certification claims.

## Canonical product evidence chain

```text
selected strategy / landscape-supported candidate
        ↓ lineage only
fresh controlled product retrain
        ↓
Product Candidate Model Card
        ↓
Product Battery execution
        ↓
Product Battery Record
        ↓
qualification decision under versioned policy
        ↓
Qualification Record
        ↓
Qualified Specialist package
```

A competition Model Card MUST NOT be promoted, mutated, or relabeled into a product qualification artifact. A fresh product retrain produces a materially distinct trained artifact and therefore its own Model Card.

Every Product Battery attempt produces a Product Battery Record, including failed attempts. Negative evidence remains part of the durable record and may feed Landscape decision support under its disclosure rules.

A Qualification Record is the canonical product-plane claim object. It references the candidate Model Card and Product Battery Record rather than duplicating or rewriting them. It states the bounded context of use, validity envelope, applicable qualification-policy identity, known limitations, escalation conditions, requalification triggers, lifecycle state, provenance, and evidence commitments allowed by policy.

A Qualified Specialist is not merely weights or a passing leaderboard entry. It is the deployable artifact plus its current Qualification Record and the evidence/package references required by the applicable commercial policy.

## Specialist Bank terminology reconciliation

The following older phrases in `Specialist_Bank.md` are superseded semantically as follows:

| Legacy shorthand | Canonical meaning |
|---|---|
| `Model Card + product-battery certs` | Product Candidate Model Card + Product Battery Record + Qualification Record |
| `product-battery certs` / `PB certs` | Product Battery Record plus, when qualification succeeds, the Qualification Record; not a regulatory certificate |
| `PB report` | Audience-appropriate projection of the Product Battery Record; the underlying record remains canonical |
| `certified artifact` / `certified weights` | Qualified Specialist under a current Qualification Record; avoid implying external regulatory certification |
| `gate certificate` | Evidence projection/record of the applicable gate results; not a standalone product qualification |
| `closed SKU` | Qualified Specialist commercial package, whose private artifact/recipe may remain licensed and controlled |
| `re-PB after adapt` | Requalification under the applicable policy; historical records remain immutable |
| `refresh/retire on PB regression` | Append-only qualification lifecycle transition or supersession; never rewrite prior evidence |

Future edits to `Specialist_Bank.md` SHOULD use the canonical terms directly.

## Dual egress under the evidence model

Carbon's transparency model is tiered rather than all-or-nothing.

### Public / catalog surface

Carbon SHOULD expose enough to make the bounded claim inspectable without leaking the exam or proprietary know-how. This may include, subject to disclosure policy:

- specialist/version identity;
- qualification status and policy/version identity;
- declared context of use and validity envelope;
- high-level Product Battery coverage and allowed outcomes;
- known limitations and escalation conditions;
- provenance/commitment references that are safe to disclose;
- supersession or requalification state.

### Buyer / controlled diligence surface

Authorized buyers MAY receive deeper evidence projections, detailed Product Battery reports, deployment specifications, artifact hashes, runtime requirements, and other materials needed for technical/procurement review, subject to contract and security policy.

### Private Carbon / authorized audit surface

Raw reconstruction-sensitive exam material, private execution evidence, exact protected recipes, Landscape internals, and other moat/security-sensitive material remain controlled.

The governing doctrine is:

> **Open the claim and its provenance; disclose the evidence appropriate to the audience; keep the answer key and proprietary recipe controlled.**

Transparency therefore means that Carbon makes the scope and basis of a claim inspectable. It does not mean publishing information that would compromise future hidden evaluation or surrender proprietary search knowledge.

## Grounding gate reconciliation

For a full commercial surrogate, `ship_commercial_full_sku` MUST require at minimum:

```text
fresh_product_candidate_model_card
AND required_product_battery_execution_complete
AND product_battery_record_finalized
AND qualification_record_current_and_eligible_for_ship
AND seed/decontamination_policy_ok
AND applicable packaging/license controls satisfied
```

Passing a Product Battery module does not by itself create a qualification claim. Qualification is the policy-governed judgment recorded in the Qualification Record.

No rank, checkpoint, prior Model Card, commercial payment, or Landscape recommendation can bypass this grounding gate.

## Requalification and historical truth

Qualification is a bounded state, not a permanent badge. The governing qualification policy MUST declare material-change and evidence-change conditions that require requalification. Agents and implementations must not invent those scientific conditions.

When requalification occurs:

1. prior Model Cards remain immutable;
2. prior Product Battery Records remain immutable;
3. prior Qualification Records remain historical truth;
4. new evidence produces a new Qualification Record or explicit supersession relationship;
5. public/buyer surfaces must not present a superseded or requalification-required record as current.

## Commercial moat and evidence integrity

Carbon's strategic advantage is compatible with strong transparency because the value is split across layers:

- the **claim** can be explicit;
- the **provenance** can be auditable;
- the **qualification standard** can be inspectable;
- the **allowed evidence projection** can be reviewable;
- while hidden exam realizations, reconstruction-sensitive diagnostics, exact proprietary recipes, private Landscape intelligence, and licensed model artifacts remain controlled.

This is the intended evidence rail: trustworthy enough for an engineering organization to understand what Carbon is claiming, without converting the qualification process into an answer key or the commercial system into an open recipe dump.

## Non-claims

- `Qualification Record` is not, by name alone, a regulatory certificate or standards-compliance attestation.
- A public evidence projection is not the full private evidence store.
- A current qualification does not imply validity outside its context of use or envelope.
- Historical qualification does not imply current qualification after a declared requalification trigger.
- Product qualification status never enters lean subnet scientific scoring or emissions.
