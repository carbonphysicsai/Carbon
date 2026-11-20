"""The receiver's last stop step ends every docker client child it still has (live 116, 20 Nov 2026 13:13:32Z: a docker
child outlived the main process and systemd waited its 90 s stop timeout), names each one by subcommand and container
prefix only, and never fails the stop."""

from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest

from carbon.development_session import research_carrier as carrier

pytestmark = pytest.mark.skipif(not os.path.isdir("/proc"), reason="/proc")

STUBBORN = (
    "import signal,time\n"
    "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
    "time.sleep(60)\n"
)


def test_a_docker_child_that_ignores_sigterm_is_killed_and_named(monkeypatch):
    lines = []
    from carbon.battery import intake

    monkeypatch.setattr(
        intake, "log", lambda event, **fields: lines.append((event, fields))
    )
    monkeypatch.setattr(carrier, "_STREAM_RELEASE_SECONDS", 0.5)
    child = subprocess.Popen(
        [
            "docker",
            "-c",
            STUBBORN,
            "exec",
            "carbon-d4-0123456789abcdef0123",
            "secret-program",
        ],
        executable=sys.executable,
    )
    try:
        time.sleep(0.3)  # its SIG_IGN is set
        carrier.release_own_docker_clients()
        assert child.wait(timeout=10) == -9
    finally:
        if child.poll() is None:
            child.kill()
    ((event, fields),) = lines
    assert event == "stop_docker_client_ended" and fields["killed"] == 1
    assert fields["clients"] == [
        {"subcommand": "exec", "container": "carbon-d4-0123456789abcd"}
    ]
    assert "secret" not in repr(fields)


def test_with_no_docker_child_nothing_is_logged(monkeypatch):
    lines = []
    from carbon.battery import intake

    monkeypatch.setattr(intake, "log", lambda event, **fields: lines.append(event))
    carrier.release_own_docker_clients()
    assert lines == []


def test_the_sweep_never_raises(monkeypatch):
    def broken(me):
        raise RuntimeError("proc unreadable")

    monkeypatch.setattr(carrier, "_docker_children", broken)
    carrier.release_own_docker_clients()
