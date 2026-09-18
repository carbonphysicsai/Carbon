"""Official SDK wire plus existing Workbench domain fixture; no paid host claim."""

from __future__ import annotations

import asyncio
import json
import sys
from copy import copy
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPOSITORY), str(REPOSITORY / "tests/cpu")]

from carbon.miner_mcp.mcp_apps import (
    APP_EXTENSION,
    APP_META,
    APP_MIME,
    APP_URI,
    TOOL_NAME,
    make_workbench_app_extension,
    packaged_app,
)
from tests.cpu.test_workbench_science import configured


def test_app_wire_fallback_exact_service_and_separate_authorization(
    tmp_path, monkeypatch
):
    import httpx2
    from mcp import Client
    from mcp.client.extension import advertise
    from mcp.client.streamable_http import streamable_http_client
    from mcp.server import MCPServer
    from mcp.server.transport_security import TransportSecuritySettings
    from mcp.shared.exceptions import MCPError

    service, request, records, ledger, executions, calls, composition = configured(
        tmp_path, monkeypatch
    )
    allowed = {"research": True, "workbench": True}

    def research_guard():
        if not allowed["research"]:
            raise PermissionError("private research token diagnostic")

    def workbench_guard():
        if not allowed["workbench"]:
            raise PermissionError("private Workbench rights diagnostic")

    extension = make_workbench_app_extension(
        adapter=service.adapter,
        workbench=service,
        authorize_workbench=workbench_guard,
        guard=research_guard,
    )
    server = MCPServer("Carbon App deterministic fixture", extensions=[extension])
    application = server.streamable_http_app(
        json_response=True,
        stateless_http=True,
        transport_security=TransportSecuritySettings(allowed_hosts=["localhost"]),
    )

    async def exercise():
        async with (
            application.router.lifespan_context(application),
            httpx2.AsyncClient(transport=httpx2.ASGITransport(app=application)) as http,
        ):
            async with Client(
                streamable_http_client("http://localhost/mcp", http_client=http),
                extensions=[advertise(APP_EXTENSION, {"mimeTypes": [APP_MIME]})],
            ) as client:
                listing = await client.list_tools()
                tool = next(item for item in listing.tools if item.name == TOOL_NAME)
                assert tool.meta["ui"]["resourceUri"] == APP_URI
                assert tool.input_schema["properties"]["action"]["enum"] == [
                    "capabilities",
                    "start",
                    "status",
                    "result",
                    "cancel",
                ]
                html = await client.read_resource(APP_URI)
                assert html.contents[0].text == packaged_app()
                assert html.contents[0].mime_type == APP_MIME
                assert html.contents[0].meta == APP_META
                assert executions == calls == []
                for arguments in (
                    {"action": "start", "request": json.dumps(request)},
                    {"action": "start", "request": request, "principal": "other"},
                    {"action": "capabilities", "request": request},
                    {"action": "start", "request": None},
                ):
                    bad = await client.call_tool(TOOL_NAME, arguments)
                    assert bad.is_error
                assert executions == calls == []
                for permission in ("workbench", "research"):
                    allowed[permission] = False
                    denied = await client.call_tool(
                        TOOL_NAME, {"action": "start", "request": request}
                    )
                    assert denied.is_error and "private" not in json.dumps(
                        denied.model_dump(mode="json")
                    )
                    with pytest.raises(MCPError):
                        await client.read_resource(APP_URI)
                    allowed[permission] = True
                assert executions == calls == []
                started = await client.call_tool(
                    TOOL_NAME, {"action": "start", "request": request}
                )
                assert not started.is_error
                payload = started.structured_content
                assert json.loads(started.content[0].text) == payload
                assert payload["request"] == request
                assert payload["response"]["status"] == "COMPLETE"
                assert payload["response"]["qualification"] == "NOT_QUALIFIED"
                task_id = payload["response"]["task_id"]
                (tmp_path / "browser-fixture.json").write_text(
                    json.dumps(
                        {
                            "request": request,
                            "structured": payload,
                            "result": started.model_dump(
                                by_alias=True, mode="json", exclude_none=True
                            ),
                        }
                    ),
                    encoding="utf-8",
                )

            # A client without Apps still receives the same result, never HTML in
            # place of structured/text data and never a second numerical run.
            async with Client(
                streamable_http_client("http://localhost/mcp", http_client=http)
            ) as plain:
                for action in ("start", "status", "result", "cancel"):
                    result = await plain.call_tool(
                        TOOL_NAME, {"action": action, "request": request}
                    )
                    assert not result.is_error
                    assert result.structured_content["response"]["task_id"] == task_id
                    assert (
                        json.loads(result.content[0].text) == result.structured_content
                    )
                assert len(executions) == 1
                assert (
                    ledger.status(owner=service.adapter.principal)["used"][
                        "reference_invocations"
                    ]
                    == 2
                )
                records.clear()
                denied = await plain.call_tool(
                    TOOL_NAME, {"action": "start", "request": request}
                )
                assert denied.is_error and len(executions) == 1

    try:
        asyncio.run(exercise())
    finally:
        composition.tasks.close()


def test_app_requires_exact_bound_service_and_operator_authorizer(
    tmp_path, monkeypatch
):
    service, _, _, _, _, _, composition = configured(tmp_path, monkeypatch)
    try:
        for changes in (
            {"adapter": object()},
            {"adapter": copy(service.adapter)},
            {"workbench": object()},
            {"authorize_workbench": None},
            {"guard": "caller-selected"},
        ):
            with pytest.raises(TypeError):
                make_workbench_app_extension(
                    **(
                        {
                            "adapter": service.adapter,
                            "workbench": service,
                            "authorize_workbench": lambda: None,
                        }
                        | changes
                    )
                )
    finally:
        composition.tasks.close()
