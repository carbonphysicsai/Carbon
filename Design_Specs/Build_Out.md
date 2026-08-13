# Carbon Build-Out Specification

**Audience:** Coding agents, lead engineers, SciML reviewers (Harshdeep-class), contractors.  
**Version:** 1.2  
**Status:** Executable requirements contract  
**Companions:** `SPEC.md`, `Miner_MCP.md` (v2.2), `Scoring.md`, `Generator_Creation.md`, `Generator_Validation.md`, `Evidence_and_Envelope_Standards.md`, `Data_Management.md`, `Launch_Bar.md`, `POC_Burgers_FNO.md`

---

## 0. Read this first — execution plan

### 0.1 Principle

**Coding agents build the full framework.**  
**Humans (SciML / protocol lead) fill science, thresholds, and launch judgment.**

Wherever a human must decide physics or incentives, the agent still ships interfaces, loaders, fixtures with `HUMAN_INPUT` / `TODO(sciml)` markers, and tests that fail closed when human inputs are missing in LIVE mode. An agent never invents gate thresholds, envelope claims, or dossier pass/fail as truth.

### 0.2 Confidence matrix (who owns what)

| ID | Component | Agent confidence | Agent builds | Human fills |
|----|-----------|------------------|--------------|-------------|
| C0 | Monorepo / CI | **High** | All | Review |
| C1 | Challenge registry | **High** | All | LIVE decision |
| C2 | Strategy schema | **High** | All | Rare field adds |
| C3 | Procedural generator | **Med** | Interface, roles, determinism harness, fixture generator | Envelope, sampling law, exclusions |
| C4 | Dossier | **Low** | Script skeleton, artifact layout, registry gate | Pass/fail, reference rank, calibration |
| C5 | Scoring engine + packs | **High** / **Low** | Engine, YAML schema, fail-closed | Thresholds, weights |
| C6 | Seeding / roles | **High** | All policy code + tests | Seed derivation formula confirm |
| C7 | Validator neuron | **Med** | Queue, harness, limits, card write | Train backend accept, BT edge |
| C8 | Miner neuron | **High** | Optional thin client | — |
| C9 | Miner MCP | **High** | All tools + policy guards | Bootstrap prior content |
| C10 | Prior publisher | **Med** | Pipeline + redact tests | Coarsen policy, first prior |
| C11 | Mock packs / scaffolds | **Med** | Format, registry, mock_ guards | MOCK_RANGES, scaffold body |
| C12 | Card store | **High** | All + disclosure filter | Tier policy confirm |
| C13 | Fees | **High** | All | Fee amount |
| C14 | Leaderboard | **High** | All | — |
| C15 | Bittensor | **Med** | Template wiring, weight map stub | Mainnet params |
| C16 | Observability | **High** | All | Alert thresholds |
| C17–18 | Landscape / specialists | **Out P0** | Optional card schema hooks only | Design later |
| C19 | Reference solvers | **Low** | Wrapper + pin skeleton | Convergence evidence |

### 0.3 Agent build sequence (Phase 0)

```text
WAVE A — pure agent (no SciML blocked)
  C0 monorepo + CI
  C2 strategy schema + dry_validate
  C1 registry (file-backed) + hashes
  C6 seeding + mock_ enforcement
  C5 scoring ENGINE + fixture pack numbers
  C12 card store + Phase 0 disclosure filter
  C13 fees
  C9 MCP skeleton: info, prior, scaffold, dry_validate, estimate, submit, get_submission_result
  C14 leaderboard API
  C16 logging

WAVE B — agent frameworks; SciML fills content
  C3 Generator API + Burgers fixture stub (HUMAN_INPUT ranges)
  C11 mock pack schema + one mock_ fixture; scaffold schema + placeholder scaffold
  C9 light_compare / light_train wired to TrainEvalAPI stub
  C10 prior pipeline code + bootstrap prior JSON placeholder
  C4 dossier directory layout + “cannot LIVE without dossier flag”
  C19 reference runner interface

WAVE C — integrate
  C7 validator: queue → generate hidden → TrainEvalAPI → score → card
  C9 e2e: free loop then paid loop against local validator
  C15 testnet weight mapping

WAVE D — human gates (not agent-owned)
  SciML: real envelope, dossier Level-1, gate thresholds, MOCK incompleteness, scaffold mediocrity
  Protocol: Launch_Bar (+ MCP §2.4), testnet, fee value, LIVE flip
```

### 0.4 Hard interfaces

```text
Generator.generate(seed, role, params) -> Batch
TrainEvalAPI.run(strategy, batches, mode: mock|official, limits) -> RunMetrics
ScoreEngine.evaluate(metrics, pack, stress_batches?) -> InternalResult
CardStore.write_internal / read_budgeted
```

`mode="mock"` must refuse non-`mock_` packs and validator seeds.

### 0.5 HUMAN_INPUT convention

Null thresholds tagged `BLOCKED_FOR_LIVE_UNTIL_SET`. Registry cannot go `live` while any remain.

### 0.6 Agent PR definition of done

Fixtures green; LIVE fails closed without human inputs; no invented physics thresholds as production truth.

---

## 1. What “running Carbon” means

```text
Miner/agent → Miner MCP (free loop + submit)
               ↓
Validator  → hidden data → train → physics gates → Score Pack → card
               ↓
Network    → weights from lean scores only
               ↓
Public     → leaderboard + budgeted feedback
               ↓
Ops        → priors + mock scaffolds from verified cards
```

Phase 0 = one challenge vertical slice.

### 1.1 Model Card vs EvaluationCard

| Record | Audience | Contents |
|--------|----------|----------|
| **Model Card / InternalResult** | Ops, CI, later Landscape | Full gate vectors, margins, pack hash, generator version, seed *roles*, diagnostics |
| **EvaluationCard** | Submitting miner via MCP | **Budgeted** projection: overall, coarse components, gate pass/fail, failure tags, short diagnostics — **no** seeds, draw ids, fine margins, per-stress breakdowns |

Validator writes both (or writes internal and derives budgeted on read). Landscape compounds only from Launch-Bar-grade Model Cards, not from free-path mock metrics.

### 1.2 Target layout vs current repo

Build_Out target tree: `carbon/`, `packs/`, `mcp/`, `neurons/`, `tests/`.

**Current repo may still use** `poc/`, `Carbon_Logic/`, `neurons/`, `Julia/`. Agents must **map**, not blindly delete:

| Current | Role in Wave B/C |
|---------|------------------|
| `poc/` | Prefer as TrainEvalAPI + Burgers fixture home until promoted |
| `Carbon_Logic/` | Library code to fold under `carbon/` when safe |
| `neurons/` | Validator/miner entrypoints |
| `Design_Specs/` | Normative docs |

Greenfield rename is optional; **interfaces and tests matter more than directory names** in P0.

### 1.3 PoC handoff

`POC_Burgers_FNO.md` proves the atomic lean loop **without** MCP. Build_Out Phase 0 **adds** MCP, fees, cards, testnet on top of that TrainEvalAPI. PoC green is a dependency of P0, not a competing definition of done.

---

## 2. Component map

| ID | Component | Scope | P0 |
|----|-----------|-------|----|
| C0–C2, C5 engine, C6, C9, C12–C16 | Global infrastructure | Global | Required |
| C3, C4, C5 pack, C11, C19 | Challenge pack | **Per challenge** | 1 pack |
| C7 | Validator | Global | Required |
| C10 | Prior publisher | Global | Bootstrap OK |
| C17–C18 | Landscape / Specialist | Global | **Out** |

---

## 3. Phase milestones

**P0:** one real loop — pack, dossier, score, validator, MCP free+paid, testnet, Launch_Bar (+ MCP §2.4).  
**Out of P0:** Landscape graph, specialist SKUs, automated mock corr service, commercial CAE.  
**1A / 1B / 2:** more packs, automated priors, mock rotation, mainnet, product path.

---

## 4. Components (summary requirements)

**C0–C2, C6, C12–C14, C16:** Agent-owned; High confidence.  
**C3–C4, C11, C19:** Agent builds framework + fixtures; SciML fills physics/dossier/ranges.  
**C5:** Agent builds engine; human sets thresholds (45/30/25 is a Score Pack proposal for Burgers, not engine law).  
**C7:** Agent builds harness calling TrainEvalAPI; human owns production train quality.  
**C9:** Normative surface = `Miner_MCP.md` v2.2 — free loop first, paid rare.  
**C10:** Pipeline code agent; bootstrap content human.  
**C15:** Testnet in P0; mainnet human.  
**C17–C18:** Out of P0 SOW.

Full acceptance criteria and Wave ownership remain as in v1.1 confidence matrix (§0.2).

---

## 5. TrainEvalAPI (critical shared contract)

Agent ships interface + stub returning deterministic fake metrics for CI. SciML/dev replaces with real NO train. Validator and MCP both call the same API.

---

## 6. Phase 0 checklist

**Agent:** C0–C2, C5 engine, C6, C9 tools, C12–C14, C3/C11/C4/C10 frameworks, C7 e2e on fixture, C15 testnet stub.  
**Human before LIVE:** envelope, dossier Level-1, thresholds, MOCK incompleteness, scaffold mediocrity, real TrainEvalAPI, Launch_Bar (+ §2.4 MCP) signed.

---

## 7. Non-goals (initial SOW)

Landscape causal stack · specialist SKU · marketplace UI · automated corr-rotation service · commercial CAE mesh pipeline · per-lab agent plugins · agent-invented LIVE thresholds.

---

## 8. Doctrine for coding agents

1. Build the stadium and the rules engine.  
2. Leave physics calibration to SciML.  
3. Fail closed when human inputs are missing.  
4. Prefer one vertical fixture loop over ten empty modules.  
5. Enforce Miner_MCP invariants in code.  
6. Never present placeholder thresholds as production truth.  

---

*Build_Out v1.2 — coherency with Miner_MCP, Scoring, Launch_Bar, POC handoff. Design authority: SPEC + Miner_MCP + Scoring.*
