# A8 TrainEval deterministic fixture stub — pre-implementation plan

**Ticket:** A8 — bounded fixture-official TrainEvalAPI stub contract

**Ratification branch:** `agent/a8-contract-ratification`

**Ratification starting main:**
`6a3fe0f8e34602af5a4eaeaa8ae145d967537724`

**Ratification starting tree:**
`b5052df524b43ef07ece953757a74fe0e84da1e8`

**Historical status at ratification:** documentation-only contract candidate;
no implementation, test, fixture, dependency, packaging, CI,
quality-baseline, tracker, or A9+ change.

```text
A8 SPECIFIED / RATIFIED: YES only after this documentation candidate is independently reviewed, explicitly human-authorized, and merged
A8 IMPLEMENTED: NO
A8 TESTED: NO
A8 PRODUCTION-QUALIFIED: NO
A8 WAVE STATUS: todo
```

This plan is not executable authority before merge. A separate human-reviewed
task must re-fetch the ratification merge, verify A8 remains `todo` and
unimplemented, and explicitly authorize the bounded implementation.

The preceding status and the future-tense plan below are preserved as the
chronology that governed ratification and implementation. They are
superseded for current maturity only by the executed-plan record later in this
file and the current `.agent/WAVE.md`/ticket evidence.

## Current administrative-closeout candidate

```text
A8 SPECIFIED / RATIFIED: YES
A8 IMPLEMENTED: YES on current main for the bounded fixture-official,
deterministic, process-local stub scope, including the reviewed conformance repair
A8 TESTED: YES only for the exact recorded CPU/security/import/wheel/quality scope
A8 SCIENTIFICALLY_QUALIFIED: NO
A8 SECURITY_QUALIFIED: NO
A8 NETWORK_QUALIFIED: NO
A8 COMMERCIALLY_VALIDATED: NO
A8 PRODUCTION_QUALIFIED: NO
A8 WAVE STATUS: done only after this documentation-only closeout is independently reviewed, explicitly human-authorized, and merged
```

This closeout is documentation only. It checks the existing twenty-five
bounded implementation criteria after mapping each one to current code/tests;
it does not begin A9 or confer any scientific, security, network, commercial,
or production qualification.

## Repository gate at ratification

- Fresh fetch/prune resolved `origin/main` to the exact starting commit/tree
  above, subject `Merge pull request #27 from
  carbonphysicsai/agent/a7-closeout`.
- Ordered parents are exact A7 implementation merge
  `5b7b38a4db3b0a7bbf2d97ae872a28a3d885d77d` followed by reviewed closeout
  head `2d192a10475568af092df74bb0afff3e9dece6a8`.
- GitHub reports PR #27 `MERGED` as
  `6a3fe0f8e34602af5a4eaeaa8ae145d967537724`; the reviewed second parent is
  ancestral and its tree equals the merge tree exactly.
- Push run `32630014802` is `completed / success` on exact `main` head: `1423
  passed in 30.36s`; quality inventory `Ruff 757/776; Black 62/68`; zero
  changed Python files; no new debt.
- `.agent/WAVE.md` records A7 `done` and A8--A12 `todo`. The A7 ticket contains
  twenty checked and zero unchecked bounded criteria.
- Open/closed PR and remote-branch searches for A8, TrainEval, traineval,
  backend stub, and execution adapter found only historical references; no
  competing A8 source, test, plan, branch, PR, or lifecycle existed.
- `carbon/traineval/__init__.py` is still the A0 marker. There is no A8 model,
  service, backend, result, canonical test, fixture, dependency, or prior plan.
- Starting `git status --porcelain=v1` was empty.

## Source-authority and conflict map

| Authority | Controlling A8 effect |
|---|---|
| Current A2--A7 code and `tests/cpu/` | Governs actual accepted Strategy, challenge admission, context types, Score Pack/result boundaries, cards, submission/attempt identity, FSM, and publication. A8 cannot infer missing behavior from prose. |
| `Design_Specs/Scoring.md` and current A5 | Sole scoring/input/result authority. A8/later owns raw execution and complete validator-authorized scalar construction; incomplete/infra material is not science. |
| `Design_Specs/Build_Out.md` §5 | This candidate repairs the stale generic request/mode/status contract while preserving one TrainEval architectural owner and Wave sequencing. |
| `Build_Out_Protocol_Extension.md` and `Evaluation_Evidence_and_Validator_Audit.md` | Require non-emitting stub provenance, execution isolation, backend qualification and later evidence separation; they do not make evidence an A8 result. |
| A4-R1--A4-R11 | Exact context/domain/derivation separation, fixture/provider boundaries and no leakage. |
| A5-R1--A5-R14 | Exact fixture pack pin, validated `ScoreInput`, `ScoreEngine`, result statuses, infra/science separation and false eligibility. |
| A6-R1--A6-R12 | Exact private result storage and positive public projection. A8 cannot call or bypass A6. |
| A7-R1--A7-R15 and current `carbon/fees/` | Exact accepted snapshot/hash, fixture envelope, attempt handle, environment identity, current-handle authority, retry/fee/cancel/FSM and exclusive A6 publication. |
| `docs/context/Implemented_vs_Specified` | Maturity ledger; specification never implies implementation/testing/qualification. |
| `docs/context/Open_Questions.md` | Retains OQ-004--OQ-008 and OQ-011/OQ-012 human production decisions. Recommendations are not ratified values. |
| Legacy/PoC/neurons/Julia/deployment material | Archaeology only unless a later scoped qualification keeps/wraps/repairs it. |

The historical `run(strategy, batches, mode, limits, pin) -> RunResult`, A2-only
dependency, caller batches/limits/pins, generic `mock | official`,
`invalid_strategy`, numerical-failure-to-gate, and direct card/emission
language are superseded rather than averaged with current A4--A7 authority.

## KEEP → WRAP → REPAIR → REPLACE

| Area | Disposition for A8 |
|---|---|
| `carbon/traineval` A0 marker | **KEEP; REPAIR later.** Preserve the seam; add only the four ratified modules in the implementation task. |
| A4 exact fixture provider/context/derivation | **KEEP / WRAP.** Consume exact APIs without copying seed semantics. |
| A5 pack loader, `fixture_score_input`, `ScoreEngine`, `InternalResult` | **KEEP / WRAP.** A8 constructs inputs through A5 and returns exact completed results; it does not duplicate scoring. |
| A7 exact handle/envelope/environment pin | **KEEP / WRAP.** Reconstruct safe values and return the exact attempt identity without importing A7 lifecycle storage. |
| A2/A3 validation/admission | **KEEP upstream; do not wrap in A8.** Their decisions already occurred before execution. |
| `carbon/backbones` lazy registry/wrappers | **KEEP for later WRAP.** Useful optional-dependency seam, but mutable registration is not backend authority or qualification and is excluded from the stub. |
| PoC NumPy/JAX kernels/generator/relative-error ideas | **ARCHAEOLOGY; REPAIR/WRAP later.** Preserve for separate scientific/backend audit; never use in the deterministic stub. |
| `carbon/training`, historical validators, defaulting gates/scorers, raw-seed cards, direct weight writers | **REPLACE/EXCLUDE.** They conflict with A4--A7, infra/science, leakage, lifecycle and emission boundaries. |
| Julia service and historical deployment/container manifests | **ARCHAEOLOGY; REPAIR/QUALIFY later.** They do not satisfy environment pinning, sandboxing or reference qualification. |
| Stale Build Out §5 and A8 ticket | **REPAIR in this candidate.** Replace only conflicting contract text and retain unrelated sequencing. |
| New runtime dependency | **REPLACE with standard library/current packages.** None is justified for the stub. |

## Exact ownership and exclusions

A8 later owns trusted fixture profile/runtime configuration, A4 fixture
context consumption, deterministic backend invocation, private output
validation, complete A5-authorized scalar construction, `ScoreEngine.score`,
closed attribution, redaction, and private outcome production.

A8 does not own:

| Owner | Boundary preserved |
|---|---|
| A2 | Structural Strategy validation and rejection |
| A3 | Challenge/version/LIVE/backbone admission |
| A4 | Context, seed-domain and derivation semantics |
| A5 | Score Pack/input/status/result/scientific math |
| A6 | Result storage, card projection or publication |
| A7 | Submission/hash/snapshot, attempt/FSM, retry budget, fee/refund, cancellation or publication |
| A9 | Miner-facing transport/disclosure for later mock/light execution |
| A10--A12 | Leaderboard, logging/metrics and invariant aggregation |
| Later evidence/chain | Transcript, receipt, signature, provenance, weights and emissions |

## Exact future private model

Future `model.py` owns exact frozen/slotted values conceptually equivalent to:

```text
FixtureStubProfile
FixtureRuntimePolicy
FixtureRunRequestError
FixtureRunIdentityError

InfrastructureRetryClass = RETRYABLE | NON_RETRYABLE

StrategyFailureCause =
  STRATEGY_RUNTIME_FAILURE |
  STRATEGY_TRAINING_FAILURE |
  STRATEGY_NUMERICAL_FAILURE

InfrastructureCause =
  CONFIGURATION_UNAVAILABLE |
  SCORE_PACK_MISMATCH |
  SCORE_PACK_NOT_READY |
  CONTEXT_UNAVAILABLE |
  ENVIRONMENT_MISMATCH |
  BACKEND_UNAVAILABLE |
  BACKEND_STARTUP_FAILURE |
  EXECUTION_TIMEOUT |
  RESOURCE_VIOLATION |
  BACKEND_NUMERICAL_FAILURE |
  REFERENCE_FAILURE |
  INCOMPLETE_EXECUTION_MATERIAL |
  SCORE_INPUT_FAILURE |
  SCORE_COMPUTATION_FAILURE

FixtureRunOutcome =
  CompletedFixtureRun(exact handle, exact completed InternalResult) |
  StrategyFailedRun(exact handle, exact StrategyFailureCause) |
  InfrastructureFailedRun(
    exact handle,
    exact InfrastructureRetryClass,
    exact InfrastructureCause
  )
```

`FixtureRuntimePolicy` is exact, frozen and slotted. Its fields are literal
policy ID `a8_fixture_stub_policy_v1`, exact safe `backend_profile_id`, exact
safe `container_digest`, and an immutable total tuple mapping each exact
`InfrastructureCause` once to an exact `InfrastructureRetryClass`. It carries
no generic mode, numeric runtime limit, production control/value, fallback,
backend selector or emission Boolean. That table is injected trusted fixture
test policy—not an infrastructure fact, retry permission, A7 budget or
production default.

`FixtureRunRequestError` has exact code
`traineval.fixture_request_invalid` and exact message `Fixture execution
request is invalid.`. `FixtureRunIdentityError` has exact code
`traineval.fixture_identity_invalid` and exact message `Fixture execution
identity is invalid.`. Neither accepts caller diagnostics; exception chaining
is suppressed.

Only `SCORED` and `MANDATORY_GATE_FAILED` exact A5 results may appear in
`CompletedFixtureRun`. The result-bearing types are a trusted private
integration surface, not miner/public/root convenience types. Closed causes
are the only diagnostics. No arbitrary string, exception object or runtime
payload is retained.

## Exact service and construction contract

```text
FixtureTrainEvalService(
  exact FixtureStubProfile,
  exact DeterministicFixtureProvider,
  exact verified LoadedScorePack,
  trusted FixtureRuntimePolicy,
  exact separately declared ExecutionEnvironmentPin identity,
  exact FixtureStubBackend
)

FixtureTrainEvalService.run_fixture(
  exact FixtureExecutionEnvelope
) -> private FixtureRunOutcome
```

Trusted composition fully constructs and preflights the service before asking
A7 to start an attempt. Construction failure is a pre-start integration error,
not a handle-free run outcome. The run call accepts no independent Strategy,
StrategyHash, batches, mode, runtime limits, attempt number, ChallengeKey,
SeedPin, environment pin, context, seed, Score Pack, or backend identity.

The service reconstructs an `ExecutionEnvironmentPin` from the policy's safe
backend-profile/container-digest fields and requires equality with the
separately declared identity, exact backend capability metadata and handle pin.
The backend capability is mechanically non-emitting. Trusted composition then
passes the exact envelope returned directly by A7 start.
A8 validates structural exactness and self-consistency only; A7 is the sole
authority for whether a handle is authentic/current when the callback is
applied. A8 never imports/calls `SubmissionService`, reaches an A7 store, calls
A6, or creates lifecycle state.

## Boundary-validation and run-time failure order

1. Require exact `FixtureExecutionEnvelope`; subclasses and cross-kind values
   fail with stable boundary errors.
2. Reconstruct exact handle, ChallengeKey, SeedPin and environment pin using
   their current constructors/safe ownership boundaries.
3. Require `AdmissionKind.FIXTURE` and envelope ChallengeKey equality with the
   handle SeedPin ChallengeKey.
4. Reject malformed or internally contradictory untrusted values without A7
   mutation based on them.
5. Ignore mutable `envelope.strategy` and independently presented
   `envelope.strategy_hash` for synthetic material. Mutation cannot affect the
   profile result.
6. Once the structurally valid envelope boundary exists, return closed
   infrastructure outcomes for run-time trusted profile/config/pack/context/
   environment/backend/material/input/scoring failures so composition can
   resolve the original handle.
7. A7 revalidates current handle/state for every mapped callback; stale or
   wrong values cause no A7 mutation.

Exact/frozen Python values are not authenticated or tamperproof. Fresh
reconstruction, no retained caller aliases, private composition and A7
callback validation are the bounded correctness controls. A future real
backend needs a separately ratified immutable/verifiable Strategy snapshot
handoff before interpreting Strategy parameters.

## Exact outcome-to-A7 mapping

| A8 condition | A8 representation | Retry authority | Trusted A7 operation | A5 result / A6 card | Nature and diagnostic |
|---|---|---|---|---|---|
| Wrong/subclassed/cross-kind/malformed/contradictory untrusted value | Stable request/identity error | N/A | None based on that value | None / never | Operational boundary; closed code only |
| Stale/wrong callback | A7 typed rejection | A7 | None; no mutation | None / never | Operational; A7 discloses no state dump |
| Positive Strategy attribution | `StrategyFailedRun` | No retry implied | `fail_strategy` | None / never | Operational lifecycle fact; closed Strategy cause |
| Trusted retry-classified integration fault | `InfrastructureFailedRun(RETRYABLE, cause)` | A7 applies budget; A8 classifies only | `retry_infrastructure` | None / never | Operational; closed infrastructure cause |
| Trusted non-retryable integration fault | `InfrastructureFailedRun(NON_RETRYABLE, cause)` | A7 terminalizes | `fail_infrastructure` | None / never | Operational; closed infrastructure cause |
| Complete valid mandatory gate failure | `CompletedFixtureRun` | N/A | `complete_and_publish` | Exact A5 result / only through A7 | Completed fixture scoring semantics, no scientific authority |
| Complete valid scored result | `CompletedFixtureRun` | N/A | `complete_and_publish` | Exact A5 result / only through A7 | Completed fixture scoring semantics, no scientific authority |

Unknown exceptions and ambiguous numerical/backend/reference/attribution cases
default to infrastructure. `PACK_NOT_READY` is operational. The sole ready
fixture profile does not normally produce it; its cause remains defensive for
exact A5 integration and future ratified profiles. No A8 status is
`invalid_strategy`, `FAILED_INFRA`, `FAILED_STRATEGY`, `CANCELLED`, `SCORED`,
or `PUBLISHED`; those names belong to A2/A3, A5 or A7 as applicable.

The first deterministic fixture backend ignores Strategy and executes no miner
code, so its service has no positive-attribution path and cannot emit
`StrategyFailedRun`. The closed variant remains for a future separately
ratified real backend; future implementation tests cover its A7 mapping only at
the private outcome/composition seam and never fabricate Strategy blame in the
fixture service.

## A4 context rights and seed use

The fixture service uses only:

- exact `DeterministicFixtureProvider`;
- `acquire_fixture_official_context(provider, handle.seed_pin)`;
- exact returned `FixtureOfficialContext` with `context.pin == handle.seed_pin`;
- `derive_fixture_official_seed`.

It rejects `MockContext`, provider-origin `OfficialContext`,
`QualificationContext`, raw entropy/private roots and caller-provided derived
seeds. Context and derived bytes are ephemeral call-local material, never
returned, retained after use, logged, serialized or sent to A7/A6/A9+.

Exact profile derivations at draw `0`:

| Phase | A4 domain | RoleKey | Profile inputs |
|---|---|---|---|
| train-shaped | `OFFICIAL_TRAIN` | `a8_fixture_train` | `diagnostic_error` |
| eval-shaped | `OFFICIAL_EVAL` | `a8_fixture_eval` | `gate_error`, `physics_error`, `accuracy_error_a`, `accuracy_error_b` |
| stress-shaped | `OFFICIAL_STRESS` | `a8_fixture_stress` | `robust_mean_a`, `robust_tail_a`, `robust_mean_b`, `robust_tail_b` |

`finite_ok` is exact `True` and consumes no derived bytes. Phase labels in the
synthetic HMAC message are exact ASCII `official_train`, `official_eval`, and
`official_stress`.

## Exact fixture profile and independent oracle

Profile ID `a8_fixture_stub_v1` supports exactly:

```text
ChallengeKey:               a5_fixture / fixture-1.0
scoring_version:            fixture-1.0
scoring_digest:             sha256:255923831905a84f55a88d8575e8ebcab42f3351676d6cf5ac9038dcc495fb57
generator_version_required: fixture-1.0
generator_digest_required:  sha256:1111111111111111111111111111111111111111111111111111111111111111
schema_version:              1.0
numerical_profile:           python_binary64_v1
fixture_origin:              true
```

The current A7 focused fixture uses a different `a7_fixture` identity. Future
A8 tests construct an A7 envelope aligned to the existing A5 pin; this
documentation does not claim the existing A5/A7 fixtures already integrate or
change either fixture.

For each profile numeric input:

1. Select the exact phase-derived A4 bytes above as HMAC-SHA-256 key.
2. Start the message with exact ASCII
   `carbon.a8.fixture-stub.scalar.v1`.
3. Append these exact ASCII fields in order, each framed as unsigned four-byte
   big-endian byte length plus bytes: profile ID, phase label, input key,
   scoring digest, generator digest, configured backend-profile ID, configured
   container digest.
4. Compute `n = int.from_bytes(digest[0:8], "big") >> 11`.
5. Compute built-in binary64 `u = n / 2**53`.
6. For `gate_error`, compute in order `0.5 + (1.0 * u)`; for every other
   numeric input, compute `0.125 + (0.5 * u)`.

The mapping is conspicuous synthetic test material. It is not a prediction,
reference, relative error, metric operator, scientific threshold/tolerance,
qualification result or production value. Attempt number, mutable Strategy,
independently presented StrategyHash, time, Python `hash()`, `random`, ambient
environment variables, filesystem/order, network, mutable backend registry/
global state and call order are absent. The A4 derived key binds the exact
SeedPin/EvaluationBinding; configured environment values bind the environment
separately.

Future tests include literal expected outputs and an independent straight-line
oracle that imports no implementation encoder/helper. They perturb every
SeedPin identity field through A4, opaque EvaluationBinding, environment
profile/digest, profile, phase and input key. A retry vector changes the exact
handle attempt only and preserves scalar material. Test failures never expose
fixture entropy or derived bytes.

## A5 construction and completion boundary

First require the complete exact profile pin. Then compare only the shared
SeedPin projection:

```text
ScorePackPin.challenge_key              == SeedPin.challenge_key
ScorePackPin.scoring_version            == SeedPin.scoring_version
ScorePackPin.scoring_digest             == SeedPin.scoring_digest
ScorePackPin.generator_version_required == SeedPin.generator_version
ScorePackPin.generator_digest_required  == SeedPin.generator_digest
```

EvaluationBinding and seed scheme have no A5 pin fields; wholesale pin
equality is not claimed. Schema version, numerical profile and fixture origin
are checked through full loaded-pin equality with `FixtureStubProfile`.

A8 creates exact `NumericInput`/`BooleanInput` material and calls only
`LoadedScorePack.fixture_score_input`, then `ScoreEngine.score`. It never calls
the private ScoreInput factory or constructs `InternalResult`. Missing, extra,
malformed, partial or non-finite material reaches no ScoreInput or engine.
Pack/input/computation/infrastructure/reference failures create no gate or
zero. Only A5 constructs the exact two completed statuses.

## Environment, resource, launch and shutdown taxonomy

| Concern | Owner |
|---|---|
| Hostile submission topology/identity admissibility | A7 `SubmissionResourceLimits` before A2 |
| Retained submission-record capacity | A7 store policy |
| Safe immutable environment identity | A7 `ExecutionEnvironmentPin` |
| Attempt identity/currentness/FSM/retry budget/fee/refund/cancellation/publication | A7 |
| Trusted fixture runtime profile/configuration | A8 |
| Actual CPU/GPU/backend selection | A8/backend adapter |
| Concrete memory/time/process/filesystem/network controls | A8 real runtime and qualified container |
| Launch/materialization/output validation/redaction | A8 |
| Production values and retry classifications | Human security/operations/protocol owners |
| Transcript/receipt/config evidence/authenticated provenance | Later evidence owner |

The trusted A8 configuration reconstructs its declared environment pin and
requires exact handle equality before launch. It never executes configuration
from the pin or treats equality as qualification evidence. Fixture runtime
values are conspicuous nominal fixture inputs structurally rejected by future
production types; no value is selected in this ratification.

The first stub is synchronous and has no cancellation API. Current A7 owns its
requester cancellation state. A future real adapter separately owns transient
cooperative/hard shutdown mechanics without creating another lifecycle.
Same-process execution provides none of the OS/container controls listed for a
real backend.

## Threat, leakage, and redaction plan

| Threat | Wave-A stub control | Later required control |
|---|---|---|
| Pathological nested/large accepted Strategy values | Ignore raw Strategy; use safe handle identity only | Closed real-backend parameter interpretation and hard runtime bounds |
| Backend-selection/path/import injection | Exact trusted backend/profile; no dynamic import/path | Qualified backend registry/container |
| Path traversal/filesystem/network/credential exfiltration | No filesystem/network/env/credential access and no miner code | Mount/network/credential isolation |
| Fork/process/memory/disk bomb and timeout evasion | No miner-controlled subprocess or unbounded allocation | PID/cgroup/quota/supervisor/hard kill |
| Malformed/non-finite output | Exact bounded key/type/shape/finiteness/completeness checks | Qualified tensor/protocol adapter |
| Hostile exception/repr/amplification | Never call `str`/`repr`; closed cause only | Process-boundary protocol and bounded telemetry |
| Fixture/mock/production relabelling | Exact fixture envelope/context/profile/service/outcome types | Positive qualified production provenance |
| Forged/subclassed values | Exact type/reconstruction for structural correctness | Authentication/evidence; exact values alone are not capabilities |
| Stale completion | Return exact handle; A7 callback revalidates | Durable/distributed coordination later |
| Seed/runtime leakage | Ephemeral secret handling; no result/error/retention fields | Audited logging/evidence pipeline |

Minimum private outcome fields are the owned handle, variant, cause/retry class
where applicable, and exact completed A5 result where applicable. The handle
necessarily carries safe `SeedPin` and `ExecutionEnvironmentPin`; the outcome
does not duplicate runtime configuration.

Outcomes, errors, retained post-run state and reachable public graphs exclude
context, entropy/private roots, raw official/master/derived seed, domain/role/
draw identity, predictions, references, raw metric/category/percentile
vectors, ScoreInput, checkpoint/model weights, exception text/stack traces,
paths, environment variables/runtime config, credentials, fee data, A6 cards,
public diagnostics, transcripts/receipts/evidence/signatures, emission weights
and eligibility overrides.

## Mechanical false emission and later refusal

- Exact fixture backend capability is mechanically false.
- Exact fixture service capability is mechanically false.
- Exact fixture outcome capability is mechanically false.
- No caller sets or mutates an emission Boolean through supported APIs.
- A5 independently guarantees `eligible_for_emission=False`.
- A6 independently projects exact fixture origin and false eligibility.
- A8 imports/calls no A6, leaderboard, chain or weight writer.

A future official consumer must require positive qualified production origin,
profile/pack and required evidence/receipt. Merely observing a false/true
Boolean is never provenance. Actual downstream refusal belongs to the later
consumer's integration test and is not implemented by A8.

## Reserved mock/light and production limitations

TrainEval remains one architectural execution owner, but data rights use exact
separate services:

```text
MockTrainEvalService.run_mock(
  exact future MockExecutionRequest
) -> MockRunOutcome
```

The mock result is not A5/A7/A6 material and cannot affect fee, official score,
card, leaderboard, weight or emission. A9 owns miner-facing transport/
disclosure, not mock execution semantics. Exact mock request/resource/
disclosure and joint A8/A9 integration remain a later documentation task; A9
estimate/light implementation cannot begin first.

Future production is another nominal service accepting only
`ProductionExecutionEnvelope` and provider-acquired `OfficialContext`. It is
blocked on OQ-005/OQ-006, production A3/backend/A5/A6/evidence/security/
operations qualification, exact resource/retry policy and human authorization.
No fixture/mock type can be relabelled into it.

## Expected future implementation surface and imports

| Module | Responsibility | Allowed source imports | Forbidden source imports/calls | Visibility |
|---|---|---|---|---|
| `carbon/traineval/model.py` | Exact profile/policy, errors, enums and private outcomes | Stdlib; minimum A5/A7 types | A2/A3 gates, A6, A7 service/store, A9+, legacy/heavy/network | Private integration types; narrow construction types only at root |
| `carbon/traineval/stub.py` | HMAC-based synthetic backend and output material | Stdlib plus private A8 model | All optional/heavy/dynamic/network/legacy backends | `FixtureStubBackend` is a narrow trusted-composition root export; raw backend material is private |
| `carbon/traineval/service.py` | Boundary order, config/pin/context/profile checks, A5 input/score | Exact A4/A5 and A7 model types | A2 validation, A3 admission, A6, A7 service/store, A9+ | Narrow fixture service |
| `carbon/traineval/__init__.py` | Exact root exports: `FixtureRunIdentityError`, `FixtureRunRequestError`, `FixtureRuntimePolicy`, `FixtureStubBackend`, `FixtureStubProfile`, `FixtureTrainEvalService` | A8 modules only | Cause/retry enums, outcomes, backend material, `InternalResult` or other raw/private convenience exports | No miner/public result surface |

No `integration.py` is added in the first implementation; trusted composition
maps outcomes outside A7/A8. A7 never imports A8.

Import tests enforce direct source dependencies and calls. They do not falsely
require `sys.modules` to exclude A7 service/A6: current
`carbon.fees.__init__` eagerly initializes its existing dependencies when A7
model types are imported. A8 adds no direct dependency/call to those owners
and no new package dependency.

## Future CPU and quality matrix

Canonical future file: `tests/cpu/test_traineval_stub.py`.

The implementation task maps every one of the ticket's twenty-five unchecked
criteria to tests. The matrix includes exact/subclass and cross-kind rejection;
pin/profile/context/environment agreement; service preflight; no A2/A3 repeat;
no direct A6/A7-service/store access; all outcomes and A7 mappings; stale
callback rejection by A7; retry-policy ownership; deterministic equality;
independent literal goldens; exact domain/role/draw and all-identity
perturbations; attempt invariance; no ambient time/random/network/filesystem/
environment/global state; output bounds/finiteness/completeness; A5-only input
and result construction; PACK_NOT_READY separation; hostile exception
redaction; false emission capability; hidden-material exclusion; fresh
ownership and supported-API mutation isolation; serialization refusal; direct
source-import graph; optional/heavy dependency isolation; wheel/outside-tree
execution; no new dependency; related A4--A7/leakage/package suites; full CPU;
Ruff, Black and no-new-debt.

The future test may construct a fixture A7 envelope matching the existing A5
pack. It must not alter A2--A7 semantics or claim the current mismatched A7
test fixture already integrates. Documentation/test descriptions are not
current `TESTED` evidence.

## Bounded future implementation sequence

After the separate start gate:

1. Add exact private model/profile/error/outcome types.
2. Add deterministic standard-library stub with literal profile constants.
3. Add fixture service boundary, A4 derivation, pack/environment checks and A5
   handoff.
4. Add the single canonical CPU file and direct import/wheel checks.
5. Run focused, related, full CPU and quality ratchet.
6. Record evidence without marking production/mock/scientific qualification.

No step adds a real backend, sandbox, mock service, A9 integration, A6 access,
evidence, logging, leaderboard, chain, weights or emissions.

## Ratification-only validation

The documentation PR must contain exactly:

```text
Design_Specs/Build_Out.md
.agent/DECISIONS.md
.agent/plans/A8_traineval_stub.md
.agent/tickets/A8_traineval_stub.md
docs/context/Implemented_vs_Specified
```

Validation is limited to documentation checks: exact manifest, `git diff
--check`, maturity text, ticket checkbox count, Build Out conflict search,
tracker/A9+ exclusion and clean post-commit worktree. No Python test result is
created or claimed by this candidate.

## Implementation start gate

Implementation remains forbidden until all of these occur in a separate task:

1. This candidate receives independent technical review.
2. A human explicitly authorizes the documentation contract.
3. The draft PR is marked ready and merged by an authorized human workflow.
4. A fresh fetch verifies the exact ratification merge/tree and successful
   required CI.
5. A fresh branch/PR/concurrency search finds no competing A8 implementation.
6. `.agent/WAVE.md` still records A8 `todo` and A9--A12 `todo`.
7. A human issues a separate bounded A8 implementation task.

Only then may A8 be marked `in_progress`. Merge of documentation alone never
marks it implemented, tested, production-qualified, or done.

## Executed plan and bounded closeout evidence

The historical gates above were executed in separate, human-authorized
lifecycles:

1. **Ratification.** PR #28 preserved reviewed head
   `b354c4df4f559b90df2d53f28c06bed3ec0df87f` and merged normally as
   `872be272fe80df19c28611388fc4e1ebcd7b4900`, tree
   `925191f711daaafb3fa33d58c0bd8c53efc74141`. That merge ratified A8-R1
   through A8-R15 without implementing A8.
2. **Bounded implementation.** Original commit
   `e16677b54e6523b1203d09c7807a736909041ac9`, parent the ratification merge,
   implemented the four-module fixture seam and canonical CPU test.
3. **Synchronization.** Reviewed synchronization commit
   `872736cdee0b4149856a68229b34c69e2b2f0490` has ordered parents
   `e16677b54e6523b1203d09c7807a736909041ac9` and
   `f8c211602191a10c9a59f1e6f68fb60918f70882`, and tree
   `9d7f5ee3e78edbc72dc75391fafb87373ae3019d`.
4. **Implementation merge.** PR #29 merged the synchronized head normally as
   `d0011e959622b65f6ae737db7477062104bafa33`, with the synchronized head as
   parent two and the same tree. Post-merge push run `32676389502` passed
   `1562` tests in `41.34s` and the unchanged quality ratchet.
5. **Independent closeout audit.** Review stopped closeout on two
   `IMPLEMENTATION_LAG` defects: A8 reconstructed A5 `InternalResult`
   directly, and malformed `SeedPin.seed_scheme` identity was silently
   normalized while its perturbation was omitted. The source guard also
   covered only `service.py`.
6. **Corrective repair.** Head
   `eb1af294edc35b25ea36a699968092470e5d2afa`, parent the PR #29 merge,
   moved recursive result copying to A5, rejected malformed scheme identity at
   A4, delegated from A8, added the seventh identity case, and expanded the
   guard across every A8 module. PR #30 merged it normally as
   `b30c3f5fc2a53df0611d5e8b80120fbf4b64531c`; ordered parents are
   `d0011e959622b65f6ae737db7477062104bafa33` and the corrective head, and the
   corrective-head/merge tree is exactly
   `db94ca592af2ee808976c615b97065dbcbeb7f24`.
7. **Final current-main evidence.** Push run `32686140393` passed `1584` CPU
   tests in `42.19s`; quality remained `Ruff 757/776; Black 62/68`, removed
   debt `Ruff 19, Black 6`, six changed Python files clean, and no new debt.
   Recorded focused/related/full results are `649`/`1197`/`1584`; the
   independent golden selection passed `17`, retaining all nine literal
   scalars, literal leg scores, and combined score `0.8947523571654831`.
   Fresh Python 3.11.11 wheel/outside-tree `-I` import retained the exact six
   exports with no blocked optional-heavy/later module and wheel SHA-256
   `a37f4d0f1545582ae42a2a4de0a1d56276de4c64fbd5b9bc547fd63cfb408f25`.

The implemented surface is exactly:

```text
carbon/traineval/__init__.py
carbon/traineval/model.py
carbon/traineval/service.py
carbon/traineval/stub.py
tests/cpu/test_traineval_stub.py
```

The corrective repair additionally changed only the A5/A4/A8 owner models and
their three canonical CPU test files, plus tracker evidence. Those owner-test
additions weakened no existing A0--A7 behavior or expectation and changed no
fixture, dependency, packaging, CI, or quality baseline.

The executed reuse result followed the planned order:

- **KEEP:** the package seam, A4 provider/context/derivation, A5 pack/engine/
  result authority, A7 envelope/handle/FSM authority, and dependency-light
  standard-library path.
- **WRAP:** exact A4/A5/A7 values behind the nominal fixture-only A8 service
  and private outcome boundary.
- **REPAIR:** the stale Build Out/ticket contract before implementation, then
  the two independently found conformance defects and incomplete source guard.
- **REPLACE/EXCLUDE:** legacy/PoC/neurons/Julia/training/validator/backend/
  emission behavior remained outside A8; no broad rewrite was performed.

All `25/25` existing bounded criteria have current code/test evidence and are
checked in the ticket by this documentation-only closeout candidate. The
proposed `done` status becomes authoritative only after independent review,
explicit human authorization, and merge. A9--A12 remain unstarted and `todo`.
The exact mock request/resource/disclosure contract still requires separate
A8/A9 documentation ratification before any A9 estimate/light implementation.

## Explicit non-goals

No real neural-operator training; production backend; production container or
sandbox; production runtime/resource/retry values; scientific threshold,
metric, transform, weight or tolerance; production provider/timing/fallback;
LIVE challenge or Score Pack; immutable real-backend Strategy handoff;
authenticated provenance; transcript, receipt, evidence or signature; A6
publication bypass; MCP or mock implementation; leaderboard; logging/metrics;
A12 invariant implementation; Bittensor/chain; weight setting; emissions; or
production/scientific/security qualification.
