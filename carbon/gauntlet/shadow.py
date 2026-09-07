"""Evaluator-held toy shadow cases, structurally absent from agent sessions."""

from __future__ import annotations

import hashlib
import json

from carbon.toy import evaluate_fixture_reference


class HeldoutToyShadowCases:
    __slots__ = ("__cases", "__distribution_ref")

    def __init__(
        self, *, distribution_ref: str, cases: tuple[tuple[int, int], ...]
    ) -> None:
        if type(distribution_ref) is not str or not distribution_ref:
            raise ValueError("declared fixture distribution identity is required")
        if (
            type(cases) is not tuple
            or len(cases) < 2
            or any(
                type(item) is not tuple
                or len(item) != 2
                or any(type(value) is not int for value in item)
                for item in cases
            )
        ):
            raise ValueError("shadow cases require bounded exact toy observations")
        object.__setattr__(
            self, "_HeldoutToyShadowCases__distribution_ref", distribution_ref
        )
        object.__setattr__(self, "_HeldoutToyShadowCases__cases", cases)

    def __repr__(self) -> str:
        return "HeldoutToyShadowCases(<evaluator-held>)"

    def __getstate__(self) -> object:
        raise TypeError("shadow cases cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("shadow cases cannot be serialized")

    @property
    def fixture_digest(self) -> str:
        payload = json.dumps(
            [self.__distribution_ref, self.__cases], separators=(",", ":")
        ).encode("ascii")
        return (
            "sha256:"
            + hashlib.sha256(b"carbon.be4.shadow.v1\x00" + payload).hexdigest()
        )

    def evaluate(self, coefficient: float) -> float:
        return evaluate_fixture_reference(coefficient, self.__cases)
