# Compute Optimization Strategy

## TL;DR

**What this is:** System-level plan for where Neural Operator training cost goes and how Carbon spends less without weakening gates or incentives.

**Cost reality (FNO-family):** spectral convolution often 35–55% of step time; residual/loss can dominate; pure kernel work alone is not enough.

**Levers (use together):**
1. **Algorithmic** — multi-fidelity curricula, early stop, mode schedules, LoRA on priors (highest system ROI)
2. **Kernel** — low-rank spectral weights, fused FFT+GEMM, adaptive modes
3. **System** — progressive Tier-1/Tier-2 eval, reputation-weighted depth, priority queue, sponsored capacity, hard GPU-second budgets

**Principle:** expose efficiency knobs in `strategy.json` so the network *searches* efficiency; validators ship high-ROI backends; **full physics gates remain mandatory** for real emissions weight or Specialist Bank entry.

**Build priority:** multi-fidelity + early stop + low-rank kernels + progressive eval first; broad custom kernel libraries later.

**Read next:** §2 cost profile, §4 algorithmic levers, §5 system mechanisms, §7 priority matrix.

---

# Compute Optimization Strategy for Carbon

**Carbon PDE Subnet**  
**Technical Analysis Document**  
**Version:** 2.0 (July 2026)  
**Status:** Core Engineering & Strategy Appendix

This document provides a rigorous, system-level analysis of compute efficiency as a limiting factor for the Carbon subnet. It examines where computational cost actually arises in Neural Operator training, evaluates kernel-level and algorithmic strategies for reducing that cost, and analyzes how those strategies interact with validator economics, miner incentives, model quality, and long-term commercial value.

Carbon treats compute efficiency as a first-class design concern. The goal is not merely to reduce validator expense, but to expand the parallel search capacity of the network while preserving (and ideally strengthening) scientific rigor and the quality of models that enter the Specialist Bank.

---

## 1. Motivation & Problem Statement

High-fidelity Neural Operator training is expensive. As Carbon progresses from academic PDEs through compressible flow, reacting flows, multi-physics coupling, and 3D turbulence, the computational cost per official evaluation rises sharply. Without deliberate efficiency mechanisms, validator throughput becomes the binding constraint on the subnet's ability to explore strategy space in parallel — the core structural advantage of a decentralized approach.

Three pressures make this limiting factor acute:

1. **Validator economics** — Emissions and operational costs must remain sustainable as problem complexity grows.
2. **Search capacity** — The number of strategies that can be rigorously evaluated per unit time directly determines how fast superior training methodologies can be discovered.
3. **Commercial viability** — Sponsored Challenges and Specialist Bank offerings become more attractive when the cost of producing high-quality, verified models is lower.

Carbon's response is multi-layered: kernel-level optimizations, miner-expressible algorithmic strategies, and system-level evaluation controls that concentrate expensive compute on the submissions that matter most.

---

## 2. Where Time and Memory Are Actually Spent

Understanding the cost structure of Neural Operator training is a prerequisite for rational optimization.

### Typical Profile (FNO-Family Models)

| Component | Approximate Share of Time | Memory Pressure | Sensitivity |
|-----------|---------------------------|------------------|-------------|
| Spectral convolution (FFT → multiply → iFFT) | 35–55% | High | Dominates at high mode counts and 3D |
| Other linear layers + activations | 15–25% | Medium | Moderate |
| Physics residual / loss computation | 10–25% | Medium–High | Can dominate with high-order derivatives or dense residual sampling |
| Data loading / preprocessing | 5–15% | Low–Medium | Becomes visible once kernels are fast |
| Optimizer + gradient bookkeeping | 5–10% | Medium | Relatively stable |

For GINO-style graph operators the profile shifts toward message-passing and scatter/gather operations. For attention-based operators the dominant cost moves to attention kernels.

**Implication**: Kernel work focused on spectral convolutions is high-leverage for FNO-family workloads, but pure kernel optimization has diminishing returns if the number of full-resolution steps is not also reduced. The highest system-level gains come from combining efficient kernels with algorithmic strategies that reduce the volume of expensive computation.

---

## 3. Kernel-Level Strategies

### 3.1 Low-Rank / Factorized Spectral Kernels

**Mechanism**  
Approximate the full mode-wise complex weight tensor with a low-rank factorization (or related structured approximation).

**Realistic Performance Impact**
- Parameter count: often 5–20× reduction for moderate ranks
- Spectral-domain matmul and memory bandwidth: 2–4× improvement in favorable regimes
- End-to-end training step: typically 1.3–2.2× faster
- Model size: substantially smaller (important for Specialist Bank and air-gapped deployment)

**System-Level Effects**
- Makes higher mode counts and 3D problems tractable under fixed validator budgets
- Improves the quality–cost frontier of models that can be produced and deployed
- Can be exposed as a controllable parameter in `strategy.json`, turning efficiency into a searchable dimension

**Risk**  
Excessively low rank can degrade high-frequency accuracy. This is mitigated by making rank a miner-controlled parameter and by retaining full physics-gate evaluation for any model that receives significant emissions or enters the Specialist Bank.

### 3.2 Continuous / Mode-Wise Kernel Parameterization

**Mechanism**  
A small hypernetwork (commonly SIREN-style) generates kernel weights as a continuous function of frequency rather than storing an independent tensor per mode.

**Realistic Performance Impact**
- Strong parameter efficiency
- Improved resolution generalization
- Modest direct wall-clock speedup, but enables higher effective mode counts for a given parameter budget

**System-Level Effects**
- Pairs naturally with multi-fidelity curricula: the same continuous kernel can be queried at different mode budgets without re-initialization
- Improves transfer across resolutions, supporting the 2D → 3D curriculum later in the roadmap

### 3.3 Fused FFT + Complex GEMM / Custom Triton Kernels

**Mechanism**  
Replace separate library calls (cuFFT + cuBLAS or equivalents) with fused kernels that keep intermediate data in registers or shared memory.

**Realistic Performance Impact**
- Spectral convolution alone: 1.5–2.5× in well-tuned cases
- End-to-end step: typically 1.2–1.7×
- Larger relative gains at high resolution and high mode count

**System-Level Effects**
- Pure validator-side efficiency win when implemented as an optimized backend
- Does not change model expressivity — only the cost of evaluation
- Highest value under heavy concurrent submission load

**Limitation**  
Benefits shrink when spectral convolution is no longer the dominant cost (e.g., residual-heavy or graph-heavy workloads).

### 3.4 Adaptive / Learned Mode Selection

**Mechanism**  
Allocate capacity across frequencies statically or dynamically instead of treating all modes equally.

**Realistic Performance Impact**
- Early training phases can operate with substantially fewer modes
- Combined with spatial multi-fidelity curricula, total training FLOPs can be reduced by 2–4× while recovering final accuracy

**System-Level Effects**
- One of the highest-leverage algorithmic levers available to miners
- Directly reduces average validator cost when used well
- Creates an additional discovery surface for the Landscape Agent

### 3.5 Additional Kernel Directions

| Direction | Potential | Notes |
|-----------|-----------|-------|
| Hierarchical / multi-resolution kernels | Medium–High | Aligns with multi-fidelity training; higher implementation complexity |
| Graph kernel optimizations (GINO) | Medium | Important once graph operators become common |
| Attention kernel optimizations (Transolver-style) | Medium–High | Leverages existing FlashAttention-style progress |
| Memory-layout and fusion beyond spectral layers | Medium | Incremental but compounding |

---

## 4. Algorithmic and Strategy-Level Levers

These strategies can be expressed in `strategy.json` and are therefore discoverable by the network itself.

| Strategy | Typical FLOPs Reduction | Quality Impact | Notes |
|----------|--------------------------|----------------|-------|
| Multi-fidelity spatial + mode curriculum | 2–5× | Neutral to positive when well-designed | Already partially supported in the architecture |
| Velocity-based early stopping + hard budgets | 1.5–3× | Neutral if properly gated | Strongly recommended on the validator side |
| Low-rank adapters (LoRA) on strong priors | Large wall-clock reduction | High when priors are strong | Phase 2A+ capability |
| Physics-parameter + resolution co-curriculum | 1.5–3× | Often positive | Under-explored discovery surface |
| Progressive residual point sampling | 1.3–2× | Neutral to positive | Reduces residual evaluation cost |
| **Gradient accumulation + checkpointing (Phase 3-4)** | **30-50% VRAM reduction** | Neutral | **Essential for Phase 3-4** |

**Key Observation**  
In practice, the combination of multi-fidelity curricula, early stopping, and low-rank kernels consistently outperforms pure kernel optimization in isolation. Kernel improvements amplify good algorithmic strategies; they do not replace them.

---

## 5. System-Level Mechanisms for Compute Management

Beyond per-step efficiency, Carbon can control *which* submissions consume expensive evaluation resources.

### 5.1 Reputation- and Stake-Weighted Evaluation Depth

New or low-reputation submissions receive a lighter evaluation (reduced stress-set size, coarser multi-fidelity schedule). High-reputation or high-stake submissions receive the full adversarial suite. Record-setting models can be given an even deeper championship evaluation.

This concentrates expensive compute on the strategies that actually drive emissions and Specialist Bank quality while still providing statistically meaningful signal to all participants.

### 5.2 Progressive / Multi-Stage Official Evaluation

A fast Tier-1 filter (coarse resolution, reduced stress set, basic gates) rejects the majority of weak submissions cheaply. Only the upper portion of the distribution proceeds to full Tier-2 evaluation. This is already partially present in the design and should be formalized as a first-class mechanism.

### 5.3 Sponsored Evaluation Capacity

Sponsors of Challenges (particularly Tier 3 and Tier 4) can purchase additional evaluation capacity or priority lanes. This creates a direct economic link between those who benefit from deeper verification and those who fund it, turning compute cost from a pure subnet expense into a scalable commercial input.

### 5.4 Hard Per-Challenge and Per-Hotkey Budgets

Each challenge carries a total GPU-second budget per tempo. Individual hotkeys have submission quotas. These controls prevent any single challenge or miner from starving the network and force prioritization toward higher-value work.

### 5.4 Pre-qualification via Estimation / Light Training

Priority (or a soft requirement) can be given to submissions that have already demonstrated promise under Estimation Mode or Light Training. This filters pure speculative submissions before they enter the expensive full-evaluation queue, while reinforcing the low-friction iteration loop the subnet wants miners and agents to use.

### 5.5 Validator Queue Management & Prioritization

See `JAX_Optimization.md` for the production queue implementation. Priority order: sponsored tiers → high reputation → standard → estimation mode.

---

## 6. Full-System Interactions and Second-Order Effects

### Validator Economics and Search Capacity
Efficient kernels and algorithmic strategies increase the number of strategies that can be rigorously evaluated under a fixed GPU budget. This directly expands the parallel search capacity of the subnet — the central structural advantage of the decentralized design.

### Miner Incentives and Discovery Surface
When efficiency knobs (rank, mode budget, resolution schedule, etc.) are first-class citizens in `strategy.json`, miners and autonomous agents search the joint space of architecture, training strategy, *and* efficiency. This expands the discovery surface beyond loss weights and learning-rate schedules alone.

### Specialist Bank and Commercial Value
Smaller, faster, higher-quality specialists are more deployable, especially in air-gapped and edge environments. Efficiency gains also make higher-fidelity challenges economically viable earlier in the roadmap. Sponsored Challenges become more attractive because the cost of producing a verified specialist declines.

### Risk Surface and Credibility
Efficiency mechanisms must not create paths for physically invalid models to reach high emissions or the Specialist Bank. Full physics gates and adversarial evaluation remain mandatory for any model that receives significant weight or commercial packaging. Custom kernels must preserve the determinism and reproducibility guarantees that underpin trustless verification.

---

## 7. Priority Matrix (Updated)

| Strategy | Impact | Difficulty | Primary Side | Priority |
|----------|--------|------------|--------------|----------|
| Multi-fidelity spatial + mode curriculum | Very High | Low–Medium | Both | Highest |
| Low-rank / factorized spectral kernels | High | Medium | Both | High |
| Velocity-based early stopping + hard budgets | High | Low | Validator | High |
| Adaptive mode schedules | High | Medium | Miner-expressible | High |
| Reputation- / stake-weighted evaluation depth | High | Medium | System | High |
| Progressive multi-stage evaluation | High | Medium | System | High |
| **Gradient accumulation + checkpointing (Phase 3-4)** | **Very High** | **Medium** | **Both** | **Highest (Ph 3+)** |
| Fused Triton spectral kernels | Medium–High | Medium | Validator | Medium–High |
| Continuous (SIREN-style) kernels | Medium–High | Medium–High | Both | Medium |
| Sponsored evaluation capacity | Medium–High | Low–Medium | System / Commercial | Medium–High |
| Hierarchical multi-resolution kernels | Medium–High | High | Both | Medium (later) |
| Full general kernel library (all backbones) | Medium | High | Validator | Lower (later) |

---

## 8. Recommended Strategic Posture (Updated)

Carbon should treat compute efficiency as a searchable dimension of the problem the network is solving, not merely as a one-time systems optimization.

**Core principles:**

1. Expose efficiency knobs (rank, mode budget, resolution schedule, gradient accumulation steps, checkpointing) in `strategy.json` so the network can discover effective combinations.
2. Implement targeted, high-ROI kernel improvements on the validator side to lower the cost of evaluating those strategies.
3. Maintain strong physics gates and progressive evaluation so that efficiency gains cannot be used to bypass physical validity.
4. Allow the Landscape Agent to learn which efficiency choices causally improve robustness and generalization, not merely training speed.
5. Align commercial mechanisms (sponsored evaluation capacity) with the actual cost of rigorous verification.
6. **Hardware-aware phase budgeting**: Phase 3-4 budgets include 2-3× safety margins for coupling overhead and multi-GPU scaling inefficiency.

This posture expands parallel search capacity, improves the quality–cost frontier of the Specialist Bank, and strengthens the economic sustainability of the subnet as problem complexity grows — without compromising the scientific rigor that underpins Carbon's credibility.

---

## 9. Relationship to Other Documents

- `appendices/JAX_Optimization.md` — Detailed implementation designs for unified loss masking, early-stopping via `lax.scan`, bfloat16 policy, multi-fidelity resolution handling, gradient accumulation, gradient checkpointing.
- Main `SPEC.md` — Phase roadmap, physics gates, scoring, and trustless verification requirements that any efficiency mechanism must respect.
- `TRUSTLESS_VERIFICATION_AND_DATA_GENERATION.md` — Constraints on reproducibility and auditability that custom kernels and evaluation-depth policies must satisfy.

---

*This document is intended as a living technical analysis. Cost models, kernel performance numbers, and priority rankings should be updated as empirical measurements from the running subnet become available.*
