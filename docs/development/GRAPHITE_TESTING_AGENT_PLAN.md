# Graphite: Carbon's in-house research and testing agent (plan)

**Status:** PLAN, 2026-10-02. Phase 1 (the harness) is built. Phase 2 (the
literature layer) is built and has not run live: it waits for the owner to
complete its grant (OWNER-GRAPHITE-02). Later phases are not built.

- The owner decided on 2026-10-01 to build an in-house agent rather than
  buy Autoscience Mira.
- On 2026-10-02 the owner decided that agent inference runs on Chutes or
  Engy.

Both decisions are recorded as OWNER-GRAPHITE-01 in `.agent/DECISIONS.md`.

**Authority.** This is internal development tooling under
OWNER-CHALLENGE-ADMISSION-01. It never runs on mainnet, is never shown to
miners, is not a qualification gate, and grants no evaluator authority.
**Graphite proposes; Carbon's verifier decides** (invariants 7.9 and 7.10).

**Name.** Graphite is carbon arranged in layers. Each layer of the agent is a
role (literature, hypothesis, experiment, attack, write-up), and none of the
roles holds evaluator authority.

---

## 1. What we are mirroring, and what we do differently

Autoscience's own site (read 2026-10-01; see
`docs/development/mira/CAPABILITY_REPORT.md`) describes Mira in four steps.
"Agent proposes, verifier decides" is their own phrase.

| Mira step (their words) | Graphite equivalent | What Carbon already has |
|---|---|---|
| "Sees every paper." Extracts methods and proposes combinations specific to the customer's model | **Literature layer**: a curated, continuously updated index of physics-ML, surrogate-modelling, operator-learning and battery papers, with method cards | Nothing yet |
| "Experiments on your model." Isolated training runs, loss curves against the baseline | **Experiment layer**: the agent proposes constructions; Carbon's runner trains them on pinned pods | The pod runner with hash-pinned code shipping, ledgers and caps (EV4: 1,338 physics solves and 100 GPU fits for USD 2.48); the construction contract and recipe compiler |
| "Verifies on your eval." The customer's metrics and significance threshold decide, pass/fail | **Judge layer**: Carbon's frozen exam rule, gates and paired comparison. The agent sees development feedback only and never sees confirmation cases | Exam machinery (gates, `final_compare`, screening pools), the EV decision contracts, the admission validator |
| "Ships improvements as PRs" with run logs, ablations and a write-up | **Delivery layer**: one PR per accepted improvement, carrying the recipe, run logs, ablations, write-up and a rebuild script | The repo delivery workflow; reconstruction and delivery rebuild |

Two things Mira does not need and Carbon does:

- **An attacker role.** Admission testing (Track A) needs an adversary that
  tries to break construction, disclosure, resource and evidence boundaries.
  Mira is built to improve models, not to attack the grader.
- **Confidential execution for client challenges.** Later, client truth runs
  inside attested hardware (Targon confidential compute, §8). Because Graphite
  is ours, it can run where client data lives. A vendor agent could not.

**What "SOTA" means here.** It is a measured target, not a claim.

- Graphite is state of the art for Carbon when it beats both our current
  practice (the fixed recipe panel and the fixed-grid optimizer) and any
  vendor alternative at equal compute.
- The tasks are frozen Carbon benchmarks with untouched confirmation cases
  (§6).
- Until §6 runs, nothing is claimed.

## 2. Architecture

**Graphite is built on what Carbon already runs.**
`carbon/development_session/` already contains a durable, metered research
agent that works through the miner's own path:

- `research_loop.py`: a finite, durable research epoch;
- `research_agent.py`: metered provider calls, typed failures and replay
  without resending;
- `research_tools.py`: the closed miner SDK;
- `research_workspace.py`: miner-owned files with no evaluator handle;
- the isolated research carrier, and the ledger;
- `model_provider.py`, the inference layer. It has Engy adapters for
  Messages and Chat Completions, a published price list, and per-call
  settlement from Engy's reported charge. A generic OpenAI-compatible chat
  adapter is also there.

Graphite adds the parts a *testing* agent needs:

- the literature layer;
- the four roles;
- campaign control through the #475 controller;
- PR delivery.

Because Graphite acts through the **real miner path**, every construction
and attack it runs exercises the same intake, sealing and isolation that a
miner would hit. That is the point of admission testing.

**Rule order, KEEP → WRAP → REPAIR → REPLACE.**

- **Keep:** the research loop, tools, workspace, carrier and provider layer.
- **Wrap:** them in a `GraphiteProvider` behind the #475 controller.
- **Repair** only what the testing roles need.
- **Replace** nothing.

```
            ┌──────────────────────── Carbon-controlled ─────────────────────────┐
 owner ──►  │ Campaign controller (carbon/agent_campaign, #475)                  │
 grant      │  intent ledger · spend reservation · caps · cancel/verify ·        │
            │  findings stop expansion · hash-chained attempt ledger             │
            │        │ start / stop / reconcile          ▲ results (data only)  │
            │        ▼                                    │                     │
            │  GraphiteProvider  →  existing research loop (research_loop.py)    │
            └────────┼────────────────────────────────────┼─────────────────────┘
                     ▼                                    │
   ┌──── isolated research carrier (one per role/session) ────────────────────┐
   │ model calls: Engy or Chutes (Bittensor inference) via model_provider.py   │
   │ tools: closed miner SDK (research_tools.py) · research workspace ·        │
   │        lit.search / lit.card (literature layer, read-only)                │
   │        no confirmation material · no evaluator writes · no pod keys       │
   │ output: proposals, recipes, code, reports  →  returned as data            │
   └───────────────────────────────────────────────────────────────────────────┘
                     │ proposals only
                     ▼
   Carbon runner (RunPod pods, later Targon CC)  →  frozen verifier  →  ledger
```

**Design rules**

1. **One controller.** Graphite is a second provider behind the controller
   built in #475. Grants, caps, cancellation checks, findings and ledgers
   apply to it exactly as they would to Mira. This is also what makes a
   later comparison fair (§6).
2. **Inference on Bittensor (owner, 2026-10-02).**
   - **Engy** is the first provider; its adapters already exist.
   - **Chutes** follows. Today Carbon has no Chutes adapter, and the generic
     OpenAI-compatible chat adapter has not been tried against it
     (`scripts/dev/miner_launchpad/controller.py`). Launchpad slice C-MLP-03
     §2 plans the Engy and Chutes adapters. Graphite reuses that adapter
     rather than writing a second one.
   - The harness is our own research loop, not a vendor agent SDK. It speaks
     whatever the provider layer speaks.
3. **Least authority.** The carrier has:
   - no Carbon repository beyond the allowlisted research checkout;
   - no evaluator credentials;
   - no RunPod key: the controller launches pods, not the agent;
   - outbound network limited to the inference endpoint, the literature
     index and the campaign-scoped endpoint.

   Prompt injection in papers, repository text or tool output is assumed.
   Permissions and the controller hold the boundary even when the model
   obeys an injected instruction.
4. **Agent output is data.** Proposals, recipes, code and reports are stored
   and then executed by Carbon's runner. The agent never executes a grade,
   edits a ledger or touches confirmation material.
5. **Everything is reproducible.** Each session records:
   - provider, model ID and settings;
   - the system-prompt digest and the tool manifest;
   - the literature-index snapshot and the checkout commit;
   - every call's reservation and its settled charge (the existing research
     ledger).

   A delivered improvement must rebuild from its PR alone, without the
   agent.

## 3. Roles and models

**Models come from the providers' own lists, and the existing owner ladder
applies.** `model_provider.ENGY_MODELS` is the owner's ladder of
2026-09-26, cheapest first, with prices from Engy's published list observed
on that date:

| Model | Input / cached / output (USD per 1M tokens) | Context |
|---|---|---|
| `deepseek-v4-flash-0731` (default) | 0.045 / 0.009 / 0.090 | 1.05M |
| `qwen3.8-27b` | 0.045 / 0.015 / 0.320 | 1.00M |
| `glm-5.3-flash` | 0.135 / 0.027 / 0.450 | 262K |
| `glm-5.2` | 0.680 / 0.180 / 1.500 | 262K |
| `kimi-k3` | 1.950 / 0.195 / 9.750 | 1.05M |

The ladder's rule is to escalate one rung only on an observed research
failure. Graphite keeps that rule per role:

| Role | Job | Starting rung | Escalates when |
|---|---|---|---|
| **Planner** | Picks the next hypothesis from method cards and past results; writes the plan and stopping rule before any run | `glm-5.2` | Its plans repeatedly fail to produce a runnable or distinct hypothesis |
| **Constructor** | Turns a plan into a recipe or code inside the permission profile; reads loss curves; iterates | `deepseek-v4-flash-0731` | Its builds fail to compile, or stall against the baseline, over a registered number of attempts |
| **Attacker** | Track A red team: leakage, boundary optimism, resource and disclosure attacks | `glm-5.2` | It produces no well-formed attempt in a family |
| **Optimizer researcher** | Proposes design-search methods, compared against the fixed grid on development material only | `glm-5.2` | Its proposals do not run |
| **Reader** | Paper triage and method-card extraction | `deepseek-v4-flash-0731` | Hand-checked cards show extraction errors |
| **Writer** | PR write-up from run logs and ablations | `qwen3.8-27b` | Write-ups fail the PR checklist |

- **Starting rungs are engineering guesses,** to be measured in §6. Nothing
  here claims one model is better than another for these tasks.
- **Prices and models change.** Graphite reads the provider's live model list
  at session start and records it. A model with no known price runs only as
  `UNKNOWN_SPEND`, with the full reservation the provider layer already
  applies; prices are never invented.
- **Chutes models** join the table once the Chutes adapter exists and its
  list and prices have been read.

## 4. The literature layer ("sees every paper")

- **Sources.** arXiv feeds such as `physics.comp-ph`, `cs.LG` and
  `math.NA`, filtered by keywords:
  - neural operators;
  - physics-informed learning and surrogate models;
  - battery modelling, fast charging, reduced-order electrochemistry;
  - design optimization and inverse design;
  - ML benchmarks and evaluation.

  Plus a curated seed list, and later the photonics, cold-plate and motor
  challenges as they become ready.
- **Pipeline.**
  1. Nightly fetch.
  2. Triage on the cheapest rung (relevant or not).
  3. The Reader role extracts a **method card**: technique, claimed effect, data
     regime, cost, code availability, and applicability to each Carbon
     challenge.
  4. The index stores the cards with their embeddings.
  5. The Planner queries cards, never raw PDFs, unless it asks for one.
- **Snapshots.** Each session pins an index snapshot digest, so a result can
  be traced to the papers the agent could see.
- **As built in phase 2.** The modules are in `carbon/agent_campaign/graphite/`.
  The backfill runs on demand rather than nightly. It has no embeddings yet:
  `lit_search` is keyword search over the cards.
  - `literature_fetch.py`: a registered, versioned query set; the arXiv API,
    at least 3 s between requests; content-addressed pages and records; a
    hard record cap; typed `FAILED_INFRA` failures.
  - `method_cards.py`: one Reader call per abstract, which both triages
    (`relevant`) and extracts. The card shape is closed. Cards are written
    `UNCHECKED`. Human checks need an interactive confirmation.
    Deterministic snapshots load into `LiteratureIndex`.
  - `triage.py`: metering through `research_agent` and the research ledger,
    under the grant.
  - `phase2.py`: the runner.
- **Cost control.** Cheapest rungs for triage and extraction, a stable
  cached prefix, and per-call settlement from the provider's reported charge.

## 5. The experiment loop ("experiments on your model", "verifies on your eval")

For each campaign, which the controller dispatches:

1. **Plan.** The Planner picks a hypothesis from the method cards and
   history, writes the expected effect and a stopping rule, and records both
   before any run.
2. **Build.** The Constructor writes the change inside the campaign's
   permission profile (construction ladder levels 0-5, Challenge Admission
   §8).
   - Higher levels unlock only when the profile is recorded, a #468 record
     exists, and no finding is open.
3. **Run.** The controller sends the build to Carbon's runner on development
   material: TRAIN v1 and practice or screening feedback.
4. **Read.** The agent gets the loss curves and development scores, then
   iterates within its attempt budget.
5. **Submit.** A finished candidate is scored by Carbon's frozen rule with a
   paired comparison against the incumbent. The agent never sees
   confirmation cases.
6. **Deliver.**
   - An improvement that clears the frozen rule becomes a PR: recipe, run
     logs, ablations (each change removed one at a time), write-up and a
     rebuild script.
   - A clean worker then rebuilds it from the PR alone.

**The attacker loop** is the same machinery with an attack objective. Each
attack family has:

- a registered vulnerable specimen, which shows the detector can fire;
- a valid control, which measures wrongful rejection.

A verified violation becomes a finding, and expansion stops.

**The optimizer-researcher loop** wraps the fixed EV4 optimizer with the #475
commitment layer: query budget fixed, commitment before reference access,
comparison against the fixed grid at equal queries. EV4's confirmation
conditions are refused by construction.

## 6. How we know it works (the bake-off)

Each experiment is pre-registered before it runs, in the style of EV4.

| Benchmark | Measure | Baseline |
|---|---|---|
| **B1: battery construction** (Level 0, then Level 1-2) | Improvement over the EV4 panel's best eligible member on held-out cases under the frozen rule, per dollar | EV4 panel; optionally Mira at equal compute if Autoscience prices a pilot |
| **B2: admission red team** | Verified findings per family at equal attempt budget, with false-positive rate on valid controls | The registered specimens; the existing EV2/EV4 divergence findings |
| **B3: design optimizer** | Verified Problem C outcome at equal model queries | The fixed 31 × 33 grid (EV4) |
| **B4: delivery** | Fraction of improvements that rebuild from the PR alone within tolerance | Must be 100 % of accepted improvements; any miss is a finding |

**Ablations.** Each benchmark also runs:

- no literature layer;
- one rung lower in the Constructor role;
- one rung higher in the Planner role.

This shows what each piece buys.

**What it cannot show.**

- No scientific qualification and no security audit.
- No claim beyond the frozen tasks.
- A search that finds nothing is not a safety bound.

## 7. Plan, cost and order

Token figures are planning estimates. The first sessions measure real usage
and replace them.

| Phase | Builds | Spend | Exit evidence |
|---|---|---|---|
| **0. Records** | This plan, OWNER-GRAPHITE-01, ticket GRAPHITE-01 | none | Merged plan |
| **1. Harness** | `GraphiteProvider` behind the #475 controller; sandbox image; allowlisted checkout; tool manifest; a scripted fake model for tests; session records | none | Fake-model tests: lifecycle, crash recovery, caps, cancellation, injection-as-data, mutation tests |
| **2. Literature layer** | Fetch, triage, method cards, snapshot index | Under USD 5 of tokens on the cheap rungs for a backfill of a few thousand abstracts | Index snapshot; 50 hand-checked method cards |
| **3. Constructor, Level 0** | Live loop on battery development material through the real miner path | Tokens per session, at about 150 turns with a mostly cached 50K-token prefix: about USD 0.10 on `deepseek-v4-flash-0731`, about USD 2 on `glm-5.2`, about USD 6 on `kimi-k3`. Plus about USD 1-3 of pod time. First block 3 sessions | First end-to-end proposal → run → frozen-rule score → PR → clean rebuild. **Reconstruction path:** every construction stays inside the recorded construction contract, and Carbon rebuilds each one (`carbon/reconstruction` expansion records; `test_battery_construction_contract.py::test_every_surface_changes_what_carbon_rebuilds`) |
| **4. Attacker** | Red-team role and the eight Track A families | 3 sessions × 20 attempts: about USD 1-20 of tokens depending on rung, plus about USD 7 of compute | Eight-check coverage report with specimens and controls. **Reconstruction path:** Carbon rebuilds every attack construction it scores, and refuses, typed, any it cannot |
| **5. Optimizer researcher** | Proposals compared against the fixed grid | About USD 1-10 | B3 result. **Reconstruction path:** Carbon reruns each proposal from its record |
| **6. Bake-off** | B1-B4 frozen and run | Sized by the pre-registration; owner approves | Report: retain, change or drop each role and rung. **Reconstruction path:** B4 (rebuild from the PR alone) |
| **7. Confidential compute** | Targon-attested execution for client challenges | Deferred (owner, 2026-10-01) | §8 |

**The reconstruction rule (OWNER-GRAPHITE-02).** Graphite exists to test
construction freedom, so Carbon must be able to rebuild whatever Graphite
constructs. The rule has three parts:

- A phase that widens what an agent may construct ships, in the same phase,
  Carbon's reconstruction capability for the widened surface, with tests that
  Carbon rebuilds it.
- A construction Carbon cannot rebuild is refused fail-closed, with a typed
  refusal, and recorded as a finding. It is never scored.
- So each phase's exit evidence includes its reconstruction path.

Phase 2 widens no construction surface: it reads papers and writes cards.
Phase 3 constructs only within the existing recorded construction contract.

**Phase 2 grant (OWNER-GRAPHITE-02).**

- The ceiling is USD 9.
- It is recorded in `docs/development/graphite/grants/GRAPHITE-GRANT-PHASE2.json`,
  with the derivation in its README. The owner completed the account
  (`Carbon-Account`) and expiry (2026-12-31) on 2026-10-02.

**Phase 3 grant (OWNER-GRAPHITE-03).**

- The ceiling is USD 15, and it includes RunPod pod time: the owner's words
  were "$15 runpod included". One grant covers both kinds of spend.
- It is recorded in `docs/development/graphite/grants/GRAPHITE-GRANT-PHASE3.json`,
  with the derivation in its README. Each of the 3 runs is capped at USD 4.91:
  USD 2.96 for 12 thirty-minute pods and USD 1.95 for tokens.
- Phase 3 is built (GRAPHITE-01, phase 3 delivery). Its first block of 3
  live sessions is pending.

**Total for phases 1-5:** about USD 10-60 of inference, depending on which
rungs the roles reach, plus about USD 10-20 of pod time.

- Token figures are estimates from Engy's list of 2026-09-26. Each call is
  settled from Engy's reported charge, and the first sessions replace these
  numbers with measured ones.
- Each phase runs under its own grant, enforced by the controller. A phase
  that trends over its estimate stops for an owner decision.

**Credentials needed:** an Engy API key (and later a Chutes key) for
Graphite. It is stored as an environment secret and passed by reference
(`model_provider.CredentialReference`), never placed in the carrier image.

## 8. Confidential compute (deferred)

The owner chose Targon's confidential compute for future client challenges.
It is not needed now. The design keeps the door open:

- The verifier and reference solver for a client challenge run inside an
  attested environment. The client's truth and hidden cases are decrypted
  only there.
- Graphite's sandbox stays outside it. It sees only what the challenge's
  disclosure policy allows, exactly as now.
- **What attestation proves.** It proves which code ran on which data. It
  does not prove that the code is correct, or that the challenge is
  scientifically qualified. Both stay separate reviews.
- **Before building:** Targon's attestation, GPU and data-handling details
  must be read from their documentation and checked. This plan assumes
  nothing about them.

## 9. Decisions still reserved

| Decision | Owner | Blocks |
|---|---|---|
| Per-phase spending grants (token and compute). Phase 2: USD 9, decided and complete (OWNER-GRAPHITE-02) | Owner | Phases 3-6 |
| Level-0 study population, reconstruction tolerances, attack budget | Science owner and owner | Phases 3-4 freeze |
| Attacker model and isolation scope for hostile executables | Security owner | Executable attack families |
| PB-INV / PB-ADV acceptance policies | Science owner | Pass/fail use of B3 |
| Whether to run a paid Mira comparison in the bake-off (Mira work is paused, OWNER-GRAPHITE-02) | Owner | B1 vendor arm only |
| A widened construction surface that Carbon cannot yet rebuild | Owner, through the reconstruction rule (§7) | That surface: it is refused and recorded as a finding until its reconstruction ships |

Decided since the plan was written (OWNER-GRAPHITE-02):

- the Constructor's stall limit is 5 attempts (`roles.CONSTRUCTOR_STALL_ATTEMPTS`);
- the Chutes adapter is approved.

Decided since (OWNER-GRAPHITE-03): phase 3's grant is USD 15, RunPod pod time
included.

## 10. Relation to existing work

- **#475** (Mira admission integration): the controller, grants,
  boundaries, study sheet and search-commitment layer are reused unchanged.
  Graphite is a second provider. The Mira adapter stays and keeps refusing
  until a vendor contract exists.
- **#476** (EV4): its panel, references and optimizer are Graphite's first
  baselines. Its frozen pre-registration is never modified.
- **#477** (held readiness gate): unaffected.
- **#468** (construction expansion records) and the battery construction
  contract: Graphite's constructions stay inside them, and Carbon rebuilds
  each one. A widened surface ships its reconstruction in the same phase
  (the reconstruction rule, §7).
- **Mira** (#475): paused by the owner on 2026-10-02.
