"""The owner installer on a PyTorch CPU profile installs python-cpu bundles
over the C-03 CPU worker the Torch image was built from (two parents,
OWNER-BACKBONE-CATALOG-01), with every existing check kept and Docker's own
labels checked; a plain CPU profile is unchanged."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_direct_parents import torch_image

from carbon.development_session import research_campaign
from carbon.reconstruction.worker import docker_runtime
from scripts.dev import library_bundle

ROOT = Path(__file__).resolve().parents[2]
LOCK = "sha256:" + hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest()


@pytest.fixture
def host(monkeypatch):
    state = {"image": torch_image(), "eligible": True, "verified": []}
    monkeypatch.setattr(
        library_bundle, "load_image_identity", lambda path: state["image"]
    )
    monkeypatch.setattr(
        docker_runtime,
        "doctor",
        lambda **kw: SimpleNamespace(eligible=state["eligible"]),
    )
    monkeypatch.setattr(
        research_campaign,
        "verify_direct_v13_worker",
        lambda image, impl, role: state["verified"].append((image, role)),
    )
    return state


def profile(image):
    return {
        "paths": {"image_manifest": "/srv/worker.json"},
        "runtime": {
            "implementation": {"revision": "x"},
            "images": [image.image_id, "sha256:" + "f" * 64],
        },
    }


def test_a_torch_profile_installs_python_cpu_bundles_over_the_derived_cpu_parent(host):
    image = host["image"]
    parent = library_bundle._checked_cpu_parent(
        profile(image), {"base_environment_digest": LOCK}
    )
    assert parent.image_id == image.base_image_digest and parent.lock_digest == LOCK
    assert host["verified"] == [(parent, "cpu")]


def test_a_cpu_parent_docker_does_not_hold_is_refused(host):
    host["eligible"] = False
    with pytest.raises(ValueError, match="CPU parent unavailable"):
        library_bundle._checked_cpu_parent(
            profile(host["image"]), {"base_environment_digest": LOCK}
        )


def test_a_torch_image_other_than_the_profiles_is_refused(host):
    other = profile(host["image"])
    other["runtime"]["images"][0] = "sha256:" + "9" * 64
    with pytest.raises(ValueError, match="differs from profile"):
        library_bundle._checked_cpu_parent(other, {"base_environment_digest": LOCK})


def test_a_bundle_on_another_lock_is_refused(host):
    with pytest.raises(ValueError, match="lock or ABI differs"):
        library_bundle._checked_cpu_parent(
            profile(host["image"]), {"base_environment_digest": "sha256:" + "1" * 64}
        )


def test_a_plain_cpu_profile_keeps_its_own_parent(host):
    from carbon.development_session.gpu_practice import derived_cpu_parent

    cpu = derived_cpu_parent(host["image"])
    host["image"] = cpu
    assert (
        library_bundle._checked_cpu_parent(
            profile(cpu), {"base_environment_digest": LOCK}
        )
        is cpu
    )
