# Battery EV optimizer v2 — admissible session time as the objective

**DEVELOPMENT / SPECIFIED; prospective amendment to #759.** The
[historical optimizer](battery-ev-fast-charge.md) keeps its old semantics;
this version supersedes its Battery directions where they conflict with
[owner-selected packet v2](../round1/battery-ev-fast-charge-v2.md) and the
[continuous-primary law proposal](../question-laws/battery-continuous-v3.md).
No runtime optimizer, score, bank or execution is registered.

## 1. Decision and admissibility

Choose a single pinned two-stage c1/c2 protocol before independent reference
access. Existing bounds c1=0.5–2.0 C, c2=0.2–1.0 C remain the starting grammar,
not approval of a finite lattice. Preserve120-s initial rest, the4.0/4.2-V
switch/CV-to-C/20 and30-cycle programme. Optional cooling is separately
reported and only scoreable after an explicit action/reference version; no
default multiplier, subambient bath or free preconditioning.

Hard conditions **precede** time ranking: every CC/CV charge leg in all30
cycles must satisfy the drawn charging thermal maximum (no greater than45 C)
and drawn plating minimum (no less than0 V), at **each** required ambient.
Retain4.2-V programme voltage and0.99 Q30/Q1 minimum, unless an expressly
identified audit question uses the stricter0.995 floor. Discharge/rest thermal
extrema and whole-programme maxima are labelled diagnostics, not mislabeled
charging failures. No30-minute cap, reward for unsafe speed or physical
absence-of-plating claim.

At SOC0.10 minimize admissible session-start10–80% time, including rest,
from pinned charge-integral/capacity-basis crossing. For the proposed
SOC0.20/0.30 extension the quantity is explicitly session-start SOC0→80%:
same within-task comparator, different observable label. Its adoption and
coverage remain HUMAN_INPUT. Do not use time-to-CV, voltage probes or a
first-hour truncation. Missing/uncertain crossing is UNRESOLVED until the
observer decides a genuinely observed NOT_REACHED under its full horizon.

Proposed primary aggregation: minimize buyer ambient-mix weighted expected
minutes over the five covered ambients, subject to all five hard constraints;
secondary lower capacity loss, then frozen bank order at registered observer
resolution. Aggregation/tie bands remain HUMAN_INPUT. This supersedes the
old draft's unadopted worst25/35 recommendation for **primary-law** questions;
retain it in the four-grid audit. Neither averaged temperature nor evidence
weights may substitute for buyer time coefficients or per-case safety.

## 2. Search and task identity

KEEP/WRAP Challenge-neutral `carbon/design_search/tasks.py` v2 action grammar,
finite-bank digest, frozen optimizer/query budget and commit-before-judge
machinery. The file is now merged, correcting #759's historical absence note.
Conditional class(a) exhaustive finite lattice remains recommended while the
approved action set is small. Register its spacing/order/count; changing to
local search or adding cooling needs its own version/budget. Producer alone
owns protected draws and reference truth; validators rebuild/score, never
perform reference solves.

Bind law version, drawn limits/mix/SOC/fresh-or-approved-restart state,
programme, candidate/context bank, physical inputs, observer/projection,
uncertainty/refinement, reference pins, exposure and optimizer in an immutable
task manifest. Generic task strata p/q/w do not define the outer law, buyer
mixture objective or role-scoped charging quantities. Project complete
condition-role reductions in a versioned owning observer, retaining source
phase/cycle/time observables; missing/inapplicable values cannot be favorable
zeros. No extension of generic runtime fields in this PR.

Recommended `B_model=5N` complete programme/observer calls per question with
one chosen SOC, N=100 as a **planning benchmark**, not an adopted grid cap.
No early stop claims exhaustive comparison. Eight questions nominally4000
calls; repeated mix/limit questions can reuse exact model/context predictions
only under registered cache and budget semantics. Continuous thresholds do
not protect an exposed action lattice: keep off-lattice diagnostic coverage
under independently covered truth, rather than inventing unseen physical data.

## 3. Truth, regret and cost

Pre-resolve the full approved comparator bank at all required physical contexts
and observer scope; commit picks before reference judgment. Known feasible
members establish existence, not a settled optimum when competitors remain
unresolved. A fully settled all-fail bank yields NONE_FEASIBLE and permits
correct abstention; keep it without redraws. Unknown reference coverage is
UNRESOLVED, never candidate failure or a least-violating winner.

Refine intervals crossing thermal/plating/voltage/capacity boundaries or
objective ordering. Report exact best-in-bank and regret only under registered
resolved ordering/tie rules. Regret is excess expected session **minutes**
against the same task's best reference-feasible protocol, not dollars, negative
infinity for abstention or a soft penalty compensating safety. Separately report
false-feasible, missed-opportunity, correct abstention and unresolved outcomes.

Proposed100×5×3 fresh-state bank needs1500 base programme solves plus refined
work. Costs remain UNMEASURED for these SOC/observer/phase semantics. Historical
2684×about90 CPU-s≈68 CPU-h is not a quote for this bank. Retain setup, failures,
refinement, memory and full timings; no execution or spend grant here.

## 4. Handoff and maturity

Test Lead owns score use, power, uncertainty handling and the four behavioural
controls; report diagnostics(a)–(e) and expected winner occupancy under P and Q.
Continuous-primary is owner selected, not a promise of several winners. Arbitrary
aged-cell initialization lacks current reference support; first stage is a
fresh-state point mass, preserving30-cycle ageing. Data Collection supplies
proper restart and crossing/all-charge coverage before expansion.

Required before executable use: adopted numeric law/aggregation/action bank;
qualified observer and complete truth/intervals; task/outer-manifest integration;
cost/cadence and cluster-aware power; approved reference credibility. #815's
prospective score-rule registration and #808's sealed reports retain their
own identities and are not implicitly migrated by this customer proposal.
Reference/physical/security/product qualification remains NOT_DEMONSTRATED.
No Motor/five-family optimizer change, EV5/journal14/live-contract edit or
historical rescore.
