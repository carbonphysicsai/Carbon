"""--gpu selects the GPU worker of each installed backend (Validator ruling;
launch must: GPU for every Challenge, backend parity).

Before this, `install_miner.sh --gpu` always built and selected the JAX GPU
worker, even with --pytorch, so the catalog's PyTorch entries never got a GPU
build (M1 5090: catalog_gpu_build_missing). These tests hold:
- with --pytorch --gpu the installer builds (or pulls, with --release) the
  PyTorch GPU worker beside the JAX one, reuses one built from this exact
  source tree, and records both;
- this machine's GPU practice then checks the PyTorch GPU worker, so its
  runtime is torch-cu130-py311 and each PyTorch catalog entry has its GPU
  twin; a check against it is not stale;
- the JAX-only path is unchanged.
Docker, the driver and every image are stand-ins.
"""

from __future__ import annotations

import json

import pytest
from test_battery_gpu_practice import BATTERY_REF, gpu_image, gpu_setup
from test_miner_install import RELEASE, Sandbox, publish_release, pulled, run_release

from carbon.backbone_catalog import pipeline
from carbon.development_session import gpu_practice
from carbon.reconstruction import torch_profile
from scripts.dev.miner_launchpad import installed
from scripts.dev.miner_launchpad.environment_setup import LOCAL_GPU, REMOTE

TORCH_RELEASE = ("torch", "torch-analysis", "c03", "accelerator")


@pytest.fixture
def sandbox(tmp_path):
    box = Sandbox(tmp_path)
    box._executable(box.tools / "nvidia-smi", "#!/bin/sh\necho fixture GPU\n")
    for script, label in (
        ("torch_worker_image.sh", "torch worker"),
        ("torch_gpu_worker_image.sh", "torch gpu worker"),
    ):
        box._executable(
            box.work / "scripts/dev" / script,
            '#!/bin/sh\nmkdir -p "$(dirname "$1")"\n'
            'echo "{\\"image_id\\":\\"sha256:'
            + label.replace(" ", "-")
            + '-$(git rev-parse HEAD)\\"}" > "$1"\n'
            f'echo "{label}" >> "$CARBON_TEST_LOG"\n',
        )
    box.publish("fixture Torch builders")
    return box


def recorded(sandbox):
    (line,) = [line for line in sandbox.logged() if "installed write" in line]
    return line


def test_pytorch_gpu_builds_both_gpu_workers_and_records_both(sandbox):
    result = sandbox.run("--pytorch", "--gpu", "--no-start")
    assert result.returncode == 0, result.stderr
    log = sandbox.logged()
    assert "gpu worker" in log and "torch gpu worker" in log
    artifacts = sandbox.clone / ".carbon-artifacts"
    line = recorded(sandbox)
    assert f"--gpu-image-manifest {artifacts}/accelerator-worker-image.json" in line
    assert f"--torch-gpu-image-manifest {artifacts}/torch-gpu-worker-image.json" in line
    # Run again at this revision: both GPU workers are used again, not rebuilt.
    sandbox.log.unlink()
    again = sandbox.run("--pytorch", "--gpu", "--no-start")
    assert again.returncode == 0, again.stderr
    assert "torch gpu worker" not in sandbox.logged()
    assert "PyTorch GPU worker built here from this exact source tree" in again.stdout


def test_jax_only_gpu_is_unchanged(sandbox):
    result = sandbox.run("--gpu", "--no-start")
    assert result.returncode == 0, result.stderr
    log = sandbox.logged()
    assert "gpu worker" in log and "torch gpu worker" not in log
    assert "--torch-gpu-image-manifest" not in recorded(sandbox)


def test_a_pytorch_gpu_release_pulls_the_torch_gpu_worker_too(sandbox):
    publish_release(sandbox, kinds=(*TORCH_RELEASE, "torch-gpu"))
    result = run_release(
        sandbox, "--pytorch", "--gpu", "--release", RELEASE, "--no-start"
    )
    assert result.returncode == 0, result.stderr
    assert "torch-gpu-worker-image.release.json" in pulled(sandbox.logged())
    releases = sandbox.clone / ".carbon-artifacts" / "releases" / RELEASE
    assert (
        f"--torch-gpu-image-manifest {releases}/torch-gpu-worker-image.json"
        in recorded(sandbox)
    )


def test_a_pytorch_release_without_gpu_needs_no_torch_gpu_record(sandbox):
    publish_release(sandbox, kinds=TORCH_RELEASE)
    result = run_release(sandbox, "--pytorch", "--release", RELEASE, "--no-start")
    assert result.returncode == 0, result.stderr
    assert "torch-gpu" not in " ".join(pulled(sandbox.logged()))


# --- setup: this machine's GPU practice checks the PyTorch GPU worker ----------


def record_install(setup, home, paths, *, torch=True):
    (home / "torch-gpu.json").write_text("{}")
    installed.write(
        setup.root.parent,
        image_manifest=paths["image_manifest"],
        analysis_image_manifest=paths["analysis_image_manifest"],
        gpu_image_manifest=home / "gpu.json",
        torch_gpu_image_manifest=home / "torch-gpu.json" if torch else None,
    )


def test_this_machines_gpu_practice_checks_the_pytorch_gpu_worker_too(tmp_path):
    """One GPU worker per installed backend: the JAX worker setup offers
    stays the profile's `gpu_image`, and the PyTorch one is checked beside it
    (`extra_gpu_image`; test_gpu_per_backend has the scopes)."""
    setup, checks, home, paths = gpu_setup(tmp_path)
    record_install(setup, home, paths)
    offered = installed.found(setup.root.parent, tmp_path)["gpu_image_manifest"]
    assert offered["path"] == str((home / "gpu.json").resolve())
    setup.compute(
        {
            "choice": LOCAL_GPU,
            **paths,
            "gpu_image_manifest": offered["path"],
            "challenge": BATTERY_REF,
        }
    )
    torch_path = str((home / "torch-gpu.json").resolve())
    assert checks.calls[-2:] == [("gpu", offered["path"]), ("gpu", torch_path)]
    compute = setup._record()["compute"]
    assert compute["gpu_image"] == offered["path"]
    assert compute["extra_gpu_image"] == torch_path
    # Not stale against the installer's record, which built both.
    assert setup._stale(compute) == []
    # A path the miner names themself is checked as named, alone.
    named = home / "own-gpu.json"
    named.write_text("{}")
    setup.compute(
        {
            "choice": LOCAL_GPU,
            **paths,
            "gpu_image_manifest": str(named),
            "challenge": BATTERY_REF,
        }
    )
    assert checks.calls[-1] == ("gpu", str(named))
    assert "extra_gpu_image" not in setup._record()["compute"]


def test_without_a_pytorch_gpu_worker_the_jax_one_is_checked(tmp_path):
    setup, checks, home, paths = gpu_setup(tmp_path)
    record_install(setup, home, paths, torch=False)
    jax = str((home / "gpu.json").resolve())
    setup.compute(
        {
            "choice": LOCAL_GPU,
            **paths,
            "gpu_image_manifest": jax,
            "challenge": BATTERY_REF,
        }
    )
    assert checks.calls[-1] == ("gpu", jax)
    assert REMOTE != LOCAL_GPU  # the remote route is not touched by this


def test_a_pytorch_gpu_worker_gives_each_torch_entry_its_gpu_twin():
    torch_gpu = gpu_image("8", lock=torch_profile.GPU_LOCK_DIGEST)
    assert gpu_practice.gpu_runtime(torch_gpu) == "torch-cu130-py311"
    assert gpu_practice.gpu_runtime(gpu_image()) == "jax-cuda13-py311"
    torch_entries = [
        item
        for item in pipeline.load()["entries"]
        if item["bundle_ref"]["runtime_profile_id"] == "torch-cpu-py311"
    ]
    twins = [
        item
        for item in torch_entries
        if "torch-cu130-py311" in (item.get("bundle_refs") or {})
    ]
    assert twins, "the catalog has PyTorch entries with a GPU build"
    # The JAX GPU worker's runtime is not one any PyTorch entry builds for:
    # why --gpu with --pytorch needs the PyTorch GPU worker.
    assert not [
        item
        for item in torch_entries
        if "jax-cuda13-py311" in (item.get("bundle_refs") or {})
    ]


def test_the_installed_record_carries_both_gpu_workers(tmp_path):
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    files = {name: tmp_path / f"{name}.json" for name in ("w", "a", "g", "t")}
    for path in files.values():
        path.write_text(json.dumps({"image_id": "x"}))
    installed.write(
        state,
        image_manifest=files["w"],
        analysis_image_manifest=files["a"],
        gpu_image_manifest=files["g"],
        torch_gpu_image_manifest=files["t"],
    )
    record = installed.read(state)
    assert record["gpu_image_manifest"] == str(files["g"].resolve())
    assert record["torch_gpu_image_manifest"] == str(files["t"].resolve())
    found = installed.found(state, tmp_path)
    assert found["torch_gpu_image_manifest"]["build"].endswith(
        "scripts/dev/torch_gpu_worker_image.sh"
    )


def test_a_check_with_the_pytorch_gpu_worker_is_not_another_image(
    tmp_path, monkeypatch
):
    """The installer recorded the JAX GPU worker and, beside it, the PyTorch
    one: a compute check made with the PyTorch one is what it built."""
    from scripts.dev.miner_launchpad import environment_setup as environment
    from scripts.dev.miner_launchpad.environment_setup import (
        INSTALLATION_SCHEMA,
        write_private,
    )

    setup, _, home, _ = gpu_setup(tmp_path)
    revision = "c" * 40
    monkeypatch.setattr(environment, "checkout_revision", lambda repo=None: revision)
    jax, torch = home / "gpu.json", home / "torch-gpu.json"
    torch.write_text("{}")
    write_private(
        setup.installation_path,
        json.dumps(
            {
                "schema": INSTALLATION_SCHEMA,
                "revision": revision,
                "images": {
                    "gpu_image_manifest": {"path": str(jax)},
                    "torch_gpu_image_manifest": {"path": str(torch)},
                },
            }
        ).encode(),
    )
    drift = setup._install_drift(
        revision, {"gpu_image_manifest": str(torch)}, made="made", other="another"
    )
    assert drift == ([], False)
    other = setup._install_drift(
        revision,
        {"gpu_image_manifest": str(home / "elsewhere.json")},
        made="made",
        other="another",
    )
    assert other[0] == ["another GPU worker image than the one the installer built"]


def test_an_ordinary_install_clears_a_candidate_pin_and_says_so_to_installed(sandbox):
    """`installed write` keeps an operator's development candidate pin; the
    installer clears it for an install that is not a candidate one."""
    result = sandbox.run("--no-start")
    assert result.returncode == 0, result.stderr
    assert "--clear-development-candidate" in recorded(sandbox)


def test_the_remote_check_accepts_the_registered_pytorch_gpu_worker(
    tmp_path, monkeypatch
):
    """M1 E2E: setup refused the PyTorch GPU worker as gpu_image_unverified;
    any registered GPU worker passes the image check (the Challenge's scope
    decides what it serves), and an unregistered one is still refused."""
    from dataclasses import asdict

    from carbon.compute import remote_transport
    from scripts.dev.miner_launchpad.environment_setup import (
        LiveChecks,
        SetupRefused,
    )

    monkeypatch.setattr(
        remote_transport, "transport_for", lambda machine, **kw: "transport"
    )
    checks = LiveChecks(repo=tmp_path)
    for name, image in (
        ("torch", gpu_image("8", lock=torch_profile.GPU_LOCK_DIGEST)),
        ("jax", gpu_image()),
    ):
        manifest = tmp_path / f"{name}.json"
        manifest.write_text(
            json.dumps({**asdict(image), "schema": "carbon.c03.worker-image.v1"})
        )
        assert checks._remote(manifest, object()) == (image, "transport")
    other = tmp_path / "other.json"
    other.write_text(
        json.dumps(
            {
                **asdict(gpu_image("7", lock="sha256:" + "0" * 64)),
                "schema": "carbon.c03.worker-image.v1",
            }
        )
    )
    with pytest.raises(SetupRefused) as refused:
        checks._remote(other, object())
    assert refused.value.code == "gpu_image_unverified"


def test_gpu_without_a_driver_builds_the_workers_for_a_remote_gpu(tmp_path):
    """M1 E2E S4: a CPU-only controller driving a rented GPU. Building the
    GPU workers needs Docker only: they are built and recorded, said to be
    for a remote GPU, and this machine's GPU practice stays refused by
    setup's own driver check."""
    box = Sandbox(tmp_path)  # no nvidia-smi among its tools
    result = box.run("--gpu", "--no-start")
    assert result.returncode == 0, result.stderr
    assert "No NVIDIA driver here" in result.stdout
    assert "will not run on this machine" in result.stdout
    assert "gpu worker" in box.logged()
    assert "--gpu-image-manifest" in recorded(box)


def test_a_pytorch_gpu_build_needs_buildx_and_says_so_before_building(sandbox):
    """M1 12g: Docker 29 without buildx built a PyTorch GPU worker with its
    parent's identity, silently. --gpu with --pytorch now needs buildx,
    checked before any image is built; a JAX-only or CPU install does not."""
    docker = sandbox.tools / "docker"
    docker.write_text(
        '#!/bin/sh\ncase "$1" in buildx) echo "docker: unknown command" >&2; exit 1 ;; esac\n'
        'if [ "$*" = "info --format {{.DockerRootDir}}" ]; then\n'
        '  echo "$CARBON_TEST_DOCKER_ROOT"\nfi\nexit 0\n'
    )
    docker.chmod(0o755)
    refused = sandbox.run("--pytorch", "--gpu", "--no-start")
    assert refused.returncode == 2
    assert "needs Docker buildx" in refused.stderr
    assert "docker-buildx-plugin" in refused.stderr
    assert not any("worker" in line for line in sandbox.logged())
    # A CPU-only --pytorch install, then a JAX-only GPU one: neither needs
    # buildx. (After a GPU worker is built here, a --pytorch install builds
    # the PyTorch GPU worker too, and then needs it.)
    for args in (("--pytorch",), ("--gpu",)):
        allowed = sandbox.run(*args, "--no-start")
        assert allowed.returncode == 0, allowed.stderr
    again = sandbox.run("--pytorch", "--no-start")
    assert again.returncode == 2 and "needs Docker buildx" in again.stderr
