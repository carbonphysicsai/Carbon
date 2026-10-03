# Challenge Roadmap

How Carbon designs, tests and ranks challenges: one pipeline, defined on
battery, run in priority order across 26 simulation families.

| Field | Value |
| --- | --- |
| Document | Challenge Roadmap |
| Revision | 2.2 |
| Date (UTC) | 2026-10-02 |
| Status | Direction approved |
| Process approver | Fitz |
| Technical | Ryan |
| Science | Harshdeep |

| Rev | Date | Change |
| --- | --- | --- |
| 2.2 | 10-02 | Owner amendments (OWNER-CHALLENGE-ROADMAP-03): the construction ladder (Challenge Admission §3, Levels 0-5) is the spine of construction iteration; every Challenge starts at Level 0 and climbs one level at a time, and battery's Phase 1 includes its first climb. Graphite proposes the capabilities for every level of every Challenge, and the construction contract owner accepts them. The protocol is Challenge-neutral and improves through recorded revisions, with a lessons entry after every execution. Graphite is the testing agent. Corrects rev 2.1's backend wording: JAX and PyTorch are where Carbon rebuilds a declarative recipe, not executable submissions. |
| 2.1 | 10-02 | Owner amendments (OWNER-CHALLENGE-ROADMAP-02): admission and rebuilds accept every backend the construction contract supports (JAX and PyTorch); the reference timing hardware is approved by the technical owner alone and is a RunPod CPU pod, flavor cpu5c, 16 vCPU. |
| 2.0 | 10-02 | Rebuilt around one pipeline: Prioritize → Design → Test/iterate → Rank for deployment. Battery defines the protocol with Graphite. In-house challenges only; customer track, Workbench and commercial gates removed. Deployment leaderboard added. |
| 1.1 | 10-02 | Current solve time added as a third, equally weighted ranking factor. |
| 1.0 | 10-02 | First proposal: 26-family ranking, contracts, test tracks, gates. |

## How this document is held in the repository

- **Authority.** The owner adopted this roadmap as Carbon's standing challenge
  development pipeline on 2026-10-02 (OWNER-CHALLENGE-ROADMAP-01 in
  `.agent/DECISIONS.md`, which also classifies how it meets earlier
  decisions). The text below is the roadmap as written. A change to it is a
  new revision with its own row in the table above.
- **Source.** The roadmap page at
  `https://claude.ai/artifact/Ea5rm63kTBhaPeMiUW8u5p`, version
  `1790946516-a04e`. Its family data (§04 and §07) are transcribed exactly
  into `carbon/challenge_pipeline/families.json`, with the page's SHA-256.
- **Machinery.** `carbon/challenge_pipeline/` ports the page's arithmetic
  (queue, false-feasible bound, leaderboard) and holds the pipeline's
  versioned state: the protocol, the rubric, one record per family with its
  construction level (`ladder.py`), and the lessons log (`lessons/`). The
  page's shared store remains the owners' interactive view, with the same
  record fields; the repository copy is the versioned one.
- **Generated view.** `docs/development/CHALLENGE_PIPELINE.md`, regenerated
  by `python -m carbon.challenge_pipeline render` and checked by the tests.
- **Phase 1 work** is tracked step by step in
  `carbon/challenge_pipeline/protocol.json`, one ticket per step.

---

## 00 Operating model

### One pipeline, defined on battery, run on every challenge.

Carbon's core capability is taking a simulation family from "has a solver, a
plan and data" to "tested, with construction and scoring optimized", the same
way every time. Battery goes through first and defines the protocol. Once
Fitz approves it, the protocol is locked, and every other challenge goes
through the same stages and the same test suite in priority order. Challenges
deploy in order of how cleanly they survive attack and how closely their score
tracks engineering value.

- **Phase 1. Battery defines the protocol.** Stage definitions, test suite
  v1, rubric, the construction ladder's climb procedure and Graphite
  procedure, built and proven on battery.
- **Protocol lock.** Fitz approves.
- **Phase 2. Every challenge, in priority order.** Same stages, same suite.
  Ranked on the deployment leaderboard as each one finishes testing.

| Stage | Name | Summary | Output or exit |
| --- | --- | --- | --- |
| 1 | Prioritize | The three-factor ranking picks the next family; prerequisites are checked. | Output: challenge brief. Harshdeep accepts scope. |
| 2 | Design | Pin the solver, write the plan, build the data. Measure real solve time. | Exit: challenge has solver, plan and data. Harshdeep signs. |
| 3 | Test / iterate | Attack suite and score-to-value tests; optimize construction and scoring; final run on the frozen suite. Iterate, then freeze. | Exit: tested, construction and scoring optimized. Ryan and Harshdeep sign. |
| 4 | Rank for deployment | Rubric gates, then order by score-to-value match and attack cleanliness. | Output: leaderboard position. Fitz picks deployments. |

### Start where we are; add construction freedom slowly.

Construction freedom grows one level at a time on the construction ladder
(Challenge Admission §3, `carbon/challenge_pipeline/ladder.py`). Every
challenge enters Test/iterate at Level 0, its pinned recipe and registered
operations. It climbs only by the climb procedure in §02, and only after the
level below is tested. A level Carbon cannot yet rebuild is NOT_RUN, never a
pass.

**The climb is internal testing.** Graphite climbs on development-only
contracts that miners never see. When testing is done, the owners choose the
challenge's best construction level. The challenge is then frozen, locked and
opened to miners at that level (owner, 2026-10-02: "This is all internal
testing. We choose a best construction level. Then lock and open challenge to
miners!").

### Generalizable, and improved as we go.

The protocol is Challenge-neutral. Battery is its first instance, never its
design. Each challenge supplies its own records and the shared machinery reads
them:
- its brief and design packet;
- its construction contract, with the contract's map onto the ladder;
- its expansion records;
- its campaign and readiness record.

After every execution, a lessons entry records what ran, what happened
against what was expected, what to keep and what to change
(`carbon/challenge_pipeline/lessons/`). An execution is a test run, a campaign
session, a pod run, a ladder climb, an optimizer pilot, a coverage run or a
stage gate. A lesson that should change the protocol is a proposed revision.
A named owner adopts or declines it, and an adopted revision becomes a
recorded change: a roadmap revision, a protocol version or a suite version.
Nothing changes silently.

### Who does what

- **Fitz.** Approves the protocol at lock, approves the rubric, and picks
  deployments from the leaderboard.
- **Ryan.** Owns the construction contract, the attack suite and pinning the
  test harness. Signs Track A results.
- **Harshdeep.** Owns references, data, scoring and the score-to-value tests.
  Proposes rubric thresholds. Signs Design and Track B results.
- **Graphite.** Works in every stage: drafts briefs and design packets, runs
  reference, refinement and timing studies, attacks construction and exams,
  and proposes construction and scoring changes. Every action is logged
  against a per-stage permission ledger. It does not produce or touch the
  frozen results used for deployment ranking.

### Settled 2 October

- Battery defines the testing and design protocol.
- Graphite runs throughout the workflow.
- In-house challenges only. Customer pilots and Workbench intake are outside
  this plan.
- Challenges enter the pipeline in three-factor priority order.
- Deployment goes to the challenges with the cleanest attack results and the
  closest score-to-value match.

### Set during battery, approved at lock

- Rubric thresholds for rank agreement, false-feasible bound, scenario count
  and regret.
- Test suite v1: attack vectors, severity rules, EV studies.
- Graphite permission ledger and operating procedure.
- The construction ladder's climb procedure, proven on battery's first climb.
- The lessons log and how a proposed revision is adopted.
- Exam rotation cadence and sealed-pool size.
- Per-challenge iteration budget and stop rules.

The reference timing hardware is approved by the technical owner alone
(rev 2.1): a RunPod CPU pod, flavor `cpu5c`, 16 vCPU, each challenge's pinned
image.

---

## 01 Phase 1: Battery defines the protocol.

Battery goes first because it carries the most evidence: PyBaMM DFN
references, engineering-value work, EV1 complete with weak positive ranking
alignment and one boundary-optimist failure, EV2 running and EV3 designed as
of 29 September, and construction and threat work around PR 458. [C1] [C2]
Those statements are dated; reconcile them against the repository before
building on them.

### Steps

1. **Reconcile battery's current state.** Contract, EV1–EV3 results, PR 458
   status, current exam batch. Output: battery status record with commit IDs.
2. **Write the four stage definitions, with battery as the worked example.**
   Entry criteria, work, Graphite's permissions, output artifact and exit gate
   for each stage. Output: protocol draft.
3. **Build test suite v1.** Track A attack vectors with severity rules, Track
   B EV1–EV3, exam rotation and sealed pool. Output: versioned, pinned suite.
4. **Run battery through Test/iterate with Graphite at Level 0, then climb
   once.** Attack, fix, re-score; tune construction and scoring within
   Level 0 until results stop improving or the iteration budget runs out.
   Then climb to Level 1 by the climb procedure, as its worked example.
   Output: iteration log, a lessons entry for every execution, and battery's
   Level 1 climb record.
5. **Choose battery's construction level, freeze and run the final
   evidence.** The owners choose the best level step 4's internal testing
   supports. The run uses the pinned suite and battery's sealed pool at that
   level, with no changes during the run. Output: frozen evidence record and the
   first leaderboard entry.
6. **Set rubric v1.** Harshdeep proposes thresholds from what battery showed
   is achievable and meaningful. Output: rubric v1, entered in §05.
7. **Record cost and calendar time for every stage.** Output: cycle-time
   baseline for planning throughput.
8. **Fitz approves. Protocol v1.0 is locked,** with every lesson proposed for
   it adopted or declined. Output: the process package below, versioned.

### What gets locked

Stage definitions · Challenge brief template · Design packet template · Test
suite v1 · Deployment rubric v1 · Graphite procedure and permission ledger ·
Construction ladder and climb procedure · Lessons log and revision procedure ·
Iteration budget and stop rules · Cycle-time baseline.

### Plan for one revision after challenge 2

Battery solves in seconds on an electrochemical model with no meshing.
Laminar internal flow, first in the queue after battery, needs 3D geometry and
meshing, OpenFOAM references that take minutes to an hour, and failed-solve
handling. Treat the second challenge as a conformance run: keep the stages
and suite as locked, record where they strain in the lessons log, and expect
protocol v1.1 from the revisions those lessons propose. A
change that alters the suite creates suite v2, and challenges already on the
leaderboard re-run on it before they are compared.

---

## 02 Pipeline stages

### Each stage has an entry, an output and a gate.

#### Stage 1: Prioritize

- **Entry.** Protocol locked; family at the top of the queue in §04.
- **Work.** Check prerequisites ("builds on"). Confirm the v1 scope and
  exclusions from the family's design brief.
- **Graphite.** Drafts the challenge brief; lists reusable infrastructure and
  missing prerequisites.
- **Output.** Challenge brief.
- **Exit.** Harshdeep accepts the scope.

#### Stage 2: Design

- **Entry.** Accepted challenge brief.
- **Work.** Pin the reference build. Analytical controls and refinement.
  30-case feasibility panel. Measure p50/p95 solve time on the reference
  hardware. Case generator; splits by whole geometry, trajectory or regime;
  rotating exam batches and a sealed pool. Construction contract at Level 0
  (each capability mapped onto the ladder, Carbon's reconstruction for it and
  the first expansion record) and cheap baselines.
- **Graphite.** Sets up and runs reference, refinement and timing studies;
  drafts the generator and splits; proposes the capabilities for every
  construction level, 0 through 5, from which the Level 0 contract is built.
- **Output.** Design packet; measured solve time entered in §05.
- **Exit.** Challenge has solver, plan, data and a Level 0 construction
  contract Carbon rebuilds. Harshdeep signs.

#### Stage 3: Test / iterate

- **Entry.** Signed design packet.
- **Work.**
  - At the challenge's current construction level: run the suite, fix what
    breaks, and tune construction rules and scoring within that level.
  - Climb one level at a time by the climb procedure, internally.
  - Repeat within the iteration budget.
  - The owners choose the best construction level. Freeze at it, then run the
    pinned suite on the sealed pool.
- **Graphite.** Attacks construction and exams (Track A), runs development EV
  studies, proposes construction and scoring changes and the next level.
  Before freeze only.
- **Output.** The chosen construction level, and a frozen evidence record taken
  at it. Results are entered in §05.
- **Exit.** Tested, construction and scoring optimized. Ryan signs Track A,
  Harshdeep signs Track B.

#### Stage 4: Rank for deployment

- **Entry.** Frozen evidence record.
- **Work.** Apply the rubric gates and place the challenge on the leaderboard.
- **Graphite.** Compiles the evidence summary. No role in grades.
- **Output.** Leaderboard position.
- **Exit.** Fitz picks deployments. A deployed challenge opens to miners at its
  chosen construction level, locked. Network activation stays a separate owner
  decision.

### Construction ladder

The levels are Challenge Admission §3's. Each adds to the one below.

| Level | Adds |
| --- | --- |
| 0 | The challenge's current recipe and registered operations |
| 1 | Custom loss expressions using a bounded operation set |
| 2 | Training schedules, optimisers and permitted TRAIN sampling |
| 3 | Training-time numerical routines such as preconditioners |
| 4 | New architectures exporting through a constrained inference interface |
| 5 | Custom inference in an independently isolated execution stage |

The challenge's permission manifest is the authority. The level is its label.
Where today's Level 0 already admits a surface the ladder places higher, the
record says so rather than hiding it.

**Graphite proposes every level's capabilities.** The ladder is the same for
every challenge, but what each level admits is challenge-specific. For every
challenge, Graphite proposes the capabilities for every level, 0 through 5
(owner, 2026-10-02: "I want graphite to propose capabilities for every
construction level"). A proposal states:
- what each capability adds and its bounds;
- the research behind it: Graphite's method cards and development
  experiments;
- the reconstruction work Carbon must ship for it;
- the attack surface it opens;
- what the level leaves out.

The construction contract owner accepts or declines each proposal. Graphite
proposes; it never writes the contract or an expansion record.

**Climb procedure, internal, for every level above 0:**
1. Graphite proposes the level's capabilities for this Challenge, with their
   bounds, the research behind them, the reconstruction work each needs and
   the attack surface it opens; the construction contract owner accepts or
   declines the proposal.
2. Record the changed contract and permissions as an expansion record.
3. Ship Carbon's reconstruction for the new level, with a test that Carbon
   rebuilds it.
4. Run valid constructions under the previous and the expanded profile.
5. Run matched adversarial budgets under both profiles.
6. Remove the new permission and repeat the comparison (ablation).
7. Test interactions with earlier permissions (combined-permission attacks).
8. Reconstruct promising valid submissions on clean workers.

The climb runs on a development-only contract variant. It is held outside the
miner-facing registry and served only to Carbon's own registered Graphite
campaigns (owner, 2026-10-02).

**Then launch:**
1. Choose the challenge's construction level: the owners choose the best
   level the internal evidence supports, which need not be the highest
   tested.
2. Freeze at the chosen level, lock it, and open the challenge to miners at
   that level once validators serve its contract.

**How a validator knows how to build a construction.** A miner never sends
build instructions. A submission is a declarative recipe plus the digest of
the construction contract it was written against. The validator rebuilds it
with the reconstruction code pinned in its own Carbon version, and refuses a
digest it does not serve. Opening a challenge at its chosen level is
therefore a Carbon release, made of three parts:
- the chosen level's contract;
- its reconstruction code;
- a validator update.

Levels 4 and 5 are where a submission carries participant code. They need
isolated execution, so they stay NOT_RUN until that isolation and its
reconstruction exist.

**Rules.**
- A finding stops further climbing until it is repaired and retested.
- A level that is not implemented is NOT_RUN, never a pass.
- Miners only ever see the chosen, locked level. A level tested internally is
  never opened to miners to gather acceptance data.
- Frozen evidence and leaderboard entries name the chosen level they were
  taken at.

### Freeze rule

Before freeze, Graphite and the team can change anything: construction rules,
scoring, the exam design, the suite's challenge-specific attacks. At freeze,
the suite version, harness code, scoring, sealed pool and chosen construction
level are pinned, and only the run on those feeds the leaderboard. A change
after freeze, including choosing a different level, creates a new challenge
version and a new frozen run. Earlier evidence stays bound to its level.

### Graphite operating rules

- Graphite is Carbon's own research and testing agent. No external research
  agent takes its role.
- Runs through a controller with a per-stage permission ledger; every action
  lands in the iteration log, and every execution gets a lessons entry.
- Never reads or writes the sealed pool, and never edits the pinned harness or
  a frozen record.
- Proposes the capabilities for every construction level of every
  challenge. Constructs only within the campaign's recorded level; a proposed
  level opens only by the climb procedure, after the construction contract
  owner accepts the proposal.
- Its outputs are drafts until a named owner signs the stage gate.

### Stop rules

Park a challenge when its reference costs more than its budget, numerical
uncertainty is larger than the decision margin, a cheap baseline
(interpolation, superposition, a reduced-order model) already matches it, or
it still fails the rubric when the iteration budget runs out. Parked
challenges keep their records and re-enter the queue only with a changed
scope.

---

## 03 Common test suite

### Every challenge faces the same suite.

The leaderboard only ranks fairly if every challenge faced the same attack
vectors and the same score-to-value tests under the same suite version.
Battery builds suite v1. Challenge-specific attacks are added on top, never in
place of the shared ones.

### Track A: construction, reconstruction and attack

1. **Admission:** reject undeclared inputs, unsupported recipes, pretrained
   payloads, any surface above the challenge's recorded construction level,
   executable content at a level that admits none (submissions are
   declarative below Level 4; Carbon rebuilds the recipe in a backend the
   construction contract supports, JAX or PyTorch) and disguised executable
   content.
2. **Execution isolation:** block unauthorized filesystem, network, process,
   credential and cross-job access.
3. **Protected-data separation:** test whether a producer can observe or
   influence seeds, references, exam batches, the sealed pool or evaluation
   services.
4. **Resource enforcement:** terminate time, memory, storage and compute
   overruns; never grade a partial artifact as valid.
5. **Clean reconstruction:** rebuild from the declaration, permitted data and
   pinned environment on a fresh worker; repeat seeds to measure variation.
6. **Artifact integrity:** bind recipe, data, dependencies, model and report
   hashes; test substitutions, stale cache reuse and replay.
7. **Evidence integrity:** test forged outputs, altered metrics, missing
   provenance and disagreement between workers; quarantine unresolved grades.
8. **Adaptive exposure:** test memorization, repeated-query feedback against a
   rotating batch, and cross-case leakage; enforce the disclosure budget.

Track A runs at every implemented construction level with the same
legitimate panel and attack budget, plus single-permission ablations and
combined-permission attacks. A vector that needs a level the challenge has
not reached is NOT_RUN at that level, never a pass. Shared infrastructure
evidence may be reused across challenges only with matching pins and a
recorded applicability analysis (Challenge Admission §3).
Challenge-specific score exploitation and integration tests always run.

Ryan grades each open finding critical, high, medium or low and records the
open count at freeze. A clean run does not prove resistance to unrestricted
agents.

### Track B: score-to-engineering-value

1. **EV1, fixed choice:** a diverse model panel chooses from the same finite
   candidate set; reference-score each choice. Include feasible and
   infeasible scenarios.
2. **EV2, boundary behavior:** flawed controls, near-limit cases and fresh
   conditions. Measure false-feasible decisions, missed feasible options and
   abstention behavior.
3. **EV3, design search:** each model drives the same frozen optimizer,
   bounds, stopping rules, initialization and query budget. Reference-check
   each proposed design and its registered perturbations.
4. **Baselines:** compare against the direct solver with caching or
   factorization reuse, interpolation, and a reduced-order model where one
   exists, at matched budgets.

- **Rank agreement (ρ).** Spearman correlation between the challenge score
  and reference-measured engineering value across candidate models on the
  sealed pool. 1.0 means the score orders models exactly as their engineering
  value does; this is the "1:1" measure.
- **False-feasible bound.** One-sided 95% upper bound on how often a design
  the score accepts is rejected by the reference, from *k* events in *n*
  independent scenarios.
- **Regret.** Mean shortfall of chosen feasible designs against the best
  achievable, as a percentage of the best.

### Exam batches and the sealed pool

The exam uses a fixed batch rotated on a cadence toward the next valuable
areas to observe. Repeated score feedback on a fixed batch lets miners adapt
to it, and batches chosen by interest are not comparable with each other.
Each challenge therefore registers its rotation cadence and selection rule, a
disclosure budget, a small anchor set present in every rotation, and a sealed
pool sampled across the whole envelope that never enters rotation. Final runs
and the leaderboard use only the sealed pool.

### How many scenarios

Count independent scenario blocks, not correlated points from one sweep. With
zero false-feasible events in *n* independent trials, the 95% upper bound is
1 − 0.05^(1/*n*). It says nothing about rare events under shift or adaptive
optimization. (`carbon.challenge_pipeline.roadmap.ff_upper` computes the
bound, and the exact Clopper–Pearson bound when there are events.)

---

## 04 Priority queue

### 26 families, in the order they enter the pipeline.

Each family scores 1–5 on three equally weighted factors: workflow frequency,
surrogate value, and current solve time (slower reference solves leave more
room for a fast model). The composite is their mean; ties go to solve time,
then value, then the v1.0 priority. Solve times start as estimates for each
v1 scope and switch to the measured p50 when Design records one, so the queue
corrects itself as challenges come through. The next queued family enters
Prioritize when the previous one leaves Design.

Solve-time score: 1 under 1 s · 2 for 1–10 s · 3 for 10–60 s · 4 for 1–10 min
· 5 for 10 min or more. Tags: *estimate* (the v1-scope estimate), *measured*
(the recorded p50), *prior work* (existing Carbon work to start from),
*prerequisite later* (builds on a family ranked lower; pull it forward or
build it inside).

The families, their frequency and value labels, estimates and briefs are in
`carbon/challenge_pipeline/families.json`. The current queue is in
`docs/development/CHALLENGE_PIPELINE.md`.

---

## 05 Deployment leaderboard

### Deploy the challenges that survive attack and track value.

**Gates.** The challenge is ready for deployment, has no open critical or
high attack findings on the frozen suite, and meets the rubric's minimum rank
agreement, maximum false-feasible bound, minimum scenario count and, if set,
maximum regret.

**Order among challenges that pass.** Closest score-to-value match first:
higher rank agreement, then lower false-feasible bound, then lower regret.
Then fewer open medium and low findings. Then priority.

Harshdeep proposes thresholds from battery's results; Fitz approves them as
rubric v1 at protocol lock. Until then the leaderboard lists results without
eligibility.

The rubric's fields are: minimum rank agreement ρ, maximum false-feasible
bound (%), minimum independent scenarios, maximum regret (%, optional),
maximum open critical, maximum open high, and the rubric version. They are in
`carbon/challenge_pipeline/rubric.json`.

A challenge record holds:
- its stage and solve time: stage, measured p50 and p95 wall time, cases
  timed and hardware;
- its construction levels: the highest reached, each level's state and the
  chosen level;
- its attack results: suite version, and the open critical, high, medium and
  low findings at freeze;
- its score-to-value results: rank agreement ρ, regret, independent
  scenarios and false-feasible events.

Saving replaces the earlier record for that challenge. Enter Track A and B
results from the frozen run only. A leaderboard entry is a challenge at a
version and its chosen construction level. Choosing a different level makes
a new version and a new frozen run.

---

## 06 Design standards

### What every design packet contains.

| Element | Required design |
| --- | --- |
| Engineering decision | The user, design and control variables, objective, constraints and consequence of error the challenge represents. |
| Scope and data | Geometry topology, numeric bounds, units, material provenance, boundary and initial conditions, output locations, time or frequency grids. |
| Reference | Exact solver build, discretization, tolerances, hardware, deterministic settings, refinement evidence, failed-case policy, measured p50/p95 solve time. |
| Construction | The construction contract at Level 0, each capability mapped onto the ladder, with Carbon's reconstruction for it and the first expansion record; the backends Carbon rebuilds recipes in (JAX or PyTorch); permitted declarations and methods, authorized data, build resources, seeds, dependencies, reconstruction and artifact identity. Launchpad reference build identical to the validator pin. |
| Evidence | Physical gates, normalized errors, critical regions, uncertainty treatment, decision tests, disclosure budget, rotation cadence, anchor set, sealed pool. |
| Deployment record | Supported inputs and outputs, latency budget, version pinning and requalification triggers. |

### Reference credibility

1. **Numerical correctness:** analytical or manufactured controls, refinement
   and implementation checks.
2. **Model adequacy:** evidence that assumptions and parameters describe the
   intended physical system.
3. **Decision reliance:** evidence that remaining errors are acceptable for a
   named engineering decision.

In-house challenges launch at credibility level 1 with an explicit synthetic
scope. These are the reference's credibility levels, not construction levels.
A score that matches the reference 1:1 is only as good as the reference, so
claims name the credibility level reached. A reference comparison alone does not
establish certification or real-world safety.

### Reference budget and timing

Start with a 30-case stratified feasibility panel spanning the center,
boundaries and difficult combinations, plus refinement cases and analytical
controls. Time setup, solve, post-processing and failures separately on the
named hardware; report warm and cold runs, peak memory and p50/p95. Never
coarsen a reference to meet a runtime target while ignoring numerical error.
Count failed solves by rule rather than dropping them.

### Data and generalization

Separate public practice, permitted construction data, development holdout,
rotating exam batches and the sealed pool. Split by whole geometry families,
trajectories, material regimes or operating combinations; random splits of
nearby samples from one sweep overstate generalization. Keep distinct
interpolation, boundary and out-of-envelope panels. Register dimensionless
regimes such as Reynolds, Péclet and skin-depth ratios. Expanded bounds are a
new version.

### Construction and solver access

Carbon accepts and rebuilds only submissions within the challenge's recorded
construction level. Below Level 4 a submission is a declarative recipe and
the digest of the contract it was written against. Carbon rebuilds it in a
backend the construction contract supports (JAX or PyTorch), and the
validator pin carries the contract and the reconstruction code every rebuild
needs. Launchpad ships the pinned
reference solver for each active challenge so miners can generate their own
training and test data; they never see exam cases or the sealed pool. Keeping
that build identical to the validator's is part of Design. OpenFOAM,
CalculiX, GetDP, XFOIL, Meep and MPB are GPL-licensed; check redistribution
terms when packaging them for Launchpad.

The existing scientific rule remains: mandatory physical failure disqualifies
a candidate regardless of predictive accuracy, and producers never control
official draws, reference answers or grades.

### Composed challenges

A challenge that combines families (conduction and flow in a cold plate,
magnetostatics and eddy losses in a motor) is scored against the coupled
reference. Passing component tests does not establish interface correctness,
accumulated uncertainty or coupled stability.

---

## 07 Design briefs

### The starting scope for each family.

Graphite drafts each challenge brief from these. Solver names indicate
reference candidates or existing routes, not qualified implementations; exact
versions, bounds and thresholds are set in Design. The list follows the
current priority order.

Each family's brief is in `carbon/challenge_pipeline/families.json`: who it
serves (`cust`), the first scope (`first`), inputs, predictions, the
reference route (`ref`), the exam, the engineering-value test (`ev`), what to
build (`build`) and how it extends (`exp`).

---

## 08 Sources and limits

Frequency and value scores are planning judgments. Solve-time figures are
engineering estimates for each v1 scope until Design records measurements.
Tool documentation below establishes capabilities, not Carbon performance or
runtimes. Public documentation checked 2 October 2026 UTC.

1. **C1. Carbon Litepaper v3, 28 September 2026.** Internal. Construction
   boundaries, portfolio and dated development evidence. Repository baseline
   63950e36fcf35b6996f9bbc92f793cfdbcd84304.
2. **C2. Brief: Explaining Carbon Score Testing, 29 September 2026.**
   Internal. EV1 finding, EV2/EV3 dated status, fixed-optimizer comparison
   and claims limits.
3. **S1. FEniCS / DOLFINx documentation** (https://fenicsproject.org/documentation/).
   General finite-element framework and examples.
4. **S2. CalculiX** (https://www.calculix.de/). Structural FE solver: static,
   dynamic and thermal analysis.
5. **S3. OpenFOAM standard solvers**
   (https://www.openfoam.com/documentation/user-guide/a-reference/a.1-standard-solvers).
   Flow and conjugate heat transfer. Pin a distribution and release.
6. **S4. PyBaMM documentation** (https://docs.pybamm.org/en/stable/). Battery
   models and solvers.
7. **S5. fdtdx documentation** (https://fdtdx.readthedocs.io/en/stable/).
   JAX-based FDTD toolkit; existing Carbon photonics pilot route.
8. **S6. Meep mode decomposition**
   (https://meep.readthedocs.io/en/latest/Mode_Decomposition/). Candidate
   cross-check for scattering outputs.
9. **S7. GetDP manual** (https://getdp.info/doc/texinfo/getdp.html).
   Electromagnetic and coupled finite-element problems.
10. **S8. XFOIL** (https://web.mit.edu/drela/Public/web/xfoil/). Isolated
    subsonic airfoils; no 3D validity.
11. **S9. MIT Photonic Bands** (https://mpb.readthedocs.io/en/latest/).
    Eigenmode solver.
12. **S10. Project Chrono**
    (https://api.chrono.projectchrono.org/tutorial_table_of_content_chrono_mbs.html).
    Multibody dynamics.
13. **S11. Modelica.Fluid**
    (https://doc.modelica.org/Modelica%204.0.0/Resources/helpDymola/Modelica_Fluid.html).
    Fluid-network library; pin OpenModelica or Dymola as the simulation tool.
14. **S12. ngspice documentation** (https://ngspice.sourceforge.io/docs.html).
    Circuit simulator.
15. **S13. US EPA EPANET** (https://www.epa.gov/water-research/epanet).
    Water-distribution modeling.

*Challenge Roadmap rev 2.0 · Internal planning document. Deployment requires
frozen, challenge-specific evidence.*
