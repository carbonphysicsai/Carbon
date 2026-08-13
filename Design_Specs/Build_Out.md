# Carbon Build-Out Specification

**Audience:** Lead engineer, small team, or contractor building Carbon to run.  
**Version:** 1.0  
**Status:** Requirements contract  
**Companion docs:** `SPEC.md`, `Miner_MCP.md`, `Scoring.md`, `Generator_Creation.md`, `Generator_Validation.md`, `Evidence_and_Envelope_Standards.md`, `Data_Management.md`, `Launch_Bar.md`

---

## How to use this document

1. **High-level map (§1–3)** — what exists, what is global vs per-challenge, which phase needs it.  
2. **Phase milestones (§4)** — definition of done for Phase 0 / 1A / 1B / 2.  
3. **Component requirements (§5+)** — buildable requirements, acceptance checks, dependencies.  

**Rule for builders:** Phase 0 is a *vertical slice* (one challenge, full loop), not a horizontal skeleton of every future feature.

---

## 1. What “running Carbon” means

Minimum live system:

```text
Miner/agent  →  Miner MCP / submit strategy
                    ↓
Validator    →  hidden procedural data → train per strategy → physics gates → Score Pack → card
                    ↓
Network      →  weights / emissions from lean scores only
                    ↓
Public       →  leaderboard + budgeted feedback to submitter
                    ↓
Ops          →  priors + mock scaffolds updated from verified cards
```

Later: Landscape graph, specialist bank, sponsored challenges — **not** required to run Phase 0.

---

## 2. Component map (high level)

| ID | Component | Scope | Phase 0 | Phase 1A | Phase 1B+ |
|----|-----------|-------|---------|----------|-----------|
| C0 | Monorepo, packaging, CI | Global | Required | — | — |
| C1 | Challenge registry | Global + per challenge row | Required | Extend | Extend |
| C2 | Strategy schema + denylist | Global (+ per-challenge fields) | Required | Extend | Extend |
| C3 | Procedural generator | **Per challenge** | 1 challenge | More packs | Partner packs |
| C4 | Generator validation / dossier | **Per challenge** | Level-1 dossier | Level-2/3 | Partner goldens |
| C5 | Score Pack + scoring engine | **Per challenge** + engine global | Required | Regime packs | — |
| C6 | Seeding / data roles | Global policy | Required | Per-validator seeds optional | — |
| C7 | Validator neuron | Global | Required | Perf / scale | — |
| C8 | Miner neuron (thin) | Global | Optional if MCP-first | — | — |
| C9 | Miner MCP | Global | Required | Harden | — |
| C10 | Prior publisher | Global | Bootstrap prior OK | Automated | Landscape Port A |
| C11 | Mock packs + scaffolds | **Per challenge** | 1 pack + 1 scaffold | Rotation | Multiple families |
| C12 | Evaluation card store | Global | Required | Feedback tiers | — |
| C13 | Fees / rate limits | Global | Simple fee | Sybil controls | — |
| C14 | Leaderboard / public API | Global | Minimal | Polish | — |
| C15 | Bittensor integration | Global | Testnet | Mainnet | — |
| C16 | Observability / ops | Global | Basic logs | Metrics | — |
| C17 | Landscape agent | Global | **Out** | Thin telemetry | Full |
| C18 | Specialist bank | Global | **Out** | Rehearse optional | Product path |
| C19 | Julia / reference oracle | Per backend | Phase 0 analytic/FEM path | CFD backends | — |

---

## 3. Global vs per-challenge

### Always global (build once)

- MCP server and tool surface  
- Validator orchestration (queue, train harness, gate runner interface)  
- Scoring *engine* (loads Score Pack YAML; computes legs)  
- Card store, fee ledger, hotkey auth  
- Prior/scaffold *publish pipeline*  
- Bittensor neuron wiring, emissions mapping  
- CI, images, deployment  

### Per challenge (repeatable pack)

- Generator code + envelope + MOCK_RANGES + VALIDATOR ranges  
- Score Pack (gates, weights, thresholds)  
- Validation dossier + reference evidence  
- Mock pack(s) + mock scaffold(s)  
- Challenge registry entry (hashes, versions, disclosure tier)  
- Optional: challenge-specific gate implementations  

**Builder implication:** invest in a **pack format** so challenge #2 is config + generator, not a fork of the subnet.

---

## 4. Phase milestones

### Phase 0 — “One real loop” (launch bar)

**Goal:** One physics challenge; agents and humans can free-iterate and submit; validators grade under hidden data; emissions reflect lean scores only.

| Milestone | Done when |
|-----------|-----------|
| **P0.1 Pack** | Burgers (or chosen PDE) generator deterministic by `(seed, role)`; train≠eval≠stress; MOCK_RANGES ⊂ envelope |
| **P0.2 Dossier** | Level-1 validation dossier published; reference rank stated; gates calibrated; claim ≤ evidence |
| **P0.3 Score Pack** | YAML pack bound to `generator_version`; hard gates fail-closed; prior similarity **absent** |
| **P0.4 Validator** | Accept strategy → materialize hidden data → train → gates → components → card record |
| **P0.5 MCP** | Tools: info, prior, scaffold, dry_validate, estimate, light_compare, light_train, submit, get_submission_result |
| **P0.6 Free path** | Agent can loop estimate+compare without fee; mock-only; no validator seeds |
| **P0.7 Paid path** | Fee → queue → card with Phase 0 disclosure tier |
| **P0.8 Network** | Testnet neuron; weights from lean score; leaderboard shows hotkey + score |
| **P0.9 Launch bar** | Checklist in `Launch_Bar.md` green; bootstrap prior marked if needed |

**Out of Phase 0:** Landscape causal graph, specialist bank SKUs, multi-mock rotation automation, commercial CAE backends, per-validator seed diversity.

### Phase 1A — “Credible regime expansion”

- Additional packs (e.g. Darcy / elasticity / simplified aero-like)  
- Automated prior publisher from cards  
- Mock pack rotation policy + manual/assisted corr monitor  
- Stronger FOSS/Julia reference path  
- Validator throughput optimizations  
- Mainnet candidate  

### Phase 1B — “Harder physics + partners”

- Reacting / sequential multiphysics *screening* packs only if dossier depth matches  
- Partner golden qualification path  
- Optional commercial solver ops integration  

### Phase 2 — “Product path”

- Landscape opportunity ranking (read-only from cards first)  
- Specialist bank pilot (closed SKU, product battery)  
- Sponsored challenge tier  
- Customer bounds path without training on raw proprietary dumps  

---

## 5. C0 — Monorepo, packaging, CI

**Scope:** Global  

### Requirements

- Installable Python package (`pyproject.toml`); `pip install -e .`  
- Clear layout: `carbon/` (library), `neurons/`, `challenges/` or `packs/`, `mcp/`, `tests/`  
- CI: lint, unit tests, schema tests on PR  
- Pinned dependency policy for validator image vs miner-light extras  
- Docker image targets: `validator`, `mcp` (and optional `miner`)  

### Acceptance

- Fresh clone → install → unit tests pass  
- CI required to merge  

### Phase

- P0: required  

---

## 6. C1 — Challenge registry

**Scope:** Global service + per-challenge records  

### Requirements

Each LIVE challenge record includes:

- `challenge_id`, display metadata  
- `generator_version`, `scoring_pack_hash`, `schema_version`  
- `disclosure_tier`  
- Active `mock_pack_ids[]`, current `scaffold_id`  
- Fee quote  
- Status: `draft | dossier | live | retired`  
- Content hashes for generator + pack artifacts  

### Acceptance

- MCP `get_challenge_info` reads only registry  
- Submit rejected if strategy targets non-live or hash mismatch policy  

### Phase

- P0: file- or DB-backed registry with one live row  
- P1: admin tooling to publish versions  

---

## 7. C2 — Strategy schema

**Scope:** Global schema + optional per-challenge extensions  

### Requirements

- Versioned JSON Schema for strategies  
- **Denylist:** `eval_seed`, `stress_seed`, official `generator_pack_hash`, gate disable flags  
- Allowed: backbone, training, loss enables, curriculum, data hints, `meta.prior_version`  
- `dry_validate` implements schema + denylist  

### Acceptance

- Invalid strategies never enter train harness  
- Denylist fields ignored or rejected (document which)  

### Phase

- P0: one schema version  

---

## 8. C3 — Procedural generator (**per challenge**)

**Scope:** Per challenge  
**Primary docs:** `Generator_Creation.md`, `Data_Management.md`  

### Requirements

- `generate(seed, role ∈ {train, eval, stress}) → batch`  
- Deterministic given `(generator_version, seed, role, params)`  
- Envelope + **excluded regimes** documented  
- Role separation enforced (train≠eval≠stress draws)  
- Entropy / anti-degenerate checks  
- Public code for the generator **family**  

### Acceptance

- Fixed seeds replay byte-stable (or documented float tolerance)  
- Role split tested  
- Envelope violations impossible by construction or rejected  

### Phase

- P0: one PDE pack (recommended: Burgers 1D or similar)  
- P1+: additional packs via same interface  

---

## 9. C4 — Generator validation / dossier (**per challenge**)

**Scope:** Per challenge  
**Primary docs:** `Generator_Validation.md`, `Evidence_and_Envelope_Standards.md`  

### Requirements

- Level-1: mesh/time convergence where applicable, reference agreement, conservation sanity  
- Stated reference rank (R5–R1)  
- Gate threshold calibration notes  
- Coverage notes (even light in P0)  
- Published dossier artifact + hashes before LIVE  

### Acceptance

- Registry cannot mark `live` without dossier pass flag  
- Claim width ≤ dossier evidence  

### Phase

- P0: Level-1 mandatory  
- P1A: Level-2 coverage  
- Partner: goldens for qualification only  

---

## 10. C5 — Score Pack + scoring engine

**Scope:** Engine global; packs **per challenge**  
**Primary doc:** `Scoring.md`  

### Requirements

**Engine**

- Load Score Pack by hash  
- Run hard gates fail-closed  
- Compute component scores (physics, robustness, accuracy) per pack weights  
- Emit structured internal result (may include fine margins for ops)  
- **Forbidden:** prior similarity, fee amount, estimate output as score inputs  

**Pack (per challenge)**

- Gate IDs + thresholds  
- Component weights  
- Bound `generator_version`  
- Stress category coverage rules  

### Acceptance

- Unit tests: gate fail → zero / no emission path  
- Same strategy + same hidden draw → same score (determinism policy)  

### Phase

- P0: one pack, physics-heavy weights  

---

## 11. C6 — Seeding / data roles

**Scope:** Global policy  

### Requirements

- Official exam seeds derived from commit/block policy (miner-unknown before eval)  
- Train / eval / stress isolation  
- Mock path: miner-chosen seeds only + `mock_*` packs  
- No MCP tool exposes official seeds  

### Acceptance

- Security tests: MCP handlers cannot return validator seed material  
- Light path rejects non-`mock_` packs  

### Phase

- P0: shared seed policy across validators OK if documented  
- Later: per-validator diversity optional  

---

## 12. C7 — Validator neuron

**Scope:** Global  

### Requirements

1. Pull/accept queued submissions (strategy JSON + hotkey + payment status)  
2. Resolve challenge registry → generator_version + Score Pack  
3. Materialize **hidden** train/eval/stress data  
4. Execute training under strategy constraints (timeouts, resource limits)  
5. Run gates → scoring engine  
6. Persist **internal** result + **budgeted** EvaluationCard  
7. Map scores to on-chain weights per metagraph rules  
8. Fail closed on infra errors without inventing physics passes  

### Acceptance

- End-to-end: known strategy on fixture pack produces expected gate pattern  
- Resource limits prevent runaway jobs  
- Card visible to submitter only via MCP authz  

### Phase

- P0: single-worker validator OK  
- P1: queue scale-out, caching of dossier reference as needed  

### Note

Validator **compute cost** is the main ops limfac — implement timeouts and max epochs from Score Pack / challenge config on day one.

---

## 13. C8 — Miner neuron (optional thin client)

**Scope:** Global  

### Requirements

- Optional: classic Bittensor miner that calls MCP or submits strategies  
- Not required if MCP is the supported agent path  

### Phase

- P0: optional  

---

## 14. C9 — Miner MCP

**Scope:** Global  
**Primary doc:** `Miner_MCP.md` v2.2  

### Requirements (tooling)

| Tool | Req |
|------|-----|
| `get_challenge_info` | Registry-backed |
| `get_prior` | Serve published prior JSON |
| `get_mock_scaffold` | Serve runnable scaffold; **not** prior invert |
| `dry_validate` | Schema + denylist |
| `estimate` | Avoid-atlas + prior_delta; `non_binding` |
| `light_compare` | Shared mock draws; candidate vs scaffold_id |
| `light_train` | Mock only; private metrics |
| `submit` | Fee + queue + SubmitReceipt |
| `get_submission_result` | Budgeted card; submitter authz |

### Requirements (policy)

- Free path never sees VALIDATOR packs/seeds  
- `corr` doctrine: free signal informative but imperfect  
- Phase 0 card: no fine margins / per-stress breakdowns  
- Invariants in Miner_MCP §14 enforced in code where possible  

### Acceptance

- Integration test: agent script free-loops then submits once; card returned  
- Attempt to pass validator pack id into light_* → reject  

### Phase

- P0: all tools above  
- P1: mock rotation hooks, list_my_submissions  

---

## 15. C10 — Prior publisher

**Scope:** Global  

### Requirements

- Input: lean cards (incl. structured failure tags)  
- Pipeline: window → eligibility → k-aggregate → lag → coarsen → noise → redact → channels  
- Output: versioned prior JSON + content_hash  
- Bootstrap prior allowed at launch if marked  

### Acceptance

- No weights/seeds in prior  
- Hard zeros feed avoid_atlas not structural_steer  

### Phase

- P0: manual or semi-manual publish OK  
- P1: automated job  

---

## 16. C11 — Mock packs + scaffolds (**per challenge**)

**Scope:** Per challenge  

### Requirements

- At least one `mock_*` pack with MOCK_RANGES and listed missing stress tags  
- At least one versioned mock scaffold (mediocre, runnable, public)  
- Registry points MCP at active ids  
- Rotation procedure documented (manual OK in P0)  

### Acceptance

- light_compare runs against scaffold on mock pack  
- Official ranges not accessible from light_*  

### Phase

- P0: one each  
- P1: rotation when offline corr too high  

---

## 17. C12 — Evaluation card store

**Scope:** Global  

### Requirements

- Store internal result (ops) and miner-visible card (budgeted)  
- Authz: only submitting hotkey reads full card via MCP  
- Idempotent write on exam completion  

### Acceptance

- Unauthorized hotkey cannot read card  
- Disclosure tier filter applied on read or write  

### Phase

- P0: required  

---

## 18. C13 — Fees and rate limits

**Scope:** Global  

### Requirements

- Small exam fee charged on accept (spam + partial verification recovery)  
- Fee **not** an input to score  
- Optional per-hotkey submit rate limits  
- Policy for identical strategy_hash resubmits  

### Acceptance

- Unpaid submit rejected  
- Score fixtures unchanged by fee amount  

### Phase

- P0: simple fee  

---

## 19. C14 — Leaderboard / public API

**Scope:** Global  

### Requirements

- Public: hotkey, challenge_id, overall_score, timestamp (and rank)  
- Does not expose seeds or fine internal margins  
- Consistent with card overall_score when complete  

### Acceptance

- Matches validator-written scores  

### Phase

- P0: minimal table or API  
- P1: polish / per-challenge pages  

---

## 20. C15 — Bittensor integration

**Scope:** Global  

### Requirements

- Validator sets weights from lean scores per tempo  
- Miner registration / hotkey association with submissions  
- Testnet first  
- Document network UID / hyperparameters ownership  

### Acceptance

- Testnet: scores → weights → visible on metagraph tooling  

### Phase

- P0: testnet  
- P1: mainnet readiness  

---

## 21. C16 — Observability

**Scope:** Global  

### Requirements

- Structured logs: submit, exam start/end, gate fails, errors  
- Metrics: queue depth, exam latency, fail rates, MCP call counts  
- Alerts on validator crash / queue backup  

### Phase

- P0: logs + basic metrics  

---

## 22. C17–C18 — Landscape & Specialist Bank

**Scope:** Global  
**Phase:** **Not in Phase 0 build contract**  

Telemetry may *write* Model Cards in a format Landscape can later read. Do not block launch on causal graph or product battery.

---

## 23. C19 — Reference / truth backends

**Scope:** Per challenge dossier path  

### Requirements

- Phase 0: analytic and/or light FEM / Julia as appropriate to pack  
- Dossier scripts reproducible  
- Version-pin solver containers where used  

### Phase

- P0: minimum bar per `Generator_Creation` phase table  
- P1A: FOSS CFD/FEA where claimed  

---

## 24. Suggested team shape

| Role | Owns |
|------|------|
| Protocol / subnet eng | C7, C15, C13, queue, weights |
| SciML eng | C3, C4, C5 packs, C19, train harness |
| Fullstack / agent eng | C9 MCP, C10–C12, C14 |
| Ops | Registry LIVE, priors/scaffolds publish, mock rotation |

One strong generalist can sequence P0 in series; two people should split **train/validator** vs **MCP/card**.

---

## 25. Phase 0 delivery checklist (send to builder)

- [ ] Pack: generator + MOCK + validator ranges + role split  
- [ ] Dossier Level-1 + registry hashes  
- [ ] Score Pack + engine + gate unit tests  
- [ ] Validator e2e on fixture strategy  
- [ ] MCP free loop (estimate + light_compare + scaffold)  
- [ ] MCP paid loop (submit + budgeted card)  
- [ ] Fee gate  
- [ ] Testnet weights from scores  
- [ ] Minimal leaderboard  
- [ ] Bootstrap prior + one scaffold published  
- [ ] Launch_Bar checklist signed  

---

## 26. Explicit non-goals for the initial contractor SOW

Unless separately contracted:

- Landscape causal / symbolic stack  
- Specialist commercial SKU / product battery  
- Multi-challenge production marketplace UI  
- Automated mock corr rotation service  
- Full commercial CAE mesh pipeline  
- Hermes/Mira vendor-specific plugins  

---

*This document is the engineering requirements map for building Carbon to run. Design authority remains SPEC + appendices; where conflict exists, SPEC and scoring/MCP invariants win.*
