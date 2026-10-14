"""PLT-30 CI repair: synthetic adoption failures, no Docker/key/registry access."""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_julia_depot_identity import FakeDocker

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
    return [
        json.loads(s) for s in capsys.readouterr().out.splitlines() if s.startswith("{")
    ]


def test_required_pull_failure_is_typed_private_and_cannot_continue_cold(
    tmp_path, monkeypatch, capsys
):
    setup(monkeypatch)

    def fail(*args, **kwargs):
        raise WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=MARKER.encode())

    monkeypatch.setattr(command, "DockerCLI", lambda: SimpleNamespace(run=fail))
    monkeypatch.setattr(
        command.build,
        "adopt_depot",
        lambda *a, **k: pytest.fail("failed pull must not adopt"),
    )
    assert command.main(["adopt", "--root", str(tmp_path), "--require-published"]) == 2
    rows = events(capsys)
    failure = [r for r in rows if r.get("status") == "failed"][-1]
    assert failure["stage"] == "pull"
    assert failure["code"] == WorkerCode.RUNTIME.value
    assert type(failure["elapsed_seconds"]) in (int, float)
    assert MARKER not in json.dumps(rows)
    assert not build.depot_manifest(tmp_path).exists()


def test_optional_failure_retains_explicit_operator_cold_build_route(
    tmp_path, monkeypatch, capsys
):
    setup(monkeypatch)

    def fail(*args, **kwargs):
        raise WorkerFailure(WorkerCode.UNAVAILABLE)

    monkeypatch.setattr(command, "DockerCLI", lambda: SimpleNamespace(run=fail))
    assert command.main(["adopt", "--root", str(tmp_path)]) == 0
    rows = events(capsys)
    assert any(r.get("stage") == "pull" and r.get("status") == "failed" for r in rows)


def test_required_missing_or_stale_lock_refuses_without_docker(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(command.build, "read_lock", lambda: None)
    monkeypatch.setattr(
        command, "DockerCLI", lambda: pytest.fail("missing lock must not access Docker")
    )
    assert command.main(["adopt", "--root", str(tmp_path), "--require-published"]) == 2
    assert any(r.get("code") == "published_depot_unavailable" for r in events(capsys))


def test_service_requires_adoption_and_keeps_every_registered_suite():
    script = (
        Path(__file__).resolve().parents[2] / "scripts/dev/julia_worker_service.sh"
    ).read_text(encoding="utf-8")
    assert "--require-published" in script
    assert script.index("--require-published") < script.index("-m pytest")
    assert "set -euo pipefail" in script
    assert script.count("-m pytest") == 9


def installed(tmp_path, monkeypatch):
    lock = setup(monkeypatch)
    cli = FakeDocker()
    monkeypatch.setattr(build, "tree_digest", lambda *args: "sha256:tree")
    depot, _ = build.build_depot(tmp_path, cli)
    cli.images.setdefault("ids", {})[lock["image"]] = depot.image_id
    cli.images[lock["image"]] = cli.images[depot.image_id]
    calls = []
    run = cli.run

    def observed(arguments, **kwargs):
        calls.append((arguments, kwargs))
        return run(arguments, **kwargs)

    cli.run = observed
    monkeypatch.setattr(command, "DockerCLI", lambda: cli)
    return cli, depot, lock, calls


def test_exact_published_depot_verifies_before_recording_and_never_builds_cold(
    tmp_path, monkeypatch, capsys
):
    cli, depot, lock, calls = installed(tmp_path, monkeypatch)
    built_count = len(cli.builds)
    assert command.main(["adopt", "--root", str(tmp_path), "--require-published"]) == 0
    rows = events(capsys)
    assert [(r["stage"], r["status"]) for r in rows if "stage" in r] == [
        (s, "success")
        for s in ("lock", "pull", "image_inspect", "tree_digest", "binding", "record")
    ]
    assert calls[0] == (
        ["pull", "--quiet", "--platform=linux/amd64", lock["image"]],
        {"timeout": 3600},
    )
    assert len(cli.builds) == built_count
    assert build.load_depot(build.depot_manifest(tmp_path)) == depot
    assert any(
        r.get("how") == "adopted"
        for r in map(
            json.loads,
            (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines(),
        )
    )


@pytest.mark.parametrize("stage", ["image_inspect", "tree_digest", "binding"])
def test_failed_adoption_cannot_replace_a_cached_record(
    tmp_path, monkeypatch, capsys, stage
):
    cli, depot, _lock, _calls = installed(tmp_path, monkeypatch)
    before = build.depot_manifest(tmp_path).read_bytes()
    if stage == "image_inspect":

        def fail(*args, **kwargs):
            raise WorkerFailure(
                WorkerCode.UNAVAILABLE, private_diagnostic=MARKER.encode()
            )

        monkeypatch.setattr(cli, "json", fail)
        expected = WorkerCode.UNAVAILABLE.value
    elif stage == "tree_digest":

        def fail(*args, **kwargs):
            raise build.TreeReadFailure("tree_read_deadline")

        monkeypatch.setattr(build, "tree_digest", fail)
        expected = "tree_read_deadline"
    else:
        cli.images[depot.image_id] = {build.DEPOT_LABEL: "sha256:" + "0" * 64}
        expected = "identity_refused"
    assert command.main(["adopt", "--root", str(tmp_path), "--require-published"]) == 2
    rows = events(capsys)
    failure = [r for r in rows if r.get("status") == "failed"][-1]
    assert (failure["stage"], failure["code"]) == (stage, expected)
    assert build.depot_manifest(tmp_path).read_bytes() == before
    assert not any(r.get("stage") == "record" for r in rows)
    assert MARKER not in json.dumps(rows)


def test_a_noisy_pull_hits_the_real_capture_cap_but_quiet_output_fits(monkeypatch):
    from carbon.reconstruction.worker import docker_runtime as runtime
    from carbon.reconstruction.worker.model import DIAGNOSTIC_BYTES

    with pytest.raises(WorkerFailure) as failure:
        runtime._bounded_capture(
            [
                sys.executable,
                "-c",
                f"import sys;sys.stdout.buffer.write(b'A'*{DIAGNOSTIC_BYTES+1})",
            ],
            environment={},
            timeout=5,
            maximum=DIAGNOSTIC_BYTES,
        )
    assert failure.value.code is WorkerCode.RUNTIME
    assert failure.value.private_diagnostic.startswith(
        b"controller response exceeded cap"
    )
    result = runtime._bounded_capture(
        [sys.executable, "-c", "print('sha256:'+'a'*64)"],
        environment={},
        timeout=5,
        maximum=DIAGNOSTIC_BYTES,
    )
    assert result.returncode == 0
    # This reproduces one possible WorkerFailure route, not the original CI
    # root cause, whose lost diagnostic cannot be reconstructed from its type.


def test_tree_digest_preserves_the_complete_content_mode_and_link_hash(
    tmp_path, monkeypatch
):
    body = b"public fixture"
    archive = tmp_path / "tree.tar"
    with tarfile.open(archive, "w") as tar:
        member = tarfile.TarInfo("tree/a")
        member.mode = 0o444
        member.size = len(body)
        tar.addfile(member, io.BytesIO(body))
        link = tarfile.TarInfo("tree/link")
        link.type = tarfile.SYMTYPE
        link.linkname = "a"
        link.mode = 0o777
        tar.addfile(link)
    original = subprocess.Popen
    monkeypatch.setattr(
        build.subprocess,
        "Popen",
        lambda args, **kwargs: original(
            [
                sys.executable,
                "-c",
                "import pathlib,sys;sys.stdout.buffer.write(pathlib.Path(sys.argv[1]).read_bytes())",
                str(archive),
            ],
            **kwargs,
        ),
    )
    calls = []
    cli = SimpleNamespace(
        run=lambda args, **kwargs: calls.append(args)
        or SimpleNamespace(stdout=b"fixture-container")
    )
    found = build.tree_digest(cli, "fixture-image", "/public-tree")
    expected = [
        ["a", "0", 0o444, "", hashlib.sha256(body).hexdigest()],
        ["link", "2", 0o777, "a", ""],
    ]
    assert found == build.digest(json.dumps(expected, separators=(",", ":")).encode())
    assert calls[-1] == ["rm", "--force", "fixture-container"]


def test_hung_tree_stream_is_deadline_bounded_and_created_container_removed(
    monkeypatch,
):
    original = subprocess.Popen
    children = []

    def hang(args, **kwargs):
        p = original([sys.executable, "-c", "import time;time.sleep(30)"], **kwargs)
        children.append(p)
        return p

    monkeypatch.setattr(build.subprocess, "Popen", hang)
    monkeypatch.setattr(build, "TREE_READ_SECONDS", 0.2)
    calls = []
    cli = SimpleNamespace(
        run=lambda args, **kwargs: calls.append(args)
        or SimpleNamespace(stdout=b"fixture-container")
    )
    started = time.monotonic()
    with pytest.raises(build.TreeReadFailure) as failure:
        build.tree_digest(cli, "fixture-image", "/public-tree")
    assert failure.value.code == "tree_read_deadline"
    assert time.monotonic() - started < 5
    assert len(children) == 1 and children[0].poll() is not None
    assert calls[-1] == ["rm", "--force", "fixture-container"]


@pytest.mark.skipif(
    os.name != "posix", reason="actual CI shell and executable fixtures"
)
def test_failed_required_service_adoption_stops_before_tests_and_logs_out(tmp_path):
    repo = tmp_path / "repo"
    scripts = repo / "scripts/dev"
    scripts.mkdir(parents=True)
    source = Path(__file__).resolve().parents[2] / "scripts/dev/julia_worker_service.sh"
    script = scripts / source.name
    script.write_bytes(source.read_bytes())
    worker = repo / ".carbon-artifacts/julia-worker-image.json"
    worker.parent.mkdir()
    worker.write_text("public fixture", encoding="utf-8")
    binary = repo / ".venv/bin"
    binary.mkdir(parents=True)
    log = tmp_path / "calls.log"
    python = binary / "python"
    python.write_text(
        '#!/bin/sh\nprintf "python %s\\n" "$*" >> "$TEST_LOG"\nexit 2\n',
        encoding="utf-8",
    )
    docker = binary / "docker"
    docker.write_text(
        '#!/bin/sh\nprintf "docker %s\\n" "$*" >> "$TEST_LOG"\nexit 0\n',
        encoding="utf-8",
    )
    python.chmod(0o700)
    docker.chmod(0o700)
    done = subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
        env={
            "PATH": str(binary) + os.pathsep + os.defpath,
            "TEST_LOG": str(log),
            "GHCR_READ_TOKEN": "public-fixture",
            "GITHUB_ACTOR": "fixture",
        },
    )
    assert done.returncode == 2
    calls = log.read_text(encoding="utf-8")
    assert "--require-published" in calls and "-m pytest" not in calls
    assert calls.splitlines()[-1] == "docker logout ghcr.io"
    assert "public-fixture" not in calls


@pytest.mark.parametrize("required", [False, True])
def test_malformed_lock_always_refuses_and_never_prints_raw_failure(
    tmp_path, monkeypatch, capsys, required
):
    def broken():
        raise ValueError(MARKER)

    monkeypatch.setattr(command.build, "read_lock", broken)
    monkeypatch.setattr(
        command,
        "DockerCLI",
        lambda: pytest.fail("malformed lock must not access Docker"),
    )
    args = ["adopt", "--root", str(tmp_path)] + (
        ["--require-published"] if required else []
    )
    assert command.main(args) == 2
    rows = events(capsys)
    assert rows[-1]["stage"] == "lock" and rows[-1]["code"] == "identity_refused"
    assert MARKER not in json.dumps(rows)


def test_stage_duration_is_measured_and_unknown_error_text_stays_private(
    tmp_path, monkeypatch, capsys
):
    ticks = iter([100.0, 146.5])
    monkeypatch.setattr(command, "time", SimpleNamespace(monotonic=lambda: next(ticks)))

    def broken():
        raise RuntimeError(MARKER)

    with pytest.raises(command.AdoptionFailed):
        command._phase(tmp_path, "pull", broken)
    [row] = events(capsys)
    assert (row["stage"], row["elapsed_seconds"], row["code"]) == (
        "pull",
        46.5,
        "unexpected_failure",
    )
    assert MARKER not in json.dumps(row)
