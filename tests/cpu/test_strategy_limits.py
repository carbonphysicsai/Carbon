"""A strategy refused for its size is told which published limit it broke.

The compiler keeps its closed code `strategy.identity_invalid`; the research
surface names the limit beside it (OWNER-BATTERY-V2-DISCLOSURE-01, item 4).
Each case breaks exactly one limit and is also refused by the real compiler,
so the named limit is always about an actual refusal. The within-limit twin of
each case is the specimen that the diagnostic is not simply naming everything.
"""

import pytest

from carbon.development_session.contracts import strategy_limits
from carbon.development_session.design_check import _refused
from carbon.development_session.research_catalog import (
    RecipeRejected,
    compile_recipe,
)
from carbon.development_session.strategy_limits import CAPTURE_LIMITS, limits_exceeded

LIMITS = strategy_limits()


def strategy(**parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": "burgers-dynamics-v1",
        "backbone": "fno",
        "parameters": parameters,
    }


def members(n):
    return strategy(**{f"p{i:02d}": 1 for i in range(n)})


CASES = {
    "max_object_members": (members(33), members(32)),
    "max_list_items": (strategy(p=[1] * 33), strategy(p=[1] * 32)),
    "max_total_value_nodes": (
        strategy(**{f"p{i:02d}": [1] * 30 for i in range(17)}),
        strategy(**{f"p{i:02d}": [1] * 30 for i in range(15)}),
    ),
    "max_string_utf8_bytes": (strategy(p="x" * 1025), strategy(p="x" * 1024)),
    "max_object_key_utf8_bytes": (
        strategy(**{"k" * 129: 1}),
        strategy(**{"k" * 128: 1}),
    ),
    "max_strategy_identity_bytes": (
        strategy(**{f"p{i:02d}": "x" * 1000 for i in range(20)}),
        strategy(**{f"p{i:02d}": "x" * 1000 for i in range(10)}),
    ),
}


def test_every_capture_limit_has_a_case():
    assert set(CASES) == set(CAPTURE_LIMITS)


@pytest.mark.parametrize("name", CAPTURE_LIMITS)
def test_the_exceeded_limit_is_named_and_only_that_one(name):
    over, within = CASES[name]
    assert limits_exceeded(over, LIMITS) == (
        {"limit": name, "value": getattr(LIMITS, name)},
    )
    assert limits_exceeded(within, LIMITS) == ()


@pytest.mark.parametrize("name", CAPTURE_LIMITS)
def test_the_compiler_refuses_the_same_strategy_with_its_closed_code(name):
    over, _ = CASES[name]
    with pytest.raises(RecipeRejected) as rejected:
        compile_recipe(over)
    assert [i.code for i in rejected.value.rejected.issues] == [
        "strategy.identity_invalid"
    ]
    refusal = _refused(rejected.value, over)
    assert refusal["issues"][0]["code"] == "strategy.identity_invalid"
    assert refusal["limits_exceeded"] == [
        {"limit": name, "value": getattr(LIMITS, name)}
    ]


def test_a_refusal_for_another_reason_names_no_limit():
    with pytest.raises(RecipeRejected) as rejected:
        compile_recipe(strategy(ensemble_members=2))
    assert "limits_exceeded" not in _refused(rejected.value, strategy())
