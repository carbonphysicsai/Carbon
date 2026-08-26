# Evidence & Envelope Standards

> **Reconciliation (post-ratification):** All **score-bearing stress** stays inside the **declared exam envelope**. Reference evidence is role-based and Challenge-specific, not a universal scalar rank or a vote weight in `S_combined`.


**Carbon Subnet**  
**Version:** 1.0  
**Status:** Shared standards for generator dossiers and commercial specialists  
**Related:** [`Generator_Creation.md`](./Generator_Creation.md), [`Generator_Validation.md`](./Generator_Validation.md), [`Specialist_Bank.md`](./Specialist_Bank.md), [`Scoring.md`](./Scoring.md)

---

## TL;DR

These rules apply wherever Carbon claims physical credibility:

1. **Reference authority is qualified by role** — state what each source tests, its independence, applicability, uncertainty, and limits.
2. **Envelope = maximum claim** — exclusions are first-class; no certification wider than the tested domain.
3. **Coverage is measured** — dossier must show the generator actually exercises the claimed envelope.
4. **Thresholds are calibrated** — gate limits come from reference uncertainty and engineering relevance, not vibes.
5. **Product certificates** (Specialist Bank) inherit the same envelope discipline at higher depth.

---

## 1. Reference evidence roles

Treat "truth" as a qualified, uncertainty-bearing reference process, not a
single oracle or a universal ladder. Different sources answer different V&V
questions and may be combined only through a prospectively registered
`ReferencePolicy`.

| Evidence role | What it can support | Principal limitation to examine |
|---|---|---|
| Analytic or manufactured solution | Code verification and exact/controlled subdomains | May not represent the full target physics or operating envelope |
| Mesh/time/tolerance-converged numerical study | Numerical verification and uncertainty characterization | Discretization and model-form error remain |
| Methodologically independent cross-code witness | Correlated-error detection and corroboration | Shared equations, libraries, data, or personnel can preserve common bias |
| Experimental or industrial observation | Validation against the physical system and model-form adequacy | Measurement uncertainty, sparse coverage, provenance, and representativeness |
| Qualified accelerator/surrogate reference | Routine operational answer-key generation | Inherits a bounded envelope and must remain anchored and audited against stronger evidence |
| Unconverged or otherwise unqualified output | Exploratory diagnostics only | Insufficient by itself for a LIVE decision |

**Rules**

- Every `ReferencePolicy` states which source is primary, which sources are
  witnesses or anchors, what question each addresses, and the exact
  applicability, independence, uncertainty, disagreement, and failure rules.
- No source qualifies a generator, reference, or Challenge merely by category.
  Each contributes evidence to the registered Dossier acceptance argument.
- Multi-code agreement is not independence by definition. Shared methods,
  libraries, calibration data, assumptions, and personnel must be disclosed.
- When sources disagree, preserve the disagreement and apply the registered
  indeterminate/failure policy. Do not average incompatible evidence into
  truth or weaken gates to force a decision.

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
| Reference evidence roles and policies used inside the envelope | Yes |

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
| **Adaptive stress proposals (later)** | Failure-atlas evidence may propose a prospective Generator/Score Pack version. The new fixed sampling law must be qualified and activated for all eligible candidates under a new identity; no live candidate-specific adaptation. |

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
