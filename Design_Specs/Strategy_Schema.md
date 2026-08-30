# Strategy Schema — Miner Knob Space (Proposal)

**Carbon Subnet**
**Version:** 1.1 (proposed — extends live `1.0`)
**Status:** Proposal, pending team review
**Related:** [`Generator_Creation.md`](./Generator_Creation.md), [`Scoring.md`](./Scoring.md), [`Scoring_Formulas.md`](./Scoring_Formulas.md), [`Miner_MCP.md`](./Miner_MCP.md), current `carbon/schema/strategy.py`, and `docs/history/LEGACY_CODE_INDEX.md` for retired implementation

> **Current A2 reconciliation (ratified):** This document remains unratified
> future knob-space input; it is not the current wire contract. Strategy v1.0
> has exactly `schema_version`, `challenge_id`, scalar `backbone`, and
> `parameters` at the top level. The older top-level `loss`, `training`,
> `curriculum`, `regularization`, and `compute_tier` examples below are
> historical or proposed catalog shapes, not accepted Strategy v1.0 wire
> fields. Future ratified catalogs belong under `parameters` or in a later
> schema version.

> **Wave B candidate direction:**
> `Miner_MCP_Wave_B_Research_Contract.md` keeps the four-field Strategy v1
> envelope and moves executable knob semantics into a Challenge-bound public
> `ParameterCatalog`, `CandidateAssemblyContract`, and deterministic compiler.
> A catalog may expose only registered, Challenge-bounded training sampling,
> curriculum, and augmentation levers. These resolve to one canonical
> `ResolvedTrainingSamplingPolicy`, denoted `R_strategy`, plus its
> content-addressed `TrainingSamplingPolicyRef`; the validator derives train
> seeds and draws.
> Wave B accepts no raw/custom dataset, data path or URI, miner seed, or official
> evaluation control.
> The examples below are input to that future catalog review, not an executable
> catalog and not permission to implement their values.

---

## TL;DR

**Job:** Define the full knob space a miner can set in a submitted training strategy, so the validator's train+eval loop has something worth searching over.

**Status of the historical catalog called `1.0` here:** Its executable
prototype is archived at `archive/pre-wave-b-legacy-2026-08-30`; it is not
the current four-field Strategy v1 wire contract. This document proposes
future catalog input and grants no permission to restore the archived code.

**What's new in `1.1`:** a `curriculum` block (named by the team as a wanted knob, not yet implemented anywhere), five new loss terms chosen to map directly onto the two highest-weighted Score Pack legs, a `regularization` block, a `compute_tier` field, and a reconciled backbone list.

**Non-goal:** implementation. This is a design document for review. Any
future implementation must use the then-current schema authority; historical
prototype sources are retrievable through `docs/history/LEGACY_CODE_INDEX.md`
only when an owning ticket explicitly authorizes a deliberate port.

---

## 1. Why this schema shape

Scoring (`Scoring_Formulas.md`) weights the three legs **physics 0.40 / robustness 0.35 / accuracy 0.25**, gated by mandatory hard checks (`finite`, `mass_conservation`, `energy_stability`, `short_rollout`) that zero the score on failure. Accuracy is deliberately the *lowest*-weighted leg, "so pure memorization cannot dominate emissions." Every knob proposed below is chosen because it gives a miner a concrete way to move one of these three legs, not because it's a knob that happens to exist in typical neural-operator tooling. A knob that doesn't map to a scored leg isn't earning its complexity here.

---

## 2. Historical proposed catalog (`1.0`, not current runtime authority)

| Block | Fields | Source |
|---|---|---|
| `backbone` | one of `fno`, `fno1d`, `fno2d`, `gino`, `wno`, `transolver`, `physicsnemo_fno`, `pino` | `strategy_schema.py: ALLOWED_BACKBONES` |
| `backbone_config` | `modes`, `width`, `depth`/`layers` | clamped to `VALIDATOR_LIMITS` |
| `loss` | `data_mse`, `physics_residual`, `boundary_mse`, `conservation_penalty`, `initial_condition` — each `{enabled: bool, weight: float}` | `strategy_schema.py: LOSS_TERM_KEYS` |
| `training` | `optimizer`, `learning_rate`, `weight_decay`, `epochs`, `batch_size`, `gradient_clip`, `lr_schedule` | `strategy_schema.py` |
| `budget` | `max_steps`, `batch_size` | `strategy_schema.py` |

**Historical limits are not current authority:** the old PoC validator-limit
file and legacy `strategy_schema.py` remain in the immutable archive. Their
values are unqualified historical evidence and must not be ported or compared
as current limits without the later owning ticket and required human decision.

---

## 3. Proposed `1.1` additions

### 3.1 Backbone list — reconcile, don't just append

| Change | Rationale |
|---|---|
| Collapse `fno` / `fno1d` / `fno2d` into one `fno` backbone + a `dims` field | Same architecture at different dimensionality, not three models |
| Fold TFNO in as `backbone_config.factorization: "tucker" \| "none"` on `fno` | TFNO is FNO with a tensor-factorized spectral weight, not a separate architecture |
| Add `gaot` | Geometry-aware, handles irregular meshes — relevant once challenges move past regular grids (elasticity, NS) |
| Add `gno` | Graph-based, same rationale as GAOT |
| Keep `physicsnemo_fno`, `pino` | Already good inclusions, no change |

### 3.2 New loss terms

| Term | Penalizes | Maps to |
|---|---|---|
| `noise_robustness` | Output sensitivity to small input/IC perturbations | **Robustness leg (0.35, highest-weighted)** and the `viscosity_range` / `ic_amplitude` / `boundary_shift` stress categories directly |
| `rollout_consistency` | Drift when the operator is applied autoregressively for K steps vs. single-step | The `short_rollout` **mandatory hard gate** directly |
| `spectral_matching` | Error concentrated in high-wavenumber modes | Counters FNO's known spectral-bias failure mode; relevant to shock-forming problems (Burgers) |
| `sobolev_penalty` | Mismatch in spatial derivatives, not just field values | Physical realism of gradients — elasticity (stress/strain), NS (velocity gradients) |
| `smoothness_tv` | Spurious oscillation near discontinuities | Standard fix for Gibbs-like artifacts in spectral methods near shocks |

**Phase 0 priority recommendation:** `noise_robustness` and `rollout_consistency` first — they map onto the highest-weighted leg and a mandatory gate respectively, and both are cheap to implement (no new generator or reference-solver work required). The other three are physics-family-specific and can follow as those challenges come online.

All five follow the existing `{enabled, weight}` shape — no new validation pattern needed in `strategy_schema.py`, just additions to `LOSS_TERM_KEYS`.

### 3.3 `curriculum` — new block, not yet implemented anywhere

```json
"curriculum": {
  "type": "none",
  "schedule": "linear",
  "target": "viscosity",
  "anneal_steps": 500
}
```

- `type`: `none` (default) \| `viscosity_anneal` \| `resolution_ramp` \| `loss_weight_schedule`
- `viscosity_anneal` (Burgers-specific example): start training on high-viscosity draws (smooth, no shock) and anneal toward the low-viscosity/shock-forming regime by end of training. Directly implementable against the existing train/eval viscosity bounds (`[0.001, 0.01]`) — no new generator work.
- `loss_weight_schedule`: start `data_mse`-dominant, anneal physics/conservation weight up over training. Standard mitigation for the PINN optimization pathology where physics losses dominate early and the network never fits a baseline.

### 3.4 `regularization` — new block

| Field | Values | Note |
|---|---|---|
| `dropout` | `[0, 0.5]` | Standard |
| `normalization` | `none` \| `layernorm` \| `groupnorm` | Standard |
| `activation` | `gelu` \| `silu` \| `tanh` | Spectral methods sometimes prefer smooth activations |
| `weight_init` | `default` \| `scaled` | FNO spectral weights are sensitive to initial output magnitude — near-free accuracy-leg gain |
| `ema` | `{enabled: bool, decay: float}` | Exponential moving average at eval time, stabilizes generalization without touching the training loss itself |

### 3.5 `compute_tier` — ties to the "pay for an edge" discussion

```json
"compute_tier": "standard"
```

`standard` (default, base fee) vs. `extended` (paid, unlocks a higher `max_steps`/`max_wall_s` ceiling — still hard-capped at `VALIDATOR_LIMITS` regardless of payment). Gives the fee mechanism a concrete field to key off of; does not change the validator's hard rails.

---

## 4. Explicitly out of scope for the miner

Stated because it's as much a design decision as what's included:

- **Seeds** — validator/generator-controlled fresh draws only. This is the core anti-gaming invariant in `Generator_Creation.md` ("Live miner exams use fresh seeded draws... not the public exam set"); a miner-chosen seed would break it directly.
- **Gate thresholds or Score Pack weights** — fixed per `scoring_version`, not per-strategy.
- **Eval/stress data visibility** — never exposed, per the same invariant.

---

## 5. Worked example (`1.0` gold fixture + `1.1` knobs)

```json
{
  "schema_version": "1.1",
  "challenge_id": "burgers1d_v0",
  "backbone": "fno",
  "backbone_config": { "dims": 1, "modes": 16, "width": 32, "depth": 4, "factorization": "none", "weight_init": "scaled" },
  "loss": {
    "data_mse": { "enabled": true, "weight": 1.0 },
    "physics_residual": { "enabled": true, "weight": 0.1 },
    "conservation_penalty": { "enabled": true, "weight": 0.05 },
    "noise_robustness": { "enabled": true, "weight": 0.2 },
    "rollout_consistency": { "enabled": true, "weight": 0.15 }
  },
  "curriculum": { "type": "viscosity_anneal", "schedule": "linear", "anneal_steps": 500 },
  "training": { "optimizer": "adamw", "learning_rate": 0.001, "epochs": 800, "batch_size": 32, "lr_schedule": "cosine" },
  "compute_tier": "standard",
  "budget": { "max_steps": 800, "batch_size": 32 }
}
```

---

## 6. Open questions before implementation

- [ ] Backbone list reconciliation (§3.1) is a code decision (collapsing `fno1d`/`fno2d`, folding TFNO into `factorization`), not just an addition — needs sign-off before touching `ALLOWED_BACKBONES`.
- [ ] Confirm Phase 0 priority ordering for the five new loss terms (§3.2 recommends `noise_robustness` + `rollout_consistency` first).
- [ ] Is `compute_tier`/fee-gating in scope now, or a later-phase concern once the fee mechanism itself is designed?

---

## 7. Done-when checklist (for the eventual implementation PR)

- [ ] `LOSS_TERM_KEYS` extended with the five new terms
- [ ] `curriculum` block added to `validate_and_normalize_strategy`
- [ ] `regularization` block added
- [ ] `compute_tier` added and wired to the fee mechanism
- [ ] Backbone list reconciled in `ALLOWED_BACKBONES` and `Carbon_Logic/backbones/registry.py`
- [ ] New current-authority fixtures added under the owning ticket's canonical fixture root
- [ ] Any justified historical schema idea deliberately ported from the immutable archive, without restoring PoC authority

---

## 8. Relationship to other docs

| Doc | Role |
|---|---|
| **This file** | The miner-facing knob space: what a strategy can specify |
| **`Scoring.md` / `Scoring_Formulas.md`** | What those knobs are scored against — the reason each knob here exists |
| **`Generator_Creation.md`** | Where the training/eval data each strategy is judged on comes from |
| **`Miner_MCP.md`** | How a strategy actually reaches the validator, and where the feedback-loop estimator (next design piece) plugs in |
| **`carbon/schema/strategy.py`** | The current exact Strategy v1 wire authority; this proposal does not extend it automatically |
| **`docs/history/LEGACY_CODE_INDEX.md`** | Retrieval index for the retired proposal-era implementation; archive presence grants no authority |
