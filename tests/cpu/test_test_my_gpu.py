"""Test my GPU (OWNER-TEST-MY-GPU-01).

The miner, or their agent on their say-so, runs each GPU worker framework
once on their own GPU - this machine, or their own remote machine - to learn
whether it works, before practising. These tests hold:
- it is offered by status with exactly what it runs, and runs only on
  consent naming that; never from the compute check;
- each framework's run is the pinned worker, once, in a hardened container
  (one GPU, no network, read-only root, no capabilities, bounded time), on
  public synthetic data it makes itself - nothing mounted, no exam or bank;
- a plain verdict per framework, with the driver advice where the driver is
  older than the worker's CUDA runtime;
- it writes no score and no ledger: only setup's record of the verdicts.
Scripts run for real in bash against a fake docker and nvidia-smi.
"""

from __future__ import annotations

import json

import pytest
from test_gpu_per_backend import JAX, TORCH, record
from test_miner_launchpad_environment_setup import Checks, Onboarding
from test_remote_gpu_probe import IMAGE, fake_host, run

from carbon.compute.remote_machine import (
    GPU_TEST_DRIVER_TOO_OLD,
    GPU_TEST_FAILED,
    GPU_TEST_PROGRAMS,
    NO_WORKER_IMAGE,
    gpu_test_script,
)
from scripts.dev.miner_launchpad import setup_operations
from scripts.dev.miner_launchpad.environment_setup import (
    LOCAL_GPU,
    REMOTE,
    EnvironmentSetup,
    SetupRefused,
)

DRIVER = (
    "cudaErrorInsufficientDriver : CUDA driver version is insufficient for CUDA "
    "runtime version"
)


@pytest.mark.parametrize(
    ("output", "rc", "expected"),
    [("1", 0, 0), (DRIVER, 1, GPU_TEST_DRIVER_TOO_OLD), ("boom", 1, GPU_TEST_FAILED)],
    ids=["works", "driver-too-old", "does-not-work"],
)
def test_one_framework_runs_once_hardened_on_synthetic_data(
    tmp_path, output, rc, expected
):
    env = fake_host(tmp_path, output, rc)
    code, stdout = run(gpu_test_script(IMAGE, "jax"), env)
    assert code == expected
    assert b"carbon-driver-cuda 12.8" in stdout
    runs = [
        line
        for line in (tmp_path / "docker.log").read_text().splitlines()
        if line.startswith("run ")
    ]
    assert len(runs) == 1
    for flag in (
        "--rm",
        "--network none",
        "--read-only",
        "--cap-drop ALL",
        "no-new-privileges",
        "device=GPU-0123abcd-4567-89ef",
        IMAGE,
    ):
        assert flag in runs[0]
    # Nothing is mounted into it: no exam, bank or campaign data can reach it.
    assert " -v " not in runs[0] and "--mount" not in runs[0]


def test_the_programs_make_their_own_synthetic_data():
    assert set(GPU_TEST_PROGRAMS) == {"jax", "pytorch"}
    for program in GPU_TEST_PROGRAMS.values():
        assert "open(" not in program and "load" not in program
        assert "ones(" in program


def test_a_missing_worker_is_said_before_anything_runs(tmp_path):
    env = fake_host(tmp_path, "unused", 0)
    other = "sha256:" + "b" * 64
    code, _ = run(gpu_test_script(other, "pytorch"), env)
    assert code == NO_WORKER_IMAGE
    assert "run " not in (tmp_path / "docker.log").read_text()


class GpuChecks(Checks):
    """Fixture checks: the JAX worker meets an old driver, PyTorch works."""

    def __init__(self):
        super().__init__()
        self.tested = []

    def test_gpu(self, script, machine=None):
        self.tested.append((script, machine))
        if "import jax" in script:
            return GPU_TEST_DRIVER_TOO_OLD, b"carbon-driver-cuda 12.8\n"
        return 0, b"carbon-driver-cuda 12.8\n"


@pytest.fixture
def gpu_setup(tmp_path):
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    checks = GpuChecks()
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=checks)
    images = tmp_path / "images"
    images.mkdir(mode=0o700)
    record(images, "jax.json", JAX)
    record(images, "torch.json", TORCH)
    setup._save(
        {
            "hotkey": "5Hotkey",
            "compute": {
                "choice": LOCAL_GPU,
                "gpu_image": str(images / "jax.json"),
                "extra_gpu_image": str(images / "torch.json"),
                "checked_at": 1,
            },
        }
    )
    return setup, checks, state


def test_status_offers_exactly_what_runs_and_runs_nothing(gpu_setup):
    setup, checks, _ = gpu_setup
    offer = setup.gpu_test_offer()
    assert offer["where"] == {"this_machine": True}
    assert [w["backend"] for w in offer["workers"]] == ["jax", "pytorch"]
    assert offer["workers"][0]["command"] == gpu_test_script(JAX.image_id, "jax")
    view = setup_operations.status(setup, door=setup_operations.MCP)
    assert view["test_gpu"]["call"]["tool"] == "carbon_setup_test_gpu"
    assert view["test_gpu"]["consent"] == {"test": offer}
    assert view["test_gpu"]["last"] is None
    assert checks.tested == []


def test_it_runs_only_on_consent_naming_what_runs(gpu_setup):
    setup, checks, _ = gpu_setup
    offer = setup.gpu_test_offer()
    changed = {
        "test": {**offer, "workers": [{**offer["workers"][0], "command": "rm -rf /"}]}
    }
    for consent in ({}, changed, {"test": {**offer, "where": {"remote": {}}}}):
        with pytest.raises(SetupRefused) as refused:
            setup.test_gpu({"consent": consent})
        assert refused.value.code == "consent_must_name_what_runs"
    assert checks.tested == []


def test_a_plain_verdict_per_framework_with_driver_advice_and_no_ledger(gpu_setup):
    setup, checks, state = gpu_setup
    before = {p.relative_to(state) for p in state.rglob("*")}
    offer = setup.gpu_test_offer()
    result = setup.test_gpu({"consent": {"test": offer}})["gpu_test"]
    jax, torch = result["verdicts"]
    assert (jax["backend"], jax["verdict"], jax["code"]) == (
        "jax",
        "does_not_work",
        "gpu_driver_too_old",
    )
    assert "CUDA 12.8" in jax["next_step"] and "update the driver" in jax["next_step"]
    assert (torch["backend"], torch["verdict"]) == ("pytorch", "works")
    assert "code" not in torch and torch["driver_cuda"] == "12.8"
    # Each framework ran once, on this machine, exactly as consented.
    assert [script for script, _ in checks.tested] == [
        w["command"] for w in offer["workers"]
    ]
    assert all(machine is None for _, machine in checks.tested)
    # No score, no ledger: setup's own record is the only file it touched.
    after = {p.relative_to(state) for p in state.rglob("*")}
    assert after - before <= {(setup.root / "setup.lock").relative_to(state)}
    saved = json.loads((setup.root / "setup.json").read_bytes())
    assert saved["gpu_test"]["verdicts"] == result["verdicts"]
    assert "score" not in json.dumps(result)
    view = setup_operations.status(setup, door=setup_operations.HTTP)
    assert view["test_gpu"]["last"]["verdicts"] == result["verdicts"]


def test_without_a_gpu_compute_step_it_is_not_offered(gpu_setup):
    setup, _, _ = gpu_setup
    saved = json.loads((setup.root / "setup.json").read_bytes())
    setup._save({**saved, "compute": {**saved["compute"], "choice": "local-cpu"}})
    assert setup.gpu_test_offer() is None
    assert setup_operations.status(setup, door="mcp")["test_gpu"] is None
    with pytest.raises(SetupRefused) as refused:
        setup.test_gpu({"consent": {"test": {}}})
    assert refused.value.code == "gpu_compute_not_checked"
    # A remote container (no Docker of its own) is not offered either.
    remote = {"transport": "ssh-container", "destination": "me@box"}
    setup._save(
        {
            **saved,
            "compute": {**saved["compute"], "choice": REMOTE, "remote_machine": remote},
        }
    )
    assert setup.gpu_test_offer() is None


def test_it_is_a_setup_operation_on_both_doors_never_the_compute_check():
    op = setup_operations.SETUP_OPERATIONS["test_gpu"]
    assert (op.tier, op.step, op.required) == (
        setup_operations.REGISTERED,
        "compute",
        frozenset({"consent"}),
    )
    import inspect

    from scripts.dev.miner_launchpad import environment_setup

    source = inspect.getsource(environment_setup.EnvironmentSetup.compute)
    assert "test_gpu" not in source and "gpu_test_script" not in source


def test_a_framework_that_fails_otherwise_says_so_with_its_step(gpu_setup):
    setup, checks, _ = gpu_setup
    checks.test_gpu = lambda script, machine=None: (GPU_TEST_FAILED, b"")
    offer = setup.gpu_test_offer()
    verdicts = setup.test_gpu({"consent": {"test": offer}})["gpu_test"]["verdicts"]
    assert {v["code"] for v in verdicts} == {"gpu_test_failed"}
    assert all("NVIDIA Container Toolkit" in v["next_step"] for v in verdicts)
    assert all(v["verdict"] == "does_not_work" for v in verdicts)
