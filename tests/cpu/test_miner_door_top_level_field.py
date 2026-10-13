"""The miner door names the top-level field to correct (2026-10-13 L4 dry run).

Through the Graphite miner path, every top-level violation of a research tool
call came back as a bare INVALID_ARGUMENT with no field and no correction
(seven of seven: a missing hypothesis, expected_effect, kind, action,
arguments or strategy, and an unknown extra key), so an agent had nothing to
correct and stalled. Each is now refused before dispatch with its declared
field and the registered correction, as the object wire's schema refusal
already does. A key the caller invented is never named back, and no caller
value is repeated.
"""

from __future__ import annotations

import pytest

from carbon.miner_mcp import standard

RUN = {
    "source": "print(1)",
    "files": [],
    "seconds": 30,
    "hypothesis": "h",
    "expected_effect": "e",
}
GOOD = {
    "kind": "workspace",
    "strategy": None,
    "action": "run_python",
    "arguments": RUN,
    "hypothesis": "h",
    "expected_effect": "e",
}
SECRET = "caller-value-7f3a"


def _refusal(call):
    with pytest.raises(standard.AdapterFailure) as refused:
        standard._arguments("start_research_task", call)
    failure = refused.value
    assert failure.code is standard.AdapterCode.INVALID_ARGUMENT
    assert failure.dispatch_may_have_occurred is False
    assert failure.correction is not None, "a refusal must say what to correct"
    return failure


def test_the_good_call_passes():
    args = standard._arguments("start_research_task", GOOD)
    assert args["strategy_json"] is None and args["hypothesis"] == "h"


@pytest.mark.parametrize("key", sorted(GOOD))
def test_a_missing_top_level_field_is_named(key):
    failure = _refusal({k: v for k, v in GOOD.items() if k != key})
    assert failure.field == key
    assert failure.correction["correction_code"] == "tool_field_missing"
    assert key in failure.correction["correction"]
    assert "start_research_task" in failure.correction["correction"]


def test_an_invented_key_is_refused_without_being_named_back():
    failure = _refusal({**GOOD, SECRET: 1})
    assert failure.field is None
    assert failure.correction["correction_code"] == "tool_field_unexpected"
    assert SECRET not in repr(failure.correction)


@pytest.mark.parametrize(
    ("change", "field", "code"),
    [
        ({"hypothesis": ""}, "hypothesis", "tool_text_bounded"),
        ({"expected_effect": "x" * 2049}, "expected_effect", "tool_text_bounded"),
        ({"kind": SECRET}, "kind", "tool_value_invalid"),
        ({"action": SECRET}, "action", "workspace_action_unknown"),
        ({"strategy": {"x": SECRET}}, "strategy", "workspace_recipe_forbidden"),
        ({"arguments": SECRET}, "arguments", "json_object_required"),
    ],
)
def test_a_bad_top_level_value_is_named_and_never_repeated(change, field, code):
    failure = _refusal({**GOOD, **change})
    assert failure.field == field
    assert failure.correction["correction_code"] == code
    assert SECRET not in repr(failure.correction)


def test_a_non_object_request_is_still_refused():
    with pytest.raises(standard.AdapterFailure) as refused:
        standard._arguments("start_research_task", ["not", "an", "object"])
    assert refused.value.code is standard.AdapterCode.INVALID_ARGUMENT
