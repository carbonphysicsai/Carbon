# Ticket A8 — bounded fixture-official TrainEvalAPI stub contract

**Wave:** A

**Status:** proposed `done` by this documentation-only closeout; effective only
after independently reviewed, explicitly human-authorized merge

**Build_Out:** §5 TrainEvalAPI and Wave-A stub policy

**Direct contract dependencies:** A4, A5, A7

**Prior admission authorities:** A2 and A3, already consumed by A7

**Decision authority:** A8-R1--A8-R15, ratified by reviewed, human-authorized
PR #28 merge `872be272fe80df19c28611388fc4e1ebcd7b4900`

**Implementation plan:** `.agent/plans/A8_traineval_stub.md`

## Current bounded maturity

```text
A8 SPECIFIED / RATIFIED: YES
A8 IMPLEMENTED: YES on current main for the bounded fixture-official,
deterministic, process-local stub scope, including the reviewed conformance
repair
A8 TESTED: YES only for the exact recorded CPU/security/import/wheel/quality
scope
A8 SCIENTIFICALLY_QUALIFIED: NO
A8 SECURITY_QUALIFIED: NO
A8 NETWORK_QUALIFIED: NO
A8 COMMERCIALLY_VALIDATED: NO
A8 PRODUCTION-QUALIFIED: NO
A8 WAVE STATUS: done only after this documentation-only closeout is
independently reviewed, explicitly human-authorized, and merged
```

The earlier maturity block and future-only wording in this ticket were the
pre-implementation snapshot ratified by PR #28. They are historically
superseded by the reviewed PR #29 implementation and PR #30 conformance repair
now present on current `main`; documentation detail itself is still neither
implementation nor test evidence. This candidate records administrative
closeout only. A9 has not begun, and A9--A12 remain `todo`.

## Goal

Current `main` implements the smallest deterministic fixture-official TrainEval
service that consumes A7's exact fixture execution envelope, uses only A4's
fixture-official context path, constructs complete synthetic fixture scalar
input through A5's validated boundary, invokes current `ScoreEngine`, and
returns a private closed orchestration outcome. The stub is useful for
lifecycle and contract tests but is mechanically incapable of scientific or
emission authority.

## Bounded conceptual contract

```text
FixtureTrainEvalService.run_fixture(
    envelope: exact FixtureExecutionEnvelope
) -> private FixtureRunOutcome
```

Trusted composition supplies an immutable exact `FixtureStubProfile`, exact
A4 `DeterministicFixtureProvider`, exact verified `LoadedScorePack`, trusted
fixture runtime configuration, exact declared execution-environment identity,
and deterministic `FixtureStubBackend`.

The exact `FixtureRuntimePolicy` is a frozen/slotted fixture-only value with
literal ID `a8_fixture_stub_policy_v1`, safe backend-profile/container-digest
identity fields, and an immutable total cause-to-retry-class tuple. It contains
no production or numeric runtime values. The service reconstructs the
environment pin from those fields and requires policy, separately declared
identity, exact backend capability metadata, and handle pin agreement. The
table is trusted fixture test policy, not retry permission or a production
default.

The run call accepts no independent Strategy, StrategyHash, batch, mode,
runtime limit, attempt number, ChallengeKey, SeedPin, environment pin, context,
seed, Score Pack, or backend identity. A7 supplies the exact fixture envelope
and handle. The stub ignores the independently presented mutable Strategy and
StrategyHash; A4 derivation through the handle's exact SeedPin already binds
the opaque A7 `EvaluationBinding` built from A7's stored submission,
StrategyHash, and ChallengeKey identity.

Current exact-type process-local envelopes are correctness values, not
authenticated capabilities. A future real backend needs a separately ratified
immutable/verifiable Strategy snapshot handoff.

## Closed private outcomes

```text
FixtureRunOutcome =
    CompletedFixtureRun(exact ExecutionAttemptHandle, exact InternalResult)
  | StrategyFailedRun(exact handle, closed StrategyFailureCause)
  | InfrastructureFailedRun(
        exact handle,
        closed InfrastructureRetryClass,
        closed InfrastructureCause
    )
```

Only exact A5 `SCORED` and `MANDATORY_GATE_FAILED` results may complete.
`PACK_NOT_READY` is operational and cannot appear in a completion. The retry
class is trusted policy classification, not permission to retry; A7 alone
applies attempt budget and terminalization.

The deterministic fixture service ignores Strategy and executes no miner code,
so it cannot positively attribute or emit `StrategyFailedRun`. That closed
variant is reserved for a separately ratified real backend; its current A7
mapping is tested only at the private outcome/composition seam.

Exact cause names are specified by A8-R8 in `.agent/DECISIONS.md`. Arbitrary
diagnostic strings are forbidden. Wrong/subclassed/cross-kind/malformed or
internally contradictory untrusted envelope values produce stable non-echoing
typed errors. Trusted composition preconstructs and preflights the service
before starting the A7 attempt. Once a structurally exact owned fixture
envelope boundary is established,
trusted configuration, pack, context, environment, backend, materialization,
input, and scoring failures return a closed infrastructure outcome so the A7
attempt is not stranded `RUNNING`. Only A7 establishes current-handle
authority; A8 does not authenticate the envelope.

The exact errors are `FixtureRunRequestError` with code
`traineval.fixture_request_invalid` and message `Fixture execution request is
invalid.`, and `FixtureRunIdentityError` with code
`traineval.fixture_identity_invalid` and message `Fixture execution identity
is invalid.`. They accept no caller diagnostic arguments and suppress exception
chaining at the boundary.

Trusted composition maps the outcomes to A7 operations; A8 never mutates A7:

```text
CompletedFixtureRun       -> complete_and_publish
StrategyFailedRun         -> fail_strategy
RETRYABLE infrastructure  -> retry_infrastructure
NON_RETRYABLE infra       -> fail_infrastructure
malformed untrusted value -> no mutation based on that value
stale callback            -> A7 rejects with no mutation
```

## Fixture context, profile, and scoring boundary

The fixture service accepts only exact `FixtureOfficialContext` acquisition
through `acquire_fixture_official_context` and derivation through
`derive_fixture_official_seed`. It never accepts `MockContext`, provider-origin
`OfficialContext`, qualification context, raw entropy, or caller-provided
derived seeds.

`FixtureStubProfile` is conspicuously fixture-only and supports exactly the
current A5 fixture ScorePackPin recorded in A8-R6, including its exact external
scoring digest. Any other pack fails closed. The profile defines private
synthetic scalar inputs only; it makes no prediction, reference, metric,
scientific-validity, backend-qualification, or production claim.

A8 constructs the complete input only through
`LoadedScorePack.fixture_score_input` and calls `ScoreEngine.score`. A5 alone
owns input validation, pack readiness, gates, transforms, aggregation,
`ScoreStatus`, `InternalResult`, and fixture emission ineligibility.

## Reserved mock/light lane

Build Out and current A9 intent retain a mock/light free path, but it is not
part of this first implementation and never shares a generic string mode. A
future separately ratified nominal contract may resemble:

```text
MockTrainEvalService.run_mock(
    request: exact future MockExecutionRequest
) -> MockRunOutcome
```

That outcome is not an A5 `InternalResult`, does not enter A7/A6, creates no
card, and affects no fee, official score, leaderboard rank, weight, or
emission. A9 may not begin estimate/light implementation until the exact mock
request/resource/disclosure contract is separately ratified. This ticket does
not edit or begin A9.

## Bounded implementation Definition of Done

- [x] The future branch starts from the reviewed ratification merge after a
      fresh main, status, and competing-work check; A8 alone is marked
      `in_progress` only in that separately authorized task.
- [x] `model.py` defines frozen/slotted exact fixture profile/policy, closed
      non-echoing errors, causes, retry class, and private nonserializable
      outcome variants without arbitrary diagnostic text.
- [x] `FixtureTrainEvalService.run_fixture` accepts only an exact
      `FixtureExecutionEnvelope`; exact-type/subclass, malformed, cross-kind,
      contradictory identity, and reconstruction cases are tested.
- [x] The service reconstructs the exact handle and safe identity values,
      requires `AdmissionKind.FIXTURE`, and requires envelope ChallengeKey to
      equal the exact handle SeedPin ChallengeKey.
- [x] The exact fixture profile is bound to the recorded A5 fixture
      `ScorePackPin`, including scoring digest; every other pack fails closed,
      and exact ChallengeKey, scoring-version/digest, and required-generator-
      version/digest projection mismatches with the handle SeedPin fail
      operationally without claiming wholesale pin equality.
- [x] Trusted A8 configuration reconstructs its exact
      `ExecutionEnvironmentPin` and requires equality with the handle pin;
      the pin is never used as runtime configuration or qualification proof.
- [x] The fixture provider/context boundary accepts only exact A4 fixture
      types, acquires using the handle SeedPin, requires exact context-pin
      equality, and rejects fixture/mock/production/qualification crossing.
- [x] The deterministic backend implements A8-R6's exact domain/role/draw,
      framing, HMAC and binary64 synthetic-scalar profile with no use of raw
      Strategy or independently presented StrategyHash.
- [x] Independent literal golden vectors and a straight-line oracle cover the
      exact fixture profile without exposing fixture entropy or derived seeds.
- [x] Perturbation vectors cover every SeedPin identity field through A4,
      EvaluationBinding changes, environment profile/digest, profile version,
      and phase/input separation.
- [x] Repeated execution is equal; attempt-number changes alter only the
      returned handle while immutable synthetic scalar material remains
      equal across retries.
- [x] Tests prove no Python `hash()`, ambient time/randomness, network,
      filesystem access/ordering, mutable process-global registry, ambient
      environment-variable value,
      or call-order state affects execution.
- [x] Stub output is exact, bounded, complete and finite; malformed,
      non-finite, missing, extra, shape-invalid, or amplified output becomes a
      closed infrastructure outcome and never a scientific zero/gate.
- [x] Complete inputs are constructed only through
      `LoadedScorePack.fixture_score_input`; `ScoreEngine.score` is invoked and
      A8 never constructs `ScoreInput` or `InternalResult` directly.
- [x] Only exact `SCORED` and `MANDATORY_GATE_FAILED` results can construct
      `CompletedFixtureRun`; `PACK_NOT_READY`, pack mismatch, input failure and
      computation failure remain operational.
- [x] The fixture service proves `StrategyFailedRun` unreachable because it
      ignores Strategy and executes no miner code; private composition tests
      preserve its future real-backend mapping, and every ambiguous numerical,
      backend, reference, exception or attribution case defaults to
      infrastructure.
- [x] Every closed outcome maps exactly to the A7 operation recorded above;
      A7 applies retry budget, stale handles fail without mutation, and no real
      attempt is stranded by a trusted integration failure.
- [x] Spies/source-import checks prove A8 never calls A2 `dry_validate`, repeats
      A3 admission/backbone logic, directly source-imports A7 service/store or
      A6, or invokes those owners; tests do not falsely require transitive
      `carbon.fees` package initialization to omit its existing dependencies.
- [x] Fixture backend, service and outcome mechanically expose false emission
      capability without a caller-settable Boolean; exact A5/A6 fixture false
      eligibility remains independent defense in depth.
- [x] Hidden context/entropy/raw official, master or derived seed, raw execution
      material, exception, path, runtime configuration/environment-variable,
      credential, fee, card and later evidence fields are absent from return
      values, errors, retained objects and reachable public graphs; the exact
      handle necessarily retains its safe SeedPin and ExecutionEnvironmentPin.
- [x] Fresh reconstruction and no retained caller aliases isolate supported
      caller/envelope/backend/result mutation from owned identity/outcomes;
      generic serialization/copying is refused where appropriate without
      claiming frozen Python objects resist arbitrary same-process tampering.
- [x] Source/import tests enforce the four-module dependency direction and
      exclude legacy/PoC/neurons/Julia, A9+, network clients, dynamic backend
      imports, and eager Torch/JAX/PhysicsNeMo/neural-operator loading.
- [x] Installed-wheel/outside-tree import is dependency-light and usable with
      no new dependency; canonical focused tests live only at
      `tests/cpu/test_traineval_stub.py`.
- [x] Full default CPU regression passes without changing A0--A7 behavior,
      tests, fixtures, dependencies, packaging, CI or quality baseline.
- [x] Ruff, Black and repository no-new-debt checks pass with every changed
      Python file clean; evidence remains fixture/process-local and makes no
      production qualification claim.

Criterion 24 records behavioral/test-contract preservation, not the absence of
corrective regression coverage. PR #30 added A4/A5 owner regression tests and
expanded the A8 source guard, but weakened no A0--A7 behavior or existing test
expectation and changed no fixture, dependency, packaging, CI, or quality
baseline.

## Closeout evidence

- Ratification PR #28 merged normally as
  `872be272fe80df19c28611388fc4e1ebcd7b4900`, tree
  `925191f711daaafb3fa33d58c0bd8c53efc74141`, with ordered parents
  `6a3fe0f8e34602af5a4eaeaa8ae145d967537724` and
  `b354c4df4f559b90df2d53f28c06bed3ec0df87f`.
- The original bounded implementation commit
  `e16677b54e6523b1203d09c7807a736909041ac9`, tree
  `e29e4874c72fc0bcbee101e2063773f244dd640b`, has the ratification merge as
  its sole parent. Synchronization commit
  `872736cdee0b4149856a68229b34c69e2b2f0490`, tree
  `9d7f5ee3e78edbc72dc75391fafb87373ae3019d`, has ordered parents
  `e16677b54e6523b1203d09c7807a736909041ac9` and
  `f8c211602191a10c9a59f1e6f68fb60918f70882`.
- Implementation PR #29 merged normally as
  `d0011e959622b65f6ae737db7477062104bafa33`, with ordered parents
  `f8c211602191a10c9a59f1e6f68fb60918f70882` and
  `872736cdee0b4149856a68229b34c69e2b2f0490`; its merge tree is the exact
  synchronized-head tree `9d7f5ee3e78edbc72dc75391fafb87373ae3019d`.
  Its bounded manifest is `.agent/WAVE.md`, the four
  `carbon/traineval/*.py` modules, and
  `tests/cpu/test_traineval_stub.py`. Post-merge push run `32676389502`
  completed successfully with `1562` CPU tests and the quality gate passing.
- Independent closeout review found two `IMPLEMENTATION_LAG` defects: A8
  directly reconstructed A5 `InternalResult`, and malformed
  `SeedPin.seed_scheme` identity was silently normalized while the A8
  perturbation matrix omitted that field. Neither finding changed the ratified
  A8 contract.
- Corrective head `eb1af294edc35b25ea36a699968092470e5d2afa`, tree
  `db94ca592af2ee808976c615b97065dbcbeb7f24`, has sole parent
  `d0011e959622b65f6ae737db7477062104bafa33`. Corrective PR #30 merged
  normally as current-main commit
  `b30c3f5fc2a53df0611d5e8b80120fbf4b64531c`, with ordered parents
  `d0011e959622b65f6ae737db7477062104bafa33` and
  `eb1af294edc35b25ea36a699968092470e5d2afa`; the merge tree remains exact
  `db94ca592af2ee808976c615b97065dbcbeb7f24`, and the head-to-merge diff is
  empty.
- The corrective manifest is exactly `.agent/WAVE.md`,
  `carbon/scoring/model.py`, `carbon/seeding/model.py`,
  `carbon/traineval/model.py`, `tests/cpu/test_scoring_engine.py`,
  `tests/cpu/test_seeding.py`, and `tests/cpu/test_traineval_stub.py`. A5 now
  owns recursive result copying, A4 rejects malformed seed-scheme identity,
  A8 delegates to A5, and the source guard covers every A8 Python module.
- Corrective evidence is focused `649 passed in 7.08s`, related
  `1197 passed in 29.66s`, full `1584 passed in 34.33s`, and the unchanged
  independent oracle/golden/identity/retry/concurrency selection
  `17 passed in 0.16s`. All nine literal synthetic scalars, all three literal
  leg scores, and exact combined score `0.8947523571654831` remain unchanged.
- Fresh Python 3.11.11 wheel/outside-tree `-I` installation with `--no-deps`
  preserved the exact six root exports and loaded zero blocked optional-heavy
  or later modules. Wheel SHA-256 is
  `a37f4d0f1545582ae42a2a4de0a1d56276de4c64fbd5b9bc547fd63cfb408f25`.
- Post-corrective main push run `32686140393` completed successfully at exact
  head `b30c3f5fc2a53df0611d5e8b80120fbf4b64531c`: CPU was
  `1584 passed in 42.19s`; quality was `Ruff 757/776; Black 62/68`, removed
  debt `Ruff 19, Black 6`, all six changed Python files clean, and no new debt.
- All 25 bounded engineering criteria are satisfied. Checking them confers no
  scientific, security, network, commercial, or production qualification.
  A9--A12 remain unstarted and `todo`.

## Implemented bounded layout

```text
carbon/traineval/
    __init__.py
    model.py
    service.py
    stub.py
```

- `model.py`: immutable fixture profile/policy, private outcomes and stable
  errors.
- `stub.py`: deterministic dependency-free fixture backend.
- `service.py`: exact envelope/config/pin/context checks, profile execution,
  A5 validated input construction and scoring.
- `__init__.py`: exact root exports are `FixtureRunIdentityError`,
  `FixtureRunRequestError`, `FixtureRuntimePolicy`, `FixtureStubBackend`,
  `FixtureStubProfile`, and `FixtureTrainEvalService`. Cause/retry enums,
  backend material, outcomes and `InternalResult` are not root exports;
  completion remains a trusted private integration surface rather than a
  miner/public API.

Forbidden direct source imports/calls include A2 validation, A3 admission, `carbon.cards`,
`carbon.fees.service`, A7 stores, A9--A12, legacy training/validator/emission,
PoC, neurons, Julia, eager heavy scientific frameworks, network clients, and
dynamic backend imports. Current `carbon.fees` package initialization may load
its existing service/card dependencies when A8 imports A7 model types; that is
not permission for an A8 source dependency or call. A7 must not import A8.

## Explicit non-goals

No real neural-operator training, production backend/container/sandbox,
production runtime value, scientific threshold/tolerance/metric/transform,
production context/provider policy, LIVE Score Pack, immutable real-backend
Strategy handoff, authenticated provenance, transcript/receipt/evidence/
signature, A6 bypass, MCP/mock implementation, leaderboard, logging/metrics,
A12 invariant implementation, Bittensor/chain, weights, or emissions.

**Canonical bounded tests:**
`python -m pytest tests/cpu/test_traineval_stub.py -q`
