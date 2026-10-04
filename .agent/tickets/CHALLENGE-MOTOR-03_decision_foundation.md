# CHALLENGE-MOTOR-03 — customer-decision construction

**Status:** engineering implementation complete; counted execution blocked on
pinned image and compute/spend approval

**Authority:** OWNER-CHALLENGE-FOUNDATION-01, OWNER-CHALLENGE-DESIGN-01 and
OWNER-DX-03 and OWNER-GRAPHITE-TEST-WAVE-01 section 6. Paid compute remains
unapproved.

**Predecessor:** `CHALLENGE-MOTOR-01_development_exam.md`

**Tracking:** successor development ticket; no LIVE or miner-path activation

## Outcome

Turn the existing motor predictor exam into the first customer-decision
experiment without changing its physical model. The ticket compares analytical
and learned models, compares registered search methods, and can reference-check
selected geometries plus the finite comparator. It implements:

1. an explicit no-default torque/ripple decision contract;
2. a budgeted fail-closed model oracle;
3. fixed-grid and registered screen-then-confirm search;
4. immutable proposal or abstention commitments;
5. a real reconstruction of the existing kernel-ridge motor baseline;
6. a concrete synthetic 8-design x 6-condition DEVELOPMENT configuration;
7. four persisted commitments made without reference access; and
8. an analytical reference fixture for lifecycle tests that is structurally
   unable to count as GetDP evidence;
9. a digest-pinned Docker campaign plan, durable pre-dispatch ledger and
   one-retry policy for the complete 48-case comparator; and
10. strict retained-artifact import, finite comparator/regret, descriptive
    metrics and machine-readable/Markdown result generation.

`CHALLENGE-MOTOR-02` remains the distinct Launchpad miner integration. Counted
solver dispatch is not part of engineering acceptance and remains fail closed
until the exact image-bound plan receives compute/spend approval.

## Scope

KEEP the registered 2D, 8-pole/24-slot, one-period magnetostatic system, generic
iron law, 60-angle torque curve, GetDP/Gmsh reference and existing public TRAIN
and PRACTICE records. WRAP the existing analytical and learned baselines with a
decision layer. Do not alter the exam or private-pool evidence.

Out of scope:

- 3D end effects, skew, speed/voltage maps, losses, thermal limits, inverter
  control, structural mechanics, manufacturing tolerances or a physical rig;
- miner integration, Graphite construction freedom, scoring changes, LIVE,
  qualification, customer acceptance or launch readiness;
- counted GetDP execution outside the section 6 synthetic study authority or
  before the remaining compute/spend approval;
- treating the analytical fixture as learned or solver evidence.

## Working contract

The design is the first six registered inputs. Operating conditions are peak
current density and current angle. The decision minimizes worst-case
peak-to-peak torque-ripple fraction among designs predicted to meet both a
supplied mean-torque floor and ripple-fraction limit at all conditions.

Limits have no defaults and bind an explicit requirement reference. The study
uses the owner-delegated synthetic DEVELOPMENT values in
OWNER-GRAPHITE-TEST-WAVE-01 section 6: 4.0 N m and 0.30. They are approved for
this internal study but are not physical requirements, customer limits, gates
or qualification thresholds.

The model-query accounting unit is an attempted design-condition evaluation.
Duplicate points are forbidden within and across calls. A batch is charged
before inference, and infrastructure failure, malformed output or a failed
prediction-validity gate seals the arm. There is no in-oracle retry.

Construction freezes the exact scenario, code, models, methods and budgets,
then writes all four proposal commitments. No reference object is passed to or
constructed by this stage.

## Frozen DEVELOPMENT proposal

- Eight buildable geometries: a 2 x 2 x 2 grid over magnet thickness, embrace
  and airgap; the other three geometric variables stay at the registered frame
  values.
- Six current commands: four representative and two boundary-stress cases.
- Models: registered analytical surface-PM baseline and the actual Gaussian
  kernel-ridge baseline reconstructed from 150 public TRAIN cases at the
  already selected `(length=4.0, ridge=0.0001)` settings.
- Methods: full fixed grid and `screen_then_confirm` with equal 48-point query
  budgets.
- Verification allocation: six condition evaluations per committed proposal
  plus 48 finite-comparator evaluations. Reused design-condition evidence is
  cached but each requested condition evaluation remains visible in accounting.

The scenario, its rationale and the owner decision table are in
`docs/development/MOTOR_DECISION_DESIGN_PACKET.md`.

## Acceptance

- [x] No scientific limit is defaulted by the API.
- [x] Candidate designs and conditions are exact, unique and in the registered
  domain; every design is buildable.
- [x] Query attempts are charged before inference.
- [x] Duplicate queries and continuation after a failed batch are rejected.
- [x] A commitment file exists before any reference can be verified.
- [x] A confirmed violation remains visible when another condition is
  unavailable.
- [x] The learned arm reconstructs the prior measured KRR model, not an
  analytical stand-in.
- [x] All four arms can be constructed without reference access.
- [x] Representative and boundary-stress labels remain separate in the freeze.
- [x] All commitments are validated before a reference plan or evaluation is
  available.
- [x] The registered campaign requires a digest-pinned Docker image and exact
  CPU, parallelism, timeout and retention settings.
- [x] Every initial/retry execution is atomically reserved before dispatch;
  restart, concurrent-launcher and output-directory budget evasion fail closed.
- [x] Counted evidence binds plan, image, resource record, ledger, mesh,
  configuration, convergence/applicability, run and retained artifacts.
- [x] Known violations dominate missing evidence; unresolved competitors block
  exact finite-set regret.
- [x] Fixture reports are descriptive and make no population reliability claim.
- [x] Final focused, motor subsystem and formatting checks recorded below.

## Validation evidence

- Focused Motor decision, shared commitment, cold-plate compatibility and
  lesson-validation suite: `89 passed, 1 skipped`.
- Remaining Motor subsystem diagnostics: `32 passed, 3 deselected`; the three
  deselections are Windows-host-only failures around POSIX Docker UID/GID and
  POSIX private-file mode checks. They are exercised by canonical Linux CI.
- Ruff on every changed Python implementation/test path: passed.
- Fixture construction/evaluation: four immutable proposals; 187 attempted
  model queries; 12 unique selected design-condition fixture cases and 12
  evidence reuses; zero solver executions.
- Canonical Docker validation and image build were unavailable because the
  local Docker daemon was not running. Counted execution remains blocked.

## Maturity ceiling

SPECIFIED, IMPLEMENTED and fixture-TESTED when the final checks pass. The work
is not scientifically qualified, security qualified, customer accepted,
production qualified, LIVE or launch ready.

## Human input required

Compute/spend approval for the exact pinned image and registered envelope: 48
initial executions, up to 12 eligible one-time retries, 60-attempt hard cap, 2
CPUs each, 6 concurrent, 3,600-second timeout and retain-all policy. The
planning estimate and configured ceiling are 96 initial / 120 maximum allocated
core-hours, plus host/storage/orchestration overhead.

The exact synthetic decision values and conditions are already supplied by
OWNER-GRAPHITE-TEST-WAVE-01 section 6. Compute approval blocks counted GetDP
execution and any solver-backed decision claim, but not construction-layer
implementation.

## Files

- `carbon/motor/customer_decision.py`
- `carbon/motor/decision_study.py`
- `carbon/motor/reference_campaign.py`
- `carbon/design_search/aggregate_methods.py`
- `carbon/design_search/campaign.py`
- `carbon/design_search/reference_comparison.py`
- `scripts/dev/motor/decision_study.py`
- `scripts/dev/motor/reference/run_batch.py`
- `docs/development/studies/MOTOR_SYNTHETIC_DECISION_V1.json`
- `docs/development/MOTOR_DECISION_DESIGN_PACKET.md`
- `docs/development/evidence/motor-decision-construction-fixture-v1/`
- `tests/cpu/test_motor_customer_decision.py`
- `tests/cpu/test_motor_decision_study.py`
