# Challenge readiness: the launch portfolio

**What this is.** It is #347's first deliverable. There is one versioned
readiness record per launch-portfolio Challenge:
- `carbon/challenge_readiness/records/<challenge_id>.v<N>.json`;
- validated by `carbon/challenge_readiness/record.py`;
- schema `carbon.challenge-readiness.v3`.

**The training budget study** (OWNER-TRAINING-BUDGET-STUDY-01, schema v2).
Every record carries a required `training_budget_study` block: its state,
result report and owner decision. The validator refuses a launch approval
unless the study is `COMPLETE`. This checks the readiness record; the LIVE
qualification/activation path remains separate.
Every record starts `NOT_STARTED`. The spec is
`docs/development/CHALLENGE_TRAINING_BUDGET_STUDY.md`.

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

## Provenance: what in each record is evidence, and what is a placeholder

Audited 2026-09-27. Every path a record cites resolves on `main`. The
registry identity (`challenge_id`, `tracking`) is enforced by the validator.

Kinds of field:
- **Verified.** Recounted from raw files by the tests.
- **Relayed.** Taken from an existing record, not rerun.
- **Placeholder.** A declared unknown, or a proposal awaiting review.

| Field | Battery | Cold plate | Motor | Photonics |
|---|---|---|---|---|
| Identity and tracking | verified against the registry | verified | verified | verified |
| Decision, intended use | from code and campaign docs | proposal (#342) | proposal (#344) | proposal (#345) |
| Buyer | hypothesis | hypothesis | hypothesis | hypothesis |
| Design variables, outputs, units | from `carbon/battery/domain.py` | proposal; the parameter list is not fixed | proposal; not fixed | proposal; not fixed |
| Reference solver | PyBaMM 26.8.0.0 overlay, verified (truth-verify) | OpenFOAM v2512 candidate, verified on channel flow and uniform-flux heat transfer only (rungs 1 and 2) | placeholder (none) | fdtdx, relayed; diagnostic only |
| Licence | placeholder (not recorded) | GPL-3.0 as published; redistribution not reviewed | placeholder | placeholder |
| Pilot outcomes | verified (recounted from `records.jsonl`) | none | none | verified (recounted) |
| Costs | measured and relayed (reference, reconstruction, discarded); **estimated** (finalist, inference); unknown (startup, cleanup) | all unknown | all unknown | **estimated** (reference); the rest unknown |
| Limits | proposed OD-2 DEVELOPMENT values; none approved | none declared | none declared | none declared |
| Population | proposed; none approved | proposed | proposed | proposed |
| Reviews | none approved; security IN_REVIEW, where OD-3 covers the testnet images only | none started | none started | none started |
| Recommendation | PROCEED, on verified counts | none: no pilot has run | none | DEFER, relayed from RESULT section 9 and #345 |

**Corrections made by this audit** (v1 to v2; v1 remains in git history):
- **Battery finalist cost (USD 0.29).** `measured` → `estimated`. It is
  composed from separately measured parts and was never measured as one run.
- **Photonics reference cost (USD 0.36).** `measured` → `estimated`. It is
  extrapolated from one measured run time of about 265 s.
- **Cold-plate reference.** Now records the pinned OpenFOAM candidate and the
  rung-1 channel-flow verification. Maturity stays `SCOPED`: a channel-flow
  check is not a cold-plate pilot.

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

## Two-track admission (schema v3)

[Challenge Admission](../../Design_Specs/Challenge_Admission.md) is now a standing
requirement. `admission_tests` binds construction-integrity and engineering-value
studies to one exact challenge version and capability profile. The validator
refuses a launch-approved record until both are ACCEPTED with matching frozen
criteria, reports, retained evidence hashes and scoped review decisions. It
verifies file completeness and bindings, not human identity or scientific truth.

Both new tracks start NOT_STARTED in all four catalogue records; prior battery
EV work remains supporting evidence. Their `admission_blockers` appear in the
validate command. A valid record is not an accepted challenge. Schema v2 cannot
be used to omit the new fields. Catalogue filenames remain stable in this schema
migration and previous bytes remain in git history. No runtime permission,
scoring rule, historical result or qualification state changes.
