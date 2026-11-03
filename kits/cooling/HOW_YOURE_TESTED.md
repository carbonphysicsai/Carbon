# Cooling 1.8: how you're tested

Every value here is Carbon's published or registered value. Where Cooling
1.8's own value is not registered yet, it says **HUMAN_INPUT** (the Cooling
owner supplies it before this page is published). Cooling 1.6's published
values are shown beside them for reference; they are not Cooling 1.8's until
confirmed.

## 1. The internal range (the kit samples anywhere inside it)

| Input | Unit | Range |
|---|---|---|
| channel_width_mm | mm | 0.2 to 0.5 |
| fin_width_mm | mm | 0.2 to 0.5 |
| channel_depth_mm | mm | 1.0 to 3.0 |
| flow_lpm_per_kw | L/min per kW | 1.25 to 2.0 |
| inlet_c | C | 30.0 to 45.0 |
| heat_load_w | W | 500 to 1500 |
| hotspot_ratio | peak to average | 1.0 to 3.0 |
| hotspot_center_mm | mm along the flow | 3.0 to 27.0 |
| hotspot_width_mm | mm | 1.5 to 3.5 |

**Constraint (the population's screen, `carbon/cold_plate/population.py`):**
a case belongs when the public closed-form model keeps the hottest wetted
wall at most 95 C (the PG25 coolant model ends at 99 C) and the Reynolds
number at most 2,000 (laminar). The reference then checks its own fluid: a
solved case whose coolant passes 99 C, or whose flow leaves the laminar range,
is out of applicability and is dropped, never scored.

**Fixed plate:** a copper plate on a 30 x 30 mm heated footprint with straight
parallel channels; coolant 25 % propylene glycol (PG25) with temperature-
dependent properties; heat capacity held at its inlet value. The thermal
interface resistance is fixed at 5e-6 m2 K/W: not an input and not predicted;
Carbon applies it when it turns your outputs into the die temperature.

**Official TRAIN:** cooling-dev-train-400-v2-encoded (400 cases, the
law-safe encoded layout). The grade trains your recipe on this TRAIN only,
never on your kit data.

## 2. All the rules

- **Score:** `TOTAL = 0.5 x A + 0.5 x D`, 0 to 1, higher is better
  (published). Cooling 1.8's A rule (minimum or mean of in-range and
  out-of-range accuracy), its top-3 design rule and its honesty scale:
  **HUMAN_INPUT**.
- **Gates come first.** A failed gate means no score, however good the rest.
  Cooling 1.6's published gates: `native_cold_plate`,
  `complete_grid_common_mask`, `selected_design_verified_feasible`,
  `physics_laws`, `schema_finite` (peak, the 30-value profile and the
  pressure drop are finite), `face_above_inlet`, `peak_bounds_profile`,
  `pressure_drop_positive`, `paired_repeat`, the physics gates on every
  answer in and out of range, and the speed gate. Gated laws: the peak is at
  least the profile, the profile is above the inlet, the pressure drop is
  positive. Cooling 1.8's gate list: **HUMAN_INPUT**.
- **Limits (Cooling 1.6, published):** die peak at most 100 C, hydraulic
  power at most 0.25 W. Cooling 1.8: **HUMAN_INPUT**.
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
  validator's machine: Cooling 2.84 s per design.
- **Submission rules:** any finite learning rate; fitted constants only
  inside the budget; no trained or starting weights (no `initial_state`);
  everything trainable trains from scratch in Carbon's own training.
- **Build and training rules:** graphs on the open operation set (allowlist
  v8); Carbon standardises your targets, never your inputs (normalise inputs
  inside your graph); Cooling trains in float64; the official grade builds at
  seed 0. Rebuild resources and time limits for Cooling 1.8: **HUMAN_INPUT**
  (Cooling 1.6: 4 CPUs, 16 GiB, build and inference up to 648 s each, 947 s
  in total).
- **Design value search:** Carbon's fixed CMA-ES asks your model for designs'
  outputs per target and the pick is looked up in solved truth. Cooling 1.8's
  query budget: **HUMAN_INPUT**.

## 3. What we test

- **Graded outputs:** the peak face temperature, the 30-segment profile and
  the pressure drop, read as the die peak temperature (through the fixed
  thermal interface) and the hydraulic power. Registered reference
  uncertainty (Cooling 1.6): die peak 0.037 C, hydraulic power 3 % of the
  value; Cooling 1.8: **HUMAN_INPUT**.
- **Outside the training range:** Cooling 1.8 is the first Cooling version
  with exam cases outside the range above. They count for accuracy, for
  design picks and for the gates. How far they extend is not published.
- **Region kinds and their rule:** the exam is balanced over region kinds:
  inside the training range; an inner band just outside it; and an outer
  shell beyond the inner band. Each kind holds at least 3 hidden targets.
  Extents are never published.
- **A model has to generalise.** A fit of any one dataset, yours included,
  is tested where that dataset does not reach.

Kit results can differ from Carbon's pinned reference, which alone grades.
Run `verify` first.
