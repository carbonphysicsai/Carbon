"""Direct task admission binds public kit bytes and refuses fake completion.

These are provider/canonical tests. They do not substitute for a real C-03
container run, which is required before the direct task operation is advertised.
"""

from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_c08_authenticated_miner_mcp import (
    CONTEXT,
    NOW,
    _Adapter,
    _headers,
    _snapshot,
    _Verifier,
)

from carbon import research
from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v3
from carbon.development_session import bundle_construction_worker
from carbon.development_session.construction_recipe import ConstructionRecipe
from carbon.development_session.library_bundles import (
    LibraryBundleRef,
    ProvisionedLibraryEnvironment,
)
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_image import LibraryWorkerImage
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_service import DirectFixtureDiscovery
from carbon.development_session.research_tasks import DirectDevelopmentTasksV3
from carbon.miner_mcp.research import AuthenticatedResearchService
from carbon.reconstruction.worker.model import WorkerImageIdentity
from carbon.transport.gateway import AuthenticatedGateway
from carbon.transport.models import message
from carbon.transport.store import ReceiptJournal


def _fixture(tmp_path, monkeypatch, material=None, task_root=None):
    material = bundle_material_v3() if material is None else material
    discovery = DirectFixtureDiscovery(material, task_admission=True)
    bundle_ref = {
        "schema": "carbon.library-bundle-ref.v1",
        "bundle_digest": "sha256:" + "1" * 64,
        "language": "python",
        "runtime_profile_id": "jax-cuda13-py311",
        "environment_digest": "sha256:" + "2" * 64,
    }
    parent_digest = "sha256:" + "4" * 64
    parent = WorkerImageIdentity(*(parent_digest for _ in range(8)))
    image = LibraryWorkerImage(
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
    inference_image = parent
    monkeypatch.setattr(
        "carbon.development_session.research_image.verify_library_worker_image",
        lambda value: value,
    )
    recipe = {
        "schema": "carbon.construction-recipe.v1",
        "challenge": material["construction_kit"],
        "source": {"kind": "bundle", "bundle_ref": bundle_ref},
        "procedure": {
            "entrypoint": {"module": "candidate.build", "name": "build"},
            "configuration": {},
            "train_use": {"cases": "all"},
            "initial_state": None,
        },
        "output": {
            "format": "carbon.numeric-graph.v1",
            "interface_digest": material["construction_kit"]["interface_digest"],
        },
    }
    request = research.DirectStartTaskRequestV3(
        material["challenge_key"],
        "direct-task-durable-001",
        recipe,
        research.canonical_digest(discovery.info),
        research.canonical_digest(discovery.manifest),
        digest(canonical(material["construction_kit"])),
        discovery.info.public_train_digest,
        discovery.info.practice_inputs_digest,
        discovery.info.interface_digest,
        discovery.info.construction_limits_digest,
        digest(
            canonical(
                material["construction_limits_document"][
                    "reconstruction_resource_policy"
                ]
            )
        ),
    )
    ledger = CampaignLedger(tmp_path / "ledger")

    def provider(owner="miner"):
        return DirectDevelopmentTasksV3(
            root=tmp_path / "tasks" if task_root is None else task_root,
            requester=owner,
            ledger=ledger,
            owner=owner,
            discovery=discovery,
            image=image,
            inference_image=inference_image,
        )

    return request, provider, discovery


@pytest.mark.parametrize("changed_child", [False, True])
def test_direct_v3_resolves_each_bundle_and_refuses_changed_child_on_restart(
    tmp_path, monkeypatch, changed_child
):
    request, fixed_provider, discovery = _fixture(tmp_path, monkeypatch)
    fixed = fixed_provider()
    image, parent, ledger = fixed.image, fixed.inference_image, fixed.ledger
    fixed.close()
    # The original fixed-image store and a per-recipe store have distinct
    # durable roots. The public request still names only the bundle ref.
    first_ref = image.bundle_ref
    second_ref = {**first_ref, "bundle_digest": "sha256:" + "3" * 64}
    second_image = LibraryWorkerImage(
        replace(
            image.provisioned,
            bundle=LibraryBundleRef.from_dict(second_ref),
            image_id="sha256:" + "7" * 64,
        ),
        parent,
        second_ref,
    )
    installed = {
        first_ref["bundle_digest"]: image,
        second_ref["bundle_digest"]: second_image,
    }

    def resolve(bundle):
        try:
            return installed[bundle.bundle_digest]
        except KeyError:
            raise FileNotFoundError("owner cache has no installed bundle") from None

    def provider(resolver=resolve):
        return DirectDevelopmentTasksV3(
            root=tmp_path / "per-recipe-tasks",
            requester="miner",
            ledger=ledger,
            owner="miner",
            discovery=discovery,
            image=None,
            inference_image=parent,
            image_resolver=resolver,
        )

    second_request = replace(
        request,
        idempotency_key="direct-task-durable-second-001",
        recipe={
            **request.recipe,
            "source": {"kind": "bundle", "bundle_ref": second_ref},
        },
    )
    tasks = provider()
    try:
        first = tasks.start_research_task(request).task
        second = tasks.start_research_task(second_request).task
        assert first.task_id != second.task_id
        assert tasks._task_image_bindings[first.task_id.value] != (
            tasks._task_image_bindings[second.task_id.value]
        )
        cancelled = tasks.cancel_research_task(
            research.DirectCancelTaskRequestV3(
                second_request.challenge_key,
                second.task_id,
                "cancel-second-bundle-001",
            )
        )
        assert cancelled.task.state is research.DirectTaskStateV3.CANCELLED
    finally:
        tasks.close()

    # A valid-looking but different cached child cannot execute the retained
    # queued task. The other bundle's terminal custody remains readable.
    if changed_child:
        installed[first_ref["bundle_digest"]] = LibraryWorkerImage(
            replace(image.provisioned, image_id="sha256:" + "8" * 64),
            parent,
            first_ref,
        )

    class UpgradedResolver:
        def __call__(self, bundle):
            return resolve(bundle)

        def inspect_source(self, bundle):
            pytest.fail("historical queued image pin must not become source-only")

        def provision_admitted(self, bundle, *, parent, cli):
            pytest.fail("historical queued image must not be reprovisioned")

    invoked = []

    def claimed(*args, **kwargs):
        invoked.append(kwargs["image"])
        return {"claimed": "success"}

    monkeypatch.setattr(
        bundle_construction_worker, "reconstruct_and_infer_public", claimed
    )
    reopened = provider(UpgradedResolver())
    try:
        assert (
            reopened.get_research_result(
                research.DirectGetTaskRequestV3(
                    second_request.challenge_key, second.task_id
                )
            ).task.state
            is research.DirectTaskStateV3.CANCELLED
        )
        ended = reopened.run_queued_task(first.task_id)
        if changed_child:
            assert ended.state is research.DirectTaskStateV3.FAILED_INFRA
            assert (
                ended.terminal_receipt.infrastructure_failure_class
                is research.InfrastructureFailureClass.DEPENDENCY_UNAVAILABLE
            )
            assert invoked == []
        else:
            # The unchanged pinned child reaches the existing construction seam;
            # a mocked return still cannot mint verified model evidence.
            assert ended.state is research.DirectTaskStateV3.UNRESOLVED
            assert invoked == [image]
        assert reopened.private_attempt(first.task_id) is None
    finally:
        reopened.close()


@pytest.mark.parametrize("parent_valid", [True, False])
def test_direct_v3_inspects_source_then_provisions_only_after_durable_queue(
    tmp_path, monkeypatch, parent_valid
):
    from carbon.development_session import library_bundles, library_environment_cache

    request, fixed_provider, discovery = _fixture(tmp_path, monkeypatch)
    fixed = fixed_provider()
    image, parent, ledger = fixed.image, fixed.inference_image, fixed.ledger
    fixed.close()

    class Resolver:
        cache_root = tmp_path / "owner-cache"
        inspected = 0
        provisioned = 0

        def __call__(self, _bundle):
            pytest.fail("pre-admission image resolution ran")

        def inspect_source(self, bundle):
            self.inspected += 1
            assert bundle.to_dict() == image.bundle_ref
            return bundle

        def provision_admitted(self, bundle, *, parent, cli):
            del cli
            assert verified == [parent]
            self.provisioned += 1
            assert bundle.to_dict() == image.bundle_ref
            assert parent == image.parent
            return image

    resolver = Resolver()
    verified = []
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

    def check_parent(manifest, parent):
        assert manifest == {"base": "fixture"}
        verified.append(parent)
        if not parent_valid:
            raise ValueError("staged bundle base differs from registered parent")

    monkeypatch.setattr(
        library_bundles, "verify_bundle_parent_environment", check_parent
    )
    inference_image = WorkerImageIdentity(*("sha256:" + "9" * 64 for _ in range(8)))
    tasks = DirectDevelopmentTasksV3(
        root=tmp_path / "admitted-tasks",
        requester="miner",
        ledger=ledger,
        owner="miner",
        discovery=discovery,
        image=None,
        inference_image=inference_image,
        construction_parent=parent,
        image_resolver=resolver,
    )
    try:
        started = tasks.start_research_task(request).task
        assert started.state is research.DirectTaskStateV3.QUEUED
        assert resolver.inspected == 1
        assert resolver.provisioned == 0
        with tasks._db() as db:
            retained = db.execute(
                "SELECT identity FROM direct_task_images WHERE id=?",
                (started.task_id.value,),
            ).fetchone()[0]
        assert json.loads(retained) == ["BUNDLE_SOURCE", image.bundle_ref]
        with tasks._db() as db:
            identity = json.loads(
                db.execute("SELECT identity FROM direct_binding WHERE id=1").fetchone()[
                    0
                ]
            )
        assert identity[-2:] == [inference_image.image_id, parent.image_id]

        def claimed(*args, **kwargs):
            assert resolver.provisioned == 1
            assert verified == [parent]
            assert type(kwargs["total_deadline_started"]) is float
            return {"claimed": "success"}

        monkeypatch.setattr(
            bundle_construction_worker, "reconstruct_and_infer_public", claimed
        )
        ended = tasks.run_queued_task(started.task_id)
        if not parent_valid:
            assert ended.state is research.DirectTaskStateV3.FAILED_INFRA
            assert resolver.provisioned == 0
            assert verified == [parent]
            return
        assert ended.state is research.DirectTaskStateV3.UNRESOLVED
        with tasks._db() as db:
            actual = db.execute(
                "SELECT identity FROM direct_task_images WHERE id=?",
                (started.task_id.value,),
            ).fetchone()[0]
        assert actual == tasks._image_binding(image)
        assert actual != retained
    finally:
        tasks.close()


@pytest.mark.parametrize(
    "build_backend,infer_backend",
    (("cpu", "cpu"), ("jax", "jax"), ("torch", "jax"), ("torch", "cpu")),
)
def test_direct_v3_cold_overlay_binds_completed_prep_after_queue(
    tmp_path, monkeypatch, build_backend, infer_backend
):
    from carbon.development_session import library_bundles, library_environment_cache
    from carbon.development_session.bundle_construction_worker import (
        BundleOverlayPrepResult,
    )
    from carbon.development_session.research_carrier import MINER_GPU
    from carbon.reconstruction.accelerators import GPU_PROFILE
    from carbon.reconstruction.torch_profile import GPU_LOCK_DIGEST

    request, fixed_provider, discovery = _fixture(tmp_path, monkeypatch)
    fixed = fixed_provider()
    image, parent, ledger = fixed.image, fixed.inference_image, fixed.ledger
    fixed.close()
    cpu_inference = parent
    locks = {"jax": GPU_PROFILE.environment_lock_digest, "torch": GPU_LOCK_DIGEST}
    if build_backend != "cpu":
        parent = replace(parent, lock_digest=locks[build_backend])
    inference_image = (
        cpu_inference
        if infer_backend == "cpu"
        else replace(cpu_inference, lock_digest=locks[infer_backend])
    )
    build_gpu = build_backend != "cpu"
    infer_gpu = infer_backend != "cpu"
    bundle = LibraryBundleRef.from_dict(image.bundle_ref)
    overlay = library_environment_cache.VerifiedLibraryOverlay(
        tmp_path / "sealed-overlay",
        "sha256:" + "a" * 64,
        bundle,
        parent.image_id,
        "sha256:" + "b" * 64,
        1,
        4,
    )
    prep = BundleOverlayPrepResult(
        tmp_path / "prep-snapshot",
        {"bundle_ref": bundle.to_dict()},
        "operation-" + "c" * 64,
        "sha256:" + "d" * 64,
    )
    calls = []

    class Resolver:
        cache_root = tmp_path / "owner-cache"
        material_cache_bytes = 10 * 1024**2

        def __call__(self, _bundle):
            pytest.fail("source-only admission resolved a child")

        def inspect_source(self, selected):
            assert selected == bundle
            calls.append("inspect")
            return selected

        def provision_admitted(self, selected, *, parent, cli):
            assert selected == bundle and parent == image.parent
            calls.append("cache-miss")
            raise FileNotFoundError(
                "bounded automatic dependency build unavailable; verified child missing"
            )

    monkeypatch.setattr(
        library_environment_cache,
        "inspect_staged_bundle_material",
        lambda *_args: tmp_path / "source-material",
    )
    monkeypatch.setattr(
        library_bundles,
        "load_pinned_bundle_directory",
        lambda _path: (object(), b"source", {}, b"lock", b"license"),
    )
    monkeypatch.setattr(
        library_bundles,
        "verify_bundle_parent_environment",
        lambda _manifest, selected_parent: calls.append("parent-verified"),
    )

    def fixed_prep(_ledger, **kwargs):
        assert kwargs["parent"] == parent
        assert kwargs.get("accelerator") == (MINER_GPU if build_gpu else None)
        assert ("accelerator" in kwargs) is build_gpu
        assert kwargs["identity"].endswith("-prep")
        assert "uv_binary" not in kwargs
        assert 40 <= kwargs["seconds"] <= 600
        assert type(kwargs["deadline"]) is float
        kwargs["cancel"]()
        calls.append("bounded-prep")
        return prep

    def fixed_cache(*_args, **kwargs):
        assert kwargs["expected_bundle"] == bundle
        assert kwargs["expected_parent"] == parent
        assert kwargs["expected_receipt"] == prep.receipt
        assert kwargs["material_cache_bytes"] == Resolver.material_cache_bytes
        assert type(kwargs["deadline"]) is float
        kwargs["cancel"]()
        calls.append("sealed-cache")
        return overlay

    monkeypatch.setattr(
        bundle_construction_worker, "prepare_library_overlay", fixed_prep
    )
    monkeypatch.setattr(
        library_environment_cache, "cache_verified_overlay", fixed_cache
    )

    def construction(*_args, **kwargs):
        assert kwargs.get("accelerator") == (MINER_GPU if build_gpu else None)
        assert ("accelerator" in kwargs) is build_gpu
        assert kwargs.get("inference_accelerator") == (MINER_GPU if infer_gpu else None)
        assert ("inference_accelerator" in kwargs) is infer_gpu
        calls.append("construction")
        return {"claimed": kwargs["image"]}

    monkeypatch.setattr(
        bundle_construction_worker, "reconstruct_and_infer_public", construction
    )
    tasks = DirectDevelopmentTasksV3(
        root=tmp_path / "cold-tasks",
        requester="miner",
        ledger=ledger,
        owner="miner",
        discovery=discovery,
        image=None,
        inference_image=inference_image,
        construction_parent=parent,
        image_resolver=Resolver(),
    )
    try:
        started = tasks.start_research_task(request).task
        assert started.state is research.DirectTaskStateV3.QUEUED
        assert calls == ["inspect"]
        assert len(tasks._all_children(started.task_id)) == 3
        ended = tasks.run_queued_task(started.task_id)
        assert ended.state is research.DirectTaskStateV3.UNRESOLVED
        assert calls == [
            "inspect",
            "inspect",
            "parent-verified",
            *([] if build_gpu else ["cache-miss"]),
            "bounded-prep",
            "sealed-cache",
            "construction",
        ]
        assert tasks._task_image_bindings[
            started.task_id.value
        ] == tasks._image_binding(overlay)
        assert len(tasks._all_children(started.task_id)) == 3
    finally:
        tasks.close()


def test_direct_v3_wire_and_durable_idempotency_refuse_changed_material(
    tmp_path, monkeypatch
):
    request, provider, _discovery = _fixture(tmp_path, monkeypatch)
    assert (
        research.load_canonical(
            research.canonical_bytes(request), research.DirectStartTaskRequestV3
        )
        == request
    )
    tasks = provider()
    try:
        first = tasks.start_research_task(request)
        assert first.created
        assert (
            first.task.immutable_bindings.public_train_digest
            == request.public_train_digest
        )
        assert tasks.start_research_task(request).task == first.task
        with pytest.raises(research.ResearchTaskProviderError):
            tasks.start_research_task(
                replace(request, resource_policy_digest="sha256:" + "0" * 64)
            )
        task_id = first.task.task_id
    finally:
        tasks.close()
    reopened = provider()
    try:
        assert reopened.start_research_task(request).task.task_id == task_id
        assert (
            reopened.get_research_result(
                research.DirectGetTaskRequestV3(request.challenge_key, task_id)
            ).task.state
            is research.DirectTaskStateV3.QUEUED
        )
    finally:
        reopened.close()


def test_direct_v3_fake_callback_cannot_become_success(tmp_path, monkeypatch):
    request, provider, _discovery = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        started = tasks.start_research_task(request)
        monkeypatch.setattr(
            bundle_construction_worker,
            "reconstruct_and_infer_public",
            lambda *args, **kwargs: {"claimed": "success"},
        )
        view = tasks.run_queued_task(started.task.task_id)
        assert view.state is research.DirectTaskStateV3.UNRESOLVED
        assert view.terminal_receipt.refusal_code == "unresolved_execution"
        assert tasks.private_attempt(started.task.task_id) is None
    finally:
        tasks.close()


def test_direct_v3_typed_candidate_failure_is_not_infrastructure(tmp_path, monkeypatch):
    request, provider, _discovery = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        started = tasks.start_research_task(request)
        from carbon.development_session import research_carrier
        from carbon.reconstruction.worker.model import WorkerCode

        failure = research_carrier.MinerProgramFailure(
            {
                "schema": research_carrier.MINER_FAILURE_SCHEMA,
                "failure_code": WorkerCode.RUNTIME.value,
                "observation": "NONZERO_EXIT",
            }
        )

        def failing(*args, **kwargs):
            raise failure

        monkeypatch.setattr(
            bundle_construction_worker, "reconstruct_and_infer_public", failing
        )
        view = tasks.run_queued_task(started.task.task_id)
        assert view.state is research.DirectTaskStateV3.REFUSED
        assert view.terminal_receipt.refusal_code == "candidate_program_failed"
        assert view.terminal_receipt.infrastructure_failure_class is None
    finally:
        tasks.close()


@pytest.mark.parametrize(
    ("state", "refusal_code"),
    [
        (research.DirectTaskStateV3.REFUSED, "candidate_program_failed"),
        (research.DirectTaskStateV3.UNRESOLVED, "unresolved_execution"),
    ],
)
def test_direct_cancel_preserves_terminal_refusal_or_unresolved_receipt(
    tmp_path, monkeypatch, state, refusal_code
):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        started = tasks.start_research_task(request).task
        receipt = tasks._receipt(started, state, refusal_code=refusal_code)
        infra = (
            {"failed_stage": "orchestration", "reason_code": "unclassified_internal"}
            if state is research.DirectTaskStateV3.UNRESOLVED
            else None
        )
        terminal = tasks._transition(started, state, receipt=receipt, infra=infra)
        cancellation = research.DirectCancelTaskRequestV3(
            request.challenge_key, terminal.task_id, "terminal-cancel-001"
        )
        result = tasks.cancel_research_task(cancellation)
        assert result.disposition is research.CancellationDisposition.TOO_LATE
        assert result.task == terminal
        assert (
            tasks.get_research_result(
                research.DirectGetTaskRequestV3(request.challenge_key, terminal.task_id)
            ).task
            == terminal
        )
    finally:
        tasks.close()
    reopened = provider()
    try:
        retained = reopened.get_research_result(
            research.DirectGetTaskRequestV3(request.challenge_key, terminal.task_id)
        ).task
        assert retained == terminal
        assert digest(research.canonical_bytes(retained.terminal_receipt)) == digest(
            research.canonical_bytes(receipt)
        )
        assert reopened.cancel_research_task(cancellation).task == terminal
    finally:
        reopened.close()


def test_direct_v3_settled_infrastructure_child_is_typed_at_parent(
    tmp_path, monkeypatch
):
    request, provider, _discovery = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        started = tasks.start_research_task(request)
        build, _inference = tasks._children(started.task.task_id)
        monkeypatch.setattr(
            tasks.ledger,
            "operation_state",
            lambda identity, *, owner: (
                "FAILED_INFRA" if identity == build and owner == tasks.owner else None
            ),
        )

        def failing(*args, **kwargs):
            raise OSError("host doctor failed")

        monkeypatch.setattr(
            bundle_construction_worker, "reconstruct_and_infer_public", failing
        )
        view = tasks.run_queued_task(started.task.task_id)
        assert view.state is research.DirectTaskStateV3.FAILED_INFRA
        assert (
            view.terminal_receipt.infrastructure_failure_class
            is research.InfrastructureFailureClass.INTERNAL
        )
        assert view.terminal_receipt.refusal_code is None
    finally:
        tasks.close()


@pytest.mark.parametrize(
    ("refusal", "operation"),
    [
        (
            b"aten_op_not_lowered at aten._softmax.default",
            "aten._softmax.default",
        ),
        (
            b"aten_scatter_index_not_static at aten.scatter_add.default",
            "aten.scatter_add.default",
        ),
    ],
)
def test_direct_v3_export_gap_has_bounded_durable_public_feedback(
    tmp_path, monkeypatch, refusal, operation
):
    request, provider, _discovery = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        started = tasks.start_research_task(request)
        build, _inference = tasks._children(started.task.task_id)
        monkeypatch.setattr(
            tasks.ledger,
            "operation_state",
            lambda identity, *, owner: (
                "FAILED_INFRA" if identity == build and owner == tasks.owner else None
            ),
        )
        from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

        private = (
            b"private host path and traceback must stay private\n"
            b"carbon.level4.graph.GraphRefused: " + refusal + b"\n"
        )

        def failing(*args, **kwargs):
            raise WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=private)

        monkeypatch.setattr(
            bundle_construction_worker, "reconstruct_and_infer_public", failing
        )
        view = tasks.run_queued_task(started.task.task_id)
        assert view.state is research.DirectTaskStateV3.FAILED_INFRA
        assert (
            view.terminal_receipt.infrastructure_failure_class
            is research.InfrastructureFailureClass.INTERNAL
        )
        projected = tasks.public_result(view)
        assert projected == {
            "schema": "carbon.direct-public-construction-failure.v1",
            "task_id": view.task_id.value,
            "receipt_digest": digest(research.canonical_bytes(view.terminal_receipt)),
            "failed_stage": "BUILD_EXPORT",
            "reason_code": "REPORTED_CARBON_EXPORT_OPERATION_GAP",
            "diagnostic_provenance": "WORKER_DIAGNOSTIC_ADVISORY",
            "reported_operation": operation,
            "next_step": "CHECK_CARBON_ADAPTER_SUPPORT",
            "official_eligible": False,
        }
        assert b"private host path" not in canonical(projected)
    finally:
        tasks.close()
    reopened = provider()
    try:
        readback = reopened.get_research_result(
            research.DirectGetTaskRequestV3(request.challenge_key, view.task_id)
        ).task
        assert readback == view
        assert reopened.public_result(readback) == projected
    finally:
        reopened.close()


@pytest.mark.parametrize(
    "refusal",
    [
        b"aten_op_not_lowered at aten._softmax.default",
        b"aten_scatter_index_not_static at aten.scatter_add.default",
    ],
)
def test_direct_v3_export_gap_does_not_echo_arbitrary_worker_text(refusal):
    from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

    failure = WorkerFailure(
        WorkerCode.RUNTIME,
        private_diagnostic=(
            b"carbon.level4.graph.GraphRefused: " + refusal + b";private-data\n"
        ),
    )
    assert (
        DirectDevelopmentTasksV3._reported_export_gap(failure, ["FAILED_INFRA", None])
        is None
    )
    assert (
        DirectDevelopmentTasksV3._reported_export_gap(failure, ["FAILED_MINER", None])
        is None
    )


@pytest.mark.parametrize(
    "diagnostic",
    [
        (
            b"carbon.level4.graph.GraphRefused: "
            b"aten_scatter_index_not_static at aten.scatter.default\n"
        ),
        (
            b"carbon.level4.graph.GraphRefused: "
            b"aten_scatter_index_not_lowered at aten.scatter_add.default\n"
        ),
        (
            b"carbon.level4.graph.GraphRefused: "
            b"aten_scatter_index_not_static at aten.scatter_add.default\n"
            b"carbon.level4.graph.GraphRefused: "
            b"aten_scatter_index_not_static at aten.scatter_add.default\n"
        ),
        (
            b"carbon.level4.graph.GraphRefused: "
            b"aten_op_not_lowered at aten._softmax.default\n"
            b"carbon.level4.graph.GraphRefused: "
            b"aten_scatter_index_not_static at aten.scatter_add.default\n"
        ),
    ],
)
def test_direct_v3_scatter_index_advisory_requires_one_exact_refusal(diagnostic):
    from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

    failure = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=diagnostic)
    assert (
        DirectDevelopmentTasksV3._reported_export_gap(failure, ["FAILED_INFRA", None])
        is None
    )


def test_direct_v3_scatter_index_advisory_preserves_worker_guards():
    from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

    diagnostic = (
        b"carbon.level4.graph.GraphRefused: "
        b"aten_scatter_index_not_static at aten.scatter_add.default\n"
    )
    for code, states in (
        (WorkerCode.INVALID, ["FAILED_INFRA", None]),
        (WorkerCode.RUNTIME, ["FAILED_MINER", None]),
        (WorkerCode.RUNTIME, ["FAILED_INFRA", "FAILED_INFRA"]),
    ):
        failure = WorkerFailure(code, private_diagnostic=diagnostic)
        assert DirectDevelopmentTasksV3._reported_export_gap(failure, states) is None


def test_direct_v3_success_evidence_tamper_fails_closed_on_read_and_reload(
    tmp_path, monkeypatch
):
    """A fabricated DB fixture tests retained-byte checks, not worker success."""
    request, provider, _discovery = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    started = tasks.start_research_task(request)
    raw = b"[[1.0]]"
    predictions_digest = digest(raw)
    recipe_digest = ConstructionRecipe.from_dict(request.recipe).digest
    state_digest = "sha256:" + "a" * 64
    now = started.task.updated_at_micros + 1
    receipt = research.DirectTaskReceiptV3(
        started.task.task_id,
        research.DirectTaskStateV3.SUCCEEDED,
        started.task.immutable_bindings,
        state_digest,
        predictions_digest,
        None,
        None,
        now,
        ("PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY",),
    )
    succeeded = replace(
        started.task,
        state=research.DirectTaskStateV3.SUCCEEDED,
        revision=1,
        updated_at_micros=now,
        terminal_receipt=receipt,
    )
    private = {
        "state_digest": state_digest,
        "predictions_digest": predictions_digest,
        "predictions_raw_base64": base64.b64encode(raw).decode("ascii"),
        "inference_receipt": {
            "schema": "carbon.development.bundle-inference.v1",
            "recipe_digest": recipe_digest,
            "state_digest": state_digest,
            "inputs_digest": "sha256:" + "b" * 64,
            "predictions_digest": predictions_digest,
        },
    }
    with tasks._db() as db:
        db.execute(
            "INSERT INTO direct_evidence VALUES(?,?)",
            (started.task.task_id.value, canonical(private)),
        )
        db.execute(
            "UPDATE direct_tasks SET view=? WHERE id=?",
            (research.canonical_bytes(succeeded), started.task.task_id.value),
        )
    tasks._views[started.task.task_id.value] = succeeded
    assert tasks.public_result(succeeded)["predictions"] == [[1.0]]
    altered = {
        **private,
        "predictions_raw_base64": base64.b64encode(b"[[2.0]]").decode("ascii"),
    }
    with tasks._db() as db:
        db.execute(
            "UPDATE direct_evidence SET body=? WHERE id=?",
            (canonical(altered), started.task.task_id.value),
        )
    with pytest.raises(ValueError, match="custody differs"):
        tasks.get_research_result(
            research.DirectGetTaskRequestV3(request.challenge_key, started.task.task_id)
        )
    with tasks._db() as db:
        db.execute(
            "DELETE FROM direct_evidence WHERE id=?", (started.task.task_id.value,)
        )
    tasks.close()
    with pytest.raises(ValueError, match="custody differs"):
        provider()


def test_direct_measured_query_profile_survives_restart_and_cannot_switch(
    tmp_path, monkeypatch
):
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5

    request, provider, _ = _fixture(
        tmp_path, monkeypatch, material=bundle_material_v5()
    )
    first = provider()
    try:
        task = first.start_research_task(request, measure_query=True).task
    finally:
        first.close()
    reopened = provider()
    try:
        assert not reopened.start_research_task(request, measure_query=True).created
        with pytest.raises(research.ResearchTaskProviderError) as mismatch:
            reopened.start_research_task(request)
        assert (
            mismatch.value.code
            is research.ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
        )
        historical = replace(request, idempotency_key="historical-v1-0001")
        reopened.start_research_task(historical)
        with pytest.raises(research.ResearchTaskProviderError) as old_mismatch:
            reopened.start_research_task(historical, measure_query=True)
        assert (
            old_mismatch.value.code
            is research.ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
        )
        seen = {}

        def stopped(*args, **kwargs):
            seen.update(kwargs)
            raise ValueError("test-only worker stop")

        monkeypatch.setattr(
            bundle_construction_worker, "reconstruct_and_infer_public", stopped
        )
        result = reopened.run_queued_task(task.task_id)
        assert result.state is research.DirectTaskStateV3.UNRESOLVED
        assert seen["measure_query"] is True
        assert seen["expected_output_dtype"] == "float32"
    finally:
        reopened.close()


@pytest.mark.parametrize("version", ["1.1", "1.3"])
def test_direct_unmeasured_v13_still_enforces_registered_output_dtype(
    tmp_path, monkeypatch, version
):
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5

    material = bundle_material_v5() if version == "1.3" else bundle_material_v3()
    request, provider, _ = _fixture(tmp_path, monkeypatch, material=material)
    tasks = provider()
    try:
        started = tasks.start_research_task(request).task
        seen = {}

        def stopped(*args, **kwargs):
            seen.update(kwargs)
            raise ValueError("test-only worker stop")

        monkeypatch.setattr(
            bundle_construction_worker, "reconstruct_and_infer_public", stopped
        )
        result = tasks.run_queued_task(started.task_id)
        assert result.state is research.DirectTaskStateV3.UNRESOLVED
        assert seen["measure_query"] is False
        assert seen["expected_output_dtype"] == (
            "float32" if version == "1.3" else None
        )
    finally:
        tasks.close()


def test_retained_v2_measurement_is_bound_to_profile_and_shape(tmp_path, monkeypatch):
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5

    material = bundle_material_v5()
    request, provider, _ = _fixture(tmp_path, monkeypatch, material=material)
    tasks = provider()
    started = tasks.start_research_task(request, measure_query=True)
    raw = json.dumps(
        material["practice_reference"].tolist(), separators=(",", ":")
    ).encode()
    prediction_digest = digest(raw)
    state_digest = "sha256:" + "a" * 64
    now = started.task.updated_at_micros + 1
    terminal = research.DirectTaskReceiptV3(
        started.task.task_id,
        research.DirectTaskStateV3.SUCCEEDED,
        started.task.immutable_bindings,
        state_digest,
        prediction_digest,
        None,
        None,
        now,
        ("PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY",),
    )
    succeeded = replace(
        started.task,
        state=research.DirectTaskStateV3.SUCCEEDED,
        revision=1,
        updated_at_micros=now,
        terminal_receipt=terminal,
    )
    # The graded query is unmeasured (one case at a time); the measurement belongs
    # to the separate batched cold query kept only for timing.
    inputs_digest = digest(
        bundle_construction_worker._tensors(inputs=material["practice_inputs"])
    )
    private = {
        "state_digest": state_digest,
        "predictions_digest": prediction_digest,
        "predictions_raw_base64": base64.b64encode(raw).decode("ascii"),
        "inference_receipt": {
            "schema": "carbon.development.bundle-inference.v1",
            "recipe_digest": ConstructionRecipe.from_dict(request.recipe).digest,
            "state_digest": state_digest,
            "inputs_digest": inputs_digest,
            "predictions_digest": prediction_digest,
        },
        "timed_operation": "operation-" + "9" * 64,
        "timed_receipt": {
            "schema": "carbon.development.bundle-inference.v2",
            "recipe_digest": ConstructionRecipe.from_dict(request.recipe).digest,
            "state_digest": state_digest,
            "inputs_digest": inputs_digest,
            "predictions_digest": prediction_digest,
            "measurement": {
                "scope": "COLD_SINGLE_WORKER_QUERY_INCLUDES_GRAPH_LOAD_AND_JAX_COMPILE",
                "timing_s": {
                    "preprocess": 0.1,
                    "inference": 0.2,
                    "postprocess": 0.1,
                    "export": 0.1,
                },
                "input_shape": list(material["practice_inputs"].shape),
                "input_dtype": str(material["practice_inputs"].dtype),
                "output_shape": list(material["expected_output_shape"]),
                "output_dtype": material["interface_document"]["outputs"]["dtype"],
            },
        },
    }
    with tasks._db() as db:
        db.execute(
            "INSERT INTO direct_evidence VALUES(?,?)",
            (started.task.task_id.value, canonical(private)),
        )
        db.execute(
            "UPDATE direct_tasks SET view=? WHERE id=?",
            (research.canonical_bytes(succeeded), started.task.task_id.value),
        )
    tasks._views[started.task.task_id.value] = succeeded
    assert (
        tasks.private_attempt(started.task.task_id)["timed_receipt"]
        == private["timed_receipt"]
    )
    tasks.close()
    reopened = provider()
    try:
        readback = reopened.private_attempt(started.task.task_id)
        assert readback["timed_receipt"]["measurement"]["timing_s"]["inference"] == 0.2
        bad = {**private, "timed_receipt": {**private["timed_receipt"]}}
        bad["timed_receipt"]["measurement"] = {
            **private["timed_receipt"]["measurement"],
            "output_shape": [1],
        }
        with reopened._db() as db:
            db.execute(
                "UPDATE direct_evidence SET body=? WHERE id=?",
                (canonical(bad), started.task.task_id.value),
            )
        with pytest.raises(ValueError, match="retained direct measurement differs"):
            reopened.public_result(succeeded)
    finally:
        reopened.close()


def test_direct_v3_forged_c03_result_without_ledger_controls_is_unresolved(
    tmp_path, monkeypatch
):
    request, provider, _discovery = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        started = tasks.start_research_task(request)
        recipe_digest = ConstructionRecipe.from_dict(request.recipe).digest
        state_digest = "sha256:" + "a" * 64
        fake = bundle_construction_worker.DirectReconstructionResult(
            bundle_construction_worker.BundleBuildResult(
                recipe_digest,
                state_digest,
                tmp_path / "missing-state.npz",
                "operation-" + "b" * 64,
                {},
            ),
            bundle_construction_worker.BundleInferenceResult(
                recipe_digest,
                state_digest,
                "sha256:" + "c" * 64,
                [],
                "operation-" + "d" * 64,
                {},
            ),
            request.construction_limits_digest,
            "C03_DOCKER",
            "sha256:" + "e" * 64,
            "sha256:" + "f" * 64,
            0.1,
        )
        monkeypatch.setattr(
            bundle_construction_worker,
            "reconstruct_and_infer_public",
            lambda *args, **kwargs: fake,
        )
        view = tasks.run_queued_task(started.task.task_id)
        assert view.state is research.DirectTaskStateV3.UNRESOLVED
        assert tasks.private_attempt(started.task.task_id) is None
    finally:
        tasks.close()


def test_direct_restart_reconciles_before_image_doctor_failure(tmp_path, monkeypatch):
    request, provider, _discovery = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        started = tasks.start_research_task(request)
        tasks._transition(started.task, research.DirectTaskStateV3.RUNNING)
    finally:
        tasks.close()
    monkeypatch.setattr(
        "carbon.development_session.research_image.verify_library_worker_image",
        lambda image: (_ for _ in ()).throw(ValueError("image unavailable")),
    )
    with pytest.raises(ValueError, match="image unavailable"):
        provider()
    # The recovery state was saved before admission refused the missing image.
    monkeypatch.setattr(
        "carbon.development_session.research_image.verify_library_worker_image",
        lambda image: image,
    )
    recovered = provider()
    try:
        view = recovered.get_research_result(
            research.DirectGetTaskRequestV3(request.challenge_key, started.task.task_id)
        ).task
        assert view.state is research.DirectTaskStateV3.FAILED_INFRA
        assert (
            view.terminal_receipt.infrastructure_failure_class
            is research.InfrastructureFailureClass.WORKER_LOST
        )
    finally:
        recovered.close()


def test_direct_cancellation_retries_child_flags_after_write_failure(
    tmp_path, monkeypatch
):
    request, provider, _discovery = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        started = tasks.start_research_task(request)
        tasks._transition(started.task, research.DirectTaskStateV3.RUNNING)
        from carbon.development_session import research_tasks

        real = research_tasks.request_cancel
        calls = 0

        def fail_once(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("flag write failed")
            return real(*args, **kwargs)

        monkeypatch.setattr(research_tasks, "request_cancel", fail_once)
        cancellation = research.DirectCancelTaskRequestV3(
            request.challenge_key,
            started.task.task_id,
            "direct-cancel-retry-001",
        )
        with pytest.raises(OSError, match="flag write failed"):
            tasks.cancel_research_task(cancellation)
        view = tasks.get_research_result(
            research.DirectGetTaskRequestV3(request.challenge_key, started.task.task_id)
        ).task
        assert view.state is research.DirectTaskStateV3.CANCEL_REQUESTED
        retry = tasks.cancel_research_task(cancellation)
        assert retry.disposition is research.CancellationDisposition.ALREADY_ACCEPTED
        assert calls == 3  # historical image tasks retain both child flags
    finally:
        tasks.close()


def test_direct_cancel_before_child_reservation_blocks_both_phases(
    tmp_path, monkeypatch
):
    request, provider, _discovery = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        started = tasks.start_research_task(request)
        tasks._transition(started.task, research.DirectTaskStateV3.RUNNING)
        cancellation = research.DirectCancelTaskRequestV3(
            request.challenge_key,
            started.task.task_id,
            "direct-cancel-before-reserve-001",
        )
        result = tasks.cancel_research_task(cancellation)
        assert result.task.state is research.DirectTaskStateV3.CANCEL_REQUESTED
        from carbon.development_session.research_carrier import _check_cancel

        for child in tasks._children(started.task.task_id):
            assert tasks.ledger.operation_state(child, owner=tasks.owner) is None
            with pytest.raises(ValueError, match="cancelled"):
                _check_cancel(tasks.ledger, tasks.owner, child)
        tasks._reconcile_interrupted()
        terminal = tasks.get_research_result(
            research.DirectGetTaskRequestV3(request.challenge_key, started.task.task_id)
        ).task
        assert terminal.state is research.DirectTaskStateV3.CANCELLED
    finally:
        tasks.close()


def test_direct_v3_authenticated_start_dispatches_to_refusal(tmp_path, monkeypatch):
    # Trusted local task configuration exercises authenticated scheduling;
    # default public construction remains discovery-only.
    request, provider, discovery = _fixture(tmp_path, monkeypatch)
    state = _snapshot()
    gateway = AuthenticatedGateway(
        CONTEXT,
        request.challenge_key,
        "validator",
        _Adapter(state),
        _Verifier(),
        ReceiptJournal(tmp_path / "transport.sqlite3", CONTEXT),
        clock_ns=lambda: NOW,
    )
    probe = research.ServiceCall(
        research.RESEARCH_NAMESPACE,
        "get_challenge_info",
        research.GetChallengeInfoRequest(request.challenge_key),
    )
    probe_wire = message(
        CONTEXT,
        state.snapshot_id,
        request.challenge_key,
        session="research",
        request="direct-probe-1",
        tool=research.RESEARCH_NAMESPACE,
        fields={
            "call_base64": base64.b64encode(research.canonical_bytes(probe)).decode(
                "ascii"
            )
        },
    )
    owner = asyncio.run(
        gateway.receive(probe_wire, _headers(probe_wire, NOW))
    ).requester.value
    tasks = provider(owner)
    try:
        service = research.LocalResearchService(
            research.DirectPublicResearchContext(discovery, discovery, tasks)
        )
        wrapper = AuthenticatedResearchService(gateway, {owner: service})
        composition = SimpleNamespace(service=service, tasks=tasks)
        monkeypatch.setattr(
            bundle_construction_worker,
            "reconstruct_and_infer_public",
            lambda *args, **kwargs: {"claimed": "success"},
        )
        call = research.ServiceCall(
            research.RESEARCH_NAMESPACE, "start_research_task", request
        )
        wire = message(
            CONTEXT,
            state.snapshot_id,
            request.challenge_key,
            session="research",
            request="direct-call-1",
            tool=research.RESEARCH_NAMESPACE,
            fields={
                "call_base64": base64.b64encode(research.canonical_bytes(call)).decode(
                    "ascii"
                )
            },
        )
        result = asyncio.run(
            wrapper.supervised_call(wire, _headers(wire, NOW + 1), {owner: composition})
        )
        reply = research.load_canonical(
            base64.b64decode(result["protocol_reply_base64"]), research.ServiceReply
        )
        assert reply.status is research.ReplyStatus.OK
        assert type(reply.result) is research.DirectStartTaskResultV3
        observed = research.load_canonical(
            base64.b64decode(result["terminal_observation_base64"]),
            research.DirectTaskViewV3,
        )
        assert observed.state is research.DirectTaskStateV3.UNRESOLVED
        assert result["public_result"] is None
        assert result["requires_reconciliation"] is False
    finally:
        tasks.close()
