# POWER-PLANNING-01 working contract

**Scope:** DEVELOPMENT simulation and recommendation only. The owner requested
power tables for battery v3, motor and f02 using the question-law proposals in
`docs/development/challenge_pipeline/question-laws/` and published aggregate
panel shapes. No reference solver, private bank, hidden case, AX42 input, paid
compute, LIVE change or adopted scoring/bank policy is in scope.

The script takes **assumed** per-independent-bank probability that the good
model beats a behaviour control, the control's severity expressed in buyer
units, question count B, independent-bank count, k, exposure E and windows.
It samples sequential questions while charging every draw to its underlying
bank's exposure. A shared bank contributes one sign-test observation across
questions and windows. Detection uses the neutral harness's one-sided exact
sign test at an explicitly supplied alpha. Conditional power is computed from
the assumed bank effect; it is not inferred from unresolved producer exports.

The output is aggregate-only: exposure feasibility, distinct bank count and
detection probability with Monte Carlo error for every scenario. It must show
the present one-bank state separately, including its inability to reach
alpha=0.05. Proposed P, Q and w stay separate; simulation uses no observed
P/Q rates and calls its hypothetical question draws a planning assumption.
Requirements and buyer units come from #919, #922 and #927 but their
HUMAN_INPUT values remain recommendations. Costs are labelled as scenarios,
not quotations or spending authority.

**Primary historical map_ref:** `SYSTEM/DEVELOPMENT-SEQUENCING`. The current
delivery protocol retires Hub maintenance; this ticket does not edit its files.
KEEP the neutral sign-test semantics and question-law sheets; WRAP their
aggregate shapes in a standalone development simulation. No runtime score or
validator interface changes.

Plan: add a deterministic stdlib simulation, checked-in assumption manifest,
aggregate tables and a concise interpretation; test clustering, exposure,
determinism and refusal of invalid assumptions; run focused and canonical CI;
hand one PR at its exact head to PR Lead. Test Lead and owner select any
real k/E, severities and qualification after settled evidence exists.
