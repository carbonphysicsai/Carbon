"""Outside a validity model's range is UNRESOLVED, never PASS or FAIL.

A cross-Challenge gate rule (VALIDITY-ENVELOPE-01; the Carbon Validator owns
every Challenge's gates). Cooling point B's registered scoring extrapolated
24 design strata past the coolant model's 99 C limit and scored them PASS or
FAIL. A reference or a score built on a property model, a correlation or a
surrogate outside the range where that model holds is not evidence about a
candidate, so the case is typed `UNRESOLVED` (or the Challenge's own
`REFERENCE_INVALID`), is never counted as a pass or a fail, and is never
charged to the candidate (invariant 7.5).

Each registered Challenge declares here, explicitly, either the validity
models its reference and scoring use, with their ranges, or why none is
declared yet and who owns the declaration. A missing entry fails the
standing test (`test_validity_envelope_rule.py`); an empty one is refused
(lesson X4). Ranges are copied from each Challenge's own domain module and
the test checks they still agree; no range is invented here (AGENTS.md §5).

`applicability(models, observed)` is the one check: every declared quantity
must be observed, finite and inside its range, or the result is the
`UNRESOLVED` record. A missing or non-finite quantity is unresolved too (fail
closed).

Plain data and the standard library only: the challenge-validator package is
a variant-invariant, miner-reachable surface.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class ValidityModel:
    """One model's range: `quantities` maps an observed quantity's name to
    its inclusive `(low, high)` bounds; either bound may be None (open)."""

    name: str
    quantities: tuple[tuple[str, float | None, float | None], ...]
    source: str

    def __post_init__(self):
        if not self.name or not self.quantities or not self.source:
            raise ValueError("a validity model names itself, its ranges and source")
        for quantity, low, high in self.quantities:
            if not quantity or (low is None and high is None):
                raise ValueError("a range bounds at least one side")
            if low is not None and high is not None and not low < high:
                raise ValueError("a range's low bound is below its high bound")


@dataclass(frozen=True)
class Declared:
    """The Challenge's validity models."""

    models: tuple[ValidityModel, ...]

    def __post_init__(self):
        if not self.models:
            raise ValueError("a declaration names at least one model; use Undeclared")


@dataclass(frozen=True)
class Undeclared:
    """No range declared yet: why, and who owns the declaration. Until it is
    declared, the Challenge's reference statuses are not evidence of
    applicability."""

    reason: str
    owner: str

    def __post_init__(self):
        if not self.reason or not self.owner:
            raise ValueError("an undeclared entry names its reason and owner")


@dataclass(frozen=True)
class NoPropertyModel:
    """A deliberate "none": the reference uses no property model, correlation
    or surrogate with a range (for example, a synthetic PDE)."""

    reason: str


def applicability(models, observed):
    """None when every declared quantity is observed, finite and in range;
    otherwise the typed `UNRESOLVED` record naming the first violation."""
    for model in models:
        for quantity, low, high in model.quantities:
            value = observed.get(quantity)
            if (
                type(value) not in (int, float)
                or isinstance(value, bool)
                or not math.isfinite(value)
            ):
                return _unresolved(model, quantity, "not observed")
            if (low is not None and value < low) or (high is not None and value > high):
                return _unresolved(model, quantity, "outside range")
    return None


def _unresolved(model, quantity, why):
    return {
        "status": UNRESOLVED,
        "reason": f"outside_validity:{model.name}:{quantity}",
        "detail": why,
        "candidate_failure": False,
    }


#: Cold plate: `carbon/cold_plate/domain.py` (PG25_VALID_C, RE_LAMINAR_MAX).
COLD_PLATE = Declared(
    (
        ValidityModel(
            "pg25-coolant",
            (("fluid_min_c", 30.0, 99.0), ("fluid_max_c", 30.0, 99.0)),
            "carbon/cold_plate/domain.py PG25_VALID_C (CoolProp INCOMP::MPG[0.25])",
        ),
        ValidityModel(
            "laminar-duct",
            (("reynolds", None, 2000.0),),
            "carbon/cold_plate/domain.py RE_LAMINAR_MAX",
        ),
    )
)

#: Every registered Challenge's declaration, by Challenge id.
DECLARATIONS = {
    "chip-cold-plate": COLD_PLATE,
    "battery-fastcharge-ageing-development-v1": Undeclared(
        "the OKane2022 DFN reference (PyBaMM) carries no declared temperature, "
        "state or C-rate range; t_max_c and voltages are diagnostics only "
        "(carbon/battery/reference.py), so an out-of-range solve reads OK",
        "Data Collection (ranges from the parameter set's source) with the "
        "science owner (adoption)",
    ),
    "electric-motor-magnetics": Undeclared(
        "the linear magnet model (Br 1.2 T, mu_r 1) excludes demagnetization "
        "(scripts/dev/motor/reference/pilot_plan.py), and the reference "
        "status checks only convergence and periodicity",
        "Data Collection (a demagnetization check) with the science owner "
        "(the limit)",
    ),
    "burgers-dynamics-v1": NoPropertyModel(
        "a synthetic PDE with no property model, correlation or surrogate"
    ),
}

#: Challenges in the launch portfolio without a registered construction
#: contract yet, declared ahead of registration so their onboarding inherits
#: the rule.
PRE_REGISTRATION = {
    "photonic": Undeclared(
        "the supermode table holds from 150 nm to the port gap; inputs are "
        "bounds-checked so it is unreachable, but its failure is an untyped "
        "ValueError, not a typed UNRESOLVED",
        "Data Collection",
    ),
    "f02": Undeclared(
        "the Elmer conduction stack uses constant k, rho and cp with no "
        "declared temperature range",
        "Data Collection with the science owner",
    ),
}


def declaration(challenge_id):
    """The Challenge's declaration; KeyError for an unknown id (fail closed)."""
    return {**DECLARATIONS, **PRE_REGISTRATION}[challenge_id]


__all__ = [
    "COLD_PLATE",
    "DECLARATIONS",
    "PRE_REGISTRATION",
    "UNRESOLVED",
    "Declared",
    "NoPropertyModel",
    "Undeclared",
    "ValidityModel",
    "applicability",
    "declaration",
]
