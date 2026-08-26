# Compute Optimization Strategy

## TL;DR

**What this is:** System-level plan for where Neural Operator training cost goes and how Carbon spends less without weakening gates or incentives.

**Workload classes (do not conflate)**

| Class | When | Cost model |
|-------|------|------------|
| **`lean_eval`** | Every full submission | Default unit cost; emissions path; staged ordering may stop on a conclusive mandatory failure, while every nonzero score completes the same registered pack |
| **`practice_research`** | Optional miner research | Separate local/practice budget and rights; never official admission, priority, or score |
| **`bank_retrain`** | Specialist promotion | Occasional; same train stack, fresh seeds |
| **`product_battery`** | After bank lean re-gate | Rare INV/ROLL/ADV/LAT jobs — **never** baked into per-submission price |

**Cost reality (FNO-family):** spectral convolution often 35–55% of step time; residual/loss can dominate; pure kernel work alone is not enough.

**Levers (use together):**
1. **Algorithmic** — multi-fidelity curricula, early stop, mode schedules, and later rights-qualified reusable base artifacts (highest system ROI; PriorPacks contain evidence, not weights)
2. **Kernel** — low-rank spectral weights, fused FFT+GEMM, adaptive modes
3. **System** — staged mandatory-check ordering, fair queue admission, sponsored capacity, hard GPU-second budgets, practice isolation, **PB isolation**

**Principle:** expose efficiency knobs in `strategy.json` so the network *searches* efficiency; validators ship high-ROI backends; **lean physics gates remain mandatory** for emissions weight; **product battery** remains mandatory for commercial full SKUs — on a **separate** budget.

**Build priority:** multi-fidelity + conclusive mandatory-failure early stop + low-rank kernels + fair lean scheduling first; broad custom kernel libraries later.

**Read next:** §2 cost profile, §4 algorithmic levers, §5 system mechanisms, §5.6 workload isolation, §7 priority matrix.

---

# Compute Optimization Strategy for Carbon

**Carbon PDE Subnet**  
**Technical Analysis Document**  
**Version:** 2.2 (August 2026)
**Status:** Core Engineering & Strategy Appendix

This document provides a rigorous, system-level analysis of compute efficiency as a limiting factor for the Carbon subnet. It examines where computational cost actually arises in Neural Operator training, evaluates kernel-level and algorithmic strategies for reducing that cost, and analyzes how those strategies interact with validator economics, miner incentives, model quality, and long-term commercial value.

Carbon treats compute efficiency as a first-class design concern. The goal is not merely to reduce validator expense, but to expand the parallel search capacity of the network while preserving scientific rigor and the quality of models that enter the Specialist Bank **via the product battery** — without taxing every miner submission as if it were a commercial graduation exam.

---

## 1. Motivation & Problem Statement

High-fidelity Neural Operator training is expensive. As Carbon progresses from academic PDEs through compressible flow, reacting flows, multi-physics coupling, and 3D turbulence, the computational cost per official **lean** evaluation rises sharply. Without deliberate efficiency mechanisms, validator throughput becomes the binding constraint on parallel strategy search — the core structural advantage of a decentralized approach.

Four pressures make this limiting factor acute:

1. **Validator economics** — Emissions and operational costs must remain sustainable as problem complexity grows.
2. **Search capacity** — Strategies rigorously evaluated per unit time drive discovery speed.
3. **Commercial viability** — Sponsored Challenges and Specialist Bank offerings need lower cost per *verified* product — but product tests are rare, not universal.
4. **Dual threshold** — Inverse-design / deep plant / adversarial suites must not be smuggled into every `lean_eval` or the network collapses under OEM-exam cost.

Carbon's response is multi-layered: kernel-level optimizations,
miner-expressible algorithmic strategies, system-level lean scheduling controls,
an isolated practice-research budget, and **isolated promotion capacity** for
bank/PB work.

---

## 2. Where Time and Memory Are Actually Spent

### Typical Profile (FNO-Family Models)

| Component | Approximate Share of Time | Memory Pressure | Sensitivity |
|-----------|---------------------------|------------------|-------------|
| Spectral convolution (FFT → multiply → iFFT) | 35–55% | High | Dominates at high mode counts and 3D |
| Other linear layers + activations | 15–25% | Medium | Moderate |
| Physics residual / loss computation | 10–25% | Medium–High | Can dominate with high-order derivatives |
| Data loading / preprocessing | 5–15% | Low–Medium | Visible once kernels are fast |
| Optimizer + gradient bookkeeping | 5–10% | Medium | Relatively stable |

**Implication:** Kernel work on spectral convolutions is high-leverage for FNO-family workloads, but the highest system-level gains combine efficient kernels with algorithmic strategies that reduce the **volume** of expensive steps — and with queue policy that does not run product-battery jobs as if they were lean submissions.

---

## 3. Kernel-Level Strategies

### 3.1–3.5 Summary

Low-rank / factorized spectral kernels, continuous mode-wise parameterization, fused FFT+GEMM / Triton kernels, adaptive mode selection, hierarchical / graph / attention directions — **unchanged technical content from v2.0**.

**Risk framing (updated):** Excessively low rank can degrade high-frequency accuracy. Mitigate by miner-controlled rank **and** retaining full **lean** physics-gate evaluation for emissions weight. Commercial SKU entry additionally requires the **product battery** (`Specialist_Bank.md`) — not a weaker lean exam.

---

## 4. Algorithmic and Strategy-Level Levers

Expressible in `strategy.json` and discoverable by the network:

| Strategy | Typical FLOPs Reduction | Notes |
|----------|--------------------------|-------|
| Multi-fidelity spatial + mode curriculum | 2–5× | Highest system ROI |
| Velocity-based early stopping + hard budgets | 1.5–3× | Validator-side rails |
| Low-rank adapters (LoRA) on rights-qualified base artifacts | Large wall-clock | Phase 2A+ under a separate artifact/security contract; miner PriorPacks contain evidence, not weights |
| Physics-parameter + resolution co-curriculum | 1.5–3× | Discovery surface |
| Progressive residual point sampling | 1.3–2× | Residual cost |
| Grad accumulation + checkpointing (Phase 3–4) | VRAM ↓ | Essential for coupled/3D |

Kernel improvements amplify good algorithmic strategies; they do not replace them.

---

## 5. System-Level Mechanisms for Compute Management

### 5.1 Admission and Scheduling Do Not Change the Exam

Rate limits, fair queueing, congestion control, and separately authorized
sponsored capacity may change when work starts. Reputation, stake, sponsorship,
practice results, priors, and resource forecasts must not change the registered
mandatory exam, scientific score, or access to a nonzero result.

### 5.2 Staged Official **Lean** Evaluation

Validators may order mandatory checks to reject a candidate after a conclusive
hard-gate failure. A partial path cannot produce a positive score. Every
candidate receiving a nonzero score completes the same registered lean pack
under the same Challenge identity.

### 5.3 Sponsored Evaluation Capacity

Sponsors (T3/T4) can fund isolated admission capacity for the same registered
lean exam and/or **dedicated PB capacity** for their Challenge definitions.
Funding cannot buy a different candidate-specific exam, scoring depth, or
scientific result.

### 5.4 Hard Per-Challenge and Per-Hotkey Budgets

GPU-second budgets and quotas prevent starvation of the lean path.

### 5.5 Practice Research Isolation

Practice research uses separate nominal request/result types, data rights,
quotas, and workers. Practice results help miners choose what to submit. They do
not prequalify, prioritize, admit, reject, or score official submissions.

### 5.6 Workload Isolation (Bank / Product Battery)

| Rule | Detail |
|------|--------|
| Job classes | `lean_eval` · `practice_research` · `bank_retrain` · `product_battery` (`JAX_Optimization.md`) |
| Scheduling | Separate workers/quotas for practice and separate pool or off-peak quota for bank/PB |
| SLO | Product-battery GPU **must not** block lean emissions latency targets |
| Accounting | Do **not** amortize PB into per-submission unit cost models |
| Failure | PB fail → Landscape promotion_fail; does **not** rewrite the miner’s lean score |

See `Specialist_Bank.md` for what PB contains; this document only constrains **when and how** that compute is spent.

### 5.7 Validator Queue Priority

See `JAX_Optimization.md`. The lean queue uses transparent operational
admission and congestion rules without changing exam depth or scientific
outcome. Practice and bank/PB use isolated capacity.

---

## 6. Full-System Interactions and Second-Order Effects

### Validator Economics and Search Capacity
Efficient kernels, algorithmic levers, conclusive mandatory-failure early stop,
and fair scheduling expand the strategies evaluated under a fixed GPU budget.

### Miner Incentives and Discovery Surface
Efficiency knobs in `strategy.json` expand search beyond loss weights alone. Miner-facing guidance is immutable, coarsened, evidence-labeled PriorPack content only—full specialist warm-starts would collapse search (dual egress).

### Specialist Bank and Commercial Value
Smaller, faster specialists help deployability. **Credibility** still requires gauntlet/PB, paid from promotion budgets — not by weakening lean gates.

### Risk Surface and Credibility
Efficiency must not create paths for physically invalid models to earn emissions **or** commercial packaging. Lean gates are mandatory for weight; the product battery is mandatory for a full SKU. Custom kernels must preserve the registered reproducibility and audit contract.

---

## 7. Priority Matrix (Updated)

| Strategy | Impact | Difficulty | Primary Side | Priority |
|----------|--------|------------|--------------|----------|
| Multi-fidelity spatial + mode curriculum | Very High | Low–Medium | Both | Highest |
| Workload isolation (lean vs PB) | Very High | Low–Medium | System | Highest |
| Low-rank / factorized spectral kernels | High | Medium | Both | High |
| Velocity-based early stopping + hard budgets | High | Low | Validator | High |
| Adaptive mode schedules | High | Medium | Miner-expressible | High |
| Fair admission and queue scheduling | High | Medium | System | High |
| Staged mandatory-check execution | High | Medium | System | High |
| Grad accumulation + checkpointing (Ph 3–4) | Very High | Medium | Both | Highest (Ph 3+) |
| Fused Triton spectral kernels | Medium–High | Medium | Validator | Medium–High |
| Sponsored lean + PB capacity | Medium–High | Low–Medium | Commercial | Medium–High |
| Full general kernel library | Medium | High | Validator | Lower (later) |

---

## 8. Recommended Strategic Posture

1. Expose efficiency knobs in `strategy.json`.  
2. Ship high-ROI kernels on the validator lean path.  
3. Keep lean physics gates hard for emissions.  
4. Isolate product-battery compute; never pretend it is a per-submission cost.  
5. Let Landscape test which efficiency choices predict or support robustness under declared evidence assumptions, not only speed.
6. Isolate sponsored admission capacity and PB capacity without changing the registered lean pack.
7. Phase 3–4 budgets: 2–3× safety margins for coupling / multi-GPU.

---

## 9. Relationship to Other Documents

- [`JAX_Optimization.md`](./JAX_Optimization.md) — masks, scan rails, precision, **job classes**, queue  
- [`Specialist_Bank.md`](./Specialist_Bank.md) — product battery contents and dual egress  
- [`Landscape_Agent.md`](./Landscape_Agent.md) — flywheel ports  
- `SPEC.md` — dual threshold, gates, phases  
- Trust-minimized verification docs — reproducibility constraints on kernels

---

*v2.2 (August 2026): explicit lean, practice, and bank/PB workload isolation; fair admission; the same registered exam pack for every nonzero result. Living analysis, to be updated with measured subnet evidence.*
