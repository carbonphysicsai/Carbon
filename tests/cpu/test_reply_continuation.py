"""A reply cut at its output limit is continued (`REPLY_CONTINUATION_V1`).

Graphite context and reply spec (2026-10-21), part 2, and sweep S27: Build
replies cut at max_output 16,384 stopped the campaign after two turns. Under
the reply-continuation rule a new Graphite plan freezes, the first cut reply
in a row is asked to continue without repeating itself, the next to send only
its tool call, and only the rule's `max_truncated_turns` cuts in a row stop
the session, with the same typed outcome. A plan without the rule is
unchanged: its tests are `test_research_loop_resilience`.
"""

from __future__ import annotations

import json

import pytest
from test_cw1_research_ledger import ledger
from test_parallel_tool_calls_v2 import SDK, START, call, epoch, folder, never, text
from test_research_loop_resilience import ended, notes, replies

from carbon.development_session.research_loop import (
    OUTPUT_CAP_HIT,
    REPLIES_TRUNCATED,
    REPLY_CONTINUATION_SCHEMA,
    REPLY_CONTINUATION_V1,
    check_reply_continuation,
)

RULE = REPLY_CONTINUATION_V1
CUT = ended([text("Thinking at length")], output_tokens=2048)


def test_the_rule_is_the_registered_record():
    assert RULE == {
        "schema": "carbon.autoresearch.reply-continuation.v1",
        "max_truncated_turns": 3,
    }
    assert check_reply_continuation(dict(RULE)) == RULE
    for bad in (
        None,
        {"schema": REPLY_CONTINUATION_SCHEMA},
        {**RULE, "max_truncated_turns": 1},
        {**RULE, "max_truncated_turns": True},
        {**RULE, "schema": "carbon.autoresearch.reply-continuation.v0"},
        {**RULE, "extra": 1},
    ):
        with pytest.raises(ValueError):
            check_reply_continuation(bad)


def test_a_cut_reply_is_continued_then_asked_for_its_tool_call_only(tmp_path):
    """Two cut replies in a row no longer stop the session: the first note
    asks the model to continue without repeating, the second for only the
    tool call; a completed reply after them goes on as usual."""
    meter = ledger(tmp_path)
    sdk = SDK(meter)
    transport, requests = replies(CUT, CUT, [text()])
    result = epoch(meter, sdk, transport, reply_continuation=RULE)
    assert result["status"] == "STOPPED"
    assert result["reason"] == "agent elected to stop"
    assert len(requests) == 3
    (first,) = notes(requests[1])
    assert "cut off at its limit of 2048 output tokens" in first
    assert "Do not repeat what you already wrote" in first
    assert "Carbon stops this run" not in first
    second = notes(requests[2])[-1]
    assert "only the tool call you need" in second
    assert "If your next reply also ends before any tool call" in second
    for turn, attempt in (("000", 1), ("001", 2)):
        record = json.loads(
            (folder(meter) / f"epoch-1-provider-{turn}-truncated.json").read_bytes()
        )
        assert record["rule"] == RULE and record["attempt"] == attempt
        assert record["reason"] == "max_output_tokens"
    plan = json.loads((folder(meter) / "plan.json").read_bytes())
    assert plan["reply_continuation"] == RULE
    # Every cut reply was metered; nothing was resent or dropped.
    assert meter.status(owner="alice")["used"]["provider_attempts"] == 3
    # A resume replays it all: no provider call, the same outcome.
    assert epoch(meter, sdk, never, reply_continuation=RULE) == result


@pytest.mark.parametrize(
    "cut",
    [CUT, ended([call("a", START, {"kind": "practice"})])],
)
def test_only_the_rules_count_of_cuts_in_a_row_stops_typed(tmp_path, cut):
    meter = ledger(tmp_path)
    sdk = SDK(meter)
    transport, requests = replies(*[cut] * 5)
    result = epoch(meter, sdk, transport, reply_continuation=RULE)
    assert result["status"] == "STOPPED" and result["code"] == REPLIES_TRUNCATED
    assert len(requests) == RULE["max_truncated_turns"] == 3
    assert result["truncated_turns"] == [
        "epoch-1-provider-000",
        "epoch-1-provider-001",
        "epoch-1-provider-002",
    ]
    assert result["cause"] == OUTPUT_CAP_HIT
    assert sdk.dispatched == []
    assert epoch(meter, sdk, never, reply_continuation=RULE) == result


def test_a_reply_whose_call_ran_resets_the_attempts(tmp_path):
    """A cut reply that still finished a call made progress: the next cut
    one is asked to continue again, not for its tool call only."""
    meter = ledger(tmp_path)
    sdk = SDK(meter)
    transport, _ = replies(CUT, [call("a")], CUT, [text()])
    result = epoch(meter, sdk, transport, reply_continuation=RULE)
    assert result["reason"] == "agent elected to stop"
    record = json.loads(
        (folder(meter) / "epoch-1-provider-002-truncated.json").read_bytes()
    )
    assert record["attempt"] == 1
    assert "Do not repeat what you already wrote" in record["message"]["content"]


def test_a_plan_without_the_rule_keeps_the_historical_note_and_stop(tmp_path):
    meter = ledger(tmp_path)
    transport, requests = replies(CUT, CUT, CUT)
    result = epoch(meter, SDK(meter), transport)
    assert result["code"] == REPLIES_TRUNCATED and len(requests) == 2
    record = json.loads(
        (folder(meter) / "epoch-1-provider-000-truncated.json").read_bytes()
    )
    assert "rule" not in record and "attempt" not in record
    assert "more concisely" in record["message"]["content"]
    plan = json.loads((folder(meter) / "plan.json").read_bytes())
    assert "reply_continuation" not in plan
