"""Exact public values for the bounded Wave-A MCP control plane."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from carbon.cards.model import EvaluationCard
from carbon.fees import (
    SubmissionId,
    SubmissionRequestError,
    SubmissionState,
    SubmissionStatusView,
)
from carbon.registry import (
    ChallengeKey,
    is_sha256_digest,
    validate_canonical_identifier,
    validate_version,
)
from carbon.schema import ValidationIssue, ValidationResult

_SCHEMA_VERSION = "1.0"
_ESTIMATE_DISCLAIMER = "non_binding_structural_prior_only"
_UINT64_MAX = (1 << 64) - 1


def _reject_state(value: object) -> None:
    raise TypeError(f"{type(value).__name__} does not support generic serialization")


def _reject_reduce(value: object, protocol: int) -> object:
    del protocol
    raise TypeError(f"{type(value).__name__} does not support generic serialization")


class _NoSerialization:
    __slots__ = ()

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


class _FixedLiteral:
    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def __get__(self, instance: object, owner: type[object]) -> str:
        del instance, owner
        return self._value

    def __set__(self, instance: object, value: object) -> None:
        del instance, value
        raise AttributeError("MCP error payload is read-only")


def _set_error_attribute(value: BaseException, name: str, item: object) -> None:
    if name in {
        "__cause__",
        "__context__",
        "__suppress_context__",
        "__traceback__",
    }:
        BaseException.__setattr__(value, name, item)
        return
    raise AttributeError("MCP error payload is read-only")


class McpRequestError(ValueError):
    """Stable failure for an invalid public MCP request."""

    __slots__ = ()
    code = _FixedLiteral("mcp.request.invalid")
    message = _FixedLiteral("MCP request is invalid.")

    def __init__(self) -> None:
        ValueError.__init__(self, self.message)

    __setattr__ = _set_error_attribute

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


class McpResourceError(RuntimeError):
    """Stable failure for an exceeded MCP resource limit."""

    __slots__ = ()
    code = _FixedLiteral("mcp.resource_limit_exceeded")
    message = _FixedLiteral("MCP resource limit was exceeded.")

    def __init__(self) -> None:
        RuntimeError.__init__(self, self.message)

    __setattr__ = _set_error_attribute

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


class McpToolUnavailableError(LookupError):
    """Stable failure for an unavailable Wave-A tool."""

    __slots__ = ()
    code = _FixedLiteral("mcp.tool_unavailable")
    message = _FixedLiteral("MCP tool is unavailable.")

    def __init__(self) -> None:
        LookupError.__init__(self, self.message)

    __setattr__ = _set_error_attribute

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


class McpChallengeUnavailableError(LookupError):
    """Stable failure for an unavailable Challenge."""

    __slots__ = ()
    code = _FixedLiteral("mcp.challenge_unavailable")
    message = _FixedLiteral("Challenge is unavailable.")

    def __init__(self) -> None:
        LookupError.__init__(self, self.message)

    __setattr__ = _set_error_attribute

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


class McpSubmissionUnavailableError(LookupError):
    """Stable failure for an unavailable requester-bound submission."""

    __slots__ = ()
    code = _FixedLiteral("mcp.submission_unavailable")
    message = _FixedLiteral("Submission is unavailable.")

    def __init__(self) -> None:
        LookupError.__init__(self, self.message)

    __setattr__ = _set_error_attribute

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


class McpQueryBudgetError(RuntimeError):
    """Stable failure for an exhausted MCP polling budget."""

    __slots__ = ()
    code = _FixedLiteral("mcp.query_budget_exceeded")
    message = _FixedLiteral("MCP query budget was exceeded.")

    def __init__(self) -> None:
        RuntimeError.__init__(self, self.message)

    __setattr__ = _set_error_attribute

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


class McpIntegrationError(RuntimeError):
    """Stable failure for a trusted MCP integration seam."""

    __slots__ = ()
    code = _FixedLiteral("mcp.integration_failure")
    message = _FixedLiteral("MCP integration failed.")

    def __init__(self) -> None:
        RuntimeError.__init__(self, self.message)

    __setattr__ = _set_error_attribute

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


class McpTool(str, Enum):
    """The exact closed Wave-A tool vocabulary."""

    GET_CHALLENGE_INFO = "get_challenge_info"
    GET_PRIOR = "get_prior"
    GET_MOCK_SCAFFOLD = "get_mock_scaffold"
    DRY_VALIDATE = "dry_validate"
    ESTIMATE = "estimate"
    SUBMIT = "submit"
    GET_SUBMISSION_RESULT = "get_submission_result"


class PriorDirectiveKind(str, Enum):
    """The exact closed prior-directive vocabulary."""

    STRUCTURAL_STEER = "structural_steer"
    AVOID = "avoid"
    EXPLORE = "explore"
    NOT_INCLUDED = "not_included"


def _is_canonical_directive_kind(value: object) -> bool:
    expected = (
        (
            PriorDirectiveKind.STRUCTURAL_STEER,
            "STRUCTURAL_STEER",
            "structural_steer",
        ),
        (PriorDirectiveKind.AVOID, "AVOID", "avoid"),
        (PriorDirectiveKind.EXPLORE, "EXPLORE", "explore"),
        (PriorDirectiveKind.NOT_INCLUDED, "NOT_INCLUDED", "not_included"),
    )
    for member, name, literal in expected:
        if value is not member:
            continue
        try:
            current_name = object.__getattribute__(member, "name")
            current_value = object.__getattribute__(member, "value")
        except AttributeError:
            return False
        return (
            type(current_name) is str
            and current_name == name
            and type(current_value) is str
            and current_value == literal
        )
    return False


@dataclass(frozen=True, slots=True)
class McpField(_NoSerialization):
    """One raw ordered call field; validation belongs to :class:`McpService`."""

    name: str
    value: object


@dataclass(frozen=True, slots=True)
class McpCall(_NoSerialization):
    """A raw call envelope whose constructor deliberately performs no checks."""

    schema_version: str
    tool: str
    fields: tuple[McpField, ...]


@dataclass(frozen=True, slots=True, repr=False)
class McpResourceLimits(_NoSerialization):
    """Mandatory finite resource policy for one MCP service."""

    max_call_fields: int
    max_total_request_value_nodes: int
    max_request_object_members: int
    max_request_list_items: int
    max_request_string_utf8_bytes: int
    max_request_object_key_utf8_bytes: int
    max_request_integer_bits: int
    max_total_request_utf8_bytes: int
    max_total_response_value_nodes: int
    max_response_sequence_items: int
    max_response_string_utf8_bytes: int
    max_response_integer_bits: int
    max_total_response_utf8_bytes: int
    max_concurrent_calls: int

    def __post_init__(self) -> None:
        if type(self) is not McpResourceLimits:
            raise McpRequestError()
        values = (
            self.max_call_fields,
            self.max_total_request_value_nodes,
            self.max_request_object_members,
            self.max_request_list_items,
            self.max_request_string_utf8_bytes,
            self.max_request_object_key_utf8_bytes,
            self.max_request_integer_bits,
            self.max_total_request_utf8_bytes,
            self.max_total_response_value_nodes,
            self.max_response_sequence_items,
            self.max_response_string_utf8_bytes,
            self.max_response_integer_bits,
            self.max_total_response_utf8_bytes,
            self.max_concurrent_calls,
        )
        if not all(type(value) is int and 0 < value <= _UINT64_MAX for value in values):
            raise McpRequestError()


def _copy_challenge_key(value: object, error: type[Exception]) -> ChallengeKey:
    if type(value) is not ChallengeKey:
        raise error()
    try:
        challenge_id = object.__getattribute__(value, "challenge_id")
    except AttributeError:
        raise error() from None
    owned_challenge_id = _canonical(challenge_id, "challenge_id", error)
    try:
        version = object.__getattribute__(value, "version")
    except AttributeError:
        raise error() from None
    owned_version = _version(version, error)
    try:
        return ChallengeKey(owned_challenge_id, owned_version)
    except (TypeError, ValueError):
        raise error() from None


def _copy_submission_id(value: object, error: type[Exception]) -> SubmissionId:
    if type(value) is not SubmissionId:
        raise error()
    try:
        return SubmissionId(value.value)
    except (AttributeError, SubmissionRequestError, TypeError, ValueError):
        raise error() from None


_SUBMISSION_STATE_LITERALS = (
    (SubmissionState.RECEIVED, "RECEIVED"),
    (SubmissionState.VALIDATED, "VALIDATED"),
    (SubmissionState.QUEUED, "QUEUED"),
    (SubmissionState.RUNNING, "RUNNING"),
    (SubmissionState.SCORED, "SCORED"),
    (SubmissionState.PUBLISHED, "PUBLISHED"),
    (SubmissionState.REJECTED, "REJECTED"),
    (SubmissionState.FAILED_INFRA, "FAILED_INFRA"),
    (SubmissionState.FAILED_STRATEGY, "FAILED_STRATEGY"),
    (SubmissionState.CANCELLED, "CANCELLED"),
)


def _canonical_submission_state(
    value: object, error: type[Exception]
) -> SubmissionState:
    if type(value) is not SubmissionState:
        raise error()
    for member, literal in _SUBMISSION_STATE_LITERALS:
        if value is not member:
            continue
        try:
            current_name = object.__getattribute__(member, "name")
            current_value = object.__getattribute__(member, "value")
        except AttributeError:
            raise error() from None
        if (
            type(current_name) is str
            and current_name == literal
            and type(current_value) is str
            and current_value == literal
        ):
            return member
        raise error()
    raise error()


def _copy_submission_status(
    value: object, error: type[Exception]
) -> SubmissionStatusView:
    if type(value) is not SubmissionStatusView:
        raise error()
    try:
        submission_id = object.__getattribute__(value, "submission_id")
    except AttributeError:
        raise error() from None
    owned_id = _copy_submission_id(submission_id, error)
    try:
        state = object.__getattribute__(value, "state")
    except AttributeError:
        raise error() from None
    owned_state = _canonical_submission_state(state, error)
    try:
        return SubmissionStatusView(owned_id, owned_state)
    except (AttributeError, SubmissionRequestError, TypeError, ValueError):
        raise error() from None


def _canonical(value: object, field_name: str, error: type[Exception]) -> str:
    try:
        return validate_canonical_identifier(value, field_name)
    except (TypeError, ValueError):
        raise error() from None


def _version(value: object, error: type[Exception]) -> str:
    try:
        return validate_version(value)
    except (TypeError, ValueError):
        raise error() from None


def _directive_parts(
    value: object,
    error: type[Exception],
) -> tuple[PriorDirectiveKind, str, tuple[str, ...]]:
    if type(value) is not PriorDirective:
        raise error()
    try:
        kind = object.__getattribute__(value, "kind")
    except AttributeError:
        raise error() from None
    if type(kind) is not PriorDirectiveKind or not _is_canonical_directive_kind(kind):
        raise error()
    try:
        subject = object.__getattribute__(value, "subject")
    except AttributeError:
        raise error() from None
    owned_subject = _canonical(subject, "directive subject", error)
    try:
        tokens = object.__getattribute__(value, "tokens")
    except AttributeError:
        raise error() from None
    if type(tokens) is not tuple:
        raise error()
    for index in range(tuple.__len__(tokens)):
        token = tuple.__getitem__(tokens, index)
        _canonical(token, "directive token", error)
    return kind, owned_subject, tokens


def _owned_validation(
    value: object,
    error: type[Exception],
) -> ValidationResult:
    if type(value) is not ValidationResult:
        raise error()
    try:
        ok = object.__getattribute__(value, "ok")
    except AttributeError:
        raise error() from None
    if type(ok) is not bool:
        raise error()
    try:
        errors = object.__getattribute__(value, "errors")
    except AttributeError:
        raise error() from None
    if type(errors) is not tuple:
        raise error()
    owned_errors: list[ValidationIssue] = []
    for index in range(tuple.__len__(errors)):
        issue = tuple.__getitem__(errors, index)
        if type(issue) is not ValidationIssue:
            raise error()
        try:
            code = object.__getattribute__(issue, "code")
            path = object.__getattribute__(issue, "path")
            message = object.__getattribute__(issue, "message")
        except AttributeError:
            raise error() from None
        if type(code) is not str or type(path) is not str or type(message) is not str:
            raise error()
        owned_errors.append(ValidationIssue(code, path, message))
    if ok is bool(owned_errors):
        raise error()
    return ValidationResult(ok, tuple(owned_errors))


def _validate_card(value: object, error: type[Exception]) -> None:
    if type(value) is not EvaluationCard:
        raise error()
    try:
        schema_version = object.__getattribute__(value, "schema_version")
        result_id = object.__getattribute__(value, "result_id")
        status = object.__getattribute__(value, "status")
        scoring_pack_hash = object.__getattribute__(value, "scoring_pack_hash")
        overall_score = object.__getattribute__(value, "overall_score")
        component_scores = object.__getattribute__(value, "component_scores")
        gate_results = object.__getattribute__(value, "gate_results")
        failure_tags = object.__getattribute__(value, "failure_tags")
        fixture_origin = object.__getattribute__(value, "fixture_origin")
        eligible_for_emission = object.__getattribute__(
            value,
            "eligible_for_emission",
        )
        public_diagnostics = object.__getattribute__(value, "public_diagnostics")
        disclosure_tier = object.__getattribute__(value, "disclosure_tier")
        EvaluationCard(
            schema_version,
            result_id,
            status,
            scoring_pack_hash,
            overall_score,
            component_scores,
            gate_results,
            failure_tags,
            fixture_origin,
            eligible_for_emission,
            public_diagnostics,
            disclosure_tier,
        )
    except (AttributeError, TypeError, ValueError):
        raise error() from None


@dataclass(frozen=True, slots=True)
class GetChallengeInfoRequest(_NoSerialization):
    challenge_key: ChallengeKey

    def __post_init__(self) -> None:
        if type(self) is not GetChallengeInfoRequest:
            raise McpRequestError()
        object.__setattr__(
            self,
            "challenge_key",
            _copy_challenge_key(self.challenge_key, McpRequestError),
        )


@dataclass(frozen=True, slots=True)
class GetPriorRequest(_NoSerialization):
    challenge_key: ChallengeKey

    def __post_init__(self) -> None:
        if type(self) is not GetPriorRequest:
            raise McpRequestError()
        object.__setattr__(
            self,
            "challenge_key",
            _copy_challenge_key(self.challenge_key, McpRequestError),
        )


@dataclass(frozen=True, slots=True)
class GetMockScaffoldRequest(_NoSerialization):
    challenge_key: ChallengeKey
    scaffold_id: str | None

    def __post_init__(self) -> None:
        if type(self) is not GetMockScaffoldRequest:
            raise McpRequestError()
        object.__setattr__(
            self,
            "challenge_key",
            _copy_challenge_key(self.challenge_key, McpRequestError),
        )
        if self.scaffold_id is not None:
            object.__setattr__(
                self,
                "scaffold_id",
                _canonical(self.scaffold_id, "scaffold_id", McpRequestError),
            )


@dataclass(frozen=True, slots=True)
class DryValidateRequest(_NoSerialization):
    strategy: object

    def __post_init__(self) -> None:
        if type(self) is not DryValidateRequest:
            raise McpRequestError()


@dataclass(frozen=True, slots=True)
class EstimateRequest(_NoSerialization):
    challenge_key: ChallengeKey
    strategy: object

    def __post_init__(self) -> None:
        if type(self) is not EstimateRequest:
            raise McpRequestError()
        object.__setattr__(
            self,
            "challenge_key",
            _copy_challenge_key(self.challenge_key, McpRequestError),
        )


@dataclass(frozen=True, slots=True)
class SubmitRequest(_NoSerialization):
    challenge_key: ChallengeKey
    strategy: object

    def __post_init__(self) -> None:
        if type(self) is not SubmitRequest:
            raise McpRequestError()
        object.__setattr__(
            self,
            "challenge_key",
            _copy_challenge_key(self.challenge_key, McpRequestError),
        )


@dataclass(frozen=True, slots=True)
class GetSubmissionResultRequest(_NoSerialization):
    submission_id: SubmissionId

    def __post_init__(self) -> None:
        if type(self) is not GetSubmissionResultRequest:
            raise McpRequestError()
        object.__setattr__(
            self,
            "submission_id",
            _copy_submission_id(self.submission_id, McpRequestError),
        )


@dataclass(frozen=True, slots=True)
class PriorRef(_NoSerialization):
    challenge_key: ChallengeKey
    prior_id: str
    prior_version: str
    content_hash: str

    def __post_init__(self) -> None:
        if type(self) is not PriorRef:
            raise McpIntegrationError()
        object.__setattr__(
            self,
            "challenge_key",
            _copy_challenge_key(self.challenge_key, McpIntegrationError),
        )
        object.__setattr__(
            self,
            "prior_id",
            _canonical(self.prior_id, "prior_id", McpIntegrationError),
        )
        object.__setattr__(
            self, "prior_version", _version(self.prior_version, McpIntegrationError)
        )
        if type(self.content_hash) is not str or not is_sha256_digest(
            self.content_hash
        ):
            raise McpIntegrationError()


@dataclass(frozen=True, slots=True)
class ScaffoldRef(_NoSerialization):
    challenge_key: ChallengeKey
    scaffold_id: str
    scaffold_version: str
    content_hash: str

    def __post_init__(self) -> None:
        if type(self) is not ScaffoldRef:
            raise McpIntegrationError()
        object.__setattr__(
            self,
            "challenge_key",
            _copy_challenge_key(self.challenge_key, McpIntegrationError),
        )
        object.__setattr__(
            self,
            "scaffold_id",
            _canonical(self.scaffold_id, "scaffold_id", McpIntegrationError),
        )
        object.__setattr__(
            self,
            "scaffold_version",
            _version(self.scaffold_version, McpIntegrationError),
        )
        if type(self.content_hash) is not str or not is_sha256_digest(
            self.content_hash
        ):
            raise McpIntegrationError()


def _copy_prior_ref(value: object, error: type[Exception]) -> PriorRef:
    if type(value) is not PriorRef:
        raise error()
    try:
        challenge_key = object.__getattribute__(value, "challenge_key")
    except AttributeError:
        raise error() from None
    owned_challenge = _copy_challenge_key(challenge_key, error)
    try:
        prior_id = object.__getattribute__(value, "prior_id")
    except AttributeError:
        raise error() from None
    owned_prior_id = _canonical(prior_id, "prior_id", error)
    try:
        prior_version = object.__getattribute__(value, "prior_version")
    except AttributeError:
        raise error() from None
    owned_prior_version = _version(prior_version, error)
    try:
        content_hash = object.__getattribute__(value, "content_hash")
    except AttributeError:
        raise error() from None
    if type(content_hash) is not str or not is_sha256_digest(content_hash):
        raise error()
    return PriorRef(
        owned_challenge,
        owned_prior_id,
        owned_prior_version,
        content_hash,
    )


def _copy_scaffold_ref(value: object, error: type[Exception]) -> ScaffoldRef:
    if type(value) is not ScaffoldRef:
        raise error()
    try:
        challenge_key = object.__getattribute__(value, "challenge_key")
    except AttributeError:
        raise error() from None
    owned_challenge = _copy_challenge_key(challenge_key, error)
    try:
        scaffold_id = object.__getattribute__(value, "scaffold_id")
    except AttributeError:
        raise error() from None
    owned_scaffold_id = _canonical(scaffold_id, "scaffold_id", error)
    try:
        scaffold_version = object.__getattribute__(value, "scaffold_version")
    except AttributeError:
        raise error() from None
    owned_scaffold_version = _version(scaffold_version, error)
    try:
        content_hash = object.__getattribute__(value, "content_hash")
    except AttributeError:
        raise error() from None
    if type(content_hash) is not str or not is_sha256_digest(content_hash):
        raise error()
    return ScaffoldRef(
        owned_challenge,
        owned_scaffold_id,
        owned_scaffold_version,
        content_hash,
    )


@dataclass(frozen=True, slots=True)
class PriorDirective(_NoSerialization):
    kind: PriorDirectiveKind
    subject: str
    tokens: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self) is not PriorDirective:
            raise McpIntegrationError()
        kind, subject, tokens = _directive_parts(self, McpIntegrationError)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "subject", subject)
        object.__setattr__(self, "tokens", tokens)


def _unique_directives(value: object) -> bool:
    if type(value) is not tuple:
        raise McpIntegrationError()
    seen: set[tuple[PriorDirectiveKind, str, tuple[str, ...]]] = set()
    for index in range(tuple.__len__(value)):
        key = _directive_parts(
            tuple.__getitem__(value, index),
            McpIntegrationError,
        )
        if key in seen:
            return False
        seen.add(key)
    return True


@dataclass(frozen=True, slots=True)
class PublishedPrior(_NoSerialization):
    schema_version: str
    prior_ref: PriorRef
    directives: tuple[PriorDirective, ...]

    def __post_init__(self) -> None:
        if type(self) is not PublishedPrior:
            raise McpIntegrationError()
        if (
            type(self.schema_version) is not str
            or self.schema_version != _SCHEMA_VERSION
        ):
            raise McpIntegrationError()
        object.__setattr__(
            self,
            "prior_ref",
            _copy_prior_ref(self.prior_ref, McpIntegrationError),
        )
        if not _unique_directives(self.directives):
            raise McpIntegrationError()


@dataclass(frozen=True, slots=True)
class PublishedScaffold(_NoSerialization):
    schema_version: str
    scaffold_ref: ScaffoldRef
    strategy: dict[str, object]
    informed_by_prior: PriorRef | None
    execution_deferred: bool

    def __post_init__(self) -> None:
        if type(self) is not PublishedScaffold:
            raise McpIntegrationError()
        if (
            type(self.schema_version) is not str
            or self.schema_version != _SCHEMA_VERSION
        ):
            raise McpIntegrationError()
        object.__setattr__(
            self,
            "scaffold_ref",
            _copy_scaffold_ref(self.scaffold_ref, McpIntegrationError),
        )
        if type(self.strategy) is not dict:
            raise McpIntegrationError()
        if self.informed_by_prior is not None:
            object.__setattr__(
                self,
                "informed_by_prior",
                _copy_prior_ref(self.informed_by_prior, McpIntegrationError),
            )
        if self.execution_deferred is not True:
            raise McpIntegrationError()


@dataclass(frozen=True, slots=True)
class ChallengeInfo(_NoSerialization):
    schema_version: str
    challenge_key: ChallengeKey
    lifecycle_status: str
    fixture_origin: bool
    effectively_live: bool
    allowed_backbones: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self) is not ChallengeInfo:
            raise McpIntegrationError()
        if (
            type(self.schema_version) is not str
            or self.schema_version != _SCHEMA_VERSION
        ):
            raise McpIntegrationError()
        object.__setattr__(
            self,
            "challenge_key",
            _copy_challenge_key(self.challenge_key, McpIntegrationError),
        )
        if type(self.lifecycle_status) is not str or self.lifecycle_status not in (
            "fixture",
            "live",
        ):
            raise McpIntegrationError()
        if type(self.fixture_origin) is not bool:
            raise McpIntegrationError()
        if type(self.effectively_live) is not bool:
            raise McpIntegrationError()
        if self.lifecycle_status == "fixture" and (
            self.fixture_origin is not True or self.effectively_live is not False
        ):
            raise McpIntegrationError()
        if type(self.allowed_backbones) is not tuple:
            raise McpIntegrationError()
        backbones = tuple(
            _canonical(backbone, "backbone", McpIntegrationError)
            for backbone in self.allowed_backbones
        )
        if len(set(backbones)) != len(backbones):
            raise McpIntegrationError()
        object.__setattr__(self, "allowed_backbones", backbones)


@dataclass(frozen=True, slots=True)
class DryValidateResponse(_NoSerialization):
    schema_version: str
    validation: ValidationResult

    def __post_init__(self) -> None:
        if type(self) is not DryValidateResponse:
            raise McpIntegrationError()
        if (
            type(self.schema_version) is not str
            or self.schema_version != _SCHEMA_VERSION
        ):
            raise McpIntegrationError()
        object.__setattr__(
            self,
            "validation",
            _owned_validation(self.validation, McpIntegrationError),
        )


@dataclass(frozen=True, slots=True)
class StructuralEstimate(_NoSerialization):
    schema_version: str
    challenge_key: ChallengeKey
    prior_ref: PriorRef
    validation: ValidationResult
    applicable_directives: tuple[PriorDirective, ...]
    disclaimer: str

    def __post_init__(self) -> None:
        if type(self) is not StructuralEstimate:
            raise McpIntegrationError()
        if (
            type(self.schema_version) is not str
            or self.schema_version != _SCHEMA_VERSION
        ):
            raise McpIntegrationError()
        object.__setattr__(
            self,
            "challenge_key",
            _copy_challenge_key(self.challenge_key, McpIntegrationError),
        )
        object.__setattr__(
            self,
            "prior_ref",
            _copy_prior_ref(self.prior_ref, McpIntegrationError),
        )
        _owned_validation(self.validation, McpIntegrationError)
        if not _unique_directives(self.applicable_directives):
            raise McpIntegrationError()
        if type(self.disclaimer) is not str or self.disclaimer != _ESTIMATE_DISCLAIMER:
            raise McpIntegrationError()


@dataclass(frozen=True, slots=True)
class SubmitReceipt(_NoSerialization):
    schema_version: str
    status: SubmissionStatusView

    def __post_init__(self) -> None:
        if (
            type(self) is not SubmitReceipt
            or type(self.schema_version) is not str
            or self.schema_version != _SCHEMA_VERSION
            or type(self.status) is not SubmissionStatusView
        ):
            raise McpIntegrationError()
        object.__setattr__(
            self,
            "status",
            _copy_submission_status(self.status, McpIntegrationError),
        )


@dataclass(frozen=True, slots=True)
class SubmissionResult(_NoSerialization):
    schema_version: str
    status: SubmissionStatusView
    card: EvaluationCard | None

    def __post_init__(self) -> None:
        if type(self) is not SubmissionResult:
            raise McpIntegrationError()
        if (
            type(self.schema_version) is not str
            or self.schema_version != _SCHEMA_VERSION
        ):
            raise McpIntegrationError()
        if type(self.status) is not SubmissionStatusView:
            raise McpIntegrationError()
        owned_status = _copy_submission_status(self.status, McpIntegrationError)
        if self.card is not None and type(self.card) is not EvaluationCard:
            raise McpIntegrationError()
        if self.card is not None:
            _validate_card(self.card, McpIntegrationError)
        if (
            owned_status.state is SubmissionState.PUBLISHED
            and type(self.card) is not EvaluationCard
        ) or (
            owned_status.state is not SubmissionState.PUBLISHED
            and self.card is not None
        ):
            raise McpIntegrationError()
        if self.card is not None:
            try:
                result_id = self.card.result_id
            except AttributeError:
                raise McpIntegrationError() from None
            if (
                type(result_id) is not str
                or result_id != owned_status.submission_id.value
            ):
                raise McpIntegrationError()
        object.__setattr__(self, "status", owned_status)
