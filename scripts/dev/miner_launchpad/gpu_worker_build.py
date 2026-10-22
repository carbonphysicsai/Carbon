"""Setup's "Build the GPU worker" action, on the Control Center page only (S15a).

The owner, 2026-10-21: "whatever makes it easiest for miners". A GPU route
(this machine's GPU, or the miner's own remote machine or container) needs
the pinned GPU worker. When setup finds no manifest for it, the Compute step
offers one button instead of a command to copy. The button runs the
installer's own GPU build on the miner's own machine:
`scripts/dev/accelerator_worker_image.sh <checkout>/.carbon-artifacts/
accelerator-worker-image.json`, the call `install_miner.sh --gpu` makes at
its step 4. No second recipe exists. The script writes the manifest where
`installed.found` looks for it, so the next compute check reads it.

**One door.** Only the page starts it: the controller's
`POST /api/v1/page/gpu_worker_build`, behind the page's loopback session
token. It is not a setup operation (`setup_operations.SETUP_OPERATIONS`), so
no MCP tool and no status call names it, and `EnvironmentSetup` has no
method of that name for `setup_operations.perform` to reach. Only the
controller's `Server` holds this object; `carbon-mcp`, the page's research
tool door and Graphite hold none.

**Consent names what runs.** The request carries the exact command this
action shows (`{"route": ..., "consent": {"build": {"command": ...}}}`). A
page drawn from another checkout or another command builds nothing.

**One at a time, readable while it runs.** It runs as a background process
with its output in an owner-only log in setup's directory. That process holds
an exclusive lock on `gpu-build.lock`, so a second build is refused even
after a Control Center restart. `status` reports the build's state, how long
it has run, Docker's last `[n/m]` step and its last output line.

**Refusals name the exact failure**, before anything runs: Docker not
installed or not reachable, no NVIDIA driver (`nvidia-smi`, for this
machine's GPU route, as `install_miner.sh --gpu` checks it; the script builds
images only, so a remote route needs no GPU here), and too little disk where
Docker keeps its images (the installer's `GPU_GIB`). A build that stops says
whether Docker ran out of disk or could not be reached, or the exit status.

Nothing is rented, started remotely or billed (OWNER-MINER-COMPUTE-LINK-ONLY-
01): the build runs on the miner's own machine with their own Docker.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import threading
import time
from pathlib import Path

SCHEMA = "carbon.launchpad.gpu-worker-build.v1"
#: The installer's GPU build, exactly as `install_miner.sh` step 4 calls it:
#: the script, and the manifest it writes under the checkout's artifacts.
SCRIPT = "scripts/dev/accelerator_worker_image.sh"
#: The GiB the installer reserves for the GPU worker (`GPU_GIB` in
#: `scripts/install_miner.sh`; a test holds the two equal).
GPU_BUILD_GIB = 12
#: The routes that need the GPU worker, and the one that needs this
#: machine's NVIDIA driver to build it (the installer's `--gpu` check).
LOCAL_GPU = "this-machine-gpu"
REMOTE = "remote-machine"
ROUTES = (LOCAL_GPU, REMOTE)
DRIVER_ROUTES = (LOCAL_GPU,)
#: Its files, in setup's owner-only directory.
RECORD = "gpu-build.json"
LOG = "gpu-build.log"
LOCK = "gpu-build.lock"
#: How much of the log's end `status` reads.
TAIL_BYTES = 64 * 1024
_STEP = re.compile(rb"\[\s*(\d{1,4})\s*/\s*(\d{1,4})\]")

#: What to do after each refusal or ended build.
NEXT = {
    "docker_not_installed": (
        "install Docker Engine on this machine, then build the GPU worker again"
    ),
    "docker_unreachable": (
        "start Docker, or add yourself to the docker group and log in again, "
        "then build the GPU worker again"
    ),
    "nvidia_driver_not_found": (
        "install the NVIDIA driver so nvidia-smi is found on this machine, "
        "then build the GPU worker again. A remote GPU route needs no GPU here"
    ),
    "gpu_build_disk_full": (
        "free space where Docker keeps its images (see what Docker keeps "
        "with: docker system df), then build the GPU worker again"
    ),
    "gpu_build_failed": (
        "read the end of the build's output below, fix what it names, then "
        "build the GPU worker again"
    ),
    "gpu_build_wrote_no_manifest": (
        "the build ended without writing its manifest; build the GPU worker " "again"
    ),
    "gpu_build_interrupted": (
        "the build stopped before it finished (the Control Center restarted?); "
        "build the GPU worker again"
    ),
    "gpu_build_running": "wait for the running build to finish",
    "gpu_worker_already_built": ("setup found your GPU worker: check compute with it"),
    "gpu_build_is_for_a_gpu_route": (
        "choose this machine's GPU or your own remote machine first"
    ),
    "consent_must_name_the_command": (
        "reload the page and agree to the command it shows"
    ),
}


class HostProbe:
    """What the build needs on this machine, read without changing it."""

    def which(self, name: str) -> str | None:
        return shutil.which(name)

    def _docker(self, *arguments) -> subprocess.CompletedProcess | None:
        try:
            return subprocess.run(
                ["docker", *arguments],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None

    def docker_reachable(self) -> bool:
        answer = self._docker("info", "--format", "{{.ServerVersion}}")
        return answer is not None and answer.returncode == 0

    def docker_root(self) -> str | None:
        answer = self._docker("info", "--format", "{{.DockerRootDir}}")
        if answer is None or answer.returncode != 0:
            return None
        root = answer.stdout.decode("utf-8", "replace").strip()
        return root if root and Path(root).is_dir() else None

    def free_gib(self, path: str) -> int | None:
        try:
            return shutil.disk_usage(path).free // (1 << 30)
        except OSError:
            return None


def spawn(command, *, cwd, log_fd, lock_fd):
    """Start the build: its output to the log, the lock held by it."""
    return subprocess.Popen(
        command,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=log_fd,
        stderr=subprocess.STDOUT,
        pass_fds=(lock_fd,),
        # Its own session: stopping the Control Center does not stop a build
        # half way; the lock it holds keeps a second one from starting.
        start_new_session=True,
    )


def _text(raw: bytes, limit: int = 200) -> str:
    """One output line as plain printable text, never markup."""
    text = "".join(
        c if " " <= c <= "~" else " " for c in raw.decode("utf-8", "replace")
    )
    return " ".join(text.split())[:limit]


class GpuWorkerBuild:
    """The page's build action over setup's directory `state_dir`."""

    def __init__(self, state_dir, *, repo=None, probe=None, runner=None, clock=None):
        from scripts.dev.miner_launchpad.environment_setup import REPO

        self.state_dir = Path(state_dir)
        self.root = self.state_dir / "environment"
        self.repo = Path(repo) if repo is not None else REPO
        self.probe = probe or HostProbe()
        self.runner = runner or spawn
        self.clock = clock or time.time
        self.guard = threading.Lock()
        self.thread = None

    # -- what runs

    @property
    def manifest(self) -> Path:
        from scripts.dev.miner_launchpad.installed import GPU_DEFAULT

        return self.repo / GPU_DEFAULT

    def command(self) -> list[str]:
        """The installer's GPU build call, with this checkout's paths."""
        return [str(self.repo / SCRIPT), str(self.manifest)]

    def command_text(self) -> str:
        return shlex.join(self.command())

    def _found(self) -> str | None:
        from scripts.dev.miner_launchpad import installed

        return installed.found(self.state_dir, self.repo)["gpu_image_manifest"]["path"]

    # -- records

    def _record(self) -> dict | None:
        path = self.root / RECORD
        try:
            if path.is_symlink() or path.stat().st_size > 8192:
                return None
            record = json.loads(path.read_bytes())
        except (OSError, ValueError):
            return None
        return (
            record if type(record) is dict and record.get("schema") == SCHEMA else None
        )

    def _save(self, record: dict) -> None:
        from scripts.dev.miner_launchpad.environment_setup import write_private

        write_private(self.root / RECORD, json.dumps(record, sort_keys=True).encode())

    def _lock(self):
        """The build lock's descriptor, held: or None when a build holds it."""
        import fcntl

        from scripts.dev.miner_launchpad.environment_setup import _private_dir

        _private_dir(self.root)
        fd = os.open(
            self.root / LOCK,
            os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            return None
        except BaseException:
            os.close(fd)
            raise
        return fd

    def running(self) -> bool:
        if self.thread is not None and self.thread.is_alive():
            return True
        if not (self.root / LOCK).exists():
            return False
        fd = self._lock()
        if fd is None:
            return True
        os.close(fd)
        return False

    def _tail(self) -> bytes:
        path = self.root / LOG
        try:
            if path.is_symlink():
                return b""
            with open(path, "rb") as handle:
                handle.seek(0, os.SEEK_END)
                handle.seek(max(0, handle.tell() - TAIL_BYTES))
                return handle.read()
        except OSError:
            return b""

    # -- the action

    def _refuse(self, field, code, next_step=None):
        from scripts.dev.miner_launchpad.environment_setup import SetupRefused

        return SetupRefused(field, code, next_step=next_step or NEXT[code])

    def preflight(self, route: str) -> None:
        """Refuse, naming the exact failure, before anything runs."""
        if self.probe.which("docker") is None:
            raise self._refuse("docker", "docker_not_installed")
        if not self.probe.docker_reachable():
            raise self._refuse("docker", "docker_unreachable")
        if route in DRIVER_ROUTES and self.probe.which("nvidia-smi") is None:
            raise self._refuse("gpu", "nvidia_driver_not_found")
        root = self.probe.docker_root()
        free = None if root is None else self.probe.free_gib(root)
        if free is not None and free < GPU_BUILD_GIB:
            raise self._refuse(
                "disk",
                "gpu_build_disk_full",
                next_step=(
                    f"the GPU worker needs {GPU_BUILD_GIB} GiB free where Docker "
                    f"keeps its images ({root}), and {free} GiB are free there: "
                    + NEXT["gpu_build_disk_full"]
                ),
            )

    def start(self, value) -> dict:
        """Start the build on consent to its exact command; its status."""
        from scripts.dev.miner_launchpad.environment_setup import SetupRefused

        if type(value) is not dict or set(value) != {"route", "consent"}:
            raise SetupRefused(
                "consent",
                "closed_setup_request_required",
                next_step="send route and consent only",
            )
        if value["route"] not in ROUTES:
            raise self._refuse("route", "gpu_build_is_for_a_gpu_route")
        if value["consent"] != {"build": {"command": self.command_text()}}:
            raise self._refuse("consent", "consent_must_name_the_command")
        with self.guard:
            if self.running():
                raise self._refuse("gpu_build", "gpu_build_running")
            if self._found() is not None:
                raise self._refuse("gpu_image_manifest", "gpu_worker_already_built")
            self.preflight(value["route"])
            lock = self._lock()
            if lock is None:
                raise self._refuse("gpu_build", "gpu_build_running")
            try:
                log = os.open(
                    self.root / LOG,
                    os.O_WRONLY
                    | os.O_CREAT
                    | os.O_TRUNC
                    | getattr(os, "O_NOFOLLOW", 0),
                    0o600,
                )
                try:
                    started = int(self.clock())
                    self._save(
                        {
                            "schema": SCHEMA,
                            "command": self.command_text(),
                            "route": value["route"],
                            "started_at": started,
                        }
                    )
                    process = self.runner(
                        self.command(), cwd=str(self.repo), log_fd=log, lock_fd=lock
                    )
                finally:
                    os.close(log)
            except BaseException:
                os.close(lock)
                raise
            self.thread = threading.Thread(
                target=self._watch,
                args=(process, lock, value["route"], started),
                name="carbon-gpu-worker-build",
                daemon=True,
            )
            self.thread.start()
        return self.status()

    def _watch(self, process, lock, route, started) -> None:
        try:
            code = process.wait()
        except Exception:  # noqa: BLE001 - the build's end, never a crash here
            code = None
        finally:
            os.close(lock)
        if code == 0:
            outcome = (
                None
                if self.manifest.is_file() and not self.manifest.is_symlink()
                else "gpu_build_wrote_no_manifest"
            )
        else:
            tail = self._tail().lower()
            if b"no space left on device" in tail:
                outcome = "gpu_build_disk_full"
            elif (
                b"cannot connect to the docker daemon" in tail
                or b"permission denied while trying to connect to the docker" in tail
            ):
                outcome = "docker_unreachable"
            else:
                outcome = "gpu_build_failed"
        self._save(
            {
                "schema": SCHEMA,
                "command": self.command_text(),
                "route": route,
                "started_at": started,
                "finished_at": int(self.clock()),
                "exit_code": code,
                "outcome": outcome,
            }
        )

    def status(self) -> dict:
        """Whether the build is offered, and how the last one stands."""
        found = self._found()
        running = self.running()
        record = self._record()
        value = {
            "schema": SCHEMA,
            "offered": found is None and not running,
            "command": self.command_text(),
            "routes": list(ROUTES),
            "driver_needed_for": list(DRIVER_ROUTES),
            "disk_gib": GPU_BUILD_GIB,
            "state": "idle",
        }
        if record is None:
            return {**value, "state": "running"} if running else value
        now = int(self.clock())
        started = record.get("started_at")
        if type(started) is int:
            end = record.get("finished_at")
            value["elapsed_seconds"] = max(
                0, (end if type(end) is int else now) - started
            )
        tail = self._tail()
        steps = _STEP.findall(tail)
        if steps:
            value["step"] = steps[-1][0].decode() + "/" + steps[-1][1].decode()
        lines = [line for line in tail.splitlines() if line.strip()]
        if lines:
            value["last_line"] = _text(lines[-1])
        value["log"] = str(self.root / LOG)
        if running:
            value["state"] = "running"
        elif "finished_at" not in record:
            # The process that watched it is gone and the build no longer
            # holds its lock: it ended unobserved.
            value["state"] = "built" if found is not None else "interrupted"
            if found is None:
                value["outcome"] = {
                    "code": "gpu_build_interrupted",
                    "next_step": NEXT["gpu_build_interrupted"],
                }
        elif record.get("outcome") is None:
            value["state"] = "built"
        else:
            code = record["outcome"]
            value["state"] = "failed"
            value["outcome"] = {
                "code": code,
                "next_step": NEXT.get(code, NEXT["gpu_build_failed"]),
            }
            if type(record.get("exit_code")) is int:
                value["outcome"]["exit_code"] = record["exit_code"]
        return value
