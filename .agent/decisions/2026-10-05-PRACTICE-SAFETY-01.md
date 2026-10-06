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

## Addendum 2026-10-06: B4 computed

Data Collection committed the practice decision set (#669,
`docs/development/evidence/practice-decision-set-v1/`). B4 moves from
BLOCKED to computed, as the ticket's B4 section defines it.

- **Pin.** `DECISION_SET_SUMS_SHA256` pins the set's `SHA256SUMS`, and each of
  `conditions.json` and `records.jsonl.gz` is read once and checked against
  it before it is parsed. A missing file, a `SHA256SUMS` off its pin (even
  one consistent with forged files), a file off `SHA256SUMS`, or a set that
  is not 6 OK unrefined conditions at EV4's 35-candidate grid is refused
  with one of four typed reasons (`B4_REFUSALS`). B4 then reports that
  reason, nothing is computed and no decision case is staged. A mutant that
  skips the file digest check is killed by test.
- **Definition.** Each condition is one scenario (EV4's adaptation: one
  condition per scenario). The model's predictions choose with
  `decision.assess_predicted` and `decision.select` (EV4's rules, no band,
  EV4's tie rule). The reference verifies the choice with
  `decision.assess_reference` (EV4's bands). The EV4 grid is copied as
  `CANDIDATES`, and a test binds it and the tie rule to the contract. The
  mistake costs do not enter: B4 is a feasibility rate, not a decision loss.
- **Working decision (engineering, recorded): the rate's denominator.**
  `rate = feasible_choice / chosen`, where `chosen` counts the choices the
  reference resolves FEASIBLE or INFEASIBLE. Abstentions (`abstained`) and
  choices the reference leaves UNRESOLVED or unavailable (`unresolved`) are
  counted beside the rate and never in it (ticket rule 5, and "abstentions
  are reported separately"). All four counts are reported, so another
  reading of the share can be derived. With the reference as the model, B4
  is 5 of 5 chosen and 1 abstained.
- **Missing data.** Any unmeasurable decision-set prediction makes B4 null.
  The document's `unmeasured` then also counts the decision-set cases. B1-B3
  are still gated on the practice cases alone.
- **Allow-list.** B4 is exactly `{feasible_choice, chosen, rate, abstained,
  unresolved, feedback_only}`, null, or a typed refusal. No case id,
  condition id, condition value or per-condition verdict can leave. The
  BLOCKED literal is no longer accepted.
- **Worker inputs.** The provider loads the set inside its practice trial
  (`practice_safety.decision_set`) and stages its 210 inputs (no label)
  beside PRACTICE's in `practice-inputs.json`, under
  `carbon.battery.practice-inputs.v2`. `staged_files` without extra cases
  still stages exactly v1, so the validator's scoring and the stager
  allow-list are unchanged. The practice score still reads PRACTICE alone.
- **Versioning.** The battery practice result is
  `carbon.battery.practice-feedback.v3`: v2's fields, with B4 computed and
  `unmeasured` counting the set's cases. A stored v2 result keeps its
  meaning (B4 always `ps.B4_BLOCKED`). Cooling and motor stay at v2. The
  shared safety document schema is unchanged, because each Challenge
  declares its own metric shapes.
- **Separation.** The committed set passes the ruled list (every EV1, EV2,
  EV4 and EV5 decision condition and EV4's protected grids, which is
  exactly the list the selection excluded) at the ruled box, and it shares
  no 4 dp point with any protected point, EV5's protected grids included.
  **For the Test Lead:** D6's check above runs on a declared superset that
  adds EV5's protected grids. Against that superset, 2 of the 6 conditions
  lie inside both bounds of an EV5 protected-grid point (3 points in all).
  The ruling does not name those grids, so B4 is computed on the set as
  committed. If the ruling should include them, the set needs a v2 with
  those 2 conditions reselected (70 solves), and a new pin.
- **Feedback only.** B4 enters no score, rank, reward or weight. The
  isolation tests now cover it. They check that the battery provider calls
  the safety code only inside its practice trial, that no official path
  loads it, and that the practice score is the same with B4.
