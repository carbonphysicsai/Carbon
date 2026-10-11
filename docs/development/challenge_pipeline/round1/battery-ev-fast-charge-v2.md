# Battery mock customer v2 — fastest admissible charging session

**Role-play / DEVELOPMENT / SPECIFIED.** Prospective owner revision dated
2026-10-08, under [OWNER-BATTERY-COOLING-PACKETS-02](../../../../.agent/decisions/2026-10-08-OWNER-BATTERY-COOLING-PACKETS-02.md).
This supersedes the affected buyer requirements of [v1](battery-ev-fast-charge.md)
for future versioned work only. V1 results, Battery EV5, sealed journal
sequence14 and the live contract are unchanged. The
[v2 planning amendment](first-three-requirements-v2.json) is not runtime input.

## 1. Engineering job

I am the hypothetical fleet charging-calibration engineer. Choose a protocol
that completes my simulated cell's 10–80% charging session **as quickly as
possible while meeting the hard charging constraints**. I do not want a
false promise of a 30-minute session that violates a thermal or plating
allocation, nor rejection of an otherwise admissible 32-minute improvement.

| Buyer requirement / objective | Why it matters |
| --- | --- |
| Minimise session-start 10–80% time in minutes, including the retained 120-s initial rest | Turnaround is continuous value, not a cliff at 30 minutes |
| Charging temperature <=45 C on every declared charging leg, including CV | Do not buy speed by using up more charging thermal headroom |
| Minimum local model plating reaction overpotential >=0 V during every charge | Retain the model's plating boundary; this does not prove no physical plating |
| Retain the v1 4.2-V programme ceiling and Q30/Q1>=0.99 screening requirement | Do not silently weaken other existing buyer checks when removing the time deadline |
| Test-discharge and rest temperature extrema are reported diagnostics | A laboratory discharge peak is not a charging thermal breach; it is still visible |
| Cooling is an optional, reported action | Distinguish faster charging bought with cooling from protocol-only improvements |

There is **no hard 30-minute limit** in v2. Thermal management is not mandated,
and no cooling multiplier is selected here. The buyer's time value is minutes
saved against a matched, admissible baseline. At the v1 hypothetical $30/h
driver value, saving delta-t minutes is `$0.50 * delta-t` gross per session.
This is not an actual customer saving or a score coefficient. The v1 abort
assumption (15 minutes) remains $7.50 of driver time; hardware investigation
and replacement are separate. Account for cooling energy/hardware and model/
reference costs before claiming net value; their prices remain HUMAN_INPUT.

## 2. Physical system

KEEP the existing [Battery reference](../../../../carbon/battery/reference.py),
one pinned simulated cell, declared parameter set and thermal law, two-stage
charging action and 30-cycle screening programme. Initial SOC 0.10 and target
SOC 0.80 retain their meanings. Cell-level screening is not a pack/BMS, charger,
vehicle lifetime or fleet deployment claim.

An optional cooling action must name its boundary law, effective conductance,
environment, phase schedule, energy/heat-removal outputs and physical-model
limits. The earlier h-multiplier proposal is history, not an owner selection
in v2. Keep the unmodified reference cooling baseline explicitly pinned;
do not invent an unpowered unlimited cooler or subambient bath. Missing
cooling-action coverage yields UNRESOLVED for that action, not free cooling.

## 3. Population P, Q and w

Retain the synthetic five ambient contexts 5/15/25/35/40 C as the planning
panel, not observed fleet frequencies. Charging limits apply to every
declared charging leg at every included ambient. Report session time by
ambient; aggregation for a buyer question is a separate HUMAN_INPUT law.
The #776 recommendation is worst 25/35-C session time, with the complete
mandatory panel retained. It is not an approved warm-fleet population.

Outer P_job, diagnostic Q_job and weighting w_job stay separate and
unregistered in the [v2 question-law amendment](../question-laws/proposals-v2.json).
Remove time-ceiling variation; retain proposed charging-temperature/capacity
requirement variation over supported truth. Near-limit enrichment examines
charging thermal/plating and other mandatory margins; near-tied session
objectives require refinement too. Threshold changes do not renew bank E.
Do not redraw NONE_FEASIBLE tasks until a convenient pass appears.

## 4. Case contract

Bind packet v2, action, optional cooling identity, ambient, initial SOC,
complete programme/phase catalogue, material/parameter laws, solver/build,
mesh/time/event settings and observer identity. Preserve units and the exact
charge-integral SOC capacity basis. A 30-s voltage-probe termination is not
the 10–80% charge-integral clock. A changed phase or cooling law needs a new
case/reference identity, not a cache hit on an old case ID.

Charging scope means all CC/CV charge legs, not discharge. Report initial,
inter-leg and inter-cycle rest extrema separately. Any extension of a hard
thermal rule to rest needs an explicit phase policy; no whole-programme
temperature scalar may silently reintroduce the retired discharge limit.
Invalid inputs are refused; missing phase coverage remains UNRESOLVED.

## 5. Reference policy

KEEP pinned PyBaMM DFN/parameter/ageing reference and v1 numerical controls
where their applicability is unchanged. Pin and validate the event/charge-
integral extraction, capacity denominator and all-cycle reductions. Refinement
must settle both mandatory charging margins and potentially decision-changing
session-time ordering. A missing 80%-SOC crossing is NOT_REACHED/UNRESOLVED
for the objective, not a clipped success or a fabricated finite time.

Buyer credibility target remains **Tier3 before actual EV reliance**, with
interim Tier2 simulator matching against the assumed COMSOL workflow and
matched electrochemical/thermal decks. The [common credibility contract](reference-credibility.md)
and v1 published-benchmark candidates remain applicable, not earned evidence.
Cross-tool/lab acceptance tolerances stay HUMAN_INPUT with v1 recommendations.
Compare phase-resolved traces, charging extrema, charge-integral times and
discharge diagnostics, plus feasibility/pick agreement and regret in minutes.
Use separate non-hidden draws or verified retired published cases, never
hidden EVAL/STRESS/quiz/tuning. Credibility remains NOT_DEMONSTRATED.

## 6. Output and measurement contract

For every cycle retain phase-labelled temperature/voltage extrema, time/cycle/
phase identities, every-charge local plating minimum and capacity checkpoints
1/10/20/30. Retain whole-programme extrema **as diagnostics**, alongside the
hard charging-scope temperature reduction. Never discard a discharge peak.
For the first session report charge-integral SOC 0.10→0.80 crossing elapsed
from session start, including the 120-s initial rest, or the typed missing crossing.

Optional cooling reports must include baseline/action identity, effective
conductance and phase schedule, peak heat removal and integrated removed
energy where supported; cooler electrical cost is not equal to extracted
thermal energy. Unsupported actuator/energy models remain named gaps.

Choose the minimum resolved session time among actions passing all hard
criteria on the question's complete mandatory panel, with frozen aggregation/
ties before reference access. Secondary capacity loss and bank-order ties
remain #776 recommendations, not adopted science. Reference intervals crossing
a hard limit or overlapping enough to change the best pick require producer
refinement under separate authority, or UNRESOLVED. A complete resolved bank
with no admissible action returns NONE_FEASIBLE; failure is not reference blame.

## 7. Construction contract

KEEP reconstruction and permitted TRAIN provenance. This document adds no
candidate inputs to existing adapters, no scored thermal action and no new
Level permission. Future phase-aware task projections/optional-cooling schemas
need versioned implementation in their owning lanes. Commit model choices
before producer verification; candidates do not define the answer key.

## 8. Research kit

Reuse public Battery research/own-seed generator/reference provisions and
v1 offline calibration story/speed targets as **unmeasured goals**. The model
replaces first-pass protocol sweeps, not final reference/lab verification or
the live BMS. Publish the v2 objective, units, phase scopes and observer gap;
no protected scenario, seed or label enters research or pods. No deployment
throughput improvement was measured in this revision.

## 9. Evidence plan

Owner-reported public feasibility at
`031284d1a6f8c56f1355606908feaa737b5b9a86`, `battery-feasibility-02/`, 435
solves: **NO_VERIFIED_FEASIBLE_PROTOCOL at 25 C under the earlier brief**;
best within limits 32.9 min. The previously reported 35.6 min was derived from
30-s voltage probes; the charge-integral observer gives 63.3 min for that
reported observation. **63.3 is not the best 32.9.** Codex did not replay
these references here. V2 objective/scope revision does not retroactively
pass them or demonstrate a feasible complete five-ambient bank.

Forward Q2/Q3 changes are in [quiz impact v2](../question-laws/quiz-impact-v2.md).
Compare protocol-only and declared cooled actions with the same observer,
complete coverage and budgets; report false-feasibility, missed safe picks,
time regret, discharge diagnostics and net cost. Refined truth belongs to the
producer, never validator solves. No counted comparison, fresh confirmation,
solver execution, rig or spend is granted or run by this packet.

## 10. Readiness and claim record

KEEP v1 assets/history; NEW selected prospective objective/thermal scope and
v2 documentation. GAPS: all-phase/charge-integral observer support receipts,
optional cooling mapping, supported v2 truth, phase-aware gates/task projection,
question-law registration, reference/lab credibility and deployment evidence.
Owner requirements are SPECIFIED; document tests demonstrate consistency only.
Scientific/production/security qualification remains unearned. Coordination
goes to Test Lead/Carbon Validator/PR Lead on #643 and science on #42. EV5,
journal sequence14, live contract, family queue and 45/30/25 remain untouched.
