"""A real host child compile must not poison the next exact-source admission.

The CLI module is a tiny non-model fixture. Git and the Python child are real;
no authority check is mocked and no numerical/scientific claim is made.
"""

import hashlib
import os
import subprocess
import time

import pytest
from test_development_candidate_implementation import _candidate, _checked, _git

from carbon.development_session import construction_level
from carbon.reconstruction.worker import docker_runtime, liveness_reaper


def test_first_compile_preserves_second_case_clean_candidate(tmp_path, monkeypatch):
    repo, revision, tree, source_digest = _candidate(tmp_path)
    module = repo / "fixture_level_cli.py"
    module.write_text("import json\nprint(json.dumps({'fixture': True}))\n")
    _git(repo, "add", module.name)
    _git(repo, "commit", "-qm", "fixture child module")
    # Freeze the actual new source, never amend an old accepted identity.
    revision = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    source_digest = (
        "sha256:"
        + hashlib.sha256(
            _git(repo, "archive", "--format=tar", "HEAD", text=False)
        ).hexdigest()
    )
    monkeypatch.setattr(
        construction_level,
        "__file__",
        repo / "carbon/development_session/construction_level.py",
    )
    monkeypatch.setattr(construction_level, "CLI_MODULE", "fixture_level_cli")
    # Isolate the bytecode behavior from the maintained result-schema tests.
    monkeypatch.setattr(construction_level, "checked", lambda value, **kwargs: value)
    monkeypatch.delenv("PYTHONDONTWRITEBYTECODE", raising=False)
    assert _checked(repo, revision, tree, source_digest)["revision"] == revision
    assert construction_level._run({}) == {"fixture": True}
    assert not _git(repo, "status", "--porcelain", "--untracked-files=all")
    # Parent -B is not inherited: without an explicit child flag Python creates
    # ignored bytecode and the next case's stricter candidate check fails.
    assert _checked(repo, revision, tree, source_digest)["revision"] == revision
    assert not list(repo.rglob("*.pyc"))


def test_ignored_runtime_source_still_refuses_after_compile_fix(tmp_path):
    repo, revision, tree, source_digest = _candidate(tmp_path)
    ignored = repo / "carbon" / "forged.pyc"
    ignored.write_bytes(b"fixture runtime source")
    assert not _git(repo, "status", "--porcelain", "--untracked-files=all")
    with pytest.raises(ValueError, match="ignored runtime source"):
        _checked(repo, revision, tree, source_digest)


@pytest.mark.parametrize("kind", ["deadline", "liveness"])
def test_real_reaper_child_preserves_second_case_clean_candidate(
    tmp_path, monkeypatch, kind
):
    repo, _, _, _ = _candidate(tmp_path)
    package = repo / "carbon" / "reconstruction" / "worker"
    package.mkdir(parents=True)
    for path in (package.parent, package):
        (path / "__init__.py").write_text("# fixture package\n")
    module = "watchdog" if kind == "deadline" else "liveness_reaper"
    (package / (module + ".py")).write_text(
        "# import-only fixture; no Docker or model\n"
    )
    _git(repo, "add", "carbon")
    _git(repo, "commit", "-qm", "fixture reaper module")
    revision = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    source_digest = (
        "sha256:"
        + hashlib.sha256(
            _git(repo, "archive", "--format=tar", "HEAD", text=False)
        ).hexdigest()
    )
    assert _checked(repo, revision, tree, source_digest)["revision"] == revision
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    monkeypatch.setenv("DOCKER_CONTEXT", "fixture-context")
    monkeypatch.setattr(
        liveness_reaper, "process_identity", lambda pid: "fixture-owner"
    )
    real_popen = subprocess.Popen
    children = []

    def capture(arguments, **kwargs):
        # The existing hostile-environment scrub remains intact. The child
        # interpreter must carry its own -B because the environment drops it.
        assert set(kwargs["env"]) <= {
            "PATH",
            "DOCKER_HOST",
            "DOCKER_CONTEXT",
            "DOCKER_TLS_VERIFY",
            "DOCKER_CERT_PATH",
        }
        assert kwargs["env"]["DOCKER_CONTEXT"] == "fixture-context"
        assert kwargs["start_new_session"] and kwargs["close_fds"]
        assert (
            kwargs["stdin"]
            == kwargs["stdout"]
            == kwargs["stderr"]
            == subprocess.DEVNULL
        )
        process = real_popen(arguments, **kwargs)
        children.append(process)
        return process

    try:
        with monkeypatch.context() as launch:
            launch.setattr(subprocess, "Popen", capture)
            if kind == "deadline":
                docker_runtime.spawn_watchdog(
                    container_name="fixture-container",
                    launch_digest="sha256:" + "a" * 64,
                    deadline_unix=time.time() + 60.0,
                )
            else:
                liveness_reaper.spawn_liveness_reaper(
                    container_name="fixture-container",
                    launch_digest="sha256:" + "a" * 64,
                    guard={
                        "kind": "CONTROLLER_LIVENESS",
                        "pid": os.getpid(),
                        "identity": "fixture-owner",
                    },
                )
        assert len(children) == 1
        assert children[0].wait(timeout=10) == 0
    finally:
        for process in children:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
    assert not _git(repo, "status", "--porcelain", "--untracked-files=all")
    assert _checked(repo, revision, tree, source_digest)["revision"] == revision
    assert not list(repo.rglob("*.pyc"))
