# STAGE-A-REPORT-AUTOMATION-01

**Status:** DEVELOPMENT working contract. Owner request 2026-10-10.
No hidden data, solver run, spend, LIVE change or score-rule change.

## Contract

Take #942's digest-bound Stage A development-summary manifest and run its
existing alignment analyzer. Add #953's committed Stage A refused-capability
JSONL (strict rows with counts, role, run and UTC span) and a closed
spend summary (observed USD spend per committed grant). Produce a compact
stage-end Markdown owner one-pager and a JSON aggregate. Missing comparisons
stay UNMEASURED; refusal frequencies rank investigation candidates, not
approved Level 5 capabilities. #953's JSONL is produced from per-run extracts
after the runs; this script never infers missing refusals.

## Decisions

KEEP #942's analyzer as the score/value authority; WRAP its output. Verify
each grant's cap against its committed grant document. Report cap overrun as
an observation, never suppress it. A JSONL digest does not prove that every
run refusal was extracted; the owner one-pager carries that limit. Hub map_ref
`SYSTEM/AGENT-EXECUTION`, with no Hub edits because the
Hub is retired. Maturity ceiling: tested development report tooling.
