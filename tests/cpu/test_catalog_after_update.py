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
  measured; it starts from the page's Review and one click, never with
  nothing missing;
- the installer's `catalog-needed` and `session-link` say how many entries
  to install and print the page's link with this install's token.
"""

from __future__ import annotations

import json
import threading

import pytest
from test_miner_launchpad_environment_setup import Checks, Onboarding, completed

from carbon.backbone_catalog import pipeline
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
    monkeypatch.setattr(pipeline, "load", lambda: {"entries": items})
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
        return 0

    assert catalog_build.run(state, install=install, clock=lambda: next(clock)) == 0
    ended = catalog_build.status(state)
    assert ended["state"] == "INCOMPLETE" and ended["exit_code"] == 0
    assert "skipped" in ended["note"]
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
    assert catalog_build.run(state, install=lambda _: 2, clock=lambda: 5.0) == 2
    assert catalog_build.status(state)["state"] == "STOPPED"
    assert setup.catalog()["missing"]


def test_the_page_starts_it_after_review_and_on_one_click(tmp_path, state):
    calls = []
    served = controller.Server(
        controller.Controller(tmp_path / "runs.sqlite3"),
        TOKEN,
        port=0,
        onboarding=Onboarding(),
        state_dir=state,
        setup_checks=Checks(),
    )
    served.start_catalog = lambda: calls.append("start") or {"state": "RUNNING"}
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
        assert calls == ["start"]
        status, body = post(controller.CATALOG_ROUTE, {"start": True})
        assert (status, body) == (200, {"state": "RUNNING"})
        assert calls == ["start", "start"]
        assert post(controller.CATALOG_ROUTE, {"start": True, "x": 1})[0] == 400
    finally:
        served.shutdown()
        served.server_close()
        thread.join(timeout=3)


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
