# Carbon Subnet Data Management Specification

## TL;DR

**Job:** Keep train and eval cryptographically separated so the subnet’s trustless claim holds.

**Invariant (do not violate):** miners may influence *training* data inside the challenge envelope; **eval/stress data is validator-only**, generated from `hash(challenge_id ‖ block_hash ‖ run_nonce)`, never returned to miners.

**What to implement first**
1. Seed hierarchy + role split (`train` / `eval` / `stress`)
2. Frozen challenge generator configs (miners cannot edit eval generators)
3. Extended stress envelopes + category coverage checks before scoring
4. Entropy floor on miner `generator_params` (anti-degenerate distributions)
5. Custom-dataset path: ref-solver + physics validation before any train merge

**What miners control (train only):** distribution params in envelope, augmentation, curriculum, optional custom data.  
**What they never control:** stress seeds, stress tensors, gate thresholds, eval generator config.

**Only realistic train-side attack** is narrowing the train distribution to yesterday’s stress cluster — it **self-corrects** on the next extended draw. Treat that as a feature: force full-envelope coverage.

**Phase-0 checklist:** 7 generators, seed derivation, stress categories, gate path, determinism harness, Model Cards.

**Read deeper:** §2 invariants → §4 train/eval separation → §5 stress → §6 entropy floor → §8 attack matrix.

---

**Version**: 1.0  
**Status**: Implementation Specification  
**Classification**: Core Protocol — Security Critical  

---

## 1. Executive Summary

This document specifies Carbon's complete data management architecture. The central security invariant is **strict separation between training data (miner-influenced) and evaluation data (validator-controlled, hidden, physics-gated)**. This separation is the foundation of Carbon's trustless verification claim.

**Security Invariant**: *Miners optimize for training distribution. Validators evaluate on hidden, procedurally generated distribution with hard physics gates. These distributions are cryptographically separated by block-hash seeding.*

---

## 2. Core Security Architecture

### 2.1 Threat Model

| Adversary | Capability | Goal |
|-----------|------------|------|
| **Malicious Miner** | Controls training data distribution, submits custom datasets, chooses strategy | Pass evaluation without genuine physics compliance |
| **Colluding Validators** | Control evaluation seed, stress generation | Favor specific miners |
| **External Attacker** | Manipulates reference data, precomputed cache | Poison ground truth |

### 2.2 Security Boundaries

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        TRUST BOUNDARIES                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  MINER REALM (Untrusted)              VALIDATOR REALM (Trusted)         │
│  ┌─────────────────────────┐          ┌─────────────────────────────┐  │
│  │ Strategy JSON           │          │ Challenge Spec (Immutable)  │  │
│  │ • data_generation params│          │ Generator Config (Frozen)   │  │
│  │ • custom_dataset ref    │          │ Gate Thresholds (Frozen)    │  │
│  │ • custom_dataset URI    │          │ Gate Logic (Immutable)      │  │
│  └───────────┬─────────────┘          └──────────────┬──────────────┘  │
│               │                                       │                │
│               │ Strategy JSON (v1.1)                  │                │
│               ▼                                       ▼                │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │              VALIDATOR EXECUTION ENVIRONMENT                     │  │
│  │  ┌─────────────────┐  ┌─────────────────────────────────────┐  │  │
│  │  │ TRAINING PIPE   │  │ EVALUATION PIPE (SEPARATE PROCESS)  │  │  │
│  │  │ • Miner params  │  │ • Validator-controlled generator    │  │  │
│  │  │ • Custom dataset│  │ • Hidden seed (block hash)          │  │
│  │  │ • Miner augment │  │ • Extended envelopes                │  │
│  │  │ • Miner curriculum    │ • Hard physics gates              │  │
│  │  └────────┬────────┘  └──────────────────┬──────────────────┘  │  │
│  │           │                                │                  │  │
│  │           ▼                                ▼                  │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │           SCORING ENGINE (Immutable)                     │  │  │
│  │  │  Physics Gates (Hard) → Score → Emissions               │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Critical Separation Invariants

| Invariant | Enforcement Mechanism | Violation Consequence |
|-----------|----------------------|----------------------|
| **Eval seed unknown to miners** | `seed = hash(challenge_id + block_hash + run_nonce)` | Miners cannot pre-compute eval distribution |
| **Eval generator immutable** | Generator config frozen in Challenge Spec (on-chain) | Validators cannot bias eval for specific miners |
| **Physics gates are hard** | Binary PASS/FAIL, zero score on failure | No gradient hacking possible |
| **Eval data never exposed** | Stress variants generated in-validator-memory only | Miners cannot train on eval distribution |
| **Training ≠ Evaluation distribution** | Extended envelopes for stress variants | Overfitting to training = failing eval |

---

## 3–11. Full Specification Body

The complete data-management specification (generator taxonomy and interfaces, seed derivation, train vs eval envelopes, custom-dataset validation, stress categories and coverage, miner control surface + entropy floor, generator credibility vs reference solvers, attack-surface matrix, phase checklists, Challenge Spec / Strategy Schema JSON, and sign-off) is restored from the security-critical v1.0 design.

**Implementers:** treat §2 invariants as non-negotiable. Full code listings for generators, seeding, stress specs, entropy floor, and schemas live at blob `ab247d17` (commit `00eb0a34`) and are the coding source of truth for Phase 0.

Key operational rules from that body:

- **Training vs eval:** different seed derivation paths; eval uses extended envelopes and validator-only generators
- **Entropy floor:** reject degenerate miner generator distributions at submission time
- **Custom datasets:** ref-solver + physics validation before train merge
- **Stress coverage:** require ≥95% category coverage before scoring
- **Self-correcting attack:** narrow train dist → fail next extended stress draw → expand envelope

---

## Phase Launch Checklists (Condensed)

**Phase 0:** 7 PDE generators · FEniCS harness · seed hierarchy · stress categories · gates · Model Cards · determinism harness  
**Phase 1A:** compressible NS generators · SU2/OpenFOAM · shock capture · adjoint gate  
**Phase 1B:** reacting/FSI/6-DOF/CHT · chemistry UQ · sequential FSI  
**Phase 2A:** schema v1.1 · entropy floor in SDK · MT bridge · DML · Specialist Bank  
**Phase 2B:** air-gap toolkit · preCICE · sequential multiphysics ladder

---

*Classification: Core Protocol — Security Critical. Do not weaken train/eval separation or expose stress seeds to miners.*
