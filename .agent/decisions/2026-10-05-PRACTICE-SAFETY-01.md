## 2026-10-05 — PRACTICE-SAFETY-01: decision-value safety metrics beside the practice score

**Authority.** Owner decision A8, relayed by the Test Lead on 2026-10-05, who
approved the spec
(`.agent/tickets/PRACTICE-SAFETY-01_decision_value_feedback.md`, FINAL). The
Test Engineer builds it. The decisions below are engineering decisions within
that spec, recorded by the executor. No score, gate, rule, tolerance,
threshold or EV study changes. Every limit, band and window used is one the
ticket names.

### D1. One shared allow-list, one module per Challenge

`carbon/practice_safety_feedback.py` holds the document schema
(`carbon.practice-safety-feedback.v1`), the labels and the allow-list check.
`carbon/{battery,cold_plate,motor}/practice_safety.py` each compute their
Challenge's metrics from the public PRACTICE references and the worker's
predictions, and declare their allow-list. `document` refuses any field,
label or value type the Challenge does not declare: only counts, rates,
signed means, the declared labels and `feedback_only: true` can leave. Labels
are fixed literals, so no free text (and so no case id) can be carried.

### D2. Limits and bands are copied, bound by tests, never read at run time

The ticket names sources that also hold protected material: EV4's contract
holds EV4's conditions, and the two synthetic studies hold their designs and
conditions. So the metric code never opens them. It carries a copy of only
what it needs (EV4's objective, constraint thresholds and reference bands;
the cooling die and hydraulic limits; the motor torque and ripple limits),
and a test asserts each copy equals its source. A change to a source fails
the test instead of silently diverging.

### D3. Battery reimplements the value modules' few lines over `decision`

The ticket defines B1, B2 and B3 by `value.false_acceptance.component`,
`value.admissibility.near_optimism` and `value.margins._margins`. Those
modules import `value.scoring`, the private scoring-set module, which the
ticket's import-graph check forbids. So `battery/practice_safety.py`
reimplements their arithmetic over `value.decision` (which imports nothing),
and a test proves the results equal the value modules' on the 200 practice
references for every constructed control.

### D4. Missing or invalid data

- A prediction is UNMEASURED when it is missing or fails the Challenge's own
  validity check: battery's finite, grid-shaped voltage and temperature and a
  finite plating margin; cooling's and motor's exam gates, as
  `customer_decision.quantities` refuses a gate-failing prediction.
- Any UNMEASURED practice case makes every computed metric `null`. A model
  never looks clean by omission.
- `unresolved` counts reference verdicts excluded, one per case and
  constraint: battery's references inside EV4's band of a limit; cooling's
  and motor's references that fail validity (none in the committed sets).

### D5. Metric details the ticket leaves to the build

- Battery B1's worst constraint is the highest rate, ties to the later name,
  as `false_acceptance.component` breaks them. B2 shows the value only.
- Cooling quantities are `exam.feasibility`'s, the function Track B's
  `customer_decision.quantities` uses. C3's sign label says negative is
  optimistic: a model that reads cooler than the reference is optimistic.
- Motor reference quantities are `derived.mean_nm` and `ripple_pk_pk_nm`.
  The ripple fraction is `ripple / mean` for a positive mean and infinite
  otherwise, `customer_decision`'s definition (the ticket's `|mean|` differs
  only for a non-positive mean, which is infeasible either way). Each motor
  metric says `n = 30` beside its counts.
- Cooling and motor metrics carry `"uncertainty": "no uncertainty band
  applied"`.

### D6. B4 is BLOCKED

`DECISION_SET_PATH` is None, and B4 reports `"BLOCKED: practice decision set
not committed"` (the ticket's B4 section; its output example says
"registered", and the ruled text is used). Nothing is fabricated.

**Separation (Test Lead ruling, 2026-10-05, correcting the ticket's
wording).** A practice decision condition is TOO CLOSE, and refused, when it
is within BOTH bounds of any EV1, EV2, EV4 or EV5 condition or point on
EV4's protected optimizer grid: |dt_amb| < 2 degC AND |dsoc0| < 0.03. It is
allowed when it is at least that far away in at least one dimension.
`decision_set_clear` implements this. The ticket's literal wording (at least
2 degC AND at least 0.03 from every condition) had no solution inside the
published box, because EV4's optimizer grid is 2.06 degC apart in t_amb;
the ruled reading leaves 8,422 workable points on a 0.1 degC x 0.001 grid.
The check runs against every committed EV contract's conditions and EV4's
and EV5's protected grids, a superset of the ruled list. Tests cover a point
inside both bounds (refused), a point outside in one dimension only
(allowed), the 8,422 count, and a mutant that restores the
AND-of-separations reading (killed).

### D7. Versioning and the official path

- Practice feedback schemas move to v2 for all three Challenges
  (`carbon.{battery,cold-plate,motor}.practice-feedback.v2`). v2 is v1 plus
  the `safety` block. `feedback(...)` without `safety` still returns exactly
  the v1 shape and schema, so a stored v1 result keeps its meaning and a
  caller that passes no safety block never claims v2.
- Only the three practice providers call the safety code, each once inside
  its practice trial. Tests check that statically, that no other module
  imports it, that exam, scoring-set, Track B, validator and scoring modules
  load none of it, and that the practice score is unchanged by it. The
  battery validator daemon loads `battery/research.py` for its feedback field
  names, so the module is loaded there but never called.
- The new modules join each provider's `implementation_files` (and battery's
  `value/decision.py`). The shared module is named
  `practice_safety_feedback.py` because the worker implementation digest is
  keyed by base name.

### Not changed

The practice score, rules v1/v2, gates, EV studies and hidden-batch results.
The attack adapters' disclosure allow-lists still name v1's fields: their
probes call `feedback` without safety, so they stay green, but they do not
yet probe the v2 block (follow-up on the attack side).
