"""Explicit, journalled context compaction (OWNER-GRAPHITE-MINER-01, item 6).

Under `COMPACTION_V1`, when a turn's request nears the context admission
ceiling the loop makes one explicit model call asking for a summary in a
closed schema, then continues with the initial observation, the summary -
labelled as the model's own - and the last turns. The call is metered and
replayed like any model call, its record names exactly what left the
context, and nothing is dropped silently. A plan without the rule stops at
the ceiling as before.

Deterministic Responses mocks test control flow, never agent evidence.
"""

import json
import re

import pytest
from test_cw1_research_ledger import ledger
from test_research_loop_limits import (
    INFO,
    INFO_TOOL,
    LIMITS_V2,
    ROOMY,
    SDK,
    call,
    epoch,
    never,
    role,
    select,
    stop,
    text,
)

from carbon.development_session import model_provider as mp
from carbon.development_session import research_loop
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_agent_policy import (
    COMPACT,
    COMPACTION_FIELDS,
    COMPACTION_SUMMARY_CHARACTERS,
    COMPACTION_TOOL,
    COMPACTION_V1,
    GRAPHITE_MINER,
    STOP_TOOL,
    check_compaction,
    graphite_miner_prompt,
    limits_v2,
)
from carbon.development_session.research_loop import (
    COMPACTION_FAILED,
    COMPACTION_NOT_REQUESTED,
    SELECTION_TOOL,
    compaction_summary,
)

#: A model whose context is small enough for a short scripted run to reach.
SELECTION = mp.select(
    provider_id="openai-responses",
    model_id="gpt-4.1",
    credential={"kind": "file", "reference": "/fixture/not-a-credential"},
    settings={
        "reasoning_effort": None,
        "max_input_tokens": 16384,
        "max_output_tokens": 1024,
    },
)
SUMMARY = {
    "findings": "Wider spectral modes lowered practice error twice.",
    "open_hypotheses": "Depth may matter more than width past 32 modes.",
    "best_recipes": '{"backbone": "fno", "parameters": {"steps": 512}}',
    "constraints": "CPU practice only; the exam is private.",
    "next_steps": "Practise the deeper variant, then select.",
}
_RECORD = re.compile(r"-compact-(\d{3})\.json$")


class Bulky(SDK):
    """Each result carries 600 bytes, so the context grows by about a
    kilobyte a turn: a 16K-token model reaches its compaction trigger after
    about fifteen turns, and the six turns it keeps are a third of it."""

    async def call(self, name, arguments, identity):
        result = await super().call(name, arguments, identity)
        return {**result, "blob": "x" * 600}


#: Turns enough to reach the trigger once, and not twice.
TURNS = 20


def asked_to_compact(request):
    last = request["input"][-1]
    return last.get("role") == "user" and str(last.get("content", "")).startswith(
        ("Carbon context compaction", "Carbon: no valid compaction")
    )


def reply(output, request):
    """A completed reply reporting input tokens as half the request's bytes,
    an honest count for a tokenizer at two bytes a token."""
    return {
        "model": request["model"],
        "status": "completed",
        "output": output,
        "usage": {
            "input_tokens": len(canonical(request)) // 2,
            "output_tokens": 20,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
    }


def summary_call(identity="sum", summary=SUMMARY):
    return call(identity, COMPACT, summary)


def long_run(turns, compactions=None, end=None):
    """A model that calls a tool `turns` times and then ends with `end` (a
    selection by default); asked to compact, it answers from `compactions` in
    order, a summary by default."""
    requests = []
    answers = list(compactions or [])

    def transport(request):
        requests.append(json.loads(canonical(request)))
        if asked_to_compact(request):
            return reply(answers.pop(0) if answers else [summary_call()], request)
        done = sum(not asked_to_compact(r) for r in requests) - 1
        if done < turns:
            return reply([call(f"t{done}", INFO)], request)
        return reply([select("s") if end is None else end], request)

    return transport, requests


def session(meter, transport, **extra):
    return role(
        meter,
        transport,
        Bulky(meter),
        provider=SELECTION,
        compaction=extra.pop("compaction", COMPACTION_V1),
        **extra,
    )


def records(root):
    return sorted(
        path for path in root.glob("*-compact-*.json") if _RECORD.search(path.name)
    )


def assert_journalled(meter, requests, stage=None):
    """The first compaction is on record exactly: what left the context,
    what stayed, the labelled summary the model then read, and its model
    call. Returns the record and the turn it preceded."""
    root = meter.root / "epoch-1" / (stage or "")
    prefix = "epoch-1" if stage is None else "epoch-1-" + stage
    found = records(root)
    assert found, "no compaction record"
    record = json.loads(found[0].read_bytes())
    index = int(_RECORD.search(found[0].name).group(1))
    assert record["turn"] == f"{prefix}-provider-{index:03d}"
    assert record["turns_kept"] == [
        f"{prefix}-provider-{i:03d}" for i in range(index - 6, index)
    ]
    assert record["turns_summarized"] == [
        f"{prefix}-provider-{i:03d}" for i in range(index - 6)
    ]
    at = next(i for i, r in enumerate(requests) if asked_to_compact(r))
    history = requests[at]["input"][:-1]
    dropped = history[1 : 1 + record["dropped_items"]]
    kept = history[1 + record["dropped_items"] :]
    assert record["kept_items"] == len(kept)
    assert record["dropped_digest"] == digest(canonical(dropped))
    after = next(r for r in requests[at:] if not asked_to_compact(r))
    assert after["input"][0] == history[0]
    assert after["input"][1] == record["message"]
    assert after["input"][2 : 2 + len(kept)] == kept
    shown = json.loads(record["message"]["content"])["carbon_context_compaction"]
    assert shown["label"] == "SUMMARY" and shown["summary"] == record["summary"]
    assert "your own summary" in shown["notice"]
    identity = record["calls"][-1]
    assert (root / (identity + "-turn.json")).exists()
    operation = next(
        op for op in meter.status(owner="alice")["operations"] if op["id"] == identity
    )
    assert operation["reservation"]["provider_attempts"] == 1
    return record, index


def test_the_rule_is_closed_and_belongs_to_a_role(tmp_path):
    assert COMPACTION_V1 == {
        "schema": "carbon.autoresearch.compaction.v1",
        "trigger_fraction": 0.85,
        "keep_last_turns": 6,
    }
    assert check_compaction(COMPACTION_V1) is COMPACTION_V1
    for bad in (
        None,
        {**COMPACTION_V1, "keep_last_turns": 6.0},
        {**COMPACTION_V1, "trigger_fraction": 0.9},
        {**COMPACTION_V1, "extra": 1},
    ):
        with pytest.raises(ValueError, match="unknown context compaction rule"):
            check_compaction(bad)
    with pytest.raises(ValueError, match="only a role's session takes compaction"):
        epoch(ledger(tmp_path), never, compaction=COMPACTION_V1)
    assert set(COMPACTION_TOOL["parameters"]["required"]) == set(COMPACTION_FIELDS)


def test_a_long_run_compacts_once_and_continues(tmp_path):
    meter = ledger(tmp_path, ceilings=ROOMY)
    transport, requests = long_run(TURNS)
    report = session(meter, transport)
    assert report["status"] == "SELECTED"
    assert report["compactions"] == 1
    record, index = assert_journalled(meter, requests)
    assert record["summary"] == SUMMARY
    assert record["calls"] == [f"epoch-1-compact-{index:03d}"]
    # The compaction request is an append to the last turn's request: the
    # same instructions and tools, the history so far, then the note.
    at = next(i for i, r in enumerate(requests) if asked_to_compact(r))
    asked, before = requests[at], requests[at - 1]
    assert asked["instructions"] == before["instructions"]
    assert asked["tools"] == before["tools"]
    assert asked["input"][: len(before["input"])] == before["input"]
    # The bound the compacted request was admitted under: the compaction
    # request's reported tokens plus the summary's bytes.
    tokens = len(canonical(asked)) // 2
    assert record["anchor"][0] == tokens + len(canonical(record["message"]))
    # The compaction call is metered and reported like a turn.
    assert f"epoch-1-compact-{index:03d}" in [
        t["turn"] for t in report["provider_turns"]
    ]
    # The tool was offered from the first turn, and the plan froze the rule.
    plan = json.loads((meter.root / "epoch-1" / "plan.json").read_bytes())
    assert plan["compaction"] == COMPACTION_V1
    assert COMPACTION_TOOL in plan["tools"]
    assert requests[0]["tools"] == plan["tools"]
    # A replay is exact and makes no model call.
    (meter.root / "epoch-1" / "outcome.json").unlink()
    assert session(meter, never) == report


def test_a_resume_after_the_compaction_call_does_not_resend_it(tmp_path, monkeypatch):
    reference, _ = long_run(TURNS)
    expected = session(ledger(tmp_path / "reference", ceilings=ROOMY), reference)
    meter = ledger(tmp_path / "resumed", ceilings=ROOMY)

    class Death(BaseException):
        """A process death after the compaction reply was booked."""

    def dies(*args, **kwargs):
        raise Death

    monkeypatch.setattr(research_loop, "compaction_message", dies)
    first, sent = long_run(TURNS)
    with pytest.raises(Death):
        session(meter, first)
    assert asked_to_compact(sent[-1]) and records(meter.root / "epoch-1") == []
    monkeypatch.undo()
    before = len(sent)
    again = session(meter, first)
    # The resume replays the compaction call from the journal: none is sent.
    assert not any(asked_to_compact(r) for r in sent[before:])
    assert {**again, "accounting": None} == {**expected, "accounting": None}


def test_an_invalid_summary_is_asked_for_once_more(tmp_path):
    meter = ledger(tmp_path, ceilings=ROOMY)
    transport, requests = long_run(TURNS, compactions=[[text("Here is a summary.")]])
    report = session(meter, transport)
    assert report["status"] == "SELECTED"
    record, index = assert_journalled(meter, requests)
    assert record["calls"] == [
        f"epoch-1-compact-{index:03d}",
        f"epoch-1-compact-{index:03d}-02",
    ]
    retry = [r for r in requests if asked_to_compact(r)][1]
    assert retry["input"][-1]["content"].startswith(
        "Carbon: no valid compaction was recorded (the reply did not call " + COMPACT
    )


def test_a_summary_is_read_only_in_its_closed_schema():
    good = summary_call()
    assert compaction_summary([good]) == (SUMMARY, None)
    assert compaction_summary([text(), good, summary_call("2")])[0] == SUMMARY
    for output, why in (
        ([text()], "did not call " + COMPACT),
        ([call("x", INFO)], "did not call " + COMPACT),
        ([{**good, "arguments": "{"}], "not one JSON object"),
        ([summary_call(summary={**SUMMARY, "extra": "x"})], "exactly"),
        ([summary_call(summary={**SUMMARY, "findings": 7})], "every field is text"),
        ([summary_call(summary={**SUMMARY, "findings": "  "})], "findings is empty"),
        (
            [
                summary_call(
                    summary={
                        **SUMMARY,
                        "findings": "y" * COMPACTION_SUMMARY_CHARACTERS,
                    }
                )
            ],
            "the limit is",
        ),
    ):
        summary, reason = compaction_summary(output)
        assert summary is None and why in reason, (output, reason)
    assert compaction_summary([good], cut=["sum"]) == (
        None,
        "the call was cut off before it was complete",
    )


@pytest.mark.parametrize(
    "bad",
    [
        [text("no tool")],
        [summary_call(summary={**SUMMARY, "findings": " "})],
        [summary_call(summary={k: v for k, v in SUMMARY.items() if k != "next_steps"})],
        [call("other", INFO)],
    ],
)
def test_no_valid_summary_stops_typed_and_drops_nothing(tmp_path, bad):
    meter = ledger(tmp_path, ceilings=ROOMY)
    transport, requests = long_run(TURNS, compactions=[bad, bad])
    report = session(meter, transport)
    assert report["status"] == "STOPPED"
    assert report["code"] == COMPACTION_FAILED
    assert "no history silently discarded" in report["reason"]
    assert len(report["compaction_calls"]) == 2
    # No turn ran after it and nothing was recorded as compacted.
    assert asked_to_compact(requests[-1])
    assert records(meter.root / "epoch-1") == []


def test_without_the_rule_the_session_stops_at_the_ceiling(tmp_path):
    """The historical rule, unchanged: past the ceiling the session stops,
    history never silently dropped."""
    meter = ledger(tmp_path, ceilings=ROOMY)
    transport, requests = long_run(40)
    report = role(meter, transport, Bulky(meter), provider=SELECTION)
    assert report["status"] == "STOPPED"
    assert report["reason"] == (
        "context admission ceiling; no history silently discarded"
    )
    assert "code" not in report and "compactions" not in report
    assert not any(asked_to_compact(r) for r in requests)


def test_an_unrequested_compaction_call_is_refused(tmp_path):
    meter = ledger(tmp_path, ceilings=ROOMY)
    seen = []

    def transport(request):
        seen.append(json.loads(canonical(request)))
        if len(seen) == 1:
            return reply([summary_call("early")], request)
        return reply([text()], request)

    report = session(meter, transport)
    answered = {
        item["call_id"]: json.loads(item["output"])
        for item in seen[1]["input"]
        if item.get("type") == "function_call_output"
    }
    assert answered["early"]["code"] == COMPACTION_NOT_REQUESTED
    assert report["compactions"] == 0


def test_compaction_calls_count_against_a_set_call_cap(tmp_path):
    meter = ledger(tmp_path, ceilings=ROOMY)
    transport, sent = long_run(40)
    report = session(meter, transport, limits=limits_v2(calls_per_epoch=25))
    assert report["reason"] == "epoch provider-call ceiling"
    asked = [r for r in sent if asked_to_compact(r)]
    assert asked and len(sent) == 25
    assert meter.status(owner="alice")["used"]["provider_attempts"] == 25
    turns = [t["turn"] for t in report["provider_turns"]]
    assert sum("-compact-" in t for t in turns) == len(asked)


def test_a_staged_miner_session_compacts_under_its_own_identity(tmp_path):
    from carbon.battery.challenge import CHALLENGE

    meter = ledger(tmp_path, ceilings=ROOMY)
    transport, requests = long_run(30, end=stop())
    report = role(
        meter,
        transport,
        Bulky(meter),
        provider=SELECTION,
        compaction=COMPACTION_V1,
        limits=LIMITS_V2,
        stage="build",
        agent_policy=GRAPHITE_MINER,
        challenge=CHALLENGE,
        tools=(INFO_TOOL, SELECTION_TOOL, STOP_TOOL),
    )
    assert report["status"] == "STOPPED" and report["compactions"] >= 1
    record, index = assert_journalled(meter, requests, stage="build")
    assert record["calls"][0] == f"epoch-1-build-compact-{index:03d}"
    # The miner prompt states the rule with the values that enforce it.
    prompt = requests[0]["instructions"]
    assert prompt == graphite_miner_prompt(
        "Synthetic role.",
        limits=LIMITS_V2,
        compaction=COMPACTION_V1,
        select=True,
        stop=True,
    )
    for phrase in (
        "would pass 85% of that ceiling",
        "while the conversation holds more than 6 turns",
        f"call {COMPACT}, and only it",
        f"at most {COMPACTION_SUMMARY_CHARACTERS} characters",
        "the last 6 turns unchanged",
        "and so does each compaction request",
    ):
        assert phrase in prompt, phrase


def test_the_compaction_journal_mutation_is_caught(tmp_path, monkeypatch):
    """Specimen: were the loop to compact without its record, the journal
    check above fails - nothing may leave the context unrecorded."""
    real = research_loop.write_once

    def lossy(path, payload):
        if _RECORD.search(path.name):
            return None
        return real(path, payload)

    monkeypatch.setattr(research_loop, "write_once", lossy)
    meter = ledger(tmp_path, ceilings=ROOMY)
    transport, requests = long_run(TURNS)
    session(meter, transport)
    with pytest.raises(AssertionError, match="no compaction record"):
        assert_journalled(meter, requests)
