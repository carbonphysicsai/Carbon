"""graphite_run_proposal names the argument it refuses (2026-10-13 fresh-agent pass).

The last refusal before a pod, proposal_arguments_malformed, came back with no
argument and no correction for every malformed call, so an agent that had done
all the work had nothing to fix. It now names the declared argument and how to
correct it; an invented argument is never named back and no caller value is
repeated. A well-formed call is unchanged.
"""

from __future__ import annotations

import json

import pytest

from carbon.agent_campaign.graphite import experiment as ex

SECRET = "caller-value-5be1"
GOOD = {
    "strategy_json": json.dumps({"schema_version": 1}),
    "hypothesis": "h",
    "expected_effect": "e",
}


@pytest.mark.parametrize(
    ("call", "field", "problem"),
    [
        ({"strategy_json": GOOD["strategy_json"]}, "hypothesis", "missing"),
        (
            {k: GOOD[k] for k in ("strategy_json", "hypothesis")},
            "expected_effect",
            "missing",
        ),
        (
            {k: GOOD[k] for k in ("hypothesis", "expected_effect")},
            "strategy_json",
            "missing",
        ),
        ({**GOOD, SECRET: 1}, None, "unexpected_argument"),
        (
            {**GOOD, "strategy_json": {"schema_version": SECRET}},
            "strategy_json",
            "json_string_required",
        ),
        ({**GOOD, "hypothesis": ""}, "hypothesis", "text_1_to_2048_characters"),
        (
            {**GOOD, "expected_effect": SECRET * 400},
            "expected_effect",
            "text_1_to_2048_characters",
        ),
        ("not an object", None, "arguments_not_an_object"),
    ],
)
def test_a_malformed_proposal_call_names_its_argument(call, field, problem):
    reply = ex.Experiment.propose_tool(None, call, "t1")
    assert (
        reply["status"] == "REJECTED_BEFORE_DISPATCH" and reply["dispatched"] is False
    )
    assert reply["reason_code"] == "proposal_arguments_malformed"
    assert reply["field"] == field and reply["problem"] == problem
    assert reply["correction"].startswith(ex.PROPOSAL_ARGUMENTS_CORRECTION)
    assert SECRET not in json.dumps(reply)
    if field is not None:
        assert reply["correction"].endswith(
            "The argument that broke it: " + field + "."
        )


def test_the_named_arguments_are_the_tools_own():
    from carbon.agent_campaign.graphite.roles import PROPOSAL_TOOL

    assert tuple(PROPOSAL_TOOL["parameters"]["required"]) == ex.PROPOSAL_ARGUMENTS
    assert ex._proposal_argument_fault(GOOD) is None
