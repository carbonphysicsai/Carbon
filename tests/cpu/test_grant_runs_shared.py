"""A grant's run count is shared across every controller root on the host.

Stage A's 5-run Constructor grant ran a sixth run from a new controller root because each
root counted its own runs. A LIVE controller (`shared_runs=True`) claims each launch in one
host-level ledger keyed by grant id: locked, outside the repository, counts and ids only,
and failing closed.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from test_agent_campaign_controller import (
    PROFILE,
    Clock,
    grant_document,
    register,
    spec,
)

from carbon.agent_campaign import controller as ctl
from carbon.agent_campaign import grant_runs
from carbon.agent_campaign.fake import FakeProvider
from carbon.agent_campaign.grant import SpendingGrant

REPOSITORY = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def ledger(tmp_path, monkeypatch):
    directory = tmp_path / "host-ledger"
    monkeypatch.setenv(grant_runs.ENV, str(directory))
    return directory


def live(tmp_path, name, runs=3, **grant):
    controller = ctl.CampaignController(
        root=tmp_path / name,
        provider=FakeProvider(),
        grant=SpendingGrant.from_document(
            grant_document(permitted_runs=runs, max_concurrency=10, **grant)
        ),
        operator="carbon-operator",
        clock=Clock(),
        shared_runs=True,
    )
    register(controller, ceiling="9.00")
    return controller


def launch(controller, key):
    return controller.launch(spec(), key)


def test_two_roots_on_one_grant_share_the_cap(tmp_path):
    first, second = live(tmp_path, "root-a"), live(tmp_path, "root-b")
    launch(first, "a1")
    launch(first, "a2")
    launch(second, "b1")  # the third run of the grant, from another root
    with pytest.raises(ctl.ControllerError, match="run_limit_reached"):
        launch(second, "b2")  # the fourth: this root alone has used only one
    with pytest.raises(ctl.ControllerError, match="run_limit_reached"):
        launch(first, "a3")
    assert grant_runs.count("test-grant") == 3


def test_a_relaunch_of_the_same_key_is_not_counted_twice(tmp_path):
    controller = live(tmp_path, "root-a")
    launch(controller, "k1")
    launch(controller, "k1")
    assert grant_runs.count("test-grant") == 1


def test_different_grants_have_different_counts(tmp_path):
    other = live(tmp_path, "root-a", grant_id="other-grant")
    mine = live(tmp_path, "root-b")
    launch(other, "o1")
    launch(mine, "m1")
    assert grant_runs.count("other-grant") == 1 and grant_runs.count("test-grant") == 1


def test_a_corrupt_ledger_refuses_every_launch(tmp_path, ledger):
    controller = live(tmp_path, "root-a")
    launch(controller, "k1")
    [path] = list(ledger.glob("*.jsonl"))
    path.write_bytes(path.read_bytes() + b"not json\n")
    with pytest.raises(ctl.ControllerError, match="grant_runs_unavailable"):
        launch(controller, "k2")
    with pytest.raises(grant_runs.SharedRunsError):
        grant_runs.count("test-grant")


def test_an_unusable_ledger_directory_refuses_the_launch(tmp_path, monkeypatch):
    blocker = tmp_path / "a-file"
    blocker.write_text("x")
    monkeypatch.setenv(grant_runs.ENV, str(blocker / "ledger"))
    controller = live(tmp_path, "root-a")
    with pytest.raises(ctl.ControllerError, match="grant_runs_unavailable"):
        launch(controller, "k1")


def test_a_directory_inside_the_repository_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv(grant_runs.ENV, str(REPOSITORY / "tmp-grant-runs"))
    controller = live(tmp_path, "root-a")
    with pytest.raises(ctl.ControllerError, match="grant_runs_unavailable"):
        launch(controller, "k1")
    assert not (REPOSITORY / "tmp-grant-runs").exists()


def test_a_relative_directory_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv(grant_runs.ENV, "relative/ledger")
    controller = live(tmp_path, "root-a")
    with pytest.raises(ctl.ControllerError, match="grant_runs_unavailable"):
        launch(controller, "k1")


def test_concurrent_claims_cannot_both_take_the_last_slot(tmp_path):
    grant = SpendingGrant.from_document(grant_document(permitted_runs=1))
    results, barrier = [], threading.Barrier(8)

    def claimant(number):
        store = f"{number:032x}"
        barrier.wait()
        try:
            grant_runs.claim(grant, store, f"key-{number}")
            results.append("claimed")
        except grant_runs.SharedRunsError as error:
            results.append(error.code)

    threads = [threading.Thread(target=claimant, args=(n,)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results.count("claimed") == 1
    assert results.count(grant_runs.LIMIT) == 7
    assert grant_runs.count("test-grant") == 1


def test_a_root_with_existing_runs_seeds_them_so_they_are_never_under_counted(tmp_path):
    # A root that launched before the ledger existed: its runs are per-root only.
    old = ctl.CampaignController(
        root=tmp_path / "old",
        provider=FakeProvider(),
        grant=SpendingGrant.from_document(
            grant_document(permitted_runs=3, max_concurrency=10)
        ),
        operator="carbon-operator",
        clock=Clock(),
    )
    register(old, ceiling="9.00")
    launch(old, "old1")
    launch(old, "old2")
    old.close()
    assert grant_runs.count("test-grant") == 0
    reopened = ctl.CampaignController(
        root=tmp_path / "old",
        provider=FakeProvider(),
        grant=SpendingGrant.from_document(
            grant_document(permitted_runs=3, max_concurrency=10)
        ),
        operator="carbon-operator",
        clock=Clock(),
        shared_runs=True,
    )
    launch(reopened, "new1")  # seeds old1 and old2, then claims: 3 of 3
    assert grant_runs.count("test-grant") == 3
    reopened.close()
    other = live(tmp_path, "root-b")
    with pytest.raises(ctl.ControllerError, match="run_limit_reached"):
        launch(other, "b1")


def test_the_seed_command_counts_other_roots_that_predate_the_ledger(tmp_path, capsys):
    old = ctl.CampaignController(
        root=tmp_path / "old",
        provider=FakeProvider(),
        grant=SpendingGrant.from_document(
            grant_document(permitted_runs=3, max_concurrency=10)
        ),
        operator="carbon-operator",
        clock=Clock(),
    )
    register(old, ceiling="9.00")
    launch(old, "old1")
    launch(old, "old2")
    old.close()
    document = tmp_path / "grant.json"
    document.write_text(json.dumps(grant_document(permitted_runs=3)))
    assert (
        grant_runs.main(["seed", "--grant", str(document), "--root", str(old.root)])
        == 0
    )
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["claimed"] == 2
    other = live(tmp_path, "root-b")
    launch(other, "b1")
    with pytest.raises(ctl.ControllerError, match="run_limit_reached"):
        launch(other, "b2")


def test_the_ledger_holds_counts_and_ids_only(tmp_path, ledger):
    controller = live(tmp_path, "root-a")
    launch(controller, "k1")
    [path] = list(ledger.glob("*.jsonl"))
    body = path.read_text()
    for forbidden in ("account", "balance", "test-account", "ceiling", "USD", PROFILE):
        assert forbidden not in body
    entry = json.loads(body.splitlines()[0])
    assert set(entry) == {"entry", "store", "seeded"}


def test_a_controller_without_shared_runs_never_touches_the_ledger(tmp_path, ledger):
    plain = ctl.CampaignController(
        root=tmp_path / "plain",
        provider=FakeProvider(),
        grant=SpendingGrant.from_document(grant_document()),
        operator="carbon-operator",
        clock=Clock(),
    )
    register(plain, ceiling="9.00")
    launch(plain, "p1")
    assert not ledger.exists() or not list(ledger.glob("*.jsonl"))


def test_a_live_phase4_run_counts_shared_runs_by_default_and_prelive_does_not():
    import inspect

    from carbon.agent_campaign.graphite import phase4, phase4_prelive

    assert inspect.signature(phase4.run_live).parameters["shared_runs"].default is True
    assert "shared_runs=False" in inspect.getsource(phase4_prelive)
    assert "shared_runs=True" in inspect.getsource(phase4.controller_for) or (
        'kwargs["shared_runs"] = True' in inspect.getsource(phase4.controller_for)
    )
