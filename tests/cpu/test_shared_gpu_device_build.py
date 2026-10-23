"""One shared GPU practice path (Lead/owner, 2026-10-22), stage S1: the
device choice every Challenge's catalog practice makes, by runtime only."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from carbon.backbone_catalog import served
from carbon.development_session import gpu_practice


def test_the_gpu_runtime_is_registered_for_the_pytorch_gpu_parent():
    assert gpu_practice.DIRECT_RUNTIMES["torch-cu130-py311"] == "pytorch"
    assert gpu_practice.DIRECT_RUNTIMES["jax-cuda13-py311"] == "jax"
    assert gpu_practice.GPU_RUNTIMES == {
        "pytorch": "torch-cu130-py311",
        "jax": "jax-cuda13-py311",
    }
    assert gpu_practice.gpu_runtime(None) is None


def test_an_entry_without_a_gpu_build_is_refused_typed_and_cpu_is_unchanged():
    item = {"catalog_id": "x", "bundle_ref": {"runtime_profile_id": "torch-cpu-py311"}}
    assert served._bundle_ref(item, None) is item["bundle_ref"]
    with pytest.raises(served.GpuBuildMissing) as refused:
        served._bundle_ref(item, "torch-cu130-py311")
    assert refused.value.code == "catalog_gpu_build_missing"
    gpu = {"runtime_profile_id": "torch-cu130-py311", "bundle_digest": "sha256:g"}
    # A GPU ref with no receipt is not served for practice either (Validator, 2026-10-22): a build never shown to
    # run on a GPU is not offered, and the typed GAP names the CPU build. A receipted build is served
    # (tests/cpu/test_backbone_catalog_practice_runtime.py).
    with pytest.raises(served.GpuBuildNotOffered) as refused:
        served._bundle_ref(
            {**item, "bundle_refs": {"torch-cu130-py311": gpu}}, "torch-cu130-py311"
        )
    assert refused.value.code == "catalog_gpu_build_not_offered"


class _Practice:
    def __init__(self, gpu_image, resolved):
        self.gpu_image, self.resolved = gpu_image, resolved

    def _resolve(self, bundle):
        image = self.resolved.get(bundle)
        if image is None:
            raise FileNotFoundError("not installed")
        return image

    def parents(self):
        return SimpleNamespace(for_bundle=lambda bundle: "parent-of-" + bundle)


def _expand_for(runtime):
    return {"source": {"bundle_ref": "gpu" if runtime else "cpu"}}


def test_a_cpu_host_runs_the_cpu_build_with_no_note(monkeypatch):
    monkeypatch.setattr(gpu_practice, "gpu_runtime", lambda image: None)
    out = gpu_practice.device_build(
        _Practice(None, {"cpu": "cpu-image"}), _expand_for, str
    )
    assert out == (_expand_for(None), "cpu", "cpu-image", "parent-of-cpu", None, None)


def test_a_gpu_host_without_the_gpu_build_installed_falls_back_and_says_why(
    monkeypatch,
):
    monkeypatch.setattr(gpu_practice, "gpu_runtime", lambda image: "torch-cu130-py311")
    out = gpu_practice.device_build(
        _Practice("gpu", {"cpu": "cpu-image"}), _expand_for, str
    )
    assert out[3:] == ("parent-of-cpu", None, "gpu_overlay_not_installed")

    # An overlay preparation that fails never fails the practice: CPU runs.
    def failing(bundle, parent, built):
        raise RuntimeError("prep failed")

    out = gpu_practice.device_build(
        _Practice("gpu", {"cpu": "cpu-image"}), _expand_for, str, failing
    )
    assert out[3:] == ("parent-of-cpu", None, "gpu_build_failed")
    # A GPU build resolved as a library child, not a verified overlay, is not
    # run on the GPU (the bundle worker requires the overlay).
    out = gpu_practice.device_build(
        _Practice("gpu", {"cpu": "cpu-image", "gpu": "child"}), _expand_for, str
    )
    assert out[4:] == (None, "gpu_overlay_not_installed")


def test_a_gpu_host_with_the_overlay_runs_the_gpu_build_on_the_gpu(monkeypatch):
    from carbon.development_session import library_environment_cache as cache
    from carbon.development_session.research_carrier import MINER_GPU

    class Overlay:
        pass

    monkeypatch.setattr(cache, "VerifiedLibraryOverlay", Overlay)
    monkeypatch.setattr(gpu_practice, "gpu_runtime", lambda image: "torch-cu130-py311")
    overlay = Overlay()
    out = gpu_practice.device_build(
        _Practice("gpu", {"gpu": overlay}), _expand_for, str
    )
    assert out == (_expand_for("x"), "gpu", overlay, "parent-of-gpu", MINER_GPU, None)


def test_a_gpu_host_prepares_the_overlay_on_demand(monkeypatch):
    from carbon.development_session import library_environment_cache as cache
    from carbon.development_session.research_carrier import MINER_GPU

    class Overlay:
        pass

    monkeypatch.setattr(cache, "VerifiedLibraryOverlay", Overlay)
    monkeypatch.setattr(gpu_practice, "gpu_runtime", lambda image: "torch-cu130-py311")
    made = Overlay()
    asked = []

    def overlay(bundle, parent, built):
        asked.append((bundle, parent))
        return made

    out = gpu_practice.device_build(
        _Practice("gpu", {"gpu": "child"}), _expand_for, str, overlay
    )
    assert out[2:5] == (made, "parent-of-gpu", MINER_GPU)
    assert asked == [("gpu", "parent-of-gpu")]
