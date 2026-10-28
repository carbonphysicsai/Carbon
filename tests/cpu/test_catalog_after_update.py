"""The backbone catalog after an update, installed for a newcomer, and the
page's link (M1 E2E R7-1, E2, E1).

An update rebuilt the PyTorch CPU construction parent; every catalog child
was built over the old one, so practice refused `catalog_not_installed`
while setup showed every step done. A newcomer had to know to run a
separate ~40 minute install. These tests hold:
- the catalog's state is read per current parent, from each child's
  receipt, for every entry this install serves;
- setup status lists the catalog as its own not-done item, saying it does
  not block launch, with its background install's progress, and never reads
  all-done in that state;
- the background install runs once (a lock), records how it ended, reports
  progress per Challenge version and estimates the rest only from what it
  measured; it starts from either setup door's confirmed Review and the
  page's one-click retry, never with nothing missing;
- the installer's `catalog-needed` and `session-link` say how many entries
  to install and print the page's link with this install's token.
"""

from __future__ import annotations

import json
import os
import threading

import pytest
from test_miner_launchpad_environment_setup import Checks, Onboarding, completed

from carbon.backbone_catalog import listing, pipeline
from scripts.dev.miner_launchpad import (
    catalog_build,
    catalog_state,
    controller,
    environment_setup,
)
from scripts.dev.miner_launchpad import setup_operations as operations
from scripts.dev.miner_launchpad.environment_setup import EnvironmentSetup

OLD = "sha256:" + "1" * 64
NEW = "sha256:" + "2" * 64
TOKEN = "t" * 43


def torch_entries():
    return [
        item
        for item in pipeline.load()["entries"]
        if item["bundle_ref"]["runtime_profile_id"] == "torch-cpu-py311"
    ]


def stage(root, items, parent):
    """A child receipt over `parent` for each item, as the install leaves."""
    for item in items:
        digest = item["bundle_ref"]["bundle_digest"][7:]
        (root / digest).mkdir(parents=True, exist_ok=True)
        (root / digest / (parent[7:] + ".image.json")).write_text("{}")


@pytest.fixture
def cfg(tmp_path):
    return {"campaigns_root": str(tmp_path / "campaigns")}


def test_the_catalog_is_judged_for_the_current_parent(cfg, monkeypatch):
    root = catalog_state.cache_root(cfg)
    items = torch_entries()
    ids = [item["catalog_id"] for item in items]
    monkeypatch.setattr(catalog_state, "parents", lambda _: {"torch-cpu-py311": OLD})
    # Never installed: every entry this install serves is missing.
    assert catalog_state.state(cfg) == {"entries": len(items), "missing": ids}
    stage(root, items, OLD)
    assert catalog_state.state(cfg) == {"entries": len(items), "missing": []}
    # The update rebuilt the parent: no child exists over the new one.
    monkeypatch.setattr(catalog_state, "parents", lambda _: {"torch-cpu-py311": NEW})
    assert catalog_state.state(cfg)["missing"] == ids
    stage(root, items[:1], NEW)
    assert catalog_state.state(cfg)["missing"] == ids[1:]
    found = catalog_state.progress(cfg)
    assert (found["installed"], found["total"]) == (1, len(items))
    first = items[0]["challenges"][0]
    row = next(
        r
        for r in found["challenges"]
        if (r["id"], r["version"]) == (first["id"], first["version"])
    )
    assert row["ready"] == 1 and row["total"] >= 1
    # A runtime this install does not serve is not counted.
    monkeypatch.setattr(catalog_state, "parents", lambda _: {})
    assert catalog_state.state(cfg) == {"entries": 0, "missing": []}
    assert catalog_state.cache_root({}) is None


@pytest.fixture
def state(tmp_path):
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    return root


def ready(tmp_path, state):
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Checks())
    completed(tmp_path, setup)
    setup.review({"confirm": True})
    return setup


def test_status_lists_a_missing_catalog_and_never_reads_all_done(
    tmp_path, state, monkeypatch
):
    setup = ready(tmp_path, state)
    view = operations.status(setup, door=operations.MCP)
    assert view["next"]["step"] == "launch"
    assert all(row["id"] != "catalog" for row in view["steps"])
    monkeypatch.setattr(
        setup, "catalog", lambda: {"entries": 3, "missing": ["a", "b", "c"]}
    )
    for door in (operations.MCP, operations.HTTP):
        view = operations.status(setup, door=door)
        row = next(r for r in view["steps"] if r["id"] == "catalog")
        assert row["state"] == "next" and row["blocks_launch"] is False
        assert row["missing"] == ["catalog_not_installed_for_this_install"]
        assert row["not_installed"] == ["a", "b", "c"] and row["entries"] == 3
        assert row["install"]["schema"] == catalog_build.SCHEMA
        assert "40 minutes" in row["duration"]
        assert "catalog" not in view["done"]
        assert len(view["done"]) < len(view["steps"])
        nxt = view["next"]
        assert nxt["step"] == "catalog" and nxt["blocks_launch"] is False
        assert nxt["human_action_required"]["command"] == (
            "python -m scripts.dev.catalog_install --state-dir " + str(state)
        )
        assert nxt["then"]["step"] == "launch"
    # While it installs, the step shows its progress and asks nothing.
    monkeypatch.setattr(
        catalog_build,
        "status",
        lambda _: {"state": "RUNNING", "installed": 1, "total": 3},
    )
    row = next(
        r
        for r in operations.status(setup, door=operations.MCP)["steps"]
        if r["id"] == "catalog"
    )
    assert row["install"]["state"] == "RUNNING"
    assert "human_action_required" not in row
    # Installed: gone.
    monkeypatch.setattr(setup, "catalog", lambda: {"entries": 3, "missing": []})
    assert operations.status(setup, door=operations.MCP)["next"]["step"] == "launch"


def test_the_background_install_runs_once_and_reports_progress(
    tmp_path, state, monkeypatch
):
    assert catalog_build.status(state)["state"] == "NO_PROFILE"
    setup = ready(tmp_path, state)
    cfg = json.loads(setup.profile_path.read_bytes())
    root = catalog_state.cache_root(cfg)
    items = torch_entries()[:3]
    monkeypatch.setattr(
        catalog_state,
        "parents",
        lambda _: {"torch-cpu-py311": NEW},
    )
    # Miner paths read the catalog through `listing` (the import-closure cut).
    monkeypatch.setattr(listing, "load", lambda: {"entries": items})
    spawned = []
    started = catalog_build.start(
        state, spawn=lambda argv, **kw: spawned.append((argv, kw))
    )
    assert started["state"] == "RUNNING" and started["total"] == 3
    ((argv, kw),) = spawned
    assert argv[1:4] == ["-B", "-m", "scripts.dev.miner_launchpad.catalog_build"]
    assert argv[4:] == ["run", "--state-dir", str(state)]
    assert kw["start_new_session"] is True
    assert kw["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    # The job itself: one entry installs, the clock says how long it took.
    clock = iter([1000.0, 1100.0, 1300.0])

    def install(state_dir):
        assert catalog_build.running(state_dir)  # it holds the lock
        # A second start while it runs reports it and spawns nothing.
        again = catalog_build.start(state_dir, spawn=lambda *a, **k: 1 / 0)
        assert again["state"] == "RUNNING"
        stage(root, items[:1], NEW)
        found = catalog_build.status(state_dir, clock=lambda: 1100.0)
        # Measured: 100 s for one entry, so 200 s for the two left.
        assert found["estimate_seconds"] == 200
        assert (found["installed"], found["total"]) == (1, 3)
        # What catalog_install --report writes: one entry skipped by name.
        (state / "environment" / catalog_build.REPORT).write_text(
            json.dumps({"installed": 1, "skipped": [skip]})
        )
        return 0

    fetched = []
    skip = {"catalog_id": items[1]["catalog_id"], "reason": "wheel_missing"}
    skip["wheel"] = "torch_harmonics-0.7.4-py3-none-any.whl"
    assert (
        catalog_build.run(
            state,
            install=install,
            fetch=lambda d: fetched.append(d) or True,
            clock=lambda: next(clock),
        )
        == 0
    )
    assert fetched == [state]  # the wheels are fetched first
    ended = catalog_build.status(state)
    assert ended["state"] == "INCOMPLETE" and ended["exit_code"] == 0
    assert ended["skipped"] == [
        {
            "catalog_id": skip["catalog_id"],
            "reason": "wheel_missing",
            "words": skip["catalog_id"]
            + ": its pinned wheel torch_harmonics-0.7.4-py3-none-any.whl could "
            "not be fetched",
        }
    ]
    assert ended["skipped"][0]["words"] in ended["note"]
    assert catalog_build.SKIP_NEXT in ended["note"]
    assert "Traceback" not in ended["note"]
    assert ended["estimate_seconds"] is None
    stage(root, items, NEW)
    assert catalog_build.status(state)["state"] == "COMPLETE"
    # Nothing missing: nothing starts.
    assert catalog_build.start(state, spawn=lambda *a, **k: 1 / 0)["state"] == (
        "COMPLETE"
    )


def test_a_failed_install_reads_stopped(tmp_path, state, monkeypatch):
    setup = ready(tmp_path, state)
    monkeypatch.setattr(catalog_state, "parents", lambda _: {"torch-cpu-py311": NEW})
    assert (
        catalog_build.run(
            state, install=lambda _: 2, fetch=lambda _: True, clock=lambda: 5.0
        )
        == 2
    )
    stopped = catalog_build.status(state)
    assert stopped["state"] == "STOPPED"
    assert "its log says why" in stopped["note"]
    assert setup.catalog()["missing"]


def test_wheels_that_cannot_be_fetched_are_said_and_the_rest_install(
    tmp_path, state, monkeypatch
):
    """Offline, or a file that differs from its pin: one plain line, and the
    install still runs (M1 E2E R10-1)."""
    ready(tmp_path, state)
    monkeypatch.setattr(catalog_state, "parents", lambda _: {"torch-cpu-py311": NEW})
    installed = []
    assert (
        catalog_build.run(
            state,
            install=lambda d: installed.append(d) or 0,
            fetch=lambda _: False,
            clock=lambda: 5.0,
        )
        == 0
    )
    assert installed == [state]
    found = catalog_build.status(state)
    assert found["state"] == "INCOMPLETE"
    assert "pinned wheels could not be fetched this time" in found["note"]


def test_the_wheel_fetch_says_one_plain_line_when_it_fails(monkeypatch, capsys):
    import subprocess

    def refused(argv, **kwargs):
        assert argv[1:] == ["-B", "-m", "scripts.dev.catalog_wheelhouse"]
        return subprocess.CompletedProcess(argv, 1, "", "refused: offline\n")

    monkeypatch.setattr(catalog_build.subprocess, "run", refused)
    assert catalog_build._fetch_wheels("unused") is False
    out = capsys.readouterr().out.strip().splitlines()
    assert out == [
        (
            "Could not fetch the catalog's pinned wheels (refused: offline); the "
            "entries that need them are skipped and the rest install."
        )
    ]


def test_the_page_door_names_each_skipped_entry_by_code(tmp_path, state):
    """The skipped reason codes reach the page through its real door."""
    served = controller.Server(
        controller.Controller(tmp_path / "runs.sqlite3"),
        TOKEN,
        port=0,
        onboarding=Onboarding(),
        state_dir=state,
        setup_checks=Checks(),
    )
    served.setup.attach = lambda path: True
    served.start_catalog = lambda: {"state": "RUNNING"}
    completed(tmp_path, served.setup)
    served.setup.review({"confirm": True})
    catalog_build._save(
        state,
        {
            "started_at": 1.0,
            "ended_at": 2.0,
            "exit_code": 0,
            "wheels": "unavailable",
            "skipped": [
                {"catalog_id": "a", "reason": "wheel_missing", "wheel": "w.whl"},
                {"catalog_id": "b", "reason": "install_failed", "detail": "E: x"},
            ],
        },
    )
    thread = threading.Thread(target=served.serve_forever, daemon=True)
    thread.start()
    try:
        import http.client

        connection = http.client.HTTPConnection(
            "127.0.0.1", served.server_port, timeout=10
        )
        connection.request(
            "GET", "/api/v1/setup", headers={"Authorization": "Bearer " + TOKEN}
        )
        response = connection.getresponse()
        document = json.loads(response.read())
        connection.close()
    finally:
        served.shutdown()
        served.server_close()
        thread.join(timeout=3)
    assert response.status == 200
    skipped = document["catalog_build"]["skipped"]
    assert [item["reason"] for item in skipped] == ["wheel_missing", "install_failed"]
    assert skipped[0]["words"] == "a: its pinned wheel w.whl could not be fetched"
    assert skipped[1]["words"] == "b: its install failed (E: x)"


def test_the_page_starts_it_after_review_and_on_one_click(tmp_path, state, monkeypatch):
    calls = []
    served = controller.Server(
        controller.Controller(tmp_path / "runs.sqlite3"),
        TOKEN,
        port=0,
        onboarding=Onboarding(),
        state_dir=state,
        setup_checks=Checks(),
    )
    monkeypatch.setattr(
        catalog_build,
        "start",
        lambda state_dir: calls.append(state_dir) or {"state": "RUNNING"},
    )
    served.setup.attach = lambda path: True
    thread = threading.Thread(target=served.serve_forever, daemon=True)
    thread.start()
    try:
        import http.client

        def post(path, body):
            connection = http.client.HTTPConnection(
                "127.0.0.1", served.server_port, timeout=10
            )
            connection.request(
                "POST",
                path,
                body=json.dumps(body).encode(),
                headers={
                    "Authorization": "Bearer " + TOKEN,
                    "Content-Type": "application/json",
                },
            )
            response = connection.getresponse()
            result = response.status, json.loads(response.read())
            connection.close()
            return result

        completed(tmp_path, served.setup)
        assert post("/api/v1/setup/review", {"confirm": True})[0] == 200
        assert calls == [state]
        status, body = post(controller.CATALOG_ROUTE, {"start": True})
        assert (status, body) == (200, {"state": "RUNNING"})
        assert calls == [state, state]
        # Only the closed {"start": true} body starts it; anything else is
        # refused by its code before an install is started.
        for wrong in ({"start": True, "x": 1}, {"start": False}, ["start"]):
            status, body = post(controller.CATALOG_ROUTE, wrong)
            assert status == 400
            assert body["error"] == "closed_catalog_request_required"
        assert calls == [state, state]
    finally:
        served.shutdown()
        served.server_close()
        thread.join(timeout=3)


def test_own_agent_mcp_review_starts_only_after_the_profile_is_saved(
    tmp_path, monkeypatch
):
    from test_miner_setup_agent_first import Chain, call, door, made

    from scripts.dev.miner_launchpad.environment_setup import OWN_AGENT

    state_dir = made(tmp_path)
    server, setup, _ = door(state_dir, Checks(), Chain())
    calls, locks = [], []
    original_start = catalog_build.start

    def spawn(argv, **_kwargs):
        profile = json.loads(setup.profile_path.read_bytes())
        assert profile["practice_identity"]["kind"] == "PRACTICE_ONLY"
        calls.append(argv)
        # The actual background child holds this existing lock. No installer,
        # Docker build or network call is run by this synthetic fixture.
        locks.append(catalog_build._lock(setup.root))
        assert locks[-1] is not None

    monkeypatch.setattr(
        catalog_build,
        "start",
        lambda root: original_start(root, spawn=spawn),
    )
    call(server, "carbon_setup_practice", {"confirm": True})
    call(server, "carbon_setup_agent", {"choice": OWN_AGENT})
    options = operations.status(setup, door=operations.MCP)["next"]["options"]
    call(
        server,
        "carbon_setup_compute",
        {
            "choice": options["choice"][0],
            "image_manifest": options["image_manifest"],
            "analysis_image_manifest": options["analysis_image_manifest"],
        },
    )
    assert calls == [] and not setup.profile_path.exists()
    items = torch_entries()[:1]
    monkeypatch.setattr(catalog_state, "parents", lambda _: {"torch-cpu-py311": NEW})
    monkeypatch.setattr(listing, "load", lambda: {"entries": items})
    try:
        reviewed = call(server, "carbon_setup_review", {"confirm": True})["payload"]
        assert reviewed["steps"]["review"]["profile_written"] is True
        assert len(calls) == 1
        assert calls[0][-2:] == ["--state-dir", str(state_dir)]
        call(server, "carbon_setup_status", {})
        call(server, "carbon_setup_review", {"confirm": True})
        assert len(calls) == 1  # the maintained starter reports the running job
        assert catalog_build.status(state_dir)["state"] == "RUNNING"
    finally:
        for fd in locks:
            os.close(fd)


@pytest.mark.parametrize("door", [operations.MCP, operations.HTTP])
def test_a_refused_review_or_read_only_status_never_starts_the_catalog(
    tmp_path, state, monkeypatch, door
):
    from scripts.dev.miner_launchpad.environment_setup import SetupRefused

    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Checks())
    starts = []
    monkeypatch.setattr(catalog_build, "start", lambda root: starts.append(root))
    operations.status(setup, door=door)
    assert catalog_build.status(state)["state"] == "NO_PROFILE"
    with pytest.raises(SetupRefused):
        operations.perform(setup, "review", {"confirm": True}, door=door)
    completed(tmp_path, setup)
    with pytest.raises(SetupRefused) as refused:
        operations.perform(setup, "review", {"confirm": False}, door=door)
    assert refused.value.code == "review_needs_confirmation"
    operations.status(setup, door=door)
    assert starts == [] and not setup.profile_path.exists()


@pytest.mark.parametrize("door", [operations.MCP, operations.HTTP])
def test_a_start_failure_preserves_review_and_offers_an_honest_retry(
    tmp_path, state, monkeypatch, door
):
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Checks())
    completed(tmp_path, setup)
    monkeypatch.setattr(catalog_state, "parents", lambda _: {"torch-cpu-py311": NEW})

    def failed(_state):
        raise OSError("synthetic background spawn failure")

    monkeypatch.setattr(catalog_build, "start", failed)
    reviewed = operations.perform(setup, "review", {"confirm": True}, door=door)
    assert reviewed["steps"]["review"]["profile_written"] is True
    assert json.loads(setup.profile_path.read_bytes())["campaigns_root"]
    job = catalog_build.status(state)
    assert job["state"] == "INCOMPLETE" and job["started_at"] is None
    retry = operations.status(setup, door=door)["next"]
    assert retry["step"] == "catalog" and retry["install"] == job
    assert "could not start" in retry["human_action_required"]["why"]
    assert "never start" not in retry["human_action_required"]["why"]


def test_catalog_needed_counts_what_to_install(tmp_path, state, monkeypatch, capsys):
    assert environment_setup.main(["catalog-needed", "--state-dir", str(state)]) == 0
    assert capsys.readouterr().out == "no\n"  # no profile
    ready(tmp_path, state)
    monkeypatch.setattr(catalog_state, "parents", lambda _: {"torch-cpu-py311": NEW})
    assert environment_setup.main(["catalog-needed", "--state-dir", str(state)]) == 0
    assert capsys.readouterr().out == str(len(torch_entries())) + "\n"


def test_session_link_prints_the_page_link_with_this_installs_token(state, capsys):
    """M1 E2E E1: the installer's last line opens the page with no paste.
    The token is the one the Control Center keeps and reuses."""
    argv = ["session-link", "--state-dir", str(state), "--port", "8788"]
    assert environment_setup.main(argv) == 0
    link = capsys.readouterr().out.strip()
    token = controller.session_token(state)
    assert link == "http://127.0.0.1:8788/#token=" + token
    assert environment_setup.main(argv) == 0
    assert capsys.readouterr().out.strip() == link  # the same, every time
