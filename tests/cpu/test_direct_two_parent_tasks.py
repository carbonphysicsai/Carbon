"""Two CPU construction parents in the direct task supervisor and the owner
resolver (OWNER-BACKBONE-CATALOG-01; Validator, 2026-10-20): each bundle task
builds on the parent of its pinned runtime only, the store binds both parents,
an unregistered runtime is refused and an absent parent is not served."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from test_direct_parents import torch_image
from test_direct_v3_durable_tasks import _fixture

from carbon import research
from carbon.development_session import (
    bundle_construction_worker,
    gpu_practice,
    library_bundles,
    library_environment_cache,
)
from carbon.development_session.library_bundles import (
    LibraryBundleRef,
    ProvisionedLibraryEnvironment,
)
from carbon.development_session.research_image import LibraryWorkerImage
from carbon.development_session.research_tasks import DirectDevelopmentTasksV3
from carbon.research.errors import ResearchServiceErrorCode
from carbon.research.lifecycle import ResearchTaskProviderError

needs_fcntl = pytest.mark.skipif(
    sys.platform == "win32", reason="the task supervisor leases with fcntl"
)


def _bundle(runtime):
    return {
        "schema": "carbon.library-bundle-ref.v1",
        "bundle_digest": "sha256:" + "1" * 64,
        "language": "python",
        "runtime_profile_id": runtime,
        "environment_digest": "sha256:" + "2" * 64,
    }


def _image(tmp_path, bundle_ref, parent):
    return LibraryWorkerImage(
        ProvisionedLibraryEnvironment(
            LibraryBundleRef.from_dict(bundle_ref),
            parent.image_id,
            tmp_path,
            "sha256:" + "5" * 64,
            "sha256:" + "6" * 64,
        ),
        parent,
        bundle_ref,
    )


class _Resolver:
    def __init__(self, cache_root, images):
        self.cache_root, self.images, self.provisioned = cache_root, images, []

    def __call__(self, _bundle):
        pytest.fail("pre-admission image resolution ran")

    def inspect_source(self, bundle):
        return bundle

    def provision_admitted(self, bundle, *, parent, cli):
        del cli
        self.provisioned.append((bundle.runtime_profile_id, parent))
        return self.images[bundle.runtime_profile_id]


def _tasks(tmp_path, monkeypatch, parents, runtime):
    request, fixed_provider, discovery = _fixture(tmp_path, monkeypatch)
    fixed = fixed_provider()
    ledger = fixed.ledger
    fixed.close()
    bundle_ref = _bundle(runtime)
    recipe = json.loads(json.dumps(request.recipe))
    recipe["source"]["bundle_ref"] = bundle_ref
    request = replace(request, recipe=recipe)
    images = {
        runtime: _image(tmp_path, _bundle(runtime), parent)
        for runtime, parent in ((r, parents.for_runtime(r)) for r in parents.runtimes())
    }
    resolver = _Resolver(tmp_path / "owner-cache", images)
    monkeypatch.setattr(
        library_environment_cache,
        "inspect_staged_bundle_material",
        lambda *_args: tmp_path / "source-material",
    )
    monkeypatch.setattr(
        library_bundles,
        "load_pinned_bundle_directory",
        lambda _path: ({"base": "fixture"}, b"source", {}, b"lock", b"license"),
    )
    checked = []
    monkeypatch.setattr(
        library_bundles,
        "verify_bundle_parent_environment",
        lambda _manifest, parent: checked.append(parent),
    )
    tasks = DirectDevelopmentTasksV3(
        root=tmp_path / "two-parent-tasks",
        requester="miner",
        ledger=ledger,
        owner="miner",
        discovery=discovery,
        image=None,
        inference_image=torch_image(),
        image_resolver=resolver,
        construction_parents=parents,
    )
    return tasks, request, resolver, checked


@needs_fcntl
@pytest.mark.parametrize("runtime", ["torch-cpu-py311", "python-cpu-py311"])
def test_each_task_builds_on_its_own_runtimes_parent(tmp_path, monkeypatch, runtime):
    parents = gpu_practice.DirectParents.from_torch(torch_image())
    tasks, request, resolver, checked = _tasks(tmp_path, monkeypatch, parents, runtime)
    try:
        with tasks._db() as db:
            identity = json.loads(
                db.execute("SELECT identity FROM direct_binding WHERE id=1").fetchone()[
                    0
                ]
            )
        # Both parents are bound, by runtime, beside the inference image.
        assert identity[-7:] == [
            torch_image().image_id,
            "CONSTRUCTION_PARENT",
            "python-cpu-py311",
            torch_image().base_image_digest,
            "CONSTRUCTION_PARENT",
            "torch-cpu-py311",
            torch_image().image_id,
        ]
        started = tasks.start_research_task(request).task
        assert started.state is research.DirectTaskStateV3.QUEUED
        seen = {}

        def claimed(*_args, **kwargs):
            seen["parent"] = kwargs["construction_parent"]
            return {"claimed": "success"}

        monkeypatch.setattr(
            bundle_construction_worker, "reconstruct_and_infer_public", claimed
        )
        tasks.run_queued_task(started.task_id)
        expected = parents.for_runtime(runtime)
        assert checked == [expected]
        assert resolver.provisioned == [(runtime, expected)]
        assert seen["parent"] == expected
    finally:
        tasks.close()


@needs_fcntl
@pytest.mark.parametrize(
    "parents, runtime, code",
    [
        (
            lambda: gpu_practice.DirectParents.from_torch(torch_image()),
            "torch-cu130-py311",
            ResearchServiceErrorCode.REFERENCE_MISMATCH,
        ),
        (
            lambda: gpu_practice.DirectParents({"torch-cpu-py311": torch_image()}),
            "python-cpu-py311",
            ResearchServiceErrorCode.CAPABILITY_UNAVAILABLE,
        ),
    ],
)
def test_a_runtime_without_a_parent_here_is_refused_before_admission(
    tmp_path, monkeypatch, parents, runtime, code
):
    tasks, request, resolver, checked = _tasks(
        tmp_path, monkeypatch, parents(), runtime
    )
    try:
        with pytest.raises(ResearchTaskProviderError) as refused:
            tasks.start_research_task(request)
        assert refused.value.code is code
        assert resolver.provisioned == checked == []
    finally:
        tasks.close()


@needs_fcntl
def test_a_store_bound_to_other_parents_is_refused(tmp_path, monkeypatch):
    both = gpu_practice.DirectParents.from_torch(torch_image())
    tasks, *_ = _tasks(tmp_path, monkeypatch, both, "torch-cpu-py311")
    tasks.close()
    with pytest.raises(ValueError, match="binding changed"):
        _tasks(
            tmp_path,
            monkeypatch,
            gpu_practice.DirectParents({"torch-cpu-py311": torch_image()}),
            "torch-cpu-py311",
        )


def test_per_runtime_parents_need_the_resolver_and_exclude_one_parent(tmp_path):
    parents = gpu_practice.DirectParents.from_torch(torch_image())
    common = {
        "root": tmp_path / "t",
        "requester": "miner",
        "ledger": None,
        "owner": "miner",
        "discovery": None,
        "inference_image": torch_image(),
    }
    for extra in (
        {"image_resolver": None},
        {"image_resolver": object(), "construction_parent": torch_image()},
        {"image_resolver": object(), "construction_parents": object()},
        {
            "image_resolver": object(),
            "construction_parents": gpu_practice.DirectParents({}),
        },
    ):
        kwargs = {"construction_parents": parents, **common, **extra}
        with pytest.raises(ValueError, match="per-runtime parents"):
            DirectDevelopmentTasksV3(**kwargs)
    assert not (tmp_path / "t").exists()


# --- the owner resolver ---------------------------------------------------------


def test_the_resolver_picks_each_bundles_parent_from_its_runtime(tmp_path, monkeypatch):
    from carbon.miner_mcp.standard_cli import DirectOwnerImageResolver

    parents = gpu_practice.DirectParents.from_torch(torch_image())
    cache = tmp_path / "owner-cache"
    cache.mkdir(mode=0o700)
    resolver = DirectOwnerImageResolver(cache, parents=parents)
    seen = []
    receipt = cache / "verified.image.json"
    receipt.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(
        library_environment_cache,
        "library_image_cache_paths",
        lambda root, bundle, parent: (seen.append(parent), (receipt, cache / "c"))[1],
    )
    monkeypatch.setattr(
        library_environment_cache,
        "load_cached_library_worker_image",
        lambda path, *, expected_bundle, expected_parent, context_root: (
            expected_bundle.runtime_profile_id,
            expected_parent,
        ),
    )
    for runtime in parents.runtimes():
        bundle = LibraryBundleRef.from_dict(_bundle(runtime))
        assert resolver(bundle) == (runtime, parents.for_runtime(runtime))
        assert resolver.parent_for(bundle) == parents.for_runtime(runtime)
    assert seen == [parents.for_runtime(r) for r in parents.runtimes()]
    with pytest.raises(gpu_practice.DirectParentRefused) as refused:
        resolver(LibraryBundleRef.from_dict(_bundle("jax-cuda13-py311")))
    assert refused.value.code == "construction_runtime_unknown"
    only_torch = DirectOwnerImageResolver(
        cache, parents=gpu_practice.DirectParents({"torch-cpu-py311": torch_image()})
    )
    with pytest.raises(gpu_practice.DirectParentRefused) as refused:
        only_torch(LibraryBundleRef.from_dict(_bundle("python-cpu-py311")))
    assert refused.value.code == "backend_not_served"


def test_the_resolver_takes_one_parent_or_the_per_runtime_parents(tmp_path):
    from carbon.miner_mcp.standard_cli import DirectOwnerImageResolver

    parents = gpu_practice.DirectParents.from_torch(torch_image())
    for kwargs in (
        {"parent": torch_image(), "parents": parents},
        {"parents": {"torch-cpu-py311": torch_image()}},
    ):
        with pytest.raises(ValueError, match="one parent or the per-runtime"):
            DirectOwnerImageResolver(Path(tmp_path), **kwargs)
