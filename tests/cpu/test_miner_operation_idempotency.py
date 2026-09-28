"""A retried practice, freeze or submit replays; it never runs twice.

Against the real campaign host (`journey_fixture`: the RunnerAdapter, the
operations table and its gates, research_campaign's freeze and submit, the
ledger), with only preparation, training and the final exam as fixtures. A
dispatch is counted where the host starts an operation's thread, and a final
exam where research_campaign runs one, so "replayed" means "nothing started".
"""

import threading

import pytest
from test_battery_validator_daemon import backend, refs  # noqa: F401 - fixtures

from carbon.development_session import research_campaign
from carbon.miner_mcp.mcp_operations import PREFIX, make_operation_tools
from scripts.dev.miner_launchpad.controller import Rejected
from scripts.dev.miner_launchpad.journey_fixture import journey_host
from scripts.dev.miner_launchpad.operations import OPERATIONS, perform
from scripts.dev.miner_launchpad.runner import RunnerAdapter, _operation_digest

RECIPE = {
    "schema_version": "1.0",
    "challenge_id": "burgers-dynamics-v1",
    "backbone": "fno",
    "parameters": {"steps": 64},
}
KEYED = ("practice", "freeze_candidate", "submit")


def settle(host, identity):
    thread = host.threads.get(identity)
    if thread is not None:
        thread.join(timeout=30)
        assert not thread.is_alive()
    return host.get(identity)


class Counted:
    """The host with its operation dispatches and final exams counted."""

    def __init__(self, host, monkeypatch, *, hold=None):
        self.host, self.dispatches, self.exams = host, [], []
        original = host._operation_thread

        def dispatch(admitted, work):
            self.dispatches.append(admitted.campaign["id"])
            if hold is not None:
                hold.wait(timeout=30)
            return original(admitted, work)

        monkeypatch.setattr(host, "_operation_thread", dispatch)

        async def final_epoch(args, ledger, owner, epoch, strategy, *_):
            self.exams.append((epoch, strategy))
            return {
                "disposition": "UI_FIXTURE_NOT_EVALUATED",
                "scores": {},
                "mandatory_failures": [],
            }, "fixture-ref"

        monkeypatch.setattr(research_campaign, "final_epoch", final_epoch)


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    host = journey_host(tmp_path, patch=monkeypatch.setattr)
    launched = perform(
        host, "launch", {"agent": "none", "idempotency_key": "launch-key-0000001"}
    )
    assert settle(host, launched["id"])["state"] == "READY"
    return host, launched["id"]


def practice(identity, key, hypothesis="width helps"):
    return {
        "campaign": identity,
        "strategy": RECIPE,
        "hypothesis": hypothesis,
        "idempotency_key": key,
    }


def test_every_keyed_operation_takes_the_key_on_both_doors():
    tools = {t.name: t for t in make_operation_tools(object())}
    for name in KEYED:
        op = OPERATIONS[name]
        assert "idempotency_key" in op.optional and "replay" in op.gates
        schema = tools[PREFIX + name].parameters
        assert "idempotency_key" in schema["properties"]
        assert "idempotency_key" not in schema.get("required", [])


def test_a_retried_practice_replays_and_a_changed_one_conflicts(campaign, monkeypatch):
    host, identity = campaign
    counted = Counted(host, monkeypatch)
    first = perform(host, "practice", practice(identity, "practice-key-00001"))
    settle(host, identity)
    again = perform(host, "practice", practice(identity, "practice-key-00001"))
    assert counted.dispatches == [identity]
    assert again["id"] == first["id"] == identity
    with pytest.raises(Rejected, match="operation_replay_conflict") as refused:
        perform(host, "practice", practice(identity, "practice-key-00001", "other"))
    assert refused.value.status == 409
    # The key names one action, whichever operation: reusing it for another
    # operation is the same conflict.
    with pytest.raises(Rejected, match="operation_replay_conflict"):
        perform(
            host,
            "freeze_candidate",
            {
                "campaign": identity,
                "strategy": RECIPE,
                "reason": "practiced",
                "idempotency_key": "practice-key-00001",
            },
        )
    # Specimen: a new key is a new action, and it is dispatched.
    perform(host, "practice", practice(identity, "practice-key-00002"))
    settle(host, identity)
    assert counted.dispatches == [identity, identity]


def test_an_invalid_key_is_refused_before_the_chain_is_read(campaign):
    host, identity = campaign
    reads = []
    host.registration = lambda cfg: reads.append(cfg)
    with pytest.raises(Rejected, match="invalid_idempotency_key"):
        perform(host, "submit", {"campaign": identity, "idempotency_key": "short"})
    assert reads == []


def test_a_replay_survives_a_controller_restart(campaign, monkeypatch):
    host, identity = campaign
    counted = Counted(host, monkeypatch)
    perform(host, "practice", practice(identity, "practice-key-00001"))
    settle(host, identity)
    freeze = {
        "campaign": identity,
        "strategy": RECIPE,
        "reason": "practiced",
        "idempotency_key": "freeze-key-0000001",
    }
    perform(host, "freeze_candidate", freeze)
    settle(host, identity)
    submit = {"campaign": identity, "idempotency_key": "submit-key-0000001"}
    perform(host, "submit", submit)
    settle(host, identity)
    assert counted.exams == [(1, RECIPE)] and len(counted.dispatches) == 3

    restarted = RunnerAdapter(
        host.database, principal="alice", registration=host.registration
    )
    restarted.configured = host.configured
    after = Counted(restarted, monkeypatch)
    # Without the durable record each of these would run again, or be refused
    # for a reason that is not the truth (the candidate was already frozen).
    for name, body in (("freeze_candidate", freeze), ("submit", submit)):
        assert perform(restarted, name, body)["id"] == identity
    assert after.dispatches == [] and after.exams == []
    with pytest.raises(Rejected, match="operation_replay_conflict"):
        perform(restarted, "freeze_candidate", {**freeze, "reason": "changed"})


def test_a_double_clicked_submit_evaluates_the_candidate_once(campaign, monkeypatch):
    host, identity = campaign
    perform(host, "practice", practice(identity, "practice-key-00001"))
    settle(host, identity)
    perform(
        host,
        "freeze_candidate",
        {"campaign": identity, "strategy": RECIPE, "reason": "practiced"},
    )
    settle(host, identity)
    hold = threading.Event()
    counted = Counted(host, monkeypatch, hold=hold)
    submit = {"campaign": identity, "idempotency_key": "submit-key-0000001"}
    answers, errors = [], []

    def click(body):
        try:
            answers.append(perform(host, "submit", body))
        except Rejected as refused:
            errors.append(refused.code)

    clicks = [threading.Thread(target=click, args=(submit,)) for _ in range(3)]
    # And one click that lost its key: a separate action, refused as busy.
    clicks.append(
        threading.Thread(
            target=click, args=({**submit, "idempotency_key": "submit-key-0000002"},)
        )
    )
    for thread in clicks:
        thread.start()
    for thread in clicks:
        thread.join(timeout=30)
    hold.set()
    settle(host, identity)
    assert counted.dispatches == [identity]
    assert counted.exams == [(1, RECIPE)]
    assert len(answers) == 3 and errors == ["campaign_busy"]
    # After it completed, the keyless retry finds nothing frozen to submit.
    with pytest.raises(Rejected, match="freeze_a_candidate_first"):
        perform(host, "submit", {"campaign": identity})
    assert counted.exams == [(1, RECIPE)]


def test_a_strategy_counts_by_value_whichever_door_sent_it():
    body = practice("cmp", "practice-key-00001")
    as_text = {
        **body,
        "strategy": '{"backbone":"fno","parameters":{"steps":64},'
        '"challenge_id":"burgers-dynamics-v1","schema_version":"1.0"}',
    }
    assert _operation_digest("practice", body) == _operation_digest("practice", as_text)
    assert _operation_digest("practice", body) != _operation_digest(
        "practice", {**body, "hypothesis": "other"}
    )
    # The key names the request; it is not part of what was asked.
    assert _operation_digest("practice", body) == _operation_digest(
        "practice", {**body, "idempotency_key": "another-key-000001"}
    )


def test_a_battery_resubmission_is_the_same_admission_never_a_second_evaluation(
    tmp_path,
    refs,  # noqa: F811 - fixture
    backend,  # noqa: F811 - fixture
):
    """Below the host: a submit retried after an interrupted campaign thread
    reaches the validator again with a fresh transport receipt. The evaluator
    the campaign calls (`deployment.evaluate`) admits it as the same
    submission and rebuilds nothing."""
    from test_battery_validator_daemon import make, submission

    from carbon.battery import deployment
    from carbon.battery.daemon import AuthenticatedSubmission

    target = make(tmp_path, refs, backend)
    target.lock_path = tmp_path / "state.lock"
    first = deployment.evaluate(target, submission("hk1"))
    before = dict(backend.calls)
    retried = submission("hk1")
    again = deployment.evaluate(
        target,
        AuthenticatedSubmission(
            retried.hotkey,
            {"sequence": 2, "digest": "e" * 64},
            retried.challenge_id,
            retried.challenge_version,
            retried.strategy,
            retried.contract_digest,
        ),
    )
    assert again["submission_id"] == first["submission_id"]
    assert again["state"] == first["state"] == "SCORED"
    assert backend.calls == before
    assert len(target.store.events("scored")) == 1
    # Specimen: a different recipe is a different admission, and it is built.
    deployment.evaluate(target, submission("hk1", neighbours=3))
    assert backend.calls["reconstruct"] == before["reconstruct"] + 1
