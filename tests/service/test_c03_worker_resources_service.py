"""Required Linux/Docker evidence for the larger worker resources
(OWNER-WORKER-RESOURCES-LARGE-MODELS-01; Validator ruling
VALIDATOR_RULING_RUNF_REAL_V7_20261022): one real C-03 launch at the v7
profile, and the same test at the v6 profile.

Nothing here is a double. The production launch path runs: the real
`doctor` sized for the profile, `create_arguments`, the real daemon, the real
`inspect_effective_controls` (daemon HostConfig, cgroup v2 and filesystem
readings against the profile), and probes executed inside the started worker
container. The profile is applied in-test (the gate in the code is off until
this evidence exists). A host too small for the v7 profile skips with the
doctor's code rather than weakening the profile.

Asserts, per profile:
1. `docker inspect`: memory, swap, NanoCpus, ShmSize, the /scratch tmpfs size
   with ``uid=65532,gid=65532,mode=0700``, PIDs and nofile as registered.
2. Enforcement inside the worker: scratch past its size fails with ENOSPC;
   shared memory past its size fails with ENOSPC and a smaller write inside it
   succeeds; an output past the envelope is refused by the exporter (rc 20)
   while one inside it exports; the network and filesystem probes still hold.
   A parallel shared-memory workload runs under each shm, parent-aware: a torch
   DataLoader where the parent has torch, a numpy/JAX workload over a
   SharedMemory block where it has none (the python-cpu JAX parent).
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from carbon.development_session import research_carrier as rc
from carbon.reconstruction.worker import model
from carbon.reconstruction.worker.docker_runtime import (
    DockerCLI,
    create_arguments,
    doctor,
    inspect_effective_controls,
    load_image_identity,
    remove_exact_container,
)

GIB = 1024**3
MIB = 1024**2
V7 = "level4-allowlist-v7"
PROBES = [
    "/opt/carbon-worker/bin/python",
    "-I",
    "-m",
    "carbon.reconstruction.worker.probes",
]

#: Writes `target` bytes to a tmpfs file in 1 MiB blocks; exits 0 when the
#: write is refused with ENOSPC, 12 when it all lands.
FILL = """
import errno, sys
path, target = sys.argv[1], int(sys.argv[2])
try:
    with open(path, "wb", buffering=0) as stream:
        for _ in range(target // (1 << 20)):
            stream.write(b"x" * (1 << 20))
except OSError as error:
    raise SystemExit(0 if error.errno == errno.ENOSPC else 13)
raise SystemExit(12)
"""
#: A sparse file of `size` bytes in the exporter's output tree.
INSIDE = """
import sys
with open(sys.argv[1], "wb", buffering=0) as stream:
    for _ in range(int(sys.argv[2]) // (1 << 20)):
        stream.write(b"x" * (1 << 20))
"""
SPARSE = """
import os, sys
os.makedirs("/scratch/output", exist_ok=True)
with open("/scratch/output/member", "wb") as stream:
    stream.truncate(int(sys.argv[1]))
"""
DATALOADER = """
import sys
try:
    import torch
    from torch.utils.data import DataLoader, TensorDataset
except ImportError:
    raise SystemExit(77)
data = TensorDataset(torch.arange(256, dtype=torch.float32).reshape(64, 4))
total = sum(batch[0].sum().item() for batch in DataLoader(data, batch_size=8, num_workers=2))
raise SystemExit(0 if total == sum(range(256)) else 12)
"""


HAS_TORCH = """
import importlib.util
print(1 if importlib.util.find_spec("torch") is not None else 0)
"""
#: numpy over a SharedMemory block in /dev/shm, summed by two worker processes
#: (the DataLoader's pattern), then a jitted JAX reduction of the same data.
#: Exits 0 on the exact expected totals, 12 otherwise.
SHM_WORKLOAD = """
import multiprocessing as mp
import sys
from multiprocessing import shared_memory

import numpy as np


def _sum(name, count, start, stop, queue):
    block = shared_memory.SharedMemory(name=name)
    try:
        queue.put(float(np.ndarray((count,), np.float32, buffer=block.buf)[start:stop].sum()))
    finally:
        block.close()


if __name__ == "__main__":
    count = int(sys.argv[1]) // 4
    block = shared_memory.SharedMemory(create=True, size=count * 4)
    try:
        data = np.ndarray((count,), np.float32, buffer=block.buf)
        data[:] = 1.0
        queue = mp.get_context("fork").Queue()
        half = count // 2
        procs = [
            mp.get_context("fork").Process(target=_sum, args=(block.name, count, a, b, queue))
            for a, b in ((0, half), (half, count))
        ]
        for proc in procs:
            proc.start()
        total = sum(queue.get(timeout=120) for _ in procs)
        for proc in procs:
            proc.join(timeout=60)
        import jax.numpy as jnp

        jax_total = float(jnp.asarray(data).sum())
        ok = total == float(count) and jax_total == float(count)
    finally:
        block.close()
        block.unlink()
    raise SystemExit(0 if ok else 12)
"""


@pytest.fixture
def real_docker():
    manifest = os.environ.get("CARBON_C03_IMAGE_MANIFEST")
    assert manifest, "CARBON_C03_IMAGE_MANIFEST names the pinned worker image"
    return load_image_identity(Path(manifest)), DockerCLI()


def _profile(version, monkeypatch):
    monkeypatch.setattr(model, "LARGE_MODEL_PROFILE_APPLIED", True)
    return rc._worker_profile(None, rc.LIBRARY_BUILD_PROVENANCE, version)


def _started(real_docker, profile, tmp_path):
    image, cli = real_docker
    checked = doctor(
        image_id=image.image_id, image_identity=image, cli=cli, worker_profile=profile
    )
    if not checked.eligible:
        pytest.skip("host cannot carry this profile: " + checked.code)
    input_directory = tmp_path / "input"
    input_directory.mkdir()
    input_directory.chmod(0o555)
    name = "carbon-c03-res-" + uuid.uuid4().hex[:12]
    launch = "sha256:" + uuid.uuid4().hex + uuid.uuid4().hex
    cli.run(
        create_arguments(
            container_name=name,
            image_id=image.image_id,
            input_directory=input_directory,
            cpuset=checked.cpuset,
            launch_digest=launch,
            worker_profile=profile,
        ),
        timeout=30,
    )
    cli.run(["start", name], timeout=20)
    _, evidence = inspect_effective_controls(
        cli=cli,
        container_name=name,
        image_id=image.image_id,
        input_directory=input_directory,
        cpuset=checked.cpuset,
        launch_digest=launch,
        worker_profile=profile,
    )
    return name, launch, evidence


def _exec(cli, name, arguments, *, accepted=(0,), timeout=600):
    return cli.run(
        ["exec", "--user", "65532:65532", name, *arguments],
        timeout=timeout,
        accepted=accepted,
    )


def _python(cli, name, code, *arguments, accepted=(0,), timeout=600):
    return _exec(
        cli,
        name,
        ["/opt/carbon-worker/bin/python", "-I", "-c", code, *arguments],
        accepted=accepted,
        timeout=timeout,
    )


def _run_profile(real_docker, profile, tmp_path, expected):
    image, cli = real_docker
    name, launch, evidence = _started(real_docker, profile, tmp_path)
    try:
        host = evidence["daemon_host_config"]
        assert host["memory"] == host["memory_swap"] == expected["memory"]
        assert host["nano_cpus"] == expected["cpus"] * 10**9
        assert host["shm_size"] == expected["shm"]
        assert host["pids_limit"] == 256
        assert host["tmpfs"]["/scratch"] == (
            f"rw,nosuid,nodev,noexec,size={expected['scratch']},nr_inodes=8192,"
            f"mode=700,uid=65532,gid=65532"
        )
        assert {
            (item["Name"], item["Soft"], item["Hard"]) for item in host["ulimits"]
        } >= {("nofile", 1024, 1024), ("core", 0, 0)}
        assert evidence["cgroup_v2"]["memory.max"] == str(expected["memory"])
        assert evidence["cgroup_v2"]["pids.max"] == "256"
        assert evidence["filesystem"]["scratch_bytes"] == expected["scratch"]
        assert evidence["filesystem"]["shm_bytes"] == expected["shm"]

        # Scratch past its size is refused by the kernel.
        _python(
            cli,
            name,
            FILL,
            "/scratch/fill",
            str(expected["scratch"] + 64 * MIB),
            timeout=900,
        )
        _python(cli, name, "import os;os.unlink('/scratch/fill')")
        # Shared memory: past its size is refused, and a write inside it lands.
        _python(
            cli,
            name,
            FILL,
            "/dev/shm/fill",
            str(expected["shm"] + 64 * MIB),
            timeout=900,
        )
        _python(cli, name, "import os;os.unlink('/dev/shm/fill')")
        _python(
            cli,
            name,
            INSIDE,
            "/dev/shm/inside",
            str(min(expected["shm"] // 2, 512 * MIB)),
        )
        # The exporter: a member past the envelope is refused (typed rc 20);
        # one inside it exports (control specimen).
        _python(cli, name, SPARSE, str(expected["output"] + 1))
        refused = _exec(
            cli,
            name,
            [
                "/opt/carbon-worker/bin/python",
                "-I",
                "-m",
                "carbon.reconstruction.worker.exporter",
                *expected["export_args"],
            ],
            accepted=(20,),
        )
        assert refused.returncode == 20
        _python(cli, name, SPARSE, "4096")
        exported = _exec(
            cli,
            name,
            [
                "/opt/carbon-worker/bin/python",
                "-I",
                "-m",
                "carbon.reconstruction.worker.exporter",
                *expected["export_args"],
            ],
        )
        assert exported.returncode == 0
        # The network and filesystem probes still hold.
        assert _exec(cli, name, [*PROBES, "paths"]).returncode == 0
        assert (
            _exec(
                cli, name, [*PROBES, "connect", "1.1.1.1", "53"], accepted=(10,)
            ).returncode
            == 10
        )
        # Real shared memory under a parallel workload, parent-aware: the torch
        # parent runs a DataLoader with workers; the python-cpu (JAX) parent has no
        # torch by design (rc 77 there) and runs an equivalent numpy/JAX workload
        # over a shared-memory block with worker processes. Neither is a skip.
        torch_present = _python(cli, name, HAS_TORCH).stdout.strip() == b"1"
        if torch_present:
            assert _python(cli, name, DATALOADER).returncode == 0
        else:
            assert _python(cli, name, DATALOADER, accepted=(0, 77)).returncode == 77
            # The write-inside specimen above is removed first and the block is a
            # quarter of shm, so the semaphores the workers need have room.
            _python(cli, name, "import os;os.unlink('/dev/shm/inside')")
            block = min(expected["shm"] // 4, 256 * MIB)
            assert _python(cli, name, SHM_WORKLOAD, str(block)).returncode == 0
    finally:
        remove_exact_container(cli=cli, container_name=name, launch_digest=launch)


def test_a_v7_launch_gets_2_4_16_and_the_kernel_enforces_it(
    real_docker, tmp_path, monkeypatch
):
    profile = _profile(V7, monkeypatch)
    assert profile.large_model
    _run_profile(
        real_docker,
        profile,
        tmp_path,
        {
            "memory": 16 * GIB,
            "cpus": 4,
            "shm": 2 * GIB,
            "scratch": 4 * GIB,
            "output": 2 * GIB,
            "export_args": [str(2 * GIB)],
        },
    )


def test_a_v6_launch_keeps_todays_envelope_byte_for_byte(
    real_docker, tmp_path, monkeypatch
):
    profile = _profile(None, monkeypatch)
    assert not profile.large_model
    _run_profile(
        real_docker,
        profile,
        tmp_path,
        {
            "memory": 4 * GIB,
            "cpus": 2,
            "shm": 8 * MIB,
            "scratch": 512 * MIB - 8 * MIB,
            "output": 128 * MIB,
            "export_args": [],
        },
    )
