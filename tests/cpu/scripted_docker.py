"""A scripted container CLI for controller lifecycle tests.

No daemon is contacted, no image is pulled, no container exists and no device is
attached. What makes this useful rather than circular is that the container it
describes is *derived from the arguments the controller actually passed*: the
inspect response is built by parsing the create command line, so a control the
controller failed to request simply is not there and the real
`inspect_effective_controls` rejects it.

Everything above that boundary in the controller is real: the durable launch
store, the execution queue, staging, the request reader, cleanup and the
terminal-state machine.

What this cannot do is produce a genuine trained artifact, so the terminal
success path through `validate_snapshot_bounded` is not reachable here and is
not claimed anywhere in these tests.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import accelerator_host

from carbon.reconstruction.accelerators import GPU_PROFILE
from carbon.reconstruction.worker.docker_runtime import (
    _SCRATCH_TMPFS_BYTES,
    _SHM_BYTES,
    CPU_COUNT,
    MEMORY_BYTES,
    NOFILE_LIMIT,
    PIDS_LIMIT,
    SCRATCH_INODES,
    WORKER_GID,
    WORKER_UID,
)
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

CONTAINER_ID = "c" * 64


class Removed(Exception):
    """Raised by a fixture that is asked to act on a removed container."""


def _flags(arguments):
    """Index a create command line by option, as the daemon would see it."""
    values: dict[str, list[str]] = {}
    index = 0
    while index < len(arguments):
        item = arguments[index]
        if item.startswith("--"):
            name = item[2:]
            following = arguments[index + 1] if index + 1 < len(arguments) else ""
            if following.startswith("--") or index + 1 >= len(arguments):
                values.setdefault(name, []).append("")
                index += 1
                continue
            values.setdefault(name, []).append(following)
            index += 2
            continue
        index += 1
    return values


class ScriptedDocker:
    """One container's worth of scripted daemon responses."""

    def __init__(
        self,
        *,
        image,
        stage=None,
        ready_after=0,
        running=True,
        removable=True,
        fail_on=(),
        exporter=None,
    ):
        self.image = image
        self.stage = stage
        self.created = None
        self.create_arguments: list[str] = []
        self.commands: list[list[str]] = []
        self.started = False
        self.removed = False
        self.ready_after = ready_after
        self.running = running
        self.removable = removable
        self.fail_on = set(fail_on)
        self.exporter = exporter
        self.existing_containers = b""
        self.export_bounds: list[dict] = []
        self._waits = 0

    # --- json responses -------------------------------------------------------

    def json(self, command):
        self.commands.append(list(command))
        head = command[0]
        if head == "version":
            return {"Version": "27.0.0", "ApiVersion": "1.46"}
        if head == "info":
            return {
                "NCPU": 8,
                "MemTotal": MEMORY_BYTES + 8 * 1024**3,
                "CgroupVersion": "2",
                "CgroupDriver": "systemd",
                "SecurityOptions": ["name=seccomp,profile=builtin"],
                "KernelVersion": "6.8.0",
                "OperatingSystem": "Ubuntu 24.04",
                "Architecture": "x86_64",
                "Runtimes": {"runc": {}, "nvidia": {}},
            }
        if head == "image":
            return self._image_document()
        if head == "inspect":
            if self.removed:
                raise WorkerFailure(WorkerCode.RUNTIME)
            if "{{json .State}}" in command:
                return {"Running": self.running}
            return self._container_document()
        raise AssertionError(f"unscripted json command: {command}")

    def _image_document(self):
        return {
            "Id": self.image.image_id,
            "Os": "linux",
            "Architecture": "amd64",
            "Config": {
                "User": f"{WORKER_UID}:{WORKER_GID}",
                "Entrypoint": [
                    "/opt/carbon-worker/bin/python",
                    "-I",
                    "-m",
                    "carbon.reconstruction.worker.entrypoint",
                ],
                "Labels": {
                    "org.opencontainers.image.carbon.c03.scope": (
                        "UNQUALIFIED_PUBLIC_DEVELOPMENT"
                    ),
                    "org.opencontainers.image.carbon.c03.source-tree": (
                        self.image.source_tree_digest
                    ),
                    "org.opencontainers.image.carbon.c03.lock": self.image.lock_digest,
                    "org.opencontainers.image.carbon.c03.base-image": (
                        self.image.base_image_digest
                    ),
                    "org.opencontainers.image.carbon.c03.build-recipe": (
                        self.image.build_recipe_digest
                    ),
                    "org.opencontainers.image.carbon.c03.entrypoint": (
                        self.image.entrypoint_digest
                    ),
                    # The accelerator image binding the runtime requires before
                    # any device-backed launch.
                    "org.opencontainers.image.carbon.accelerator.profile": (
                        GPU_PROFILE.digest
                    ),
                    "org.opencontainers.image.carbon.accelerator.environment": (
                        GPU_PROFILE.environment_lock_digest
                    ),
                },
            },
        }

    def _container_document(self):
        """The container the controller asked for, and nothing more.

        Built by reading back the create command line, so a control the
        controller did not request is genuinely absent here.
        """
        flags = _flags(self.create_arguments)
        environment = flags.get("env", [])
        labels = dict(
            item.split("=", 1) for item in flags.get("label", []) if "=" in item
        )
        mounts = []
        for value in flags.get("mount", []):
            fields = dict(
                part.split("=", 1) for part in value.split(",") if "=" in part
            )
            mounts.append(
                {
                    "Type": fields.get("type"),
                    "Source": fields.get("source", fields.get("src")),
                    "Destination": fields.get("target", fields.get("destination")),
                    # `readonly` is a bare flag in the mount specification, not
                    # a key=value pair.
                    "RW": "readonly" not in value.split(","),
                }
            )
        tmpfs = {}
        for value in flags.get("tmpfs", []):
            destination, _, options = value.partition(":")
            tmpfs[destination] = options
        ulimits = []
        for value in flags.get("ulimit", []):
            name, _, limits = value.partition("=")
            soft, _, hard = limits.partition(":")
            ulimits.append({"Name": name, "Soft": int(soft), "Hard": int(hard or soft)})
        requests = []
        if "gpus" in flags:
            from carbon.reconstruction.worker.accelerator_runtime import device_request

            requests = [device_request()]
        return {
            "Id": CONTAINER_ID,
            "Image": self.image.image_id,
            "AppArmorProfile": "docker-default",
            "State": {"Running": self.running},
            "Mounts": mounts,
            "Config": {
                "User": (flags.get("user") or [None])[0],
                "Env": environment,
                "Labels": labels,
            },
            "HostConfig": {
                "ReadonlyRootfs": "read-only" in flags,
                "Privileged": False,
                "NetworkMode": (flags.get("network") or [""])[0],
                "IpcMode": (flags.get("ipc") or [""])[0],
                "PidMode": (flags.get("pid") or [""])[0],
                "RestartPolicy": {"Name": (flags.get("restart") or ["no"])[0]},
                "LogConfig": {
                    "Type": (flags.get("log-driver") or [""])[0],
                    "Config": dict(
                        item.split("=", 1)
                        for item in flags.get("log-opt", [])
                        if "=" in item
                    ),
                },
                "PidsLimit": int((flags.get("pids-limit") or [0])[0]),
                "Memory": MEMORY_BYTES,
                "MemorySwap": MEMORY_BYTES,
                "NanoCpus": CPU_COUNT * 1_000_000_000,
                "CpusetCpus": (flags.get("cpuset-cpus") or [""])[0],
                "ShmSize": _SHM_BYTES,
                "CapAdd": [],
                "CapDrop": flags.get("cap-drop", []),
                "Devices": [],
                "DeviceRequests": requests,
                "PortBindings": {},
                "PublishAllPorts": False,
                "SecurityOpt": flags.get("security-opt", []),
                "Ulimits": ulimits,
                "Tmpfs": tmpfs,
                "Runtime": (flags.get("runtime") or [""])[0],
            },
        }

    # --- run responses --------------------------------------------------------

    def run(self, command, *, timeout=None, accepted=(0,)):
        self.commands.append(list(command))
        head = command[0]
        if head in self.fail_on:
            raise WorkerFailure(WorkerCode.RUNTIME)
        if head in ("create", "run"):
            self.create_arguments = list(command)
            self.created = True
            return SimpleNamespace(
                returncode=0, stdout=(CONTAINER_ID + "\n").encode(), stderr=b""
            )
        if head == "start":
            self.started = True
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        if head in ("kill", "stop"):
            self.running = False
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        if head == "rm":
            if self.removable:
                self.removed = True
                return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
            return SimpleNamespace(returncode=1, stdout=b"", stderr=b"")
        if head == "inspect":
            # Cleanup polls this to confirm the container is gone.
            return SimpleNamespace(
                returncode=1 if self.removed else 0, stdout=b"", stderr=b""
            )
        if head == "ps":
            # The existing-container sweep before any attachment. An empty
            # result means no container already holds the device.
            return SimpleNamespace(
                returncode=0, stdout=self.existing_containers, stderr=b""
            )
        if head == "exec":
            return self._exec(command, accepted)
        raise AssertionError(f"unscripted run command: {command}")

    def _exec(self, command, accepted):
        if self.removed:
            raise Removed(command)
        tail = command[command.index("exec") + 1 :]
        if "/usr/bin/test" in tail:
            self._waits += 1
            ready = self._waits > self.ready_after
            return SimpleNamespace(returncode=0 if ready else 1, stdout=b"", stderr=b"")
        if "/usr/bin/touch" in tail:
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        if "/bin/cat" in tail:
            return SimpleNamespace(returncode=0, stdout=self._cat(tail[-1]), stderr=b"")
        if "/bin/df" in tail:
            if "/dev/shm" in tail:
                return SimpleNamespace(
                    returncode=0, stdout=f"size\n{_SHM_BYTES}\n".encode(), stderr=b""
                )
            if "--output=size,used" in tail:
                return SimpleNamespace(
                    returncode=0,
                    stdout=f"size used\n{_SCRATCH_TMPFS_BYTES} 0\n".encode(),
                    stderr=b"",
                )
            if "--output=itotal,iused" in tail:
                return SimpleNamespace(
                    returncode=0,
                    stdout=f"itotal iused\n{SCRATCH_INODES} 0\n".encode(),
                    stderr=b"",
                )
            if "--output=itotal" in tail:
                return SimpleNamespace(
                    returncode=0,
                    stdout=f"itotal\n{SCRATCH_INODES}\n".encode(),
                    stderr=b"",
                )
            return SimpleNamespace(
                returncode=0,
                stdout=f"size\n{_SCRATCH_TMPFS_BYTES}\n".encode(),
                stderr=b"",
            )
        if "/usr/bin/nvidia-smi" in tail:
            return self._smi(tail)
        raise AssertionError(f"unscripted exec: {command}")

    def _cat(self, path):
        if path.endswith("/proc/1/status"):
            return (
                b"Name:\tpython\nCapEff:\t0000000000000000\n"
                b"NoNewPrivs:\t1\nSeccomp:\t2\n"
            )
        table = {
            "cpu.max": f"{CPU_COUNT * 100000} 100000",
            "cpuset.cpus.effective": "0-1",
            "memory.max": str(MEMORY_BYTES),
            "memory.swap.max": "0",
            "pids.max": str(PIDS_LIMIT),
        }
        for name, value in table.items():
            if path.endswith(name):
                return (value + "\n").encode()
        # Resource observation reads further counters and already tolerates any
        # it cannot read, so anything not pinned above answers plausibly rather
        # than being treated as a gap in the script.
        if path.endswith((".stat", ".events", ".pressure")):
            return b"some 0\nfull 0\n"
        if "/sys/fs/cgroup/" in path:
            return b"0\n"
        raise AssertionError(f"unscripted cat: {path}")

    def _smi(self, tail):
        query = next((item for item in tail if item.startswith("--query")), "")
        if "driver_model" in query:
            return SimpleNamespace(returncode=0, stdout=b"WDDM\n", stderr=b"")
        if "compute-apps" in query:
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        return SimpleNamespace(
            returncode=0,
            stdout=(accelerator_host.identity_row() + "\n").encode(),
            stderr=b"",
        )

    # --- output ---------------------------------------------------------------

    def stream_to_file(self, command, destination, *, maximum=None, timeout=None):
        self.commands.append(list(command))
        # Recorded because the byte bound the controller applies to worker output
        # is an enforced limit, and a test needs to read the value actually used
        # rather than the value some record claims.
        self.export_bounds.append({"maximum": maximum, "timeout": timeout})
        if "export" in self.fail_on:
            raise WorkerFailure(WorkerCode.RUNTIME)
        if self.exporter is None:
            raise WorkerFailure(WorkerCode.OUTPUT)
        destination.write_bytes(self.exporter)
        return SimpleNamespace(returncode=0)


def framed(members):
    """One closed output stream, in the encoding the decoder accepts."""
    payload = b""
    for name, data in members.items():
        header = {"path": name, "bytes": len(data)}
        payload += json.dumps(header, sort_keys=True, separators=(",", ":")).encode()
        payload += b"\n" + data
    return payload


NOFILE = NOFILE_LIMIT
