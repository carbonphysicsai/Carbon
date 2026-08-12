# Generator Creation — Per-Phase Build Plan

**Carbon Subnet**  
**Version:** 1.0  
**Status:** Build & onboarding guide  
**Related:** [`Generator_Validation.md`](./Generator_Validation.md) (dossier protocol), [`Runtime_Julia_Truth_Oracle.md`](./Runtime_Julia_Truth_Oracle.md), [`Data_Management.md`](./Data_Management.md), `SPEC.md`

---

## TL;DR

**Job:** Stand up a **procedural generator** for a challenge so it can pass a Validation Dossier and go LIVE.

**Invariant:** Live miner exams use **fresh seeded draws** from a qualified generator. Reference solves and partner goldens qualify the **generator** — they are not the public exam set.

**Build loop (every pack):**  
Envelope → generator code → sample → reference backend → dossier → Score Pack bind → registry LIVE.

**Reference backends (pick per pack):** Julia/SciML → FOSS solvers (FEniCS/OpenFOAM/SU2) → commercial CAE (e.g. Simr ops) → partner goldens for qualification only.

**Phase rule:** Depth of reference rigor scales with physics difficulty. Phase 0 is analytic/light FEM. Do not claim industrial V&V on day one.

---

## 1. Purpose

`Generator_Validation.md` defines **how** a generator proves credibility (dossier).  
This document defines **how we create** generators challenge-by-challenge: inputs, phases, backends, fallbacks, and done-when.

---

## 2. What “a generator” is

A challenge generator is versioned code + config that maps:

```text
(seed, role ∈ {train, eval, stress}) → fields / ICs / BCs / coefficients inside a declared envelope
```

| Asset | Public? | Notes |
|-------|---------|--------|
| Generator code + parameter ranges | Yes | Scientific justification required |
| Score Pack + gate thresholds | Yes (versioned) | Bound to generator version |
| Validation Dossier | Yes | Evidence pack before LIVE |
| Live eval/stress tensors | **No** | Materialized on validator at runtime |
| Dossier reference cache | Controlled | Qualification only; not miner exam feed |

---

## 3. Inputs to create a challenge generator

### 3.1 Always required

| Input | Source |
|-------|--------|
| Physics family + dimension | Internal roadmap or partner |
| Operating envelope (ranges, BCs, regimes) | Spec owner / partner |
| Conserved quantities & failure modes | Physics lead |
| Stress taxonomy (categories that must be covered) | Score Pack design |
| Backbone allowlist | Protocol |
| Acceptance tolerances for dossier | Physics lead |

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

---

## 4. Per-phase requirements

| Phase | Physics (examples) | Generator complexity | Minimum reference bar | Fallback if reference is hard |
|-------|--------------------|----------------------|------------------------|-------------------------------|
| **0** | Burgers, Poisson, Darcy, heat, linear elasticity | Low (1D/2D, clear conservation) | Analytic and/or light FEM; published harness | Analytic-only packs first; defer hard geometries |
| **1A** | Simplified compressible / aero-like screening | Medium | FOSS or commercial solver + mesh study on sample set | Narrow envelope; inviscid or reduced model; Julia where honest |
| **1B** | Reacting / sequential FSI screening | High | Mechanism-aware reference policy; coupled checks | Split packs (flow-only then coupled); longer dossier cycle |
| **2** | Customer-adapted envelopes | Medium–high | Partner criteria + goldens for **qualification** | Bounds-only SKU; customer local adapt path |
| **3–4** | Coupled multiphysics / 3D turbulence-class | Very high | Statistical / multi-code agreement policy | Don’t LIVE until dossier depth matches claim |

**Phase 0 done-when (example):** generator + Score Pack + dossier with analytic/FEM agreement + stress category coverage + CI harness green.

---

## 5. SOTA build plan (standard sequence)

```text
1. Envelope freeze
   - Ranges, BCs, excluded regimes, stress categories
   - Written scientific justification (even if short in Phase 0)

2. Implement generator
   - Deterministic from seed + role
   - Train/eval/stress role split enforced
   - Entropy floor / anti-degenerate checks (Data_Management)

3. Choose reference backend(s)  ← see §6

4. Sample & solve
   - Fixed audit seeds for dossier
   - N cases sized to claim (Phase 0: tens; harder packs: more)

5. Dossier
   - Mesh/time convergence where applicable
   - Reference agreement metrics
   - Conservation / residual sanity on generated fields
   - Gate threshold calibration from statistics (not vibes)

6. Bind Score Pack
   - generator_version + scoring_version pinned together

7. Registry LIVE
   - Only after mandatory Level-1 dossier checks pass
   - Publish dossier artifact + content hashes
```

**Owners (recommended):**

| Step | Primary |
|------|---------|
| Envelope + justification | Physics / SciML lead |
| Generator implementation | SciML + protocol eng |
| Reference runs | SciML + solver ops (Julia and/or CAE) |
| Score Pack | Protocol + physics |
| LIVE decision | Stop-ship checklist (`Launch_Bar.md` spirit) |

---

## 6. Reference backend options

Pick **one primary** and document **fallback** before starting expensive runs.

| Backend | Best for | Strengths | Limits |
|---------|----------|-----------|--------|
| **A. Julia / SciML oracle** | Phase 0–1A packs expressible in SciML; adjoints | Native, programmable, auditable, subnet-aligned | Not full industrial CFD/FEA |
| **B. FOSS solvers** (FEniCS, OpenFOAM, SU2, …) | Open credibility, third-party re-run | Public, dossier-friendly | Ops + scheme sensitivity |
| **C. Commercial CAE** (Ansys / Abaqus / STAR-CCM+ via ops e.g. Simr) | Partner-grade regimes | Industry-recognizable truth path | Cost, licenses, less “anyone re-run” |
| **D. Partner goldens** | Sponsored challenges | Locks acceptance to buyer’s trusted cases | Must not replace procedural live exam |

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

## 7. Challenge partner path

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

---

## 8. Fallback playbook (when stuck)

| Failure mode | Response |
|--------------|----------|
| Reference solves too expensive | Reduce dimension/envelope; fewer dossier seeds; multi-fidelity reference |
| Solver disagreement | Document; tighten envelope; fix scheme; delay LIVE |
| No analytic truth | Require FEM/FOSS minimum; no Phase-0 pure-ML self-grade |
| Partner goldens too few | Treat as smoke tests only; enlarge procedural sample for dossier |
| Julia can’t express the PDE honestly | Don’t force it — switch to FOSS/CAE backend |
| Team bandwidth | Cap concurrent packs; Phase 0 depth > many weak LIVEs |
| Suspect generator degeneracy | Entropy floors, category coverage, reject pack |

**Global fallback:** fewer LIVE challenges with strong dossiers beat many weak ones.

---

## 9. Done-when checklist (per challenge)

- [ ] Envelope and excluded regimes written  
- [ ] Generator deterministic by `(seed, role)`  
- [ ] Train ≠ eval ≠ stress role separation tested  
- [ ] Primary reference backend chosen and version-pinned  
- [ ] Fallback backend or shrink-envelope plan written  
- [ ] Dossier Level-1 checks pass (see `Generator_Validation.md`)  
- [ ] Score Pack bound to `generator_version`  
- [ ] Stress category coverage defined and enforceable  
- [ ] Content hashes published; registry updated  
- [ ] No claim wider than dossier evidence  

---

## 10. Relationship to other docs

| Doc | Role |
|-----|------|
| **This file** | How we **build** generators and choose truth sources |
| **`Generator_Validation.md`** | How we **prove** a generator before LIVE |
| **`Runtime_Julia_Truth_Oracle.md`** | Native SciML reference/adjoint service |
| **`Data_Management.md`** | Seed hierarchy; train/eval/stress isolation |
| **`Scoring.md`** | Score Pack binding after generator exists |

---

*Create few generators well. Qualify them in public. Examine miners on fresh draws from those generators — not on a static answer key.*
