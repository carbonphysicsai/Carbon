"""A remote GPU build's program can outlive the door (owner, 20 Nov 2026: a door restart must never cancel an in-flight
build; live 116 01:52Z: ~22 builds cancelled and re-run from zero). Head A of the re-attach design
(codex-queue/reports/DOOR_CODE/BUILD_REATTACH_DESIGN_20261120.md): the program runs under `DETACHABLE_FRONT`, which relays
exactly what the bare bootstrap showed (stdout, stderr, exit status) and also keeps them in its run directory, and keeps
running when the door's end of the stream goes away. Real processes (this interpreter as the worker's python), no
container: the front end's own code is what runs in the container.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from carbon.development_session import research_carrier
from carbon.development_session.research_carrier import (
    BOOTSTRAP,
    DETACHABLE_FRONT,
    DETACHABLE_RUN_DIR,
    _detachable,
    _program_command,
)
from carbon.reconstruction.worker.model import DIAGNOSTIC_BYTES

pytestmark = pytest.mark.skipif(os.name != "posix", reason="fork and pipes")

CAP = 1024**2 + 1


def _boot(program):
    """A bootstrap like the worker's: it ``execv``s into the program."""
    return (
        "import os,sys\n"
        f"os.execv(sys.executable,[sys.executable,'-I','-c',{program!r}])\n"
    )


def _bare(boot):
    return subprocess.run(
        [sys.executable, "-I", "-c", boot],
        capture_output=True,
        timeout=60,
        check=False,
    )


def _front(boot, run, caps=(CAP, CAP)):
    return subprocess.run(
        [sys.executable, "-I", "-c", DETACHABLE_FRONT, boot, str(run), *map(str, caps)],
        capture_output=True,
        timeout=60,
        check=False,
    )


PROGRAMS = {
    "ok": "import sys\nprint('built');print('note',file=sys.stderr)",
    "fails": "import sys\nsys.stdout.write('partial');sys.stderr.write('Traceback: boom\\n');sys.exit(3)",
    "large": "import sys\nsys.stdout.write('x'*300000);sys.stderr.write('y'*70000)",
    "exit_text": "import sys\nsys.exit('a message')",
}


@pytest.mark.parametrize("which", sorted(PROGRAMS))
def test_the_front_end_relays_exactly_what_the_bare_bootstrap_shows(which, tmp_path):
    boot = _boot(PROGRAMS[which])
    bare = _bare(boot)
    run = tmp_path / "run"
    front = _front(boot, run)
    assert (front.returncode, front.stdout, front.stderr) == (
        bare.returncode,
        bare.stdout,
        bare.stderr,
    )
    # and the same, kept in its run directory (owner-only), the exit status written whole
    assert (run / "stdout").read_bytes() == bare.stdout
    assert (run / "stderr").read_bytes() == bare.stderr
    assert (run / "exit").read_text() == f"{bare.returncode}\n"
    assert not (run / "exit.part").exists()
    assert oct(run.stat().st_mode & 0o777) == oct(0o700)


def test_a_bootstrap_that_fails_before_its_program_fails_the_same_way(tmp_path):
    boot = "raise ValueError('staging failed')\n"
    bare, front = _bare(boot), _front(boot, tmp_path / "run")
    assert front.returncode == bare.returncode == 1
    assert front.stdout == bare.stdout == b""
    assert front.stderr.splitlines()[-1] == bare.stderr.splitlines()[-1]
    assert (tmp_path / "run" / "exit").read_text() == "1\n"


def test_a_program_killed_by_a_signal_reports_128_plus_n_as_docker_exec_does(
    tmp_path,
):
    boot = _boot("import os,signal\nos.kill(os.getpid(),signal.SIGKILL)")
    assert _bare(boot).returncode == -9
    front = _front(boot, tmp_path / "run")
    assert front.returncode == 137
    assert (tmp_path / "run" / "exit").read_text() == "137\n"


def test_the_program_is_the_front_ends_one_child_and_the_front_end_waits_for_it(
    tmp_path,
):
    """The front end stays the exec's root while the program runs (the box's program-age read finds exactly one root,
    `_BOX_PROGRAM_AGE`): the program's parent is the front end itself."""
    boot = _boot("import os\nprint(os.getppid())")
    process = subprocess.Popen(
        [sys.executable, "-I", "-c", DETACHABLE_FRONT, boot, str(tmp_path / "run")]
        + [str(CAP), str(CAP)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out, _ = process.communicate(timeout=60)
    assert process.returncode == 0
    assert int(out) == process.pid


def test_the_program_runs_on_and_its_result_is_kept_when_the_door_goes_away(
    tmp_path,
):
    """The door's end of both streams is closed while the program still runs (a door restart): the program finishes,
    and its exit status and output are in the run directory."""
    program = (
        "import sys,time\n"
        "time.sleep(0.5)\n"
        "sys.stdout.write('o'*200000);sys.stdout.flush()\n"
        "sys.stderr.write('e'*1000);sys.stderr.flush()\n"
        "sys.exit(5)"
    )
    run = tmp_path / "run"
    process = subprocess.Popen(
        [sys.executable, "-I", "-c", DETACHABLE_FRONT, _boot(program), str(run)]
        + [str(CAP), str(CAP)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    process.stdout.close()
    process.stderr.close()
    assert process.wait(timeout=60) == 5
    assert (run / "exit").read_text() == "5\n"
    assert (run / "stdout").read_bytes() == b"o" * 200000
    assert (run / "stderr").read_bytes() == b"e" * 1000


def test_a_stream_over_its_cap_is_relayed_one_byte_past_it_so_the_door_still_refuses_it(
    tmp_path,
):
    cap = 4096
    front = _front(
        _boot("import sys\nsys.stdout.write('z'*10000)"),
        tmp_path / "run",
        caps=(cap + 1, cap + 1),
    )
    assert front.returncode == 0
    assert front.stdout == b"z" * (
        cap + 1
    )  # more than the door's maximum: refused there, as before
    assert (tmp_path / "run" / "stdout").read_bytes() == b"z" * (cap + 1)


def test_a_run_directory_that_exists_keeps_the_relay_and_writes_nothing(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    boot = _boot("import sys\nprint('built');sys.exit(2)")
    bare, front = _bare(boot), _front(boot, run)
    assert (front.returncode, front.stdout, front.stderr) == (
        bare.returncode,
        bare.stdout,
        bare.stderr,
    )
    assert list(run.iterdir()) == []


def test_only_a_remote_gpu_build_op_runs_detachable_and_every_other_command_is_unchanged(
    monkeypatch,
):
    today = ["exec", "c1", "/opt/carbon-worker/bin/python", "-I", "-c", BOOTSTRAP]
    assert _program_command("c1", BOOTSTRAP, detachable=False, maximum=1024**2) == today
    assert _program_command("c1", BOOTSTRAP, detachable=True, maximum=1024**2) == [
        *today[:5],
        DETACHABLE_FRONT,
        BOOTSTRAP,
        DETACHABLE_RUN_DIR,
        str(1024**2 + 1),
        str(DIAGNOSTIC_BYTES + 1),
    ]
    gpu = research_carrier.remote_gpu_build
    # the door's own daemon (no slot op), a LOCAL slot lane (no DOCKER_HOST), a grade session's member op: unchanged
    monkeypatch.setattr(gpu, "current_op", lambda: None)
    monkeypatch.setattr(gpu, "docker_host", lambda: None)
    assert _detachable() is False
    monkeypatch.setattr(gpu, "current_op", lambda: object())
    assert _detachable() is False
    monkeypatch.setattr(gpu, "docker_host", lambda: "ssh://carbon@box")
    assert _detachable() is True
    assert _detachable(session=object()) is False
