# Challenge development protocol: draft v0.1

**Phase 1, step 2 of the Challenge Roadmap** (`Design_Specs/Challenge_Roadmap.md`),
ticket CHALLENGE-PROTOCOL-02. The four stage definitions, with battery as the
worked example.

**Status: DRAFT.** It becomes protocol v1.0 only when the process owner
approves it at lock (step 8). Steps 3 to 7 will change it. Where it differs
from the roadmap, the roadmap governs. Values marked `HUMAN_INPUT` are open;
§7 lists who sets each one.

## 0. What it reuses

The protocol adds stages and a common suite on top of machinery Carbon
already has. It does not replace any of it.

| Existing | Its role here |
| --- | --- |
| Challenge admission (`Design_Specs/Challenge_Admission.md`, OWNER-CHALLENGE-ADMISSION-01) | Tracks A and B are the suite's two tracks. The frozen study sheet (§2 there) is what freeze pins. The decision and evidence package (§5 there) is the frozen evidence record. The trigger model (expand freely, escalate on a finding) governs iteration before freeze. |
| Construction permission levels 0–5 (admission §3) | The construction freedom a challenge is tested at. A higher level opens only with an expansion record (#468). |
| The campaign controller (`carbon/agent_campaign/controller.py`) and Graphite's roles (`carbon/agent_campaign/graphite/roles.py`) | Graphite runs only through the controller, under a grant. The per-stage permission ledger (§6) says which roles may act at which stage. |
| Checkout boundaries (`carbon/agent_campaign/boundaries.py`) | Graphite's sessions never receive evidence, tickets, the controller or protected material. The sealed pool is generated under an operator-held root outside the repository, as the cold plate, motor and photonic private pools are. |
| Readiness records (`carbon/challenge_readiness/`) | Each challenge's readiness record stays its machine-readable design summary. The design packet points to it. |
| Pipeline records (`carbon/challenge_pipeline/`) | Hold each family's stage, gates, timings and frozen results, and enforce who signs what. |

## 1. Stage 1: Prioritize

- **Entry.** The protocol is locked. The family is the highest-ranked queued
  family in `docs/development/CHALLENGE_PIPELINE.md`, and the previous family
  has left Design (roadmap §04).
- **Work.**
  - **Check each prerequisite.** For every family it builds on that is ranked
    lower and still queued (the view's "prerequisite later" column), decide
    whether to pull the prerequisite forward or build it inside this
    challenge, and record which.
  - **Confirm the v1 scope and exclusions** from the family's design brief
    (`families.json`: `first`, `inputs`, `preds`, `ref`, `exam`, `ev`,
    `build`, `exp`).
  - **List prior work and reusable infrastructure** (the family's pipeline
    record, `prior_work`).
- **Graphite.** Reader, Planner and Writer.
  - It drafts the challenge brief, and lists reusable infrastructure and
    missing prerequisites.
  - No compute grant: nothing is run at this stage.
- **Output.** The challenge brief (`templates/CHALLENGE_BRIEF.md`), committed
  and linked from the pipeline record (`evidence.brief`).
- **Exit.** The science owner accepts the scope (gate `scope`), and the
  record moves to `design`.

**Battery, worked example.**
- Battery does not pass through Prioritize: it defines the protocol (Phase 1).
- Its brief would be the family's `first` scope: one cell chemistry and
  parameter-set family, starting from the existing contract, without silently
  replacing its objective or expanding to packs. The status record
  (`BATTERY_STATUS_2026-10-02.md` §1) supplies the contract.
- It has no lower-ranked prerequisite (`needs` is empty).
- Battery discharge (f15) builds on battery and would be scoped as a
  separate family.

## 2. Stage 2: Design

- **Entry.** An accepted brief (gate `scope`).
- **Work**, in the order the design packet records it:
  1. **Pin the reference build:** exact solver version and image digest,
     discretization, tolerances, deterministic settings, failed-case policy.
  2. **Analytical or manufactured controls, and refinement:** the reference's
     numerical-correctness evidence (roadmap §06, level 1).
  3. **A 30-case stratified feasibility panel** across the center,
     boundaries and difficult combinations.
  4. **Timing on the reference hardware:** setup, solve, post-processing and
     failures separately; warm and cold; peak memory; p50 and p95.
  5. **The case generator, and the splits:** by whole geometry, trajectory or
     regime.
     - Public practice, permitted construction data, development holdout,
       rotating exam batches, an anchor set and the sealed pool.
     - Distinct interpolation, boundary and out-of-envelope panels.
     - Dimensionless regimes registered.
  6. **The construction contract and cheap baselines:** direct solver with
     reuse, interpolation, and a reduced-order model where one exists.
- **Graphite.** Planner, Constructor, Reader and Writer.
  - It drafts the generator, splits and construction contract, and proposes
    reference, refinement and timing studies. Carbon's runner executes them
    under the stage's grant.
  - It never generates, reads or holds the sealed pool.
  - Gap: Graphite has no reference-study tool yet. Until one exists, the
    executor runs these studies and Graphite drafts around their results.
- **Output.**
  - The design packet (`templates/DESIGN_PACKET.md`), linked as
    `evidence.design_packet`.
  - The timing study, linked as `evidence.timing`, with the record's `p50s`,
    `p95s`, `cases` and `hw` (which must be the reference hardware). The
    queue then re-ranks on the measured time.
- **Exit.** The science owner signs the design (gate `design`). The record
  moves to `test`, and the next queued family may enter Prioritize.

**Battery, worked example.** Battery's existing work maps onto the packet as
follows. Gaps are named, not filled.

| Packet section | Battery today | Gap |
| --- | --- | --- |
| Engineering decision | Choose a feasible fast-charge protocol under a fixed objective (EV1/EV2/EV4 decision contracts in `carbon/battery/value/contracts/`) | none for v1 |
| Scope and data | `carbon/battery/domain.py`, the published input box | units and regimes to restate in the packet |
| Reference | PyBaMM 26.8.0.0 DFN, OKane2022, lumped thermal, IDAKLU; pinned truth image (`carbon/battery/reference.py`, `truth.py`) | Refinement evidence to cite; **p50/p95 not measured on reference hardware**, which is not yet chosen |
| Construction | `BATTERY_CONTRACT` (`carbon/reconstruction/capability_registry.py`), recipes in `carbon/battery/recipes.py` | JAX-only vs PyTorch is an open owner question (§7) |
| Evidence | Exam rule v1 (`carbon/battery/exam.py`), screening batches and finals, private pool under an operator-held root | Anchor set, disclosure budget and a sealed pool that never enters rotation are not registered as such |
| Baselines | EV panels include kNN and synthetic controls | Direct-solver-with-reuse, interpolation and reduced-order baselines not registered |

## 3. Stage 3: Test / iterate

- **Entry.** A signed design packet (gate `design`).
- **Work.**
  - **Run the common suite**: Track A's eight attack vectors, Track B's
    EV1–EV3 and baselines, and any challenge-specific attacks added on top.
    - Suite v1, a DRAFT, is `carbon/challenge_pipeline/suite_v1.json`.
    - `python -m carbon.challenge_pipeline suite <challenge>` reports each
      Track A vector's coverage against the suite's pin.
  - **Fix what breaks, and tune construction rules and scoring.** Repeat
    within the iteration budget (`HUMAN_INPUT`, §7).
  - The admission trigger model applies throughout. Widening needs no
    per-change review. Every widening is recorded (#468). A finding (score-
    value divergence, a failing trigger, a gate anomaly) stops the widening
    and escalates (#470), and is never suppressed.
  - **Freeze**, then run the pinned suite on the sealed pool once.
- **Graphite.** Attacker (Track A), Constructor (the legitimate panel),
  Optimizer researcher (design-search methods on development material),
  Planner and Writer.
  - **Before freeze only.** At freeze its stage grant ends.
  - The frozen run is Carbon's evaluation role
    (`boundaries.Role.EVALUATION`), never dispatched to an external provider.
- **Freeze (roadmap §02).** These are pinned and committed before the frozen
  run:
  - the suite version;
  - the harness code commit;
  - the scoring digest;
  - the sealed pool's root commitment;
  - the frozen study sheet (admission §2).

  A change after freeze creates a new challenge version and a new frozen run.
- **Output.** The frozen evidence record (`templates/FROZEN_EVIDENCE_RECORD.md`),
  linked as `evidence.frozen`. Its results enter the pipeline record:
  - the suite version;
  - open critical, high, medium and low findings, graded by the technical
    owner;
  - rank agreement ρ;
  - independent scenarios *n* and false-feasible events *k*;
  - regret.
- **Exit.** The technical owner signs Track A (gate `track_a`) and the
  science owner signs Track B (gate `track_b`). The record moves to `ready`.

**Battery, worked example.** Steps 4 and 5 of Phase 1 are this stage.
- **Track A.** These instruments exist:
  - the admission protocol (#473);
  - the divergence detector (#470);
  - the expansion record (#468);
  - the tier 3B leak ladder (#472).

  No suite version grades findings yet.
- **Track B.** EV1, EV2 and EV4 (with Problem C) ran under frozen
  pre-registrations. EV3 as the roadmap defines it has not run.
- **The frozen run** on a sealed pool has not happened.
- **Iteration log.** Battery's iteration log so far is its study history:
  EV1 → EV2 → the decision-aware proposal → EV4, and tiers 1–3B.

## 4. Stage 4: Rank for deployment

- **Entry.** A frozen evidence record.
- **Work.** Apply the rubric gates and order the board
  (`carbon.challenge_pipeline.roadmap.board_rows`, roadmap §05).
- **Graphite.** Writer only. It compiles the evidence summary from the
  frozen record. It has no role in grades.
- **Output.** A leaderboard position in the generated view.
- **Exit.** The process owner picks deployments (gate `deploy`, stage
  `deployed`). Network activation stays a separate owner decision. A
  deployment is not scientific, security or production qualification, and
  confers no LIVE or reward authority.

**Battery, worked example.** Battery's first leaderboard entry is Phase 1
step 5's output. Until rubric v1 is approved, it lists without eligibility.

## 5. Stop rules

Park a challenge (stage `parked`) when any of these holds:
- its reference costs more than its budget;
- numerical uncertainty is larger than the decision margin;
- a cheap baseline already matches it;
- it still fails the rubric when the iteration budget runs out.

A parked challenge keeps its records, and re-enters the queue only with a
changed scope. The budget and margin values are `HUMAN_INPUT` per challenge
(§7). The record's notes name the rule that parked it.

## 6. Graphite permission ledger (draft)

Machine-readable in `carbon/challenge_pipeline/graphite_ledger.json`. The
role names are Graphite's (`carbon.agent_campaign.graphite.roles.RoleName`).
A role absent from a stage is refused at that stage.

| Stage | Graphite roles allowed | Compute grant |
| --- | --- | --- |
| Prioritize | reader, planner, writer | none |
| Design | reader, planner, constructor, writer | Design studies, under the stage's grant |
| Test / iterate, before freeze | planner, constructor, attacker, optimizer_researcher, reader, writer | Iteration runs, under the stage's grant |
| Test / iterate, frozen run | none | Carbon evaluation only |
| Rank for deployment | writer | none |

At every stage Graphite never:
- reads or writes the sealed pool;
- edits the pinned harness or a frozen record;
- holds a grade, a gate or evaluator authority;
- receives official seeds, confirmation references or private validator
  state.

Its outputs are drafts until a named owner signs the stage gate. A wider
construction freedom it proposes is tested as a separate experiment before
admission (roadmap §02).

**Not yet wired.** The controller does not read this ledger yet. Running
battery through Test/iterate with Graphite (step 4) needs the controller to
refuse a role outside its stage's row. That wiring is part of step 3's
harness work.

## 7. Open values: set during battery, approved at lock

| Value | Proposed by | Approved by | State |
| --- | --- | --- | --- |
| Rubric thresholds: ρ, false-feasible bound, scenario count, regret | science owner, from battery's frozen results (step 6) | process owner | `HUMAN_INPUT` |
| Test suite v1: attack vectors, severity rules, EV studies | technical owner (Track A), science owner (Track B), step 3 | process owner | DRAFT (`suite_v1.json`; severity rules drafted for the technical owner) |
| Graphite permission ledger and procedure | this draft (§6) | process owner | DRAFT |
| Exam rotation cadence and sealed-pool size | science owner | process owner | `HUMAN_INPUT`. Battery's rule v1 rotates screening batches of 100, 3 active. |
| Per-challenge iteration budget and stop-rule values | technical and science owners, from battery's cycle-time baseline (step 7) | process owner | `HUMAN_INPUT` |
| Reference timing hardware | technical owner | technical owner alone (rev 2.1) | **Approved** 2026-10-02 (OWNER-CHALLENGE-ROADMAP-02), below |
| Backends admitted by Track A vector 1 | owner | owner | **Decided** 2026-10-02: JAX and PyTorch (OWNER-CHALLENGE-ROADMAP-02) |

**Reference timing hardware, approved.** A RunPod CPU pod, recorded in
`protocol.json` as `runpod-cpu5c-16vcpu` with the technical owner's approval:
- flavor `cpu5c` with no fallback, so every measurement runs on the same CPU
  family;
- 16 vCPU;
- the challenge's pinned image.

Each timing study records the CPU model it ran on. The earlier pool pods,
created with a fallback flavor, landed on two different processors (EPYC
9655P and 4564P).
- **Why this hardware.** Anyone on the team can rent the same machine, so a
  measurement can be repeated and checked. The cold plate and motor pools
  already ran natively on such pods, and matched the owner host's container
  results to round-off.
- **What it costs.** About USD 0.03 per vCPU-hour at list price.
- **Who approved it.** The owner approved it on 2026-10-02 and made it the
  technical owner's approval alone (roadmap rev 2.1).
