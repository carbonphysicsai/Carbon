"""The combined run's Challenge-neutral parts, on a synthetic two-axis Challenge.

No battery value appears here: the box, conditions and origins are made up,
so these tests show the module takes every specific from its caller.
"""

from __future__ import annotations

import math

import pytest

from carbon.challenge_readiness import combined_run as cr

BOX = ((0.0, 10.0), (1.0, 2.0))
RUN = {"dev": ((1.0, 1.5), (2.0, 1.5)), "check": ((3.0, 1.25),)}


def test_fresh_conditions_inside_the_box_pass_unchanged():
    assert cr.check_conditions(RUN, BOX, {"earlier": ((9.0, 1.0),)}) is RUN
    assert cr.repeats(RUN, {"earlier": ((9.0, 1.0),)}) == []


@pytest.mark.parametrize(
    ("splits", "prior", "code"),
    [
        ({"dev": ((11.0, 1.5),)}, {}, "condition_outside_box"),
        ({"dev": ((1.0, 0.5),)}, {}, "condition_outside_box"),
        ({"dev": ((1.0,),)}, {}, "condition_shape"),
        ({"dev": ()}, {}, "conditions_empty"),
        ({"dev": ((1.0, 1.5),), "check": ((1.0, 1.5),)}, {}, "condition_repeated"),
        (
            {"dev": ((1.0, 1.5),)},
            {"earlier": ((1.0 + 1e-12, 1.5),)},
            "condition_not_fresh",
        ),
    ],
)
def test_conditions_outside_repeated_or_stale_are_refused_by_name(splits, prior, code):
    with pytest.raises(cr.CombinedRunError) as refused:
        cr.check_conditions(splits, BOX, prior)
    assert refused.value.code == code


def test_repeats_name_every_earlier_source():
    found = cr.repeats(RUN, {"a": ((3.0, 1.25),), "b": ((3.0, 1.25), (2.0, 1.5))})
    assert found == [
        {"split": "dev", "condition": [2.0, 1.5], "sources": ["b"]},
        {"split": "check", "condition": [3.0, 1.25], "sources": ["a", "b"]},
    ]


def _entry(**change):
    entry = {
        "origin": "harness",
        "family": "surface",
        "attempt": "one",
        "material": cr.DECLARATIVE_RECIPE,
        "document": {"recipe": "x"},
    }
    return {**entry, **change}


def test_a_declarative_recipe_from_a_named_origin_is_admitted():
    entry = _entry()
    assert cr.admit_attack_construction(entry, origins=("harness",)) is entry
    assert cr.PANEL_KINDS == (
        "RECONSTRUCTED",
        "SYNTHETIC_CONTROL",
        "ATTACK_CONSTRUCTION",
    )


@pytest.mark.parametrize(
    ("entry", "code"),
    [
        (_entry(material=cr.PARTICIPANT_CODE), "participant_code_out_of_scope"),
        (_entry(origin="agent"), "attack_construction_origin"),
        (_entry(material="binary"), "attack_construction_material"),
        (_entry(document="print(1)"), "declarative_recipe_not_a_document"),
        ({"origin": "harness"}, "attack_construction_fields"),
        (["not", "a", "dict"], "attack_construction_fields"),
    ],
)
def test_other_constructions_are_refused_by_name(entry, code):
    with pytest.raises(cr.CombinedRunError) as refused:
        cr.admit_attack_construction(entry, origins=("harness",))
    assert refused.value.code == code


def test_a_freeze_names_every_unset_value_and_refuses():
    values = {"a": None, "b": "HUMAN_INPUT", "c": " HUMAN_INPUT ", "d": 0.0, "e": "x"}
    assert cr.unset(values) == ["a", "b", "c"]
    cr.refuse_freeze([])
    with pytest.raises(cr.CombinedRunError) as refused:
        cr.refuse_freeze(["first", "second"])
    assert refused.value.code == "freeze_refused"
    assert refused.value.blockers == ("first", "second")


def test_digests_are_canonical_and_refuse_non_finite_values():
    assert cr.digest({"b": 1, "a": [1.5]}) == cr.digest({"a": [1.5], "b": 1})
    assert cr.digest({"a": 1}).startswith("sha256:")
    with pytest.raises(ValueError):
        cr.digest({"a": math.nan})
