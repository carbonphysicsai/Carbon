# Testing Design Specification (Phase 0)

**Document:** `docs/TESTING_DESIGN.md`
**Version:** 1.0
**Date:** July 2026
**Focus:** Automated testing for scorer, physics gates, and ChallengeWinnerTracker

---

## 1. Purpose

Create a reliable, maintainable automated test suite that gives high confidence the core evaluation components work correctly, robustly, and reproducibly.

This is essential for Phase 0 credibility, future maintenance, and validator audits.

---

## 2. Scope (Phase 0 Focus)

We prioritize testing the most critical and error-prone parts of the evaluation pipeline:

- Physics gates (hard + soft)
- Multi-objective scoring logic
- `ChallengeWinnerTracker` behavior
- Reproducibility of scoring results

Out of scope for Phase 0: full end-to-end validator integration tests and preCICE/multi-physics testing (those come in Phase 1+).

---

## 3. Recommended Test Structure

```
tests/
├── test_physics_gates.py
├── test_scorer.py
├── test_tracker.py
├── test_reproducibility.py
└── conftest.py
```

## 4. Key Test Categories

### 4.1 Physics Gates
- Verify every hard gate correctly returns score = 0 when violated
- Test soft gate penalty functions across input ranges
- Test phase-field specific gates (when implemented)
- Include edge cases (NaN, inf, empty results, missing metrics)

### 4.2 Multi-Objective Scorer
- Verify correct weighted combination (default 45/30/25)
- Test behavior with missing or invalid metric values
- Test combined score calculation and final output

### 4.3 ChallengeWinnerTracker
- Test exponential decay behavior over multiple updates
- Verify only new best combined scores affect the current leader
- Test winner-heavy vs participation dust allocation
- Test isolation between different challenges

### 4.4 Reproducibility
- Run the same submission multiple times
- Assert scores and key intermediate results are identical (within defined floating-point tolerance)

## 5. Success Criteria for Phase 0

- Core evaluation logic has meaningful automated test coverage (target >70%)
- All hard physics gates are explicitly tested
- `ChallengeWinnerTracker` behavior is well covered
- Reproducibility of scoring is verified in tests
- Tests are easy to run (`pytest`) and structured for future CI integration

## 6. Dependencies

- Benefits from item #2 (determinism guarantees), but can be developed in parallel
- Does not block other remaining Phase 0 items

## 7. Future Considerations

- Add integration tests once the full validator pipeline is stable
- Add stress test generation tests when that system is implemented
- Add property-based testing for physics gates where appropriate

---

*This document defines the testing strategy for Phase 0 core evaluation components.*
