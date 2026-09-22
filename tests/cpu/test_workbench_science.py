"""Draft authority and real shared lifecycle tests with a synthetic worker."""

import asyncio
import threading
import time
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_julia_research import prepared

from carbon import research
from carbon.development_session.julia_research import (
    JuliaPublicMaterial,
    PublicJuliaStudy,
)
from carbon.development_session.research_material import PublicMaterial
from carbon.development_session.research_service import make_research_service
from carbon.development_session.research_tools import ResearchMinerTools, public_wire
from carbon.miner_mcp.standard import ResearchToolAdapter
from carbon.scientific_tasks.workbench import (
    REQUEST,
    TEMPLATE,
    RegisteredWorkbenchDraft,
    WorkbenchScience,
    wire_digest,
)


def configured(tmp_path, monkeypatch, *, image=None, envelope=False):
    data, ledger, executions = prepared(
        tmp_path, monkeypatch, image=image, envelope=envelope
    )
    from carbon.development_session.julia_envelope import (
        JuliaEnvelopeMaterial,
        julia_envelope_scope,
    )

    scope = julia_envelope_scope(data.image, data.role_root) if envelope else None
    material = JuliaPublicMaterial(
        PublicMaterial(data), PublicJuliaStudy(data, envelope_scope=scope)
    )
    if envelope:
        material = JuliaEnvelopeMaterial(material)
    composition = make_research_service(
        root=tmp_path / "tasks",
        ledger=ledger,
        owner=data.owner,
        image=data.image,
        public_material=material,
        practice=None,
    )

    async def registered():
        return None

    sdk = ResearchMinerTools(
        connection=SimpleNamespace(check_registration=registered),
        wrapper=object(),
        composition=composition,
        ledger=ledger,
        owner=data.owner,
    )
    calls = []

    async def domain(self, name, args, identity, *, transport_request_id=None):
        calls.append((name, identity))
        operation = name.removeprefix("carbon_research_v2__")
        spec = self._request(operation, args, identity)
        reply = composition.service.call(
            research.ServiceCall(research.RESEARCH_NAMESPACE, operation, spec)
        )
        task = None
        projection = None
        if reply.status is research.ReplyStatus.OK:
            task = reply.result.task
            if (
                operation == "start_research_task"
                and task.state is research.ResearchTaskState.QUEUED
            ):
                task = await asyncio.to_thread(
                    composition.tasks.run_queued_task, task.task_id
                )
            projection = composition.executor.public_result(task)
        return {
            "protocol": research.RESEARCH_NAMESPACE,
            "operation": operation,
            "reply": public_wire(reply),
            "terminal_task": public_wire(task) if task else None,
            "public_result": projection,
            "requires_reconciliation": False,
        }

    monkeypatch.setattr(ResearchMinerTools, "_call", domain)
    adapter = ResearchToolAdapter(sdk, principal=data.owner)
    records = {}

    def resolve(principal, job, design, revision):
        return records.get((principal, job, design, revision))

    service = WorkbenchScience(adapter, draft_resolver=resolve)
    physical = asyncio.run(service.capabilities())["physical"]
    scope = {
        key: "operator reviewed fixture"
        for key in (
            "inputs",
            "outputs",
            "units",
            "geometry",
            "conditions",
            "regime",
            "exclusions",
            "query_workload",
            "reference_equation",
            "reference_method",
        )
    }
    scope.update(
        physics_family=TEMPLATE,
        requested_goal="Dynamics",
        rights_scope="SYNTHETIC_INTERNAL",
    )
    record = RegisteredWorkbenchDraft(
        data.owner, "job-one", "design-one", 1, 1, scope, physical, "SYNTHETIC_INTERNAL"
    )
    records[(data.owner, "job-one", "design-one", 1)] = record
    binding = {
        "job_id": "job-one",
        "design_id": "design-one",
        "design_revision": 1,
        "physical_sha256": wire_digest(
            {"template_id": TEMPLATE, "physical": physical, "draft_scope": scope}
        ),
    }
    request = {
        "schema": REQUEST,
        "operation_id": "study-" + wire_digest(binding),
        "action": "REFERENCE_FEASIBILITY",
        "binding": binding,
        "template_id": TEMPLATE,
        "physical": physical,
        "draft_scope": scope,
        "rights_scope": "SYNTHETIC_INTERNAL",
    }
    return service, request, records, ledger, executions, calls, composition


def test_js_python_number_identity_vector():
    assert (
        wire_digest({"z": [0, -0.0, 1, 0.1], "a": "μ"})
        == "6bc889a793327e63b9457521c3cb14581a39d075248b518251b8b711f5aa31bf"
    )


def test_same_task_and_ledger_results_across_workbench_reconnect(tmp_path, monkeypatch):
    service, request, _records, ledger, executions, _calls, composition = configured(
        tmp_path, monkeypatch
    )
    try:
        first = asyncio.run(service.call("start", request))
        assert first["status"] == "COMPLETE"
        assert first["result"]["values"] == [[0.0] * 64 for _ in range(13)]
        reopened = WorkbenchScience(service.adapter, draft_resolver=service.resolver)
        for action in ("start", "status", "result"):
            result = asyncio.run(reopened.call(action, request))
            assert result["task_id"] == first["task_id"]
            assert result["binding"] == request["binding"]
        assert len(executions) == 1
        assert (
            ledger.status(owner=service.adapter.principal)["used"][
                "reference_invocations"
            ]
            == 2
        )
        assert (
            first["remaining_budget"]["reference_invocations_remaining"]
            # 2048 service capacity less the 2 consumed. The former 144
            # final reserve is no longer withheld: reserving is the
            # miner's choice, not a standing deduction.
            == 2048 - 2
        )
        assert (
            first["official_eligible"] is False
            and first["qualification"] == "NOT_QUALIFIED"
        )
    finally:
        composition.tasks.close()


@pytest.mark.parametrize("change", ["missing", "owner", "scope", "revision", "rights"])
def test_client_rights_never_replace_registered_draft_authority(
    tmp_path, monkeypatch, change
):
    service, request, records, _ledger, executions, calls, composition = configured(
        tmp_path, monkeypatch
    )
    key = next(iter(records))
    original = records[key]
    if change == "missing":
        records.clear()
    elif change == "owner":
        records[key] = replace(original, principal="other-user")
    elif change == "scope":
        records[key] = replace(
            original,
            draft_scope={**original.draft_scope, "conditions": "different condition"},
        )
    elif change == "revision":
        records[key] = replace(original, current_revision=2)
    else:
        records[key] = replace(original, rights_scope="CUSTOMER_PRIVATE")
    try:
        with pytest.raises(PermissionError, match="operator draft binding"):
            asyncio.run(service.call("start", request))
        assert calls == executions == []
    finally:
        composition.tasks.close()


def test_late_draft_change_retains_task_but_rejects_association_and_allows_cancel(
    tmp_path, monkeypatch
):
    service, request, records, ledger, executions, _calls, composition = configured(
        tmp_path, monkeypatch
    )
    key = next(iter(records))
    original_call = ResearchToolAdapter.call

    async def changed(self, value):
        result = await original_call(self, value)
        records[key] = replace(records[key], current_revision=2)
        return result

    monkeypatch.setattr(ResearchToolAdapter, "call", changed)
    try:
        with pytest.raises(PermissionError, match="stale"):
            asyncio.run(service.call("start", request))
        assert len(executions) == 1
        assert (
            ledger.status(owner=service.adapter.principal)["used"][
                "reference_invocations"
            ]
            == 2
        )
        cancelled = asyncio.run(service.call("cancel", request))
        assert cancelled["binding"] == request["binding"]
        assert len(executions) == 1
    finally:
        composition.tasks.close()


def test_status_cannot_start_work_and_tampered_artifact_is_rejected(
    tmp_path, monkeypatch
):
    service, request, _records, _ledger, _executions, calls, composition = configured(
        tmp_path, monkeypatch
    )
    try:
        with pytest.raises(ValueError, match="no existing admitted task"):
            asyncio.run(service.call("status", request))
        assert calls == []
        result = asyncio.run(service.call("start", request))
        name = result["result"]["metadata"]["solution"]
        workspace = composition.executor.workspace
        from carbon.development_session.profile import digest

        workspace.put(name, b"tampered", expected_digest=digest(workspace.get(name)))
        with pytest.raises(ValueError, match="artifact changed"):
            asyncio.run(service.call("result", request))
    finally:
        composition.tasks.close()


def test_expired_grant_can_cancel_owned_running_work_without_new_admission(
    tmp_path, monkeypatch
):
    service, request, records, ledger, _executions, _calls, composition = configured(
        tmp_path, monkeypatch
    )
    running, stopped = threading.Event(), threading.Event()
    attempts = []

    def cancellable(value, *, cancelled):
        attempts.append(value.request_digest)
        running.set()
        deadline = time.monotonic() + 10
        while not cancelled() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert cancelled(), "owned cancellation must reach the worker supervisor"
        stopped.set()
        raise RuntimeError("synthetic worker cancelled; reconciliation retained")

    service.material.study.data.controller = SimpleNamespace(execute=cancellable)

    async def exercise():
        started = asyncio.create_task(service.call("start", request))
        for _ in range(1000):
            if running.is_set():
                break
            await asyncio.sleep(0.01)
        assert running.is_set()
        ledger.clock = lambda: 50001
        before = ledger.status(owner=service.adapter.principal)["used"]
        result = await service.call("cancel", request)
        assert result["status"] in {"CANCEL_REQUESTED", "REQUIRES_RECONCILIATION"}
        await started
        assert stopped.is_set()
        assert ledger.status(owner=service.adapter.principal)["used"] == before
        with pytest.raises(ValueError, match="expired"):
            await service.call("start", request)
        key = next(iter(records))
        records[key] = replace(records[key], principal="different-principal")
        with pytest.raises(PermissionError):
            await service.call("cancel", request)

    try:
        asyncio.run(exercise())
        assert len(attempts) == 1
        assert (
            ledger.status(owner=service.adapter.principal)["used"][
                "numerical_milliseconds"
            ]
            == 720000
        )
    finally:
        composition.tasks.close()
