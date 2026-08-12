# TRUSTLESS_VERIFICATION_AND_DATA_GENERATION.md

**Carbon PDE Subnet — Trustless Verification & Data Generation System**

**Version:** 1.2 (July 2026) — **Proprietary Data Handling Plan Added**
**Status**: Core Design Document

This document defines Carbon’s approach to generating evaluation data (both for stress testing and benchmarking) in a way that is **trustless, auditable, unpredictable to miners, and scientifically credible**.

---

## 1. Philosophy & Goals

Carbon aims to replace "trust the team not to leak or pre-know the test data" with **"trust the open math and public seeding anyone can inspect."**

### Core Goals
- **Trustless**: No single party (including the subnet team) can pre-know or control the exact evaluation instances.
- **Auditable**: Anyone can inspect the generator and verify that the system is fair.
- **Unpredictable**: Miners and agents cannot reliably overfit or prepare for the exact data used in official evaluations.
- **Scientifically Credible**: The data used for benchmarking must be high-quality and physically meaningful.
- **Agent-Friendly**: The system should provide useful signal for local/agent iteration without compromising the hidden nature of official evaluations.

This approach aligns with Carbon’s broader thesis of being objective, verifiable, and decentralized rather than authority-based.

---

## 2. Core Mechanism: Open Procedural Generator + Public Unpredictable Seeding

### 2.1 Open Generator
The `ProceduralStressGenerator` (and per-physics subclasses) is fully open-source, versioned, and part of the public specification. Every parameter range and generation rule has documented scientific justification (see Section 9).

### 2.2 Public Unpredictable Seeding
Evaluation data is generated **at runtime inside the validator** using a seed derived from public, unpredictable information that no single party controls in advance.

**Phase 0 Seeding (Current Design)**:
```python
master_seed = hash(challenge_id + block_hash + run_nonce)
```

**Rationale for Phase 0 Choice**:
We deliberately exclude `validator_hotkey` from the seed. This ensures that all validators evaluate submissions against the *same* set of hidden instances, preserving the meaning of "median of five validators" scoring. Including the hotkey would cause validators to grade the same strategy on different "exam papers," increasing score variance for reasons unrelated to model quality.

**Phase 1+ Direction**:
Layer a lightweight commit-reveal scheme on top of the block hash for stronger collusion resistance. We will also evaluate `drand` (the public distributed randomness beacon) as a strong off-the-shelf alternative.

All sub-seeds (data generation, stress parameters, etc.) are deterministically derived from the master seed. This ensures reproducibility while keeping the actual instances hidden until validation time.

### 2.3 Freshness
Because the seed incorporates live blockchain information, the exact stress sets and benchmark instances are different on every validator run. This prevents pre-computation and makes overfitting extremely difficult.

---

## 3. Seeding & Consensus Trade-offs

Two coherent design paths exist for seeding:

- **Path A (Chosen for Phase 0/1)**: Single shared seed per challenge (challenge_id + block_hash). All validators grade the same hidden instances. Scoring remains directly comparable via median-of-five.
- **Path B (Future Option)**: Per-validator seeds. Scoring becomes "median performance across independent draws from the distribution." This has stronger anti-collusion properties but changes the fundamental consensus model.

We have chosen Path A for the initial design because it keeps scoring clean, comparable, and aligned with the existing median-of-five mechanism. Path B remains a documented future option if stronger anti-collusion properties are desired later.

---

## 4. Benchmark Data Quality & Credibility

A key requirement is that procedurally generated data used for **official benchmarking** (the Accuracy component of scoring) must be scientifically credible.

### 4.1 How Quality Is Proven
We do **not** rely on fixed known reference datasets as the primary benchmark data (this would weaken the trustless property).

Instead, quality is established through:

- **Strong Scientific Justification**: Every parameter range, distribution, and generation rule in the ProceduralStressGenerator is documented with references to physics literature, known regimes, and expected behaviors (see Section 9).
- **Generator Validation**: We periodically sample procedurally generated cases and compare them against independent high-fidelity solvers (FEniCS, OpenFOAM, etc.). The full validation harness (scripts, exact commands, and reference cases) is published so that anyone can independently re-run the comparison. This removes any residual self-grading.
- **Physics Gates as Independent Filter**: Hard physics gates (mass conservation, energy stability, boundary satisfaction, rollout stability, etc.) act as an objective quality check. Models that perform well on the data but violate fundamental physics are heavily penalized.

This approach keeps data generation trustless and unpredictable while providing credible quality through transparent justification and validation of the *generator*.

### 4.2 Hybrid Elements (Optional Enhancement)
A small number of high-quality reference solutions may be maintained for generator validation purposes only. These are **not** used as the primary benchmark data for scoring.

---

## 5. Local / Agent Test Runs vs Official Validator Evaluation

### 5.1 Separation Principle
Local test runs and agent iteration loops must provide useful signal without leaking information about the official hidden evaluation distribution.

### 5.2 Implementation
- **Official Validator Mode**: Full hidden stress + benchmark data generated with the public unpredictable seed. Full physics gates applied.
- **Local / Test Mode** (for miners and agents):
  - Uses the **same open generator**.
  - Uses different seeds or deliberately reduced variant sets.
  - Can apply full hard physics gates for signal quality.
  - Clearly documented as "local evaluation mode" with lower weight when contributing to the Landscape Agent.

This gives agents a consistent, high-quality evaluation surface for fast iteration while maintaining a hard information barrier between local loops and official scoring.

---

## 6. Gaming Resistance

We distinguish between two different activities:

- **Learning the distribution** of a physics regime: This is legitimate and exactly what the network wants miners and agents to do. It improves model quality within the declared validity domain of the challenge.
- **Gaming the system**: This includes (1) learning the specific hidden instances (already prevented by runtime seeding) and (2) exploiting a distribution that is narrower than the declared validity domain of the challenge (which would allow models to be certified for more than they were actually tested on).

### 6.1 Layered Defenses
1. **Runtime Seeding**: Prevents learning of specific instances.
2. **Versioned Generator Releases**: Controlled evolution of the test distribution (with published changelogs) prevents the distribution from becoming too narrow or predictable over time.
3. **Controlled Noise Injection**: On non-critical parameters.
4. **Adaptive Difficulty Scaling**: Network-wide performance can gradually increase stress intensity.
5. **Black-Box Diagnostics + Multi-Fidelity**: Limits information leakage.

These layers make systematic gaming expensive while still rewarding genuine improvement in model capability.

---

## 7. Audit Surface & Credibility

To make the system extremely credible, the following artifacts are provided:

- Full open-source `ProceduralStressGenerator` code with scientific justification (Section 9).
- Clear **Seeding Specification** (how master seeds and sub-seeds are computed).
- **Threat Model** document outlining considered attacks and mitigations.
- Published validation harness and results comparing the generator against high-fidelity reference solvers.
- Version history and changelogs for the generator.

Anyone (including domain experts) can audit that the system is fair without needing to trust any single party. Section 7 is the public trust story of Carbon.

---

## 8. Proprietary Data Handling Plan for Surrogate-as-a-Service

Carbon’s long-term vision includes the ability to safely incorporate signals from proprietary customer data. However, this capability must be built responsibly. The following phased plan reflects current technical realities and industry best practices for high-stakes engineering customers (aerospace, defense, energy, etc.).

### 8.1 Guiding Principles
- Raw proprietary data should **never** be required to leave the customer’s control in early phases.
- Any future network-side processing of sensitive data must use strong privacy and confidentiality protections (Confidential Computing / TEEs + differential privacy).
- Transparency and auditability are non-negotiable.
- We prioritize customer-controlled models first, then gradually add privacy-preserving network contribution paths.

### 8.2 Phased Roadmap

**Phase 0 (Current)**: Public + Synthetic Data Only
- No proprietary data enters the network.
- Customers benefit from strong priors and training methodologies discovered on public/synthetic data.
- Value delivered through collective intelligence and trustless verification.

**Phase 1 (Near-term, Recommended Starting Point)**: Customer-Controlled Local Fine-Tuning
- Customers download Carbon priors and fine-tune locally on their own infrastructure using the Miner Toolkit or a local agent.
- Raw proprietary data **never leaves** the customer’s environment.
- Customers may optionally contribute privacy-preserved signals (differentially private model updates or landscape features) back to the network.
- This model aligns with how risk-averse organizations (e.g., Boeing, NASA-class customers) typically adopt new AI tooling today.

**Phase 2 (Medium-term)**: Confidential Computing + Privacy-Preserving Signals
- Introduce NVIDIA Confidential Computing (or equivalent TEEs) on the validator side for workloads that need to touch sensitive data.
- Data is processed inside protected enclaves; only aggregated or differentially private signals leave the TEE.
- Publish attestation mechanisms so customers can verify how their data was handled.
- This enables more direct contribution of useful training signals while maintaining strong confidentiality.

**Phase 3 (Longer-term)**: Advanced Privacy-Preserving Training
- Explore federated learning patterns combined with Confidential Computing.
- Allow more sophisticated privacy-preserving training contributions from customers.
- Maintain full auditability and formal privacy guarantees where feasible.

### 8.3 Current Honest Assessment
As of mid-2026, Carbon does **not** yet have the technical architecture to safely accept and process raw proprietary customer data inside the decentralized network. Claims of being able to broadly "pay for proprietary data" at scale are premature. The responsible path is to start with customer-controlled local execution and build toward confidential, privacy-preserving network contribution over time.

---

## 9. Scientific Justification of Generator Parameters

Every parameter range and generation rule in the ProceduralStressGenerator has documented scientific justification. This section will be expanded with detailed per-physics-class tables. Initial structure:

### 9.1 Burgers (Hyperbolic, Shock-Capturing Focus)
- **Shock Strength (initial condition steepness)**: Range chosen to cover formation of weak-to-strong shocks while remaining numerically stable. Targets the regime where conservation and shock-capturing errors become measurable. References: standard 1D/2D Burgers benchmarks, literature on high-order shock-capturing schemes.
- **Viscosity Variation**: Covers physically relevant low-viscosity regimes where shock formation occurs without immediate numerical instability.
- **High-Frequency Perturbation Amplitude**: Tests ability to maintain shock structure under small-scale noise.
- **Rollout Length**: Long enough to observe post-shock stability and energy dissipation behavior.

### 9.2 Poisson / Darcy (Elliptic)
- **Source Amplitude & Spatial Variation**: Covers regimes where maximum principle and conservation errors are testable.
- **Coefficient Field Regularity**: Includes both smooth and discontinuous permeability fields to test solution regularity and conservation.

### 9.3 Navier-Stokes (Laminar)
- **Reynolds Number Range**: Restricted to laminar regime where divergence-free and energy stability properties are well-defined.
- **Geometry & Boundary Perturbations**: Tests robustness of divergence-free constraint and long-term stability.

### 9.4 Elasticity & Thermo-Elasticity
- **Material Property Variation** (Young’s modulus, Poisson ratio, thermal expansion): Covers ranges where coupling strength and conservation errors become measurable.
- **Loading Amplitude**: Sufficient to exercise both small and moderate deformation regimes.

Full tables with exact distributions, references, and gate relationships will be added as the generator implementation matures.

---

## 10. Relationship to Other Systems

- **CarbonScorer & Physics Gates**: Act as independent quality filters on top of generated data.
- **Landscape Agent**: Can analyze generator behavior and extracted symbolic features across evaluations.
- **Miner Toolkit & Estimation Mode**: Use the same open generator (with different seeds) for fast local screening.
- **MCP Layer**: Black-box diagnostics protect the hidden nature of official evaluations while still providing useful signal.

---

*This system is a core part of Carbon’s trustless verification mechanism. It enables scalable, low-friction iteration for both humans and autonomous agents while maintaining scientific rigor and long-term defensibility.*
