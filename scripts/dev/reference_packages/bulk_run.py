"""Bulk reference-data runner: many families' frozen decks on one large host.

    python3 bulk_run.py --plan PLAN.json --out OUT --dry-run
    python3 bulk_run.py --plan PLAN.json --out OUT
    python3 bulk_run.py --plan PLAN.json --out OUT --summarize

The general form of ``triage_run.py`` (which stays as it is for the
OWNER-REFERENCE-ROUTE-TRIAGE-GRANT-01 triage): one hourly cloud machine runs
cases of several families at once. Standard library only, Python 3.11+.

Input is a run plan, schema ``carbon.reference-bulk.run-plan.v1``::

    {"schema": "carbon.reference-bulk.run-plan.v1", "plan_id": "bulk-2026-10-a",
     "authority": "<decision id that grants the spend>", "host_profile": "...",
     "machine": {"cpus": 48, "memory_gib": 180, "node_hours": 10,
                 "eur_cap": 20, "eur_per_hour": 1.5, "billing_quantum_s": 3600,
                 "reserve_cpus": 1, "reserve_memory_gib": 8, "margin_minutes": 15,
                 "clock_start": "boot", "starvation_s": 900, "min_case_window_s": 600},
     "families": [{"family": "f02", "manifest_dir": "decks/f02",
                   "image": "sha256:<id> | repo@sha256:<digest>", "priority": 10,
                   "case_limits": {"cpus": 1, "memory_gib": 4, "pids": 64,
                                   "wall_timeout_s": 7200},
                   "ceilings": {"launches": 400, "cpu_hours": 120},
                   "acceptance": {"command": "ElmerSolver -v", "timeout_s": 300},
                   "entrypoint": "override", "shell": "sh", "env": {},
                   "reservation_order": ["primary", "..."]}]}

``manifest_dir`` (relative to the plan file) holds a frozen manifest, schema
``carbon.reference-triage.frozen-decks.v1``: ``manifest.json`` with ``image``
and ``cases[{family, case, reservation, command, files{relpath: sha256},
mesh?, estimate_cpu_s?, estimate_wall_s?, estimate_mem_mib?}]``, case files
in ``<manifest_dir>/<family>/<case>/``.

Rules (from the triage grant, kept for every bulk run):

- Before any launch every family's image is inspected and must carry the
  manifest's pinned identity, and every case file is hashed against the
  manifest. Each case's files are copied to a fresh work dir and hashed
  again just before launch.
- Containers run with ``--network none --read-only``, a writable work dir at
  ``/case``, ``--cpus/--memory/--memory-swap/--pids-limit`` from the family's
  case limits, no capabilities. The case's cgroup CPU usage and memory peak
  (cgroup v2 ``cpu.stat``/``memory.peak``; v1 ``cpuacct.usage``/
  ``memory.max_usage_in_bytes``) are recorded from inside the container.
- Cases are bin-packed by CPUs and memory against the machine's totals minus
  its reserve; the machine is never oversubscribed.
- A launch first appends a STARTED row that reserves ``timeout x cpus``
  against the family's CPU-hour ceiling and counts one launch, so concurrent
  cases can never overshoot a ceiling. The FINISHED row then books the real
  ``wall x cpus``. A case whose remaining budget is shorter than its timeout
  waits while its family has cases in flight, else runs clipped and is
  CENSORED_FAMILY_CAP if it reaches the clip.
- No retries, ever. A case with a STARTED row is never launched again; a
  STARTED row without its FINISHED row (runner crash) becomes
  ABANDONED_ON_RESUME, booked at its full reservation, and its container is
  killed.
- Global stops: node-hours (clock from host boot by default) and the EUR cap
  give a deadline; cases are clipped to it (CENSORED_MACHINE_CAP). ``OUT/STOP``
  (or one SIGTERM/SIGINT) drains: nothing new starts, running cases finish.
  ``OUT/STOP_NOW`` (or a second signal) stops running cases
  (CENSORED_OPERATOR_STOP).
- Output: ``OUT/ledger.jsonl``, ``OUT/cases/<family>/<case>/{work,meta}``,
  ``OUT/summary/<family>.json`` and ``OUT/summary/all.json``.

``--executor native`` (for a host without Docker, such as a RunPod CPU pod
built as the pinned image is, ``scripts/dev/reference_packages/pod_phase.py``)
runs each case's command directly, with the same ledger, ceilings, scheduler
and no-retry rules. What changes:

- the image check becomes an environment check: every family needs
  ``native {version_command, version_expect}`` and the command's output must
  contain the expected solver version string before any launch;
- the case runs in its own session (process group) as ``shell -c command`` in
  its fresh work dir, pinned to ``ceil(cpus)`` free cores when enough are
  free, under ``RLIMIT_AS`` = the memory limit (``native.memory_cap``
  ``rlimit_as``, the default; ``rss`` drops it) and a sampled whole-group RSS
  watchdog that kills the group past the limit (exit 137, ``oom_suspected``);
  no network or filesystem isolation and no PID limit (the host is a
  single-tenant pod);
- timeout and cancel SIGTERM the group ``grace`` s before the limit and then
  SIGKILL it; leftovers in the group are killed when the shell exits;
- cost is ``os.wait4`` rusage (user + system CPU of the shell and every
  descendant it reaped, ``ru_maxrss`` = the largest single process) plus the
  sampled group RSS peak; ledger rows carry ``executor: native`` and the
  environment description instead of cgroup figures.

Engineering tooling only: it runs public decks under enforced caps and records
cost. It decides nothing about reference adequacy, qualification or spend.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import heapq
import json
import math
import os
import platform
import queue
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

PLAN_SCHEMA = "carbon.reference-bulk.run-plan.v1"
MANIFEST_SCHEMA = "carbon.reference-triage.frozen-decks.v1"
LEDGER_SCHEMA = "carbon.reference-bulk.ledger.v1"
SUMMARY_SCHEMA = "carbon.reference-bulk.summary.v1"
#: Default run order within a family, the same as ``triage_run.PRIORITY``:
#: primaries first, so a ceiling can only censor refinements.
PRIORITY = (
    "primary",
    "primary_sweeps",
    "controls",
    "steady_baselines",
    "separate_frequency_smoke",
    "mesh_and_time",
    "fine_sweeps",
    "witness_studies",
    "cold_repeat",
)
GIB, MIB = 1024**3, 1024**2
STOP_GRACE_S = 20
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
IMAGE_REF = re.compile(
    r"^(sha256:[0-9a-f]{64}|[a-z0-9][a-z0-9._/:-]*@sha256:[0-9a-f]{64})$"
)
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
OUTCOMES = (
    "COMPLETED",
    "FAILED",
    "FAILED_INFRA",
    "CENSORED_CASE_TIMEOUT",
    "CENSORED_FAMILY_CAP",
    "CENSORED_MACHINE_CAP",
    "CENSORED_OPERATOR_STOP",
    "ABANDONED_ON_RESUME",
)

#: POSIX sh, PID 1 of the container (or a child of the image's entrypoint).
#: Runs the case, then writes the container cgroup's CPU usage and memory peak.
WRAPPER = r"""
echo $$ > /carbon-meta/pid
_stats() {
  c=/sys/fs/cgroup
  {
    if [ -r $c/memory.peak ]; then
      echo "memory_peak_bytes $(cat $c/memory.peak)"; echo "cgroup_version 2"
    elif [ -r $c/memory/memory.max_usage_in_bytes ]; then
      echo "memory_peak_bytes $(cat $c/memory/memory.max_usage_in_bytes)"
      echo "cgroup_version 1"
    fi
    if [ -r $c/cpu.stat ]; then
      while read k v; do [ "$k" = usage_usec ] && echo "cpu_usage_usec $v"; done < $c/cpu.stat
    elif [ -r $c/cpuacct/cpuacct.usage ]; then
      echo "cpu_usage_nsec $(cat $c/cpuacct/cpuacct.usage)"
    elif [ -r $c/cpu,cpuacct/cpuacct.usage ]; then
      echo "cpu_usage_nsec $(cat $c/cpu,cpuacct/cpuacct.usage)"
    fi
  } > /carbon-meta/cgroup.txt 2>/dev/null
}
_term() { kill -TERM -1 2>/dev/null; wait; _stats; echo 143 > /carbon-meta/exit; exit 143; }
trap _term TERM INT
"$CARBON_SHELL" -c "$CARBON_CMD" &
wait $!
rc=$?
_stats
echo "$rc" > /carbon-meta/exit
exit "$rc"
"""


class PlanError(Exception):
    """The plan, a manifest, an image or a case file is not as pinned."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


@dataclass(frozen=True)
class Limits:
    cpus: float
    memory_bytes: int
    pids: int
    wall_timeout_s: float


@dataclass
class Case:
    family: str
    name: str
    reservation: str
    command: str
    files: dict
    source_dir: Path
    est_cpu_s: float | None
    est_wall_s: float | None
    est_mem_mib: float | None
    rank: tuple

    @property
    def key(self):
        return (self.family, self.name)


@dataclass
class Family:
    name: str
    priority: int
    image: str
    manifest_dir: Path
    limits: Limits
    max_launches: int
    cpu_hours: float
    acceptance: dict | None
    entrypoint: str
    shell: str
    env: dict
    order: tuple
    native: dict | None = None
    manifest_image: str = ""
    manifest_sha256: str = ""
    cases: list = field(default_factory=list)


@dataclass
class Plan:
    path: Path
    digest: str
    plan_id: str
    authority: str | None
    host_profile: str | None
    machine: dict
    families: list

    @property
    def usable_cpus(self):
        return self.machine["cpus"] - self.machine["reserve_cpus"]

    @property
    def usable_memory_bytes(self):
        m = self.machine
        return int((m["memory_gib"] - m["reserve_memory_gib"]) * GIB)

    def family(self, name):
        return next(f for f in self.families if f.name == name)

    def cases(self):
        return sorted((c for f in self.families for c in f.cases), key=lambda c: c.rank)


# --------------------------------------------------------------------- plan


def _num(obj, key, where, problems, *, default=None, integer=False, positive=True):
    if key not in obj:
        if default is None:
            problems.append(f"{where}.{key} is required")
        return default
    value = obj[key]
    ok = isinstance(value, int if integer else (int, float)) and not isinstance(
        value, bool
    )
    if not ok or (value <= 0 if positive else value < 0):
        kind = "integer" if integer else "number"
        problems.append(
            f"{where}.{key} must be a {'positive' if positive else 'non-negative'} {kind}"
        )
        return default
    return value


def _keys(obj, allowed, where, problems):
    if not isinstance(obj, dict):
        problems.append(f"{where} must be an object")
        return False
    extra = sorted(set(obj) - set(allowed))
    if extra:
        problems.append(f"{where}: unknown keys {extra}")
    return True


def _safe_relpath(rel):
    parts = Path(rel).parts
    return bool(parts) and not Path(rel).is_absolute() and ".." not in parts


def _sha_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_plan(path):
    """Parse and validate a run plan and its families' manifests."""
    path = Path(path)
    raw = path.read_bytes()
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PlanError([f"plan is not JSON: {exc}"]) from exc
    problems = []
    top = {"schema", "plan_id", "authority", "host_profile", "machine", "families"}
    _keys(doc, top, "plan", problems)
    if doc.get("schema") != PLAN_SCHEMA:
        problems.append(f"plan.schema must be {PLAN_SCHEMA}")
    plan_id = doc.get("plan_id", "")
    if not isinstance(plan_id, str) or not NAME.match(plan_id):
        problems.append("plan.plan_id must match [A-Za-z0-9._-]")
    machine = _machine(doc.get("machine", {}), problems)
    families = []
    for i, entry in enumerate(doc.get("families") or []):
        fam = _family(entry, f"families[{i}]", path.parent, machine, problems)
        if fam:
            families.append(fam)
    if not doc.get("families"):
        problems.append("plan.families must be a non-empty list")
    names = [f.name for f in families]
    if len(names) != len(set(names)):
        problems.append("plan.families: a family appears twice")
    for fam in families:
        _load_manifest(fam, problems)
    if problems:
        raise PlanError(problems)
    canonical = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
    return Plan(
        path=path,
        digest="sha256:" + hashlib.sha256(canonical).hexdigest(),
        plan_id=plan_id,
        authority=doc.get("authority"),
        host_profile=doc.get("host_profile"),
        machine=machine,
        families=families,
    )


def _machine(m, problems):
    allowed = {
        "cpus",
        "memory_gib",
        "node_hours",
        "eur_cap",
        "eur_per_hour",
        "billing_quantum_s",
        "reserve_cpus",
        "reserve_memory_gib",
        "margin_minutes",
        "clock_start",
        "starvation_s",
        "min_case_window_s",
    }
    if not _keys(m, allowed, "machine", problems):
        return {}
    out = {
        "cpus": _num(m, "cpus", "machine", problems),
        "memory_gib": _num(m, "memory_gib", "machine", problems),
        "node_hours": _num(m, "node_hours", "machine", problems),
        "billing_quantum_s": _num(
            m, "billing_quantum_s", "machine", problems, default=3600
        ),
        "reserve_cpus": _num(
            m, "reserve_cpus", "machine", problems, default=0, positive=False
        ),
        "reserve_memory_gib": _num(
            m, "reserve_memory_gib", "machine", problems, default=0, positive=False
        ),
        "margin_minutes": _num(
            m, "margin_minutes", "machine", problems, default=15, positive=False
        ),
        "starvation_s": _num(
            m, "starvation_s", "machine", problems, default=900, positive=False
        ),
        "min_case_window_s": _num(
            m, "min_case_window_s", "machine", problems, default=600, positive=False
        ),
        "eur_cap": None,
        "eur_per_hour": None,
    }
    if ("eur_cap" in m) != ("eur_per_hour" in m):
        problems.append("machine.eur_cap and machine.eur_per_hour go together")
    elif "eur_cap" in m:
        out["eur_cap"] = _num(m, "eur_cap", "machine", problems)
        out["eur_per_hour"] = _num(m, "eur_per_hour", "machine", problems)
    clock = m.get("clock_start", "boot")
    if clock not in ("boot", "first_run") and not (
        isinstance(clock, (int, float)) and not isinstance(clock, bool) and clock > 0
    ):
        problems.append("machine.clock_start must be boot, first_run or a unix time")
    out["clock_start"] = clock
    if None in (out["cpus"], out["memory_gib"]):
        return out
    if out["reserve_cpus"] >= out["cpus"]:
        problems.append("machine.reserve_cpus leaves no CPU for cases")
    if out["reserve_memory_gib"] >= out["memory_gib"]:
        problems.append("machine.reserve_memory_gib leaves no memory for cases")
    return out


def _family(entry, where, base, machine, problems):
    allowed = {
        "family",
        "manifest_dir",
        "image",
        "priority",
        "case_limits",
        "ceilings",
        "acceptance",
        "entrypoint",
        "shell",
        "env",
        "reservation_order",
        "native",
    }
    if not _keys(entry, allowed, where, problems):
        return None
    n0 = len(problems)
    name = entry.get("family", "")
    if not isinstance(name, str) or not NAME.match(name):
        problems.append(f"{where}.family must match [A-Za-z0-9._-]")
    image = entry.get("image", "")
    if not isinstance(image, str) or not IMAGE_REF.match(image):
        problems.append(
            f"{where}.image must be an image id (sha256:...) or repo@sha256:... digest"
        )
    if not isinstance(entry.get("manifest_dir"), str):
        problems.append(f"{where}.manifest_dir is required")
    priority = entry.get("priority", 100)
    if not isinstance(priority, int) or isinstance(priority, bool):
        problems.append(f"{where}.priority must be an integer")
    lim = entry.get("case_limits")
    limits = None
    if _keys(
        lim,
        {"cpus", "memory_gib", "pids", "wall_timeout_s"},
        f"{where}.case_limits",
        problems,
    ):
        w = f"{where}.case_limits"
        cpus = _num(lim, "cpus", w, problems)
        mem = _num(lim, "memory_gib", w, problems)
        pids = _num(lim, "pids", w, problems, integer=True)
        wall = _num(lim, "wall_timeout_s", w, problems)
        if None not in (cpus, mem, pids, wall):
            limits = Limits(cpus, int(mem * GIB), pids, float(wall))
            if machine.get("cpus") and machine.get("memory_gib"):
                usable_cpus = machine["cpus"] - machine["reserve_cpus"]
                usable_mem = (
                    machine["memory_gib"] - machine["reserve_memory_gib"]
                ) * GIB
                if cpus > usable_cpus or limits.memory_bytes > usable_mem:
                    problems.append(f"{w} exceed the machine's usable CPUs or memory")
    ceil = entry.get("ceilings")
    launches = cpu_hours = None
    if _keys(ceil, {"launches", "cpu_hours"}, f"{where}.ceilings", problems):
        launches = _num(ceil, "launches", f"{where}.ceilings", problems, integer=True)
        cpu_hours = _num(ceil, "cpu_hours", f"{where}.ceilings", problems)
    acceptance = entry.get("acceptance")
    if acceptance is not None and _keys(
        acceptance,
        {"command", "timeout_s", "cpus", "memory_gib"},
        f"{where}.acceptance",
        problems,
    ):
        if not isinstance(acceptance.get("command"), str) or not acceptance["command"]:
            problems.append(f"{where}.acceptance.command is required")
        for key in ("timeout_s", "cpus", "memory_gib"):
            if key in acceptance:
                _num(acceptance, key, f"{where}.acceptance", problems)
    entrypoint = entry.get("entrypoint", "override")
    if entrypoint not in ("override", "image"):
        problems.append(f"{where}.entrypoint must be override or image")
    shell = entry.get("shell", "sh")
    if not isinstance(shell, str) or not re.match(r"^[A-Za-z0-9/._-]+$", shell):
        problems.append(f"{where}.shell must be a plain program name")
    env = entry.get("env", {})
    if not isinstance(env, dict) or not all(
        isinstance(k, str) and ENV_NAME.match(k) and isinstance(v, str)
        for k, v in env.items()
    ):
        problems.append(f"{where}.env must map names to strings")
    order = entry.get("reservation_order", list(PRIORITY))
    if not isinstance(order, list) or not all(isinstance(x, str) for x in order):
        problems.append(f"{where}.reservation_order must be a list of strings")
    native = entry.get("native")
    if native is not None and _keys(
        native,
        {"version_command", "version_expect", "timeout_s", "memory_cap"},
        f"{where}.native",
        problems,
    ):
        for key in ("version_command", "version_expect"):
            if not isinstance(native.get(key), str) or not native[key].strip():
                problems.append(f"{where}.native.{key} is required")
        if "timeout_s" in native:
            _num(native, "timeout_s", f"{where}.native", problems)
        if native.get("memory_cap", "rlimit_as") not in ("rlimit_as", "rss"):
            problems.append(f"{where}.native.memory_cap must be rlimit_as or rss")
    if len(problems) > n0:
        return None
    return Family(
        name=name,
        priority=priority,
        image=image,
        manifest_dir=(base / entry["manifest_dir"]).resolve(),
        limits=limits,
        max_launches=launches,
        cpu_hours=float(cpu_hours),
        acceptance=acceptance,
        entrypoint=entrypoint,
        shell=shell,
        env=dict(env),
        order=tuple(order),
        native=dict(native) if native is not None else None,
    )


def _load_manifest(fam, problems):
    where = f"{fam.name} manifest"
    path = fam.manifest_dir / "manifest.json"
    if not path.is_file():
        problems.append(f"{where}: {path} not found")
        return
    raw = path.read_bytes()
    fam.manifest_sha256 = "sha256:" + hashlib.sha256(raw).hexdigest()
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        problems.append(f"{where}: not JSON: {exc}")
        return
    if doc.get("schema") != MANIFEST_SCHEMA:
        problems.append(f"{where}: schema must be {MANIFEST_SCHEMA}")
    fam.manifest_image = doc.get("image", "")
    if not isinstance(fam.manifest_image, str) or not (
        DIGEST.match(fam.manifest_image) or IMAGE_REF.match(fam.manifest_image)
    ):
        problems.append(f"{where}: image must be a sha256 pin")
    order = {r: i for i, r in enumerate(fam.order)}
    seen = set()
    for index, entry in enumerate(doc.get("cases") or []):
        if not isinstance(entry, dict) or entry.get("family") != fam.name:
            continue
        name = entry.get("case", "")
        tag = f"{where}: case {name!r}"
        if not isinstance(name, str) or not NAME.match(name) or name in seen:
            problems.append(f"{tag}: missing, unsafe or duplicate name")
            continue
        seen.add(name)
        command = entry.get("command")
        files = entry.get("files")
        if not isinstance(command, str) or not command.strip():
            problems.append(f"{tag}: command is required")
        if (
            not isinstance(files, dict)
            or not files
            or not all(
                isinstance(k, str)
                and _safe_relpath(k)
                and isinstance(v, str)
                and re.match(r"^[0-9a-f]{64}$", v)
                for k, v in files.items()
            )
        ):
            problems.append(f"{tag}: files must map safe relative paths to sha256")
            continue
        estimates = {}
        for key in ("estimate_cpu_s", "estimate_wall_s", "estimate_mem_mib"):
            value = entry.get(key)
            if value is not None and (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or value < 0
            ):
                problems.append(f"{tag}: {key} must be a non-negative number")
                value = None
            estimates[key] = value
        reservation = str(entry.get("reservation", ""))
        fam.cases.append(
            Case(
                family=fam.name,
                name=name,
                reservation=reservation,
                command=command or "",
                files=dict(files),
                source_dir=fam.manifest_dir / fam.name / name,
                est_cpu_s=estimates["estimate_cpu_s"],
                est_wall_s=estimates["estimate_wall_s"],
                est_mem_mib=estimates["estimate_mem_mib"],
                rank=(
                    fam.priority,
                    order.get(reservation, len(order)),
                    index,
                    fam.name,
                ),
            )
        )
    if not fam.cases:
        problems.append(f"{where}: no cases for family {fam.name}")


def verify_case_files(directory, files):
    """Relative paths whose file is missing or differs from its pinned sha256."""
    bad = []
    for rel, want in sorted(files.items()):
        path = Path(directory) / rel
        if not path.is_file() or _sha_file(path) != want:
            bad.append(rel)
    return bad


def preflight(plan, docker, check_images=True):
    """Every image carries its manifest's pin and every case file its hash."""
    problems, images = [], {}
    for fam in plan.families:
        if not check_images:
            continue
        ids = docker.image_identities(fam.image)
        if ids is None:
            problems.append(f"{fam.name}: image {fam.image} is not on this host")
            continue
        if fam.manifest_image not in ids:
            ids = set(ids) | set(docker.config_digests(fam.image))
        if fam.manifest_image not in ids:
            problems.append(
                f"{fam.name}: image {fam.image} is not the manifest's {fam.manifest_image}"
            )
        images[fam.name] = sorted(ids)
    for case in plan.cases():
        bad = verify_case_files(case.source_dir, case.files)
        if bad:
            problems.append(
                f"{case.family}/{case.name}: files differ from the manifest: {bad[:3]}"
            )
    if problems:
        raise PlanError(problems)
    return images


# ------------------------------------------------------------------- ledger


class Ledger:
    """Append-only JSONL; each row is flushed and fsynced before it counts."""

    def __init__(self, path):
        self.path = Path(path)
        self.rows, self.corrupt_lines = [], 0
        self._lock = threading.Lock()
        if self.path.exists():
            raw = self.path.read_bytes()
            for line in raw.decode(errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    self.rows.append(json.loads(line))
                except json.JSONDecodeError:
                    self.corrupt_lines += 1  # a crash mid-write; never reused
            if raw and not raw.endswith(b"\n"):
                with open(self.path, "ab") as handle:
                    handle.write(b"\n")

    def append(self, row):
        row = {"schema": LEDGER_SCHEMA, **row}
        line = json.dumps(row, sort_keys=True) + "\n"
        with self._lock:
            with open(self.path, "a") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
            self.rows.append(row)
        return row


@dataclass
class Book:
    """A family's ceiling use: launches, booked and reserved allocated CPU-s."""

    launches: int = 0
    booked_cpu_s: float = 0.0
    reserved: dict = field(default_factory=dict)

    def free_cpu_s(self, fam):
        return fam.cpu_hours * 3600 - self.booked_cpu_s - sum(self.reserved.values())


@dataclass
class Job:
    case: Case
    timeout_s: float
    clip: str
    reserved_cpu_s: float
    started_unix: float
    work: Path
    meta: Path
    cancel: threading.Event = field(default_factory=threading.Event)


# ------------------------------------------------------------------- docker


def _parse_cgroup(path):
    out = {
        "cgroup_cpu_s": None,
        "cgroup_memory_peak_bytes": None,
        "cgroup_version": None,
    }
    if not Path(path).exists():
        return out
    for line in Path(path).read_text().splitlines():
        key, _, value = line.partition(" ")
        if not value.strip().isdigit():
            continue
        value = int(value)
        if key == "memory_peak_bytes":
            out["cgroup_memory_peak_bytes"] = value
        elif key == "cpu_usage_usec":
            out["cgroup_cpu_s"] = round(value / 1e6, 3)
        elif key == "cpu_usage_nsec":
            out["cgroup_cpu_s"] = round(value / 1e9, 3)
        elif key == "cgroup_version":
            out["cgroup_version"] = value
    return out


def container_name(plan_id, family, case):
    tag = hashlib.sha256(f"{plan_id}/{family}/{case}".encode()).hexdigest()[:8]
    return f"cb-{plan_id}-{family}-{case}"[:96] + f"-{tag}"


class DockerCli:
    """The real docker; tests inject an object with the same methods."""

    def info(self):
        done = subprocess.run(
            ["docker", "info", "--format", "{{json .}}"],
            capture_output=True,
            text=True,
            check=False,
        )
        try:
            info = json.loads(done.stdout)
        except json.JSONDecodeError:
            return {}
        keys = (
            "ServerVersion",
            "CgroupVersion",
            "CgroupDriver",
            "Driver",
            "NCPU",
            "MemTotal",
        )
        return {k: info.get(k) for k in keys}

    def image_identities(self, ref):
        """Digests docker knows this image by, or None when it is absent."""
        done = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{json .}}", ref],
            capture_output=True,
            text=True,
            check=False,
        )
        if done.returncode != 0:
            return None
        info = json.loads(done.stdout)
        ids = {info.get("Id")}
        ids.add((info.get("Descriptor") or {}).get("digest"))
        ids.update(
            d.split("@", 1)[1] for d in info.get("RepoDigests") or [] if "@" in d
        )
        plat = subprocess.run(
            [
                "docker",
                "image",
                "inspect",
                "--platform",
                "linux/amd64",
                "--format",
                "{{.Id}}",
                ref,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if plat.returncode == 0:
            ids.add(plat.stdout.strip())
        return {i for i in ids if isinstance(i, str) and DIGEST.match(i)}

    def config_digests(self, ref):
        """The image config digest(s), read from ``docker image save``'s
        manifest.json (a containerd store names images by manifest digest)."""
        proc = subprocess.Popen(
            ["docker", "image", "save", ref],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        found = set()
        try:
            with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
                for member in tar:
                    if member.name == "manifest.json":
                        for item in json.load(tar.extractfile(member)):
                            leaf = str(item.get("Config", "")).rsplit("/", 1)[-1]
                            leaf = leaf.removesuffix(".json")
                            if re.match(r"^[0-9a-f]{64}$", leaf):
                                found.add("sha256:" + leaf)
                        break
        except (tarfile.TarError, OSError, json.JSONDecodeError):
            pass
        finally:
            proc.kill()
            proc.wait()
        return found

    def kill_stale(self, plan_id):
        done = subprocess.run(
            ["docker", "ps", "-aq", "--filter", f"label=carbon.bulk.plan={plan_id}"],
            capture_output=True,
            text=True,
            check=False,
        )
        ids = done.stdout.split()
        if ids:
            subprocess.run(
                ["docker", "rm", "-f", *ids], capture_output=True, check=False
            )
        return ids

    @staticmethod
    def command(spec):
        env = {
            "HOME": "/tmp",
            "CARBON_CMD": spec["command"],
            "CARBON_SHELL": spec["shell"],
            "CARBON_CPUS": f"{spec['cpus']:g}",
            "CARBON_MEMORY_BYTES": str(spec["memory_bytes"]),
            **spec["env"],
        }
        cmd = [
            "docker",
            "run",
            "--rm",
            "--name",
            spec["name"],
            "--label",
            f"carbon.bulk.plan={spec['plan_id']}",
            "--label",
            f"carbon.bulk.case={spec['family']}/{spec['case']}",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,exec,nosuid",
            "--cpus",
            f"{spec['cpus']:g}",
            "--memory",
            str(spec["memory_bytes"]),
            "--memory-swap",
            str(spec["memory_bytes"]),
            "--pids-limit",
            str(spec["pids"]),
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "-v",
            f"{spec['work_dir']}:/case",
            "-v",
            f"{spec['meta_dir']}:/carbon-meta",
            "-w",
            "/case",
        ]
        for key, value in env.items():
            cmd += ["-e", f"{key}={value}"]
        if spec["entrypoint"] == "override":
            return cmd + ["--entrypoint", "sh", spec["image"], "-c", WRAPPER]
        return cmd + [spec["image"], "sh", "-c", WRAPPER]

    def run(self, spec, timeout_s, cancel):
        """Run one case; at ``timeout_s - grace`` SIGTERM it so the wrapper
        records cgroup stats, and kill it at ``timeout_s``."""
        meta = Path(spec["meta_dir"])
        grace = min(STOP_GRACE_S, timeout_s / 4)
        t0 = time.monotonic()
        reason = "exit"
        with (
            open(meta / "docker.stdout", "wb") as out,
            open(meta / "docker.stderr", "wb") as err,
        ):
            proc = subprocess.Popen(self.command(spec), stdout=out, stderr=err)
            while True:
                left = timeout_s - grace - (time.monotonic() - t0)
                try:
                    rc = proc.wait(timeout=min(1.0, max(0.05, left)))
                    break
                except subprocess.TimeoutExpired:
                    pass
                if cancel.is_set():
                    reason = "cancel"
                elif time.monotonic() - t0 >= timeout_s - grace:
                    reason = "timeout"
                else:
                    continue
                rc = self._stop(spec["name"], proc, max(grace, 1.0))
                break
        result = {"exit": rc, "stop_reason": reason, "wall_s": time.monotonic() - t0}
        result.update(_parse_cgroup(meta / "cgroup.txt"))
        return result

    @staticmethod
    def _stop(name, proc, grace):
        """SIGTERM the wrapper (it stops the case and records cgroup stats),
        then kill the container once ``grace`` seconds have passed."""
        t0 = time.monotonic()
        try:
            subprocess.run(
                [
                    "docker",
                    "exec",
                    name,
                    "sh",
                    "-c",
                    "kill -TERM $(cat /carbon-meta/pid)",
                ],
                capture_output=True,
                check=False,
                timeout=grace,
            )
        except subprocess.TimeoutExpired:
            pass
        try:
            return proc.wait(timeout=max(0.1, grace - (time.monotonic() - t0)))
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "kill", name], capture_output=True, check=False)
            return proc.wait(timeout=120)


# ------------------------------------------------------------------- native

#: Environment a native case never inherits: provider keys, the pod
#: bootstrap's token and code manifest, any credential-looking name.
NATIVE_ENV_DROP = re.compile(
    r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|^CODE_MANIFEST|^PROBE_|^CARBON_BOOT$",
    re.IGNORECASE,
)
#: Sets the address-space limit and CPU affinity, then becomes the case
#: (``exec``): no ``preexec_fn`` in a threaded runner, and no window in which
#: the case runs unlimited. argv: memory bytes (0 = none), CPU list ("" = all),
#: then the command.
TRAMPOLINE = (
    "import os,resource,sys\n"
    "m=int(sys.argv[1])\n"
    "if m: resource.setrlimit(resource.RLIMIT_AS,(m,m))\n"
    "resource.setrlimit(resource.RLIMIT_CORE,(0,0))\n"
    "c=sys.argv[2]\n"
    "if c: os.sched_setaffinity(0,{int(x) for x in c.split(',')})\n"
    "os.execvp(sys.argv[3],sys.argv[3:])\n"
)
#: Ledger fields a native result adds to its FINISHED row.
NATIVE_FIELDS = (
    "executor",
    "environment",
    "signal",
    "rusage_cpu_s",
    "rusage_user_s",
    "rusage_sys_s",
    "rusage_maxrss_bytes",
    "sampled_group_rss_peak_bytes",
    "rlimit_as_bytes",
    "cpu_affinity",
)


def _group_rss(pgid):
    """Resident bytes of every live process in process group ``pgid``."""
    total, page = 0, os.sysconf("SC_PAGE_SIZE")
    try:
        entries = os.listdir("/proc")
    except OSError:
        return 0
    for name in entries:
        if not name.isdigit():
            continue
        try:
            stat = Path("/proc", name, "stat").read_text()
        except OSError:
            continue
        fields = stat.rsplit(")", 1)[-1].split()
        # fields[0] is the state (stat field 3): pgrp is field 5, rss field 24.
        if len(fields) > 21 and fields[2] == str(pgid):
            total += int(fields[21]) * page
    return total


def _killpg(pgid, sig):
    try:
        os.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def run_native(
    argv,
    cwd,
    env,
    timeout_s,
    cancel,
    *,
    memory_bytes=None,
    rss_limit_bytes=None,
    cpus=None,
    stdout=None,
    stderr=None,
    pgid_file=None,
    poll_s=0.1,
    sample_s=1.0,
):
    """Run ``argv`` natively in its own session and measure it.

    ``memory_bytes`` becomes ``RLIMIT_AS``; ``rss_limit_bytes`` kills the
    whole group once its sampled resident memory passes it; ``cpus`` is a
    set of cores to pin to. At ``timeout_s - grace`` (or on ``cancel``) the
    group gets SIGTERM, then SIGKILL after ``grace``. Returns ``exit``
    (128 + signal for a signalled shell), ``signal``, ``stop_reason``
    (exit/timeout/cancel/memory), ``wall_s`` and the rusage figures."""
    grace = min(STOP_GRACE_S, timeout_s / 4)
    cores = ",".join(str(c) for c in sorted(cpus)) if cpus else ""
    full = [
        sys.executable,
        "-I",
        "-S",
        "-c",
        TRAMPOLINE,
        str(int(memory_bytes or 0)),
        cores,
        *argv,
    ]
    t0 = time.monotonic()
    proc = subprocess.Popen(
        full,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=stdout,
        stderr=stderr,
        start_new_session=True,
    )
    if pgid_file is not None:
        Path(pgid_file).write_text(f"{proc.pid}\n")
    reason, term_at, peak, next_sample = "exit", None, 0, 0.0
    while True:
        pid, status, usage = os.wait4(proc.pid, os.WNOHANG)
        if pid:
            break
        now = time.monotonic()
        if now >= next_sample:
            peak = max(peak, _group_rss(proc.pid))
            next_sample = now + sample_s
        if term_at is None:
            if cancel.is_set():
                reason = "cancel"
            elif now - t0 >= timeout_s - grace:
                reason = "timeout"
            elif rss_limit_bytes and peak > rss_limit_bytes:
                reason = "memory"
                _killpg(proc.pid, signal.SIGKILL)
            if reason in ("cancel", "timeout"):
                _killpg(proc.pid, signal.SIGTERM)
            if reason != "exit":
                term_at = now
        elif now - term_at >= grace:
            _killpg(proc.pid, signal.SIGKILL)
        time.sleep(poll_s)
    wall = time.monotonic() - t0
    proc.returncode = os.waitstatus_to_exitcode(status)
    _killpg(proc.pid, signal.SIGKILL)  # nothing of the case outlives it
    sig = -proc.returncode if proc.returncode < 0 else None
    return {
        "exit": 128 + sig if sig else proc.returncode,
        "signal": sig,
        "stop_reason": reason,
        "wall_s": wall,
        "rusage_user_s": round(usage.ru_utime, 3),
        "rusage_sys_s": round(usage.ru_stime, 3),
        "rusage_cpu_s": round(usage.ru_utime + usage.ru_stime, 3),
        "rusage_maxrss_bytes": usage.ru_maxrss * 1024,  # Linux reports KiB
        "sampled_group_rss_peak_bytes": peak,
        "rlimit_as_bytes": int(memory_bytes) if memory_bytes else None,
    }


def native_env(extra, home):
    """This host's environment for a native case: credentials dropped, HOME
    and the temporary directories inside the case's own scratch dir."""
    env = {k: v for k, v in os.environ.items() if not NATIVE_ENV_DROP.search(k)}
    env.update(extra)
    for key in ("HOME", "TMPDIR", "TMP", "TEMP"):
        env[key] = str(home)
    return env


class NativeExecutor:
    """Runs cases directly on this host, as ``DockerCli`` runs them in
    containers; BulkRun drives either through the same methods."""

    name = "native"

    def __init__(self, out=None, environment=None, cores=None):
        self.out = Path(out) if out is not None else None
        self.environment = environment or os.environ.get(
            "CARBON_REFERENCE_ENV", "native (undescribed)"
        )
        self._free = set(cores if cores is not None else os.sched_getaffinity(0))
        self._lock = threading.Lock()
        self.checks = {}

    def info(self):
        return {
            "executor": "native",
            "environment": self.environment,
            "python": platform.python_version(),
            "affinity_cores": len(self._free),
            "environment_checks": self.checks,
        }

    def check_environment(self, fam):
        """Run the family's version command; its output must contain the
        expected version string. Returns the check's record."""
        spec = fam.native or {}
        record = {
            "command": spec.get("version_command"),
            "expect": spec.get("version_expect"),
        }
        if not spec:
            return record | {"ok": False, "why": "family has no native block"}
        try:
            done = subprocess.run(
                [fam.shell, "-c", spec["version_command"]],
                capture_output=True,
                text=True,
                timeout=float(spec.get("timeout_s", 120)),
                env=native_env(fam.env, "/tmp"),
                check=False,
            )
            text = (done.stdout or "") + (done.stderr or "")
        except (OSError, subprocess.TimeoutExpired) as exc:
            return record | {"ok": False, "why": repr(exc)[:300]}
        line = next(
            (x.strip() for x in text.splitlines() if spec["version_expect"] in x), None
        )
        record |= {
            "ok": line is not None,
            "line": line,
            "exit": done.returncode,
            "output_sha256": hashlib.sha256(text.encode()).hexdigest(),
        }
        self.checks[fam.name] = record
        return record

    def kill_stale(self, plan_id):
        """Process groups a crashed runner of this plan left behind."""
        killed = []
        if self.out is None:
            return killed
        for path in sorted(self.out.glob("cases/*/*/meta/native.pgid")):
            try:
                pgid = int(path.read_text().split()[0])
                environ = Path(f"/proc/{pgid}/environ").read_bytes()
            except (OSError, ValueError, IndexError):
                continue
            if f"CARBON_BULK_PLAN={plan_id}".encode() in environ.split(b"\0"):
                _killpg(pgid, signal.SIGKILL)
                killed.append(pgid)
        return killed

    def _take(self, cpus):
        need = math.ceil(cpus)
        with self._lock:
            if need > len(self._free):
                return set()  # not enough whole cores free: no pinning
            cores = set(sorted(self._free)[:need])
            self._free -= cores
            return cores

    def _give(self, cores):
        with self._lock:
            self._free |= cores

    def run(self, spec, timeout_s, cancel):
        work, meta = Path(spec["work_dir"]), Path(spec["meta_dir"])
        scratch = work.parent / "tmp"
        scratch.mkdir(exist_ok=True)
        env = native_env(
            {
                "CARBON_BULK_PLAN": spec["plan_id"],
                "CARBON_CMD": spec["command"],
                "CARBON_SHELL": spec["shell"],
                "CARBON_CPUS": f"{spec['cpus']:g}",
                "CARBON_MEMORY_BYTES": str(spec["memory_bytes"]),
                **spec["env"],
            },
            scratch,
        )
        cap = spec.get("memory_cap", "rlimit_as")
        cores = self._take(spec["cpus"])
        try:
            with (
                open(meta / "native.stdout", "wb") as out,
                open(meta / "native.stderr", "wb") as err,
            ):
                result = run_native(
                    [spec["shell"], "-c", spec["command"]],
                    work,
                    env,
                    timeout_s,
                    cancel,
                    memory_bytes=spec["memory_bytes"] if cap == "rlimit_as" else None,
                    rss_limit_bytes=spec["memory_bytes"],
                    cpus=cores,
                    stdout=out,
                    stderr=err,
                    pgid_file=meta / "native.pgid",
                )
        finally:
            self._give(cores)
            shutil.rmtree(scratch, ignore_errors=True)
        result["executor"] = "native"
        result["environment"] = self.environment
        result["cpu_affinity"] = len(cores) or None
        return result


def check_native(plan, executor):
    """Before any launch: every family's environment reports its expected
    solver version (the native counterpart of the image check)."""
    problems, checks = [], {}
    for fam in plan.families:
        record = executor.check_environment(fam)
        checks[fam.name] = record
        if not record.get("ok"):
            problems.append(
                f"{fam.name}: environment check failed: expected "
                f"{record.get('expect')!r} from {record.get('command')!r}"
                + (f" ({record['why']})" if record.get("why") else "")
            )
    if problems:
        raise PlanError(problems)
    return checks


def host_info():
    info = {"nproc": os.cpu_count(), "mem_total_bytes": None, "cpu_model": None}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                info["mem_total_bytes"] = int(line.split()[1]) * 1024
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                info["cpu_model"] = line.split(":", 1)[1].strip()
                break
        for line in Path("/proc/stat").read_text().splitlines():
            if line.startswith("btime "):
                info["boot_unix"] = int(line.split()[1])
    except OSError:
        pass
    info["host_cgroup_version"] = (
        2 if Path("/sys/fs/cgroup/cgroup.controllers").exists() else 1
    )
    return info


# --------------------------------------------------------------- scheduling


def _est_wall(case, fam):
    if case.est_wall_s is not None:
        return case.est_wall_s
    if case.est_cpu_s is not None:
        return case.est_cpu_s / fam.limits.cpus
    return None


def _percentile(values, p):
    """Nearest-rank percentile; None for no values."""
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    return values[max(0, math.ceil(p / 100 * len(values)) - 1)]


def machine_deadline(plan, clock_start):
    m = plan.machine
    hours = m["node_hours"]
    if m["eur_cap"] is not None:
        quantum_h = m["billing_quantum_s"] / 3600
        hours = min(
            hours, math.floor(m["eur_cap"] / m["eur_per_hour"] / quantum_h) * quantum_h
        )
    return clock_start + hours * 3600 - m["margin_minutes"] * 60


class BulkRun:
    def __init__(
        self, plan, out, docker, host=None, clock=time.time, poll_s=2.0, log=None
    ):
        self.plan, self.out, self.docker = plan, Path(out), docker
        self.host = host if host is not None else host_info()
        self.clock, self.poll_s = clock, poll_s
        self.log = log or (lambda msg: print(msg, flush=True))
        self.ledger = Ledger(self.out / "ledger.jsonl")
        self.fams = {f.name: f for f in plan.families}
        self.books = {f.name: Book() for f in plan.families}
        self.inflight, self.done_q = {}, queue.Queue()
        self.not_launched, self.blocked, self.defer_reason = {}, {}, {}
        self.blocked_since, self.acceptance = {}, {}
        self.stop_reason, self.signals = None, 0
        self.done_keys, self.abandoned = set(), []
        self.clock_start = self.deadline = None

    # -- resume -------------------------------------------------------------
    def _replay(self):
        started, closed = {}, set()
        for row in self.ledger.rows:
            fam, event = row.get("family"), row.get("event")
            if fam not in self.books:
                continue
            book, key = self.books[fam], (fam, row.get("case"))
            if event == "STARTED":
                book.launches += 1
                started[key] = row
            elif event in ("FINISHED", "ABANDONED_ON_RESUME"):
                book.booked_cpu_s += row.get("allocated_cpu_s") or 0.0
                closed.add(key)
            elif event == "REFUSED":
                self.done_keys.add(key)
                self.blocked[fam] = "REFUSED_HASH_MISMATCH"
            elif event == "ACCEPTANCE":
                book.booked_cpu_s += row.get("allocated_cpu_s") or 0.0
                self.acceptance[fam] = row
                if not row.get("passed"):
                    self.blocked[fam] = "BLOCKED_ACCEPTANCE"
        self.done_keys |= set(started)
        self.abandoned = [started[k] for k in started if k not in closed]

    def _first_run_unix(self):
        starts = [
            r["started_unix"] for r in self.ledger.rows if r.get("event") == "RUN_START"
        ]
        return min(starts) if starts else self.clock()

    def _resolve_clock(self):
        start = self.plan.machine["clock_start"]
        if start == "boot":
            start = self.host.get("boot_unix") or self._first_run_unix()
        elif start == "first_run":
            start = self._first_run_unix()
        self.clock_start = float(start)
        self.deadline = machine_deadline(self.plan, self.clock_start)

    # -- main ---------------------------------------------------------------
    def execute(self, accept_plan_change=False, docker_info=None):
        plan, host = self.plan, self.host
        if host.get("nproc") and plan.machine["cpus"] > host["nproc"]:
            raise PlanError(
                [f"plan has {plan.machine['cpus']} CPUs; host has {host['nproc']}"]
            )
        mem = host.get("mem_total_bytes")
        if mem and plan.machine["memory_gib"] * GIB > mem:
            raise PlanError(
                [f"plan has {plan.machine['memory_gib']} GiB; host has {mem / GIB:.1f}"]
            )
        prior = [r for r in self.ledger.rows if r.get("event") == "RUN_START"]
        if (
            prior
            and prior[-1].get("plan_digest") != plan.digest
            and not accept_plan_change
        ):
            raise PlanError(
                ["this ledger was written under another plan (--accept-plan-change)"]
            )
        self._replay()
        # A crashed runner leaves its --rm containers running: kill them first.
        stale = self.docker.kill_stale(plan.plan_id)
        self.ledger.append(
            {
                "event": "RUN_START",
                "stale_containers_killed": len(stale),
                "plan_id": plan.plan_id,
                "plan_digest": plan.digest,
                "authority": plan.authority,
                "host_profile": plan.host_profile,
                "started_unix": self.clock(),
                "host": host,
                "docker": docker_info or {},
                "manifests": {f.name: f.manifest_sha256 for f in plan.families},
            }
        )
        self._resolve_clock()
        for row in self.abandoned:
            key = (row["family"], row["case"])
            reserved = row.get("reserved_cpu_s") or 0.0
            self.books[row["family"]].booked_cpu_s += reserved
            self.ledger.append(
                {
                    "event": "ABANDONED_ON_RESUME",
                    "family": key[0],
                    "case": key[1],
                    "reservation": row.get("reservation"),
                    "started_unix": row.get("started_unix"),
                    "allocated_cpu_s": reserved,
                    "outcome": "ABANDONED_ON_RESUME",
                }
            )
            self.log(f"{key[0]}/{key[1]}: ABANDONED_ON_RESUME (not retried)")
        self._run_acceptance()
        self.queue = [c for c in plan.cases() if c.key not in self.done_keys]
        self._loop()
        return self.write_summaries()

    def _spec(self, fam, name, work, meta, command, cpus, memory_bytes):
        return {
            "plan_id": self.plan.plan_id,
            "family": fam.name,
            "case": name,
            "name": container_name(self.plan.plan_id, fam.name, name),
            "image": fam.image,
            "command": command,
            "shell": fam.shell,
            "entrypoint": fam.entrypoint,
            "env": fam.env,
            "cpus": cpus,
            "memory_bytes": memory_bytes,
            "pids": fam.limits.pids,
            "work_dir": str(work.resolve()),
            "meta_dir": str(meta.resolve()),
            "memory_cap": (fam.native or {}).get("memory_cap", "rlimit_as"),
        }

    def _fresh_dirs(self, family, name):
        root = self.out / "cases" / family / name
        if root.exists():  # never started (no STARTED row), safe to clear
            shutil.rmtree(root)
        work, meta = root / "work", root / "meta"
        work.mkdir(parents=True)
        meta.mkdir()
        return work, meta

    def _run_acceptance(self):
        for fam in sorted(self.plan.families, key=lambda f: (f.priority, f.name)):
            if (
                not fam.acceptance
                or fam.name in self.acceptance
                or fam.name in self.blocked
            ):
                continue
            self._check_stops(self.clock())
            if self.stop_reason:
                return
            acc = fam.acceptance
            cpus = acc.get("cpus", fam.limits.cpus)
            memory = (
                int(acc["memory_gib"] * GIB)
                if "memory_gib" in acc
                else fam.limits.memory_bytes
            )
            work, meta = self._fresh_dirs(fam.name, "_acceptance")
            spec = self._spec(
                fam, "_acceptance", work, meta, acc["command"], cpus, memory
            )
            started = self.clock()
            try:
                result = self.docker.run(
                    spec, float(acc.get("timeout_s", 600)), threading.Event()
                )
            except Exception as exc:  # noqa: BLE001 - recorded, never raised
                result = {
                    "exit": None,
                    "stop_reason": "error",
                    "wall_s": 0.0,
                    "infra_error": repr(exc),
                }
            passed = result.get("exit") == 0 and result.get("stop_reason") == "exit"
            allocated = round(result.get("wall_s", 0.0) * cpus, 3)
            self.books[fam.name].booked_cpu_s += allocated
            row = self.ledger.append(
                {
                    "event": "ACCEPTANCE",
                    "family": fam.name,
                    "command": acc["command"],
                    "started_unix": started,
                    "passed": passed,
                    "allocated_cpu_s": allocated,
                    "image_ref": fam.image,
                    **{
                        k: result.get(k)
                        for k in ("exit", "stop_reason", "wall_s", "infra_error")
                    },
                }
            )
            self.acceptance[fam.name] = row
            if not passed:
                self.blocked[fam.name] = "BLOCKED_ACCEPTANCE"
                self.log(f"{fam.name}: acceptance failed; family BLOCKED_ACCEPTANCE")

    def request_stop(self, *_):
        self.signals += 1

    def _check_stops(self, now):
        if (self.out / "STOP_NOW").exists() or self.signals >= 2:
            if self.stop_reason != "STOP_NOW":
                self.stop_reason = "STOP_NOW"
                self.log("STOP_NOW: stopping running cases")
                for job in self.inflight.values():
                    job.cancel.set()
        elif not self.stop_reason and (
            (self.out / "STOP").exists() or self.signals == 1
        ):
            self.stop_reason = "STOP"
            self.log("STOP: draining; no new launches")
        if not self.stop_reason and now >= self.deadline:
            self.stop_reason = "MACHINE_CAP"
            self.log("machine node-hour / EUR deadline reached; draining")

    def _loop(self):
        while True:
            now = self.clock()
            self._check_stops(now)
            launched = 0 if self.stop_reason else self._fill(now)
            if not self.inflight and (self.stop_reason or launched == 0):
                break
            try:
                job, result = self.done_q.get(timeout=self.poll_s)
            except queue.Empty:
                continue
            self._finish(job, result)
            while True:
                try:
                    self._finish(*self.done_q.get_nowait())
                except queue.Empty:
                    break
        for case in self.queue:
            reason = self.stop_reason or self.defer_reason.get(
                case.key, "NOT_LAUNCHABLE"
            )
            self.not_launched[case.key] = self.blocked.get(case.family, reason)
        self.queue = []

    def _admit(self, case, now):
        fam, book = self.fams[case.family], self.books[case.family]
        if case.family in self.blocked:
            return ("drop", self.blocked[case.family])
        if book.launches >= fam.max_launches:
            return ("drop", "FAMILY_LAUNCH_CEILING")
        lim = fam.limits.wall_timeout_s
        est = _est_wall(case, fam)
        window = min(lim, max(self.plan.machine["min_case_window_s"], 2 * (est or 0)))
        fam_wall = book.free_cpu_s(fam) / fam.limits.cpus
        if fam_wall < lim:
            if book.reserved:
                return ("defer", "FAMILY_CPU_RESERVED")
            if fam_wall < window:
                return ("drop", "FAMILY_CPU_CEILING")
        machine_wall = self.deadline - now
        if machine_wall < window:
            return ("defer", "MACHINE_CAP")
        timeout = min(lim, fam_wall, machine_wall)
        if timeout >= lim:
            clip = "CASE"
        else:
            clip = "FAMILY" if fam_wall <= machine_wall else "MACHINE"
        return ("go", timeout, clip)

    def _fill(self, now):
        free_cpus = self.plan.usable_cpus - sum(
            self.fams[j.case.family].limits.cpus for j in self.inflight.values()
        )
        free_mem = self.plan.usable_memory_bytes - sum(
            self.fams[j.case.family].limits.memory_bytes for j in self.inflight.values()
        )
        launched = 0
        for case in list(self.queue):
            decision = self._admit(case, now)
            if decision[0] == "drop":
                self.queue.remove(case)
                self.not_launched[case.key] = decision[1]
                continue
            if decision[0] == "defer":
                self.defer_reason[case.key] = decision[1]
                continue
            lim = self.fams[case.family].limits
            if lim.cpus <= free_cpus + 1e-9 and lim.memory_bytes <= free_mem:
                self.queue.remove(case)
                self.blocked_since.pop(case.key, None)
                if self._launch(case, decision[1], decision[2]):
                    free_cpus -= lim.cpus
                    free_mem -= lim.memory_bytes
                    launched += 1
            else:
                since = self.blocked_since.setdefault(case.key, now)
                if now - since >= self.plan.machine["starvation_s"]:
                    break  # hold the machine for the long-waiting case
        return launched

    def _launch(self, case, timeout, clip):
        fam, book = self.fams[case.family], self.books[case.family]
        work, meta = self._fresh_dirs(case.family, case.name)
        for rel in case.files:
            target = work / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(case.source_dir / rel, target)
        bad = verify_case_files(work, case.files)
        if bad:
            self.ledger.append(
                {
                    "event": "REFUSED",
                    "family": case.family,
                    "case": case.name,
                    "reason": "HASH_MISMATCH",
                    "files": bad[:20],
                    "outcome": "REFUSED_HASH_MISMATCH",
                }
            )
            self.blocked[case.family] = "REFUSED_HASH_MISMATCH"
            self.not_launched[case.key] = "REFUSED_HASH_MISMATCH"
            self.log(
                f"{case.family}/{case.name}: files differ from manifest; family stopped"
            )
            return False
        reserved = round(timeout * fam.limits.cpus, 3)
        book.launches += 1
        book.reserved[case.key] = reserved
        job = Job(case, timeout, clip, reserved, self.clock(), work, meta)
        started = {
            "event": "STARTED",
            "family": case.family,
            "case": case.name,
            "reservation": case.reservation,
            "started_unix": job.started_unix,
            "timeout_s": round(timeout, 3),
            "timeout_clip": clip,
            "cpus": fam.limits.cpus,
            "memory_limit_bytes": fam.limits.memory_bytes,
            "pids_limit": fam.limits.pids,
            "reserved_cpu_s": reserved,
            "image_ref": fam.image,
            "image_pin": fam.manifest_image,
        }
        if getattr(self.docker, "name", None) == "native":
            # The image is the manifest's pin, never run: name what ran.
            started |= {
                "executor": "native",
                "environment": self.docker.environment,
                "pids_limit": None,
            }
        self.ledger.append(started)
        spec = self._spec(
            fam,
            case.name,
            work,
            meta,
            case.command,
            fam.limits.cpus,
            fam.limits.memory_bytes,
        )
        self.inflight[case.key] = job
        threading.Thread(target=self._work, args=(job, spec), daemon=True).start()
        return True

    def _work(self, job, spec):
        t0 = time.monotonic()
        try:
            result = self.docker.run(spec, job.timeout_s, job.cancel)
        except Exception as exc:  # noqa: BLE001 - booked as FAILED_INFRA
            result = {
                "exit": None,
                "stop_reason": "error",
                "wall_s": time.monotonic() - t0,
                "infra_error": repr(exc),
            }
        try:
            result["output_manifest_sha256"] = _output_manifest(job.work, job.meta)
        except OSError as exc:
            result["output_manifest_error"] = repr(exc)
        self.done_q.put((job, result))

    def _finish(self, job, result):
        case, fam = job.case, self.fams[job.case.family]
        book = self.books[case.family]
        self.inflight.pop(case.key, None)
        book.reserved.pop(case.key, None)
        wall = float(result.get("wall_s") or 0.0)
        allocated = round(wall * fam.limits.cpus, 3)
        book.booked_cpu_s += allocated
        outcome = classify(result, job.clip)
        peak = result.get("cgroup_memory_peak_bytes")
        native = {k: result[k] for k in NATIVE_FIELDS if k in result}
        row = self.ledger.append(
            {
                **native,
                "event": "FINISHED",
                "family": case.family,
                "case": case.name,
                "reservation": case.reservation,
                "started_unix": job.started_unix,
                "finished_unix": self.clock(),
                "wall_s": round(wall, 3),
                "cpus": fam.limits.cpus,
                "allocated_cpu_s": allocated,
                "timeout_s": round(job.timeout_s, 3),
                "timeout_clip": job.clip,
                "exit": result.get("exit"),
                "stop_reason": result.get("stop_reason"),
                "outcome": outcome,
                "cgroup_cpu_s": result.get("cgroup_cpu_s"),
                "cgroup_memory_peak_bytes": peak,
                "cgroup_version": result.get("cgroup_version"),
                "memory_limit_bytes": fam.limits.memory_bytes,
                "oom_suspected": outcome == "FAILED" and result.get("exit") == 137,
                "infra_error": result.get("infra_error"),
                "output_manifest_sha256": result.get("output_manifest_sha256"),
                "nproc": self.host.get("nproc"),
                "host_profile": self.plan.host_profile,
                "image_ref": fam.image,
                "image_pin": fam.manifest_image,
            }
        )
        self.log(
            f"{case.family}/{case.name}: {outcome} wall={row['wall_s']}s "
            f"cpu={_row_cpu_s(row)}s peak={_row_peak_bytes(row)}"
        )

    def write_summaries(self):
        return write_summaries(
            self.plan,
            self.ledger,
            self.out,
            self.not_launched,
            stop_reason=self.stop_reason,
            clock_start=self.clock_start,
            deadline=self.deadline,
            now=self.clock(),
        )


def classify(result, clip):
    if result.get("infra_error"):
        return "FAILED_INFRA"
    reason = result.get("stop_reason")
    if reason == "cancel":
        return "CENSORED_OPERATOR_STOP"
    if reason == "timeout":
        return {
            "CASE": "CENSORED_CASE_TIMEOUT",
            "FAMILY": "CENSORED_FAMILY_CAP",
            "MACHINE": "CENSORED_MACHINE_CAP",
        }[clip]
    if result.get("exit") == 0:
        return "COMPLETED"
    if result.get("exit") == 125 and result.get("executor") != "native":
        return "FAILED_INFRA"  # docker could not create the container
    return "FAILED"


def _row_cpu_s(row):
    """A case's measured CPU-s: the container cgroup's, else native rusage."""
    value = row.get("cgroup_cpu_s")
    return value if value is not None else row.get("rusage_cpu_s")


def _row_peak_bytes(row):
    """A case's measured memory peak: the cgroup's, else the larger of the
    native rusage peak (largest process) and the sampled group RSS peak."""
    value = row.get("cgroup_memory_peak_bytes")
    if value is not None:
        return value
    native = [
        row.get(k)
        for k in ("rusage_maxrss_bytes", "sampled_group_rss_peak_bytes")
        if row.get(k) is not None
    ]
    return max(native) if native else None


def _output_manifest(work, meta):
    files = {}
    for path in sorted(Path(work).rglob("*")):
        if path.is_file() and not path.is_symlink():
            rel = path.relative_to(work).as_posix()
            files[rel] = {"sha256": _sha_file(path), "bytes": path.stat().st_size}
    raw = json.dumps(files, sort_keys=True, indent=1).encode()
    (Path(meta) / "outputs.json").write_bytes(raw)
    return "sha256:" + hashlib.sha256(raw).hexdigest()


# ------------------------------------------------------------------ summary


def _mib(value):
    return None if value is None else round(value / MIB, 1)


def family_summary(plan, fam, rows, not_launched):
    mine = [r for r in rows if r.get("family") == fam.name]
    closed = [r for r in mine if r.get("event") in ("FINISHED", "ABANDONED_ON_RESUME")]
    started = {r["case"] for r in mine if r.get("event") == "STARTED"}
    refused = {r["case"] for r in mine if r.get("event") == "REFUSED"}
    acceptance = [r for r in mine if r.get("event") == "ACCEPTANCE"]
    counts = Counter(r["outcome"] for r in closed)
    pending = [c for c in fam.cases if c.name not in started | refused]
    reasons = Counter(not_launched.get(c.key, "NOT_LAUNCHED") for c in pending)
    allocated = sum(r.get("allocated_cpu_s") or 0.0 for r in closed + acceptance)
    walls = [r.get("wall_s") for r in closed if r.get("event") == "FINISHED"]
    peaks = [_row_peak_bytes(r) for r in closed]
    cpu = [_row_cpu_s(r) for r in closed if _row_cpu_s(r) is not None]
    executors = sorted(
        {r.get("executor", "docker") for r in closed if r.get("event") == "FINISHED"}
    )
    return {
        "schema": SUMMARY_SCHEMA,
        "plan_id": plan.plan_id,
        "family": fam.name,
        "image_ref": fam.image,
        "image_pin": fam.manifest_image,
        "manifest_sha256": fam.manifest_sha256,
        "cases_in_manifest": len(fam.cases),
        "launches": len(started),
        "outcomes": {k: counts[k] for k in OUTCOMES if counts[k]},
        "refused": len(refused),
        "not_launched": dict(sorted(reasons.items())),
        "acceptance": (
            None
            if not acceptance
            else {
                "passed": acceptance[-1].get("passed"),
                "exit": acceptance[-1].get("exit"),
            }
        ),
        "ceilings": {"launches": fam.max_launches, "cpu_hours": fam.cpu_hours},
        "allocated_cpu_hours": round(allocated / 3600, 4),
        "cgroup_cpu_hours": round(
            sum(r.get("cgroup_cpu_s") or 0.0 for r in closed) / 3600, 4
        ),
        # The cgroup's CPU for Docker rows, os.wait4 rusage for native rows.
        "measured_cpu_hours": round(sum(cpu) / 3600, 4),
        "executors": executors,
        "wall_s": {
            "total": round(sum(w for w in walls if w is not None), 1),
            "p50": _percentile(walls, 50),
            "p95": _percentile(walls, 95),
            "max": _percentile(walls, 100),
        },
        "memory_peak_mib": {
            "p50": _mib(_percentile(peaks, 50)),
            "p95": _mib(_percentile(peaks, 95)),
            "max": _mib(_percentile(peaks, 100)),
            "cases_with_peak": sum(p is not None for p in peaks),
            "limit": _mib(fam.limits.memory_bytes),
        },
        "maturity": "DEVELOPMENT cost measurement; no qualification or adequacy claim",
    }


def write_summaries(
    plan,
    ledger,
    out,
    not_launched,
    *,
    stop_reason=None,
    clock_start=None,
    deadline=None,
    now=None,
):
    out = Path(out) / "summary"
    out.mkdir(parents=True, exist_ok=True)
    families = []
    for fam in plan.families:
        summary = family_summary(plan, fam, ledger.rows, not_launched)
        (out / f"{fam.name}.json").write_text(json.dumps(summary, indent=1) + "\n")
        families.append(summary)
    now = now or time.time()
    elapsed_h = None if clock_start is None else max(0.0, (now - clock_start) / 3600)
    m = plan.machine
    eur = None
    if elapsed_h is not None and m["eur_per_hour"] is not None:
        quantum_h = m["billing_quantum_s"] / 3600
        eur = round(math.ceil(elapsed_h / quantum_h) * quantum_h * m["eur_per_hour"], 2)
    total = {
        "schema": SUMMARY_SCHEMA,
        "plan_id": plan.plan_id,
        "plan_digest": plan.digest,
        "authority": plan.authority,
        "host_profile": plan.host_profile,
        "machine": m,
        "stop_reason": stop_reason,
        "clock_start_unix": clock_start,
        "deadline_unix": deadline,
        "elapsed_node_hours": None if elapsed_h is None else round(elapsed_h, 4),
        "eur_estimate_billed_quanta": eur,
        "ledger_corrupt_lines": ledger.corrupt_lines,
        "launches": sum(f["launches"] for f in families),
        "allocated_cpu_hours": round(
            sum(f["allocated_cpu_hours"] for f in families), 4
        ),
        "families": {
            f["family"]: {k: f[k] for k in ("launches", "outcomes", "not_launched")}
            for f in families
        },
    }
    (out / "all.json").write_text(json.dumps(total, indent=1) + "\n")
    return total


# ------------------------------------------------------------------ dry run


def simulate(plan, cases, available_s):
    """Estimate the schedule: the runner's first-fit packing with estimated
    walls (``estimate_wall_s``, else ``estimate_cpu_s / cpus``, else the wall
    timeout as an upper bound) and estimated family CPU against ceilings."""
    free_cpus, free_mem = plan.usable_cpus, plan.usable_memory_bytes
    used = {
        f.name: {"launches": 0, "cpu_s": 0.0, "unestimated": 0} for f in plan.families
    }
    dropped, running, pending, t = Counter(), [], list(cases), 0.0
    seq = 0
    while pending or running:
        for case in list(pending):
            fam = plan.family(case.family)
            use = used[case.family]
            est = _est_wall(case, fam)
            wall = est if est is not None else fam.limits.wall_timeout_s
            if use["launches"] >= fam.max_launches:
                pending.remove(case)
                dropped[(case.family, "FAMILY_LAUNCH_CEILING")] += 1
            elif use["cpu_s"] + wall * fam.limits.cpus > fam.cpu_hours * 3600:
                pending.remove(case)
                dropped[(case.family, "FAMILY_CPU_CEILING")] += 1
            elif (
                fam.limits.cpus <= free_cpus + 1e-9
                and fam.limits.memory_bytes <= free_mem
            ):
                pending.remove(case)
                free_cpus -= fam.limits.cpus
                free_mem -= fam.limits.memory_bytes
                use["launches"] += 1
                use["cpu_s"] += wall * fam.limits.cpus
                use["unestimated"] += est is None
                seq += 1
                heapq.heappush(running, (t + wall, seq, case))
        if not running:
            break
        t, _, done = heapq.heappop(running)
        fam = plan.family(done.family)
        free_cpus += fam.limits.cpus
        free_mem += fam.limits.memory_bytes
    return {
        "makespan_s": round(t, 1),
        "makespan_node_hours": round(t / 3600, 3),
        "available_node_hours": round(available_s / 3600, 3),
        "fits_machine_cap": t <= available_s,
        "families": {
            name: {
                "launches": u["launches"],
                "allocated_cpu_hours": round(u["cpu_s"] / 3600, 3),
                "cases_without_estimate_at_timeout": u["unestimated"],
                "dropped": {r: n for (f, r), n in dropped.items() if f == name},
            }
            for name, u in used.items()
        },
    }


def dry_run(plan, out, docker, host, check_images=True, now=None):
    native = getattr(docker, "name", None) == "native"
    images = preflight(plan, docker, check_images=check_images and not native)
    environment = check_native(plan, docker) if native and check_images else None
    ledger = Ledger(Path(out) / "ledger.jsonl")
    done = {
        (r.get("family"), r.get("case"))
        for r in ledger.rows
        if r.get("event") in ("STARTED", "REFUSED")
    }
    cases = [c for c in plan.cases() if c.key not in done]
    now = now or time.time()
    start = plan.machine["clock_start"]
    if start == "boot":
        start = host.get("boot_unix") or now
    elif start == "first_run":
        starts = [
            r["started_unix"] for r in ledger.rows if r.get("event") == "RUN_START"
        ]
        start = min(starts) if starts else now
    available = max(0.0, machine_deadline(plan, float(start)) - now)
    warnings = []
    for case in cases:
        fam = plan.family(case.family)
        if (
            case.est_mem_mib is not None
            and case.est_mem_mib * MIB > fam.limits.memory_bytes
        ):
            warnings.append(
                f"{case.family}/{case.name}: estimate_mem_mib exceeds the memory limit"
            )
        est = _est_wall(case, fam)
        if est is not None and est > fam.limits.wall_timeout_s:
            warnings.append(
                f"{case.family}/{case.name}: estimated wall exceeds the timeout"
            )
    return {
        "plan_id": plan.plan_id,
        "plan_digest": plan.digest,
        "usable_cpus": plan.usable_cpus,
        "usable_memory_gib": round(plan.usable_memory_bytes / GIB, 2),
        "executor": "native" if native else "docker",
        "images_checked": check_images and not native,
        "image_identities": images,
        "environment_checks": environment,
        "families": {
            f.name: {
                "cases": len(f.cases),
                "pending": sum(c.family == f.name for c in cases),
                "image": f.image,
                "image_pin": f.manifest_image,
                "manifest_sha256": f.manifest_sha256,
            }
            for f in plan.families
        },
        "estimate": simulate(plan, cases, available),
        "warnings": warnings,
    }


# ---------------------------------------------------------------------- cli


def main(argv=None, docker=None):
    parser = argparse.ArgumentParser(
        prog="bulk_run", description=__doc__.split("\n\n")[0]
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument(
        "--summarize", action="store_true", help="rewrite summaries from the ledger"
    )
    parser.add_argument(
        "--skip-image-check",
        action="store_true",
        help="dry-run only: planning off-host (native: skips the environment check)",
    )
    parser.add_argument(
        "--executor",
        choices=("docker", "native"),
        default="docker",
        help="native: run each case directly on this host (no Docker)",
    )
    parser.add_argument("--accept-plan-change", action="store_true")
    parser.add_argument("--poll-s", type=float, default=2.0)
    args = parser.parse_args(argv)
    if args.skip_image_check and not args.dry_run:
        parser.error("--skip-image-check is for --dry-run only")
    if docker is None:
        docker = (
            NativeExecutor(out=args.out) if args.executor == "native" else DockerCli()
        )
    native = getattr(docker, "name", None) == "native"
    try:
        plan = load_plan(args.plan)
        if args.summarize:
            total = write_summaries(
                plan, Ledger(args.out / "ledger.jsonl"), args.out, {}
            )
            print(json.dumps(total, indent=1))
            return 0
        if args.dry_run:
            report = dry_run(
                plan, args.out, docker, host_info(), not args.skip_image_check
            )
            print(json.dumps(report, indent=1))
            return 0
        preflight(plan, docker, check_images=not native)
        if native:
            check_native(plan, docker)
        args.out.mkdir(parents=True, exist_ok=True)
        with open(args.out / ".lock", "w") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise PlanError([f"another bulk_run holds {args.out}"]) from None
            runner = BulkRun(plan, args.out, docker, poll_s=args.poll_s)
            signal.signal(signal.SIGTERM, runner.request_stop)
            signal.signal(signal.SIGINT, runner.request_stop)
            total = runner.execute(args.accept_plan_change, docker.info())
        print(json.dumps(total, indent=1))
        return 0
    except PlanError as exc:
        for problem in exc.problems:
            print(f"refused: {problem}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
