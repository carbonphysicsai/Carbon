"""Three Launchpad Test Runner findings on a Graphite Cooling 1.2 BUILD
campaign (cmp-40627272..., caps 40 calls / USD 0.50 / 30 min):

G1 - after 8 calls booked USD 0.084 the status was "sure of only 1 more
call" with USD 0.42 left, so Graphite stopped after one practice. Under
`BUDGET_HEADROOM_V1` the status also counts the spend at the calls' booked
average; the reservation and the ledger's admission are unchanged.

G2 - Graphite froze and submitted a practice that failed 58 of 100 gates.
Under `SELECTION_ADMISSIBLE_V1` a gate-failed practice cannot be selected.

G3 - one construction receiver (Motor only) was shown as every Challenge's
intake. Setup reads which Challenge a receiver serves and shows it only
beside that one; the submit refusal's next step says so plainly.

Deterministic mocks test control flow, never agent evidence.
"""

import json
from types import SimpleNamespace

import pytest
from test_cw1_research_ledger import ledger
from test_parallel_tool_calls_v2 import record_practice
from test_research_loop_limits import (
    INFO,
    LIMITS_V2,
    ROOMY,
    SDK,
    START,
    STRATEGY,
    call,
    role,
    scripted,
    select,
)
from test_research_loop_stages import miner, outputs

from carbon.agent_campaign.graphite.miner import driver
from carbon.development_session import research_loop
from carbon.development_session.profile import canonical
from carbon.development_session.research_campaign import (
    PRACTICE_DUAL_SCHEMA,
    practice_gates_failed,
    trial_admissible,
)
from carbon.development_session.research_loop import (
    BUDGET_HEADROOM_V1,
    SELECTION_ADMISSIBLE_V1,
    SELECTION_NOT_ADMISSIBLE,
    budget_status,
    money_headroom,
)
from scripts.dev.miner_launchpad import environment_setup as environment
from scripts.dev.miner_launchpad import prelaunch, runner
from scripts.dev.miner_launchpad.supervisor import next_action

NANO = 10**9
HOTKEY = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"

# -- G1: the budget's real headroom ---------------------------------------------


def test_the_test_runners_budget_fits_many_more_calls():
    """USD 0.50 ceiling, 8 calls booked USD 0.084, a USD 0.30 hold: one call
    is sure, and at the booked average about a dozen more fit."""
    left, hold = int(0.416 * NANO), int(0.30 * NANO)
    sure, likely = money_headroom(left, hold, 8, int(0.084 * NANO))
    assert sure == 1
    assert likely == 1 + (left - hold) // -(-int(0.084 * NANO) // 8) == 12
    # Less than one hold left: no call starts, whatever the average.
    assert money_headroom(hold - 1, hold, 8, 10) == (0, 0)
    # Nothing booked yet: only the sure count is known.
    assert money_headroom(left, hold, 0, 0) == (1, None)
    # Never fewer than the sure count.
    assert money_headroom(3 * hold, hold, 1, hold * 5)[1] == 3


def status(tmp_path, headroom, used_calls=8, used_nano=int(0.084 * NANO)):
    tmp_path.mkdir(parents=True, exist_ok=True)
    provider = SimpleNamespace(reservation_nano=int(0.30 * NANO))
    ledger_status = {
        "budget": {"provider_attempts": 40, "provider_nanodollars": NANO // 2},
        "used": {
            "provider_attempts": used_calls,
            "provider_nanodollars": used_nano,
            "research_trials": 0,
        },
    }
    message = budget_status(
        tmp_path,
        "epoch-1-provider-008",
        calls_left=None,
        call_limit=None,
        slots_left=None,
        trial_limit=None,
        ledger_status=ledger_status,
        provider=provider,
        unit="session",
        offered=set(),
        headroom=headroom,
    )
    record = json.loads((tmp_path / "epoch-1-provider-008-status.json").read_bytes())
    return message["content"], record


def test_under_the_rule_the_status_says_the_booked_headroom(tmp_path):
    text, record = status(tmp_path / "v1", BUDGET_HEADROOM_V1)
    assert "the 8 calls so far booked USD 0.0840" in text
    assert "about 12 more calls fit (at least 1 if every call cost its whole hold)" in (
        text
    )
    assert "a call starts only while that much is left" in text
    assert "Notice" not in text
    assert record["schema"] == "carbon.autoresearch.turn-status.v3"
    assert record["budget_headroom"] == BUDGET_HEADROOM_V1
    assert (
        record["model_calls_likely_by_spend"],
        record["model_calls_guaranteed"],
    ) == (
        12,
        12,
    )
    # Without the rule: exactly the historical v2 bytes and notice.
    old, record = status(tmp_path / "none", None)
    assert "Notice: the budget is sure of only 1 more model call," in old
    assert record["schema"] == "carbon.autoresearch.turn-status.v2"
    assert "budget_headroom" not in record and "so far booked" not in old


def test_under_the_rule_the_notice_comes_near_the_real_end(tmp_path):
    text, _ = status(tmp_path, BUDGET_HEADROOM_V1, used_nano=int(0.19 * NANO))
    # USD 0.31 left: one hold and a little, so one call fits at any cost.
    assert "Notice: the budget fits only about 1 more model call," in text


def test_the_headroom_rule_is_closed(tmp_path):
    with pytest.raises(ValueError, match="budget-headroom"):
        status(tmp_path, "carbon.autoresearch.budget-headroom.v0")
    with pytest.raises(ValueError, match="budget-headroom"):
        role(ledger(tmp_path, ceilings=ROOMY), None, budget_headroom="x")


def test_a_session_under_the_rule_records_it_in_its_plan(tmp_path):
    meter = ledger(tmp_path, ceilings=ROOMY)
    transport, requests = scripted([[call("a", INFO)], [select("s")]])
    role(meter, transport, limits=LIMITS_V2, budget_headroom=BUDGET_HEADROOM_V1)
    plan = json.loads((meter.root / "epoch-1" / "plan.json").read_bytes())
    assert plan["budget_headroom"] == BUDGET_HEADROOM_V1
    second = requests[1]["input"][-1]["content"]
    assert "a call starts only while that much is left" in second
    assert "1 call so far booked" in second


def test_the_launch_says_what_the_ceiling_buys():
    from test_research_loop_limits import fixture_selection

    from carbon.development_session.model_provider import DEFAULT_SELECTION

    window = driver.launch_window(DEFAULT_SELECTION)
    hold = window["per_call_reservation_nanodollars"]
    assert "USD " + format(hold / 1e9, ".4f") + " pays one call" in (
        window["budget_note"]
    )
    assert "booked average" in window["budget_note"]
    assert "max_input" not in window["budget_note"]
    assert "spend is left" in next_action("graphite_ceilings_required")
    unpriced = driver.launch_window(fixture_selection())
    assert "no listed price" in unpriced["budget_note"]


def provider_holds(meter):
    """Every model call's money reservation, in ledger order."""
    with meter.db() as db:
        rows = db.execute(
            "SELECT id,reservation FROM operations ORDER BY rowid"
        ).fetchall()
    return [
        json.loads(reserved)["provider_nanodollars"]
        for identity, reserved in rows
        if "provider_nanodollars" in json.loads(reserved)
    ]


def test_under_the_hold_rule_a_call_holds_its_own_requests_cost(tmp_path):
    """G1 (1): a call whose request extends the anchored one exactly holds
    its own request's input bound plus the whole output cap - provider-added
    tokens aside, which are detected - not the whole input window's. The
    first call has no anchor and holds the full reservation (Validator).
    Without the rule every call holds the full reservation, as before."""
    from carbon.development_session.model_provider import DEFAULT_SELECTION
    from carbon.development_session.research_agent import (
        REQUEST_HOLD_V1,
        request_hold,
    )

    full = DEFAULT_SELECTION.reservation_nano
    held = ledger(tmp_path / "held", ceilings=ROOMY)
    transport, requests = scripted([[call("a", INFO)], [select("s")]])
    role(held, transport, limits=LIMITS_V2, request_hold=REQUEST_HOLD_V1)
    holds = provider_holds(held)
    assert len(holds) == 2 and holds[0] == full and 0 < holds[1] < full
    turn = json.loads(
        (held.root / "epoch-1" / "epoch-1-provider-000-turn.json").read_bytes()
    )
    anchor = (turn["input_tokens"], len(canonical(requests[0])))
    assert holds[1] == request_hold(
        DEFAULT_SELECTION, len(canonical(requests[1])), anchor, True
    )
    settings, pricing = DEFAULT_SELECTION.settings, DEFAULT_SELECTION.pricing
    assert holds[1] >= settings.max_output_tokens * pricing.output_nano
    plan = json.loads((held.root / "epoch-1" / "plan.json").read_bytes())
    assert plan["request_hold"] == REQUEST_HOLD_V1
    status = requests[1]["input"][-1]["content"]
    assert "holds its own request's input and its whole output cap" in status
    assert "overshoot is detected and recorded" in status
    plain = ledger(tmp_path / "plain", ceilings=ROOMY)
    role(plain, scripted([[call("a", INFO)], [select("s")]])[0], limits=LIMITS_V2)
    assert provider_holds(plain) == [full, full]


def test_a_request_hold_never_exceeds_the_full_reservation():
    from carbon.development_session.model_provider import DEFAULT_SELECTION
    from carbon.development_session.research_agent import request_hold

    full = DEFAULT_SELECTION.reservation_nano
    # No anchor, or a request that does not extend it: the whole reservation.
    assert request_hold(DEFAULT_SELECTION, 1000) == full
    assert request_hold(DEFAULT_SELECTION, 5000, (100, 4000), False) == full
    # Anchored and extending: the reported tokens plus the bytes appended.
    small = request_hold(DEFAULT_SELECTION, 5000, (100, 4000), True)
    assert small < full
    assert small == request_hold(DEFAULT_SELECTION, 3900, (200, 3000), True)
    assert request_hold(DEFAULT_SELECTION, 10**9, (10**8, 1), True) == full


def test_a_rewritten_history_extends_nothing_and_holds_in_full():
    """Validator condition 2: the anchor counts only for a request that
    extends the anchored one exactly, by digest of its input prefix."""
    from carbon.development_session.research_agent import request_extends

    base = {"model": "m", "instructions": "i", "input": [{"a": 1}, {"b": 2}]}
    assert request_extends(base, {**base, "input": [{"a": 1}, {"b": 2}, {"c": 3}]})
    assert request_extends(base, base)
    # An earlier item rewritten (a compaction or an edit), or one dropped.
    assert not request_extends(base, {**base, "input": [{"a": 9}, {"b": 2}, {"c": 3}]})
    assert not request_extends(base, {**base, "input": [{"b": 2}, {"c": 3}]})
    # Any other field changed.
    assert not request_extends(base, {**base, "instructions": "j"})
    assert not request_extends(None, base) and not request_extends(base, None)


def test_the_request_hold_rule_is_closed(tmp_path):
    with pytest.raises(ValueError, match="request-hold"):
        role(ledger(tmp_path, ceilings=ROOMY), None, request_hold="x")


# -- G2: admissibility before ranking -------------------------------------------


def test_the_gate_reader_reads_summary_and_dual_verdicts():
    assert practice_gates_failed({"summary": {"eligible": False}})
    assert not practice_gates_failed({"summary": {"eligible": True}})
    dual = {"schema": PRACTICE_DUAL_SCHEMA, "available": True, "eligible": False}
    assert practice_gates_failed({"practice_dual": dual})
    assert practice_gates_failed({"summary": {"practice_dual": dual}})
    assert not practice_gates_failed({"practice_dual": {**dual, "eligible": True}})
    # An unavailable dual block, or no verdict at all, is no failure here.
    assert not practice_gates_failed({"practice_dual": {**dual, "available": False}})
    assert not practice_gates_failed({"provenance": "X", "recipe": {}})


def gated(meter, recipe, eligible):
    """A completed practice that reports its gate verdict."""
    from carbon.development_session.profile import canonical, digest

    record_practice(meter, recipe)
    body = canonical(
        {
            "provenance": "REAL_JAX_PUBLIC_PRACTICE",
            "recipe": recipe,
            "summary": {"eligible": eligible, "n_cases": 100},
        }
    )
    with meter.db() as db:
        db.execute(
            "INSERT INTO research_results VALUES(?,?,?,?)",
            ("alice", "gated-" + json.dumps(recipe), body, digest(body)),
        )


OTHER = {**STRATEGY, "parameters": {"steps": 256, "enforce_mean": True}}


def test_a_gate_failed_practice_cannot_be_selected_under_the_rule(tmp_path):
    meter = ledger(tmp_path, ceilings=ROOMY)
    gated(meter, STRATEGY, eligible=False)

    class Practising(SDK):
        async def call(self, name, arguments, identity):
            result = await super().call(name, arguments, identity)
            if name == START:
                gated(meter, json.loads(arguments["strategy_json"]), eligible=True)
            return result

    practice = {"kind": "practice", "strategy_json": json.dumps(OTHER)}
    transport, requests = scripted(
        [[select("s1")], [call("p", START, practice)], [select("s2", OTHER)]]
    )
    report = miner(
        meter,
        transport,
        Practising(meter),
        selection_admissibility=SELECTION_ADMISSIBLE_V1,
    )
    assert len(requests) == 3, "a gate-failed selection ended the session"
    refused = outputs(requests[1])["s1"]
    assert refused["code"] == SELECTION_NOT_ADMISSIBLE
    assert refused["admissible_recipes"] == [] and "gate" in refused["reason"]
    assert report["status"] == "SELECTED" and report["strategy"] == OTHER
    assert not trial_admissible(meter, "alice", STRATEGY)
    plan = json.loads((meter.root / "epoch-1" / "plan.json").read_bytes())
    assert plan["selection_admissibility"] == SELECTION_ADMISSIBLE_V1


def test_without_the_rule_a_gate_failed_practice_selects_as_before(tmp_path):
    """A plan frozen before the rule replays unchanged."""
    meter = ledger(tmp_path, ceilings=ROOMY)
    gated(meter, STRATEGY, eligible=False)
    report = miner(meter, scripted([[select("s1")]])[0], SDK(meter))
    assert report["status"] == "SELECTED"
    plan = json.loads((meter.root / "epoch-1" / "plan.json").read_bytes())
    assert "selection_admissibility" not in plan


def test_the_admissibility_mutation_is_caught(tmp_path, monkeypatch):
    """Specimen: with the gate reader made blind, the rule test fails."""
    from carbon.development_session import research_campaign

    monkeypatch.setattr(research_campaign, "practice_gates_failed", lambda r: False)
    with pytest.raises(AssertionError, match="gate-failed selection ended"):
        test_a_gate_failed_practice_cannot_be_selected_under_the_rule(tmp_path)


def test_the_gate_verdict_says_not_reported_for_no_verdict(tmp_path):
    from carbon.development_session.research_campaign import practice_gate_verdict

    meter = ledger(tmp_path, ceilings=ROOMY)
    assert practice_gate_verdict(meter, "alice", STRATEGY) == "NOT_REPORTED"
    record_practice(meter, STRATEGY)
    assert practice_gate_verdict(meter, "alice", STRATEGY) == "NOT_REPORTED"
    gated(meter, OTHER, eligible=True)
    assert practice_gate_verdict(meter, "alice", OTHER) == "PASSED"
    failed = {**OTHER, "parameters": {"steps": 128, "enforce_mean": True}}
    gated(meter, failed, eligible=False)
    assert practice_gate_verdict(meter, "alice", failed) == "FAILED"


def test_the_admissibility_rule_is_closed(tmp_path):
    with pytest.raises(ValueError, match="selection-admissibility"):
        research_loop.practice_check(ledger(tmp_path), "alice", "x")


# -- G3: which Challenge each intake serves -------------------------------------


def two_challenges():
    items = environment.intake_challenges()
    first = items[0]
    second = next(
        c for c in items if (c["id"], c["version"]) != (first["id"], first["version"])
    )
    return first, second


def test_setup_shows_a_receiver_only_beside_the_challenge_it_serves():
    served, other = two_challenges()
    target = {"intake_url": "http://127.0.0.1:9080", "receiver_hotkey": HOTKEY}
    record = {
        "profile": {"intakes": {}},
        "direct_intake_target": target,
        "direct_intake_serves": {"id": served["id"], "version": served["version"]},
    }
    host = SimpleNamespace(_own_intakes=lambda record: {})
    items = {
        (i["id"], i["version"]): i
        for i in environment.EnvironmentSetup._evaluation(host, record)["challenges"]
    }
    mine = items[(served["id"], served["version"])]
    assert mine["direct_intake"] == {
        **target,
        "serves": {"id": served["id"], "version": served["version"]},
    }
    theirs = items[(other["id"], other["version"])]
    assert "direct_intake" not in theirs
    assert theirs["direct_intake_serves_other"]["serves"]["id"] == served["id"]
    note = theirs["direct_intake_serves_other"]["note"]
    assert served["title"] in note and other["title"] in note
    assert "construction_intake_challenge_mismatch" in note


def test_an_unread_receiver_says_so():
    target = {"intake_url": "http://127.0.0.1:9080", "receiver_hotkey": HOTKEY}
    record = {"profile": {"intakes": {}}, "direct_intake_target": target}
    host = SimpleNamespace(_own_intakes=lambda record: {})
    items = environment.EnvironmentSetup._evaluation(host, record)["challenges"]
    assert all(i["direct_intake"] == target for i in items)
    assert all(
        i["direct_intake_serves_note"] == environment.DIRECT_SERVES_UNREAD
        for i in items
    )


def test_review_reads_and_keeps_what_a_receiver_serves(tmp_path):
    from test_miner_launchpad_environment_setup import (
        Checks,
        Onboarding,
        completed,
    )

    served, _ = two_challenges()
    reads = []

    class Reading(Checks):
        def direct_intake(self, url):
            reads.append(url)
            return {
                "receiver": HOTKEY,
                "challenge": {"id": served["id"], "version": served["version"]},
            }

    state = tmp_path / "state"
    state.mkdir()
    setup = environment.EnvironmentSetup(
        state, onboarding=Onboarding(), checks=Reading()
    )
    completed(tmp_path, setup)
    target = {"intake_url": "http://127.0.0.1:9080", "receiver_hotkey": HOTKEY}
    setup.review({"confirm": True, "direct_intake_target": target})
    profile = runner.validated_profile(json.loads(setup.profile_path.read_bytes()))
    assert profile["direct_intake_serves"] == {
        "id": served["id"],
        "version": served["version"],
    }
    # A later Review keeps it with the target, without reading again.
    setup.review({"confirm": True})
    assert len(reads) == 1
    assert json.loads(setup.profile_path.read_bytes())["direct_intake_serves"] == (
        profile["direct_intake_serves"]
    )
    setup.review({"confirm": True, "direct_intake_target": None})
    assert "direct_intake_serves" not in json.loads(setup.profile_path.read_bytes())


def test_the_prelaunch_review_shows_the_receiver_only_for_its_challenge():
    served, other = two_challenges()
    target = {"intake_url": "http://127.0.0.1:9080", "receiver_hotkey": HOTKEY}
    cfg = {
        "paths": {},
        "direct_intake_target": target,
        "direct_intake_serves": {"id": served["id"], "version": served["version"]},
    }
    items = {
        (i["challenge_id"], i["version"]): i
        for i in prelaunch.evaluation(cfg)["challenges"]
    }
    mine = items[(served["id"], served["version"])]
    assert mine["status"] == "INTAKE_CONFIGURED" and mine["direct"] is True
    theirs = items[(other["id"], other["version"])]
    assert theirs["status"] != "INTAKE_CONFIGURED"
    assert served["title"] in theirs["direct_intake_serves_other"]["note"]


def test_setup_refuses_another_challenges_intake_at_review():
    facts = {
        "receiver": HOTKEY,
        "snapshot": {"id": "s"},
        "challenge": {"id": "motor-x", "version": "1.2"},
    }
    campaign = SimpleNamespace(
        intake_check=lambda url: facts,
        key=SimpleNamespace(challenge_id="cooling-x", version="1.2"),
    )
    with pytest.raises(environment.SetupRefused) as refused:
        environment.LiveChecks.intake(None, "https://x.example.org", campaign)
    assert refused.value.code == "intake_serves_another_chain_or_challenge"
    same = SimpleNamespace(
        intake_check=lambda url: facts,
        key=SimpleNamespace(challenge_id="motor-x", version="1.2"),
    )
    assert environment.LiveChecks.intake(None, "https://x.example.org", same) == {
        "receiver": HOTKEY,
        "snapshot": "s",
    }


def test_the_mismatch_refusal_says_plainly_what_to_do():
    step = next_action("construction_intake_challenge_mismatch")
    assert "serves exactly one Challenge version" in step
    assert "carbon_setup_review" in step and "frozen candidate is kept" in step
    from scripts.dev.miner_launchpad.supervisor import FALLBACK_ACTION

    for code in (
        "construction_intake_challenge_mismatch",
        "construction_intake_chain_mismatch",
        "construction_contract_not_served",
    ):
        assert next_action(code) != FALLBACK_ACTION
