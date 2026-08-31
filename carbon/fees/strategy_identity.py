"""Bounded Strategy capture and canonical A7 identity construction.

This public A7-owned seam detaches hostile values, preserves A2 as the first
semantic authority, and constructs the deployed versioned Strategy identity.
It does not admit a submission or grant fee, execution, or scientific
authority.
"""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Callable
from dataclasses import dataclass

from carbon import schema as strategy_schema
from carbon.fees.model import (
    StrategyHash,
    SubmissionResourceError,
    SubmissionResourceLimits,
)
from carbon.registry import ChallengeKey
from carbon.schema import ValidationResult

_STRATEGY_IDENTITY_HEADER = b"carbon.strategy.identity.v1"
_FRAME_HEADER_BYTES = 9
_CONTAINER_COUNT_BYTES = 8
_UINT32_MAX = (1 << 32) - 1
_UINT64_MAX = (1 << 64) - 1

_CAPTURE_UNSTABLE = "strategy.capture_unstable"
_ALIAS_FORBIDDEN = "strategy.alias_forbidden"
_UTF8_INVALID = "strategy.utf8_invalid"
_IDENTITY_INVALID = "strategy.identity_invalid"
_CANONICAL_SUBMISSION_ID_SAMPLE = "00000000-0000-4000-8000-000000000000"
_TAGGED_STRATEGY_HASH_SAMPLE = "sha256:" + "0" * 64


class _InvalidKey:
    """Fresh inert non-string key used only in an A2 candidate."""

    __slots__ = ()


class _InvalidLeaf:
    """Fresh inert non-JSON leaf used only in an A2 candidate."""

    __slots__ = ()


class _CaptureUnstable(RuntimeError):
    """Internal signal for an observed mutation during bounded capture."""


class _IdentityEncodingFailure(RuntimeError):
    """Internal constant-payload signal for an impossible accepted encoding."""


@dataclass(frozen=True, slots=True)
class _CapturedCandidate:
    candidate: object
    value_nodes: int
    identity_lower_bound_bytes: int
    repeated_container: bool
    invalid_utf8: bool
    error_code: str | None


@dataclass(frozen=True, slots=True)
class StrategyIdentityResult:
    """Detached Strategy identity result with unchanged A7 rejection detail."""

    strategy: dict[str, object] | None
    validation: ValidationResult | None
    strategy_hash: StrategyHash | None
    value_nodes: int
    identity_bytes: int
    a7_error_code: str | None


_StrategyIdentityResult = StrategyIdentityResult

_Utf8Scan = Callable[[str, int], tuple[int, bool]]
_StableDictItems = Callable[[dict[object, object], int], list[tuple[object, object]]]
_CaptureStrategy = Callable[[object, SubmissionResourceLimits], _CapturedCandidate]
_StrategyHashBuilder = Callable[[dict[str, object], int], tuple[StrategyHash, int]]
_BindingPayloadsRepresentable = Callable[[ChallengeKey], bool]


def _raise_resource_limit() -> None:
    raise SubmissionResourceError._limit()


def _checked_meter_add(current: int, addition: int, limit: int) -> int:
    if addition < 0 or current > limit - addition:
        _raise_resource_limit()
    return current + addition


def _utf8_scan(value: str, limit: int) -> tuple[int, bool]:
    """Count bounded UTF-8 width without allocating an encoded copy.

    A lone surrogate has no strict UTF-8 encoding.  It is charged the
    conservative one-octet lower bound solely to keep a rejecting scan
    bounded without making invalid UTF-8 itself a resource overrun;
    ``invalid`` prevents that value from ever reaching canonical encoding.
    """

    byte_count = 0
    invalid = False
    value_length = str.__len__(value)
    for index in range(value_length):
        code_point = ord(str.__getitem__(value, index))
        if code_point <= 0x7F:
            width = 1
        elif code_point <= 0x7FF:
            width = 2
        elif 0xD800 <= code_point <= 0xDFFF:
            width = 1
            invalid = True
        elif code_point <= 0xFFFF:
            width = 3
        else:
            width = 4
        byte_count = _checked_meter_add(byte_count, width, limit)
    return byte_count, invalid


def _primitive_payload_size(
    value: object,
    string_limit: int,
    *,
    utf8_scan: _Utf8Scan | None = None,
) -> tuple[int, bool]:
    active_utf8_scan = _utf8_scan if utf8_scan is None else utf8_scan
    value_type = type(value)
    if value is None or value_type is bool:
        return 0, False
    if value_type is int:
        magnitude_bytes = (int.bit_length(value) + 7) // 8
        return _checked_meter_add(1, magnitude_bytes, _UINT64_MAX), False
    if value_type is float:
        return 8, False
    if value_type is str:
        return active_utf8_scan(value, string_limit)
    return 0, False


def _assign(destination: object, slot: object, value: object) -> None:
    if type(destination) is list:
        list.__setitem__(destination, slot, value)
        return
    if type(destination) is dict:
        dict.__setitem__(destination, slot, value)
        return
    raise _CaptureUnstable() from None


def _stable_dict_items(
    source: dict[object, object], expected: int
) -> list[tuple[object, object]]:
    observed: list[tuple[object, object]] = []
    try:
        iterator = iter(dict.items(source))
        for _ in range(expected):
            observed.append(next(iterator))
        try:
            next(iterator)
        except StopIteration:
            pass
        else:
            raise _CaptureUnstable()
        if dict.__len__(source) != expected:
            raise _CaptureUnstable()
    except (RuntimeError, StopIteration):
        raise _CaptureUnstable() from None
    return observed


def _stable_list_items(source: list[object], expected: int) -> list[object]:
    observed: list[object] = []
    try:
        for index in range(expected):
            observed.append(list.__getitem__(source, index))
        if list.__len__(source) != expected:
            raise _CaptureUnstable()
    except (IndexError, RuntimeError):
        raise _CaptureUnstable() from None
    return observed


def _capture_strategy(
    strategy: object,
    limits: SubmissionResourceLimits,
    *,
    utf8_scan: _Utf8Scan | None = None,
    stable_dict_items: _StableDictItems | None = None,
) -> _CapturedCandidate:
    """Detach one bounded topology-preserving candidate from hostile input."""

    if type(limits) is not SubmissionResourceLimits:
        raise TypeError("Submission resource limits are invalid.")

    active_utf8_scan = _utf8_scan if utf8_scan is None else utf8_scan
    active_stable_dict_items = (
        _stable_dict_items if stable_dict_items is None else stable_dict_items
    )

    max_nodes = limits.max_total_value_nodes
    identity_limit = limits.max_strategy_identity_bytes
    value_nodes = 1
    if value_nodes > max_nodes:
        _raise_resource_limit()
    identity_bytes = _checked_meter_add(
        len(_STRATEGY_IDENTITY_HEADER), _FRAME_HEADER_BYTES, identity_limit
    )

    root_holder: list[object] = [None]
    work: list[tuple[object, object, object]] = [(strategy, root_holder, 0)]
    # Strong source references prevent object-id reuse during the capture.
    memo: dict[int, tuple[object, object]] = {}
    repeated_container = False
    invalid_utf8 = False

    while work:
        source, destination, slot = work.pop()
        source_type = type(source)

        if source_type is dict or source_type is list:
            source_identity = id(source)
            memo_entry = memo.get(source_identity)
            if memo_entry is not None:
                retained_source, copied_container = memo_entry
                if retained_source is not source:
                    raise _CaptureUnstable() from None
                repeated_container = True
                _assign(destination, slot, copied_container)
                continue

            try:
                cardinality = (
                    dict.__len__(source)
                    if source_type is dict
                    else list.__len__(source)
                )
            except (RuntimeError, TypeError):
                raise _CaptureUnstable() from None

            cardinality_limit = (
                limits.max_object_members
                if source_type is dict
                else limits.max_list_items
            )
            if cardinality > cardinality_limit or value_nodes > max_nodes - cardinality:
                _raise_resource_limit()

            identity_bytes = _checked_meter_add(
                identity_bytes, _CONTAINER_COUNT_BYTES, identity_limit
            )
            identity_bytes = _checked_meter_add(
                identity_bytes,
                cardinality * _FRAME_HEADER_BYTES,
                identity_limit,
            )
            if source_type is dict:
                identity_bytes = _checked_meter_add(
                    identity_bytes,
                    cardinality * _FRAME_HEADER_BYTES,
                    identity_limit,
                )
            value_nodes += cardinality

            if source_type is list:
                copied_list: list[object] = [None] * cardinality
                memo[source_identity] = (source, copied_list)
                _assign(destination, slot, copied_list)
                children = _stable_list_items(source, cardinality)
                for index in range(cardinality - 1, -1, -1):
                    work.append((children[index], copied_list, index))
                continue

            copied_dict: dict[object, object] = {}
            memo[source_identity] = (source, copied_dict)
            _assign(destination, slot, copied_dict)
            items = active_stable_dict_items(source, cardinality)
            child_work: list[tuple[object, object, object]] = []
            seen_string_keys: set[str] = set()
            for source_key, child in items:
                if type(source_key) is not str:
                    inert_key = _InvalidKey()
                    dict.__setitem__(copied_dict, inert_key, _InvalidLeaf())
                    continue
                key_bytes, key_invalid = active_utf8_scan(
                    source_key,
                    min(
                        limits.max_object_key_utf8_bytes,
                        identity_limit - identity_bytes,
                    ),
                )
                invalid_utf8 = invalid_utf8 or key_invalid
                identity_bytes = _checked_meter_add(
                    identity_bytes, key_bytes, identity_limit
                )
                if source_key in seen_string_keys:
                    raise _CaptureUnstable() from None
                seen_string_keys.add(source_key)
                dict.__setitem__(copied_dict, source_key, _InvalidLeaf())
                child_work.append((child, copied_dict, source_key))
            work.extend(reversed(child_work))
            continue

        copied_value: object
        if (
            source is None
            or source_type is bool
            or source_type is int
            or source_type is float
            or source_type is str
        ):
            payload_size, value_invalid = _primitive_payload_size(
                source,
                min(
                    limits.max_string_utf8_bytes,
                    identity_limit - identity_bytes,
                ),
                utf8_scan=active_utf8_scan,
            )
            invalid_utf8 = invalid_utf8 or value_invalid
            identity_bytes = _checked_meter_add(
                identity_bytes, payload_size, identity_limit
            )
            copied_value = source
        else:
            copied_value = _InvalidLeaf()
        _assign(destination, slot, copied_value)

    return _CapturedCandidate(
        candidate=root_holder[0],
        value_nodes=value_nodes,
        identity_lower_bound_bytes=identity_bytes,
        repeated_container=repeated_container,
        invalid_utf8=invalid_utf8,
        error_code=None,
    )


def _frame_tag(value: object) -> int:
    value_type = type(value)
    if value is None:
        return 0x00
    if value_type is bool:
        return 0x02 if value else 0x01
    if value_type is int:
        return 0x03
    if value_type is float:
        return 0x04
    if value_type is str:
        return 0x05
    if value_type is list:
        return 0x06
    if value_type is dict:
        return 0x07
    raise RuntimeError("Captured Strategy identity is invalid.")


def _strict_utf8_size(value: str) -> int:
    byte_count, invalid = _utf8_scan(value, _UINT64_MAX)
    if invalid:
        raise _IdentityEncodingFailure() from None
    return byte_count


def _primitive_frame_size(value: object) -> int:
    payload_size, invalid = _primitive_payload_size(value, _UINT64_MAX)
    if invalid:
        raise _IdentityEncodingFailure() from None
    return _FRAME_HEADER_BYTES + payload_size


def _checked_identity_add(current: int, addition: int, limit: int) -> int:
    if addition < 0 or addition > _UINT64_MAX or current > limit - addition:
        _raise_resource_limit()
    return current + addition


def _measure_strategy_frames(
    strategy: dict[str, object], identity_limit: int
) -> tuple[int, dict[int, int]]:
    """Compute every container payload length bottom-up without recursion."""

    payload_lengths: dict[int, int] = {}
    work: list[tuple[bool, object]] = [(False, strategy)]
    while work:
        leaving, value = work.pop()
        value_type = type(value)
        if value_type is not dict and value_type is not list:
            continue
        if not leaving:
            work.append((True, value))
            if value_type is list:
                for child in reversed(value):
                    if type(child) is dict or type(child) is list:
                        work.append((False, child))
            else:
                for key, child in reversed(tuple(dict.items(value))):
                    if type(key) is not str:
                        raise RuntimeError("Captured Strategy identity is invalid.")
                    if type(child) is dict or type(child) is list:
                        work.append((False, child))
            continue

        payload_size = _CONTAINER_COUNT_BYTES
        if value_type is list:
            for child in value:
                child_type = type(child)
                child_size = (
                    _FRAME_HEADER_BYTES + payload_lengths[id(child)]
                    if child_type is dict or child_type is list
                    else _primitive_frame_size(child)
                )
                payload_size = _checked_identity_add(
                    payload_size, child_size, identity_limit
                )
        else:
            for key, child in dict.items(value):
                if type(key) is not str:
                    raise RuntimeError("Captured Strategy identity is invalid.")
                key_frame_size = _FRAME_HEADER_BYTES + _strict_utf8_size(key)
                payload_size = _checked_identity_add(
                    payload_size, key_frame_size, identity_limit
                )
                child_type = type(child)
                child_size = (
                    _FRAME_HEADER_BYTES + payload_lengths[id(child)]
                    if child_type is dict or child_type is list
                    else _primitive_frame_size(child)
                )
                payload_size = _checked_identity_add(
                    payload_size, child_size, identity_limit
                )
        if payload_size > _UINT64_MAX:
            _raise_resource_limit()
        payload_lengths[id(value)] = payload_size

    root_frame_size = _FRAME_HEADER_BYTES + payload_lengths[id(strategy)]
    total_size = _checked_identity_add(
        len(_STRATEGY_IDENTITY_HEADER), root_frame_size, identity_limit
    )
    return total_size, payload_lengths


def _stream_primitive_payload(
    digest: object,
    value: object,
) -> int:
    value_type = type(value)
    if value is None or value_type is bool:
        return 0
    if value_type is int:
        if value == 0:
            digest.update(b"\x00")
            return 1
        sign = b"\x01" if value < 0 else b"\x00"
        magnitude = -value if value < 0 else value
        magnitude_size = (int.bit_length(magnitude) + 7) // 8
        digest.update(sign)
        digest.update(int.to_bytes(magnitude, magnitude_size, "big"))
        return 1 + magnitude_size
    if value_type is float:
        digest.update(struct.pack(">d", value))
        return 8
    if value_type is str:
        payload = str.encode(value, "utf-8", "strict")
        digest.update(payload)
        return len(payload)
    raise RuntimeError("Captured Strategy identity is invalid.")


def _strategy_hash(
    strategy: dict[str, object], identity_limit: int
) -> tuple[StrategyHash, int]:
    total_size, payload_lengths = _measure_strategy_frames(strategy, identity_limit)
    digest = hashlib.sha256()
    digest.update(_STRATEGY_IDENTITY_HEADER)
    emitted = len(_STRATEGY_IDENTITY_HEADER)
    work: list[object] = [strategy]
    while work:
        value = work.pop()
        value_type = type(value)
        tag = _frame_tag(value)
        if value_type is dict or value_type is list:
            payload_size = payload_lengths[id(value)]
        else:
            payload_size, invalid = _primitive_payload_size(value, _UINT64_MAX)
            if invalid:
                raise RuntimeError("Captured Strategy identity is invalid.")

        header = bytes((tag,)) + int.to_bytes(payload_size, 8, "big")
        digest.update(header)
        emitted += len(header)

        if value_type is list:
            count = int.to_bytes(list.__len__(value), 8, "big")
            digest.update(count)
            emitted += len(count)
            work.extend(reversed(value))
        elif value_type is dict:
            count = int.to_bytes(dict.__len__(value), 8, "big")
            digest.update(count)
            emitted += len(count)
            ordered_items = list(dict.items(value))
            ordered_items.sort(key=lambda item: str.encode(item[0], "utf-8", "strict"))
            for key, child in reversed(ordered_items):
                work.append(child)
                work.append(key)
        else:
            emitted += _stream_primitive_payload(digest, value)

    if emitted != total_size:
        raise RuntimeError("Captured Strategy identity is invalid.")
    return StrategyHash(f"sha256:{digest.hexdigest()}"), total_size


def _invalid_identity_result(
    *,
    validation: ValidationResult | None,
    value_nodes: int,
    code: str,
) -> _StrategyIdentityResult:
    return _StrategyIdentityResult(
        strategy=None,
        validation=validation,
        strategy_hash=None,
        value_nodes=value_nodes,
        identity_bytes=0,
        a7_error_code=code,
    )


def _binding_payloads_representable(
    challenge_key: ChallengeKey,
    *,
    uint32_max: int | None = None,
) -> bool:
    if type(challenge_key) is not ChallengeKey:
        raise TypeError("Challenge identity is invalid.")
    active_uint32_max = _UINT32_MAX if uint32_max is None else uint32_max
    fields = (
        _CANONICAL_SUBMISSION_ID_SAMPLE,
        _TAGGED_STRATEGY_HASH_SAMPLE,
        challenge_key.challenge_id,
        challenge_key.version,
    )
    return all(
        type(field) is str
        and str.isascii(field)
        and str.__len__(field) <= active_uint32_max
        for field in fields
    )


def _validate_and_hash_strategy(
    strategy: object,
    limits: SubmissionResourceLimits,
    *,
    challenge_key: ChallengeKey | None = None,
    capture_strategy: _CaptureStrategy | None = None,
    strategy_hash_builder: _StrategyHashBuilder | None = None,
    binding_payloads_representable: _BindingPayloadsRepresentable | None = None,
) -> _StrategyIdentityResult:
    """Capture, invoke A2 exactly once, and identify an accepted Strategy."""

    active_capture_strategy = (
        _capture_strategy if capture_strategy is None else capture_strategy
    )
    active_strategy_hash_builder = (
        _strategy_hash if strategy_hash_builder is None else strategy_hash_builder
    )
    active_binding_payloads_representable = (
        _binding_payloads_representable
        if binding_payloads_representable is None
        else binding_payloads_representable
    )
    try:
        captured = active_capture_strategy(strategy, limits)
    except _CaptureUnstable:
        return _invalid_identity_result(
            validation=None, value_nodes=0, code=_CAPTURE_UNSTABLE
        )

    validation = strategy_schema.dry_validate(captured.candidate)
    if not validation.ok:
        return _StrategyIdentityResult(
            strategy=None,
            validation=validation,
            strategy_hash=None,
            value_nodes=captured.value_nodes,
            identity_bytes=0,
            a7_error_code=None,
        )
    if captured.repeated_container:
        return _invalid_identity_result(
            validation=validation,
            value_nodes=captured.value_nodes,
            code=_ALIAS_FORBIDDEN,
        )
    if captured.invalid_utf8:
        return _invalid_identity_result(
            validation=validation,
            value_nodes=captured.value_nodes,
            code=_UTF8_INVALID,
        )
    if type(captured.candidate) is not dict:
        return _invalid_identity_result(
            validation=validation,
            value_nodes=captured.value_nodes,
            code=_IDENTITY_INVALID,
        )
    if challenge_key is not None:
        candidate_challenge = dict.get(captured.candidate, "challenge_id")
        if (
            type(candidate_challenge) is not str
            or candidate_challenge != challenge_key.challenge_id
            or not active_binding_payloads_representable(challenge_key)
        ):
            return _invalid_identity_result(
                validation=validation,
                value_nodes=captured.value_nodes,
                code=_IDENTITY_INVALID,
            )

    try:
        strategy_hash, identity_bytes = active_strategy_hash_builder(
            captured.candidate,
            limits.max_strategy_identity_bytes,
        )
    except SubmissionResourceError:
        raise
    except (RuntimeError, UnicodeEncodeError):
        return _invalid_identity_result(
            validation=validation,
            value_nodes=captured.value_nodes,
            code=_IDENTITY_INVALID,
        )
    if identity_bytes != captured.identity_lower_bound_bytes:
        return _invalid_identity_result(
            validation=validation,
            value_nodes=captured.value_nodes,
            code=_IDENTITY_INVALID,
        )
    return _StrategyIdentityResult(
        strategy=captured.candidate,
        validation=validation,
        strategy_hash=strategy_hash,
        value_nodes=captured.value_nodes,
        identity_bytes=identity_bytes,
        a7_error_code=None,
    )


def identify_strategy(
    strategy: object,
    limits: SubmissionResourceLimits,
) -> StrategyIdentityResult:
    """Return A7's detached bounded Strategy snapshot and identity result."""

    return _validate_and_hash_strategy(strategy, limits)


def _copy_strategy_tree(tree: dict[str, object]) -> dict[str, object]:
    """Return a fresh iterative copy of one already accepted Strategy tree."""

    if type(tree) is not dict:
        raise TypeError("Stored Strategy identity is invalid.")
    copied_root: dict[str, object] = {}
    memo: dict[int, object] = {id(tree): copied_root}
    work: list[tuple[object, object]] = [(tree, copied_root)]
    while work:
        source, destination = work.pop()
        if type(source) is dict:
            for key, child in dict.items(source):
                if type(key) is not str:
                    raise RuntimeError("Stored Strategy identity is invalid.")
                child_type = type(child)
                if child_type is dict or child_type is list:
                    copied_child = memo.get(id(child))
                    if copied_child is None:
                        copied_child = {} if child_type is dict else [None] * len(child)
                        memo[id(child)] = copied_child
                        work.append((child, copied_child))
                    dict.__setitem__(destination, key, copied_child)
                elif (
                    child is None
                    or child_type is bool
                    or child_type is int
                    or child_type is float
                    or child_type is str
                ):
                    dict.__setitem__(destination, key, child)
                else:
                    raise RuntimeError("Stored Strategy identity is invalid.")
        else:
            for index, child in enumerate(source):
                child_type = type(child)
                if child_type is dict or child_type is list:
                    copied_child = memo.get(id(child))
                    if copied_child is None:
                        copied_child = {} if child_type is dict else [None] * len(child)
                        memo[id(child)] = copied_child
                        work.append((child, copied_child))
                    list.__setitem__(destination, index, copied_child)
                elif (
                    child is None
                    or child_type is bool
                    or child_type is int
                    or child_type is float
                    or child_type is str
                ):
                    list.__setitem__(destination, index, child)
                else:
                    raise RuntimeError("Stored Strategy identity is invalid.")
    return copied_root


__all__ = (
    "StrategyHash",
    "StrategyIdentityResult",
    "SubmissionResourceLimits",
    "identify_strategy",
)
