# Battery v3 round-two design-question law

**DEVELOPMENT / SPECIFIED; draft for owner/Test Lead approval.**
CHALLENGE-BATTERY-V3-QUESTION-LAW-01, main
`6848d9316c0341113ee701100e53fcc984d1531e`. This prospective supplement keeps
the [v3 buyer job](../round1/battery-ambient-map-v3.md),
[original law](battery-ambient-indexed-v3.md) and
[indexed optimizer proposal](../optimizers/battery-ambient-map-v3.md).
The [sheet](battery-v3-round2.json) is not a runtime registration. No solver
runs, spend, hidden or AX42 data, score/power adoption or sealed rescore.

## 1. One question and approved actions

One question asks the fleet-calibration engineer for **one complete five-band
charge map**, not five independent questions: one protocol and cooling action
for each 5/15/25/35/40 C band, at a pinned start SOC, initial state and 30-cycle
programme. Freeze physical bank, reference/observer, optimizer, action menu,
requirements, buyer mix, query budget and exposure links before predictions.
An answer is a feasible best-in-bank map, NONE_FEASIBLE, or UNRESOLVED; it is
not a continuous global optimum. All five bands remain mandatory, including
a zero-weight band. No unsafe band can be averaged away.

Owner, 2026-10-08: C rates are selected on a **0.01-C lattice**, and cooling
is **x1/x2/x4 only**. This is a quantized action space, not an arbitrary
real-valued C rate. Lattice bounds, order restrictions, switch-voltage menu,
physical cooling definition/nominal h and model-support pins must be frozen;
their prospective accepted values are HUMAN_INPUT, not inferred from bank
extrema. A finite sampled bank need not cover every point in a bounding box.
Requirements/mix, not the action lattice, have the primary continuous law.
Historical off-lattice or x3/x6 diagnostic solves remain history: no rounding,
interpolation or relabelling turns them into truth for an approved action.

Keep charging T <=45 C, every-charge plating >=0 V, programme V <=4.2 V and
Q30/Q1 >=0.99. Time is the minimized session-start-SOC-to80 objective; there
is no hard 30-min cap. Discharge thermal extremes are diagnostic. Refine
observer/extreme/band ambiguities rather than introducing safety slack.
The producer export's 4.200001-V numerical convention needs an explicit
reference reconciliation; this proposal does not amend the buyer's 4.2-V cap.

## 2. P: supported service and continuous requirements

Keep the prior HUMAN_INPUT recommendation: mix ~Dirichlet(2,3,8,5,2), mean
(0.10,0.15,0.40,0.25,0.10), thermal margin U[0,2.5] K and plating margin
U[0,0.002] V, conditionally independent, with common margins across all bands.
These are synthetic planning distributions, not measured fleet frequencies.
Each band is evaluated at T <=45-mT and plating >=mEta; voltage/retention
remain unchanged. A question's ambient service is the full five-band panel;
the mix specifies how often the buyer uses its answers, not randomly dropping
a safety band. Require measured support of the drawn limits and objective.

Separate **covered pilot support** (SOC10%, identified fresh initial state)
from the owner-selected **expanded support** (SOC10/20/30%, prior proposed
masses 0.5/0.3/0.2). Current data do not support the latter law. HOLD an
expanded-law execution until the session-start observable and full physical
bank exist; do not silently reject unsupported draws and renormalize P.
Fresh initial state remains a point mass; 30-cycle ageing is a programme,
not evidence for arbitrary initial aged/SOH inputs. No general SOH law is
proposed without restart/model support. These support restrictions must be
explicit in a future pilot identity, not a quiet change to a fleet claim.

## 3. Q and w are different objects

Keep diagnostic Q's HUMAN_INPUT recommendation: 20% interior, 50% hard-limit
edges and 30% pick/value edges, drawn from separate public or retired cases.
Freeze per-quantity refinement bands and selection/normalization before
use. Refine at the **drawn** requirement, not just nominal 45 C/0 V. Empty
edge support is reported, never manufactured by a redraw. No hidden quiz,
EVAL/STRESS or tuning material enters research/comparator training.

Owner-selected band value weights are the drawn buyer mix:
`expected_minutes = sum_b mix_b * minutes_b`, after every hard gate passes.
They are not Q's enrichment or outer-question weights. For P-drawn pilot
questions recommend unit outer weights and shared-bank clustering. For a
population estimate using Q, an explicitly supported P/Q correction and
separate raw Q report need Test Lead registration. No correction exists
where Q omits positive-P support. Score use/power remain Optimizer/Test Lead's.
Retain the original best-anchored 0.5-min value-equivalence recommendation as
HUMAN_INPUT; it is never thermal/plating/voltage safety tolerance.

## 4. k, diversity, exposure and NONE_FEASIBLE

Recommend **k=8 complete-map questions per batch**, not 8 questions per band.
Power and cost determine final k; this draft asserts neither. Query count for
exhaustive per-band search is `sum_b N_b`, not the product of five menus.
Threshold/mix reuse adds no physical solves only for identical fully covered
truth, observer and action/context pins. New SOC, cooling or action support
requires truth. No startup cost or execution grant is supplied here.

Expected distinct winners is **NOT_DEMONSTRATED per band**. Once settled
answers establish P masses p_bj, iid k-draw occupancy is
`sum_j [1-(1-p_bj)^k]`, bounded by 0..min(k,N_b). Report actual distinct
value-equivalent sets, feasibility/none/unresolved shares, edge/refinement
rates and full-map vector diversity. Positive mix changes alone do not
change independent band argmins: do not count weight draws as new answers.
Q is not iid P; correlated windows require the owner's accumulation design.
All reused underlying cases consume the same E; new question thresholds,
SOC labels or map IDs do not renew it. E remains HUMAN_INPUT: neither a
development export's E=5 nor an open E=2 suggestion adopts exposure policy.

**Recommendation: forward NONE_FEASIBLE draws are valid buyer questions;
never redraw them.** A settled empty feasible menu in one mandatory band
proves no complete map exists. A missing/uncertain row instead leaves the
question UNRESOLVED unless other settled evidence suffices to decide it.
Do not choose a least-unsafe protocol. No-feasible answers consume E just
like feasible answers. Motor's producer-simulated 4/20 is not a battery rate
or a settled motor acceptance receipt. Power comes from separate diagnostic Q.

**Gate-owner seam (HUMAN_INPUT):** the framework still requires T1, a complete
feasible answer on refined truth, before hidden-bank readiness. Recommend
distinguishing an anchored feasible bank from stricter requirement draws
that legitimately have no answer. If Test Lead interprets T1 as requiring a
feasible answer for every P draw, this proposed none-feasible support HOLDS;
do not weaken T1 or redraw to conceal the conflict. This is a draft policy
choice, not a new production NONE_FEASIBLE rule.

## 5. What tier-4 actually demonstrates

Immutable acquisition head
[`66ea509888e4ef0f5ac08750554db744b56b92bf`](https://github.com/carbonphysicsai/Carbon/tree/66ea509888e4ef0f5ac08750554db744b56b92bf/docs/development/evidence/battery-feasibility-02)
contains `tier4-boundary.json` and the v3 provenance note. Its counts:

| Tier-4 band | Actions | Producer feasible / infeasible / unresolved | Infeasible within 2 / 5 diagnostic bands | Approved-menu one-band T2(a) |
| --- | ---: | --- | --- | --- |
| 5 C | 80 | 17 / 62 / 1 | 8 / 26 | NOT_DEMONSTRATED |
| 40 C | 137 | 53 / 78 / 6 | 30 / 51 | NOT_DEMONSTRATED |
| 15 / 25 / 35 C | not in this tier-4 summary | no tier-4 count supplied | not supplied | NOT_DEMONSTRATED |

The reported contested flags use **two/five** diagnostic bands, not the
framework's **one registered refinement band**. T40 includes x3/x6 actions;
some T5 rates are off the prospective lattice. Neither flag establishes five
approved, resolved feasible plus five approved near-limit infeasible actions.
Per-limit thermal/plating/voltage/retention counts must not be conflated.

The designated shared SOC10/fresh development export, byte SHA256
`31463626c13549916feffa4ef9917f520e1437eb24dc08c8c402b6926e4717d4`,
logical digest `sha256:2ec4da3ccfc358d412bd38648f4ca9fb6a010e838964a1e4e3f65a4a2b5f041d`,
contains a different filtered/refined inventory. Nominal q00 canonical
interval assessment, using the original export contract, gives:

| Band | Rows | Feasible / infeasible / unresolved |
| --- | ---: | --- |
| 5 C | 80 | 13 / 62 / 5 |
| 15 C | 42 | 10 / 28 / 4 |
| 25 C | 147 | 15 / 115 / 17 |
| 35 C | 147 | 15 / 117 / 15 |
| 40 C | 77 | 22 / 51 / 4 |

This is **read-only development arithmetic**, not solver replay, adopted
v3.01 truth or a T2 pass. Nine historical rows are off-lattice, and accepted
pick settlement is absent: all 25 complete-question reference comparisons
remain unresolved. Preserve the original producer counts, rather than
silently replacing them with this different assessment. A known feasible
map is not proof of settled optima, answer changes or contested one-band
coverage. T2(a) remains NOT_DEMONSTRATED in every band today.

## 6. Required return and prospective adoption

Data Collection returns an identity-bound, approved-menu inventory with
reference intervals and accepted settlement: per-limit feasible and one-band
near-infeasible counts, unsupported/off-lattice exclusions, P support,
close-call/refinement rates, and settled per-band winner/equivalence cells.
Retain physical case exposure links; threshold copies are not new cases.
Optimizer Codex then owns diversity/power/score-value/readiness measurements.
No extra solves, package changes or evidence-settlement fields are authorized
by this request. Unavailable inputs HOLD the affected measurement.

Keep the four-vector grid (T caps42.5/45 x retention0.99/0.995, plating0,
SOC10, fixed documented mix) **audit only**, not primary law. A stricter
retention requirement is not a relaxed safety bound. Q2 targets full-charge
per-band safety; Q3 commits a complete map. Diagnostics (a)–(e) and four
behavioural controls stay with existing owners. No motor/cooling/five-family
law change is forced. Runtime BatteryCase limitations still require its
own versioned migration, not permissive validation here.
