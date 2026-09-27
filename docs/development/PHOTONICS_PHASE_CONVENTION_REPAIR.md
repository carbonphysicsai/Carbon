# Photonics (#345): the phase-convention and convergence repair

**Status.** This is a repair note, not a scope and not an exam design.
- #345 comes before any photonic exam: "an exam built on an unresolved
  convention grades the convention".
- The convention proposed in §2 is an engineering proposal for scientific
  review, not a chosen value.
- The convergence plan in §3 is priced for owner approval and has not run.

**Sources.**
- `docs/development/EXAM_DESIGN_CAMPAIGN_RESULT.md` §9: the diagnostics,
  relayed.
- `scripts/dev/exam_design/photonic_reference.py`: read for this note.
- The locked `fdtdx==0.6.2` wheel from
  `scripts/dev/exam_design/locks/photonic-overlay.lock.json`. It was fetched
  and its SHA-256 matched the lock. The source was read, not run.

## 1. What the current diagnostics assume (T6.1)

**Finding: the diagnostics have no phase convention of their own.** The phase
they report is whatever the eigensolver returned. That is a convention by
default, not by choice.

- **The mode's phase is never fixed.**
  - Each port's mode is solved independently by Tidy3D's mode solver, called
    from `fdtdx/core/physics/modes.py`.
  - fdtdx then rescales it to unit power (`normalize_by_poynting_flux` in
    `core/physics/metrics.py`). The code divides E and H by
    √|∫ ½ Re(E*×H)·x̂ dA|, a positive real factor, so the solver's complex
    phase passes through untouched.
  - Carbon's `photonic_reference.py` adds no phase or sign rule.
  - Whether Tidy3D's solver fixes a phase internally was **not verified**: its
    source is not in this wheel. Neither Carbon nor fdtdx relies on one.
- **Every S entry carries an arbitrary ratio of phases.**
  - `calculate_sparam` returns S = overlap(output mode) / overlap(input
    mode), from `utils/sparams.py:317`.
  - With each mode's phase left to its own solve, S carries the ratio of two
    independent phases.
  - This explains the observation in RESULT §9: arg(S41/S31) is −1.66, +1.53
    and −1.63 rad at 40, 30 and 20 nm. That is a π flip, which a sign chosen
    independently at each port and each resolution produces.
- **The reference planes are not de-embedded.**
  - The detector planes sit 0.4 × the lead length in from each end, snapped to
    the grid.
  - Absolute phase includes the propagation phase to those planes, which moves
    with resolution. RESULT §9: arg S31 = 2.37, 2.09 and 1.11 rad, not
    converged.
- **The magnitudes do not depend on phase, and they check out.**
  - Straight-guide |S31|² = 0.9996, with S31 = S13 exactly at 30 nm.
  - Reciprocity holds to 0.42 % at 20 nm.
  - So normalization and the mirrored-excitation mapping work. **The defect is
    phase, not power.**

## 2. What the convention should be, and why (proposal for scientific review)

**A port's phase should be a property of the geometry at a declared plane, not
of the solver's eigenvector.** Two rules together give that.

1. **Fix each mode's phase deterministically after solving it.** Multiply the
   mode by e^{−iφ}, where φ is the phase of the dominant transverse E
   component (E_y for the fundamental TE mode) integrated over the port
   cross-section. That integral then becomes real and positive.
   - Why the integral: it is insensitive to single-cell noise. Because it is
     taken on the same geometry, it gives the same sign at every resolution
     and at every port with the same waveguide.
   - The alternative is the field value at the mode's maximum. It is cheaper,
     but for a symmetric mode it depends on which grid cell holds the maximum.
2. **Declare reference planes fixed to the device and de-embed to them.**
   - Multiply each port's S factor by e^{iβΔx}, using the port mode's own β
     (from n_eff) and the distance Δx from the detector plane to the declared
     plane.
   - Reported phases then refer to planes that do not move with grid snapping.
   - Until this is in place, only phase differences between ports on the
     same x-plane are comparable.

**How to check it** (engineering, before any exam):
- Repeat the 40/30/20 nm diagnostic with both rules.
- arg(S41/S31) should stop flipping by π. Any remaining drift is a
  convergence question (§3), not a convention question.
- The straight guide must keep S31 = S13. The mirrored-excitation mapping is
  unaffected by construction, because the mirror maps each port's TE mode onto
  a TE mode with the same integral sign.

**Reserved for the scientific reviewer (the SciML holder):**
- whether complex S-parameters are supportable at all, or whether the
  Challenge should use a power-only contract (#345 task 6). A power-only
  variant is a new, explicit contract, not a silent substitution;
- which declared planes the exam uses;
- any phase tolerance.

None of these is chosen here.

## 3. Coupled-power convergence (T6.2)

**State, relayed from RESULT §9.** |S41|² is 0.052, 0.070 and 0.060 at 40, 30
and 20 nm.
- The sequence is not monotone, so the resolutions are not yet in the
  asymptotic range.
- The spread is about 15 % of the coupled fraction.
- Radiated and absorbed power are not accounted for, so no passivity
  tolerance is supportable.

**Projected cost of finer runs.** These are **estimates**, extrapolated from
the two measured points: 76 s and 4 GB at 30 nm; 265 s and 10.9 GB at 20 nm.

| Resolution | Wall time per run | GPU memory | Fits an A40 (48 GB)? |
|---|---|---|---|
| 20 nm (measured) | 265 s | 10.9 GB | yes |
| 15 nm | 640 to 840 s | 22 to 26 GB | yes |
| 10 nm | 2,200 to 4,200 s | 60 to 87 GB | **no**: needs an 80 GB-class GPU, or a mode-expansion reference |

The range spans the observed scaling (time ∝ Δ^−3.1, memory ∝ Δ^−2.5) and
the ideal 3D FDTD scaling (Δ^−4, Δ^−3).

**Proposed first study**, for owner approval; not run:
- one coupler geometry, 1.55 µm, both excitations;
- 30, 20 and 15 nm, with the §2 convention applied.
- That is six runs, about 0.6 h of A40 time plus about 0.25 h for boot and
  cleanup.
- **Estimated about USD 0.42** at the recorded A40 rate of USD 0.49/h. The
  price must be re-read before any dispatch.

It answers three questions:
- whether the convention removes the π flip;
- whether |S41|² starts to converge by 15 nm;
- whether a 10 nm step or a mode-expansion reference is needed.

The 10 nm step, or an eigenmode-expansion reference as an independent check,
would be a second, separately priced decision.

## 4. What this note does not do

- It runs nothing and spends nothing.
- It sets no convention, tolerance or plane. It proposes, for review.
- It designs no photonic exam and changes no readiness record. Photonics stays
  `DEFER`.
