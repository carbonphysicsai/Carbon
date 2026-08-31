"""Compatibility delegates for A7 Strategy identity and evaluation binding.

The public Strategy-only boundary lives in :mod:`carbon.fees.strategy_identity`.
A7's service and historical tests retain these private names while callers
migrate without changing any deployed identity or rejection behavior.
"""

from __future__ import annotations

import hashlib

from carbon.fees import strategy_identity as _strategy_identity
from carbon.fees.model import StrategyHash, SubmissionId, SubmissionResourceLimits
from carbon.registry import ChallengeKey
from carbon.seeding import EvaluationBinding

strategy_schema = _strategy_identity.strategy_schema

_EVALUATION_BINDING_HEADER = b"carbon.a7.evaluation-binding.v1"
_UINT32_MAX = (1 << 32) - 1

_CaptureUnstable = _strategy_identity._CaptureUnstable
_CapturedCandidate = _strategy_identity._CapturedCandidate
_StrategyIdentityResult = _strategy_identity.StrategyIdentityResult


def _utf8_scan(value: str, limit: int) -> tuple[int, bool]:
    return _strategy_identity._utf8_scan(value, limit)


def _stable_dict_items(
    source: dict[object, object], expected: int
) -> list[tuple[object, object]]:
    return _strategy_identity._stable_dict_items(source, expected)


def _capture_strategy(
    strategy: object, limits: SubmissionResourceLimits
) -> _CapturedCandidate:
    return _strategy_identity._capture_strategy(
        strategy,
        limits,
        utf8_scan=_utf8_scan,
        stable_dict_items=_stable_dict_items,
    )


def _strategy_hash(
    strategy: dict[str, object], identity_limit: int
) -> tuple[StrategyHash, int]:
    return _strategy_identity._strategy_hash(strategy, identity_limit)


def _binding_payloads_representable(challenge_key: ChallengeKey) -> bool:
    return _strategy_identity._binding_payloads_representable(
        challenge_key,
        uint32_max=_UINT32_MAX,
    )


def _validate_and_hash_strategy(
    strategy: object,
    limits: SubmissionResourceLimits,
    *,
    challenge_key: ChallengeKey | None = None,
) -> _StrategyIdentityResult:
    return _strategy_identity._validate_and_hash_strategy(
        strategy,
        limits,
        challenge_key=challenge_key,
        capture_strategy=_capture_strategy,
        strategy_hash_builder=_strategy_hash,
        binding_payloads_representable=_binding_payloads_representable,
    )


def _copy_strategy_tree(tree: dict[str, object]) -> dict[str, object]:
    return _strategy_identity._copy_strategy_tree(tree)


def _evaluation_binding(
    submission_id: SubmissionId,
    strategy_hash: StrategyHash,
    challenge_key: ChallengeKey,
) -> EvaluationBinding:
    """Build A4's exact 32-byte binding from safe A7/A3 identities."""

    if type(submission_id) is not SubmissionId:
        raise TypeError("Submission identity is invalid.")
    if type(strategy_hash) is not StrategyHash:
        raise TypeError("Strategy identity is invalid.")
    if type(challenge_key) is not ChallengeKey:
        raise TypeError("Challenge identity is invalid.")

    submission_value = submission_id.value
    strategy_hash_value = strategy_hash.value
    challenge_id = challenge_key.challenge_id
    challenge_version = challenge_key.version
    owned_submission = SubmissionId(submission_value)
    owned_hash = StrategyHash(strategy_hash_value)
    owned_challenge = ChallengeKey(challenge_id, challenge_version)

    fields = (
        (0x01, owned_submission.value),
        (0x02, owned_hash.value),
        (0x03, owned_challenge.challenge_id),
        (0x04, owned_challenge.version),
    )
    digest = hashlib.sha256()
    digest.update(_EVALUATION_BINDING_HEADER)
    for tag, value in fields:
        payload = str.encode(value, "ascii", "strict")
        if len(payload) > _UINT32_MAX:
            raise ValueError("Evaluation binding identity is invalid.")
        digest.update(bytes((tag,)))
        digest.update(int.to_bytes(len(payload), 4, "big"))
        digest.update(payload)
    return EvaluationBinding(digest.digest())


__all__ = ()
