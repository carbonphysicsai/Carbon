# f02 round 2 — burst joules within a fixed thermal ceiling

**CHALLENGE-F02-QUESTION-LAW-01 / DEVELOPMENT / SPECIFIED.** Owner-approval
draft, no solver runs, spend, hidden/AX42 data or bank draw. New law values
are **HUMAN_INPUT recommendations**, not registered defaults. See the
[sheet](f02-round2.json), [customer packet](../round1/f02-burst-thermal.md),
[#776 baseline](proposals.json), [quiz](foundation-quiz.md),
[optimizer](../optimizers/f02-burst-thermal.md) and
[#864 incumbent](../cheap-baselines/f02.md).

## 1. Buyer and supported job

A thermal architect chooses a burst schedule for a known package/cooling
condition. Maximize extra input joules above 20 W over 120 s, subject to the
top-die **spatial/temporal maximum <=95 C**. Joules are not measured AI work,
throughput or chip reliability. This is offline simulation design, not an
actuator. A scenario-indexed schedule is a complete answer: the buyer need
not use one schedule for every cooling/initial-state condition.

Retain the synthetic three-layer stack, two source patches, constant material
laws, perfect contacts and underside Robin cooling. Supported contexts:
2 cooling pairs (30 C/2500 W/m2K, 40 C/1500 W/m2K) x initial40/55 C x
split50:50/80:20 x rectangular/ramp/two-pulse = **24**. No continuous inlet,
material, geometry or convection interpolation is implied. Each is a
service context of one fixed package, not an independent real buyer/package.
No extension to coolant dynamics, vapor chambers or full cold plates.

Reference adequacy, matched Icepak/Mechanical Tier 2 and public value-panel
receipt remain NOT_DEMONSTRATED. Owner-reported C1 is 2-3 CPU-min per
transient; this checkout has no pinned full-task p50/p95/RSS receipt.
REFERENCE-PACKAGES-01 / Data Collection owns the exact Elmer package,
mesher, source events, time scheme, extractor and manifest. Do not create
another solver environment or inherit steady cold-plate timings.

## 2. Actions and boundary registration

The historical actions are peak{80,110,140} W x duration{5,10,20} s: **9**.
They cannot satisfy >=5 feasible + >=5 infeasible distinct actions in a
condition, even before proximity checks. Do not relabel this as a passed law.

Recommend the [existing prospective f02-v2 proposal](../value-cost/f02.md):
continuous peak80-140 W and duration5-20 s, same fixed waveform family,
20-s onset, 10-s two-pulse gap and all physical/safety limits. Exact numeric
rounding, action grammar, optimizer and model-query budget need adoption.
This document does not replace the current discrete runtime with continuous
search. A finite covered bank, not an unverified off-bank suggestion, is
the truth comparator; global optimality is not claimed.

**Public feasibility/value panel recommendation:** seed coverage with the
4x4 actions peak{80,100,120,140} W x duration{5,10,15,20} s, at all24 contexts
(384 transients). Retain original nine-action results if available, including
110-W neighbors; do not discard difficult actions to increase pass fraction.
Before acquisition, register deterministic power/duration bracketing toward
each active thermal boundary, target requirement, signed side, parent action,
step/rounding, maximum attempts, mesh/time rungs, stop rule and IDs.
Sixteen supplies capacity for ten, **not evidence** of ten near-boundary actions.
If no bracket exists, report the gap; do not move95 C, expand the envelope or
increase a truth band. Action order/geometry/source/solver/observer pins are
immutable within each prospective panel. Failed attempts remain in the return.

## 3. One question and separate P, Q, w

One Q3 question is one known service context, a requirement draw, its full
finite action bank and frozen optimizer. It asks for maximum extra J while
passing the drawn thermal ceiling and energy floor; exact ties use a registered
secondary (recommend lower peak temperature) then fixed bank order. Energy:
`(peak-20)*D` for rectangle/two-pulse, half that for ramp. Never use peak*D
for the ramp, or count two pulses/time samples as separate questions.

- **P_job recommendation:** uniform over24 supported contexts, independently
  draw thermal cap U[90,95] C and energy minimum U[300,900] J. Uniformity and
  independence are synthetic hypotheses, not observed customer frequency.
  This is stricter-or-equal to95 C, never a safety relaxation. Unsupported
  context/observer support is HOLD, not silently conditioned on feasibility.
- **P_reference / pool:** separate density over covered context/action pairs.
  Continuous action-density/validity-conditioned generator and its pool role
  are HUMAN_INPUT; a Q3 action menu is not automatically a random buyer state.
- **Q3:** recommend Q_job=P_job. Keep diagnostic Q2 thermal/frontier
  enrichment separate, with explicitly frozen eligible intervals and quotas.
  Diagnostic cases are not buyer frequencies. Candidate error cannot steer P.
- **w:** unit weight for the uniform P_job pilot; Q2 reports separately.
  A future P/Q importance-weighted estimate needs actual densities and support,
  not arbitrary equal weights copied into `tasks.py` inner condition strata.
  Every thermal condition must pass before objective ranking.

Continuous requirements are the primary recommendation; owner selects them.
Retain #776's 3x3 requirement grid (90/92.5/95 C x 300/600/900 J) as audit:
24x9=216 **raw questions**, not216 distinct winners or new physical solves.
New requirements reuse truth only if spatial/time extrema and waveform
integrals support them. Changed crossing-time diagnostics require a supported
observer, not substitution of the old95-C crossing into a90-C question.

## 4. k, answers and abstention

Recommend **k=8 complete questions/window**, conditional on Test Lead's
cluster-aware power and exposure study. A window draws distinct eligible
questions without replacement; correlated questions still cluster by their
physical package/support bank. No statistical power is earned by k alone.

Keep forward **NONE_FEASIBLE** as a valuable buyer answer: no covered schedule
can supply the requested useful energy safely. No redraw until an easy winner
appears. FEASIBLE_EXISTS requires a settled passing action; NONE_FEASIBLE
requires a demonstrated breach for every eligible action. Missing/band-crossing
truth otherwise yields UNRESOLVED. A choice with excessive peak remains
false-feasible regardless of joules; do not price degrees C into compensating
utility. A correct abstention has zero opportunity regret only when no action
is genuinely feasible; unnecessary abstention loses attainable extra J.

Expected answer diversity is **NOT_DEMONSTRATED**, not8 or216. For iid draws,
report `sum_j [1-(1-p_j)^k]` over design winners from covered P/Q answer masses;
for a fixed bank without replacement use its hypergeometric counterpart.
Report per context/family distinct and equivalent picks, answer concentration,
feasible/none/unresolved mix, close-call and residual unresolved rates, P mass
covered and shared-support clusters. A different context can repeat a valid
schedule; equal J may be value-equivalent even with a different ID. For the
original nine actions each waveform has only7 distinct energy levels.
Threshold decimals do not create unlimited independent answers or reset E.
At a fixed context and thermal cap, varying the energy floor alone can change
FEASIBLE_EXISTS to NONE_FEASIBLE, but cannot change the maximum-J winner.
Winner diversity must therefore come from supported context/thermal-cap
changes and resolved frontier actions, not a count of energy-floor decimals.

## 5. T2(a), refined edges and the required value panel

**Test Lead working value, 2026-10-08:** >=5 distinct resolved feasible and
>=5 distinct resolved infeasible actions within **two refinement bands** per
required condition/question family. Report both sides, joint feasibility and
overall pass fraction; never gate on20-80%. More frontier resolution, not a
wider band, repairs a shortage. Same action at different timesteps is one action.

The packet's1-C unresolved edge and0.5-C mesh/time peak-shift checks are working
values, not calibrated confidence intervals. If b_T=1 C is adopted as the
thermal truth band, resolved near counts lie at distances >b_T and <=2b_T,
not inside the unresolved band. The full decision must also meet the energy
floor. Record the actual registered band, not assume b_T merely from this
example. Energy comes from an exact specified waveform integral; a numerical
energy-nearness/refinement band is **HUMAN_INPUT**, to derive from acquisition/
event precision or register a separate deterministic requirement diagnostic.
Do not fabricate energy uncertainty or widen thermal bands to fill energy quotas.

Data Collection first applies the packet's four controls and four steady
baselines; use existing pinned results only if identities match. Cover24
contexts with the seed actions, then registered frontier additions. Independently
refine every potentially decision-changing action using mesh/time halving,
internal spatial/event peak and first-crossing search. Recommend at least12
initial refinement jobs as a planning floor, not an adequacy promise or grant.
Limit/objective intervals that cannot settle within the frozen cap stay unresolved.

Return for **every24 context and each requested family**:

1. Distinct near-feasible/near-infeasible counts within two registered bands,
   active constraints, all-design fraction and unresolved denominator.
2. Extra-J spread across admissible actions (recommend >=100 J as the packet's
   low value increment, HUMAN_INPUT), equivalent winners and temperature margin.
3. One complete context-indexed feasible schedule under anchor requirements,
   or an explicit absent/unknown context; do not force one universal action.
4. Best/equivalent answer changes across contexts and requirement draws;
   no hidden redraw to improve diversity, and no proof from a30-case timing panel.
5. Exact action/context/deck/digest/observer/rung identities, retained failures,
   CPU/user/system/wall/RSS costs, peak/crossing/recovery and steady-baseline
   coverage. All unmeasured fields remain null/NOT_MEASURED.

No value check passes today: cardinality fails the old menu, while denser
feasibility, boundary counts, spread, complete answer and answer changes all
need reference evidence. That is a measured-work request, not a bank grant.

## 6. Strong cheap incumbent and honest value

Compare exact covered-bank lookup and a **two-input impulse-response or small
state-space thermal ROM**, one for each cooling regime, with initial-state
response and separate patch sources. Constant-property conduction is linear;
a one-node average RC is not the strongest baseline. Independent spatial
peak/event extraction is still necessary. Hold out entire waveform/action
panels, not timesteps; report pointwise curves AND verdict/pick/J-regret,
abstention, unresolved coverage and all calibration/fitting/query/verification
costs. The [#864 specification](../cheap-baselines/f02.md) remains canonical.

Carbon could beat a cheap model only where its adequately supported local
peak/crossing or imbalance forecast changes safe schedule choice. If the
impulse-response method already answers correctly at comparable total cost,
**V4 fails**; do not invent nonlinearity, alter stack or claim speed alone wins.
Original vs denser action proposal retains100/300/600 J incremental-value
assumptions and $200/$600/$1600 gross revision savings, demonstrated net floor0.
Buyer gives up nine-point audit simplicity, not the95-C safety ceiling.

## 7. B, E and startup arithmetic, without a grant

[Owner bank class policy](../../../../.agent/decisions/2026-10-07-OWNER-BANK-ARCHITECTURE-01.md):
cheap CPU-minute class B=20n/E=5. Recommend f02 in this class prospectively;
f02 has no adopted rule here. Battery's pool E=2 and Motor10n/E10 do not transfer.
With proposed n_Q3=k=8, **B_Q3=160 questions**. Pool/Q2 n and their allocation
are HUMAN_INPUT. Questions, actions M, unique physical jobs U and node-hours
are different units. The design-bank reference-feasible-only live path needs
an explicit future f02 NONE_FEASIBLE integration; no runtime change is made.

Threshold-only questions can share24x16=384 transients; they do not need
160x16 independent physical panels by arithmetic alone. But every reuse
keeps underlying-case exposure links: new requirement/task IDs cannot renew E.
With one-question-per-underlying-draw semantics, identical fully shared support
has only its remaining E draws, not B_Q3*E/k independent fresh windows. Actual
bundle accounting/active-window disjointness requires validator-owned
registration/enforcement. B_Q3*E/k=100 is only a question-appearance upper
bound before top-ups; it is not established bank lifetime or power.
Retired, published truth never returns to hidden use.

Using **owner-reported 2-3 CPU-min**, €1.37/CCX63 node-h as a scenario input
(not a quote), and illustrative serial CPU=wall:

| Physical inventory, before refinement | CPU-h | Bare-node euros |
| --- | ---: | ---: |
| Historical9 actions x24 contexts | 7.2-10.8 | 9.86-14.80 |
| Proposed16 x24 | 12.8-19.2 | 17.54-26.30 |
| Proposed panel +4 controls +4 baselines | 13.07-19.60 | 17.90-26.85 |
| 160 independent16-action question supports | 85.33-128.00 | 116.91-175.36 |

At illustrative19% tax +€20 non-node reserve, the392-standard-job scenario
is **€41.30-€51.95 before refinement/witness/failure additions**. To remain
under€100 on this serial assumption, total billable node time must be <=49.07 h;
12 refinement jobs could average only <=3.00 h at the2-min base or <=2.46 h
at the3-min base, with no other unbudgeted work. These are **budget ceilings,
not measured refinement times**. Larger independent supports already exceed
the target before overhead under serial execution. Real concurrency, RAM,
quote, failures, storage, matched-tool witnesses and tax must be measured;
never divide by advertised vCPU count to infer an invoice.

C2 remains UNMEASURED, not PASSED. C3 turnover depends on actual unique-case
depletion/E/windows and top-up policy, not new solves per threshold. C4 includes
validator rebuild plus complete optimization/query cost; validators never run
Elmer references. The old50-attempt/$20 feasibility allowance cannot fund384
cases. No free/paid dispatch or counted/fresh campaign is approved by this law.

## 8. Freeze and owner decisions

Adopt law/action discretization and supported density/dependence, objective/ties,
k/n/B/E and new rule identity only after owner/Test Lead review. DC supplies
complete public adequacy/value/cost panel. Optimizer Codex supplies clustered
power/strong-baseline evidence, not this document. Validator owner resolves
forward-none and shared-case exposure seams. The operator supplies exact pins,
resource/spend enforcement and a separately scoped grant before acquisition.

Recommend freeze as **a proposal**, HOLD hidden-bank production until those
dependencies and two-band contested evidence are satisfied. Other seven laws,
Battery EV5, journal14/live contract and prior evidence stay unchanged. The
Battery-led protocol remains DEFINING. No qualification or runtime IDs earned.
