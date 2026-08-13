# Evidence & Envelope Standards

**Carbon Subnet**  
**Version:** 1.0  
**Status:** Shared standards for generator dossiers and commercial specialists  
**Related:** [`Generator_Creation.md`](./Generator_Creation.md), [`Generator_Validation.md`](./Generator_Validation.md), [`Specialist_Bank.md`](./Specialist_Bank.md), [`Scoring.md`](./Scoring.md)

---

## TL;DR

These rules apply wherever Carbon claims physical credibility:

1. **Reference strength is ranked** — state which level you used; never imply a stronger level than the evidence.
2. **Envelope = maximum claim** — exclusions are first-class; no certification wider than the tested domain.
3. **Coverage is measured** — dossier must show the generator actually exercises the claimed envelope.
4. **Thresholds are calibrated** — gate limits come from reference uncertainty and engineering relevance, not vibes.
5. **Product certificates** (Specialist Bank) inherit the same envelope discipline at higher depth.

---

## 1. Reference evidence hierarchy

Treat "truth" as **reference evidence with a stated strength**, not a single oracle.

| Rank | Evidence type | Typical use |
|------|---------------|-------------|
| **R5** | Analytic / manufactured solution | Phase 0 packs where available |
| **R4** | Mesh/time-converged numerical reference (pinned FOSS or SciML) | Default dossier bar |
| **R3** | Multi-code agreement (two independent solvers) | Disputed regimes; higher claims |
| **R2** | Trusted industrial golden (partner / lab) | Qualification support only |
| **R1** | Single-code unconverged or weak approximate | Insufficient for LIVE alone |

**Rules**

- Every Validation Dossier states the **highest rank actually achieved** and on how many audit seeds.
- R2 goldens **qualify generators**; they are not the live miner exam set.
- R1 cannot carry a LIVE decision by itself.
- When ranks disagree: document both; prefer principle checks (conservation, stability); tighten envelope before weakening gates.

---

## 2. Operating envelope as claim boundary

The envelope is not marketing text. It is the **maximum domain** Carbon will defend for that generator or specialist.

Must be written before LIVE (generators) or before commercial ship (specialists):

| Element | Required |
|---------|----------|
| Parameter ranges (e.g. Re, Ma, material bounds) | Yes |
| Geometry / BC class | Yes |
| **Excluded regimes** (shocks, cavitation, turbulence class, ...) | Yes |
| Stress categories that must be hit | Yes (generator) |
| Reference rank used inside the envelope | Yes |

**Rule:** No claim wider than dossier (lean) or product-battery (commercial) evidence.

---

## 3. Generator coverage metrics (dossier)

Level-1 dossiers must not only match reference on a few seeds; they should show the **draw distribution** covers the claim.

Minimum reporting (Phase 0 can be light; Phase 1A+ stricter):

| Metric | Intent |
|--------|--------|
| Range coverage | Samples reach near envelope bounds |
| Category coverage | Required stress categories appear at target rates |
| Degeneracy / entropy | Avoid collapsed or trivial draws (`Data_Management`) |
| Rare-regime rate | Low-probability but declared regimes still appear |

Coverage failures → shrink envelope or fix generator; do not lower physics gates to compensate.

---

## 4. Threshold calibration

Gate thresholds in the Score Pack must be **traceable**:

1. Measure reference solver uncertainty / residual floors on dossier samples  
2. Set hard gates above numerical noise, below engineering-irrelevant slack  
3. Publish calibration notes in the dossier (even a short table)  
4. Bind thresholds to `(generator_version, scoring_version)`

**Forbidden:** copying thresholds from another PDE family without re-calibration.

---

## 5. Stress generation intent

Stress exists to **hunt failure modes** inside the envelope (conservation breaks, shocks, stiff regimes, BC edges, long-ish rollout instability) — not to invent a second random benchmark.

| Layer | Scope |
|-------|--------|
| **Lean exam** | Fixed category taxonomy per Score Pack; hidden seeds |
| **Product battery** | Deeper adversarial / inverse / plant suites (`Specialist_Bank`) |
| **Adaptive stress (later)** | Optional Port B evolution from failure atlas — **out of scope for Phase 0 Creation** |

---

## 6. Specialist / product inheritance

Commercial specialists **do not** invent a new physics domain silently.

| Artifact | Envelope rule |
|----------|---------------|
| Lean challenge generator | Dossier envelope |
| Standard specialist | Same or **stricter** subset; product battery on that subset |
| Customer bounds specialist | Customer envelope + Carbon qualification path; bounds-in default |

Product-facing language may call this an **operating certificate**: qualified domain, exclusions, measured battery results, reference rank. That certificate is earned by the gauntlet — not by leaderboard rank.

---

## 7. Doc ownership

| Concern | Canonical doc |
|---------|----------------|
| Build sequence, backends, partner path | `Generator_Creation.md` |
| Dossier protocol, cache, publication | `Generator_Validation.md` |
| Evidence ranks, coverage, calibration, envelope claims | **This file** |
| Product battery, dual egress, commercial ship | `Specialist_Bank.md` |
| Gate formulas and category IDs | `Scoring.md` |

---

*Strength of claim ≤ strength of evidence. Envelope is the claim boundary. Goldens qualify generators; fresh draws examine models.*
