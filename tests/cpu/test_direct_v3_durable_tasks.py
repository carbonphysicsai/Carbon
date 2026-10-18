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


def test_direct_v3_resolves_each_bundle_and_refuses_changed_child_on_restart(
    tmp_path, monkeypatch
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

    def provider():
        return DirectDevelopmentTasksV3(
            root=tmp_path / "per-recipe-tasks",
            requester="miner",
            ledger=ledger,
            owner="miner",
            discovery=discovery,
            image=None,
            inference_image=parent,
            image_resolver=resolve,
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
    installed[first_ref["bundle_digest"]] = LibraryWorkerImage(
        replace(image.provisioned, image_id="sha256:" + "8" * 64),
        parent,
        first_ref,
    )
    reopened = provider()
    try:
        assert (
            reopened.get_research_result(
                research.DirectGetTaskRequestV3(
                    second_request.challenge_key, second.task_id
                )
            ).task.state
            is research.DirectTaskStateV3.CANCELLED
        )
        refused = reopened.run_queued_task(first.task_id)
        assert refused.state is research.DirectTaskStateV3.FAILED_INFRA
        assert (
            refused.terminal_receipt.infrastructure_failure_class
            is research.InfrastructureFailureClass.DEPENDENCY_UNAVAILABLE
        )
        assert reopened.private_attempt(first.task_id) is None
    finally:
        reopened.close()


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
        terminal = tasks._transition(started, state, receipt=receipt)
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
    private = {
        "state_digest": state_digest,
        "predictions_digest": prediction_digest,
        "predictions_raw_base64": base64.b64encode(raw).decode("ascii"),
        "inference_receipt": {
            "schema": "carbon.development.bundle-inference.v2",
            "recipe_digest": ConstructionRecipe.from_dict(request.recipe).digest,
            "state_digest": state_digest,
            "inputs_digest": digest(
                bundle_construction_worker._tensors(inputs=material["practice_inputs"])
            ),
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
        tasks.private_attempt(started.task.task_id)["inference_receipt"]
        == private["inference_receipt"]
    )
    tasks.close()
    reopened = provider()
    try:
        readback = reopened.private_attempt(started.task.task_id)
        assert (
            readback["inference_receipt"]["measurement"]["timing_s"]["inference"] == 0.2
        )
        bad = {**private, "inference_receipt": {**private["inference_receipt"]}}
        bad["inference_receipt"]["measurement"] = {
            **private["inference_receipt"]["measurement"],
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
        assert calls == 3  # both child flags on the retry
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
