"""Every Docker CLI call runs in a directory the controller does not depend on.

Docker CLI 29.6.1 stats `./-` for `docker cp CONTAINER:/x -`, so a controller whose own working directory was
unreadable (a service started from a private directory) failed the pinned-uv copy at STAGING with `stat -:
permission denied`, and every GPU practice fell back to CPU on a fresh 4090 VM. The CLI wrapper now pins the
working directory to the filesystem root for every call it makes."""

from __future__ import annotations

import os
import stat

import pytest

from carbon.reconstruction.worker import docker_runtime

posix = pytest.mark.skipif(os.name != "posix", reason="a POSIX working directory")


def _fake_docker(tmp_path):
    script = tmp_path / "fake-docker"
    script.write_text("#!/bin/sh\npwd\n")
    script.chmod(stat.S_IRWXU)
    return str(script)


@posix
def test_run_and_stream_to_file_do_not_inherit_an_unreadable_working_directory(
    tmp_path,
):
    unreadable = tmp_path / "private"
    unreadable.mkdir()
    cli = docker_runtime.DockerCLI()
    cli.executable = _fake_docker(tmp_path)  # the constructor takes only 'docker'
    here = os.getcwd()
    os.chdir(unreadable)
    unreadable.chmod(0)
    try:
        assert cli.run(["anything"]).stdout.strip() == os.sep.encode()
        out = tmp_path / "out.txt"
        cli.stream_to_file(["anything"], out, maximum=1024, timeout=10)
        assert out.read_bytes().strip() == os.sep.encode()
    finally:
        unreadable.chmod(0o700)
        os.chdir(here)


def test_the_directory_is_the_root():
    assert docker_runtime.DOCKER_CWD.as_posix() == "/"
