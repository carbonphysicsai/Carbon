# Miner MCP Specification

**Carbon — steer · free iterate · submit · independent exam · structured feedback**

**Version:** 2.1  
**Status:** Implementation contract  
**Scope:** Miner- and agent-facing interface only  
**Non-scope:** Validator training internals, Landscape private graph / Port B, product-battery packs, Score Pack math (see [`Scoring.md`](./Scoring.md))

---

## TLDR

Carbon’s Miner MCP is the **agent-native control surface** for competitive scientific search on physics training strategies.

**Two loops (normative):**

```text
FREE LOOP (no exam fee — default agent grind)
  get_challenge_info / get_prior
        → mutate strategy
        → estimate          # doom filter + prior-delta (non-binding)
        → light_compare     # mock-only relative eval vs noisy steer scaffold
        → light_train       # optional deeper local practice
        → repeat

PAID LOOP (rare — only official grade)
  submit (exam fee)
        → get_submission_result   # miner-visible evaluation card
        → feed failure_modes into next free-loop mutate
```

- **Priors** — lagged, coarsened, noisy steer / avoid / explore (never weights or eval seeds).
- **Estimate** — free, deterministic triage + structured prior-delta — **not** a predicted lean score.
- **light_compare** — free relative signal on **mock** data: candidate vs noisy steer scaffold (cheap “vs frontier” without champion weights).
- **Light train** — deeper local practice on mock ranges; cannot reproduce the official draw.
- **Submit** — only emissions path; hidden data; hard gates; small fee.
- **get_submission_result** — structured feedback after the independent exam (tags + scores, never seeds).
- **Hard rules:** prior similarity banned in lean score; priors never thin gates; no VIP channel; free path never writes Yuma; result tags share avoid-atlas vocabulary.

**Position:** Carbon does not need to build the best AI scientist. It is the **place where AI scientists compete** — problems, tools, incentives, and a trustworthy referee. Agents must be able to **grind without paying** and only submit when free signal plateaus.

---

## 1. Purpose and thesis

### 1.1 What this interface is for

Enable humans **and autonomous research agents** (Hermes, Mira-class, AutoScience-class, university bots, anonymous Bittensor miners) to run continuous search against Carbon challenges:

1. Orient with a **steering prior**  
2. **Iterate for free** — estimate risk, relatively compare on mock data, optionally light-train  
3. **Submit rarely** for the only official lean grade  
4. **Read structured feedback** and return to the free loop  

**Design requirement:** An agent must be able to run a long local loop **without submitting**. Paid exams are for confirmation, not for every hypothesis.

### 1.2 Operating-system framing

As AI research becomes autonomous, the scarce layer is a **trustworthy referee**: hard problems, open competition over methods, independent hidden evaluation, economic incentives, and compounding failure knowledge.

```text
More researchers → more free experiments → selective paid exams
  → more verified outcomes → better priors / avoid-atlas
  → smarter search → better strategies → harder commercial challenges
  → greater rewards → better researchers
```

Phase 0/1 stays primitive: one credible challenge, one clean MCP, enough participants to show open search finds better training strategies. The MCP must still be **loop-complete** (including a dense **free** signal) so agents plug in without Carbon-specific forks.

### 1.3 Design principle

> Build the Miner MCP correctly. Do not build per-lab integrations.  
> If an off-the-shelf autonomous ML scientist can mine Carbon — grinding free, submitting rarely — that is the proof point.

Pitch line: **Bring your scientist. Carbon brings the problems, incentives, and independent exam.**

---

## 2. Goals and non-goals

### Goals

- **Dense free iteration** (estimate + light_compare + light_train) without exam fee  
- Closed research loop after submit (evaluation card → next hypothesis)  
- Compound network search without handing out the answer key  
- Agent-stable JSON tools (idempotent, versioned, cost-aware)  
- Clear trust boundary: steer ≠ triage ≠ mock-relative ≠ grade ≠ sell  
- Spam-resistant full exams  

### Non-goals

- Local replay of the official exam  
- Champion weights or exact winning recipes  
- Estimation or light_compare as a substitute for lean score / Yuma  
- Predicted official lean score on the free path  
- VIP prior or VIP result channels  
- Embedding Landscape causal graphs in the miner toolkit  
- Building Carbon’s own “best AI scientist” inside this MCP  
- Per-lab MCP adapters  

---

## 3. Trust boundary

| Asset | Via Miner MCP? | Rule |
|-------|----------------|------|
| Noisy prior document | Yes | Lagged, coarsened, challenge-bound |
| Avoid-atlas (failure-mode tags) | Yes | Aggregated, delayed; no seed material |
| Explore / freeze masks | Yes | Steering only |
| Estimate / light_compare outputs | Yes | Non-binding; mock or prior-delta only |
| Miner-visible evaluation card | Yes | Own submissions only; tags + scores; no seeds |
| Official eval / stress seeds | **Never** | Validator-only |
| Live stress catalogs / draw ids | **Never** | Public *rules* may be documented |
| Champion weights / exact bank recipe | **Never** | Dual egress elsewhere |
| Lean official score | After submit + validator complete | Hidden data, hard gates |
| Prior distance as score feature | **Forbidden** | See Scoring.md |

**Doctrine:** *Steering before the exam. Free relative practice on incomplete mock data. Independent exam when you pay. Structured feedback after. No answer key at any step. Gates do not get thinner because priors exist.*

---

## 4. Why priors exist

Without priors: cold start, wasted fees, agent thrashing.  
With full winner disclosure: clone races, diversity collapse.

| Intent | How |
|--------|-----|
| Orient search | Coarse choices that recently survived lean exams |
| Speed agents | Mutate JSON; scaffold for light_compare |
| Preserve adversarial grading | No weights, no eval seeds, no exact schedules |
| Kill pure clone value | Lag + coarsen + noise + multi-winner blend |
| Transmit failure knowledge | Avoid-atlas mode tags |
| Direct exploration | Explore vs freeze masks |

**Success metric:** more *diverse, non-doomed* free iterations and fewer doomed paid submits — not higher clone rate of the leader.

---

## 5. Where priors come from

**Producer:** subnet-side prior publisher (ops today; Landscape Port A later).  
**Consumers:** all miners via `get_prior` — one public channel.

```text
Lean-verified cards (including structured fails from evaluation cards)
        → window select → eligibility (challenge_id + scoring_pack_hash)
        → k-aggregate → lag → coarsen → noise → redact
        → split: structural_steer | avoid_atlas | explore_mask
        → bind prior_version, as_of, content_hash → publish
```

Hard zeros and `failure_modes` from evaluation cards feed **avoid_atlas** (aggregated, lagged).  
**Gate:** no public prior (or only bootstrap) until [`Launch_Bar.md`](./Launch_Bar.md) allows.

### Worked example — Burgers 1D / FNO-family prior

```json
{
  "prior_version": "burgers1d-fno-2026-08-03-a",
  "content_hash": "sha256:9f2c…",
  "challenge_id": "burgers1d",
  "backbone_scope": "fno_family",
  "scoring_pack_hash": "sha256:pack_burgers_v1",
  "as_of": "2026-08-03T00:00:00Z",
  "lag_policy": "exclude_latest_tempo",
  "structural_steer": {
    "backbone_family": "fno1d",
    "loss_enables_coarse": {
      "data_l2": true,
      "residual": true,
      "conservation": true,
      "adversarial_noise": false
    },
    "curriculum_stage_tags": ["smooth_ic", "moderate_nu"],
    "training_family_tags": ["adam", "cosine_decay_bin_b"]
  },
  "strength_bands": {
    "physics": "mid_high",
    "robustness": "mid",
    "accuracy": "mid"
  },
  "avoid_atlas": [
    { "mode_tag": "conservation_fail", "severity": "hard_zero" },
    { "mode_tag": "rollout_blowup_long", "severity": "high" }
  ],
  "explore_mask": {
    "freeze": ["backbone_family", "loss_enables_coarse.conservation"],
    "explore": ["curriculum_stage_tags", "loss_enables_coarse.adversarial_noise", "training_family_tags"]
  },
  "noise_manifest": { "strength_band_jitter": true, "optional_flag_dropout_p": 0.1 },
  "not_included": ["weights", "exact_lr_schedule", "validator_eval_seeds", "stress_draw_ids", "full_winner_strategy_json"]
}
```

---

## 6. Prior document shape

```text
Prior {
  prior_version, content_hash, challenge_id, backbone_scope,
  scoring_pack_hash, as_of, lag_policy,
  structural_steer, strength_bands, avoid_atlas, explore_mask,
  noise_manifest, not_included[]
}
```

| Channel | Role |
|---------|------|
| **structural_steer** | Frontier scaffold for mutate + light_compare |
| **avoid_atlas** | What recently failed closed |
| **explore_mask** | Where to search without publishing the optimum |

---

## 7. Core objects

### 7.1 Strategy

Schema-versioned JSON: `schema_version`, `challenge_id`, `backbone`, `training`, `loss` enables, `curriculum`, `data` hints, `meta`.

**Invariants:** no validator seeds / stress ids / gate disable flags; `meta.prior_version` analytics only (not a score input).

### 7.2 Estimate

```text
Estimate {
  strategy_hash, prior_version,
  predicted_components: { physics?, robustness?, accuracy? },  # coarse bands only
  gate_fail_risk: { mode_tag_or_gate: low|med|high },
  prior_delta: {
    flipped_fields: string[],          # coarse steer fields that differ
    reopened_avoid_tags: string[],     # avoid-atlas hits
    guided_by_explore: bool,
    hamming_bin: low|med|high
  },
  clone_proximity_warning: none|elevated,   # UX only — NOT official score
  confidence: low|med|high,
  warnings: string[],
  disclaimer: "non_binding"
}
```

**Never:** `predicted_lean_score`, `emission_weight`, `official_rank`.

### 7.3 LightCompareResult

```text
LightCompareResult {
  candidate_hash, scaffold_source,  # e.g. prior.structural_steer | local_best
  mock_pack_id, miner_seed_root, n_batches,
  candidate_metrics: { ... },       # private mock metrics
  scaffold_metrics: { ... },
  delta: { ... },                   # candidate − scaffold on shared mock draws
  local_gate_checks: { ... },       # optional soft checks on mock only
  warnings: string[],
  disclaimer: "non_binding_mock_only"
}
```

### 7.4 SubmitReceipt

`submission_id`, `strategy_hash`, `challenge_id`, `fee_status`, `accepted`, `queue_ref`, `status: accepted_queued`.  
Official score is **not** on the receipt.

### 7.5 EvaluationCard (miner-visible)

```text
EvaluationCard {
  submission_id, strategy_hash, challenge_id,
  status: queued | running | complete | failed_ops | rejected,
  scoring_pack_hash,
  overall_score,
  component_scores: { physics?, robustness?, accuracy? },
  gate_results: [ { gate_id, pass, severity? } ],
  failure_modes: [ { mode_tag, severity } ],   # SAME vocabulary as avoid_atlas
  public_diagnostics: string[],
  challenge_rank?, completed_at?
}
```

**Never:** eval seeds, stress draw ids, full fields, other miners’ cards.

---

## 8. MCP tools

| Tool | Cost | Role |
|------|------|------|
| `get_challenge_info` | Free | Rules, schema, fee quote, pack hashes, mock pack ids, tag catalog ref |
| `get_prior` | Free | Current prior |
| `dry_validate` | Free | Schema / denylist — no fee |
| `estimate` | Free | Doom filter + prior-delta (§9) |
| `light_compare` | Miner CPU | Mock-only relative eval vs scaffold (§10) |
| `light_train` | Miner CPU | Deeper local practice on mock (§10) |
| `submit` | Exam fee | Official exam; SubmitReceipt |
| `get_submission_result` | Free | Poll EvaluationCard (submitter only) |
| `list_my_submissions` | Free | Optional recent ids + coarse status |

No tool returns specialist weights, clean champion JSON, or validator packs.

---

## 9. Estimation mode (free triage)

### 9.1 Purpose

**Filter doomed strategies and describe delta vs prior** before spending mock CPU or exam fee.  
**Not** a certificate. **Not** a predicted official lean score.  
**Official truth = validator lean score only.**

### 9.2 Reference estimator v1

```text
function estimate(strategy, prior):
  risks = {}
  prior_delta = { flipped_fields: [], reopened_avoid_tags: [], guided_by_explore: false, hamming_bin: "low" }
  conf = "med"
  warnings = []

  # 1) Avoid-atlas match (highest priority)
  for item in prior.avoid_atlas:
    if strategy_reopens_mode(strategy, item.mode_tag):
      risks[item.mode_tag] = item.severity
      prior_delta.reopened_avoid_tags.append(item.mode_tag)

  # 2) Structured prior-delta (coarse fields only)
  flips = coarse_field_diffs(strategy, prior.structural_steer)
  prior_delta.flipped_fields = flips.names
  prior_delta.hamming_bin = bin(flips.count)
  prior_delta.guided_by_explore = all_flips_allowed(flips, prior.explore_mask)
  if flips.count large and not prior_delta.guided_by_explore:
    conf = downgrade(conf)
    warnings.append("unguided_large_delta")

  # 3) Band inheritance (coarse only — never invent a lean_score)
  predicted = inherit_bands(prior.strength_bands)
  predicted = nudge_from_public_rules(predicted, strategy)

  # 4) Clone proximity (UX only)
  prox = "elevated" if flips.count <= ε else "none"

  if prior is bootstrap or bands empty: conf = "low"
  if many hard risks: conf = "high"   # confidence in *failure* prediction

  return Estimate(..., disclaimer="non_binding")
```

### 9.3 Honesty rules

- Always `disclaimer: "non_binding"`  
- Forbidden: `lean_score`, `emission_weight`, `official_rank`, any “predicted Yuma”  
- `clone_proximity_warning` is UX only  
- Cannot change fee, skip gates, or raise score ceiling  
- Every accepted submit is fully re-examined on hidden data  

---

## 10. Free local practice — light_compare and light_train

### 10.1 Purpose

Dense **free** learning signal. Miners spend their own compute. **Cannot** replace submit.

| Tool | Question it answers |
|------|---------------------|
| `estimate` | Am I obviously doomed / how far from steer? |
| `light_compare` | On shared mock draws, do I beat the noisy steer scaffold (or my local best)? |
| `light_train` | Can I improve local mock metrics with more steps? |

**Closest honest form of “vs prior champion”:** compare candidate to **noisy `structural_steer` scaffold** on **mock** data — never full champion weights, never validator seeds.

### 10.2 Official vs mock

| Piece | Validator exam | light_compare / light_train |
|-------|----------------|-----------------------------|
| Generator code | Public family | Same family |
| Pack identity | Registry + hidden seed schedule | `mock_` + challenge_id + `_v*` |
| Seeds | Miner-unknown | Miner-chosen root seed |
| Ranges | VALIDATOR_RANGES / full stress | MOCK_RANGES ⊆ milder / incomplete |
| Result | Official lean score | Private metrics only |

### 10.3 light_compare contract

```text
light_compare(candidate, scaffold, challenge_id, miner_seed, mock_pack_id, n_batches):
  require mock_pack_id starts with "mock_"
  require mock_pack_id in published MOCK_PACKS[challenge_id]
  scaffold defaults to materialize_coarse(prior.structural_steer)  # not champion weights
  draws = [light_sample(..., index=i) for i in 0..n_batches)
  # same draws for candidate and scaffold
  cand_m = run_local(candidate, draws)
  scaf_m = run_local(scaffold, draws)
  return LightCompareResult(
    candidate_metrics=cand_m,
    scaffold_metrics=scaf_m,
    delta=cand_m - scaf_m,
    disclaimer="non_binding_mock_only"
  )
```

**Forbidden:** validator pack hashes, hidden seed APIs, modes named “official replay”, strategy fields setting `eval_seed` / official `generator_pack_hash`.

### 10.4 Why this is not gameable into emissions

1. Cannot reproduce the official draw  
2. Mock / compare success **never enters Yuma**  
3. Overfit to MOCK_RANGES should die on the hidden envelope  
4. Same fee + full exam even if local delta looks perfect  
5. Scaffold is noisy steer — not a weight dump of the leader  

### 10.5 light_train

Same mock sampling as compare; single-strategy local optimization. Optional after a positive `light_compare` delta.

---

## 11. Submit path

1. Prefer free loop until estimate + light_compare justify the fee  
2. `dry_validate` → charge small evaluation fee → `SubmitReceipt`  
3. Validator: hidden data → train as required → hard gates → Score Pack  
4. Outcome via `get_submission_result` only  
5. Fee never enters the score function  

---

## 12. get_submission_result — paid-loop feedback

Closes the loop after the independent exam.

| `status` | Meaning |
|----------|---------|
| `queued` / `running` | Not terminal |
| `complete` | Scores / gates / failure_modes populated |
| `failed_ops` | Infra failure; not a physics grade |
| `rejected` | Schema/fee/auth before exam |

Authz: submitter only.  
Disclosure: leaderboard-class info structured for agents — **no seeds**.  
`failure_modes.mode_tag` shares catalog with avoid-atlas so free-loop mutate can consume paid feedback.

Subnet prior publisher may aggregate lagged failure tags into avoid-atlas (public channel compounding).

---

## 13. Data and eval separation

| Stage | Data | Meaning | Cost |
|-------|------|---------|------|
| Prior | Lagged noisy derivative | Steering | Free |
| Estimate | Strategy + prior | Doom filter + prior-delta | Free |
| light_compare | Miner seeds + MOCK_RANGES | Relative mock signal vs scaffold | Miner CPU |
| light_train | Miner seeds + MOCK_RANGES | Local practice | Miner CPU |
| Submit | Hidden validator packs | Official lean score | Exam fee |
| Result card | Own exam summary | Feedback for next free loop | Free poll |

Train ≠ eval ≠ stress on the validator path remains protocol law.

---

## 14. Reference agent loop (free-first)

```text
info  = get_challenge_info(challenge_id)
prior = get_prior(challenge_id)
budget = { compute, max_submits, max_fees }
local_best = None
last_card = None

while budget.remaining:
  strategy = mutate(
    prior.structural_steer,
    avoid=prior.avoid_atlas,
    explore=prior.explore_mask,
    last_card=last_card,
    local_best=local_best
  )
  if not dry_validate(strategy).ok: continue

  est = estimate(strategy, prior_version=prior.prior_version)
  if est.gate_fail_risk indicates hard_zero: continue
  if est.clone_proximity_warning == elevated:
    strategy = force_explore(strategy, prior.explore_mask)

  # FREE relative signal — default grind
  if budget.compute:
    cmp = light_compare(
      strategy,
      scaffold=local_best or prior.structural_steer,
      mock_pack_id=info.default_mock_pack,
      miner_seed=fresh_seed(),
      n_batches=info.compare_batches_default
    )
    if cmp.delta improves: local_best = strategy
    elif est.confidence low:
      light_train(strategy)   # optional deeper mock practice

  # PAID exam — rare
  if worth_exam(est, cmp, info.fee_quote, budget):
    receipt = submit(strategy)
    card = poll get_submission_result(receipt.submission_id)
    last_card = card
    prior = get_prior(challenge_id)   # lagged avoid-atlas may update
```

Client budgets (“$300 compute, max 5 paid submits”) are **agent policy**, not protocol consensus.

---

## 15. Gaming matrix

| Vector | Mitigation |
|--------|------------|
| Prior as weight dump | Redact; coarsen |
| Prior as exact recipe | Coarsen + noise + k-aggregate |
| Prior as eval oracle | No seeds; lag; tags ≠ draws |
| Prior similarity score | **Banned** in Score Pack |
| Estimate as fake official score | No lean_score field; non_binding |
| light_compare as official grade | mock_only disclaimer; never Yuma |
| Overfit mock → claim grade | Only submit grades |
| Scaffold = champion weights | Scaffold is coarse steer only |
| Result card seed leak | Tags/scores; own submission |
| Gates weakened by prior | Priors never thin gates |
| Spam submits | Fee + dry_validate + rate policy |

---

## 16. Versioning

- `prior_version` and strategy `schema_version` evolve independently  
- Submit validates against **current** challenge schema  
- EvaluationCard echoes `scoring_pack_hash`  
- Mock pack ids versioned separately from validator packs  

---

## 17. Invariants (normative)

1. Priors never include weights or official eval seeds.  
2. Priors never appear as a term in lean scoring.  
3. Estimation never authorizes emissions or predicts official lean score.  
4. light_compare / light_train never see validator packs or VALIDATOR_RANGES.  
5. Submit always re-runs the hidden exam; fee ≠ score.  
6. Existence of a prior never reduces the mandatory gate set.  
7. One public prior channel — no VIP clean feed.  
8. `get_submission_result` never returns seeds, draw ids, or other miners’ full cards.  
9. `failure_modes` tags share vocabulary with avoid-atlas.  
10. No lab-specific MCP forks required for standard agent miners.  
11. **Free path is first-class:** agents must be able to iterate without submitting; paid exam is confirmation, not the default step.  
12. light_compare scaffold is noisy steer (or miner local best) — never champion checkpoint weights.  

---

## 18. Related documents

| Doc | Role |
|-----|------|
| [`../SPEC.md`](../SPEC.md) | Dual path, trustless exam, phases |
| [`Scoring.md`](./Scoring.md) | Lean formulas; ban on prior similarity |
| [`Launch_Bar.md`](./Launch_Bar.md) | Before public prior publish |
| [`Data_Management.md`](./Data_Management.md) | Seeds; train ≠ eval |
| [`Landscape_Agent.md`](./Landscape_Agent.md) | Subnet-side prior production |
| [`Generator_Creation.md`](./Generator_Creation.md) / [`Evidence_and_Envelope_Standards.md`](./Evidence_and_Envelope_Standards.md) | Challenge credibility upstream |

---

## 19. Doctrine

**Carbon’s Miner MCP is a control surface for competitive scientific discovery.**

Agents **grind for free**: priors steer, estimate filters doom, light_compare ranks candidates against a noisy frontier scaffold on incomplete mock data, light_train deepens local practice. **Submit is rare:** the only official grade uses hidden draws and hard gates. **get_submission_result** returns scores and failure tags — never the answer key — so the next free loop is smarter.

Carbon need not build the best AI scientist. It supplies hard physics problems, open method competition, agent-native tools, a dense free practice surface, independent evaluation, incentives, and compounding failure knowledge. Any researcher — human, Hermes, Mira, or anonymous miner — can plug in, iterate without paying, and submit when they believe they can beat the exam.

---

*Miner MCP v2.1 — free-first iteration (estimate + light_compare), closed paid feedback, referee thesis. Implementation must preserve all §17 invariants.*
