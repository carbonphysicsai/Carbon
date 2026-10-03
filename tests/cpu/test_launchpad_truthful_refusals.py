"""Truthful state and named refusals at every door (LP-PROD-C, part 2).

Observed live on 2026-10-03 and confirmed in the code: a submit refused on its
thread (no validator configured) left the page reading "Submitted"; the HTTP
door answered every ValueError and RuntimeError `research_reconciliation_required`;
a stale accepted revision surfaced only as an interrupted campaign; changing
any profile setting refused every resume; practice on a campaign an agent held
answered PRACTICING and then failed; and one campaign whose records could not
be read back took the whole campaign list down.

Against the real campaign host (`journey_fixture`), with only preparation and
training as fixtures. No chain, provider, compute or network beyond loopback.
"""

import contextlib
import dataclasses
import http.client
import json
import os
import sqlite3
import subprocess
import threading
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from carbon.development_session import research_campaign
from carbon.development_session.profile import canonical
from carbon.development_session.research_control import CampaignControl
from carbon.development_session.research_ledger import CampaignLedger
from scripts.dev.miner_launchpad import supervisor as supervision
from scripts.dev.miner_launchpad.campaign_view import stages
from scripts.dev.miner_launchpad.controller import (
    Controller,
    LockHeld,
    Rejected,
    Server,
    error_body,
    failure_answer,
    owner_lock,
    session_link_supported,
    session_url,
)
from scripts.dev.miner_launchpad.journey_fixture import (
    FIXTURE_CHALLENGE,
    journey_host,
    reference_burgers_campaign,
)
from scripts.dev.miner_launchpad.operations import perform
from scripts.dev.miner_launchpad.projection import RecordsDiffer
from scripts.dev.miner_launchpad.runner import (
    CARBON_UPDATED,
    PATH_FIELDS,
    RunnerAdapter,
    binding_changes,
    campaign_args,
    checkout_refusal,
    evaluation_refusal,
)

RECIPE = {
    "schema_version": "1.0",
    "challenge_id": "burgers-dynamics-v1",
    "backbone": "fno",
    "parameters": {"steps": 64},
}
TOKEN = "fixture-token-long-enough-for-session"
INTAKE = "https://validator.example/intake"


@pytest.fixture
def journey(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    host = journey_host(tmp_path, patch=monkeypatch.setattr)
    monkeypatch.setattr(
        RunnerAdapter, "spawn", staticmethod(lambda configuration: None)
    )
    yield host
    host.close()


def launch(host, key="launch-key-0000001", agent="none"):
    return perform(
        host,
        "launch",
        {
            "challenge": FIXTURE_CHALLENGE["id"],
            "challenge_version": FIXTURE_CHALLENGE["version"],
            "agent": agent,
            "idempotency_key": key,
        },
    )


def practice(identity, key):
    return {
        "campaign": identity,
        "strategy": RECIPE,
        "hypothesis": "width helps",
        "idempotency_key": key,
    }


def join(host):
    for thread in list(host.threads.values()):
        thread.join(timeout=30)
        assert not thread.is_alive()


def root_of(host, identity):
    return Path(host._bound(identity)[2])


def frozen_campaign(host):
    """An agent-less campaign with a practiced, frozen candidate."""
    identity = launch(host)["id"]
    join(host)
    perform(host, "practice", practice(identity, "practice-key-00001"))
    join(host)
    perform(
        host,
        "freeze_candidate",
        {"campaign": identity, "strategy": RECIPE, "reason": "practiced"},
    )
    join(host)
    assert host.get(identity)["journey"]["frozen_awaiting_submission"] is True
    return identity


def evaluated_by_a_validator(monkeypatch):
    """The fixture Challenge's campaign, declaring validator feedback as the
    battery campaign does, so a submit needs a configured deployment."""
    from carbon.challenge_registry import campaigns

    validated = dataclasses.replace(
        reference_burgers_campaign(), feedback_schema="fixture.permitted-feedback.v1"
    )
    mapping = campaigns._campaigns
    monkeypatch.setattr(
        campaigns,
        "_campaigns",
        lambda: {**mapping(), FIXTURE_CHALLENGE["id"]: lambda: validated},
    )


# --- item 5 / D11: a submit that cannot be evaluated is refused at once --------


def test_a_submit_with_no_validator_for_its_challenge_is_refused_at_once(
    journey, monkeypatch
):
    """The live failure: no validator or intake for the Challenge, the submit
    answered SUBMITTING, the page said "Submitted", and the refusal went only
    to the owner-only interruptions file."""
    evaluated_by_a_validator(monkeypatch)
    identity = frozen_campaign(journey)
    submit = {"campaign": identity, "idempotency_key": "submit-key-0000001"}
    with pytest.raises(Rejected, match="evaluation_unavailable"):
        perform(journey, "submit", submit)
    view = journey.get(identity)
    assert view["in_flight"] is None and view["last_refusal"] is None
    assert view["journey"]["submitted_epochs"] == []
    assert view["journey"]["frozen_awaiting_submission"] is True  # kept
    # Nothing was recorded under the key: once an intake is configured the
    # same request is admitted, not replayed.
    cfg = journey.configured()
    journey.configured = lambda: {**cfg, "intakes": {FIXTURE_CHALLENGE["id"]: INTAKE}}
    perform(journey, "submit", submit)
    join(journey)
    assert journey.get(identity)["journey"]["submitted_epochs"] == [1]


def test_the_gate_reads_what_the_battery_campaign_submits_through(tmp_path):
    """`evaluation_refusal` answers from exactly what
    `carbon.battery.campaign` reads when it submits - per-Challenge
    `validators` and `intakes` and their legacy names - for every shape."""
    from carbon.battery import campaign as battery
    from carbon.challenge_registry.campaigns import challenge_ref
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

    manifest = {"challenge": challenge_ref(BATTERY_CHALLENGE)}
    base = {"paths": {"miner_public": "/fixture/miner-public.json"}}
    shapes = [
        base,
        {**base, "intakes": {BATTERY_CHALLENGE: INTAKE}},
        {**base, "battery_intake": INTAKE},
        {**base, "validators": {BATTERY_CHALLENGE: "/srv/validator"}},
        {"paths": {**base["paths"], "battery_validator": "/srv/validator"}},
    ]
    answers = []
    for cfg in shapes:
        prepared = SimpleNamespace(args=campaign_args(cfg, root=tmp_path))
        configured = battery.evaluation_config(prepared) or battery._intake(prepared)
        refused = evaluation_refusal(cfg, manifest)
        assert (refused is None) == (configured is not None), cfg
        answers.append(refused)
    assert answers == ["evaluation_unavailable", None, None, None, None]


def test_the_mirror_knows_every_argument_the_battery_campaign_reads(tmp_path):
    """`evaluation_refusal` mirrors the battery campaign's readers instead of
    importing them (this runner names no Challenge's module). Any argument
    those readers start to read that the mirror does not know fails here,
    so the synchronous gate cannot drift from what submission reads."""
    from carbon.battery import campaign as battery

    read = set()

    class Recording(SimpleNamespace):
        def __getattribute__(self, name):
            if not name.startswith("__"):
                read.add(name)
            return super().__getattribute__(name)

    cfg = {"paths": {"miner_public": "/fixture/miner-public.json"}}
    prepared = SimpleNamespace(
        args=Recording(**vars(campaign_args(cfg, root=tmp_path)))
    )
    battery.evaluation_config(prepared)
    battery._intake(prepared)
    # What `runner.validators` and `runner.intakes` read, by name and legacy name.
    assert read <= {"validators", "intakes", "battery_validator", "battery_intake"}
    assert {"validators", "intakes"} <= read


def test_the_http_door_says_what_to_do_about_a_submit_it_refuses(
    journey, monkeypatch, tmp_path
):
    """Review finding: the synchronous `evaluation_unavailable` came with no
    next action at either door. The browser's answer now carries it."""
    evaluated_by_a_validator(monkeypatch)
    identity = frozen_campaign(journey)
    server, thread = serve(tmp_path, journey)
    try:
        answer = request(
            server,
            "POST",
            "/api/v1/operations/submit",
            {"campaign": identity, "idempotency_key": "submit-key-0000001"},
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
    assert answer == (
        409,
        {
            "error": "evaluation_unavailable",
            "next_step": supervision.NEXT_ACTIONS["evaluation_unavailable"],
        },
    )


def test_a_submit_refuses_at_once_what_its_thread_would_have(tmp_path):
    """Carbon's agent selects, or both final exams are used: named now,
    never answered SUBMITTING."""
    root = tmp_path / "campaign"
    root.mkdir()
    admitted = SimpleNamespace(campaign={"root": str(root)})
    manifest = root / "campaign-manifest.json"
    manifest.write_bytes(canonical({"agent": "autonomous"}))
    with pytest.raises(Rejected, match="the_agent_selects_in_this_campaign"):
        RunnerAdapter._require_frozen(admitted)
    manifest.write_bytes(canonical({"agent": "none"}))
    with pytest.raises(Rejected, match="freeze_a_candidate_first"):
        RunnerAdapter._require_frozen(admitted)
    for epoch in (1, 2):
        folder = root / ("epoch-" + str(epoch))
        folder.mkdir()
        (folder / "permitted-final-feedback.json").write_text("{}")
    with pytest.raises(Rejected, match="final_exams_used"):
        RunnerAdapter._require_frozen(admitted)


def test_the_stage_a_refusal_belongs_to_says_so():
    entry = supervision.refusal("evaluation_failed_infra", operation="submit")
    own = {
        "state": "READY",
        "journey": {"frozen_awaiting_submission": True, "final_exams_remaining": 2},
        "candidate_freezes": [{"epoch": 1}],
        "last_refusal": entry,
    }
    submit = {s["id"]: s for s in stages(own)}["submit"]
    assert submit["refusal"] == {
        "code": "evaluation_failed_infra",
        "next_action": supervision.NEXT_ACTIONS["evaluation_failed_infra"],
        "kind": "refused",
    }
    assert "last attempt refused: evaluation_failed_infra" in submit["detail"]
    assert all("refusal" not in s for s in stages({**own, "last_refusal": None}))


# --- item 8 / D11: a held campaign is refused before the thread starts ---------


def test_a_held_campaign_refuses_practice_at_once_and_records_nothing(journey):
    identity = launch(journey)["id"]
    join(journey)
    client = RunnerAdapter(
        journey.database,
        principal="alice",
        registration=journey.registration,
        role=supervision.CLIENT,
    )
    client.configured = journey.configured
    try:
        with owner_lock(root_of(journey, identity)):  # an attached agent
            for door in (journey, client):
                with pytest.raises(Rejected, match="campaign_busy"):
                    perform(door, "practice", practice(identity, "practice-key-00001"))
        with journey.db() as db:
            queued = db.execute(
                "SELECT COUNT(*) FROM launchpad_dispatch WHERE operation='practice'"
            ).fetchone()[0]
        assert queued == 0
        assert journey.get(identity)["last_refusal"] is None
        # Detached: the same key is admitted (nothing was recorded under it).
        perform(journey, "practice", practice(identity, "practice-key-00001"))
        join(journey)
        view = journey.get(identity)
        assert view["completed_experiments"] == 1 and view["last_refusal"] is None
    finally:
        client.close()


def test_a_campaign_thread_waits_out_a_doors_instant_probe(tmp_path):
    root = tmp_path / "campaign"
    root.mkdir()
    host = RunnerAdapter(tmp_path / "runner.sqlite3", principal="alice")
    held, release = threading.Event(), threading.Event()

    def holder():
        with owner_lock(root):
            held.set()
            release.wait(10)

    thread = threading.Thread(target=holder)
    thread.start()
    assert held.wait(10)
    threading.Timer(0.2, release.set).start()
    with ExitStack() as stack:
        host._hold(stack, root)  # taken once the holder lets go
    thread.join(10)
    host.LOCK_WAIT_SECONDS = 0.1
    with owner_lock(root), ExitStack() as stack, pytest.raises(LockHeld):
        host._hold(stack, root)


def test_a_paused_agents_run_is_named_as_what_holds_the_tools(journey):
    identity = launch(journey)["id"]
    join(journey)
    journey.threads[identity] = SimpleNamespace(is_alive=lambda: True)
    try:
        assert journey.tools_busy_hint(identity) == "carbon_agent_or_operation"
        CampaignControl(CampaignLedger(root_of(journey, identity))).request("pause")
        assert journey.tools_busy_hint(identity) == "carbon_agent_paused"
    finally:
        del journey.threads[identity]


def test_the_tools_door_names_the_check_that_refused_it():
    from carbon.miner_mcp.standard_cli import AttachRefused
    from scripts.dev.miner_launchpad.tool_door import ToolSessions

    def opener_raising(failure):
        @contextlib.asynccontextmanager
        async def opener(campaign):
            raise failure
            yield

        return opener

    left = AttachRefused("task_left_running", "uncertain task")
    with pytest.raises(Rejected) as refused:
        ToolSessions(opener_raising(left)).open("c" * 32)
    assert refused.value.code == "task_left_running"
    with pytest.raises(Rejected) as refused:
        ToolSessions(opener_raising(RuntimeError("private detail"))).open("c" * 32)
    assert refused.value.code == "tools_unavailable_for_campaign"


# --- item 7 / D10: resume is bound to the frozen campaign ----------------------


def test_resume_is_bound_to_the_frozen_campaign_not_the_whole_profile(journey):
    identity = launch(journey)["id"]
    join(journey)
    cfg = journey.configured()
    assert journey.control(identity, "pause")["state"] == "PAUSED"
    # Settings the campaign was not frozen with changed: it resumes. Until
    # 2026-10-03 any change to the profile refused every resume.
    journey.configured = lambda: {
        **cfg,
        "profile_id": "renamed-profile",
        "intakes": {FIXTURE_CHALLENGE["id"]: INTAKE},
    }
    journey.control(identity, "resume")
    join(journey)
    assert journey.get(identity)["state"] == "READY"
    # What it was frozen with changed: refused by name, nothing started.
    assert journey.control(identity, "pause")["state"] == "PAUSED"
    journey.configured = lambda: {
        **cfg,
        "accepted_revision": "b" * 40,
        "runtime": {**cfg["runtime"], "implementation": {"revision": "b" * 40}},
    }
    with pytest.raises(Rejected, match="profile_changed_since_launch"):
        journey.control(identity, "resume")
    view = journey.get(identity)
    assert view["state"] == "PAUSED" and view["in_flight"] is None


def test_a_launch_never_prepared_stays_bound_to_the_profile_its_miner_reviewed(
    journey,
):
    client = RunnerAdapter(
        journey.database,
        principal="alice",
        registration=journey.registration,
        role=supervision.CLIENT,
    )
    client.configured = journey.configured
    try:
        identity = launch(client)["id"]
        with client.db() as db:
            db.execute("UPDATE launchpad_dispatch SET state='DONE'")
        cfg = journey.configured()
        client.configured = lambda: {**cfg, "profile_id": "renamed-profile"}
        with pytest.raises(Rejected, match="profile_changed_since_launch"):
            client.control(identity, "resume")
    finally:
        client.close()


def test_binding_changes_names_each_frozen_field(tmp_path):
    public = tmp_path / "miner-public.json"
    public.write_text(json.dumps({"hotkey": "5Frozen"}))
    cfg = {
        "principal": "alice",
        "accepted_revision": "a" * 40,
        "runtime": {"images": ["sha256:worker", "sha256:analysis"]},
        "paths": {"miner_public": str(public)},
    }
    manifest = {
        "principal": "alice",
        "implementation": {"revision": "a" * 40},
        "images": ["sha256:worker", "sha256:analysis"],
        "admission": {"hotkey": "5Frozen"},
    }
    row = {"research_guidance": None}
    assert binding_changes(cfg, row, manifest) == []
    unrelated = {
        **cfg,
        "profile_id": "renamed",
        "intakes": {"battery": INTAKE},
        "model_selection": {"provider_id": "x", "model_id": "y"},
        "remote_machine": {"transport": "ssh-docker"},
        "enabled": False,
    }
    assert binding_changes(unrelated, row, manifest) == []
    assert binding_changes({**cfg, "principal": "bob"}, row, manifest) == ["principal"]
    assert binding_changes({**cfg, "accepted_revision": "b" * 40}, row, manifest) == [
        "revision"
    ]
    images = {**cfg, "runtime": {"images": ["sha256:rebuilt", "sha256:analysis"]}}
    assert binding_changes(images, row, manifest) == ["images"]
    guided = {**cfg, "research_guidance": "Try wider operators first."}
    assert binding_changes(guided, row, manifest) == ["research_guidance"]
    public.write_text(json.dumps({"hotkey": "5Another"}))
    assert binding_changes(cfg, row, manifest) == ["hotkey"]
    public.unlink()  # unreadable here: preparation judges it
    assert binding_changes(cfg, row, manifest) == []


# --- item 6 / D9: a checkout updated after the installer is named --------------


def git_repository(tmp_path):
    """A throwaway repository with two commits, isolated from any user or
    system git configuration."""
    repository = tmp_path / "repository"
    repository.mkdir()
    environment = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    }

    def git(*argv):
        return subprocess.run(
            ["git", *argv],
            cwd=repository,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    git("init", "-q")
    git("commit", "-q", "--allow-empty", "-m", "accepted")
    accepted = git("rev-parse", "HEAD")
    git("commit", "-q", "--allow-empty", "-m", "updated")
    return repository, accepted, git("rev-parse", "HEAD")


def test_a_checkout_updated_after_the_profile_was_written_is_named(tmp_path):
    repository, accepted, updated = git_repository(tmp_path)
    assert checkout_refusal({"accepted_revision": accepted}, repository) == (
        CARBON_UPDATED
    )
    assert checkout_refusal({"accepted_revision": updated}, repository) is None
    # What this checkout cannot judge is left to execution's own check.
    assert checkout_refusal({"accepted_revision": "f" * 40}, repository) is None
    assert checkout_refusal({}, repository) is None
    missing = tmp_path / "no-checkout"
    assert checkout_refusal({"accepted_revision": accepted}, missing) is None


def test_a_worker_image_the_profile_did_not_accept_is_named(tmp_path):
    from carbon.reconstruction.worker.docker_runtime import load_image_identity

    record = tmp_path / "worker-image.json"
    identity = {
        "schema": "carbon.c03.worker-image.v1",
        "image_id": "sha256:" + "1" * 64,
        "config_digest": "sha256:" + "1" * 64,
        "source_tree_digest": "sha256:" + "2" * 64,
        **{
            name: "sha256:" + "0" * 64
            for name in (
                "wheel_digest",
                "lock_digest",
                "base_image_digest",
                "build_recipe_digest",
                "entrypoint_digest",
            )
        },
    }
    record.write_text(json.dumps(identity))
    assert load_image_identity(record).image_id == identity["image_id"]
    runtime = {
        "implementation": {"source_tree_digest": identity["source_tree_digest"]},
        "images": [identity["image_id"], "sha256:" + "5" * 64],
    }
    cfg = {"paths": {"image_manifest": str(record)}, "runtime": runtime}
    nowhere = tmp_path / "no-checkout"
    assert checkout_refusal(cfg, nowhere) is None
    rebuilt = {**cfg, "runtime": {**runtime, "images": ["sha256:" + "3" * 64]}}
    assert checkout_refusal(rebuilt, nowhere) == CARBON_UPDATED
    source = {"source_tree_digest": "sha256:" + "4" * 64}
    other = {**cfg, "runtime": {**runtime, "implementation": source}}
    assert checkout_refusal(other, nowhere) == CARBON_UPDATED


def test_new_work_on_an_updated_checkout_is_refused_before_it_starts(
    journey, monkeypatch
):
    identity = launch(journey)["id"]
    join(journey)
    monkeypatch.setattr(
        RunnerAdapter, "checkout_refusal", staticmethod(lambda cfg: CARBON_UPDATED)
    )
    with pytest.raises(Rejected, match=CARBON_UPDATED):
        launch(journey, key="launch-key-0000002")
    with pytest.raises(Rejected, match=CARBON_UPDATED):
        perform(journey, "practice", practice(identity, "practice-key-00001"))
    journey.control(identity, "pause")
    with pytest.raises(Rejected, match=CARBON_UPDATED):
        journey.control(identity, "resume")
    assert [run["id"] for run in journey.recent()] == [identity]
    # A launch already admitted still replays: only new work is refused.
    assert launch(journey)["id"] == identity


def test_preflight_names_an_updated_checkout(tmp_path, monkeypatch):
    path = minimal_profile(tmp_path)
    host = RunnerAdapter(
        tmp_path / "runner.sqlite3", configuration=path, registration=lambda _: None
    )
    assert host.preflight()["available"] is True
    monkeypatch.setattr(
        RunnerAdapter, "checkout_refusal", staticmethod(lambda cfg: CARBON_UPDATED)
    )
    value = host.preflight()
    assert value["available"] is False
    assert (value["status"], value["code"]) == ("CARBON_UPDATED", CARBON_UPDATED)
    assert value["reason"] == supervision.NEXT_ACTIONS[CARBON_UPDATED]
    assert str(tmp_path) not in json.dumps(value)


# --- item 6 / D8: the HTTP door answers what failed ----------------------------


class FailingHost:
    """A campaign host whose reads and controls fail with `failure`."""

    tool_sessions = None

    def __init__(self, failure):
        self.failure = failure

    def preflight(self):
        return {"available": False, "status": "FIXTURE"}

    def recent(self):
        return []

    def get(self, identity):
        raise self.failure

    def control(self, identity, action):
        raise self.failure


def serve(tmp_path, runner):
    server = Server(
        Controller(tmp_path / "http.sqlite3"), TOKEN, 0, research_runner=runner
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def request(server, method, path, body=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
    headers = {
        "Host": server.authority,
        "Authorization": "Bearer " + TOKEN,
    }
    payload = None
    if body is not None:
        payload = json.dumps(body)
        headers["Content-Type"] = "application/json"
    try:
        connection.request(method, path, payload, headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("failure", "reading", "writing"),
    [
        (
            RecordsDiffer("campaign projection association differs"),
            "campaign_readback_unavailable",
            "campaign_readback_unavailable",
        ),
        (
            ValueError("private detail"),
            "campaign_read_failed",
            "operation_not_completed",
        ),
        (
            RuntimeError("private detail"),
            "campaign_read_failed",
            "operation_not_completed",
        ),
        (
            LockHeld("Another launcher owns this state directory"),
            "campaign_busy",
            "campaign_busy",
        ),
        (
            research_campaign.OperationRefused("evaluation_queued"),
            "evaluation_queued",
            "evaluation_queued",
        ),
    ],
)
def test_the_http_door_answers_what_failed_not_reconciliation(
    tmp_path, failure, reading, writing
):
    """Until 2026-10-03 every ValueError and RuntimeError was answered
    `research_reconciliation_required`, naming a state the campaign was not
    in. A held lock is campaign_busy; a typed failure is its own code; a
    campaign whose records disagree is `campaign_readback_unavailable`, and
    one that merely could not be read just now is the milder
    `campaign_read_failed` (review: an unexpected error was told to launch a
    new campaign)."""
    server, thread = serve(tmp_path, FailingHost(failure))
    identity = "e" * 32
    try:
        read = request(server, "GET", "/api/v1/research/" + identity)
        wrote = request(server, "POST", "/api/v1/research/" + identity + "/pause", {})
        refusals = request(server, "GET", "/api/v1/refusals")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
    # Each answer carries its next step (review: a synchronous refusal gave
    # none), the catalog's fixed text, under the name setup refusals use.
    next_actions = supervision.NEXT_ACTIONS
    assert read == (409, {"error": reading, "next_step": next_actions[reading]})
    assert wrote == (409, {"error": writing, "next_step": next_actions[writing]})
    assert refusals == (200, supervision.catalog())
    assert "private detail" not in json.dumps([read, wrote])


def test_an_error_body_carries_the_catalogs_next_step_only():
    """`next_step` is the catalog's text for a code it names; a setup
    refusal's own field and step win; an unnamed code stays `{error}`."""
    assert error_body("campaign_busy") == {
        "error": "campaign_busy",
        "next_step": supervision.NEXT_ACTIONS["campaign_busy"],
    }
    assert error_body("closed_request_required") == {"error": "closed_request_required"}
    own = SimpleNamespace(field="address", next_step="Paste your hotkey address.")
    assert error_body("hotkey_address_required", own) == {
        "error": "hotkey_address_required",
        "field": "address",
        "next_step": "Paste your hotkey address.",
    }


def test_failure_answers_are_closed():
    assert failure_answer(ValueError("x"), reading=True) == (
        409,
        "readback_unavailable",
    )
    assert failure_answer(ValueError("x"), reading=True, campaign=True) == (
        409,
        "campaign_read_failed",
    )
    assert failure_answer(RecordsDiffer("x"), reading=True, campaign=True) == (
        409,
        "campaign_readback_unavailable",
    )
    assert failure_answer(KeyError("x"), reading=False) == (
        409,
        "operation_not_completed",
    )
    # A code that is not a closed identifier is never echoed.
    hostile = SimpleNamespace(code="Provider said: SECRET token=abc")
    assert supervision.exception_code(hostile) is None
    listed = supervision.catalog()
    assert listed["schema"] == "carbon.launchpad.refusal-catalog.v1"
    assert listed["fallback"] == supervision.FALLBACK_ACTION
    # Every code this slice answers or records has its own next action.
    for code in (
        "campaign_busy",
        "campaign_paused",
        "campaign_readback_unavailable",
        "campaign_read_failed",
        "readback_unavailable",
        "operation_not_completed",
        "profile_changed_since_launch",
        CARBON_UPDATED,
        "evaluation_unavailable",
        "task_left_running",
        "the_agent_selects_in_this_campaign",
        "final_exams_used",
        "campaign_owner_changed",
        supervision.HANDED_OVER,
        "withdrawn_when_supervisor_closed",
    ):
        assert code in listed["next_actions"], code


# --- item 9 / D13: one unreadable campaign never takes the list down -----------


def test_one_unreadable_campaign_never_takes_the_list_down(journey, tmp_path):
    good = launch(journey)["id"]
    join(journey)
    bad = launch(journey, key="launch-key-0000002")["id"]
    join(journey)
    with journey.db() as db:
        db.execute(
            "UPDATE launchpad_campaigns SET campaign=? WHERE id=?",
            ("cmp-elsewhere", bad),
        )
    with pytest.raises(ValueError, match="association differs"):
        journey.get(bad)
    rows = {row["id"]: row for row in journey.recent()}
    assert rows[good]["state"] == "READY"
    assert rows[bad]["state"] == "READBACK_UNAVAILABLE"
    assert rows[bad]["code"] == "campaign_readback_unavailable"
    assert (
        rows[bad]["next_action"]
        == supervision.NEXT_ACTIONS["campaign_readback_unavailable"]
    )
    server, thread = serve(tmp_path, journey)
    try:
        listed = request(server, "GET", "/api/v1/research")
        one = request(server, "GET", "/api/v1/research/" + bad)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
    assert listed[0] == 200 and len(listed[1]["runs"]) == 2
    assert one == (
        409,
        {
            "error": "campaign_readback_unavailable",
            "next_step": supervision.NEXT_ACTIONS["campaign_readback_unavailable"],
        },
    )
    # A failure that may pass (a busy database) is never advice to abandon
    # the campaign (review nit): it is `campaign_read_failed`.
    real = journey.get

    def busy(identity):
        if identity == good:
            raise sqlite3.OperationalError("database is locked")
        return real(identity)

    journey.get = busy
    try:
        rows = {row["id"]: row for row in journey.recent()}
    finally:
        del journey.get
    assert (rows[good]["state"], rows[good]["code"]) == (
        "READBACK_UNAVAILABLE",
        "campaign_read_failed",
    )
    assert rows[good]["next_action"] == supervision.NEXT_ACTIONS["campaign_read_failed"]
    assert rows[bad]["code"] == "campaign_readback_unavailable"


# --- item 10 / D14: the session link --------------------------------------------


def test_the_session_link_keeps_the_token_in_its_fragment():
    """A fragment never reaches the server, its log or a Referer; the page
    reads it once and removes it (slice F)."""
    parts = urlsplit(session_url("http://127.0.0.1:8788", "token_0123-abc"))
    assert (parts.scheme, parts.netloc, parts.path, parts.query) == (
        "http",
        "127.0.0.1:8788",
        "/",
        "",
    )
    assert parts.fragment == "token=token_0123-abc"


def test_the_session_link_is_printed_only_once_the_page_reads_it(tmp_path):
    """Review finding: a page that does not read `#token=` would keep the
    printed link's token in its saved route and history, and not connect.
    So the link is printed only once the page declares, in its own head,
    that it reads the fragment (slice F), whatever order the two land in."""
    page = tmp_path / "index.html"
    page.write_text('<head><meta charset="utf-8"></head>', encoding="utf-8")
    assert not session_link_supported(page)
    page.write_text(
        '<head><meta name="carbon-session-link"  content="fragment-v1"></head>',
        encoding="utf-8",
    )
    assert session_link_supported(page)
    for other in ('content="fragment-v2"', 'content="yes"'):
        page.write_text(
            f'<head><meta name="carbon-session-link" {other}></head>', encoding="utf-8"
        )
        assert not session_link_supported(page)
    assert not session_link_supported(tmp_path / "missing.html")


# --- helpers ---------------------------------------------------------------------


def minimal_profile(tmp_path):
    """A closed runner profile v2 that names files it never opens here."""
    tmp_path.chmod(0o700)
    campaigns = tmp_path / "campaigns"
    campaigns.mkdir(mode=0o700, exist_ok=True)
    revision = "a" * 40
    cfg = {
        "schema": "carbon.launchpad.runner-profile.v2",
        "profile_id": "truthful-profile",
        "principal": "alice",
        "enabled": True,
        "accepted_revision": revision,
        "campaigns_root": str(campaigns),
        "runtime": {
            "implementation": {
                "revision": revision,
                "tree": "b" * 40,
                "source_tree_digest": "sha256:" + "c" * 64,
            },
            "images": ["sha256:" + "d" * 64],
        },
        "paths": {
            key: str(tmp_path / (key + ".json"))
            for key in PATH_FIELDS | {"operator_config"}
        },
    }
    path = tmp_path / "runner-profile.json"
    path.write_bytes(canonical(cfg))
    path.chmod(0o600)
    return path
