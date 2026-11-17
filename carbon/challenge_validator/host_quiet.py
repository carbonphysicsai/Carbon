"""Whether the grading host was provably QUIET while a timed build ran (owner, 5 Nov 21:3x: "All our rebuild should be
consistently timed. It's an issue if some timeout because our machine is busy").

Door ruling (Validator-2, 5 Nov 21:28): a WORKER_WALL counts as the model's result ONLY when the host was provably quiet
for that build:

1. the build ran while ITS receiver held the host grading lock for the whole build;
2. no OTHER GPU compute process was on the device during it (sampled during the run and at the stop);
3. no other Carbon build container was running (sampled during the run, and none left at the stop).

Any of the three failing, or any sample that cannot be read, is NOT quiet (invariant 7: our load is never the miner's
loss), so the failure is Carbon's: retried as infrastructure, never counted as the model's result.

Two users:

- the counted grade (`auto_grade.AutoGrader._wall_counted`): its existing guard (1 + 3) gains the GPU check (2);
- the crown rebuilds (`lean_recipe_retention.rebuild_at_seed`: the averaging and re-measure rebuilds): a derived rebuild
  that fails while the host is not quiet is marked HOST-CONTENDED, so the next try builds a fresh generation of it (the
  same seed) instead of re-reading the failed task, and the rebuild raises `crown_average.RebuildInfra`
  (`REBUILD_HOST_CONTENDED`).

The probe is active only inside `AutoGrader.run_once` (`activate`), where the lock state is known. Elsewhere (operator
tools) `start` returns None and a rebuild behaves exactly as before.

Evidence (host-private, counts and booleans only; never a miner surface): ``<auto-grade>/host-contended/<task>.json``
(create-only) and ``crown-wall-stops.jsonl`` beside it.
"""

from __future__ import annotations

import contextvars
import json
import os
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

#: The carrier names every worker container it starts ``carbon-d4-<launch digest>`` (`research_carrier`).
WORKER_PREFIX = "carbon-d4-"
#: The reason a crown rebuild ends with when every try met a busy host (`crown_average`).
REBUILD_HOST_CONTENDED = "rebuild_host_contended"
MARKS_DIR = "host-contended"
LOG_NAME = "crown-wall-stops.jsonl"

_ACTIVE = contextvars.ContextVar("carbon_host_quiet_active", default=None)


def _run(argv, timeout=10):
    return subprocess.run(argv, capture_output=True, timeout=timeout, check=False)


def worker_containers():
    """The ids of the Carbon worker containers running on this host now, or None when the daemon cannot say."""
    try:
        done = _run(
            [
                "docker",
                "ps",
                "--filter",
                "name=" + WORKER_PREFIX,
                "--format",
                "{{.ID}} {{.Names}}",
            ]
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    ids = []
    for line in done.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].startswith(WORKER_PREFIX):
            ids.append(parts[0])
    return ids


def _container_pids(ids):
    pids = set()
    for cid in ids:
        try:
            done = _run(["docker", "top", cid, "-eo", "pid"])
        except (OSError, subprocess.SubprocessError):
            return None
        if done.returncode != 0:
            return None
        for token in done.stdout.decode("utf-8", "replace").split()[1:]:
            if token.isascii() and token.isdigit():
                pids.add(int(token))
    return pids


def foreign_gpu_compute():
    """How many GPU compute processes run on this host now that do NOT belong to a Carbon worker container, or None
    when it cannot be read. A host with no NVIDIA driver at all (no ``nvidia-smi``) has no GPU to contend: 0.
    """
    try:
        done = _run(
            ["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader,nounits"]
        )
    except FileNotFoundError:
        return 0
    except (OSError, subprocess.SubprocessError):
        return None
    text = done.stdout.decode("utf-8", "replace")
    if "No devices were found" in text:
        return 0
    if done.returncode != 0:
        return None
    gpu = set()
    for token in text.split():
        if not (token.isascii() and token.isdigit()):
            return None  # e.g. '[N/A]' (no host pid namespace): unknown, so not quiet
        gpu.add(int(token))
    if not gpu:
        return 0
    ids = worker_containers()
    if ids is None:
        return None
    own = _container_pids(ids)
    if own is None:
        return None
    return len(gpu - own)


#: The box's GPU compute listing: ``nvidia-smi`` when the box has one, else a marker (no driver: no GPU to contend).
_BOX_GPU_QUERY = (
    "if command -v nvidia-smi >/dev/null 2>&1; then "
    "nvidia-smi --query-compute-apps=pid --format=csv,noheader,nounits; "
    "else echo carbon-no-nvidia-smi; fi"
)


def _box_docker(lane, argv):
    from carbon.reconstruction import remote_gpu_build, remote_lane

    if isinstance(lane, remote_gpu_build.OpBinding):
        # a GPU build box: through its wrapper, whose ssh carries the box's pinned host key
        try:
            prefix, environment = remote_gpu_build.box_docker(lane)
        except remote_lane.RemoteLaneDown as error:
            raise OSError("remote_gpu_build_box_wrapper") from error
    else:
        prefix, environment = ["docker"], remote_lane.docker_environment(
            lane.docker_host
        )
    return subprocess.run(
        [*prefix, *argv],
        capture_output=True,
        timeout=10,
        check=False,
        env=environment,
        cwd=os.sep,
    )


def _box_output(lane, script):
    from carbon.reconstruction import remote_gpu_build, remote_lane

    if isinstance(lane, remote_gpu_build.OpBinding):
        return remote_gpu_build.box_output(lane, script)
    return remote_lane.box_output(lane, script)


def box_worker_containers(lane):
    """The ids of the Carbon worker containers running on REMOTE ``lane``'s box now (every lane of that box shares its
    daemon), or None when the daemon cannot say (a link fault counts as unknown, so not quiet).
    """
    try:
        done = _box_docker(
            lane,
            [
                "ps",
                "--filter",
                "name=" + WORKER_PREFIX,
                "--format",
                "{{.ID}} {{.Names}}",
            ],
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    ids = []
    for line in done.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].startswith(WORKER_PREFIX):
            ids.append(parts[0])
    return ids


def box_foreign_gpu(lane):
    """`foreign_gpu_compute` on REMOTE ``lane``'s box (read there over ssh), or None when it cannot be read."""
    raw = _box_output(lane, _BOX_GPU_QUERY)
    if raw is None:
        return None
    text = raw.decode("utf-8", "replace")
    if text.strip() == "carbon-no-nvidia-smi" or "No devices were found" in text:
        return 0
    gpu = set()
    for token in text.split():
        if not (token.isascii() and token.isdigit()):
            return None
        gpu.add(int(token))
    if not gpu:
        return 0
    ids = box_worker_containers(lane)
    if ids is None:
        return None
    own = set()
    for cid in ids:
        try:
            done = _box_docker(lane, ["top", cid, "-eo", "pid"])
        except (OSError, ValueError, subprocess.SubprocessError):
            return None
        if done.returncode != 0:
            return None
        for token in done.stdout.decode("utf-8", "replace").split()[1:]:
            if token.isascii() and token.isdigit():
                own.add(int(token))
    return len(gpu - own)


def count_lane_containers(cpuset, lane=None):
    """How many Carbon worker containers run now with a core of ``cpuset`` (one lane's cores), or None when the daemon
    cannot say: on this host, or, for a REMOTE ``lane``, on its box (read through its daemon). A container with no cpuset
    of its own may run on any core: it counts.
    """
    from carbon.reconstruction.host_execution import parse_cpuset

    def run(argv):
        try:
            if lane is not None and getattr(lane, "docker_host", None) is not None:
                done = _box_docker(lane, argv[1:])
            else:
                done = subprocess.run(
                    argv, capture_output=True, timeout=10, check=False
                )
        except (OSError, ValueError, subprocess.SubprocessError):
            return None
        return None if done.returncode != 0 else done.stdout.decode("utf-8", "replace")

    listed = run(
        ["docker", "ps", "--filter", "name=" + WORKER_PREFIX, "--format", "{{.Names}}"]
    )
    if listed is None:
        return None
    names = [name for name in listed.split() if name.startswith(WORKER_PREFIX)]
    if not names:
        return 0
    found = run(["docker", "inspect", "--format", "{{.HostConfig.CpusetCpus}}", *names])
    if found is None:
        return None  # one ended between the two reads (or the daemon failed): not readable, never quiet
    try:
        mine = set(parse_cpuset(cpuset))
    except Exception:  # noqa: BLE001 - unreadable: never quiet
        return None
    count = 0
    for line in found.splitlines():
        value = line.strip()
        try:
            cores = set(parse_cpuset(value)) if value else None
        except Exception:  # noqa: BLE001 - unreadable: never quiet
            return None
        if cores is None or cores & mine:
            count += 1
    return count


def box_counters(lane):
    """``(containers, gpu)`` sampling callables for REMOTE ``lane``'s box (a `Probe`'s or a grade sampler's), read on the
    box itself through its daemon and ssh. Every answered sample is also a heartbeat of the link (CV-Motor L12624 (c)):
    a sample the link could not deliver is None, which is never quiet."""

    def containers():
        ids = box_worker_containers(lane)
        return None if ids is None else len(ids)

    return containers, (lambda: box_foreign_gpu(lane))


def uncontended(
    *, lock_held, samples, stop, gpu_samples, gpu_stop, require_samples=False
):
    """The ruling's three conditions on one run's samples. ``samples`` / ``stop``: Carbon worker containers during the
    run (at most this build's own: <= 1) and at the stop (this build's own already removed: 0); ``gpu_samples`` /
    ``gpu_stop``: foreign GPU compute processes (0 every time). An unreadable sample (None) is not quiet.

    ``require_samples``: the run must have been OBSERVED, at least one in-run sample of each kind. A build that ends
    inside the first sampling interval has only its stop sample, which is enough for a failure that happened at the stop
    (`Probe`: the default) but says nothing about a wall stop, which takes the whole wall: a wall stop "observed" with
    no in-run sample is a replay of an earlier operation (a retry that re-read the kept ledger row, no new run), whose
    quiet verdict would be vacuous (testnet #2, 13 Nov: counted with 0 samples). The wall-stop count passes True.
    """
    known = [s for s in samples if s is not None]
    gpu_known = [g for g in gpu_samples if g is not None]
    if require_samples and not (samples and gpu_samples):
        return False
    return bool(
        lock_held
        and stop == 0
        and len(known) == len(samples)
        and (not known or max(known) <= 1)
        and gpu_stop == 0
        and len(gpu_known) == len(gpu_samples)
        and all(g == 0 for g in gpu_known)
    )


@dataclass(frozen=True)
class QuietVerdict:
    lock_held: bool
    samples: int
    unknown_samples: int
    max_worker_containers: int | None
    stop_worker_containers: int | None
    gpu_unknown_samples: int
    max_foreign_gpu: int | None
    stop_foreign_gpu: int | None
    quiet: bool


class Probe:
    """Samples (worker containers, foreign GPU processes) every ``seconds`` on its own thread from `start` until
    `verdict`, which takes the stop sample. A build that ends within the first interval has only its stop sample.
    """

    def __init__(self, *, lock_held, containers, gpu, seconds, require_samples=False):
        self.lock_held = lock_held is True
        self.containers, self.gpu, self.seconds = containers, gpu, seconds
        #: a remote box's probe needs in-run samples (its heartbeats, `box_counters`), as a wall-stop count does
        self.require_samples = require_samples is True
        self.samples, self.gpu_samples = [], []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._done = None

    def _loop(self):
        while not self._stop.wait(self.seconds):
            self.samples.append(self.containers())
            self.gpu_samples.append(self.gpu())

    def start(self):
        self._thread.start()
        return self

    def verdict(self):
        if self._done is None:
            self._stop.set()
            self._thread.join(self.seconds + 15)
            stop, gpu_stop = self.containers(), self.gpu()
            known = [s for s in self.samples if s is not None]
            gpu_known = [g for g in self.gpu_samples if g is not None]
            self._done = QuietVerdict(
                lock_held=self.lock_held,
                samples=len(self.samples),
                unknown_samples=len(self.samples) - len(known),
                max_worker_containers=max(known) if known else None,
                stop_worker_containers=stop,
                gpu_unknown_samples=len(self.gpu_samples) - len(gpu_known),
                max_foreign_gpu=max(gpu_known) if gpu_known else None,
                stop_foreign_gpu=gpu_stop,
                quiet=uncontended(
                    lock_held=self.lock_held,
                    samples=self.samples,
                    stop=stop,
                    gpu_samples=self.gpu_samples,
                    gpu_stop=gpu_stop,
                    require_samples=self.require_samples,
                ),
            )
        return self._done


def activate(*, lock_held, containers, gpu, seconds):
    """Make rebuilds started in this context probe the host (`AutoGrader.run_once`). Returns the reset token."""
    return _ACTIVE.set(
        {
            "lock_held": lock_held,
            "containers": containers,
            "gpu": gpu,
            "seconds": seconds,
        }
    )


def deactivate(token):
    _ACTIVE.reset(token)


def start():
    """A running `Probe` for a rebuild about to start, or None when no grading loop is active here (then the rebuild
    behaves exactly as before: nothing is marked)."""
    params = _ACTIVE.get()
    if params is None:
        return None
    from carbon.reconstruction import remote_lane

    lane = remote_lane.current()
    if lane is not None:
        # a REMOTE lane's containers run on another machine: its quiet is sampled ON that box, through its daemon and
        # ssh, every sample a heartbeat of the link (CV-Motor L12624 (b) + (c)); in-run samples are required
        containers, gpu = box_counters(lane)
        return Probe(
            lock_held=params["lock_held"],
            containers=containers,
            gpu=gpu,
            seconds=params["seconds"],
            require_samples=True,
        ).start()
    return Probe(**params).start()


class _NotQuiet:
    """A probe whose verdict is never quiet (kept for callers that know a host cannot be observed)."""

    def verdict(self):
        return QuietVerdict(
            lock_held=False,
            samples=0,
            unknown_samples=0,
            max_worker_containers=None,
            stop_worker_containers=None,
            gpu_unknown_samples=0,
            max_foreign_gpu=None,
            stop_foreign_gpu=None,
            quiet=False,
        )


def finish(probe):
    return None if probe is None else probe.verdict()


def is_contended(marks, task_id):
    return (Path(marks) / f"{task_id}.json").is_file()


def mark_contended(marks, task_id, verdict, *, reason, path):
    """Mark ``task_id`` HOST-CONTENDED (create-only) and log the stop (counts only). Best effort on the log; the mark
    itself must be written, else the next try would re-read the failed task."""
    marks = Path(marks)
    marks.mkdir(mode=0o700, parents=True, exist_ok=True)
    body = {
        "task": task_id,
        "path": path,
        "reason": reason if type(reason) is str else type(reason).__name__,
        "at_ns": time.time_ns(),
        **asdict(verdict),
    }
    raw = (json.dumps(body, sort_keys=True) + "\n").encode()
    try:
        fd = os.open(
            marks / f"{task_id}.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
    try:
        with open(marks.parent / LOG_NAME, "ab") as log:
            log.write(raw)
    except OSError:
        pass
    return body
