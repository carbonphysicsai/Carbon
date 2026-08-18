# Launch_Bar.md — Gate & Score Bar Before Landscape Compounds

> **Reconciliation (post-ratification):** **Port B** strengthened — every scored nonzero submission completes the **same mandatory lean pack**. Progressive depth is **scheduling / prefilter / supplemental**, not variable grading of the lean exam identity.


## TL;DR

**Problem:** The Landscape flywheel treats lean Model Cards as training labels. If gates and scores are unfinished, **garbage-in compounds**.

**Rule:** Do not present cards as “verified” for Port A publish, causal fits, or external intelligence claims until this bar is green.

**Lead product claim at raise / pre-launch:** trustless verification + dual threshold + sponsored path.  
**Landscape:** architecture and build order — not a live brain.

---

**Version:** 1.1  
**Status:** Protocol stop-ship checklist  
**Related:** `Scoring.md`, `Data_Management.md`, `POC_Burgers_FNO.md`, `Miner_MCP.md`, `Build_Out.md`, `Landscape_Agent.md`, `SPEC.md` §8

---

## 1. Why this bar exists

| Epistemic grade | What it is |
|-----------------|------------|
| **Hard gates + lean score** | Protocol ground truth (when implemented) |
| **Causal bands / priors** | Observational estimates on those labels |

Causal libraries cannot be more trustworthy than the labels that feed them. This document binds Landscape L0+ to a **working lean exam**.

---

## 2. Stop-ship checklist (all required)

### 2.1 Lean exam integrity

- [ ] **Hard gates can zero** `S_combined` (finite / NaN, conservation, residual ceiling, short rollout as pack requires)
- [ ] **Train ≠ eval ≠ stress** seeds (Data Management invariants; automated test)
- [ ] **Score Pack** loaded by `(challenge_id, scoring_version)`; content hash pinned; **no silent global default**
- [ ] Generator version required by Score Pack matches active Generator Pack
- [ ] Stress **category coverage** ≥ pack minimum before soft score
- [ ] Physics / robustness / accuracy legs computed per Score Pack (see `Scoring.md`)

### 2.2 Discrimination & reproducibility

- [ ] **Gate-fail fixture** → `gate_failed=true`, `S_combined=0`
- [ ] **Discrimination:** compliant / physics-aware strategy ranks above broken strategy on combined (same seeds)
- [ ] **Reproducibility:** fixed seeds → scores within documented ε (CPU stricter)
- [ ] Golden fixtures checked into CI for the first live challenge (Burgers or designated)

### 2.3 Model Card minimum

- [ ] Card writes: gate results, `physics_margins`, `robustness_by_category`, accuracy summary, `S_*`, pack hash, generator version, seeds roles
- [ ] Cards from full evals are append-only loggable (even if Landscape publish is off)
- [ ] Miner-visible **EvaluationCard** is a budgeted projection of the Model Card (see `Miner_MCP.md`) — not a second scoring path

### 2.4 Miner MCP readiness (Phase 0 subnet loop)

Required before marketing agent mining or public prior surfaces that agents will grind against. Detail: `Miner_MCP.md`, `Build_Out.md`.

- [ ] **Mock isolation:** `light_compare` / `light_train` reject non-`mock_` packs; no official seeds on free path
- [ ] **Free signal imperfect:** mock ranges intentionally incomplete; free metrics **never** enter lean score / Yuma
- [ ] **Scaffold path:** `get_mock_scaffold` serves a versioned mediocre baseline (not champion weights; not silent prior invert)
- [ ] **Budgeted EvaluationCard:** miner-visible card withholds fine margins / per-stress breakdowns / seeds
- [ ] **Fee ≠ score:** exam fee does not enter Score Pack
- [ ] **Forbidden score inputs:** no prior similarity, estimate, or light_compare in `S_combined`
- [ ] **PoC handoff:** TrainEvalAPI (or equivalent) used by both official exam and mock path without mode confusion

`Build_Out` Phase 0.9 = this document’s lean exam bar **plus** §2.4 when shipping the full agent/subnet loop (not required for offline PoC-only demos).

### 2.5 Landscape publish gates (L0)

Until §2.1–2.3 are green for at least one live challenge family (and §2.4 if public agent/MCP mining is claimed):

- [ ] **No** public claim that Landscape “produces intelligence” or causal effects
- [ ] **No** Port A daily noisy-prior product surface marketed as verified guidance
- [ ] Cards may be retained **offline for engineering only**
- [ ] Port B progressive routing **off** or forced full-depth only

When green:

- [ ] L0 may publish **aggregate / noisy** priors with `landscape_version` + `data_cutoff_block`
- [ ] Explicit status: L0 = card lake + noisy aggregates — **no causal yet** (causal = L2)

---

## 3. Representation discipline (pitch & external)

| Allowed | Not allowed |
|---------|-------------|
| Verification layer + dual threshold + sponsored challenges as lead | “Private AI brain already knows what works” |
| Landscape as **designed** four-port compounding architecture | Gate-level certainty on causal bands |
| Build order L0→L4 with status marks | Implied live DML / Port D at raise |
| Success = post-gate progress + later PB conversion | Success = guidance-API engagement |

**Epistemic line (repeatable):**  
*Gates are verified when the Launch Bar is green. Causal effects are estimated decision-support under selection bias — never spoken as protocol truth.*

---

## 4. Port B floor (even after bar is green)

Progressive depth is the highest-risk Landscape port (touches how hard the exam looks).

**Always full depth when any apply:**

- New or low-history hotkey on that challenge  
- Random audit fraction (pack- or policy-defined)  
- Top-K leaderboard threat / near-record combined  
- Prior shallow path followed by contested rank movement  

**Never:** miner-visible routing; routing written into score; shallow-only path as sole exam for emissions without audit coverage.

Detail: `Landscape_Agent.md` § Port B bounds.

---

## 5. Exit criteria summary

```text
Launch_Bar_GREEN(challenge_family) =
    hard_gates_zero_score
    AND seed_separation_tested
    AND score_pack_hash_pinned
    AND discrimination_and_repro_CI
    AND model_card_vectors_written
```

```text
MCP_AGENT_SURFACE_GREEN =
    Launch_Bar_GREEN(family)
    AND mock_isolation_tested
    AND free_metrics_not_in_yuma
    AND budgeted_evaluation_card
    AND fee_not_in_score
```

```text
Landscape_L0_PUBLISH_ALLOWED =
    Launch_Bar_GREEN(at least one live family)
    AND representation_discipline_acknowledged
```

```text
Landscape_L2_CAUSAL_PUBLISH_ALLOWED =
    L0_PUBLISH_ALLOWED
    AND sufficient card volume + overlap diagnostics
    AND publish gates (CI excludes zero, stability windows)
    AND still no gate-level certainty language
```

---

## 6. Ownership

| Item | Owner |
|------|--------|
| Gate/score implementation | Protocol + SciML eng |
| Score Pack science (τ, categories) | Physics lead |
| Launch Bar CI enforcement | Tech lead |
| MCP free-path guards | Protocol + agent eng |
| External representation | Founder / GTM — must match this doc |

---

*The flywheel is only as honest as the exam. This bar is the exam’s on-switch for compounding claims.*
