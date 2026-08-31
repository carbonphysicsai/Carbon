"""Focused B-02B tests for the public A7-owned Strategy identity seam."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from carbon import fees
from carbon.fees import (
    StrategyHash,
    SubmissionResourceError,
    SubmissionResourceLimits,
    strategy_identity,
)
from carbon.fees import identity as legacy_identity
from carbon.fees.strategy_identity import StrategyIdentityResult, identify_strategy


def _limits(**overrides: object) -> SubmissionResourceLimits:
    values: dict[str, object] = {
        "max_total_value_nodes": 10_000,
        "max_object_members": 256,
        "max_list_items": 256,
        "max_string_utf8_bytes": 4096,
        "max_object_key_utf8_bytes": 512,
        "max_strategy_identity_bytes": 1_000_000,
        "max_challenge_id_bytes": 256,
        "max_concurrent_identity_builds": 8,
        "max_retained_submission_records": 256,
        "max_retained_value_nodes": 1_000_000,
        "max_retained_strategy_identity_bytes": 16_000_000,
    }
    values.update(overrides)
    return SubmissionResourceLimits(**values)  # type: ignore[arg-type]


def _strategy() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "challenge_id": "a7_fixture",
        "backbone": "fno",
        "parameters": {
            "fixture_note": "deliberately_non_scientific",
            "layers": [1, 2, 3],
        },
    }


def test_public_identity_preserves_exact_a7_golden_and_result_shape() -> None:
    source = _strategy()

    result = identify_strategy(source, _limits())

    assert type(result) is StrategyIdentityResult
    assert tuple(field.name for field in fields(result)) == (
        "strategy",
        "validation",
        "strategy_hash",
        "value_nodes",
        "identity_bytes",
        "a7_error_code",
    )
    assert not hasattr(result, "__dict__")
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        result.identity_bytes = 0  # type: ignore[misc]
    assert result.validation is not None and result.validation.ok
    assert type(result.strategy_hash) is StrategyHash
    assert result.strategy_hash.value == (
        "sha256:aee363f955383bda8cc569730492cc2ba567949056d5636a52858cbb8ca82839"
    )
    assert result.value_nodes == 10
    assert result.identity_bytes == 306
    assert result.a7_error_code is None


def test_public_identity_returns_one_detached_topology_preserving_snapshot() -> None:
    source = _strategy()
    source_parameters = source["parameters"]
    assert type(source_parameters) is dict
    source_layers = source_parameters["layers"]
    assert type(source_layers) is list

    result = identify_strategy(source, _limits())

    assert result.strategy == source
    assert result.strategy is not source
    accepted_parameters = result.strategy["parameters"]  # type: ignore[index]
    assert accepted_parameters is not source_parameters
    assert accepted_parameters["layers"] is not source_layers  # type: ignore[index]
    source_layers.append(4)
    assert accepted_parameters["layers"] == [1, 2, 3]  # type: ignore[index]


def test_public_identity_invokes_a2_once_on_the_detached_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _strategy()
    original = strategy_identity.strategy_schema.dry_validate
    observed: list[object] = []

    def spy(candidate: object) -> object:
        observed.append(candidate)
        assert candidate is not source
        return original(candidate)

    monkeypatch.setattr(strategy_identity.strategy_schema, "dry_validate", spy)

    result = identify_strategy(source, _limits())

    assert result.validation is not None and result.validation.ok
    assert observed == [result.strategy]


def test_private_a7_delegate_remains_byte_type_and_failure_identical() -> None:
    source = _strategy()

    public = identify_strategy(source, _limits())
    delegated = legacy_identity._validate_and_hash_strategy(source, _limits())

    assert type(delegated) is StrategyIdentityResult
    assert delegated == public
    assert delegated.strategy is not public.strategy
    assert type(delegated.strategy_hash) is type(public.strategy_hash) is StrategyHash

    shared: list[object] = [1]
    aliased = _strategy()
    aliased["parameters"] = {"left": shared, "right": shared}
    public_rejected = identify_strategy(aliased, _limits())
    delegated_rejected = legacy_identity._validate_and_hash_strategy(aliased, _limits())
    assert public_rejected == delegated_rejected
    assert public_rejected.a7_error_code == "strategy.alias_forbidden"


def test_public_identity_keeps_a7_resource_error_mapping() -> None:
    with pytest.raises(SubmissionResourceError) as caught:
        identify_strategy(
            _strategy(),
            _limits(max_strategy_identity_bytes=305),
        )

    assert caught.value.code == "submission.resource_limit_exceeded"
    assert str(caught.value) == "Submission resource limit was exceeded."


def test_public_submodule_does_not_change_a7_root_exports_or_hash_class() -> None:
    assert strategy_identity.__all__ == (
        "StrategyHash",
        "StrategyIdentityResult",
        "SubmissionResourceLimits",
        "identify_strategy",
    )
    assert strategy_identity.StrategyHash is StrategyHash
    assert strategy_identity.SubmissionResourceLimits is SubmissionResourceLimits
    assert fees.StrategyHash is StrategyHash
    assert "identify_strategy" not in fees.__all__
    assert "StrategyIdentityResult" not in fees.__all__
