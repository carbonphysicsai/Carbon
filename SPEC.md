# Carbon — Protocol Specification

**A Bittensor subnet for trustless verification of physics-informed neural operator training strategies**

**Status:** Phase 0 foundations + offline PoC. Landscape and commercial layers are **build-ordered** — not assumed live at launch.

**Canonical companions**

| Doc | Role |
|-----|------|
| [`appendices/Scoring.md`](./appendices/Scoring.md) | Lean formulas, Score Bank, validator load path |
| [`appendices/Launch_Bar.md`](./appendices/Launch_Bar.md) | Stop-ship before public prior publish |
| [`appendices/Generator_Creation.md`](./appendices/Generator_Creation.md) | Per-phase generator build plan, reference backends, partner path, fallbacks |
| [`appendices/Generator_Validation.md`](./appendices/Generator_Validation.md) | Validation Dossier protocol before LIVE |
| [`docs/TRUSTLESS_VERIFICATION_AND_DATA_GENERATION.md`](./docs/TRUSTLESS_VERIFICATION_AND_DATA_GENERATION.md) | Seeding philosophy, trustless eval, proprietary-data plan |
| [`appendices/Data_Management.md`](./appendices/Data_Management.md) | Seeds, train ≠ eval |
| [`appendices/Runtime_Julia_Truth_Oracle.md`](./appendices/Runtime_Julia_Truth_Oracle.md) | SciML reference / adjoint oracle |
| [`appendices/Landscape_Agent.md`](./appendices/Landscape_Agent.md) | Four-port knowledge architecture (v1.2+) |
| [`appendices/Specialist_Bank.md`](./appendices/Specialist_Bank.md) | Product gauntlet, dual egress (v1.3+) |
| [`appendices/Use_Cases_by_Phase.md`](./appendices/Use_Cases_by_Phase.md) | Inverse design / plant / UQ / hybrid truth |
| [`appendices/Implementation.md`](./appendices/Implementation.md) / `IMPLEMENTATION.md` | Code-level patterns |
| [`appendices/Compute_Optimization.md`](./appendices/Compute_Optimization.md) | Compute strategy |
| [`appendices/JAX_Optimization.md`](./appendices/JAX_Optimization.md) | Validator JAX efficiency |
| [`appendices/Operations.md`](./appendices/Operations.md) | Deploy / ops |

---

## 1. Executive summary

Carbon coordinates miners and agents to discover training strategies for neural operators (FNO, GINO, WNO, Transolver, and successors). Validators retrain and evaluate those strategies on hidden, procedurally generated data under hard physics gates. Emissions follow that independent score — not self-reported metrics.

**Core loop:** Miners submit training strategies (loss configurations, curricula, architectures, data-generation parameters). Validators execute deterministic training from scratch on hidden procedural data, evaluate against hard physics gates and challenge-bound Score Packs, and emit Model Cards. Verified cards later feed a knowledge layer that compounds insight under strict publish rules and, only after a verification gauntlet, commercial specialists.

> **Note:** Full SPEC body sections §2–§18 remain as previously published on `main`. This commit prioritizes companion table + §4 generator coherency. If any body section is missing after merge, restore from the prior SPEC revision and keep the companion table and §4 block below.

## 4. Trustless verification and data generation

### Core principles

- **Procedural generation at runtime:** Primary evaluation and stress data are generated at runtime with open-source generators.
- **Public unpredictable seeding:** Phase 0 uses `hash(challenge_id + block_hash + run_nonce)`; Phase 1B+ moves toward commit-reveal + drand-class randomness where useful.
- **Auditable by anyone:** Generator code is open; anyone can reproduce a draw given the seed.
- **Scientific credibility:** Parameter ranges need documented physical justification; generators validated against high-fidelity references (FEniCS, OpenFOAM, SU2, DPLR, US3D, **DifferentialEquations.jl**, and peers).
- **No fixed public benchmark as the live exam:** Fixed datasets may validate generators; they are not the miner-facing answer key.
- **Train ≠ eval ≠ stress:** Distributions and seeds are separated; miner local loops must not see validator eval seeds.

### Ground truth oracle

Julia/SciML supplies reference solutions, adjoints, and structured loss hooks — for generator validation and optional structured losses, not as a substitute for the adversarial exam. See [`Runtime_Julia_Truth_Oracle.md`](./appendices/Runtime_Julia_Truth_Oracle.md).

### Generator creation and qualification

| Doc | Role |
|-----|------|
| [`Generator_Creation.md`](./appendices/Generator_Creation.md) | How packs are **built**: envelope, per-phase bar, reference backend menu (Julia / FOSS / CAE / partner goldens), fallbacks |
| [`Generator_Validation.md`](./appendices/Generator_Validation.md) | How packs are **proven**: Validation Dossier before LIVE |
| [`TRUSTLESS_VERIFICATION_AND_DATA_GENERATION.md`](./docs/TRUSTLESS_VERIFICATION_AND_DATA_GENERATION.md) | Seeding philosophy, local vs official eval, proprietary-data phases |

**Invariant:** Partner goldens and dossier reference caches **qualify the generator**. Live miner exams use **fresh seeded draws** from that generator — not a static public answer key.

### Data generation invariants

- `stress_seed` unknown to miners until evaluation.
- Validator generator config ignores miner-supplied eval params.
- Score Pack robustness category IDs must align with Generator Pack categories ([`Scoring.md`](./appendices/Scoring.md) + [`Data_Management.md`](./appendices/Data_Management.md)).
- Stress category coverage targets remain as specified in Data Management (≥95% where defined).
- No challenge goes LIVE without a Validation Dossier that meets the mandatory Level-1 bar (`Generator_Validation.md`).

### Launch checklist addendum

- [ ] Generator Validation Dossier Level-1 green for first LIVE challenge(s)

---

*Lean exams keep search and emissions honest. Generators are built and dossier-qualified before LIVE. Landscape compounds under explicit port law. Specialist Bank ships only gauntlet-verified products.*
