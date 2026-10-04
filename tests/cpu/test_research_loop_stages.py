"""Stages, a caller's finish tool and the Graphite miner policy
(OWNER-GRAPHITE-MINER-01).

A stage namespaces a session inside its epoch, so the miner edition's
research and build sessions share one epoch without sharing an identity. A
finish tool is a role's own local terminal tool (the Planner's
`graphite_record_plan`), computed before its intent like the selection. The
Graphite miner policy runs a role's own instructions and tools with a
Challenge under the rules Carbon's autonomous agent has. Each default
reproduces today's plans byte for byte (`test_research_loop_limits`).

Deterministic Responses mocks test control flow, never agent evidence.
"""

import json

import pytest
from test_cw1_research_ledger import ledger
from test_cw1_research_loop import response
from test_parallel_tool_calls_v2 import record_practice
from test_research_loop_limits import (
    INFO,
    INFO_TOOL,
    LIMITS_V2,
    ROOMY,
    SDK,
    START,
    START_TOOL,
    STRATEGY,
    ShareLedger,
    call,
    epoch,
    forever,
    never,
    post,
    role,
    scripted,
    select,
    stop,
    text,
)

from carbon.development_session import miner_guidance as guidance
from carbon.development_session import model_provider as mp
from carbon.development_session import research_loop
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_agent_policy import (
    AUTONOMOUS,
    GRAPHITE_MINER,
    PARALLEL_CALLS,
    STOP_TOOL,
    graphite_miner_prompt,
    graphite_miner_reminder,
    limits_v2,
)
from carbon.development_session.research_loop import (
    FINISH_INVALID,
    MINER_CEILING_REACHED,
    SELECTION_NOT_PRACTICED,
    SELECTION_TOOL,
    CeilingReached,
    MinerCeilings,
    guidance_cursor,
    guidance_delivered,
    miner_ceiling,
    session_turns,
    tool_identity,
)

RECORD = "graphite_record_plan"
RECORD_TOOL = {
    "type": "function",
    "name": RECORD,
    "strict": True,
    "description": "Record the ranked plan and finish this session.",
    "parameters": {
        "type": "object",
        "properties": {"plan_json": {"type": "string"}},
        "required": ["plan_json"],
        "additionalProperties": False,
    },
}


def planner_finish(seen=None):
    """A finish tool whose validator accepts a plan with hypotheses and
    refuses any other with its own typed refusal."""

    def validate(arguments):
        if seen is not None:
            seen.append(arguments)
        plan = json.loads(arguments.get("plan_json") or "null")
        if type(plan) is dict and plan.get("hypotheses"):
            return True, None
        return False, {
            "status": "REJECTED_BEFORE_DISPATCH",
            "code": "plan_invalid",
            "field": "plan_json",
            "authority_granted": False,
        }

    return {"tool": RECORD_TOOL, "validate": validate, "status": "PLANNED"}


def record_plan(identity, plan):
    return call(identity, RECORD, {"plan_json": json.dumps(plan)})


PLAN = {"hypotheses": [{"hypothesis": "wider modes", "cites": []}]}


def folder(meter, stage=None, epoch_=1):
    root = meter.root / f"epoch-{epoch_}"
    return root if stage is None else root / stage


def outputs(request):
    return {
        item["call_id"]: json.loads(item["output"])
        for item in request["input"]
        if item.get("type") == "function_call_output"
    }


# -- stages ---------------------------------------------------------------------


def _two_stages(meter):
    research, _ = scripted([[call("a", INFO)], [record_plan("r", PLAN)]])
    first = role(
        meter,
        research,
        tools=(INFO_TOOL,),
        stage="research",
        finish=planner_finish(),
        limits=LIMITS_V2,
    )
    build, _ = scripted([[call("b", INFO)], [select("s")]])
    second = role(meter, build, stage="build", limits=LIMITS_V2)
    return first, second


def test_two_stages_share_one_epoch_under_their_own_identities(tmp_path):
    meter = ledger(tmp_path, ceilings=ROOMY)
    first, second = _two_stages(meter)
    assert first["status"] == "PLANNED" and first["stage"] == "research"
    assert second["status"] == "SELECTED" and second["stage"] == "build"
    for stage, report in (("research", first), ("build", second)):
        root = folder(meter, stage)
        plan = json.loads((root / "plan.json").read_bytes())
        assert plan["stage"] == stage
        assert (root / f"epoch-1-{stage}-provider-000-turn.json").exists()
        assert (root / f"epoch-1-{stage}-tool-000-intent.json").exists()
        # Each report counts only its own session's turns.
        assert [t["turn"] for t in report["provider_turns"]] == [
            f"epoch-1-{stage}-provider-000",
            f"epoch-1-{stage}-provider-001",
        ]
    assert (folder(meter, "build") / "selected-recipe.json").exists()
    assert not (folder(meter) / "selected-recipe.json").exists()
    # A stage starts without spending the epoch's unit.
    status = meter.status(owner="alice")
    assert status["used"]["epochs"] == 0
    starts = {
        op["id"]: op["reservation"]
        for op in status["operations"]
        if op["id"].startswith("research-")
    }
    assert starts == {"research-epoch-1-research": {}, "research-epoch-1-build": {}}
    # Each replays from its own journal with no provider call; an outcome's
    # accounting is the whole campaign's when it is written, as an epoch's is.
    for stage, report in (("research", first), ("build", second)):
        (folder(meter, stage) / "outcome.json").unlink()
    research, build = _replays(meter)
    assert build == second
    assert {**research, "accounting": None} == {**first, "accounting": None}


def _replays(meter):
    first = role(
        meter,
        never,
        tools=(INFO_TOOL,),
        stage="research",
        finish=planner_finish(),
        limits=LIMITS_V2,
    )
    second = role(meter, never, stage="build", limits=LIMITS_V2)
    return first, second


def test_the_stage_namespace_mutation_is_caught(tmp_path, monkeypatch):
    """Specimen: with the stage dropped from its identities, the test above
    fails - the second session of an epoch collides with the first."""
    monkeypatch.setattr(
        research_loop, "session_prefix", lambda epoch, stage=None: f"epoch-{epoch}"
    )
    with pytest.raises(ValueError, match="conflict"):
        test_two_stages_share_one_epoch_under_their_own_identities(tmp_path)


def test_an_unstaged_epoch_reads_only_its_own_turns(tmp_path):
    meter = ledger(tmp_path, ceilings=ROOMY)
    role(
        meter,
        scripted([[record_plan("r", PLAN)]])[0],
        tools=(INFO_TOOL,),
        stage="research",
        finish=planner_finish(),
        limits=LIMITS_V2,
    )
    report = epoch(meter, scripted([[call("a")], [text()]])[0])
    assert [t["turn"] for t in report["provider_turns"]] == [
        "epoch-1-provider-000",
        "epoch-1-provider-001",
    ]
    assert meter.status(owner="alice")["used"]["epochs"] == 1
    turns = [
        {"turn": name}
        for name in (
            "epoch-1-provider-000",
            "epoch-1-provider-000-rl1",
            "epoch-1-compact-003",
            "epoch-1-research-provider-000",
            "epoch-1-research-compact-003",
            "epoch-1-research_x-provider-000",
            "epoch-10-provider-000",
            "epoch-2-provider-000",
        )
    ]
    assert [t["turn"] for t in session_turns(turns, 1)] == [
        "epoch-1-provider-000",
        "epoch-1-provider-000-rl1",
        "epoch-1-compact-003",
    ]
    assert [t["turn"] for t in session_turns(turns, 1, "research")] == [
        "epoch-1-research-provider-000",
        "epoch-1-research-compact-003",
    ]


def test_stage_names_are_closed(tmp_path):
    for n, bad in enumerate(
        ("", "Research", "re-search", "provider", "tool", "compact", "x" * 33, 7)
    ):
        meter = ledger(tmp_path / str(n))
        with pytest.raises(ValueError, match="a stage is"):
            role(meter, never, stage=bad)
        assert not (meter.root / "epoch-1").exists()
    assert tool_identity(1, 2) == "epoch-1-tool-002"
    assert tool_identity(1, 2, 1, "build") == "epoch-1-build-tool-002-01"


# -- a caller's finish tool -------------------------------------------------------


def test_a_finish_tool_ends_the_session_with_its_arguments(tmp_path):
    meter = ledger(tmp_path, ceilings=ROOMY)
    seen = []
    transport, requests = scripted(
        [[record_plan("bad", {"hypotheses": []})], [record_plan("ok", PLAN)]]
    )
    report = role(meter, transport, tools=(INFO_TOOL,), finish=planner_finish(seen))
    # The validator's own refusal reaches the model; the session goes on.
    refused = outputs(requests[1])["bad"]
    assert refused["code"] == "plan_invalid"
    assert report["status"] == "PLANNED"
    assert report["tool"] == RECORD
    assert json.loads(report["arguments"]["plan_json"]) == PLAN
    assert report["final_evidence"] is False
    # Offered, recorded in the plan, journalled before and after like a call.
    plan = json.loads((folder(meter) / "plan.json").read_bytes())
    assert plan["finish"] == {"tool": RECORD, "status": "PLANNED"}
    assert RECORD_TOOL in plan["tools"]
    assert (folder(meter) / "epoch-1-tool-001-intent.json").exists()
    assert len(seen) == 2
    # A replay reads the journal: the validator is not asked again.
    (folder(meter) / "outcome.json").unlink()
    again = role(meter, never, tools=(INFO_TOOL,), finish=planner_finish(seen))
    assert again == report and len(seen) == 2


def test_the_notice_to_finish_names_the_finish_tool(tmp_path):
    for n, limits in enumerate((None, limits_v2(calls_per_epoch=2))):
        meter = ledger(tmp_path / str(n), ceilings=ROOMY)
        transport, requests = scripted([[record_plan("ok", PLAN)]])
        role(
            meter,
            transport,
            tools=(INFO_TOOL,),
            finish=planner_finish(),
            limits=limits,
            max_provider_calls=None if limits else 2,
        )
        assert "Finish with graphite_record_plan now" in (
            requests[0]["input"][-1]["content"]
        )


def test_a_finish_refusal_without_its_own_record_is_typed(tmp_path):
    finish = {
        "tool": RECORD_TOOL,
        "validate": lambda arguments: (False, None),
        "status": "PLANNED",
    }
    transport, requests = scripted([[record_plan("x", PLAN)], [text()]])
    role(ledger(tmp_path), transport, tools=(INFO_TOOL,), finish=finish)
    assert outputs(requests[1])["x"]["code"] == FINISH_INVALID


def test_a_finish_is_checked_before_anything_runs(tmp_path):
    good = planner_finish()
    for n, bad in enumerate(
        (
            {**good, "extra": 1},
            {**good, "status": "SELECTED"},
            {**good, "status": "planned"},
            {**good, "validate": None},
            {**good, "tool": {**RECORD_TOOL, "name": "carbon_autoresearch_stop"}},
            {**good, "tool": {**RECORD_TOOL, "type": "hosted"}},
        )
    ):
        meter = ledger(tmp_path / str(n))
        with pytest.raises((ValueError, TypeError)):
            role(meter, never, tools=(INFO_TOOL,), finish=bad)
        assert not (meter.root / "epoch-1").exists()
    with pytest.raises(ValueError, match="only a role's session takes finish"):
        epoch(ledger(tmp_path / "no-role"), never, finish=good)
    # A role tool by the finish tool's name must be that tool exactly.
    with pytest.raises(ValueError, match="differs"):
        role(
            ledger(tmp_path / "clash"),
            never,
            tools=(INFO_TOOL, {**RECORD_TOOL, "description": "other"}),
            finish=good,
        )


def test_a_finish_validator_that_raises_is_answered_and_the_session_goes_on(
    tmp_path,
):
    """Review regression: the Planner's validator reads model-written
    arguments after the reply is journalled. Malformed plan_json makes it
    raise; that is answered `finish_invalid` naming the exception, never
    raised, so the session goes on and every resume replays it."""
    meter = ledger(tmp_path, ceilings=ROOMY)
    seen = []
    bad = call("bad", RECORD, {"plan_json": "{bad"})
    transport, requests = scripted([[bad], [record_plan("ok", PLAN)]])
    report = role(meter, transport, tools=(INFO_TOOL,), finish=planner_finish(seen))
    refused = outputs(requests[1])["bad"]
    assert refused["status"] == "REJECTED_BEFORE_DISPATCH"
    assert refused["code"] == FINISH_INVALID
    assert refused["reason"] == (
        f"{RECORD} could not read these arguments (JSONDecodeError)"
    )
    assert report["status"] == "PLANNED" and len(seen) == 2
    # A resume reads the journal; nothing is raised again or re-asked.
    (folder(meter) / "outcome.json").unlink()
    again = role(meter, never, tools=(INFO_TOOL,), finish=planner_finish(seen))
    assert again == report and len(seen) == 2


@pytest.mark.parametrize(
    "verdict",
    [
        True,
        (1, None),
        (False, {"status": "PLANNED"}),
        (False, {"status": "REJECTED_BEFORE_DISPATCH", "x": float("nan")}),
    ],
)
def test_a_finish_validator_out_of_contract_is_answered_not_raised(tmp_path, verdict):
    """A verdict outside `(ok, refusal)`, or a refusal that is not a JSON
    REJECTED_BEFORE_DISPATCH record, is the caller's fault: the model is
    told so (`checked: false`) and the session goes on."""
    finish = {"tool": RECORD_TOOL, "validate": lambda a: verdict, "status": "PLANNED"}
    transport, requests = scripted([[record_plan("x", PLAN)], [text()], [text()]])
    report = role(ledger(tmp_path), transport, tools=(INFO_TOOL,), finish=finish)
    refused = outputs(requests[1])["x"]
    assert refused["code"] == FINISH_INVALID and refused["checked"] is False
    assert "not a fault in your arguments" in refused["reason"]
    assert report["status"] == "STOPPED"


def test_only_the_finish_tool_ends_the_session_with_its_status(tmp_path):
    """Review: a result of another tool that happens to carry the finish
    status does not end the session; only the finish tool's own does."""

    class Planned(SDK):
        async def call(self, name, arguments, identity):
            await super().call(name, arguments, identity)
            return {"status": "PLANNED", "authority_granted": False}

    meter = ledger(tmp_path, ceilings=ROOMY)
    transport, requests = scripted([[call("a", INFO)], [record_plan("ok", PLAN)]])
    report = role(
        meter, transport, Planned(meter), tools=(INFO_TOOL,), finish=planner_finish()
    )
    assert outputs(requests[1])["a"]["status"] == "PLANNED"
    assert len(requests) == 2
    assert report["status"] == "PLANNED" and report["tool"] == RECORD


# -- the Graphite miner policy ------------------------------------------------------


def miner(meter, transport, sdk=None, **extra):
    from carbon.battery.challenge import CHALLENGE

    return role(
        meter,
        transport,
        sdk,
        tools=extra.pop("tools", (INFO_TOOL, START_TOOL, SELECTION_TOOL, STOP_TOOL)),
        instructions=extra.pop("instructions", "Synthetic constructor role."),
        agent_policy=GRAPHITE_MINER,
        challenge=extra.pop("challenge", CHALLENGE),
        limits=extra.pop("limits", LIMITS_V2),
        **extra,
    )


def test_a_miner_role_runs_its_instructions_with_a_challenge(tmp_path):
    from carbon.battery.challenge import CHALLENGE

    meter = ledger(tmp_path, ceilings=ROOMY)
    transport, requests = scripted([[call("a", INFO)], [stop()]])
    report = miner(meter, transport)
    assert report["status"] == "STOPPED"
    assert report["reason"] == "agent reported no_feasible_action"
    plan = json.loads((folder(meter) / "plan.json").read_bytes())
    prompt = graphite_miner_prompt(
        "Synthetic constructor role.", limits=LIMITS_V2, select=True, stop=True
    )
    assert plan["prompt"] == prompt == requests[0]["instructions"]
    assert prompt.startswith("Synthetic constructor role.\nOperating rules.")
    policy = plan["agent_policy"]
    assert policy["version"] == GRAPHITE_MINER
    assert policy["challenge"] == {
        "id": CHALLENGE.challenge_id,
        "version": CHALLENGE.version,
    }
    assert policy["prompt_digest"] == digest(prompt.encode())
    assert policy["instructions_digest"] == digest(b"Synthetic constructor role.")
    assert policy["free_text_reminders"] == 1
    # A Challenge result reaches the model as model_view shows it; the
    # retained result keeps everything.
    seen = outputs(requests[1])["a"]
    assert "immutable_bindings" not in seen and seen["status"] == "OK"
    retained = json.loads((folder(meter) / "epoch-1-tool-000-result.json").read_bytes())
    assert "immutable_bindings" in retained


def test_a_miner_selection_needs_a_practiced_recipe(tmp_path):
    meter = ledger(tmp_path, ceilings=ROOMY)

    class Practising(SDK):
        async def call(self, name, arguments, identity):
            result = await super().call(name, arguments, identity)
            if name == START:
                record_practice(meter, json.loads(arguments["strategy_json"]))
            return result

    practice = {"kind": "practice", "strategy_json": json.dumps(STRATEGY)}
    transport, requests = scripted(
        [[select("s1")], [call("p", START, practice)], [select("s2")]]
    )
    report = miner(meter, transport, Practising(meter))
    assert len(requests) == 3, "an unpracticed selection ended the session"
    refused = outputs(requests[1])["s1"]
    assert refused["code"] == SELECTION_NOT_PRACTICED
    assert report["status"] == "SELECTED" and report["strategy"] == STRATEGY


def test_the_practice_check_mutation_is_caught(tmp_path, monkeypatch):
    """Specimen: with the practice check made a no-op, the test above
    fails - a miner role selects a recipe it never practised."""
    monkeypatch.setattr(research_loop, "practice_check", lambda ledger, owner: None)
    with pytest.raises(AssertionError, match="unpracticed selection ended"):
        test_a_miner_selection_needs_a_practiced_recipe(tmp_path)


def test_a_miner_role_states_its_call_cap_in_limits(tmp_path):
    """Review regression: a miner role's prompt states its call cap from the
    limits rule, so a cap passed any other way is refused before anything is
    written - the prompt can never state 48 while the loop enforces 150."""
    meter = ledger(tmp_path, ceilings=ROOMY)
    with pytest.raises(ValueError, match="sets its call cap in limits"):
        miner(meter, never, limits=None, max_provider_calls=150)
    assert not folder(meter).exists()
    transport, requests = scripted([[stop()]])
    miner(meter, transport, limits=limits_v2(calls_per_epoch=150))
    plan = json.loads((folder(meter) / "plan.json").read_bytes())
    assert plan["max_provider_calls"] == 150
    assert "This session also allows at most 150 model calls" in plan["prompt"]
    assert "150 of 150 model calls left" in requests[0]["input"][-1]["content"]


def test_a_miner_role_is_reminded_once_per_tool_call(tmp_path):
    meter = ledger(tmp_path, ceilings=ROOMY)
    turns = [[text()], [call("a", INFO)], [text()], [text()]]
    transport, requests = scripted(turns)
    report = miner(meter, transport, finish=planner_finish(), tools=(INFO_TOOL,))
    assert report["reason"] == "unstructured agent stop after one clarification"
    reminders = [
        json.loads(path.read_bytes())["message"]["content"]
        for path in sorted(folder(meter).glob("*-continuation.json"))
    ]
    expected = graphite_miner_reminder(finish=RECORD)
    assert reminders == [expected, expected]
    assert "select a practiced recipe" not in expected and RECORD in expected
    plan = json.loads((folder(meter) / "plan.json").read_bytes())
    assert plan["agent_policy"]["reminder_digest"] == digest(expected.encode())
    assert len(requests) == 4


def test_the_miner_policy_is_a_closed_role_under_v2(tmp_path):
    with pytest.raises(ValueError, match="role's instructions"):
        epoch(ledger(tmp_path / "a"), never, agent_policy=GRAPHITE_MINER)
    with pytest.raises(ValueError, match="PARALLEL_CALLS_V2"):
        miner(ledger(tmp_path / "b"), never, parallel_calls=PARALLEL_CALLS)
    # Role instructions still run under no other policy.
    with pytest.raises(ValueError, match="legacy policy"):
        role(ledger(tmp_path / "c"), never, agent_policy=AUTONOMOUS)


def test_a_miner_role_reads_the_miners_messages_across_stages(tmp_path):
    """The miner's messages reach a miner role at each step; a later stage
    does not re-read what an earlier one read, carries it forward, and the
    agent may reply to it."""
    meter = ledger(tmp_path, ceilings=ROOMY)
    post(meter, "Look at spectral methods first.")
    research, research_requests = scripted([[record_plan("r", PLAN)]])
    miner(
        meter,
        research,
        tools=(INFO_TOOL,),
        stage="research",
        finish=planner_finish(),
        miner_guidance=guidance.RULE,
    )
    entries = [
        json.loads(item["content"])["miner_guidance"]
        for item in research_requests[0]["input"]
        if item.get("role") == "user" and "miner_guidance" in item["content"]
    ]
    assert [m["text"] for m in entries[0]["messages"]] == [
        "Look at spectral methods first."
    ]
    sequence = entries[0]["messages"][0]["sequence"]
    assert guidance_cursor(meter.root) == sequence
    # The unstaged cursor alone never sees a staged record.
    assert guidance.cursor(meter.root) == 0
    reply = call("re", guidance.REPLY, {"reply_to": sequence, "text": "Will do."})
    build, build_requests = scripted([[reply], [stop()]])
    report = miner(meter, build, stage="build", miner_guidance=guidance.RULE)
    entries = [
        json.loads(item["content"])["miner_guidance"]
        for item in build_requests[0]["input"]
        if item.get("role") == "user" and "miner_guidance" in item["content"]
    ]
    assert entries[0]["messages"] == []
    carried = entries[0]["carried_forward"]["messages"]
    assert [m["text"] for m in carried] == ["Look at spectral methods first."]
    assert outputs(build_requests[1])["re"]["status"] == "REPLIED"
    assert guidance_delivered(meter.root) == {sequence}
    assert report["miner_guidance"]["carried"] == [sequence]
    assert report["miner_guidance"]["read"] == []


def test_a_miner_role_offers_the_reply_tool_with_the_rule(tmp_path):
    meter = ledger(tmp_path, ceilings=ROOMY)
    miner(meter, scripted([[stop()]])[0], miner_guidance=guidance.RULE)
    plan = json.loads((folder(meter) / "plan.json").read_bytes())
    assert guidance.REPLY_TOOL in plan["tools"]
    assert plan["miner_guidance"] == guidance.RULE
    assert canonical(plan["tools"][-1]) == canonical(guidance.REPLY_TOOL)


# -- the miner's own ceilings end a miner session, typed -----------------------


def test_a_miner_session_ends_typed_at_its_own_provider_call_ceiling(tmp_path):
    """Integration regression (journey 8e): with no call cap a miner session
    runs until the miner's own provider-call ceiling refuses its next model
    call, and that is its normal end - STOPPED `miner_ceiling_reached`,
    journalled, never raised. Raised, it left the campaign INTERRUPTED,
    telling the miner to resume into the same refusal."""
    meter = ledger(tmp_path, ceilings={**ROOMY, "provider_attempts": 5})
    transport, requests = forever()
    report = miner(meter, transport)
    assert report["status"] == "STOPPED"
    assert report["code"] == MINER_CEILING_REACHED
    assert report["dimension"] == "provider_attempts"
    assert "nothing of it was reserved or sent" in report["reason"]
    assert len(requests) == 5
    # The refused call holds nothing in the ledger.
    status = meter.status(owner="alice")
    assert status["used"]["provider_attempts"] == 5
    assert not [
        op for op in status["operations"] if op["id"].startswith("epoch-1-provider-005")
    ]
    assert json.loads((folder(meter) / "outcome.json").read_bytes()) == report
    # A resume replays the five calls, meets the same refusal and calls nothing.
    (folder(meter) / "outcome.json").unlink()
    assert miner(meter, never) == report


def test_the_miner_ceiling_mutation_is_caught(tmp_path, monkeypatch):
    """Specimen: with the miner's ceiling read as an ordinary refusal, the
    test above fails - the session raises the ledger's refusal instead of
    ending typed."""
    monkeypatch.setattr(research_loop, "miner_ceiling", lambda *a, **k: None)
    with pytest.raises(ValueError, match="miner budget: provider_attempts"):
        test_a_miner_session_ends_typed_at_its_own_provider_call_ceiling(tmp_path)


def test_a_miner_session_ends_typed_at_its_own_money_ceiling(tmp_path):
    reservation = mp.DEFAULT_SELECTION.reservation_nano
    # Room for one call's reservation; the booked call leaves too little.
    meter = ledger(
        tmp_path, ceilings={**ROOMY, "provider_nanodollars": reservation + 1}
    )
    transport, requests = forever()
    report = miner(meter, transport)
    assert (report["status"], report["code"], report["dimension"]) == (
        "STOPPED",
        MINER_CEILING_REACHED,
        "provider_nanodollars",
    )
    assert len(requests) == 1


def test_a_miner_session_ends_typed_when_its_time_cannot_hold_a_call(tmp_path):
    """The campaign's elapsed time is the miner's ceiling too: a call whose
    provider timeout no longer fits is refused before its reservation."""
    timeout = mp.DEFAULT_SELECTION.settings.timeout_seconds
    now = [1000.0]
    meter = ledger(
        tmp_path,
        clock=lambda: now[0],
        ceilings=ROOMY,
        elapsed_seconds=timeout + 250,
    )
    requests = []

    def slow(request):
        # Each reply takes 100 seconds of the campaign's time.
        requests.append(request)
        now[0] += 100
        return response([call(f"c{len(requests)}", INFO)])

    report = miner(meter, slow)
    assert (report["status"], report["code"], report["dimension"]) == (
        "STOPPED",
        MINER_CEILING_REACHED,
        "elapsed_seconds",
    )
    # Started at 1000 with 250 s beyond one timeout: the fourth call, at
    # 1300, could not finish by 1000 + timeout + 250.
    assert len(requests) == 3
    assert meter.status(owner="alice")["used"]["provider_attempts"] == 3
    (folder(meter) / "outcome.json").unlink()
    assert miner(meter, never) == report


def test_a_stage_ledgers_own_typed_refusal_keeps_its_code(tmp_path):
    """The research share's typed refusal is the stage ledger's, not the
    miner's ceiling: it ends a miner session with its own code."""
    ledger(tmp_path, ceilings=ROOMY)
    meter = ShareLedger(tmp_path, clock=lambda: 1000)
    report = miner(meter, forever()[0])
    assert report["code"] == "research_share_reached"


def test_outside_the_miner_policy_a_ceiling_refusal_still_propagates(tmp_path):
    """A role that is not a miner's (internal Graphite, whose own ledger
    types the refusal as its run cap) keeps the ledger's refusal as it was."""
    meter = ledger(tmp_path, ceilings={**ROOMY, "provider_attempts": 2})
    with pytest.raises(ValueError, match="miner budget: provider_attempts"):
        role(meter, forever()[0], limits=LIMITS_V2)
    assert not (folder(meter) / "outcome.json").exists()


def test_a_refusal_after_the_reservation_is_not_a_ceiling_stop(tmp_path):
    """Only a refusal before anything of the call is recorded ends the
    session typed. One raised after its reservation (the storage check)
    leaves the call for reconciliation, as it always has."""
    meter = ledger(tmp_path, ceilings=ROOMY)

    def full(_bytes):
        raise ValueError("miner budget: retained_bytes")

    meter.check_storage = full
    with pytest.raises(ValueError, match="miner budget: retained_bytes"):
        miner(meter, never)
    assert not (folder(meter) / "outcome.json").exists()
    assert meter.operation_state("epoch-1-provider-000", owner="alice") == "RESERVED"


def test_a_tools_own_ceiling_refusal_is_not_a_session_stop(tmp_path):
    """A research trial's reservation is the tool's to refuse: the miner's
    ceiling is read only on a model call's reservation, never inside a tool
    dispatch, whose intent is already journalled."""
    meter = ledger(tmp_path, ceilings={**ROOMY, "research_trials": 0})
    practice = {"kind": "practice", "strategy_json": json.dumps(STRATEGY)}
    transport, _ = scripted([[call("p", START, practice)]])
    with pytest.raises(ValueError, match="miner budget: research_trials"):
        miner(meter, transport)
    assert not (folder(meter) / "outcome.json").exists()
    # Not even through the session's own ledger view: no model-call dimension.
    with pytest.raises(ValueError, match="miner budget: research_trials") as raised:
        MinerCeilings(meter).reserve(
            "fixture-trial",
            owner="alice",
            phase="research",
            request={},
            resources={"research_trials": 1},
        )
    assert type(raised.value) is ValueError


def test_only_the_ledgers_plain_ceiling_refusals_are_the_miners_ceiling():
    reached = miner_ceiling(
        ValueError("miner budget: provider_attempts"), reserving=True
    )
    assert type(reached) is CeilingReached
    assert (reached.code, reached.dimension) == (
        MINER_CEILING_REACHED,
        "provider_attempts",
    )
    timed = miner_ceiling(
        ValueError("provider timeout cannot fit remaining campaign time"),
        reserving=False,
    )
    assert (timed.code, timed.dimension) == (MINER_CEILING_REACHED, "elapsed_seconds")

    class RunCap(ValueError):
        """An internal run's own typed cap."""

    for error, reserving in (
        # Not raised by the reservation, so possibly after it.
        (ValueError("miner budget: provider_attempts"), False),
        (ValueError("provider timeout cannot fit remaining campaign time"), True),
        (RunCap("miner budget: provider_attempts"), True),
        (RuntimeError("miner budget: provider_attempts"), True),
        (ValueError("miner budget: not_a_dimension"), True),
        (ValueError("carbon service capacity: reference_invocations"), True),
        (ValueError("miner budget, sequence aggregate: provider_attempts"), True),
        (ValueError("provider timeout cannot fit remaining grant"), False),
        (ValueError("campaign elapsed-time exhausted or clock regressed"), False),
    ):
        assert miner_ceiling(error, reserving=reserving) is None, error
