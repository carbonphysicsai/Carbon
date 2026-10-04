"""The v2 parallel-call rule (OWNER-LAUNCHPAD-PROD-01, LP-PROD-A).

A campaign that froze `PARALLEL_CALLS_V2` runs every function call of a turn,
one after another in the model's order, each journalled before and after it
runs under its own identity, with no consecutive-turn stop. A selection, a
stop or an unresolved dispatch ends the epoch, and the turn's later calls are
journalled as not run. The agent sees its remaining budget before every turn,
any tool call renews its one free-text reminder, and Carbon's own agent can
select only a practiced recipe. Campaigns frozen under `PARALLEL_CALLS` or no
rule keep exactly their behaviour (`test_parallel_tool_calls.py`).

Deterministic Responses mocks test control flow, never agent evidence.
"""

import asyncio
import json

import pytest
from test_cw1_research_ledger import ledger
from test_cw1_research_loop import response

from carbon.development_session import research_loop
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_agent_policy import (
    AUTONOMOUS,
    PARALLEL_CALLS,
    PARALLEL_CALLS_V2,
    STOP,
    prompt_for,
)
from carbon.development_session.research_loop import (
    SELECT,
    SELECTION_NOT_PRACTICED,
    run_epoch,
)
from carbon.development_session.research_tools import PREFIX

LIST = PREFIX + "list_public_material"
START = PREFIX + "start_research_task"
#: The Burgers fixture recipe `test_cw1_research_loop` selects; it compiles.
STRATEGY = {
    "schema_version": "1.0",
    "challenge_id": "burgers-dynamics-v1",
    "backbone": "fno",
    "parameters": {"steps": 512, "enforce_mean": True},
}


def call(identity, name=LIST, arguments=None):
    return {
        "type": "function_call",
        "name": name,
        "call_id": identity,
        "arguments": json.dumps({} if arguments is None else arguments),
    }


def text(words="Nothing further in this synthetic control."):
    return {
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": words}],
    }


def stop(identity):
    return call(
        identity,
        STOP,
        {
            "reason": "no_feasible_action",
            "evidence": "Synthetic control; no real result.",
            "used_feedback": False,
        },
    )


def select(identity, strategy=STRATEGY):
    return call(
        identity,
        SELECT,
        {
            "strategy_json": json.dumps(strategy),
            "reason": "synthetic control-flow test, no quality claim",
            "used_feedback": False,
        },
    )


class SDK:
    """Records every dispatched tool. A numerical task charges one research
    trial, as the executor does; `practiced` records a completed practice the
    way the task store does; `unresolved` names call ids whose dispatch is
    reported unresolved."""

    def __init__(self, meter=None, *, practiced=False, unresolved=()):
        self.meter, self.practiced, self.unresolved = meter, practiced, unresolved
        self.dispatched = []

    async def call(self, name, arguments, identity):
        self.dispatched.append((name, identity))
        if name == START:
            operation = "fixture-trial-" + identity
            self.meter.reserve(
                operation,
                owner="alice",
                phase="research",
                request=arguments,
                resources={"research_trials": 1},
            )
            self.meter.finish(
                operation,
                owner="alice",
                state="SUCCEEDED",
                actual={"research_trials": 1},
                result={"status": "FIXTURE_STARTED"},
            )
            if self.practiced:
                record_practice(self.meter, arguments["recipe"])
        if identity in self.unresolved:
            return {"status": "UNKNOWN", "requires_reconciliation": True}
        return {"status": "OK", "fixture": True}


def record_practice(meter, recipe, provenance="REAL_JAX_PUBLIC_PRACTICE"):
    body = canonical({"provenance": provenance, "recipe": recipe})
    with meter.db() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS research_results(owner TEXT NOT NULL,"
            "task TEXT NOT NULL,body BLOB NOT NULL,digest TEXT NOT NULL,"
            "PRIMARY KEY(owner,task))"
        )
        count = db.execute("SELECT COUNT(*) FROM research_results").fetchone()[0]
        db.execute(
            "INSERT INTO research_results VALUES(?,?,?,?)",
            ("alice", f"fixture-task-{count}", body, digest(body)),
        )


def scripted(turns):
    """A transport replying with each scripted turn's output in order. Each
    request is kept as it was sent: the loop goes on appending to its live
    history."""
    requests = []

    def transport(request):
        requests.append(json.loads(canonical(request)))
        return response(turns[len(requests) - 1])

    return transport, requests


def never(_request):
    pytest.fail("a replay made a provider call")


def epoch(meter, sdk, transport, rule=PARALLEL_CALLS_V2, **extra):
    return asyncio.run(
        run_epoch(
            meter,
            owner="alice",
            epoch=1,
            sdk=sdk,
            credential_file=None,
            initial_observation={"fixture": True},
            transport=transport,
            parallel_calls=rule,
            **extra,
        )
    )


def outputs(request):
    return [
        (item["call_id"], json.loads(item["output"]))
        for item in request["input"]
        if item.get("type") == "function_call_output"
    ]


def folder(meter):
    return meter.root / "epoch-1"


def test_every_call_of_a_turn_runs_in_order_each_journalled(tmp_path):
    meter = ledger(tmp_path)
    sdk = SDK(meter)
    transport, requests = scripted([[call("a"), call("b"), call("c")], [text()]])
    result = epoch(meter, sdk, transport)
    assert result["status"] == "STOPPED"
    # Every call ran, in order, under its own identity.
    assert [identity for _, identity in sdk.dispatched] == [
        "epoch-1-tool-000",
        "epoch-1-tool-000-01",
        "epoch-1-tool-000-02",
    ]
    # Each was journalled before it ran and after; the turn is journalled.
    for identity, call_id in zip(
        ("epoch-1-tool-000", "epoch-1-tool-000-01", "epoch-1-tool-000-02"), "abc"
    ):
        intent = json.loads((folder(meter) / (identity + "-intent.json")).read_bytes())
        assert intent == {"name": LIST, "arguments": {}, "call_id": call_id}
        assert (folder(meter) / (identity + "-result.json")).exists()
    turn = json.loads((folder(meter) / "epoch-1-provider-000-calls.json").read_bytes())
    assert [c["tool"] for c in turn["calls"]] == [
        "epoch-1-tool-000",
        "epoch-1-tool-000-01",
        "epoch-1-tool-000-02",
    ]
    assert turn["rule"] == PARALLEL_CALLS_V2
    # Every call is answered with its own result, in the model's order.
    assert outputs(requests[1]) == [
        (c, {"status": "OK", "fixture": True}) for c in "abc"
    ]
    # The request allows parallel calls and the plan freezes the rule.
    assert all(request["parallel_tool_calls"] is True for request in requests)
    plan = json.loads((folder(meter) / "plan.json").read_bytes())
    assert plan["parallel_calls"] == PARALLEL_CALLS_V2
    # A replay reproduces the outcome with no provider call and no dispatch.
    assert epoch(meter, sdk, never) == result
    assert len(requests) == 2 and len(sdk.dispatched) == 3
    assert research_loop.parallel_call_counts(folder(meter)) == {
        "parallel_calls_run": 3,
        "parallel_calls_not_run": 0,
    }


def test_v2_has_no_consecutive_turn_stop(tmp_path):
    sdk = SDK()
    turns = [[call(f"x{n}"), call(f"y{n}")] for n in range(5)] + [[text()]]
    transport, requests = scripted(turns)
    result = epoch(ledger(tmp_path), sdk, transport)
    assert result["status"] == "STOPPED" and "consecutive" not in result["reason"]
    assert len(requests) == 6 and len(sdk.dispatched) == 10


def test_a_resume_runs_only_the_calls_that_had_not_run(tmp_path):
    """Exactly once, per call: an interruption after the first of three calls
    replays the first from its journal and runs the other two."""
    meter = ledger(tmp_path)
    transport, requests = scripted([[call("a"), call("b"), call("c")], [text()]])

    class Crash(Exception):
        """A process death while the second call is in flight."""

    class Crashing(SDK):
        async def call(self, name, arguments, identity):
            if identity == "epoch-1-tool-000-01":
                raise Crash
            return await super().call(name, arguments, identity)

    with pytest.raises(Crash):
        epoch(meter, Crashing(), transport)
    # The second call's intent was journalled before it was dispatched, so it
    # stops for reconciliation rather than running twice.
    with pytest.raises(ValueError, match="tool dispatch incomplete"):
        epoch(meter, SDK(), transport)
    # Reconciled as never run, the resume runs it and the third once each.
    (folder(meter) / "epoch-1-tool-000-01-intent.json").unlink()
    sdk = SDK()
    result = epoch(meter, sdk, transport)
    assert result["status"] == "STOPPED"
    assert [identity for _, identity in sdk.dispatched] == [
        "epoch-1-tool-000-01",
        "epoch-1-tool-000-02",
    ]
    assert len(requests) == 2


def test_a_stop_ends_the_epoch_and_later_calls_are_journalled_not_run(tmp_path):
    meter = ledger(tmp_path)
    sdk = SDK()
    transport, requests = scripted([[call("a"), stop("s"), call("c"), call("d")]])
    result = epoch(meter, sdk, transport, agent_policy=AUTONOMOUS)
    assert result["status"] == "STOPPED"
    assert result["reason"] == "agent reported no_feasible_action"
    # The call before the stop ran; the calls after it did not.
    assert [identity for _, identity in sdk.dispatched] == ["epoch-1-tool-000"]
    journal = json.loads(
        (folder(meter) / "epoch-1-provider-000-not-run.json").read_bytes()
    )
    assert journal["ended_by"] == "epoch-1-tool-000-01"
    assert journal["ended_with"] == "STOPPED"
    assert [(c["call_id"], c["tool"]) for c in journal["not_run"]] == [
        ("c", "epoch-1-tool-000-02"),
        ("d", "epoch-1-tool-000-03"),
    ]
    assert not (folder(meter) / "epoch-1-tool-000-02-intent.json").exists()
    assert research_loop.parallel_call_counts(folder(meter)) == {
        "parallel_calls_run": 2,
        "parallel_calls_not_run": 2,
    }
    assert epoch(meter, sdk, never, agent_policy=AUTONOMOUS) == result
    assert len(requests) == 1


def test_an_unresolved_dispatch_ends_the_epoch_and_later_calls_do_not_run(tmp_path):
    meter = ledger(tmp_path)
    sdk = SDK(unresolved={"epoch-1-tool-000-01"})
    transport, _ = scripted([[call("a"), call("b"), call("c")]])
    result = epoch(meter, sdk, transport)
    assert result["status"] == "RECONCILIATION_REQUIRED"
    assert result["tool"] == "epoch-1-tool-000-01"
    assert len(sdk.dispatched) == 2
    journal = json.loads(
        (folder(meter) / "epoch-1-provider-000-not-run.json").read_bytes()
    )
    assert [c["call_id"] for c in journal["not_run"]] == ["c"]


def test_a_turn_cannot_overspend_the_trial_ceiling(tmp_path, monkeypatch):
    """The trial count is re-read before every numerical call: with two slots
    left, a turn of three trials runs two, and run_julia counts like practice
    and run_python."""
    monkeypatch.setattr(research_loop, "MAX_RESEARCH_TRIALS", 2)
    meter = ledger(tmp_path)
    sdk = SDK(meter)
    trials = [
        call("p", START, {"kind": "practice"}),
        call("py", START, {"kind": "workspace", "action": "run_python"}),
        call("jl", START, {"kind": "workspace", "action": "run_julia"}),
    ]
    transport, requests = scripted([trials, [text()]])
    epoch(meter, sdk, transport)
    assert len(sdk.dispatched) == 2
    answered = dict(outputs(requests[1]))
    assert answered["jl"]["status"] == "UNAVAILABLE"
    assert "trial ceiling" in answered["jl"]["reason"]
    assert meter.status(owner="alice")["used"]["research_trials"] == 2


@pytest.mark.parametrize("rule", [None, PARALLEL_CALLS, PARALLEL_CALLS_V2])
def test_run_julia_spends_a_slot_under_every_rule(tmp_path, monkeypatch, rule):
    """`run_julia` is charged a research-trial slot by the executor under
    every rule, so the loop's ceiling counts it under every rule too."""
    monkeypatch.setattr(research_loop, "MAX_RESEARCH_TRIALS", 1)
    meter = ledger(tmp_path)
    sdk = SDK(meter)
    transport, requests = scripted(
        [
            [call("p", START, {"kind": "practice"})],
            [call("jl", START, {"kind": "workspace", "action": "run_julia"})],
            [text()],
        ]
    )
    epoch(meter, sdk, transport, rule=rule)
    assert [name for name, _ in sdk.dispatched] == [START]
    assert dict(outputs(requests[2]))["jl"]["status"] == "UNAVAILABLE"


def test_the_agent_sees_its_budget_before_every_turn(tmp_path, monkeypatch):
    monkeypatch.setattr(research_loop, "MAX_PROVIDER_CALLS", 3)
    meter = ledger(tmp_path)
    transport, requests = scripted([[call("a")], [call("b")], [text()]])
    epoch(meter, SDK(), transport)
    notes = [request["input"][-1] for request in requests]
    assert all(note["role"] == "user" for note in notes)
    assert notes[0]["content"] == (
        "Carbon status before this turn: 3 of 3 model calls left in this epoch, "
        "counting this turn; 8 of 8 research-trial slots left."
    )
    assert "Notice" not in notes[0]["content"]
    # With two calls left the agent is told to finish, and how.
    assert "Notice: only 2 model calls left, counting this turn." in notes[1]["content"]
    assert "Select a practiced recipe now" in notes[1]["content"]
    assert "Notice: only 1 model call left" in notes[2]["content"]
    # Journalled before the request, so a replay sends the same requests: the
    # ledger refuses a changed request under a used identity.
    status = json.loads(
        (folder(meter) / "epoch-1-provider-001-status.json").read_bytes()
    )
    assert (status["model_calls_left"], status["trial_slots_left"]) == (2, 8)
    first = json.loads((folder(meter) / "outcome.json").read_bytes())
    (folder(meter) / "outcome.json").unlink()
    assert epoch(meter, SDK(), never) == first


def test_the_status_counts_the_slots_spent(tmp_path):
    meter = ledger(tmp_path)
    transport, requests = scripted([[call("p", START, {"kind": "practice"})], [text()]])
    epoch(meter, SDK(meter), transport)
    assert "7 of 8 research-trial slots left" in requests[1]["input"][-1]["content"]


def test_no_budget_note_under_v1_or_the_historical_rule(tmp_path):
    for n, rule in enumerate((None, PARALLEL_CALLS)):
        transport, requests = scripted([[text()]])
        epoch(ledger(tmp_path / str(n)), SDK(), transport, rule=rule)
        assert requests[0]["input"] == [{"role": "user", "content": '{"fixture":true}'}]
        assert requests[0]["parallel_tool_calls"] is False


def test_any_tool_call_renews_the_free_text_reminder(tmp_path):
    meter = ledger(tmp_path)
    turns = [[text()], [call("a")], [text()], [call("b")], [text()], [text()]]
    transport, requests = scripted(turns)
    result = epoch(meter, SDK(), transport, agent_policy=AUTONOMOUS)
    assert result["reason"] == "unstructured agent stop after one clarification"
    assert len(requests) == 6
    assert len(list(folder(meter).glob("*-continuation.json"))) == 3


def test_the_historical_reminder_is_not_renewed(tmp_path):
    transport, requests = scripted([[text()], [call("a")], [text()]])
    result = epoch(
        ledger(tmp_path), SDK(), transport, rule=None, agent_policy=AUTONOMOUS
    )
    assert result["reason"] == "unstructured agent stop after one clarification"
    assert len(requests) == 3


def test_a_selection_needs_a_practiced_recipe(tmp_path):
    """Carbon's own agent: an unpracticed selection is refused with the
    practiced recipes listed and the epoch goes on; once the recipe is
    practiced the same selection is accepted."""
    meter = ledger(tmp_path)
    sdk = SDK(meter, practiced=True)
    transport, requests = scripted(
        [
            [select("s1")],
            [call("p", START, {"kind": "practice", "recipe": STRATEGY})],
            [select("s2")],
        ]
    )
    result = epoch(meter, sdk, transport)
    refused = dict(outputs(requests[1]))["s1"]
    assert refused["status"] == "REJECTED_BEFORE_DISPATCH"
    assert refused["code"] == SELECTION_NOT_PRACTICED
    assert refused["field"] == "strategy_json"
    # No results table yet: nothing is practiced, said so, not assumed.
    assert refused["practiced_recipes"] == [] and refused["practiced_recipe_count"] == 0
    assert result["status"] == "SELECTED" and result["strategy"] == STRATEGY
    selected = json.loads((folder(meter) / "selected-recipe.json").read_bytes())
    assert selected["strategy"] == STRATEGY


def test_a_refused_selection_lists_the_practiced_recipes(tmp_path):
    meter = ledger(tmp_path)
    other = {**STRATEGY, "parameters": {"steps": 256, "enforce_mean": True}}
    record_practice(meter, other)
    record_practice(meter, other)  # listed once
    record_practice(meter, STRATEGY, provenance="NOT_A_PRACTICE")
    transport, requests = scripted([[select("s")], [text()]])
    epoch(meter, SDK(), transport)
    refused = dict(outputs(requests[1]))["s"]
    assert refused["code"] == SELECTION_NOT_PRACTICED
    assert refused["practiced_recipes"] == [other]
    assert refused["practiced_recipe_count"] == 1


def test_a_role_owns_what_its_selection_means(tmp_path):
    """A caller's own role (Graphite) selects under its own evidence rule: the
    loop's practice requirement is for Carbon's own agent."""
    from carbon.development_session.research_loop import SELECTION_TOOL

    meter = ledger(tmp_path)
    transport, _ = scripted([[select("s")]])
    result = epoch(
        meter,
        SDK(),
        transport,
        instructions="Synthetic role.",
        tools=[SELECTION_TOOL],
    )
    assert result["status"] == "SELECTED"


def test_the_v2_plan_states_the_v2_prompt(tmp_path):
    from carbon.battery.challenge import CHALLENGE

    meter = ledger(tmp_path)
    transport, _ = scripted([[stop("s")]])
    epoch(meter, SDK(), transport, agent_policy=AUTONOMOUS, challenge=CHALLENGE)
    plan = json.loads((folder(meter) / "plan.json").read_bytes())
    expected = prompt_for(AUTONOMOUS, CHALLENGE, PARALLEL_CALLS_V2)
    assert plan["prompt"] == expected
    assert plan["agent_policy"]["prompt_digest"] == digest(expected.encode())


def test_an_unknown_rule_is_refused_before_anything_runs(tmp_path):
    with pytest.raises(ValueError, match="unknown parallel tool call rule"):
        epoch(ledger(tmp_path), SDK(), never, rule={**PARALLEL_CALLS_V2, "extra": 1})
