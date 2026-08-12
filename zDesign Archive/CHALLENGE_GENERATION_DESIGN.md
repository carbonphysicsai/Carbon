# Challenge Generation Function Design (Phase 0)

**Document:** `docs/CHALLENGE_GENERATION_DESIGN.md`
**Version:** 1.0
**Date:** July 2026
**Focus:** Clean, deterministic challenge generation function

---

## 1. Purpose

Create a single, well-designed function that generates everything needed to run a challenge in a deterministic and auditable way.

This function is foundational for reproducibility, stress test generation, and future symbolic metadata integration.

---

## 2. Requirements

- Must be **deterministic**: Same `challenge_id` → same output
- Must produce or reference:
  - Training data split
  - Holdout data split
  - Stress test configuration
  - Symbolic metadata (when available)
  - Physics class
  - Difficulty parameters
- Must be **extensible** for future symbolic metadata and advanced stress generation
- Should support both procedural challenges and data-driven challenges

---

## 3. Proposed Interface

```python
def generate_challenge(
    challenge_id: str,
    config: Optional[Dict[str, Any]] = None
) -> Challenge:
    """
    Generate a fully defined Challenge object.
    """
    ...
```

### 3.1 Challenge Data Class (Proposed)

```python
@dataclass
class Challenge:
    challenge_id: str
    physics_class: str
    training_data: Any                    # Reference or loaded data
    holdout_data: Any
    stress_config: Dict[str, Any]         # Parameters for stress generation
    symbolic_metadata: Optional[SymbolicMetadata] = None
    difficulty: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)
```

---

## 4. Key Design Decisions

### 4.1 Deterministic Seeding

The function must derive all random behavior from `challenge_id` (plus optional validator hotkey for stress data).

### 4.2 Separation of Concerns

- `generate_challenge()` should focus on **structure and references**.
- Actual data loading can happen lazily or in a separate `load_challenge_data()` function.
- Stress generation should be delegated to the `StressGenerator` (see stress test design).

### 4.3 Extensibility

The design should easily support:
- Adding symbolic metadata in Phase 1+
- Future stress configuration (adversarial, uncertainty-guided, etc.)
- Multi-physics challenge definitions

---

## 5. Success Criteria for Phase 0

- One function call produces a complete, usable `Challenge` object.
- Output is fully deterministic given `challenge_id`.
- The object contains (or references) everything needed for training, holdout evaluation, and stress testing.
- Easy to extend for symbolic metadata and advanced stress features.

---

## 6. Recommended Implementation Order

1. Define `Challenge` dataclass
2. Implement `generate_challenge()` with basic procedural logic
3. Integrate with stress generation (item #1)
4. Wire in symbolic metadata when available (item #3)
5. Add tests for determinism and output structure

---

*This document defines the design for a clean challenge generation function.*
