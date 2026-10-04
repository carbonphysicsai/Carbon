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

import itertools
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
    post,
    role,
    select,
    stop,
    text,
)

from carbon.development_session import miner_guidance as guidance
from carbon.development_session import model_provider as mp
from carbon.development_session import research_loop
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_agent import CONTEXT_RESERVE_TOKENS
from carbon.development_session.research_agent_policy import (
    COMPACT,
    COMPACTION_FIELDS,
    COMPACTION_HEADROOM_TOKENS,
    COMPACTION_SUMMARY_CHARACTERS,
    COMPACTION_TOOL,
    COMPACTION_V1,
    GRAPHITE_MINER,
    MAX_TOOL_ARGUMENT_BYTES,
    STOP_TOOL,
    check_compaction,
    graphite_miner_prompt,
    limits_v2,
)
from carbon.development_session.research_loop import (
    COMPACTION_FAILED,
    COMPACTION_NOT_REQUESTED,
    CONTEXT_CEILING,
    SELECTION_TOOL,
    compaction_summary,
)


def model(max_input_tokens=None):
    """A fixture model selection; None keeps the default context size."""
    settings = {"reasoning_effort": None, "max_output_tokens": 1024}
    if max_input_tokens is not None:
        settings["max_input_tokens"] = max_input_tokens
    return mp.select(
        provider_id="openai-responses",
        model_id="gpt-4.1",
        credential={"kind": "file", "reference": "/fixture/not-a-credential"},
        settings=settings,
    )


#: A model whose context is small enough for a short scripted run to reach.
SELECTION = model(16384)
#: Room beside a miner role's longer prompt for a summary.
WIDER = model(32768)
#: The default context size, 65,536 tokens.
DEFAULT = model()
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
        "Carbon context compaction"
    )


def stated(request):
    """The summary size a compaction request states."""
    return int(
        re.search(
            r"at most (\d+) characters in all", request["input"][-1]["content"]
        ).group(1)
    )


def least_bound(requests, at, record, per=2):
    """The bound the compacted request is admitted under, computed here from
    the requests as sent: the least of its bytes, the compaction requests'
    reported tokens plus the summary message's bytes, and the least tokens a
    turn reported plus the bytes after the initial observation (every
    fixture reply reports `per` bytes a token)."""
    asked = requests[at]
    history = asked["input"][:-1]
    kept = history[1 + record["dropped_items"] :]
    size = len(canonical({**asked, "input": [history[0], record["message"], *kept]}))
    compacting = list(itertools.takewhile(asked_to_compact, requests[at:]))
    compaction_tokens = min(len(canonical(r)) // per for r in compacting)
    base = min(len(canonical(r)) // per for r in requests[:at])
    base_bytes = len(canonical({**asked, "input": history[:1]}))
    return min(
        size,
        compaction_tokens + len(canonical(record["message"])),
        base + size - base_bytes,
    )


def reply(output, request, per=2):
    """A completed reply reporting input tokens as the request's bytes over
    `per`, an honest count for a tokenizer at `per` bytes a token."""
    return {
        "model": request["model"],
        "status": "completed",
        "output": output,
        "usage": {
            "input_tokens": len(canonical(request)) // per,
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


class Wordy(SDK):
    """Each result carries `size` bytes of words."""

    def __init__(self, meter, size):
        super().__init__(meter)
        self.size = size

    async def call(self, name, arguments, identity):
        result = await super().call(name, arguments, identity)
        return {**result, "blob": "word " * (self.size // 5)}


def written(characters, alphabet="a"):
    """A summary of exactly `characters` characters over its five fields."""
    each, extra = divmod(characters, len(COMPACTION_FIELDS))
    summary = {}
    for position, field in enumerate(COMPACTION_FIELDS):
        size = each + (position < extra)
        summary[field] = (alphabet * (size // len(alphabet) + 1))[:size]
    return summary


def obeying(turns, *, per, alphabet="a", first=None):
    """A model that calls a tool `turns` times and then selects; asked to
    compact, it writes exactly the characters the request states, in
    `alphabet` - or `first` characters the first time it is asked."""
    requests = []

    def transport(request):
        requests.append(json.loads(canonical(request)))
        if asked_to_compact(request):
            asks = sum(asked_to_compact(r) for r in requests)
            size = first if first is not None and asks == 1 else stated(request)
            summary = written(size, alphabet)
            return reply([summary_call(summary=summary)], request, per)
        done = sum(not asked_to_compact(r) for r in requests) - 1
        if done < turns:
            return reply([call(f"t{done}", INFO)], request, per)
        return reply([select("s")], request, per)

    return transport, requests


def long_session(meter, transport, size):
    """A long session at the default context size: results of `size` bytes,
    and no per-session call cap - the campaign's 400 provider calls bound
    it."""
    return session(
        meter, transport, provider=DEFAULT, sdk=Wordy(meter, size), limits=LIMITS_V2
    )


def turns_after(requests, at):
    """Model turns sent after the compaction request at `at`."""
    return sum(not asked_to_compact(r) for r in requests[at + 1 :])


def session(meter, transport, **extra):
    sdk = extra.pop("sdk", None)
    return role(
        meter,
        transport,
        Bulky(meter) if sdk is None else sdk,
        provider=extra.pop("provider", SELECTION),
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
    assert record["summary_characters_asked"] == [stated(asked)]
    # The compacted request was admitted under the least of three valid
    # bounds: its bytes; the compaction request's tokens plus the summary
    # message's bytes; the first turn's tokens plus the bytes after the
    # initial observation.
    assert record["admission"] == {
        "input_token_bound": least_bound(requests, at, record),
        "spare": COMPACTION_HEADROOM_TOKENS,
        "anchor": record["admission"]["anchor"],
    }
    assert record["admission"]["input_token_bound"] + COMPACTION_HEADROOM_TOKENS <= (
        SELECTION.settings.max_input_tokens - CONTEXT_RESERVE_TOKENS
    )
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


def test_a_full_summary_at_the_default_context_size_is_admitted(tmp_path):
    """Review regression: at the default 65,536-token context a summary of
    the full 12,000 characters the request states is admitted, and the
    session goes on after the compaction instead of stopping at the
    ceiling. The compacted request is measured by the least valid bound,
    not by the compaction request's tokens plus the summary alone."""
    meter = ledger(tmp_path, ceilings={**ROOMY, "provider_attempts": 400})
    transport, requests = obeying(80, per=3)
    report = long_session(meter, transport, 2000)
    assert report["status"] == "SELECTED"
    assert report["compactions"] >= 1 and report["compactions_deferred"] == 0
    record, _ = assert_journalled(meter, requests)
    at = next(i for i, r in enumerate(requests) if asked_to_compact(r))
    assert stated(requests[at]) == COMPACTION_SUMMARY_CHARACTERS
    summary = record["summary"]
    assert sum(map(len, summary.values())) == COMPACTION_SUMMARY_CHARACTERS
    assert record["calls"] == [record["calls"][0]]
    assert record["admission"]["input_token_bound"] == least_bound(
        requests, at, record, per=3
    )
    # Admitted with room to spare, and the session carried on.
    ceiling = DEFAULT.settings.max_input_tokens - CONTEXT_RESERVE_TOKENS
    assert record["admission"]["input_token_bound"] + COMPACTION_HEADROOM_TOKENS <= (
        ceiling
    )
    assert turns_after(requests, at) >= 10
    (meter.root / "epoch-1" / "outcome.json").unlink()
    assert long_session(meter, never, 2000) == report


def test_a_non_ascii_summary_is_asked_for_again_at_the_size_that_fits(tmp_path):
    """A summary in non-ASCII text at the stated size breaks the tool's
    argument bound; the last request asks for the size its own bytes a
    character show will fit, and the session goes on."""
    meter = ledger(tmp_path, ceilings={**ROOMY, "provider_attempts": 400})
    transport, requests = obeying(80, per=3, alphabet="é")
    report = long_session(meter, transport, 2000)
    assert report["status"] == "SELECTED" and report["compactions"] >= 1
    record, _ = assert_journalled(meter, requests)
    first, second = record["summary_characters_asked"]
    assert first == COMPACTION_SUMMARY_CHARACTERS
    assert 0 < second < first and sum(map(len, record["summary"].values())) == second
    retry = [r for r in requests if asked_to_compact(r)][1]
    assert f"bytes; the limit is {MAX_TOOL_ARGUMENT_BYTES} bytes of JSON" in (
        retry["input"][-1]["content"]
    )
    at = requests.index(retry)
    assert turns_after(requests, at) >= 10


def test_a_summary_too_long_for_the_context_left_is_asked_for_again(tmp_path):
    """Large kept turns leave room for fewer characters than the cap; a
    summary longer than the room is refused before it can stop the session,
    and asked for again at the size that fits."""
    meter = ledger(tmp_path, ceilings={**ROOMY, "provider_attempts": 400})
    transport, requests = obeying(40, per=2, first=COMPACTION_SUMMARY_CHARACTERS)
    report = long_session(meter, transport, 7500)
    assert report["status"] == "SELECTED" and report["compactions"] >= 1
    record, _ = assert_journalled(meter, requests)
    first, second = record["summary_characters_asked"]
    # The room held fewer than the cap: the request said so.
    assert first < COMPACTION_SUMMARY_CHARACTERS // 2
    asked = [r for r in requests if asked_to_compact(r)]
    assert stated(asked[0]) == first and stated(asked[1]) == second
    assert "bytes of context and" in asked[1]["input"][-1]["content"]
    assert "are left beside the last 6 turns" in asked[1]["input"][-1]["content"]
    assert first <= second < COMPACTION_SUMMARY_CHARACTERS
    assert turns_after(requests, requests.index(asked[1])) >= 1


def test_no_compaction_is_asked_for_when_no_summary_has_room(tmp_path):
    """When the last turns leave no room for a summary worth its call, no
    compaction is asked for or paid for: the session goes on as it would
    without the rule and stops at the ceiling, typed, history kept."""
    meter = ledger(tmp_path, ceilings=ROOMY)
    transport, requests = obeying(40, per=2)
    report = session(meter, transport, sdk=Wordy(meter, 1500))
    assert report["status"] == "STOPPED" and report["code"] == CONTEXT_CEILING
    assert report["compactions"] == 0 and report["compactions_deferred"] >= 1
    assert not any(asked_to_compact(r) for r in requests)
    assert records(meter.root / "epoch-1") == []
    assert all("-compact-" not in t["turn"] for t in report["provider_turns"])
    (meter.root / "epoch-1" / "outcome.json").unlink()
    assert session(meter, never, sdk=Wordy(meter, 1500)) == report


def test_a_resume_after_the_compaction_call_does_not_resend_it(tmp_path, monkeypatch):
    reference, _ = long_run(TURNS)
    expected = session(ledger(tmp_path / "reference", ceilings=ROOMY), reference)
    meter = ledger(tmp_path / "resumed", ceilings=ROOMY)

    class Death(BaseException):
        """A process death after the compaction reply was booked."""

    def dies(*args, **kwargs):
        raise Death

    monkeypatch.setattr(research_loop, "compaction_summary", dies)
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
    first, retry = [r for r in requests if asked_to_compact(r)]
    note = retry["input"][-1]["content"]
    assert (
        "Carbon asked for this once already and the reply recorded no valid "
        f"compaction (the reply did not call {COMPACT}); this is the last request"
    ) in note
    assert "If this reply records none either, the session stops." in note
    # The last request is the conversation and the note again, not the
    # refused reply, so it is admitted whenever the first was.
    assert retry["input"][:-1] == first["input"][:-1]
    assert record["summary_characters_asked"] == [stated(first), stated(retry)]


def test_a_summary_is_read_only_in_its_closed_schema():
    good = summary_call()
    assert compaction_summary([good]) == (SUMMARY, None)
    assert compaction_summary([text(), good, summary_call("2")])[0] == SUMMARY
    for output, why in (
        ([text()], "did not call " + COMPACT),
        ([call("x", INFO)], "did not call " + COMPACT),
        ([{**good, "arguments": "{"}], "arguments is not valid JSON"),
        ([{**good, "arguments": "[]"}], "arguments is a JSON array, not an object"),
        (
            [summary_call(summary={**SUMMARY, "findings": "é" * 3000})],
            f"bytes; the limit is {MAX_TOOL_ARGUMENT_BYTES} bytes of JSON",
        ),
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
    # A compaction never spends the call the turn after it needs.
    assert not asked_to_compact(sent[-1])
    assert meter.status(owner="alice")["used"]["provider_attempts"] == 25
    turns = [t["turn"] for t in report["provider_turns"]]
    assert sum("-compact-" in t for t in turns) == len(asked)


def test_a_staged_miner_session_compacts_under_its_own_identity(tmp_path):
    """A Graphite miner role compacts in its own stage, and the miner's
    messages are never summarised away unread: the step's message is read
    before the compaction, left out of the compaction request, counted in
    the room the summary must leave, and follows the summary."""
    from carbon.battery.challenge import CHALLENGE

    meter = ledger(tmp_path, ceilings=ROOMY)
    transport, requests = long_run(60, end=stop())

    def posting(request):
        if not asked_to_compact(request):
            post(meter, f"Message {len(requests)}: keep runs on CPU.")
        return transport(request)

    report = role(
        meter,
        posting,
        Bulky(meter),
        provider=WIDER,
        compaction=COMPACTION_V1,
        limits=LIMITS_V2,
        stage="build",
        agent_policy=GRAPHITE_MINER,
        challenge=CHALLENGE,
        tools=(INFO_TOOL, SELECTION_TOOL, STOP_TOOL),
        miner_guidance=guidance.RULE,
    )
    assert report["status"] == "STOPPED" and report["compactions"] >= 1
    record, index = assert_journalled(meter, requests, stage="build")
    assert record["calls"][0] == f"epoch-1-build-compact-{index:03d}"
    at = next(i for i, r in enumerate(requests) if asked_to_compact(r))
    asked, after = requests[at], requests[at + 1]
    assert "keep in constraints every message of the miner's" in (
        asked["input"][-1]["content"]
    )
    # The step's message: read before the compaction, not in its request,
    # right after the kept turns in the next one, and counted in the room.
    shown = after["input"][2 + record["kept_items"]]
    text_ = json.loads(shown["content"])["miner_guidance"]["messages"][0]["text"]
    assert text_ not in canonical(asked).decode()
    assert record["admission"]["spare"] == (
        COMPACTION_HEADROOM_TOKENS + len(canonical(shown)) + 1
    )
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
        f"never more than {COMPACTION_SUMMARY_CHARACTERS} in all",
        "the last 6 turns unchanged",
        "and so does each compaction request",
        "is accepted only if the conversation then fits under the ceiling",
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
