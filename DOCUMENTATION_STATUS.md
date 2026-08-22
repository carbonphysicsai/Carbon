# Carbon Documentation Status and Authority Index

**Status:** OWNER-RECOMMENDED documentation-control index for `design/symbolic-numeric-integration`.  
**Date:** 2026-08-22.  
**Purpose:** Prevent stale documents, historical prototypes, and future-architecture drafts from silently overriding one another.

## Status vocabulary

- **CURRENT-RUNTIME** — governs implemented/current P0 behavior until intentionally migrated.
- **CURRENT-ARCHITECTURE** — owner-recommended integrated design to be reviewed and migrated into runtime specs.
- **LOCKED-ARCHITECTURE** — owner-ratified architectural boundary already accepted as durable, even if exact implementation remains under review.
- **MIGRATION-PENDING** — still useful, but contains statements that must change when vNext is ratified.
- **SUPERSEDED** — retained for provenance; do not use as current design authority.
- **HISTORICAL / GAUNTLET** — evidence of design learning, simulations, or prior implementation.
- **ARCHIVE** — legacy reference only.

## Read order for current design review

1. `docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md` — scientific constitution / claim control.
2. `Design_Specs/System_Identity_and_Roadmap_v2.md` — integrated system identity and roadmap.
3. `Design_Specs/Challenge_Instance_Distribution.md` — target population / SamplingPlan architecture.
4. `Design_Specs/Generator_Validation.md` — Validation Dossier / qualified-exam architecture.
5. `Design_Specs/Score_Pack_Architecture_v1.md` — Score Pack as Evidence Use Contract.
6. `Design_Specs/Challenge_Portfolio_and_Frontier_Economics_v1.md` — frontier promotion and equal Challenge opportunity.
7. `Design_Specs/Treasury_Settlement_Architecture_v1.md` — treasury-neuron settlement design.
8. `Design_Specs/Emissions_Mapping_v3.md` — current future economic semantics.
9. `Design_Specs/Burgers_Challenge_Qualification_v1.md` — first-Challenge repair / qualification decisions.
10. `SPEC_VNEXT_INTEGRATED.md` and `Design_Specs/Build_Out_vNext_Integrated.md` — consolidated migration targets.

## Runtime authority that remains in force during migration

The integrated architecture does **not** silently change deployed/current behavior. Until reviewed migration is approved:

| Document / code | Status | Role |
|---|---|---|
| `SPEC.md` | CURRENT-RUNTIME + MIGRATION-PENDING | Current protocol architecture; several narrative/economic sections are stale relative to vNext. |
| `Design_Specs/Scoring.md` | CURRENT-RUNTIME + MIGRATION-PENDING | Sole current P0 scoring mathematics; emissions coupling inside it is stale for vNext. |
| `Design_Specs/Build_Out.md` | CURRENT-RUNTIME + MIGRATION-PENDING | Current sequencing authority; direct score→weights acceptance path is stale for vNext. |
| `Design_Specs/Miner_MCP.md` | CURRENT-RUNTIME | Miner-facing interface / disclosure unless changed by reviewed migration. |
| `Design_Specs/Data_Management.md` | CURRENT-RUNTIME + MIGRATION-PENDING | Seed/data-role behavior; reconcile with first-class population/SamplingPlan objects. |
| `Design_Specs/Trustless_Verification.md` | CURRENT-RUNTIME + MIGRATION-PENDING | Existing generator/truth rules; reconcile with Challenge-specific truth policy and qualified-exam chain. |
| Existing P0 schemas / packs / validator code | CURRENT-RUNTIME | Implementation reality; not automatically rewritten by design documents. |

## Current architecture documents

| Document | Status | Notes |
|---|---|---|
| `docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md` | CURRENT-ARCHITECTURE | Supersedes v3 for integrated scientific constitution; v3 remains bibliographic annex. |
| `Design_Specs/System_Identity_and_Roadmap_v2.md` | CURRENT-ARCHITECTURE | Supersedes old narrative roadmap. |
| `Design_Specs/Challenge_Instance_Distribution.md` | LOCKED-ARCHITECTURE | Population / SamplingPlan authority boundary. |
| `Design_Specs/Generator_Validation.md` | LOCKED-ARCHITECTURE | Validation Dossier / exam qualification. |
| `Design_Specs/Score_Pack_Architecture_v1.md` | CURRENT-ARCHITECTURE | Future generalized Score Pack semantics. |
| `Design_Specs/Challenge_Portfolio_and_Frontier_Economics_v1.md` | CURRENT-ARCHITECTURE | Frontier-only performance reward; equal `1/N` Challenge opportunity. |
| `Design_Specs/Treasury_Settlement_Architecture_v1.md` | CURRENT-ARCHITECTURE | Preferred settlement architecture; production requires localnet/testnet qualification. |
| `Design_Specs/Emissions_Mapping_v3.md` | CURRENT-ARCHITECTURE | Supersedes v1/v2 future emissions recommendations. |
| `Design_Specs/Burgers_Challenge_Qualification_v1.md` | CURRENT-ARCHITECTURE | First authoritative Burgers repair plan; not production-qualified yet. |
| `SPEC_VNEXT_INTEGRATED.md` | CURRENT-ARCHITECTURE / MIGRATION TARGET | Consolidated future protocol, not current runtime. |
| `Design_Specs/Build_Out_vNext_Integrated.md` | CURRENT-ARCHITECTURE / MIGRATION TARGET | Future implementation sequence. |

## Superseded / historical documents

| Document | Status | Replacement / use |
|---|---|---|
| `Design_Specs/System_Identity_and_Roadmap.md` | SUPERSEDED | Use `System_Identity_and_Roadmap_v2.md`. |
| `docs/context/SCIENTIFIC_REFERENCE_CANON_V3_MASTER.md` | SUPERSEDED FOR INTEGRATED CONSTITUTION | Retain as detailed evidence/bibliography annex under Canon v4. |
| `docs/context/SCIENTIFIC_REFERENCE_CANON.md` | SUPERSEDED | Historical canon. |
| `Design_Specs/Score_Pack_Architecture.md` | SUPERSEDED | Use `Score_Pack_Architecture_v1.md`. |
| `Design_Specs/Emissions_Mapping_v1.md` | SUPERSEDED | Continuous proportional reward rejected for base performance market. |
| `Design_Specs/Emissions_Mapping_v2.md` | SUPERSEDED | Use treasury-aware v3. |
| `Design_Specs/Bittensor_Settlement_Adapter_v1.md` | HISTORICAL / GAUNTLET INPUT | Important transport-failure analysis; preferred future route is treasury settlement. |
| `Design_Specs/POC_Burgers_FNO.md` | HISTORICAL IMPLEMENTATION POC | Do not use as authoritative Burgers science; use `Burgers_Challenge_Qualification_v1.md`. |
| `zDesign Archive/*`, `zBuild Appendices/*` | ARCHIVE | Legacy reference only unless explicitly cited by a current spec. |

## High-priority migration-pending documents

1. `README.md` — old score→emissions language and old roadmap/docs map.
2. `SPEC.md` — direct score→weights, winner-heavy decay, Landscape Port C dynamic emission targeting, universalized Julia language.
3. `Design_Specs/Scoring.md` — scoring math remains runtime authority, but `emissions: lean_score_decay` and economic-allocation language must leave the scoring domain.
4. `Design_Specs/Build_Out.md` — direct scores→weights / C15 path must become frontier-event + treasury integration after review.
5. `Design_Specs/Landscape_Agent.md` — Port C must not dynamically reweight the base equal-Challenge performance portfolio.
6. `Design_Specs/Runtime_Julia_Truth_Oracle.md` — reframe as an optional qualified Julia reference backend, not universal truth authority.
7. `Design_Specs/Operations.md` — add treasury/frontier states and Challenge-specific reference service semantics; remove direct lean-score emission assumptions.
8. `Design_Specs/Launch_Bar.md` — expand to full qualified-exam + frontier/settlement stop-ships; remove unqualified Burgers residual assumptions.
9. `docs/context/Open_Questions.md` — use `Open_Questions_v2.md` for current unresolved questions.
10. `docs/context/Decisions.md` — D1–D50 remain provenance; current integrated decisions continue in `Decisions_v2.md`.
11. `docs/context/Architecture_Rationale.md` — durable sections remain useful; score→weights and generator/reference rationale need v2 language.

## Publication sources

Current integrated publication source should live under `docs/publications/`:

- `Carbon_Whitepaper_v3.0.tex`
- `Carbon_Academic_Litepaper_v3.0.tex`
- `Carbon_Exploit_Summit_Pitch_Deck_Review_v4.md`

Rendered PDF/DOCX files are release artifacts; source-controlled text is the canonical editable publication source.

## Reconciliation law

> **A document may remain historically correct without remaining current authority. Preserve provenance, label status, and migrate intentionally rather than silently rewriting history.**
