"""A model's mistakes are answered, never raised (OWNER-LAUNCHPAD-PROD-01,
LP-PROD-A).

A provider reply is journalled under a fixed identity and replayed on every
resume, so an exception raised on a model's mistake would stop the epoch again
on every resume. Arguments that are not one bounded JSON object, a malformed
selection and a recipe Carbon cannot rebuild each come back as a typed
REJECTED_BEFORE_DISPATCH tool result naming the field and the fix, and the
epoch goes on. A tool call with no identity cannot be answered, so the epoch
stops with a typed STOPPED outcome. These hold under every parallel-call rule:
none of them changes a turn that was ever journalled, because each replaces
an exception.

Deterministic Responses mocks test control flow, never agent evidence.
"""

import json

import pytest
from test_cw1_research_ledger import ledger
from test_parallel_tool_calls_v2 import (
    LIST,
    SDK,
    START,
    STRATEGY,
    call,
    epoch,
    folder,
    never,
    outputs,
    scripted,
    text,
)

from carbon.development_session.research_agent_policy import (
    PARALLEL_CALLS,
    PARALLEL_CALLS_V2,
)
from carbon.development_session.research_loop import (
    ARGUMENTS_INVALID,
    CANDIDATE_INVALID,
    REFUSAL_CODES,
    SELECT,
    SELECTION_INVALID,
    TOOL_CALL_MALFORMED,
    argument_problem,
    rejected_call,
)
from carbon.development_session.research_tools import PREFIX, _json

RULES = [None, PARALLEL_CALLS, PARALLEL_CALLS_V2]
CHALLENGE_INFO = PREFIX + "get_challenge_info"


def raw_call(identity, name, arguments):
    return {
        "type": "function_call",
        "name": name,
        "call_id": identity,
        "arguments": arguments,
    }


def answered(requests, index, call_id):
    return dict(outputs(requests[index]))[call_id]


@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize(
    ("raw", "words"),
    [
        ("{not json", "is not valid JSON (Expecting property name"),
        ("", "is not valid JSON (Expecting value at line 1 column 1)"),
        (
            '{"kind":"practice","kind":"workspace"}',
            'names the key "kind" more than once',
        ),
        ('{"kind": NaN}', "holds NaN, which is not a JSON number"),
        ("[1, 2]", "is a JSON array, not an object"),
        ('"text"', "is a JSON string, not an object"),
        ("[" * 8000 + "]" * 8000, "is nested too deeply"),
        (json.dumps({"kind": "x" * 16400}), "the limit is 16384 bytes"),
        (12, "must be one JSON object encoded as a string"),
    ],
)
def test_malformed_arguments_are_answered_and_the_epoch_goes_on(
    tmp_path, rule, raw, words
):
    meter = ledger(tmp_path)
    sdk = SDK(meter)
    transport, requests = scripted([[raw_call("a", START, raw)], [text()]])
    result = epoch(meter, sdk, transport, rule=rule)
    assert result["status"] == "STOPPED" and result["reason"] == "agent elected to stop"
    rejection = answered(requests, 1, "a")
    assert rejection["status"] == "REJECTED_BEFORE_DISPATCH"
    assert rejection["code"] == ARGUMENTS_INVALID
    assert rejection["field"] == "arguments"
    assert words in rejection["reason"], rejection["reason"]
    assert rejection["fix"] and rejection["authority_granted"] is False
    # Nothing ran and no slot was spent; the call is journalled, both halves.
    assert sdk.dispatched == []
    assert meter.status(owner="alice")["used"]["research_trials"] == 0
    intent = json.loads((folder(meter) / "epoch-1-tool-000-intent.json").read_bytes())
    assert intent == {"name": START, "arguments": None, "call_id": "a"}
    # A resume replays the answer: no provider call, no dispatch, no raise.
    assert epoch(meter, sdk, never, rule=rule) == result


def test_the_argument_limit_named_is_the_one_enforced():
    from carbon.development_session.research_agent_policy import (
        MAX_TOOL_ARGUMENT_BYTES,
    )

    def sized(n):
        return '{"k":"' + "x" * (n - len('{"k":""}')) + '"}'

    assert len(sized(MAX_TOOL_ARGUMENT_BYTES)) == MAX_TOOL_ARGUMENT_BYTES
    assert _json(sized(MAX_TOOL_ARGUMENT_BYTES))["k"]
    with pytest.raises(ValueError):
        _json(sized(MAX_TOOL_ARGUMENT_BYTES + 1))
    reason, _ = argument_problem(sized(MAX_TOOL_ARGUMENT_BYTES + 1))
    assert f"the limit is {MAX_TOOL_ARGUMENT_BYTES} bytes" in reason


@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize("raw", ["", None, "null", "  "])
def test_an_empty_call_to_a_tool_with_no_arguments_runs_with_none(tmp_path, rule, raw):
    """Models send "", null or nothing for a call with no arguments; a tool
    whose schema takes none runs with {}, as if they had sent it."""
    meter = ledger(tmp_path)
    sdk = SDK(meter)
    transport, requests = scripted([[raw_call("a", CHALLENGE_INFO, raw)], [text()]])
    epoch(meter, sdk, transport, rule=rule)
    assert sdk.dispatched == [(CHALLENGE_INFO, "epoch-1-tool-000")]
    assert answered(requests, 1, "a") == {"status": "OK", "fixture": True}


def test_an_empty_call_to_a_tool_that_takes_arguments_is_refused(tmp_path):
    meter = ledger(tmp_path)
    sdk = SDK(meter)
    transport, requests = scripted([[raw_call("a", START, None)], [text()]])
    epoch(meter, sdk, transport)
    assert answered(requests, 1, "a")["code"] == ARGUMENTS_INVALID
    assert sdk.dispatched == []


def selection(**fields):
    base = {
        "strategy_json": json.dumps(STRATEGY),
        "reason": "synthetic control-flow test, no quality claim",
        "used_feedback": False,
    }
    base.update(fields)
    return {k: v for k, v in base.items() if v is not None}


@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize(
    ("arguments", "code", "field", "words"),
    [
        (selection(reason=None), SELECTION_INVALID, "reason", "reason is required"),
        (selection(grant=True), SELECTION_INVALID, "grant", "only"),
        (
            selection(used_feedback="false"),
            SELECTION_INVALID,
            "used_feedback",
            "true or false",
        ),
        (selection(reason=""), SELECTION_INVALID, "reason", "1 to 4096"),
        (selection(reason="x" * 4097), SELECTION_INVALID, "reason", "1 to 4096"),
        (
            selection(strategy_json="{recipe"),
            CANDIDATE_INVALID,
            "strategy_json",
            "strategy_json is not valid JSON",
        ),
        (
            selection(strategy_json=json.dumps({**STRATEGY, "challenge_id": None})),
            CANDIDATE_INVALID,
            "strategy_json",
            "names no challenge_id",
        ),
        (
            selection(
                strategy_json=json.dumps({**STRATEGY, "parameters": {"steps": "many"}})
            ),
            CANDIDATE_INVALID,
            "strategy_json",
            "Carbon cannot rebuild this recipe",
        ),
    ],
)
def test_a_malformed_selection_is_answered_and_the_epoch_goes_on(
    tmp_path, rule, arguments, code, field, words
):
    """Validated before its intent is journalled; under the old code the
    intent was written first and the check raised, so every resume said
    'tool dispatch incomplete'."""
    meter = ledger(tmp_path)
    transport, requests = scripted([[call("s", SELECT, arguments)], [text()]])
    result = epoch(meter, SDK(meter), transport, rule=rule)
    assert result["status"] == "STOPPED"
    rejection = answered(requests, 1, "s")
    assert (rejection["code"], rejection["field"]) == (code, field)
    assert words in rejection["reason"], rejection["reason"]
    assert not (folder(meter) / "selected-recipe.json").exists()
    assert epoch(meter, SDK(meter), never, rule=rule) == result


def test_a_recipe_carbon_cannot_rebuild_names_its_issues(tmp_path):
    meter = ledger(tmp_path)
    bad = {**STRATEGY, "parameters": {"steps": "many"}}
    transport, requests = scripted(
        [[call("s", SELECT, selection(strategy_json=json.dumps(bad)))], [text()]]
    )
    epoch(meter, SDK(meter), transport, rule=None)
    rejection = answered(requests, 1, "s")
    assert rejection["issues"], rejection
    assert all(set(issue) == {"code", "path"} for issue in rejection["issues"])


def test_an_interrupted_selection_is_recomputed_not_wedged(tmp_path):
    """A selection dispatches nothing outside the epoch folder, so an intent
    left without a result (an interruption, or a wedge recorded by the old
    code) is recomputed on resume, byte for byte."""
    meter = ledger(tmp_path)
    transport, _ = scripted([[call("s", SELECT, selection(reason=""))], [text()]])
    first = epoch(meter, SDK(meter), transport, rule=PARALLEL_CALLS)
    result_file = folder(meter) / "epoch-1-tool-000-result.json"
    retained = result_file.read_bytes()
    result_file.unlink()
    (folder(meter) / "outcome.json").unlink()
    assert epoch(meter, SDK(meter), never, rule=PARALLEL_CALLS) == first
    assert result_file.read_bytes() == retained


def test_an_interrupted_dispatch_still_needs_reconciliation(tmp_path):
    """Exactly once is unchanged for a call that leaves the folder: its intent
    without a result stops for reconciliation, never a second dispatch."""
    meter = ledger(tmp_path)
    transport, _ = scripted([[call("a", LIST)], [text()]])
    epoch(meter, SDK(meter), transport)
    (folder(meter) / "epoch-1-tool-000-result.json").unlink()
    (folder(meter) / "outcome.json").unlink()
    with pytest.raises(ValueError, match="tool dispatch incomplete"):
        epoch(meter, SDK(meter), never)


@pytest.mark.parametrize(
    ("rule", "turn"),
    [
        (None, [{"type": "function_call", "name": LIST, "arguments": "{}"}]),
        (None, [{"type": "function_call", "call_id": "a", "arguments": "{}"}]),
        (
            PARALLEL_CALLS,
            [call("a"), {"type": "function_call", "name": LIST, "arguments": "{}"}],
        ),
        (
            PARALLEL_CALLS_V2,
            [call("a"), {"type": "function_call", "call_id": "b", "arguments": "{}"}],
        ),
    ],
)
def test_a_tool_call_without_identity_stops_the_epoch_typed(tmp_path, rule, turn):
    """It cannot be answered, so the epoch stops, retained - before any call of
    the turn runs."""
    meter = ledger(tmp_path)
    sdk = SDK(meter)
    transport, _ = scripted([turn])
    result = epoch(meter, sdk, transport, rule=rule)
    assert result["status"] == "STOPPED"
    assert result["code"] == TOOL_CALL_MALFORMED
    assert sdk.dispatched == []
    assert epoch(meter, sdk, never, rule=rule) == result


def test_refusal_codes_are_closed():
    with pytest.raises(ValueError, match="unknown loop refusal code"):
        rejected_call("anything_else", "arguments", "reason", "fix")
    for code in REFUSAL_CODES:
        assert (
            rejected_call(code, "f", "r", "x")["status"] == "REJECTED_BEFORE_DISPATCH"
        )
