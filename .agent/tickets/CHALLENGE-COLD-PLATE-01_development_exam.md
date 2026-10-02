# CHALLENGE-COLD-PLATE-01 — the cold plate as a DEVELOPMENT exam, ready for testing

**Status:** in progress.
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

The miner path (CHALLENGE-COLD-PLATE-02), any paid compute, any mainnet path,
and scientific or launch acceptance, which stays human-reserved.
