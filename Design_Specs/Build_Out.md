# Carbon Build-Out Specification

> **Reconciliation:** sequencing authority only. Scoring: binary gates + weighted geometric; P0 baseline **0.45/0.30/0.25**.


> **Reconciliation (post-ratification):** `Build_Out.md` remains **sequencing authority**, not an alternate design spec. Reflect reconciled semantics only after higher-level docs (`Scoring.md`, `Trustless_Verification.md`, `Miner_MCP.md`, `Launch_Bar.md`) are treated as source of truth. Do not re-introduce sigmoid-hard-gates, raw soft-leg multiplication as normative aggregate, or mock-as-false-physics language in tickets.


**Audience:** Coding agents, lead engineers, SciML reviewers, contractors.  
**Version:** 1.4  
**Status:** Executable requirements contract  
**Companions:** `SPEC.md`, `Miner_MCP.md` (v2.2+), `Scoring.md`, `Generator_Creation.md`, `Generator_Validation.md`, `Evidence_and_Envelope_Standards.md`, `Data_Management.md`, `Launch_Bar.md`, `POC_Burgers_FNO.md`  
**Post-P0 companions:** `Landscape_Agent.md`, `Specialist_Bank.md`, `Customer_Bounds_Specialist.md`, `Use_Cases_by_Phase.md`

---

## 0. Normative authority (read first)

Authority is **domain-owned**, not a single global precedence ladder. When documents overlap, use the document that owns the semantic domain below. A higher-level document's example does not override the domain owner's normative rule.

| Domain | Canonical owner |
|--------|-----------------|
| System architecture / protocol doctrine / constitutional invariants | `SPEC.md` |
| Miner-facing behaviour, free vs paid loop, disclosure | `Miner_MCP.md` |
| Exact scoring mathematics, forbidden score inputs, Score Pack schema | `Scoring.md` |
| Official data, seed hierarchy, train/eval/stress separation | `Data_Management.md` + `Trustless_Verification.md` |
| Generator construction, scientific evidence, envelope qualification | `Generator_Creation.md`, `Generator_Validation.md`, `Evidence_and_Envelope_Standards.md` |
| Stop-ship and representation readiness | `Launch_Bar.md` |
| Commercial specialist qualification | `Specialist_Bank.md` |
| Landscape knowledge-layer behaviour | `Landscape_Agent.md` |
| Implementation sequencing, ownership, dependencies, Wave acceptance | **This file (`Build_Out.md`)** |

`Build_Out.md` does **not** override semantic behaviour owned by another domain document. If two documents within the same domain materially conflict, stop the affected implementation, record the exact conflict, and request a human decision rather than inventing a resolution.

**No historical version pointers.** Acceptance criteria live in the current documents — not in “v1.1 somewhere.”

## 1. Execution principle

**Coding agents build the full framework.**  
**Humans (SciML / protocol lead) fill science, thresholds, and launch judgment.**

Agents ship interfaces, loaders, fixtures with `HUMAN_INPUT` / `TODO(sciml)` markers, and tests that **fail closed** when human inputs are missing in LIVE mode. Agents never invent gate thresholds, envelope claims, or dossier pass/fail as production truth.

**P0 doctrine:** Prefer one vertical fixture loop over ten empty modules.

---

## 2. Cross-cutting invariants (never violate)

These rules bind every component. Tests must cover them where enforceable in code.

1. **No seed leakage.** Official seeds, derived seeds, draw IDs, or reversible identifiers never appear in EvaluationCard, leaderboard, MCP outputs, or miner-visible logs.
2. **Mock isolation.** Mock / light execution never accesses official packs, official seeds, or hidden exam data.
3. **Pinned evaluation.** Every scored submission is bound to immutable challenge / generator / Score Pack / backend (container digest) versions.
4. **Disclosure allow-list.** InternalResult / Model Card fields are never returned on miner-facing APIs unless explicitly allow-listed for the disclosure tier.
5. **LIVE requires qualification.** LIVE challenges require a complete signed human qualification manifest for that exact challenge version (not merely non-null YAML).
6. **Execution isolation.** Miner-supplied strategies run under enforced compute, network, filesystem, and wall-clock limits. Strategy execution isolation is a **P0 security invariant** (implementation may live in ops docs; requirement is here).
7. **Infra ≠ science.** Infrastructure failures (OOM policy kill, node death, queue loss) are never scored as scientific / physics failures and never grant emissions.
8. **Determinism.** Re-running an identical official evaluation under identical versions, seeds, and limits is deterministic within documented tolerances.
9. **No placeholder LIVE.** Placeholder, fixture, or mock values never enter LIVE configuration or emission weights.
10. **No silent rescore.** Historical evaluation records are never silently reinterpreted under newer packs; new pack ⇒ new scoring_version for future runs only.
11. **Forbidden score inputs.** Prior similarity, `estimate` / `light_*` metrics, exam fee, and mock metrics never enter `S_combined` / Yuma weights.
12. **Free path imperfect.** Free-loop signal may be directionally useful but must remain a **non-oracle** vs the official exam (no reliable rank substitution / exam reconstruction; see Miner_MCP).

---

## 3. Confidence matrix (who owns what)

| ID | Component | Agent confidence | Agent builds | Human fills |
|----|-----------|------------------|--------------|-------------|
| C0 | Monorepo / CI | **High** | All | Review |
| C1 | Challenge registry | **High** | All + LIVE gate enforcement | LIVE decision + qualification artifacts |
| C2 | Strategy schema | **High** | All | Rare field adds |
| C3 | Procedural generator | **Med** | Interface, roles, determinism harness, fixture generator | Envelope, sampling law, exclusions |
| C4 | Dossier | **Low** | Script skeleton, artifact layout, registry gate | Pass/fail, reference rank, calibration |
| C5 | Scoring engine + packs | **High** / **Low** | Engine, YAML schema, fail-closed, forbidden-input guards | Thresholds, weights |
| C6 | Seeding / roles | **High** | Domain separation + leakage tests | Seed derivation formula confirm |
| C7 | Validator neuron | **Med** | Queue, FSM, harness, isolation limits, card write | Train backend quality, BT ops |
| C8 | Miner neuron | **High** | Optional thin client | — |
| C9 | Miner MCP | **High** | All tools + policy guards | Bootstrap prior content |
| C10 | Prior publisher | **Med** | Pipeline + redact tests | Coarsen policy, first prior |
| C11 | Mock packs / scaffolds | **Med** | Format, registry, mock_ guards | MOCK_RANGES, scaffold body |
| C12 | Card store | **High** | Internal + budgeted paths | Disclosure tier confirm |
| C13 | Fees | **High** | Ledger, idempotency, fee≠score | Fee amount |
| C14 | Leaderboard | **High** | Public fields only | — |
| C15 | Bittensor | **Med** | Wiring + weight map | Mainnet params |
| C16 | Observability | **High** | Logs/metrics | Alert thresholds |
| C17–18 | Landscape / specialists | **Out P0** | Card schema hooks only in P0; Waves E–F in §18 | See `Landscape_Agent.md`, `Specialist_Bank.md` |
| C19 | Reference solvers | **Low** | Wrapper + pin skeleton | Convergence evidence |

---

## 4. Phase 0 waves

```text
WAVE A — infrastructure science cannot block
  C0 CI · C2 schema · C1 registry · C6 seeds/mock guards
  C5 scoring ENGINE + fixture pack schema (HUMAN_INPUT thresholds OK)
  C12 card store + Phase 0 disclosure filter
  C13 fees + submission_id + FSM skeleton
  C9 MCP: info, prior, scaffold, dry_validate, estimate, submit, get_submission_result
  C14 leaderboard · C16 logging
  TrainEvalAPI STUB (deterministic fake metrics; never emission-capable)

WAVE B — science-ready skeletons
  C3 Generator API + Burgers fixture (HUMAN_INPUT ranges)
  C11 mock pack + placeholder scaffold
  C9 light_compare / light_train → TrainEvalAPI (stub or real)
  C10 prior pipeline + bootstrap prior placeholder
  C4 dossier layout + qualification manifest schema
  C19 reference runner interface

WAVE C — vertical integration
  Real TrainEvalAPI (or PoC-promoted backend) behind official + mock modes
  C7 validator: queue → hidden data → run → score → cards
  MCP e2e: free loop then paid loop
  C15: actual Bittensor testnet path (not stub-only)

WAVE D — human qualification (not agent-owned)
  SciML: envelope, dossier Level-1, thresholds, MOCK incompleteness, scaffold mediocrity
  Protocol: Launch_Bar (+ MCP §2.4), fee value, qualification manifest signed, LIVE flip

POST-P0 (not required for P0; see §18)
  WAVE E — Landscape signals          → Landscape_Agent.md
  WAVE F — Specialist bank            → Specialist_Bank.md
  WAVE G — Customer bounds / sponsors → Customer_Bounds_Specialist.md
```

**Stub policy:** Wave A/B may use TrainEvalAPI stubs for CI and MCP plumbing. **Stub metrics must never write emission weights or LIVE leaderboard ranks.** Wave C swaps in real backend before testnet acceptance.

---

## 5. TrainEvalAPI (critical shared contract)

Used by **validator official path** and **MCP light_compare / light_train**. One harness; mode selects data rights.

### 5.1 Signature (conceptual)

```text
run(
  strategy: dict,
  batches: list[Batch],
  mode: "mock" | "official",
  limits: ResourceLimits,
  pin: EvaluationPin   # challenge_id, generator_version, pack_hash, strategy_hash, env_digest
) -> RunResult
```

### 5.2 ResourceLimits (minimum)

- max_steps / max_epochs  
- wall_clock_seconds  
- max_vram_mb (if applicable)  
- max_cpu_cores  
- network: deny by default  
- filesystem: scratch only  

### 5.3 RunResult status classes

| status | Meaning | Score? |
|--------|---------|--------|
| `success` | Finished; metrics populated | Yes — feed ScoreEngine |
| `invalid_strategy` | Schema/denylist/unsupported backbone | No — REJECTED |
| `timeout` | Hit wall clock / step cap | No emissions; card may note limit |
| `resource_violation` | OOM / limit kill | **FAILED_INFRA** path — not physics fail |
| `numerical_failure` | NaN/Inf during train | Gate/scientific fail path |
| `train_failure` | Optimizer/crash in user strategy | Scientific / strategy fail |
| `infra_failure` | Node/queue/storage fault | **FAILED_INFRA** — retry/refund policy |
| `incomplete_metrics` | Partial metrics; cannot score | Fail closed |

### 5.4 EvaluationPin (reproducibility)

Every official run records: `strategy_hash`, `challenge_id`, `generator_version`, `scoring_pack_hash`, `env_digest` (container/image), `limits` snapshot, seed **roles** (not raw official seeds on miner path).

### 5.5 Mode rules

| mode | Allowed data | Emissions |
|------|----------------|-----------|
| `mock` | `mock_*` packs, miner-chosen seeds only | Never |
| `official` | Validator generator roles, hidden seeds | Only if scored under LIVE pack |

`mode=mock` **must refuse** non-`mock_` packs and official seeds.

---

## 6. Submission lifecycle

Every `submit` returns a permanent **`submission_id`**.

### 6.1 States

```text
RECEIVED → VALIDATED → QUEUED → RUNNING → SCORED → PUBLISHED
```

Exceptional:

```text
REJECTED          # schema/denylist/fee/auth
FAILED_STRATEGY   # train/numerical attributable to strategy
FAILED_INFRA      # Carbon/validator infrastructure
CANCELLED         # policy-defined
```

### 6.2 Fee & idempotency semantics

| Event | Fee | Notes |
|-------|-----|-------|
| REJECTED before queue | Not charged / refund | Invalid strategy, unpaid, non-LIVE challenge |
| FAILED_INFRA | Refund or retry credit | Never scored as physics zero for emissions blame |
| FAILED_STRATEGY / SCORED | Charged | Exam was delivered |
| Duplicate `strategy_hash` + hotkey + challenge version | Policy: reject or no-op with same `submission_id` | Define one; default **idempotent return of existing id** if still open |
| `get_submission_result` | Read-only | Repeatable; no re-charge |
| Validator crash mid-RUNNING | → FAILED_INFRA or re-QUEUED | Must not emit partial physics scores |

Fee amount is human-set; **fee is never a score input**.

---

## 7. Seeding (C6)

### 7.1 Seed domains (must not collide)

Separate namespaces for:

```text
mock | official_train | official_eval | official_stress | reference | dossier
```

Derivation formulas are human-confirmed; **domain separation is agent-enforced**.

### 7.2 Required tests

- Role split: train ≠ eval ≠ stress draws  
- Leakage: no official seed / draw id / reversible identifier in EvaluationCard, leaderboard, MCP, miner logs  
- Mock path cannot derive official domain seeds  

---

## 8. LIVE qualification manifest

Non-null thresholds are **necessary but not sufficient**.

LIVE requires a **qualification manifest** bound to the exact challenge version, with artifact hashes, e.g.:

```text
generator_envelope:     APPROVED  + content_hash
generator_validation:   PASSED    + dossier_hash
dossier_level_1:        APPROVED  + signoff
score_pack:             APPROVED  + pack_hash
mock_incompleteness:    APPROVED  + mock_pack_ids
train_backend:          QUALIFIED + env_digest
launch_bar:             SIGNED    + checklist_ref
mcp_readiness:          SIGNED    + Launch_Bar §2.4
```

Registry transition to `live` **fails** unless all required slots are present and hashes match the artifacts being activated. Agents implement the gate; humans produce the approvals.

---

## 9. Model Card vs EvaluationCard

| Record | Audience | Contents |
|--------|----------|----------|
| **Model Card / InternalResult** | Ops, CI, later Landscape | Full gates, margins, pack hash, generator version, seed *roles*, pin, diagnostics |
| **EvaluationCard** | Submitting miner (MCP) | Budgeted: overall, coarse components, gate pass/fail, failure tags, short diagnostics — **no** seeds, draw ids, fine margins, per-stress breakdowns |

Landscape (future) compounds **only** from Launch-Bar-grade Model Cards — never from free-path mock metrics.

---

## 10. Pack format (per challenge)

One challenge = one pack directory (name flexible; contents mandatory):

```text
packs/<challenge_id>/
  generator/          # code + version
  ranges/             # MOCK_RANGES + official envelope refs
  scoring/            # Score Pack YAML + hash
  dossier/            # Level-1 artifacts + signoff slots
  mock/               # mock pack ids + missing_stress_tags
  scaffolds/          # versioned mediocre baselines
  qualification.json  # manifest slots for LIVE
```

Challenge #2 should add a pack, not fork the subnet.

---

## 11. What “running Carbon” means (P0)

```text
Miner/agent → MCP free loop → optional submit
Validator  → hidden data → TrainEvalAPI official → gates → Score Pack → cards
Network    → weights from lean scores only (testnet in P0)
Public     → leaderboard + budgeted EvaluationCard
Ops        → priors/scaffolds from verified cards (after Launch_Bar)
```

**P0 acceptance includes actual Bittensor testnet path** (scores → weights visible).  
**Agent Wave C deliverable** includes wiring; **P0 done** ≠ “testnet stub only.”

**Out of P0:** Landscape graph, specialist SKUs, automated free-loop non-oracle monitoring, commercial CAE, mainnet.

**PoC handoff:** `POC_Burgers_FNO.md` proves lean loop without MCP. Promote its TrainEvalAPI into Wave C; PoC green is a dependency of P0, not a competing SOW.

**Layout:** Prefer mapping `poc/` + `Carbon_Logic/` over forced rename. Interfaces > directory cosmetics.

---

## 12. Wave acceptance checklists

### Wave A done when

- [ ] CI green on schema, seed/mock guards, scoring engine unit tests  
- [ ] Registry blocks LIVE without qualification manifest  
- [ ] MCP tools respond; dry_validate enforces denylist  
- [ ] submit → `submission_id` + FSM; fee≠score tested  
- [ ] Card store: budgeted read allow-list tested; unauthorized hotkey denied  
- [ ] TrainEvalAPI **stub** only; cannot mark emission-ready  
- [ ] Leakage tests for EvaluationCard/leaderboard fields  

### Wave B done when

- [ ] Generator + mock pack interfaces callable with fixtures  
- [ ] light_* reject non-mock packs  
- [ ] Dossier + qualification manifest schemas exist  
- [ ] Prior pipeline runs on fixture cards (redact tests)  

### Wave C done when

- [ ] Real TrainEvalAPI (or PoC backend) behind official + mock  
- [ ] Validator e2e: strategy → score → Model Card + EvaluationCard  
- [ ] MCP free then paid loop e2e  
- [ ] Gate fail → non-emitting  
- [ ] **Testnet:** lean scores → weights observable  
- [ ] FAILED_INFRA vs FAILED_STRATEGY distinguished  

### Wave D / LIVE done when

- [ ] Qualification manifest fully APPROVED/SIGNED for challenge version  
- [ ] Launch_Bar + MCP §2.4 green  
- [ ] Human thresholds/envelope/MOCK incompleteness/scaffold accepted  
- [ ] Registry `live` flip succeeds only with matching hashes  

---

## 13. Component notes (compact)

**C5 Engine:** Load pack by hash; hard gates fail-closed; forbidden inputs enforced in code. Weights (e.g. 45/30/25) are **Score Pack fields**, not engine constants.  
**C7:** Implements FSM + isolation limits + pin recording; calls TrainEvalAPI; never invents physics passes on infra failure.  
**C9:** Tool surface and disclosure per `Miner_MCP.md`. Free loop default; paid rare.  
**C13:** Fee ledger with §6 semantics.  
**C15:** P0 = working testnet path; mainnet = human.  
**C17–C18:** Out of **Phase 0** SOW; preserve Model Card hooks in P0. Sequenced as Post-P0 Waves E–F (§18).  

---

## 14. Security / isolation (P0)

Strategy execution must enforce, at minimum:

- network deny-by-default  
- filesystem scratch-only  
- CPU/GPU/RAM and wall-clock limits  
- container/env pinning (`env_digest` on pin)  
- no access to validator secrets or official seed material  
- no path for hidden-data exfiltration via metrics/logs to miners  

Detail may live in Operations docs; **absence of isolation is a P0 blocker**, not a post-launch harden item.

---

## 15. Non-goals (Phase 0 / initial SOW)

These are **out of Phase 0 waves A–D**. They are not “never.” Post-P0 sequencing is §18.

- Landscape causal / symbolic stack → **Wave E** (`Landscape_Agent.md`)  
- Specialist commercial SKU / product battery → **Wave F** (`Specialist_Bank.md`)  
- Customer bounds / sponsored-challenge GTM → **Wave G** (`Customer_Bounds_Specialist.md`)  
- Marketplace UI  
- free-surface non-oracle monitoring / mock refresh service (track as P1 ops; §17)  
- Full commercial CAE mesh pipeline  
- Hermes/Mira vendor plugins  
- Agent-invented LIVE physics thresholds (**permanent** non-goal)  
- Repo-wide rename as a deliverable  
- Major C8 investment unless subnet requires it  

---

## 16. Doctrine for coding agents

1. Build the stadium and the rules engine.  
2. Leave physics calibration to SciML.  
3. Fail closed when human inputs or qualification slots are missing.  
4. Prefer one vertical fixture loop over ten empty modules.  
5. Enforce cross-cutting invariants in tests.  
6. Never present placeholder thresholds as production truth.  
7. Never emit from stubs.  
8. When docs conflict, obey §0 domain ownership.  

---

## 17. Open opportunities (not blockers; track)

Items noticed in review that improve P0/P1 without changing architecture:

| Opportunity | Why | Phase |
|-------------|-----|-------|
| Free-path rate limits on `light_compare` | Stop compute DoS of mock runner | P0 soft / P1 |
| Cost estimate field on light/estimate responses | Miner UX; optional | P1 |
| Explicit `corr` monitor offline job | Mock rotation trigger when free≈official | P1 |
| CI matrix: CPU-only unit vs GPU integration tags | Agents/CI without GPU | P0 |
| Hotkey↔submission binding tests | Fee and card authz | P0 |
| Pack content-addressed store | Pin verification | P1 |
| Well / external corpus hooks in dossier templates | Optional supporting evidence | P1 packs |
| Structured failure tag ontology shared MCP↔cards | Better avoid-atlas / priors | P0 schema, P1 richness |

Do **not** block Wave A on these.

---

## 18. Post-P0 waves (company + compounding product)

Phase 0 ends at **Wave D / LIVE** for at least one challenge and a working **testnet** path (Wave C).  
What follows is **not** required to claim P0 subnet readiness. It *is* required to claim Landscape intelligence, commercial specialists, or sponsored-challenge GTM.

**Hard rule:** Post-P0 waves **must not** weaken Phase 0 invariants (gates judge score; stubs never emit; no seed leakage; fee≠score). Landscape never overrides hard gates.

**Prerequisites before public product claims:**
- Wave C green (real TrainEval + validator e2e + testnet weights observable)
- Wave D green for the challenge versions that feed cards into Landscape
- `Launch_Bar.md` green before L0 “verified card” compounding or public prior-quality claims (`Landscape_Agent.md`)

```text
WAVE E — Landscape signals (C17)
  Card lake from Launch-Bar-grade Model Cards only
  L0: ingest + daily noisy prior packs (redact, lag, no full champ weights)
  L1: failure atlas / symbolic hooks
  L2: causal core + specialist *pipeline hooks* (not full SKU)
  Ports: A search (miners) · B eval (validators only) · C economy proposals · D product hooks
  Authority: Landscape_Agent.md
  Human: coarsen policy, publish cadence, what may leave the building

WAVE F — Specialist bank (C18)
  Effect-synthesized recipes from Landscape → controlled retrain
  Product battery (verification gauntlet) before any commercial SKU
  Dual egress: noisy search path vs closed product path
  No teacher-checkpoint distillation as the product
  Authority: Specialist_Bank.md
  Human: which regimes to productize; battery pass/fail signoff

WAVE G — Customer bounds & sponsored challenges (GTM)
  Bounds intake: requirements / constraints / envelope (default: no customer proprietary trajectories)
  Match Landscape evidence → fulfill off-subnet when sufficient
  Sponsored / open / IP-licensed / private challenge tiers when network search is needed
  Customer-side adapt kit voids prior cert until re-qualification
  Authority: Customer_Bounds_Specialist.md, Use_Cases_by_Phase.md
  Human: pricing, contracts, which challenges to host
```

### 18.1 Post-P0 acceptance (directional)

| Wave | Done when (summary) |
|------|---------------------|
| **E** | Card lake + noisy prior publish path exist; gates still sole score authority; Launch_Bar respected |
| **F** | At least one regime can run recipe → retrain → **product battery** → closed artifact (fixture or real) |
| **G** | Bounds schema + fulfillment rules documented and demoed; one trial path without requiring customer secret data |

### 18.2 What stays human

- LIVE thresholds and dossier science (still Wave D discipline per challenge)
- Mainnet parameters and emission economics
- Commercial pricing, sponsorship terms, IP licenses
- Any claim that a specialist is “system certified” for a customer plant

### 18.3 Explicit non-coupling

| Do not | Why |
|--------|-----|
| Feed free-path mock metrics into Landscape as verified truth | Corrupts Port D |
| Sell eval outcomes or emission weight | Protocol integrity |
| Ship specialist without product battery | `Specialist_Bank.md` doctrine |
| Block Phase 0 on Waves E–G | P0 is subnet readiness, not OpCo scale |

---

*Build_Out v1.4 — Phase 0 waves A–D + Post-P0 waves E–G. **Sequencing authority only.** Domain ownership: SPEC (architecture), Scoring (mathematics), Trustless/Data (seeds/exam identity), Miner_MCP (miner surface), Launch_Bar (stop-ships), Specialist_Bank (productization). Post-P0 product docs as cited in §18.*
