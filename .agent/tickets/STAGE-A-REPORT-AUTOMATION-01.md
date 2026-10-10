# STAGE-A-REPORT-AUTOMATION-01

**Status:** DEVELOPMENT working contract. Owner request 2026-10-10.
No hidden data, solver run, spend, LIVE change or score-rule change.

## Contract

Take #942's digest-bound Stage A development-summary manifest and run its
existing alignment analyzer. Add a closed, aggregate refused-capability
summary (capability ID, level, closed refusal code per occurrence) and a closed
spend summary (observed USD spend per committed grant). Produce a compact
stage-end Markdown owner one-pager and a JSON aggregate. Missing comparisons
stay UNMEASURED; refusal frequencies rank investigation candidates, not
approved Level 5 capabilities. The native Testing Manager refusal-log schema
is not committed on main, so the intake format is explicitly an interim
operator summary until that producer contract is supplied.

## Decisions

KEEP #942's analyzer as the score/value authority; WRAP its output. Verify
each grant's cap against its committed grant document. Report cap overrun as
an observation, never suppress it. Neither digest nor self-declared
completeness authenticates a manager log; the owner one-pager carries that
limit. Hub map_ref `SYSTEM/AGENT-EXECUTION`, with no Hub edits because the
Hub is retired. Maturity ceiling: tested development report tooling.
