# OWNER-EVIDENCE-RESEARCH-01 requirements traceability and handoff

**Status:** prospective documentation integration; no future ticket is selected
**Integration ticket:** `GOV-EVIDENCE-RESEARCH-02`
**Working base:** `91b023a` (`origin/main`, fetched 2026-09-07)
**Source limitation:** `Carbon_Evidence_Archive_Design_v0.3.zip` was unavailable. This crosswalk is complete against verified repository sources and the owner brief, but it is not described as a lossless ZIP reconciliation. ZIP-only diagrams, dialogue field names, opportunity-register wording, acceptance identifiers, inherited version labels, and reconciliation notes could not be verified.

## 1. Canonical ownership and source-to-ticket crosswalk

| Requirement | Canonical owner/section | Future ticket(s) | Dependencies | Acceptance criterion | Maturity/owner decision |
|---|---|---|---|---|---|
| admission and all-attempt accounting | `Evidence_Archive_and_Custody.md` §§1–2 | C-EA0/1/2/3 | current lifecycle, execution, evidence owners | every admission reconciles; statuses remain separate | fault profile and required artifacts human-owned |
| archive-before-finalization | archive contract §§5–6 | C-EA1/2/3 | C1 orchestration | verified acknowledgement precedes finalization | production/DR approval human-owned |
| custody/retention/deletion | archive contract §§4,7 | C-EA0/1/3 | data, Operations, rights/security | zones, manifests, deletion/restore handling pass | retention, legal/IP, key custody reserved |
| scientific archive views | archive contract §§2–3 | E-EA4 | C-EA3; eligible evidence | reproducible versioned view preserves missingness/dependence | scientific uses/estimands reserved |
| Landscape learning and Ports B/C/D | `Landscape_Agent.md`; paid/opportunity contract §§4–5 | E-EA5 | E-EA4 | scoped ports cannot mutate judge | scientific/product qualification retained |
| launch dialogue protocol/auth | concierge contract §§1–3 | C-DC1 | C0 identity/transport | closed protocol/negative matrix | identity, limits, provider policy reserved |
| durable private threads | concierge contract §4 | C-DC2 | C-DC1 | restart, privacy, idempotency, withdrawal | retention/privacy reserved |
| useful launch Concierge | concierge contract §§1–3,8 | C-DC3/4 | C-DC2; approved bootstrap sources | held-out utility, grounding, abstention, recovery | thresholds/security/launch reserved |
| launch demand capture; later aggregation | concierge contract §5 | C-DC2/3; E-D12 | private thread + purpose permissions | no duplicate counts; opt-out/deletion; funnel distinctions | purposes/aggregation/funding reserved |
| EvidenceBrief lifecycle | concierge contract §6 | E-EB1 | E-EA4/5 | counterevidence, provenance, permissions, exact approval | epistemic/release decisions reserved |
| cumulative disclosure/release | concierge contract §6 | E-EA6 | E-EB1; existing PriorPack release | cross-surface accumulation tests | disclosure/security/rights reserved |
| correction/update propagation | concierge contract §7 | C-DC2/3/4; E-EA7 | dependency lineage | append, impact, idempotent authorized update | customer/scientific actions reserved |
| Specialist Bank inputs/failures | `Specialist_Bank.md` amendment | E-EA5 then Wave F owner | qualified eligible evidence/signals | no qualification duplication | product qualification owner retained |
| paid pilot scorecard first | paid contract §§1,3 | G-PR0 | business/product/evaluation owners | preregistration immutable before observations | targets/budget reserved |
| entitlement/quotes/context | paid contract §§1–2 | G-PR1/2 | G-PR0 | exact bounded auth, tenant isolation | price/rights/legal reserved |
| isolated paid execution/billing | paid contract §§2,5 | G-PR3/4 | G-PR1/2; qualified execution | no dispatch without auth/funds; official isolation | security/deployment/economics reserved |
| paid pilot/expansion | paid contract §3 | G-PR5 | G-PR0..4 | measured utility/demand/contribution/safety | commercial decision reserved |
| advanced predictive/portfolio tools | paid contract §5; E-RI1 | E-RI1; post-E/G reservations | frozen candidates, prospective evidence | time-forward lineage/leakage tests | no new wave/role without owner selection |

## 2. Acyclic dependency and launch split

```text
Wave B -> C0 identity/transport -> C1 real execution -> C2 testnet proof -> D -> H -> I
                              |            |
                              |            +-> C-EA0 -> C-EA1 -> C-EA2 -> C-EA3
                              +-> C-DC1 -> C-DC2 -> C-DC3 -> C-DC4

after eligible evidence: C-EA3 -> E-EA4 -> E-EA5 -> E-EB1 -> E-EA6 -> E-EA7
                            C-DC2/3 -> E-D12
                    E-EA5 + E-EB1/6/7 -> E-RI1

G-PR0 -> G-PR1 -> G-PR2 -> G-PR3 -> G-PR5
                    \----------> G-PR4 --/
```

The first authenticated external miner launch needs the applicable C evidence-capture deployment and C-DC1..4 dialogue deployment, each with its own security/operations approval. It uses approved bootstrap/public resources. Wave E learned briefs/D12 aggregation and Wave G paid work are later and do not gate D→H→I. Capture records real attempts before qualification and retains their original status. Frozen private release candidates plus prospective evidence can qualify a later release without circularly requiring public activation.

## 3. Future acceptance matrix

| Gate | Tickets | Required evidence | Explicit non-claim |
|---|---|---|---|
| capture semantics | C-EA0 | approved contract/fault and retention decisions | no storage/runtime |
| archive availability | C-EA1..3 | crash, restore, manifest, reconciliation, backpressure | no universal losslessness or scientific truth |
| dialogue protocol/durability | C-DC1/2 | authz, conformance, idempotency, privacy, recovery | no reasoning/launch authority alone |
| Concierge launch | C-DC3/4 | held-out utility, grounding, injection, withdrawal, resource isolation, ops owner | no Challenge qualification |
| research intelligence | E-EA4/5, E-D12 | provenance/dependence, permission, manipulation, port bounds | no score/funding/revenue inference |
| external learned release | E-EB1/EA6/EA7/RI1 | exact artifact, cumulative disclosure, correction, prospective utility | no archive export or role transfer |
| paid execution | G-PR0..4 | frozen scorecard, rights/auth, isolation, funds/reconciliation | no traction or official evidence |
| paid expansion | G-PR5 | preregistered pilot result and owner decision | no automatic product/scientific qualification |

## 4. Conflict register

| Seam | Classification | Resolution |
|---|---|---|
| prior overlay said future boards should materialize tickets | `DOCUMENTATION_LAG` | 21 passive ticket documents now exist; boards still control activation |
| Build Out Phase-0 non-goal wording could imply launch dialogue is post-P0 | `DOCUMENTATION_LAG` | Wave C launch minimum is additive; E/F/G remain post-D parallel lanes |
| D12 previously appeared to own demand capture | `DOCUMENTATION_LAG` | C captures purpose-eligible observations; E aggregates/clusters/plans |
| correction detail previously concentrated in E | `DOCUMENTATION_LAG` | C has minimum source/dependency/update controls; E has transitive propagation |
| launch Concierge might appear dependent on learned Landscape | `DOCUMENTATION_LAG` | bootstrap/public sources launch first; learned briefs require E |
| ZIP claims/labels versus repository protocols | `NEW_OWNER_DECISION_REQUIRED` if material after ZIP review | repository protocol owners remain controlling; no ZIP-only semantics inferred |
| durability, retention, rights, pricing, security, scientific thresholds | `NEW_OWNER_DECISION_REQUIRED` | exact affected capability stays fail closed; documentation continues |

## 5. Open owner decisions

| Decision needed | Owner | Blocked capability |
|---|---|---|
| production durability/fault profile, provider/topology, acknowledgement guarantee and recovery objectives | Operations/security/repository owner | C-EA1..3 production acceptance |
| retention classes/durations, legal hold, deletion, IP/source licences and provider data policy | legal/privacy/rights owner | archive, dialogue, D12 and paid activation |
| required original evidence/artifact profiles and scientific use/estimand/epistemic thresholds | scientific domain owners | C-EA0, E-EA4/EB1/RI1 |
| identity/tenant model, quotas, service budgets, model/provider, operational owner and launch thresholds | product/security/Operations owner | C-DC1..4 launch |
| public/paid exact release policy and cumulative disclosure acceptance | disclosure/science/security/rights owners | E-EA6 external serving |
| demand purposes, aggregation rules, Port C priorities/funding | privacy/research-governance owner | E-D12 uses |
| pilot cohort, targets, budget, prices, quote/refund terms and customer reuse rights | business/finance/legal owner | G-PR0..5 |
| exact deployment and LIVE activation | repository/launch owner | any external production service |

## 6. Next-executor handoff

When a controlling board activates a ticket, begin with that ticket file, then read the canonical design and focused companion it names, this crosswalk, current authority files, and source-owner contracts. Confirm current main and competing work, record owner inputs, write the exact runtime contract/migration, and implement only the selected ticket. Do not begin from the ZIP or from this crosswalk alone. For C-EA work, start with C-EA0; for dialogue, C-DC1; for Landscape evidence, E-EA4 (E-D12 may start from eligible C observations under its board); for paid research, G-PR0.
