"""Synthetic transport accounting tests; these are not agent inference."""

import pytest
from test_cw1_research_ledger import ledger

from carbon.development_session.agent import MAX_OUTPUT_TOKENS, MODEL
from carbon.development_session.research_agent import (
    RESERVATION_NANO,
    request_model,
    usage_cost,
)


def request():
    return {
        "model": MODEL,
        "instructions": "test",
        "input": [],
        "tools": [],
        "parallel_tool_calls": False,
        "store": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "reasoning": {"effort": "low"},
    }


def test_cache_and_reasoning_are_metered_without_double_charging():
    value = usage_cost(
        {
            "input_tokens": 1000,
            "output_tokens": 100,
            "input_tokens_details": {"cached_tokens": 800},
            "output_tokens_details": {"reasoning_tokens": 80},
        }
    )
    assert value["nanodollars"] == 200 * 250 + 800 * 25 + 100 * 2000
    assert value["reasoning_tokens"] == 80


def test_exact_replay_uses_retained_response_not_transport(tmp_path):
    budget = ledger(tmp_path)
    calls = []

    def fake(value):
        calls.append(value)
        return {
            "model": MODEL,
            "status": "completed",
            "usage": {"input_tokens": 100, "output_tokens": 10},
            "output": [],
        }

    args = {
        "owner": "alice",
        "identity": "model-1",
        "request": request(),
        "credential_file": None,
        "transport": fake,
    }
    first = request_model(budget, **args)
    assert request_model(budget, **args) == first
    assert len(calls) == 1
    assert budget.status(owner="alice")["used"]["provider_attempts"] == 1


def test_timeout_keeps_full_reservation_and_never_resends(tmp_path):
    budget = ledger(tmp_path)
    calls = []

    def ambiguous(value):
        calls.append(value)
        raise TimeoutError("never echo a provider error")

    args = {
        "owner": "alice",
        "identity": "model-1",
        "request": request(),
        "credential_file": None,
        "transport": ambiguous,
    }
    with pytest.raises(ValueError, match="full reservation"):
        request_model(budget, **args)
    with pytest.raises(ValueError, match="no resend"):
        request_model(budget, **args)
    assert len(calls) == 1
    assert (
        budget.status(owner="alice")["used"]["provider_nanodollars"] == RESERVATION_NANO
    )


@pytest.mark.parametrize(
    "usage",
    [
        None,
        {},
        {"input_tokens": True, "output_tokens": 1},
        {
            "input_tokens": 1,
            "output_tokens": 1,
            "input_tokens_details": {"cached_tokens": 2},
        },
    ],
)
def test_missing_or_impossible_usage_is_not_zero(usage):
    with pytest.raises(ValueError):
        usage_cost(usage)
