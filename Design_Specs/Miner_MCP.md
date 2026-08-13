# Miner MCP Specification

**Carbon — steer · experiment · submit · independent exam · structured feedback**

**Version:** 2.0  
**Status:** Implementation contract  
**Scope:** Miner- and agent-facing interface only  
**Non-scope:** Validator training internals, Landscape private graph / Port B, product-battery packs, Score Pack math (see [`Scoring.md`](./Scoring.md))

---

## TLDR

Carbon’s Miner MCP is the **agent-native control surface** for competitive scientific search on physics training strategies.

**Closed loop (normative):**

```text
get_challenge_info / get_prior
        → estimate (optional)
        → light_train (optional, miner compute)
        → submit (exam fee)
        → get_submission_result  ← miner-visible evaluation card
        → mutate from failure_modes / scores
        → repeat
```

- **Priors** — lagged, coarsened, noisy steer / avoid / explore (never weights or eval seeds).
- **Estimate** — non-binding triage filter.
- **Light train** — mock generator only; cannot reproduce the official draw.
- **Submit** — only emissions path; hidden data; hard gates; small fee.
- **get_submission_result** — structured feedback after the independent exam (tags + scores, never seeds).
- **Hard rules:** prior similarity banned in lean score; priors never thin gates; no VIP channel; result cards use the same failure-tag vocabulary as avoid-atlas.

**Position:** Carbon does not need to build the best AI scientist. It is the **place where AI scientists compete** — problems, tools, incentives, and a trustworthy referee.

---

## 1. Purpose and thesis

### 1.1 What this interface is for

Enable humans **and autonomous research agents** (Hermes, Mira-class, AutoScience-class, university bots, anonymous Bittensor miners) to run a continuous search loop against Carbon challenges:

1. Orient with a **steering prior**  
2. Propose strategy deltas; **estimate** risk  
3. Optionally **light-train** on local compute  
4. **Submit** for the only official lean grade  
5. **Read structured feedback** and form the next hypothesis  

Casual path: prior → submit → result.  
Power path: full loop with estimate + light train under a compute/fee budget.

### 1.2 Operating-system framing

As AI research becomes autonomous, the scarce layer is a **trustworthy referee**: hard problems, open competition over methods, independent hidden evaluation, economic incentives, and compounding failure knowledge — not another self-reported leaderboard.

```text
More researchers → more experiments → more verified outcomes
  → better priors / avoid-atlas → smarter search → better strategies
  → harder commercial challenges → greater rewards → better researchers
```

Phase 0/1 stays primitive on purpose: one credible challenge, one clean MCP, enough participants to show open search finds better training strategies. The MCP must still be **loop-complete** so agents can plug in without Carbon-specific forks.

### 1.3 Design principle

> Build the Miner MCP correctly. Do not build per-lab integrations.  
> If an off-the-shelf autonomous ML scientist can mine Carbon, that is the proof point.

Pitch line: **Bring your scientist. Carbon brings the problems, incentives, and independent exam.**

---

## 2. Goals and non-goals

### Goals

- Closed research loop for agents (hypothesis → exam → feedback → next hypothesis)  
- Compound network search without handing out the answer key  
- Agent-stable JSON tools (idempotent, versioned, cost-aware)  
- Clear trust boundary: steer ≠ triage ≠ grade ≠ sell  
- Spam-resistant full exams  
- Upside unbounded in local iteration; official grade only via submit  

### Non-goals

- Local replay of the official exam  
- Champion weights or exact winning recipes  
- Estimation as a substitute for lean score / Yuma  
- VIP prior or VIP result channels  
- Embedding Landscape causal graphs in the miner toolkit  
- Building Carbon’s own “best AI scientist” product inside this MCP  
- AutoScience- / Mira- / Hermes-specific adapters  

---

## 3. Trust boundary

| Asset | Via Miner MCP? | Rule |
|-------|----------------|------|
| Noisy prior document | Yes | Lagged, coarsened, challenge-bound |
| Avoid-atlas (failure-mode tags) | Yes | Aggregated, delayed; no seed material |
| Explore / freeze masks | Yes | Steering only |
| Miner-visible evaluation card | Yes | Own submissions only; tags + scores; no seeds |
| Official eval / stress seeds | **Never** | Validator-only |
| Live stress catalogs / draw ids | **Never** | Public *rules* may be documented |
| Champion weights / exact bank recipe | **Never** | Dual egress elsewhere |
| Lean official score | After submit + validator complete | Hidden data, hard gates |
| Prior distance as score feature | **Forbidden** | See Scoring.md |

**Doctrine:** *Steering before the exam. Independent exam. Structured feedback after. No answer key at any step. Gates do not get thinner because priors exist.*

---

## 4. Why priors exist

Without priors: cold start, wasted fees, agent thrashing, weak network effect.  
With full winner disclosure: clone races, diversity collapse, gaming via leader theft.

| Intent | How |
|--------|-----|
| Orient search | Coarse choices that recently survived lean exams |
| Speed agents | Mutate JSON; do not invent schema from scratch |
| Preserve adversarial grading | No weights, no eval seeds, no exact schedules |
| Kill pure clone value | Lag + coarsen + noise + multi-winner blend |
| Transmit failure knowledge | Avoid-atlas mode tags (highest agent value) |
| Direct exploration | Explore vs freeze masks |

**Success metric:** more *diverse, non-doomed* submissions per fee — not higher clone rate of the leader.

---

## 5. Where priors come from

**Producer:** subnet-side prior publisher (ops today; Landscape Port A later).  
**Consumers:** all miners via `get_prior` — one public channel.

### 5.1 Pipeline

```text
Lean-verified cards (including structured fails from evaluation cards)
        → window select (e.g. last K tempos / 24h)
        → eligibility (challenge_id + scoring_pack_hash match)
        → k-aggregate (≥ k distinct strategies / hotkeys preferred)
        → lag (drop freshest unevaluated tip)
        → coarsen → bins / tags
        → noise / optional flag dropout
        → redact weights, seeds, exact schedules, eval params
        → split: structural_steer | avoid_atlas | explore_mask
        → bind prior_version, as_of, content_hash → publish
```

**Gate:** no public prior (or only marked bootstrap) until [`Launch_Bar.md`](./Launch_Bar.md) allows.

Hard zeros and structured `failure_modes` from miner-visible cards feed **avoid_atlas** (aggregated, lagged) — not structural_steer.

### 5.2 Required transforms

1. Lag · 2. Aggregate · 3. Coarsen · 4. Noise · 5. Redact · 6. Split channels · 7. Bind + hash  

(`challenge_id`, `backbone_scope`, `scoring_pack_hash`, `prior_version`, `as_of`, `content_hash`)

### 5.3 Worked example — Burgers 1D / FNO-family prior

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
    "explore": [
      "curriculum_stage_tags",
      "loss_enables_coarse.adversarial_noise",
      "training_family_tags"
    ]
  },
  "noise_manifest": {
    "strength_band_jitter": true,
    "optional_flag_dropout_p": 0.1
  },
  "not_included": [
    "weights",
    "exact_lr_schedule",
    "validator_eval_seeds",
    "stress_draw_ids",
    "full_winner_strategy_json"
  ]
}
```

### 5.4 Gaming controls on priors

| Attack | Control |
|--------|---------|
| Clone weights | Never included |
| Pre-fit today’s eval | No seeds; lag |
| Reverse-engineer stress set | Avoid-atlas = mode tags, not draws |
| Rank via “look like prior” | **Forbidden** in lean score |
| Insider clean feed | Single public channel |
| One-miner prior capture | k-aggregate + lag |
| Disable gates via prior | Validator ignores miner gate toggles; schema denylist |

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
| **structural_steer** | Where the frontier roughly sits |
| **avoid_atlas** | What recently failed closed |
| **explore_mask** | Where to search without publishing the optimum |

Agents that only clone `structural_steer` under-use the interface.

---

## 7. Core objects

### 7.1 Strategy

Schema-versioned JSON: `schema_version`, `challenge_id`, `backbone`, `training`, `loss` enables, `curriculum`, `data` hints, `meta`.

**Invariants**

- Must not set validator eval seeds, stress ids, or gate disable flags  
- `meta.prior_version` recommended (analytics only; **not** a score input)  
- Optional `meta.delta_from_prior` (documentation only)  
- Entropy / anti-degenerate rules as in SPEC  

### 7.2 Estimate

```text
Estimate {
  strategy_hash, prior_version,
  predicted_components: { physics?, robustness?, accuracy? },
  gate_fail_risk: { gate_id_or_mode_tag: low|med|high },
  clone_proximity_warning: none|elevated,   # UX only — NOT official score
  confidence: low|med|high,
  warnings: string[],
  disclaimer: "non_binding"
}
```

### 7.3 SubmitReceipt

```text
SubmitReceipt {
  submission_id, strategy_hash, challenge_id,
  fee_status, accepted, queue_ref,
  status: accepted_queued
}
```

Official lean score is **not** on the receipt. Poll `get_submission_result`.

### 7.4 EvaluationCard (miner-visible)

Returned by `get_submission_result` when the validator reaches a terminal state. **Own submissions only.**

```text
EvaluationCard {
  submission_id, strategy_hash, challenge_id,
  status: queued | running | complete | failed_ops | rejected,
  scoring_pack_hash,
  overall_score,                    # null if gates hard-failed / not complete
  component_scores: { physics?, robustness?, accuracy? },
  gate_results: [ { gate_id, pass: bool, severity? } ],
  failure_modes: [ { mode_tag, severity } ],   # SAME vocabulary as avoid_atlas
  public_diagnostics: string[],     # short structured reasons; no seed material
  challenge_rank?,                  # only if already public on leaderboard policy
  completed_at?
}
```

**Never included:** eval seeds, stress draw ids, full field tensors, other miners’ cards, unpublished thresholds used as attack surface.

**Rule:** `failure_modes.mode_tag` must be drawn from the public tag catalog shared with avoid-atlas so agents can map result → next mutate without a side channel.

---

## 8. MCP tools

| Tool | Cost | Role |
|------|------|------|
| `get_challenge_info` | Free | Public rules, schema version, fee quote, pack hashes, mock pack ids, tag catalog ref |
| `get_prior` | Free | Current prior for `challenge_id` (+ optional backbone scope) |
| `dry_validate` | Free | Schema / denylist check — no queue, no fee |
| `estimate` | Free / CPU | Non-binding forecast (§9) |
| `light_train` | Miner compute | Local mock loop (§10); no network grade |
| `submit` | Exam fee | Queue official validator exam; returns SubmitReceipt |
| `get_submission_result` | Free | Poll EvaluationCard for `submission_id` (authz: submitter only) |
| `list_my_submissions` | Free | Optional: recent submission_ids + coarse status for this hotkey |

No tool returns specialist weights, clean champion JSON, validator packs, or another miner’s full card.

---

## 9. Estimation mode

### 9.1 Purpose

Filter doomed strategies before an exam fee. **Not** a certificate.  
**Official truth = validator lean score only.**

### 9.2 Reference estimator v0

```text
function estimate(strategy, prior):
  risks = {}
  conf = "med"
  warnings = []

  for item in prior.avoid_atlas:
    if strategy_reopens_mode(strategy, item.mode_tag):
      risks[item.mode_tag] = item.severity

  flips = coarse_field_hamming(strategy, prior.structural_steer)
  if flips large and not guided_by(prior.explore_mask):
    conf = downgrade(conf)
    warnings.append("unguided_large_delta")

  predicted = inherit_bands(prior.strength_bands)
  predicted = nudge_from_public_rules(predicted, strategy)

  prox = "elevated" if flips <= ε else "none"

  if prior is bootstrap or bands empty: conf = "low"
  if many hard risks: conf = "high"   # confidence in failure prediction

  return Estimate(..., disclaimer="non_binding")
```

### 9.3 Honesty rules

- Always `disclaimer: "non_binding"`  
- Forbidden output names: `lean_score`, `emission_weight`, `official_rank`, …  
- `clone_proximity_warning` is UX only  
- Estimation cannot change fee, skip gates, or raise score ceiling  
- Every accepted submit is fully re-examined on hidden data  

---

## 10. Light training — mock generator contract

Optional local practice. **Cannot** replace submit.

| Piece | Validator exam | Light-train mock |
|-------|----------------|------------------|
| Generator code | Public family | Same family |
| Pack identity | Registry + hidden seed schedule | `mock_` + challenge_id + `_v*` |
| Seeds | Miner-unknown | Miner-chosen root seed |
| Ranges | VALIDATOR_RANGES / full stress | MOCK_RANGES ⊆ milder / incomplete |
| Result | Official lean score | Private metrics only |

```text
light_sample(challenge_id, miner_seed, mock_pack_id, index) -> batch
  require mock_pack_id starts with "mock_"
  require mock_pack_id in published MOCK_PACKS[challenge_id]
  seed_i = hash(miner_seed, mock_pack_id, index)
  params ~ MOCK_RANGES[challenge_id]
  return public_generator(challenge_id, seed_i, params)
```

Mock success never enters Yuma. Overfit to MOCK_RANGES is expected and should die on the hidden envelope.

---

## 11. Submit path

1. `dry_validate` recommended  
2. Charge **small evaluation fee** (spam + verification recovery)  
3. Return `SubmitReceipt` (`accepted_queued`)  
4. Validator: hidden procedural data → train as required → hard gates → Score Pack → card  
5. Miner learns outcome only via `get_submission_result`  
6. Fee never enters the score function  

**Idempotency:** identical `strategy_hash` within a defined window follows published fee policy.  
**Rate / sybil:** per-hotkey limits allowed; still no prior-similarity reward.

---

## 12. get_submission_result — closing the agent loop

### 12.1 Why it exists

The valuable learning event is **after** the independent exam. Without a structured result tool, autonomous miners cannot run:

```text
hypothesis → experiment → submit → hidden evaluation → feedback → new hypothesis
```

Carbon would be a drop-box, not an environment.

### 12.2 Semantics

| `status` | Meaning |
|----------|---------|
| `queued` / `running` | Not terminal; card fields may be null |
| `complete` | Terminal success path; scores/gates/failure_modes populated per policy |
| `failed_ops` | Infrastructure failure; may be requeued under ops policy; not a physics grade |
| `rejected` | Schema/fee/auth failure before exam |

Authz: only the submitting hotkey (or delegated miner key) may read the card.

### 12.3 Disclosure policy

Emit **the same class of information** a careful human would get from a public leaderboard row + public Model Card summary — structured for agents.

| Include | Exclude |
|---------|---------|
| overall + component scores | eval / stress seeds |
| per-gate pass/fail | stress draw ids |
| failure mode tags (shared catalog) | full solution fields |
| short public diagnostics | other miners’ raw cards |
| scoring_pack_hash | unpublished attackable constants |

### 12.4 Flywheel link

Subnet-side prior publisher may aggregate lagged `failure_modes` into avoid-atlas. That is **public channel compounding**, not a private tutor API.

---

## 13. Data and eval separation

| Stage | Data | Gates | Meaning | Cost |
|-------|------|-------|---------|------|
| Prior | Aggregated lagged noisy derivative | n/a | Steering | Free |
| Estimate | Strategy + prior + public constants | Soft risk | Forecast | ~0 |
| Light train | Miner seeds + MOCK_RANGES | Optional local | Private learning | Miner |
| Submit | Hidden validator packs | Mandatory hard | Official lean score | Exam fee |
| Result card | Miner-visible summary of own exam | Reported | Feedback for next hypothesis | Free poll |

Train ≠ eval ≠ stress on the validator path remains protocol law ([`Data_Management.md`](./Data_Management.md)).

---

## 14. Reference agent loop (closed)

```text
info  = get_challenge_info(challenge_id)
prior = get_prior(challenge_id)
budget = { compute, max_submits, max_fees }

while budget.remaining:
  strategy = mutate(
    prior.structural_steer,
    avoid=prior.avoid_atlas,
    explore=prior.explore_mask,
    last_card=last_evaluation_card   # may be null on first pass
  )
  if not dry_validate(strategy).ok: continue

  est = estimate(strategy, prior_version=prior.prior_version)
  if est.gate_fail_risk indicates hard_zero: continue
  if est.clone_proximity_warning == elevated:
    strategy = force_explore(strategy, prior.explore_mask)

  if budget.compute and est.confidence low:
    light_train(strategy)            # mock only

  if worth_exam(est, info.fee_quote, budget):
    receipt = submit(strategy)
    card = poll get_submission_result(receipt.submission_id)
    last_evaluation_card = card
    # map card.failure_modes → next mutate; optionally refresh prior
    prior = get_prior(challenge_id)  # pick up lagged avoid-atlas updates
```

Client-side budgets (“$300 compute, max 5 paid submits”) are **agent policy**, not protocol consensus.

---

## 15. Gaming matrix

| Vector | Mitigation |
|--------|------------|
| Prior as weight dump | Redact; coarsen |
| Prior as exact recipe | Coarsen + noise + k-aggregate |
| Prior as eval oracle | No seeds; lag; tags ≠ draws |
| Prior similarity score | **Banned** in Score Pack |
| Estimate laundering | Non-binding; no fee/score coupling |
| Light train exam leak | mock_* only |
| Overfit mock → claim grade | Only submit grades |
| Result card seed leak | Tags/scores only; own submission |
| Result card as side channel | Same public tag catalog; no extra secrets |
| Strategy injects eval knobs | Schema denylist; validator ignores |
| Gates weakened by prior | Priors never thin gates |
| Spam submits | Fee + dry_validate + rate policy |
| Single-winner prior capture | k-aggregate |

---

## 16. Versioning

- `prior_version` and strategy `schema_version` evolve independently  
- Submit validates against **current** challenge schema  
- `content_hash` / `scoring_pack_hash` enable client integrity checks  
- EvaluationCard always echoes `scoring_pack_hash` used for the grade  

---

## 17. Invariants (normative)

1. Priors never include weights or official eval seeds.  
2. Priors never appear as a term in lean scoring.  
3. Estimation never authorizes emissions.  
4. Light train never sees validator packs or VALIDATOR_RANGES.  
5. Submit always re-runs the hidden exam; fee ≠ score.  
6. Existence of a prior never reduces the mandatory gate set.  
7. One public prior channel — no VIP clean feed.  
8. `get_submission_result` never returns seeds, draw ids, or other miners’ full cards.  
9. `failure_modes` tags share vocabulary with avoid-atlas.  
10. No lab-specific MCP forks required for standard agent miners.  

---

## 18. Related documents

| Doc | Role |
|-----|------|
| [`../SPEC.md`](../SPEC.md) | Dual path, trustless exam, phases |
| [`Scoring.md`](./Scoring.md) | Lean formulas; ban on prior similarity |
| [`Launch_Bar.md`](./Launch_Bar.md) | Before public prior publish |
| [`Data_Management.md`](./Data_Management.md) | Seeds; train ≠ eval |
| [`Landscape_Agent.md`](./Landscape_Agent.md) | Subnet-side prior production |
| [`Generator_Creation.md`](./Generator_Creation.md) / [`Evidence_and_Envelope_Standards.md`](./Evidence_and_Envelope_Standards.md) | Challenge credibility upstream of exams |

---

## 19. Doctrine

**Carbon’s Miner MCP is a control surface for competitive scientific discovery**, not a model zoo API.

**Priors** steer search under information restriction. **Estimation** triages fees. **Light train** is an incomplete sandbox. **Submit** is the only grade: hidden draws, hard gates, small fee. **get_submission_result** returns a miner-visible evaluation card so autonomous agents can close the loop — scores and failure tags, never the answer key.

Carbon need not build the best AI scientist. It supplies hard physics problems, open method competition, agent-native tools, independent evaluation, incentives, and compounding failure knowledge. Any researcher — human, Hermes, Mira, or anonymous miner — can plug in and try to prove they are better.

---

*Miner MCP v2.0 — closed agent loop, evaluation cards, referee thesis. Implementation must preserve all §17 invariants.*
