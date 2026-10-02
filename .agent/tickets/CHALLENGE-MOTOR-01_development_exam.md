# CHALLENGE-MOTOR-01 — the electric motor as a DEVELOPMENT exam, ready for testing

**Status:** slices 1-3 complete. Slice 4's pools (150/30/60) are running on
the owner's host, and its baselines are scored when they finish. Readiness record v3
waits in CHALLENGE-READINESS-RELAY-01.
**Primary Hub map_ref:** `SYSTEM/AGENT-EXECUTION`, `HUB_UPDATE_REQUIRED`.
**Authority:** OWNER-CHALLENGE-DESIGN-01 (2026-10-01) and OWNER-DX-03; the
internal admission protocol OWNER-CHALLENGE-ADMISSION-01 (amended).
**Tracking:** carbonphysicsai/Carbon#344.

## Outcome

The same checkable list as CHALLENGE-COLD-PLATE-01:
1. a reference service;
2. a pilot (8 ordinary, 4 difficult, 4 paired refinements);
3. a DEVELOPMENT population with a public sampling law;
4. the four kinds of rule kept separate;
5. public and private pools;
6. a closed-form baseline and one learned baseline;
7. the readiness record.

The miner-path integration is CHALLENGE-MOTOR-02.

## Maturity ceiling

DEVELOPMENT, internal, non-paying. It confers:
- no qualified population, tolerance or gate;
- no LIVE, reward or chain authority;
- no scientific or security qualification.

## The reference: Carbon's own, on GPL tools run operator-side

**Why not the benchmark's model files.**
- The ONELAB electric-machine models carry a copyright line and no licence.
- #344 says to verify redistribution rights, not assume them, and they are
  not established.
- So Carbon wrote its own geometry and formulation:
  - `carbon/motor/mesh.py` is a Gmsh Python script;
  - `carbon/motor/getdp.py` generates the GetDP input.
- The benchmark model is used only as a local cross-check. It is never
  redistributed.

**The image.** `scripts/dev/motor/reference/Dockerfile`:
- GetDP 3.5.0 and Gmsh 4.15.2, each checked by SHA-256 at build;
- the repository's digest-pinned Ubuntu base;
- apt packages from a dated Ubuntu snapshot. `ca-certificates` comes from the
  current archive, because the snapshot is HTTPS-only.
- It runs with `--network none`.

**Exact rotation.**
- The rotor and stator are meshed once each. They meet on a mid-airgap circle
  of uniformly spaced nodes.
- A rotor angle of whole node steps rotates the rotor's nodes and renumbers
  the shared circle.
- So torque ripple cannot be remeshing noise.

**Torque, two ways:**
- Arkkio's Maxwell stress over the exact airgap annulus;
- virtual work from the co-energy, with currents frozen.

## Decisions taken under delegation

- **D1. The frame is the GRUCAD 8-pole, 24-slot surface-PM machine.**
  - It uses the published dimensions (Ferreira da Luz et al., IEEE Trans.
    Magn. 38(2), 2002): rotor surface 25.6 mm, stator outer radius 46 mm,
    stack 35 mm.
  - The magnets are radially magnetized, Br 1.2 T with mu_r 1.
  - The winding is single-layer, one slot per pole per phase, 104 turns per
    slot.
  - The shaft is 10.5 mm.
- **D2. The iron is Brauer's law with the ONELAB models' coefficients,
  nu = 100 + 10 exp(1.8 B^2), with vacuum permeability in parallel**
  (mu = mu_Brauer + mu0).
  - It is a generic soft iron, not a named steel. The reference is graded
    against this declared law, as battery's is against its declared cell.
  - The parallel term keeps iron no less permeable than vacuum. Without it,
    the law reaches mu_r ≈ 0.007 at 3 T, and Newton diverged (rung M2).
- **D3. The nonlinear solver.**
  - Damped Newton (0.5) to 1e-3, then full Newton to 1e-6, both on the
    relative solution increment.
  - Undamped Newton cycles from a cold start at rated current, and so does
    the benchmark's own model (rung M2).
  - **Why 1e-6.** The pilot's first attempt asked 1e-8 and stopped. Some
    rotor positions stall near 4.4e-7, a floor this problem reaches. They
    were mislabelled as non-converged and cost about 30 wasted iterations
    each.
    - Torque agrees to 1e-11 between 1e-8 and 1e-6 where both converge
      (10.2974268694 N·m), three orders below the mesh error.
    - That attempt's directory is kept as
      `pilot-v1-attempt1-newton-1e-8` on the host.
- **D3a. One BLAS thread per solve.**
  - GetDP's linked OpenBLAS starts a thread per host CPU, about 20, inside a
    two-CPU container.
  - The pilot's second attempt ran six such containers at a load average of
    42-48 on 20 CPUs, and no case finished in about 50 minutes.
  - One rotor position took 53.8 s, against 16.7 s with `OMP_NUM_THREADS` and
    `OPENBLAS_NUM_THREADS` set to 1. The runner now sets both.
  - The attempt left no records. A relaunch made before the fix landed was
    stopped within a minute. Its log overwrote attempt 2's.
- **D4. Eight inputs.**

  | Input | Range |
  |---|---|
  | Magnet thickness | 1.5-4.0 mm |
  | Pole embrace | 0.55-0.95 |
  | Airgap | 0.3-1.0 mm |
  | Slot opening | 1-6° |
  | Tooth width | 2.5-5.0 mm |
  | Slot bottom radius | 34-42 mm |
  | Peak current density | 0-15 A/mm² |
  | Current angle (field weakening) | 0-60° |

  - Current enters as a density, so it means the same in every slot shape.
  - The geometry must also be buildable:
    - the slot is at least 1 mm wide where the coil starts;
    - the opening fits the slot behind it, with 0.2 mm to spare;
    - the slot is at least 1 mm deep.
- **D5. The output is the torque at 60 rotor angles over one 15° period**,
  with the currents turning with the rotor.
  - This slot and pole count's cogging period and six-pulse period coincide,
    so one period holds both.
  - Mean torque and ripple are derived from the curve, never predicted
    separately.
- **D6. The mesh is 1,440 airgap nodes (0.25° steps).**
  - Rung M1 measured Maxwell-stress torque within about 2 % of its
    extrapolated value at the cogging peak at this mesh.
  - The two torque methods agree within 1.2-2.6 % here, and within 0.3-0.7 %
    at 2,880 nodes.
- **D7. The exam (`carbon/motor/exam.py`), in the cold plate's shape.**
  - Gates: the output's shape and finiteness; a non-negative period-mean
    torque, within the reference's own periodicity allowance, because the
    current is in the motoring quadrant; and the paired repeat.
  - The score is the mean of two TRAIN-normalized errors: the period-mean
    torque, and the ripple's shape (the curve less its mean). They are kept
    apart so that a flat-curve model is charged for the ripple it omits.
  - The important region is a current density of 10 A/mm² or more, where
    saturation acts. The signed mean-torque bias is reported there, not
    scored.
  - Feasibility (a torque floor and a ripple fraction) is a decision about
    designs, reported beside the score.
- **D8. Pools of 150 TRAIN, 30 PRACTICE and 60 private cases** (amended
  2026-10-02).
  - The first plan was 300/60/120. Beside the cold plate pools, the host
    completed about 0.13 motor cases per minute, which put those pools at
    more than two days.
  - Halving them keeps a learned baseline and a scored private pool
    meaningful at about a third of the wait.
  - Draws are sequential from a fixed generator, so each pool is exactly
    the first N cases of the running plans. The batches stop when those
    cases are recorded.
  - The private pool is drawn from an operator-held root. Its commitment is
    `sha256:5ec0222502eb608c52d1162f4be6c7347deed7b6d4f03777ec4ea31b6d619559`.
- **D9. The learned baseline is Gaussian-kernel ridge regression**
  (`carbon/learned_baseline.py`), shared with the cold plate.
  - It learns the 60-angle curve from the eight scaled inputs.
  - Its two hyperparameters are chosen on PRACTICE.
  - Its one clamp lifts a negative-mean curve to a zero mean.

- **D10. The public pools were solved on rented CPU pods; the private pool
  on the owner's host only** (CHALLENGE-POOLS-CLOUD-01, under the owner's
  grant of 2026-10-02).
  - 149 cases ran natively on a RunPod CPU pod: 124 TRAIN and 25 PRACTICE.
    The pod used the pinned Ubuntu base, with this ticket's Dockerfile steps
    replayed and SHA-256-checked.
  - Native results are bitwise identical to the container on the smoke
    cases.
  - `assemble.py` built each pool from every run that solved its cases. No
    case changed.
- **D11. The learned baseline uses the widened shared grid** (cold plate
  D11).
  - On the original grid the cold plate's PRACTICE choice sat at the grid's
    edge, so the shared grid now spans lengths 0.25 to 16 and ridges 1e-8
    to 1.
  - `select` reports any choice on an edge.
  - The motor's private pool is scored once, with this grid.

## Evidence so far

**Rung M1, linear iron (mu_r 1,000), the benchmark's dimensions.**
- Cogging over one period:
  - mean −3e-5 N·m, as a cogging torque must average zero;
  - periodic to 2e-6, and antisymmetric.
- Mesh refinement over 720, 1,440 and 2,880 nodes:
  - Maxwell stress converges at observed order 1.9;
  - virtual work meets it, from 5.7-11.8 % apart at 720 to 0.3-0.7 % at
    2,880.
- The current-angle law holds: ±30° gives 13.07 cos 30° = 11.32 N·m, with no
  reluctance torque, as surface magnets with mu_r 1 require.

**Rung M2, nonlinear iron.**
- Saturation costs 10 % of the torque at 10.9 A: 11.73 N·m against 13.07.
- **Under saturation the two torque methods agree to 0.03 %:**
  - 11.730 against 11.727 N·m at 10.9 A;
  - 22.096 against 22.089 N·m at 25 A.

**The benchmark's quoted "2.5 N·m nominal" is not compared.** It belongs to
the original model's generator-with-load setup, not to a fixed-current motor
point.

## The pilot (slice 3): 17 of 17 OK

Evidence is in `docs/development/evidence/motor-pilot-v1/`. The README has
the tables.
- **Periodicity:** worst 6.3e-5, against the 1e-3 check.
- **Mesh, 1,440 against 2,880 nodes:**
  - torque within 0.26 % of peak;
  - mean within 0.1 %;
  - ripple peak-to-peak within 1 %.
- **Angle.** Linear interpolation between the 0.25° samples misses the
  0.125° midpoints by at most 8e-5 of peak. So 60 angles per period
  resolve the ripple. This is rung M3.
- **Determinism.** The same mesh at the same angle gives identical torque
  across cases.
- **The textbook baseline** over-predicts the mean torque in every case,
  by 5-26 %, and omits 0.10-0.82 N·m RMS of ripple.
- **Recommendation: PROCEED.**
- **Provenance.** The committed sources equal those that ran after three
  cosmetic transforms, recorded and checked in the evidence's
  `PROVENANCE.md`.

## Slices

1. Reference, image and rungs M1-M3, where M3 is the angle resolution.
2. Package: domain, analytic, population, exam and runner, with tests.
3. Pilot and readiness record.
4. Pools, baselines and exam scoring.

## Out of scope

The miner path (CHALLENGE-MOTOR-02), paid compute, mainnet, and any
scientific or launch acceptance.
