# CHALLENGE-COLD-PLATE-01 — the cold plate as a DEVELOPMENT exam, ready for testing

**Status:** slices 1-4 complete; readiness record v6 (baselines MEASURED,
PROCEED). Under the Challenge Roadmap (OWNER-CHALLENGE-ROADMAP-01) this design is
prior work for laminar internal flow (f04) and steady conduction (f03).
**Primary Hub map_ref:** `CL-CP-01`, `HUB_UPDATE_REQUIRED`.
**Authority:** OWNER-CHALLENGE-DESIGN-01 (2026-10-01) and OWNER-DX-03, under
the design basis delegated by OWNER-BATTERY-V2-DISCLOSURE-01 items 10-12 and
the internal admission protocol OWNER-CHALLENGE-ADMISSION-01 (amended).
**Tracking:** carbonphysicsai/Carbon#342.

## Outcome

The AI-chip cold plate becomes an exam Carbon can test against, as battery's
exam-design campaign made battery one. Concretely, it is ready for testing
when all of the following exist and are recorded:

1. **A reference service.** It turns nine inputs into the outputs: a typed
   outcome, exact checks, a pinned image, no network. It is verified against
   the rungs.
2. **A pilot**, the shape #342 specifies: 8 ordinary and 4 difficult cases,
   with paired refinement of 4.
   - Every attempt, failure, cost and convergence result is recorded.
   - It ends in proceed, narrow or defer.
3. **A DEVELOPMENT population.**
   - Its sampling law and its frozen heat-map family are explicit and public.
   - Membership is computable by anyone.
4. **The four kinds of rule, kept separate:**
   - reference numerical checks;
   - candidate physical gates;
   - engineering feasibility constraints;
   - soft scores.
   An accurate prediction of a bad design is never rejected for describing
   one.
5. **Pools.**
   - Public TRAIN and PRACTICE data.
   - A private evaluation pool whose seed root never enters the repository.
6. **Baselines:** the closed-form (conventional) model and one learned model,
   scored by the exam on the private pool.
7. **The readiness record** for `chip-cold-plate`, updated from the evidence.

The miner-path integration is CHALLENGE-COLD-PLATE-02, the next ticket. It
covers the registry's move from RESERVED, the research workspace, practice
feedback and validator dispatch. That split is a real dependency: the
integration consumes this ticket's exam, pools and contract.

## Maturity ceiling

DEVELOPMENT, internal, non-paying. Nothing here is a qualified population,
tolerance, gate or production claim. No LIVE, reward, frontier or chain
authority. Not scientifically or security qualified. Every numeric choice
below is a provisional DEVELOPMENT value with its basis beside it.

## Decisions taken under delegation (recorded as they are made)

- **D1. Scope: the periodic interior of a straight-microchannel plate.**
  - It is the rungs' repeating cell: half a channel and half a fin between
    symmetry planes.
  - Headers, manifolds, plate edges, serpentines and heat-map variation
    across the channels are excluded. They need a multi-channel domain at
    about 50 times the cost.
  - They are the recorded v2 expansion.
- **D2. The heat map varies along the flow: an axial hot band.**
  - The finding behind it: with a uniform map, the textbook closed-form
    model lands within 0.1-0.35 K of the reference peak and 2-4 % of Δp at
    the nominal points. That leaves a learned model almost nothing to add.
  - A hot spot brings in base spreading, which the closed-form model ignores.
  - The map is a Gaussian on a uniform floor, normalized to the heat load:
    - peak-to-average ratio 1-3 (the design basis's "up to 3x");
    - centre 3-27 mm;
    - width σ 1.5-3.5 mm. The top of that range is the widest that still
      reaches 3x on a 30 mm die.
- **D3. Nine inputs:**
  - channel width, fin width and depth;
  - flow per kW, inlet temperature and heat load;
  - hot-spot ratio, centre and width.
  Ranges are the design basis's.
- **D4. The fluid model.**
  - PG25's viscosity, density and conductivity vary with temperature, from
    fits to the pinned CoolProp model over 30-99 °C.
  - Heat capacity is held at the inlet temperature. Letting it vary breaks
    the solver's exact energy conservation at the solid-fluid interface (rung
    7).
- **D5. Outputs.**
  - The reference reports five:
    - the heated face's peak and mean temperature;
    - its span-mean temperature over 30 one-millimetre segments along the
      flow;
    - the outlet bulk temperature;
    - the pressure drop.
  - **A model predicts three: peak, profile and pressure drop.** The mean is
    exactly the profile's mean, and the outlet is exactly the energy balance
    of the inputs. Grading them would grade arithmetic, so Carbon derives
    them.
  - The TIM is added after the solve and reported beside, never predicted.
- **D5a. The conventional baseline includes axial spreading.** The textbook
  one-dimensional model, without conduction along the flow, reads a 3x hot
  spot 27.6 K too hot (rung 7). With the copper section conducting along the
  flow (a fin equation), it reads 2.4 K too cold. A baseline that ignores
  spreading would flatter every learned model, and as the population screen
  it would exclude most strong hot spots.
- **D6. Population.**
  - Uniform over the box, admitted when the closed-form model's hottest wall
    is ≤ 95 °C and its Re ≤ 2,000. That is about 84 % of the box. The
    admitted share falls from 91 % to 74 % across the hot-spot ratio range,
    against 85 % to 25 % before the baseline modelled spreading.
  - The reference re-checks its own fluid (≤ 99 °C, the coolant model's
    end). A violation is REFERENCE_INVALID, charged to the reference.
- **D8. The exam's rules.** Each kind is in `carbon/cold_plate/exam.py`.
  - **Gates:** physical laws only.
    - The schema is finite and of the declared shape.
    - The face is above the inlet.
    - The peak bounds the profile.
    - The pressure drop is positive.
    - A hidden duplicate repeats.
    - `calibrate` refuses any gate that a sound reference fails.
  - **Score:** the mean of TRAIN-normalized peak error, profile RMS error and
    log pressure-drop error.
  - **Important region:** a reference peak of at least 85 °C, the upper third
    of the population. The signed peak error there is reported as an optimism
    diagnostic, following EV2.
  - **Feasibility:** die temperature through the TIM, and hydraulic power. It
    is a decision property and is never a gate.
- **D7. Reference numerical checks:**
  - mass imbalance ≤ 1e-6;
  - energy imbalance ≤ 1e-5, using the solver's own enthalpy flows;
  - iteration change between the half-way and final writes ≤ 1e-3 K and
    1e-5 relative in Δp.
  Each is at least 100 times looser than the rungs observed.

- **D9. Pools: 400 TRAIN, 100 PRACTICE and 200 private cases.**
  - The sizes follow battery's: 400 TRAIN cases in its construction contract;
    screening batches of 100; an exam rule verified on 200 private cases.
  - TRAIN and PRACTICE are public draws of the population, reproducible by
    anyone from their labels (`carbon.cold-plate.pools-v1.train` and
    `.practice`).
  - The private pool is drawn from a 32-byte root held by the operator,
    outside the repository, as HMAC-SHA256(root, label).
    - Only its commitment is published: `sha256:72ae0d2f6cf8b6a7e138aae93e8db986fd07862bf743725cbc4c290d0d433c2b`.
    - Its plan and records never enter the repository or rented compute.
  - Every case runs 2,000 iterations. The pilot agreed between 2,000 and
    4,000 to 2e-7 K.
- **D10. The public pools were solved on rented CPU pods; the private pool
  on the owner's host only** (CHALLENGE-POOLS-CLOUD-01, under the owner's
  grant of 2026-10-02).
  - 308 TRAIN cases ran natively in the pinned OpenFOAM image on a RunPod CPU
    pod. The native results agree with the container to 1.7e-13 K.
  - `assemble.py` built each pool from every run that solved its cases.
  - This was a decision about compute only; no case changed.
- **D11. The learned baseline's declared grid is widened before the private
  pool is scored.**
  - On the original grid (lengths 0.25 to 2, ridges 1e-8 to 1e-2), PRACTICE
    chose length 2 and ridge 1e-2, both at the grid's edge. The search was
    truncated there, and the learned model barely beat the closed form on
    PRACTICE (0.119 against 0.120).
  - The shared grid is now lengths 0.25 to 16 and ridges 1e-8 to 1, which
    puts the optimum inside it. Length and ridge trade off along a flat
    valley at about 0.099.
  - `select` now reports a choice on an edge (`at_edge`), so a truncated
    search shows in the report.
  - **Disclosure.** Before this change, a dry run of the baseline script
    scored the 83 private cases then finished with the original grid. The
    change was decided from the PRACTICE grid alone. The private pool is
    scored once more, in full, with the declared grid.
  - The motor shares the module. Its baselines are scored with the same
    widened grid.

## Pools and baselines (slice 4)

Evidence is in `docs/development/evidence/cold-plate-pools-v1/`: the public
pools, `pools.json` and `baselines.json`, which holds aggregates only.

- **Pools.** All 700 cases are OK:
  - 400 TRAIN, of which 308 were solved on a RunPod CPU pod (D10);
  - 100 PRACTICE;
  - 200 private cases from the operator-held root (D9), solved on the
    owner's host only.
- **Exam.**
  - Every gate holds on every reference of every pool. The smallest TRAIN
    margins are a face 3.7 K above the inlet, and a peak 6e-4 K above the
    hottest profile segment.
  - The scales come from TRAIN alone: peak 10.6 K, profile
    11.5 K, log pressure drop 0.837.
- **Baselines**, scored through the exam (lower is better):

  | | PRACTICE | Private | Private peak | Private profile | Private pressure | Private important region |
  | --- | --- | --- | --- | --- | --- | --- |
  | Conventional closed form (axial spreading) | 0.120 | 0.109 | 0.138 | 0.149 | 0.041 | 0.143 |
  | Kernel ridge (length 8, ridge 1e-06) | 0.099 | 0.105 | 0.118 | 0.182 | 0.016 | 0.141 |

- **The generic learned model barely beats the conventional one, and is
  worse on the profile.**
  - With axial spreading modelled (D5a), the closed form is a strong
    baseline. 400 samples in nine inputs are too few for a model that knows
    nothing of the physics to do much better.
  - So a useful surrogate here has to beat a physics-aware baseline. A
    learned correction to the conventional model is the natural next
    baseline. That is new design, and it waits for the family's turn in the
    challenge pipeline.
- **Dry-run disclosure (D11).** Before the grid was widened, a dry run
  scored the first 83 private cases: closed form 0.115, kernel ridge on the
  original grid 0.101. The final scores above use the declared grid, once,
  on all 200.
- **Reproducibility.** A test reproduces the PRACTICE scores and the scales
  from the committed public pools.

## Slices

1. Rung 6e (merged separately as #484, an independent rung) and rung 7: the
   package reference against the rungs.
2. `carbon/cold_plate/` `domain`, `analytic`, `openfoam`, `analysis` and
   `population`, plus `scripts/dev/cold_plate/reference/`, with tests.
3. The pilot. Its readiness record, v5 (PILOTED, PROCEED), is held for one
   batched relay with the motor and photonic records
   (CHALLENGE-READINESS-RELAY-01).
   - **Why it is held.** The Pilot Designer relays each Challenge's latest
     record, and the owner-approved Ask Carbon release pins the Pilot
     Designer's bytes. So a record bump needs an Ask Carbon candidate
     reconciliation, and one is better than three.
4. Pools, the exam (gates, feasibility, scores), baselines, and the readiness
   record.

## Out of scope

The miner path (CHALLENGE-COLD-PLATE-02), paid compute beyond the owner's grant
of 2026-10-02, any mainnet path,
and scientific or launch acceptance, which stays human-reserved.
