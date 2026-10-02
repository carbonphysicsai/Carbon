# Cold plate (#342): the reference service, rung 7, and the pilot

This directory runs Carbon's cold plate reference: the package
`carbon/cold_plate/`. It writes each Challenge case as an OpenFOAM case,
solves it in the pinned image, and reads it back as typed outputs and checks.

The verification rungs in `../plate_channel/` built and checked the physics
one change at a time. This rung moves that physics into the package. It then
adds the changes a population needs, each measured before use.

Ticket: `.agent/tickets/CHALLENGE-COLD-PLATE-01_development_exam.md`.
Decision: OWNER-CHALLENGE-DESIGN-01.

**Everything here is DEVELOPMENT.** No value is a qualified threshold,
population or production claim.

## Commands

```bash
python scripts/dev/cold_plate/reference/pilot_plan.py PLAN.json
python scripts/dev/cold_plate/reference/run_batch.py PLAN.json --out DIR [--parallel 10] [--timeout-s 14400] [--keep all|failed|none]
python scripts/dev/cold_plate/reference/pilot_report.py DIR [--json OUT]
```

`run_batch.py` gives each case its own container:
- the pinned image, with no network and a two-CPU cap;
- a hard wall limit, after which it kills that container by its unique
  name and touches no other.

Every case ends as one typed record, whose outcome is one of:
- `OK`;
- `REFERENCE_INVALID`: a check failed, or the case left the applicability;
- `REFERENCE_SOLVER_FAILED`: nothing readable;
- `REFERENCE_TIMEOUT`;
- `FAILED_INFRA`: the case could not start.

No outcome is ever charged to a candidate.

## What a case is

Nine inputs:
- channel width, fin width and depth;
- flow per kW, inlet temperature and heat load;
- an axial hot spot: its peak-to-average ratio, centre and width.

The ranges are in `carbon/cold_plate/domain.py` and the design basis.

**The solid is the rungs' repeating cell.** It is half a channel and half a
fin between symmetry planes, on the rungs' wall-graded mesh (r = 2,
grading 4).

**The reference reports five outputs. A model predicts three:**

| Output | Predicted? | Why |
|---|---|---|
| Heated-face peak | yes | |
| Heated-face span-mean profile, 30 one-millimetre segments | yes | |
| Pressure drop | yes | |
| Heated-face mean | no | exactly the profile's mean |
| Outlet bulk temperature | no | exactly the energy balance of the inputs |

## Rung 7: the package reference against the rungs

**What changed from rung 6e.** Each item was measured before it was used.

1. **Every file is written by `carbon/cold_plate/openfoam.py`.** No template
   directory is involved, and the mesh is the rungs' `block_mesh`, unchanged.
2. **Density and conductivity vary with temperature, as viscosity does.**
   - Their fits come from the same pinned CoolProp model, over 30-99 °C.
     `../plate_channel/fit_properties.py` produces them under rung 6e's
     selection rule.
   - In that model density, heat capacity and conductivity are exact cubics
     in T.
3. **Heat capacity is held at the inlet temperature.**
   - Letting it vary breaks the solver's exact energy conservation at the
     solid-fluid interface. The solver's own enthalpy flow fell 4.3e-4 to
     9e-4 short of the heat in, shrinking with the mesh.
   - Holding cp keeps the energy check exact, at a cost measured below.
4. **The heat flux follows the case's hot-spot map.**
   - It is written as an OpenFOAM `expression` in the face position. The
     pinned image's `externalWallHeatFluxTemperature` takes `q` as a
     `PatchFunction1`.
   - The analyzer computes the heat put in exactly as the solver applies it:
     the map at each of the 100 heated face centres.
5. **The energy check uses the solver's own enthalpy flows.**
   - These are function objects summing `phi h` over the inlet and outlet,
     so the check stays exact whatever cp does.

**The nominal geometry, 4,000 iterations, r = 2:**

| Case | Outcome | Peak − inlet | Mean − inlet | Δp | Energy |
|---|---|---|---|---|---|
| package, viscosity only | OK | 37.162 K | 29.947 K | 3,901.4 Pa | +2e-9 |
| rung 6e (30-99 °C fit) | | 37.159 K | 29.944 K | 3,901.4 Pa | |
| **package, the reference fluid** | **OK** | **36.677 K** | **29.616 K** | **3,925.4 Pa** | −8e-9 |
| package, cp varying too | REFERENCE_INVALID | 36.598 K | 29.563 K | 3,928.3 Pa | **−4.3e-4** |

**Findings.**
- **The package reproduces the rungs.**
  - Its viscosity-only case matches rung 6e to +0.003 K and −0.002 % Δp.
    That residue is the design basis table's rounding: the package takes
    every constant from the exact polynomials.
- **Varying density and conductivity matters.**
  - It moves the peak by −0.49 K and Δp by +0.62 %, so the reference keeps
    them.
- **Holding cp costs about 0.1 K.**
  - The peak moves −0.08 K at the nominal point and −0.12 K at 45 °C and
    1.5 kW, and Δp under 0.1 %. That is less than holding density and
    conductivity cost, and it keeps exact energy conservation.
  - The cp-varying diagnostic fails the energy check by design. That is
    what the check is for.
- **A hot spot needs base spreading.** The case is a 3x spot, centre 10 mm,
  width 2.5 mm, at 1 kW and 40 °C.
  - The reference puts its peak at 88.95 °C at x = 10.65 mm, with every
    check exact.
  - The textbook closed-form model reads it 27.6 K too hot: it carries the
    spot's flux straight down to the coolant.
  - With conduction along the flow added (a fin equation over the copper
    section of one period), the model reads it 2.4 K too cold.
  - The closed-form baseline (`carbon/cold_plate/analytic.py`) now includes
    that spreading. It is a fair conventional method, and the population's
    screen uses it.
- **Undershoot.**
  - The coldest fluid sits about 1 K below the inlet near the inlet corner,
    in every case so far, rungs 6e and 7 included.
  - linearUpwind is unbounded, and this is its undershoot.
  - It is reported as `inlet_undershoot_k` and not judged.

## The pilot

**Shape.** #342's: 8 ordinary and 4 difficult cases, with 4 paired
refinements.
- **Ordinary:** drawn from the DEVELOPMENT population
  (`carbon/cold_plate/population.py`): uniform over the box, admitted when
  the closed-form model's hottest wall is ≤ 95 °C and its Re ≤ 2,000.
- **Difficult:** each maximizes a stated property over 4,000 admitted draws:
  - the screen edge;
  - the sharpest spot;
  - the highest pressure drop;
  - the highest Reynolds number.
- **Refinements:** two ordinary and two difficult cases again at r = 3.
- **Plan.** `pilot_plan.py` writes it, and every draw is public. The frozen
  plan's SHA-256 is
  `680bdf52c27387df9c5dcfee97b5df1e1d9e6818d003602b81250fb6cec349a7`.

**Where it ran.** The owner's local host, at no marginal spend:
- a 12th-generation Core i7-12700H with 20 logical CPUs;
- ten cases at a time.

**An attempt before this one was stopped by the operator** after about two
minutes, to move it to a runner that outlives the session. It left no
records, and its directory is kept as `pilot-v1-aborted-operator-move` on the
host.

## Pilot result (2026-10-02, this host)

**All 16 cases are OK.** None is REFERENCE_INVALID, timed out or failed.
- The records are in
  `docs/development/evidence/cold-plate-pilot-v1/records.jsonl`, and the
  summary is `report.json`, produced by `pilot_report.py`.

**The worst reference check over the 16 cases:**

| Check | Worst | Limit |
|---|---|---|
| Mass imbalance | 6.9e-10 | 1e-6 |
| Energy imbalance | 2.1e-6 | 1e-5 |
| Change, half-way to final write | 1.6e-7 K; 1.4e-9 in Δp | 1e-3 K; 1e-5 |

**The screen held, with its margin partly used.**
- The hottest fluid was 96.7 °C, in the screen-edge case, against the
  coolant model's 99 °C.
- The closed-form screen read that case's hottest wall 1.7 K low.
- So 2.3 K of the 4 K margin remains.

**The inlet undershoot** reached 2.3 K. It is reported, not judged.

**Refinement, r = 2 → r = 3:**

| Case | Peak | Profile, largest change | Δp |
|---|---|---|---|
| ordinary-1 | +0.02 K | 0.05 K | +0.9 % |
| ordinary-2 | +0.02 K | 0.06 K | +1.1 % |
| sharpest spot | +0.10 K | 0.12 K | +0.9 % |
| screen edge | −0.33 K | 0.65 K | +1.6 % |

- The reference's discretization error at r = 2 is about 0.1 K on the
  peak for most cases.
- It reaches 0.33 K on the peak and 0.65 K on the profile at the screen
  edge: wide, shallow channels at Re 939, where flow is still developing
  over much of the length.
- r = 2 reads Δp 0.9-1.6 % low, as rung 5b's −1.1 % pressure-gradient
  error predicted.

**The conventional baseline,** the closed-form model with spreading, on the
12 non-refined cases:

| Error | Range |
|---|---|
| Peak | −2.6 to +3.8 K |
| Profile RMS | 0.4 to 5.3 K |
| Δp | −6.0 to +9.2 % |

- Its errors are about ten times the reference's own uncertainty. So the
  reference resolves what a better model would improve on.
- The baseline is worst at the screen edge, with a profile RMS of 5.3 K.
- It is best for mild, uniform cases, with a profile RMS of 0.4 K.

**Cost.**
- r = 2 cases took 849-1,545 s each, with ten cases sharing the host.
- r = 3 cases took 2,998-3,785 s.
- The batch took 5,175 s.
- One r = 2 case is about 0.4 core-hours at this sharing, about 7 minutes
  alone (rung 6e).

**Iterations.** Every case agreed between iterations 2,000 and 4,000 to
2e-7 K. So pools run at 2,000 iterations; the check then compares 1,000 with
2,000, and a case that has not converged by then is typed and rerun.

**Recommendation: PROCEED** to pools and baselines, within the scope D1-D8
already narrowed:
- every case ran OK, with exact checks;
- discretization is about a tenth of the baseline's error;
- the conventional method leaves a measurable margin for a learned model.

The open items are listed in the ticket. The readiness record carries them
once it is relayed (CHALLENGE-READINESS-RELAY-01).
