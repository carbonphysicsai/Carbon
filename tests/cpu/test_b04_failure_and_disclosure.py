"""Failure separation and protected-data disclosure checks for B-04."""

from __future__ import annotations

import pickle

import pytest

import carbon.evaluation.errors as errors_module
from carbon.evaluation.errors import (
    ReferenceDisclosureCode,
    ReferenceDisclosureError,
    ReferenceInputCode,
    ReferenceServiceCode,
    ReferenceServiceError,
    ReferenceValidationError,
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
