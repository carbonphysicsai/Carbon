"""The strategy commitment at the Launchpad's doors (LAUNCHPAD-ACCEPT-02).

Against the real campaign host (`journey_fixture`) and the real
`carbon_miner_signer` on a real socket, holding a public development key with
SYNTHETIC pins (`test_miner_signer_commit`). The chain is the poster tests'
stand-in (`test_commitment_poster.FakeChain`); the miner at the signer's
terminal is played by the test. The fixture Challenge commits on chain as the
battery Challenge does, through hooks with the same shape. Engineering
evidence only: the acceptance is the plan's cells F10, F13 and A5 on testnet.
"""

import asyncio
import dataclasses
import json
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_validator_daemon import submission
from test_commitment_poster import FakeChain, signer  # noqa: F401 - fixture
from test_launchpad_truthful_refusals import (
    INTAKE,
    frozen_campaign,
    join,
    journey,  # noqa: F401 - fixture
    request,
    root_of,
    serve,
)
from test_miner_signer_commit import short_dir  # noqa: F401 - fixture

from carbon.battery.daemon import commitment_digest
from carbon.chain import commitment_poster as cp
from carbon.chain.external_signer import COMMIT_REFUSALS, SignerCode
from carbon.development_session.profile import canonical, digest
from carbon.miner_mcp.mcp_operations import PREFIX, make_operation_tools
from scripts.dev.miner_launchpad import supervisor as supervision
from scripts.dev.miner_launchpad.controller import Rejected
from scripts.dev.miner_launchpad.journey_fixture import (
    FIXTURE_CHALLENGE,
    reference_burgers_campaign,
)
from scripts.dev.miner_launchpad.operations import (
    OPERATIONS,
    REFUSAL_FIELDS,
    perform,
    refusal,
)

#: SYNTHETIC: the contract the fixture Challenge's candidates are frozen under.
CONTRACT = "sha256:" + "a" * 64
BATTERY = "battery-fastcharge-ageing-development-v1"
URL = "https://validator.example/intake"


def fixture_digest(record, manifest):
    """The fixture Challenge's L1, shaped as battery's: the daemon's own
    digest over the Challenge, contract and strategy."""
    return commitment_digest(
        FIXTURE_CHALLENGE["id"], CONTRACT, digest(canonical(record["strategy"]))
    )


def committing(monkeypatch):
    """The fixture Challenge's campaign, judged by a validator that requires a
    commitment, reached through an intake, as the battery Challenge's is."""
    from carbon.challenge_registry import campaigns

    def due(args, root, epoch):
        return (
            FIXTURE_CHALLENGE["id"] in (args.intakes or {})
            and not (Path(root) / f"sent-epoch-{epoch}").exists()
        )

    validated = dataclasses.replace(
        reference_burgers_campaign(),
        feedback_schema="fixture.permitted-feedback.v1",
        commitment=fixture_digest,
        commitment_due=due,
    )
    mapping = campaigns._campaigns
    monkeypatch.setattr(
        campaigns,
        "_campaigns",
        lambda: {**mapping(), FIXTURE_CHALLENGE["id"]: lambda: validated},
    )


@pytest.fixture
def wired(journey, monkeypatch, signer):  # noqa: F811
    """The journey host with a chain stand-in and the real signer."""
    committing(monkeypatch)
    chain = FakeChain()
    cfg = journey.configured()
    Path(cfg["paths"]["miner_public"]).write_text(
        json.dumps({"hotkey": signer.ss58_address})
    )
    journey.configured = lambda: {
        **cfg,
        "intakes": {FIXTURE_CHALLENGE["id"]: INTAKE},
    }
    journey.commitment_chain = lambda _cfg: chain
    journey.commitment_signer = lambda _cfg: signer.sign
    return SimpleNamespace(host=journey, chain=chain, signer=signer)


def candidate_digest(host, identity):
    record = json.loads(
        (root_of(host, identity) / "epoch-1/selected-recipe.json").read_bytes()
    )
    return fixture_digest(record, None)


def mcp(host, name, body):
    tool = {t.name: t for t in make_operation_tools(host)}[PREFIX + name]
    return asyncio.run(tool.fn(**body))


def mcp_refusal(host, name, body):
    from mcp.server.mcpserver.exceptions import ToolError

    with pytest.raises(ToolError) as refused:
        mcp(host, name, body)
    return json.loads(str(refused.value))


def until(host, identity, check, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = host.get(identity)
        if check(value):
            return value
        time.sleep(0.02)
    raise AssertionError(host.get(identity)["commitment"])


def nothing_sent(wired):
    assert wired.chain.broadcasts == [] and wired.chain.prepared == []
    assert wired.signer.requests == [] and wired.signer.asked.prompts == []


# ---- The table and the catalog ----------------------------------------------


def test_commit_is_one_operation_on_both_doors_with_no_confirm_field():
    op = OPERATIONS["commit"]
    assert op.gates == ("request", "profile", "replay", "registration", "campaign")
    assert op.admits_work and op.required == {"campaign"}
    assert op.optional == {"recommit", "idempotency_key"}
    tool = {t.name: t for t in make_operation_tools(SimpleNamespace())}[
        PREFIX + "commit"
    ]
    # D10: nothing an agent can send confirms; there is no digest to send.
    assert set(tool.parameters["properties"]) == {
        "campaign",
        "recommit",
        "idempotency_key",
    }
    assert tool.parameters["properties"]["recommit"]["anyOf"][0]["type"] == "boolean"
    assert "commit" in supervision.OPERATIONS


def test_every_code_a_commitment_can_end_with_has_its_own_step():
    codes = (
        {code.value for code in cp.PostCode} - cp.DONE
        | COMMIT_REFUSALS
        | {code.value for code in SignerCode}
        | {
            cp.REQUIRED,
            cp.UNREADABLE,
            cp.STALE,
            "recommit_boolean_required",
            "commitment_not_offered",
            "commitment_digest_unavailable",
        }
    )
    missing = sorted(code for code in codes if code not in supervision.NEXT_ACTIONS)
    assert not missing, missing
    for code in codes:
        assert supervision.refusal(code, operation="commit")["code"] == code
    assert REFUSAL_FIELDS["recommit_boolean_required"] == "recommit"
    # Each signer refusal reaches a door as its own closed value.
    for value in COMMIT_REFUSALS:
        assert cp.closed_code("signer_refused:" + value) == value
    assert cp.closed_code("signer_not_running") == "signer_not_running"
    # The validator's two commitment refusals send the miner to commit.
    assert "carbon_commit" in supervision.NEXT_ACTIONS[cp.REQUIRED]
    stale = supervision.NEXT_ACTIONS[cp.STALE]
    assert "carbon_commit" in stale and "recommit=true" in stale


# ---- L1: the frozen candidate's digest is the daemon's ------------------------


def test_the_battery_candidates_digest_is_the_daemons_expected_digest(tmp_path):
    from carbon.battery import campaign
    from carbon.battery.compile import compile_recipe
    from carbon.challenge_registry.campaigns import campaign_for_id

    sub = submission("hk1")
    _, recipe = compile_recipe(sub.strategy)
    expected = commitment_digest(
        sub.strategy["challenge_id"], sub.contract_digest, recipe.strategy_hash
    )
    hooks = campaign_for_id(BATTERY)
    record = {"strategy": sub.strategy, "contract_digest": sub.contract_digest}
    assert hooks.commitment(record, {}) == expected
    # A record frozen before it carried its contract uses the manifest's.
    assert (
        hooks.commitment(
            {"strategy": sub.strategy}, {"contract_digest": sub.contract_digest}
        )
        == expected
    )
    # Due only on the first send through an intake.
    args = SimpleNamespace(intakes={BATTERY: URL}, validators={})
    assert hooks.commitment_due(args, tmp_path, 1) is True
    (tmp_path / "intake-submission-epoch-1.json").write_text("{}")
    assert hooks.commitment_due(args, tmp_path, 1) is False
    assert hooks.commitment_due(args, tmp_path, 2) is True
    local = SimpleNamespace(intakes={BATTERY: URL}, validators={BATTERY: tmp_path})
    assert hooks.commitment_due(local, tmp_path, 2) is False
    none = SimpleNamespace(intakes={}, validators={})
    assert hooks.commitment_due(none, tmp_path, 2) is False
    assert campaign.commitment_due is hooks.commitment_due


def test_the_commit_digest_is_the_frozen_candidates(wired):
    identity = frozen_campaign(wired.host)
    answer = perform(wired.host, "commit", {"campaign": identity})
    join(wired.host)
    expected = candidate_digest(wired.host, identity)
    assert answer["commitment"]["digest"] == expected
    assert wired.chain.prepared == [expected]
    assert [r["digest"] for r in wired.signer.requests] == [expected]


# ---- Submit gating -------------------------------------------------------------


def test_a_submit_is_refused_commitment_required_before_anything_is_sent(
    wired, tmp_path
):
    host = wired.host
    identity = frozen_campaign(host)
    body = {"campaign": identity, "idempotency_key": "submit-key-0000001"}
    with pytest.raises(Rejected) as refused:
        perform(host, "submit", body)
    assert (refused.value.code, refused.value.status) == (cp.REQUIRED, 409)
    nothing_sent(wired)
    view = host.get(identity)
    assert view["in_flight"] is None and view["journey"]["submitted_epochs"] == []
    assert view["journey"]["frozen_awaiting_submission"] is True  # kept
    # Both doors: the same closed code and the step to commit.
    server, thread = serve(tmp_path, host)
    try:
        browser = request(server, "POST", "/api/v1/operations/submit", body)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
    assert browser == (409, refusal(cp.REQUIRED))
    assert mcp_refusal(host, "submit", body) == refusal(cp.REQUIRED)
    nothing_sent(wired)
    # Nothing was recorded under the key: once committed, the same request
    # is admitted, not replayed.
    perform(host, "commit", {"campaign": identity})
    join(host)
    assert host.get(identity)["commitment"]["state"] == "COMMITTED"
    perform(host, "submit", body)
    join(host)
    assert host.get(identity)["journey"]["submitted_epochs"] == [1]


def test_another_digest_on_chain_is_still_commitment_required(wired):
    wired.chain.on_chain = {"digest": "sha256:" + "f" * 64, "block": 9}
    identity = frozen_campaign(wired.host)
    with pytest.raises(Rejected, match=cp.REQUIRED):
        perform(wired.host, "submit", {"campaign": identity})
    nothing_sent(wired)


def test_an_unreadable_chain_refuses_the_submit_unsent(wired):
    """Fail closed: a commitment that cannot be read is never assumed."""
    wired.chain.read_down = True
    identity = frozen_campaign(wired.host)
    with pytest.raises(Rejected) as refused:
        perform(wired.host, "submit", {"campaign": identity})
    assert (refused.value.code, refused.value.status) == (cp.UNREADABLE, 503)
    nothing_sent(wired)


def test_a_submission_the_intake_already_holds_is_not_gated_again(wired):
    """The intake holds the epoch's submission: polling it is never blocked,
    and a resend is the intake's to refuse (`intake.RECEIVED_AGAIN`)."""
    identity = frozen_campaign(wired.host)
    (root_of(wired.host, identity) / "sent-epoch-1").write_text("")
    perform(wired.host, "submit", {"campaign": identity})
    join(wired.host)
    assert wired.host.get(identity)["journey"]["submitted_epochs"] == [1]
    nothing_sent(wired)


def test_a_host_that_reads_no_chain_gates_nothing(journey, monkeypatch):  # noqa: F811
    """A fixture host stubs the chain and names no commitment reader: its
    submits are unchanged (the validator still refuses one it requires)."""
    committing(monkeypatch)
    cfg = journey.configured()
    journey.configured = lambda: {**cfg, "intakes": {FIXTURE_CHALLENGE["id"]: INTAKE}}
    assert journey.commitment_chain is None
    identity = frozen_campaign(journey)
    perform(journey, "submit", {"campaign": identity})
    join(journey)
    assert journey.get(identity)["journey"]["submitted_epochs"] == [1]


def test_a_challenge_without_a_commitment_is_never_gated(wired, monkeypatch):
    from carbon.challenge_registry import campaigns

    plain = dataclasses.replace(
        reference_burgers_campaign(), feedback_schema="fixture.permitted-feedback.v1"
    )
    mapping = campaigns._campaigns
    monkeypatch.setattr(
        campaigns,
        "_campaigns",
        lambda: {**mapping(), FIXTURE_CHALLENGE["id"]: lambda: plain},
    )
    identity = frozen_campaign(wired.host)
    with pytest.raises(Rejected, match="commitment_not_offered"):
        perform(wired.host, "commit", {"campaign": identity})
    perform(wired.host, "submit", {"campaign": identity})
    join(wired.host)
    assert wired.host.get(identity)["journey"]["submitted_epochs"] == [1]
    nothing_sent(wired)


# ---- The commit: plan, the miner's confirmation, read-back -------------------


def test_commit_answers_the_plan_and_waits_for_the_miner_at_the_signer(wired):
    host, chain = wired.host, wired.chain
    previous = "sha256:" + "f" * 64
    chain.on_chain = {"digest": previous, "block": 9}
    release = threading.Event()

    def at_terminal(expected):
        release.wait(10)
        return True

    wired.signer.asked.answer = at_terminal
    identity = frozen_campaign(host)
    expected = candidate_digest(host, identity)
    answer = mcp(host, "commit", {"campaign": identity}).payload
    plan = answer["commitment"]["plan"]
    assert plan["current"] == previous and plan["current_block"] == 9
    assert plan["needed"] is True and "replaces" in plan["warning"]
    asked = until(
        host, identity, lambda v: v["commitment"]["state"] == "CONFIRM_COMMITMENT"
    )["commitment"]
    assert asked["human_action_required"] == "confirm_commitment"
    assert asked["confirm_with"] == expected[-8:]
    assert asked["requested_by"] == "miner" and asked["on_chain"] is None
    assert "cannot confirm" in asked["next_step"]
    assert chain.broadcasts == []  # nothing until the miner types
    release.set()
    join(host)
    done = host.get(identity)
    assert done["commitment"]["state"] == "COMMITTED"
    assert done["commitment"]["human_action_required"] is None
    assert done["commitment"]["on_chain"] == {
        "digest": expected,
        "block": 7_202,
        "extrinsic_id": None,
    }
    assert done["last_refusal"] is None and done["in_flight"] is None
    assert len(chain.broadcasts) == 1
    # The research view shows the same document.
    view = mcp(host, "campaign_view", {"campaign": identity}).payload
    assert view["commitment"] == done["commitment"]
    # The page's stage and its in-flight reading know the operation.
    from scripts.dev.miner_launchpad.campaign_view import STAGE_OF_OPERATION

    assert STAGE_OF_OPERATION["commit"] == "submit"


def test_the_same_digest_on_chain_is_not_posted_again_unless_recommit(wired):
    host = wired.host
    identity = frozen_campaign(host)
    expected = candidate_digest(host, identity)
    wired.chain.on_chain = {"digest": expected, "block": 40}
    answer = perform(host, "commit", {"campaign": identity})
    assert answer["commitment"]["state"] == "ALREADY_ON_CHAIN"
    assert answer["commitment"]["on_chain"]["block"] == 40
    assert answer["in_flight"] is None
    nothing_sent(wired)
    # L7: a validator's commitment_stale is answered by a recommit.
    with pytest.raises(Rejected, match="recommit_boolean_required"):
        perform(host, "commit", {"campaign": identity, "recommit": "yes"})
    perform(host, "commit", {"campaign": identity, "recommit": True})
    join(host)
    done = host.get(identity)["commitment"]
    assert done["state"] == "COMMITTED" and done["recommit"] is True
    assert done["on_chain"]["block"] == 7_202
    assert len(wired.chain.broadcasts) == 1


def test_both_doors_answer_and_show_the_same_commitment(wired, tmp_path):
    host = wired.host
    identity = frozen_campaign(host)
    mcp(host, "commit", {"campaign": identity})
    join(host)
    server, thread = serve(tmp_path, host)
    try:
        code, browser = request(
            server, "POST", "/api/v1/operations/commit", {"campaign": identity}
        )
        observed = request(
            server, "POST", "/api/v1/operations/observe", {"campaign": identity}
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
    via_mcp = mcp(host, "commit", {"campaign": identity}).payload
    assert code == 200
    assert browser["commitment"] == via_mcp["commitment"]
    assert browser["commitment"]["state"] == "ALREADY_ON_CHAIN"
    assert observed[1]["commitment"] == via_mcp["commitment"]
    assert len(wired.chain.broadcasts) == 1


def test_a_commit_refusal_is_the_same_closed_code_on_both_doors(wired, tmp_path):
    from test_launchpad_truthful_refusals import launch

    host = wired.host
    identity = launch(host)["id"]
    join(host)
    body = {"campaign": identity}
    server, thread = serve(tmp_path, host)
    try:
        browser = request(server, "POST", "/api/v1/operations/commit", body)
        extra = request(
            server,
            "POST",
            "/api/v1/operations/commit",
            {**body, "confirm": identity[-8:]},
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
    # The same code and step; the MCP door also names the field to correct.
    via_mcp = mcp_refusal(host, "commit", body)
    assert via_mcp == refusal("freeze_a_candidate_first")
    assert browser == (409, {k: via_mcp[k] for k in ("error", "next_step")})
    # D10: no input completes a confirmation, on either door.
    assert extra == (400, refusal("closed_request_required"))
    assert mcp_refusal(host, "commit", {**body, "confirm": "x"}) == refusal(
        "closed_request_required"
    )
    nothing_sent(wired)


def test_an_agent_cannot_confirm_only_the_signer_terminal_does(wired):
    """D10: the agent's call returns at once; the signer asks the miner on its
    own terminal, and a miner who does not confirm leaves nothing signed."""
    host = wired.host
    wired.signer.asked.answer = False
    identity = frozen_campaign(host)
    mcp(host, "commit", {"campaign": identity})
    join(host)
    view = host.get(identity)
    assert view["commitment"]["state"] == "NOT_COMMITTED"
    assert view["commitment"]["code"] == "NOT_CONFIRMED"
    assert view["commitment"]["next_step"] == supervision.NEXT_ACTIONS["NOT_CONFIRMED"]
    assert view["last_refusal"]["code"] == "NOT_CONFIRMED"
    assert view["last_refusal"]["operation"] == "commit"
    assert len(wired.signer.asked.prompts) == 1  # asked at the terminal only
    assert wired.chain.broadcasts == []
    # What reached the signer carried no confirmation of any kind.
    (sent,) = wired.signer.requests
    assert set(sent) == {"netuid", "digest", "unsigned", "fee"}
    assert "confirm" not in json.dumps(sent)


def test_an_outcome_unknown_post_is_reconciled_and_never_resent(wired):
    host, chain = wired.host, wired.chain
    chain.outcome = "RAISE"
    identity = frozen_campaign(host)
    expected = candidate_digest(host, identity)
    perform(host, "commit", {"campaign": identity})
    join(host)
    view = host.get(identity)
    assert view["commitment"]["state"] == "RECONCILING"
    assert view["commitment"]["human_action_required"] is None
    assert view["last_refusal"]["code"] == "commitment_ambiguous"
    assert len(chain.broadcasts) == 1
    # Asked again while the signature's era is live: read, never resent.
    chain.outcome = "FINALIZED"
    perform(host, "commit", {"campaign": identity})
    join(host)
    assert host.get(identity)["commitment"]["state"] == "RECONCILING"
    assert len(chain.broadcasts) == 1 and len(wired.signer.asked.prompts) == 1
    # It landed after all: the plan reads it and nothing is posted (L3).
    chain.on_chain = {"digest": expected, "block": 7_203}
    answer = perform(host, "commit", {"campaign": identity})
    assert answer["commitment"]["state"] == "ALREADY_ON_CHAIN"
    assert len(chain.broadcasts) == 1 and len(wired.signer.asked.prompts) == 1


# ---- Graphite's selection asks; only the miner confirms (D10) ---------------


def battery_prepared(tmp_path, wired, agent):
    from carbon.chain.commitment_poster import CommitmentGate, CommitmentPoster

    root = tmp_path / "campaign"
    root.mkdir(mode=0o700)
    sub = submission("hk1")
    poster = CommitmentPoster(
        hotkey=wired.signer.ss58_address,
        chain=wired.chain,
        sign=wired.signer.sign,
        state_dir=tmp_path / "commitments",
    )
    prepared = SimpleNamespace(
        agent=agent,
        sdk=SimpleNamespace(connection=SimpleNamespace(miner_key=wired.signer)),
        ledger=SimpleNamespace(root=root),
        manifest={"contract_digest": sub.contract_digest},
        args=SimpleNamespace(
            intakes={BATTERY: URL},
            validators={},
            commitment_gate=CommitmentGate(poster),
        ),
    )
    record = {"strategy": sub.strategy, "contract_digest": sub.contract_digest}
    return prepared, record, cp.expected_digest(sub.strategy, sub.contract_digest)


@pytest.fixture
def battery_chain(signer):  # noqa: F811
    return SimpleNamespace(chain=FakeChain(), signer=signer)


def sends(monkeypatch, answers, log):
    from carbon.battery import campaign
    from carbon.battery.remote_submission import IntakeRefusal

    def submit_through_intake(url, key, **kwargs):
        log.append(("send", list(kwargs["strategy"])))
        answer = answers.pop(0)
        if isinstance(answer, str):
            raise IntakeRefusal(answer)
        return answer

    monkeypatch.setattr(campaign, "submit_through_intake", submit_through_intake)


def test_graphites_selection_requests_the_commitment_and_the_miner_confirms(
    tmp_path, battery_chain, monkeypatch
):
    from carbon.battery import campaign
    from carbon.development_session.research_campaign import OperationRefused

    prepared, record, expected = battery_prepared(tmp_path, battery_chain, "graphite")
    log = []
    sends(monkeypatch, ["evaluation_queued"], log)
    with pytest.raises(OperationRefused, match="evaluation_queued"):
        asyncio.run(campaign.evaluate_candidate(prepared, 1, record))
    # Asked at the signer's terminal, committed, read back, then sent once.
    assert [e for _, e in battery_chain.signer.asked.prompts] == [expected[-8:]]
    assert battery_chain.chain.on_chain == {"digest": expected, "block": 7_202}
    assert len(log) == 1
    request = cp.read_request(prepared.ledger.root)
    assert request["requested_by"] == "agent" and request["digest"] == expected


def test_graphite_sends_nothing_when_the_miner_does_not_confirm(
    tmp_path, battery_chain, monkeypatch
):
    from carbon.battery import campaign
    from carbon.development_session.research_campaign import OperationRefused

    battery_chain.signer.asked.answer = False
    prepared, record, _ = battery_prepared(tmp_path, battery_chain, "graphite")
    log = []
    sends(monkeypatch, [], log)
    with pytest.raises(OperationRefused, match="NOT_CONFIRMED"):
        asyncio.run(campaign.evaluate_candidate(prepared, 1, record))
    assert log == [] and battery_chain.chain.broadcasts == []


def test_the_miners_own_submit_never_posts_from_the_campaign(
    tmp_path, battery_chain, monkeypatch
):
    from carbon.battery import campaign
    from carbon.development_session.research_campaign import OperationRefused

    prepared, record, _ = battery_prepared(tmp_path, battery_chain, "none")
    log = []
    sends(monkeypatch, [], log)
    with pytest.raises(OperationRefused, match=cp.REQUIRED):
        asyncio.run(campaign.evaluate_candidate(prepared, 1, record))
    assert log == [] and battery_chain.signer.requests == []


def test_a_stale_commitment_gets_one_recommit_for_graphite(
    tmp_path, battery_chain, monkeypatch
):
    from carbon.battery import campaign
    from carbon.development_session.research_campaign import OperationRefused

    prepared, record, expected = battery_prepared(tmp_path, battery_chain, "graphite")
    battery_chain.chain.on_chain = {"digest": expected, "block": 40}
    stale = (200, {"state": "REFUSED", "failure": {"code": cp.STALE}}, "sub-1")
    log = []
    sends(monkeypatch, [stale, "evaluation_queued"], log)
    with pytest.raises(OperationRefused, match="evaluation_queued"):
        asyncio.run(campaign.evaluate_candidate(prepared, 1, record))
    assert len(log) == 2 and len(battery_chain.chain.broadcasts) == 1
    assert battery_chain.chain.on_chain == {"digest": expected, "block": 7_202}
    assert cp.read_request(prepared.ledger.root)["recommit"] is True
    # Stale again after its recommit: the miner's to act on, never a loop.
    battery_chain.chain.head += 400  # the next tempo
    sends(monkeypatch, [stale, stale], log)
    with pytest.raises(OperationRefused, match=cp.STALE):
        asyncio.run(campaign.evaluate_candidate(prepared, 1, record))
    assert len(log) == 4 and len(battery_chain.chain.broadcasts) == 2
