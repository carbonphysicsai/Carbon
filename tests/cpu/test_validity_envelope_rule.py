"""VALIDITY-ENVELOPE-01: outside a validity model's range is UNRESOLVED.

A standing cross-Challenge gate test. Every registered Challenge declares its
reference's validity models (or, explicitly, why none is declared and who owns
it); a case outside a declared range, or missing a declared quantity, is the
typed UNRESOLVED record, never PASS or FAIL and never the candidate's failure.
"""

from __future__ import annotations

import math

import pytest

from carbon.challenge_validator import validity as v
from carbon.reconstruction.capability_registry import CONTRACTS


def test_every_registered_challenge_declares_its_validity_models():
    kinds = (v.Declared, v.Undeclared, v.NoPropertyModel)
    for challenge in CONTRACTS:
        assert challenge in v.DECLARATIONS, f"{challenge}: no validity declaration"
        assert isinstance(v.DECLARATIONS[challenge], kinds)
    for challenge, entry in v.PRE_REGISTRATION.items():
        assert isinstance(entry, kinds), challenge
    with pytest.raises(KeyError):
        v.declaration("no-such-challenge")


def test_an_empty_or_unowned_declaration_is_refused():
    with pytest.raises(ValueError):
        v.Declared(())
    with pytest.raises(ValueError):
        v.Undeclared("", "someone")
    with pytest.raises(ValueError):
        v.Undeclared("why", "")
    with pytest.raises(ValueError):
        v.ValidityModel("m", (("x", None, None),), "src")


def test_the_cold_plate_ranges_are_its_domain_modules_own():
    from carbon.cold_plate import domain

    pg25, laminar = v.COLD_PLATE.models
    assert {q: (lo, hi) for q, lo, hi in pg25.quantities} == {
        "fluid_min_c": domain.PG25_VALID_C,
        "fluid_max_c": domain.PG25_VALID_C,
    }
    assert laminar.quantities == (("reynolds", None, domain.RE_LAMINAR_MAX),)


INSIDE = {"fluid_min_c": 40.0, "fluid_max_c": 70.0, "reynolds": 900.0}


@pytest.mark.parametrize(
    "change, reason",
    [
        # Point B's case: a stratum scaled past the coolant model's 99 C.
        ({"fluid_max_c": 99.4}, "outside_validity:pg25-coolant:fluid_max_c"),
        ({"fluid_min_c": 29.0}, "outside_validity:pg25-coolant:fluid_min_c"),
        ({"reynolds": 2400.0}, "outside_validity:laminar-duct:reynolds"),
        ({"reynolds": math.nan}, "outside_validity:laminar-duct:reynolds"),
        ({"fluid_max_c": None}, "outside_validity:pg25-coolant:fluid_max_c"),
        ({"fluid_max_c": True}, "outside_validity:pg25-coolant:fluid_max_c"),
    ],
)
def test_outside_or_unobserved_is_unresolved_never_pass_or_fail(change, reason):
    found = v.applicability(v.COLD_PLATE.models, {**INSIDE, **change})
    assert found["status"] == v.UNRESOLVED
    assert found["reason"] == reason
    assert found["candidate_failure"] is False
    assert found["status"] not in ("PASS", "FAIL")


def test_inside_every_range_is_applicable_and_the_bounds_are_inclusive():
    assert v.applicability(v.COLD_PLATE.models, INSIDE) is None
    edge = {"fluid_min_c": 30.0, "fluid_max_c": 99.0, "reynolds": 2000.0}
    assert v.applicability(v.COLD_PLATE.models, edge) is None
    missing = {k: x for k, x in INSIDE.items() if k != "reynolds"}
    assert v.applicability(v.COLD_PLATE.models, missing)["status"] == v.UNRESOLVED
