# Electric motor (#344): the reference service, its rungs and the pilot

This directory runs Carbon's motor reference, the package `carbon/motor/`. It
meshes each Challenge case with Gmsh, solves it with GetDP in a pinned image,
and reads back a typed torque curve with its checks.

Ticket: `.agent/tickets/CHALLENGE-MOTOR-01_development_exam.md`.
Decision: OWNER-CHALLENGE-DESIGN-01.

**Everything here is DEVELOPMENT.** No value is a qualified threshold,
population or production claim.

## Commands

```bash
docker build -t carbon-motor-reference:dev scripts/dev/motor/reference
python scripts/dev/motor/reference/pilot_plan.py PLAN.json
python scripts/dev/motor/reference/run_batch.py PLAN.json --out DIR [--parallel 6] [--timeout-s 14400] [--keep all|failed|none]
python scripts/dev/motor/reference/pilot_report.py DIR [--json OUT]
python scripts/dev/motor/reference/pool_plan.py OUTDIR --root ROOT_FILE
python scripts/dev/motor/reference/baselines.py --train DIR --practice DIR --private DIR --out REPORT.json
```

`run_batch.py` gives each case one container:
- the pinned image, with no network and a two-CPU cap;
- one BLAS thread (D3a);
- a hard wall limit, after which it kills that container by its unique name
  and touches no other.

A case meshes once and solves every rotor position in that container.
Every case ends as one typed record, whose outcome is one of:
- `OK`;
- `REFERENCE_INVALID`: a position did not converge, or the torque at 15°
  does not repeat the torque at 0°;
- `REFERENCE_SOLVER_FAILED`: a position left no torque;
- `REFERENCE_TIMEOUT`;
- `FAILED_INFRA`: the case could not start.

No outcome is ever charged to a candidate.

## What a case is

**The frame is fixed:** the GRUCAD 8-pole, 24-slot surface-PM machine's
published dimensions, with a single-layer winding of 104 turns per slot.

**Eight inputs vary it:**
- magnet thickness and pole embrace;
- airgap and slot opening;
- tooth width and slot bottom radius;
- peak current density and current angle.

The ranges are in `carbon/motor/domain.py`. The geometry must be buildable
(`domain.validity`), which about 91 % of the box is.

**The output is the torque at 60 rotor angles over one 15° period**, with the
three phase currents turning with the rotor. A model predicts that curve. The
mean torque and the ripple are derived from it, never predicted separately.

## The reference

**The tools.**
- Gmsh 4.15.2 and GetDP 3.5.0, both GPL, each checked by SHA-256 when the
  image is built (`Dockerfile`).
- The image runs on the owner's host only. Carbon writes the inputs and reads
  the outputs; it redistributes neither tool.

**Carbon's own models.** The benchmark's model files carry a copyright line
and no licence, so Carbon wrote its own:
- the geometry, `carbon/motor/mesh.py`;
- the formulation, `carbon/motor/getdp.py`: 2D magnetostatics in the
  vector potential.

**The iron** is Brauer's law, ν = 100 + 10 exp(1.8 B²), with vacuum
permeability in parallel. That is a generic soft iron, declared, not a named
steel.

**Exact rotation.**
- The rotor and stator are meshed once each. They meet on a mid-airgap circle
  of 1,440 uniformly spaced nodes.
- A rotor angle is a whole number of node steps, so the mesh never changes
  with angle. Torque ripple cannot be remeshing noise.

**Torque** is Arkkio's Maxwell stress over the exact airgap annulus. Virtual
work from the co-energy cross-checks it in the rungs.

**The nonlinear solve** is damped Newton (0.5) to 1e-3, then full Newton to
1e-6 on the relative increment (D3).

## The rungs

**M1, linear iron (μr 1,000), the benchmark's dimensions.**
- Cogging over one period:
  - its mean is −3e-5 N·m;
  - it is periodic to 2e-6, and antisymmetric.
- Mesh refinement over 720, 1,440 and 2,880 nodes:
  - Maxwell stress converges at an observed order of 1.9;
  - virtual work meets it, from 5.7-11.8 % apart at 720 to 0.3-0.7 % at
    2,880.
- The current-angle law holds exactly, with no reluctance torque.

**M2, nonlinear iron.**
- Saturation costs 10 % of the torque at 10.9 A: 11.73 N·m against 13.07.
- Under saturation Maxwell stress and virtual work agree to 0.03 %:
  - 11.730 against 11.727 N·m at 10.9 A;
  - 22.096 against 22.089 N·m at 25 A.

## The pilot

Seventeen cases (`pilot_plan.py`), all from public draws, run on the
owner's host. Evidence is in `docs/development/evidence/motor-pilot-v1/`;
what ran, and how it maps onto the committed sources, is in its
`PROVENANCE.md`.
- **8 ordinary** draws of the population.
- **4 difficult** cases, each the most extreme of 4,000 further draws:
  - deep saturation;
  - the sharpest cogging;
  - the weakest field;
  - the deepest field weakening.
- **4 refined:** two ordinary and two difficult cases again at 2,880 airgap
  nodes, every 1° over the period.
- **1 angle-resolution window:** 0.125° steps over the first 3.75° of an
  ordinary case, on the 2,880-node mesh.

**Outcomes: 17 of 17 OK.**
- Every rotor position converged.
- Every full period repeats: the worst mismatch between the torque at 15°
  and at 0° is 6.3e-5 of the peak, against the 1e-3 check.

**The population's range.** Mean torque runs from 0.32 to 11.5 N·m, and
peak-to-peak ripple from 0.29 to 2.38 N·m.

| Check (worst over its pairs) | Result |
|---|---|
| Mesh: 1,440 against 2,880 nodes, at 1° | torque within 0.017 N·m (0.26 % of peak); mean within 0.1 %; ripple peak-to-peak within 1 % |
| Angle: the 0.25° samples against the 0.125° midpoints | linear interpolation within 4.6e-4 N·m (8e-5 of peak); the window's peak-to-peak is identical with or without them |
| Determinism: the window against the refined run at 1° | identical (difference 0.0) |
| Textbook baseline, mean torque | over-predicted in every case, by 5-26 % (0.08 to 2.96 N·m) |
| Textbook baseline, ripple | omits 0.10 to 0.82 N·m RMS |

**So the reference resolves what the Challenge asks for.**
- Its discretization (0.1 % in mean torque) is a fiftieth or less of the
  baseline's mean-torque error.
- 60 angles per period capture the ripple's shape.

**Cost on the owner's host, with no marginal spend.** These are the walls
with six cases sharing the host and the cold plate pools running beside
them:

| Case | Wall |
|---|---|
| Ordinary | 1,109 to 2,455 s |
| Difficult | 1,072 to 3,417 s |
| Refined (16 positions at 2,880 nodes) | 1,535 to 4,550 s |
| The 31-position window | 5,983 s |

One position at 1,440 nodes costs about 17 s alone on one core.

**Recommendation: PROCEED** to the pools and the learned baseline.

The rungs' raw outputs are in `docs/development/evidence/motor-rungs/`.

## The exam, pools and baselines

- **The exam** is `carbon/motor/exam.py`.
  - Gates: shape, a non-negative motoring mean, and the paired repeat.
  - Score: the mean of the TRAIN-normalized mean-torque and ripple-shape
    errors.
- **The pools:** 150 TRAIN, 30 PRACTICE and 60 private cases (ticket D8,
  amended for cost).
  - The private pool comes from an operator-held root. Its commitment is
    `sha256:5ec0222502eb608c52d1162f4be6c7347deed7b6d4f03777ec4ea31b6d619559`.
- **The baselines:**
  - the textbook surface-PM model (`carbon/motor/analytic.py`);
  - Gaussian-kernel ridge regression (`carbon/learned_baseline.py`), scored
    when the pools are complete.
