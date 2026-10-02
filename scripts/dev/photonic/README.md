# Photonic coupler (#345): the repair, the reference and the test Challenge

The package is `carbon/photonic/`. It holds Carbon's own full-vector mode
solver, a symmetric directional coupler in the local-supermode model, and the
DEVELOPMENT test Challenge built on them.

Ticket: `.agent/tickets/CHALLENGE-PHOTONIC-01_repair_and_reference.md`.
Decision: OWNER-CHALLENGE-DESIGN-01.

**Everything here is DEVELOPMENT.** No value is a qualified threshold,
population or production claim. **The reference is the local-supermode
model, declared as such.** It is not the planned 3D FDTD, and it is never
relabelled as one (#345).

## Commands

```bash
python scripts/dev/photonic/build_tables.py OUT.json --step-nm 10 [--every 1] [--workers 2]
python scripts/dev/photonic/pilot.py OUTDIR --t20 T20.json --t5 T5.json
python scripts/dev/photonic/pools.py PRIVATE_DIR --root ROOT_FILE --public PUBLIC_DIR
python scripts/dev/photonic/baselines.py PUBLIC_DIR --private PRIVATE_DIR/private.jsonl --out REPORT.json
```

numpy and scipy (the `science-jax` group) are needed to build tables and for
the learned baseline. Evaluating the reference from committed tables is pure
Python.

## The repair (#345 tasks 1-6)

- **The phase convention, by construction.**
  - Each port's mode is the TE0 mode of its guide alone at the port pitch,
    with unit power.
  - Its sign makes its Ex integrate real and positive over its own core.
  - For a mirror-symmetric pair, the port-plane supermodes are then exactly
    (upper ± lower)/√2, so a supermode's own phase cancels. That gives
    S31 = e^(−iΣ) cos(Δφ/2), S41 = −i e^(−iΣ) sin(Δφ/2), and
    arg(S41/S31) = −π/2 exactly.
  - The campaign's ±π/2 flips were the mode-sign ambiguity this removes.
- **The mode solver**, `modes.py`, is the standard Yee-grid FDFD
  eigenproblem.
  - Sub-pixel permittivity averaging puts the cores' true edges into every
    mesh.
  - A fixed pseudo-random start vector makes every solve bit-reproducible.
- **Energy.** The model is lossless by construction. The campaign's FDTD lost
  2-3 % to radiation, reflection and discretization; that is outside this
  model, and it is its stated limit.

## The reference

A case is two inputs: the gap (150-300 nm) and the coupling length
(1-6 µm). The fixed family is:
- two 500 × 220 nm silicon strips in silica (n 3.48 and 1.444);
- cosine S-bends of 3.0 and 2.0 µm to a 1.6 µm port pitch;
- five wavelengths, 1.50-1.60 µm.

**The outputs, per wavelength:**
- the cross power, |S41|² = sin²(Δφ/2);
- the unwrapped common phase, Σ = (φ_even + φ_odd)/2.

S31 and S41 follow from these two exactly.

**The reference has two steps:**
1. **Tables.** The even and odd supermode indices on a 41-gap geometric
   ladder from 150 to 1,100 nm (where the bends end), at a 10 nm mesh.
   - They are committed as `carbon/photonic/tables_v1.json`.
   - They are pinned by hash to the sources that built them.
   - Each entry carries its checks:
     - TE fraction above 1/2;
     - mirror parity ±1 within 1e-3;
     - eigen-residual at most 1e-8;
     - indices between silica's and silicon's;
     - splitting monotone in the gap.
2. **Integration.** `reference.py` interpolates the log-splitting and the
   mean index in the gap. It integrates them along the case's gap profile
   with 6,000 midpoints. That costs milliseconds per case.

## Evidence

**Rung P1, the mode solver.**
- **An exact slab, both polarizations, both orientations.**
  - TE converges to the exact 2.851739.
  - TM, which exercises the x-derivative terms, goes 2.0597 to 2.0567
    against an exact 2.0563.
- **The 500 × 220 nm strip:** TE0 n_eff 2.4488, 2.4539, 2.4493 and 2.4496 at
  40, 20, 10 and 5 nm.
  - The last step changes it by 3e-4.
  - The value matches the published ~2.44-2.45.

**Rung P2, the supermode splitting with averaging.**
- At a 208.8 nm gap: 0.01826, 0.01815 and 0.01870 at 40, 20 and 10 nm.
- At a 500 nm gap: 0.001474, 0.001461 and 0.001511.

**The FDTD comparison at the campaign's case** (gap 208.8 nm, length
5.618 µm, 1.55 µm):
- **Cross power:** the supermode model gives 0.0592 at 20 nm and 0.0626 at
  10 nm. The FDTD's finest run (20 nm) gives 0.0598.
- **Both are still moving with the mesh.** The supermode model moved 6 % from
  20 to 10 nm. The FDTD moved 15 % from 30 to 20 nm.
- **So the evidence supports agreement at the 5-10 % level, no finer.** A
  radiation-inclusive check needs 3D FDTD at 10 nm or finer. That is paid
  compute, costed in the ticket and not run.

**Rung P3, the tables.**
- **Every entry passes its checks at 20, 10 and 5 nm.**
- **A grid-alignment wobble remains.** It is periodic in the gap, because
  where the core edges fall on the grid moves with it. Against a smooth fit
  in the gap:

  | Mesh | Mean index (rms, max) | Splitting (rms, max) |
  |---|---|---|
  | 20 nm | 2.5e-4, 8.7e-4 | 0.8 %, 1.5 % |
  | 10 nm | 9e-5, 2.7e-4 | 0.25 %, 0.55 % |

  - At 10 nm it moves a case's common phase by at most about 7e-3 rad, and
    its cross power by about 0.5 %.
  - **The tables are not smoothed.** The wobble is part of the declared
    reference and is reported as its noise.
- **Determinism.** Two builds of the 20 nm table from the same sources are
  bitwise equal, and a sub-ladder build reproduces the full ladder's entries
  bitwise.

## The pilot

Twelve cases (`scripts/dev/photonic/pilot.py`, evidence
`docs/development/evidence/photonic-pilot-v1/`), from public draws:
- 8 ordinary draws of the population;
- 4 difficult cases at the box's corners:
  - the strongest coupler (150 nm, 6 µm);
  - the weakest (300 nm, 1 µm);
  - the shortest strong one, coupled mostly in its bends;
  - the longest weak one.

Every case carries four refinement pairs. Each isolates one cause:

| Pair (worst over 12 cases) | Δφ | Common phase | Cross power |
|---|---|---|---|
| 4x the z points | 2e-8 | 3.5e-8 rad | 7e-9 |
| Every fourth ladder gap, against all 41 | 0.4 % | 5.6e-3 rad | 4.8e-4 |
| 5 nm against 10 nm, on every fourth gap | **0.25 %** | **0.024 rad** | 1.1e-3 |
| 20 nm against 10 nm, likewise | 2.7 % | 0.21 rad | 5.9e-3 |

**Outcomes: 12 of 12 OK.**
- Each case's integral converged.
- Each output passes the exam's gates.

**The mesh error.**
- The 20-10-5 nm sequence converges at an observed order of about 3.
- That puts the 10 nm reference's remaining error at about 0.3 % in Δφ and
  0.03 rad in the common phase.
- **So the score measures agreement with the declared 10 nm contract.**
  Below about 0.03, a score difference says nothing about the converged
  model.

**The ladder's interpolation error** with all 41 gaps is a fraction of the
every-fourth-gap figure above.

**The closed-form baseline errs by 1.1-1.7 in score**, almost all of it
phase (1.1-2.1 rad RMS).
- The effective index method overestimates the index and the coupling.
- Its cross power at 1.55 µm is 0.002-0.19 high.

**The pilot's cross power at 1.55 µm** runs from 0.0013 to 0.19.

**Cost on the owner's host, with no marginal spend:**

| Item | Cost |
|---|---|
| 10 nm table, 205 solves | 1.5 core-hours (27 s per solve) |
| 5 nm sub-ladder, 55 solves | 2.3 core-hours (151 s per solve) |
| One case's reference from the tables | 0.1 s |

## The exam, pools and baselines

**The exam** is `carbon/photonic/exam.py`.
- **Gates:**
  - shape and finiteness;
  - a cross power in [0, 1], because the contract is passive and lossless;
  - a common phase falling with wavelength, because a guided mode's group
    delay is positive;
  - the paired repeat.
- **The score is the RMS complex S-parameter error, √(mean over λ of
  |ΔS31|² + |ΔS41|²).** It is unit-free and reads as radians for small
  phase errors. A whole turn of common phase costs nothing, because no
  measurement could see it.
- **The important region** is a cross power at 1.55 µm of 0.10 or more.
- **Feasibility** is a tap ratio with a flatness limit. It is a decision
  about designs, reported beside the score.

**The pools** (`scripts/dev/photonic/pools.py`) are generated whole, because
the reference costs a tenth of a second.
- **Public, in `docs/development/evidence/photonic-pools-v1/`:**
  - TRAIN, 1,000 cases;
  - PRACTICE, 200 cases.
- **Private:** 500 cases, drawn from an operator-held root and kept
  owner-only outside the repository.
  - Its commitment is
    `sha256:bf1849494ab5a542c2a03d0e4646454a2bba15ebbf9d5db71e391ea9b3885109`.
- All 1,700 references are OK, and every gate holds on every one.

**The baselines** (`scripts/dev/photonic/baselines.py`, report
`baselines.json`):

| Baseline | PRACTICE | Private | Important region (private) |
|---|---|---|---|
| Closed-form (effective index method) | 1.437 | 1.446 | 1.674 |
| Learned (Chebyshev ridge, degree 12, chosen on PRACTICE) | 5.3e-4 | 5.8e-4 | 2.3e-3 |

- The closed-form model's cross-power bias in the important region is
  +0.14.
- The learned model scores below the reference's own mesh error. For two
  smooth inputs and 1,000 cases that is expected: this family is a phase-aware
  test Challenge, not a demonstration of engineering value (ticket D2).
