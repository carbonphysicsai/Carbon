"""Explicit Burgers physical scaling, separate from fitted loss normalization."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass


def _positive_float(value: object, field: str) -> float:
    if type(value) is not float or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{field} must be a finite positive float")
    return value


def _unit_token(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > 128
        or not all(character.isalnum() or character in "._:/^-" for character in value)
    ):
        raise ValueError("physical unit-system token is invalid")
    return value


@dataclass(frozen=True, slots=True)
class BurgersPhysicalScaling:
    """Reversible ``x=L*x_hat, t=T*t_hat, u=U*u_hat`` transformation.

    ``unit_system`` names the complete native physical-unit contract.  Carbon
    compares the token exactly and never guesses or converts between unit
    systems.  The separately fitted TRAIN RMS used by the learner is not one
    of these physical scales.
    """

    length_scale: float
    time_scale: float
    velocity_scale: float
    unit_system: str

    def __post_init__(self) -> None:
        for field in ("length_scale", "time_scale", "velocity_scale"):
            object.__setattr__(
                self, field, _positive_float(getattr(self, field), field)
            )
        object.__setattr__(self, "unit_system", _unit_token(self.unit_system))

    @property
    def advection_coefficient(self) -> float:
        return self.velocity_scale * self.time_scale / self.length_scale

    def viscosity_coefficient(self, viscosity: object):
        """Return per-case ``nu*T/L**2`` without collapsing viscosity to a scale."""
        import numpy as np

        value = np.asarray(viscosity)
        if not np.issubdtype(value.dtype, np.floating) or not np.isfinite(value).all():
            raise ValueError("viscosity must contain finite floating-point values")
        if (value <= 0).any():
            raise ValueError("viscosity must be positive")
        return value * (self.time_scale / self.length_scale**2)

    def to_dimensionless_position(self, value: object):
        return self._finite_array(value, "position") / self.length_scale

    def to_physical_position(self, value: object):
        return self._finite_array(value, "position") * self.length_scale

    def to_dimensionless_time(self, value: object):
        return self._finite_array(value, "time") / self.time_scale

    def to_physical_time(self, value: object):
        return self._finite_array(value, "time") * self.time_scale

    def to_dimensionless_velocity(self, value: object):
        return self._finite_array(value, "velocity") / self.velocity_scale

    def to_physical_velocity(self, value: object):
        return self._finite_array(value, "velocity") * self.velocity_scale

    def require_unit_system(self, supplied: object) -> None:
        if supplied != self.unit_system:
            raise ValueError("incompatible physical unit system")

    def assert_representable(self, dtype: str) -> None:
        import numpy as np

        target = np.dtype(dtype)
        if target.kind != "f":
            raise ValueError("physical scales require a floating-point dtype")
        values = (
            self.length_scale,
            self.time_scale,
            self.velocity_scale,
            self.advection_coefficient,
            self.time_scale / self.length_scale**2,
        )
        cast = np.asarray(values, dtype=target)
        if not np.isfinite(cast).all() or (cast == 0).any():
            raise ValueError(
                "physical scales are not representable in the execution dtype"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "carbon.burgers-physical-scaling.v1",
            **asdict(self),
            "advection_coefficient": self.advection_coefficient,
            "viscosity_transform": "nu_hat=nu*T/L^2",
            "numerical_normalization": "separate_train_rms",
        }

    @property
    def digest(self) -> str:
        payload = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()

    @classmethod
    def from_dict(cls, value: object) -> BurgersPhysicalScaling:
        if type(value) is not dict or set(value) != {
            "schema",
            "length_scale",
            "time_scale",
            "velocity_scale",
            "unit_system",
            "advection_coefficient",
            "viscosity_transform",
            "numerical_normalization",
        }:
            raise ValueError("physical scaling record is invalid")
        if (
            value["schema"] != "carbon.burgers-physical-scaling.v1"
            or value["viscosity_transform"] != "nu_hat=nu*T/L^2"
            or value["numerical_normalization"] != "separate_train_rms"
        ):
            raise ValueError("physical scaling record is invalid")
        result = cls(
            length_scale=value["length_scale"],
            time_scale=value["time_scale"],
            velocity_scale=value["velocity_scale"],
            unit_system=value["unit_system"],
        )
        if value["advection_coefficient"] != result.advection_coefficient:
            raise ValueError("physical scaling coefficient mismatch")
        return result

    @staticmethod
    def _finite_array(value: object, field: str):
        import numpy as np

        array = np.asarray(value)
        if not np.issubdtype(array.dtype, np.floating) or not np.isfinite(array).all():
            raise ValueError(f"{field} must contain finite floating-point values")
        return array


__all__ = ["BurgersPhysicalScaling"]
