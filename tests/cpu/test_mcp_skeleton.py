"""CPU acceptance tests for the bounded Wave-A MCP control plane."""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import inspect
import os
import pickle
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from carbon import mcp
from carbon.cards.model import (
    EvaluationCard,
    EvaluationComponentScores,
    EvaluationGateResult,
)
from carbon.fees import (
    ExecutionEnvironmentPin,
    FeePolicyKey,
    FixtureSubmissionPolicy,
    RequesterIdentity,
    SubmissionAuthorizationError,
    SubmissionId,
    SubmissionNotFoundError,
    SubmissionRequestError,
    SubmissionResourceError,
    SubmissionResourceLimits,
    SubmissionService,
    SubmissionState,
    SubmissionStatusView,
)
from carbon.mcp import (
    ChallengeInfo,
    DryValidateResponse,
    McpCall,
    McpChallengeUnavailableError,
    McpField,
    McpIntegrationError,
    McpQueryBudgetError,
    McpRequestError,
    McpResourceError,
    McpResourceLimits,
    McpService,
    McpSubmissionUnavailableError,
    McpTool,
    McpToolUnavailableError,
    PriorDirective,
    PriorDirectiveKind,
    PriorRef,
    PublishedPrior,
    PublishedScaffold,
    ScaffoldRef,
    StructuralEstimate,
    SubmissionResult,
    SubmitReceipt,
)
from carbon.mcp import service as service_module
from carbon.registry import (
    REQUIRED_QUALIFICATION_STATES,
    ArtifactBinding,
    ChallengeKey,
    ChallengeRecord,
    ChallengeRegistry,
    QualificationEvidence,
    QualificationManifest,
)
from carbon.schema import ValidationIssue, ValidationResult, dry_validate

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CHALLENGE_ID = "a9_fixture"
CHALLENGE_VERSION = "fixture-1.0"
CHALLENGE_KEY = ChallengeKey(CHALLENGE_ID, CHALLENGE_VERSION)
REQUESTER = RequesterIdentity("fixture-requester-v1")
OTHER_REQUESTER = RequesterIdentity("fixture-other-requester-v1")
FIXED_SUBMISSION_ID = "123e4567-e89b-42d3-a456-426614174000"
PUBLIC_EXPORTS = (
    "ChallengeInfo",
    "DryValidateRequest",
    "DryValidateResponse",
    "EstimateProvider",
    "EstimateRequest",
    "GetChallengeInfoRequest",
    "GetMockScaffoldRequest",
    "GetPriorRequest",
    "GetSubmissionResultRequest",
    "McpCall",
    "McpChallengeUnavailableError",
    "McpField",
    "McpIntegrationError",
    "McpQueryBudgetError",
    "McpRequestError",
    "McpResourceError",
    "McpResourceLimits",
    "McpService",
    "McpSubmissionUnavailableError",
    "McpTool",
    "McpToolUnavailableError",
    "PriorDirective",
    "PriorDirectiveKind",
    "PriorProvider",
    "PriorRef",
    "PublishedPrior",
    "PublishedScaffold",
    "QueryBudgetGate",
    "ScaffoldProvider",
    "ScaffoldRef",
    "StructuralEstimate",
    "SubmissionResult",
    "SubmitReceipt",
    "SubmitRequest",
)
_DYNAMIC_IMPORT_NAMES = frozenset({"__import__", "import_module"})
_PROHIBITED_RUNTIME_NAMES = frozenset(
    {
        *_DYNAMIC_IMPORT_NAMES,
        "__builtins__",
        "compile",
        "eval",
        "exec",
        "getattr",
        "globals",
        "locals",
        "vars",
    }
)


def _static_source_string(node: ast.AST) -> str | None:
    if type(node) is ast.Constant:
        value = node.value
        return value if type(value) is str else None
    if type(node) is ast.BinOp and type(node.op) is ast.Add:
        left = _static_source_string(node.left)
        right = _static_source_string(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _source_runtime_escape_violations(
    tree: ast.AST,
) -> tuple[tuple[int, str], ...]:
    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if type(node) is ast.Name and node.id in _PROHIBITED_RUNTIME_NAMES:
            violations.append((node.lineno, f"name:{node.id}"))
        elif type(node) is ast.Attribute and node.attr in _DYNAMIC_IMPORT_NAMES:
            violations.append((node.lineno, f"attribute:{node.attr}"))
        elif (
            type(node) is ast.Call
            and type(node.func) is ast.Name
            and node.func.id == "getattr"
            and len(node.args) >= 2
        ):
            attribute_name = _static_source_string(node.args[1])
            if attribute_name in _DYNAMIC_IMPORT_NAMES:
                violations.append((node.lineno, f"getattr:{attribute_name}"))
        elif type(node) is ast.Subscript:
            key = _static_source_string(node.slice)
            if key in _DYNAMIC_IMPORT_NAMES:
                violations.append((node.lineno, f"subscript:{key}"))
    return tuple(violations)


class _StringSubclass(str):
    pass


class _IntegerSubclass(int):
    pass


class _Hostile:
    def __repr__(self) -> str:
        raise AssertionError("hostile repr invoked")

    def __str__(self) -> str:
        raise AssertionError("hostile str invoked")

    def __iter__(self) -> object:
        raise AssertionError("hostile iterator invoked")

    def __hash__(self) -> int:
        raise AssertionError("hostile hash invoked")

    def __eq__(self, other: object) -> bool:
        del other
        raise AssertionError("hostile equality invoked")


class _Gate:
    def __init__(self) -> None:
        self.calls: list[tuple[RequesterIdentity, McpTool]] = []
        self.result: object = None
        self.failure: BaseException | None = None

    def consume(self, requester: RequesterIdentity, tool: McpTool) -> object:
        self.calls.append((requester, tool))
        if self.failure is not None:
            raise self.failure
        return self.result


class _PriorProvider:
    def __init__(self, value: PublishedPrior) -> None:
        self.value = value
        self.calls: list[ChallengeKey] = []
        self.failure: BaseException | None = None

    def get_prior(self, challenge_key: ChallengeKey) -> PublishedPrior:
        self.calls.append(challenge_key)
        if self.failure is not None:
            raise self.failure
        return self.value


class _ScaffoldProvider:
    def __init__(self, value: PublishedScaffold) -> None:
        self.value = value
        self.calls: list[tuple[ChallengeKey, str | None]] = []
        self.failure: BaseException | None = None

    def get_scaffold(
        self, challenge_key: ChallengeKey, scaffold_id: str | None
    ) -> PublishedScaffold:
        self.calls.append((challenge_key, scaffold_id))
        if self.failure is not None:
            raise self.failure
        return self.value


class _EstimateProvider:
    def __init__(self, directive: PriorDirective) -> None:
        self.directive = directive
        self.calls: list[
            tuple[ChallengeKey, PublishedPrior, dict[str, object], ValidationResult]
        ] = []
        self.substitute_validation = False

    def estimate(
        self,
        challenge_key: ChallengeKey,
        prior: PublishedPrior,
        strategy: dict[str, object],
        validation: ValidationResult,
    ) -> StructuralEstimate:
        self.calls.append((challenge_key, prior, strategy, validation))
        returned_validation = (
            ValidationResult(validation.ok, validation.errors)
            if self.substitute_validation
            else validation
        )
        return StructuralEstimate(
            "1.0",
            challenge_key,
            prior.prior_ref,
            returned_validation,
            (self.directive,),
            "non_binding_structural_prior_only",
        )


def _mcp_limits(**overrides: object) -> McpResourceLimits:
    values: dict[str, object] = {
        "max_call_fields": 16,
        "max_total_request_value_nodes": 10_000,
        "max_request_object_members": 256,
        "max_request_list_items": 256,
        "max_request_string_utf8_bytes": 4096,
        "max_request_object_key_utf8_bytes": 512,
        "max_request_integer_bits": 4096,
        "max_total_request_utf8_bytes": 1_000_000,
        "max_total_response_value_nodes": 10_000,
        "max_response_sequence_items": 256,
        "max_response_string_utf8_bytes": 4096,
        "max_response_integer_bits": 4096,
        "max_total_response_utf8_bytes": 1_000_000,
        "max_concurrent_calls": 8,
    }
    values.update(overrides)
    return McpResourceLimits(**values)  # type: ignore[arg-type]


def _a7_limits() -> SubmissionResourceLimits:
    return SubmissionResourceLimits(
        max_total_value_nodes=10_000,
        max_object_members=256,
        max_list_items=256,
        max_string_utf8_bytes=4096,
        max_object_key_utf8_bytes=512,
        max_strategy_identity_bytes=1_000_000,
        max_challenge_id_bytes=256,
        max_concurrent_identity_builds=8,
        max_retained_submission_records=256,
        max_retained_value_nodes=1_000_000,
        max_retained_strategy_identity_bytes=16_000_000,
    )


def _policy() -> FixtureSubmissionPolicy:
    return FixtureSubmissionPolicy(
        fee_policy_key=FeePolicyKey("fixture-fee-policy-v1.0"),
        amount_minor=1,
        max_attempts=2,
        generator_version="fixture-generator-v1.0",
        generator_digest="sha256:" + "a" * 64,
        scoring_version="fixture-scoring-v1.0",
        scoring_digest="sha256:" + "b" * 64,
        environment_pin=ExecutionEnvironmentPin(
            "fixture-backend-v1.0", "sha256:" + "c" * 64
        ),
    )


def _strategy(**overrides: object) -> dict[str, object]:
    strategy: dict[str, object] = {
        "schema_version": "1.0",
        "challenge_id": CHALLENGE_ID,
        "backbone": "fno",
        "parameters": {},
    }
    strategy.update(overrides)
    return strategy


def _registry(
    tmp_path: Path,
    *,
    lifecycle: str = "fixture",
    name: str = "default",
) -> tuple[ChallengeRegistry, Path]:
    registry_root = tmp_path / f"registry-{name}"
    artifact_root = tmp_path / f"artifacts-{name}"
    registry_root.mkdir(parents=True)
    artifact_root.mkdir(parents=True)
    registry = ChallengeRegistry(registry_root, artifact_root)
    artifact_id = "fixture_bundle"
    artifact_path = f"{CHALLENGE_ID}/{CHALLENGE_VERSION}/bundle.bin"
    content = b"A9 conspicuous non-scientific fixture artifact\n"
    target = artifact_root.joinpath(*artifact_path.split("/"))
    target.parent.mkdir(parents=True)
    target.write_bytes(content)
    digest = "sha256:" + hashlib.sha256(content).hexdigest()
    fixture = lifecycle == "fixture"
    slots = {
        slot: QualificationEvidence(
            state=state,
            artifact_id=artifact_id,
            reference="a9-bounded-fixture-reference",
        )
        for slot, state in REQUIRED_QUALIFICATION_STATES
    }
    record = ChallengeRecord(
        challenge_id=CHALLENGE_ID,
        version=CHALLENGE_VERSION,
        fixture_origin=fixture,
        status="fixture" if fixture else "draft",
        allowed_backbones=("fno",),
        artifacts={artifact_id: ArtifactBinding(artifact_path, digest)},
        qualification=QualificationManifest(
            CHALLENGE_ID,
            CHALLENGE_VERSION,
            "fixture" if fixture else "production",
            slots,
        ),
    )
    registry.save(record)
    if lifecycle == "live":
        registry.activate_live(CHALLENGE_ID, CHALLENGE_VERSION)
    return registry, target


def _publications() -> tuple[PublishedPrior, PublishedScaffold, PriorDirective]:
    prior_ref = PriorRef(
        CHALLENGE_KEY,
        "public_prior",
        "v1.0",
        "sha256:" + "d" * 64,
    )
    directive = PriorDirective(
        PriorDirectiveKind.EXPLORE,
        "backbone",
        ("fno",),
    )
    prior = PublishedPrior("1.0", prior_ref, (directive,))
    shared: list[object] = [1, 2]
    strategy = _strategy(parameters={"left": shared, "right": shared})
    scaffold = PublishedScaffold(
        "1.0",
        ScaffoldRef(
            CHALLENGE_KEY,
            "starter",
            "v1.0",
            "sha256:" + "e" * 64,
        ),
        strategy,
        prior_ref,
        True,
    )
    return prior, scaffold, directive


def _service(
    tmp_path: Path,
    *,
    limits: McpResourceLimits | None = None,
    registry: ChallengeRegistry | None = None,
    prior_provider: object = ...,
    scaffold_provider: object = ...,
    estimate_provider: object = ...,
    gate: _Gate | None = None,
) -> tuple[
    McpService,
    ChallengeRegistry,
    SubmissionService,
    _Gate,
    _PriorProvider,
    _ScaffoldProvider,
    _EstimateProvider,
]:
    if registry is None:
        registry, _ = _registry(tmp_path)
    submission_service = SubmissionService(_a7_limits(), registry, _policy())
    prior, scaffold, directive = _publications()
    default_prior = _PriorProvider(prior)
    default_scaffold = _ScaffoldProvider(scaffold)
    default_estimate = _EstimateProvider(directive)
    query_gate = gate or _Gate()
    service = McpService(
        registry,
        submission_service,
        limits or _mcp_limits(),
        query_gate,
        default_prior if prior_provider is ... else prior_provider,
        default_scaffold if scaffold_provider is ... else scaffold_provider,
        default_estimate if estimate_provider is ... else estimate_provider,
    )
    return (
        service,
        registry,
        submission_service,
        query_gate,
        default_prior,
        default_scaffold,
        default_estimate,
    )


def _call(
    service: McpService,
    tool: object,
    *fields: tuple[object, object],
    requester: RequesterIdentity = REQUESTER,
    schema_version: object = "1.0",
) -> object:
    return service.call(
        McpCall(
            schema_version,
            tool,
            tuple(McpField(name, value) for name, value in fields),
        ),
        requester,
    )


def _challenge_fields() -> tuple[tuple[str, str], tuple[str, str]]:
    return (
        ("challenge_id", CHALLENGE_ID),
        ("challenge_version", CHALLENGE_VERSION),
    )


def _submission_fields(
    strategy: object,
) -> tuple[tuple[str, object], tuple[str, object], tuple[str, object]]:
    return (*_challenge_fields(), ("strategy", strategy))


def _forge(model_type: type[object], **values: object) -> object:
    value = object.__new__(model_type)
    for name, item in values.items():
        object.__setattr__(value, name, item)
    return value


def _forged_directive_kind(member: PriorDirectiveKind) -> PriorDirectiveKind:
    forged = str.__new__(PriorDirectiveKind, member.value)
    object.__setattr__(forged, "_name_", "FORGED_" + member.name)
    object.__setattr__(forged, "_value_", member.value)
    return forged


def _forged_submission_state(member: SubmissionState) -> SubmissionState:
    forged = str.__new__(SubmissionState, member.value)
    object.__setattr__(forged, "_name_", "FORGED_" + member.name)
    object.__setattr__(forged, "_value_", member.value)
    return forged


def _card() -> EvaluationCard:
    return EvaluationCard(
        schema_version="1.0",
        result_id=FIXED_SUBMISSION_ID,
        status="SCORED",
        scoring_pack_hash="sha256:" + "f" * 64,
        overall_score=0.5,
        component_scores=EvaluationComponentScores(0.4, 0.5, 0.6),
        gate_results=(EvaluationGateResult("physics_gate", True),),
        failure_tags=(),
        fixture_origin=True,
        eligible_for_emission=False,
        public_diagnostics=(),
        disclosure_tier="phase0_budgeted",
    )


def test_exact_exports_enums_and_public_layout() -> None:
    assert mcp.__all__ == PUBLIC_EXPORTS
    assert tuple(tool.value for tool in McpTool) == (
        "get_challenge_info",
        "get_prior",
        "get_mock_scaffold",
        "dry_validate",
        "estimate",
        "submit",
        "get_submission_result",
    )
    assert tuple(kind.value for kind in PriorDirectiveKind) == (
        "structural_steer",
        "avoid",
        "explore",
        "not_included",
    )
    assert tuple(field.name for field in dataclasses.fields(McpResourceLimits)) == (
        "max_call_fields",
        "max_total_request_value_nodes",
        "max_request_object_members",
        "max_request_list_items",
        "max_request_string_utf8_bytes",
        "max_request_object_key_utf8_bytes",
        "max_request_integer_bits",
        "max_total_request_utf8_bytes",
        "max_total_response_value_nodes",
        "max_response_sequence_items",
        "max_response_string_utf8_bytes",
        "max_response_integer_bits",
        "max_total_response_utf8_bytes",
        "max_concurrent_calls",
    )
    assert "ChallengeKey" not in vars(mcp)
    assert "EvaluationCard" not in vars(mcp)
    assert "RequesterIdentity" not in vars(mcp)


def test_raw_envelopes_are_storage_only_frozen_and_slotted() -> None:
    class FieldSubclass(McpField):
        pass

    class CallSubclass(McpCall):
        pass

    hostile = _Hostile()
    field = McpField(hostile, hostile)
    call = McpCall(hostile, hostile, hostile)
    subclassed_field = FieldSubclass(hostile, hostile)
    subclassed_call = CallSubclass(hostile, hostile, hostile)
    assert field.name is hostile and field.value is hostile
    assert call.schema_version is hostile and call.tool is hostile
    assert call.fields is hostile
    assert subclassed_field.value is hostile
    assert subclassed_call.fields is hostile
    assert not hasattr(field, "__dict__")
    assert not hasattr(call, "__dict__")
    with pytest.raises(dataclasses.FrozenInstanceError):
        field.value = None  # type: ignore[misc]


@pytest.mark.parametrize(
    ("error_type", "code", "message"),
    (
        (McpRequestError, "mcp.request.invalid", "MCP request is invalid."),
        (
            McpResourceError,
            "mcp.resource_limit_exceeded",
            "MCP resource limit was exceeded.",
        ),
        (
            McpToolUnavailableError,
            "mcp.tool_unavailable",
            "MCP tool is unavailable.",
        ),
        (
            McpChallengeUnavailableError,
            "mcp.challenge_unavailable",
            "Challenge is unavailable.",
        ),
        (
            McpSubmissionUnavailableError,
            "mcp.submission_unavailable",
            "Submission is unavailable.",
        ),
        (
            McpQueryBudgetError,
            "mcp.query_budget_exceeded",
            "MCP query budget was exceeded.",
        ),
        (
            McpIntegrationError,
            "mcp.integration_failure",
            "MCP integration failed.",
        ),
    ),
)
def test_errors_have_exact_fixed_nonserializable_payloads(
    error_type: type[Exception], code: str, message: str
) -> None:
    error = error_type()
    assert type(error) is error_type
    assert error.code == code  # type: ignore[attr-defined]
    assert error.message == message  # type: ignore[attr-defined]
    assert str(error) == message
    assert error.args == (message,)
    with pytest.raises(TypeError):
        error_type("diagnostic")  # type: ignore[call-arg]
    with pytest.raises(AttributeError):
        error.code = "changed"  # type: ignore[attr-defined,misc]
    error.__dict__["code"] = "shadowed"
    error.__dict__["message"] = "shadowed"
    assert error.code == code  # type: ignore[attr-defined]
    assert error.message == message  # type: ignore[attr-defined]
    cause = ValueError("private canary")
    error.__cause__ = cause
    error.__context__ = cause
    error.__suppress_context__ = True
    error.__traceback__ = None
    assert error.__cause__ is cause
    assert error.__context__ is cause
    assert error.__suppress_context__ is True
    with pytest.raises(TypeError):
        pickle.dumps(error)


def test_validated_public_nominals_reject_subclasses_and_forged_enums() -> None:
    class PriorRefSubclass(PriorRef):
        pass

    class LimitsSubclass(McpResourceLimits):
        pass

    with pytest.raises(McpIntegrationError):
        PriorRefSubclass(
            CHALLENGE_KEY,
            "public_prior",
            "v1.0",
            "sha256:" + "d" * 64,
        )
    with pytest.raises(McpRequestError):
        LimitsSubclass(*dataclasses.astuple(_mcp_limits()))
    with pytest.raises(McpIntegrationError):
        PriorDirective(
            _forged_directive_kind(PriorDirectiveKind.EXPLORE),
            "backbone",
            ("fno",),
        )

    forged_directive = _forge(
        PriorDirective,
        kind=PriorDirectiveKind.EXPLORE,
        subject="backbone",
        tokens=["fno"],
    )
    prior_ref = PriorRef(
        CHALLENGE_KEY,
        "public_prior",
        "v1.0",
        "sha256:" + "d" * 64,
    )
    with pytest.raises(McpIntegrationError):
        PublishedPrior("1.0", prior_ref, (forged_directive,))  # type: ignore[arg-type]
    with pytest.raises(McpIntegrationError):
        StructuralEstimate(
            "1.0",
            CHALLENGE_KEY,
            prior_ref,
            ValidationResult(True, ()),
            (forged_directive,),  # type: ignore[arg-type]
            "non_binding_structural_prior_only",
        )
    with pytest.raises(McpIntegrationError):
        PublishedPrior("1.0", object.__new__(PriorRef), ())  # type: ignore[arg-type]
    with pytest.raises(McpIntegrationError):
        DryValidateResponse(
            "1.0",
            object.__new__(ValidationResult),  # type: ignore[arg-type]
        )

    published = SubmissionStatusView(
        SubmissionId(FIXED_SUBMISSION_ID),
        SubmissionState.PUBLISHED,
    )
    partial_card = _forge(EvaluationCard, result_id=FIXED_SUBMISSION_ID)
    with pytest.raises(McpIntegrationError):
        SubmissionResult(
            "1.0",
            published,
            partial_card,  # type: ignore[arg-type]
        )


def test_submission_wrappers_own_status_and_reject_cross_binding() -> None:
    submission_id = SubmissionId(FIXED_SUBMISSION_ID)
    forged_status = _forge(
        SubmissionStatusView,
        submission_id=submission_id,
        state=_forged_submission_state(SubmissionState.PUBLISHED),
    )
    with pytest.raises(McpIntegrationError):
        SubmitReceipt("1.0", forged_status)  # type: ignore[arg-type]
    with pytest.raises(McpIntegrationError):
        SubmissionResult("1.0", forged_status, _card())  # type: ignore[arg-type]

    status = SubmissionStatusView(submission_id, SubmissionState.PUBLISHED)
    card = _card()
    receipt = SubmitReceipt("1.0", status)
    result = SubmissionResult("1.0", status, card)
    assert receipt.status == status and receipt.status is not status
    assert result.status == status and result.status is not status
    assert result.card is card

    mismatched = dataclasses.replace(
        card,
        result_id="123e4567-e89b-42d3-a456-426614174001",
    )
    with pytest.raises(McpIntegrationError):
        SubmissionResult("1.0", status, mismatched)


@pytest.mark.parametrize("invalid", (0, -1, True, _IntegerSubclass(1), 1 << 64))
def test_resource_limits_require_exact_positive_u64(invalid: object) -> None:
    with pytest.raises(McpRequestError):
        _mcp_limits(max_call_fields=invalid)


@pytest.mark.parametrize(
    "tool",
    (
        "info",
        "prior",
        "scaffold",
        "validate_strategy",
        "submit_strategy",
        "light_compare",
        "light_train",
        "list_my_submissions",
        "unknown",
    ),
)
def test_alias_deferred_and_unknown_tools_are_unavailable_without_capture(
    tmp_path: Path, tool: str
) -> None:
    service, *_ = _service(tmp_path)
    with pytest.raises(McpToolUnavailableError) as raised:
        _call(service, tool, ("unknown_semantic_field", _Hostile()))
    assert raised.value.__cause__ is None


def test_outer_and_structural_call_validation(tmp_path: Path) -> None:
    service, *_ = _service(tmp_path)

    class CallSubclass(McpCall):
        pass

    class RequesterSubclass(RequesterIdentity):
        pass

    class FieldSubclass(McpField):
        pass

    with pytest.raises(McpRequestError):
        service.call({}, REQUESTER)  # type: ignore[arg-type]
    with pytest.raises(McpRequestError):
        service.call(CallSubclass("1.0", "dry_validate", ()), REQUESTER)
    with pytest.raises(McpRequestError):
        service.call(McpCall("1.0", "dry_validate", ()), RequesterSubclass("v1"))
    for call in (
        McpCall(1, "dry_validate", ()),
        McpCall("1.0", 1, ()),
        McpCall("1.0", "dry_validate", []),
        McpCall("2.0", "dry_validate", (McpField("strategy", {}),)),
        McpCall("1.0", "dry_validate", (object(),)),
        McpCall("1.0", "dry_validate", (FieldSubclass("strategy", {}),)),
        McpCall("1.0", "dry_validate", (McpField(1, {}),)),
        McpCall(
            "1.0",
            "dry_validate",
            (McpField("strategy", {}), McpField("strategy", {})),
        ),
        McpCall("1.0", "dry_validate", ()),
        McpCall(
            "1.0",
            "dry_validate",
            (McpField("strategy", {}), McpField("extra", None)),
        ),
    ):
        with pytest.raises(McpRequestError):
            service.call(call, REQUESTER)


def test_call_field_limit_precedes_entry_scan(tmp_path: Path) -> None:
    service, *_ = _service(tmp_path, limits=_mcp_limits(max_call_fields=1))
    with pytest.raises(McpResourceError):
        service.call(
            McpCall("1.0", "unknown", (McpField("a", None), _Hostile())),
            REQUESTER,
        )


def test_field_names_precede_value_access_and_tool_dispatch(tmp_path: Path) -> None:
    missing_value = object.__new__(McpField)
    object.__setattr__(missing_value, "name", "ignored")
    service, *_ = _service(tmp_path / "unknown")
    with pytest.raises(McpToolUnavailableError):
        service.call(McpCall("1.0", "unknown", (missing_value,)), REQUESTER)

    overlong_name = object.__new__(McpField)
    object.__setattr__(overlong_name, "name", "strategy_extra")
    service, *_ = _service(
        tmp_path / "resource",
        limits=_mcp_limits(max_request_string_utf8_bytes=12),
    )
    with pytest.raises(McpResourceError):
        service.call(
            McpCall("1.0", "dry_validate", (overlong_name,)),
            REQUESTER,
        )

    missing_semantic_value = object.__new__(McpField)
    object.__setattr__(missing_semantic_value, "name", "strategy")
    with pytest.raises(McpRequestError):
        service.call(
            McpCall("1.0", "dry_validate", (missing_semantic_value,)),
            REQUESTER,
        )

    missing_later_value = object.__new__(McpField)
    object.__setattr__(missing_later_value, "name", "challenge_version")
    service, *_ = _service(
        tmp_path / "value-order",
        limits=_mcp_limits(max_request_string_utf8_bytes=20),
    )
    with pytest.raises(McpResourceError):
        service.call(
            McpCall(
                "1.0",
                "estimate",
                (
                    McpField("challenge_id", "x" * 21),
                    missing_later_value,
                    McpField("strategy", {}),
                ),
            ),
            REQUESTER,
        )

    service, *_ = _service(
        tmp_path / "root-node-order",
        limits=_mcp_limits(max_total_request_value_nodes=1),
    )
    with pytest.raises(McpResourceError):
        service.call(
            McpCall(
                "1.0",
                "estimate",
                (
                    McpField("challenge_id", CHALLENGE_ID),
                    missing_later_value,
                    McpField("strategy", {}),
                ),
            ),
            REQUESTER,
        )


def test_request_container_cardinality_is_committed_before_children(
    tmp_path: Path,
) -> None:
    service, *_ = _service(
        tmp_path,
        limits=_mcp_limits(max_total_request_value_nodes=4),
    )
    with pytest.raises(McpResourceError):
        _call(service, "dry_validate", ("strategy", [[_Hostile(), None], None]))


@pytest.mark.parametrize(
    "strategy",
    (
        (_Hostile(),),
        {("unsupported",): None},
        {"value": float("inf")},
        {"value": _StringSubclass("subclass")},
    ),
)
def test_capture_rejects_unsupported_values_without_rendering(
    tmp_path: Path, strategy: object
) -> None:
    service, *_ = _service(tmp_path)
    with pytest.raises(McpRequestError) as raised:
        _call(service, "dry_validate", ("strategy", strategy))
    assert str(raised.value) == "MCP request is invalid."


def test_capture_preserves_aliases_and_cycles_for_a2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, *_ = _service(tmp_path)
    shared: list[object] = []
    strategy = _strategy(parameters={"left": shared, "right": shared})
    observed: list[object] = []
    canonical = service_module.dry_validate

    def recording(value: object) -> ValidationResult:
        observed.append(value)
        return canonical(value)

    monkeypatch.setattr(service_module, "dry_validate", recording)
    response = _call(service, "dry_validate", ("strategy", strategy))
    assert type(response) is DryValidateResponse
    captured = observed[0]
    assert type(captured) is dict and captured is not strategy
    parameters = captured["parameters"]
    assert type(parameters) is dict
    assert parameters["left"] is parameters["right"]
    assert parameters["left"] is not shared

    cycle: list[object] = []
    cycle.append(cycle)
    response = _call(service, "dry_validate", ("strategy", cycle))
    assert response.validation == dry_validate(cycle)
    assert response.validation is not dry_validate(cycle)


@pytest.mark.parametrize(
    ("override", "value"),
    (
        ("max_total_request_value_nodes", [[], []]),
        ("max_request_list_items", [None, None]),
        ("max_request_object_members", {"a": None, "b": None}),
        ("max_request_string_utf8_bytes", "long"),
        ("max_request_object_key_utf8_bytes", {"long": None}),
        ("max_request_integer_bits", 8),
    ),
)
def test_each_request_resource_dimension_is_enforced(
    tmp_path: Path, override: str, value: object
) -> None:
    limits = _mcp_limits(
        **{
            override: 1,
            "max_total_request_utf8_bytes": 1_000_000,
        }
    )
    service, *_ = _service(tmp_path, limits=limits)
    with pytest.raises(McpResourceError):
        _call(service, "dry_validate", ("strategy", value))


def test_alias_and_cycle_node_accounting_is_identity_aware(tmp_path: Path) -> None:
    shared: list[object] = []
    aliased = [shared, shared]
    service, *_ = _service(
        tmp_path / "pass",
        limits=_mcp_limits(max_total_request_value_nodes=3),
    )
    response = _call(service, "dry_validate", ("strategy", aliased))
    assert response.validation.ok is False

    service, *_ = _service(
        tmp_path / "fail",
        limits=_mcp_limits(max_total_request_value_nodes=2),
    )
    with pytest.raises(McpResourceError):
        _call(service, "dry_validate", ("strategy", aliased))

    cycle: list[object] = []
    cycle.append(cycle)
    service, *_ = _service(
        tmp_path / "cycle",
        limits=_mcp_limits(max_total_request_value_nodes=2),
    )
    assert _call(service, "dry_validate", ("strategy", cycle)).validation.ok is False


def test_request_utf8_surrogate_is_invalid_after_metering(tmp_path: Path) -> None:
    service, *_ = _service(tmp_path / "invalid")
    with pytest.raises(McpRequestError):
        _call(service, "dry_validate", ("strategy", "\ud800"))
    service, *_ = _service(
        tmp_path / "resource",
        limits=_mcp_limits(max_request_string_utf8_bytes=1),
    )
    with pytest.raises(McpResourceError):
        _call(service, "dry_validate", ("strategy", "\ud800x"))


def test_concurrency_precedes_internal_validation_and_releases(
    tmp_path: Path,
) -> None:
    entered = threading.Event()
    release = threading.Event()
    prior, _, _ = _publications()

    class BlockingProvider(_PriorProvider):
        def get_prior(self, challenge_key: ChallengeKey) -> PublishedPrior:
            entered.set()
            assert release.wait(timeout=5)
            return super().get_prior(challenge_key)

    provider = BlockingProvider(prior)
    service, *_ = _service(
        tmp_path,
        limits=_mcp_limits(max_concurrent_calls=1),
        prior_provider=provider,
    )
    failures: list[BaseException] = []

    def worker() -> None:
        try:
            _call(service, "get_prior", *_challenge_fields())
        except BaseException as exc:  # noqa: BLE001 - asserted below
            failures.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    assert entered.wait(timeout=5)
    with pytest.raises(McpResourceError):
        service.call(McpCall(1, 1, 1), REQUESTER)
    release.set()
    thread.join(timeout=5)
    assert not thread.is_alive() and not failures
    assert type(_call(service, "get_prior", *_challenge_fields())) is PublishedPrior


def test_fixture_challenge_projection_is_minimal_and_does_not_enumerate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, registry, *_ = _service(tmp_path)

    def forbidden(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("forbidden registry API called")

    monkeypatch.setattr(type(registry), "scan", forbidden)
    monkeypatch.setattr(type(registry), "can_go_live", forbidden)
    monkeypatch.setattr(type(registry), "activate_live", forbidden)
    monkeypatch.setattr(type(registry), "is_backbone_allowed", forbidden)
    response = _call(service, "get_challenge_info", *_challenge_fields())
    assert type(response) is ChallengeInfo
    assert dataclasses.asdict(response) == {
        "schema_version": "1.0",
        "challenge_key": {
            "challenge_id": CHALLENGE_ID,
            "version": CHALLENGE_VERSION,
        },
        "lifecycle_status": "fixture",
        "fixture_origin": True,
        "effectively_live": False,
        "allowed_backbones": ("fno",),
    }


def test_challenge_projection_uses_pre_assessment_record_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, registry, *_ = _service(tmp_path)
    record = registry.load(CHALLENGE_ID, CHALLENGE_VERSION)
    original_assessment = ChallengeRegistry.assess_live_eligibility

    def cached_load(
        self: ChallengeRegistry,
        challenge_id: str,
        version: str,
    ) -> ChallengeRecord:
        del self, challenge_id, version
        return record

    def mutating_assessment(
        self: ChallengeRegistry,
        challenge_id: str,
        version: str,
        *,
        fixture_mode: bool = False,
    ) -> object:
        result = original_assessment(
            self,
            challenge_id,
            version,
            fixture_mode=fixture_mode,
        )
        object.__setattr__(record, "status", "live")
        object.__setattr__(record, "fixture_origin", False)
        object.__setattr__(record, "allowed_backbones", ("mutated",))
        return result

    monkeypatch.setattr(ChallengeRegistry, "load", cached_load)
    monkeypatch.setattr(
        ChallengeRegistry,
        "assess_live_eligibility",
        mutating_assessment,
    )
    response = _call(service, "get_challenge_info", *_challenge_fields())
    assert response.lifecycle_status == "fixture"
    assert response.fixture_origin is True
    assert response.effectively_live is False
    assert response.allowed_backbones == ("fno",)


def test_draft_and_false_fixture_assessment_are_unavailable(tmp_path: Path) -> None:
    draft_registry, _ = _registry(tmp_path, lifecycle="draft", name="draft")
    service, *_ = _service(tmp_path / "draft-service", registry=draft_registry)
    with pytest.raises(McpChallengeUnavailableError):
        _call(service, "get_challenge_info", *_challenge_fields())

    fixture_registry, artifact = _registry(
        tmp_path, lifecycle="fixture", name="fixture"
    )
    artifact.write_bytes(b"mutated")
    service, *_ = _service(tmp_path / "fixture-service", registry=fixture_registry)
    with pytest.raises(McpChallengeUnavailableError):
        _call(service, "get_challenge_info", *_challenge_fields())


def test_live_true_and_false_are_both_visible(tmp_path: Path) -> None:
    registry, artifact = _registry(tmp_path, lifecycle="live", name="live")
    service, *_ = _service(tmp_path / "live-service", registry=registry)
    response = _call(service, "get_challenge_info", *_challenge_fields())
    assert response.lifecycle_status == "live"
    assert response.effectively_live is True
    artifact.write_bytes(b"mutated")
    response = _call(service, "get_challenge_info", *_challenge_fields())
    assert response.lifecycle_status == "live"
    assert response.effectively_live is False


def test_provider_absence_precedes_missing_challenge(tmp_path: Path) -> None:
    registry, _ = _registry(tmp_path, name="registry")
    service, *_ = _service(
        tmp_path / "service",
        registry=registry,
        prior_provider=None,
        scaffold_provider=None,
        estimate_provider=None,
    )
    missing = (("challenge_id", "missing"), ("challenge_version", "v1"))
    with pytest.raises(McpToolUnavailableError):
        _call(service, "get_prior", *missing)
    with pytest.raises(McpToolUnavailableError):
        _call(service, "get_mock_scaffold", *missing)
    with pytest.raises(McpToolUnavailableError):
        _call(service, "estimate", *missing, ("strategy", {}))


def test_prior_is_validated_bound_and_fresh(tmp_path: Path) -> None:
    service, _, _, _, provider, *_ = _service(tmp_path)
    response = _call(service, "get_prior", *_challenge_fields())
    assert type(response) is PublishedPrior
    assert response == provider.value
    assert response is not provider.value
    assert response.prior_ref is not provider.value.prior_ref
    assert (
        response.prior_ref.challenge_key is not provider.value.prior_ref.challenge_key
    )
    assert response.directives[0] is not provider.value.directives[0]
    assert len(provider.calls) == 1


def test_provider_exception_and_cross_binding_fail_closed(tmp_path: Path) -> None:
    service, _, _, _, provider, *_ = _service(tmp_path / "failure")
    provider.failure = RuntimeError("private provider canary")
    with pytest.raises(McpIntegrationError) as raised:
        _call(service, "get_prior", *_challenge_fields())
    assert "canary" not in str(raised.value)
    assert raised.value.__cause__ is None

    other_key = ChallengeKey("other", "v1")
    prior = PublishedPrior(
        "1.0",
        PriorRef(other_key, "prior", "v1", "sha256:" + "d" * 64),
        (),
    )
    service, *_ = _service(tmp_path / "binding", prior_provider=_PriorProvider(prior))
    with pytest.raises(McpIntegrationError):
        _call(service, "get_prior", *_challenge_fields())


def test_valid_shaped_provider_response_limit_is_resource(tmp_path: Path) -> None:
    prior = PublishedPrior(
        "1.0",
        PriorRef(CHALLENGE_KEY, "very_long_prior", "v1", "sha256:" + "d" * 64),
        (),
    )
    service, *_ = _service(
        tmp_path,
        limits=_mcp_limits(max_response_string_utf8_bytes=8),
        prior_provider=_PriorProvider(prior),
    )
    with pytest.raises(McpResourceError):
        _call(service, "get_prior", *_challenge_fields())


def test_provider_projection_follows_declared_field_precedence(tmp_path: Path) -> None:
    missing_later_fields = _forge(
        PublishedPrior,
        schema_version="overlong_schema",
    )
    service, *_ = _service(
        tmp_path / "prior",
        limits=_mcp_limits(max_response_string_utf8_bytes=8),
        prior_provider=_PriorProvider(missing_later_fields),  # type: ignore[arg-type]
    )
    with pytest.raises(McpResourceError):
        _call(service, "get_prior", *_challenge_fields())

    _, scaffold, _ = _publications()
    non_object = _forge(
        PublishedScaffold,
        schema_version="1.0",
        scaffold_ref=scaffold.scaffold_ref,
        strategy=[None, None],
        informed_by_prior=scaffold.informed_by_prior,
        execution_deferred=True,
    )
    service, *_ = _service(
        tmp_path / "scaffold-shape",
        limits=_mcp_limits(max_response_sequence_items=1),
        scaffold_provider=_ScaffoldProvider(non_object),  # type: ignore[arg-type]
    )
    with pytest.raises(McpIntegrationError):
        _call(service, "get_mock_scaffold", *_challenge_fields())


def test_response_container_cardinality_is_committed_before_children(
    tmp_path: Path,
) -> None:
    prior, _, _ = _publications()
    malformed = _forge(
        PublishedPrior,
        schema_version="1.0",
        prior_ref=prior.prior_ref,
        directives=(_Hostile(), None),
    )
    service, *_ = _service(
        tmp_path,
        limits=_mcp_limits(max_total_response_value_nodes=11),
        prior_provider=_PriorProvider(malformed),  # type: ignore[arg-type]
    )
    with pytest.raises(McpResourceError):
        _call(service, "get_prior", *_challenge_fields())


def test_response_directive_token_alias_is_charged_once_and_preserved(
    tmp_path: Path,
) -> None:
    shared_tokens = ("fno",)
    prior = PublishedPrior(
        "1.0",
        PriorRef(
            CHALLENGE_KEY,
            "public_prior",
            "v1.0",
            "sha256:" + "d" * 64,
        ),
        (
            PriorDirective(
                PriorDirectiveKind.EXPLORE,
                "backbone",
                shared_tokens,
            ),
            PriorDirective(
                PriorDirectiveKind.AVOID,
                "optimizer",
                shared_tokens,
            ),
        ),
    )
    service, *_ = _service(
        tmp_path,
        limits=_mcp_limits(max_total_response_value_nodes=19),
        prior_provider=_PriorProvider(prior),
    )
    response = _call(service, "get_prior", *_challenge_fields())
    assert response.directives[0].tokens is response.directives[1].tokens
    assert response.directives[0].tokens is not shared_tokens


def test_response_enum_value_limit_precedes_hidden_name_corruption(
    tmp_path: Path,
) -> None:
    prior, _, _ = _publications()

    class MutatingProvider:
        def get_prior(self, challenge_key: ChallengeKey) -> PublishedPrior:
            del challenge_key
            object.__setattr__(PriorDirectiveKind.EXPLORE, "_name_", "CORRUPTED")
            object.__setattr__(PriorDirectiveKind.EXPLORE, "_value_", "x" * 72)
            return prior

    service, *_ = _service(
        tmp_path,
        limits=_mcp_limits(max_response_string_utf8_bytes=64),
        prior_provider=MutatingProvider(),
    )
    try:
        with pytest.raises(McpResourceError):
            _call(service, "get_prior", *_challenge_fields())
    finally:
        object.__setattr__(PriorDirectiveKind.EXPLORE, "_name_", "EXPLORE")
        object.__setattr__(PriorDirectiveKind.EXPLORE, "_value_", "explore")
    assert PriorDirectiveKind.EXPLORE.name == "EXPLORE"
    assert PriorDirectiveKind.EXPLORE.value == "explore"


def test_scaffold_challenge_binding_precedes_later_fields(tmp_path: Path) -> None:
    _, scaffold, _ = _publications()
    mismatched = PublishedScaffold(
        "1.0",
        scaffold.scaffold_ref,
        _strategy(challenge_id="other", parameters={"later": "x" * 72}),
        scaffold.informed_by_prior,
        True,
    )
    service, *_ = _service(
        tmp_path,
        limits=_mcp_limits(max_response_string_utf8_bytes=71),
        scaffold_provider=_ScaffoldProvider(mismatched),
    )
    with pytest.raises(McpIntegrationError):
        _call(service, "get_mock_scaffold", *_challenge_fields())

    missing_binding = PublishedScaffold(
        "1.0",
        scaffold.scaffold_ref,
        {"x" * 72: None},
        scaffold.informed_by_prior,
        True,
    )
    service, *_ = _service(
        tmp_path / "missing-after-resource",
        limits=_mcp_limits(max_response_string_utf8_bytes=71),
        scaffold_provider=_ScaffoldProvider(missing_binding),
    )
    with pytest.raises(McpResourceError):
        _call(service, "get_mock_scaffold", *_challenge_fields())


def test_scaffold_selector_detachment_topology_and_exact_a2_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _, _, _, prior_provider, scaffold_provider, _ = _service(tmp_path)
    observed: list[object] = []
    canonical = service_module.dry_validate

    def recording(value: object) -> ValidationResult:
        observed.append(value)
        return canonical(value)

    monkeypatch.setattr(service_module, "dry_validate", recording)
    response = _call(
        service,
        "get_mock_scaffold",
        *_challenge_fields(),
        ("scaffold_id", "starter"),
    )
    assert type(response) is PublishedScaffold
    assert len(scaffold_provider.calls) == 1
    assert not prior_provider.calls
    assert observed == [response.strategy]
    assert observed[0] is not response.strategy
    assert response.strategy is not scaffold_provider.value.strategy
    parameters = response.strategy["parameters"]
    assert type(parameters) is dict
    assert parameters["left"] is parameters["right"]
    assert (
        parameters["left"] is not scaffold_provider.value.strategy["parameters"]["left"]
    )


def test_scaffold_a2_mutation_cannot_change_returned_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, *_ = _service(tmp_path)

    def mutating_validation(value: object) -> ValidationResult:
        assert type(value) is dict
        value["backbone"] = "mutated"
        return ValidationResult(True, ())

    monkeypatch.setattr(service_module, "dry_validate", mutating_validation)
    response = _call(service, "get_mock_scaffold", *_challenge_fields())
    assert type(response) is PublishedScaffold
    assert response.strategy["backbone"] == "fno"


def test_scaffold_selector_and_a2_invalid_output_fail_integration(
    tmp_path: Path,
) -> None:
    service, *_ = _service(tmp_path / "selector")
    with pytest.raises(McpIntegrationError):
        _call(
            service,
            "get_mock_scaffold",
            *_challenge_fields(),
            ("scaffold_id", "different"),
        )

    _, scaffold, _ = _publications()
    malformed = PublishedScaffold(
        "1.0",
        scaffold.scaffold_ref,
        _strategy(backbone="unknown"),
        scaffold.informed_by_prior,
        True,
    )
    service, *_ = _service(
        tmp_path / "invalid", scaffold_provider=_ScaffoldProvider(malformed)
    )
    with pytest.raises(McpIntegrationError):
        _call(service, "get_mock_scaffold", *_challenge_fields())


def test_dry_validate_delegates_once_and_reconstructs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, *_ = _service(tmp_path)
    calls: list[object] = []
    canonical = service_module.dry_validate

    def recording(value: object) -> ValidationResult:
        calls.append(value)
        return canonical(value)

    monkeypatch.setattr(service_module, "dry_validate", recording)
    expected = dry_validate({})
    response = _call(service, "dry_validate", ("strategy", {}))
    assert len(calls) == 1
    assert response.validation == expected
    assert response.validation is not expected
    assert response.validation.errors[0] is not expected.errors[0]


@pytest.mark.parametrize(
    ("strategy", "expected_code"),
    (
        pytest.param(None, "strategy.type", id="none-root"),
        pytest.param(False, "strategy.type", id="bool-root"),
        pytest.param(0, "strategy.type", id="int-root"),
        pytest.param(1.25, "strategy.type", id="finite-float-root"),
        pytest.param("not-a-strategy", "strategy.type", id="string-root"),
        pytest.param([], "strategy.type", id="list-root"),
        pytest.param({}, "field.required", id="missing-fields"),
        pytest.param({1: None}, "json.key_type", id="invalid-key"),
        pytest.param(
            {
                "schema_version": "1.0",
                "challenge_id": CHALLENGE_ID,
            },
            "field.required",
            id="partial-missing-fields",
        ),
        pytest.param(
            _strategy(backbone=1),
            "field.type",
            id="invalid-field-value",
        ),
    ),
)
def test_invalid_estimate_preserves_a2_result_and_skips_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    strategy: object,
    expected_code: str,
) -> None:
    canonical = dry_validate
    expected = canonical(strategy)
    calls: list[tuple[object, ValidationResult]] = []

    def recording(value: object) -> ValidationResult:
        result = canonical(value)
        calls.append((value, result))
        return result

    monkeypatch.setattr(service_module, "dry_validate", recording)
    service, _, _, _, _, _, provider = _service(tmp_path)
    response = _call(service, "estimate", *_submission_fields(strategy))

    assert len(calls) == 1
    service_result = calls[0][1]
    assert service_result == expected
    assert response.validation == expected
    assert response.validation is not service_result
    assert response.validation.errors is not service_result.errors
    assert all(
        copied is not original
        for copied, original in zip(
            response.validation.errors,
            service_result.errors,
            strict=True,
        )
    )
    assert response.validation.ok is False
    assert any(issue.code == expected_code for issue in response.validation.errors)
    if type(strategy) is not dict:
        assert expected == ValidationResult(
            False,
            (
                ValidationIssue(
                    "strategy.type",
                    "",
                    "Strategy must be a JSON object.",
                ),
            ),
        )
    assert response.applicable_directives == ()
    assert response.disclaimer == "non_binding_structural_prior_only"
    assert len(provider.calls) == 0


def test_cyclic_estimate_reaches_a2_and_skips_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cycle: dict[str, object] = {}
    cycle["self"] = cycle
    canonical = dry_validate
    expected = canonical(cycle)
    calls: list[tuple[object, ValidationResult]] = []

    def recording(value: object) -> ValidationResult:
        result = canonical(value)
        calls.append((value, result))
        return result

    monkeypatch.setattr(service_module, "dry_validate", recording)
    service, _, _, _, _, _, provider = _service(tmp_path)
    response = _call(service, "estimate", *_submission_fields(cycle))

    assert len(calls) == 1
    service_result = calls[0][1]
    assert service_result == expected
    assert response.validation == expected
    assert response.validation is not service_result
    assert response.validation.errors is not service_result.errors
    assert all(
        copied is not original
        for copied, original in zip(
            response.validation.errors,
            service_result.errors,
            strict=True,
        )
    )
    assert response.validation.ok is False
    assert response.applicable_directives == ()
    assert response.disclaimer == "non_binding_structural_prior_only"
    assert len(provider.calls) == 0


def test_invalid_estimate_meters_a2_errors_before_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    validation = ValidationResult(
        False,
        (
            ValidationIssue("first", "/first", "First issue."),
            ValidationIssue("second", "/second", "Second issue."),
        ),
    )
    monkeypatch.setattr(service_module, "dry_validate", lambda value: validation)
    service, _, _, _, _, _, provider = _service(
        tmp_path,
        limits=_mcp_limits(max_response_sequence_items=1),
    )
    with pytest.raises(McpResourceError):
        _call(service, "estimate", *_submission_fields(_strategy()))
    assert not provider.calls


def test_valid_estimate_calls_provider_once_with_owned_strategy(tmp_path: Path) -> None:
    service, _, _, _, _, _, provider = _service(tmp_path)
    strategy = _strategy()
    response = _call(service, "estimate", *_submission_fields(strategy))
    assert type(response) is StructuralEstimate
    assert len(provider.calls) == 1
    _, prior, captured, validation = provider.calls[0]
    assert captured == strategy and captured is not strategy
    assert validation.ok is True
    assert response.validation == validation and response.validation is not validation
    assert response.applicable_directives == (prior.directives[0],)
    assert response.applicable_directives[0] is not prior.directives[0]


def test_estimate_a2_mutation_cannot_change_provider_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _, _, _, _, _, provider = _service(tmp_path)

    def mutating_validation(value: object) -> ValidationResult:
        assert type(value) is dict
        value["backbone"] = "mutated"
        return ValidationResult(True, ())

    monkeypatch.setattr(service_module, "dry_validate", mutating_validation)
    response = _call(service, "estimate", *_submission_fields(_strategy()))
    assert type(response) is StructuralEstimate
    assert provider.calls[0][2]["backbone"] == "fno"


def test_estimate_provider_must_preserve_validation_identity(tmp_path: Path) -> None:
    service, _, _, _, _, _, provider = _service(tmp_path)
    provider.substitute_validation = True
    with pytest.raises(McpIntegrationError):
        _call(service, "estimate", *_submission_fields(_strategy()))
    assert len(provider.calls) == 1


def test_estimate_directive_subset_binds_before_later_fields(tmp_path: Path) -> None:
    class WrongKindProvider:
        def estimate(
            self,
            challenge_key: ChallengeKey,
            prior: PublishedPrior,
            strategy: dict[str, object],
            validation: ValidationResult,
        ) -> StructuralEstimate:
            del strategy
            return StructuralEstimate(
                "1.0",
                challenge_key,
                prior.prior_ref,
                validation,
                (
                    PriorDirective(
                        PriorDirectiveKind.AVOID,
                        "x" * 72,
                        (),
                    ),
                ),
                "non_binding_structural_prior_only",
            )

    service, *_ = _service(
        tmp_path,
        limits=_mcp_limits(max_response_string_utf8_bytes=71),
        estimate_provider=WrongKindProvider(),
    )
    with pytest.raises(McpIntegrationError):
        _call(service, "estimate", *_submission_fields(_strategy()))


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    (
        ("ok", McpIntegrationError),
        ("errors", McpResourceError),
    ),
)
def test_estimate_validation_snapshot_uses_progressive_precedence(
    tmp_path: Path,
    mutation: str,
    expected_error: type[Exception],
) -> None:
    class MutatingValidationProvider:
        def estimate(
            self,
            challenge_key: ChallengeKey,
            prior: PublishedPrior,
            strategy: dict[str, object],
            validation: ValidationResult,
        ) -> StructuralEstimate:
            del strategy
            if mutation == "ok":
                object.__setattr__(validation, "ok", False)
                directives = prior.directives * 2
            else:
                object.__setattr__(
                    validation,
                    "errors",
                    (
                        ValidationIssue("first", "/first", "First issue."),
                        ValidationIssue("second", "/second", "Second issue."),
                    ),
                )
                directives = ()
            return _forge(
                StructuralEstimate,
                schema_version="1.0",
                challenge_key=challenge_key,
                prior_ref=prior.prior_ref,
                validation=validation,
                applicable_directives=directives,
                disclaimer="non_binding_structural_prior_only",
            )  # type: ignore[return-value]

    service, *_ = _service(
        tmp_path,
        limits=_mcp_limits(max_response_sequence_items=1),
        estimate_provider=MutatingValidationProvider(),
    )
    with pytest.raises(expected_error):
        _call(service, "estimate", *_submission_fields(_strategy()))


@pytest.mark.parametrize("mutation", ("prior", "validation"))
def test_estimate_provider_cannot_mutate_trusted_snapshots(
    tmp_path: Path, mutation: str
) -> None:
    class MutatingProvider:
        def estimate(
            self,
            challenge_key: ChallengeKey,
            prior: PublishedPrior,
            strategy: dict[str, object],
            validation: ValidationResult,
        ) -> StructuralEstimate:
            del strategy
            if mutation == "prior":
                object.__setattr__(prior.prior_ref, "prior_id", "mutated_prior")
            else:
                object.__setattr__(validation, "ok", False)
            return StructuralEstimate(
                "1.0",
                challenge_key,
                prior.prior_ref,
                validation,
                (),
                "non_binding_structural_prior_only",
            )

    service, *_ = _service(tmp_path, estimate_provider=MutatingProvider())
    with pytest.raises(McpIntegrationError):
        _call(service, "estimate", *_submission_fields(_strategy()))


def test_estimate_provider_cannot_mutate_directive_enum_name(tmp_path: Path) -> None:
    class MutatingProvider:
        def estimate(
            self,
            challenge_key: ChallengeKey,
            prior: PublishedPrior,
            strategy: dict[str, object],
            validation: ValidationResult,
        ) -> StructuralEstimate:
            del strategy
            object.__setattr__(prior.directives[0].kind, "_name_", "CORRUPTED")
            return StructuralEstimate(
                "1.0",
                challenge_key,
                prior.prior_ref,
                validation,
                (),
                "non_binding_structural_prior_only",
            )

    service, *_ = _service(tmp_path, estimate_provider=MutatingProvider())
    try:
        with pytest.raises(McpIntegrationError):
            _call(service, "estimate", *_submission_fields(_strategy()))
    finally:
        object.__setattr__(PriorDirectiveKind.EXPLORE, "_name_", "EXPLORE")
    assert PriorDirectiveKind.EXPLORE.name == "EXPLORE"


def test_submit_preserves_a7_rejected_received_and_duplicate_behavior(
    tmp_path: Path,
) -> None:
    service, *_ = _service(tmp_path)
    rejected = _call(service, "submit", *_submission_fields({}))
    assert type(rejected) is SubmitReceipt
    assert rejected.status.state is SubmissionState.REJECTED

    strategy = _strategy()
    first = _call(service, "submit", *_submission_fields(strategy))
    second = _call(service, "submit", *_submission_fields(strategy))
    assert first.status.state is SubmissionState.RECEIVED
    assert second.status.state is SubmissionState.RECEIVED
    assert second.status.submission_id.value == first.status.submission_id.value


@pytest.mark.parametrize(
    ("owner_error", "public_error"),
    (
        (SubmissionRequestError(), McpRequestError),
        (SubmissionResourceError(), McpResourceError),
    ),
)
def test_submit_maps_canonical_owner_boundary_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    owner_error: Exception,
    public_error: type[Exception],
) -> None:
    service, *_ = _service(tmp_path)

    def fail(*args: object) -> SubmissionId:
        del args
        raise owner_error

    monkeypatch.setattr(SubmissionService, "submit", fail)
    with pytest.raises(public_error) as raised:
        _call(service, "submit", *_submission_fields(_strategy()))
    assert raised.value.__cause__ is None


@pytest.mark.parametrize(
    "owner_error",
    (
        SubmissionRequestError(),
        SubmissionResourceError(),
        SubmissionNotFoundError(),
        SubmissionAuthorizationError(),
    ),
)
def test_post_submit_status_failure_is_integration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    owner_error: Exception,
) -> None:
    service, *_ = _service(tmp_path)

    def fail(*args: object) -> SubmissionStatusView:
        del args
        raise owner_error

    monkeypatch.setattr(SubmissionService, "get_status", fail)
    with pytest.raises(McpIntegrationError) as raised:
        _call(service, "submit", *_submission_fields(_strategy()))
    assert raised.value.__cause__ is None


def test_post_submit_status_projection_capacity_is_integration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, *_ = _service(
        tmp_path,
        limits=_mcp_limits(max_response_string_utf8_bytes=36),
    )

    def oversized_status(
        self: SubmissionService,
        submission_id: SubmissionId,
        requester: RequesterIdentity,
    ) -> SubmissionStatusView:
        del self, requester
        object.__setattr__(submission_id, "value", "x" * 37)
        return _forge(
            SubmissionStatusView,
            submission_id=submission_id,
            state=SubmissionState.RECEIVED,
        )

    monkeypatch.setattr(SubmissionService, "get_status", oversized_status)
    with pytest.raises(McpIntegrationError) as raised:
        _call(service, "submit", *_submission_fields(_strategy()))
    assert raised.value.__cause__ is None


def test_submit_binds_receipt_to_pre_status_submission_id_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, *_ = _service(tmp_path)
    submitted_values: list[str] = []

    def substitute_id(
        self: SubmissionService,
        submission_id: SubmissionId,
        requester: RequesterIdentity,
    ) -> SubmissionStatusView:
        del self, requester
        submitted_values.append(submission_id.value)
        object.__setattr__(submission_id, "value", FIXED_SUBMISSION_ID)
        return SubmissionStatusView(submission_id, SubmissionState.RECEIVED)

    monkeypatch.setattr(SubmissionService, "get_status", substitute_id)
    with pytest.raises(McpIntegrationError):
        _call(service, "submit", *_submission_fields(_strategy()))
    assert len(submitted_values) == 1
    assert submitted_values[0] != FIXED_SUBMISSION_ID


def test_submit_response_preflight_precedes_a7_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _, _, _, *_ = _service(
        tmp_path,
        limits=_mcp_limits(max_total_response_value_nodes=5),
    )
    calls = 0
    original = SubmissionService.submit

    def recording(self: SubmissionService, *args: object) -> SubmissionId:
        nonlocal calls
        calls += 1
        return original(self, *args)  # type: ignore[arg-type]

    monkeypatch.setattr(SubmissionService, "submit", recording)
    with pytest.raises(McpResourceError):
        _call(service, "submit", *_submission_fields(_strategy()))
    assert calls == 0


@pytest.mark.parametrize("dimension", ("string", "total"))
def test_submit_preflights_all_maximum_receipt_string_bounds(
    tmp_path: Path, dimension: str
) -> None:
    override = (
        {"max_response_string_utf8_bytes": 35}
        if dimension == "string"
        else {"max_total_response_utf8_bytes": 53}
    )
    service, *_ = _service(tmp_path, limits=_mcp_limits(**override))
    with pytest.raises(McpResourceError):
        _call(service, "submit", *_submission_fields(_strategy()))


def test_poll_gate_precedes_lookup_and_requires_exact_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = _Gate()
    service, *_ = _service(tmp_path, gate=gate)
    calls = 0
    original = SubmissionService.get_status

    def recording(
        self: SubmissionService,
        submission_id: SubmissionId,
        requester: RequesterIdentity,
    ) -> SubmissionStatusView:
        nonlocal calls
        calls += 1
        return original(self, submission_id, requester)

    monkeypatch.setattr(SubmissionService, "get_status", recording)
    gate.result = False
    with pytest.raises(McpIntegrationError):
        _call(
            service,
            "get_submission_result",
            ("submission_id", FIXED_SUBMISSION_ID),
        )
    assert calls == 0
    assert len(gate.calls) == 1
    assert gate.calls[0][0] is not REQUESTER
    assert gate.calls[0][0] == REQUESTER


def test_query_budget_error_is_fresh_and_subclasses_fail_integration(
    tmp_path: Path,
) -> None:
    gate = _Gate()
    service, *_ = _service(tmp_path / "exact", gate=gate)
    original = McpQueryBudgetError()
    gate.failure = original
    with pytest.raises(McpQueryBudgetError) as raised:
        _call(
            service,
            "get_submission_result",
            ("submission_id", FIXED_SUBMISSION_ID),
        )
    assert raised.value is not original
    assert raised.value.__cause__ is None

    class BudgetSubclass(McpQueryBudgetError):
        pass

    gate = _Gate()
    service, *_ = _service(tmp_path / "subclass", gate=gate)
    gate.failure = BudgetSubclass()
    with pytest.raises(McpIntegrationError):
        _call(
            service,
            "get_submission_result",
            ("submission_id", FIXED_SUBMISSION_ID),
        )


@pytest.mark.parametrize(
    ("attribute", "corrupted", "restored"),
    (
        ("_value_", "corrupted", "get_submission_result"),
        ("_name_", "CORRUPTED", "GET_SUBMISSION_RESULT"),
    ),
)
def test_query_gate_cannot_mutate_exported_tool_singleton(
    tmp_path: Path,
    attribute: str,
    corrupted: str,
    restored: str,
) -> None:
    class MutatingGate(_Gate):
        def consume(self, requester: RequesterIdentity, tool: McpTool) -> None:
            del requester
            object.__setattr__(tool, attribute, corrupted)

    service, *_ = _service(tmp_path, gate=MutatingGate())
    try:
        with pytest.raises(McpIntegrationError):
            _call(
                service,
                "get_submission_result",
                ("submission_id", FIXED_SUBMISSION_ID),
            )
    finally:
        object.__setattr__(McpTool.GET_SUBMISSION_RESULT, attribute, restored)
    assert McpTool.GET_SUBMISSION_RESULT.name == "GET_SUBMISSION_RESULT"
    assert McpTool.GET_SUBMISSION_RESULT.value == "get_submission_result"


@pytest.mark.parametrize("state", tuple(SubmissionState))
def test_poll_covers_every_state_and_reads_card_only_when_published(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    state: SubmissionState,
) -> None:
    service, _, _, gate, *_ = _service(tmp_path)
    submission_id = SubmissionId(FIXED_SUBMISSION_ID)
    status = SubmissionStatusView(submission_id, state)
    card = _card()
    order: list[str] = []

    def get_status(
        self: SubmissionService,
        supplied_id: SubmissionId,
        requester: RequesterIdentity,
    ) -> SubmissionStatusView:
        del self, requester
        order.append("status")
        assert supplied_id == submission_id
        return status

    def read_published(
        self: SubmissionService,
        supplied_id: SubmissionId,
        requester: RequesterIdentity,
    ) -> EvaluationCard:
        del self, requester
        order.append("card")
        assert supplied_id == submission_id
        return card

    monkeypatch.setattr(SubmissionService, "get_status", get_status)
    monkeypatch.setattr(SubmissionService, "read_published", read_published)
    result = _call(
        service,
        "get_submission_result",
        ("submission_id", FIXED_SUBMISSION_ID),
    )
    assert type(result) is SubmissionResult
    assert result.status.state is state
    assert order == (
        ["status", "card"] if state is SubmissionState.PUBLISHED else ["status"]
    )
    assert result.card is (card if state is SubmissionState.PUBLISHED else None)
    assert len(gate.calls) == 1


def test_poll_rejects_missing_or_cross_bound_published_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, *_ = _service(tmp_path)
    submission_id = SubmissionId(FIXED_SUBMISSION_ID)
    status = SubmissionStatusView(submission_id, SubmissionState.PUBLISHED)

    def get_status(*args: object) -> SubmissionStatusView:
        del args
        return status

    monkeypatch.setattr(SubmissionService, "get_status", get_status)
    monkeypatch.setattr(SubmissionService, "read_published", lambda *args: None)
    with pytest.raises(McpIntegrationError):
        _call(
            service,
            "get_submission_result",
            ("submission_id", FIXED_SUBMISSION_ID),
        )

    mismatched = dataclasses.replace(
        _card(),
        result_id="123e4567-e89b-42d3-a456-426614174001",
    )
    monkeypatch.setattr(
        SubmissionService,
        "read_published",
        lambda *args: mismatched,
    )
    bounded_service, *_ = _service(
        tmp_path / "bounded",
        limits=_mcp_limits(max_total_response_value_nodes=9),
    )
    with pytest.raises(McpIntegrationError):
        _call(
            bounded_service,
            "get_submission_result",
            ("submission_id", FIXED_SUBMISSION_ID),
        )

    mutable_status = SubmissionStatusView(
        submission_id,
        SubmissionState.PUBLISHED,
    )

    def get_mutable_status(*args: object) -> SubmissionStatusView:
        del args
        return mutable_status

    returned_card = _card()

    def mutate_status(*args: object) -> EvaluationCard:
        del args
        object.__setattr__(mutable_status, "state", SubmissionState.RECEIVED)
        return returned_card

    monkeypatch.setattr(SubmissionService, "get_status", get_mutable_status)
    monkeypatch.setattr(SubmissionService, "read_published", mutate_status)
    snapshot_service, *_ = _service(
        tmp_path / "mutated-status",
    )
    result = _call(
        snapshot_service,
        "get_submission_result",
        ("submission_id", FIXED_SUBMISSION_ID),
    )
    assert result.status.state is SubmissionState.PUBLISHED
    assert result.card is returned_card

    object.__setattr__(mutable_status, "state", SubmissionState.PUBLISHED)

    def mutate_status_without_card(*args: object) -> None:
        del args
        object.__setattr__(mutable_status, "state", SubmissionState.RECEIVED)

    monkeypatch.setattr(
        SubmissionService,
        "read_published",
        mutate_status_without_card,
    )
    with pytest.raises(McpIntegrationError):
        _call(
            snapshot_service,
            "get_submission_result",
            ("submission_id", FIXED_SUBMISSION_ID),
        )


@pytest.mark.parametrize(
    ("attribute", "corrupted", "restored"),
    (
        ("_value_", "corrupted", "PUBLISHED"),
        ("_name_", "CORRUPTED", "PUBLISHED"),
    ),
)
def test_poll_revalidates_status_enum_before_projecting_card(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    attribute: str,
    corrupted: str,
    restored: str,
) -> None:
    status = SubmissionStatusView(
        SubmissionId(FIXED_SUBMISSION_ID),
        SubmissionState.PUBLISHED,
    )
    card = _card()
    card_values = {
        field.name: getattr(card, field.name) for field in dataclasses.fields(card)
    }
    card_values["schema_version"] = "x" * 128
    overlong_card = _forge(EvaluationCard, **card_values)

    monkeypatch.setattr(
        SubmissionService,
        "get_status",
        lambda *args: status,
    )

    def mutate_state(*args: object) -> EvaluationCard:
        del args
        object.__setattr__(SubmissionState.PUBLISHED, attribute, corrupted)
        return overlong_card

    monkeypatch.setattr(SubmissionService, "read_published", mutate_state)
    service, *_ = _service(
        tmp_path,
        limits=_mcp_limits(max_response_string_utf8_bytes=64),
    )
    try:
        with pytest.raises(McpIntegrationError):
            _call(
                service,
                "get_submission_result",
                ("submission_id", FIXED_SUBMISSION_ID),
            )
    finally:
        object.__setattr__(SubmissionState.PUBLISHED, attribute, restored)
    assert SubmissionState.PUBLISHED.name == "PUBLISHED"
    assert SubmissionState.PUBLISHED.value == "PUBLISHED"


def test_card_declared_field_semantics_precede_later_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    card = _card()
    values = {
        field.name: getattr(card, field.name) for field in dataclasses.fields(card)
    }
    values["overall_score"] = None
    values["gate_results"] = card.gate_results * 2
    malformed = _forge(EvaluationCard, **values)
    status = SubmissionStatusView(
        SubmissionId(FIXED_SUBMISSION_ID),
        SubmissionState.PUBLISHED,
    )

    def get_status(*args: object) -> SubmissionStatusView:
        del args
        return status

    def read_published(*args: object) -> EvaluationCard:
        del args
        return malformed  # type: ignore[return-value]

    monkeypatch.setattr(SubmissionService, "get_status", get_status)
    monkeypatch.setattr(SubmissionService, "read_published", read_published)
    service, *_ = _service(
        tmp_path,
        limits=_mcp_limits(max_response_sequence_items=1),
    )
    with pytest.raises(McpIntegrationError):
        _call(
            service,
            "get_submission_result",
            ("submission_id", FIXED_SUBMISSION_ID),
        )


def test_poll_collapses_not_found_and_wrong_requester(tmp_path: Path) -> None:
    service, *_ = _service(tmp_path)
    with pytest.raises(McpSubmissionUnavailableError) as missing:
        _call(
            service,
            "get_submission_result",
            ("submission_id", FIXED_SUBMISSION_ID),
        )
    receipt = _call(service, "submit", *_submission_fields(_strategy()))
    with pytest.raises(McpSubmissionUnavailableError) as denied:
        _call(
            service,
            "get_submission_result",
            ("submission_id", receipt.status.submission_id.value),
            requester=OTHER_REQUESTER,
        )
    assert type(missing.value) is type(denied.value)
    assert missing.value.args == denied.value.args


def test_poll_canonical_owner_errors_are_not_publicly_distinguished(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, *_ = _service(tmp_path)
    failures = (SubmissionNotFoundError(), SubmissionAuthorizationError())
    public: list[tuple[str, tuple[object, ...]]] = []
    for failure in failures:

        def fail(*args: object, failure: BaseException = failure) -> object:
            del args
            raise failure

        monkeypatch.setattr(SubmissionService, "get_status", fail)
        with pytest.raises(McpSubmissionUnavailableError) as raised:
            _call(
                service,
                "get_submission_result",
                ("submission_id", FIXED_SUBMISSION_ID),
            )
        public.append((raised.value.code, raised.value.args))
    assert public[0] == public[1]


@pytest.mark.parametrize(
    ("owner_error", "public_error"),
    (
        (SubmissionRequestError(), McpRequestError),
        (SubmissionResourceError(), McpResourceError),
    ),
)
def test_poll_maps_canonical_owner_boundary_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    owner_error: Exception,
    public_error: type[Exception],
) -> None:
    service, *_ = _service(tmp_path)

    def fail(*args: object) -> SubmissionStatusView:
        del args
        raise owner_error

    monkeypatch.setattr(SubmissionService, "get_status", fail)
    with pytest.raises(public_error) as raised:
        _call(
            service,
            "get_submission_result",
            ("submission_id", FIXED_SUBMISSION_ID),
        )
    assert raised.value.__cause__ is None


def test_static_source_string_accepts_only_bounded_exact_forms() -> None:
    literal = ast.parse('"literal"', mode="eval").body
    recursive = ast.parse('"__" + ("im" + "port__")', mode="eval").body
    multiplied = ast.parse('"im" * 2', mode="eval").body
    called = ast.parse('str("import__")', mode="eval").body

    assert _static_source_string(literal) == "literal"
    assert _static_source_string(recursive) == "__import__"
    assert _static_source_string(ast.Constant(value=_StringSubclass("literal"))) is None
    assert _static_source_string(ast.Constant(value=1)) is None
    assert _static_source_string(multiplied) is None
    assert _static_source_string(called) is None


@pytest.mark.parametrize(
    ("source", "expected_violation"),
    (
        pytest.param(
            'globals()["__" + "import__"]',
            "subscript:__import__",
            id="computed-import-subscript",
        ),
        pytest.param(
            'globals()["import_" + "module"]',
            "subscript:import_module",
            id="computed-import-module-subscript",
        ),
        pytest.param(
            'loader = globals()["__" + "import__"]',
            "subscript:__import__",
            id="assignment-binding",
        ),
        pytest.param(
            'getattr(__builtins__, "__" + "import__")',
            "getattr:__import__",
            id="computed-import-getattr",
        ),
        pytest.param(
            'getattr(__builtins__, "import_" + "module")',
            "getattr:import_module",
            id="computed-import-module-getattr",
        ),
        pytest.param(
            'vars(__builtins__)["__" + "import__"]',
            "subscript:__import__",
            id="vars-builtins-subscript",
        ),
        pytest.param(
            "eval(\"__import__('forbidden')\")",
            "name:eval",
            id="eval",
        ),
        pytest.param(
            'exec("import forbidden")',
            "name:exec",
            id="exec",
        ),
        pytest.param(
            'compile("import forbidden", "<string>", "exec")',
            "name:compile",
            id="compile",
        ),
        pytest.param(
            '__import__("forbidden")',
            "name:__import__",
            id="direct-import-name",
        ),
        pytest.param(
            'import_module("forbidden")',
            "name:import_module",
            id="direct-import-module-name",
        ),
        pytest.param(
            'builtins.__import__("forbidden")',
            "attribute:__import__",
            id="import-attribute",
        ),
        pytest.param(
            'importlib.import_module("forbidden")',
            "attribute:import_module",
            id="import-module-attribute",
        ),
        pytest.param("locals()", "name:locals", id="locals"),
    ),
)
def test_source_runtime_escape_policy_rejects_prohibited_syntax(
    source: str,
    expected_violation: str,
) -> None:
    violations = _source_runtime_escape_violations(ast.parse(source))
    assert expected_violation in {violation for _, violation in violations}


@pytest.mark.parametrize(
    "source",
    (
        pytest.param(
            'mapping["ordinary_" + "key"]',
            id="ordinary-computed-key",
        ),
        pytest.param(
            'object.__getattribute__(value, "field")',
            id="intentional-object-getattribute",
        ),
    ),
)
def test_source_runtime_escape_policy_allows_safe_controls(source: str) -> None:
    assert _source_runtime_escape_violations(ast.parse(source)) == ()


def test_source_dependency_and_owner_call_guards() -> None:
    mcp_root = REPOSITORY_ROOT / "carbon" / "mcp"
    files = tuple(sorted(mcp_root.rglob("*.py")))
    assert tuple(path.relative_to(mcp_root).as_posix() for path in files) == (
        "__init__.py",
        "model.py",
        "providers.py",
        "service.py",
    )

    ImportRecord = tuple[str, str, int, str | None, str, str | None]

    def expected_from(
        filename: str,
        level: int,
        module: str,
        names: tuple[str, ...],
    ) -> tuple[ImportRecord, ...]:
        return tuple((filename, "from", level, module, name, None) for name in names)

    model_names = (
        "ChallengeInfo",
        "DryValidateRequest",
        "DryValidateResponse",
        "EstimateRequest",
        "GetChallengeInfoRequest",
        "GetMockScaffoldRequest",
        "GetPriorRequest",
        "GetSubmissionResultRequest",
        "McpCall",
        "McpChallengeUnavailableError",
        "McpField",
        "McpIntegrationError",
        "McpQueryBudgetError",
        "McpRequestError",
        "McpResourceError",
        "McpResourceLimits",
        "McpSubmissionUnavailableError",
        "McpTool",
        "McpToolUnavailableError",
        "PriorDirective",
        "PriorDirectiveKind",
        "PriorRef",
        "PublishedPrior",
        "PublishedScaffold",
        "ScaffoldRef",
        "StructuralEstimate",
        "SubmissionResult",
        "SubmitReceipt",
        "SubmitRequest",
    )
    provider_names = (
        "EstimateProvider",
        "PriorProvider",
        "QueryBudgetGate",
        "ScaffoldProvider",
    )
    owner_symbol_allowlists = {
        "carbon.cards.model": frozenset(
            {
                "EvaluationCard",
                "EvaluationComponentScores",
                "EvaluationGateResult",
            }
        ),
        "carbon.fees": frozenset(
            {
                "RequesterIdentity",
                "SubmissionAuthorizationError",
                "SubmissionId",
                "SubmissionNotFoundError",
                "SubmissionRequestError",
                "SubmissionResourceError",
                "SubmissionService",
                "SubmissionState",
                "SubmissionStatusView",
            }
        ),
        "carbon.registry": frozenset(
            {
                "ChallengeKey",
                "ChallengeRecord",
                "ChallengeRegistry",
                "LiveEligibility",
                "RegistryError",
                "is_sha256_digest",
                "validate_canonical_identifier",
                "validate_version",
            }
        ),
        "carbon.schema": frozenset(
            {
                "ValidationIssue",
                "ValidationResult",
                "dry_validate",
            }
        ),
    }
    standard_library_allowlist = frozenset(
        {
            ("from", 0, "__future__", "annotations"),
            ("from", 0, "dataclasses", "dataclass"),
            ("from", 0, "enum", "Enum"),
            ("import", 0, None, "math"),
            ("import", 0, None, "threading"),
            ("from", 0, "typing", "Protocol"),
        }
    )
    expected_imports = (
        *expected_from("__init__.py", 1, "model", model_names),
        *expected_from("__init__.py", 1, "providers", provider_names),
        *expected_from("__init__.py", 1, "service", ("McpService",)),
        *expected_from("model.py", 0, "__future__", ("annotations",)),
        *expected_from("model.py", 0, "dataclasses", ("dataclass",)),
        *expected_from("model.py", 0, "enum", ("Enum",)),
        *expected_from(
            "model.py",
            0,
            "carbon.cards.model",
            ("EvaluationCard",),
        ),
        *expected_from(
            "model.py",
            0,
            "carbon.fees",
            (
                "SubmissionId",
                "SubmissionRequestError",
                "SubmissionState",
                "SubmissionStatusView",
            ),
        ),
        *expected_from(
            "model.py",
            0,
            "carbon.registry",
            (
                "ChallengeKey",
                "is_sha256_digest",
                "validate_canonical_identifier",
                "validate_version",
            ),
        ),
        *expected_from(
            "model.py",
            0,
            "carbon.schema",
            ("ValidationIssue", "ValidationResult"),
        ),
        *expected_from("providers.py", 0, "__future__", ("annotations",)),
        *expected_from("providers.py", 0, "typing", ("Protocol",)),
        *expected_from(
            "providers.py",
            0,
            "carbon.fees",
            ("RequesterIdentity",),
        ),
        *expected_from(
            "providers.py",
            0,
            "carbon.registry",
            ("ChallengeKey",),
        ),
        *expected_from(
            "providers.py",
            0,
            "carbon.schema",
            ("ValidationResult",),
        ),
        *expected_from(
            "providers.py",
            1,
            "model",
            (
                "McpTool",
                "PublishedPrior",
                "PublishedScaffold",
                "StructuralEstimate",
            ),
        ),
        *expected_from("service.py", 0, "__future__", ("annotations",)),
        ("service.py", "import", 0, None, "math", None),
        ("service.py", "import", 0, None, "threading", None),
        *expected_from(
            "service.py",
            0,
            "carbon.cards.model",
            (
                "EvaluationCard",
                "EvaluationComponentScores",
                "EvaluationGateResult",
            ),
        ),
        *expected_from(
            "service.py",
            0,
            "carbon.fees",
            (
                "RequesterIdentity",
                "SubmissionAuthorizationError",
                "SubmissionId",
                "SubmissionNotFoundError",
                "SubmissionRequestError",
                "SubmissionResourceError",
                "SubmissionService",
                "SubmissionState",
                "SubmissionStatusView",
            ),
        ),
        *expected_from(
            "service.py",
            0,
            "carbon.registry",
            (
                "ChallengeKey",
                "ChallengeRecord",
                "ChallengeRegistry",
                "LiveEligibility",
                "RegistryError",
                "is_sha256_digest",
                "validate_canonical_identifier",
                "validate_version",
            ),
        ),
        *expected_from(
            "service.py",
            0,
            "carbon.schema",
            ("ValidationIssue", "ValidationResult", "dry_validate"),
        ),
        *expected_from("service.py", 1, "model", model_names),
        *expected_from("service.py", 1, "providers", provider_names),
    )

    imports: list[ImportRecord] = []
    absolute_modules: set[tuple[str, str]] = set()
    attributes: set[str] = set()
    runtime_escape_violations: list[tuple[str, int, str]] = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        runtime_escape_violations.extend(
            (path.name, line, violation)
            for line, violation in _source_runtime_escape_violations(tree)
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(
                        (path.name, "import", 0, None, alias.name, alias.asname)
                    )
                    absolute_modules.add((path.name, alias.name))
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imports.append(
                        (
                            path.name,
                            "from",
                            node.level,
                            node.module,
                            alias.name,
                            alias.asname,
                        )
                    )
                    if node.level == 0 and node.module is not None:
                        absolute_modules.add((path.name, node.module))
            elif isinstance(node, ast.Attribute):
                attributes.add(node.attr)

    forbidden_prefixes = (
        "carbon.seeding",
        "carbon.scoring",
        "carbon.traineval",
        "carbon.cards.store",
        "carbon.fees.store",
        "carbon.registry.store",
        "carbon.leaderboard",
        "carbon.logging_utils",
        "carbon.chain",
        "carbon.audit",
        "carbon.landscape",
        "carbon.miner",
        "carbon.training",
        "carbon.backbones",
        "carbon.emission",
        "legacy",
        "poc",
        "neurons",
        "bittensor",
        "torch",
        "jax",
        "numpy",
        "pydantic",
        "fastapi",
        "flask",
        "mcp",
    )
    forbidden_imports = tuple(
        (filename, imported)
        for filename, imported in sorted(absolute_modules)
        for prefix in forbidden_prefixes
        if imported == prefix or imported.startswith(f"{prefix}.")
    )
    assert not forbidden_imports
    assert tuple(imports) == expected_imports
    assert all(name != "*" and asname is None for *_, name, asname in imports)
    assert not runtime_escape_violations

    allowed_relative_modules = frozenset({"model", "providers", "service"})
    for _, kind, level, module, name, _ in imports:
        if level:
            assert kind == "from"
            assert level == 1
            assert module in allowed_relative_modules
        elif module is not None and module.startswith("carbon."):
            assert kind == "from"
            assert module in owner_symbol_allowlists
            assert name in owner_symbol_allowlists[module]
        else:
            assert (kind, level, module, name) in standard_library_allowlist

    assert (
        not {
            "scan",
            "mark_validated",
            "admit_fixture",
            "admit_production",
            "start_fixture_attempt",
            "start_production_attempt",
            "cancel",
            "complete_and_publish",
        }
        & attributes
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in files)
    for prohibited in (
        "MockContext",
        "ScoreInput",
        "InternalResult",
        "light_compare",
        "light_train",
        "list_my_submissions",
    ):
        assert prohibited not in source


def test_installed_outside_tree_isolated_import(tmp_path: Path) -> None:
    script = f"""
import pathlib
import sys
import carbon.mcp
assert carbon.mcp.__all__ == {PUBLIC_EXPORTS!r}
assert pathlib.Path(carbon.mcp.__file__).resolve().is_file()
blocked = (
    'bittensor', 'torch', 'jax', 'numpy', 'pydantic', 'fastapi', 'flask', 'mcp',
    'carbon.traineval', 'carbon.leaderboard', 'carbon.logging_utils', 'carbon.chain',
)
assert not any(
    name == blocked_name or name.startswith(blocked_name + '.')
    for name in sys.modules
    for blocked_name in blocked
)
print(pathlib.Path(carbon.mcp.__file__).resolve())
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_fresh_wheel_outside_tree_import(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy2(REPOSITORY_ROOT / "pyproject.toml", source / "pyproject.toml")
    shutil.copy2(REPOSITORY_ROOT / "README.md", source / "README.md")
    shutil.copytree(
        REPOSITORY_ROOT / "carbon",
        source / "carbon",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    builder = None
    checked: set[str] = set()
    for candidate in (sys.executable, getattr(sys, "_base_executable", None)):
        if type(candidate) is not str or candidate in checked:
            continue
        checked.add(candidate)
        probe = subprocess.run(
            [candidate, "-I", "-c", "import setuptools, wheel"],
            check=False,
            capture_output=True,
            text=True,
        )
        if probe.returncode == 0:
            builder = candidate
            break
    assert builder is not None
    environment_values = os.environ.copy()
    environment_values.update(
        {
            "PIP_CACHE_DIR": str(tmp_path / "pip-cache"),
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INDEX": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    build = subprocess.run(
        [
            builder,
            "-m",
            "pip",
            "wheel",
            "--no-cache-dir",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheelhouse),
            str(source),
        ],
        env=environment_values,
        check=False,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr
    wheel = next(wheelhouse.glob("carbon-0.9.0-*.whl"))
    environment = tmp_path / "venv"
    create = subprocess.run(
        [sys.executable, "-m", "venv", str(environment)],
        env=environment_values,
        check=False,
        capture_output=True,
        text=True,
    )
    assert create.returncode == 0, create.stderr
    python = environment / "bin" / "python"
    install = subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-index",
            str(wheel),
        ],
        env=environment_values,
        check=False,
        capture_output=True,
        text=True,
    )
    assert install.returncode == 0, install.stderr
    outside = tmp_path / "outside"
    outside.mkdir()
    script = f"""
import importlib.metadata
import pathlib
import sys
import carbon.mcp
assert importlib.metadata.version('carbon') == '0.9.0'
assert carbon.mcp.__all__ == {PUBLIC_EXPORTS!r}
assert {str(source)!r} not in str(pathlib.Path(carbon.mcp.__file__).resolve())
blocked = (
    'bittensor', 'torch', 'jax', 'numpy', 'pydantic', 'fastapi', 'flask', 'mcp',
    'carbon.traineval', 'carbon.leaderboard', 'carbon.logging_utils', 'carbon.chain',
)
assert not any(
    name == blocked_name or name.startswith(blocked_name + '.')
    for name in sys.modules
    for blocked_name in blocked
)
field = carbon.mcp.McpField('strategy', {{}})
assert carbon.mcp.McpCall('1.0', 'dry_validate', (field,)).tool == 'dry_validate'
limits = carbon.mcp.McpResourceLimits(*((1,) * 14))
assert limits.max_concurrent_calls == 1
directive = carbon.mcp.PriorDirective(
    carbon.mcp.PriorDirectiveKind.EXPLORE,
    'backbone',
    ('fno',),
)
assert directive.tokens == ('fno',)
print(pathlib.Path(carbon.mcp.__file__).resolve())
"""
    imported = subprocess.run(
        [str(python), "-I", "-c", script],
        cwd=outside,
        env=environment_values,
        check=False,
        capture_output=True,
        text=True,
    )
    assert imported.returncode == 0, imported.stderr


def test_service_surface_has_no_cache_history_or_store(tmp_path: Path) -> None:
    service, *_ = _service(tmp_path)
    assert type(service).__slots__ == (
        "_estimate_provider",
        "_limits",
        "_permit",
        "_prior_provider",
        "_query_budget_gate",
        "_registry",
        "_scaffold_provider",
        "_submission_service",
    )
    assert not hasattr(service, "__dict__")
    assert not any(
        token in slot
        for slot in type(service).__slots__
        for token in ("cache", "history", "result_store", "request_store")
    )
    assert tuple(inspect.signature(McpService.call).parameters) == (
        "self",
        "call",
        "requester_identity",
    )
