"""One GPU worker per installed backend (Validator ruling; launch must: GPU
for every Challenge, backend parity).

A profile carries the JAX GPU worker and, beside it, the PyTorch one; each
catalog entry practises on the worker of its own backend: a PyTorch entry's
twin on the PyTorch worker, a jno.* entry's on the JAX worker. These tests
hold:
- `device_build` picks the entry's GPU build by backend among the declared
  workers, and gives the typed `catalog_gpu_build_missing` when the entry
  has a build for none of them;
- a runtime declares one GPU scope per worker (distinct backends), the
  campaign root holds one record per worker, and the registered images are
  verified against them; a single-worker runtime and profile read exactly
  as before (migration, not refusal);
- the remote route runs one remote runner per worker and routes each run to
  the one whose image it names;
- the runner profile carries `extra_gpu_image` exactly when the runtime
  declares a second GPU scope;
- setup checks both workers when the installer built both.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest
from test_battery_gpu_practice import Checks, Onboarding, gpu_image

from carbon.backbone_catalog.served import GpuBuildMissing
from carbon.development_session import catalog_gpu, gpu_practice
from carbon.reconstruction import torch_profile

MOTOR = {"id": "electric-motor-magnetics", "version": "1.3"}
JAX = gpu_image("9")
TORCH = gpu_image("8", lock=torch_profile.GPU_LOCK_DIGEST)


# --- device_build: by the entry's backend ----------------------------------------


class Overlay:
    """A stand-in for a verified overlay of the entry's GPU build."""


class Parents:
    def __init__(self, practice):
        self.practice = practice

    def for_bundle(self, bundle):
        return ("parent", bundle)


class Practice:
    def __init__(self, workers):
        self.gpu_image = workers

    def parents(self):
        return Parents(self)

    def _resolve(self, bundle):
        return Overlay() if bundle != "cpu" else "cpu image"


def entry(builds):
    """`expand_for` of an entry with GPU builds for `builds` (runtimes)."""

    def expand_for(runtime):
        if runtime is not None and runtime not in builds:
            raise GpuBuildMissing("entry", runtime)
        return {"source": {"bundle_ref": runtime or "cpu"}}

    return expand_for


@pytest.fixture
def overlays(monkeypatch):
    from carbon.development_session import library_environment_cache

    monkeypatch.setattr(library_environment_cache, "VerifiedLibraryOverlay", Overlay)


def test_each_entry_practises_on_the_worker_of_its_backend(overlays):
    practice = Practice((JAX, TORCH))
    torch_entry = entry({"torch-cu130-py311"})
    jno_entry = entry({"jax-cuda13-py311"})
    for expand_for, runtime in (
        (torch_entry, "torch-cu130-py311"),
        (jno_entry, "jax-cuda13-py311"),
    ):
        _, bundle, image, _, accelerator, note = gpu_practice.device_build(
            practice, expand_for, lambda ref: ref
        )
        assert bundle == runtime and type(image) is Overlay
        assert accelerator is not None and note is None


def test_an_entry_with_no_build_for_any_worker_gives_the_typed_note(overlays):
    practice = Practice((JAX, TORCH))
    _, bundle, _, _, accelerator, note = gpu_practice.device_build(
        practice, entry(set()), lambda ref: ref
    )
    assert (bundle, accelerator, note) == ("cpu", None, "catalog_gpu_build_missing")
    # The backend the host has no worker for: the same typed note.
    single = Practice(JAX)
    *_, accelerator, note = gpu_practice.device_build(
        single, entry({"torch-cu130-py311"}), lambda ref: ref
    )
    assert (accelerator, note) == (None, "catalog_gpu_build_missing")


def test_a_single_worker_host_is_unchanged(overlays):
    *_, accelerator, note = gpu_practice.device_build(
        Practice(TORCH), entry({"torch-cu130-py311"}), lambda ref: ref
    )
    assert accelerator is not None and note is None
    assert gpu_practice.gpu_images(None) == ()
    assert gpu_practice.gpu_images(TORCH) == (TORCH,)
    with pytest.raises(ValueError, match="one registered GPU worker per backend"):
        gpu_practice.gpu_images((JAX, JAX))


def test_each_worker_is_the_parent_of_its_runtime():
    parents = gpu_practice.DirectParents({})
    both = gpu_practice.with_gpu_parent(parents, (JAX, TORCH))
    assert both.for_runtime("jax-cuda13-py311") == JAX
    assert both.for_runtime("torch-cu130-py311") == TORCH


# --- the runtime, the records, the registered images ----------------------------


def record(root, name, image):
    path = root / name
    path.write_text(
        json.dumps({**asdict(image), "schema": "carbon.c03.worker-image.v1"})
    )
    path.chmod(0o600)


def test_two_scopes_two_records_two_registered_workers(tmp_path):
    root = tmp_path / "campaign"
    root.mkdir(mode=0o700)
    runtime = catalog_gpu.with_gpu({}, {"gpu_research": []}, MOTOR["id"], (JAX, TORCH))
    scopes = runtime["gpu_research"]
    assert [s["backend"] for s in scopes] == ["jax", "pytorch"]
    assert catalog_gpu.declared_scope(runtime) == scopes
    record(root, "gpu-worker-image.json", JAX)
    record(root, "extra-gpu-worker-image.json", TORCH)
    assert catalog_gpu.registered_gpu_image(root, runtime, MOTOR["id"]) == (
        JAX,
        TORCH,
    )
    # Two scopes of one backend are refused.
    with pytest.raises(ValueError, match="exact catalog GPU practice scope"):
        catalog_gpu.declared_scope({"gpu_research": [scopes[0], scopes[0]]})


def test_an_older_single_worker_runtime_reads_as_before(tmp_path):
    """Migration, not refusal: a profile written before one worker per
    backend - its one worker JAX, or the PyTorch one a0d9590de selected."""
    root = tmp_path / "campaign"
    root.mkdir(mode=0o700)
    for image in (JAX, TORCH):
        runtime = catalog_gpu.with_gpu({}, {"gpu_research": []}, MOTOR["id"], image)
        record(root, "gpu-worker-image.json", image)
        assert catalog_gpu.registered_gpu_image(root, runtime, MOTOR["id"]) == image


# --- the remote route: one runner per worker -------------------------------------


def test_the_remote_route_runs_each_worker_on_its_own_runner(monkeypatch):
    from carbon.compute import remote_route
    from carbon.compute.remote_runner import RemoteRunner, RemoteWorker
    from carbon.compute.remote_transport import SSH_DOCKER
    from carbon.development_session.catalog_gpu import RemotePractice

    declared = {
        "gpu_research": [catalog_gpu.gpu_scope(MOTOR["id"], i) for i in (JAX, TORCH)],
        "remote_gpu": [
            remote_route.remote_scope(MOTOR["id"], i, SSH_DOCKER) for i in (JAX, TORCH)
        ],
    }
    assert len(remote_route.declared_remotes(declared)) == 2
    assert remote_route.declared_remote(declared)["image"] == JAX.image_id

    class Machine:
        transport = SSH_DOCKER

    monkeypatch.setattr(
        remote_route.RemoteMachine, "from_document", staticmethod(lambda d: Machine())
    )
    monkeypatch.setattr(remote_route, "transport_for", lambda machine, **kw: "ssh")

    class Campaign:
        class key:
            challenge_id = MOTOR["id"]

        @staticmethod
        def remote_worker(image):
            return RemoteWorker(image=image)

    runners = remote_route.campaign_runner(
        Campaign, runtime=declared, machine={}, gpu_image=(JAX, TORCH)
    )
    assert [r.image_id for r in runners] == [JAX.image_id, TORCH.image_id]
    seen = []
    monkeypatch.setattr(
        RemoteRunner, "__call__", lambda self, ledger, **kw: seen.append(self.image_id)
    )

    def runner(image):
        return RemoteRunner(transport="ssh", worker=RemoteWorker(image=image))

    routed = RemotePractice(
        (runner(JAX), runner(TORCH)),
        local=lambda ledger, **kwargs: seen.append("local"),
    )
    with pytest.raises(ValueError):
        RemotePractice((runner(JAX), runner(JAX)))
    for image in (TORCH, JAX, gpu_image("7")):
        routed("ledger", image=image)
    assert seen == [TORCH.image_id, JAX.image_id, "local"]


# --- the runner profile ---------------------------------------------------------


def test_the_profile_carries_the_extra_worker_exactly_with_a_second_scope(tmp_path):
    from scripts.dev.miner_launchpad import runner

    scope = catalog_gpu.gpu_scope(MOTOR["id"], JAX)
    extra = catalog_gpu.gpu_scope(MOTOR["id"], TORCH)
    for scopes, fields, ok in (
        ([scope], {"gpu_image"}, True),
        ([scope, extra], {"gpu_image", "extra_gpu_image"}, True),
        ([scope, extra], {"gpu_image"}, False),
        ([scope], {"gpu_image", "extra_gpu_image"}, False),
        ([scope, extra], {"extra_gpu_image"}, False),
    ):
        cfg = {field: str(tmp_path / f"{field}.json") for field in fields}
        runtime = {"gpu_research": scopes}
        if ok:
            runner.image_records_declared(cfg, runtime)
        else:
            with pytest.raises(ValueError):
                runner.image_records_declared(cfg, runtime)
    assert "extra_gpu_image" in runner.OPTIONAL_PROFILE_FIELDS
    assert runner.RESEARCH_IMAGE_RECORDS["extra_gpu_image"] == (
        "gpu_research",
        "extra-gpu-worker-image.json",
    )


# --- setup: both workers checked --------------------------------------------------


class BothChecks(Checks):
    """GPU checks that read each worker from its manifest's backend."""

    def gpu(self, manifest, campaign=None):
        self.calls.append(("gpu", str(manifest)))
        image = TORCH if Path(manifest).name.startswith("torch") else JAX
        return {
            "scope": campaign.gpu_scope(image),
            "device_kind": "NVIDIA GeForce RTX 4090",
            "record_digest": "sha256:" + "4" * 64,
        }


def test_setup_checks_both_workers_and_declares_both_scopes(tmp_path):
    from test_battery_gpu_practice import HOTKEY

    from scripts.dev.miner_launchpad import installed
    from scripts.dev.miner_launchpad.environment_setup import (
        LOCAL_GPU,
        EnvironmentSetup,
    )

    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    home = tmp_path / "miner"
    home.mkdir(mode=0o700)
    for name in ("worker.json", "analysis.json", "gpu.json", "torch-gpu.json"):
        (home / name).write_text("{}")
    checks = BothChecks()
    setup = EnvironmentSetup(root, onboarding=Onboarding(), checks=checks)
    setup.begin({"address": HOTKEY})
    installed.write(
        root,
        image_manifest=home / "worker.json",
        analysis_image_manifest=home / "analysis.json",
        gpu_image_manifest=home / "gpu.json",
        torch_gpu_image_manifest=home / "torch-gpu.json",
    )
    jax = str((home / "gpu.json").resolve())
    setup.compute(
        {
            "choice": LOCAL_GPU,
            "image_manifest": str(home / "worker.json"),
            "analysis_image_manifest": str(home / "analysis.json"),
            "gpu_image_manifest": jax,
            "challenge": MOTOR,
        }
    )
    torch_path = str((home / "torch-gpu.json").resolve())
    assert [call for call in checks.calls if call[0] == "gpu"] == [
        ("gpu", jax),
        ("gpu", torch_path),
    ]
    compute = setup._record()["compute"]
    assert compute["gpu_image"] == jax and compute["extra_gpu_image"] == torch_path
    assert [s["backend"] for s in compute["runtime"]["gpu_research"]] == [
        "jax",
        "pytorch",
    ]
    assert setup._stale(compute) == []


def test_a_pytorch_worker_setup_cannot_use_is_said_not_dropped(tmp_path):
    """M1 12g: the PyTorch GPU worker read as unregistered (its identity step
    had not run) and setup dropped it without a word, so only the JAX worker
    was offered. The check now says so, with the step that fixes it."""
    from test_battery_gpu_practice import HOTKEY

    from scripts.dev.miner_launchpad import installed
    from scripts.dev.miner_launchpad.environment_setup import (
        LOCAL_GPU,
        EnvironmentSetup,
        SetupRefused,
    )

    class Unregistered(BothChecks):
        def gpu(self, manifest, campaign=None):
            if Path(manifest).name.startswith("torch"):
                raise SetupRefused("gpu_image_manifest", "gpu_image_unverified")
            return super().gpu(manifest, campaign)

    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    home = tmp_path / "miner"
    home.mkdir(mode=0o700)
    for name in ("worker.json", "analysis.json", "gpu.json", "torch-gpu.json"):
        (home / name).write_text("{}")
    setup = EnvironmentSetup(root, onboarding=Onboarding(), checks=Unregistered())
    setup.begin({"address": HOTKEY})
    installed.write(
        root,
        image_manifest=home / "worker.json",
        analysis_image_manifest=home / "analysis.json",
        gpu_image_manifest=home / "gpu.json",
        torch_gpu_image_manifest=home / "torch-gpu.json",
    )
    setup.compute(
        {
            "choice": LOCAL_GPU,
            "image_manifest": str(home / "worker.json"),
            "analysis_image_manifest": str(home / "analysis.json"),
            "gpu_image_manifest": str((home / "gpu.json").resolve()),
            "challenge": MOTOR,
        }
    )
    compute = setup._record()["compute"]
    assert "extra_gpu_image" not in compute
    refused = compute["check"]["extra_gpu_refused"]
    assert refused["code"] == "gpu_image_unverified"
    assert "DOCKER_BUILDKIT=1" in refused["next_step"]
