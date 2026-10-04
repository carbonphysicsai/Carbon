"""Tunable limits for the research loop (OWNER-GRAPHITE-MINER-01, item 6).

Money and time are the limits, not call counts: under `LIMITS_V2` a session's
per-epoch model-call and research-trial caps are optional, and unset means
only the campaign ledger's own ceilings bind. A plan without the rule keeps
48 model calls and 8 trial slots exactly, and every default replays byte for
byte (`DEFAULT_PINS`).

Deterministic Responses mocks test control flow, never agent evidence.
"""

import asyncio
import json

import pytest
from test_cw1_research_ledger import DEVELOPMENT_CEILINGS, ledger
from test_cw1_research_loop import response

from carbon.development_session import miner_guidance as guidance
from carbon.development_session import model_provider as mp
from carbon.development_session import research_loop
from carbon.development_session.agent import MODEL
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_agent_policy import (
    AUTONOMOUS,
    LIMITS_V2,
    MAX_TUNABLE_CAP,
    PARALLEL_CALLS,
    PARALLEL_CALLS_V2,
    STOP,
    check_limits,
    limits_v2,
)
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_loop import (
    SELECT,
    SELECTION_TOOL,
    CeilingReached,
    run_epoch,
)
from carbon.development_session.research_tools import PREFIX, TOOLS

LIST = PREFIX + "list_public_material"
INFO = PREFIX + "get_challenge_info"
START = PREFIX + "start_research_task"
#: The Burgers fixture recipe the loop tests select; it compiles.
STRATEGY = {
    "schema_version": "1.0",
    "challenge_id": "burgers-dynamics-v1",
    "backbone": "fno",
    "parameters": {"steps": 512, "enforce_mean": True},
}
#: A role tool, as a closed Graphite role offers one.
INFO_TOOL = next(tool for tool in TOOLS if tool["name"] == INFO)
START_TOOL = next(tool for tool in TOOLS if tool["name"] == START)
#: Keyword arguments every `epoch` call in this module also passes; a test
#: sets them to show that passing a new parameter's default changes nothing.
EXTRA = {}
#: A campaign budget whose money never binds before its call ceiling.
ROOMY = {**DEVELOPMENT_CEILINGS, "provider_nanodollars": 10**13}


def call(identity, name=LIST, arguments=None, status=None):
    item = {
        "type": "function_call",
        "name": name,
        "call_id": identity,
        "arguments": json.dumps({} if arguments is None else arguments),
    }
    if status is not None:
        item["status"] = status
    return item


def text(words="Nothing further in this synthetic control."):
    return {
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": words}],
    }


def stop(identity="stop"):
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


def incomplete(output, model=MODEL):
    """A reply the provider cut off at its output limit."""
    return {
        **response(output),
        "model": model,
        "status": "incomplete",
        "incomplete_details": {"reason": "max_output_tokens"},
    }


class SDK:
    """Records every dispatched tool; a numerical task charges one research
    trial as the executor does. Each result repeats integrity metadata a
    Challenge campaign's model does not see (`model_view`)."""

    def __init__(self, meter=None, owner="alice"):
        self.meter, self.owner = meter, owner
        self.dispatched = []

    async def call(self, name, arguments, identity):
        self.dispatched.append((name, identity))
        if name == START and self.meter is not None:
            operation = "fixture-trial-" + identity
            self.meter.reserve(
                operation,
                owner=self.owner,
                phase="research",
                request=arguments,
                resources={"research_trials": 1},
            )
            self.meter.finish(
                operation,
                owner=self.owner,
                state="SUCCEEDED",
                actual={"research_trials": 1},
                result={"status": "FIXTURE_STARTED"},
            )
        return {
            "status": "OK",
            "fixture": True,
            "immutable_bindings": {"fixture": identity},
        }


def scripted(turns, between=None):
    """A transport replying with each scripted turn in order. A turn is a
    list of output items, or a whole response. Each request is kept as sent;
    `between[n]` runs during request n."""
    requests = []

    def transport(request):
        requests.append(json.loads(canonical(request)))
        if between and len(requests) - 1 in between:
            between[len(requests) - 1]()
        turn = turns[len(requests) - 1]
        return turn if type(turn) is dict else response(turn)

    return transport, requests


def post(meter, text_, when=1000):
    """A miner message exactly as the page's own route records it."""
    meter.note(
        owner="alice",
        kind="notebook",
        body={
            "schema": guidance.MESSAGE_SCHEMA,
            "note_kind": guidance.MESSAGE_KIND,
            "text": text_,
            "posted_unix": when,
            "digest": guidance.message_digest(text_, when),
        },
    )


def fixture_selection(max_output_tokens=1024):
    """A non-default model selection; its credential path is a fixture."""
    return mp.select(
        provider_id="openai-responses",
        model_id="gpt-4.1",
        credential={"kind": "file", "reference": "/fixture/not-a-credential"},
        settings={"reasoning_effort": None, "max_output_tokens": max_output_tokens},
    )


def epoch(meter, transport, sdk=None, **extra):
    return asyncio.run(
        run_epoch(
            meter,
            owner="alice",
            epoch=extra.pop("epoch", 1),
            sdk=SDK(meter) if sdk is None else sdk,
            credential_file=None,
            initial_observation=extra.pop("initial_observation", {"fixture": True}),
            transport=transport,
            **EXTRA,
            **extra,
        )
    )


def role(meter, transport, sdk=None, tools=(INFO_TOOL, SELECTION_TOOL), **extra):
    """A closed role's session under v2, as an internal Graphite role or a
    miner role runs."""
    return epoch(
        meter,
        transport,
        sdk,
        instructions=extra.pop("instructions", "Synthetic role."),
        tools=list(tools),
        parallel_calls=extra.pop("parallel_calls", PARALLEL_CALLS_V2),
        **extra,
    )


def forever(name=INFO):
    """A model that always calls one tool: only a cap or a ceiling ends it."""
    requests = []

    def transport(request):
        requests.append(request)
        return response([call(f"c{len(requests)}", name)])

    return transport, requests


def never(_request):
    raise AssertionError("a replay made a provider call")


def recorded(meter):
    """Every file the epoch and its model calls left under the campaign
    root, by relative path and digest; the SQLite ledger and the lease file
    aside (the outcome carries the ledger's accounting)."""
    return {
        str(path.relative_to(meter.root)): digest(path.read_bytes())
        for path in sorted(meter.root.rglob("*"))
        if path.is_file() and path.suffix == ".json"
    }


# -- every default reproduces today's plans, requests and journals ------------


def _legacy_none(tmp_path):
    meter = ledger(tmp_path)
    transport, requests = scripted([[call("a")], [text()]])
    epoch(meter, transport)
    return meter, requests


def _autonomous_v1(tmp_path):
    meter = ledger(tmp_path)
    transport, requests = scripted([[call("a"), call("b")], [text()], [text()]])
    epoch(meter, transport, agent_policy=AUTONOMOUS, parallel_calls=PARALLEL_CALLS)
    return meter, requests


def _challenge_v2(tmp_path):
    """Carbon's autonomous agent on a Challenge under v2 with the miner's
    messages: parallel calls, a cut reply, a refused unpracticed selection,
    a free-text reminder and a stop."""
    from carbon.battery.challenge import CHALLENGE

    meter = ledger(tmp_path)
    post(meter, "Spend this epoch on capacity.")
    transport, requests = scripted(
        [
            [call("a"), call("b")],
            incomplete([call("c", status="incomplete")]),
            [select("s1")],
            [text()],
            [stop()],
        ],
        between={1: lambda: post(meter, "Keep runs on CPU.")},
    )
    epoch(
        meter,
        transport,
        agent_policy=AUTONOMOUS,
        challenge=CHALLENGE,
        parallel_calls=PARALLEL_CALLS_V2,
        miner_guidance=guidance.RULE,
    )
    return meter, requests


def _graphite_role(tmp_path):
    """An internal Graphite role: its own prompt, closed tools, call cap and
    model selection, under v2."""
    meter = ledger(tmp_path)
    selection = fixture_selection()
    transport, requests = scripted(
        [
            {**response([call("a", INFO), call("b", INFO)]), "model": "gpt-4.1"},
            {**response([select("s")]), "model": "gpt-4.1"},
        ]
    )
    epoch(
        meter,
        transport,
        instructions="Synthetic role.",
        tools=[INFO_TOOL, SELECTION_TOOL],
        max_provider_calls=150,
        parallel_calls=PARALLEL_CALLS_V2,
        provider=selection,
    )
    return meter, requests


DEFAULT_SCENARIOS = {
    "legacy_no_rule": _legacy_none,
    "autonomous_v1": _autonomous_v1,
    "challenge_v2_guidance": _challenge_v2,
    "graphite_role_v2": _graphite_role,
}


def default_record(name, tmp_path):
    meter, requests = DEFAULT_SCENARIOS[name](tmp_path)
    return {
        "requests": [digest(canonical(r)) for r in requests],
        "files": recorded(meter),
    }


#: Each default scenario's requests and journals, computed on the Launchpad
#: wiring head (9bfd9add) before stages, finish tools, limits and compaction
#: existed. Frozen plans replay byte-identically, so these never change.
DEFAULT_PINS = {
    "legacy_no_rule": (
        "sha256:69dc5e3ddcd55295f064ab9cd4631f51c746d6764d352249e6673062b5a76404"
    ),
    "autonomous_v1": (
        "sha256:c93e6519d9a6d5d70ac9358e7dc19a74c4f6b09ab0853442c4435fa70f609eec"
    ),
    "challenge_v2_guidance": (
        "sha256:3d8f0cbb893aaa1dddfc4a210a080e1eaecab0e9d53207ae106a53b640047394"
    ),
    "graphite_role_v2": (
        "sha256:0e36a6555707672dc5095756ff15d8b288edff46202aa07aaf64d977a285e71b"
    ),
}
#: Passing every new parameter's default changes nothing.
NEW_DEFAULTS = {"stage": None, "finish": None, "limits": None, "compaction": None}


@pytest.mark.parametrize("name", sorted(DEFAULT_SCENARIOS))
def test_every_default_replays_byte_for_byte(tmp_path, monkeypatch, name):
    """No rule, v1, v2 with a Challenge and the miner's messages, and an
    internal Graphite role: the same requests, plans, identities, journals
    and outcomes as before, whether the new parameters are omitted or passed
    as None."""
    record = default_record(name, tmp_path / "omitted")
    assert digest(canonical(record)) == DEFAULT_PINS[name], record
    monkeypatch.setitem(globals(), "EXTRA", NEW_DEFAULTS)
    assert default_record(name, tmp_path / "explicit") == record


def test_a_plan_without_the_rule_keeps_48_calls_and_8_trials(tmp_path):
    meter = ledger(tmp_path)
    role(meter, scripted([[text()]])[0])
    plan = json.loads((meter.root / "epoch-1" / "plan.json").read_bytes())
    assert (plan["max_provider_calls"], plan["max_research_trials"]) == (48, 8)
    assert "limits" not in plan


def test_the_limits_rule_is_closed():
    assert LIMITS_V2 == {
        "schema": "carbon.autoresearch.limits.v2",
        "calls_per_epoch": None,
        "trials_per_epoch": None,
    }
    assert check_limits(LIMITS_V2) is LIMITS_V2
    assert limits_v2(60, 0) == {
        **LIMITS_V2,
        "calls_per_epoch": 60,
        "trials_per_epoch": 0,
    }
    for bad in (
        None,
        {**LIMITS_V2, "schema": "carbon.autoresearch.limits.v1"},
        {**LIMITS_V2, "extra": 1},
        {k: v for k, v in LIMITS_V2.items() if k != "trials_per_epoch"},
        {**LIMITS_V2, "calls_per_epoch": 0},
        {**LIMITS_V2, "calls_per_epoch": True},
        {**LIMITS_V2, "calls_per_epoch": 48.0},
        {**LIMITS_V2, "trials_per_epoch": -1},
        {**LIMITS_V2, "calls_per_epoch": MAX_TUNABLE_CAP + 1},
    ):
        with pytest.raises(ValueError):
            check_limits(bad)


def test_unset_caps_let_a_session_run_past_48_bounded_by_the_ledger(tmp_path):
    """OWNER-GRAPHITE-MINER-01, item 6: with no per-epoch cap the session runs
    past the historical 48 model calls, and the campaign's own provider-call
    ceiling ends it, refused by the ledger before anything is sent. Outside
    the miner policy the refusal propagates (a miner session ends typed:
    `test_research_loop_stages`)."""
    meter = ledger(tmp_path, ceilings={**ROOMY, "provider_attempts": 60})
    transport, requests = forever()
    with pytest.raises(ValueError, match="miner budget: provider_attempts"):
        role(meter, transport, limits=LIMITS_V2)
    assert len(requests) == 60
    assert meter.status(owner="alice")["used"]["provider_attempts"] == 60
    plan = json.loads((meter.root / "epoch-1" / "plan.json").read_bytes())
    assert plan["limits"] == LIMITS_V2
    assert (plan["max_provider_calls"], plan["max_research_trials"]) == (None, None)


def test_a_set_call_cap_binds(tmp_path):
    meter = ledger(tmp_path, ceilings=ROOMY)
    transport, requests = forever()
    report = role(meter, transport, limits=limits_v2(calls_per_epoch=5))
    assert report["status"] == "STOPPED"
    assert report["reason"] == "epoch provider-call ceiling"
    assert len(requests) == 5
    plan = json.loads((meter.root / "epoch-1" / "plan.json").read_bytes())
    assert plan["max_provider_calls"] == 5


def test_a_set_trial_cap_binds_and_an_unset_one_leaves_the_ledger(tmp_path):
    practice = {"kind": "practice", "strategy_json": json.dumps(STRATEGY)}
    turns = [[call("p1", START, practice)], [call("p2", START, practice)], [text()]]
    tools = (START_TOOL, SELECTION_TOOL)
    capped = ledger(tmp_path / "capped", ceilings=ROOMY)
    transport, requests = scripted(turns)
    role(capped, transport, tools=tools, limits=limits_v2(trials_per_epoch=1))
    answered = {
        item["call_id"]: json.loads(item["output"])
        for item in requests[2]["input"]
        if item.get("type") == "function_call_output"
    }
    assert answered["p2"]["status"] == "UNAVAILABLE"
    assert capped.status(owner="alice")["used"]["research_trials"] == 1
    # Unset: the loop refuses nothing; only the ledger's own ceiling binds.
    free = ledger(tmp_path / "free", ceilings=ROOMY)
    role(free, scripted(turns)[0], tools=tools, limits=LIMITS_V2)
    assert free.status(owner="alice")["used"]["research_trials"] == 2


def test_a_session_without_a_call_cap_needs_a_ledger_that_bounds_it(tmp_path):
    """The loop stays finite through the ledger: no call cap needs a finite
    provider_attempts ceiling, or a money ceiling with a priced selection.
    Refused before anything is written."""
    for name, ceilings, provider in (
        ("none", None, mp.DEFAULT_SELECTION),
        ("unpriced", {"provider_nanodollars": 10**12}, fixture_selection()),
    ):
        meter = ledger(tmp_path / name, ceilings=ceilings)
        with pytest.raises(ValueError, match="finite provider_attempts"):
            role(meter, never, limits=LIMITS_V2, provider=provider)
        assert not (meter.root / "epoch-1").exists()
    # A money ceiling with a priced selection bounds it.
    meter = ledger(tmp_path / "money", ceilings={"provider_nanodollars": 10**12})
    report = role(meter, scripted([[text()]])[0], limits=LIMITS_V2)
    assert report["status"] == "STOPPED"
    # A set call cap needs nothing of the ledger.
    meter = ledger(tmp_path / "capped", ceilings=None)
    report = role(meter, scripted([[text()]])[0], limits=limits_v2(calls_per_epoch=3))
    assert report["status"] == "STOPPED"


def test_limits_belong_to_a_role_and_replace_its_call_cap(tmp_path):
    with pytest.raises(ValueError, match="only a role's session takes limits"):
        epoch(ledger(tmp_path / "a"), never, limits=LIMITS_V2)
    with pytest.raises(ValueError, match="not both"):
        role(ledger(tmp_path / "b"), never, limits=LIMITS_V2, max_provider_calls=60)
    with pytest.raises(ValueError, match="unknown limits rule"):
        role(ledger(tmp_path / "c"), never, limits={**LIMITS_V2, "x": 1})


def test_the_agent_sees_the_campaign_budget_before_every_turn(tmp_path):
    meter = ledger(
        tmp_path,
        ceilings={**ROOMY, "provider_attempts": 4, "research_trials": 3},
    )
    tools = (INFO_TOOL, START_TOOL, SELECTION_TOOL)
    transport, requests = scripted([[call("a", INFO)], [call("b", INFO)], [text()]])
    role(meter, transport, tools=tools, limits=LIMITS_V2)
    notes = [request["input"][-1]["content"] for request in requests]
    assert notes[0].startswith(
        "Carbon status before this turn: 4 of 4 provider calls left in the campaign "
        "budget, counting this turn; USD 10000.0000 of USD 10000.0000 provider spend "
        "left in the campaign budget; each model call holds up to USD "
    )
    assert "3 of 3 research trials left in the campaign budget" in notes[0]
    assert "Notice" not in notes[0] and "per-session" not in notes[0]
    assert "3 of 4 provider calls left" in notes[1] and "Notice" not in notes[1]
    # The ledger is sure of only two more: the agent is told to finish.
    assert "2 of 4 provider calls left" in notes[2]
    assert "Notice: the budget is sure of only 2 more model calls" in notes[2]
    assert "Select a practiced recipe now" in notes[2]
    status = json.loads(
        (meter.root / "epoch-1" / "epoch-1-provider-002-status.json").read_bytes()
    )
    assert status["schema"] == "carbon.autoresearch.turn-status.v2"
    assert status["campaign_provider_calls_left"] == 2
    assert status["model_calls"] is None and status["trial_slots"] is None
    # Journalled before the request: a replay sends the same requests.
    first = json.loads((meter.root / "epoch-1" / "outcome.json").read_bytes())
    (meter.root / "epoch-1" / "outcome.json").unlink()
    assert role(meter, never, tools=tools, limits=LIMITS_V2) == first


def test_a_set_cap_is_stated_with_the_campaign_budget(tmp_path):
    meter = ledger(tmp_path, ceilings=ROOMY)
    transport, requests = scripted([[call("a", INFO)], [text()]])
    role(meter, transport, limits=limits_v2(calls_per_epoch=2))
    first, second = (request["input"][-1]["content"] for request in requests)
    assert first.startswith(
        "Carbon status before this turn: 2 of 2 model calls left in this session, "
        "counting this turn; 96 of 96 provider calls left in the campaign budget"
    )
    assert "Notice: the budget is sure of only 2 more model calls" in first
    assert "Notice: the budget is sure of only 1 more model call," in second


class ShareLedger(CampaignLedger):
    """A stage ledger as the miner edition's FULL mode uses one: its reserve
    refuses a new model call past a share of the campaign's calls, typed, and
    never refuses an identity it already admitted."""

    share = 3

    def _reserve(self, identity, **kwargs):
        with self.db() as db:
            known = db.execute(
                "SELECT 1 FROM operations WHERE id=?", (identity,)
            ).fetchone()
        used = self.status(owner="alice")["used"]["provider_attempts"]
        if (
            known is None
            and kwargs["resources"].get("provider_attempts")
            and used >= self.share
        ):
            raise CeilingReached(
                "research_share_reached", dimension="provider_attempts"
            )
        return super()._reserve(identity, **kwargs)


def test_a_typed_ledger_refusal_ends_the_session_typed(tmp_path):
    ledger(tmp_path, ceilings=ROOMY)
    meter = ShareLedger(tmp_path, clock=lambda: 1000)
    transport, requests = forever()
    report = role(meter, transport, limits=LIMITS_V2)
    assert report["status"] == "STOPPED"
    assert report["code"] == "research_share_reached"
    assert report["dimension"] == "provider_attempts"
    assert len(requests) == 3
    # Nothing of the refused call was reserved.
    assert meter.status(owner="alice")["used"]["provider_attempts"] == 3
    # A replay passes the admitted identities and is refused at the same one.
    (meter.root / "epoch-1" / "outcome.json").unlink()
    assert role(meter, never, limits=LIMITS_V2) == report
    with pytest.raises(ValueError, match="closed snake_case"):
        CeilingReached("Research Share")


def test_without_the_rule_a_ledger_refusal_still_propagates(tmp_path):
    """A plan frozen without limits keeps its behaviour: a ledger refusal
    that is not `CeilingReached` propagates as before."""
    meter = ledger(tmp_path, ceilings={**ROOMY, "provider_attempts": 2})
    transport, requests = forever()
    with pytest.raises(ValueError, match="miner budget: provider_attempts"):
        role(meter, transport)
    assert len(requests) == 2


def test_the_finite_ledger_mutation_is_caught(tmp_path, monkeypatch):
    """Specimen: with the finite-ledger requirement dropped, the refusal
    test above fails - an unbounded session is not refused."""
    monkeypatch.setattr(research_loop, "finite_provider_bound", lambda *a: True)
    # The refusal the test expects is missing: the session starts instead.
    with pytest.raises(
        (AssertionError, pytest.fail.Exception),
        match="finite provider_attempts|DID NOT RAISE",
    ):
        test_a_session_without_a_call_cap_needs_a_ledger_that_bounds_it(tmp_path)
