# Scoring.md — Lean Emission Scoring & Challenge Score Bank

## TL;DR

**Job:** Define *exactly* how a trained model becomes a lean emission score — in a way that is **challenge-specific, versioned, auditable, and trustless**.

**Core split**

| Concept | Role |
|---------|------|
| **Training loss** | Optimizer objective *during* validator retrain — **not** an emission term |
| **Hard gates** | Binary kill switch (FAIL → score 0) |
| **Soft legs** | Physics 45% · Robustness 30% · Accuracy 25% |
| **Challenge Score Pack** | Frozen YAML/JSON bound to `challenge_id` + `scoring_version` + generator version |

**Trustless rule:** Validator does **not** invent weights at runtime. It loads the Score Pack registered for that challenge version. Anyone with `(challenge_id, scoring_version, generator_version, seed material)` can reproduce scores.

**Bank:** `carbon/scoring/bank/<challenge_id>/vX.Y.yaml` (or equivalent). Same pattern as generators in Data Management — one pack per challenge version.

**Landscape:** Scalar `S_combined` pays emissions. **Vectors** (margins, per-category robustness) on the Model Card feed specialists. Landscape never writes the grade.

**Not in lean score:** train loss, product battery, Landscape similarity, prior distance, commercial SKU status.

---

**Version:** 1.0  
**Status:** Protocol appendix — security + incentive critical  
**Related:** `SPEC.md` §8, `Data_Management.md`, `POC_Burgers_FNO.md`, `Specialist_Bank.md`, `Landscape_Agent.md`

---

## 1. Why a Score Bank (not one global formula)

Different PDEs have different conserved quantities, residual definitions, and stress taxonomies.

| Challenge family | Physics legs differ | Stress categories differ |
|------------------|---------------------|---------------------------|
| Burgers 1D | residual, mass-proxy, short roll | low ν, high amplitude IC |
| Incompressible NS | div-free, momentum residual, energy | Re range, inflow, geometry |
| Compressible / shock | shock capture, entropy | Mach, discontinuity strength |
| Elasticity | equilibrium residual, traction BC | load paths, material contrast |

A single hard-coded residual formula would either be wrong for most challenges or so generic it stops discriminating.

**Therefore:** each challenge ships a **Score Pack** versioned with its **Generator Pack**. Changing τ, α, or category defs is a **version bump**, not a silent validator tweak.

---

## 2. Binding: Challenge Spec owns data + scoring

```text
Challenge Spec (immutable for a live version)
├─ challenge_id
├─ generator_version          # Data_Management
├─ scoring_version            # this document
├─ gate_version               # hard thresholds (may share scoring_version)
├─ backbone_allowlist
└─ scientific notes / refs
```

**Invariant**

```text
score = ScoreEngine(ScorePack[challenge_id, scoring_version],
                    predictions, references, gate_inputs,
                    stress_meta)
```

Validator algorithm:

1. Read `submission.challenge_id`
2. Resolve active `(generator_version, scoring_version)` from on-chain / pinned Challenge Registry
3. Load Generator Pack + Score Pack for those versions (**reject** if missing or hash mismatch)
4. Derive seeds → generate train/eval/stress
5. Train under strategy
6. Run **hard gates** from pack
7. If pass → compute soft legs → `S_combined`
8. Write Model Card with pack hashes + full vectors

**No path** where the validator substitutes “default global weights” when a pack is missing. Missing pack = evaluation error, not a fallback score.

---

## 3. Score Pack schema

```yaml
# carbon/scoring/bank/burgers1d_v0/scoring_v1.0.yaml
challenge_id: burgers1d_v0
scoring_version: "1.0"
generator_version_required: "burgers1d_v0.1"  # must match or be in allow-list
precision: fp32

weights:
  physics: 0.45
  robustness: 0.30
  accuracy: 0.25

margin:
  type: linear_clip   # linear_clip | logistic
  # m(e, tau) = clip(1 - e/tau, 0, 1)

hard_gates:
  - id: finite
    type: no_nan_inf
  - id: conservation
    type: threshold
    error_key: e_cons
    tau: 1.0e-2
  - id: residual_ceiling
    type: threshold
    error_key: e_res
    tau: 5.0e-2
  - id: short_rollout
    type: threshold
    error_key: e_roll
    tau: 1.0e-1

physics:
  components:
    - key: e_res
      alpha: 0.40
      tau: 5.0e-2
      definition: burgers_residual_l2   # registry of named operators
    - key: e_cons
      alpha: 0.30
      tau: 1.0e-2
      definition: periodic_mass_proxy
    - key: e_roll
      alpha: 0.30
      tau: 1.0e-1
      definition: short_rollout_rel_l2

robustness:
  field_error: relative_l2
  lambda_mean_tail: 0.5      # 0.5 mean + 0.5 tail
  tail_quantile: 0.9
  beta_coverage_min: 0.6     # 0.6 mean_c + 0.4 min_c
  tau_rob: 2.0e-1
  categories:                # must align with generator stress categories
    - id: low_viscosity
    - id: high_amplitude_ic
    - id: steep_gradient
  min_category_coverage: 0.95

accuracy:
  field_error: relative_l2
  tau_acc: 1.0e-1
  aggregate: mean            # over eval set

card_required_fields:
  - physics_margins
  - robustness_by_category
  - accuracy_eval
  - gate_results
  - scoring_pack_hash
  - generator_version
```

**Named definitions** (`burgers_residual_l2`, …) live in code under `carbon/scoring/metrics/` and are **referenced by string** from the pack — not reimplemented in YAML. YAML owns weights and thresholds; code owns math kernels.

---

## 4. Lean scoring formulas (protocol)

### 4.1 Hard gates

For each gate in `hard_gates`:

- Evaluate declared error key / predicate in fp32
- If any mandatory gate fails → `S_combined = 0`, still write card with `gate_failed: true`

### 4.2 Margin map

Default:

$\[
m(e,\tau) = \mathrm{clip}\left(1 - \frac{e}{\tau},\, 0,\, 1\right)
\]$

Optional logistic (pack-selectable):

$\[
m_\sigma(e,\tau) = \left(1 + \exp\!\left(-\frac{\tau - e}{\sigma_0\tau}\right)\right)^{-1}
\]$

### 4.3 Physics fidelity $\(S_{\mathrm{physics}}\)$ (weight 0.45)

$\[
S_{\mathrm{physics}} = \sum_k \alpha_k\, m(e_k, \tau_k)
\quad \sum_k \alpha_k = 1
\]$

Component set **and** \(\alpha_k,\tau_k\) come **only** from the Score Pack. Typical Phase-0 families:

| Component | Role |
|-----------|------|
| residual | Local PDE residual norm |
| conservation | Global invariant defect |
| boundary | BC residual when applicable |
| short_rollout | Lean multi-step / stability proxy |

### 4.4 Robustness $\(S_{\mathrm{robustness}}\)$ (weight 0.30)

Per stress category \(c\), field error \(\varepsilon_{c,i}\) (same family as accuracy, usually relative \(L^2\)):

$\[
E_c^{\mathrm{mean}} = \mathrm{mean}_i\varepsilon_{c,i},\quad
E_c^{\mathrm{tail}} = \mathrm{quantile}_q(\varepsilon_{c,i})
\]$

$\[
r_c = m\big(\lambda E_c^{\mathrm{mean}} + (1-\lambda) E_c^{\mathrm{tail}},\, \tau_{\mathrm{rob}}\big)
\]$

$\[
S_{\mathrm{robustness}} =
\beta\,\mathrm{mean}_c(r_c) + (1-\beta)\,\min_c(r_c)
\]$

Defaults unless pack overrides: \(\lambda=0.5\), \(q=0.9\), \(\beta=0.6\).

If category coverage \(<\) `min_category_coverage` → evaluation error (do not score).

### 4.5 Accuracy $\(S_{\mathrm{accuracy}}\)$ (weight 0.25)

Eval set only (never stress):

$\[
\varepsilon_{\mathrm{eval}} = \mathrm{agg}_i\,\frac{\|\hat u_i - u_i\|}{\|u_i\| + \delta}
\]$

$\[
S_{\mathrm{accuracy}} = m(\varepsilon_{\mathrm{eval}}, \tau_{\mathrm{acc}})
\]$

### 4.6 Combined

$\[
S_{\mathrm{combined}} =
\begin{cases}0 & \text{any hard gate FAIL} \\
0.45\,S_{\mathrm{physics}} + 0.30\,S_{\mathrm{robustness}} + 0.25\,S_{\mathrm{accuracy}}
  & \text{else (weights from pack; must sum to 1)}
\end{cases}
\]$

Pack **may** override the 45/30/25 split only via governance version bump — Phase 0 packs should keep the global default unless a scientific note justifies otherwise.

### 4.7 Emissions

$\[
w \propto S_{\mathrm{combined}} \cdot \exp(-\Delta_{\mathrm{blocks}} / t_{1/2})
\]$

(`ChallengeWinnerTracker` on lean scores only.)

---

## 5. Validator selection logic (deterministic)

```text
def load_score_engine(challenge_id: str, registry: ChallengeRegistry) -> ScoreEngine:
    meta = registry.active(challenge_id)  # scoring_version, generator_version, content hashes
    pack = ScoreBank.load(challenge_id, meta.scoring_version)
    assert pack.content_hash == meta.scoring_pack_hash
    assert pack.generator_version_required compatible_with meta.generator_version
    return ScoreEngine(pack, metric_registry)
```

| Failure | Result |
|---------|--------|
| Unknown challenge_id | Reject submission |
| Score pack hash ≠ registry | Halt eval (validator misconfig) |
| Generator/scoring version skew | Halt eval |
| Metric `definition` string unknown | Halt eval |

**Consensus:** validators that load different pack hashes produce divergent scores → caught by score mismatch / weight disagreement. Pin packs in the validator image + registry.

---

## 6. Relationship to data generation

| Concern | Owner |
|---------|--------|
| Train/eval/stress **seeds** | Data Management |
| Stress **category IDs** | Generator Pack (source of truth) |
| Robustness category list | Score Pack **must reference the same IDs** |
| Extended stress envelopes | Generator Pack |
| τ / α / λ / β | Score Pack |

**Coupling rule:** Score Pack `robustness.categories[].id` ⊆ Generator Pack stress category set. CI test: bank consistency check on every pack publish.

---

## 7. Model Card requirements (lean)

Every scored run writes at least:

```json
{
  "challenge_id": "burgers1d_v0",
  "scoring_version": "1.0",
  "scoring_pack_hash": "sha256:...",
  "generator_version": "burgers1d_v0.1",
  "gate_results": [{"id": "conservation", "pass": true, "value": 0.001, "tau": 0.01}],
  "physics_margins": {"e_res": 0.82, "e_cons": 0.91, "e_roll": 0.70},
  "S_physics": 0.81,
  "robustness_by_category": {
    "low_viscosity": {"mean": 0.04, "tail": 0.09, "r": 0.75},
    "high_amplitude_ic": {"mean": 0.06, "tail": 0.12, "r": 0.60}
  },
  "S_robustness": 0.68,
  "accuracy_eval": {"rel_l2_mean": 0.03, "S": 0.70},
  "S_combined": 0.74,
  "gate_failed": false
}
```

Landscape ingests vectors (D1). Emissions use `S_combined` only.

---

## 8. Explicit non-goals (lean path)

| Item | Where it lives instead |
|------|------------------------|
| Train loss curves as score | Training diagnostics only |
| Full inverse-design bakeoff | Product battery (Specialist Bank) |
| Deep HIL-horizon plant suite | PB-ROLL |
| ONNX latency class | PB-LAT |
| Landscape causal similarity | Forbidden as score term |
| Miner-supplied eval metrics | Ignored |

---

## 9. Score Bank layout (repo)

```text
carbon/scoring/
  bank/
    burgers1d_v0/
      scoring_v1.0.yaml
      SCIENTIFIC_NOTES.md      # why τ and categories
    poisson2d_v0/
      scoring_v1.0.yaml
    ...
  metrics/
    residual.py                # named definitions
    conservation.py
    field_error.py
    rollout.py
  engine.py                    # load pack → run gates → soft legs
  registry_client.py           # resolve active versions + hashes
  tests/
    test_pack_schema.py
    test_bank_generator_alignment.py
    test_margin_monotonic.py
    test_hard_gate_zero.py
```

PoC may inline a single pack under `poc/configs/scoring_burgers1d.yaml` until the bank directory exists — same schema.

---

## 10. Versioning & governance

| Change | Action |
|--------|--------|
| Tune τ or α | Bump `scoring_version`; old live challenges unchanged |
| Add stress category | Generator bump **and** scoring bump together |
| Change 45/30/25 | Governance + scoring major version |
| Fix metric bug in code | Metric code version in card; consider rescoring policy |

Historical scores remain comparable only within `(challenge_id, scoring_version)`.

---

## 11. Phase 0 reference pack (Burgers-1D)

| Field | Value |
|-------|-------|
| weights | 0.45 / 0.30 / 0.25 |
| physics α | res 0.40, cons 0.30, roll 0.30 |
| robustness λ, q, β | 0.5, 0.9, 0.6 |
| margin | linear_clip |
| categories | low_viscosity, high_amplitude_ic, steep_gradient |

Exact τ values are challenge science — set in YAML with notes (mesh, ν range, reference solver). Do not hard-code magic numbers in `engine.py`.

---

## 12. Trustlessness checklist

- [ ] Score Pack content hash pinned in Challenge Registry
- [ ] Generator version required by pack matches eval generators
- [ ] All metric definitions pure functions of (pred, ref, config) in fp32
- [ ] Seeds from public derivation path (Data Management)
- [ ] No miner fields enter gate thresholds or τ
- [ ] Card records pack hash + vectors
- [ ] Missing/mismatched pack → hard fail, not silent default
- [ ] Unit tests: monotonic margins, gate zero, category coverage enforce

---

## 13. Implementation order

1. Schema + `ScoreEngine` + margin/gate unit tests  
2. Burgers pack + wire PoC `run_once`  
3. Model Card vector fields  
4. Registry hash pin (even local JSON registry for PoC)  
5. Bank consistency CI vs generator category IDs  
6. Remaining Phase-0 PDE packs  

---

## 14. Relationship to other docs

| Doc | Boundary |
|-----|----------|
| `Data_Management.md` | Seeds, train≠eval, stress categories, entropy floor |
| `SPEC.md` §8 | High-level 45/30/25 + hard-gate rule |
| **This file** | Formulas, pack schema, validator load path |
| `Specialist_Bank.md` | Product battery — **not** lean scoring |
| `Landscape_Agent.md` | Consumes card vectors; does not grade |
| `POC_Burgers_FNO.md` | First consumer of a single pack |

---

*Lean scoring is a versioned, challenge-bound exam: hard gates kill, soft margins rank, vectors train the Landscape, scalars pay emissions. Validators only execute the registered Score Pack — they never improvise the exam.*
