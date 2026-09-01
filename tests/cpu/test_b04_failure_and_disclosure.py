"""Failure separation and protected-data disclosure checks for B-04."""

from __future__ import annotations

import pickle

import pytest

import carbon.evaluation.errors as errors_module
from carbon.evaluation.errors import (
    ReferenceCanonicalDecodingError,
    ReferenceDisclosureCode,
    ReferenceDisclosureError,
    ReferenceInputCode,
    ReferenceServiceCode,
    ReferenceServiceError,
    ReferenceValidationError,
)

_ERROR_CODE_FAMILIES = (
    (ReferenceInputCode, ReferenceValidationError),
    (ReferenceServiceCode, ReferenceServiceError),
    (ReferenceDisclosureCode, ReferenceDisclosureError),
)


@pytest.mark.parametrize(
    "error",
    (
        ReferenceValidationError(
            ReferenceInputCode.STALE_BINDING,
            path="/policy_ref/attacker_secret",
        ),
        ReferenceServiceError(
            ReferenceServiceCode.RUNNER_UNAVAILABLE,
            path="/run_ref/attacker_secret",
        ),
        ReferenceDisclosureError(
            ReferenceDisclosureCode.PROJECTION_NOT_PERMITTED,
            path="/projection/attacker_secret",
        ),
    ),
)
def test_reference_failures_never_echo_hostile_paths_or_pickle(
    error: Exception,
) -> None:
    rendered = f"{error!r} {error}"
    assert "attacker_secret" not in rendered
    with pytest.raises(TypeError):
        pickle.dumps(error)


def test_reference_failure_taxonomy_has_no_candidate_or_scoring_semantics() -> None:
    all_literals = {
        item.value
        for enum_type in (ReferenceInputCode, ReferenceServiceCode)
        for item in enum_type
    }
    forbidden_fragments = ("CANDIDATE", "GATE", "SCORE", "RANK", "SETTLE")
    assert all(
        fragment not in literal
        for literal in all_literals
        for fragment in forbidden_fragments
    )


@pytest.mark.parametrize("enum_type,error_type", _ERROR_CODE_FAMILIES)
def test_error_codes_require_registered_identity_or_exact_string_value(
    enum_type: type,
    error_type: type,
) -> None:
    registered = next(iter(enum_type))
    assert error_type(registered).code == registered.value
    assert type(registered.value) is str
    assert error_type(registered.value).code == registered.value

    pseudo = str.__new__(enum_type, registered.value)
    object.__setattr__(pseudo, "_name_", registered.name)
    object.__setattr__(pseudo, "_value_", "protected-error-secret")
    assert pseudo is not registered
    assert type(pseudo) is enum_type

    with pytest.raises(TypeError) as pseudo_error:
        error_type(pseudo)
    with pytest.raises(TypeError):
        error_type(type("StringSubclass", (str,), {})(registered.value))
    assert "protected-error-secret" not in repr(pseudo_error.value)


@pytest.mark.parametrize("trailing", (0, 1, "false", None))
def test_canonical_decoding_error_trailing_flag_requires_exact_bool(
    trailing: object,
) -> None:
    with pytest.raises(TypeError):
        ReferenceCanonicalDecodingError(trailing=trailing)

    assert (
        ReferenceCanonicalDecodingError(trailing=False).code
        == ReferenceInputCode.INVALID_CANONICAL_BYTES.value
    )
    assert (
        ReferenceCanonicalDecodingError(trailing=True).code
        == ReferenceInputCode.TRAILING_BYTES.value
    )


@pytest.mark.parametrize(
    "mapping_name,key",
    (
        ("INPUT_REJECTION_MESSAGES", ReferenceInputCode.STALE_BINDING),
        ("SERVICE_FAILURE_MESSAGES", ReferenceServiceCode.RUNNER_UNAVAILABLE),
        (
            "DISCLOSURE_FAILURE_MESSAGES",
            ReferenceDisclosureCode.PROJECTION_NOT_PERMITTED,
        ),
    ),
)
def test_failure_message_registries_are_immutable(
    mapping_name: str, key: object
) -> None:
    mapping = getattr(errors_module, mapping_name)
    with pytest.raises(TypeError):
        mapping[key] = "caller-controlled failure text"
