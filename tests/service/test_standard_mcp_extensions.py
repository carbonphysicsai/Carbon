"""Released Tasks/Skills wire contracts through the independent Python SDK.

This deterministic protocol fixture does not claim hardware or agent usefulness.
Signed controller/task lifecycle tests separately exercise the real adapter.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Literal

import pytest

from tests.service.test_standard_mcp_http import (
    RESOURCE,
    adapter,
    make_keys,
    token,
    verifier,
)

TASK_ID = "rtsk_" + "a" * 64
FOREIGN_ID = "rtsk_" + "b" * 64
OPERATION_ID = "extension-operation-fixture-0001"
PREFIX = "carbon_research_v2__"


@pytest.fixture(scope="module")
def keys():
    return make_keys()


def _arguments():
    return {
        "operation_id": OPERATION_ID,
        "kind": "practice",
        "strategy": {"parameters": {"steps": 512}},
        "action": None,
        "arguments": None,
        "hypothesis": "Exercise a deterministic protocol lifecycle",
        "expected_effect": "The same task is available to reconnected clients",
    }


def _result(state):
    from carbon.miner_mcp.standard import ResearchToolResult

    view = {
        "task_id": {"value": TASK_ID},
        "state": state,
        "created_at_micros": 1_700_000_000_000_001,
        "updated_at_micros": 1_700_000_000_000_002,
    }
    return ResearchToolResult(
        "start_research_task",
        OPERATION_ID,
        {
            "protocol": "fixture",
            "operation": "start_research_task",
            "reply": {"status": "OK", "result": {"created": True, "task": view}},
            "terminal_task": view,
            "public_result": {"fixture_only": True, "state": state},
            "requires_reconciliation": state in {"RUNNING", "CANCEL_REQUESTED"},
        },
        state in {"RUNNING", "CANCEL_REQUESTED"},
    )


def _wire_types():
    from mcp.client.extension import ClientExtension, ResultClaim
    from mcp.types import Request, RequestParams, Result
    from pydantic import Field

    from carbon.miner_mcp.mcp_extensions import TASKS_EXTENSION

    class Handle(Result):
        result_type: Literal["task"] = Field(default="task", alias="resultType")
        task_id: str = Field(alias="taskId")
        status: str
        created_at: str = Field(alias="createdAt")
        last_updated_at: str = Field(alias="lastUpdatedAt")
        ttl_ms: int | None = Field(alias="ttlMs")

    class TaskParams(RequestParams):
        task_id: str = Field(alias="taskId")

    class GetTask(Request[TaskParams, Literal["tasks/get"]]):
        method: Literal["tasks/get"] = "tasks/get"
        name_param = "taskId"

    class CancelTask(Request[TaskParams, Literal["tasks/cancel"]]):
        method: Literal["tasks/cancel"] = "tasks/cancel"
        name_param = "taskId"

    class GetSkills(Request[RequestParams, Literal["skills/list"]]):
        method: Literal["skills/list"] = "skills/list"

    class SkillParams(RequestParams):
        uri: str

    class GetSkill(Request[SkillParams, Literal["skills/get"]]):
        method: Literal["skills/get"] = "skills/get"
        name_param = "uri"

    async def unused_resolver(handle, ctx):
        raise AssertionError("This test explicitly owns its task handle")

    class TasksClient(ClientExtension):
        identifier = TASKS_EXTENSION

        def claims(self):
            return (
                ResultClaim(result_type="task", model=Handle, resolve=unused_resolver),
            )

    return (
        TasksClient,
        Handle,
        TaskParams,
        GetTask,
        CancelTask,
        GetSkills,
        SkillParams,
        GetSkill,
    )


def test_negotiated_tasks_reconnect_results_cancel_and_skills(
    keys, monkeypatch, tmp_path
):
    import httpx2
    from mcp import Client
    from mcp.client.extension import advertise
    from mcp.client.streamable_http import streamable_http_client
    from mcp.shared.exceptions import MCPError
    from mcp.types import Request, RequestParams
    from mcp.types import Result as BaseResult
    from pydantic import ConfigDict, Field

    from carbon.miner_mcp.mcp_skills import FILES, SKILL_URI, SKILLS_EXTENSION
    from carbon.miner_mcp.standard import (
        AdapterCode,
        AdapterFailure,
        ResearchToolAdapter,
    )
    from carbon.miner_mcp.standard_http import create_http_app
    from tests.cpu.test_cw1_research_ledger import ledger

    class Result(BaseResult):
        # Base Result intentionally drops extension-owned fields. An external
        # client must register a result model for the verbs it implements.
        model_config = ConfigDict(extra="allow")

    (
        TasksClient,
        Handle,
        TaskParams,
        GetTask,
        CancelTask,
        GetSkills,
        SkillParams,
        GetSkill,
    ) = _wire_types()

    class UpdateParams(TaskParams):
        input_responses: dict = Field(alias="inputResponses")

    class UpdateTask(Request[UpdateParams, Literal["tasks/update"]]):
        method: Literal["tasks/update"] = "tasks/update"
        name_param = "taskId"

    service, fallback_calls = adapter(monkeypatch, meter=ledger(tmp_path))
    operations = []
    state = {"value": "RUNNING"}

    async def start(self, request):
        operations.append(("start", request.operation_id))
        return _result(state["value"])

    async def observe(self, identity):
        if identity != TASK_ID:
            raise AdapterFailure(AdapterCode.OWNER_BINDING)
        operations.append(("observe", identity))
        return _result(state["value"])

    async def cancel(self, identity):
        await observe(self, identity)
        state["value"] = "CANCEL_REQUESTED"
        return _result(state["value"])

    monkeypatch.setattr(ResearchToolAdapter, "start_task", start)
    monkeypatch.setattr(ResearchToolAdapter, "observe_task", observe)
    monkeypatch.setattr(ResearchToolAdapter, "cancel_task", cancel)
    app = create_http_app(service, verifier(keys))
    requests = []
    responses = []

    async def record(request):
        requests.append(
            (request.headers.get("mcp-method"), request.headers.get("mcp-name"))
        )

    async def record_response(response):
        await response.aread()
        if "application/json" in response.headers.get("content-type", ""):
            responses.append(
                (response.request.headers.get("mcp-method"), response.json())
            )

    async def exercise():
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app),
                headers={"authorization": "Bearer " + token(keys)},
                event_hooks={"request": [record], "response": [record_response]},
            ) as http,
        ):

            def client():
                return Client(
                    streamable_http_client(RESOURCE, http_client=http),
                    extensions=[TasksClient(), advertise(SKILLS_EXTENSION)],
                    read_timeout_seconds=15,
                )

            async with client() as first:
                handle = await first.session.call_tool(
                    PREFIX + "start_research_task", _arguments(), allow_claimed=True
                )
                assert isinstance(handle, Handle)
                assert handle.task_id == TASK_ID and handle.status == "working"
                assert handle.ttl_ms is None
                assert handle.created_at.endswith(".000001Z")
                bad = await first.session.call_tool(
                    PREFIX + "start_research_task",
                    {**_arguments(), "strategy": "{}"},
                    allow_claimed=True,
                )
                assert bad.is_error
                assert operations == [("start", OPERATION_ID)]
                listing = await first.session.send_request(
                    GetSkills(params=RequestParams()), Result
                )
                data = listing.model_dump(by_alias=True, mode="json")
                assert data["cacheScope"] == "private" and data["ttlMs"] == 0
                entry = data["skills"][0]
                direct = await first.session.send_request(
                    GetSkill(params=SkillParams(uri=SKILL_URI)), Result
                )
                assert direct.model_dump(by_alias=True)["skill"] == entry
                assert {r["uri"] for r in entry["resources"]} == {
                    uri for uri, _ in FILES
                }
                for resource in entry["resources"]:
                    result = await first.read_resource(resource["uri"])
                    raw = result.contents[0].text.encode("utf-8")
                    assert len(raw) == resource["size"]
                    assert (
                        "sha256:" + hashlib.sha256(raw).hexdigest()
                        == resource["digest"]
                    )
                with pytest.raises(MCPError) as unknown:
                    await first.session.send_request(
                        GetSkill(params=SkillParams(uri=SKILL_URI + "/../private")),
                        Result,
                    )
                assert unknown.value.code == -32602

            async with client() as second:
                observed = await second.session.send_request(
                    GetTask(params=TaskParams(taskId=TASK_ID)), Result
                )
                initial = observed.model_dump(by_alias=True)
                assert initial["status"] == "working" and "result" not in initial
                with pytest.raises(MCPError) as denied:
                    await second.session.send_request(
                        GetTask(params=TaskParams(taskId=FOREIGN_ID)), Result
                    )
                assert denied.value.code == -32602
                ack = await second.session.send_request(
                    CancelTask(params=TaskParams(taskId=TASK_ID)), Result
                )
                assert "status" not in ack.model_dump()
                pending = await second.session.send_request(
                    GetTask(params=TaskParams(taskId=TASK_ID)), Result
                )
                assert pending.model_dump(by_alias=True)["status"] == "working"
                await second.session.send_request(
                    UpdateTask(
                        params=UpdateParams(
                            taskId=TASK_ID,
                            inputResponses={"not-requested": {"action": "decline"}},
                        )
                    ),
                    Result,
                )
                assert state["value"] == "CANCEL_REQUESTED"
                with pytest.raises(MCPError):
                    await second.session.send_request(
                        UpdateTask(
                            params=UpdateParams(
                                taskId=FOREIGN_ID,
                                inputResponses={},
                            )
                        ),
                        Result,
                    )
                with pytest.raises(MCPError):
                    await second.session.send_request(
                        UpdateTask(
                            params=UpdateParams(
                                taskId=TASK_ID,
                                inputResponses={
                                    str(i): {"action": "decline"} for i in range(65)
                                },
                            )
                        ),
                        Result,
                    )
                for terminal in ("SUCCEEDED", "FAILED_INFRA"):
                    # Independent fixtures test projection, not a domain transition.
                    state["value"] = terminal
                    final = (
                        await second.session.send_request(
                            GetTask(params=TaskParams(taskId=TASK_ID)), Result
                        )
                    ).model_dump(by_alias=True)
                    assert final["status"] == "completed"
                    structured = final["result"]["structuredContent"]
                    assert structured["operation_id"] == OPERATION_ID
                    assert structured["payload"]["public_result"]["state"] == terminal
                    assert structured["official_eligible"] is False
                    assert (
                        json.loads(final["result"]["content"][0]["text"]) == structured
                    )

            # Negotiation belongs to each request; it does not stick to the adapter.
            async with Client(
                streamable_http_client(RESOURCE, http_client=http)
            ) as plain:
                result = await plain.call_tool(
                    PREFIX + "start_research_task", _arguments()
                )
                assert not result.is_error
                with pytest.raises(MCPError) as missing:
                    await plain.session.send_request(
                        GetTask(params=TaskParams(taskId=TASK_ID)), Result
                    )
                assert missing.value.code == -32021

        assert len(fallback_calls) == 1
        assert ("tasks/get", TASK_ID) in requests
        assert ("tasks/cancel", TASK_ID) in requests
        assert any(
            method == "tasks/cancel" and body["result"]["resultType"] == "complete"
            for method, body in responses
            if "result" in body
        )
        assert any(
            method == "tools/call"
            and body["result"].get("resultType") == "task"
            and body["result"].get("taskId") == TASK_ID
            and "task" not in body["result"]
            for method, body in responses
            if "result" in body
        )

    asyncio.run(exercise())
