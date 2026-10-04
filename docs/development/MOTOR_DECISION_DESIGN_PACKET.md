# Electric motor — customer decision design packet

**Status:** CONSTRUCTION, CAMPAIGN CUSTODY AND EVALUATION RUNNABLE; COUNTED
GETDP EXECUTION NOT AUTHORIZED

**Challenge:** `electric-motor-magnetics`

**Physical scope:** registered 2D, 8-pole/24-slot periodic magnetostatic
cross-section

**Implementation:** `carbon/motor/customer_decision.py`,
`carbon/motor/decision_study.py`, `carbon/motor/reference_campaign.py`,
`carbon/design_search/aggregate_methods.py`, `carbon/design_search/campaign.py`,
`carbon/design_search/reference_comparison.py`, and the Motor decision/campaign
CLIs under `scripts/dev/motor/`

**Study configuration:**
`docs/development/studies/MOTOR_SYNTHETIC_DECISION_V1.json`

## End goal

A motor engineer should be able to provide a bounded family of buildable motor
geometries, a set of operating commands and explicit torque/ripple
requirements, then receive:

1. a fast model's selected geometry and predicted margins;
2. an immutable proposal made before expensive finite-element access;
3. an independent torque-curve check at every required command;
4. a comparison with the best reference-feasible member of a completely
   evaluated finite design set; and
5. a clear accounting of whether value came from the learned model or merely
   from a different search procedure.

The eventual valuable product is broader: speed/voltage and thermal envelopes,
losses and efficiency, demagnetization, manufacturing tolerances, skew and 3D
end effects, inverter limits and test-bench correlation. None of that is
silently inferred here. The current study is the smallest decision experiment
the existing reference can honestly support.

## 1. Engineering decision

**User hypothesis.** An electromagnetic motor designer choosing a surface-PM
cross-section for a declared set of current commands. No customer demand,
revenue or acceptance is claimed.

**Decision.** Choose one geometry that minimizes worst-case peak-to-peak torque
ripple as a fraction of mean torque while satisfying both a supplied mean
torque floor and ripple-fraction limit at every command. A good mean torque
cannot compensate for an excessive ripple waveform.

**Design variables.** Magnet thickness, pole embrace, airgap, slot opening,
tooth width and slot-bottom radius. **Operating variables.** Peak current
density and current angle. The output remains the full 60-angle torque curve;
mean and ripple are derived, never independently predicted.

**Consequence of error.** A false-feasible selection may miss commanded torque
or create unacceptable torque pulsation. A false-infeasible result may reject
a smoother viable geometry. Missing reference evidence is neither outcome and
must remain unresolved unless some other condition already proves the proposal
infeasible.

## 2. Physical scope and control assumption

The reference is Carbon's existing GetDP/Gmsh 2D magnetostatic implementation:
8 poles, 24 slots, generic nonlinear iron, surface magnets, one 15-degree
period and 60 rotor positions. Mesh rotation is exact at the airgap and torque
is checked by Maxwell stress and virtual work. Prior pilot and pool evidence is
documented in `.agent/tickets/CHALLENGE-MOTOR-01_development_exam.md`.

Each condition is a commanded peak current density/current-angle pair. The
comparison assumes the command has settled before a magnetostatic sweep and
that the same geometry can be operated at all six commands. This does **not**
establish an implementable speed-dependent controller: rotor speed, DC-bus
voltage, back EMF, inverter current, control dynamics, winding temperature,
losses and demagnetization limits are absent. A later control study must
declare and enforce those limits before making drive-cycle or robot-joint
claims.

The physical boundary remains explicit: no skew or 3D end effects, thermal
model, losses/efficiency, structural stress, acoustic response, manufacturing
tolerances or physical rig.

## 3. Frozen synthetic DEVELOPMENT scenario

The configuration proposes an eight-design Cartesian grid: magnet thickness
2.0/3.5 mm, embrace 0.65/0.85 and airgap 0.4/0.8 mm, with slot opening 3.7
degrees, tooth width 3.5 mm and slot-bottom radius 38.16 mm fixed. Every design
passes the registered buildability checks. This is a finite comparison set,
not a population sample or a global design space.

The commands are:

| Group | Peak current density (A/mm²) | Current angle |
|---|---:|---:|
| Representative | 8 | 0° |
| Representative | 10 | 0° |
| Representative | 12 | 0° |
| Representative | 10 | 15° |
| Boundary stress | 15 | 0° |
| Boundary stress | 12 | 30° |

The synthetic constraints are mean torque at least **4.0 N m** and
peak-to-peak ripple no more than **0.30 of mean torque** at every command.
OWNER-GRAPHITE-TEST-WAVE-01 section 6 supplies these values for this internal
DEVELOPMENT study. They are rounded public-TRAIN medians: among the 72 TRAIN
cases at 8 A/mm² or more, 33 meet both limits, 54 meet the torque floor and 40
meet the ripple limit. No private or PRACTICE result selected them. This is
study-design authority, not proof that either value is safe, useful or customer
relevant. The API still has no defaults.

The eight-design rule was recorded before any reference solve of this set:
take the full 2 x 2 x 2 factorial over two rounded interior values for the
three primary field-production levers—magnet thickness 2.0/3.5 mm, pole embrace
0.65/0.85 and airgap 0.4/0.8 mm—and hold slot opening, tooth width and
slot-bottom radius at the registered nominal frame values. Admit the set only
if all eight pass `domain.validity`. The rule was chosen without looking at a
GetDP result for any of the 48 final cases.

Representative and boundary-stress outcomes will be reported separately. No
weight combines them, and six fixed cases do not support population reliability
or generalisation confidence.

## 4. Construction contract

The freeze binds the scenario, exact design and condition rows, model
identities, registered methods, code digests, query and verification budgets,
analysis policy and no-qualification claims. The models are:

- the classical surface-PM analytical model, which predicts a flat torque
  curve and omits saturation, cogging and ripple; and
- the actual Gaussian kernel-ridge model trained on the 150 public TRAIN
  records, with the previously PRACTICE-selected length 4.0 and ridge 0.0001.

The latter is learned evidence. It is not relabelled analytical output. Prior
private-pool results showed lower prediction error for the learned model, but
those results do not establish a better design decision.

The query budget is 48 attempted model points per arm. A point is reserved in
the log before inference. Duplicate points are forbidden within and across
calls; malformed output, prediction-gate failure or infrastructure failure
seals the arm. There is no retry inside an arm.

Construction writes every proposal or abstention before a reference plan can
be generated. Evaluation first validates the freeze, reconstruction manifest,
all four exact commitment files and the construction identity; it never
regenerates a proposal. The four arms are:

| Question | Controlled comparison |
|---|---|
| Model value | Analytical versus learned, both using fixed grid |
| Search value | Fixed grid versus screen-then-confirm, separately for each model |
| Decision value | Selected geometries versus a complete finite-set GetDP comparator |

## 5. Current fixture construction result

The checked construction smoke test produced all four commitments:

| Arm | Selected design | Attempted queries |
|---|---|---:|
| Analytical + fixed grid | d07 | 48 |
| Analytical + screen-then-confirm | d07 | 48 |
| Learned KRR + fixed grid | d06 | 48 |
| Learned KRR + screen-then-confirm | d06 | 43 |

This establishes only that the two models disagree under the proposed
synthetic contract and that screening saves five learned-model queries without
changing the learned selection; it saved no analytical queries. It does **not**
establish that d06 is feasible, better than d07, or better than another
candidate. The analytical model's zero
predicted ripple is a known model limitation, not reference evidence.

## 6. Implemented reference and comparator policy

The analytical callback remains a fixture class and can never count as GetDP
evidence. The counted importer accepts only the registered 48-case plan and an
optional registered retry plan. It binds the exact digest-pinned container
image, construction and campaign identities, generated geometry and GetDP
inputs, mesh identity, nonlinear convergence, periodicity/applicability
evidence, run identity, solver logs, torque outputs, host/resource record,
ledger snapshot and retained artifact digests. A plausible callback record
cannot construct a counted session.

The counted comparison should evaluate all 8 x 6 = 48 design-condition cases,
not only the selected designs. A design is:

- `CONFIRMED_INFEASIBLE` when any usable condition proves a violation, even if
  another condition is unavailable;
- `CONFIRMED_FEASIBLE` only when all six conditions are usable and feasible;
- `UNRESOLVED` when no violation is known but at least one condition is
  unavailable; or
- `ABSTAIN` when the arm committed no design.

Exact finite-set regret is valid only when every potentially competitive
candidate is sufficiently resolved. A confirmed-infeasible candidate can be
excluded even when another one of its conditions is unavailable. A candidate
with no known violation and missing evidence remains potentially competitive.
In that case the report may show a labelled difference from the best observed
feasible design, but exact regret remains nonnumeric.

## 7. Enforced counted campaign envelope — execution not approved

The registered plan and durable SQLite ledger enforce:

- 48 initial GetDP executions;
- up to 12 registered retries, no more than one per eligible case;
- hard cap of 60 reserved attempts;
- 2 CPUs per execution, 6 concurrent executions;
- 3,600-second timeout per execution;
- retain every artifact and the campaign ledger.

The planning estimate is **96 core-hours initially** and **120 core-hours with
all retries**, based on the Test Lead's approximate two core-hours per case.
The configured allocation ceiling is separately **96 initial / 120 maximum
allocated core-hours** (`2 CPUs x 3,600 seconds x 48/60`). Host, image-build,
storage and orchestration overhead are outside those solver-allocation
figures. Actual CPU time, solver wall time and campaign wall time are recorded
after execution. These limits are implemented, not authorized expenditure.
Faster paid compute changes elapsed time and available concurrency; it does not
add cases, change the six registered concurrent executions or widen the
campaign without a new preregistered plan and approval.

The ledger is repository-relative and campaign-identity-bound. Every batch is
reserved atomically before output creation or solver dispatch, so concurrent
launchers cannot oversubscribe it and a different output directory cannot
evade the allowance. `--native` is rejected for this registered campaign
before ledger creation, output creation or process launch. Unrelated
unregistered native Motor reference work remains available.

### Interrupted campaign behavior

Reservations survive a launcher crash; automatic resumption and arbitrary
state repair do not exist. Recovery is therefore conservative:

1. preserve the SQLite ledger, every output directory and all logs;
2. inspect the ledger's batch/execution states, `records.jsonl`, retained case
   directories and any still-running solver containers;
3. classify each reservation as completed, failed, demonstrably still running
   or uncertain;
4. keep every uncertain reservation charged—never delete the ledger, change
   campaign identity or switch output directories to regain allowance;
5. use only the registered one-retry path for a completed, typed eligible
   initial failure; and
6. if the evidence requires an unsupported state transition or cannot
   reconcile a reservation with a retained execution, stop that campaign and
   present the exact reconciliation decision to the compute owner.

The current implementation intentionally has no general crash-recovery state
machine. A reservation left `RESERVED` cannot be silently reclaimed.

## 8. Owner decision table

| Decision | Recommended value/policy | Rationale | Consequence | Owner | Blocking step |
|---|---|---|---|---|---|
| Synthetic torque floor | 4.0 N m | OWNER-GRAPHITE-TEST-WAVE-01 section 6; rounded public-TRAIN median | Changes which designs can be proposed | Owner delegation, supplied | Approved for this DEVELOPMENT study |
| Synthetic ripple limit | 0.30 peak-to-peak / mean | OWNER-GRAPHITE-TEST-WAVE-01 section 6; rounded public-TRAIN median | Changes feasibility and regret | Owner delegation, supplied | Approved for this DEVELOPMENT study |
| Finite comparison set | Recorded 8-design rule x supplied 6 commands | Small complete comparator; four representative and two boundary cases | Defines what “best” can mean | Owner delegation + Codex design rule | Frozen before reference |
| Operating assumption | Settled current-density/current-angle commands; no dynamic controller claim | Matches magnetostatic solver authority | Forbids speed/drive-cycle claims | Owner delegation, supplied | Approved interpretation |
| Missing evidence | Known violation dominates; otherwise missing means unresolved | Prevents missing data hiding failures or becoming success | Controls feasibility counts | Engineering policy | Implemented; no owner approval needed |
| Comparator/regret | Exact regret only for sufficiently resolved complete set | Prevents “best observed” becoming “best in set” | May leave regret unresolved | Engineering policy | Implemented; no owner approval needed |
| Counted image | Build the registered Dockerfile and bind its immutable `IMAGE@sha256:DIGEST` | Establishes exact GetDP/Gmsh execution identity | The plan cannot be created from a mutable tag | Engineering executor | Image build/publish before approval request |
| Compute envelope | 48 initial + at most 12 one-time eligible retries; 2 CPUs, 6-way, 3600 s, retain all | Complete finite set with bounded recovery | Up to 60 attempts and 120 allocated core-hour timeout ceiling, plus overhead | Compute/spend owner | **Approval still required before solver dispatch** |

## 9. Commands and artifact order

Construction command (no reference access):

```text
python -m scripts.dev.motor.decision_study construct --out <construction-dir>
```

It creates, in order, `freeze.json`, `reconstruction.json`, four commitment
files, then `construction.json`. The checked fixture is at
`docs/development/evidence/motor-decision-construction-fixture-v1/`.

Build and publish the registered worker image, then use its immutable digest:

```text
docker build -f scripts/dev/motor/reference/Dockerfile -t <registry>/carbon-motor-reference:<version> .
docker push <registry>/carbon-motor-reference:<version>
docker image inspect --format '{{json .RepoDigests}}' <registry>/carbon-motor-reference:<version>
python -m scripts.dev.motor.decision_study plan --construction <construction-dir> --solver-image <registry>/carbon-motor-reference@sha256:<digest> --out <initial-plan.json>
```

The exact image-bound plan is the compute-approval artifact. Once its envelope
is approved, execute in this order:

```text
python -m scripts.dev.motor.reference.run_batch <initial-plan.json> --out <initial-dir> --campaign-ledger .carbon-artifacts/motor-synthetic-decision-v1-campaign.sqlite3 --parallel 6 --cpus 2 --timeout-s 3600 --keep all
python -m scripts.dev.motor.decision_study retry-plan --initial <initial-dir> --out <retry-plan.json>
python -m scripts.dev.motor.reference.run_batch <retry-plan.json> --out <retry-dir> --campaign-ledger .carbon-artifacts/motor-synthetic-decision-v1-campaign.sqlite3 --parallel 6 --cpus 2 --timeout-s 3600 --keep all
python -m scripts.dev.motor.decision_study evaluate-counted --construction <construction-dir> --reference <initial-dir> --reference <retry-dir> --out <evaluation-dir>
```

Omit the retry commands when there are no registered eligible failures; the
retry-plan command fails closed in that case. Fixture smoke testing is:

```text
python -m scripts.dev.motor.decision_study evaluate-fixture --construction <construction-dir> --out <fixture-evaluation-dir>
```

The enforced order is:

1. validate the already saved construction identity;
2. generate a 48-case plan bound to that identity and the pinned image;
3. reserve and run the initial Docker campaign through the durable ledger;
4. apply only registered eligible retries within the remaining allowance;
5. import exact retained evidence without regenerating proposals;
6. evaluate proposals and the full finite comparator; and
7. report feasibility, unresolved evidence, regret validity, query savings,
   solver attempts/retries and measured resource use.

## 10. Maturity and next justified expansion

This ticket earns specified and implemented construction, campaign-custody,
strict-import and evaluation seams with fixture tests. It does not earn
solver-backed decision evidence, scientific
qualification, customer acceptance, security qualification, LIVE readiness or
launch readiness.

The immediate next step is not Graphite or Launchpad integration. It is to
build/publish the pinned image, generate the exact plan, obtain the remaining
compute/spend approval and run the bounded comparator. If that demonstrates
useful decision separation, the next physical expansion should be selected
deliberately—likely a speed/voltage/thermal operating envelope—under a new
Challenge version and reference contract.
