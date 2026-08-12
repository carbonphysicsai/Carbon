# Symbolic Layer Design Specification (Phase 0 Foundation)

**Document:** `docs/SYMBOLIC_LAYER_DESIGN.md`
**Version:** 1.0
**Date:** July 2026
**Focus:** Minimal viable foundation for symbolic metadata + PySR track skeleton

---

## 1. Purpose

The symbolic layer is a core long-term capability of Hydrogen. It enables:

- Better physics-aware loss weighting
- A distinct Symbolic Regression competition track
- Richer features for the Landscape Agent
- Future Symbolic Gauntlet during specialist distillation

This document defines a **minimal but well-structured foundation** that can be built in Phase 0 without blocking other work.

---

## 2. Scope for Phase 0

We deliberately limit scope to keep momentum:

- Basic symbolic metadata extraction per challenge
- Skeleton for the **Symbolic Regression track** using PySR
- Clean interfaces for future expansion

**Out of scope for Phase 0**:
- Full ModelingToolkit.jl integration
- Advanced symbolic simplification
- Physics-informed custom loss inside PySR
- Automatic loss weight generation
- Symbolic Gauntlet enforcement

---

## 3. Data Model

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class SymbolicMetadata:
    challenge_id: str
    symmetries: List[str] = field(default_factory=list)
    conservation_laws: List[str] = field(default_factory=list)
    boundary_types: List[str] = field(default_factory=list)
    coupling_terms: List[str] = field(default_factory=list)
    dimensionless_groups: List[str] = field(default_factory=list)
    extracted_at: str
    version: str = "v0.1"
    metadata: Dict[str, Any] = field(default_factory=dict)
```

This structure is intentionally lightweight but extensible.

---

## 4. Core Components

| Component                        | Responsibility                                      | Phase 0 Scope                  |
|----------------------------------|-----------------------------------------------------|--------------------------------|
| `SymbolicMetadataExtractor`      | Extract basic symbolic features from challenge definition | Lightweight / rule-based or simple SymPy |
| `PySRTrackRunner`                | Run PySR on trajectory data and return scored equation     | Skeleton + basic callable     |
| `SymbolicFeatureStore`           | Persist and retrieve symbolic metadata per challenge       | Simple file or dict-based     |
| `SymbolicTrackInterface`         | Define how the symbolic regression track integrates        | Interface definition only     |

---

## 5. PySR Track Skeleton

```python
@dataclass
class SymbolicRegressionResult:
    equation: str
    complexity: int
    score: float
    loss: float
    metadata: Dict[str, Any]

def run_symbolic_regression(
    trajectories: Dict[str, np.ndarray],
    challenge_id: str,
    config: Optional[Dict] = None
) -> SymbolicRegressionResult:
    """
    Phase 0 skeleton.
    Later versions will support physics-informed loss,
    symbolic metadata validation, and scoring integration.
    """
    ...
```

---

## 6. Integration Points

| System              | Future Use of Symbolic Features                     | Phase 0 Requirement             |
|---------------------|-----------------------------------------------------|---------------------------------|
| Landscape Agent     | Richer causal features                              | Store metadata                  |
| Auto loss weighting | Derive weights from conservation laws               | Metadata schema                 |
| Symbolic Gauntlet   | Validate symbolic consistency during distillation   | Future                          |
| Scoring             | Optional Symbolic Bonus track                       | Interface ready                 |

---

## 7. Success Criteria for Phase 0

- Every challenge has a `SymbolicMetadata` object (even if partially populated).
- `PySRTrackRunner` can execute and return a scored equation.
- The design is clean enough that the Landscape Agent and future Symbolic Gauntlet can consume it without major refactoring.
- Symbolic track can be toggled on/off without breaking the main neural evaluation pipeline.

---

## 8. Recommended Implementation Order

1. Define `SymbolicMetadata` dataclass + basic extractor
2. Create `PySRTrackRunner` skeleton with clean interface
3. Add simple storage (file-based is acceptable)
4. Wire metadata into the challenge object
5. Document how it will evolve in Phase 1+

---

*This document defines the minimal viable foundation for the symbolic layer in Phase 0.*
