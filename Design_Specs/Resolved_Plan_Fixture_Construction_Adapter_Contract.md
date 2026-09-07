# Resolved-Plan Fixture Construction Adapter Contract

**Status:** working B-07F engineering authority
**Version:** 1.0
**Date:** 2026-09-07
**Decision:** B-07F-D1
**Authority ceiling:** fixture-only integration mechanics; never scientific,
security, production, LIVE, ranking, frontier, network, or settlement authority

## 1. Ownership and placement

B-07F owns one private, nominal, fixture-only TrainEval provider that consumes
an exact B-02B `ResolvedConstructionPlan`. It sits behind A7's existing
`FixtureExecutionEnvelope` and returns A8's existing `CompletedFixtureRun` on
success. A7 remains the sole submission store, lifecycle, attempt, fee, and
result-publication owner. A5 remains the score owner. B-02B remains the only
compiler and B-02C remains the resource-policy owner.

The existing A8 `FixtureTrainEvalService` and `FixtureStubBackend` are frozen
Strategy-insensitive plumbing fixtures. B-07F neither modifies nor
reinterprets them. There is no new public operation, wire version, lifecycle,
store, caller-selected mode, or dispatcher.

## 2. Trusted construction

The provider is constructed by trusted composition with exact nominal values:

- Challenge, CandidateAssemblyContract/ref, ParameterCatalog/ref, compiler
  identity, authoring origin/artifacts, and A7 Strategy limits;
- B-02C ResearchResourcePolicy/ref, exact class bundle, selected resource
  class/ref, and expected-active refs;
- DeterministicFixtureProvider, fixture execution environment, ready A5
  LoadedScorePack, B-03 fixture generator-configuration ref, B-04 pinned
  reference identity, B-05 MeasurementContractRef, and a fixture-only asset;
- the registered training-lever surface, consumer, executable-semantics ref,
  and fixture measurement input keys.

Run requests carry only A7's exact `FixtureExecutionEnvelope`. They cannot
replace configuration, entropy, context, assets, policy, scorer, or mode.
Constructor mismatch fails closed before execution.

## 3. Compilation and identity binding

For each envelope the provider invokes B-02B `compile_strategy` on the detached
Strategy. Accepted output must bind exactly to the envelope Challenge and
StrategyHash and to the constructor-pinned catalog, assembly, compiler,
training support, and canonical R_strategy. A compiler rejection returns the
exact safe `CompileIssue` tuple and no plan or score.

The provider consumes only the accepted plan and its resolved training policy.
It never branches on raw Strategy values or StrategyHash. The registered
consumer and executable-semantics ref must match the constructor-pinned
fixture mechanism, and every resolved training binding must be recognized;
otherwise construction fails as an ignored-lever defense.

## 4. Resource binding

Before construction the provider asks B-02C to assess the exact plan against
the exact constructor-pinned policy and class. Only `ADMISSIBLE` proceeds.
Forecasts, quotes, calibration labels, and caller claims are not inputs and
cannot grant execution or result authority. An unresolved B-07E forecast is
therefore irrelevant to this adapter.

## 5. Bounded responsive fixture

The B-02B fixture surface `fixture_sampling_level` is the only consumed lever.
It is a registered `SAMPLING` lever targeting
`fixture_training.sampling_level`, with levels 1 and 2 and an exact executable
semantics ref. The fixture asset contains two fixed training observations of
the non-authoritative toy relation `y = x^2` and separate held-out observations.

FixtureOfficialEntropy may deterministically order the two training
observations. Level 1 fits a through-origin linear toy model using the first
observation; level 2 fits it using both. The fit is the exact least-squares
coefficient `sum(x*y) / sum(x*x)`. Thus the plan changes both the observations
consumed during construction and the constructed coefficient. Held-out mean
squared error is measured on the separate fixture reference observations.
The two permitted levels are structurally guaranteed to differ for the fixed
asset, independent of entropy order. This demonstrates plan consumption, not
scientific superiority or production validity.

The adapter maps the non-negative held-out fixture measurement through the
fixed monotone fixture transform `e / (1 + e)` and the constructor-pinned A5
fixture input keys, then calls the existing LoadedScorePack
factory and `ScoreEngine`. It changes no B-05 contract, A5 weights, gates,
uncertainty, ranking, or score semantics.

## 6. Entropy, reference, and rights

The only entropy acquisition is `acquire_fixture_official_context` from an
exact `DeterministicFixtureProvider`, followed by
`derive_fixture_official_seed` in registered official-shaped domains. Mock,
qualification, provider-origin official, LIVE, raw caller entropy, and caller
seed values have no constructor or run path.

The fixture asset is challenge-bound and binds exact B-03 fixture generator,
B-04 reference, and B-05 measurement identities. It is non-serializable,
non-production, and cannot contain arbitrary code. Cross-Challenge and
cross-context substitution fail closed.

## 7. Outcomes and precedence

The outcome union is nominal and authority-preserving:

1. `FixtureCompilationFailed` — exact B-02B issues;
2. `FixtureResourceFailed` — B-02C non-admissibility or policy machinery;
3. `FixtureConstructionFailed` — unsupported/ignored lever or invalid toy fit;
4. `FixtureReferenceFailed` — fixture reference material cannot be evaluated;
5. `FixtureMeasurementFailed` — fixture measurement/A5 input material fails;
6. existing `InfrastructureFailedRun` — environment, entropy, or ScorePack
   identity machinery;
7. `ResolvedFixtureCompletedRun` — existing A8 completion plus receipts.

No failure becomes a zero score or another authority class. A scoring
machinery exception is a measurement failure; a scientific gate failure
produced by A5 remains an A5 scored result, not machinery failure.
Errors and reprs use closed redacted text without cases, seeds, paths, raw
measurements, scorer internals, or provider topology.

## 8. Exact private receipts

Success produces immutable content-addressed reconstruction and result
receipts. The reconstruction receipt binds the exact attempt, Challenge,
StrategyHash, plan and R_strategy refs, assembly, catalog, compiler,
training-support, resource-policy/class/assessment, environment, generator,
reference, measurement, fixture asset, consumed lever/value, and constructed
artifact digest. The result receipt binds that reconstruction receipt, A5
ScorePack pin, result status, and a digest of the owned A5 result.

Receipt canonical bytes exclude entropy, seeds, fixture cases, raw
measurements, paths, and authority-escalating labels. Both carry the fixed
marker `TEST_ONLY_FIXTURE_NOT_QUALIFIED`; their refs are private tagged SHA-256
digests. They are evidence for deterministic parity checks only.

## 9. Practice parity and determinism

B-07C nominal practice and B-07F must resolve the same Strategy under the same
Challenge, assembly, catalog, compiler, training support, R_strategy, plan,
resource-policy, and registered lever semantics. Practice and fixture-official
then diverge at their separately typed entropy and protected asset boundaries;
their numeric outcomes need not match.

For fixed envelope, constructor dependencies, asset, and fixture entropy,
canonical plan, constructed artifact, A5 result, and both receipts reproduce
exactly. Changing one registered lever changes the plan ref and constructed
artifact while unrelated pinned authorities remain fixed.

## 10. Negative authority and migration

This adapter accepts no participant code and is not a production sandbox. It
does not access official/provider reference stores, private experiment stores,
Landscape, card lake, network, leaderboard, frontier, treasury, or settlement.
It cannot emit, qualify, activate, or publish scientific claims. A real
reconstruction worker, production data rights, isolation, scientific fixture,
and qualification policy require later owner-authorized contracts and nominal
capabilities; this fixture cannot be relabeled into them.
