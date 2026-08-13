# Miner MCP Specification

**Carbon — steer · free iterate · submit · independent exam · structured feedback**

**Version:** 2.2  
**Status:** Implementation contract  
**Scope:** Miner- and agent-facing interface only  
**Non-scope:** Validator training internals, Landscape private graph / Port B, product-battery packs, Score Pack math (see [`Scoring.md`](./Scoring.md))

---

## TLDR

Carbon’s Miner MCP is the **agent-native control surface** for competitive scientific search on physics training strategies.

**Two loops:**

```text
FREE LOOP (default — no exam fee)
  get_prior / get_mock_scaffold / get_challenge_info
        → mutate → estimate → light_compare → light_train? → repeat

PAID LOOP (rare — only official grade)
  submit → get_submission_result → feed failure tags into free loop
```

**Hardening (v2.2):**

1. Free surface is **directionally informative but intentionally imperfect**  
   `corr(free_signal, official_exam) > random` and `≪ 1`  
2. Evaluation feedback is a **budget** — enough to repair, not enough to reconstruct the hidden exam  
3. **`get_mock_scaffold`** supplies a versioned runnable baseline; priors stay coarse and non-executable  

**Position:** Bring your scientist. Carbon brings problems, free practice, incentives, and an independent exam.

---

## 1. Purpose and thesis

### 1.1 Interface job

Humans and autonomous agents (Hermes, Mira-class, AutoScience-class, lab bots, Bittensor miners) run continuous search:

1. Orient (`get_prior`)  
2. Obtain a fair mock baseline (`get_mock_scaffold`)  
3. **Iterate for free** (estimate → light_compare → optional light_train)  
4. **Submit rarely** for the only official lean grade  
5. Read a **budgeted** evaluation card and return to the free loop  

**Requirement:** Long free loops without submitting. Paid exams confirm claims; they are not the default learning channel.

### 1.2 Referee framing

```text
More researchers → more free experiments → selective paid exams
  → verified outcomes → better priors / avoid-atlas / scaffolds
  → smarter search → better strategies → harder commercial challenges
```

Carbon need not build the best AI scientist. It is where AI scientists **compete** under a trustworthy referee.

### 1.3 Free-surface doctrine (normative)

```text
corr(light_compare metrics, official lean exam) > random
corr(light_compare metrics, official lean exam) ≪ 1
```

The free surface must **not** become a public surrogate of the private exam. Mock packs are rotated, incomplete, and versioned so dominating `light_compare` is not equivalent to dominating the validator.

### 1.4 Feedback doctrine (normative)

> Evaluation feedback must be sufficient for scientific repair, but insufficient for reconstructing the hidden exam through repeated querying.

Granularity is a security parameter. Seeds are necessary but not sufficient protection once agents can query the grader hundreds of times.

---

## 2. Goals and non-goals

### Goals

- Dense free iteration without exam fee  
- Closed paid loop with budgeted feedback  
- Agent-stable JSON tools  
- steer ≠ triage ≠ mock-relative ≠ grade ≠ sell  
- Intentional decorrelation of mock vs official exam  

### Non-goals

- Official exam replay  
- Champion weights / exact recipes  
- Free path as Yuma substitute or predicted lean score  
- Stable immortal mock distribution that tracks the validator  
- Fine residual margins that map the hidden draw mix  
- Per-lab MCP adapters  

---

## 3. Trust boundary

| Asset | Via MCP? | Rule |
|-------|----------|------|
| Noisy prior (coarse) | Yes | Non-executable search info |
| Mock scaffold (runnable) | Yes | Versioned, mediocre/noisy, public |
| Estimate / light_compare | Yes | Non-binding; mock only |
| EvaluationCard | Yes | Own submits; **budgeted** fields |
| Official seeds / stress draws | **Never** | Validator-only |
| Champion weights | **Never** | Dual egress elsewhere |
| Prior similarity in score | **Forbidden** | Scoring.md |

**Doctrine:** *Steering before the exam. Intentionally imperfect free practice. Independent exam when you pay. Budgeted feedback after. No answer key.*

---

## 4. Priors (coarse search information)

**Producer:** subnet prior publisher. **Consumers:** all miners — one channel.

```text
Lean cards → window → eligibility → k-aggregate → lag → coarsen → noise → redact
  → structural_steer | avoid_atlas | explore_mask → publish
```

Priors are **not** runnable strategies. Missing hyperparameters are intentional. Do not “invert” the prior into a champion recipe inside `light_compare`.

Worked prior example remains the v2.1 Burgers/FNO shape (steer / bands / avoid / explore / not_included).

---

## 5. Mock scaffold (runnable baseline)

### 5.1 Why a separate object

`structural_steer` is coarsened on purpose. Turning it into a trainable JSON requires filling defaults. If that fill is implicit and canonical, it becomes hidden public IP. If each miner fills differently, relative compare is incomparable.

**Split:**

| Tool | Role |
|------|------|
| `get_prior` | Coarse search information |
| `get_mock_scaffold` | Versioned, deliberately mediocre/noisy **runnable** strategy JSON |

Scaffold is **informed by** the prior era (same challenge, overlapping backbone family) but is **not** a lossless materialization of `structural_steer`.

### 5.2 Scaffold properties

| Property | Requirement |
|----------|-------------|
| Runnable | Valid strategy schema; runs under mock contract |
| Versioned | `scaffold_id`, `scaffold_version`, `content_hash` |
| Public | Same object for all miners |
| Mediocre / noisy | Not frontier; not champion weights |
| Bound | Optional `informed_by_prior_version` (metadata only) |
| Rotatable | Can change on a slower cadence than every prior, or with mock packs |

### 5.3 Example

```json
{
  "scaffold_id": "burgers1d-fno-mock-scaffold-2026-08-12",
  "scaffold_version": "1.0.2",
  "content_hash": "sha256:…",
  "challenge_id": "burgers1d",
  "informed_by_prior_version": "burgers1d-fno-2026-08-03-a",
  "strategy": {
    "schema_version": "1.0",
    "challenge_id": "burgers1d",
    "backbone": { "family": "fno1d", "modes": 16, "width": 32, "layers": 4 },
    "loss": { "data_l2": true, "residual": true, "conservation": true },
    "training": { "optimizer": "adam", "lr": 1e-3, "epochs": 20 },
    "curriculum": { "stages": ["smooth_ic"] },
    "meta": { "role": "mock_scaffold", "quality": "deliberately_baseline" }
  },
  "not": ["champion_weights", "exact_winner_json"]
}
```

---

## 6. Core objects (summary)

- **Strategy** — schema-versioned miner JSON (denylist: seeds, gate disables)  
- **Estimate** — non-binding; includes `prior_delta`; never `predicted_lean_score`  
- **LightCompareResult** — mock-only deltas vs `scaffold_id`  
- **SubmitReceipt** — queue ack only  
- **EvaluationCard** — budgeted miner-visible result (§12)  

---

## 7. MCP tools

| Tool | Cost | Role |
|------|------|------|
| `get_challenge_info` | Free | Rules, fees, pack hashes, **active mock_pack_ids**, tag catalog, disclosure tier |
| `get_prior` | Free | Coarse prior |
| `get_mock_scaffold` | Free | Runnable baseline (`challenge_id`, optional `scaffold_id`) |
| `dry_validate` | Free | Schema / denylist |
| `estimate` | Free | Doom filter + prior-delta |
| `light_compare` | Miner CPU | Candidate vs **scaffold_id** on active mock pack(s) |
| `light_train` | Miner CPU | Local mock practice |
| `submit` | Exam fee | Official exam |
| `get_submission_result` | Free | Budgeted EvaluationCard |
| `list_my_submissions` | Free | Optional |

---

## 8. Estimation (unchanged intent, v2.1 prior_delta)

Avoid-atlas first → structured prior-delta → coarse band inheritance → UX clone warning.  
Always `disclaimer: "non_binding"`. No official score fields.

---

## 9. Free local practice — mock packs and light_compare

### 9.1 Intentional imperfection

| Mechanism | Purpose |
|-----------|---------|
| **MOCK_RANGES ⊂ VALIDATOR envelope** | Incomplete coverage |
| **Missing stress categories** | Official path has categories mock lacks |
| **Mock pack rotation / versioning** | No single immortal practice distribution |
| **Optional multiple mock families** | Reduce single-surface Goodhart |
| **Published `mock_pack_id` list** | Clients pin versions; old packs may retire |

Ops may measure empirical rank correlation offline. If correlation drifts toward 1, **rotate or degrade mock** — do not tighten the official exam to match mock.

### 9.2 light_compare contract

```text
light_compare(candidate, scaffold_id, challenge_id, miner_seed, mock_pack_id, n_batches):
  require mock_pack_id in ACTIVE_MOCK_PACKS[challenge_id]
  scaffold = load_scaffold(scaffold_id)  # from get_mock_scaffold registry
  draws = shared mock draws from miner_seed + mock_pack_id
  cand_m = run_local(candidate, draws)
  scaf_m = run_local(scaffold.strategy, draws)
  return LightCompareResult(
    scaffold_id=scaffold_id,
    mock_pack_id=mock_pack_id,
    candidate_metrics=cand_m,
    scaffold_metrics=scaf_m,
    delta=cand_m - scaf_m,
    disclaimer="non_binding_mock_only"
  )
```

Default `scaffold_id` = current published scaffold for that challenge (not miner-invented fill of the prior).

### 9.3 light_train

Same mock sampling rules; single-strategy local optimization. Still never Yuma.

---

## 10. Submit path

Free loop until justified → `dry_validate` → fee → `SubmitReceipt` → hidden exam → card via `get_submission_result`.

---

## 11. EvaluationCard — feedback budget

### 11.1 Sensitivity tiers (Phase 0 default)

| Field class | Phase 0 | Notes |
|-------------|---------|--------|
| `status`, `scoring_pack_hash` | **Emit** | Always |
| `overall_score` | **Emit** | Low sensitivity |
| Broad `component_scores` | **Emit** | physics / robustness / accuracy bands or coarse floats |
| `gate_results` pass/fail | **Emit** | Necessary for repair |
| Coarse `failure_modes` tags | **Emit** | Shared with avoid-atlas; high agent value |
| Short `public_diagnostics` | **Emit** | No seed material |
| Fine residual margins / distances-to-gate | **Withhold or coarsen** | Oracle risk |
| Per-stress / per-regime numeric breakdowns | **Withhold** | Reconstructs draw mix |
| Eval seeds / draw ids / fields | **Never** | — |

### 11.2 Principle

Sufficient for scientific repair; insufficient for reconstructing the hidden exam via repeated queries.  
Disclosure tier is published in `get_challenge_info`. Raising granularity later is a versioned policy change, not a silent field dump.

### 11.3 Card shape (Phase 0)

```text
EvaluationCard {
  submission_id, strategy_hash, challenge_id, status, scoring_pack_hash,
  overall_score,
  component_scores: { physics?, robustness?, accuracy? },  # coarse
  gate_results: [ { gate_id, pass: bool } ],               # no fine margins
  failure_modes: [ { mode_tag, severity } ],
  public_diagnostics: string[],
  disclosure_tier: "phase0_budgeted",
  completed_at?
}
```

---

## 12. Reference agent loop (free-first)

```text
info     = get_challenge_info(challenge_id)
prior    = get_prior(challenge_id)
scaffold = get_mock_scaffold(challenge_id)
budget   = { compute, max_submits, max_fees }
local_best, last_card = None, None

while budget.remaining:
  strategy = mutate(prior, last_card, local_best)
  if not dry_validate(strategy).ok: continue

  est = estimate(strategy, prior)
  if hard_zero_risk(est): continue

  if budget.compute:
    cmp = light_compare(
      strategy,
      scaffold_id=scaffold.scaffold_id,
      mock_pack_id=info.active_mock_packs[0],
      miner_seed=fresh_seed(),
      n_batches=info.compare_batches_default
    )
    if improves(cmp): local_best = strategy
    else: light_train(strategy)  # optional

  if worth_exam(est, cmp, budget):
    receipt = submit(strategy)
    last_card = poll get_submission_result(receipt.submission_id)
    prior = get_prior(challenge_id)
    scaffold = get_mock_scaffold(challenge_id)  # if rotated
```

---

## 13. Gaming matrix (v2.2 highlights)

| Vector | Mitigation |
|--------|------------|
| Goodhart light_compare | Rotating incomplete mocks; corr ≪ 1 doctrine |
| Immortal mock ≈ exam | Pack versioning + retirement |
| Estimate as official score | No lean_score field |
| Scaffold = champion | Mediocre versioned baseline only |
| Implicit prior materialization | Separated `get_mock_scaffold` |
| Card as query oracle | Feedback budget; withhold fine margins |
| Seed leak | Never on MCP |
| Prior similarity score | Banned in Score Pack |

---

## 14. Invariants (normative)

1. Priors never include weights or official eval seeds.  
2. Priors never appear as a lean score term.  
3. Estimation never authorizes emissions or predicts official lean score.  
4. light_compare / light_train never see validator packs or VALIDATOR_RANGES.  
5. Submit always re-runs the hidden exam; fee ≠ score.  
6. Priors never thin the mandatory gate set.  
7. One public prior channel — no VIP feed.  
8. EvaluationCard never returns seeds, draw ids, or other miners’ full cards.  
9. `failure_modes` share avoid-atlas vocabulary.  
10. No lab-specific MCP forks required.  
11. Free path is first-class; paid exam is confirmation.  
12. light_compare uses `get_mock_scaffold`, not an inverted prior.  
13. **Free signal must remain intentionally imperfect vs the official exam.**  
14. **Evaluation feedback is budgeted against exam-reconstruction attacks.**  

---

## 15. Related documents

`SPEC.md`, `Scoring.md`, `Launch_Bar.md`, `Data_Management.md`, `Landscape_Agent.md`, `Generator_Creation.md`, `Evidence_and_Envelope_Standards.md`.

---

## 16. Doctrine

Agents **grind for free** on an intentionally imperfect mock surface against a public mediocre scaffold. **Submit is rare.** The referee returns budgeted feedback—enough to repair, not enough to reverse-engineer the hidden exam. Priors steer; they do not execute. Scaffolds run; they are not champions.

Carbon supplies the problems, the practice range, the incentives, and the independent exam. Any scientist can plug in.

---

*Miner MCP v2.2 — mock rotation, feedback budget, get_mock_scaffold. Preserve all §14 invariants.*
