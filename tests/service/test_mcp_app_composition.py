"""Optional factory wiring never converts research scope into Workbench rights."""

import asyncio
from dataclasses import replace

import pytest

from tests.service.test_standard_mcp_apps import configured
from tests.service.test_standard_mcp_http import RESOURCE, token, verifier
from tests.service.test_standard_mcp_http import keys as rsa_keys


@pytest.fixture(name="keys")
def _keys():
    return rsa_keys.__wrapped__()


def test_real_server_default_absence_and_http_additional_scope(
    keys, tmp_path, monkeypatch
):
    import httpx2
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client
    from mcp.server.auth.middleware.auth_context import get_access_token
    from mcp.shared.exceptions import MCPError

    from carbon.miner_mcp.mcp_apps import APP_URI, TOOL_NAME, packaged_app
    from carbon.miner_mcp.standard_http import BoundTokenVerifier, create_http_app
    from carbon.miner_mcp.standard_server import _create_server

    service, _, _, _, executions, calls, composition = configured(tmp_path, monkeypatch)
    original = verifier(keys)
    bound = BoundTokenVerifier(
        replace(original.binding, principal=service.adapter.principal),
        public_keys={"fixture-key": keys[1]},
    )

    def authorize_workbench():
        current = get_access_token()
        if current is None or "carbon:workbench:public-studies" not in current.scopes:
            raise PermissionError("separate Workbench scope required")

    for partial in (
        {"workbench": service},
        {"authorize_workbench": authorize_workbench},
    ):
        with pytest.raises(TypeError):
            _create_server(service.adapter, **partial)
    default = create_http_app(service.adapter, bound)
    explicit = create_http_app(
        service.adapter,
        bound,
        workbench=service,
        authorize_workbench=authorize_workbench,
    )

    async def exercise():
        async with (
            default.router.lifespan_context(default),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=default),
                headers={"authorization": "Bearer " + token(keys)},
            ) as http,
            Client(streamable_http_client(RESOURCE, http_client=http)) as client,
        ):
            assert TOOL_NAME not in {
                tool.name for tool in (await client.list_tools()).tools
            }
            assert APP_URI not in {
                str(item.uri) for item in (await client.list_resources()).resources
            }
            with pytest.raises(MCPError):
                await client.read_resource(APP_URI)
        async with (
            explicit.router.lifespan_context(explicit),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=explicit),
                headers={"authorization": "Bearer " + token(keys)},
            ) as http,
        ):
            async with Client(
                streamable_http_client(RESOURCE, http_client=http)
            ) as client:
                assert TOOL_NAME in {
                    tool.name for tool in (await client.list_tools()).tools
                }
                denied = await client.call_tool(
                    TOOL_NAME, {"action": "capabilities", "request": None}
                )
                assert denied.is_error
                with pytest.raises(MCPError):
                    await client.read_resource(APP_URI)
            http.headers["authorization"] = "Bearer " + token(
                keys,
                changes={"scope": "carbon:research carbon:workbench:public-studies"},
            )
            async with Client(
                streamable_http_client(RESOURCE, http_client=http)
            ) as client:
                allowed = await client.call_tool(
                    TOOL_NAME, {"action": "capabilities", "request": None}
                )
                assert not allowed.is_error
                assert allowed.structured_content["response"]["available"] is True
                assert (await client.read_resource(APP_URI)).contents[
                    0
                ].text == packaged_app()
        assert executions == calls == []

    try:
        asyncio.run(exercise())
    finally:
        composition.tasks.close()
