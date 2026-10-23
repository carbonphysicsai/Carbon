"""The backbone catalog after an update (M1 E2E R7-1).

An update rebuilt the PyTorch CPU construction parent; every catalog child
was built over the old one, so practice refused `catalog_not_installed`
while setup showed every step done. These tests hold:
- the catalog's state is read per current parent, from each child's
  receipt, not from the staged material alone;
- setup status lists the catalog as its own not-done item, saying it does
  not block launch, and never reads all-done in that state;
- the installer's `catalog-needed` says how many entries to install again.
"""

from __future__ import annotations

import json

import pytest
from test_miner_launchpad_environment_setup import Checks, Onboarding, completed

from carbon.backbone_catalog import pipeline
from scripts.dev.miner_launchpad import catalog_state, environment_setup
from scripts.dev.miner_launchpad import setup_operations as operations
from scripts.dev.miner_launchpad.environment_setup import EnvironmentSetup

OLD = "sha256:" + "1" * 64
NEW = "sha256:" + "2" * 64


def torch_entries(n):
    found = [
        item
        for item in pipeline.load()["entries"]
        if item["bundle_ref"]["runtime_profile_id"] == "torch-cpu-py311"
    ]
    return found[:n]


def stage(root, items, parent=None):
    """Material staged for each item, with a child receipt over `parent`."""
    for item in items:
        digest = item["bundle_ref"]["bundle_digest"][7:]
        (root / "materials" / digest).mkdir(parents=True, exist_ok=True)
        if parent is not None:
            (root / digest).mkdir(exist_ok=True)
            (root / digest / (parent[7:] + ".image.json")).write_text("{}")


@pytest.fixture
def cfg(tmp_path):
    return {"campaigns_root": str(tmp_path / "campaigns")}


def test_the_catalog_is_judged_for_the_current_parent(cfg, monkeypatch):
    root = catalog_state.cache_root(cfg)
    assert catalog_state.state(cfg) is None  # never installed here
    items = torch_entries(2)
    stage(root, items, OLD)
    monkeypatch.setattr(catalog_state, "parents", lambda _: {"torch-cpu-py311": OLD})
    assert catalog_state.state(cfg) == {"had": 2, "missing": []}
    # The update rebuilt the parent: the material is still staged, but no
    # child exists over the new one.
    monkeypatch.setattr(catalog_state, "parents", lambda _: {"torch-cpu-py311": NEW})
    assert catalog_state.state(cfg) == {
        "had": 2,
        "missing": [item["catalog_id"] for item in items],
    }
    stage(root, items[:1], NEW)
    assert catalog_state.state(cfg)["missing"] == [items[1]["catalog_id"]]
    # A runtime this install does not serve is not counted.
    monkeypatch.setattr(catalog_state, "parents", lambda _: {})
    assert catalog_state.state(cfg) == {"had": 0, "missing": []}


def ready(tmp_path, state):
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Checks())
    completed(tmp_path, setup)
    setup.review({"confirm": True})
    return setup


@pytest.fixture
def state(tmp_path):
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    return root


def test_status_lists_a_missing_catalog_and_never_reads_all_done(
    tmp_path, state, monkeypatch
):
    setup = ready(tmp_path, state)
    view = operations.status(setup, door=operations.MCP)
    assert view["next"]["step"] == "launch"
    assert all(row["id"] != "catalog" for row in view["steps"])
    monkeypatch.setattr(
        setup, "catalog", lambda: {"had": 3, "missing": ["a", "b", "c"]}
    )
    for door in (operations.MCP, operations.HTTP):
        view = operations.status(setup, door=door)
        row = next(r for r in view["steps"] if r["id"] == "catalog")
        assert row["state"] == "next" and row["blocks_launch"] is False
        assert row["missing"] == ["catalog_not_installed_for_this_install"]
        assert row["not_installed"] == ["a", "b", "c"] and row["entries"] == 3
        assert "catalog" not in view["done"]
        assert len(view["done"]) < len(view["steps"])
        nxt = view["next"]
        assert nxt["step"] == "catalog" and nxt["blocks_launch"] is False
        assert nxt["human_action_required"]["command"] == (
            "python -m scripts.dev.catalog_install --state-dir " + str(state)
        )
        assert nxt["then"]["step"] == "launch"
    # Installed again: gone.
    monkeypatch.setattr(setup, "catalog", lambda: {"had": 3, "missing": []})
    assert operations.status(setup, door=operations.MCP)["next"]["step"] == "launch"


def test_catalog_needed_counts_what_to_install_again(
    tmp_path, state, monkeypatch, capsys
):
    assert environment_setup.main(["catalog-needed", "--state-dir", str(state)]) == 0
    assert capsys.readouterr().out == "no\n"  # no profile, no catalog
    setup = ready(tmp_path, state)
    cfg = json.loads(setup.profile_path.read_bytes())
    stage(catalog_state.cache_root(cfg), torch_entries(2))
    monkeypatch.setattr(catalog_state, "parents", lambda _: {"torch-cpu-py311": NEW})
    assert environment_setup.main(["catalog-needed", "--state-dir", str(state)]) == 0
    assert capsys.readouterr().out == "2\n"
