# Carbon Build-Out Specification

**Audience:** Coding agents, lead engineers, SciML reviewers, contractors.  
**Version:** 1.1  
**Status:** Executable requirements contract  
**Companions:** `SPEC.md`, `Miner_MCP.md` (v2.2), `Scoring.md`, `Generator_Creation.md`, `Generator_Validation.md`, `Evidence_and_Envelope_Standards.md`, `Data_Management.md`, `Launch_Bar.md`

---

## 0. Read this first — execution plan

### 0.1 Principle

**Coding agents build the full framework.**  
**Humans (SciML / protocol lead) fill science, thresholds, and launch judgment.**

Wherever a human must decide physics or incentives, the agent still ships:

- interfaces and types  
- loaders and registries  
- validation hooks  
- fixture packs with **clear `HUMAN_INPUT` / `TODO(sciml)` markers**  
- tests that pass against fixtures and fail closed when human inputs are missing in LIVE mode  

An agent never invents gate thresholds, envelope claims, or dossier pass/fail as truth.

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

Execute in order. Do not start C7 train integration before `TrainEvalAPI` exists (stub allowed).

```text
WAVE A — pure agent (no SciML blocked)
  C0 monorepo + CI
  C2 strategy schema + dry_validate
  C1 registry (file-backed) + hashes
  C6 seeding + mock_ enforcement
  C5 scoring ENGINE (load pack, gates fail-closed) + fixture pack numbers
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
  C8 optional

WAVE D — human gates (not agent-owned)
  SciML: real envelope, dossier Level-1, gate thresholds, MOCK incompleteness, scaffold mediocrity
  Protocol: Launch_Bar, testnet, fee value, LIVE flip
```

### 0.4 Hard interfaces the agent must define early

These are the contracts everything hangs on. Ship them in Wave A/B even with stub implementations.

```text
# packs/interfaces.py (normative names)

class Generator(Protocol):
    version: str
    def generate(self, seed: int, role: Literal["train","eval","stress"], params: dict) -> Batch: ...

class TrainEvalAPI(Protocol):
    """Used by validator AND light_compare/light_train."""
    def run(self, strategy: dict, batches: list[Batch], *, mode: Literal["mock","official"],
            limits: ResourceLimits) -> RunMetrics: ...

class ScoreEngine(Protocol):
    def evaluate(self, metrics: RunMetrics, pack: ScorePack, stress_batches: list[Batch] | None) -> InternalResult: ...

class CardStore(Protocol):
    def write_internal(self, submission_id: str, result: InternalResult) -> None: ...
    def read_budgeted(self, submission_id: str, hotkey: str) -> EvaluationCard: ...
```

**Rule:** `mode="mock"` path must refuse non-`mock_` packs and validator seeds. Enforce in code.

### 0.5 `HUMAN_INPUT` convention

Any file or field the agent cannot truthfully complete:

```yaml
# Example in score pack
thresholds:
  conservation_rel: null  # HUMAN_INPUT(sciml): set from dossier calibration
  _status: BLOCKED_FOR_LIVE_UNTIL_SET
```

Registry must not transition `status: live` while any `BLOCKED_FOR_LIVE_UNTIL_SET` remains on that challenge.

### 0.6 Definition of done for an agent PR

- Implements the framework for its Wave  
- Tests pass on fixtures  
- LIVE-path fails closed without human inputs  
- No invented physics thresholds presented as final  
- Cross-links to this doc component IDs in PR description  

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

Phase 0 = one challenge vertical slice. Not a horizontal demo of every future feature.

---

## 2. Component map

| ID | Component | Scope | P0 |
|----|-----------|-------|----|
| C0 | Monorepo, packaging, CI | Global | Required |
| C1 | Challenge registry | Global + rows | Required |
| C2 | Strategy schema + denylist | Global | Required |
| C3 | Procedural generator | **Per challenge** | 1 pack |
| C4 | Generator dossier | **Per challenge** | Level-1 |
| C5 | Score Pack + engine | Engine global; pack per challenge | Required |
| C6 | Seeding / data roles | Global | Required |
| C7 | Validator neuron | Global | Required |
| C8 | Miner neuron | Global | Optional |
| C9 | Miner MCP | Global | Required |
| C10 | Prior publisher | Global | Bootstrap OK |
| C11 | Mock packs + scaffolds | **Per challenge** | 1+1 |
| C12 | Evaluation card store | Global | Required |
| C13 | Fees / rate limits | Global | Required |
| C14 | Leaderboard / public API | Global | Minimal |
| C15 | Bittensor integration | Global | Testnet |
| C16 | Observability | Global | Basic |
| C17 | Landscape agent | Global | **Out** |
| C18 | Specialist bank | Global | **Out** |
| C19 | Reference / truth backends | Per challenge | Min bar |

**Global once:** MCP, validator harness, scoring engine, cards, fees, BT, CI.  
**Per challenge pack:** generator, dossier, score pack, mock pack, scaffold, registry row.

---

## 3. Phase milestones

### Phase 0 — one real loop

| ID | Done when |
|----|-----------|
| P0.1 | Generator deterministic `(seed, role)`; train≠eval≠stress; MOCK ⊂ envelope |
| P0.2 | Level-1 dossier; claim ≤ evidence; LIVE blocked until flag |
| P0.3 | Score Pack bound to generator_version; hard gates; no prior similarity |
| P0.4 | Validator: strategy → hidden data → train → gates → card |
| P0.5 | MCP tools complete per Miner_MCP v2.2 |
| P0.6 | Free path: estimate + light_compare; mock only |
| P0.7 | Paid path: fee → queue → budgeted card |
| P0.8 | Testnet weights + minimal leaderboard |
| P0.9 | Launch_Bar green |

**Out of P0:** Landscape graph, specialist SKUs, automated mock corr service, commercial CAE, per-lab agent plugins.

### Phase 1A / 1B / 2

- **1A:** more packs, automated priors, mock rotation, FOSS reference depth, mainnet candidate  
- **1B:** harder screening packs only with matching dossiers; partner goldens  
- **2:** Landscape ranking, specialist pilot, sponsored challenges  

---

## 4. Component requirements

Each component: **Agent builds** · **Human fills** · **Requirements** · **Acceptance** · **Phase**

---

### C0 — Monorepo, packaging, CI

**Agent:** High — build all.  

**Requirements**

- `pyproject.toml`; `pip install -e .`  
- Layout: `carbon/`, `neurons/`, `packs/`, `mcp/`, `tests/`  
- CI: lint, unit, schema tests  
- Docker targets: `validator`, `mcp`  

**Acceptance:** clean clone → install → tests pass.  
**Phase:** P0 Wave A.

---

### C1 — Challenge registry

**Agent:** High — build all.  
**Human:** LIVE flip only after dossier + thresholds set.

**Requirements**

Record fields: `challenge_id`, `generator_version`, `scoring_pack_hash`, `schema_version`, `disclosure_tier`, `mock_pack_ids[]`, `scaffold_id`, fee, `status ∈ {draft,dossier,live,retired}`, content hashes.

**Acceptance:** MCP reads registry only; submit rejects non-live; LIVE blocked if HUMAN_INPUT nulls remain.  
**Phase:** P0 Wave A.

---

### C2 — Strategy schema

**Agent:** High — build all.

**Requirements**

- Versioned JSON Schema  
- Denylist: `eval_seed`, `stress_seed`, official `generator_pack_hash`, gate disables  
- `dry_validate` implements schema + denylist  

**Acceptance:** invalid strategies never train.  
**Phase:** P0 Wave A.

---

### C3 — Procedural generator (per challenge)

**Agent:** Medium — **framework required**; physics content is human.

**Agent builds**

- `Generator` protocol + registration  
- `generate(seed, role, params)` dispatch  
- Determinism tests (fixed seed replay)  
- Role isolation tests  
- Envelope schema + exclusion list structure  
- **Fixture generator** (e.g. simple Burgers-like) marked `fixture` so MCP/validator e2e work before SciML pack  

**Human fills**

- Real sampling distributions  
- Envelope bounds and excluded regimes  
- Anti-degenerate rules content  
- Generator version string for LIVE  

**Requirements**

- Deterministic `(generator_version, seed, role, params)`  
- train≠eval≠stress  
- Public generator family code  

**Acceptance:** fixture path green in CI; LIVE path requires human pack + dossier flag.  
**Phase:** P0 Wave B framework; SciML before LIVE.

---

### C4 — Generator dossier (per challenge)

**Agent:** Low science / **High framework**.

**Agent builds**

- Directory layout: `packs/<id>/dossier/`  
- Template markdown/JSON for Level-1 sections  
- Scripts that *run* reference checks when configured  
- Registry field `dossier_passed: bool` default false  
- CI check: `status=live` ⇒ `dossier_passed`  

**Human fills**

- Reference rank, convergence results, calibration notes, pass decision  

**Acceptance:** cannot mark LIVE without dossier_passed.  
**Phase:** P0 Wave B framework; SciML sign-off P0.2.

---

### C5 — Score Pack + scoring engine

**Agent:** Engine **High**; thresholds **Low**.

**Agent builds**

- Score Pack YAML schema  
- Engine: load by hash, hard gates fail-closed, component weights, InternalResult  
- Forbidden inputs enforced (no prior similarity, no fee)  
- Fixture pack with **placeholder thresholds** tagged HUMAN_INPUT  
- Unit tests: gate fail → non-emitting outcome  

**Human fills**

- Gate IDs that matter for the physics  
- Numeric thresholds from dossier  
- Component weights (physics-heavy default allowed as proposal, human confirms)  

**Acceptance:** engine tests green; LIVE pack has no null thresholds.  
**Phase:** P0 Wave A engine; SciML pack numbers before LIVE.

---

### C6 — Seeding / data roles

**Agent:** High — build all.

**Requirements**

- Official seeds from documented commit/block policy  
- Mock: miner seeds only + `mock_*`  
- MCP never returns official seeds  
- light_* rejects non-mock packs  

**Acceptance:** security unit tests for leak paths.  
**Phase:** P0 Wave A.

---

### C7 — Validator neuron

**Agent:** Medium — build harness; plug TrainEvalAPI.

**Agent builds**

- Submission queue + fee check  
- Resolve registry → generator + pack  
- Materialize hidden train/eval/stress  
- Call `TrainEvalAPI.run(..., mode="official")` with resource limits  
- ScoreEngine → write internal + budgeted card  
- Weight mapping stub for C15  
- Timeouts/max steps from config (no unbounded train)  

**Human fills**

- Production TrainEvalAPI implementation quality  
- Limit values informed by GPU budget  
- BT operational wiring acceptance  

**Acceptance:** e2e on fixture strategy; OOM/timeout fail closed (not physics pass).  
**Phase:** P0 Wave C.

---

### C8 — Miner neuron (optional)

**Agent:** High. Thin client calling MCP or submit API.  
**Phase:** P0 optional.

---

### C9 — Miner MCP

**Agent:** High — primary agent-owned surface.  
**Spec:** `Miner_MCP.md` v2.2 (normative).

**Agent builds (all tools)**

| Tool | Notes |
|------|-------|
| `get_challenge_info` | Registry |
| `get_prior` | Blob store |
| `get_mock_scaffold` | Scaffold registry; not prior invert |
| `dry_validate` | C2 |
| `estimate` | Avoid-atlas + prior_delta; non_binding |
| `light_compare` | Shared mock draws vs scaffold_id |
| `light_train` | Mock only |
| `submit` | Fee + queue + receipt |
| `get_submission_result` | Budgeted card, authz |

**Policy in code:** mock isolation; no predicted lean_score; Phase 0 disclosure tier.

**Human fills:** bootstrap prior content; first real scaffold body (agent can ship placeholder).

**Acceptance:** integration test free-loop → one submit → card; validator pack id to light_* rejected.  
**Phase:** P0 Waves A–C.

---

### C10 — Prior publisher

**Agent:** Medium — pipeline code high.

**Agent builds**

- Card intake → window → eligibility → k-aggregate → lag → coarsen → noise → redact → channels  
- Output versioned JSON + hash  
- Tests: no weights/seeds in output; hard zeros → avoid_atlas  
- Bootstrap prior file path  

**Human fills:** coarsen bins, lag length, first bootstrap content.  
**Phase:** P0 framework + bootstrap; automate P1.

---

### C11 — Mock packs + scaffolds (per challenge)

**Agent:** Medium — format and guards high.

**Agent builds**

- Mock pack schema (`mock_` prefix enforced)  
- `missing_stress_tags[]` field  
- Scaffold schema + registry  
- Placeholder scaffold strategy JSON  
- Rotation doc + manual CLI stub  

**Human fills:** MOCK_RANGES incompleteness, scaffold mediocrity, when to rotate.  
**Acceptance:** light_compare works on fixture mock; official ranges blocked.  
**Phase:** P0 Wave B.

---

### C12 — Evaluation card store

**Agent:** High.

**Requirements**

- Internal result (ops) vs budgeted card (miner)  
- Phase 0 allowlist: status, hashes, overall, coarse components, gate pass/fail, failure tags, short diagnostics  
- **Withhold:** fine margins, per-stress breakdowns, seeds  
- Authz by submitting hotkey  

**Acceptance:** unauthorized read fails; allowlist tested.  
**Phase:** P0 Wave A.

---

### C13 — Fees / rate limits

**Agent:** High. Fee on accept; not a score input; optional rate limits.  
**Human:** fee amount.  
**Phase:** P0 Wave A.

---

### C14 — Leaderboard / public API

**Agent:** High. Public: hotkey, challenge_id, overall_score, time, rank. No seeds/margins.  
**Phase:** P0 Wave A.

---

### C15 — Bittensor integration

**Agent:** Medium — template + weight map from lean scores.  
**Human:** network UID, hyperparams, mainnet.  
**Acceptance:** testnet scores → weights visible.  
**Phase:** P0 Wave C testnet.

---

### C16 — Observability

**Agent:** High. Structured logs + basic metrics (queue, latency, fail rates, MCP counts).  
**Phase:** P0 Wave A.

---

### C17–C18 — Landscape / Specialist bank

**Out of P0.** Agent may emit Model Card-shaped JSON from exams for future read path. Do not build causal graph or product battery in P0 SOW.

---

### C19 — Reference / truth backends

**Agent:** Low science / framework wrappers.

**Agent builds:** `ReferenceSolver` protocol, container pin config, dossier script hooks.  
**Human:** convergence runs, rank claim.  
**Phase:** P0 framework; SciML evidence before LIVE.

---

## 5. TrainEvalAPI (critical shared contract)

Agent ships interface + **stub** that returns deterministic fake metrics for CI.

```text
run(strategy, batches, mode, limits) -> RunMetrics
```

| mode | Allowed data |
|------|----------------|
| `mock` | mock packs, miner seeds |
| `official` | validator generator roles, hidden seeds |

SciML/dev replaces stub with real NO train (JAX/PyTorch). Validator and MCP both call the same API so light_compare and official exam do not diverge in harness bugs.

---

## 6. Team / agent operating model

| Role | Owns |
|------|------|
| **Coding agent** | Waves A–C frameworks, tests, MCP, registry, engine, cards, fees, guards |
| **SciML lead (Harshdeep-class)** | C3 content, C4 pass, C5 thresholds, C11 ranges/scaffold, C19 evidence |
| **Protocol / founder** | Launch_Bar, fee, LIVE, BT network params, incentive edge cases |
| **Dev maintainer** | Production TrainEvalAPI, GPU ops, C7 hardening, C15 mainnet |

**Rule:** Agent opens PRs with `HUMAN_INPUT` list in the description for SciML.

---

## 7. Phase 0 checklist

### Agent-deliverable

- [ ] C0 CI green  
- [ ] C1–C2 registry + schema + dry_validate  
- [ ] C5 engine + fixture pack schema  
- [ ] C6 seed/mock guards tested  
- [ ] C9 all MCP tools against stubs  
- [ ] C12 budgeted cards  
- [ ] C13 fee gate  
- [ ] C14 leaderboard  
- [ ] C3/C11/C4/C10 frameworks + placeholders  
- [ ] C7 e2e on fixture TrainEvalAPI  
- [ ] C15 testnet stub path  

### Human-deliverable before LIVE

- [ ] Real generator envelope + sampling  
- [ ] Dossier Level-1 passed  
- [ ] Score thresholds set (no nulls)  
- [ ] MOCK incompleteness intentional  
- [ ] Scaffold mediocre but fair  
- [ ] TrainEvalAPI real backend  
- [ ] Launch_Bar signed  

---

## 8. Non-goals (initial SOW)

- Landscape causal/symbolic stack  
- Specialist commercial SKU  
- Marketplace UI  
- Automated corr-rotation service (manual OK)  
- Full commercial CAE mesh pipeline  
- Hermes/Mira vendor plugins  
- Agent-invented LIVE physics thresholds  

---

## 9. Doctrine for coding agents

1. Build the stadium and the rules engine.  
2. Leave the physics calibration to SciML.  
3. Fail closed when human inputs are missing.  
4. Prefer one vertical fixture loop over ten empty modules.  
5. Enforce Miner_MCP invariants in code (mock isolation, no prior-in-score, budgeted cards).  
6. Never present placeholder thresholds as production truth.  

---

*Build_Out v1.1 — agent execution plan, confidence matrix, framework-first SciML slots. Design authority: SPEC + Miner_MCP + Scoring; this doc is the build map.*
