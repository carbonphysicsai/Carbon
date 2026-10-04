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

The launch portfolio is the eight challenges of OWNER-LAUNCH-PORTFOLIO-02
(`Design_Specs/Eight_Challenge_Foundation_Plan.md`, §4). It replaced
OWNER-LAUNCH-PORTFOLIO-01's four on 2026-10-04. Records exist so far for the
four carried over: battery, AI-chip cold plates, electric motors and silicon
photonics. The other four get records when they are mapped to registry IDs
(the plan's F0). The records make them comparable for readiness and cost. **They grade nothing.** Each Challenge keeps its own
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
| chip-cold-plate | PILOTED | MEASURED | 20 | 2 / 0 | startup, reconstruction, inference, finalist, cleanup | 7 / 7 | 0 of 5 | PROCEED |
| electric-motor-magnetics | PILOTED | MEASURED | 17 | 0 / 0 | startup, reconstruction, inference, finalist, cleanup | 4 / 4 | 0 of 5 | PROCEED |
| photonic-coupler | PILOTED | MEASURED | 12 | 0 / 0 | startup, reconstruction, inference, finalist, cleanup | 5 / 5 | 0 of 5 | PROCEED |

### Cooling post-record decision study

The cold-plate row remains the v6 readiness record and its 20-case reference
pilot denominator; it is not silently rewritten by later evidence. After that
record, the separate `CHALLENGE-AI-COOLING-FOUNDATION-01` synthetic decision
study completed 48/48 Docker/OpenFOAM cases with no retry. All four registered
arms selected `d03`; CFD confirmed its six conditions feasible; and the
complete eight-design finite comparator also selected `d03`, with exact
finite-set regret 0.0 W for each arm. See
`docs/development/evidence/ai-cooling-counted-v1/` for identities, hashes,
costs, claim ceiling and retained-artifact status.

That result does not change the readiness row's population, approvals, review
states or qualification maturity. It is one frozen synthetic DEVELOPMENT
decision problem, not population reliability, customer acceptance or a
full-manifold result.

**How to read it:**
- **Cases OK and failures** are recounted by the tests from each pilot's
  retained `records.jsonl`, so they cannot drift from the evidence.
- **Failures are split** into reference failures and infrastructure failures,
  and never charged to a candidate.
- **Photonics changed its reference in v4.** The repaired local-supermode
  model replaced the diagnostic 3D FDTD (CHALLENGE-PHOTONIC-01). The FDTD
  runs and their failures stay in v3, in git history. v4 counts only its own
  pilot.
- **An unknown cost stays unknown.** The cold plate, motor and photonic
  measured costs are their references on the owner's host, at no marginal
  spend. Everything else they declare is unknown.

## Provenance: what in each record is evidence, and what is a placeholder

Audited 2026-09-27, and updated 2026-10-02 by CHALLENGE-READINESS-RELAY-01
for cold plate v5, motor v3 and photonics v4, then by CHALLENGE-COLD-PLATE-01
slice 4 for cold plate v6 and CHALLENGE-MOTOR-01 slice 4 for motor v4.
Every path a record cites
resolves on `main`. The
registry identity (`challenge_id`, `tracking`) is enforced by the validator.

Kinds of field:
- **Verified.** Recounted from raw files by the tests.
- **Relayed.** Taken from an existing record, not rerun.
- **Placeholder.** A declared unknown, or a proposal awaiting review.

| Field | Battery | Cold plate | Motor | Photonics |
|---|---|---|---|---|
| Identity and tracking | verified against the registry | verified | verified | verified |
| Decision, intended use | from code and campaign docs | from the package and ticket (CHALLENGE-COLD-PLATE-01) | from the package and ticket (CHALLENGE-MOTOR-01) | from the package and ticket (CHALLENGE-PHOTONIC-01) |
| Buyer | hypothesis | hypothesis | hypothesis | hypothesis |
| Design variables, outputs, units | from `carbon/battery/domain.py` | from `carbon/cold_plate/domain.py`: nine inputs, three predicted outputs | from `carbon/motor/domain.py`: eight inputs, a 60-angle torque curve | from `carbon/photonic/domain.py`: two inputs, cross power and common phase at five wavelengths |
| Reference solver | PyBaMM 26.8.0.0 overlay, verified (truth-verify) | OpenFOAM v2512, pinned; verified rung by rung (`scripts/dev/cold_plate/`), the package reference against rung 6e (rung 7) | GetDP 3.5.0 and Gmsh 4.15.2, pinned; Carbon's own models, verified by rungs M1-M3 | Carbon's FDFD mode solver; committed 10 nm supermode tables, pinned to their sources |
| Licence | placeholder (not recorded) | GPL-3.0 as published; redistribution not reviewed | GPL, run on the operator host only; benchmark files not used | Carbon's own code; numpy and scipy BSD-3-Clause |
| Pilot outcomes | verified (recounted from `records.jsonl`) | verified (recounted): rung 7 and the 16-case pilot | verified (recounted): the 17-case pilot | verified (recounted): the 12-case pilot |
| Costs | measured and relayed (reference, reconstruction, discarded); **estimated** (finalist, inference); unknown (startup, cleanup) | **measured** (reference: local host, no marginal spend); the rest unknown | **measured** (reference: local host, no marginal spend); the rest unknown | **measured** (tables and reference: local host, no marginal spend); the rest unknown |
| Limits | proposed OD-2 DEVELOPMENT values; none approved | seven proposed DEVELOPMENT values; none approved | four proposed DEVELOPMENT values; none approved | five proposed DEVELOPMENT values; none approved |
| Population | proposed; none approved | proposed | proposed | proposed |
| Reviews | none approved; security IN_REVIEW, where OD-3 covers the testnet images only | none started | none started | none started |
| Recommendation | PROCEED, on verified counts | PROCEED, on the pilot's verified counts; both baselines scored on the private pool | PROCEED, on the pilot's verified counts; both baselines scored on the private pool | PROCEED, on the pilot's verified counts; both baselines scored on the private pool |

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
individually before it runs. Under OWNER-CHALLENGE-DESIGN-01 (2026-10-01),
pilots on the owner's local host, at no marginal spend, run under the
design delegation; paid compute still needs its own grant.

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

[Challenge Admission](../../Design_Specs/Challenge_Admission.md) is an
**internal development protocol** (OWNER-CHALLENGE-ADMISSION-01 as amended on
2026-10-01): never mainnet, not miner-facing, not a qualification gate.
`admission_tests` binds construction-integrity and engineering-value studies to
one exact challenge version and capability profile. Review moves from every
change to every finding:
- **Track A:** records each expansion in a ledger without per-change review.
  A finding stops widening, and acceptance is one lock of a recorded state,
  bound to both ledgers.
- **Track B:** a full review names its trigger (`STUCK`, `WINNING` or
  `OWNER_REQUEST`).

The validator refuses a launch-approved record until both tracks are ACCEPTED
with matching frozen criteria, reports, retained evidence hashes and the scoped
lock or review. It verifies file completeness and bindings, not human identity
or scientific truth.

Both new tracks start NOT_STARTED in all four catalogue records; prior battery
EV work remains supporting evidence. Their `admission_blockers` appear in the
validate command. A valid record is not an accepted challenge. Schema v2 cannot
be used to omit the new fields. Catalogue filenames remain stable in this schema
migration and previous bytes remain in git history. No runtime permission,
scoring rule, historical result or qualification state changes.
