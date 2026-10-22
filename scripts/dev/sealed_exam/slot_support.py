"""CPU/memory slots for parallel sealed jobs on one host (VALIDATOR_EXAM_ARCHITECTURE_COMMON_20261022,
C10 amended): disjoint `--cpuset-cpus` ranges plus memory caps, one `flock` per slot, a slot guard
(the slot's cores idle, memory available >= the cap) in place of the load guard on slotted hosts, and a
`docker` shim that gives every container of a job its slot's cpuset and memory (so no per-script
cpuset is hand-rolled and no producer file is edited).

    slot_support.py resolve SLOTS_FILE SLOT        prints "<cpuset> <mem_mib> <cores>"
    slot_support.py guard CPUSET MEM_MIB           exit 1 (with the reason) if the slot is not free
    slot_support.py shim REAL_DOCKER ARGS...       runs docker with the slot's flags (env SLOT_CPUSET, SLOT_MEM_MIB)

The slots file (`~/.carbon-sealed/slots.conf`) has one slot per line: `<name> <cpuset> <mem_mib>`, `#`
comments. A host with no such file is unslotted and keeps the per-host lock and the load guard.
Disjointness of the declared slots is checked on every resolve.
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

UNITS = {"b": 1, "k": 1024, "m": 1024**2, "g": 1024**3}


def cores(spec):
    """The set of CPU ids in a cpuset spec such as `0-15,32`."""
    out = set()
    for part in spec.split(","):
        if re.fullmatch(r"\d+", part):
            out.add(int(part))
        elif re.fullmatch(r"\d+-\d+", part):
            low, high = map(int, part.split("-"))
            if high < low:
                raise ValueError(f"bad cpuset {spec!r}")
            out.update(range(low, high + 1))
        else:
            raise ValueError(f"bad cpuset {spec!r}")
    if not out:
        raise ValueError("empty cpuset")
    return out


def parse_slots(text):
    """{name: (cpuset, mem_mib)} from the slots file text; slots must be disjoint."""
    slots, used = {}, {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        name, cpuset, mem = line.split()
        if name in slots:
            raise ValueError(f"slot {name!r} is declared twice")
        mem_mib = int(mem)
        if mem_mib <= 0:
            raise ValueError(f"slot {name!r} needs a positive memory cap")
        mine = cores(cpuset)
        for other, taken in used.items():
            if mine & taken:
                raise ValueError(f"slots {name!r} and {other!r} share cores")
        used[name] = mine
        slots[name] = (cpuset, mem_mib)
    return slots


def to_bytes(text):
    m = re.fullmatch(r"(\d+)([bkmg]?)", text.lower())
    if m is None:
        raise ValueError(f"bad memory {text!r}")
    return int(m.group(1)) * UNITS[m.group(2) or "b"]


def rewrite_docker_args(args, cpuset, mem_mib):
    """`docker run` arguments with the slot's `--cpuset-cpus` and `--memory`
    (+ equal `--memory-swap`) applied. A memory cap the job already asks for
    that is smaller than the slot's is kept; anything else is replaced. Other
    docker commands are returned unchanged."""
    args = list(args)
    if not args or args[0] != "run":
        return args
    cap = mem_mib * 1024**2
    out, keep_mem, i = ["run"], None, 1
    while i < len(args):
        arg = args[i]
        name, eq, value = arg.partition("=")
        if name in ("--cpuset-cpus", "--memory-swap"):
            i += 1 if eq else 2
            continue
        if name in ("--memory", "-m"):
            raw = value if eq else args[i + 1]
            wanted = to_bytes(raw)
            keep_mem = min(wanted, cap) if keep_mem is None else min(keep_mem, wanted, cap)
            i += 1 if eq else 2
            continue
        out.append(arg)
        if arg == "--":  # nothing after is an option
            out.extend(args[i + 1 :])
            break
        i += 1
    memory = keep_mem if keep_mem is not None else cap
    return ["run", "--cpuset-cpus", cpuset, "--memory", str(memory), "--memory-swap", str(memory)] + out[1:]


def _busy_fraction(cpus, read_stat, wait_s=1.0):
    """Fraction of busy time per CPU in `cpus` over `wait_s` (from /proc/stat)."""

    def sample():
        rows = {}
        for line in read_stat().splitlines():
            m = re.match(r"cpu(\d+)\s+(.*)", line)
            if m and int(m.group(1)) in cpus:
                v = list(map(int, m.group(2).split()))
                idle = v[3] + (v[4] if len(v) > 4 else 0)
                rows[int(m.group(1))] = (sum(v), idle)
        return rows

    first = sample()
    time.sleep(wait_s)
    second = sample()
    busy = {}
    for cpu in cpus:
        total = second[cpu][0] - first[cpu][0]
        idle = second[cpu][1] - first[cpu][1]
        busy[cpu] = 0.0 if total <= 0 else 1 - idle / total
    return busy


def guard(cpuset, mem_mib, *, read_stat=None, read_meminfo=None, running_cpusets=None, wait_s=1.0, max_busy=0.10):
    """`None` when the slot is free, else the reason: another container is pinned
    to any of its cores, a core is busy, or less memory is available than the cap."""
    mine = cores(cpuset)
    read_stat = read_stat or (lambda: Path("/proc/stat").read_text())
    read_meminfo = read_meminfo or (lambda: Path("/proc/meminfo").read_text())
    for other in running_cpusets if running_cpusets is not None else _container_cpusets():
        if other and cores(other) & mine:
            return "a running container is pinned to the slot's cores"
    busy = _busy_fraction(mine, read_stat, wait_s)
    worst = max(busy.values())
    if worst > max_busy:
        return f"the slot's cores are not idle (a core is {worst:.0%} busy)"
    available = int(re.search(r"MemAvailable:\s+(\d+)", read_meminfo()).group(1)) // 1024
    if available < mem_mib:
        return f"only {available} MiB available, the slot's cap is {mem_mib} MiB"
    return None


def _container_cpusets():
    try:
        ids = subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True, check=True).stdout.split()
        if not ids:
            return []
        out = subprocess.run(
            ["docker", "inspect", "--format", "{{.HostConfig.CpusetCpus}}", *ids],
            capture_output=True, text=True, check=True,
        ).stdout.split()
        return out
    except (OSError, subprocess.CalledProcessError):
        return []


def main(argv):
    command = argv[1]
    if command == "resolve" and len(argv) == 4:
        slots = parse_slots(Path(argv[2]).read_text())
        if argv[3] not in slots:
            print(f"unknown slot {argv[3]!r}; declared: {', '.join(sorted(slots))}", file=sys.stderr)
            return 2
        cpuset, mem = slots[argv[3]]
        print(cpuset, mem, len(cores(cpuset)))
        return 0
    if command == "guard" and len(argv) == 4:
        reason = guard(argv[2], int(argv[3]))
        if reason:
            print(reason, file=sys.stderr)
            return 1
        print(json.dumps({"slot_free": True}))
        return 0
    if command == "shim" and len(argv) >= 3:
        real, args = argv[2], argv[3:]
        cpuset, mem = os.environ.get("SLOT_CPUSET"), os.environ.get("SLOT_MEM_MIB")
        if cpuset and mem:
            args = rewrite_docker_args(args, cpuset, int(mem))
        os.execvp(real, [real, *args])
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
