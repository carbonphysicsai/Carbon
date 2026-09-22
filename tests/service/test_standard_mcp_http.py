"""Authenticated Streamable HTTP interoperability over private in-process ASGI.

RSA keys and domain replies are deterministic-test fixtures only. These tests
launch no network listener and establish no agent-host or paid-model evidence.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import replace
from types import SimpleNamespace

import pytest

ISSUER = "https://issuer.carbon.test/"
RESOURCE = "https://private.carbon.test/mcp"
OPERATION_ID = "http-operation-fixture-0001"
PREFIX = "carbon_research_v2__"


def make_keys():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return private, public


@pytest.fixture(scope="module")
def keys():
    return make_keys()


def token(keys, *, changes=None, omit=(), headers=None):
    import jwt

    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": RESOURCE,
        "sub": "subject-alice",
        "client_id": "client-a",
        "iat": now,
        "exp": now + 120,
        "scope": "carbon:research",
    }
    claims.update(changes or {})
    for name in omit:
        claims.pop(name)
    return jwt.encode(
        claims,
        keys[0],
        algorithm="RS256",
        headers={"kid": "fixture-key", **(headers or {})},
    )


def verifier(keys):
    from carbon.miner_mcp.standard_http import BoundTokenVerifier, HttpPrincipalBinding

    binding = HttpPrincipalBinding(
        ISSUER, RESOURCE, "client-a", "subject-alice", "alice"
    )
    return BoundTokenVerifier(binding, public_keys={"fixture-key": keys[1]})


def adapter(monkeypatch, *, meter=None):
    from carbon import research
    from carbon.development_session.research_tools import ResearchMinerTools
    from carbon.miner_mcp.standard import ResearchToolAdapter

    # Moved with the contract. A research operation now refuses at the entry
    # when there is no campaign to account against, rather than failing deeper
    # with a message about a campaign that does not exist - so a tool call
    # succeeding implies a campaign, and these transport-interop cases have to
    # stand up something to be a campaign even though `_call` is substituted
    # below. A bare object suffices: nothing here reserves, and giving it a real
    # ledger would make a transport test depend on campaign accounting.
    if meter is None:
        meter = object()

    calls = []

    async def reply(self, name, arguments, identity, *, transport_request_id=None):
        calls.append((name, arguments, identity))
        return {
            "protocol": research.RESEARCH_NAMESPACE,
            "operation": name.removeprefix(PREFIX),
            "reply": {"status": "OK", "fixture_only": True, "identity": identity},
            "terminal_task": None,
            "public_result": None,
            "requires_reconciliation": False,
        }

    monkeypatch.setattr(ResearchMinerTools, "_call", reply)
    sdk = ResearchMinerTools(
        connection=object(),
        wrapper=object(),
        composition=SimpleNamespace(executor=SimpleNamespace(owner="alice")),
        ledger=meter,
        owner="alice",
    )
    return ResearchToolAdapter(sdk, principal="alice"), calls


def rpc(method, params=None, identity=1):
    return {"jsonrpc": "2.0", "id": identity, "method": method, "params": params or {}}


def headers(value=None, session=None):
    result = {
        "accept": "application/json, text/event-stream",
        "mcp-protocol-version": "2025-11-25",
    }
    if value is not None:
        result["authorization"] = "Bearer " + value
    if session is not None:
        result["mcp-session-id"] = session
    return result


async def initialize(client, value):
    response = await client.post(
        RESOURCE,
        headers=headers(value),
        json=rpc(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {
                    "name": "carbon-independent-http-fixture",
                    "version": "1",
                },
            },
        ),
    )
    assert response.status_code == 200, response.text
    session = response.headers["mcp-session-id"]
    response = await client.post(
        RESOURCE,
        headers=headers(value, session),
        json={
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        },
    )
    assert response.status_code == 202, response.text
    return session


@pytest.mark.parametrize(
    "changes,omit,header",
    (
        ({"iss": "https://wrong.test/"}, (), {}),
        ({"aud": "https://wrong.test/mcp"}, (), {}),
        ({"aud": [RESOURCE]}, (), {}),
        ({"sub": "subject-bob"}, (), {}),
        ({"client_id": "client-b"}, (), {}),
        ({"scope": "carbon:operator"}, (), {}),
        ({"scope": ["carbon:research"]}, (), {}),
        ({"exp": 1}, (), {}),
        ({"iat": 9999999999}, (), {}),
        ({"exp": True}, (), {}),
        ({}, ("exp",), {}),
        ({}, ("sub",), {}),
        ({}, (), {"kid": "unreviewed-key"}),
        ({}, (), {"jku": "https://untrusted.test/keys"}),
    ),
)
def test_exact_token_claims_fail_closed(keys, changes, omit, header):
    assert (
        asyncio.run(
            verifier(keys).verify_token(
                token(keys, changes=changes, omit=omit, headers=header)
            )
        )
        is None
    )


def test_valid_token_and_principal_binding(keys, monkeypatch):
    from carbon.miner_mcp.standard_http import BoundTokenVerifier, create_http_app

    bound = verifier(keys)
    accepted = asyncio.run(bound.verify_token(token(keys)))
    assert accepted.subject == "subject-alice"
    assert accepted.resource == RESOURCE
    service, _ = adapter(monkeypatch)
    wrong = BoundTokenVerifier(
        replace(bound.binding, principal="bob"), public_keys={"fixture-key": keys[1]}
    )
    with pytest.raises(ValueError, match="identity"):
        create_http_app(service, wrong)


def test_http_direct_access_denied_and_transport_limits(keys, monkeypatch):
    import httpx2

    from carbon.miner_mcp.standard_http import create_http_app
    from carbon.miner_mcp.standard_server import CAPABILITIES_URI

    service, calls = adapter(monkeypatch)
    app = create_http_app(service, verifier(keys))
    valid = token(keys)

    async def exercise():
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app)) as client,
        ):
            requests = (
                rpc(
                    "tools/call",
                    {
                        "name": PREFIX + "get_challenge_info",
                        "arguments": {"operation_id": OPERATION_ID},
                    },
                ),
                rpc("resources/read", {"uri": CAPABILITIES_URI}),
                rpc("prompts/get", {"name": "carbon_research_workflow_v1"}),
                rpc("tools/list"),
                rpc("tasks/get", {"taskId": "rtsk_" + "a" * 64}),
                rpc("tasks/cancel", {"taskId": "rtsk_" + "a" * 64}),
                rpc("skills/list"),
                rpc(
                    "skills/get", {"uri": "skill://carbon/carbon-research-v1/SKILL.md"}
                ),
                rpc(
                    "resources/read",
                    {"uri": "skill://carbon/carbon-research-v1/SKILL.md"},
                ),
            )
            for body in requests:
                for unauthorized in (
                    None,
                    token(keys, changes={"sub": "subject-bob"}),
                    token(keys, changes={"exp": 1}),
                ):
                    response = await client.post(
                        RESOURCE, headers=headers(unauthorized), json=body
                    )
                    assert response.status_code == 401, response.text
            assert calls == []
            session = await initialize(client, valid)
            base = headers(valid, session)
            for extra, status in (
                ({"host": "attacker.test"}, 421),
                ({"origin": "https://attacker.test"}, 403),
            ):
                response = await client.post(
                    RESOURCE, headers=base | extra, json=rpc("tools/list")
                )
                assert response.status_code == status, response.text
            response = await client.post(
                RESOURCE,
                headers=base | {"content-type": "application/json"},
                content=b" " * 65537,
            )
            assert response.status_code == 413, response.text
            response = await client.post(
                RESOURCE,
                headers=base,
                json=rpc(
                    "tools/call",
                    {
                        "name": PREFIX + "get_challenge_info",
                        "arguments": {
                            "operation_id": OPERATION_ID,
                            "principal": "bob",
                        },
                    },
                ),
            )
            assert response.status_code == 200
            assert response.json()["result"]["isError"] is True
            assert calls == []

    asyncio.run(exercise())


def test_http_sdk_interoperability_reconnect_and_cross_user_session(keys, monkeypatch):
    import httpx2
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client

    from carbon.miner_mcp.standard_http import create_http_app
    from carbon.miner_mcp.standard_server import CAPABILITIES_URI, GUIDANCE_URI

    service, calls = adapter(monkeypatch)
    app = create_http_app(service, verifier(keys))
    valid = token(keys)

    async def exercise():
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app),
                headers={"authorization": "Bearer " + valid},
            ) as http,
        ):
            async with Client(
                streamable_http_client(RESOURCE, http_client=http),
                read_timeout_seconds=15,
            ) as client:
                assert len((await client.list_tools()).tools) == 12
                capabilities = await client.read_resource(CAPABILITIES_URI)
                assert "carbon_jax_fno1d" in capabilities.contents[0].text
                assert (
                    "operation_id stable"
                    in (await client.read_resource(GUIDANCE_URI)).contents[0].text
                )
                assert (await client.get_prompt("carbon_research_workflow_v1")).messages
                first = await client.call_tool(
                    PREFIX + "get_challenge_info", {"operation_id": OPERATION_ID}
                )
                assert not first.is_error
                assert first.structured_content["official_eligible"] is False
            async with Client(
                streamable_http_client(RESOURCE, http_client=http),
                read_timeout_seconds=15,
            ) as client:
                second = await client.call_tool(
                    PREFIX + "get_challenge_info", {"operation_id": OPERATION_ID}
                )
                assert second.structured_content == first.structured_content
            session = await initialize(http, valid)
            denied = await http.post(
                RESOURCE,
                headers=headers(token(keys, changes={"sub": "subject-bob"}), session),
                json=rpc("tools/list"),
            )
            assert denied.status_code == 401
            assert len(calls) == 2
        # Sessions are not grants: an old process's transport ID is rejected by
        # a new app. The domain adapter and durable business identity are retained.
        restarted = create_http_app(service, verifier(keys))
        async with (
            restarted.router.lifespan_context(restarted),
            httpx2.AsyncClient(transport=httpx2.ASGITransport(app=restarted)) as http,
        ):
            stale = await http.post(
                RESOURCE, headers=headers(valid, session), json=rpc("tools/list")
            )
            assert stale.status_code == 404, stale.text
            await initialize(http, valid)

    asyncio.run(exercise())
