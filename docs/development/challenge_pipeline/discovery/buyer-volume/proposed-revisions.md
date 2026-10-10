# Proposed V3 and V2 revisions — old and new side by side

**No canonical file changes and no retrospective rescore.** This proposal
preserves the framework in [value-cost](../../value-cost/README.md), and uses
main `3a6dfdd8dffdfdaf241596033d5bf55b66abfcff` as the old-input snapshot.
The new evidence changes provenance and units, not positive scenario amounts.

All tuples are **low / base / high**. Every positive scenario below is
**ASSUMPTION**, inherited from the linked old input. `HUMAN_INPUT` means no
verified exact quantity. A reported proxy is separate from the exact volume
field. Numeric observations and transfer restrictions are in
[evidence.json](evidence.json).

## Battery v3

Old inputs: [battery scorecard](https://github.com/carbonphysicsai/Carbon/blob/3a6dfdd8dffdfdaf241596033d5bf55b66abfcff/docs/development/challenge_pipeline/value-cost/battery.md)
and [volume/leverage JSON](https://github.com/carbonphysicsai/Carbon/blob/3a6dfdd8dffdfdaf241596033d5bf55b66abfcff/docs/development/challenge_pipeline/value-cost/volume-leverage.json).

| Field | Old | Proposed new | Evidence for change |
|---|---|---|---|
| Engineering cadence | ASSUMPTION **2 / 6 / 12** map revisions/BMS team/year | Preserve scenario; measured **HUMAN_INPUT / HUMAN_INPUT / HUMAN_INPUT** | B01–B04 confirm workflow and a release trigger, not a calendar cadence |
| V3 deployment quantity | ASSUMPTION **7,500 / 210,000 / 3,300,000** eligible sessions/year | Preserve scenario; exact eligible count **HUMAN_INPUT / HUMAN_INPUT / HUMAN_INPUT** | B05 adds a direct national session proxy; eligibility/adoption/buyer cohort missing |
| External sourced anchor | Vehicle-stock examples, with eligibility unmeasured | Separate **>16,000,000 / HUMAN_INPUT / HUMAN_INPUT** network sessions in 2024 | [B05 company filing](https://efiling.energy.ca.gov/GetDocument.aspx?DocumentContentId=103159&tn=266135); censored lower bound only |
| Evaluations per new decision | ASSUMPTION transfer **224 / 1,120 / 11,200** complete band/context programmes | Preserve sensitivity; exact buyer count **HUMAN_INPUT / HUMAN_INPUT / HUMAN_INPUT** | B06 is a protocol menu; B01–B03 give no exact simulation count |
| V2 per deployed eligible session | ASSUMPTION **USD 0.20 / 1.50 / 6.00** | Preserve scenario; incremental benefit **HUMAN_INPUT / HUMAN_INPUT / HUMAN_INPUT** | B01 whole-workflow acceleration and B03 adjacent test savings cannot be transferred |
| Conditional annual gross | ASSUMPTION **USD 1,500 / 315,000 / 19,800,000** | Preserve labelled scenario; realised/net value **HUMAN_INPUT / HUMAN_INPUT / HUMAN_INPUT** | No matched-admissibility benefit, adoption or capture-rate evidence |
| V3/V2 evidence status | NOT_DEMONSTRATED | NOT_DEMONSTRATED; V3 has a partial operational proxy | No exact annual buyer quantity or incremental V2 established |

The old session arithmetic uses vehicles **100 / 1,000 / 10,000** × eligible
sessions/vehicle-day **0.3 / 0.7 / 1** × operating days/year
**250 / 300 / 330**, all ASSUMPTION. The V2 chain is minutes saved/session
**1 / 3 / 6** × USD/minute **0.2 / 0.5 / 1**, all ASSUMPTION. These are
sensitivity illustrations, not public measurements.

Do not multiply engineering hours saved per map by deployed sessions.
Count offline engineering benefit at the map-revision level; count demonstrated
charge-time/energy/lifetime benefit at eligible deployment sessions. Separate
attributable recipients and exclude overlapping cost/time effects. Reusing an
unchanged verified map for a different ambient mixture requires no new recipe
bank, as the [v3 question draft](../../question-laws/battery-ambient-indexed-v3.md)
already explains. No charging limit or degradation scope is changed.

## Motor — robot-joint magnetics

Old inputs: [motor scorecard](https://github.com/carbonphysicsai/Carbon/blob/3a6dfdd8dffdfdaf241596033d5bf55b66abfcff/docs/development/challenge_pipeline/value-cost/motor.md)
and the same pinned volume/leverage JSON.

| Field | Old | Proposed new | Evidence for change |
|---|---|---|---|
| V3 quantity | ASSUMPTION **20 / 180 / 1,200** shortlist-changing revisions/year | Preserve scenario; exact count **HUMAN_INPUT / HUMAN_INPUT / HUMAN_INPUT** | M01 commercial adaptation supports job; M02 catalogue reuse prevents shipment/joint-count multiplication |
| Annual cadence | ASSUMPTION **2 / 6 / 12** revisions/team/year, teams **10 / 30 / 100** | Preserve scenario; measured team/cadence **HUMAN_INPUT / HUMAN_INPUT / HUMAN_INPUT** | M01–M04 publish no annual magnetic-design ledger |
| Evaluations per revision | ASSUMPTION transfer **50 / 505 / 2,000** complete command panels | Preserve sensitivity; actual buyer panel count **HUMAN_INPUT / HUMAN_INPUT / HUMAN_INPUT** | M04 adds a newer robot-actuator study but separates setup from cheap optimizer evaluations |
| V2 per revision | ASSUMPTION **USD 200 / 900 / 3,200** | Preserve scenario; incremental avoided rework **HUMAN_INPUT / HUMAN_INPUT / HUMAN_INPUT** | No buyer before/after rework evidence; electronics/control roles are adjacent |
| Conditional annual gross | ASSUMPTION **USD 4,000 / 162,000 / 3,840,000** | Preserve labelled scenario; realised/net value **HUMAN_INPUT / HUMAN_INPUT / HUMAN_INPUT** | No observed adoption or incremental benefit |
| V3/V2 evidence status | NOT_DEMONSTRATED | NOT_DEMONSTRATED; buyer integration and relevant research analogue supported | No exact annual volume verified |

The old V2 chain is ASSUMPTION rework hours **2 / 6 / 16** × ASSUMPTION
USD/hour **100 / 150 / 200**. A job-posting base salary cannot replace a
fully loaded hourly cost, and faster analysis is not automatically fewer paid
engineering hours. Current [motor packet](../../../MOTOR_DECISION_DESIGN_PACKET.md)
magnetostatic scope is narrower than complete speed/thermal/controller
qualification. No peak-torque feasibility failure is softened.

## Package warpage and solenoid pole

Old inputs: [discovery data, pinned snapshot](https://github.com/carbonphysicsai/Carbon/blob/3a6dfdd8dffdfdaf241596033d5bf55b66abfcff/docs/development/challenge_pipeline/discovery/data.json).
The discovery ordinal V2 is ASSUMPTION **1 / 2 / 3** and ordinal V3 is
ASSUMPTION **0 / 1 / 2** for each candidate. Preserve both; do not treat these
ordinals as demonstrated gate passes or as a substitute for economic quantities.

| Candidate/field | Old ASSUMPTION low / base / high | Proposed new | Support |
|---|---|---|---|
| D016 teams × decisions/team/year | **5 / 20 / 50** × **4 / 12 / 24** | Preserve scenarios; observed factors **HUMAN_INPUT / HUMAN_INPUT / HUMAN_INPUT** | W01–W03 confirm design/DOE/FE workflow, no annual count |
| D016 V3 decisions/year | **20 / 240 / 1,200** | Exact measured quantity **HUMAN_INPUT / HUMAN_INPUT / HUMAN_INPUT** | Shipments and package variants are not fresh full-history stack decisions |
| D016 V2 EUR/decision | **120 / 540 / 1,920** | Incremental value **HUMAN_INPUT / HUMAN_INPUT / HUMAN_INPUT** | No attributable avoided rework versus calculators/cached FE |
| D016 conditional annual gross EUR | **2,400 / 129,600 / 2,304,000** | Preserve scenario; realised/net **HUMAN_INPUT / HUMAN_INPUT / HUMAN_INPUT** | Neither volume nor incremental benefit verified |
| D012 teams × decisions/team/year | **5 / 20 / 50** × **6 / 24 / 60** | Preserve scenarios; observed factors **HUMAN_INPUT / HUMAN_INPUT / HUMAN_INPUT** | S01–S03 confirm custom-development and industrial optimization |
| D012 V3 decisions/year | **30 / 480 / 3,000** | Exact measured quantity **HUMAN_INPUT / HUMAN_INPUT / HUMAN_INPUT** | Bosch study counts are within one workflow, not annual frequency |
| D012 V2 EUR/decision | **180 / 720 / 2,400** | Incremental value **HUMAN_INPUT / HUMAN_INPUT / HUMAN_INPUT** | Existing Bosch metamodel reduces the plausible new advantage |
| D012 conditional annual gross EUR | **5,400 / 345,600 / 7,200,000** | Preserve scenario; realised/net **HUMAN_INPUT / HUMAN_INPUT / HUMAN_INPUT** | No measured incremental Carbon benefit or adoption |

**Index consequence:** no new empirical value-to-cost index is computable.
Do not mix USD and EUR or substitute a whole-toolchain speed claim into V2.
Historical assumption indices remain historical scenarios, not measured
rankings. The defensible economic floor for incremental value remains zero;
zero is a boundary, not an estimate that the customer gains nothing.
