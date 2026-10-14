"""Actual lock/pointer controls; synthetic state never changes with code selection."""

import json
from types import SimpleNamespace

import pytest
from test_validator_setup_bundle import command, source

from carbon.validator_setup import bundle as b


def arrangement(tmp_path, monkeypatch):
    from scripts.dev.battery_validator_service import service

    repo, first = source(tmp_path)
    a = b.materialize(repo, first, tmp_path / "release-a")
    (repo / "uv.lock").write_text("new-public-fixture-lock", encoding="utf-8")
    command(repo, "add", ".")
    command(repo, "commit", "-qm", "fixture update")
    second = command(repo, "rev-parse", "HEAD")
    c = b.materialize(repo, second, tmp_path / "release-b")
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    marker = state / "history"
    marker.write_bytes(b"immutable-fixture-history")
    cfg = SimpleNamespace(state_dir=state)
    monkeypatch.setattr(service, "load_service", lambda _path: cfg)
    monkeypatch.setattr(
        service, "_intake", lambda *_args: {"inbox": str(state / "inbox.sqlite3")}
    )
    pointer = state / "selected.json"
    return a, c, state, marker, pointer


def test_inactive_install_update_rollback_changes_only_code_pointer(
    tmp_path, monkeypatch
):
    a, c, state, marker, pointer = arrangement(tmp_path, monkeypatch)
    installed = b.select_release(
        a, pointer, state / "service.json", expected_current=None
    )
    assert installed["source_revision"] == a.manifest["source_revision"]
    updated = b.select_release(
        c, pointer, state / "service.json", expected_current=installed
    )
    assert updated["source_revision"] != installed["source_revision"]
    rolled_back = b.select_release(
        a, pointer, state / "service.json", expected_current=updated
    )
    assert rolled_back == installed == json.loads(pointer.read_bytes())
    assert marker.read_bytes() == b"immutable-fixture-history"


@pytest.mark.parametrize(
    "lock",
    [
        "operator-runtime.lock",
        "supervisor.lock",
        "daemon-heartbeat.json.lock",
        "inbox.sqlite3.serve.lock",
    ],
)
def test_active_managed_or_existing_child_refuses_switch_without_pointer_or_history_change(
    tmp_path, monkeypatch, lock
):
    a, c, state, marker, pointer = arrangement(tmp_path, monkeypatch)
    installed = b.select_release(
        a, pointer, state / "service.json", expected_current=None
    )
    before = pointer.read_bytes()
    with (
        b.held_lock(state / lock, exclusive=False),
        pytest.raises(
            b.SetupRefused, match="OPERATOR_RUNTIME_OR_RELEASE_SWITCH_ACTIVE"
        ),
    ):
        b.select_release(c, pointer, state / "service.json", expected_current=installed)
    assert pointer.read_bytes() == before
    assert marker.read_bytes() == b"immutable-fixture-history"


def test_stale_expected_pointer_refuses_and_preserves_current_release(
    tmp_path, monkeypatch
):
    a, c, state, marker, pointer = arrangement(tmp_path, monkeypatch)
    b.select_release(a, pointer, state / "service.json", expected_current=None)
    before = pointer.read_bytes()
    with pytest.raises(b.SetupRefused, match="RELEASE_POINTER_CHANGED"):
        b.select_release(c, pointer, state / "service.json", expected_current=None)
    assert (
        pointer.read_bytes() == before
        and marker.read_bytes() == b"immutable-fixture-history"
    )
