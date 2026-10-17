# PRD03-ASSESSMENT-HOLD-01 — preserve frozen reference authority

Ticket: PRD-03 / DECISION-ASSISTANT-01, same PR #1222.
Status: IMPLEMENTED_WORKING_DECISION; bounded engineering repair. Hub retired.

Concrete inspection of the first candidate found that a READY assessment callback
could override the search's SOLVER_NOT_ACCEPTED binding and run three synthetic
reference calls. The current owner hold must survive all subsequent assessment.

Preserve both configured-executor and Guard-record holds in the result pins and
independent assessment. Changed acceptance needs a new configured run, never
silent reassessment under wider authority. Record the assessment reference's exact
image/record/runtime. Locations: `carbon/product/decision_assistant/core.py` and
`tests/cpu/test_product_decision_assistant.py`. Five regression cases cover each
executor failure/hold and a Guard-only hold without a configured executor.

Alternative rejected: accept a later READY flag as authority to remove a recorded
hold. Reversible by explicit policy migration in those owner paths; no scientific
acceptance or qualification is selected here. Supersede this record to change it.
Carbon Validator/Data Collection review the same PR; PR Head/owner owns merge.

Focused native interactions after repair: 207 passed; pinned Black/Ruff clean.
The timing fixture stays pinned to first candidate
`f5bd7abd0383a3fc2469a6403b53b239b79c6483`, not a new measurement. Current-use
acceptance, real core costs and physical validity remain HUMAN_INPUT. Exact-head
CI and handoff are external evidence, never an evidence-only commit.
