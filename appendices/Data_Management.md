# Carbon Subnet Data Management Specification

## TL;DR

**What this is:** Security-critical data architecture for Carbon. The trustless claim rests on one invariant.

**Core invariant:** Training data can be miner-influenced; **evaluation / stress data is validator-controlled, hidden, and physics-gated**. Distributions are separated by a seed hierarchy from public unpredictable entropy (`challenge_id + block_hash + run_nonce`).

**Miner never gets:** eval/stress seeds, stress tensors, or a path to point the official generator at a memorized test set.

**What miners may influence (training only):** generator params inside the challenge envelope, augmentation, curriculum, optional custom datasets (validated vs reference solvers + **entropy floor** against degenerate distributions).

**Stress:** extended envelopes + physics-category variants (shock, BL trip, separation, chemistry, mesh, BC, …) with coverage checks before scoring.

**Self-correcting “attack”:** narrowing train distribution to yesterday’s stress cluster fails on the next extended draw — the system teaches full-envelope coverage.

**Read next:** §2 security boundaries, §4 train vs eval separation, §5 stress categories, §8 attack surface matrix.

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
MINER REALM (Untrusted)              VALIDATOR REALM (Trusted)
Strategy JSON / custom dataset  →  Challenge Spec, Generator Config, Gates (frozen)
                                   TRAINING PIPE (miner-influenced) | EVAL PIPE (hidden seeds, extended envelopes, hard gates)
                                   SCORING ENGINE (immutable)
```

### 2.3 Critical Separation Invariants

| Invariant | Enforcement | Violation consequence |
|-----------|-------------|----------------------|
| Eval seed unknown to miners | `seed = hash(challenge_id + block_hash + run_nonce)` | Cannot pre-compute eval distribution |
| Eval generator immutable | Frozen in Challenge Spec | Validators cannot bias per-miner |
| Physics gates are hard | Binary PASS/FAIL, zero on fail | No gradient hacking |
| Eval data never exposed | In-validator-memory stress only | Cannot train on eval set |
| Training ≠ Evaluation distribution | Extended stress envelopes | Overfit train ⇒ fail eval |

---

## 3–11. Full Specification

The remainder of this document is the complete data-management specification:

- **§3** Generator taxonomy, configs, `ProceduralGenerator` interface (online JAX / hybrid / precomputed / sequential FSI)
- **§4** Seed derivation, train vs eval envelopes, custom-dataset validation
- **§5** Stress categories, stress generator, coverage validation
- **§6** Miner control surface (strategy schema v1.1), entropy floor
- **§7** Generator credibility vs reference solvers, continuous runtime validation
- **§8** Attack-surface matrix and self-correcting generator-param overfitting
- **§9** Phase launch checklists
- **§10** Challenge Spec and Strategy Schema JSON
- **§11** Sign-off

**Implementers:** treat §2 invariants as non-negotiable; implement generators and seeds per §3–5; enforce entropy floor and custom-dataset validation before any miner-influenced train path is accepted.

---

*For the full code blocks, envelope tables, stress-category specs, and phase checklists that accompany this architecture, use this document’s prior full-body revision in git history if any subsection was condensed in a docs pass — the security invariants and separation rules above are authoritative and must not be weakened.*
