# Motor 1.8: how you're tested

Every value here is Carbon's published or registered value. Where Motor 1.8's
own value is not registered yet, the page says **HUMAN_INPUT**: it is filled
from the registered record before Motor 1.8 opens, and until then the version
does not grade. Where an earlier Motor version's published value is shown, it
is for reference only.

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

**Official TRAIN:** Motor 1.8 has its own TRAIN set: the 150 cases of the
earlier Motor TRAIN plus new rows inside the box, near the onset of
saturation and at zero current, so those regimes can be learned from public
data. Every row is planned to be solved again on Carbon's record-now route,
so that each one also carries the flux linkage of the three phases. Its name,
size and digest: **HUMAN_INPUT** (published at the TRAIN freeze). The grade trains your
recipe on this TRAIN only, never on your kit data.

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
  physics regression, a kernel fit on TRAIN plus extra solver data from
  inside the published limits (the kind of data the kit lets you make), the
  engineer's shortcut (torque per amp), and the nearest TRAIN row. The others
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
  advance, kept sealed.
- Your model predicts every candidate design, each on its own: a prediction
  must not depend on which other designs are in the batch. Carbon re-checks
  this; if your predictions change with the batch, design value is 0 for that
  grade.
- Only a sample of the candidates counts, drawn after your predictions, so
  you cannot know which designs count. The sample changes on a registered
  schedule (every **HUMAN_INPUT** days), and every grade in that period uses
  the same sample, so a king and a challenger are scored on the same designs.
- The designs are ranked by your predictions, with each design limit backed
  off by U, and your top five picks are looked up in the solved truths. A
  pick that truly breaks a limit scores 0. The five picks are weighted 0.4,
  0.25, 0.15, 0.12 and 0.08.
- The zero is the best of Carbon's classical picks on the same sample (and
  a random pick); the 1 is the best five picks possible from that sample. A design task's score is clipped to 0 to 1.
- The number of design tasks and the model-call budget per task:
  **HUMAN_INPUT** (set by the owner before the version opens).

**Hard gates on every answer.**

- The physics gates hold on every design your model answers, inside and
  outside the training range. Motor 1.8's gate list: **HUMAN_INPUT**.
- Speed and rebuild limits for Motor 1.8: **HUMAN_INPUT** (Motor 1.5: each
  design answered in at most 3.3 s on the validator's machine; 4 CPUs,
  16 GiB, build and inference up to 648 s each, 947 s in total).

**What you see:** your total and your status. Per-case and per-class results
are not shown, and the hidden sample rotates.

## 3. What we test

- **Graded outputs:** the torque curve at 60 rotor angles over one 15 degree
  period, read as mean torque and as torque ripple, the size of the torque
  swing (peak to peak, in N.m), so it stays well defined even near zero
  torque. Cogging, at zero current, is graded on that absolute swing in N.m,
  never as a fraction of the mean.
- **Back-EMF:** Motor 1.8 grades torque only (the training set may still
  carry the flux linkage, unscored) and back-EMF moves to Motor 1.9.
- **Reference uncertainty U:** Motor 1.8's registered values:
  **HUMAN_INPUT**. The published verify set carries mean torque 0.019 N.m
  and ripple fraction 0.15 (Motor 1.7's extended-shell U of record).
- **Outside the training range:** hidden classes include cases outside the
  training range. The kinds Motor 1.8 tests include saturation (current
  densities past where the iron starts to saturate), cross-saturation,
  and cogging at zero current. These cases count for the physics part, for the design menus
  and for the gates. Their extents are never published.
- **A model has to generalise.** A fit of any one dataset, yours included,
  is tested where that dataset does not reach.

## 4. Practice: the verify set

- Motor 1.8's verify set is published in this kit: 6 designs Carbon solved
  with its pinned reference, outside every sealed set. `verify` solves them
  on your machine and compares within U, so you can check your kit against
  Carbon's reference.
- The app's practice score for Motor 1.8 uses the same 6 designs and the
  grade's own measurement, labelled **practice (kit verify set)**. It checks
  the gates and accuracy within U. Design value and the minimums are not
  evaluated locally. A practice score is never comparable to a grade.

## 5. The crown

- Every graded total is shown rounded down to the Ladder step, so totals
  within one step show the same number.
- When a grade would take the crown, the validator rebuilds that model 10
  times on its own private seeds (never seed 0). Every rebuild must pass every
  gate and minimum, or there is no takeover. The challenger takes the crown
  only if its 10-rebuild average beats the king's average by more than the
  registered margin; within it, the king keeps the crown. An infrastructure
  failure is retried and never counts against you.
- Motor 1.8's margin: **HUMAN_INPUT** (registered before crowns open; until
  then takeovers are unavailable).
- To hold the crown a total must reach a floor, currently 0.05 (provisional,
  set by the owner); below it, no one holds the crown on Motor 1.8.
- While Carbon's crown re-score for design-menu versions is being built, a
  grade that would take the crown on Motor 1.8 is first held for review: your
  grade shows `crown_held_for_review`, the king keeps the crown, and your
  submission keeps its place in order. When Carbon releases it, it is decided
  as normal.
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
  inside your graph); Motor trains in float64; the official grade builds at
  seed 0.

Kit results can differ from Carbon's pinned reference, which alone grades.
Run `verify` first.
