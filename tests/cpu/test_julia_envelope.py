"""Synthetic public sources exercise the real sequence/service contracts."""

import asyncio
from dataclasses import replace

import pytest
from test_workbench_science import configured

from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_carrier import ACTIVE_TASK
from carbon.scientific_tasks.workbench import (
    ENVELOPE_REQUEST,
    WorkbenchScience,
    wire_digest,
)


def request(service, baseline):
    scope_digest = digest(canonical(service.material.envelope.scope))
    return {
        **baseline,
        "schema": ENVELOPE_REQUEST,
        "action": "OPERATING_ENVELOPE",
        "envelope_scope_digest": scope_digest,
        "operation_id": "envelope-"
        + wire_digest({"binding": baseline["binding"], "scope_digest": scope_digest}),
    }


def test_two_case_admission_reconnect_and_both_workbench_actions(tmp_path, monkeypatch):
    service, baseline, records, ledger, executions, _calls, composition = configured(
        tmp_path, monkeypatch, envelope=True
    )
    try:
        cap = asyncio.run(service.capabilities())
        assert len(cap["envelope"]["physical"]) == 2
        envelope = request(service, baseline)
        first = asyncio.run(service.call("start", envelope))
        assert first["status"] == "COMPLETE"
        children = first["result"]["children"]
        assert len(children) == 2
        assert all(c["state"] == "SUCCEEDED" for c in children)
        assert children[0]["case_digest"] != children[1]["case_digest"]
        assert len(executions) == 2
        assert (
            ledger.status(owner=service.adapter.principal)["used"][
                "reference_invocations"
            ]
            == 4
        )
        reopened = WorkbenchScience(service.adapter, draft_resolver=service.resolver)
        for action in ("start", "status", "result"):
            again = asyncio.run(reopened.call(action, envelope))
            assert again["task_id"] == first["task_id"]
            assert again["result"] == first["result"]
        assert len(executions) == 2
        feasibility = asyncio.run(service.call("start", baseline))
        assert feasibility["status"] == "COMPLETE"
        assert len(executions) == 3
        key = next(iter(records))
        records[key] = replace(records[key], current_revision=2)
        with pytest.raises(PermissionError):
            asyncio.run(service.call("result", envelope))
    finally:
        composition.tasks.close()


def test_v1_grant_and_scope_tampering_cannot_start_envelope(tmp_path, monkeypatch):
    service, baseline, _, _ledger, executions, _, composition = configured(
        tmp_path, monkeypatch
    )
    try:
        forged = {
            **baseline,
            "schema": ENVELOPE_REQUEST,
            "action": "OPERATING_ENVELOPE",
            "envelope_scope_digest": digest(b"not-granted"),
        }
        with pytest.raises(ValueError, match="scope differs"):
            asyncio.run(service.call("start", forged))
        assert executions == []
    finally:
        composition.tasks.close()


def test_partial_result_and_expired_cancel_release_only_second_child(
    tmp_path, monkeypatch
):
    service, _baseline, _, ledger, executions, _, composition = configured(
        tmp_path, monkeypatch, envelope=True
    )
    try:
        material = service.material.envelope
        original = material._execute

        def execute(workspace, numerical, child, parent):
            original(workspace, numerical, child, parent)
            ledger.clock = lambda: 50001

        monkeypatch.setattr(material, "_execute", execute)
        token = ACTIVE_TASK.set("fixture-parent")
        try:
            with pytest.raises(ValueError, match="expired"):
                material(composition.executor.workspace)
        finally:
            ACTIVE_TASK.reset(token)
        partial = material.projection("fixture-parent", composition.executor.workspace)
        assert [c["state"] for c in partial["children"]] == ["SUCCEEDED", "CANCELLED"]
        assert partial["children"][0]["result"] is not None
        assert partial["children"][1]["result"] is None
        assert (
            ledger.status(owner=service.adapter.principal)["used"][
                "reference_invocations"
            ]
            == 2
        )
        ledger.settle_sequence("fixture-parent", owner=service.adapter.principal)
        assert len(executions) == 1
    finally:
        composition.tasks.close()
