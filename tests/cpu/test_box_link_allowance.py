"""S6c (21 Nov 2026): a docker call to a GPU build BOX opens its own ssh connection through the box's wrapper, so every
bound on such a call gets `remote_gpu_build.BOX_LINK_SECONDS` more; a call on this host keeps its bound exactly.
"""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

from carbon.reconstruction import remote_gpu_build
from carbon.reconstruction.worker import docker_runtime


def _box_binding(tmp_path):
    spec = SimpleNamespace(
        local=False, docker_host="ssh://carbon@203.0.113.7", stage_root="/home/carbon"
    )
    lane = SimpleNamespace(spec=spec)
    return SimpleNamespace(lane=lane, docker_host=spec.docker_host)


def test_a_box_call_gets_the_link_allowance_and_a_local_one_does_not(
    tmp_path, monkeypatch
):
    seen = []

    def capture(command, *, environment, timeout, maximum, cwd=None):
        seen.append(timeout)
        return subprocess.CompletedProcess(command, 0, b"{}", b"")

    monkeypatch.setattr(docker_runtime, "_bounded_capture", capture)
    monkeypatch.setattr(remote_gpu_build, "wrapper", lambda lane: tmp_path / "docker")
    box = remote_gpu_build.cli(_box_binding(tmp_path))
    box.run(["exec", "c", "/bin/cat", "/sys/fs/cgroup/pids.max"], timeout=10)
    box.json(["inspect", "c"], timeout=30)
    assert seen == [
        10 + remote_gpu_build.BOX_LINK_SECONDS,
        30 + remote_gpu_build.BOX_LINK_SECONDS,
    ]
    seen.clear()
    docker_runtime.DockerCLI().run(["ps"], timeout=10)
    assert seen == [10]
    local = SimpleNamespace(lane=SimpleNamespace(spec=SimpleNamespace(local=True)))
    assert (
        remote_gpu_build.cli(local) is None
    )  # a local slot lane: this host's own CLI, its bounds as they are
