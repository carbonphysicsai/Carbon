# Generator Creation — Per-Phase Build Plan

**Carbon Subnet**  
**Version:** 1.1  
**Status:** Build & onboarding guide  
**Related:** [`Generator_Validation.md`](./Generator_Validation.md), [`Evidence_and_Envelope_Standards.md`](./Evidence_and_Envelope_Standards.md), [`Runtime_Julia_Truth_Oracle.md`](./Runtime_Julia_Truth_Oracle.md), [`Data_Management.md`](./Data_Management.md), `SPEC.md`

---

## TL;DR

**Job:** Stand up a **procedural generator** for a challenge so it can pass a Validation Dossier and go LIVE.

**Invariant:** Live miner exams use **fresh seeded draws** from a qualified generator. Reference solves and partner goldens qualify the **generator** — they are not the public exam set.

**Build loop (every pack):**  
Envelope → generator code → sample → reference backend → dossier → Score Pack bind → registry LIVE.

**Reference backends (pick per pack):** Julia/SciML → FOSS solvers (FEniCS/OpenFOAM/SU2) → commercial CAE (e.g. Simr ops) → partner goldens for qualification only.

**Phase rule:** Depth of reference rigor scales with physics difficulty. Phase 0 is analytic/light FEM. Do not claim industrial V&V on day one.

**Claim rule:** Strength of verification claim ≤ strength of dossier evidence. Envelope is the maximum defendable domain (see [`Evidence_and_Envelope_Standards.md`](./Evidence_and_Envelope_Standards.md)).

---

## 1. Purpose

`Generator_Validation.md` defines **how** a generator proves credibility (dossier).  
`Evidence_and_Envelope_Standards.md` defines **reference ranks, coverage metrics, and threshold calibration**.  
This document defines **how we create** generators challenge-by-challenge: inputs, phases, backends, fallbacks, and done-when.

Carbon is building **qualification infrastructure for physics problem distributions** — not a static public answer key.

---

## 2. What "a generator" is

A challenge generator is versioned code + config that maps:

```text
(seed, role ∈ {train, eval, stress}) → fields / ICs / BCs / coefficients inside a declared envelope
```

| Asset | Public? | Notes |
|-------|---------|--------|
| Generator code + parameter ranges | Yes | Scientific justification required |
| Score Pack + gate thresholds | Yes (versioned) | Bound to generator version; calibrated per Evidence Standards |
| Validation Dossier | Yes | Evidence pack before LIVE |
| Live eval/stress tensors | **No** | Materialized on validator at runtime |
| Dossier reference cache | Controlled | Qualification only; not miner exam feed |

---

## 3. Inputs to create a challenge generator

### 3.1 Always required

| Input | Source |
|-------|--------|
| Physics family + dimension | Internal roadmap or partner |
| Operating envelope (ranges, BCs, regimes, **exclusions**) | Spec owner / partner |
| Conserved quantities & failure modes | Physics lead |
| Stress taxonomy (categories that must be covered) | Score Pack design |
| Backbone allowlist | Protocol |
| Acceptance tolerances for dossier | Physics lead |
| Target reference rank (R5–R1) | Physics lead — see Evidence Standards |

### 3.2 Optional (strengthen dossier)

| Input | Source | Rule |
|-------|--------|------|
| Golden reference cases | Partner or lab | **Qualification only** — never sole live exam |
| Preferred commercial solver | Partner | Document version + scheme |
| Proprietary data | Customer | Stays with customer; bounds-in default |

### 3.3 Explicit non-goals

- Shipping a public fixed train/test dump as the exam  
- Requiring raw OEM trajectories on the network for Phase 0–1  
- Using partner goldens as the only scored instances  
- Adaptive stress that evolves from live miner failures (later Port B — not Phase 0 Creation scope)  

---

## 4. Envelope = claim boundary

Freeze the envelope **before** expensive reference runs. It is the maximum domain this generator may support in marketing or LIVE claims.

Must include:

- Parameter ranges and geometry/BC class  
- **Excluded regimes** (first-class, not footnotes)  
- Stress categories required for coverage  
- Intended reference rank for dossier  

If dossier evidence is weaker than the written envelope → **shrink the envelope**, do not inflate the claim.

---

## 5. Per-phase requirements

| Phase | Physics (examples) | Generator complexity | Minimum reference bar | Fallback if reference is hard |
|-------|--------------------|----------------------|------------------------|-------------------------------|
| **0** | Burgers, Poisson, Darcy, heat, linear elasticity | Low (1D/2D, clear conservation) | Analytic and/or light FEM (R5/R4); published harness | Analytic-only packs first; defer hard geometries |
| **1A** | Simplified compressible / aero-like screening | Medium | FOSS or commercial solver + mesh study (R4/R3) | Narrow envelope; inviscid or reduced model; Julia where honest |
| **1B** | Reacting / sequential FSI screening | High | Mechanism-aware reference policy; coupled checks | Split packs (flow-only then coupled); longer dossier cycle |
| **2** | Customer-adapted envelopes | Medium–high | Partner criteria + goldens (R2) for **qualification** + independent sample checks | Bounds-only SKU; customer local adapt path |
| **3–4** | Coupled multiphysics / 3D turbulence-class | Very high | Statistical / multi-code agreement (R3+) | Don’t LIVE until dossier depth matches claim |

**Phase 0 done-when (example):** generator + Score Pack + dossier with analytic/FEM agreement + stress category coverage + CI harness green.

---

## 6. SOTA build plan (standard sequence)

```text
1. Envelope freeze (ranges, exclusions, stress categories, target reference rank)
2. Implement generator (deterministic seed+role; train≠eval≠stress; entropy floors)
3. Choose reference backend(s) and rank  ← §7
4. Sample & solve (fixed audit seeds; N sized to claim)
5. Dossier (convergence, reference agreement, coverage metrics, calibrated thresholds)
6. Bind Score Pack (generator_version + scoring_version)
7. Registry LIVE only after Level-1 dossier pass + published hashes
```

**Owners (recommended):**

| Step | Primary |
|------|---------|
| Envelope + justification | Physics / SciML lead |
| Generator implementation | SciML + protocol eng |
| Reference runs | SciML + solver ops (Julia and/or CAE) |
| Score Pack + threshold calibration | Protocol + physics |
| LIVE decision | Stop-ship checklist (`Launch_Bar.md` spirit) |

---

## 7. Reference backend options

Pick **one primary** and document **fallback** before starting expensive runs. State the **evidence rank** (R5–R1) the dossier will claim.

| Backend | Best for | Strengths | Limits |
|---------|----------|-----------|--------|
| **A. Julia / SciML oracle** | Phase 0–1A packs expressible in SciML; adjoints | Native, programmable, auditable, subnet-aligned | Not full industrial CFD/FEA |
| **B. FOSS solvers** (FEniCS, OpenFOAM, SU2, …) | Open credibility, third-party re-run | Public, dossier-friendly | Ops + scheme sensitivity |
| **C. Commercial CAE** (Ansys / Abaqus / STAR-CCM+ via ops e.g. Simr) | Partner-grade regimes | Industry-recognizable truth path | Cost, licenses, less “anyone re-run” |
| **D. Partner goldens** | Sponsored challenges | Locks acceptance to buyer’s trusted cases | Must not replace procedural live exam |

Full rank definitions and disagreement policy: [`Evidence_and_Envelope_Standards.md`](./Evidence_and_Envelope_Standards.md).

### Recommended defaults

| Phase | Primary | Fallback |
|-------|---------|----------|
| 0 | Analytic + Julia or light FEM | Pure analytic pack; shrink envelope |
| 1A | FOSS CFD/FEA **or** Julia if honest | Narrow envelope; reduced physics |
| Partner challenge | Partner goldens **+** one independent backend on samples | Bounds-only challenge; delay LIVE |
| Hard multiphysics | Commercial CAE samples + clear disagreement policy | Split into sequential simpler packs |

### Disagreement policy (required in writing)

When two references disagree:

1. Record both  
2. Prefer conservation / principle checks both satisfy  
3. Tighten envelope or change scheme before lowering gates to “pass”  
4. Never silently average away a fail on a mandatory physical principle  

---

## 8. Challenge partner path

```text
Partner supplies: envelope + criteria (+ optional goldens)
Carbon builds:    procedural generator inside that envelope
Dossier:          goldens + independent backend qualify generator
LIVE exam:        seeded hidden draws from generator (not the golden set alone)
Output:           searchable regime → specialist / licensed path for partner
```

**Rules**

- Goldens are **dossier evidence**, not the miner leaderboard set  
- Partner does not need to upload production trajectory archives for default path  
- If evidence is too thin → don’t LIVE; offer bounds-only or delayed pack  

**Simr-class ops (optional):** Carbon defines cases → partner/ops runs commercial solvers → results feed dossier → generator approved. Ops supply reference capacity; they do not replace the open generator.

---

## 9. Fallback playbook (when stuck)

| Failure mode | Response |
|--------------|----------|
| Reference solves too expensive | Reduce dimension/envelope; fewer dossier seeds; multi-fidelity reference |
| Solver disagreement | Document; tighten envelope; fix scheme; delay LIVE |
| No analytic truth | Require FEM/FOSS minimum; no Phase-0 pure-ML self-grade |
| Partner goldens too few | Treat as smoke tests only; enlarge procedural sample for dossier |
| Julia can’t express the PDE honestly | Don’t force it — switch to FOSS/CAE backend |
| Team bandwidth | Cap concurrent packs; Phase 0 depth > many weak LIVEs |
| Suspect generator degeneracy | Entropy floors, category coverage, reject pack |
| Coverage metrics fail | Shrink envelope or fix sampler — never relax hard gates to “pass” |

**Global fallback:** fewer LIVE challenges with strong dossiers beat many weak ones.

---

## 10. Done-when checklist (per challenge)

- [ ] Envelope and **excluded regimes** written  
- [ ] Target reference rank stated  
- [ ] Generator deterministic by `(seed, role)`  
- [ ] Train ≠ eval ≠ stress role separation tested  
- [ ] Primary reference backend chosen and version-pinned  
- [ ] Fallback backend or shrink-envelope plan written  
- [ ] Dossier Level-1 checks pass (see `Generator_Validation.md`)  
- [ ] Coverage / calibration notes per Evidence Standards  
- [ ] Score Pack bound to `generator_version`  
- [ ] Stress category coverage defined and enforceable  
- [ ] Content hashes published; registry updated  
- [ ] No claim wider than dossier evidence  

---

## 11. Relationship to other docs

| Doc | Role |
|-----|------|
| **This file** | How we **build** generators and choose truth sources |
| **`Evidence_and_Envelope_Standards.md`** | Reference ranks, coverage, threshold calibration, envelope claims |
| **`Generator_Validation.md`** | How we **prove** a generator before LIVE |
| **`Runtime_Julia_Truth_Oracle.md`** | Native SciML reference/adjoint service |
| **`Data_Management.md`** | Seed hierarchy; train/eval/stress isolation |
| **`Scoring.md`** | Score Pack binding after generator exists |
| **`Specialist_Bank.md`** | Product battery inherits envelope discipline at higher depth |

---

*Create few generators well. Qualify them in public. Examine miners on fresh draws from those generators — not on a static answer key.*
