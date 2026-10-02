# CHALLENGE-PHOTONIC-01 — the photonic coupler: repair, reference and decision

**Status:** slice 2 complete; ready for testing as a DEVELOPMENT test
Challenge. Its readiness record v4 waits in CHALLENGE-READINESS-RELAY-01.
**Primary Hub map_ref:** `SYSTEM/AGENT-EXECUTION`, `HUB_UPDATE_REQUIRED`.
**Authority:** OWNER-CHALLENGE-DESIGN-01 (2026-10-01) and OWNER-DX-03.
**Tracking:** carbonphysicsai/Carbon#345.

## Why this ticket starts with a repair

#345 put the exam behind a repair: "an exam built on an unresolved convention
grades the convention".

The campaign's 3D FDTD runs at one case (gap 208.8 nm, coupling length
5.618 µm, 1.55 µm) disagreed with each other:
- **Cross power** was 0.052, 0.070 and 0.060 at 40, 30 and 20 nm.
- **Relative phase** flipped by about π between meshes.
- **The 20 nm run needed 10.9 GB of GPU memory.** This host's GPU has 6 GB.

## What this ticket does (#345 tasks 1-6)

1. **Conventions, defined by construction.** In `carbon/photonic/coupler.py`:
   - Each port's mode is the TE0 mode of its guide alone, at the port pitch.
   - It is normalized to unit power.
   - Its sign is fixed so that its Ex integrates real and positive over its
     own core.
   - The reference planes are the start of the left bend and the end of the
     right bend.
2. **The sign problem, resolved without fitting.**
   - For a mirror-symmetric pair, the port-plane supermodes are exactly
     (upper ± lower)/√2, so a supermode's own phase cancels.
   - Then S31 = e^(−iΣ) cos(Δφ/2) and S41 = −i e^(−iΣ) sin(Δφ/2), so
     **arg(S41/S31) = −π/2 exactly**, at every mesh and wavelength.
   - The campaign's ±π/2 flips are the mode-sign ambiguity this removes.
3. **An alternative reference.** It is a local-supermode model (a two-mode
   expansion along the coupler).
   - Its cross-section modes come from Carbon's own full-vector FDFD solver,
     `carbon/photonic/modes.py`, with sub-pixel permittivity averaging.
   - It is compared with the campaign's FDTD below.
4. **A costed plan for a finer comparison:** below.
5. **Energy.**
   - The FDTD's |S31|² + |S41|² is 0.972-0.98: 2-3 % leaves through
     radiation, reflection and discretization.
   - The supermode model is lossless by construction. Radiation is outside
     it, and that is its stated model-form limit.
6. **Complex S-parameters are supportable** under this contract. The phase
   is exact by construction.

## Evidence

**Rung P1: the mode solver.**
- **An exact slab, both polarizations, both orientations.**
  - TE converges to the exact 2.851739.
  - TM, which exercises the x-derivative terms, goes 2.0597 → 2.0567
    against an exact 2.0563.
- **The 500 × 220 nm strip, with averaging:** TE0 n_eff 2.4488, 2.4539,
  2.4493, 2.4496 at 40, 20, 10 and 5 nm. The last step changes it by 3e-4,
  and the value matches the published ~2.44-2.45.
- **A correction.** Without averaging, the solver's inclusive
  staircasing made the core effectively larger. That bias converges slowly:
  it read 2.41 → 2.48 → 2.50, which a Richardson estimate pushed to 2.506.
  That estimate was an artefact. Averaging is now part of the reference.

**Rung P2: supermode splitting.**
- Without averaging, the splitting was erratic across meshes: 0.0025,
  0.0065 and 0.0012 at a 500 nm gap. The splitting is exponential in the
  gap, and staircasing moves the gap.
- **With averaging, at 40, 20 and 10 nm:**
  - at a 208.8 nm gap: 0.01826, 0.01815, 0.01870 (±1.5 %);
  - at a 500 nm gap: 0.001474, 0.001461, 0.001511 (±1.7 %).

**The FDTD comparison.** The case is gap 208.8 nm, coupling length 5.618 µm:

| λ | Supermode, 20 nm | Supermode, 10 nm | FDTD cross power |
|---|---|---|---|
| 1.50 µm | 0.0381 | 0.0404 | 0.0486 (30 nm) |
| 1.55 µm | 0.0592 | **0.0626** | **0.0598 (20 nm, its finest)**; 0.0704 (30 nm); 0.0523 (40 nm) |
| 1.60 µm | 0.0903 | 0.0950 | 0.1133 (30 nm) |

- At 1.55 µm the supermode model at 10 nm and the finest FDTD differ by
  5 % (0.0626 against 0.0598).
  - Both are still moving with the mesh. The supermode model moved 6 % from
    20 to 10 nm; the FDTD moved 15 % from 30 to 20 nm.
  - So the comparison supports agreement at the 5-10 % level, no finer.
- The port modes are isolated (cross-overlap ≤ 8e-5) and unit-power.

**Rung P3: the supermode tables.** Supermodes of the pair on a 41-gap
geometric ladder from 150 to 1,100 nm, at five wavelengths. Every entry
passes its checks: TE-like, mirror parity ±1 to 1e-6, eigen-residual near
4e-14, indices ordered, and splitting monotone in the gap.
- **The tables carry a grid-alignment wobble.** Sub-pixel averaging leaves
  a small residual that depends on where the core edges fall on the grid.
  It is periodic in the gap.
  - Measured against a smooth fit in the gap:

    | Mesh | Mean index (rms, max) | Splitting (rms, max) |
    |---|---|---|
    | 20 nm | 2.5e-4, 8.7e-4 | 0.8 %, 1.5 % |
    | 10 nm | 9e-5, 2.7e-4 | 0.25 %, 0.55 % |

  - At 10 nm it moves a case's common phase by at most about 7e-3 rad, and
    its cross power by about 0.5 %.
- **20 to 10 nm:**
  - Cross power rises 2.5-6 %.
  - The common phase falls about 0.2 rad. Almost all of that is the strip's
    own index, 2.4539 to 2.4493; from 10 to 5 nm it changes by only 3e-4
    (rung P1).

## Results (slice 2)

**The pilot: 12 of 12 OK.** Evidence is in
`docs/development/evidence/photonic-pilot-v1/`.
- Every case carries four refinement pairs:
  - z integration: 3.5e-8 rad;
  - ladder interpolation, every fourth gap: 5.6e-3 rad;
  - 10 to 5 nm: 0.25 % in Δφ, 0.024 rad;
  - 20 to 10 nm: 2.7 %, 0.21 rad.
- The 10 nm reference's remaining error is about 0.3 % in Δφ and 0.03 rad.
- The closed-form baseline errs by 1.1-1.7 in score, almost all of it phase.

**The pools.** 1,000 TRAIN and 200 PRACTICE cases are public; 500 private
cases sit under commitment `sha256:bf1849494ab5a542c2a03d0e4646454a2bba15ebbf9d5db71e391ea9b3885109`.
- Every gate holds on all 1,700 references.

**The baselines on the private pool:**

| Baseline | Score |
|---|---|
| Closed-form | 1.446 |
| Learned | 5.8e-4 |

**Determinism.** Table builds are bitwise reproducible: two builds, and a
sub-ladder build against the full one.

**Cost:**
- the 10 nm table, 1.5 core-hours;
- the 5 nm sub-ladder, 2.3 core-hours;
- one case's reference, 0.1 s.

## Decision taken under delegation

- **D1. The reference contract is the local-supermode model, declared as
  such.**
  - It is not the planned 3D FDTD, and it is never relabelled as one (#345).
  - Agreement is with this model. Radiation, reflection, bend loss and the
    guides' tilt in the bends are outside it.
- **D2. Engineering value: low for the symmetric family.**
  - For a symmetric coupler, the supermode model is itself the conventional
    design method. A learned model can only learn to reproduce it.
  - That family is therefore a **phase-aware test Challenge**: cheap, exact
    in its phase convention, and useful for testing Carbon's pipeline on
    complex-valued outputs. It is not a demonstration of engineering value.
- **D3. Where the value lies (v2, scoped, not built).**
  - Asymmetric couplers, as in wavelength-flattened splitters. Their
    supermodes do not have the symmetric form, so the reference needs a
    two-mode eigenmode expansion with numerical overlaps between sections.
    That is well-posed, because the asymmetry lifts the port degeneracy.
  - And/or fabrication variation.
  - The radiation-inclusive check needs 3D FDTD at 10 nm or finer: about 8x
    the 20 nm run's 10.9 GB, so roughly 90 GB of GPU memory, beyond one
    A40.
  - **That 3D check is paid compute and needs its own owner grant.** The
    estimate follows.

- **D4. The symmetric test Challenge.**
  - **Inputs:** the gap (150-300 nm) and the coupling length (1-6 µm), in
    the campaign's family and bounds (`carbon/photonic/domain.py`).
  - **Outputs at the five wavelengths:**
    - the cross power, sin²(Δφ/2);
    - the unwrapped common phase, (φ_even + φ_odd)/2.
  - S31 and S41 follow from these two exactly, under the port convention.
    Predicting them is predicting the complex response, without a wrapped
    phase's discontinuities.
- **D5. The reference is the committed 10 nm tables, integrated.**
  - `carbon/photonic/tables_v1.json` is built by
    `scripts/dev/photonic/build_tables.py` and pinned to its sources by
    hash.
  - `carbon/photonic/reference.py` interpolates the log-splitting and the
    mean index in the gap and integrates them along the case's profile with
    6,000 midpoints.
  - **Why 10 nm.** The wobble falls about threefold from 20 nm.
  - The 5 nm sub-ladder measures what remains: 0.25 % in Δφ and 0.024 rad in
    the common phase, at an observed order of about 3 (pilot).
  - **The tables are not smoothed.** The wobble is part of the declared
    reference and is reported as its noise. A smoothed v2 could lower the
    exam's resolution floor.
- **D6. The exam (`carbon/photonic/exam.py`).**
  - **Gates:**
    - shape and finiteness;
    - a cross power in [0, 1], because the contract is passive and lossless;
    - a common phase falling with wavelength, because the group delay of a
      guided mode is positive;
    - the paired repeat.
  - **The score is unit-free:** the RMS over wavelengths of
    |ΔS31|² + |ΔS41|², square-rooted.
    - A common phase error d alone costs 2 sin(d/2), so small errors read
      as radians.
    - A whole turn costs nothing, which no measurement could see.
  - **The important region** is a cross power at 1.55 µm of 0.10 or more.
    The signed cross-power bias is reported there, not scored.
  - **Feasibility** is a tap ratio with a flatness limit, reported beside
    the score.
- **D7. Pools of 1,000 TRAIN, 200 PRACTICE and 500 private cases.**
  - The reference costs milliseconds per case, so the pools are generated
    whole.
  - The private pool is drawn from an operator-held root, and only its
    commitment is published.
- **D8. The baselines.**
  - **Closed-form:** the effective index method, a vertical slab then a
    five-layer TM pair, integrated like the reference.
  - **Learned:** ridge regression on tensor Chebyshev features of the two
    scaled inputs. Its degree and ridge are chosen on PRACTICE.
  - For two smooth inputs this generic model is appropriate. The eight- and
    nine-input Challenges use kernel ridge instead.

## The costed 3D comparison (estimate, for the owner's decision)

| Quantity | Estimate | Basis |
|---|---|---|
| Cells at 10 nm | ~8x the 20 nm run's 13.1 million | halving the spacing in three dimensions |
| Time steps | ~2x | Courant limit |
| Wall time | about 16 x 538 s ≈ 2.4 h per wavelength per excitation | the 20 nm run took 538 s on an A40 |
| GPU memory | ~90 GB | 8x 10.9 GB, so an 80 GB-class GPU at the limit, or multi-GPU |
| Cost | not priced | no rate is applied here; it needs a provider quote |

The minimum comparison is one case, three wavelengths and two excitations.
That is about 14 GPU-hours.

## Slices

1. Rungs P1-P2 and the decision record.
2. The symmetric test Challenge (this change):
   - the tables;
   - domain, population, exam and both baselines;
   - the pilot, with refinement at 20 and 5 nm;
   - the pools;
   - readiness record v4.
3. v2 asymmetric EME, if the owner wants the value version. It runs without
   paid compute.

## Out of scope

Paid compute (the 3D comparison), mainnet, the miner path, and scientific or
launch acceptance.
