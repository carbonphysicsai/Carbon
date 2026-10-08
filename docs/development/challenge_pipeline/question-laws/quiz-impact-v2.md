# Packet v2 — prospective question laws and Q2/Q3 changes

**CHALLENGE-CUSTOMER-PACKETS-02 / DEVELOPMENT / SPECIFIED only.** Owner's
2026-10-08 packet choices supersede affected Battery/Cooling semantics in
#776 for **future versioned work**, not historical quizzes or runtime.
[proposals-v2.json](proposals-v2.json) replaces only those two complete rows
of [v1](proposals.json); the other six and common P/Q/w, custody, diversity,
refinement and E policies are inherited unchanged. There is no runtime
amendment resolver/sampler in this ticket. New sampling, bands, score use,
power, aggregation and thresholds remain Test Lead/science HUMAN_INPUT.

## A. Buyer-question law changes

| Item | Historical v1 | Prospective v2 |
| --- | --- | --- |
| Battery time | Grid 25/30/35/40-min caps; continuous [25,40]-min cap | **No time-cap axis**. Minimise resolved session-start 10–80% time; aggregation/ties still need adoption |
| Battery thermal scope | Whole-programme 42.5/45-C caps | Charging-only 42.5/45-C proposals; all CC/CV charging legs; discharge/rest temperatures diagnostic |
| Battery remaining requirement variation | Capacity 0.99/0.995 | Unchanged proposed grid and continuous [0.99,0.995] |
| Battery grid capacity | 16 vectors | **4 vectors**, at most4 resolved answers, possibly one. Do not ask for8 distinct grid questions or pad/redraw |
| Cooling physical contexts | Old raw-source/ambiguous hotspot map at plate | Post-spreader interface map with explicit buyer spreader/lid properties and characterization |
| Cooling threshold proposals | 80/82.5/85 C and 20/25/30 kPa; continuous alternatives | Same proposed numeric envelopes, but new thermal quantity/reference identity; cell pressure allocations remain HUMAN_INPUT |
| Cooling alternatives | Earlier geometry/TIM/source suggestions | **Report TIM/ratio/inlet alternatives, select none**; no implied easier service population |

Battery k=8 remains only a **continuous-variant planning recommendation**;
the owner must select a supported law before use. Continuous draws can still
share one winner. Actual expected distinct winners under P and Q, feasible/
NONE_FEASIBLE shares, close-call and residual-unresolved rates remain
NOT_DEMONSTRATED/null. Grid and continuous alternatives use the same eligible
truth and residual E. Neither extra decimals nor a new packet/task ID renews
exposure. Changed Cooling maps/physics need new reference coverage and identities;
they are not a threshold-only remapping of old solves. Public/retired reuse
requires matched physical identity and release provenance, never hidden cases.

No redraws to repair NONE_FEASIBLE or force diversity. Power comes from the
separately specified diagnostic Q; selection/enrichment does not change P or
adopt w as a score weight. The old Battery ~68-CPU-h quiz measurement remains
historical-only. Costs of these revised banks remain UNMEASURED; solve counts
435/128 are not per-case timings.

## B. Battery Q2 — phase-aware near-limit cases

**Content change required.** The historic producer-only battery_quiz.py and
registryv8 stay unchanged. A future v2 registry must bind new observer/task
identities and answer keys before any candidate evaluation.

- Near-limit 45-C cases use all **charging** CC/CV legs, including later
  cycles. A hot test-discharge leg alone is not a failed charging-temperature
  verdict; retain its phase-labelled peak as a diagnostic. Do not hide it.
- Keep the every-charge 0-V local model plating boundary and retained voltage/
  capacity checks. Charge/rest/discharge reductions must remain separate;
  missing coverage is UNRESOLVED, not a favorable maximum or a candidate zero.
- **30 minutes is not a feasibility boundary**. For turnaround diagnostics,
  compare time errors/near-tied candidate choices using the pinned charge-
  integral crossing and session-start clock, not voltage probes. Objective
  ties/near-ties can change the design pick even without a hard-limit crossing.
- Cooling is optional. Compare a cooled action only with a declared supported
  cooling model/phase/energy identity; no selected h multiplier or free cooler.

Edge-optimist understates charge maxima/plating deficits or time of a
potentially winning action. Over-cautious rejects safe slow charging, including
by incorrectly reinstating a 30-min gate. Local sign-error perturbs charge-
integral current/SOC or phase-local thermal/plating sign. Optimizer/lattice-
aware behaves accurately on announced control points but errs on unseen
supported decision-changing actions. Accurate boundary optima are not gaming.
Control magnitudes and bands stay HUMAN_INPUT, fixed before answer access.

## C. Battery Q3 — shortest admissible session, not fastest under30min

Draw from the new grid/continuous law on the complete registered panel and
finite action bank. Apply hard charging 45 C / plating 0 V and retained voltage/
capacity constraints before ranking. Minimise session-start 10–80% minutes
with precommitted context aggregation and ties (worst 25/35 C is the existing
recommendation, **not newly adopted here**). Report time by ambient and
test-discharge diagnostics. A 32.9-min action is not rejected just because
it exceeds 30 min; this does not prove it satisfies all v2 requirements.

Use charge-integral SOC crossing with the pinned capacity basis, including
the retained 120-s rest. Missing 80% crossing is NOT_REACHED/UNRESOLVED for
objective coverage, not finite clipping. Do not certify a best pick if an
unresolved competitor might be better. Produce NONE_FEASIBLE only from a
complete resolved bank failing its actual hard criteria. No redraws.

Refine time/event steps and all-cycle charging reductions where reference
intervals might change hard verdicts **or objective ordering/regret**. A
temperature-only refined bank is insufficient if two times remain ambiguous.
Producer refinement needs separate authority; validators never solve references.

## D. Cooling cell Q2/Q3 — explicit post-spreader interface

**Content change required** for the Cooling half of
[Motor/Cooling quiz v1](motor-cooling-quiz.md); **Motor content is unchanged**.
No full-cold-plate or manifold questions/witnesses are added.

Q2 near-85-C cases bind the improved-cell geometry, buyer spreader/lid properties,
post-spreader flux plane/map, TIM convention and local spatial peak. Derive
`max(T_plate_face + R_TIM*q_interface)` at matching coordinates. Raw die
source maps are not interchangeable with interface maps. Map/integral or
reference-support failures are UNRESOLVED reference findings, not candidate
physics failures. Cell pressure boundaries remain proposed allocations.

Q3 grid/continuous draws use the same complete supported new interface panel
and declared geometry/flow bank. Sensitivities for TIM, ratio and inlet have
their own input identity/report; they are **not selected** to manufacture a
pass. Min-worst-cell-pressure / thermal secondary / bank-order remains the
#776 recommendation, not an adopted objective. Refine local hot regions and
pressure where hard verdicts or ranking can flip; retain unresolved competitors.

Retain the four v1 behavioural controls but apply them to v2 observables:
edge-optimist suppresses the local interface maximum; over-cautious rejects
safe cells; sign-error corrupts the local TIM increment/pressure convention;
optimizer/lattice-aware is accurate only at known points. A uniform 81.2-C
witness does not supply feasible hotspot keys; old >=117-C hotspots do not
establish the revised map's answer. Do not invent a physically feasible bank.

## E. Diagnostics (a)–(e), credibility and integration

- **(a) Optimizer stability:** rerun matched deterministic search/ties on fixed
  v2 truth; report pick agreement/regret in minutes or cell Pa, not old time
  gate pass rate or assembly watts. Algorithm seeds are not fresh questions.
- **(b) Grid resolution:** distinguish requirement thresholds from physical
  bank spacing; test objective near-ties and spatial/event resolution as well
  as mandatory edges. Continuity does not demonstrate new action coverage.
- **(c) Power by k:** retain shared-bank clusters/E, resolved winner occupancy,
  feasible/none-feasible mix and reference missingness. A 4-vector Battery
  grid does not supply 8 distinct questions. Thresholds/power stay HUMAN_INPUT.
- **(d) Agreement with decision value:** report false-feasibility, missed safe
  choices, best-pick agreement and bidirectional regret, alongside pointwise
  errors. Discharge-only heat is diagnostic; charging thermal failure cannot
  be compensated by speed. Missing/no picks do not count as successful parity.
- **(e) Unresolved rate:** separate absent buyer inputs, unsupported cooling/
  heat maps, missing phases/SOC crossings, near-tied objective truth,
  refinement budget and infrastructure. Never turn reference failure into
  a candidate score penalty.

Matched cross-tool witnesses use v2 limits, phase/map observations and value
objectives under the shared credibility contract. Decision-agreement thresholds
stay HUMAN_INPUT; systematic disagreement is a future reference revision,
not a candidate failure. Already-sealed results retain their original identity.

Integration seam **MIGRATION_REQUIRED**: tasks.py uses a limit on each listed
condition, so charging-only role projections/diagnostic discharge must be
versioned by the Test Lead/Carbon Validator. Its objective/tie mapping must
not keep the old deadline. Cooling needs a new map/observer contract and
supported bank identity; old die/full-assembly quantities cannot stand in.
This documentation ticket changes no runtime, optimizer, registry, active
#802/#783 work, EV5, journal14 or live contract. No hidden material, solver
run, counted/fresh campaign, spend, qualification or45/30/25 adoption.
