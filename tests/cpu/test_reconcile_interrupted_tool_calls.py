"""Reconcile makes an interrupted Graphite campaign resumable (Test Runner's filming run).

A Docker failure interrupted a campaign between a tool call's intent and its
result. Reconcile settled the model calls and the workers, but the tool call
still stopped every resume ("tool dispatch incomplete; reconcile without
duplication"), so the page's "Resume it; reconcile first" led nowhere. Reconcile
now answers such a call "outcome unknown" without running it, and the resumed
loop replays that answer.
"""

import json

import pytest
from test_cw1_research_ledger import ledger
from test_parallel_tool_calls_v2 import (
    LIST,
    SDK,
    call,
    epoch,
    folder,
    never,
    scripted,
    text,
)

from carbon.development_session import research_loop
from carbon.development_session.research_loop import (
    INTERRUPTED_TOOL_RESULT,
    settle_interrupted_tool_calls,
)


def _interrupt(meter, transport):
    """One epoch with a dispatched call, then the result and outcome removed as an
    interruption would leave them."""
    sdk = SDK(meter)
    epoch(meter, sdk, transport)
    (folder(meter) / "epoch-1-tool-000-result.json").unlink()
    (folder(meter) / "outcome.json").unlink()
    return sdk


def test_an_interrupted_dispatch_is_answered_and_the_campaign_resumes(tmp_path):
    meter = ledger(tmp_path)
    transport, _ = scripted([[call("a", LIST)], [text()]])
    _interrupt(meter, transport)
    with pytest.raises(ValueError, match="tool dispatch incomplete"):
        epoch(meter, SDK(meter), never)
    assert settle_interrupted_tool_calls(meter.root) == 1
    sdk = SDK(meter)
    result = epoch(meter, sdk, never)
    assert result["status"] == "STOPPED"
    # Nothing was run again: the answer was replayed.
    assert sdk.dispatched == []
    answer = json.loads((folder(meter) / "epoch-1-tool-000-result.json").read_bytes())
    assert answer == INTERRUPTED_TOOL_RESULT
    assert answer["outcome"] == "UNKNOWN" and answer["authority_granted"] is False


def test_settling_twice_changes_nothing(tmp_path):
    meter = ledger(tmp_path)
    transport, _ = scripted([[call("a", LIST)], [text()]])
    _interrupt(meter, transport)
    assert settle_interrupted_tool_calls(meter.root) == 1
    retained = (folder(meter) / "epoch-1-tool-000-result.json").read_bytes()
    assert settle_interrupted_tool_calls(meter.root) == 0
    assert (folder(meter) / "epoch-1-tool-000-result.json").read_bytes() == retained


def test_a_call_that_finished_keeps_its_result(tmp_path):
    meter = ledger(tmp_path)
    transport, _ = scripted([[call("a", LIST)], [text()]])
    epoch(meter, SDK(meter), transport)
    path = folder(meter) / "epoch-1-tool-000-result.json"
    retained = path.read_bytes()
    assert settle_interrupted_tool_calls(meter.root) == 0
    assert path.read_bytes() == retained


def test_only_dispatched_research_tools_are_settled(tmp_path):
    """A selection, stop or finish is recomputed by the loop itself; settling it as
    'unknown' would lose it."""
    meter = ledger(tmp_path)
    folder(meter)  # the epoch folder
    root = meter.root / "epoch-1"
    local = {
        "name": research_loop.SELECT,
        "arguments": {},
        "call_id": "s",
    }
    (root / "epoch-1-tool-001-intent.json").write_text(json.dumps(local))
    (root / "epoch-1-tool-002-intent.json").write_text(json.dumps({"name": "x"}))
    (root / "epoch-1-tool-003-intent.json").write_text("not json")
    assert settle_interrupted_tool_calls(meter.root) == 0
    assert not list(root.glob("*-result.json"))


def test_stage_folders_are_covered_too(tmp_path):
    meter = ledger(tmp_path)
    stage = meter.root / "epoch-2" / "plan"
    stage.mkdir(parents=True)
    intent = {
        "name": research_loop.PREFIX + "start_research_task",
        "arguments": {},
        "call_id": "c",
    }
    (stage / "epoch-2-tool-000-intent.json").write_text(json.dumps(intent))
    assert settle_interrupted_tool_calls(meter.root) == 1
    assert (stage / "epoch-2-tool-000-result.json").is_file()
