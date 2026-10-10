"""A campaign frozen on an old revision is refused by name (LA-F19).

Observed 2026-10-10: campaigns frozen while the shared checkout was at one
revision were submitted after it moved on and the installer re-recorded the
profile. Each Challenge's preparation refused the frozen runtime with a bare
ValueError on the operation thread, so the campaign went INTERRUPTED with
`operation_interrupted` and an untyped interruption record. Now practice,
freeze and submit are refused before anything starts, with the catalog's
recovery step, and the campaign stays readable.

Against the real campaign host (`journey_fixture`), with only preparation and
training as fixtures. No chain, provider, compute or network.
"""

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.development_session import research_campaign
from carbon.development_session.profile import canonical
from scripts.dev.miner_launchpad import supervisor as supervision
from scripts.dev.miner_launchpad.controller import Rejected, error_body
from scripts.dev.miner_launchpad.journey_fixture import FIXTURE_CHALLENGE, journey_host
from scripts.dev.miner_launchpad.operations import perform, refusal
from scripts.dev.miner_launchpad.runner import (
    FROZEN_ON_OLD_REVISION,
    RunnerAdapter,
    frozen_revision_refusal,
)

RECIPE = {
    "schema_version": "1.0",
    "challenge_id": "burgers-dynamics-v1",
    "backbone": "fno",
    "parameters": {"steps": 64},
}
OLD, NEW = "a" * 40, "b" * 40


@pytest.fixture
def journey(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    host = journey_host(tmp_path, patch=monkeypatch.setattr)
    monkeypatch.setattr(
        RunnerAdapter, "spawn", staticmethod(lambda configuration: None)
    )
    yield host
    host.close()


def join(host):
    for thread in list(host.threads.values()):
        thread.join(timeout=30)
        assert not thread.is_alive()


def frozen_campaign(host):
    """An agent-less campaign with a practiced, frozen candidate, frozen
    under the fixture profile's accepted revision (`OLD`)."""
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
    perform(
        host,
        "freeze_candidate",
        {"campaign": identity, "strategy": RECIPE, "reason": "practiced"},
    )
    join(host)
    assert host.get(identity)["journey"]["frozen_awaiting_submission"] is True
    return identity


def reinstalled(host, revision):
    """The checkout moved and the installer re-recorded the profile."""
    cfg = host.configured()
    host.configured = lambda: {
        **cfg,
        "accepted_revision": revision,
        "runtime": {**cfg["runtime"], "implementation": {"revision": revision}},
    }


def test_submit_on_a_campaign_frozen_on_an_old_revision_is_refused_by_name(
    journey,
):
    identity = frozen_campaign(journey)
    root = Path(journey._bound(identity)[2])
    manifest = (root / "campaign-manifest.json").read_text()
    assert OLD in manifest
    reinstalled(journey, NEW)
    with pytest.raises(Rejected) as refused:
        perform(
            journey,
            "submit",
            {"campaign": identity, "idempotency_key": "submit-key-0000001"},
        )
    assert (refused.value.code, refused.value.status) == (FROZEN_ON_OLD_REVISION, 409)
    join(journey)
    view = journey.get(identity)
    # Refused before the operation thread: nothing started, nothing recorded.
    assert view["state"] != "INTERRUPTED"
    assert view["in_flight"] is None and view["last_refusal"] is None
    assert not (root / "interruptions.jsonl").exists()
    assert view["journey"]["submitted_epochs"] == []
    assert view["journey"]["frozen_awaiting_submission"] is True  # kept
    # The same recovery step at every door: the catalog's.
    step = supervision.NEXT_ACTIONS[FROZEN_ON_OLD_REVISION]
    assert "Launch a new campaign" in step and "nothing to recommit" in step
    assert refusal(FROZEN_ON_OLD_REVISION) == {
        "error": FROZEN_ON_OLD_REVISION,
        "next_step": step,
        "field": "campaign",
    }
    assert error_body(FROZEN_ON_OLD_REVISION)["next_step"] == step
    assert supervision.refusal(FROZEN_ON_OLD_REVISION)["next_action"] == step


def test_new_work_is_refused_but_the_campaign_stays_readable(journey):
    identity = frozen_campaign(journey)
    reinstalled(journey, NEW)
    with pytest.raises(Rejected, match=FROZEN_ON_OLD_REVISION):
        perform(
            journey,
            "practice",
            {
                "campaign": identity,
                "strategy": RECIPE,
                "hypothesis": "depth helps",
                "idempotency_key": "practice-key-00002",
            },
        )
    with pytest.raises(Rejected, match=FROZEN_ON_OLD_REVISION):
        perform(
            journey,
            "freeze_candidate",
            {"campaign": identity, "strategy": RECIPE, "reason": "again"},
        )
    observed = perform(journey, "observe", {"campaign": identity})
    assert observed["id"] == identity
    view = journey.get(identity)
    assert view["state"] != "INTERRUPTED" and view["in_flight"] is None


def test_a_campaign_frozen_on_the_accepted_revision_is_unaffected(journey):
    identity = frozen_campaign(journey)
    reinstalled(journey, OLD)  # Re-recorded, same revision.
    perform(
        journey,
        "submit",
        {"campaign": identity, "idempotency_key": "submit-key-0000001"},
    )
    join(journey)
    view = journey.get(identity)
    assert view["journey"]["submitted_epochs"] == [1]
    assert view["state"] != "INTERRUPTED" and view["last_refusal"] is None


def test_frozen_revision_refusal_judges_only_a_named_revision():
    cfg = {"accepted_revision": NEW}
    old = {"implementation": {"revision": OLD}}
    assert frozen_revision_refusal(cfg, old) == FROZEN_ON_OLD_REVISION
    assert frozen_revision_refusal(cfg, {"implementation": {"revision": NEW}}) is None
    # Nothing named: left to preparation, which refuses it by its own check.
    assert frozen_revision_refusal(cfg, {}) is None
    assert frozen_revision_refusal(cfg, {"implementation": None}) is None


def test_preparation_names_it_too_so_the_thread_never_records_a_bare_error(
    tmp_path,
):
    """The source's own typed refusal: `research_campaign.prepare` raises
    `OperationRefused`, which the operation thread records as a named
    refusal, never as an untyped interruption."""
    (tmp_path / "campaign-manifest.json").write_bytes(
        canonical({"implementation": {"revision": OLD}})
    )
    args = SimpleNamespace(root=tmp_path, command="resume", accepted_revision=NEW)
    with pytest.raises(research_campaign.OperationRefused) as refused:
        asyncio.run(research_campaign.prepare(args))
    assert refused.value.code == FROZEN_ON_OLD_REVISION
    assert supervision.exception_code(refused.value) == FROZEN_ON_OLD_REVISION
    # The same revision, a new campaign, or no manifest: not judged here.
    research_campaign.refuse_old_revision(
        SimpleNamespace(root=tmp_path, command="resume", accepted_revision=OLD)
    )
    research_campaign.refuse_old_revision(
        SimpleNamespace(root=tmp_path, command="run", accepted_revision=NEW)
    )
    research_campaign.refuse_old_revision(
        SimpleNamespace(root=tmp_path / "none", command="resume", accepted_revision=NEW)
    )
