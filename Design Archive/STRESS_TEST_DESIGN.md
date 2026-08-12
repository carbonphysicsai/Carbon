# Stress Test Design Specification

**Document:** `docs/STRESS_TEST_DESIGN.md`
**Version:** 1.0
**Date:** July 2026
**Status:** Design Phase

---

## 1. Purpose & Goals

The hidden stress test system is one of Hydrogen’s core mechanisms for ensuring **robustness** and **anti-gaming**. It evaluates submissions under conditions that miners and agents do not have access to during strategy development.

### Primary Goals

- **Robustness**: Force models to generalize beyond public training/holdout data.
- **Anti-Gaming**: Make it significantly harder to overfit to known evaluation conditions.
- **Transparency & Auditability**: Allow other validators and the community to verify and reproduce stress conditions.
- **Determinism**: Every stress set must be exactly reproducible given only public inputs + validator identity.
- **Physics Grounding**: All stress must be justifiable through physical principles.

### Secondary Goals

- Support adaptive difficulty based on current leader performance.
- Enable future advanced stress generation (adversarial, uncertainty-guided, Pareto-front).
- Maintain compatibility with the `ChallengeWinnerTracker` and multi-objective scoring.

---

## 2. Core Principles

| Principle          | Requirement | Rationale |
|--------------------|-------------|-----------|
| **Hidden**         | Miners/agents must not be able to reconstruct stress conditions from public challenge data | Prevents targeted overfitting |
| **Deterministic**  | Same `challenge_id` + validator hotkey → identical stress set | Enables auditing and dispute resolution |
| **Auditable**      | Any validator or auditor must be able to regenerate and inspect stress sets | Builds trust in the evaluation process |
| **Physics-Grounded** | Every stress variant must have a clear physical justification | Maintains scientific credibility |
| **Versioned**      | Stress generation logic must be versioned and recorded | Allows historical reproducibility |
| **Access Controlled** | Raw stress data must be validator-private until after scoring | Prevents leakage |

---

## 3. Data Models

### 3.1 StressVariant

```python
from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class StressVariant:
    variant_id: str                    # Unique identifier within the stress set
    source: str                        # "procedural" | "well" | "adversarial"
    parameters: Dict[str, Any]         # Physics parameters for this variant
    well_dataset: Optional[str] = None # e.g. "turbulence", "active_matter"
    difficulty: float = 0.5            # 0.0 (easy) to 1.0 (very hard)
    metadata: Dict[str, Any] = None    # Additional provenance info
```

### 3.2 StressTestSet

```python
@dataclass
class StressTestSet:
    challenge_id: str
    seed: int
    physics_class: str                 # e.g. "elliptic", "hyperbolic", "multi_physics"
    variants: List[StressVariant]
    difficulty_level: float
    total_variants: int
    generation_config: Dict[str, Any]  # Version, generator parameters, etc.
    metadata: Dict[str, Any]
```

---

## 4. Deterministic Seeding Strategy

### 4.1 Master Seed Derivation

```python
def derive_master_seed(challenge_id: str, validator_hotkey: str) -> int:
    combined = f"{challenge_id}:{validator_hotkey}"
    return hash(combined) & 0xFFFFFFFF
```

### 4.2 Sub-seed Hierarchy

- `procedural_seed` = `hash(master_seed + "procedural")`
- `well_seed` = `hash(master_seed + "well")`
- `adversarial_seed` = `hash(master_seed + "adversarial")` (future)

This hierarchy ensures that changes to one stress type do not affect others, while the entire set remains reproducible from public inputs + validator identity.

---

## 5. Stress Generation Process

### 5.1 High-Level Flow

1. Validator receives `challenge_id`.
2. Derives master seed from `challenge_id` + validator hotkey.
3. Loads challenge metadata (physics class, relevant Well datasets).
4. Generates procedural variants using physics-class-specific rules.
5. Samples Well dataset slices (if applicable) using well seed.
6. (Future) Generates adversarial variants.
7. Assembles `StressTestSet` with full provenance metadata.
8. Stores stress set in validator-private storage.
9. Evaluates model on stress set and applies physics gates.

### 5.2 Procedural Variant Generation (by Physics Class)

The generator must be **challenge-aware**. Different physics classes require different stress dimensions.

| Physics Class       | Key Stress Dimensions                              | Example Parameters |
|---------------------|----------------------------------------------------|--------------------|
| Elliptic            | Source terms, boundary conditions, coefficient fields | Amplitude, location, smoothness |
| Parabolic           | Time-dependent forcing, variable coefficients, rollout length | Forcing frequency, conductivity variation |
| Hyperbolic          | Shock strength, high-frequency content, long-time behavior | Initial steepness, perturbation amplitude |
| Incompressible Flow | Reynolds number, geometry, boundary conditions     | Re within laminar range, obstacle scale |
| Multi-physics       | Coupling strength, individual physics parameters   | Thermal expansion coefficient, coupling term weight |
| Phase-Field         | Length scale, irreversibility parameters           | ℓ variation, degradation function parameters |

### 5.3 Well Dataset Integration

- Relevant Well datasets are mapped to physics classes.
- Slices are sampled deterministically using the well seed.
- Physics-preserving augmentations may be applied (e.g., rotations, scalings that preserve conservation properties where possible).

---

## 6. Storage & Access Control

### 6.1 Storage Location

All raw stress data must be stored in a **validator-private** directory:

```
validator_private/stress/{challenge_id}/
```

This directory must **not** be accessible to miners or public agent tooling.

### 6.2 Provenance Metadata

Every `StressTestSet` must contain:

- `generation_config` (version of generator, parameter ranges, seeds used)
- `metadata` (timestamp, validator hotkey hash, challenge version)

This enables full auditability.

### 6.3 Access Control Rules

| Actor              | Access Level                  | Rationale |
|--------------------|-------------------------------|-----------|
| Validators         | Full read access              | Must evaluate submissions |
| Miners / Agents    | No access to raw stress data  | Prevents gaming |
| Auditors           | Full read access (on request) | Enables dispute resolution and transparency |

---

## 7. Audit & Verification Process

### 7.1 Reproducibility Check

Any validator or auditor can:

1. Take `challenge_id` and the public validator hotkey.
2. Re-derive the master seed.
3. Regenerate the exact `StressTestSet` using the recorded `generation_config`.
4. Compare against the stored set.

If the sets match, the stress evaluation is considered reproducible.

### 7.2 Physics Justification Audit

Every stress variant must include metadata explaining its physical motivation (e.g., "Increased Reynolds number to stress inertial effects" or "Sampled from Well turbulence dataset to test generalization").

### 7.3 Dispute Resolution

If a miner disputes a score:

- They may request an audit.
- An independent validator regenerates the stress set.
- The original evaluation is re-run.
- Results are compared.

---

## 8. Versioning & Provenance

- The stress generator must be versioned (e.g., `v1.0`, `v1.1`).
- Every `StressTestSet` records the generator version used.
- Changes to generation logic must be documented and result in a new version.
- Historical reproducibility is maintained by keeping old generator versions available.

---

## 9. Integration with Existing Components

### 9.1 Validator

The validator calls:

```python
stress_set = stress_generator.generate(
    challenge_id=challenge_id,
    validator_hotkey=wallet.hotkey,
    difficulty=tracker.get_current_difficulty(challenge_id)
)

results = run_stress_evaluation(model, stress_set)
score = apply_physics_gates(results)
```

### 9.2 ChallengeWinnerTracker

The tracker can use `difficulty_level` from the stress set to implement adaptive stress over time (higher difficulty as leaders improve).

### 9.3 Landscape Agent (Future)

Rich stress evaluation results (including which variants caused the largest degradation) can be fed to the Landscape Agent for causal analysis.

---

## 10. Security & Anti-Leakage Measures

- Raw stress data must never be included in any public output or miner-facing API response.
- Only final aggregated scores and gate results are exposed.
- Stress data storage must be protected at the filesystem level on validator machines.
- Future adversarial generation must not leak information that could be used to reverse-engineer stress strategies.

---

## 11. Extensibility

The design supports future advanced stress layers without breaking existing functionality:

- Uncertainty-guided stress sampling
- Physics-informed adversarial perturbations
- Pareto-front multi-objective stress
- Long-horizon adaptive rollout stress

Each new layer can be added as a new `StressSource` and integrated via the registry pattern.

---

## 12. Summary

This design ensures that Hydrogen’s stress testing is:

- **Hidden** from miners during development
- **Deterministic and reproducible** for auditing
- **Physics-grounded** and justifiable
- **Extensible** to more advanced techniques
- **Transparent** enough for community verification while remaining secure

This balances the competing requirements of robustness, anti-gaming, and auditability.

---

*This document should be treated as the authoritative design reference for the stress test system and updated as implementation progresses.*
