"""The receiver's grading rebuild of a catalog entry runs on its official-grade GPU twin
(OWNER-NO-LAUNCH-WITHOUT-GPU-REBUILD-01; GPU_REBUILD_RULINGS_20261026).

Claims: a catalog recipe expands to the entry's GPU build for the first GPU runtime the receiver holds that has
an OFFICIAL-GRADE build, else to the CPU build (always official); a smoke-only or unreceipted twin is never
chosen; a receiver may hold CPU parents beside GPU ones and each bundle builds on the accelerator of its own
runtime's parent; the GPU workers are configured beside the CPU pair, verified like the receiver's other workers,
and the receiver refuses to start on a device class without the owner's hardware acceptance.
"""

from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest
from test_backbone_catalog_recipe import recipe as catalog_recipe
from test_battery_gpu_practice import gpu_image
from test_direct_parents import torch_image

from carbon.backbone_catalog import served
from carbon.backbone_catalog.entries import CatalogRefused
from carbon.development_session import gpu_practice
from carbon.development_session.research_carrier import MINER_GPU
from carbon.development_session.research_tasks import DirectDevelopmentTasksV3
from carbon.reconstruction import torch_profile

TORCH_GPU = gpu_image("8", lock=torch_profile.GPU_LOCK_DIGEST)
JAX_GPU = gpu_image("9")
TWIN = {
    "schema": "carbon.library-bundle-ref.v1",
    "bundle_digest": "sha256:" + "7" * 64,
    "language": "python",
    "runtime_profile_id": "torch-cu130-py311",
    "environment_digest": "sha256:" + "8" * 64,
}


def _official(monkeypatch, answers):
    """`runtime_bundle_ref(..., official=True)` answers per runtime: a ref or a refusal."""
    real = served.runtime_bundle_ref

    def pick(item, runtime, *, official):
        assert official is True
        answer = answers.get(runtime)
        if answer is None:
            return real(item, runtime, official=True)
        if isinstance(answer, Exception):
            raise answer
        return dict(answer)

    monkeypatch.setattr(served, "runtime_bundle_ref", pick)


def _refused():
    return CatalogRefused("catalog_runtime_not_reproducible", "practice only")


# ---- the expansion ----------------------------------------------------------------------


def test_the_entrys_official_gpu_twin_is_the_grading_build(monkeypatch):
    _official(monkeypatch, {"torch-cu130-py311": TWIN})
    expanded, runtime = served.expand_official(catalog_recipe(), ("torch-cu130-py311",))
    assert runtime == "torch-cu130-py311"
    assert expanded["source"]["bundle_ref"] == TWIN
    cpu = served.expand(catalog_recipe())
    assert cpu["source"]["bundle_ref"] != TWIN
    # nothing but the bundle ref differs: same entry point, settings, output, challenge
    for key in ("schema", "challenge", "procedure", "output"):
        assert expanded[key] == cpu[key]
    assert expanded["source"]["kind"] == "bundle"


def test_without_an_official_twin_or_a_gpu_parent_the_cpu_build_grades(monkeypatch):
    cpu = served.expand(catalog_recipe())
    _official(monkeypatch, {"torch-cu130-py311": _refused()})
    assert served.expand_official(catalog_recipe(), ("torch-cu130-py311",)) == (
        cpu,
        None,
    )
    assert served.expand_official(catalog_recipe(), ()) == (cpu, None)
    assert served.expand_official(catalog_recipe()) == (cpu, None)


def test_the_first_runtime_with_an_official_build_wins(monkeypatch):
    _official(
        monkeypatch,
        {"jax-cuda13-py311": _refused(), "torch-cu130-py311": TWIN},
    )
    _, runtime = served.expand_official(
        catalog_recipe(), ("jax-cuda13-py311", "torch-cu130-py311")
    )
    assert runtime == "torch-cu130-py311"


def test_the_real_data_never_picks_a_twin_without_its_official_receipt():
    # No monkeypatch: every Motor 1.2 entry's GPU build is judged by its real receipt.
    cpu = served.expand(catalog_recipe())
    expanded, runtime = served.expand_official(catalog_recipe(), ("torch-cu130-py311",))
    if runtime is None:
        assert expanded == cpu
    else:  # only a build that passed the official-grade test can be chosen
        from carbon.backbone_catalog import gpu_receipt, listing

        item = listing.entry("neuralop.FNO", "electric-motor-magnetics", "1.2")
        receipt = gpu_receipt.load(item["catalog_id"], runtime)
        assert gpu_receipt.official_grade_problem(receipt, runtime) is None


def test_a_recipe_the_catalog_refuses_is_still_refused(monkeypatch):
    bad = copy.deepcopy(catalog_recipe())
    bad["source"]["catalog_id"] = "nope.Nope"
    _official(monkeypatch, {"torch-cu130-py311": TWIN})
    with pytest.raises(CatalogRefused):
        served.expand_official(bad, ("torch-cu130-py311",))


# ---- the receiver --------------------------------------------------------------------


def test_the_adapter_asks_the_receiver_which_gpu_runtimes_it_holds():
    from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter

    held = SimpleNamespace(provider_for=SimpleNamespace(gpu_runtimes=lambda: ["a"]))
    assert LeanRecipeAdapter._gpu_runtimes(held) == ("a",)
    for plain in (lambda hotkey: None, SimpleNamespace()):
        assert (
            LeanRecipeAdapter._gpu_runtimes(SimpleNamespace(provider_for=plain)) == ()
        )


def test_owner_providers_report_the_gpu_runtimes_of_their_parents():
    from carbon.challenge_validator.direct_receiver import OwnerProviders

    cpu = torch_image()
    mixed = gpu_practice.with_gpu_parent(
        gpu_practice.DirectParents.from_torch(cpu), (TORCH_GPU, JAX_GPU)
    )
    receiver = object.__new__(OwnerProviders)
    receiver.parent, receiver.parents = cpu, mixed
    assert receiver.gpu_runtimes() == ("jax-cuda13-py311", "torch-cu130-py311")
    receiver.parents = gpu_practice.DirectParents.from_torch(cpu)
    assert receiver.gpu_runtimes() == ()
    # a single-parent receiver whose one parent is a GPU worker
    receiver.parent, receiver.parents = TORCH_GPU, None
    assert receiver.gpu_runtimes() == ("torch-cu130-py311",)
    receiver.parent = cpu
    assert receiver.gpu_runtimes() == ()


# ---- per-bundle accelerators in one provider -----------------------------------------


def _provider(parents):
    provider = SimpleNamespace(
        construction_parents=parents,
        construction_parent=None,
        inference_image=torch_image(),
        image_resolver=lambda bundle: None,
        image=None,
    )
    provider._parent_for = lambda bundle: DirectDevelopmentTasksV3._parent_for(
        provider, bundle
    )
    provider._build_accelerator_for = (
        lambda bundle: DirectDevelopmentTasksV3._build_accelerator_for(provider, bundle)
    )
    return provider


def _bundle(runtime):
    return SimpleNamespace(runtime_profile_id=runtime)


def test_a_receiver_may_hold_cpu_parents_beside_gpu_ones():
    cpu = torch_image()
    mixed = gpu_practice.with_gpu_parent(
        gpu_practice.DirectParents.from_torch(cpu), (TORCH_GPU,)
    )
    provider = _provider(mixed)
    DirectDevelopmentTasksV3._check_image_identity(provider)
    # the grade stays on the CPU inference image; the build accelerator is per bundle
    assert provider.inference_accelerator is None
    assert provider.build_accelerator is None  # mixed: no single answer
    assert provider._build_accelerator_for(_bundle("torch-cu130-py311")) == MINER_GPU
    assert provider._build_accelerator_for(_bundle("torch-cpu-py311")) is None
    assert provider._build_accelerator_for(_bundle("python-cpu-py311")) is None


def test_a_single_lane_receiver_is_what_it_was():
    cpu_only = _provider(gpu_practice.DirectParents.from_torch(torch_image()))
    DirectDevelopmentTasksV3._check_image_identity(cpu_only)
    assert cpu_only.build_accelerator is None and cpu_only.inference_accelerator is None
    gpu_only = _provider(gpu_practice.DirectParents({"torch-cu130-py311": TORCH_GPU}))
    DirectDevelopmentTasksV3._check_image_identity(gpu_only)
    assert gpu_only.build_accelerator == MINER_GPU


def test_a_gpu_inference_image_is_still_one_accelerator_for_every_parent():
    provider = _provider(gpu_practice.DirectParents.from_torch(torch_image()))
    provider.inference_image = JAX_GPU
    DirectDevelopmentTasksV3._check_image_identity(provider)
    assert provider.inference_accelerator == MINER_GPU


# ---- the configuration ---------------------------------------------------------------


def _config(tmp_path, **extra):
    from test_direct_receiver import _config as base

    return {**base(tmp_path), **extra}


def test_gpu_construction_images_need_the_cpu_pair_and_exact_manifests(
    tmp_path, monkeypatch
):
    from carbon.challenge_validator import direct_receiver as receiver

    manifest = tmp_path / "gpu.json"
    manifest.write_text("{}")
    good = _config(
        tmp_path,
        construction_runtimes=receiver.CONSTRUCTION_RUNTIMES,
        gpu_construction_images=[str(manifest)],
    )
    monkeypatch.setattr(receiver, "private_json", lambda _: good)
    assert receiver.load_config(tmp_path / "c.json") == good
    for bad in (
        {**good, "construction_runtimes": None},  # no CPU pair
        {**good, "gpu_construction_images": []},
        {**good, "gpu_construction_images": [str(manifest)] * 3},
        {**good, "gpu_construction_images": str(manifest)},
        {**good, "gpu_construction_images": [str(tmp_path / "missing.json")]},
        {**good, "gpu_construction_images": ["relative.json"]},
    ):
        if bad["construction_runtimes"] is None:
            bad.pop("construction_runtimes")
        monkeypatch.setattr(receiver, "private_json", lambda _, bad=bad: bad)
        with pytest.raises(ValueError):
            receiver.load_config(tmp_path / "c.json")


def _gpu_setup(monkeypatch, tmp_path, images, *, device_kind="NVIDIA GeForce RTX 4090"):
    from carbon.challenge_validator import direct_receiver as receiver
    from carbon.development_session import research_campaign, research_carrier
    from carbon.reconstruction.worker import docker_runtime

    by_path = {}
    for number, image in enumerate(images):
        path = tmp_path / f"image-{number}.json"
        by_path[str(path)] = image
    monkeypatch.setattr(
        docker_runtime, "load_image_identity", lambda p: by_path[str(p)]
    )
    monkeypatch.setattr(
        docker_runtime, "doctor", lambda **_: SimpleNamespace(eligible=True)
    )
    monkeypatch.setattr(research_campaign, "verify_current_worker", lambda *_: None)
    monkeypatch.setattr(
        research_campaign, "verify_direct_v13_worker", lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        research_carrier,
        "_gpu_device",
        lambda: SimpleNamespace(device_kind=device_kind, digest="sha256:" + "4" * 64),
    )
    cfg = {"gpu_construction_images": list(by_path)}
    return receiver, cfg


def test_configured_gpu_workers_become_parents_beside_the_cpu_pair(
    monkeypatch, tmp_path
):
    receiver, cfg = _gpu_setup(monkeypatch, tmp_path, [TORCH_GPU, JAX_GPU])
    cpu = gpu_practice.DirectParents.from_torch(torch_image())
    parents, device = receiver.gpu_construction_parents(cfg, {}, cpu, "testnet")
    assert set(parents.runtimes()) == {
        "torch-cpu-py311",
        "python-cpu-py311",
        "torch-cu130-py311",
        "jax-cuda13-py311",
    }
    assert parents.for_runtime("torch-cu130-py311") == TORCH_GPU
    assert device.device_kind == "NVIDIA GeForce RTX 4090"


def test_an_unaccepted_device_class_or_network_never_starts_the_gpu_workers(
    monkeypatch, tmp_path
):
    from carbon.reconstruction.hardware_acceptance import DeviceClassNotAccepted

    cpu = gpu_practice.DirectParents.from_torch(torch_image())
    receiver, cfg = _gpu_setup(
        monkeypatch, tmp_path, [TORCH_GPU], device_kind="NVIDIA H100 PCIe"
    )
    with pytest.raises(DeviceClassNotAccepted):
        receiver.gpu_construction_parents(cfg, {}, cpu, "testnet")
    receiver, cfg = _gpu_setup(monkeypatch, tmp_path, [TORCH_GPU])
    with pytest.raises(DeviceClassNotAccepted):
        receiver.gpu_construction_parents(cfg, {}, cpu, "mainnet")


def test_a_non_gpu_worker_or_two_of_one_backend_is_refused(monkeypatch, tmp_path):
    cpu = gpu_practice.DirectParents.from_torch(torch_image())
    receiver, cfg = _gpu_setup(monkeypatch, tmp_path, [torch_image()])
    with pytest.raises(ValueError, match="registered GPU worker"):
        receiver.gpu_construction_parents(cfg, {}, cpu, "testnet")
    receiver, cfg = _gpu_setup(
        monkeypatch,
        tmp_path,
        [TORCH_GPU, gpu_image("6", lock=torch_profile.GPU_LOCK_DIGEST)],
    )
    with pytest.raises(ValueError, match="one registered GPU worker per backend"):
        receiver.gpu_construction_parents(cfg, {}, cpu, "testnet")
