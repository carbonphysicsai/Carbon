# Carbon Publications — Reconciliation and Source Map

**Status:** publication-control documentation on `main`.  
**Purpose:** keep public papers and presentation guidance aligned with Carbon's scientific architecture, business canon, implementation maturity, and claim discipline without allowing publications to become protocol authority.

---

## Authority boundary

Publications explain Carbon. They do **not** define scientific runtime behavior, qualification criteria, commercial rights, treasury governance, or business traction.

Publication authors should reconcile against two distinct authority planes:

### Scientific authority

- current runtime specifications and code on `main` govern implemented behavior;
- owner-recommended integrated scientific architecture may exist ahead of runtime migration and must be labeled accordingly;
- external scientific literature supports premises, not Carbon-specific proof;
- Carbon experiments determine whether Carbon's hypotheses work.

### Business authority

- [`../../Business/Business_Canon.md`](../../Business/Business_Canon.md) governs durable business principles;
- [`../../Business/Business_Plan.md`](../../Business/Business_Plan.md) and companion `Business/` documents govern product, GTM, financial, investor, and company/network positioning;
- business architecture is not customer traction;
- customer payment and investor priorities never alter scientific evidence requirements.

---

## Current reconciled publication generation

### Whitepaper v3.1

Source target: `Carbon_Whitepaper_v3.1.tex`.

Reconciliation record: [`WHITEPAPER_V3_1_RECONCILIATION.md`](./WHITEPAPER_V3_1_RECONCILIATION.md).

v3.1 preserves the scientific paper's purpose and adds a bounded commercial architecture section that explicitly separates the OpCo/business loop from the scientific judge.

### Academic Litepaper v3.1

Source target: `Carbon_Academic_Litepaper_v3.1.tex`.

Reconciliation record: [`LITEPAPER_V3_1_RECONCILIATION.md`](./LITEPAPER_V3_1_RECONCILIATION.md).

v3.1 adds a concise commercial architecture section while retaining the paper's scientific/academic center of gravity.

### Exploit Summit / stage deck review v5

Source-controlled editorial review: [`Carbon_Exploit_Summit_Pitch_Deck_Review_v5.md`](./Carbon_Exploit_Summit_Pitch_Deck_Review_v5.md).

The stage deck should remain simpler than the papers. It should explain the problem, qualified exam, competition, verified frontier advance, reward, and business wedge without teaching internal schema names or treasury internals.

---

## Cross-publication reconciliation record

See [`PUBLICATION_RECONCILIATION_2026-08-23.md`](./PUBLICATION_RECONCILIATION_2026-08-23.md).

---

## Claim maturity discipline

Scientific publication claims should distinguish:

```text
EXTERNAL PREMISE
!=
CARBON DESIGN
!=
IMPLEMENTATION
!=
CARBON EVIDENCE
!=
REPLICATION
!=
PRODUCTION QUALIFICATION
```

Business/investor claims should distinguish:

```text
BUSINESS DESIGN
!=
CUSTOMER DISCOVERY
!=
PAID PILOT
!=
REPEATABLE SERVICE
!=
EXPANSION
!=
RECURRING REVENUE
!=
PLATFORMIZATION
!=
NETWORK LEVERAGE
```

Do not present a designed product, pricing architecture, revenue scenario, or network-value hypothesis as achieved traction.

---

## Current publication non-claims

Unless later evidence explicitly changes the record, Carbon should not claim that it has already demonstrated:

- production-qualified Burgers;
- production treasury deployment;
- empirically proven frontier economics;
- a successful seven-Challenge LIVE portfolio;
- superiority over centralized search;
- production-qualified generalized reconstruction;
- paid commercial traction merely because the business architecture is specified;
- proven recurring-revenue or gross-margin economics;
- a validated Physics Intelligence commercial product;
- automatic transfer of OpCo revenue into Alpha value;
- universal safety, regulatory certification, or engineering fitness from a Carbon subnet result.

---

## Build artifact policy

LaTeX source is the publication source of truth where available. Rendered PDFs are generated artifacts and should be regenerated from the exact source/version before external release. A successful compile is not a scientific, commercial, or legal approval.
