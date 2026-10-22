"""Shared GPU practice path, stage S3: one declared GPU scope for every
Challenge's catalog campaign (Validator-approved design, owner amendments)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from carbon.development_session import catalog_gpu, gpu_practice


def _image():
    return SimpleNamespace(image_id="sha256:" + "9" * 64)


def test_the_scope_is_speed_only_never_official_and_says_so(monkeypatch):
    monkeypatch.setattr(gpu_practice, "gpu_runtime", lambda image: "torch-cu130-py311")
    monkeypatch.setattr(gpu_practice, "gpu_image_backend", lambda image: "pytorch")
    monkeypatch.setattr(
        catalog_gpu, "asdict", lambda image: {"image_id": image.image_id}
    )
    scope = catalog_gpu.gpu_scope("electric-motor-magnetics", _image())
    assert scope["challenge"] == "electric-motor-magnetics"
    assert scope["bundle_runtime"] == "torch-cu130-py311"
    assert scope["purpose"] == "speed_only" and scope["score"] is None
    assert scope["official_eligible"] is False
    assert scope["label"] == "measured on GPU, not official"
    assert catalog_gpu.declared_scope({"gpu_research": [scope]}) == [scope]
    for broken in ({**scope, "score": 1.0}, {**scope, "official_eligible": True}):
        with pytest.raises(ValueError):
            catalog_gpu.declared_scope({"gpu_research": [broken]})


def test_a_non_gpu_image_has_no_scope():
    with pytest.raises(ValueError):
        catalog_gpu.gpu_scope("electric-motor-magnetics", _image())


def test_the_runtime_gains_the_scope_only_when_declared(monkeypatch):
    monkeypatch.setattr(catalog_gpu, "gpu_scope", lambda cid, image: {"c": cid})
    base = {"implementation": "i", "images": []}
    assert catalog_gpu.with_gpu(base, {}, "x", None) is base
    assert catalog_gpu.with_gpu(base, {"gpu_research": []}, "x", _image()) == {
        **base,
        "gpu_research": [{"c": "x"}],
    }
    with pytest.raises(ValueError):
        catalog_gpu.with_gpu(base, {"gpu_research": []}, "x", None)


def test_every_catalog_version_declares_gpu_practice_and_setup_lists_it():
    from carbon.challenge_registry.campaigns import implemented_campaigns
    from carbon.challenge_registry.registry import GPU_RESEARCH
    from scripts.dev.miner_launchpad.environment_setup import gpu_challenges

    listed = {(item["id"], item["version"]) for item in gpu_challenges()}
    for entry, campaign in implemented_campaigns():
        if campaign.construction_kit is None or entry.compile_strategy is not None:
            continue
        assert GPU_RESEARCH in {p.name for p in entry.profiles}, entry.challenge_id
        assert campaign.gpu_scope is not None
        assert (entry.challenge_id, entry.version) in listed
