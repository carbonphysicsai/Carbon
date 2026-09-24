# Exam-design campaign 1: specification

**Owner direction, 2026-09-24:** prepare, implement and execute the first bounded
exam-design research campaign, up to **USD 20** of RunPod charges (or the account
balance minus USD 2, whichever is lower).

**What this authorizes:**
- The named **public/synthetic DEVELOPMENT** campaign.

**What it does not authorize:**
- Resuming paused campaigns.
- Chain writes or reward changes.
- A new official exam.
- Publishing testnet weights.

Nothing here is `SCIENTIFICALLY_QUALIFIED`, `SECURITY_QUALIFIED` or
`PRODUCTION_QUALIFIED`, and no result of this campaign can make it so.

**Execution class, in the words every result must carry:** *direct execution
inside the pinned study image plus a hash-locked wheel overlay; not
`validator_launch`; containment from the provider's runtime.* It is research
execution, not validator isolation acceptance.

## The questions, in plain English

1. **Training data.** How many public training cases does a competent model
   need before more data stops paying for itself?
2. **Screening cases.** How many cases must a screening batch hold for a
   ranking to be stable enough to act on?
3. **Rotation.** After how many scored submissions should a screening batch be
   replaced, so that scores cannot be steered by repeated probing?
4. **Screening validity.** Does a model that screens well also do better on
   fresh cases it has never been scored on?
5. **Reconstruction variability.** How much does retraining the same recipe
   (other seeds; the same seed again) move scores, and does that flip decisions?
6. **Cost.** What do a reference case, a screening pass and a finalist
   comparison actually cost on the declared hardware?
7. **Gates.** Do the published gates reject the failures that matter, and only
   those, without failing correct predictions of unsafe conditions?

The campaign does not optimize for producing a winner.

## Challenges

### Primary: battery charging and degradation

**The reference.** Defined in `scripts/dev/exam_design/battery_reference.py`, `SPEC`:
- PyBaMM 26.8.0.0 `DFN`, with solvent-diffusion-limited SEI, partially
  reversible lithium plating, porosity change for both, and lumped thermal.
- The `OKane2022` parameter set, unmodified: ageing parameters are not scaled.
- IDAKLU solver at rtol 1e-5 / atol 1e-7, with 20 points per mesh domain.

**The inputs**, drawn uniformly within bounds:

| Input | Range |
|---|---|
| First-stage charge rate `c1` | 0.5–2.0 C |
| Second-stage rate `c2` (from 4.0 to 4.2 V) | 0.2–1.0 C |
| Ambient = initial temperature | 5–40 °C |
| Initial state of charge | 0.05–0.5 |

**The protocol.** Each cycle is:
1. Two-stage constant-current charge.
2. 4.2 V hold to C/20.
3. 10 min rest.
4. 1C discharge to 2.5 V.
5. 10 min rest.

Cycle 1 opens with a 2 min rest, so its first sample is an equilibrium state.

**The required outputs:**
- Voltage and temperature every 30 s over the first 3600 s.
- The **plating margin**: the minimum cycle-1-charge lithium plating reaction
  overpotential on the negative electrode. A negative value means the model
  reached plating conditions.
- Discharge capacity at declared checkpoint cycles.

**The horizon** (cycle count and checkpoints) is chosen from the pilot's measured
runtime and its refinement comparisons. The rule, fixed now: the longest horizon
that meets both conditions.
- **Cost:** it fits the per-case cost allowed by the run matrix.
- **Signal:** its capacity-change signal exceeds the pilot's refinement
  (mesh + tolerance) disagreement in the majority of pilot cases.

**What agreement means.** Agreement is with the specified model. It is **not**
validation of real-cell lifetime, plating or safety.

**Measured before this specification was written, locally:**
- *Model choice.* SPMe failed the cold 2C corner, so it was rejected in favour
  of DFN.
- *Where the uncertainty is.* Solver tolerance changes the outputs by less than
  0.02 mAh, while doubling the mesh changes cold-case fade by about 0.56 mAh.
  The mesh is where the reference uncertainty lives.
- *Capacity is not monotone.* In cold, fast cases, capacity rises across early
  cycles in the reference, so no monotonic-fade gate is defined.

### Secondary: passive reciprocal 3D photonic coupler

The secondary challenge is feasibility first:
- one bounded geometry family, one material model and one port convention;
- a pinned `fdtdx` configuration;
- a complex port response over a declared wavelength band.

A geometry and its spectrum count as **one** parent case. If it cannot fit
memory, reference accuracy or budget, its feasibility results are kept and the
campaign concentrates on battery. **A 2D substitute is never reported as 3D
success.**

### Control: public Burgers development evidence

The existing C-W1 development evidence exercises the pool, rotation and
comparison machinery before any new Burgers runs are commissioned. No new
Burgers references are generated in this campaign.

## Data boundaries

| Role | Visibility | Use |
|---|---|---|
| `train` (TRAIN v1) | public, fixed per challenge version | the **only** data every reconstructed recipe trains on |
| `practice` | public | research, the learning curve, tolerance calibration |
| `screen-B00…` | private until retired | screening batches; published once retired and dependent jobs close |
| `final` | private | fresh finalist comparison cases, never used in screening |
| `verify` | private, sealed | opened only after the exam rule and success criteria are recorded |
| `pilot` | public | reference cost and uncertainty only |

**How cases are drawn.**
- Each role's seed is `sha256("carbon.exam-design.battery.2026-09-24/<role>")`,
  truncated to 32 bits (`plans.py`).
- Separate seeds are **not** semantic decontamination: every role samples the
  same distribution, so the report gives nearest-neighbour distances between
  roles.

**How data enters TRAIN.**
- Retired batches enter TRAIN only through a named version update
  (`exam.TrainVersions.publish`).
- The campaign reports what that update would change, but does not silently
  retrain on it.

**Hidden probes.**
- Screening batches carry hidden duplicate cases for the paired-repeat gate.
- A duplicate counts once as a physical case.

## Gates

Gates are published with their formula, tolerance rule, where they apply and
which outputs they need (`gates.py`).

**How they run.**
- Every gate runs on every screening and final case.
- The gates use the same stored predictions the score uses.

**How cases are typed** before and during gating:

| State | Meaning |
|---|---|
| `REFERENCE_INVALID` | the reference failed or failed its self-check; the case is withdrawn for everyone |
| `FAILED_INFRA` | the prediction is missing because a worker failed; not scientific, not scored |
| `GATE_FAILED` | a mandatory gate failed |
| `SCORABLE` | all applicable gates passed |

**One gate failure makes a submission ineligible.** Soft performance does not
compensate for it.

| Gate | Formula | Tolerance, derived from reference evidence only |
|---|---|---|
| `schema_finite` | outputs present, shaped and finite | exact |
| `initial_voltage` | \|V̂(0) − OCV(soc0)\| ≤ τ | max(2 × max reference discrepancy, 32 float32 ulp at 4.2 V) |
| `initial_temperature` | \|T̂(0) − T_amb\| ≤ τ | max(2 × max reference discrepancy, 32 float32 ulp at 40 °C) |
| `voltage_ceiling` | max V̂ ≤ 4.2 V + τ | max(2 × max reference overshoot, 32 ulp); the cycler controls this limit, so it is not a safety limit |
| `voltage_floor` | min V̂ ≥ 2.5 V − τ | as above |
| `capacity_bound` | 0 < Q̂ ≤ Q_bound | the smallest of electrode and lithium-inventory capacity, taken from the parameter set |
| `paired_repeat` | a hidden duplicate predicts identically | 32 float32 ulp |

**Deliberately not gated:**

| Not gated | Why |
|---|---|
| Non-negative heat | entropic heat is signed |
| Temperature ≥ ambient | entropic cooling |
| Plating margin or temperature limit | correctly predicting an unsafe crossing must never fail |
| Charge conservation | current is not a required output, so conservation cannot be established from the outputs |
| Monotone capacity fade | the reference is not monotone |

**The photonic gates** are to be defined with the reference:
- **Passivity:** Σ_i |S_ij|² ≤ 1 + τ.
- **Reciprocity:** S_ij = S_ji within τ.

Both use one normalization (mode-overlap power over the source's injected power
at each wavelength), and τ is calibrated from mesh refinement.

## Score

The case error is the mean of four normalized components:
- voltage RMS;
- temperature RMS;
- plating-margin absolute error;
- capacity RMS over checkpoints.

Each component is divided by its standard deviation over TRAIN v1, which is
published with the dataset (`scoring.py`). Lower is better. The score is bound to
this challenge version and is not comparable across challenges.

**The important region** holds cases whose *reference* plating margin is at or
below 20 mV, or whose peak temperature is at or above 45 °C. These cases are
scored like any other and reported separately.

## Screening and rotation

**Screening.**
- Batches of **200** cases are prepared. The 50- and 100-case settings use
  nested prefixes of the same batches, so the comparisons share cases and are
  paired.
- **Three batches are active.** Each screening score covers the whole active pool
  and is recorded with its `pool_version`.
- Stored models are **inferred** on an incoming batch. They are never retrained
  because the pool changed.

**Rotation.**
- The rotation schedules studied retire the oldest batch after **1, 3 or 10**
  admitted submissions.
- At least three replacements are exercised for the selected schedule.
- Replay advances the schedule immediately. **Accelerated replay does not
  establish a calendar interval**; the report translates exposure into days only
  under stated traffic assumptions.
- Replay does not measure adaptive agent behaviour. No model-provider budget
  exists, so the adaptive-agent extension is prepared and reported as unrun.
  Scripted candidates are not autonomous miners.

## Final comparison

**Frozen before final inputs reach any prediction worker:**
- the recipes;
- the incumbent's identity and score;
- the comparison rule (`exam.ComparisonRule`, `exam.final_compare`).

**How it runs.**
- The incumbent and the challenger are reconstructed on TRAIN v1 under matched
  budgets, with matched seeds.
- Model state is frozen before final inputs are released.
- Both are scored on the same fresh `final` cases.

**The test.** Paired per-case differences are bootstrapped over cases. The
seed-averaged error is used when several seeds exist. The equivalence margin is
set from the measured seed-to-seed variability, not from any favoured result.

**The five outcomes:** `IMPROVEMENT`, `REGRESSION`, `TRADE_OFF`, `NO_IMPROVEMENT`
and `INSUFFICIENT_EVIDENCE`.
- An overall gain with an important-region regression is a `TRADE_OFF`, not an
  improvement.
- A challenger that fails a gate on the final cases is a `REGRESSION`.

## Recipes and controls

| Role in the study | Recipe |
|---|---|
| simple baseline | inverse-distance k-nearest-neighbour over normalized inputs, with the published boundary projections |
| competent learned baseline | MLP on normalized inputs with structural boundary conditions (exact V(0), T(0), V ≤ 4.2 V) |
| candidate intended to improve | the same, plus physics-motivated features (Arrhenius 1/T, log rates), PCA trajectory heads and weight decay |
| localized-regression control | the candidate trained with important-region cases down-weighted |
| overfitting control | *authored*: returns exposed screening references verbatim, and baseline elsewhere |
| faulty outputs | *authored* synthetic controls: NaN, wrong shape, voltage overshoot, initial-state offsets, capacity above the bound, nondeterminism, a time shift |
| negative controls | the reference itself as a prediction, which must pass every gate, including on cases that reach plating or sub-ambient temperature |

- **Authored outputs** are synthetic controls, never trained-model results.
- **Seeds.** Three seeds are used for each competent recipe, plus one same-seed
  repeat under the pinned XLA configuration. Three seeds are diagnostic evidence,
  not a promotion-reliability guarantee.

## Run matrix and accounting

**The ceiling** is fixed at campaign start:
- `cap = min(USD 20, balance − USD 2)`, recorded in
  `docs/development/evidence/exam-design-2026-09-24/accounting/ledger.jsonl`.
- **No top-up and no billing change.**

**Each pod:**
- **Budget check first.** It is refused unless all three hold:
  - the committed spend, plus this pod's full-deadline cost, plus a USD 0.25
    cleanup reserve, stays under the cap;
  - the A40 Secure rate is at most USD 0.49/hr;
  - no other pod exists.
- **Recorded the moment it exists.** Its identity is persisted as soon as the
  create call returns.
- **Bounded three ways.** A local watchdog terminates it at its deadline, the pod
  also terminates itself one minute later, and admission of new jobs stops a set
  export margin before the deadline.

**Stages** (counts after the pilot are fixed from its measured costs, not
assumed):

| Stage | Content | Allocation |
|---|---|---|
| 1 Pilot | battery: 12 LHS cases at 40 cycles (per-cycle capacity), 4 refinement comparisons; photonics: up to 12 cases + 4 refinements, or stop at the first infeasibility | USD 4 |
| 2 References | TRAIN / PRACTICE / SCREEN / FINAL / VERIFY at the pilot-chosen horizon, plus refinement comparisons on a sample | pilot-derived |
| 3 Reconstruction | learning curve on nested TRAIN subsets; three seeds for each competent recipe; one same-seed repeat; predictions for every role | pilot-derived |
| 4 Settings | batch sizes 50/100/200, rotation after 1/3/10, pool replay, statistical simulations | CPU only, no rental |
| 5 Freeze & verify | record the rule and criteria, then open `verify` | CPU only |

**Stopping rules:**
- Stop admitting work when the next pod cannot fit under the cap with its reserve.
- Stop a stage early when its question is answered.
- Stop and report if the A40 is unavailable at USD 0.49/hr; do not substitute
  hardware.
- A refusal or a reference failure is a result, and is recorded.

## What this campaign cannot establish

- A rare false-promotion rate.
- A real-world rotation interval.
- Adaptive-agent behaviour.
- Real-cell validity.
- Validator isolation.

**The simulations** state their assumptions separately from measured results.
**Verification** is fresh evidence only if the rule is not changed after it is
opened; if the rule changes, that set becomes development evidence.
