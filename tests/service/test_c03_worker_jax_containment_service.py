"""Required Linux/Docker evidence that a JAX workload stays inside the worker's
containment (Run J operator probe, made a committed test; Validator ruling).

One real C-03 launch per profile (v7 and v6), through the production path (`doctor`,
`create_arguments`, the real daemon, `inspect_effective_controls`), then a jitted
JAX load executed as the worker user inside it:

(a) JAX's persistent cache and temp files land only under /scratch; writes to the
    read-only root, /opt, /etc, /usr, /home, /tmp, /var/tmp and /input fail with
    EROFS (/root with EACCES); `docker diff` shows only the two mount points
    Docker creates; and caches pointed at the root (JAX_COMPILATION_CACHE_DIR,
    TMPDIR, XDG_CACHE_HOME, an XLA dump) write nothing outside the tmpfs mounts.
(b) The container's cgroup CPU over the load stays at or below the profile's cpus
    with hostile XLA_FLAGS and *_NUM_THREADS, and jax still sees one CPU device.

The torch-free python-cpu parent is the one that matters (the jNO parent); a
parent with no JAX skips with that reason. Nothing is a double.
"""

from __future__ import annotations

import json
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

V7 = "level4-allowlist-v7"
LOAD_SECONDS = 8
#: Slack over the profile's cpus for the cgroup accounting window (a ratio, not a
#: relaxation of the limit: the kernel quota is exact; this absorbs measurement).
SLACK = 1.05

INNER = r"""
import errno, json, os, sys, tempfile, time
res = {}
try:
    res["tmp"] = tempfile.gettempdir()
except Exception as e:  # a temp variable pointed at an unusable root
    res["tmp"] = "ERR " + type(e).__name__
def usage():
    for line in open("/sys/fs/cgroup/cpu.stat"):
        if line.startswith("usage_usec"):
            return int(line.split()[1])
import jax, jax.numpy as jnp
jax.config.update("jax_persistent_cache_min_compile_time_secs", 0)
jax.config.update("jax_persistent_cache_min_entry_size_bytes", -1)
res["devices"] = [str(d) for d in jax.devices()]
x = jnp.ones((2048, 2048), jnp.float32)
f = jax.jit(lambda a: jnp.tanh(a @ a).sum())
f(x).block_until_ready()
w0, c0 = time.monotonic(), usage()
while time.monotonic() - w0 < float(sys.argv[1]):
    f(x).block_until_ready()
w1, c1 = time.monotonic(), usage()
res["cores_used"] = (c1 - c0) / 1e6 / (w1 - w0)
writes = {}
for d in ("/", "/opt", "/opt/carbon-worker", "/home", "/root", "/tmp", "/var/tmp",
          "/etc", "/usr", "/input"):
    p = os.path.join(d, ".c03-write-probe")
    try:
        with open(p, "wb") as s:
            s.write(b"x")
        os.unlink(p)
        writes[d] = "WROTE"
    except OSError as e:
        writes[d] = errno.errorcode.get(e.errno, str(e.errno))
res["writes"] = writes
files = []
for top in ("/scratch", "/dev/shm"):
    for root, _dirs, names in os.walk(top):
        files += [os.path.join(root, n) for n in names]
res["files"] = sorted(files)
print("C03_JAX_PROBE=" + json.dumps(res, sort_keys=True))
"""
HOSTILE_THREADS = {
    "XLA_FLAGS": "--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads=64 "
    "--xla_force_host_platform_device_count=64",
    "OMP_NUM_THREADS": "64",
    "OPENBLAS_NUM_THREADS": "64",
    "MKL_NUM_THREADS": "64",
    "XLA_FORCE_HOST_PLATFORM_DEVICE_COUNT": "64",
}
ROOT_CACHES = {
    "JAX_COMPILATION_CACHE_DIR": "/opt/c03-jax-cache",
    "TMPDIR": "/opt/c03-tmp",
    "XDG_CACHE_HOME": "/opt/c03-xdg",
    "HOME": "/root",
    "XLA_FLAGS": "--xla_dump_to=/opt/c03-xla-dump",
}
#: The only paths Docker itself adds to the root of a started worker.
MOUNT_POINTS = {"A /input", "A /scratch"}


@pytest.fixture
def real_docker():
    manifest = os.environ.get("CARBON_C03_IMAGE_MANIFEST")
    assert manifest, "CARBON_C03_IMAGE_MANIFEST names the pinned worker image"
    return load_image_identity(Path(manifest)), DockerCLI()


def _launch(real_docker, version, tmp_path, monkeypatch):
    monkeypatch.setattr(model, "LARGE_MODEL_PROFILE_APPLIED", version is not None)
    profile = rc._worker_profile(None, rc.LIBRARY_BUILD_PROVENANCE, version)
    image, cli = real_docker
    checked = doctor(
        image_id=image.image_id, image_identity=image, cli=cli, worker_profile=profile
    )
    if not checked.eligible:
        pytest.skip("host cannot carry this profile: " + checked.code)
    input_directory = tmp_path / "input"
    input_directory.mkdir()
    input_directory.chmod(0o555)
    name = "carbon-c03-jax-" + uuid.uuid4().hex[:12]
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
    inspect_effective_controls(
        cli=cli,
        container_name=name,
        image_id=image.image_id,
        input_directory=input_directory,
        cpuset=checked.cpuset,
        launch_digest=launch,
        worker_profile=profile,
    )
    _wait_ready(cli, name)
    return name, launch, profile


def _wait_ready(cli, name, seconds=30):
    """The entrypoint creates /scratch/tmp and then /scratch/control-ready a moment
    after start; probing earlier
    sees an empty /scratch and no usable temp directory."""
    import time

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        done = cli.run(
            [
                "exec",
                "--user",
                "65532:65532",
                name,
                "test",
                "-e",
                "/scratch/control-ready",
            ],
            timeout=20,
            accepted=(0, 1),
        )
        if done.returncode == 0:
            return
        time.sleep(0.5)
    pytest.fail("the worker never became ready (/scratch/control-ready)")


def _probe(cli, name, env):
    arguments = ["exec", "--user", "65532:65532"]
    for key, value in sorted(env.items()):
        arguments += ["-e", f"{key}={value}"]
    arguments += [
        name,
        "/opt/carbon-worker/bin/python",
        "-I",
        "-c",
        INNER,
        str(LOAD_SECONDS),
    ]
    done = cli.run(arguments, timeout=LOAD_SECONDS + 240, accepted=(0, 1))
    if done.returncode == 1 and b"No module named 'jax'" in done.stderr:
        pytest.skip("this parent carries no JAX")
    assert done.returncode == 0, done.stderr[-2000:]
    lines = [
        line
        for line in done.stdout.decode().splitlines()
        if line.startswith("C03_JAX_PROBE=")
    ]
    assert len(lines) == 1
    return json.loads(lines[0].split("=", 1)[1])


def _diff(cli, name):
    out = cli.run(["diff", name], timeout=30).stdout.decode()
    return {line.strip() for line in out.splitlines() if line.strip()}


@pytest.mark.parametrize("version", [V7, None])
def test_jax_writes_only_under_scratch_and_the_root_stays_read_only(
    real_docker, tmp_path, monkeypatch, version
):
    name, launch, _profile = _launch(real_docker, version, tmp_path, monkeypatch)
    _image, cli = real_docker
    try:
        for env in ({}, ROOT_CACHES):
            result = _probe(cli, name, env)
            assert len(result["devices"]) == 1, result["devices"]
            # Only a variable pointed at an unusable root may leave an error; the
            # launch's own environment always has its temp files under /scratch.
            if env is ROOT_CACHES:
                assert result["tmp"].startswith(("/scratch", "ERR ")), result["tmp"]
            else:
                assert result["tmp"].startswith("/scratch"), result["tmp"]
            for directory, outcome in result["writes"].items():
                assert outcome in ("EROFS", "EACCES"), (directory, outcome)
            assert result["writes"]["/root"] in ("EROFS", "EACCES")
            assert all(
                path.startswith(("/scratch/", "/dev/shm/")) for path in result["files"]
            )
            assert _diff(cli, name) <= MOUNT_POINTS
    finally:
        remove_exact_container(cli=cli, container_name=name, launch_digest=launch)


@pytest.mark.parametrize("version", [V7, None])
def test_jax_cpu_use_stays_within_the_cpuset_under_hostile_thread_variables(
    real_docker, tmp_path, monkeypatch, version
):
    name, launch, _profile = _launch(real_docker, version, tmp_path, monkeypatch)
    _image, cli = real_docker
    try:
        # The registered cpus (OWNER-WORKER-RESOURCES-LARGE-MODELS-01): v7 gets 4,
        # today's v6 envelope 2; the resources test pins the same numbers.
        cpus = 4 if version else 2
        for env in ({}, HOSTILE_THREADS):
            result = _probe(cli, name, env)
            assert len(result["devices"]) == 1, result["devices"]
            assert result["tmp"].startswith("/scratch"), result["tmp"]
            assert result["cores_used"] <= cpus * SLACK, (
                env,
                result["cores_used"],
                cpus,
            )
    finally:
        remove_exact_container(cli=cli, container_name=name, launch_digest=launch)
