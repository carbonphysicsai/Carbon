# Miner MCP Specification

**Carbon — noisy priors · estimation · light train · submit**

**Version:** 1.1  
**Status:** Implementation contract  
**Scope:** Miner- and agent-facing interface only  
**Non-scope:** Validator training internals, Landscape private graph / Port B, product-battery packs, Score Pack math (see [`Scoring.md`](./Scoring.md))

---

## TLDR

- **Tools:** `get_prior` → `estimate` → optional `light_train` → `submit` (+ free `get_challenge_info`, `dry_validate`).
- **Priors** are produced subnet-side from lean-verified cards: lag → k-aggregate → coarsen → noise → redact → three channels (steer / avoid / explore).
- **Estimation** is a deterministic, avoid-atlas-first **filter** — trusted as triage, never as official grade.
- **Light train** uses the public generator *family* with **miner seeds** and a **mock range subset** — cannot reproduce the official exam draw.
- **Submit** is the only emissions path: hidden data, hard gates, small exam fee.
- **Hard rules:** prior similarity forbidden in lean score; priors never thin gates; no VIP prior channel.

---

## 1. Purpose

Enable humans and agents to run a tight search loop against Carbon challenges with minimum friction and maximum upside:

1. Pull a **steering prior** for the active challenge  
2. Propose strategy deltas and **estimate** risk/value  
3. Optionally **light-train** on local compute  
4. **Submit** once for the only official lean score  

Casual path skips light train. Power path spends miner compute before paying the exam fee.

---

## 2. Goals and non-goals

### Goals

- Compound network search without handing out the answer key  
- Agent-stable JSON tools (idempotent, versioned, cost-aware)  
- Clear trust boundary: steer ≠ grade ≠ sell  
- Spam-resistant full exams  
- Upside unbounded in *local* iteration, bounded only by miner resources  

### Non-goals

- Local replay of the official exam  
- Distribution of champion weights or exact winning recipes  
- Estimation as a substitute for Yuma / lean score  
- VIP prior channels  
- Embedding Landscape causal graphs in the miner toolkit  

---

## 3. Trust boundary

| Asset | Via Miner MCP? | Rule |
|-------|----------------|------|
| Noisy prior document | Yes | Lagged, coarsened, challenge-bound |
| Avoid-atlas (failure-mode tags) | Yes | Aggregated, delayed; no seed material |
| Explore / freeze masks | Yes | Steering only |
| Official eval / stress seeds | **Never** | Validator-only |
| Live stress catalogs tied to packs | **Never** | Public *rules* may be documented |
| Champion weights / exact bank recipe | **Never** | Dual egress elsewhere |
| Lean official score | Only after **submit** + validator | Hidden data, hard gates |
| Prior distance as score feature | **Forbidden** | See Scoring.md |

**Doctrine:** *Steering signal in. No answer key out. Gates do not get thinner because priors exist.*

---

## 4. Why priors exist (purpose)

### Problem without priors

Every miner starts cold → wasted full exams, agent thrashing, fee pressure, weak network effect.

### Problem with full winner disclosure

Clone races, diversity collapse, optimization against one lineage, exam gaming via leader theft instead of physics survivability.

### What priors are for

| Intent | How |
|--------|-----|
| Orient search | Coarse family of choices that recently survived lean exams |
| Speed agents | Mutate JSON, do not invent schema from scratch |
| Preserve adversarial grading | No weights, no eval seeds, no exact schedules |
| Kill pure clone value | Lag + coarsen + noise + multi-winner blend |
| Transmit failure knowledge | Avoid-atlas: modes that zeroed scores (high agent value) |
| Direct exploration | Explore-masks: dimensions worth searching vs freeze-tags |

**Success metric:** more *diverse, non-doomed* submissions per fee — not higher clone rate of the leader.

Priors are a **search accelerator under information restriction**, not a teacher checkpoint channel.

---

## 5. Where priors come from (exact pipeline)

**Producer:** subnet-side prior publisher (ops job today; Landscape Port A later).  
**Consumers:** all miners via `get_prior` — one public channel.

### 5.1 Pipeline

```text
Lean-verified cards (gates recorded, score > 0 or structured fails)
        → window select (e.g. last K tempos / 24h)
        → eligibility (challenge_id + scoring_pack_hash match)
        → k-aggregate (prefer ≥ k distinct strategies / hotkeys)
        → lag (drop freshest unevaluated tip)
        → coarsen continuous fields → bins / tags
        → noise / optional flag dropout
        → redact weights, seeds, exact schedules, eval params
        → split channels: structural_steer | avoid_atlas | explore_mask
        → bind prior_version, as_of, content_hash
        → publish
```

**Gate:** no public prior (or only a marked bootstrap prior) until [`Launch_Bar.md`](./Launch_Bar.md) policy allows.

### 5.2 Eligibility and k-aggregate

- Only results that completed the lean path under the current pack hash  
- Prefer multi-run / multi-UID blends so one miner cannot own the prior  
- Hard zeros contribute to **avoid_atlas**, not to structural_steer  

### 5.3 Required transforms

1. **Lag** — fixed delay (tempo or calendar)  
2. **Aggregate** — blend eligible coarse features  
3. **Coarsen** — hyperparams → bins; schedules → stage tags; architecture → family  
4. **Noise** — jitter on bands; optional dropout of non-mandatory flags  
5. **Redact** — tensors, exact LRs, generator eval params, full loss graphs  
6. **Split channels** — steer / avoid / explore  
7. **Bind + hash** — `challenge_id`, `backbone_scope`, `scoring_pack_hash`, `prior_version`, `as_of`, `content_hash`  

### 5.4 Worked example — Burgers 1D / FNO-family prior

Illustrative document returned by `get_prior("burgers1d")`:

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

### 5.5 Why gaming fails on production

| Attack | Control |
|--------|---------|
| Clone weights | Never included |
| Pre-fit today’s eval | Seeds never included; lag |
| Reverse-engineer stress set | Avoid-atlas = mode tags, not draws |
| Rank via “look like prior” | **Forbidden** as lean score term |
| Insider clean feed | Single public channel |
| One-miner prior capture | k-aggregate + lag |
| Disable gates via prior | Validator ignores miner gate toggles; schema denylist |

---

## 6. Prior document shape (normative channels)

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
| **avoid_atlas** | What recently failed closed (often highest agent value) |
| **explore_mask** | Where to search next without publishing the optimum |

Agents that only clone `structural_steer` and ignore avoid/explore under-use the interface; the design rewards constrained exploration.

---

## 7. Core objects

### 7.1 Strategy

Schema-versioned JSON: `schema_version`, `challenge_id`, `backbone`, `training`, `loss` enables, `curriculum`, `data` hints, `meta`.

**Invariants**

- Must not set validator eval seeds, stress ids, or gate disable flags  
- `meta.prior_version` recommended (analytics only; **not** a score input)  
- Optional `meta.delta_from_prior: true` (documentation aid, not a bonus)  
- Entropy / anti-degenerate generator rules as in SPEC  

### 7.2 Estimate

```text
Estimate {
  strategy_hash, prior_version,
  predicted_components: { physics?, robustness?, accuracy? },
  gate_fail_risk: { gate_id: low|med|high },
  clone_proximity_warning: none|elevated,   # UX only — NOT official score
  confidence: low|med|high,
  warnings: string[],
  disclaimer: "non_binding"
}
```

### 7.3 SubmitReceipt

`submission_id`, `strategy_hash`, `fee_status`, `accepted`, `queue_ref`.  
Official lean score only after validator completion.

---

## 8. MCP tools

| Tool | Cost | Role |
|------|------|------|
| `get_prior` | Free | Current prior for `challenge_id` (+ optional backbone scope) |
| `get_challenge_info` | Free | Public rules, schema version, fee quote, pack hashes, mock pack ids |
| `dry_validate` | Free | Schema / denylist check — no queue, no fee |
| `estimate` | Free / CPU | Non-binding forecast (reference algorithm in §9) |
| `light_train` | Miner compute | Local loop on mock generator (§10); no network grade |
| `submit` | Exam fee | Official validator exam |

No tool returns specialist weights, clean champion JSON, or validator packs.

---

## 9. Estimation mode — calculation and trust limits

### 9.1 Purpose

Filter doomed strategies before an exam fee. **Not** a certificate.  
**Official truth = validator lean score only.**

| Property | Meaning |
|----------|---------|
| Useful | Ranks better than random before fee |
| Calibrated | Risk flags and confidence improve as estimate→card pairs accumulate |
| Safe | Cannot mint emissions or thin gates |
| Auditable | Deterministic given `(strategy, prior_version)` |

### 9.2 Allowed / forbidden inputs

**Allowed:** strategy JSON, pinned prior, public gate *names*, public challenge constants.  
**Forbidden:** validator seeds, hidden stress draws, private cards, unpublished thresholds if any remain ops-only.

### 9.3 Reference estimator v0 (normative algorithm class)

Implementations may improve fidelity but must preserve honesty rules in §9.5.

```text
function estimate(strategy, prior):
  risks = {}
  conf = "med"
  warnings = []

  # 1) Avoid-atlas match (highest priority)
  for item in prior.avoid_atlas:
    if strategy_reopens_mode(strategy, item.mode_tag):
      risks[item.mode_tag] = item.severity   # e.g. conservation off → hard_zero risk

  # 2) Steer delta
  flips = coarse_field_hamming(strategy, prior.structural_steer)
  if flips large and not guided_by(prior.explore_mask):
    conf = downgrade(conf)
    warnings.append("unguided_large_delta")

  # 3) Band inheritance (coarse only)
  predicted = inherit_bands(prior.strength_bands)
  predicted = nudge_from_public_rules(predicted, strategy)
    # e.g. conservation enable on → lower conservation fail risk

  # 4) Clone proximity (UX only)
  prox = "elevated" if flips <= ε else "none"

  # 5) Confidence
  if prior is bootstrap or bands empty: conf = "low"
  if many hard risks: conf = "high"   # high confidence in *failure* prediction

  return Estimate(
    predicted_components=predicted,
    gate_fail_risk=risks,
    clone_proximity_warning=prox,
    confidence=conf,
    warnings=warnings,
    disclaimer="non_binding"
  )
```

### 9.4 Example estimate response

```json
{
  "strategy_hash": "sha256:…",
  "prior_version": "burgers1d-fno-2026-08-03-a",
  "predicted_components": {
    "physics": "mid",
    "robustness": "mid_low",
    "accuracy": "mid"
  },
  "gate_fail_risk": {
    "conservation": "high",
    "rollout_long": "med"
  },
  "clone_proximity_warning": "none",
  "confidence": "high",
  "warnings": ["avoid_atlas:conservation_fail matched"],
  "disclaimer": "non_binding"
}
```

### 9.5 Honesty and anti-gaming rules

- Always `disclaimer: "non_binding"`  
- Forbidden output names: `lean_score`, `emission_weight`, `official_rank`, …  
- `clone_proximity_warning` is **UX only** — validator must not score prior similarity  
- Estimation cannot change fee, skip gates, or raise score ceiling  
- Every accepted submit is fully re-examined on hidden data regardless of estimate  

### 9.6 What “trust” means here

Trust estimation as a **triage model**: high recall on obvious hard-zero patterns (especially avoid-atlas).  
Do **not** trust it as physics certification. Calibration is empirical (log prior_version + estimate + realized card).

---

## 10. Light training — mock generator contract

### 10.1 Purpose

Optional local practice loop. Miners spend their own compute. **Cannot** replace submit.

### 10.2 Official vs mock

| Piece | Validator exam | Light-train mock |
|-------|----------------|------------------|
| Generator code | Public procedural family | **Same code family** (shared library) |
| Pack identity | Registry pack + **hidden seed schedule** | `mock_pack_id = "mock_" + challenge_id + "_v*"` |
| Seeds | Block/commit-derived, miner-unknown | **Miner-chosen root seed** |
| Ranges | Full VALIDATOR_RANGES / stress categories | **MOCK_RANGES ⊆ milder / incomplete** |
| Gates | Mandatory hard gates | Optional local checks |
| Result | Official lean score | Private metrics only |

### 10.3 Mock sampling contract

```text
light_sample(challenge_id, miner_seed, mock_pack_id, index) -> batch
  require mock_pack_id starts with "mock_"
  require mock_pack_id in published MOCK_PACKS[challenge_id]
  seed_i = hash(miner_seed, mock_pack_id, index)
  params ~ MOCK_RANGES[challenge_id]     # not VALIDATOR_RANGES
  return public_generator(challenge_id, seed_i, params)
```

**Forbidden**

- Requesting validator pack hashes or hidden seed APIs from `light_train`  
- Client modes named “validator replay” / “official stress”  
- Strategy fields that set `eval_seed`, `stress_seed`, or official `generator_pack_hash` (schema denylist; validator ignores if present)  

### 10.4 Why this is not gameable into emissions

1. Miner **cannot reproduce the official draw** (no validator seeds / live stress schedule).  
2. Mock success **never enters Yuma** — only `submit` grades.  
3. Overfit to MOCK_RANGES is expected and should die on the hidden envelope (train ≠ eval).  
4. Same fee and full exam apply even if local metrics look perfect.  

Light mode is a **deliberately incomplete self-play sandbox**, not a second exam.

### 10.5 Data rules summary

| Rule | Requirement |
|------|-------------|
| Seeds | Miner-chosen only |
| Pack id | Must be `mock_*` |
| Ranges | MOCK_RANGES only |
| Upload | Lean path submits **strategy**; weights not required |
| Non-compliance | Validator-replay clients violate this MCP |

---

## 11. Submit path

1. `dry_validate` recommended client-side  
2. Charge **small evaluation fee** (spam + verification recovery)  
3. Validator: hidden procedural data → train under strategy as required → hard gates → Score Pack → card  
4. Lean score only from this path  
5. Fee never enters the score function  

**Idempotency:** identical `strategy_hash` within a defined window follows a single published fee policy.  
**Rate / sybil:** ops may add per-hotkey limits; still no prior-similarity reward.

---

## 12. Data and eval separation

| Stage | Data | Gates | Meaning | Cost |
|-------|------|-------|---------|------|
| Prior | Aggregated lagged noisy derivative | n/a | Steering | Free |
| Estimate | Strategy + prior + public constants | Soft risk | Forecast | ~0 |
| Light train | Miner seeds + MOCK_RANGES | Optional local | Private learning | Miner |
| Submit | Hidden validator packs | Mandatory hard | Official lean score | Exam fee |

Train ≠ eval ≠ stress on the validator path remains protocol law ([`Data_Management.md`](./Data_Management.md)).

---

## 13. Gaming matrix (priors, eval, data)

| Vector | Mitigation |
|--------|------------|
| Prior as weight dump | Redact tensors; coarsen |
| Prior as exact recipe | Coarsen + noise + k-aggregate |
| Prior as eval oracle | No seeds; lag; avoid-atlas ≠ draws |
| Prior similarity score | **Banned** in Score Pack |
| Estimate laundering | Non-binding; no fee/score coupling |
| Light train exam leak | mock_* packs only; no official seeds |
| Overfit mock → claim grade | Only submit grades |
| Strategy injects eval knobs | Schema denylist; validator ignores |
| Gate set weakened by prior | Invariant: priors never thin gates |
| Spam submits | Exam fee + dry_validate + rate policy |
| Stale prior tricks | Version pin + warnings |
| Single-winner prior capture | k-aggregate policy |

---

## 14. Reference agent loop

```text
info  = get_challenge_info(challenge_id)
prior = get_prior(challenge_id)
for k in budget:
  strategy = mutate(prior.structural_steer,
                    avoid=prior.avoid_atlas,
                    explore=prior.explore_mask)
  if dry_validate(strategy).ok is false: continue
  est = estimate(strategy, prior_version=prior.prior_version)
  if est.gate_fail_risk high: continue
  if est.clone_proximity_warning == elevated:
      strategy = force_explore(strategy, prior.explore_mask)
  if compute_available and est.confidence low:
      light_train(strategy)   # mock generator only
  if worth_exam(est, info.fee_quote):
      submit(strategy)
      break
```

---

## 15. Versioning

- `prior_version` and strategy `schema_version` evolve independently  
- Submit validates against **current** challenge schema  
- `content_hash` enables client-side integrity checks  

---

## 16. Invariants (normative)

1. Priors never include weights or official eval seeds.  
2. Priors never appear as a term in lean scoring.  
3. Estimation never authorizes emissions.  
4. Light train never sees validator packs or VALIDATOR_RANGES.  
5. Submit always re-runs hidden exam; fee ≠ score.  
6. Existence of a prior never reduces the mandatory gate set.  
7. One public prior channel — no VIP clean feed.  

---

## 17. Related documents

| Doc | Role |
|-----|------|
| [`../SPEC.md`](../SPEC.md) | Dual path, trustless exam, phases |
| [`Scoring.md`](./Scoring.md) | Lean formulas; ban on prior similarity |
| [`Launch_Bar.md`](./Launch_Bar.md) | Before public prior publish |
| [`Data_Management.md`](./Data_Management.md) | Seeds; train ≠ eval |
| [`Landscape_Agent.md`](./Landscape_Agent.md) | Subnet-side prior production (not miner internals) |

---

## 18. Doctrine (one paragraph)

**Priors** are built from lean-verified cards through lag, k-aggregate, coarsen, noise, and redact, then published as three channels (steer / avoid / explore)—enough to search, not enough to clone or pre-fit the exam. **Estimation** is a deterministic avoid-atlas-first triage model: useful and calibratable, never official. **Light train** uses the public generator family with miner seeds and incomplete MOCK_RANGES so local overfitting cannot unlock emissions. **Submit** remains the only grade: hidden draws, hard gates, small fee. Nothing in this MCP replaces the validator’s independent exam or writes prior similarity into score.

---

*Miner MCP v1.1 — pipeline, reference estimator, and mock generator made explicit.*
