"""Dependency-free deterministic synthetic backend for the A8 fixture lane."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import ClassVar

from .model import (
    FixtureRunRequestError,
    FixtureStubProfile,
    _is_supported_profile,
    _NonSerializableValue,
    _require_exact_uninitialized,
    _validated_environment_identity,
)

_MESSAGE_PREFIX = b"carbon.a8.fixture-stub.scalar.v1"
_TRAIN_PHASE = "official_train"
_EVAL_PHASE = "official_eval"
_STRESS_PHASE = "official_stress"
_PHASE_INPUTS = (
    (_TRAIN_PHASE, ("diagnostic_error",)),
    (
        _EVAL_PHASE,
        (
            "gate_error",
            "physics_error",
            "accuracy_error_a",
            "accuracy_error_b",
        ),
    ),
    (
        _STRESS_PHASE,
        (
            "robust_mean_a",
            "robust_tail_a",
            "robust_mean_b",
            "robust_tail_b",
        ),
    ),
)


def _frame_ascii(value: object) -> bytes:
    if type(value) is not str:
        raise FixtureRunRequestError()
    try:
        payload = value.encode("ascii", errors="strict")
    except UnicodeEncodeError:
        raise FixtureRunRequestError() from None
    return len(payload).to_bytes(4, "big") + payload


def _synthetic_scalar(
    *,
    key_material: bytes,
    profile: FixtureStubProfile,
    phase_label: str,
    input_key: str,
    backend_profile_id: str,
    container_digest: str,
) -> float:
    message = _MESSAGE_PREFIX + b"".join(
        _frame_ascii(value)
        for value in (
            profile.profile_id,
            phase_label,
            input_key,
            profile.scoring_digest,
            profile.generator_digest_required,
            backend_profile_id,
            container_digest,
        )
    )
    digest = hmac.new(key_material, message, hashlib.sha256).digest()
    integer = int.from_bytes(digest[0:8], "big") >> 11
    unit = integer / 2**53
    if input_key == "gate_error":
        return 0.5 + (1.0 * unit)
    return 0.125 + (0.5 * unit)


@dataclass(frozen=True, slots=True, repr=False)
class _FixtureBackendMaterial(_NonSerializableValue):
    """Complete private scalar material; it carries no seed or context."""

    numeric_values: tuple[tuple[str, float], ...]
    boolean_values: tuple[tuple[str, bool], ...]

    def __repr__(self) -> str:
        return "_FixtureBackendMaterial(<private>)"


@dataclass(frozen=True, slots=True, repr=False, init=False)
class FixtureStubBackend(_NonSerializableValue):
    """Conspicuous synthetic fixture backend that executes no Strategy."""

    backend_profile_id: str
    container_digest: str
    emission_capable: ClassVar[bool] = False

    def __init__(self, *, backend_profile_id: str, container_digest: str) -> None:
        _require_exact_uninitialized(
            self,
            FixtureStubBackend,
            "backend_profile_id",
        )
        environment = _validated_environment_identity(
            backend_profile_id,
            container_digest,
        )
        object.__setattr__(
            self,
            "backend_profile_id",
            environment.backend_profile_id,
        )
        object.__setattr__(self, "container_digest", environment.container_digest)

    def __repr__(self) -> str:
        return "FixtureStubBackend(<fixture-only>)"

    def _environment_pin(self) -> object:
        if type(self) is not FixtureStubBackend:
            raise FixtureRunRequestError()
        return _validated_environment_identity(
            self.backend_profile_id,
            self.container_digest,
        )

    def _execute_fixture(
        self,
        *,
        profile: FixtureStubProfile,
        train_seed: bytes,
        eval_seed: bytes,
        stress_seed: bytes,
    ) -> _FixtureBackendMaterial:
        """Produce bounded synthetic scalar material from three private A4 keys."""
        if type(self) is not FixtureStubBackend or not _is_supported_profile(profile):
            raise FixtureRunRequestError()
        phase_seeds = {
            _TRAIN_PHASE: train_seed,
            _EVAL_PHASE: eval_seed,
            _STRESS_PHASE: stress_seed,
        }
        if any(
            type(value) is not bytes or len(value) != 32
            for value in phase_seeds.values()
        ):
            raise FixtureRunRequestError()

        by_key: dict[str, float] = {}
        for phase_label, input_keys in _PHASE_INPUTS:
            key_material = phase_seeds[phase_label]
            for input_key in input_keys:
                by_key[input_key] = _synthetic_scalar(
                    key_material=key_material,
                    profile=profile,
                    phase_label=phase_label,
                    input_key=input_key,
                    backend_profile_id=self.backend_profile_id,
                    container_digest=self.container_digest,
                )
        numeric_values = tuple((key, by_key[key]) for key in profile.numeric_input_keys)
        return _FixtureBackendMaterial(
            numeric_values=numeric_values,
            boolean_values=((profile.boolean_input_keys[0], True),),
        )


__all__ = ("FixtureStubBackend",)
