"""Two CPU construction parents, one per bundle runtime (OWNER-BACKBONE-CATALOG-01;
Validator, 2026-10-20): the C-03 CPU worker is derived from the pinned PyTorch
CPU worker built FROM it, and a bundle's parent is chosen only from its pinned
runtime. An unregistered runtime is refused; an absent parent is not served."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.development_session import gpu_practice as gp
from carbon.reconstruction import torch_profile
from carbon.reconstruction.worker.model import WorkerImageIdentity

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return "sha256:" + hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def torch_image():
    parent = "sha256:" + "a" * 64
    torch_id = "sha256:" + "b" * 64
    return WorkerImageIdentity(
        image_id=torch_id,
        config_digest=torch_id,
        source_tree_digest="sha256:" + "c" * 64,
        wheel_digest="sha256:" + "d" * 64,
        lock_digest=torch_profile.requirements_digest(ROOT),
        base_image_digest=parent,
        build_recipe_digest=sha(".devcontainer/torch/Dockerfile"),
        entrypoint_digest="sha256:" + "e" * 64,
    )


def test_the_cpu_parent_is_the_image_the_torch_worker_was_built_from():
    image = torch_image()
    parent = gp.derived_cpu_parent(image)
    assert parent.image_id == parent.config_digest == image.base_image_digest
    assert parent.lock_digest == sha("uv.lock")
    assert parent.build_recipe_digest == sha(
        ".devcontainer/Dockerfile.reconstruction-worker"
    )
    assert (
        parent.source_tree_digest,
        parent.wheel_digest,
        parent.entrypoint_digest,
    ) == (
        image.source_tree_digest,
        image.wheel_digest,
        image.entrypoint_digest,
    )
    assert gp.direct_parent_backend(parent) is None  # a plain C-03 CPU worker


def test_the_pinned_base_digest_is_the_worker_scripts_own():
    script = (ROOT / "scripts/dev/c03_worker_image.sh").read_text()
    assert (
        re.search(r'base_digest="(sha256:[0-9a-f]{64})"', script).group(1)
        == gp.C03_BASE_IMAGE_DIGEST
    )


def test_a_real_torch_artifact_derives_its_recorded_parent():
    torch_record = ROOT / ".carbon-artifacts/torch-worker-image.json"
    parent_record = ROOT / ".carbon-artifacts/torch-parent-worker-image.json"
    if not (torch_record.exists() and parent_record.exists()):
        pytest.skip("no built torch worker artifacts in this checkout")
    fields = WorkerImageIdentity.__dataclass_fields__
    torch_image_ = WorkerImageIdentity(
        **{
            k: v
            for k, v in json.loads(torch_record.read_bytes()).items()
            if k in fields
        }
    )
    recorded = WorkerImageIdentity(
        **{
            k: v
            for k, v in json.loads(parent_record.read_bytes()).items()
            if k in fields
        }
    )
    assert gp.derived_cpu_parent(torch_image_) == recorded


def test_only_a_pinned_torch_cpu_worker_derives_a_parent():
    image = torch_image()
    not_torch = WorkerImageIdentity(
        **{
            **{k: getattr(image, k) for k in image.__dataclass_fields__},
            "lock_digest": sha("uv.lock"),
        }
    )
    with pytest.raises(gp.DirectParentRefused) as refused:
        gp.derived_cpu_parent(not_torch)
    assert refused.value.code == "backend_not_served"


def test_each_bundle_runtime_gets_its_own_parent_and_nothing_else():
    image = torch_image()
    parents = gp.DirectParents.from_torch(image)
    assert parents.runtimes() == ("python-cpu-py311", "torch-cpu-py311")
    assert (
        parents.for_bundle(SimpleNamespace(runtime_profile_id="torch-cpu-py311"))
        is image
    )
    assert (
        parents.for_bundle(
            SimpleNamespace(runtime_profile_id="python-cpu-py311")
        ).image_id
        == image.base_image_digest
    )
    with pytest.raises(gp.DirectParentRefused) as refused:
        parents.for_bundle(SimpleNamespace(runtime_profile_id="torch-cu130-py311"))
    assert refused.value.code == "construction_runtime_unknown"
    only_torch = gp.DirectParents({"torch-cpu-py311": image})
    with pytest.raises(gp.DirectParentRefused) as refused:
        only_torch.for_runtime("python-cpu-py311")
    assert refused.value.code == "backend_not_served"


def test_a_parent_of_the_wrong_kind_is_refused_for_its_runtime():
    image = torch_image()
    with pytest.raises(ValueError, match="differs from its runtime"):
        gp.DirectParents({"python-cpu-py311": image})
    with pytest.raises(ValueError, match="registered runtimes"):
        gp.DirectParents({"jax-cuda13-py311": image})
