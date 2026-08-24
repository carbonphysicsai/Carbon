# ruff: noqa: BLE001
"""Bounded in-process dispatch for the Wave-A MCP control plane.

Trusted provider and owner seams deliberately collapse every ordinary exception.
"""

from __future__ import annotations

import math
import threading

from carbon.cards.model import (
    EvaluationCard,
    EvaluationComponentScores,
    EvaluationGateResult,
)
from carbon.fees import (
    RequesterIdentity,
    SubmissionAuthorizationError,
    SubmissionId,
    SubmissionNotFoundError,
    SubmissionRequestError,
    SubmissionResourceError,
    SubmissionService,
    SubmissionState,
    SubmissionStatusView,
)
from carbon.registry import (
    ChallengeKey,
    ChallengeRecord,
    ChallengeRegistry,
    LiveEligibility,
    RegistryError,
    is_sha256_digest,
    validate_canonical_identifier,
    validate_version,
)
from carbon.schema import ValidationIssue, ValidationResult, dry_validate

from .model import (
    ChallengeInfo,
    DryValidateRequest,
    DryValidateResponse,
    EstimateRequest,
    GetChallengeInfoRequest,
    GetMockScaffoldRequest,
    GetPriorRequest,
    GetSubmissionResultRequest,
    McpCall,
    McpChallengeUnavailableError,
    McpField,
    McpIntegrationError,
    McpQueryBudgetError,
    McpRequestError,
    McpResourceError,
    McpResourceLimits,
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
    SubmitRequest,
)
from .providers import (
    EstimateProvider,
    PriorProvider,
    QueryBudgetGate,
    ScaffoldProvider,
)

_SCHEMA_VERSION = "1.0"
_ESTIMATE_DISCLAIMER = "non_binding_structural_prior_only"
_MAX_RECEIPT_NODES = 6
_MAX_RECEIPT_STRING_BYTES = 36
_MAX_RECEIPT_TOTAL_UTF8_BYTES = 54

_PUBLIC_ERRORS = (
    McpRequestError,
    McpResourceError,
    McpToolUnavailableError,
    McpChallengeUnavailableError,
    McpSubmissionUnavailableError,
    McpQueryBudgetError,
    McpIntegrationError,
)

_TOOL_BY_NAME = {
    "get_challenge_info": McpTool.GET_CHALLENGE_INFO,
    "get_prior": McpTool.GET_PRIOR,
    "get_mock_scaffold": McpTool.GET_MOCK_SCAFFOLD,
    "dry_validate": McpTool.DRY_VALIDATE,
    "estimate": McpTool.ESTIMATE,
    "submit": McpTool.SUBMIT,
    "get_submission_result": McpTool.GET_SUBMISSION_RESULT,
}
_FIELD_SCHEMAS = {
    McpTool.GET_CHALLENGE_INFO: (
        ("challenge_id", "challenge_version"),
        (),
    ),
    McpTool.GET_PRIOR: (("challenge_id", "challenge_version"), ()),
    McpTool.GET_MOCK_SCAFFOLD: (
        ("challenge_id", "challenge_version"),
        ("scaffold_id",),
    ),
    McpTool.DRY_VALIDATE: (("strategy",), ()),
    McpTool.ESTIMATE: (
        ("challenge_id", "challenge_version", "strategy"),
        (),
    ),
    McpTool.SUBMIT: (
        ("challenge_id", "challenge_version", "strategy"),
        (),
    ),
    McpTool.GET_SUBMISSION_RESULT: (("submission_id",), ()),
}

_DIRECTIVE_KIND_LITERALS = (
    (
        PriorDirectiveKind.STRUCTURAL_STEER,
        "STRUCTURAL_STEER",
        "structural_steer",
    ),
    (PriorDirectiveKind.AVOID, "AVOID", "avoid"),
    (PriorDirectiveKind.EXPLORE, "EXPLORE", "explore"),
    (PriorDirectiveKind.NOT_INCLUDED, "NOT_INCLUDED", "not_included"),
)
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


def _utf8_width(character: str) -> int:
    codepoint = ord(character)
    if codepoint <= 0x7F:
        return 1
    if codepoint <= 0x7FF:
        return 2
    if 0xD800 <= codepoint <= 0xDFFF:
        return 1
    if codepoint <= 0xFFFF:
        return 3
    return 4


class _RequestMeter:
    __slots__ = ("limits", "nodes", "utf8_bytes")

    def __init__(self, limits: McpResourceLimits) -> None:
        self.limits = limits
        self.nodes = 0
        self.utf8_bytes = 0

    def node(self) -> None:
        if self.nodes >= self.limits.max_total_request_value_nodes:
            raise McpResourceError()
        self.nodes += 1

    def reserve_nodes(self, count: int) -> None:
        if count > self.limits.max_total_request_value_nodes - self.nodes:
            raise McpResourceError()
        self.nodes += count

    def integer(self, value: int) -> None:
        if int.bit_length(value) > self.limits.max_request_integer_bits:
            raise McpResourceError()

    def text(self, value: str, *, key: bool = False) -> None:
        width = 0
        invalid = False
        for character in value:
            character_width = _utf8_width(character)
            if character_width > self.limits.max_request_string_utf8_bytes - width:
                raise McpResourceError()
            if key and character_width > (
                self.limits.max_request_object_key_utf8_bytes - width
            ):
                raise McpResourceError()
            if (
                character_width
                > self.limits.max_total_request_utf8_bytes - self.utf8_bytes
            ):
                raise McpResourceError()
            width += character_width
            self.utf8_bytes += character_width
            if 0xD800 <= ord(character) <= 0xDFFF:
                invalid = True
        if invalid:
            raise McpRequestError()


class _ResponseMeter:
    __slots__ = ("limits", "nodes", "utf8_bytes")

    def __init__(self, limits: McpResourceLimits) -> None:
        self.limits = limits
        self.nodes = 0
        self.utf8_bytes = 0

    def node(self) -> None:
        if self.nodes >= self.limits.max_total_response_value_nodes:
            raise McpResourceError()
        self.nodes += 1

    field = node
    item = node

    def reserve_dict_values(self, count: int) -> None:
        if count > self.limits.max_total_response_value_nodes - self.nodes:
            raise McpResourceError()
        self.nodes += count

    def sequence(self, value: object) -> int:
        if type(value) not in (tuple, list):
            raise McpIntegrationError()
        length = len(value)
        if length > self.limits.max_response_sequence_items:
            raise McpResourceError()
        self.reserve_dict_values(length)
        return length

    def integer(self, value: int) -> None:
        if int.bit_length(value) > self.limits.max_response_integer_bits:
            raise McpResourceError()

    def text(self, value: object) -> str:
        if type(value) is not str:
            raise McpIntegrationError()
        width = 0
        invalid = False
        for character in value:
            character_width = _utf8_width(character)
            if character_width > self.limits.max_response_string_utf8_bytes - width:
                raise McpResourceError()
            if (
                character_width
                > self.limits.max_total_response_utf8_bytes - self.utf8_bytes
            ):
                raise McpResourceError()
            width += character_width
            self.utf8_bytes += character_width
            if 0xD800 <= ord(character) <= 0xDFFF:
                invalid = True
        if invalid:
            raise McpIntegrationError()
        return value


def _assign(parent: object, key: object, value: object) -> None:
    if type(parent) is list:
        list.__setitem__(parent, key, value)  # type: ignore[arg-type]
    else:
        dict.__setitem__(parent, key, value)  # type: ignore[arg-type]


def _request_key(value: object, meter: _RequestMeter) -> object:
    value_type = type(value)
    if value is None or value_type is bool:
        return value
    if value_type is int:
        meter.integer(value)
        return value
    if value_type is float:
        if not math.isfinite(value):
            raise McpRequestError()
        return value
    if value_type is str:
        meter.text(value, key=True)
        return value
    raise McpRequestError()


def _capture_request_values(
    entries: tuple[McpField, ...],
    names: tuple[str, ...],
    meter: _RequestMeter,
) -> tuple[object, ...]:
    outputs: list[object] = [None] * len(entries)
    copies: dict[int, tuple[object, object]] = {}
    stack: list[tuple[str, object, object, object]] = []
    for index in range(len(entries) - 1, -1, -1):
        stack.append(("root", (entries[index], names[index]), outputs, index))

    while stack:
        kind, source, parent, key = stack.pop()
        if kind == "root":
            field, expected_name = source  # type: ignore[misc]
            try:
                current_name = field.name
                if type(current_name) is not str or current_name != expected_name:
                    raise McpRequestError()
            except AttributeError:
                raise McpRequestError() from None
            meter.node()
            try:
                field_value = field.value
            except AttributeError:
                raise McpRequestError() from None
            source = field_value
        elif kind == "member":
            member_key, member_value = source  # type: ignore[misc]
            owned_key = _request_key(member_key, meter)
            stack.append(("child", member_value, parent, owned_key))
            continue
        elif kind == "value":
            meter.node()
        source_type = type(source)
        if source is None or source_type is bool:
            _assign(parent, key, source)
            continue
        if source_type is int:
            meter.integer(source)
            _assign(parent, key, source)
            continue
        if source_type is float:
            if not math.isfinite(source):
                raise McpRequestError()
            _assign(parent, key, source)
            continue
        if source_type is str:
            meter.text(source)
            _assign(parent, key, source)
            continue
        if source_type not in (list, dict):
            raise McpRequestError()

        identity = id(source)
        seen = copies.get(identity)
        if seen is not None:
            if seen[0] is not source:
                raise McpRequestError()
            _assign(parent, key, seen[1])
            continue

        if source_type is list:
            length = list.__len__(source)
            if length > meter.limits.max_request_list_items:
                raise McpResourceError()
            meter.reserve_nodes(length)
            try:
                snapshot = [list.__getitem__(source, index) for index in range(length)]
            except (IndexError, RuntimeError):
                raise McpRequestError() from None
            if list.__len__(source) != length:
                raise McpRequestError()
            target: object = [None] * length
            copies[identity] = (source, target)
            _assign(parent, key, target)
            for index in range(length - 1, -1, -1):
                stack.append(("child", snapshot[index], target, index))
            continue

        length = dict.__len__(source)
        if length > meter.limits.max_request_object_members:
            raise McpResourceError()
        meter.reserve_nodes(length)
        try:
            items = list(dict.items(source))
        except RuntimeError:
            raise McpRequestError() from None
        if dict.__len__(source) != length or len(items) != length:
            raise McpRequestError()
        target = {}
        copies[identity] = (source, target)
        _assign(parent, key, target)
        for item in reversed(items):
            stack.append(("member", item, target, None))

    return tuple(outputs)


def _copy_owned_request_graph(value: object, limits: McpResourceLimits) -> object:
    meter = _RequestMeter(limits)
    return _capture_request_values(
        (McpField("strategy", value),),
        ("strategy",),
        meter,
    )[0]


def _copy_limits(value: object) -> McpResourceLimits:
    if type(value) is not McpResourceLimits:
        raise McpRequestError()
    try:
        return McpResourceLimits(
            value.max_call_fields,
            value.max_total_request_value_nodes,
            value.max_request_object_members,
            value.max_request_list_items,
            value.max_request_string_utf8_bytes,
            value.max_request_object_key_utf8_bytes,
            value.max_request_integer_bits,
            value.max_total_request_utf8_bytes,
            value.max_total_response_value_nodes,
            value.max_response_sequence_items,
            value.max_response_string_utf8_bytes,
            value.max_response_integer_bits,
            value.max_total_response_utf8_bytes,
            value.max_concurrent_calls,
        )
    except (AttributeError, TypeError, ValueError):
        raise McpRequestError() from None


def _requester(value: object) -> RequesterIdentity:
    if type(value) is not RequesterIdentity:
        raise McpRequestError()
    try:
        return RequesterIdentity(value.value)
    except Exception:
        raise McpRequestError() from None


def _challenge(value_id: object, value_version: object) -> ChallengeKey:
    if type(value_id) is not str or type(value_version) is not str:
        raise McpRequestError()
    try:
        return ChallengeKey(value_id, value_version)
    except (TypeError, ValueError):
        raise McpRequestError() from None


def _submission_id(value: object) -> SubmissionId:
    if type(value) is not str:
        raise McpRequestError()
    try:
        return SubmissionId(value)
    except Exception:
        raise McpRequestError() from None


def _decode_request(tool: McpTool, fields: dict[str, object]) -> object:
    if tool is McpTool.GET_CHALLENGE_INFO:
        return GetChallengeInfoRequest(
            _challenge(fields["challenge_id"], fields["challenge_version"])
        )
    if tool is McpTool.GET_PRIOR:
        return GetPriorRequest(
            _challenge(fields["challenge_id"], fields["challenge_version"])
        )
    if tool is McpTool.GET_MOCK_SCAFFOLD:
        scaffold_id = fields.get("scaffold_id")
        if "scaffold_id" in fields:
            if type(scaffold_id) is not str:
                raise McpRequestError()
            try:
                validate_canonical_identifier(scaffold_id, "scaffold_id")
            except (TypeError, ValueError):
                raise McpRequestError() from None
        return GetMockScaffoldRequest(
            _challenge(fields["challenge_id"], fields["challenge_version"]),
            scaffold_id,  # type: ignore[arg-type]
        )
    if tool is McpTool.DRY_VALIDATE:
        return DryValidateRequest(fields["strategy"])
    if tool is McpTool.ESTIMATE:
        return EstimateRequest(
            _challenge(fields["challenge_id"], fields["challenge_version"]),
            fields["strategy"],
        )
    if tool is McpTool.SUBMIT:
        return SubmitRequest(
            _challenge(fields["challenge_id"], fields["challenge_version"]),
            fields["strategy"],
        )
    return GetSubmissionResultRequest(_submission_id(fields["submission_id"]))


def _directive_kind_identity(
    value: object,
) -> tuple[PriorDirectiveKind, str, str]:
    if type(value) is not PriorDirectiveKind:
        raise McpIntegrationError()
    for member, name, literal in _DIRECTIVE_KIND_LITERALS:
        if value is member:
            return member, name, literal
    raise McpIntegrationError()


def _directive_kind_literal(value: object) -> str:
    member, name, literal = _directive_kind_identity(value)
    try:
        current_name = object.__getattribute__(member, "name")
        current_value = object.__getattribute__(member, "value")
    except AttributeError:
        raise McpIntegrationError() from None
    if (
        type(current_name) is str
        and current_name == name
        and type(current_value) is str
        and current_value == literal
    ):
        return literal
    raise McpIntegrationError()


def _submission_state_identity(
    value: object,
) -> tuple[SubmissionState, str]:
    if type(value) is not SubmissionState:
        raise McpIntegrationError()
    for member, literal in _SUBMISSION_STATE_LITERALS:
        if value is member:
            return member, literal
    raise McpIntegrationError()


def _directive_key(value: PriorDirective) -> tuple[str, str, tuple[str, ...]]:
    return (_directive_kind_literal(value.kind), value.subject, value.tokens)


def _require_tool_identity(value: object, expected_value: str) -> McpTool:
    if type(value) is not McpTool:
        raise McpIntegrationError()
    try:
        current_name = object.__getattribute__(value, "name")
        current_value = object.__getattribute__(value, "value")
    except AttributeError:
        raise McpIntegrationError() from None
    if (
        type(current_name) is not str
        or current_name != expected_value.upper()
        or type(current_value) is not str
        or current_value != expected_value
    ):
        raise McpIntegrationError()
    return value


class _Projector:
    __slots__ = ("graph_copies", "meter", "token_copies")

    def __init__(self, limits: McpResourceLimits) -> None:
        self.meter = _ResponseMeter(limits)
        self.graph_copies: dict[int, tuple[object, object]] = {}
        self.token_copies: dict[int, tuple[object, tuple[str, ...]]] = {}

    def field_value(self, value: object, name: str) -> object:
        self.meter.field()
        try:
            return object.__getattribute__(value, name)
        except Exception:
            raise McpIntegrationError() from None

    def string(self, value: object) -> str:
        return self.meter.text(value)

    def boolean(self, value: object) -> bool:
        if type(value) is not bool:
            raise McpIntegrationError()
        return value

    def directive_kind(self, value: object) -> tuple[PriorDirectiveKind, str]:
        member, name, literal = _directive_kind_identity(value)
        try:
            raw = object.__getattribute__(member, "value")
        except AttributeError:
            raise McpIntegrationError() from None
        owned = self.string(raw)
        if owned != literal:
            raise McpIntegrationError()
        try:
            current_name = object.__getattribute__(member, "name")
        except AttributeError:
            raise McpIntegrationError() from None
        if type(current_name) is not str or current_name != name:
            raise McpIntegrationError()
        return member, owned

    def submission_state(self, value: object) -> SubmissionState:
        member, literal = _submission_state_identity(value)
        try:
            raw = object.__getattribute__(member, "value")
        except AttributeError:
            raise McpIntegrationError() from None
        owned = self.string(raw)
        if owned != literal:
            raise McpIntegrationError()
        try:
            current_name = object.__getattribute__(member, "name")
        except AttributeError:
            raise McpIntegrationError() from None
        if type(current_name) is not str or current_name != literal:
            raise McpIntegrationError()
        return member

    def finite_float(self, value: object) -> float:
        if type(value) is not float or not math.isfinite(value):
            raise McpIntegrationError()
        return value

    def challenge_key(
        self,
        value: object,
        expected: ChallengeKey | None = None,
    ) -> ChallengeKey:
        if type(value) is not ChallengeKey:
            raise McpIntegrationError()
        challenge_id = self.string(self.field_value(value, "challenge_id"))
        try:
            validate_canonical_identifier(challenge_id, "challenge_id")
        except (TypeError, ValueError):
            raise McpIntegrationError() from None
        if expected is not None and challenge_id != expected.challenge_id:
            raise McpIntegrationError()
        version = self.string(self.field_value(value, "version"))
        try:
            validate_version(version)
        except (TypeError, ValueError):
            raise McpIntegrationError() from None
        if expected is not None and version != expected.version:
            raise McpIntegrationError()
        return ChallengeKey(challenge_id, version)

    def prior_ref(
        self,
        value: object,
        *,
        expected_challenge: ChallengeKey | None = None,
        expected_ref: PriorRef | None = None,
    ) -> PriorRef:
        if type(value) is not PriorRef:
            raise McpIntegrationError()
        expected_key = (
            expected_ref.challenge_key
            if expected_ref is not None
            else expected_challenge
        )
        challenge = self.challenge_key(
            self.field_value(value, "challenge_key"), expected_key
        )
        prior_id = self.string(self.field_value(value, "prior_id"))
        try:
            validate_canonical_identifier(prior_id, "prior_id")
        except (TypeError, ValueError):
            raise McpIntegrationError() from None
        if expected_ref is not None and prior_id != expected_ref.prior_id:
            raise McpIntegrationError()
        prior_version = self.string(self.field_value(value, "prior_version"))
        try:
            validate_version(prior_version)
        except (TypeError, ValueError):
            raise McpIntegrationError() from None
        if expected_ref is not None and prior_version != expected_ref.prior_version:
            raise McpIntegrationError()
        content_hash = self.string(self.field_value(value, "content_hash"))
        if not is_sha256_digest(content_hash):
            raise McpIntegrationError()
        if expected_ref is not None and content_hash != expected_ref.content_hash:
            raise McpIntegrationError()
        return PriorRef(challenge, prior_id, prior_version, content_hash)

    def scaffold_ref(
        self,
        value: object,
        *,
        expected_challenge: ChallengeKey | None = None,
        expected_scaffold_id: str | None = None,
    ) -> ScaffoldRef:
        if type(value) is not ScaffoldRef:
            raise McpIntegrationError()
        challenge = self.challenge_key(
            self.field_value(value, "challenge_key"), expected_challenge
        )
        scaffold_id = self.string(self.field_value(value, "scaffold_id"))
        try:
            validate_canonical_identifier(scaffold_id, "scaffold_id")
        except (TypeError, ValueError):
            raise McpIntegrationError() from None
        if expected_scaffold_id is not None and scaffold_id != expected_scaffold_id:
            raise McpIntegrationError()
        scaffold_version = self.string(self.field_value(value, "scaffold_version"))
        try:
            validate_version(scaffold_version)
        except (TypeError, ValueError):
            raise McpIntegrationError() from None
        content_hash = self.string(self.field_value(value, "content_hash"))
        if not is_sha256_digest(content_hash):
            raise McpIntegrationError()
        return ScaffoldRef(challenge, scaffold_id, scaffold_version, content_hash)

    def directive(self, value: object) -> PriorDirective:
        if type(value) is not PriorDirective:
            raise McpIntegrationError()
        kind, _ = self.directive_kind(self.field_value(value, "kind"))
        subject = self.string(self.field_value(value, "subject"))
        try:
            validate_canonical_identifier(subject, "directive subject")
        except (TypeError, ValueError):
            raise McpIntegrationError() from None
        tokens = self.field_value(value, "tokens")
        if type(tokens) is not tuple:
            raise McpIntegrationError()
        identity = id(tokens)
        seen_tokens = self.token_copies.get(identity)
        if seen_tokens is not None:
            if seen_tokens[0] is not tokens:
                raise McpIntegrationError()
            owned_tokens = seen_tokens[1]
        else:
            self.meter.sequence(tokens)
            copied_tokens: list[str] = []
            for token in tokens:
                copied = self.string(token)
                try:
                    validate_canonical_identifier(copied, "directive token")
                except (TypeError, ValueError):
                    raise McpIntegrationError() from None
                copied_tokens.append(copied)
            owned_tokens = tuple(copied_tokens)
            self.token_copies[identity] = (tokens, owned_tokens)
        return PriorDirective(kind, subject, owned_tokens)

    def applicable_directive(
        self,
        value: object,
        expected: tuple[PriorDirective, ...],
        start_index: int,
    ) -> tuple[PriorDirective, int]:
        if type(value) is not PriorDirective:
            raise McpIntegrationError()
        kind, kind_literal = self.directive_kind(self.field_value(value, "kind"))
        candidates = [
            index
            for index in range(start_index, len(expected))
            if _directive_kind_literal(expected[index].kind) == kind_literal
        ]
        if not candidates:
            raise McpIntegrationError()

        subject = self.string(self.field_value(value, "subject"))
        try:
            validate_canonical_identifier(subject, "directive subject")
        except (TypeError, ValueError):
            raise McpIntegrationError() from None
        candidates = [
            index for index in candidates if expected[index].subject == subject
        ]
        if not candidates:
            raise McpIntegrationError()

        tokens = self.field_value(value, "tokens")
        if type(tokens) is not tuple:
            raise McpIntegrationError()
        identity = id(tokens)
        seen_tokens = self.token_copies.get(identity)
        if seen_tokens is not None:
            if seen_tokens[0] is not tokens:
                raise McpIntegrationError()
            owned_tokens = seen_tokens[1]
            token_count = len(owned_tokens)
        else:
            token_count = self.meter.sequence(tokens)
        candidates = [
            index for index in candidates if len(expected[index].tokens) == token_count
        ]
        if not candidates:
            raise McpIntegrationError()

        copied_tokens: list[str] = []
        token_values = owned_tokens if seen_tokens is not None else tokens
        for token_index, token in enumerate(token_values):
            if seen_tokens is not None:
                copied = token
            else:
                copied = self.string(token)
                try:
                    validate_canonical_identifier(copied, "directive token")
                except (TypeError, ValueError):
                    raise McpIntegrationError() from None
            candidates = [
                index
                for index in candidates
                if expected[index].tokens[token_index] == copied
            ]
            if not candidates:
                raise McpIntegrationError()
            copied_tokens.append(copied)
        if seen_tokens is None:
            owned_tokens = tuple(copied_tokens)
            self.token_copies[identity] = (tokens, owned_tokens)
        return (
            PriorDirective(kind, subject, owned_tokens),
            candidates[0] + 1,
        )

    def validation(
        self,
        value: object,
        expected: ValidationResult | None = None,
    ) -> ValidationResult:
        if type(value) is not ValidationResult:
            raise McpIntegrationError()
        ok = self.boolean(self.field_value(value, "ok"))
        if expected is not None and ok is not expected.ok:
            raise McpIntegrationError()
        errors = self.field_value(value, "errors")
        if type(errors) is not tuple:
            raise McpIntegrationError()
        error_count = self.meter.sequence(errors)
        if expected is not None and error_count != len(expected.errors):
            raise McpIntegrationError()
        if ok is bool(error_count):
            raise McpIntegrationError()
        copied_errors: list[ValidationIssue] = []
        for index, issue in enumerate(errors):
            if type(issue) is not ValidationIssue:
                raise McpIntegrationError()
            code = self.string(self.field_value(issue, "code"))
            if expected is not None and code != expected.errors[index].code:
                raise McpIntegrationError()
            path = self.string(self.field_value(issue, "path"))
            if expected is not None and path != expected.errors[index].path:
                raise McpIntegrationError()
            message = self.string(self.field_value(issue, "message"))
            if expected is not None and message != expected.errors[index].message:
                raise McpIntegrationError()
            copied_errors.append(ValidationIssue(code, path, message))
        return ValidationResult(ok, tuple(copied_errors))

    def submission_id(
        self,
        value: object,
        expected_value: str | None = None,
    ) -> SubmissionId:
        if type(value) is not SubmissionId:
            raise McpIntegrationError()
        raw = self.string(self.field_value(value, "value"))
        try:
            owned = SubmissionId(raw)
        except Exception:
            raise McpIntegrationError() from None
        if expected_value is not None and raw != expected_value:
            raise McpIntegrationError()
        return owned

    def status(
        self,
        value: object,
        expected_submission_id: SubmissionId | None = None,
    ) -> SubmissionStatusView:
        if type(value) is not SubmissionStatusView:
            raise McpIntegrationError()
        expected_value = (
            expected_submission_id.value if expected_submission_id is not None else None
        )
        submission_id = self.submission_id(
            self.field_value(value, "submission_id"), expected_value
        )
        state = self.submission_state(self.field_value(value, "state"))
        try:
            return SubmissionStatusView(submission_id, state)
        except Exception:
            raise McpIntegrationError() from None

    def graph(
        self,
        source: object,
        expected_root_challenge_id: str | None = None,
    ) -> object:
        output: list[object] = [None]
        root_target: object | None = None
        root_challenge_seen = False
        stack: list[tuple[str, object, object, object]] = [("value", source, output, 0)]
        while stack:
            kind, current, parent, key = stack.pop()
            if kind == "root_end":
                if expected_root_challenge_id is not None and not root_challenge_seen:
                    raise McpIntegrationError()
                continue
            if kind == "item":
                stack.append(("value", current, parent, key))
                continue
            if kind == "member":
                member_key, member_value = current  # type: ignore[misc]
                key_type = type(member_key)
                if member_key is None or key_type is bool:
                    owned_key = member_key
                elif key_type is int:
                    self.meter.integer(member_key)
                    owned_key = member_key
                elif key_type is float:
                    if not math.isfinite(member_key):
                        raise McpIntegrationError()
                    owned_key = member_key
                elif key_type is str:
                    owned_key = self.string(member_key)
                else:
                    raise McpIntegrationError()
                if (
                    parent is root_target
                    and type(owned_key) is str
                    and owned_key == "challenge_id"
                    and expected_root_challenge_id is not None
                ):
                    root_challenge_seen = True
                    if type(member_value) is not str:
                        raise McpIntegrationError()
                    owned_value = self.string(member_value)
                    _assign(parent, owned_key, owned_value)
                    if owned_value != expected_root_challenge_id:
                        raise McpIntegrationError()
                    continue
                stack.append(("value", member_value, parent, owned_key))
                continue

            current_type = type(current)
            if current is None or current_type is bool:
                _assign(parent, key, current)
                continue
            if current_type is int:
                self.meter.integer(current)
                _assign(parent, key, current)
                continue
            if current_type is float:
                if not math.isfinite(current):
                    raise McpIntegrationError()
                _assign(parent, key, current)
                continue
            if current_type is str:
                _assign(parent, key, self.string(current))
                continue
            if current_type not in (list, dict):
                raise McpIntegrationError()

            identity = id(current)
            seen = self.graph_copies.get(identity)
            if seen is not None:
                if seen[0] is not current:
                    raise McpIntegrationError()
                _assign(parent, key, seen[1])
                continue

            if current_type is list:
                length = list.__len__(current)
                if length > self.meter.limits.max_response_sequence_items:
                    raise McpResourceError()
                self.meter.reserve_dict_values(length)
                try:
                    snapshot = [
                        list.__getitem__(current, index) for index in range(length)
                    ]
                except (IndexError, RuntimeError):
                    raise McpIntegrationError() from None
                if list.__len__(current) != length:
                    raise McpIntegrationError()
                target: object = [None] * length
                self.graph_copies[identity] = (current, target)
                _assign(parent, key, target)
                for index in range(length - 1, -1, -1):
                    stack.append(("item", snapshot[index], target, index))
                continue

            length = dict.__len__(current)
            self.meter.reserve_dict_values(length)
            try:
                items = list(dict.items(current))
            except RuntimeError:
                raise McpIntegrationError() from None
            if dict.__len__(current) != length or len(items) != length:
                raise McpIntegrationError()
            target = {}
            self.graph_copies[identity] = (current, target)
            if current is source:
                root_target = target
            _assign(parent, key, target)
            if current is source and expected_root_challenge_id is not None:
                stack.append(("root_end", None, target, None))
            for item in reversed(items):
                stack.append(("member", item, target, None))
        return output[0]

    def card(self, value: object, expected_result_id: str) -> EvaluationCard:
        if type(value) is not EvaluationCard:
            raise McpIntegrationError()

        schema = self.string(self.field_value(value, "schema_version"))
        if schema != "1.0":
            raise McpIntegrationError()

        result_id = self.string(self.field_value(value, "result_id"))
        try:
            validate_version(result_id)
        except (TypeError, ValueError):
            raise McpIntegrationError() from None
        if result_id != expected_result_id:
            raise McpIntegrationError()

        status = self.string(self.field_value(value, "status"))
        if status not in (
            "SCORED",
            "MANDATORY_GATE_FAILED",
            "PACK_NOT_READY",
        ):
            raise McpIntegrationError()

        digest = self.string(self.field_value(value, "scoring_pack_hash"))
        if not is_sha256_digest(digest):
            raise McpIntegrationError()

        overall = self.field_value(value, "overall_score")
        if status == "SCORED":
            overall = self.finite_float(overall)
            if not 0.0 <= overall <= 1.0 or (
                overall == 0.0 and math.copysign(1.0, overall) != 1.0
            ):
                raise McpIntegrationError()
        elif status == "MANDATORY_GATE_FAILED":
            overall = self.finite_float(overall)
            if overall != 0.0 or math.copysign(1.0, overall) != 1.0:
                raise McpIntegrationError()
        elif overall is not None:
            raise McpIntegrationError()

        components = self.field_value(value, "component_scores")
        if status == "SCORED":
            if type(components) is not EvaluationComponentScores:
                raise McpIntegrationError()
            for name in ("physics", "robustness", "accuracy"):
                component = self.finite_float(self.field_value(components, name))
                if not 0.0 <= component <= 1.0:
                    raise McpIntegrationError()
        elif components is not None:
            raise McpIntegrationError()

        gates = self.field_value(value, "gate_results")
        if type(gates) is not tuple:
            raise McpIntegrationError()
        gate_count = self.meter.sequence(gates)
        if (status == "PACK_NOT_READY" and gate_count != 0) or (
            status != "PACK_NOT_READY" and gate_count == 0
        ):
            raise McpIntegrationError()
        seen_gate_ids: set[str] = set()
        failed_gate = False
        for gate in gates:
            if type(gate) is not EvaluationGateResult:
                raise McpIntegrationError()
            gate_id = self.string(self.field_value(gate, "gate_id"))
            try:
                validate_canonical_identifier(gate_id, "gate_id")
            except (TypeError, ValueError):
                raise McpIntegrationError() from None
            if gate_id in seen_gate_ids:
                raise McpIntegrationError()
            seen_gate_ids.add(gate_id)
            passed = self.boolean(self.field_value(gate, "passed"))
            failed_gate = failed_gate or not passed
        if status == "MANDATORY_GATE_FAILED" and not failed_gate:
            raise McpIntegrationError()

        tags = self.field_value(value, "failure_tags")
        if type(tags) is not tuple:
            raise McpIntegrationError()
        tag_count = self.meter.sequence(tags)
        expected_tag_count = 1 if status == "MANDATORY_GATE_FAILED" else 0
        if tag_count != expected_tag_count:
            raise McpIntegrationError()
        for tag in tags:
            if self.string(tag) != "mandatory_gate_failed":
                raise McpIntegrationError()

        fixture_origin = self.boolean(self.field_value(value, "fixture_origin"))
        if fixture_origin is not True:
            raise McpIntegrationError()
        emission = self.boolean(self.field_value(value, "eligible_for_emission"))
        if emission is not False:
            raise McpIntegrationError()
        diagnostics = self.field_value(value, "public_diagnostics")
        if type(diagnostics) is not tuple:
            raise McpIntegrationError()
        if self.meter.sequence(diagnostics) != 0:
            raise McpIntegrationError()
        tier = self.string(self.field_value(value, "disclosure_tier"))
        if tier != "phase0_budgeted":
            raise McpIntegrationError()
        return value


def _project_challenge_info(
    challenge: ChallengeKey,
    lifecycle_status: object,
    fixture_origin_value: object,
    effectively_live_value: object,
    allowed_backbones_value: object,
    limits: McpResourceLimits,
) -> ChallengeInfo:
    projector = _Projector(limits)
    projector.meter.node()
    projector.meter.field()
    schema = projector.string(_SCHEMA_VERSION)
    if schema != _SCHEMA_VERSION:
        raise McpIntegrationError()
    projector.meter.field()
    challenge_key = projector.challenge_key(challenge)
    projector.meter.field()
    status = projector.string(lifecycle_status)
    if status not in ("fixture", "live"):
        raise McpIntegrationError()
    projector.meter.field()
    fixture_origin = projector.boolean(fixture_origin_value)
    if status == "fixture" and fixture_origin is not True:
        raise McpIntegrationError()
    projector.meter.field()
    effectively_live = projector.boolean(effectively_live_value)
    if status == "fixture" and effectively_live is not False:
        raise McpIntegrationError()
    projector.meter.field()
    backbones = allowed_backbones_value
    if type(backbones) is not tuple:
        raise McpIntegrationError()
    projector.meter.sequence(backbones)
    copied_backbones: list[str] = []
    seen_backbones: set[str] = set()
    for backbone in backbones:
        copied = projector.string(backbone)
        try:
            validate_canonical_identifier(copied, "backbone")
        except (TypeError, ValueError):
            raise McpIntegrationError() from None
        if copied in seen_backbones:
            raise McpIntegrationError()
        seen_backbones.add(copied)
        copied_backbones.append(copied)
    return ChallengeInfo(
        schema,
        challenge_key,
        status,
        fixture_origin,
        effectively_live,
        tuple(copied_backbones),
    )


def _project_prior(
    value: object,
    limits: McpResourceLimits,
    expected_challenge: ChallengeKey,
) -> PublishedPrior:
    projector = _Projector(limits)
    projector.meter.node()
    if type(value) is not PublishedPrior:
        raise McpIntegrationError()
    schema = projector.string(projector.field_value(value, "schema_version"))
    if schema != _SCHEMA_VERSION:
        raise McpIntegrationError()
    prior_ref = projector.prior_ref(
        projector.field_value(value, "prior_ref"),
        expected_challenge=expected_challenge,
    )
    raw_directives = projector.field_value(value, "directives")
    if type(raw_directives) is not tuple:
        raise McpIntegrationError()
    projector.meter.sequence(raw_directives)
    copied_directives: list[PriorDirective] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for directive in raw_directives:
        copied = projector.directive(directive)
        key = _directive_key(copied)
        if key in seen:
            raise McpIntegrationError()
        seen.add(key)
        copied_directives.append(copied)
    return PublishedPrior(schema, prior_ref, tuple(copied_directives))


def _project_scaffold(
    value: object,
    limits: McpResourceLimits,
    expected_challenge: ChallengeKey,
    expected_scaffold_id: str | None,
) -> PublishedScaffold:
    projector = _Projector(limits)
    projector.meter.node()
    if type(value) is not PublishedScaffold:
        raise McpIntegrationError()
    schema = projector.string(projector.field_value(value, "schema_version"))
    if schema != _SCHEMA_VERSION:
        raise McpIntegrationError()
    scaffold_ref = projector.scaffold_ref(
        projector.field_value(value, "scaffold_ref"),
        expected_challenge=expected_challenge,
        expected_scaffold_id=expected_scaffold_id,
    )
    raw_strategy = projector.field_value(value, "strategy")
    if type(raw_strategy) is not dict:
        raise McpIntegrationError()
    strategy = projector.graph(raw_strategy, expected_challenge.challenge_id)
    informed = projector.field_value(value, "informed_by_prior")
    if informed is not None:
        informed = projector.prior_ref(
            informed,
            expected_challenge=expected_challenge,
        )
    deferred = projector.boolean(projector.field_value(value, "execution_deferred"))
    if deferred is not True:
        raise McpIntegrationError()
    return PublishedScaffold(schema, scaffold_ref, strategy, informed, deferred)


def _project_dry_validation(
    validation: object, limits: McpResourceLimits
) -> DryValidateResponse:
    projector = _Projector(limits)
    projector.meter.node()
    projector.meter.field()
    schema = projector.string(_SCHEMA_VERSION)
    projector.meter.field()
    owned = projector.validation(validation)
    return DryValidateResponse(schema, owned)


def _project_estimate(
    value: object,
    limits: McpResourceLimits,
    expected_challenge: ChallengeKey,
    expected_prior: PublishedPrior,
    expected_validation_identity: ValidationResult,
    expected_validation_snapshot: ValidationResult,
) -> StructuralEstimate:
    projector = _Projector(limits)
    projector.meter.node()
    if type(value) is not StructuralEstimate:
        raise McpIntegrationError()
    schema = projector.string(projector.field_value(value, "schema_version"))
    if schema != _SCHEMA_VERSION:
        raise McpIntegrationError()
    challenge = projector.challenge_key(
        projector.field_value(value, "challenge_key"), expected_challenge
    )
    prior_ref = projector.prior_ref(
        projector.field_value(value, "prior_ref"),
        expected_ref=expected_prior.prior_ref,
    )
    raw_validation = projector.field_value(value, "validation")
    if raw_validation is not expected_validation_identity:
        raise McpIntegrationError()
    validation = projector.validation(raw_validation, expected_validation_snapshot)
    if validation.ok is not True:
        raise McpIntegrationError()
    directives = projector.field_value(value, "applicable_directives")
    if type(directives) is not tuple:
        raise McpIntegrationError()
    projector.meter.sequence(directives)
    copied_directives: list[PriorDirective] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    next_index = 0
    for directive in directives:
        copied, next_index = projector.applicable_directive(
            directive,
            expected_prior.directives,
            next_index,
        )
        key = _directive_key(copied)
        if key in seen:
            raise McpIntegrationError()
        seen.add(key)
        copied_directives.append(copied)
    disclaimer = projector.string(projector.field_value(value, "disclaimer"))
    if disclaimer != _ESTIMATE_DISCLAIMER:
        raise McpIntegrationError()
    return StructuralEstimate(
        schema,
        challenge,
        prior_ref,
        validation,
        tuple(copied_directives),
        disclaimer,
    )


def _project_invalid_estimate(
    challenge: ChallengeKey,
    prior: PublishedPrior,
    validation: ValidationResult,
    limits: McpResourceLimits,
) -> StructuralEstimate:
    projector = _Projector(limits)
    projector.meter.node()
    projector.meter.field()
    schema = projector.string(_SCHEMA_VERSION)
    projector.meter.field()
    owned_challenge = projector.challenge_key(challenge)
    projector.meter.field()
    prior_ref = projector.prior_ref(prior.prior_ref)
    projector.meter.field()
    owned_validation = projector.validation(validation)
    projector.meter.field()
    projector.meter.sequence(())
    projector.meter.field()
    disclaimer = projector.string(_ESTIMATE_DISCLAIMER)
    return StructuralEstimate(
        schema,
        owned_challenge,
        prior_ref,
        owned_validation,
        (),
        disclaimer,
    )


def _project_receipt(
    status: object,
    limits: McpResourceLimits,
    expected_submission_id: SubmissionId,
) -> SubmitReceipt:
    projector = _Projector(limits)
    projector.meter.node()
    projector.meter.field()
    schema = projector.string(_SCHEMA_VERSION)
    projector.meter.field()
    owned_status = projector.status(status, expected_submission_id)
    return SubmitReceipt(schema, owned_status)


def _begin_submission_result(
    status: object,
    limits: McpResourceLimits,
    expected_submission_id: SubmissionId,
) -> tuple[_Projector, str, SubmissionStatusView]:
    projector = _Projector(limits)
    projector.meter.node()
    projector.meter.field()
    schema = projector.string(_SCHEMA_VERSION)
    projector.meter.field()
    owned_status = projector.status(status, expected_submission_id)
    return projector, schema, owned_status


def _finish_submission_result(
    projector: _Projector,
    schema: str,
    owned_status: SubmissionStatusView,
    card: object,
    expected_submission_id: SubmissionId,
) -> SubmissionResult:
    _, state_literal = _submission_state_identity(owned_status.state)
    try:
        current_state_name = object.__getattribute__(owned_status.state, "name")
        current_state_literal = object.__getattribute__(owned_status.state, "value")
    except AttributeError:
        raise McpIntegrationError() from None
    if (
        type(current_state_name) is not str
        or current_state_name != state_literal
        or type(current_state_literal) is not str
        or current_state_literal != state_literal
    ):
        raise McpIntegrationError()
    projector.meter.field()
    if owned_status.state is SubmissionState.PUBLISHED:
        if type(card) is not EvaluationCard:
            raise McpIntegrationError()
        owned_card = projector.card(card, expected_submission_id.value)
    else:
        if card is not None:
            raise McpIntegrationError()
        owned_card = None
    return SubmissionResult(schema, owned_status, owned_card)


class McpService:
    """The sole bounded in-process Wave-A MCP service."""

    __slots__ = (
        "_estimate_provider",
        "_limits",
        "_permit",
        "_prior_provider",
        "_query_budget_gate",
        "_registry",
        "_scaffold_provider",
        "_submission_service",
    )

    def __init__(
        self,
        registry: ChallengeRegistry,
        submission_service: SubmissionService,
        resource_limits: McpResourceLimits,
        query_budget_gate: QueryBudgetGate,
        prior_provider: PriorProvider | None,
        scaffold_provider: ScaffoldProvider | None,
        estimate_provider: EstimateProvider | None,
    ) -> None:
        if type(self) is not McpService:
            raise McpRequestError()
        if (
            type(registry) is not ChallengeRegistry
            or type(submission_service) is not SubmissionService
            or query_budget_gate is None
        ):
            raise McpRequestError()
        limits = _copy_limits(resource_limits)
        self._registry = registry
        self._submission_service = submission_service
        self._limits = limits
        self._query_budget_gate = query_budget_gate
        self._prior_provider = prior_provider
        self._scaffold_provider = scaffold_provider
        self._estimate_provider = estimate_provider
        self._permit = threading.BoundedSemaphore(limits.max_concurrent_calls)

    def __repr__(self) -> str:
        return "<McpService>"

    def call(
        self, call: McpCall, requester_identity: RequesterIdentity
    ) -> (
        ChallengeInfo
        | PublishedPrior
        | PublishedScaffold
        | DryValidateResponse
        | StructuralEstimate
        | SubmitReceipt
        | SubmissionResult
    ):
        if (
            type(call) is not McpCall
            or type(requester_identity) is not RequesterIdentity
        ):
            raise McpRequestError()
        if not self._permit.acquire(blocking=False):
            raise McpResourceError()
        try:
            try:
                tool, request = self._frame_and_decode(call)
                requester = _requester(requester_identity)
                return self._dispatch(tool, request, requester)
            except _PUBLIC_ERRORS as exc:
                if type(exc) in _PUBLIC_ERRORS:
                    raise
                raise McpIntegrationError() from None
            except Exception:
                raise McpIntegrationError() from None
        finally:
            self._permit.release()

    def _frame_and_decode(self, call: McpCall) -> tuple[McpTool, object]:
        try:
            schema_version = call.schema_version
            tool_name = call.tool
            raw_fields = call.fields
        except AttributeError:
            raise McpRequestError() from None
        if (
            type(schema_version) is not str
            or type(tool_name) is not str
            or type(raw_fields) is not tuple
        ):
            raise McpRequestError()
        if len(raw_fields) > self._limits.max_call_fields:
            raise McpResourceError()

        meter = _RequestMeter(self._limits)
        meter.text(schema_version)
        meter.text(tool_name)
        if schema_version != _SCHEMA_VERSION:
            raise McpRequestError()

        names: list[str] = []
        entries: list[McpField] = []
        seen: set[str] = set()
        for field in raw_fields:
            if type(field) is not McpField:
                raise McpRequestError()
            try:
                name = field.name
            except AttributeError:
                raise McpRequestError() from None
            if type(name) is not str:
                raise McpRequestError()
            meter.text(name)
            if name in seen:
                raise McpRequestError()
            seen.add(name)
            names.append(name)
            entries.append(field)

        tool = _TOOL_BY_NAME.get(tool_name)
        if tool is None:
            raise McpToolUnavailableError()
        _require_tool_identity(tool, tool_name)
        required, optional = _FIELD_SCHEMAS[tool]
        allowed = required + optional
        if any(name not in allowed for name in names):
            raise McpRequestError()
        if any(name not in seen for name in required):
            raise McpRequestError()

        owned_values = _capture_request_values(
            tuple(entries),
            tuple(names),
            meter,
        )
        fields = {names[index]: owned_values[index] for index in range(len(names))}
        return tool, _decode_request(tool, fields)

    def _dispatch(
        self, tool: McpTool, request: object, requester: RequesterIdentity
    ) -> (
        ChallengeInfo
        | PublishedPrior
        | PublishedScaffold
        | DryValidateResponse
        | StructuralEstimate
        | SubmitReceipt
        | SubmissionResult
    ):
        if tool is McpTool.GET_CHALLENGE_INFO:
            return self._get_challenge_info(request)
        if tool is McpTool.GET_PRIOR:
            return self._get_prior(request)
        if tool is McpTool.GET_MOCK_SCAFFOLD:
            return self._get_mock_scaffold(request)
        if tool is McpTool.DRY_VALIDATE:
            return self._dry_validate(request)
        if tool is McpTool.ESTIMATE:
            return self._estimate(request)
        if tool is McpTool.SUBMIT:
            return self._submit(request, requester)
        return self._get_submission_result(request, requester)

    def _visible_challenge(
        self, challenge: ChallengeKey
    ) -> tuple[str, bool, tuple[str, ...], bool]:
        try:
            record = self._registry.load(challenge.challenge_id, challenge.version)
        except RegistryError:
            raise McpChallengeUnavailableError() from None
        except Exception:
            raise McpIntegrationError() from None
        if type(record) is not ChallengeRecord:
            raise McpChallengeUnavailableError()
        try:
            record_challenge_id = object.__getattribute__(record, "challenge_id")
            record_version = object.__getattribute__(record, "version")
            lifecycle_status = object.__getattribute__(record, "status")
            fixture_origin = object.__getattribute__(record, "fixture_origin")
            allowed_backbones = object.__getattribute__(record, "allowed_backbones")
            valid_record = (
                type(record_challenge_id) is str
                and type(record_version) is str
                and record_challenge_id == challenge.challenge_id
                and record_version == challenge.version
                and type(lifecycle_status) is str
                and type(fixture_origin) is bool
                and type(allowed_backbones) is tuple
                and all(type(backbone) is str for backbone in allowed_backbones)
                and len(set(allowed_backbones)) == len(allowed_backbones)
            )
            if valid_record:
                validate_canonical_identifier(record_challenge_id, "challenge_id")
                validate_version(record_version)
                for backbone in allowed_backbones:
                    validate_canonical_identifier(backbone, "backbone")
        except (AttributeError, TypeError, ValueError):
            valid_record = False
        if not valid_record:
            raise McpChallengeUnavailableError()

        if lifecycle_status == "fixture":
            if fixture_origin is not True:
                raise McpChallengeUnavailableError()
            try:
                eligibility = self._registry.assess_live_eligibility(
                    challenge.challenge_id,
                    challenge.version,
                    fixture_mode=True,
                )
            except Exception:
                raise McpIntegrationError() from None
            if type(eligibility) is not LiveEligibility:
                raise McpIntegrationError()
            try:
                eligible = eligibility.eligible
            except AttributeError:
                raise McpIntegrationError() from None
            if eligible is not True:
                if type(eligible) is bool:
                    raise McpChallengeUnavailableError()
                raise McpIntegrationError()
            return lifecycle_status, fixture_origin, allowed_backbones, False
        if lifecycle_status == "live":
            try:
                effectively_live = self._registry.is_effectively_live(
                    challenge.challenge_id, challenge.version
                )
            except Exception:
                raise McpIntegrationError() from None
            if type(effectively_live) is not bool:
                raise McpIntegrationError()
            return (
                lifecycle_status,
                fixture_origin,
                allowed_backbones,
                effectively_live,
            )
        raise McpChallengeUnavailableError()

    def _get_challenge_info(self, request: object) -> ChallengeInfo:
        if type(request) is not GetChallengeInfoRequest:
            raise McpRequestError()
        challenge = request.challenge_key
        status, fixture_origin, allowed_backbones, effectively_live = (
            self._visible_challenge(challenge)
        )
        return _project_challenge_info(
            challenge,
            status,
            fixture_origin,
            effectively_live,
            allowed_backbones,
            self._limits,
        )

    def _provider_prior(self, challenge: ChallengeKey) -> PublishedPrior:
        provider = self._prior_provider
        if provider is None:
            raise McpToolUnavailableError()
        self._visible_challenge(challenge)
        try:
            value = provider.get_prior(
                ChallengeKey(challenge.challenge_id, challenge.version)
            )
        except Exception:
            raise McpIntegrationError() from None
        return _project_prior(value, self._limits, challenge)

    def _get_prior(self, request: object) -> PublishedPrior:
        if type(request) is not GetPriorRequest:
            raise McpRequestError()
        return self._provider_prior(request.challenge_key)

    def _get_mock_scaffold(self, request: object) -> PublishedScaffold:
        if type(request) is not GetMockScaffoldRequest:
            raise McpRequestError()
        provider = self._scaffold_provider
        if provider is None:
            raise McpToolUnavailableError()
        challenge = request.challenge_key
        self._visible_challenge(challenge)
        try:
            value = provider.get_scaffold(
                ChallengeKey(challenge.challenge_id, challenge.version),
                request.scaffold_id,
            )
        except Exception:
            raise McpIntegrationError() from None
        scaffold = _project_scaffold(
            value,
            self._limits,
            challenge,
            request.scaffold_id,
        )
        validation_projector = _Projector(self._limits)
        validation_projector.meter.node()
        validation_strategy = validation_projector.graph(
            scaffold.strategy,
            challenge.challenge_id,
        )
        try:
            validation = dry_validate(validation_strategy)
        except Exception:
            raise McpIntegrationError() from None
        if (
            type(validation) is not ValidationResult
            or type(validation.ok) is not bool
            or type(validation.errors) is not tuple
            or validation.ok is not True
            or len(validation.errors) != 0
        ):
            raise McpIntegrationError()
        return scaffold

    def _dry_validate(self, request: object) -> DryValidateResponse:
        if type(request) is not DryValidateRequest:
            raise McpRequestError()
        try:
            validation = dry_validate(request.strategy)
        except Exception:
            raise McpIntegrationError() from None
        return _project_dry_validation(validation, self._limits)

    def _estimate(self, request: object) -> StructuralEstimate:
        if type(request) is not EstimateRequest:
            raise McpRequestError()
        if self._prior_provider is None or self._estimate_provider is None:
            raise McpToolUnavailableError()
        challenge = request.challenge_key
        prior = self._provider_prior(challenge)
        validation_strategy = _copy_owned_request_graph(
            request.strategy,
            self._limits,
        )
        try:
            validation = dry_validate(validation_strategy)
        except Exception:
            raise McpIntegrationError() from None
        if (
            type(validation) is not ValidationResult
            or type(validation.ok) is not bool
            or type(validation.errors) is not tuple
        ):
            raise McpIntegrationError()
        if validation.ok is not True:
            return _project_invalid_estimate(
                challenge,
                prior,
                validation,
                self._limits,
            )
        if len(validation.errors) != 0:
            raise McpIntegrationError()
        owned_validation = ValidationResult(True, ())
        if type(request.strategy) is not dict:
            raise McpIntegrationError()
        expected_directive_snapshot = tuple(
            _directive_key(directive) for directive in prior.directives
        )
        provider_prior = _project_prior(prior, self._limits, challenge)
        try:
            value = self._estimate_provider.estimate(
                ChallengeKey(challenge.challenge_id, challenge.version),
                provider_prior,
                request.strategy,
                validation,
            )
        except Exception:
            raise McpIntegrationError() from None
        try:
            current_directive_snapshot = tuple(
                _directive_key(directive) for directive in prior.directives
            )
        except Exception:
            raise McpIntegrationError() from None
        if current_directive_snapshot != expected_directive_snapshot:
            raise McpIntegrationError()
        return _project_estimate(
            value,
            self._limits,
            challenge,
            prior,
            validation,
            owned_validation,
        )

    def _preflight_receipt(self) -> None:
        if (
            self._limits.max_total_response_value_nodes < _MAX_RECEIPT_NODES
            or self._limits.max_response_string_utf8_bytes < _MAX_RECEIPT_STRING_BYTES
            or self._limits.max_total_response_utf8_bytes
            < _MAX_RECEIPT_TOTAL_UTF8_BYTES
        ):
            raise McpResourceError()

    def _submit(self, request: object, requester: RequesterIdentity) -> SubmitReceipt:
        if type(request) is not SubmitRequest:
            raise McpRequestError()
        self._preflight_receipt()
        try:
            submission_id = self._submission_service.submit(
                RequesterIdentity(requester.value),
                ChallengeKey(
                    request.challenge_key.challenge_id,
                    request.challenge_key.version,
                ),
                request.strategy,
            )
        except SubmissionResourceError as exc:
            if type(exc) is SubmissionResourceError:
                raise McpResourceError() from None
            raise McpIntegrationError() from None
        except SubmissionRequestError as exc:
            if type(exc) is SubmissionRequestError:
                raise McpRequestError() from None
            raise McpIntegrationError() from None
        except Exception:
            raise McpIntegrationError() from None
        if type(submission_id) is not SubmissionId:
            raise McpIntegrationError()
        try:
            submitted_value = submission_id.value
            owned_id = SubmissionId(submitted_value)
        except Exception:
            raise McpIntegrationError() from None
        try:
            status = self._submission_service.get_status(
                SubmissionId(submitted_value),
                RequesterIdentity(requester.value),
            )
        except Exception:
            raise McpIntegrationError() from None
        try:
            return _project_receipt(status, self._limits, owned_id)
        except Exception:
            raise McpIntegrationError() from None

    def _get_submission_result(
        self, request: object, requester: RequesterIdentity
    ) -> SubmissionResult:
        if type(request) is not GetSubmissionResultRequest:
            raise McpRequestError()
        try:
            consumed = self._query_budget_gate.consume(
                RequesterIdentity(requester.value),
                McpTool.GET_SUBMISSION_RESULT,
            )
        except McpQueryBudgetError as exc:
            if type(exc) is McpQueryBudgetError:
                raise McpQueryBudgetError() from None
            raise McpIntegrationError() from None
        except Exception:
            raise McpIntegrationError() from None
        if consumed is not None:
            raise McpIntegrationError()
        _require_tool_identity(
            McpTool.GET_SUBMISSION_RESULT,
            "get_submission_result",
        )

        submission_id = request.submission_id
        try:
            status = self._submission_service.get_status(
                SubmissionId(submission_id.value),
                RequesterIdentity(requester.value),
            )
        except (SubmissionNotFoundError, SubmissionAuthorizationError) as exc:
            if type(exc) in (SubmissionNotFoundError, SubmissionAuthorizationError):
                raise McpSubmissionUnavailableError() from None
            raise McpIntegrationError() from None
        except SubmissionResourceError as exc:
            if type(exc) is SubmissionResourceError:
                raise McpResourceError() from None
            raise McpIntegrationError() from None
        except SubmissionRequestError as exc:
            if type(exc) is SubmissionRequestError:
                raise McpRequestError() from None
            raise McpIntegrationError() from None
        except Exception:
            raise McpIntegrationError() from None
        projector, schema, owned_status = _begin_submission_result(
            status,
            self._limits,
            submission_id,
        )

        card: EvaluationCard | None = None
        if owned_status.state is SubmissionState.PUBLISHED:
            try:
                card = self._submission_service.read_published(
                    SubmissionId(submission_id.value),
                    RequesterIdentity(requester.value),
                )
            except (SubmissionNotFoundError, SubmissionAuthorizationError) as exc:
                if type(exc) in (
                    SubmissionNotFoundError,
                    SubmissionAuthorizationError,
                ):
                    raise McpSubmissionUnavailableError() from None
                raise McpIntegrationError() from None
            except SubmissionResourceError as exc:
                if type(exc) is SubmissionResourceError:
                    raise McpResourceError() from None
                raise McpIntegrationError() from None
            except Exception:
                raise McpIntegrationError() from None
        return _finish_submission_result(
            projector,
            schema,
            owned_status,
            card,
            submission_id,
        )
