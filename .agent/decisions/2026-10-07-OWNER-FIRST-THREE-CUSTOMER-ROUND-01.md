## 2026-10-07 — OWNER-FIRST-THREE-CUSTOMER-ROUND-01: independent buyer requirements

**Ticket:** CHALLENGE-CUSTOMER-PACKETS-01.
**Origin:** Ryan's direct 2026-10-07 request for mock-customer packets, Motor
first, then Cooling, then Battery, on the same standard as the new five.
**Status:** selected working DEVELOPMENT requirements under rolling owner
delegation, not qualified limits or actual customer specifications.

Owner instruction (verbatim):

> Please write mock-customer packets for the first three Challenges — **motor first, then cooling, then battery** — in the same format and standard you're using for the round-1 Challenges (persona and job, the design decision, buyer-owned limits with "why it matters", cost of a wrong decision in buyer terms, customer-recognizable scenario strata for the operating envelope, acceptance criteria, deployment context incl. speed and what the model replaces, and value per decision in time or money where possible).

## Prospective scope extension

OWNER-PORTFOLIO-DEV-ROUND-01 originally covered f02/f06/f08/f13/f17 only.
Today's explicit instruction extends its customer role-play approach to the
original three **for requirements and development test criteria only**.
The earlier record, existing scientific contracts and historical evidence
keep their original meaning. No retrospective adoption or rescoring occurs.

Select buyer value before the scoring team adapts its gates/quiz/tuning.
Codex authors these briefs independently of that implementation lane. This
organizational separation reduces target fitting; it is not independent
experimental validation or proof against bias. Do not optimize requirements
until current models happen to pass. If a job is unsupported or infeasible,
record that outcome rather than loosening its limits after seeing results.

## Working choices and rationale

| Buyer | Selected decision requirements | Basis |
| --- | --- | --- |
| Precision robot-joint integrator | 6 N·m holding; 12 N·m short peak; energized ripple ≤5% and ≤0.30/0.60 N·m peak-to-peak; unpowered cogging ≤0.05 N·m peak-to-peak | Payload/link torque and a stated motion-error allocation, not 4 N·m / 0.30 TRAIN medians |
| Accelerator cooling architect | Peak die-side TIM-interface estimate ≤85 °C; full plate plus bounded manifolds Δp ≤50 kPa and hydraulic power ≤2.5 W at ≤3 L/min | Warm-inlet/high-load service target and pump allocation, not periodic-cell 100 °C / 0.25 W examples; not a solved die temperature |
| EV fleet charging calibrator | Warm 10–80% SOC ≤30 min including the existing initial rest; peak model temperature ≤45 °C; minimum plating reaction overpotential ≥0 V; Q30/Q1 ≥0.99 diagnostic | Useful charging turnaround without relaxing thermal/plating requirements; a 30-cycle screen is not lifetime |

All quantities, scenario laws, numerical verification limits and monetary
assumptions are selected **mock DEVELOPMENT requirements**. Sources establish
context and limitations, not the truth or commercial acceptance of these
numbers. Deployment populations and actual loss probabilities remain
HUMAN_INPUT. There is no new reference/training/rig/paid execution grant.

## Implementation and alternatives

Implementation: `docs/development/challenge_pipeline/round1/` three customer
packets, `first-three-requirements.json`, index, and
`tests/cpu/test_first_three_customer_packets.py`. Branch
`codex/customer-packets-first-three`, starting main `0e7308fe9`.

KEEP existing domain/reference/validator ownership. Rejected: copying TRAIN
medians; changing existing exams in this packet PR; treating a static motor
curve, periodic cooling cell or lumped cell model as a deployed system;
claiming a 0-V model margin proves absence of physical plating; calling
hypothetical savings traction; creating another grader or compute runner.

Interface impact is **documentation-only prospective requirements**. Test
Lead/Carbon Validator may integrate in their own versioned tickets after
this packet lands. Motor needs per-scenario torque/cogging handling; Cooling
needs full-manifold observations; Battery needs explicit SOC/timing custody.
None of those runtime changes is implemented here. Numerical criteria must
actually be demonstrated before reliance. Existing 45/30/25 stays a candidate.

## Reversibility, notifications and reserved authority

Supersede the affected packet and numeric sheet prospectively if the buyer
job changes. Preserve earlier versions and results once observed; do not
relabel old outcomes against a new brief. This change has no runtime
migration cost. Notification: science #42 (@harshaa765), PR Lead/Carbon
Validator/Test Lead #643. Continuing without a routine approval wait.

Scientific qualification, true cell/material adequacy, security acceptance,
rights, deployment and launch remain HUMAN_INPUT. Protected EVAL/STRESS
cases/seeds/labels remain operator-side. Battery EV5, sealed journal sequence
14 and the live contract are untouched. Family queue/protocol stay unchanged.
The five-family $160 / 46-node-hour / 202-launch allowances are not extended
to these briefs. Change this decision and the corresponding new packet/sheet
to revise a requirement; an execution flag or score edit cannot supply any
reserved authority. Recommendation if unchanged: KEEP.
