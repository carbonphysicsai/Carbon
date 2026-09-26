# Challenge readiness: the launch portfolio

**What this is.** It is #347's first deliverable. There is one versioned
readiness record per launch-portfolio Challenge:
- `carbon/challenge_readiness/records/<challenge_id>.v1.json`;
- validated by `carbon/challenge_readiness/record.py`;
- schema `carbon.challenge-readiness.v1`.

The portfolio is battery, AI-chip cold plates, electric motors and silicon
photonics (OWNER-LAUNCH-PORTFOLIO-01). The records make them comparable for
readiness and cost. **They grade nothing.** Each Challenge keeps its own
scientific ruler.

**Status.** Every record is a `PROPOSED_DEVELOPMENT_DESIGN`.
- No population, limit or review is approved.
- Nothing is scientifically, security or production qualified.
- A passing test here is engineering evidence only.

## The table

Regenerate it with `python -m carbon.challenge_readiness table`.

| Challenge | Reference execution | Baseline | Cases OK | Reference / infra failures | Unknown cost items | Limits awaiting approval / declared | Reviews approved | Recommendation |
|---|---|---|---|---|---|---|---|---|
| battery-fastcharge-ageing-development-v1 | CAMPAIGN_COMPLETE | MEASURED | 2631 | 0 / 4 | startup, cleanup | 3 / 3 | 0 of 5 | PROCEED |
| chip-cold-plate | SCOPED | NOT_STARTED | 0 | 0 / 0 | startup, mesh, reference, reconstruction, inference, finalist, cleanup | 0 / 0 | 0 of 5 | NONE |
| electric-motor-magnetics | SCOPED | NOT_STARTED | 0 | 0 / 0 | startup, mesh, reference, reconstruction, inference, finalist, cleanup | 0 / 0 | 0 of 5 | NONE |
| photonic-coupler | PILOTED | NOT_STARTED | 6 | 13 / 16 | startup, mesh, reconstruction, inference, finalist, cleanup | 0 / 0 | 0 of 5 | DEFER |

**How to read it:**
- **Cases OK and failures** are recounted by the tests from each pilot's
  retained `records.jsonl`, so they cannot drift from the evidence.
- **Failures are split** into reference failures and infrastructure failures,
  and never charged to a candidate.
- **Photonics' reference failures** include two runs recorded as
  `REFERENCE_SOLVER_FAILED` whose cause was configuration (the ptxas
  `TMPDIR`, and the mode solver's CPU device). Their pilot notes say so; the
  counts are kept as recorded.
- **An unknown cost stays unknown.** Cold plate and motor have no measured
  cost at all.

## Order of work

Owner decision, 2026-09-26:
1. **Battery.** It proceeds as a launch Challenge.
2. **Cold plate.** Starts with the #342 first task.
3. **Motor**, as a small feasibility assessment (#344).
4. **Photonics**, starting with the phase-convention and convergence repair
   (#345). There is no photonic exam design before that repair.

Each cold-plate, motor or photonic reference pilot is priced and approved
individually before it runs.

## What the record enforces

These properties are enforced when a record is built, not left to convention:
- **Failure type.** A pilot's outcomes come from a closed reference and
  infrastructure vocabulary, and attribution is derived from the outcome. A
  candidate outcome such as `GATE_FAILED` is refused in a reference pilot.
- **Evidence behind maturity.** Maturity above `SCOPED`, and a `PROCEED` or
  `NARROW` recommendation, need at least one case that ran `OK`.
- **Costs.** A cost with basis `unknown` or `not_applicable` carries no
  amount, and a `measured` cost names its evidence.
- **Approved limits.** A limit is approved only under a named authority, with
  the scientific review `APPROVED` under that same authority. The v1 schema
  records a proposed population only.
- **Reviews.** Numerical reference, scientific, security, customer and launch
  are separate axes. Launch cannot be approved ahead of the others.
- **Identity.** Units come from a fixed set. The record's `challenge_id` and
  `tracking` must match `carbon.challenge_registry`, and duplicate attempt
  ids are refused.
- **Evidence import.** It reads a file and nothing else. The tests forbid
  sockets and subprocesses during import.

## Reuse decisions (KEEP / WRAP / REPAIR)

| Component | Decision | Reason |
|---|---|---|
| `carbon.challenge_registry` | KEEP, used as the join key | Stable ids and tracking issues already exist. Registry `version=None` is not faked. |
| `scripts/dev/exam_design/runner.py` `records.jsonl` | WRAP: imported read-only | The source of pilot attempts and typed outcomes. |
| `scripts/dev/exam_design/{exam,scoring,gates,campaign}.py` | KEEP, not reused as defaults | Battery research code. Its batch, rotation and margin values are not imported as defaults (#341, #347). |
| `carbon.seeding`, scoring, admission (GPU/MCP) | KEEP, unchanged | Readiness records are not an input to any of them. |
| `carbon.registry` (A3) `HUMAN_INPUT` idiom | WRAP as a pattern | Limits carry `HUMAN_INPUT` or a proposed value, plus an approval slot. |
| `carbon.registry.store` | Not used | A LIVE-gate store that rejects JSON numbers, so it cannot hold costs or limits. |
| `d_qual_prep_01` readiness record | WRAP as a pattern | The model for per-axis review states. |
| Carbon Fit `QUANTITY_STATUS` | WRAP as a pattern | The measured / estimated / unknown cost basis. |
| `carbon/gauntlet/readiness.py`, `resource_policy` readiness | KEEP, not reused | Domain-specific and heavyweight. |
| Workbench | REPAIR later | A read-only readiness view is the next slice. Nothing consumes these records yet. |

No scheduler, scorer, seed service or evidence store was added.
