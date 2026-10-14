"""PLT-30 CI repair: synthetic adoption failures, no Docker/key/registry access."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.development_session import julia_depot_build as build
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure
from scripts.dev import julia_depot as command

MARKER = "private-fixture-marker"


def setup(monkeypatch):
    lock = build.read_lock()
    assert lock is not None
    monkeypatch.setattr(command.build, "read_lock", lambda: lock)
    return lock


def events(capsys):
    return [json.loads(s) for s in capsys.readouterr().out.splitlines() if s.startswith("{")]


def test_required_pull_failure_is_typed_private_and_cannot_continue_cold(tmp_path, monkeypatch, capsys):
    setup(monkeypatch)
    def fail(*args, **kwargs):
        raise WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=MARKER.encode())
    monkeypatch.setattr(command, "DockerCLI", lambda: SimpleNamespace(run=fail))
    monkeypatch.setattr(command.build, "adopt_depot", lambda *a, **k: pytest.fail("failed pull must not adopt"))
    assert command.main(["adopt", "--root", str(tmp_path), "--require-published"]) == 2
    rows = events(capsys)
    failure = [r for r in rows if r.get("status") == "failed"][-1]
    assert failure["stage"] == "pull"
    assert failure["code"] == WorkerCode.RUNTIME.value
    assert type(failure["elapsed_seconds"]) in (int,float)
    assert MARKER not in json.dumps(rows)
    assert not build.depot_manifest(tmp_path).exists()


def test_optional_failure_retains_explicit_operator_cold_build_route(tmp_path, monkeypatch, capsys):
    setup(monkeypatch)
    def fail(*args, **kwargs):
        raise WorkerFailure(WorkerCode.UNAVAILABLE)
    monkeypatch.setattr(command, "DockerCLI", lambda: SimpleNamespace(run=fail))
    assert command.main(["adopt", "--root", str(tmp_path)]) == 0
    rows = events(capsys)
    assert any(r.get("stage") == "pull" and r.get("status") == "failed" for r in rows)


def test_required_missing_or_stale_lock_refuses_without_docker(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(command.build, "read_lock", lambda: None)
    monkeypatch.setattr(command, "DockerCLI", lambda: pytest.fail("missing lock must not access Docker"))
    assert command.main(["adopt", "--root", str(tmp_path), "--require-published"]) == 2
    assert any(r.get("code") == "published_depot_unavailable" for r in events(capsys))


def test_service_requires_adoption_and_keeps_every_registered_suite():
    script = (Path(__file__).resolve().parents[2]/"scripts/dev/julia_worker_service.sh").read_text(encoding="utf-8")
    assert "--require-published" in script
    assert script.index("--require-published") < script.index("-m pytest")
    assert "set -euo pipefail" in script
    assert script.count("-m pytest") == 9
