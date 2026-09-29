"""The context admission ceiling is measured in tokens, not bytes.

Synthetic control-flow tests, never campaign inference or quality evidence.
The provider replies are fixtures; only the admission arithmetic is real.
"""

import asyncio

import pytest
from test_cw1_research_ledger import ledger

from carbon.development_session.agent import MODEL
from carbon.development_session.model_provider import DEFAULT_SELECTION
from carbon.development_session.profile import canonical
from carbon.development_session.research_agent import input_token_bound
from carbon.development_session.research_agent_policy import AUTONOMOUS
from carbon.development_session.research_loop import run_epoch

CEILING = "context admission ceiling; no history silently discarded"
LIMIT = DEFAULT_SELECTION.settings.max_input_tokens - 4096


def reply(text, input_tokens):
    return {
        "model": MODEL,
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": 20,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
    }


def run(meter, transport, observation):
    return asyncio.run(
        run_epoch(
            meter,
            owner="alice",
            epoch=1,
            sdk=None,
            credential_file=None,
            initial_observation=observation,
            agent_policy=AUTONOMOUS,
            transport=transport,
        )
    )


def test_the_bound_is_bytes_until_a_turn_reports_tokens():
    assert input_token_bound(20_000, None) == 20_000
    assert input_token_bound(20_000, (3_000, 18_000)) == 5_000
    # The anchor only covers a request that appends to the anchored one.
    with pytest.raises(ValueError, match="appended request"):
        input_token_bound(17_000, (3_000, 18_000))


def _epoch(tmp_path, first_turn_tokens):
    """Two turns: the second request is over LIMIT in bytes. Requests are
    measured when sent; the loop keeps appending to the same history."""
    probe = []
    run(
        ledger(tmp_path / "probe"),
        lambda r: probe.append(len(canonical(r))) or reply("x", 1),
        {"fixture": True, "pad": ""},
    )
    padding = LIMIT - probe[0] - 500
    requests = []
    replies = [reply("y" * 2_000, first_turn_tokens), reply("done", 1)]
    outcome = run(
        ledger(tmp_path / "run"),
        lambda r: requests.append(len(canonical(r))) or replies[len(requests) - 1],
        {"fixture": True, "pad": "p" * padding},
    )
    assert requests[0] <= LIMIT
    return outcome, requests


def test_a_request_over_the_byte_bound_but_under_the_token_bound_is_admitted(
    tmp_path,
):
    outcome, requests = _epoch(tmp_path, first_turn_tokens=3_000)
    assert len(requests) == 2
    assert requests[1] > LIMIT  # the old rule stopped here
    assert outcome["reason"] != CEILING


def test_the_ceiling_still_stops_a_request_whose_tokens_exceed_it(tmp_path):
    # Specimen: the same epoch, with the first turn reporting nearly the
    # whole ceiling, stops on the ceiling before the second call.
    outcome, requests = _epoch(tmp_path, first_turn_tokens=LIMIT - 100)
    assert len(requests) == 1
    assert (outcome["status"], outcome["reason"]) == ("STOPPED", CEILING)
