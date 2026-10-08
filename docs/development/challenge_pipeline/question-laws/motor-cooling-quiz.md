# Motor and Cooling cell quiz content

**CHALLENGE-QUESTION-LAWS-01 Part B / DEVELOPMENT / SPECIFIED only.**
This defines proposed quiz content for the precision-joint buyer and the
local cooling-cell buyer. Every new population, selection, count, band,
control magnitude, diagnostic setting and acceptance policy is
**HUMAN_INPUT with a recommendation**, not a registered setting. There are
no quiz cases, hidden identities, reference/model runs or score changes here.
Test Lead owns score use, power, thresholds and adoption.

The owner required #758 **landing** before this part. It merged as
`b9fa4950327a7d46ccc02b8747e368677be82c45` from
`bb003451afdbf30abec55cfdc08b40fdd3aaf5aa`. Its design-space revisions
remain proposals: no revised feasible bank or reference adequacy follows.
The common task API from #764 merged as
`aebaf2311a3117ae0a0deff763848eea2726c753`.

KEEP the producer/validator separation in
[`battery_quiz.py`](../../../../carbon/challenge_validator/battery_quiz.py),
[Battery registry v8](../../evidence/battery-quiz-designs/quiz-registry-v8.json)
and [diagnostics (a)–(e)](../../evidence/battery-quiz-designs/quiz-diagnostics-v1.json).
WRAP these as patterns, not copied registrations: Battery's 80/320 pool,
117-point lattice, k=8, uncertainty bands, mistakes costs and measured AUC
are not Motor or Cooling evidence. Battery's Q3 redraw of all-infeasible tasks
is **not** copied: this law retains NONE_FEASIBLE questions and good abstention.
Registry v7's pessimistic pricing is not silently imported either.

## 1. Common content and answer contract

Freeze the [Part A](README.md) law alternative, P_job/Q_job/w_job, service
panel, valid actions in order, exact optimizer/query budget, observer,
reference identities, quantity units and requirement dependence before
candidate evaluation. The owner selects grid or continuous. Candidate
models predict physical observations; Carbon's frozen selector commits a
pick or abstention and predictions digest **before answer-key access**.
Candidates neither choose the question law nor access producer truth.

Q2 asks whether one action's declared condition/role observations satisfy
the buyer limits, and which constraint fails. Q3 asks which bank action is
best under the complete mandatory service panel, or whether none is
feasible. A Q2 single-condition pass is not a Q3 whole-panel pass. No
weighted mean compensates for a hard-limit breach.

Proposed internal records, not new runtime fields:

- **Question:** law/variant and context identities, buyer requirement vector,
  complete condition/role manifest, action grammar and ordered bank,
  optimizer/observer/reference pins, unit-bearing limits and refinement rule,
  underlying-case exposure links. No public protected IDs or seeds.
- **Answer key:** action-level feasible/infeasible/UNRESOLVED verdicts and
  active constraints; reference state, resolved best pick/tie and objective;
  standard/refined identities, coverage, uncertainty and terminal failures.
- **Commitment and report:** model pick/abstention bound to the question;
  selected feasible/infeasible/unresolved, missed opportunity, correct
  abstention or abstention-unresolved; regret only with a resolved comparator,
  in its physical objective unit. An infeasible selection is reported as a
  false-feasible, not assigned an invented money penalty.

`carbon/design_search/tasks.py` supplies this commitment/judging pattern.
Its `strata` are **inner** p/q/w; outer law/exposure linkage needs the
prospective contract manifest in Part A. Ordered-ID `bank_digest` is not a
digest of geometry/truth. Motor's command roles need a versioned observer
projection or task extension: no J=0 ripple-zero placeholder and no missing
quantity imputation. This ticket changes neither API nor optimizer (#779).

## 2. Motor Q2 near-limit content

**Buyer question:** can this magnetic design supply smooth positive holding
torque and usable peak torque without jerking an unpowered precision joint?
Original anchor: holding mean 6 N·m, peak mean 12 N·m, ripple fraction ≤0.05
and absolute peak-to-peak ripple ≤0.30/0.60 N·m respectively, unpowered
cogging peak-to-peak ≤0.05 N·m. Q3 varies requirements under Part A; the
anchor remains a separately labelled diagnostic, not a fixed P atom by default.

| Proposed Q2 stratum | Observation and signed passing margin | Discriminating content |
| --- | --- | --- |
| Holding torque floor | Complete declared command curve's signed mean minus holding floor, N·m | Just below/above 6 N·m and Part A floors, including a smooth but too-weak design |
| Peak torque floor | Signed peak-command mean minus peak floor, N·m | Holding-feasible but peak-too-weak design; static evidence is not a two-second thermal rating |
| Energized ripple | Cap minus combined-curve peak-to-peak torque, N·m; cap minus fraction, dimensionless | Cases near one or both holding/peak caps; passing the relative cap cannot erase an absolute breach |
| Zero-current cogging | Cogging cap minus full-rotation peak-to-peak torque, N·m | Below/above 0.05 N·m at J=0, without dividing by near-zero mean torque |

A nonpositive/near-zero loaded mean needs the registered fraction applicability
rule; the absolute curve and failed positive torque floor remain visible.
Never turn negative mean into positive torque with `abs(mean)`, silently clip
a denominator, or normalize cogging by energized torque.

The #758 revision adds a proposed 10p/12s winding, optional three-slice skew
and bounded magnet/tooth shaping beside the 8p/24s control. Keep exact
winding/phase/sign/turn tables, packaging, current/slot-fill, mesh and angular
observer identities. Loaded slices share physical currents/global command.
Full-stack-equivalent slice curves average with weights 1/3; actual partial-
stack curves would sum instead. Compute ripple from the **combined curve**,
not averaged scalar ripple. New topology needs demonstrated full-rotation
periodicity and independent angular/mesh refinement; the old 15° grid is not
truth for the new winding. Manufacturing/3D/thermal limits remain separate.

The holding/peak J=8/10 and J=12/15, phase 0/15 panel in Part A is a reuse
proposal. Command-role selection is HUMAN_INPUT. Recommendation: bind the
holding and peak command recipe to each bank action before evaluation and
require all its declared service conditions. Retain the other command curves
as diagnostics, not permission to retime a failed action after truth access.
If command pairs become independently selectable actions, count those
composite actions explicitly and revise N, optimizer and diversity identities;
the 200-geometry planning count is not automatically that larger action bank.

## 3. Cooling cell Q2 near-limit content

**Buyer question:** can this periodic cell keep the local TIM interface
within the 85 °C requirement while respecting its declared pressure allocation?
Cooling is **cell-only**: no full cold plate, header/manifold, whole-plate
hydraulic-W limit or maldistribution truth is introduced.

| Proposed Q2 stratum | Observation and signed passing margin | Discriminating content |
| --- | --- | --- |
| Warm uniform thermal edge | 85 °C minus local peak TIM-proxy temperature, °C | Cases on both sides; no substitution of a mean wall temperature |
| Central hotspot edge | Same local observer with the pinned central heat map | A nominally passing cell that fails on local flux/spreading |
| Outlet-side hotspot edge | Same observer with the pinned displaced heat map | Axial warming/local peak that a uniform-load-only model misses |
| Cell pressure allocation | Proposed cell Δp cap minus cell Δp, Pa | Thermal-feasible geometry with excessive cell pressure burden, and the reverse trade-off |

Retain the complete cold-uniform, typical, warm-uniform and two warm-hotspot
panel for Q3. Reduced-supply flow stays excluded until genuinely supported.
Local TIM jump uses the matching local flux and solid field, not mean flux.
The #758 deeper/narrower channels and thinner-base grammar is prospective;
pin its geometry validity, PG25 law, flow/regime, mesh, conservation and
observer before judging. Thin bases may worsen spreading. A pin-fin tier
requires a separate frozen grammar/reference identity, not interpolated
straight-channel labels. The reported old ideal 89 °C is not a successful
new-space witness or proof about every possible geometry.

## 4. Q2 selection and coverage

Recommendation: start public/retired diagnostic design studies with **up to
80 selected Q2 cases from up to 320 eligible case-requirement pairs** per
Challenge, inspired by Battery only. These counts, per-constraint coverage
allocations, panel membership, tie rule, near-limit distance and all bands
are HUMAN_INPUT; no power claim or exact fill requirement follows.

First predeclare the relevant reference-supported boundary regions under
diagnostic Q2 (separate from Q_job). Obtain the eligible pool producer-side,
then select by the frozen independent panel's **prediction disagreement**;
do not select based on the submitted candidate's errors. Freeze panel version,
recipe/rebuild pins and missing-prediction handling. Recommendation: missing
panel prediction makes that pair unavailable, not unanimous agreement.
Report eligibility, both sides of each boundary, active-role coverage,
overlaps, shortages and all reference/panel failures. A missing resolved
infeasible side makes that detection metric UNMEASURABLE, not perfect.

Q2 is enriched diagnostic signal. Report its selection law and unweighted
results; do not claim P_job reliability or invent inverse selection weights
for an opaque top-disagreement rule. A quantity can be close but irrelevant
to a Q3 winner; report that distinction instead of equating near-limit case
count with decision power. No protected pool is read by this specification.

## 5. Q3 design questions and refined truth

Draw Q3 briefs under the owner-selected Part A law and exact exposure-
constrained batch schedule. Recommend initial **k=12 Motor**, **k=8 Cooling
cell**; counts stay HUMAN_INPUT and must fit actual bank diversity, E and
power. Grid and continuous laws are alternatives, not mixed invisibly.
Keep genuine NONE_FEASIBLE and UNRESOLVED draws; no redraw until a convenient
feasible set appears. A bank whose questions all abstain cannot test choosing
a valuable feasible design. The old Motor bank's all-none finding needs a
revised space, not additional requirement decimals.

Motor selects the declared holding relative-ripple objective, current
secondary then frozen bank order, only after positive torque, both ripple
limits and cogging pass at every applicable role/condition. Regret is the
fraction difference (also report ×100 percentage points); absolute torque
violations remain N·m. Cooling selects minimum worst cell Δp in Pa, local
TIM-proxy temperature secondary, after all five thermal/pressure cases pass.
These remain proposed buyer-value choices, not an adopted score. Report
missed opportunities/abstention separately; do not price them as infinite
regret or import Battery's mistake costs.

Before sealing the answer key, the producer identifies every bank action
whose required observation interval intersects a drawn buyer limit, plus
potential winners whose objective ordering remains uncertain. A submitted
pick must not determine which comparator receives refinement. Recommendation:
use predeclared angular/mesh rungs for Motor and mesh/flow/conservation/local-
observer rungs for Cooling on the **same physical deck**, with exact pins and
retained standard/refined observations. Refine once according to a bounded
registered policy, or leave UNRESOLVED. Counts, rungs, uncertainty construction,
stopping criteria and allowable residual rate are HUMAN_INPUT; no solve or
execution grant follows. Continuous thresholds through a formerly settled
grid interval may make fresh refinement necessary, not a free truth claim.

No failed reference, broken mesh, missing peak or failed refined run is a
candidate scientific failure. A known independent breach can establish an
action's infeasibility; unresolved potentially better competitors prevent
claiming an exact optimum/regret. Some feasible action can establish
FEASIBLE_EXISTS without settling the best. Residual UNRESOLVED earns no
clean pass/credit; report primary rates, denominators and unresolved counts,
and a separately labelled pessimistic sensitivity **only under an owner-
selected policy**. Do not silently exclude uncertain outcomes from a
"clean" headline or convert them to physical failures.

Retain selection, exposure, refusal, standard/refined counts and answer-key
digest in the producer journal before use. Refining unchanged physics does
not mint a fresh case or renew E. A new reference/observer version is
prospective; sealed results keep their original identity, never a silent
rescore. Validators **never solve references**: they rebuild/infer, commit
picks and score only the sealed key under registered policy.

## 6. Behaviour-defined control panel

These are constructions for a separate authorized public/retired pilot,
not actual models executed here. Magnitudes, localization, mixture weights
and recipes remain HUMAN_INPUT. A control is "bad" only where it causes
the defined decision error; membership does not make it intrinsically bad
in every operating condition. Accurate edge optima are **not gaming**.

| Control | Motor behaviour | Cooling-cell behaviour | Expected diagnostic, not an earned result |
| --- | --- | --- | --- |
| Good accurate selector | Correct signed curves, combined-slice extrema, command roles and all limits; frozen selector | Correct local thermal/pressure observations across the complete panel | Resolved correct picks/abstentions and low regret; near-edge truthful optimum stays good |
| Good calibrated uncertainty | Reports calibrated curve uncertainty rather than invented torque | Reports calibrated local peak/pressure uncertainty rather than unsupported extrapolation | No invented feasibility; with settled reference, abstention can still be a missed opportunity. Only reference uncertainty makes the reference verdict UNRESOLVED |
| Edge-optimist | Genuinely reference-infeasible just-below torque or just-above ripple/cogging reported just passing, accurate elsewhere | Genuinely too-hot cell reported just below thermal limit, or excessive Δp below allocation | Q2 false-feasible; Q3 infeasible selections, caught by independently refined truth per v8 |
| Over-cautious | Rejects known-feasible torque/ripple/cogging boundary opportunities | Rejects known-feasible cool/low-pressure boundary opportunities | False-infeasible, missed opportunities and positive feasible-pick regret; never reward abstain-all as safe value |
| Localized sign-error | Reverses a predeclared constraint-margin sign; e.g. torque deficit becomes surplus or cogging exceedance becomes slack | Reverses cap-minus-T or cap-minus-Δp margin on a predeclared region | Wrong feasibility on both sides; control applies to signed margins, not nonphysical negative pressure |
| Optimizer or lattice aware | Accurate on coarse command/angle probes, optimistic at covered gaps or search-favoured low-ripple actions | Accurate at coarse geometry/probe nodes, optimistic at covered local hotspots or search-favoured low-Δp actions | Same frozen selector chooses wrongly from biased predictions; detect on covered refined witnesses, not by letting a candidate change the optimizer |

Optimizer/lattice-aware probes do not give participants evaluator code or
unbounded search. Freeze permitted witness geometry/commands and truth before
comparing optimizers; any off-bank action is separately covered or UNRESOLVED,
never judged by nearest-neighbour truth as though exact. If the action grammar
is intentionally discrete, correct bank knowledge is not itself an attack.
Truth-informed synthetic controls are operator fixtures only, never candidate
training material or public derivatives of protected cases.
Missing/uncertain **candidate** predictions are a separate coverage finding;
they do not turn settled reference truth into UNRESOLVED. A committed
abstention with a reference-feasible alternative remains a missed opportunity.

## 7. Diagnostics a through e and reporting

All five are **reported diagnostics only**; none becomes a gate or score
input here. Settings and agreement/acceptance thresholds are HUMAN_INPUT.

| Battery pattern | Motor and cell proposal | Required limitation |
| --- | --- | --- |
| (a) Optimizer stability | Compare the frozen #759/#779 production-intended selector with a precommitted diagnostic exhaustive comparator or second bounded search, same bank/objective/ties; pick agreement and spread of false-feasible, missed-opportunity and physical regret | Optimizer versions/query budgets differ explicitly; no after-truth best-of-search choice and no unresolved off-bank interpolation |
| (b) Grid resolution | Public/retired matched coarse/refined action witnesses; Motor refine mechanical-angle/mesh and bounded design actions, cell refine geometry/mesh/local peak; compare feasibility, picks and regret | Numeric truth refinement and a larger design lattice are different changes; added actions need new covered truth, not threshold-only reuse |
| (c) Power by k | Recommend exploratory k={1,2,3,4,6,8,12}, subject to actual E/diversity. Compare behaviour-defined good/bad decision errors; report AUC with mean/lower-tail uncertainty, false-infeasible and missed opportunities | Counts/tail definitions/pass bar remain HUMAN_INPUT; cluster shared banks and recipe seeds; UNMEASURABLE when class support is absent |
| (d) Agreement with decision value | Kendall tau-b/Spearman rho between member quiz decision measures and independent same-scope public DEVELOPMENT value; pick/feasibility agreement and regret in physical units | Separate witness draw or legitimately retired published cases, never hidden quiz/tuning export; no reused conditions sold as independence or cross-Challenge scalar comparison |
| (e) Unresolved rate | All-draw, truth-covered, selected-action, optimum-unresolved and refinement-terminal rates, by role/constraint/context and P/Q; report residual unresolved and missing candidate prediction separately | Denominators cannot turn missing reference into candidate failure or absent evidence into clean credit; raising k is not an automatic cure for shared unresolved truth |

The batch report also carries Part A's observed distinct winners, expected
P/Q occupancy, answer concentration, feasible/none-feasible/unresolved mix,
close-call demand and underlying E usage. Independent buyer-tool witnesses
follow the [reference credibility contract at inspected main](https://github.com/carbonphysicsai/Carbon/blob/961f5fc227c9407a48254b46e806db1134dcb2d3/docs/development/challenge_pipeline/round1/reference-credibility.md):
separate non-hidden draws or verified retired publications, pointwise **and**
decision agreement, near-limit enrichment explicit. Tool disagreement is a
reference finding, not candidate failure. Already-sealed keys are not revised.

## 8. Adoption and engineering handoff

Test Lead/science owner must choose the law alternative, intervals, command
roles, uncertainty/refinement policy, Q2 panel/sizes, E linkage, permissible
question bundling, power/score use and unresolved treatment before adoption.
Recommendation: first audit adequate **public/retired** bank coverage and
expected winner diversity, then precommit diagnostics, then use a separate
authorized producer execution ticket. Do not run a hidden quiz merely to
fill these unadopted fields or weaken the buyer limit until a winner appears.

This packet reuses shared contracts parameterized by Challenge; it does not
duplicate the neutral registry, bank, hidden-source, weighting or #779 search
implementation. Protected EVAL/STRESS/quiz/tuning cases, seeds and labels
stay operator-side. Battery EV5, journal sequence 14 and live contract are
unchanged. No mainnet, qualification, reference-credibility tier, compute
or counted/fresh campaign authority is earned.
