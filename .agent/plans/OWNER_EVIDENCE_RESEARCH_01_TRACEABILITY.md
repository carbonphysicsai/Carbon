# OWNER-EVIDENCE-RESEARCH-01 requirements traceability and handoff

**Status:** prospective documentation integration; no future ticket is selected
**Integration ticket:** `GOV-EVIDENCE-RESEARCH-02`
**Working base:** `91b023a` (`origin/main`, fetched 2026-09-07)
**Design source:** the full `Carbon_Evidence_Archive_Design_v0.3.zip` was read on 2026-09-08 and reconciled against current repository authority. The ZIP is not committed and does not override exact protocols or runtime evidence.

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

### v0.3 work-package mapping

| v0.3 package ID | Repository reservation | Mapping note |
|---|---|---|
| EA-00/01/02/03 | C-EA0/1/2/3 | capture contract, durable store, integration, then recovery remain C1 foundations |
| EA-04/05 | E-EA4/5 | scientific snapshots then Landscape learning |
| EA-06 | E-EB1 + E-EA6 | split candidate/approval from serving/cumulative disclosure |
| EA-07 | E-EA7 | transitive correction propagation |
| DC-01/02/03 | C-DC1/2/3 | exact dialogue authority, durability, then Concierge |
| DC-04 | C-DC2/3/4 minimum correction + E-EB1/EA6/EA7 learned release | split launch lineage from later learned-brief release/propagation |
| DC-05 | C-DC2/3 capture + E-D12 aggregation | original observations start at launch; clustering/planning waits for E |
| DC-06 | C-DC2/3/4 + E-EA7 | launch feedback/inbox/update control; later transitive propagation |
| DC-07 | C-DC4 | security, abuse, utility, recovery and resource isolation acceptance |
| PR-00/01/02/03/04/05 | G-PR0/1/2/3/4/5 | preregistration is separated from pilot execution/decision |
| RI-01 | E-RI1 | prospective bounded guidance/predictive qualification |
| RI-02/03/04/05 | post-E/G passive reservations | transfer, experiment value, portfolio proposals, and closed-loop guidance need later selected tickets |

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
| v0.3 archive document links to v0.2 dialogue/demand/business filenames; dialogue starter schema `$id`, title and constants say 0.2 | `DOCUMENTATION_LAG` | use v0.3 prose only as design input; future C-DC1 owns the exact version |
| v0.3 `Research_Concierge` starter schema permits unspecified properties | `DOCUMENTATION_LAG` | do not ratify/import it; future exact protocol must close fields and semantics |
| package validator requires absent v0.2 files and cannot run in the repository environment without external `jsonschema` | `DOCUMENTATION_LAG` | do not copy or treat it as acceptance/security evidence; repository checks remain controlling |
| manifest entry for `Validation/Package_Validation_Report.md` does not match ZIP bytes/hash | `DOCUMENTATION_LAG` | record mismatch; package presence report proves neither integrity chain nor runtime property |
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

## 6. v0.3 acceptance-ID crosswalk

| Package IDs | Repository ticket acceptance |
|---|---|
| ARC-01..04 | C-EA0..3 attempt, finalization, restore, and separated evidence-semantics cases |
| ARC-05 | C launch correction minimum plus E-EA7 transitive propagation |
| ARC-06 | C-DC4 and G-PR3 shared-resource isolation |
| DIA-01..02 | C-DC1/2 identity, reference substitution, and idempotency |
| DIA-03..06 | C-DC3/4 protected-state independence, gaps, injection, and epistemic-bound claims |
| DIA-07..12 | C-DC2/3/4 restart, withdrawal, corrections, inbox, flood, and kill switches |
| BRF-01..03 | E-EB1 identity/lineage, counterevidence, and transfer limits |
| DEM-01..06 | C-DC2 service-without-reuse plus E-D12 manipulation, funnel, science, gap, and taxonomy cases |
| PAY-01..05 | G-PR1/4 spending and quote; G-PR3 isolation; E-EA6 paid disclosure; G-PR0 freeze |
| REL-01..02 | E-EA6 combined-surface leakage and complete-client-caching assumptions |
| VAL-01..02 | C-DC3/4 research utility and E-RI1 prospective guidance lift |
| VAL-03 | G-PR5 repeat paid demand and full contribution |

## 7. v0.3 opportunity mapping

| Opportunity | Route | Build/stop discipline |
|---|---|---|
| Research-gap marketplace; demand-informed sponsored challenges | E-D12 -> Port C/G governance | proposal only; manipulation/pay-to-science blocks |
| EvidenceBrief library; evidence correction service | E-EB1/EA6/EA7 | exact release and update rights; leakage/staleness blocks |
| customer-funded catalogue growth | G-PR1/3/5 + evidence-use/release owner | require reusable rights, utility and contribution |
| guidance-effectiveness dataset | E-RI1 | prospective valid design; causal overclaim blocks |
| failure-demand heatmap; public resource prioritization | E-D12 -> Ports A/D | privacy/popularity bias and non-actionability stop investment |
| experiment-value ranking; research portfolio API | post-E/G reservations | require prospective calibration and decision lift before a ticket/product |
| agent-native quoting; scientific customer success; research supply pricing | G-PR1/2/4/5 | bounded auth, repeat utility, full-cost contribution; side-channel/support failure blocks |
| research update subscriptions | C-DC2/3/4 then E-EA7 | private entitled updates only; activity leakage blocks |
| method transfer intelligence | E-RI1 then post-E/G transfer ticket | scope-specific calibration; false generalization blocks |

## 8. Package verification record

All 26 ZIP entries were inspected. Recomputing manifest byte counts and SHA-256 values matched 25 entries; `Validation/Package_Validation_Report.md` was 972 bytes with SHA-256 `960d03026d46f1c3eafe4367d776f25cecab2285fc10fd8640327f854eff873b`, while the manifest declared 2057 bytes and `43b70568fbd83d90a195c0907317e51848c7be86718702f8a31378e115787376`. The included validator was not executed successfully because `jsonschema` was absent; inspection also found it requires absent v0.2 filenames. Its report's presence checks are not accepted as runtime, durability, authorization, leakage, or security qualification.

## 9. Next-executor handoff

When a controlling board activates a ticket, begin with that ticket file, then read the canonical design and focused companion it names, this crosswalk, current authority files, and source-owner contracts. Confirm current main and competing work, record owner inputs, write the exact runtime contract/migration, and implement only the selected ticket. Do not begin from the ZIP or from this crosswalk alone. For C-EA work, start with C-EA0; for dialogue, C-DC1; for Landscape evidence, E-EA4 (E-D12 may start from eligible C observations under its board); for paid research, G-PR0.
