# E-EA4 — Scientifically usable archive views

**Wave:** E Landscape and evidence memory
**Status:** `future_reserved`; unselected and unstarted
**Goal:** Produce immutable versioned `ResearchSnapshot`s whose cohorts, provenance, missingness, permissions, and dependence are scientifically inspectable.

**Prerequisites/owners:** C-EA3 and eligible real evidence; archive, measurement/Score Pack, Challenge/population, statistics, privacy/rights, and Landscape owners. Human inputs: permitted uses, scientific cohort/estimand decisions, qualification interpretations.

**Scope and reuse:** Read—not mutate—archive records. Bind source cutoff/versions, physical context, units, executed/unexecuted masks, censoring, selection probabilities/reasons, guidance exposure, shared cases/references/ancestry/repeats, interventions/comparators, and contradictions.

**Interfaces/failure/limits:** Unknown/missing stays explicit; unavailable or ineligible inputs fail the named view. No rescore, imputation-as-truth, cross-tenant linking, release, or learned claim. Snapshot identity makes reproduction and correction impact possible.

**Acceptance tests:** frozen cohort reproduction; missingness/dependence/selection cases; permission withdrawal; contradictory evidence; version cutoff; archive unavailability; no mutation or qualification upgrade.

**Definition of Done:** [ ] Domain-approved snapshot contract and implementation pass future tests. [ ] Exact use assessment and permissions are bound. [ ] No external release is created.

**Handoff:** E-EA5 and E-EB1 consume approved snapshots; E-EA7 tracks downstream impact.
