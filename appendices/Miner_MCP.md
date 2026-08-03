# Miner MCP Specification

**Carbon — noisy priors · estimation · light train · submit**

**Version:** 1.0  
**Status:** Implementation contract  
**Scope:** Miner- and agent-facing interface only  
**Non-scope:** Validator training internals, Landscape private graph / Port B, product-battery packs, Score Pack math (see [`Scoring.md`](./Scoring.md))

---

## TLDR

- **Four tools:** `get_prior` → `estimate` → optional `light_train` → `submit`.
- **Priors steer search; they do not grade and must not clone.** Lagged, coarsened, noisy, multi-winner aggregates with an explicit avoid-atlas.
- **Estimation is non-binding.** Official score only from validator exam on hidden data.
- **Light train is miner-owned** data/seeds — never official eval packs.
- **Small exam fee** on submit only: anti-spam + verification cost recovery, not pay-to-win.
- **Hard rule:** prior similarity is **forbidden** as a lean score term. Gates never shrink because a prior exists.

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

## 5. How priors are produced (anti-gaming by construction)

Subnet-side pipeline (miners never see raw card lakes through MCP):

### 5.1 Eligibility

- Only lean-verified results eligible  
- Public prior publish only when Launch Bar policy allows ([`Launch_Bar.md`](./Launch_Bar.md))  
- Prefer **multi-winner / multi-run aggregates** (k ≥ policy minimum) over single-UID dumps  

### 5.2 Required transforms

1. **Lag** — Exclude the freshest unevaluated tip; fixed delay (tempo or calendar).  
2. **Aggregate** — Blend eligible strategies so no single miner is the prior.  
3. **Coarsen** — Continuous hyperparams → bins; schedules → stage tags; architecture → family.  
4. **Noise** — Policy jitter on non-structural fields; optional dropout of optional flags.  
5. **Redact** — Strip tensors, exact seeds, generator eval params, full loss graphs.  
6. **Split channels** — Structural steer vs avoid-atlas vs explore-mask (see §6).  
7. **Bind + hash** — `challenge_id`, `backbone_scope`, `scoring_pack_hash`, `prior_version`, `as_of`, `content_hash`.  

### 5.3 Why gaming fails here

| Attack | Control |
|--------|---------|
| Clone weights | Never included |
| Pre-fit today’s eval | Seeds never included; lag on leader signal |
| Reverse-engineer stress set | Avoid-atlas is mode tags, not draws |
| Rank via “look like prior” | **Forbidden** as lean score term |
| Insider clean feed | Single public prior channel |
| One-miner takeover of prior | k-aggregate + lag |
| Use prior to disable gates | Validator ignores miner gate toggles; schema denylist |

---

## 6. Prior document shape (normative channels)

```text
Prior {
  prior_version: string
  content_hash: string
  challenge_id: string
  backbone_scope: string | "any"
  scoring_pack_hash: string
  as_of: timestamp
  lag_policy: string

  structural_steer: {
    backbone_family: ...
    loss_enables_coarse: ...      # booleans / bins, not full schedules
    curriculum_stage_tags: ...
    training_family_tags: ...
  }

  strength_bands: {
    physics: noisy band
    robustness: noisy band
    accuracy: noisy band
  }

  avoid_atlas: [
    { mode_tag, severity, note? }   # e.g. conservation_fail, shock_smear, rollout_blowup
  ]

  explore_mask: {
    freeze: [fields worth keeping stable]
    explore: [fields agents should search]
  }

  noise_manifest: object             # audit of coarsen/jitter policy
  not_included: string[]            # explicit denylist
}
```

**Innovation — three-channel prior**

| Channel | Role |
|---------|------|
| **structural_steer** | Where the frontier roughly sits |
| **avoid_atlas** | What recently *failed closed* (often more valuable than the win sketch) |
| **explore_mask** | Where to search next without publishing the optimum |

Agents that only clone `structural_steer` and ignore `avoid_atlas` / `explore_mask` are under-using the interface on purpose — the design rewards exploration under constraints.

---

## 7. Core objects

### 7.1 Strategy

Schema-versioned JSON (`schema_version`, `challenge_id`, `backbone`, `training`, `loss` enables, `curriculum`, `data` hints, `meta`).

**Invariants**

- Must not set validator eval seeds, stress ids, or gate disable flags  
- `meta.prior_version` optional but recommended (analytics only; **not** a score input)  
- Optional `meta.delta_from_prior: true` when client mutates from a pinned prior (documentation aid, not a bonus)  
- Entropy / anti-degenerate rules on miner generator params remain as in SPEC  

### 7.2 Estimate

```text
Estimate {
  strategy_hash: string
  prior_version: string
  predicted_components: { physics?, robustness?, accuracy? }
  gate_fail_risk: { gate_id: low|med|high }
  clone_proximity_warning: none|elevated   # estimator UX only — NOT official score
  confidence: low|med|high
  warnings: string[]
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
| `get_challenge_info` | Free | Public rules, schema version, fee quote, pack hashes |
| `dry_validate` | Free | Schema / denylist check only — no queue, no fee |
| `estimate` | Free / CPU | Non-binding forecast |
| `light_train` | Miner compute | Local loop; no network grade |
| `submit` | Exam fee | Official validator exam |

No tool returns specialist weights, clean champion JSON, or validator packs.

---

## 9. Estimation mode

### Purpose

Spend full exams on strategies that are less likely to hard-fail. Optimize agent search, not replace consensus.

### Allowed inputs

Strategy + pinned prior + public challenge constants.  
**Forbidden:** validator seeds, hidden stress draws, private cards.

### Method class (I/O contract; implementations may differ)

Compliant examples:

- Delta heuristics vs `structural_steer`  
- Avoid-atlas risk flags when known failure modes are re-enabled  
- Cheap sensitivity using only public aggregates  

### Honesty rules

- Always `disclaimer: "non_binding"`  
- Forbidden output names that imply official rank (`emission_weight`, `lean_score`, …)  
- Optional `clone_proximity_warning` may fire if strategy is nearly identical to coarse steer — **UX only**; validator must not implement prior-similarity scoring  

### Anti-gaming

Estimation cannot raise score ceiling, reduce fee, or skip gates. Every accepted submit is fully re-examined on hidden data.

---

## 10. Light training mode

### Purpose

Optional upside: miners buy local iterations with their own hardware or rented compute.

### Data rules

| Rule | Requirement |
|------|-------------|
| Seeds | Miner-chosen only |
| Generators | Public code allowed; must not claim official pack identity |
| Gates | Optional local learning signal |
| Upload | Lean path submits **strategy**, not a requirement to upload weights |

### Separation

Light-train distributions remain seed- and config-distinct from validator draws. Any client “validator replay” mode is non-compliant with this MCP.

---

## 11. Submit path

1. `dry_validate` recommended client-side  
2. Charge **small evaluation fee** (spam + verification recovery)  
3. Validator: hidden procedural data → train under strategy as required → hard gates → Score Pack → card  
4. Lean score only from this path  
5. Fee never enters the score function  

**Idempotency:** identical `strategy_hash` within a defined window follows a single published fee policy (no silent double-charge).

**Rate / sybil:** ops may add per-hotkey rate limits; mechanism still must not reward prior-similarity.

---

## 12. Data and eval separation

| Stage | Data | Gates | Meaning | Cost |
|-------|------|-------|---------|------|
| Prior | Aggregated lagged noisy derivative | n/a | Steering | Free |
| Estimate | Strategy + prior + public constants | Soft risk | Forecast | ~0 |
| Light train | Miner seeds / public gens | Optional local | Private learning | Miner |
| Submit | Hidden validator packs | Mandatory hard | Official lean score | Exam fee |

Train ≠ eval ≠ stress on the validator path remains protocol law ([`Data_Management.md`](./Data_Management.md)).

---

## 13. Gaming matrix (priors, eval, data)

| Vector | Mitigation |
|--------|------------|
| Prior as weight dump | Redact tensors; coarsen |
| Prior as exact recipe | Coarsen + noise + aggregate |
| Prior as eval oracle | No seeds; lag; avoid-atlas ≠ draws |
| Prior similarity score | **Banned** in Score Pack |
| Estimate laundering | Non-binding; no fee/score coupling |
| Light train exam leak | No official packs in toolkit |
| Strategy injects eval knobs | Schema denylist; validator ignores |
| Gate set weakened by prior | Explicit invariant: priors never thin gates |
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
      light_train(strategy)   # optional
  if worth_exam(est, info.fee_quote):
      submit(strategy)
      break
```

Casual agents may omit `light_train` and ignore masks at their peril. Power agents loop locally before one fee.

---

## 15. Versioning

- `prior_version` and strategy `schema_version` evolve independently  
- Submit validates against **current** challenge schema  
- `content_hash` on priors enables client-side integrity checks  

---

## 16. Invariants (normative)

1. Priors never include weights or official eval seeds.  
2. Priors never appear as a term in lean scoring.  
3. Estimation never authorizes emissions.  
4. Light train never sees validator packs.  
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
| [`Landscape_Agent.md`](./Landscape_Agent.md) | Subnet-side prior *production* (not miner internals) |

---

## 18. Doctrine (one paragraph)

**Priors exist so search compounds without cloning.** They are lagged, coarsened, noisy, multi-winner steering documents split into structural steer, avoid-atlas, and explore-mask—not weights, not eval keys, not a score feature. **Estimation** exists so agents spend exam fees on plausible work and must never be treated as rank. **Light train** exists so miners can buy upside with their own compute on non-exam data. **Submit** is the only official grade: hidden data, hard gates, small fee for spam and verification cost. Gaming via priors or local loops fails because nothing in this MCP can replace the validator’s independent draw, thin the gate set, or write prior similarity into emissions.

---

*Miner MCP v1.0 — lean interface, hard boundary, agent-first loop.*
