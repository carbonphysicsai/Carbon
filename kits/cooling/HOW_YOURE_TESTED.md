# Cooling 1.8: how you're tested

Every value here is Carbon's published or registered value. Where Cooling
1.8's own value is not registered yet, the page says **HUMAN_INPUT**: it is
filled from the registered record before Cooling 1.8 opens, and until then
the version does not grade. Where an earlier Cooling version's published value
is shown, it is for reference only.

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

**Official TRAIN:** Cooling 1.8 has its own TRAIN set: the 400 cases of
cooling-dev-train-400-v2-encoded (the law-safe encoded layout) plus new
solved rows. Its name, size and digest: **HUMAN_INPUT** (published at the
TRAIN freeze). The grade trains your recipe on this TRAIN only, never on your
kit data.

## 2. How you're scored

`TOTAL = 0.5 x physics + 0.5 x design value`, 0 to 1, higher is better.
Gates come first: a failed gate means no score, however good the rest.

**The physics part: how much of the room above classical methods you fill.**

- Carbon tests your model on hidden cases grouped into classes, most of them
  outside the training data (section 3).
- For each class and output, your error on every case is measured in units
  of the reference uncertainty U and floored at 1 U (the reference cannot
  resolve better than its own uncertainty). The class error E is the
  geometric mean of those case errors, so one wild case cannot dominate.
- The anchor A is the error of the best classical method Carbon could build
  for that class, measured the same way on the same hidden cases. The class
  scores `S = ln(A / E) / ln(A)`, clipped to 0 to 1: **0 = the best classical
  surrogate we could build for this case class; 1 = reference accuracy.** Each
  halving of the error is worth the same.
- Carbon's classical panel: Gaussian process, polynomial ridge, RBF ridge,
  gradient boosting, nearest neighbours, kernel ridge with a prior, sparse
  physics regression, a kernel fit on as much data as the kit can generate,
  the engineer's shortcut (the published closed-form correlations and fin model), and the nearest TRAIN row. All
  are trained on the public TRAIN set only.
- A class is scored only if it passes Carbon's admission checks, chief among
  them that the best classical method still misses reference accuracy by a
  wide margin there. Classes that fail are not scored. How many classes are scored in each family: **HUMAN_INPUT**
  (counts published when the version opens).
- The physics part is the mean of the scored families, each weighted
  equally; a family is the mean of its scored classes.

**In-range accuracy is a gate, not points.**

- Your accuracy inside the training range must clear a threshold, or the
  result is not admitted. Clearing it by more earns nothing extra.
- The threshold: **HUMAN_INPUT** (set by the owner; until it is set, the
  version does not open).

**Design value: picking the best designs from a menu.**

- For each design task Carbon solves a large set of candidate designs in
  advance, kept sealed. Each scoring round draws a fresh sample of them.
- Your model predicts every design in the sample, each on its own: a
  prediction must not depend on which other designs are in the batch.
- The designs are ranked by your predictions, with each design limit backed
  off by U, and your top five picks are looked up in the solved truths. A
  pick that truly breaks a limit scores 0. The five picks are weighted 0.4,
  0.25, 0.15, 0.12 and 0.08.
- The zero is the best of Carbon's classical picks on the same sample (and
  a random pick); the 1 is the best five picks any model could make from that
  sample. A design task's score is clipped to 0 to 1.
- The number of design tasks and the model-call budget per task:
  **HUMAN_INPUT** (set by the owner before the version opens).

**Hard gates on every answer.**

- The physics gates hold on every design your model answers, inside and
  outside the training range. Cooling 1.8's gate list: **HUMAN_INPUT**.
- Speed and rebuild limits for Cooling 1.8: **HUMAN_INPUT** (Cooling 1.6:
  each design answered in at most 2.84 s on the validator's machine; 4 CPUs,
  16 GiB, build and inference up to 648 s each, 947 s in total).

**What you see:** your total and your status. Per-case and per-class results
are not shown, and the hidden sample rotates.

## 3. What we test

- **Graded outputs:** the peak face temperature, the 30-segment profile and
  the pressure drop, read as the die peak temperature (through the fixed
  thermal interface) and the hydraulic power.
- **Reference uncertainty U:** Cooling 1.8's registered values:
  **HUMAN_INPUT** (Cooling 1.6: die peak 0.037 C, hydraulic power 3 % of the
  value).
- **Outside the training range:** the exam includes an inner band just
  outside the training range and an outer shell beyond it. Cooling 1.8 is the
  first Cooling version with exam cases outside the training range. These
  cases count for the physics part, for the design menus and for the gates.
  Their extents are never published.
- **A model has to generalise.** A fit of any one dataset, yours included,
  is tested where that dataset does not reach.

## 4. Practice: the verify set

- Cooling 1.8's verify set (a few designs Carbon solved with its pinned
  reference, outside every sealed set): **HUMAN_INPUT** (published in this
  kit after its digest is receipted). Until then `verify` refuses.
- Once it is published, `verify` solves those designs on your machine and
  compares within U, and once the app registers it, the app's practice score
  for Cooling 1.8 uses the same designs and the grade's own measurement, labelled **practice (kit
  verify set)**. It checks the gates and accuracy within U. Design value and
  the minimums are not evaluated locally. A practice score is never
  comparable to a grade.

## 5. The crown

- Every graded total is shown rounded down to the Ladder step, so totals
  within one step show the same number.
- When a grade would take the crown, the validator rebuilds that model 10
  times on its own private seeds (never seed 0). Every rebuild must pass every
  gate and minimum, or there is no takeover. The challenger takes the crown
  only if its 10-rebuild average beats the king's average by more than the
  registered margin; within it, the king keeps the crown. An infrastructure
  failure is retried and never counts against you.
- Cooling 1.8's margin: **HUMAN_INPUT** (registered before crowns open; until
  then takeovers are unavailable).
- To hold the crown a total must reach a floor, currently 0.05 (provisional,
  set by the owner); below it, no one holds the crown on Cooling 1.8.
- Make your graph robust to the seed: a model that trains well only at seed
  0 can fail the average.

## 6. Rules for your graph

- **Minimums:** each score part has a minimum set from Carbon's own
  baseline; below it the result is not eligible and the part is named. The
  values are not published.
- **Information budget:** everything in your graph that can carry a fitted
  number counts against one 32 KiB budget for the whole submission, by what
  it holds (a float by its real size, an integer by the bits its range
  needs, a boolean one bit, identical copies once), including the static
  values in your ops' parameters.
- **Submission rules:** any finite learning rate; fitted constants (from any
  source, including the public TRAIN set) only inside the budget; no trained
  or starting weights (no `initial_state`); everything trainable trains from
  scratch in Carbon's own training.
- **Build and training rules:** graphs on the open operation set (allowlist
  v8); Carbon standardises your targets, never your inputs (normalise inputs
  inside your graph); Cooling trains in float64; the official grade builds at
  seed 0.

Kit results can differ from Carbon's pinned reference, which alone grades.
Run `verify` first.
