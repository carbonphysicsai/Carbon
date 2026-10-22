"""CPU/memory slots for parallel sealed jobs (C10 amended,
VALIDATOR_EXAM_ARCHITECTURE_COMMON_20261022): disjoint declared slots, containers
rewritten to the slot's cpuset and memory, and a guard that refuses a slot whose
cores are pinned, busy or short of memory."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]


def _slots():
    spec = importlib.util.spec_from_file_location(
        "slot_support", REPOSITORY / "scripts/dev/sealed_exam/slot_support.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONF = """
# custody2: 48 threads, 125 GB
a 0-15 36000
b 16-31 36000   # second slot
c 32-47 36000
"""


def test_declared_slots_are_parsed_and_disjoint():
    m = _slots()
    slots = m.parse_slots(CONF)
    assert slots == {"a": ("0-15", 36000), "b": ("16-31", 36000), "c": ("32-47", 36000)}
    assert m.cores("0-3,8") == {0, 1, 2, 3, 8}
    with pytest.raises(ValueError, match="share cores"):
        m.parse_slots("a 0-15 1000\nb 15-31 1000\n")
    with pytest.raises(ValueError, match="twice"):
        m.parse_slots("a 0-3 1000\na 4-7 1000\n")
    with pytest.raises(ValueError):
        m.parse_slots("a 0-3 0\n")


def test_docker_run_gets_the_slots_cpuset_and_memory():
    m = _slots()
    out = m.rewrite_docker_args(["run", "--rm", "--cpus", "2", "img", "cmd"], "0-15", 36000)
    cap = 36000 * 1024**2
    assert out[:7] == ["run", "--cpuset-cpus", "0-15", "--memory", str(cap), "--memory-swap", str(cap)]
    assert out[7:] == ["--rm", "--cpus", "2", "img", "cmd"]
    # a job's own cpuset is replaced, a smaller memory ask is kept, a larger one is refused (never lowered)
    out = m.rewrite_docker_args(["run", "--cpuset-cpus=0-3", "--memory", "30g", "img"], "16-31", 36000)
    assert out[1:3] == ["--cpuset-cpus", "16-31"] and out[3:5] == ["--memory", str(30 * 1024**3)]
    with pytest.raises(m.SlotMemoryInsufficient):  # 50 GiB in a 32 GiB slot
        m.rewrite_docker_args(["run", "--memory", "50g", "img"], "0-15", 32 * 1024)
    with pytest.raises(m.SlotMemoryInsufficient):
        m.rewrite_docker_args(["run", "-m=100g", "img"], "0-15", 36000)
    small = m.rewrite_docker_args(["run", "-m", "2g", "--memory-swap", "9g", "img"], "0-15", 36000)
    assert small[3:7] == ["--memory", str(2 * 1024**3), "--memory-swap", str(2 * 1024**3)]
    # other docker commands pass through untouched
    assert m.rewrite_docker_args(["ps", "-q"], "0-15", 36000) == ["ps", "-q"]
    assert m.rewrite_docker_args(["image", "inspect", "x"], "0-15", 36000) == ["image", "inspect", "x"]


def _stat(busy):
    """A /proc/stat reader whose cores 0-1 are busy by `busy` (a fraction) per call."""
    calls = {"n": 0}

    def read():
        calls["n"] += 1
        n = calls["n"]
        rows = []
        for cpu in range(4):
            work = int(1000 * n * (busy if cpu < 2 else 0.0))
            idle = 1000 * n - work
            rows.append(f"cpu{cpu} {work} 0 0 {idle} 0 0 0 0")
        return "cpu 0 0 0 0\n" + "\n".join(rows) + "\n"

    return read


MEMINFO = "MemTotal: 100000 kB\nMemAvailable: {kb} kB\n"


def test_the_guard_needs_idle_cores_free_of_pinned_containers_and_enough_memory():
    m = _slots()
    ok = dict(running_cpusets=[], wait_s=0)
    meminfo = lambda: MEMINFO.format(kb=40_000_000)  # noqa: E731 - 39062 MiB
    assert m.guard("0-3", 36000, read_stat=_stat(0.0), read_meminfo=meminfo, **ok) is None
    assert "not idle" in m.guard("0-3", 36000, read_stat=_stat(0.5), read_meminfo=meminfo, **ok)
    assert "pinned" in m.guard(
        "0-3", 36000, read_stat=_stat(0.0), read_meminfo=meminfo, running_cpusets=["2-5"], wait_s=0
    )
    assert m.guard(
        "0-3", 36000, read_stat=_stat(0.0), read_meminfo=meminfo, running_cpusets=["8-11", ""], wait_s=0
    ) is None
    short = lambda: MEMINFO.format(kb=30_000_000)  # noqa: E731 - 29296 MiB < the 36000 cap
    assert "only" in m.guard("0-3", 36000, read_stat=_stat(0.0), read_meminfo=short, **ok)


def test_the_runner_takes_a_slot_lock_and_labels_walls_with_the_slot():
    text = (REPOSITORY / "scripts/dev/sealed_exam/run_sealed.sh").read_text()
    assert ".slot-$SLOT.lock" in text and "slot_support.py\" guard" in text
    assert "slot_support.py shim" in text or "slot_support.py\\\" shim" in text or "shim" in text
    assert '\\"slot\\": \\"$SLOT\\"' in text and "cpuset" in text
    assert "REFERENCE_TIMEOUT" in text and "the isolation did not hold" in text
    assert "slots.conf" in text


def test_the_runner_refuses_a_small_slot_and_types_oom_and_refusal_as_infra_stops(tmp_path):
    text = (REPOSITORY / "scripts/dev/sealed_exam/run_sealed.sh").read_text()
    assert "MEM_REQUIRED_MIB" in text and "slot_memory_insufficient" in text
    assert ".slot_oom_137" in text and ".slot_memory_insufficient" in text
    # the shim refuses a too-large container with rc 125 and the typed message, and marks an rc-137 run
    import subprocess, sys, os
    script = REPOSITORY / "scripts/dev/sealed_exam/slot_support.py"
    env = {**os.environ, "SLOT_CPUSET": "0-1", "SLOT_MEM_MIB": "32768", "SLOT_MARKER_DIR": str(tmp_path)}
    done = subprocess.run([sys.executable, str(script), "shim", "/bin/true", "run", "--memory", "50g", "img"],
                          env=env, capture_output=True, text=True)
    assert done.returncode == 125 and "slot_memory_insufficient" in done.stderr
    assert (tmp_path / ".slot_memory_insufficient").exists()
    fake = tmp_path / "docker"
    fake.write_text("#!/bin/sh\nexit 137\n")
    fake.chmod(0o755)
    done = subprocess.run([sys.executable, str(script), "shim", str(fake), "run", "img"], env=env)
    assert done.returncode == 137 and (tmp_path / ".slot_oom_137").exists()
