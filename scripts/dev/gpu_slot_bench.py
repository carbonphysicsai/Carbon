#!/usr/bin/env python3
"""How do N concurrent build slots on one GPU behave: build seconds, device memory, and whether every build's state is
bit-identical (Lead, Mon 16 Nov 2026: the slots=N bench for the remote A100 lane and the local 4090 lane).

For each N in ``--slots`` (default 1,2,4) it starts N builds AT ONCE on the one GPU, each in its own container of the
pinned GPU worker image, with what a slot of `carbon.reconstruction.remote_gpu_build` gives a build: the pinned
determinism environment (`accelerators.worker_environment`: XLA deterministic ops, autotune off,
``CUBLAS_WORKSPACE_CONFIG``, TF32 off), the device bound by its uuid, each slot on its own cores (``--cpusets``), the
worker user, and for N > 1 the slot's in-process memory share (`remote_gpu_build.slot_environment` and
`remote_gpu_build.with_slot_prelude`: JAX's BFC allocator with its fraction, PyTorch's per-process fraction; the
door enables N > 1 only once Validator-2 accepts it, `remote_gpu_build.SLOT_PRELUDE_RULED`). It is not the carrier: no worker protocol, staging, exporter or the
worker profile's memory and pids limits. While builds run it samples ``nvidia-smi`` for device memory (every compute
process on the device, so run it on an otherwise idle GPU; the baseline before each N is reported; short peaks between
samples are missed). Each build writes its state bytes to stdout; the bench hashes them. It reports, per N: each build's
seconds, the peak device memory in use (total, and the largest single process), and whether all N states are identical
and identical to the N = 1 state.

The build program is ``--program`` (any build program that writes its state bytes to stdout), or the built-in one: a
small JAX MLP trained on a fixed synthetic dataset it generates itself (public by construction; no Challenge data, no
network). It changes nothing on the door: no ledger, no receipt, no state directory. The GPU class is not qualified by
this bench; it is evidence for choosing ``slots`` in the values row (scripts/validator_host_classes/remote_gpu_build.json).

    # on the door, against the rented GPU's daemon (its device record copied from the class check run there):
    python -B scripts/dev/gpu_slot_bench.py --image sha256:<jax gpu worker> --device-record <dir> \\
        --docker-host ssh://carbon@a100-1 --cpusets 0-3,4-7,8-11,12-15 --out slot-bench.json
    # on the 4090 host itself (local daemon, this host's record):
    python -B scripts/dev/gpu_slot_bench.py --image sha256:<...> --device-record /var/lib/carbon/accelerators \\
        --cpusets 0-1,2-3,4-5,6-7

Exit code 0 when every N's states are identical to the N = 1 state, 1 otherwise; the JSON lists every run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCHEMA = "carbon.gpu-slot-bench.v1"
#: The worker image's interpreter (the carrier's `docker exec` uses the same one).
WORKER_PYTHON = "/opt/carbon-worker/bin/python"
#: How often device memory is sampled while builds run (an operational interval).
SAMPLE_SECONDS = 0.5
#: The built-in build program: deterministic synthetic data, a small JAX MLP, raw float32 state bytes on stdout.
DEFAULT_PROGRAM = '''"""Carbon GPU slot bench: a fixed synthetic build (no Challenge data)."""
import os
import sys

import jax
import jax.numpy as jnp
import numpy as np

steps = int(os.environ.get("CARBON_BENCH_STEPS", "2000"))
width = int(os.environ.get("CARBON_BENCH_WIDTH", "2048"))
rng = np.random.default_rng(0)
x = rng.standard_normal((8192, 128)).astype(np.float32)
y = np.tanh(x @ rng.standard_normal((128, 16)).astype(np.float32))
k1, k2 = jax.random.split(jax.random.PRNGKey(0))
params = {
    "w1": jax.random.normal(k1, (128, width), jnp.float32) * 0.05,
    "w2": jax.random.normal(k2, (width, 16), jnp.float32) * 0.05,
}


def loss(p, x, y):
    return jnp.mean((jnp.tanh(x @ p["w1"]) @ p["w2"] - y) ** 2)


@jax.jit
def step(p, x, y):
    g = jax.grad(loss)(p, x, y)
    return jax.tree_util.tree_map(lambda a, b: a - 1e-2 * b, p, g)


x, y = jnp.asarray(x), jnp.asarray(y)
for _ in range(steps):
    params = step(params, x, y)
assert jax.devices()[0].platform == "gpu", jax.devices()
sys.stdout.buffer.write(b"".join(np.asarray(params[k]).tobytes() for k in sorted(params)))
'''


@dataclass
class Run:
    """One build of one N."""

    slots: int
    slot: int
    seconds: float | None = None
    state_sha256: str | None = None
    state_bytes: int | None = None
    exit_code: int | None = None
    error: str | None = None


@dataclass
class Sampler:
    """Peak device memory while builds run, from ``nvidia-smi`` (MiB)."""

    query: object  # () -> list[int]: the used memory of each compute process on the device now
    peak_total: int = 0
    peak_process: int = 0
    samples: int = 0
    _stop: threading.Event = field(default_factory=threading.Event)

    def sample(self):
        try:
            used = self.query()
        except Exception:  # noqa: BLE001 - a missed sample is only a missed sample
            return
        self.samples += 1
        self.peak_total = max(self.peak_total, sum(used))
        self.peak_process = max(self.peak_process, max(used, default=0))

    def run(self, interval=SAMPLE_SECONDS):
        while not self._stop.wait(interval):
            self.sample()

    def stop(self):
        self._stop.set()


def parse_slots(value):
    """``"1,2,4"`` -> ``(1, 2, 4)``: each within `remote_gpu_build.MAX_SLOTS`, ascending, starting at 1."""
    from carbon.reconstruction.remote_gpu_build import MAX_SLOTS

    slots = tuple(int(item) for item in value.split(","))
    if (
        not slots
        or slots[0] != 1
        or list(slots) != sorted(set(slots))
        or slots[-1] > MAX_SLOTS
    ):
        raise ValueError(f"slots: ascending, from 1, at most {MAX_SLOTS}")
    return slots


def lane_for(record, slots, cpusets, docker_host, memory="shared"):
    """A `remote_gpu_build.DoorLane` describing the bench's GPU with ``slots`` slots (nothing is installed)."""
    from carbon.reconstruction import remote_gpu_build

    spec = remote_gpu_build.GpuBuildSpec(
        0,
        docker_host,
        None if docker_host is None else "/nonexistent",
        tuple(cpusets),
    )
    return remote_gpu_build.DoorLane(spec, slots, record, "/nonexistent", memory)


def environment(record, binding):
    """The environment a build of this slot runs with: the pinned GPU worker environment and the slot's share."""
    from carbon.reconstruction import accelerators, remote_gpu_build

    result = accelerators.worker_environment(
        accelerators.GPU_PROFILE,
        accelerators.AcceleratorRole.VALIDATOR_RECONSTRUCTION,
        host_device=record,
    )
    # the bench container has no /scratch tmpfs: no compilation cache, as the controller asks of every rebuild anyway
    result.pop("JAX_COMPILATION_CACHE_DIR", None)
    result.update(remote_gpu_build.slot_environment(binding))
    return result


def run_argv(image_id, record, binding, name):
    """``docker run`` for one slot's build: the program arrives on stdin, the state leaves on stdout."""
    from carbon.reconstruction.host_execution import parse_cpuset

    argv = [
        "run",
        "--rm",
        "-i",
        "--name",
        name,
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp",
        # the worker image's entrypoint is the carrier's worker protocol; the bench runs its interpreter directly
        "--entrypoint",
        WORKER_PYTHON,
        "--runtime",
        "nvidia",
        "--gpus",
        f"driver=nvidia,device={record.device_uuid}",
        "--cpuset-cpus",
        binding.cpuset,
        "--label",
        "carbon.gpu-slot-bench=1",
        # the worker's own user, and no more CPUs than the slot's cores
        "--user",
        "65532:65532",
        "--cpus",
        str(len(parse_cpuset(binding.cpuset))),
    ]
    for key, value in sorted(environment(record, binding).items()):
        argv.extend(["--env", f"{key}={value}"])
    argv.extend(["--env", f"NVIDIA_VISIBLE_DEVICES={record.device_uuid}"])
    argv.extend(["--env", "NVIDIA_DRIVER_CAPABILITIES=compute,utility"])
    argv.extend([checked_image(image_id), "-I", "-"])
    return argv


def _docker_environment(docker_host):
    from carbon.reconstruction import remote_lane

    return remote_lane.docker_environment(docker_host)


def _gpu_query(record, docker_host):
    """The used memory (MiB) of each compute process on the bench's device, from ``nvidia-smi`` on its machine."""
    argv = [
        "nvidia-smi",
        "--query-compute-apps=gpu_uuid,used_memory",
        "--format=csv,noheader,nounits",
    ]
    if docker_host is not None:
        from types import SimpleNamespace

        from carbon.reconstruction import remote_lane

        argv = [
            *remote_lane._ssh(SimpleNamespace(docker_host=docker_host)),
            shlex.join(argv),
        ]

    def query():
        done = subprocess.run(argv, capture_output=True, timeout=10, check=True)
        used = []
        for line in done.stdout.decode().splitlines():
            uuid, _, mib = (part.strip() for part in line.partition(","))
            if uuid == record.device_uuid and mib.isdigit():
                used.append(int(mib))
        return used

    return query


#: How long one build may take before the bench stops it (an operational bound).
BUILD_TIMEOUT_SECONDS = 3600
_IMAGE = re.compile(
    r"sha256:[0-9a-f]{64}|[a-z0-9][a-z0-9._/-]{0,200}(?::[A-Za-z0-9._-]{1,128})?"
)


def checked_image(value):
    """An image id or plain reference; anything that could read as a docker option refuses."""
    if (
        type(value) is not str
        or not _IMAGE.fullmatch(value)
        or (value.startswith("sha256:") and len(value) != 71)
    ):
        raise ValueError("image: sha256:<64 hex> or a plain image reference")
    return value


def run_one(
    run,
    *,
    argv,
    program,
    docker_host,
    popen=subprocess.Popen,
    clock=time.monotonic,
    timeout=BUILD_TIMEOUT_SECONDS,
):
    """Run one build; fills ``run`` in place. A build that outlives ``timeout`` is killed and recorded as an error."""
    started = clock()
    try:
        process = popen(
            ["docker", *argv],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_docker_environment(docker_host),
        )
        try:
            out, err = process.communicate(program.encode(), timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            run.error = f"timed out after {timeout} s"
            return run
    except Exception as error:  # noqa: BLE001 - recorded, never raised
        run.error = repr(error)[:512]
        return run
    run.seconds = round(clock() - started, 3)
    run.exit_code = process.returncode
    if process.returncode == 0 and out:
        run.state_sha256 = "sha256:" + hashlib.sha256(out).hexdigest()
        run.state_bytes = len(out)
    else:
        run.error = err.decode("utf-8", "replace")[-512:]
    return run


def bench(
    *,
    image_id,
    record,
    slots_list,
    cpusets,
    docker_host,
    program,
    memory="shared",
    runner=run_one,
    query=None,
    interval=SAMPLE_SECONDS,
):
    """Every N of ``slots_list``, its N builds at once; the report document."""
    from carbon.reconstruction import remote_gpu_build

    if len(cpusets) < max(slots_list):
        raise ValueError("one cpuset per slot of the largest N")
    query = _gpu_query(record, docker_host) if query is None else query
    groups, reference = [], None
    for slots in slots_list:
        lane = lane_for(record, slots, cpusets, docker_host, memory)
        runs = [Run(slots, slot) for slot in range(slots)]
        sampler = Sampler(query)
        try:
            baseline = sum(query())
        except Exception:  # noqa: BLE001 - a missed sample is only a missed sample
            baseline = None
        watcher = threading.Thread(target=sampler.run, args=(interval,), daemon=True)
        watcher.start()
        workers = []
        for run in runs:
            binding = remote_gpu_build.OpBinding(lane, run.slot)
            source = remote_gpu_build.with_slot_prelude(program, binding)
            argv = run_argv(
                image_id, record, binding, f"carbon-slot-bench-{slots}-{run.slot}"
            )
            workers.append(
                threading.Thread(
                    target=runner,
                    args=(run,),
                    kwargs={
                        "argv": argv,
                        "program": source,
                        "docker_host": docker_host,
                    },
                )
            )
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        sampler.stop()
        watcher.join(timeout=5)
        sampler.sample()
        digests = {run.state_sha256 for run in runs}
        if slots == 1:
            reference = runs[0].state_sha256
        groups.append(
            {
                "slots": slots,
                # a torch build's hard share; a JAX build has none (`remote_gpu_build.slot_environment`)
                "slot_memory": "none" if slots == 1 else memory,
                "memory_fraction": (
                    remote_gpu_build.slot_fraction(slots)
                    if slots > 1 and memory == "capped"
                    else None
                ),
                "baseline_device_memory_mib": baseline,
                "runs": [run.__dict__ for run in runs],
                "seconds_max": max((run.seconds or 0) for run in runs),
                "peak_device_memory_mib": sampler.peak_total,
                "peak_process_memory_mib": sampler.peak_process,
                "memory_samples": sampler.samples,
                "all_succeeded": all(
                    run.exit_code == 0 and run.state_sha256 for run in runs
                ),
                "states_identical": len(digests) == 1 and None not in digests,
                "identical_to_one_slot": reference is not None
                and digests == {reference},
            }
        )
    return {
        "schema": SCHEMA,
        "device": {
            "kind": record.device_kind,
            "uuid": record.device_uuid,
            "record": record.digest,
        },
        "docker_host": docker_host,
        "image_id": image_id,
        "program_sha256": "sha256:" + hashlib.sha256(program.encode()).hexdigest(),
        "groups": groups,
        "verdict": (
            "IDENTICAL"
            if all(group["identical_to_one_slot"] for group in groups)
            else "DIFFERS_OR_FAILED"
        ),
        "note": "Bench evidence for choosing slots; not a hardware acceptance or qualification.",
    }


def main(argv=None):
    from carbon.reconstruction.accelerators import GPU_PROFILE
    from carbon.reconstruction.host_inventory import (
        HostDeviceRecord,
        require_host_device,
    )

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--image", required=True, help="the pinned GPU worker image id (sha256:...)"
    )
    parser.add_argument(
        "--device-record",
        required=True,
        type=Path,
        help="directory holding the GPU machine's host-device.json",
    )
    parser.add_argument(
        "--docker-host",
        default=None,
        help="ssh://user@host[:port]; omit for this host's daemon",
    )
    parser.add_argument("--slots", default="1,2,4")
    parser.add_argument(
        "--memory",
        choices=("shared", "capped"),
        default="shared",
        help="N > 1: shared = no cap (pinned platform allocator); capped = the slot prelude's 0.9/N share",
    )
    parser.add_argument(
        "--cpusets",
        required=True,
        help="one cpuset per slot of the largest N, comma-separated groups",
    )
    parser.add_argument(
        "--program",
        type=Path,
        default=None,
        help="a build program writing its state to stdout",
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    record = require_host_device(HostDeviceRecord.load(args.device_record), GPU_PROFILE)
    if args.docker_host is not None:
        from carbon.reconstruction import remote_lane

        remote_lane.parse_docker_host(args.docker_host)
    report = bench(
        image_id=args.image,
        record=record,
        slots_list=parse_slots(args.slots),
        memory=args.memory,
        cpusets=split_cpusets(args.cpusets),
        docker_host=args.docker_host,
        program=DEFAULT_PROGRAM if args.program is None else args.program.read_text(),
    )
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.out is not None:
        args.out.write_text(text + "\n")
    return 0 if report["verdict"] == "IDENTICAL" else 1


def split_cpusets(value):
    """``"0-3,4-7"`` style: each slot's cpuset is one comma-separated item (a range or a single core)."""
    from carbon.reconstruction.host_execution import parse_cpuset

    cpusets = [item.strip() for item in value.split(",") if item.strip()]
    seen = set()
    for item in cpusets:
        cores = set(parse_cpuset(item))
        if cores & seen:
            raise ValueError("cpusets overlap")
        seen |= cores
    return cpusets


if __name__ == "__main__":
    raise SystemExit(main())
