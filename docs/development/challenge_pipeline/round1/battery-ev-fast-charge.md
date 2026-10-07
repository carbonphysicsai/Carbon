# Battery — an EV fleet charging customer's DEVELOPMENT packet

**Role-play:** a hypothetical EV fleet/BMS calibration engineer, not an actual
OEM cell specification, warranty or field safety claim. **Authority:**
[OWNER-FIRST-THREE-CUSTOMER-ROUND-01](../../../../.agent/decisions/2026-10-07-OWNER-FIRST-THREE-CUSTOMER-ROUND-01.md).
Ten-section F1 format; numeric companion:
[first-three-requirements.json](first-three-requirements.json). EV5, its sealed
journal sequence 14 and the live/historical Battery contracts stay unchanged.

## 1. Engineering job

“My delivery fleet needs predictable charging turnaround. Choose a cell-specific
two-stage charge protocol that shortens a 10–80% SOC stop without spending
thermal headroom or hiding plating/degradation risk. Give my calibration team
a verified protocol to investigate, not an autonomous BMS control policy.”
The action is (c1,c2); cell identity, ambient/initial state and ageing history
are conditions. Keep the existing 30-cycle task, not a cheaper single charge.

| Buyer-owned requirement | Why it matters |
| --- | --- |
| 10–80% SOC stop ≤30 min at 25/35 °C, including the specified 120-s initial rest | Bound warm-condition vehicle turnaround; cold/hot cases must be reported, not promised equally fast |
| Peak model cell temperature ≤45 °C throughout the complete declared programme | My selected thermal/longevity allocation; **keep 45 °C**, do not raise it to make warm cases pass |
| Minimum model lithium-plating reaction overpotential ≥0 V over all declared charging episodes | Keep the numeric development boundary; never compensate a sign violation with faster charging |
| Cell voltage ≤4.2 V under the pinned protocol | Preserve the specified terminal-voltage ceiling and termination semantics |
| Q30/Q1 ≥0.99 for the specified capacity checkpoints | A ≤1% 30-cycle diagnostic degradation budget, **not** life/warranty certification |

**Would I change 45 °C? No in this round.** Higher-temperature fast-charge
research is cell/protocol-specific; it does not justify relaxing this buyer's
budget or changing the existing exam's separate limits. The 0-V requirement
is for the pinned model observable, not a universal experimental test for
absence of plating. Real local temperature/kinetic heterogeneity and model
uncertainty still require cell-specific evidence.

**Wrong decision:** an aborted charge costing 15 min at an assumed loaded
driver rate of $30/h costs **$7.50/session**. A pack replacement might cost
**$12,000** in this hypothetical procurement scenario; no event probability
or expected safety-loss estimate is inferred. Safety harm is not priced away.
The cell model cannot estimate pack failures or warranty risk from 30 cycles.

If verification reduces a previously measured 35-min stop to 30 min, buyer
value is **5 min or $2.50/session** at that driver rate. A hypothetical 20-vehicle
fleet, two sessions/day, 250 days/year gives **$25,000/year gross opportunity**;
not realized savings, demand, contract value or Carbon revenue. One calibration
revision saving eight engineering hours at $150/h is **$1,200 gross**. Net
benefit must subtract model creation, independent verification and operation.

## 2. Physical system

KEEP [reference.py](../../../../carbon/battery/reference.py): pinned PyBaMM
26.8.0.0 DFN, OKane2022 parameters, lumped thermal model, SEI/porosity and
partially reversible lithium-plating options. The truth environment's exact
image/overlay and extraction identities remain controlling, not latest docs.
Parameters are a specified simulated cell, not the fleet's measured cells.

Current actions: c1=0.5–2.0 C, c2=0.2–1.0 C; rest 120 s, c1 to 4.0 V, c2
to 4.2 V, CV to C/20. Preserve rest/discharge/rest, 30 cycles and checkpoints
1/10/20/30. Inputs ambient 5–40 °C and initial SOC 0.05–0.5. Capacity/rate
normalization must use the pinned cell definition, not a guessed EV pack size.

An **80-kWh pack** is customer context only. Under a stated linear nominal
energy/SOC illustration, 10–80% represents 56 kWh, averaging 112 kW over
30 min. This is not the DFN's power output or a cell-to-pack scaling proof.
Charger limits, contactors, pack gradients, cooling, preconditioning and real
BMS actuation are excluded until separately modelled/validated.

## 3. Population P, Q and w

Five mock service strata: unconditioned winter start (5 °C), cool morning
(15 °C), conditioned depot (25 °C), warm repeat use (35 °C), heatwave parking
(40 °C). Pair each proposed (c1,c2) with all five at initial SOC=0.10 and
the complete 30-cycle programme. The 30-min speed goal applies to the two
25/35-°C strata; **all five** retain thermal/plating/voltage/capacity limits.
Cold-condition failure must yield a slower admissible alternative or
UNRESOLVED/NO_VERIFIED_FEASIBLE_PROTOCOL, not silently vanish from reporting.

`P_dev` assigns equal synthetic mass to these five conditions, not actual
weather/use frequencies. Diagnostic `Q` is the complete panel plus separately
labelled initial SOC 0.30/0.50 and near-limit protocol controls; the latter
do not answer a 10%-start turnaround claim. Freeze the finite protocol list
before observing references. `w=1` per protocol/condition for descriptive
counts; never weight away an unsafe or unresolved stratum. Cell-parameter
sets/whole independent experiments would be real generalization units;
cycles and time samples from one simulated cell are correlated. Deployment P,
batch laws and official evidence/score weighting remain HUMAN_INPUT.

## 4. Case contract

Pin simulated cell/parameters, protocol termination, initial SOC/temperature,
complete ageing sequence, solver/time/mesh settings and observer version.
Reject nonfinite/out-of-bound inputs and unsupported cells/protocols. Cache
identity includes SOC/timing measurement pins, not only voltage traces.
Public documentation exposes the mock job, not protected cases/seeds/labels.
No new packet ID activates a Challenge or changes sealed EV5 material.

## 5. Reference policy

KEEP present truth/custody and historical solver policy. Existing mesh20→40,
IDAKLU rtol1e-5/atol1e-7→1e-6/1e-8 and 30-s observations are starting assets,
not empirical adequacy for this new timing/customer decision. Selected
DEVELOPMENT convergence demands are successive-refinement differences ≤10 mV
voltage, ≤0.5 °C temperature, ≤2 mV minimum plating margin, ≤0.25% capacity
relative to Q1, and ≤30 s first-charge 80%-SOC crossing time. Keep a consistent
output basis and refine time/event extraction as well as mesh/tolerances.

Controls include low-current, cold high-current, warm thermal boundary,
localized negative-plating-margin and near-capacity-loss cases. Inspect
spatial/time minima before reducing to a scalar; coarse output probes cannot
erase a between-probe excursion. Reference uncertainty intersecting 0 V,
45 °C or another boundary is UNRESOLVED even if a nominal value passes.
There is no newly invented safe buffer or physical plating certification.

Real-cell parameter adequacy, sensor uncertainty and empirical plating
corroboration remain NOT_DEMONSTRATED for this buyer. Reference failure is
missing truth, not candidate scientific failure. No paid/counting/fresh
campaign or alteration of EV5 evidence occurs here.

## 6. Output and measurement contract

Existing voltage/temperature vectors use 121 time probes over the first hour;
plating margin is one scalar from cycle-1 charging and capacity is a vector
at the declared checkpoints. The existing retained solutions cover cycle 1 and checkpoints
10/20/30; current diagnostics do **not** establish a maximum across every
intermediate cycle. Current plating extraction is the minimum during cycle-1
charge steps, not all 30 charges. The buyer's all-programme 45-°C requirement
is prospectively stronger in scope than EV5's frozen first-hour 45-°C rule;
the same number does not mean the same measurement or gate.

Require a prospective retained/streaming observer of temperature and voltage
extrema across the whole programme and local plating minima over **every
charging episode**, with event/time/spatial coverage and uncertainty. Do not
relabel current checkpoint diagnostics as all-cycle acceptance. A terminal-
voltage crossing is **not** an 80%-SOC observation.
For the new buyer, define cycle-1 first-charge SOC from the pinned initial
SOC and charge-current integral using a declared capacity basis; retain the
current and capacity provenance and root/event interpolation. Report elapsed
time from session start, **including initial rest**, to the first 80% crossing.
Do not count discharge/recharge as continued first-charge time. If 80% is not
reached in the complete first-charge horizon, report NOT_REACHED with the
horizon; a one-hour clipped trace cannot supply a fabricated time.

These all-cycle and timing observers are **needed prospective implementations**, not exposed in the
present public output contract. Later cycle charges start from their pinned
post-discharge state; do not call every cycle a 10%-SOC start. Capacity loss
uses `(Q1-Q30)/Q1` with Q1>0 and exact checkpoint definitions; do not infer
vehicle range/lifetime from that diagnostic.

For the dimensional screen only, assume the SOC-transfer capacity equals
the C-rate capacity (ratio 1). The future observer must pin/verify that
normalization; a different ratio changes this lower bound. At c1≤2 C,
transferring 70% of that declared rate-capacity takes **at least
21 min** at constant 2 C, plus the 2-min rest = **23 min** before slower
stages/taper. Thus an 18-min 10–80% headline is unsupported by this bounded
action set on that normalization. The 30-min goal is a testable demand,
**not a demonstrated feasible protocol**. Do not quietly raise the C-rate.

**Acceptance of a mock shortlist:** independently verify the precommitted
protocol, every mandatory condition and the warm turnaround target, with
reference uncertainty resolved. Rank feasible protocols by worst warm-stratum
stop time, then lower 30-cycle capacity loss, then frozen protocol order.
Return NO_VERIFIED_FEASIBLE_PROTOCOL if appropriate. No average score can
compensate a plating sign error. Integration requires a new versioned
measurement/decision contract; existing grades remain unchanged.

## 7. Construction contract

KEEP current reconstruction and TRAIN-only allowed data/backends. Register
any SOC/timing output prospectively; no extra hidden observer is supplied
through practice. A model proposes a protocol; trusted independent reference
verification adjudicates it. A research tool is not a BMS safety controller.
No new construction permission or training budget is set in this packet.

## 8. Research kit

Reuse the public Battery kit, protocol vocabulary, own-seed generation and
current practice documentation. Use CCCV rules, reduced electrochemical
models and interpolation/cached references as serious baselines. The new
timing observer and warm-target acceptance are explicit gaps, not falsely
advertised public APIs. Keep all protected material operator-side.

**Deployment:** a cell-calibration engineer's offline workstation. Target
warm-model p95 ≤0.10 s for its declared trajectory output on a pinned CPU
profile; 100 proposed protocols ×5 service strata ≤50 s inference and a
shortlist within 10 min including overhead. Timing must include any new
observer/extrapolation cost. These are unmeasured targets, not live BMS
control-loop latency. Replace first-pass DFN protocol sweeps, not independent
DFN confirmation, physical cycling, pack integration or release acceptance.

## 9. Evidence plan

KEEP existing ageing/development evidence and its localized-error findings.
Future Test Lead/Validator work should compare equal search budgets and
common-case references, freeze protocols before independent verification,
and report false-feasibility/abstention, turnaround regret in **minutes**,
30-cycle diagnostic loss and full net time/money per calibration revision.
Attack controls must catch smooth voltage hiding a negative plating minimum,
clipped charge horizons, wrong capacity/rate normalization and warm-only
reporting of a cold-unsafe protocol.

Actual cells/batches, rights, reference adequacy, deployment population,
training-budget study, experimental safety, spend and sealed confirmation
require separate authority. No tuning on final confirmation, no counted or
fresh campaign in this ticket. The five new families' allowances do not fund
this EV story. 45/30/25 is still a scoring candidate, not buyer acceptance.

## 10. Readiness and claim record

KEEP: current DFN/reference/extraction, BatteryAdapter neutral replay,
[F1 worked example](../BATTERY_DESIGN_PACKET_WORKED_EXAMPLE.md), frozen EV
studies and #716 neutral-path verification. NEW: fleet persona, quantitative
cost/value assumptions, warm charge-time goal, scenario law and timing/all-cycle
observer gaps.
Requirements are SPECIFIED; offline consistency checks do not qualify an EV
or demonstrate real-cell safety, life, charger performance or paid demand.
Next engineering gate is the prospective timing/decision-measurement contract
after coordination with Test Lead/Carbon Validator (#643); science #42.

Primary context: [PyBaMM's plating example](https://docs.pybamm.org/en/latest/source/examples/notebooks/models/lithium-plating.html)
shows model/parameter dependence; it is not the pinned runtime version.
[NREL temperature-effects research](https://research-hub.nlr.gov/en/publications/fast-charging-of-li-ion-cells-part-iv-temperature-effects-and-quo/)
motivates temperature-dependent charging evidence, not a universal 45-°C law.
[PNAS research on temperature heterogeneity](https://doi.org/10.1073/pnas.2009221117)
is a reason not to equate a model 0-V pass with proof of no physical plating.
[Hyundai's conditional charging example](https://ownersmanual.hyundai.com/full_webhelp/NE1/2024/en_US/id2ad241b6107.html)
provides market context for an 18-min expectation, not a target transferable
to this cell, charger or permitted 2-C protocol.
