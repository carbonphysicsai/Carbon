# Scoring.md — Lean Emission Scoring & Challenge Score Bank

**Carbon Subnet**  
**Version:** 2.1 (August 2026)  
**Status:** Protocol Appendix — Security & Incentive Critical  
**Audience:** Simulation Engineers, Physics PhDs, Protocol Engineers, Auditors  
**Related:** `SPEC.md` §8, `Data_Management.md`, `POC_Burgers_FNO.md`, `Miner_MCP.md`, `Build_Out.md`, `Specialist_Bank.md`, `Landscape_Agent.md`

---

## Executive Summary

This document defines the **exact mathematical specification** for converting a trained neural operator surrogate into a lean emission score. The scoring function is **challenge-specific, versioned, auditable, and trustless** — designed so that the *best physics surrogates earn the most emissions*, where "best" means: **large safety margins on physics laws, worst-case robustness across all operational regimes, and genuine out-of-distribution generalization**.

**Design Philosophy:** The scoring function is the *incentive engine* of the subnet. It must translate **engineering value** (inverse design capability, plant-model fidelity, worst-case robustness) into **differentiable emission incentives**. Every component is derived from first principles of computational physics, uncertainty quantification, and reliability engineering — not heuristic tuning.

**Forbidden score inputs (normative):** The lean emission score must **not** depend on prior similarity, miner `estimate` / `light_compare` outputs, exam fee amount, or any free-path mock metrics. Only validator exam metrics under the active Score Pack (gates + component legs) enter `S_combined`. See `Miner_MCP.md` trust boundary and `Build_Out.md` C5.

**Model Card vs EvaluationCard:** The scoring engine and validator write a full **Model Card** / internal result (gates, margins, pack hash, generator version, seed *roles* — not leaked to miners as draw ids). The miner-visible **EvaluationCard** (`Miner_MCP.get_submission_result`) is a **budgeted projection** of that record (Phase 0: overall + coarse components + gate pass/fail + failure tags; no fine margins / per-stress breakdowns). Weights such as 45/30/25 are **Score Pack fields** for a challenge (e.g. Burgers P0 default), not a global hardcoded law in the engine.

> **Implementation note:** Full Score Bank formulas, per-family stress taxonomies, and gate margin definitions remain in this document’s historical body and challenge Score Packs. This v2.1 header is the coherency lock with Miner_MCP v2.2. Do not reintroduce prior similarity, estimate, fee, or light_compare as score terms in any pack.

---

## 1. Why a Score Bank (Not One Global Formula)

Different PDE families have fundamentally different mathematical structure, conserved quantities, and failure modes. Each challenge ships a **Score Pack** versioned with its **Generator Pack**. Changing τ, α, or category definitions is a **version bump** — not a silent validator tweak.

---

## 2. Binding: Challenge Spec Owns Data + Scoring

Challenge Spec (immutable for a live version) binds generator version, Score Pack hash, gate set, and disclosure tier. Validator loads packs by hash only.

---

## 3. Forbidden inputs (restate)

| Input | Allowed in `S_combined`? |
|-------|--------------------------|
| Validator gate + component metrics | Yes |
| Prior similarity / distance to prior | **No** |
| `estimate` / `light_compare` / `light_train` metrics | **No** |
| Exam fee | **No** |
| Mock pack metrics | **No** |

---

## 4. Model Card minimum vs miner EvaluationCard

See `Launch_Bar.md` §2.3–2.4 and `Miner_MCP.md` EvaluationCard disclosure tiers.

---

*Scoring v2.1 — coherency lock with Miner_MCP free path and budgeted cards. Full per-challenge formulas remain pack-owned; engine must enforce forbidden inputs.*
