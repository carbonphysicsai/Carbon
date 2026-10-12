"""LAUNCHPAD-PRACTICE-RETRY-01: the miner's choice to auto-retry an
interrupted practice, and the one-step retry when it is not.

Observed 2026-10-11: a practice was RUNNING when the lane's Control Center
restarted; recovery set the campaign READY with `operation_interrupted`, and
nothing retried it. Now a runner-profile setting, off by default, has a
supervisor that recovers such a practice queue it again with the same
request, at most `PRACTICE_RETRY_CAP` times; otherwise resume with
retry_interrupted sends it again in one call. Never a freeze, submit or
commit, and never a practice refused for a typed reason.

Against the real campaign host (`journey_fixture`), as
`test_launchpad_supervisor` drives it: a dead process is a queue item RUNNING
under a supervisor token nobody holds, with the campaign's ledger left in
flight. No chain, provider, compute or network.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.development_session import research_campaign
from carbon.development_session.research_control import CampaignControl
from carbon.development_session.research_ledger import CampaignLedger
from scripts.dev.miner_launchpad import runner
from scripts.dev.miner_launchpad import supervisor as supervision
from scripts.dev.miner_launchpad.campaign_view import recovery as view_recovery
from scripts.dev.miner_launchpad.controller import Rejected
from scripts.dev.miner_launchpad.environment_setup import (
    GRAPHITE,
    LOCAL_CPU,
    EnvironmentSetup,
    SetupRefused,
    check_quote,
)
from scripts.dev.miner_launchpad.journey_fixture import (
    FIXTURE_CHALLENGE,
    journey_host,
)
from scripts.dev.miner_launchpad.operations import OPERATIONS, perform
from scripts.dev.miner_launchpad.runner import RunnerAdapter

RECIPE = {
    "schema_version": "1.0",
    "challenge_id": "burgers-dynamics-v1",
    "backbone": "fno",
    "parameters": {"steps": 64},
}
#: The request a lost practice was admitted with, as `practice_admitted`
#: records it.
LOST = {
    "strategy": RECIPE,
    "hypothesis": "width helps",
    "expected_effect": "lower error at 64 steps",
    "identity": "miner-practice-0123456789abcdef",
}
RETRY = {"action": "retry_interrupted", "operation": "resume"}


@pytest.fixture
def journey(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    host = journey_host(tmp_path, patch=monkeypatch.setattr)
    monkeypatch.setattr(RunnerAdapter, "spawn", staticmethod(lambda _: None))
    sent = []
    fixture_practice = research_campaign.practice_recipe

    async def recorded(prepared, **params):
        sent.append(params)
        return await fixture_practice(prepared, **params)

    monkeypatch.setattr(research_campaign, "practice_recipe", recorded)
    peers = []

    def peer(role=supervision.SUPERVISOR):
        other = RunnerAdapter(
            host.database,
            principal="alice",
            registration=host.registration,
            role=role,
        )
        other.configured = host.configured
        peers.append(other)
        return other

    yield SimpleNamespace(host=host, peer=peer, sent=sent)
    for other in peers:
        other.close()
    host.close()


def auto_retry(host, on=True):
    """The miner's setting, as Review writes it into the profile."""
    cfg = host.configured()
    turned = {**cfg, "practice_auto_retry": True} if on else cfg
    host.configured = lambda: turned


def launched(host):
    identity = perform(
        host,
        "launch",
        {
            "challenge": FIXTURE_CHALLENGE["id"],
            "challenge_version": FIXTURE_CHALLENGE["version"],
            "agent": "none",
            "idempotency_key": "launch-key-0000001",
        },
    )["id"]
    join(host)
    return identity


def join(*hosts):
    for host in hosts:
        for thread in list(host.threads.values()):
            thread.join(timeout=30)
            assert not thread.is_alive()


def root_of(host, identity):
    return Path(host._bound(identity)[2])


def dispatches(host, operation=None):
    with host.db() as db:
        rows = [
            dict(r) for r in db.execute("SELECT * FROM launchpad_dispatch ORDER BY seq")
        ]
    return [r for r in rows if operation in (None, r["operation"])]


def dies_running(host, identity, operation="practice", params=LOST, seq=None):
    """A process dies with `operation` RUNNING: its queue item names a
    supervisor nobody holds, and the campaign's ledger is left in flight.
    `seq` is an item a supervisor claimed and then lost; otherwise a new one.
    Returns the item's seq."""
    CampaignControl(CampaignLedger(root_of(host, identity))).acquire()
    with host.db() as db:
        if seq is not None:
            db.execute(
                "UPDATE launchpad_dispatch SET state=?,supervisor=?,claimed=? WHERE seq=?",
                (supervision.RUNNING, "sup-dead-" + str(seq), 1.0, seq),
            )
            return seq
        return supervision.enqueue(
            db,
            principal="alice",
            campaign=identity,
            operation=operation,
            params=params,
            config_digest="sha256:dead",
            state=supervision.RUNNING,
            supervisor="sup-dead-process",
        )


def same_request(params):
    assert {k: params[k] for k in ("strategy", "hypothesis", "expected_effect")} == {
        k: LOST[k] for k in ("strategy", "hypothesis", "expected_effect")
    }
    # A fresh trial identity: the lost one is bound to the lost attempt.
    assert params["identity"] != LOST["identity"]
    assert params["identity"].startswith("miner-practice-")


# --- Setting off (the default) ---------------------------------------------


def test_off_by_default_an_interrupted_practice_waits_for_the_one_step_retry(
    journey,
):
    host = journey.host
    identity = launched(host)
    lost = dies_running(host, identity)
    supervisor = journey.peer()
    assert supervisor.supervisor.tick()  # the Control Center starts again
    join(supervisor)
    view = supervisor.get(identity)
    # Not retried: the interruption stays, with its one-call step.
    assert view["state"] == "READY" and view["in_flight"] is None
    refused = view["last_refusal"]
    assert (refused["code"], refused["operation"], refused["kind"]) == (
        "operation_interrupted",
        "practice",
        "interrupted",
    )
    assert "retry_interrupted=true (carbon_resume" in refused["next_action"]
    assert (
        refused["next_action"]
        == supervision.OPERATION_NEXT_ACTIONS[("operation_interrupted", "practice")]
    )
    assert view["recovery"] == [RETRY]
    assert view_recovery(view) == [RETRY]  # the browser's campaign view
    assert [d["seq"] for d in dispatches(host, "practice")] == [lost]
    assert journey.sent == []

    # One call, through the operations table both doors share.
    answered = perform(
        supervisor, "resume", {"campaign": identity, "retry_interrupted": True}
    )
    assert answered["last_refusal"] is None
    join(supervisor)
    (sent,) = journey.sent
    same_request(sent)
    view = supervisor.get(identity)
    assert view["state"] == "READY" and view["completed_experiments"] == 1
    assert view["recovery"] == [] and view["last_refusal"] is None
    retried = dispatches(host, "practice")[-1]
    assert (retried["retry_of"], retried["state"]) == (lost, supervision.DONE)
    same_request(json.loads(retried["params"]))
    # Sent once: there is nothing left to retry.
    with pytest.raises(Rejected, match="no_interrupted_practice"):
        perform(supervisor, "resume", {"campaign": identity, "retry_interrupted": True})


def test_the_browser_door_retries_through_the_same_operation(journey):
    host = journey.host
    identity = launched(host)
    dies_running(host, identity)
    host.recover(redispatch=True)
    assert host.get(identity)["recovery"] == [RETRY]
    host.control(identity, "retry_interrupted")
    join(host)
    (sent,) = journey.sent
    same_request(sent)
    assert host.get(identity)["completed_experiments"] == 1


def test_the_retry_flag_is_an_optional_boolean_on_resume(journey):
    host = journey.host
    identity = launched(host)
    dies_running(host, identity)
    host.recover(redispatch=True)
    with pytest.raises(Rejected, match="retry_interrupted_boolean_required"):
        perform(host, "resume", {"campaign": identity, "retry_interrupted": "yes"})
    assert journey.sent == [] and len(dispatches(host, "practice")) == 1
    assert "retry_interrupted" in OPERATIONS["resume"].optional
    assert OPERATIONS["resume"].required == frozenset({"campaign"})


# --- Setting on ---------------------------------------------------------------


def test_on_the_supervisor_retries_the_same_request_when_it_is_back(journey):
    host = journey.host
    auto_retry(host)
    identity = launched(host)
    lost = dies_running(host, identity)
    supervisor = journey.peer()
    assert supervisor.supervisor.tick()  # recovers, queues, and starts it
    join(supervisor)
    (sent,) = journey.sent
    same_request(sent)
    view = supervisor.get(identity)
    assert view["state"] == "READY" and view["completed_experiments"] == 1
    assert view["last_refusal"] is None and view["recovery"] == []
    first, retried = dispatches(host, "practice")
    assert (first["seq"], first["outcome"]) == (lost, "interrupted")
    assert (retried["retry_of"], retried["outcome"]) == (lost, "finished")


def test_on_retries_stop_after_the_cap_and_the_one_step_retry_remains(journey):
    host = journey.host
    auto_retry(host)
    identity = launched(host)
    lost = dies_running(host, identity)
    recovering = journey.peer()
    for attempt in range(supervision.PRACTICE_RETRY_CAP):
        # Recovery queues it again; the supervisor that claims it dies too.
        recovering.recover(redispatch=True)
        queued = dispatches(host, "practice")[-1]
        assert (queued["state"], queued["retry_of"]) == (supervision.QUEUED, lost)
        same_request(json.loads(queued["params"]))
        view = recovering.get(identity)
        assert view["last_refusal"] is None
        assert view["in_flight"]["operation"] == "practice"
        dies_running(host, identity, seq=queued["seq"])
    recovering.recover(redispatch=True)
    # The cap: no third retry, never a loop.
    practices = dispatches(host, "practice")
    assert len(practices) == 1 + supervision.PRACTICE_RETRY_CAP == 3
    assert all(d["state"] == supervision.DONE for d in practices)
    with host.db() as db:
        assert (
            supervision.practice_retries(db, principal="alice", original=lost)
            == supervision.PRACTICE_RETRY_CAP
        )
    view = recovering.get(identity)
    assert view["last_refusal"]["code"] == "operation_interrupted"
    assert view["recovery"] == [RETRY]
    recovering.recover(redispatch=True)  # nothing died: still nothing queued
    assert len(dispatches(host, "practice")) == 3
    assert journey.sent == []
    # The miner's one call still sends it.
    perform(host, "resume", {"campaign": identity, "retry_interrupted": True})
    join(host)
    (sent,) = journey.sent
    same_request(sent)
    assert host.get(identity)["completed_experiments"] == 1


def test_on_a_campaign_left_paused_is_not_retried_until_it_is_resumed(journey):
    host = journey.host
    auto_retry(host)
    identity = launched(host)
    assert host.control(identity, "pause")["state"] == "PAUSED"
    with host.db() as db:
        supervision.enqueue(
            db,
            principal="alice",
            campaign=identity,
            operation="practice",
            params=LOST,
            config_digest="sha256:parked",
            state=supervision.RUNNING,
            supervisor="sup-exited",
        )
    host.recover(redispatch=True)
    view = host.get(identity)
    assert view["state"] == "PAUSED"
    assert view["last_refusal"]["code"] == "operation_interrupted"
    assert view["recovery"] == [
        {"action": "resume", "operation": "resume"},
        {"action": "stop", "operation": "halt"},
    ]
    assert len(dispatches(host, "practice")) == 1
    with pytest.raises(Rejected, match="campaign_paused"):
        perform(host, "resume", {"campaign": identity, "retry_interrupted": True})


# --- Never a typed refusal; never a freeze, submit or commit -----------------


def test_a_practice_refused_for_a_typed_reason_is_never_retried(journey, monkeypatch):
    host = journey.host
    auto_retry(host)
    identity = launched(host)

    async def refused(prepared, **params):
        raise research_campaign.OperationRefused("over_compute_budget")

    monkeypatch.setattr(research_campaign, "practice_recipe", refused)
    perform(
        host,
        "practice",
        {
            "campaign": identity,
            "strategy": RECIPE,
            "hypothesis": "width helps",
            "idempotency_key": "practice-key-00001",
        },
    )
    join(host)
    view = host.get(identity)
    assert view["last_refusal"]["code"] == "over_compute_budget"
    assert view["last_refusal"]["operation"] == "practice"
    supervisor = journey.peer()
    assert supervisor.supervisor.tick()
    join(supervisor)
    view = supervisor.get(identity)
    assert view["last_refusal"]["code"] == "over_compute_budget"
    assert view["recovery"] == []
    assert len(dispatches(host, "practice")) == 1
    with pytest.raises(Rejected, match="no_interrupted_practice"):
        perform(host, "resume", {"campaign": identity, "retry_interrupted": True})
    # A typed interruption code is not operation_interrupted either.
    host._refused(identity, "signer_timeout", "practice", kind="interrupted")
    assert supervisor.interrupted_practice(identity) is None
    assert host.get(identity)["recovery"] == []


@pytest.mark.parametrize(
    "operation,params",
    [
        (
            "freeze_candidate",
            {"strategy": RECIPE, "reason": "it practised well", "used_feedback": False},
        ),
        ("submit", {}),
        ("commit", {"recommit": False}),
    ],
)
def test_freeze_submit_and_commit_are_never_auto_retried(journey, operation, params):
    host = journey.host
    auto_retry(host)
    identity = launched(host)
    dies_running(host, identity, operation, params)
    supervisor = journey.peer()
    assert supervisor.supervisor.tick()
    join(supervisor)
    view = supervisor.get(identity)
    refused = view["last_refusal"]
    assert (refused["code"], refused["operation"]) == (
        "operation_interrupted",
        operation,
    )
    # Its step is the code's own: it never points at a retry that is refused.
    assert refused["next_action"] == supervision.NEXT_ACTIONS["operation_interrupted"]
    assert "retry_interrupted" not in refused["next_action"]
    assert view["recovery"] == []
    assert [d["operation"] for d in dispatches(host)] == ["run", operation]
    with pytest.raises(Rejected, match="no_interrupted_practice"):
        perform(supervisor, "resume", {"campaign": identity, "retry_interrupted": True})
    assert journey.sent == []


def test_a_practice_whose_request_was_not_recorded_is_never_retried(journey):
    host = journey.host
    auto_retry(host)
    identity = launched(host)
    dies_running(host, identity, params={})
    host.recover(redispatch=True)
    view = host.get(identity)
    assert view["last_refusal"]["code"] == "operation_interrupted"
    assert view["recovery"] == []
    assert len(dispatches(host, "practice")) == 1


def test_recovery_actions_are_unchanged_without_a_practice_to_retry():
    for state in (
        "READY",
        "PAUSED",
        "INTERRUPTED",
        "PAUSE_REQUESTED",
        "RECONCILIATION_REQUIRED",
        "QUEUED",
    ):
        for resumable in (True, False):
            assert supervision.recovery_actions(
                state, None, resumable=resumable
            ) == supervision.recovery_actions(
                state, None, resumable=resumable, retry_practice=False
            )
    assert supervision.recovery_actions("READY", retry_practice=True) == [RETRY]
    assert supervision.recovery_actions(
        "READY", retry_practice=True, resumable=False
    ) == supervision.recovery_actions("READY", resumable=False)
    with pytest.raises(ValueError):
        supervision.enqueue(
            None,
            principal="alice",
            campaign="c",
            operation="submit",
            params={},
            config_digest="sha256:x",
            state=supervision.QUEUED,
            retry_of=1,
        )


# --- The setting: the runner profile, written at setup's Review ------------------

HOTKEY = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
RUNTIME = {
    "implementation": {
        "revision": "a" * 40,
        "tree": "b" * 40,
        "source_tree_digest": "sha256:" + "c" * 64,
    },
    "images": ["sha256:" + "d" * 64, "sha256:" + "e" * 64],
}


class Onboarding:
    def confirm(self, address):
        return {"registered": True, "confirmed": True}

    def requirements(self):
        return {}


class Checks:
    """Fixture live checks: contact nothing."""

    def published_pricing(self, provider_id, model_id):
        return {}

    def inference(self, provider_id, model_id, credential_file, spec=None):
        return {"models_source": "fixture", "models_listed": 1, "completion": "ok"}

    def compute(self, image, analysis):
        return RUNTIME

    @staticmethod
    def hermes_files():
        return []

    def agent(self, hotkey, socket_path=None):
        return {"signing": "carbon-miner-signer holds the registered hotkey"}

    @staticmethod
    def operator_config(path):
        if not path.is_file():
            raise SetupRefused("operator_config", "operator_config_invalid")


@pytest.fixture
def setup(tmp_path):
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    home = tmp_path / "miner"
    home.mkdir(mode=0o700)
    for name in ("worker.json", "analysis.json", "operator.json"):
        (home / name).write_text("{}")
    made = EnvironmentSetup(state, onboarding=Onboarding(), checks=Checks())
    made.begin({"address": HOTKEY})
    quote = check_quote("engy-chat", "deepseek-v4-flash-0731", Path("/never/read"))
    made.inference(
        {
            "provider_id": "engy-chat",
            "model_id": "deepseek-v4-flash-0731",
            "key": "sk-fixture-never-echoed-0123456789",
            "consent": {"max_cost_nano": quote["max_cost_nano"]},
        }
    )
    made.compute(
        {
            "choice": LOCAL_CPU,
            "image_manifest": str(home / "worker.json"),
            "analysis_image_manifest": str(home / "analysis.json"),
        }
    )
    made.agent({"choice": GRAPHITE, "operator_config": str(home / "operator.json")})
    return made


def written(setup):
    return json.loads(setup.profile_path.read_bytes())


def test_existing_profiles_parse_unchanged_and_review_writes_the_field_only_when_on(
    setup,
):
    from scripts.dev.miner_launchpad.setup_operations import MCP, status

    # A profile as Review wrote it before this setting: no field, parsed
    # exactly as it is, and off.
    reviewed = setup.review({"confirm": True})
    before = written(setup)
    assert runner.PRACTICE_AUTO_RETRY not in before
    assert runner.validated_profile(dict(before)) == before
    assert runner.practice_auto_retry(before) is False
    assert reviewed["preferences"] == {"practice_auto_retry": False}
    assert reviewed["steps"]["review"] == {"ready": True, "profile_written": True}
    assert status(setup, door=MCP)["preferences"] == {"practice_auto_retry": False}

    # Turned on: written, and nothing else in the profile changes.
    on = setup.review({"confirm": True, "practice_auto_retry": True})
    assert on["preferences"] == {"practice_auto_retry": True}
    cfg = written(setup)
    assert cfg == {**before, "practice_auto_retry": True}
    assert runner.practice_auto_retry(runner.validated_profile(cfg)) is True
    # A Review that names no choice (an update's) keeps it.
    setup.review({"confirm": True})
    assert written(setup) == cfg
    # Turned off: the profile is exactly as before the setting.
    setup.review({"confirm": True, "practice_auto_retry": False})
    assert written(setup) == before
    with pytest.raises(SetupRefused) as refused:
        setup.review({"confirm": True, "practice_auto_retry": "on"})
    assert refused.value.code == "practice_auto_retry_boolean_required"
    # A hand-written false parses; anything but a boolean does not.
    assert runner.validated_profile({**before, "practice_auto_retry": False})
    with pytest.raises(ValueError):
        runner.validated_profile({**before, "practice_auto_retry": "yes"})


ORIGINAL_STEP = (
    "The operation stopped before it finished, most likely because the "
    "process running it exited. Observe the campaign, then try again; "
    "reconcile first if it asks for reconciliation."
)


def test_only_an_interrupted_practice_names_the_one_step_retry():
    practice = supervision.refusal(
        "operation_interrupted", operation="practice", kind="interrupted"
    )
    assert "retry_interrupted: true" in practice["next_action"]
    assert "Retry practice" in practice["next_action"]
    # Submit, freeze and every other operation: the original text, unchanged.
    assert supervision.NEXT_ACTIONS["operation_interrupted"] == ORIGINAL_STEP
    for operation in ("submit", "freeze_candidate", "commit", "run", None):
        other = supervision.refusal(
            "operation_interrupted", operation=operation, kind="interrupted"
        )
        assert other["next_action"] == ORIGINAL_STEP
    # A stored entry is read back with the same step.
    stored = json.dumps(
        supervision.refusal(
            "operation_interrupted", operation="submit", kind="interrupted"
        )
    )
    assert supervision.read_refusal(stored)["next_action"] == ORIGINAL_STEP
    # The catalog serves both, the code's own step untouched.
    listed = supervision.catalog()
    assert listed["next_actions"]["operation_interrupted"] == ORIGINAL_STEP
    assert (
        listed["operation_next_actions"]["operation_interrupted"]["practice"]
        == practice["next_action"]
    )
