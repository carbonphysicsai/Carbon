"""End-to-end B-07G service integration and protocol conformance."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest
from b02b_fixtures import strategy_limits
from b07a_fixtures import digest, discovery_resources
from b07b_fixtures import Catalog, Compiler, Manifests, outcome
from b07c_fixtures import make_fixture
from b07d_fixtures import prior_fixture, public_pack

from carbon import research
from carbon.construction.compiler import SUPPORTED_COMPILER_IDENTITY


class _UnavailablePrior:
    def get_prior(self, request):
        raise KeyError


class _UnavailableAlignment:
    def inspect_prior_alignment(self, request):
        raise KeyError


class _Static:
    def __init__(self, **results):
        self.results = results
        self.calls = []

    def __getattr__(self, name):
        if name not in self.results:
            raise AttributeError(name)

        def invoke(argument):
            self.calls.append((name, argument))
            outcome = self.results[name]
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome

        return invoke


def _compiler(fixture):
    source = fixture.domain.compile_fixture
    return research.B02BCompilationProvider(
        candidate_assembly=source.assembly,
        candidate_assembly_ref=source.assembly.to_ref(),
        parameter_catalog=source.catalog,
        parameter_catalog_ref=source.catalog.to_ref(candidate_assembly=source.assembly),
        authoring_origin=source.authoring_origin,
        authoring_artifacts=source.authoring_artifacts,
        compiler_identity=SUPPORTED_COMPILER_IDENTITY,
        strategy_limits=strategy_limits(),
    )


def _service_fixture(tmp_path):
    fixture = make_fixture(tmp_path)
    compiler = _compiler(fixture)
    domain = fixture.domain
    inspection = research.StaticResourceInspectionProvider(
        compilation_resolver=Compiler(domain),
        expected_training_support_ref=domain.plan.training_support_ref,
        policy=domain.policy,
        policy_ref=domain.policy_ref,
        class_bundle=domain.class_bundle,
        selected_resource_class=domain.resource_class,
        selected_resource_class_ref=domain.resource_class_ref,
        authority_context=domain.context,
    )
    context = research.ExternalPublicResearchContext(
        Catalog(fixture.info),
        Manifests(fixture.manifest),
        _UnavailablePrior(),
        fixture.scaffold,
        research.A2ValidationProvider(),
        compiler,
        _UnavailableAlignment(),
        inspection,
        research.UncalibratedResourceForecastProvider(inspection),
        fixture.provider,
    )
    return fixture, research.LocalResearchService(context)


def _call(service, operation, request, namespace=research.RESEARCH_NAMESPACE):
    return service.call(research.ServiceCall(namespace, operation, request))


def _assert_ok(reply, expected_type):
    assert reply.status is research.ReplyStatus.OK
    assert type(reply.result) is expected_type
    return reply.result


def test_exact_context_graphs_have_no_mode_or_generic_registry() -> None:
    import dataclasses

    assert tuple(
        item.name for item in dataclasses.fields(research.ExternalPublicResearchContext)
    ) == (
        "challenge_catalog_provider",
        "manifest_provider",
        "public_prior_provider",
        "scaffold_provider",
        "validation_provider",
        "compilation_provider",
        "prior_alignment_provider",
        "resource_inspection_provider",
        "resource_forecast_provider",
        "research_task_provider",
    )
    assert tuple(
        item.name for item in dataclasses.fields(research.FixtureResearchContext)
    ) == (
        "challenge_catalog_provider",
        "manifest_provider",
        "public_prior_provider",
        "test_only_prior_provider",
        "test_only_authorization_provider",
        "scaffold_provider",
        "validation_provider",
        "compilation_provider",
        "prior_alignment_provider",
        "resource_inspection_provider",
        "resource_forecast_provider",
        "research_task_provider",
    )


def test_complete_non_prior_domain_operation_path_uses_real_owners(tmp_path) -> None:
    fixture, service = _service_fixture(tmp_path)
    key = fixture.info.challenge_key
    info = _assert_ok(
        _call(service, "get_challenge_info", research.GetChallengeInfoRequest(key)),
        research.ChallengeInfo,
    )
    manifest = _assert_ok(
        _call(
            service,
            "get_interaction_manifest",
            research.GetInteractionManifestRequest(key),
        ),
        research.InteractionManifest,
    )
    assert info == fixture.info
    assert manifest.capability_labels == ()

    scaffold = _assert_ok(
        _call(
            service,
            "get_mock_scaffold",
            research.GetMockScaffoldRequest(key, info.training_support_ref, None),
        ),
        research.MockScaffold,
    )
    assert "MOCK_ONLY" in scaffold.limitations
    validation = _assert_ok(
        _call(
            service,
            "dry_validate",
            research.DryValidateRequest(key, fixture.strategy),
        ),
        research.DryValidationResult,
    )
    assert validation.valid is True and validation.issues == ()
    compilation = _assert_ok(
        _call(
            service,
            "compile_strategy",
            research.CompileStrategyRequest(
                key, fixture.strategy, info.training_support_ref
            ),
        ),
        research.CompileStrategyResult,
    )
    assert compilation.accepted is True
    assert all(
        value is not None
        for value in (
            compilation.strategy_hash,
            compilation.training_sampling_policy_ref,
            compilation.resolved_plan_ref,
            compilation.compilation_ref,
        )
    )

    inspected = _assert_ok(
        _call(
            service,
            "inspect_resources",
            research.InspectResourcesRequest(
                key, fixture.strategy, fixture.domain.policy_ref
            ),
        ),
        research.InspectResourcesResult,
    )
    assert "NOT_FORECAST" in inspected.limitations
    forecast = _assert_ok(
        _call(
            service,
            "forecast_resources",
            research.ForecastResourcesRequest(
                key, fixture.strategy, fixture.domain.policy_ref, 60
            ),
        ),
        research.ResourceForecast,
    )
    assert "SUPPORT:UNRESOLVED" in forecast.limitations

    start_request = fixture.request("paired")
    started = _assert_ok(
        _call(service, "start_research_task", start_request),
        research.StartResearchTaskResult,
    )
    polled = _assert_ok(
        _call(
            service,
            "get_research_result",
            research.GetResearchResultRequest(key, started.task.task_id, 0),
        ),
        research.GetResearchResultResult,
    )
    cancelled = _assert_ok(
        _call(
            service,
            "cancel_research_task",
            research.CancelResearchTaskRequest(
                key, started.task.task_id, "cancel-fixture-0001"
            ),
        ),
        research.CancelResearchTaskResult,
    )
    assert polled.task.state is research.ResearchTaskState.QUEUED
    assert cancelled.disposition is research.CancellationDisposition.ACCEPTED
    assert cancelled.task.state is research.ResearchTaskState.CANCELLED


def _prior_service(*, fixture: bool, prior_result, authorization=None, alignment=None):
    key = prior_result.prior_pack.challenge_key
    info, manifest = discovery_resources(challenge_id=key.challenge_id)
    provider = _Static(get_prior=prior_result)
    alignment_provider = _Static(
        inspect_prior_alignment=alignment
        or research.PriorAlignmentResult(
            research.PriorAlignmentRef(key, content_digest=digest("e")),
            research.PriorAlignmentStatus.NOT_APPLICABLE,
            (),
        )
    )
    other = _Static(
        get_mock_scaffold=KeyError(),
        dry_validate=KeyError(),
        compile_strategy=KeyError(),
        inspect_resources=KeyError(),
        forecast_resources=KeyError(),
        start_research_task=KeyError(),
        get_research_result=KeyError(),
        cancel_research_task=KeyError(),
    )
    arguments = (
        Catalog(info),
        Manifests(manifest),
        provider,
    )
    if fixture:
        context = research.FixtureResearchContext(
            *arguments,
            provider,
            authorization,
            other,
            other,
            other,
            alignment_provider,
            other,
            other,
            other,
        )
    else:
        context = research.ExternalPublicResearchContext(
            *arguments,
            other,
            other,
            other,
            alignment_provider,
            other,
            other,
            other,
        )
    return research.LocalResearchService(context), info, provider, alignment_provider


def _fixture_prior_result():
    _, _, pack = prior_fixture()
    pack_ref = research.prior_pack_ref(pack)
    receipt = research.TestOnlyPriorAuthorizationReceipt(
        pack.challenge_key,
        pack_ref,
        "fixture_suite",
        9_000_000_000_000,
    )
    receipt_ref = receipt.to_ref("fixture_authorization")
    result = research.PriorLookupResult(
        research.PriorIndexSnapshotRef(
            pack.challenge_key,
            pack.channel,
            0,
            content_digest=digest("d"),
        ),
        pack,
        pack_ref,
        research.PriorLookupStatus.ACTIVE,
        research.FixturePriorAuthorization(receipt_ref),
    )
    return result, receipt


def test_fixture_context_prior_is_nominally_authorized_and_labeled() -> None:
    result, receipt = _fixture_prior_result()
    auth = _Static(fixture_authorization=receipt)
    service, info, _, _ = _prior_service(
        fixture=True, prior_result=result, authorization=auth
    )
    manifest = _assert_ok(
        _call(
            service,
            "get_interaction_manifest",
            research.GetInteractionManifestRequest(info.challenge_key),
        ),
        research.InteractionManifest,
    )
    assert manifest.capability_labels == ("TEST_ONLY_FIXTURE_PRIOR",)
    reply = _assert_ok(
        _call(
            service,
            "get_prior",
            research.GetPriorRequest(
                info.challenge_key,
                research.ExactPriorSelector(result.prior_pack_ref),
            ),
        ),
        research.PriorLookupResult,
    )
    assert reply.authorization == result.authorization
    assert set(reply.prior_pack.limitations) >= {
        "TEST_ONLY",
        "NOT_UTILITY_QUALIFIED",
    }
    assert len(auth.calls) == 1


def test_external_context_rejects_fixture_prior_before_provider() -> None:
    result, _ = _fixture_prior_result()
    service, info, provider, _ = _prior_service(fixture=False, prior_result=result)
    reply = _call(
        service,
        "get_prior",
        research.GetPriorRequest(
            info.challenge_key,
            research.ExactPriorSelector(result.prior_pack_ref),
        ),
    )
    assert (
        reply.result.code
        is research.ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID
    )
    assert provider.calls == []


def test_public_prior_and_alignment_dispatch_remain_separate() -> None:
    _, _, fixture_pack = prior_fixture()
    pack = public_pack(fixture_pack)
    pack_ref = research.prior_pack_ref(pack)
    result = research.PriorLookupResult(
        research.PriorIndexSnapshotRef(
            pack.challenge_key,
            pack.channel,
            0,
            content_digest=digest("c"),
        ),
        pack,
        pack_ref,
        research.PriorLookupStatus.ACTIVE,
        research.PublicPriorAuthorization(
            research.PriorPublicationReceiptRef(
                pack.challenge_key,
                pack.channel,
                0,
                content_digest=digest("b"),
            )
        ),
    )
    service, info, prior, alignment = _prior_service(fixture=False, prior_result=result)
    _assert_ok(
        _call(
            service,
            "get_prior",
            research.GetPriorRequest(
                info.challenge_key,
                research.ActivePriorSelector(research.PriorChannel.PUBLIC),
            ),
        ),
        research.PriorLookupResult,
    )
    _assert_ok(
        _call(
            service,
            "inspect_prior_alignment",
            research.InspectPriorAlignmentRequest(
                info.challenge_key,
                {
                    "schema_version": "1.0",
                    "challenge_id": info.challenge_key.challenge_id,
                    "backbone": "fno",
                    "parameters": {},
                },
                pack_ref,
            ),
        ),
        research.PriorAlignmentResult,
    )
    assert len(prior.calls) == 1
    assert len(alignment.calls) == 1


def test_namespace_reserved_operation_and_request_type_precedence(tmp_path) -> None:
    fixture, service = _service_fixture(tmp_path)
    request = research.GetChallengeInfoRequest(fixture.info.challenge_key)
    for namespace, operation, expected in (
        ("merged", "unknown", research.ResearchServiceErrorCode.NAMESPACE_MISMATCH),
        (
            research.RESEARCH_NAMESPACE,
            "submit",
            research.ResearchServiceErrorCode.NAMESPACE_MISMATCH,
        ),
        (
            research.RESEARCH_NAMESPACE,
            "quote_execution",
            research.ResearchServiceErrorCode.CAPABILITY_UNAVAILABLE,
        ),
        (
            research.RESEARCH_NAMESPACE,
            "latest",
            research.ResearchServiceErrorCode.OPERATION_UNSUPPORTED,
        ),
    ):
        assert _call(service, operation, request, namespace).result.code is expected

    forged = object.__new__(research.ServiceCall)
    object.__setattr__(forged, "namespace", research.RESEARCH_NAMESPACE)
    object.__setattr__(forged, "operation", "get_challenge_info")
    object.__setattr__(
        forged,
        "request",
        research.GetInteractionManifestRequest(fixture.info.challenge_key),
    )
    assert (
        service.call(forged).result.code
        is research.ResearchServiceErrorCode.REQUEST_TYPE_INVALID
    )


def test_call_bytes_canonical_unknown_bound_and_forbidden_precede_provider(
    tmp_path,
) -> None:
    fixture, service = _service_fixture(tmp_path)
    request = research.DryValidateRequest(fixture.info.challenge_key, fixture.strategy)
    payload = research.canonical_bytes(
        research.ServiceCall(research.RESEARCH_NAMESPACE, "dry_validate", request)
    )
    good = research.load_canonical(service.call_bytes(payload), research.ServiceReply)
    assert good.status is research.ReplyStatus.OK

    cases = (
        (
            payload + b"trailing",
            research.ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID,
        ),
        (
            payload.replace(b"operation", b"operatiox", 1),
            research.ResearchServiceErrorCode.UNKNOWN_FIELD,
        ),
        (
            b"x" * (research.MAX_CALL_REPLY_BYTES + 1),
            research.ResearchServiceErrorCode.BOUND_EXCEEDED,
        ),
        (
            payload.replace(b"parameters", b"privatekey", 1),
            research.ResearchServiceErrorCode.FORBIDDEN_SCIENTIFIC_CONTROL,
        ),
        (
            payload.replace(b"namespace", b"provider_", 1),
            research.ResearchServiceErrorCode.CONTEXT_SELECTION_FORBIDDEN,
        ),
    )
    for malformed, expected in cases:
        reply = research.load_canonical(
            service.call_bytes(malformed), research.ServiceReply
        )
        assert reply.status is research.ReplyStatus.ERROR
        assert reply.result.code is expected


def test_operation_scalar_bounds_and_reference_mismatch_are_typed(tmp_path) -> None:
    fixture, service = _service_fixture(tmp_path)
    request = research.ForecastResourcesRequest(
        fixture.info.challenge_key,
        fixture.strategy,
        fixture.domain.policy_ref,
        60,
    )
    payload = research.canonical_bytes(
        research.ServiceCall(research.RESEARCH_NAMESPACE, "forecast_resources", request)
    )
    bounded = payload.replace((60).to_bytes(8, "big"), (604_801).to_bytes(8, "big"))
    reply = research.load_canonical(service.call_bytes(bounded), research.ServiceReply)
    assert reply.result.code is research.ResearchServiceErrorCode.BOUND_EXCEEDED

    other_key = research.ChallengeKey("other_challenge", "1.0")
    wrong_ref = replace(fixture.domain.policy_ref, challenge_key=other_key)
    forged = object.__new__(research.InspectResourcesRequest)
    object.__setattr__(forged, "challenge_key", fixture.info.challenge_key)
    object.__setattr__(forged, "strategy", fixture.strategy)
    object.__setattr__(forged, "resource_policy_ref", wrong_ref)
    call = object.__new__(research.ServiceCall)
    object.__setattr__(call, "namespace", research.RESEARCH_NAMESPACE)
    object.__setattr__(call, "operation", "inspect_resources")
    object.__setattr__(call, "request", forged)
    assert (
        service.call(call).result.code
        is research.ResearchServiceErrorCode.REFERENCE_MISMATCH
    )


def test_malformed_call_never_reaches_any_domain_provider(tmp_path) -> None:
    fixture, service = _service_fixture(tmp_path)
    validation = _Static(
        dry_validate=research.A2ValidationProvider().dry_validate(
            research.DryValidateRequest(fixture.info.challenge_key, fixture.strategy)
        )
    )
    service = research.LocalResearchService(
        replace(service._context, validation_provider=validation)
    )
    request = research.DryValidateRequest(fixture.info.challenge_key, fixture.strategy)
    payload = research.canonical_bytes(
        research.ServiceCall(research.RESEARCH_NAMESPACE, "dry_validate", request)
    )
    reply = research.load_canonical(
        service.call_bytes(payload + b"malformed"), research.ServiceReply
    )
    assert (
        reply.result.code
        is research.ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID
    )
    assert validation.calls == []


def test_provider_failures_are_isolated_and_redacted(tmp_path) -> None:
    fixture, service = _service_fixture(tmp_path)
    context = service._context
    failing = _Static(
        forecast_resources=RuntimeError("official_seed=private implementation")
    )
    failed_service = research.LocalResearchService(
        replace(context, resource_forecast_provider=failing)
    )
    request = research.ForecastResourcesRequest(
        fixture.info.challenge_key,
        fixture.strategy,
        fixture.domain.policy_ref,
        60,
    )
    reply = _call(failed_service, "forecast_resources", request)
    assert reply.result.code is research.ResearchServiceErrorCode.INTERNAL_FAILURE
    assert "seed" not in reply.result.message.casefold()
    assert fixture.provider._tasks == {}

    unavailable = research.LocalResearchService(
        replace(
            context,
            resource_forecast_provider=_Static(
                forecast_resources=research.DiscoveryProviderUnavailable()
            ),
        )
    )
    retry = _call(unavailable, "forecast_resources", request)
    assert retry.result.code is research.ResearchServiceErrorCode.PROVIDER_UNAVAILABLE
    assert retry.result.retry_disposition is research.RetryDisposition.SAME_REQUEST

    hostile = research.LocalResearchService(
        replace(
            context,
            resource_forecast_provider=_Static(
                forecast_resources={"official_seed": "protected"}
            ),
        )
    )
    rejected = _call(hostile, "forecast_resources", request)
    assert rejected.result.code is research.ResearchServiceErrorCode.DISCLOSURE_REJECTED
    assert "protected" not in research.canonical_bytes(rejected).decode(
        "utf-8", errors="ignore"
    )

    safe_forecast = research.UncalibratedResourceForecastProvider(
        context.resource_inspection_provider
    ).forecast_resources(request)
    protected_forecast = replace(
        safe_forecast,
        limitations=(*safe_forecast.limitations, "official_seed:protected"),
    )
    protected = research.LocalResearchService(
        replace(
            context,
            resource_forecast_provider=_Static(forecast_resources=protected_forecast),
        )
    )
    assert (
        _call(protected, "forecast_resources", request).result.code
        is research.ResearchServiceErrorCode.DISCLOSURE_REJECTED
    )


def test_reply_byte_bound_is_enforced_after_provider_projection(tmp_path) -> None:
    fixture, service = _service_fixture(tmp_path)
    request = research.GetMockScaffoldRequest(
        fixture.info.challenge_key,
        fixture.info.training_support_ref,
        None,
    )
    scaffold = fixture.scaffold.get_mock_scaffold(request)
    large = replace(
        scaffold,
        strategy_template={"payload": ["x" * 16_384] * 70},
    )
    bounded = research.LocalResearchService(
        replace(
            service._context,
            scaffold_provider=_Static(get_mock_scaffold=large),
        )
    )
    reply = _call(bounded, "get_mock_scaffold", request)
    assert reply.result.code is research.ResearchServiceErrorCode.BOUND_EXCEEDED


def test_invalid_validation_and_compilation_create_no_task(tmp_path) -> None:
    fixture, service = _service_fixture(tmp_path)
    invalid = {**fixture.strategy, "unexpected": True}
    validation = _assert_ok(
        _call(
            service,
            "dry_validate",
            research.DryValidateRequest(fixture.info.challenge_key, invalid),
        ),
        research.DryValidationResult,
    )
    compilation = _assert_ok(
        _call(
            service,
            "compile_strategy",
            research.CompileStrategyRequest(
                fixture.info.challenge_key,
                invalid,
                fixture.info.training_support_ref,
            ),
        ),
        research.CompileStrategyResult,
    )
    assert validation.valid is False and validation.issues
    assert compilation.accepted is False and compilation.issues
    assert fixture.provider._tasks == {}


def test_get_prior_none_and_external_task_fixture_selector_fail_before_provider(
    tmp_path,
) -> None:
    fixture, service = _service_fixture(tmp_path)
    no_prior = _call(
        service,
        "get_prior",
        research.GetPriorRequest(
            fixture.info.challenge_key,
            research.NoPriorSelector(),
        ),
    )
    assert (
        no_prior.result.code is research.ResearchServiceErrorCode.REQUEST_TYPE_INVALID
    )

    fixture_prior_ref = research.PriorPackRef(
        fixture.info.challenge_key,
        research.PriorChannel.TEST_ONLY_FIXTURE,
        0,
        digest("a"),
    )
    request = replace(
        fixture.request("paired", key="external-fixture-prior-0001"),
        prior_selector=research.ExactPriorSelector(fixture_prior_ref),
    )
    reply = _call(service, "start_research_task", request)
    assert (
        reply.result.code
        is research.ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID
    )
    assert fixture.provider._tasks == {}


def test_concurrent_start_replay_poll_identity_and_queued_cancellation(
    tmp_path,
) -> None:
    fixture, service = _service_fixture(tmp_path)
    request = fixture.request("paired", key="concurrent-idempotency-0001")

    def start(_):
        return _call(service, "start_research_task", request)

    with ThreadPoolExecutor(max_workers=8) as pool:
        replies = list(pool.map(start, range(16)))
    results = [_assert_ok(reply, research.StartResearchTaskResult) for reply in replies]
    assert sum(result.created for result in results) == 1
    assert len({result.task.task_id for result in results}) == 1
    assert len(fixture.queue.items) == 1

    task = results[0].task
    poll = research.GetResearchResultRequest(task.challenge_key, task.task_id, 0)
    first = _call(service, "get_research_result", poll)
    repeated = _call(service, "get_research_result", poll)
    assert research.canonical_bytes(first) == research.canonical_bytes(repeated)
    skipped = _call(
        service,
        "get_research_result",
        research.GetResearchResultRequest(task.challenge_key, task.task_id, 2),
    )
    assert (
        skipped.result.code is research.ResearchServiceErrorCode.POLL_SEQUENCE_INVALID
    )
    cancelled = _assert_ok(
        _call(
            service,
            "cancel_research_task",
            research.CancelResearchTaskRequest(
                task.challenge_key, task.task_id, "concurrent-cancel-0001"
            ),
        ),
        research.CancelResearchTaskResult,
    )
    assert cancelled.task.state is research.ResearchTaskState.CANCELLED
    too_late = _assert_ok(
        _call(
            service,
            "cancel_research_task",
            research.CancelResearchTaskRequest(
                task.challenge_key, task.task_id, "concurrent-cancel-0002"
            ),
        ),
        research.CancelResearchTaskResult,
    )
    assert too_late.disposition is research.CancellationDisposition.TOO_LATE
    assert too_late.task.terminal_receipt == cancelled.task.terminal_receipt


def test_conflicting_replay_and_terminal_success_are_service_visible(tmp_path) -> None:
    fixture, service = _service_fixture(tmp_path)
    key = "service-idempotency-conflict-0001"
    _assert_ok(
        _call(service, "start_research_task", fixture.request("paired", key=key)),
        research.StartResearchTaskResult,
    )
    conflict = _call(
        service,
        "start_research_task",
        fixture.request("practice", key=key),
    )
    assert (
        conflict.result.code is research.ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
    )
    assert len(fixture.queue.items) == 1

    request = fixture.request("paired", key="service-terminal-success-0001")
    started = _assert_ok(
        _call(service, "start_research_task", request),
        research.StartResearchTaskResult,
    )
    terminal = fixture.provider.run_queued_task(started.task.task_id)
    polled = _assert_ok(
        _call(
            service,
            "get_research_result",
            research.GetResearchResultRequest(
                terminal.challenge_key, terminal.task_id, 0
            ),
        ),
        research.GetResearchResultResult,
    )
    assert polled.task.state is research.ResearchTaskState.SUCCEEDED
    assert polled.task.terminal_receipt == terminal.terminal_receipt


def test_running_cancellation_and_terminal_commit_race_use_b07b_state(tmp_path) -> None:
    fixture, service = _service_fixture(tmp_path)
    entered = threading.Event()
    release = threading.Event()

    class BlockingExecutor:
        def execute(self, attempt):
            entered.set()
            assert release.wait(5)
            return outcome()

    fixture.provider._executor = BlockingExecutor()
    request = fixture.request("paired", key="service-running-cancel-0001")
    started = _assert_ok(
        _call(service, "start_research_task", request),
        research.StartResearchTaskResult,
    )
    results = []
    worker = threading.Thread(
        target=lambda: results.append(
            fixture.provider.run_queued_task(started.task.task_id)
        )
    )
    worker.start()
    assert entered.wait(5)
    cancel = research.CancelResearchTaskRequest(
        started.task.challenge_key,
        started.task.task_id,
        "service-running-cancel-id-0001",
    )
    accepted = _assert_ok(
        _call(service, "cancel_research_task", cancel),
        research.CancelResearchTaskResult,
    )
    assert accepted.task.state is research.ResearchTaskState.CANCEL_REQUESTED
    repeated = _assert_ok(
        _call(service, "cancel_research_task", cancel),
        research.CancelResearchTaskResult,
    )
    assert repeated.disposition is research.CancellationDisposition.ALREADY_ACCEPTED
    release.set()
    worker.join(5)
    assert results[0].state is research.ResearchTaskState.CANCELLED

    fixture2, service2 = _service_fixture(tmp_path / "terminal")
    started2 = _assert_ok(
        _call(
            service2,
            "start_research_task",
            fixture2.request("paired", key="service-terminal-race-0001"),
        ),
        research.StartResearchTaskResult,
    )
    terminal = fixture2.provider.run_queued_task(started2.task.task_id)
    late = _assert_ok(
        _call(
            service2,
            "cancel_research_task",
            research.CancelResearchTaskRequest(
                terminal.challenge_key,
                terminal.task_id,
                "service-terminal-race-cancel-0001",
            ),
        ),
        research.CancelResearchTaskResult,
    )
    assert late.disposition is research.CancellationDisposition.TOO_LATE
    assert late.task.terminal_receipt == terminal.terminal_receipt


def test_operation_matrix_matches_normative_manifest_and_dispatcher() -> None:
    spec = Path("Design_Specs/Miner_MCP_Wave_B_Service_Protocol.md").read_text()
    block = spec.split("<!-- B07S-CONFORMANCE-MANIFEST-BEGIN -->", 1)[1].split(
        "<!-- B07S-CONFORMANCE-MANIFEST-END -->", 1
    )[0]
    manifest = json.loads(block.strip()[len("```json\n") : -len("```")])
    assert tuple(item.operation for item in research.OPERATION_MATRIX) == tuple(
        manifest["operations"]
    )
    assert tuple(research.OPERATION_CONTRACTS) == research.SUPPORTED_OPERATIONS
    for item in research.OPERATION_MATRIX:
        contract = manifest["operation_contracts"][item.operation]
        assert item.request_type.__name__ == contract[0]
        assert item.result_type.__name__ == contract[1]
        assert item.semantic_owner == contract[2]
        assert item.provider_method != ""
        assert item.forbidden_cross_namespace_result is (
            research.ResearchServiceErrorCode.NAMESPACE_MISMATCH
        )
    assert research.RESERVED_OPERATION.operation == "quote_execution"
    assert research.RESERVED_OPERATION.operation not in research.OPERATION_CONTRACTS


def test_dependency_substitution_changes_only_owned_result(tmp_path) -> None:
    fixture, service = _service_fixture(tmp_path)
    key = fixture.info.challenge_key
    original_info = _call(
        service, "get_challenge_info", research.GetChallengeInfoRequest(key)
    )
    original_validation = _call(
        service,
        "dry_validate",
        research.DryValidateRequest(key, fixture.strategy),
    )
    changed_info = replace(
        fixture.info,
        public_score_policy_ref=replace(
            fixture.info.public_score_policy_ref,
            content_digest=digest("f"),
        ),
    )
    alternate_catalog = _Static(get_challenge_info=changed_info)
    alternate = research.LocalResearchService(
        replace(service._context, challenge_catalog_provider=alternate_catalog)
    )
    assert (
        _call(alternate, "get_challenge_info", research.GetChallengeInfoRequest(key))
        != original_info
    )
    assert (
        _call(
            alternate,
            "dry_validate",
            research.DryValidateRequest(key, fixture.strategy),
        )
        == original_validation
    )

    forecast_request = research.ForecastResourcesRequest(
        key, fixture.strategy, fixture.domain.policy_ref, 60
    )
    original_forecast = _assert_ok(
        _call(service, "forecast_resources", forecast_request),
        research.ResourceForecast,
    )
    alternate_forecast = replace(
        original_forecast,
        limitations=("SUPPORT:UNRESOLVED", "ALTERNATE_FIXTURE_FORECAST"),
    )
    forecast_service = research.LocalResearchService(
        replace(
            service._context,
            resource_forecast_provider=_Static(forecast_resources=alternate_forecast),
        )
    )
    assert (
        _assert_ok(
            _call(forecast_service, "forecast_resources", forecast_request),
            research.ResourceForecast,
        )
        == alternate_forecast
    )
    inspect_request = research.InspectResourcesRequest(
        key, fixture.strategy, fixture.domain.policy_ref
    )
    assert _call(forecast_service, "inspect_resources", inspect_request) == _call(
        service, "inspect_resources", inspect_request
    )

    prior_result, receipt = _fixture_prior_result()
    prior_service, prior_info, _, alignment = _prior_service(
        fixture=True,
        prior_result=prior_result,
        authorization=_Static(fixture_authorization=receipt),
    )
    alignment_request = research.InspectPriorAlignmentRequest(
        prior_info.challenge_key,
        {
            "schema_version": "1.0",
            "challenge_id": prior_info.challenge_key.challenge_id,
            "backbone": "fno",
            "parameters": {},
        },
        prior_result.prior_pack_ref,
    )
    original_alignment = _assert_ok(
        _call(prior_service, "inspect_prior_alignment", alignment_request),
        research.PriorAlignmentResult,
    )
    changed_alignment = replace(
        original_alignment,
        status=research.PriorAlignmentStatus.ALIGNED,
    )
    alignment.results["inspect_prior_alignment"] = changed_alignment
    assert (
        _assert_ok(
            _call(prior_service, "inspect_prior_alignment", alignment_request),
            research.PriorAlignmentResult,
        )
        == changed_alignment
    )
    prior_lookup = research.GetPriorRequest(
        prior_info.challenge_key,
        research.ExactPriorSelector(prior_result.prior_pack_ref),
    )
    assert _call(prior_service, "get_prior", prior_lookup).result == prior_result


@pytest.mark.parametrize(
    "operation",
    ("submit", "get_submission_result", "fixture_official_evaluate"),
)
def test_official_v1_and_b07f_paths_never_dispatch(tmp_path, operation) -> None:
    fixture, service = _service_fixture(tmp_path)
    reply = _call(
        service,
        operation,
        research.GetChallengeInfoRequest(fixture.info.challenge_key),
    )
    expected = (
        research.ResearchServiceErrorCode.NAMESPACE_MISMATCH
        if operation in research.OFFICIAL_V1_OPERATIONS
        else research.ResearchServiceErrorCode.OPERATION_UNSUPPORTED
    )
    assert reply.result.code is expected
