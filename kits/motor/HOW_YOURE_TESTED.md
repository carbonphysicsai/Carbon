# Motor 1.7: how you're tested

Every value here is Carbon's published or registered value. Where Motor 1.7's
own value is not registered yet, it says **HUMAN_INPUT** (the Motor owner
supplies it before this page is published). Motor 1.5's published values are
shown beside them for reference; they are not Motor 1.7's until confirmed.

## 1. The internal range (the kit samples anywhere inside it)

| Input | Unit | Range |
|---|---|---|
| magnet_mm | mm | 1.5 to 4.0 |
| embrace | fraction of the pole pitch | 0.55 to 0.95 |
| airgap_mm | mm | 0.3 to 1.0 |
| slot_open_deg | degree | 1.0 to 6.0 |
| tooth_mm | mm | 2.5 to 5.0 |
| slot_bottom_mm | mm | 34.0 to 42.0 |
| current_density_a_mm2 | A/mm2 | 0.0 to 15.0 |
| current_angle_deg | degree | 0.0 to 60.0 |

**Constraint (buildable geometry, `carbon/motor/domain.py` `validity`):** the
slot is at least 1 mm wide where the coil starts, the slot opening is at
least 0.2 mm narrower than the slot behind it, and the slot is at least 1 mm
deep. About 91 % of the box is buildable.

**Fixed frame:** the GRUCAD 8-pole, 24-slot surface-PM machine's published
dimensions, single-layer winding of 104 turns per slot, magnet remanence 1.2 T,
stack length 35 mm. The iron is Brauer's law.

**Official TRAIN:** motor-dev-train-150-v1 (150 cases, unchanged from earlier
Motor versions). The grade trains your recipe on this TRAIN only, never on
your kit data.

## 2. All the rules

- **Score:** `TOTAL = 0.5 x A + 0.5 x D`, 0 to 1, higher is better
  (published). Motor 1.7's A rule (minimum or mean of in-range and
  out-of-range accuracy), the top-3 design rule and the honesty scale:
  **HUMAN_INPUT**.
- **Gates come first.** A failed gate means no score, however good the rest.
  Motor 1.5's published gates: `native_motor_valid`,
  `complete_fixed_coverage`, `physics_laws`, `schema_finite` (60 finite
  values), `motoring_mean_nonnegative`, `paired_repeat`, the physics gates on
  every answer in and out of range, and the speed gate. Gated law:
  mean torque positive wherever the current density exceeds 1 A/mm2. Motor
  1.7's gate list: **HUMAN_INPUT**.
- **Minimums:** each score part has a minimum set from Carbon's own
  baseline; below it the result is not eligible and the part is named. The
  values are not published.
- **Information budget:** everything in your graph that can carry a fitted
  number counts against one 32 KiB budget for the whole submission, by what
  it holds (a float by its real size, an integer by the bits its range
  needs, a boolean one bit, identical copies once), including the static
  values in your ops' parameters.
- **Speed gate:** each design answered in at most 1/500 of the reference
  solver's time for one design, median of single-design calls on the
  validator's machine: Motor 3.3 s per design.
- **Submission rules:** any finite learning rate; fitted constants only
  inside the budget; no trained or starting weights (no `initial_state`);
  everything trainable trains from scratch in Carbon's own training.
- **Build and training rules:** graphs on the open operation set (allowlist
  v8); Carbon standardises your targets, never your inputs (normalise inputs
  inside your graph); Motor trains in float64; the official grade builds at
  seed 0. Rebuild resources and time limits for Motor 1.7: **HUMAN_INPUT**
  (Motor 1.5: 4 CPUs, 16 GiB, build and inference up to 648 s each, 947 s
  in total).
- **Design value search:** Carbon's fixed CMA-ES asks your model for designs'
  outputs per target and the pick is looked up in solved truth. Motor 1.7's
  query budget: **HUMAN_INPUT** (Motor 1.5: 60 queries per target, first
  step 0.25 of the normalised design box).

## 3. What we test

- **Graded outputs:** the torque curve at 60 rotor angles over one 15 degree
  period, read as mean torque and ripple fraction (peak-to-peak over mean).
  Registered reference uncertainty (Motor 1.5): mean torque 0.0052 N.m,
  ripple fraction 0.026; Motor 1.7: **HUMAN_INPUT**.
- **Outside the training range:** part of the hidden exam lies outside the
  range above. It counts for accuracy, for design picks and for the gates.
  How far it extends is not published.
- **Region kinds and their rule:** the exam is balanced over region kinds:
  inside the training range; an inner band just outside it on every input;
  and one-sided regions, where a single input goes past one of its edges
  while every other input stays inside the training range. Each kind holds at
  least 3 hidden targets. Which sides have a one-sided region:
  **HUMAN_INPUT**. Extents are never published.
- **A model has to generalise.** A fit of any one dataset, yours included,
  is tested where that dataset does not reach.

Kit results can differ from Carbon's pinned reference, which alone grades.
Run `verify` first.
