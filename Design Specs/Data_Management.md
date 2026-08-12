# Carbon Subnet Data Management Specification

## TL;DR

**Job:** Keep train and eval cryptographically separated so the subnet’s trustless claim holds.

**Invariant (do not violate):** miners may influence *training* data inside the challenge envelope; **eval/stress data is validator-only**, generated from `hash(challenge_id ‖ block_hash ‖ run_nonce)`, never returned to miners.

**Dual path (coherency with productization)**

| Path | Data role | Seed policy |
|------|-----------|-------------|
| **Lean eval** (emissions) | train / eval / stress | Standard hierarchy; stress hidden |
| **Specialist Bank / product battery** | retrain + PB draws | **Separate** seed material from the lean cards that justified the opportunity (decontamination) |

**What to implement first**
1. Seed hierarchy + role split (`train` / `eval` / `stress`)
2. Frozen challenge generator configs (miners cannot edit eval generators)
3. Extended stress envelopes + category coverage checks before scoring
4. Entropy floor on miner `generator_params` (anti-degenerate distributions)
5. Custom-dataset path: ref-solver + physics validation before any train merge
6. Bank/PB seed separation when promotion path is live

**What miners control (train only):** distribution params in envelope, augmentation, curriculum, optional custom data.  
**What they never control:** stress seeds, stress tensors, gate thresholds, eval generator config, PB seeds.

**Only realistic train-side attack** is narrowing the train distribution to yesterday’s stress cluster — it **self-corrects** on the next extended draw.

**Phase-0 checklist:** 7 generators, seed derivation, stress categories, gate path, determinism harness, Model Cards.

**Read deeper:** §2 invariants → §4 train/eval separation → §5 stress → §6 entropy floor → §8 attack matrix → §12 bank/PB seeds.

---

**Version**: 1.1  
**Status**: Implementation Specification  
**Classification**: Core Protocol — Security Critical  
**Related:** `SPEC.md`, `Specialist_Bank.md`, `Landscape_Agent.md`

---

## 1. Executive Summary

This document specifies Carbon's complete data management architecture. The central security invariant is **strict separation between training data (miner-influenced) and evaluation data (validator-controlled, hidden, physics-gated)**. This separation is the foundation of Carbon's trustless verification claim.

**Security Invariant**: *Miners optimize for training distribution. Validators evaluate on hidden, procedurally generated distribution with hard physics gates. These distributions are cryptographically separated by block-hash seeding.*

Productization adds a second decontamination rule: **opportunity-justifying lean eval seeds must not be reused as bank verify or product-battery seeds** when feasible (`Specialist_Bank.md`).

---

## 2. Core Security Architecture

### 2.1 Threat Model

| Adversary | Capability | Goal |
|-----------|------------|------|
| **Malicious Miner** | Controls training data distribution, submits custom datasets, chooses strategy | Pass evaluation without genuine physics compliance |
| **Colluding Validators** | Control evaluation seed, stress generation | Favor specific miners |
| **External Attacker** | Manipulates reference data, precomputed cache | Poison ground truth |
| **Productization shortcut** | Reuse lean stress draws as “PB pass” evidence | Launder leaderboard into commercial SKU |

### 2.2 Security Boundaries

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        TRUST BOUNDARIES                                  │
├─────────────────────────────────────────────────────────────────────────┤
│  MINER REALM (Untrusted)              VALIDATOR REALM (Trusted)         │
│  Strategy JSON / train params         Challenge Spec (Immutable)        │
│                                       Generator Config (Frozen)         │
│                                       Gate Thresholds (Frozen)          │
│                                       Lean eval + stress (hidden seeds) │
│                                       Bank/PB draws (separate seeds)    │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Critical Separation Invariants

| Invariant | Enforcement Mechanism | Violation Consequence |
|-----------|----------------------|----------------------|
| **Eval seed unknown to miners** | `seed = hash(challenge_id + block_hash + run_nonce)` | Miners cannot pre-compute eval distribution |
| **Eval generator immutable** | Generator config frozen in Challenge Spec | Validators cannot bias eval for specific miners |
| **Physics gates are hard** | Binary PASS/FAIL, zero score on failure | No gradient hacking on lean path |
| **Eval data never exposed** | Stress variants generated in-validator-memory only | Miners cannot train on eval distribution |
| **Training ≠ Evaluation distribution** | Extended envelopes for stress variants | Overfitting to training = failing eval |
| **Bank/PB ≠ lean justifying draws** | Separate seed material / nonce family for promotion | No leaderboard laundering into SKUs |

---

## 3–11. Full Specification Body

The complete data-management specification (generator taxonomy, seed derivation, train vs eval envelopes, custom-dataset validation, stress categories and coverage, miner control surface + entropy floor, generator credibility vs reference solvers, attack-surface matrix, phase checklists, Challenge Spec / Strategy Schema JSON) remains the security-critical v1.0 design body.

**Implementers:** treat §2 invariants as non-negotiable. Full code listings for generators, seeding, stress specs, entropy floor, and schemas live at blob `ab247d17` (commit `00eb0a34`) and are the coding source of truth for Phase 0.

Key operational rules:

- **Training vs eval:** different seed derivation paths; eval uses extended envelopes and validator-only generators
- **Entropy floor:** reject degenerate miner generator distributions at submission time
- **Custom datasets:** ref-solver + physics validation before train merge
- **Stress coverage:** require ≥95% category coverage before scoring
- **Self-correcting attack:** narrow train dist → fail next extended stress draw → expand envelope

---

## 12. Bank / Product-Battery Seed Policy (v1.1)

When the Specialist Bank promotion path is live:

```text
opportunity_support_seeds  (lean cards that ranked the regime)
        ≠
bank_verify_seeds          (controlled retrain + lean re-gate)
        ≠
pb_suite_seeds             (INV / ROLL / ADV draws)   # where feasible
```

| Rule | Detail |
|------|--------|
| Document on bank Model Card | `seed_family`, `data_cutoff_block`, `landscape_version` |
| Same generator **code** | Allowed and preferred (auditable) |
| Same **draw instances** as justifying cards | Forbidden for PB pass claims |
| Miner visibility | PB seeds never published on Port A |

This is decontamination for productization — not a change to lean train≠eval.

---

## Phase Launch Checklists (Condensed)

**Phase 0:** 7 PDE generators · FEniCS/DE.jl harness · seed hierarchy · stress categories · lean gates · Model Cards · determinism harness  
**Phase 1A:** compressible NS generators · SU2/OpenFOAM · shock capture · adjoint gate  
**Phase 1B:** reacting/FSI/6-DOF/CHT · chemistry UQ · sequential FSI  
**Phase 2A:** schema v1.1 · entropy floor in SDK · MT bridge · DML · Specialist Bank **queue + PB seed families**  
**Phase 2B:** air-gap toolkit · preCICE · sequential multiphysics ladder  

---

*Classification: Core Protocol — Security Critical. Do not weaken train/eval separation, expose stress seeds to miners, or reuse lean justifying draws as product-battery evidence.*
