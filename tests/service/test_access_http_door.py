"""The remote MCP door, served behind Cloudflare Access from operator config.

`access_auth` was verified in isolation and nothing served it: no path built an
`AccessVerifier`, `create_http_app` refused one by type, and the SDK reads its
credential from `Authorization` while Access delivers the assertion in
`Cf-Access-Jwt-Assertion` - so even a wired verifier would never have been
handed a token. These tests drive the whole door over in-process ASGI.

Every value here is a fixture. The operator's real team host and AUD tag are
not in this public repository and must not be added to it. Assertions are
minted from a local test key; no listener starts and nothing reaches a network.

Refusals are paired with a specimen: the same assertion that is refused when it
arrives the wrong way is admitted when it arrives through the Access header, so
a refusal cannot pass merely because nothing could have been admitted.
"""

from __future__ import annotations

import asyncio
import json
import time

import pytest

from tests.service.test_standard_mcp_http import PREFIX, adapter, rpc

ISSUER = "https://carbon-fixture.cloudflareaccess.com"
AUD = "0" * 64
RESOURCE = "https://door.carbon.test/mcp"
CLIENT = "0123456789abcdef0123456789abcdef.access"
KID = "fixture-kid"


@pytest.fixture(scope="module")
def keypair():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return private, public.decode()


def config(**changes):
    document = {
        "schema": "carbon.mcp.access-door.v1",
        "issuer": ISSUER,
        "audience": AUD,
        "resource": RESOURCE,
        "principals": {CLIENT: "alice"},
    }
    document.update(changes)
    return document


def write(tmp_path, document):
    path = tmp_path / "access-door.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def fetcher(pem, calls=None):
    def fetch(url):
        if calls is not None:
            calls.append(url)
        return {"public_certs": [{"kid": KID, "cert": pem}]}

    return fetch


def assertion(private, **changes):
    import jwt

    claims = {
        "iss": ISSUER,
        # The observed shape: see test_access_verifier.mint.
        "aud": AUD,
        "exp": int(time.time()) + 300,
        "iat": int(time.time()),
        "sub": "",
        "common_name": CLIENT,
        "type": "app",
        "h_INTERNAL_DO_NOT_USE": "opaque",
    }
    claims.update(changes)
    return jwt.encode(claims, private, algorithm="RS256", headers={"kid": KID})


def door(tmp_path, monkeypatch, keypair, document=None):
    from carbon.miner_mcp.standard_http import create_access_http_app

    service, calls = adapter(monkeypatch)
    app = create_access_http_app(
        service, write(tmp_path, document or config()), fetch=fetcher(keypair[1])
    )
    return app, calls


BASE = {
    "accept": "application/json, text/event-stream",
    "mcp-protocol-version": "2025-11-25",
}

INITIALIZE = rpc(
    "initialize",
    {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "carbon-access-door-fixture", "version": "1"},
    },
)


def exchange(app, *requests):
    """Post each (headers, body) in one client; return the status codes."""
    import httpx2

    async def go():
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app)) as client,
        ):
            results = []
            for extra, body in requests:
                response = await client.post(RESOURCE, headers=BASE | extra, json=body)
                results.append(response.status_code)
            return results

    return asyncio.run(go())


# --- startup: operator configuration, and nothing else ---------------------


def test_no_configuration_file_stops_startup(tmp_path, monkeypatch, keypair):
    from carbon.miner_mcp.access_auth import AccessFailure
    from carbon.miner_mcp.standard_http import create_access_http_app

    service, _ = adapter(monkeypatch)
    with pytest.raises(AccessFailure, match="does not start without one"):
        create_access_http_app(
            service, tmp_path / "absent.json", fetch=fetcher(keypair[1])
        )


@pytest.mark.parametrize(
    "field", ("schema", "issuer", "audience", "resource", "principals")
)
def test_every_field_is_required_and_none_defaults(tmp_path, keypair, field):
    from carbon.miner_mcp.access_auth import AccessFailure, load_access_verifier

    document = config()
    del document[field]
    with pytest.raises(AccessFailure, match="missing: " + field):
        load_access_verifier(write(tmp_path, document), fetch=fetcher(keypair[1]))


def test_an_unrecognised_key_is_refused_not_ignored(tmp_path, keypair):
    from carbon.miner_mcp.access_auth import AccessFailure, load_access_verifier

    document = config(service_auth_401_redirect=True)
    with pytest.raises(AccessFailure, match="unrecognised"):
        load_access_verifier(write(tmp_path, document), fetch=fetcher(keypair[1]))


def test_an_empty_client_id_in_the_file_is_refused(tmp_path, keypair):
    from carbon.miner_mcp.access_auth import AccessFailure, load_access_verifier

    with pytest.raises(AccessFailure, match="non-empty Access identity"):
        load_access_verifier(
            write(tmp_path, config(principals={"": "alice"})),
            fetch=fetcher(keypair[1]),
        )


def test_there_is_no_default_fetch(tmp_path):
    from carbon.miner_mcp.access_auth import AccessFailure, load_access_verifier

    with pytest.raises(AccessFailure, match="no default"):
        load_access_verifier(write(tmp_path, config()), fetch=None)


def test_the_key_set_is_read_at_startup_from_the_configured_issuer(tmp_path, keypair):
    """A wrong team host stops startup rather than refusing the first miner."""
    from carbon.miner_mcp.access_auth import AccessFailure, load_access_verifier

    calls = []
    load_access_verifier(write(tmp_path, config()), fetch=fetcher(keypair[1], calls))
    assert calls == [ISSUER + "/cdn-cgi/access/certs"]

    with pytest.raises(AccessFailure, match="no public_certs"):
        load_access_verifier(
            write(tmp_path, config()), fetch=lambda url: {"public_cert": {}}
        )


def test_a_mapping_naming_another_principal_is_refused_at_startup(
    tmp_path, monkeypatch, keypair
):
    """One server, one campaign owner. The adapter here is alice's."""
    from carbon.miner_mcp.standard_http import create_access_http_app

    service, _ = adapter(monkeypatch)
    for principals in (
        {CLIENT: "bob"},
        {CLIENT: "alice", "fedcba9876543210fedcba9876543210.access": "bob"},
    ):
        with pytest.raises(ValueError, match="identity"):
            create_access_http_app(
                service,
                write(tmp_path, config(principals=principals)),
                fetch=fetcher(keypair[1]),
            )


def test_an_unknown_verifier_type_is_still_refused(monkeypatch):
    from carbon.miner_mcp.standard_http import create_http_app

    service, _ = adapter(monkeypatch)
    with pytest.raises(ValueError, match="identity"):
        create_http_app(service, object())


# --- requests: only the assertion Access minted counts ---------------------


def test_the_access_header_admits_a_mapped_service_token(
    tmp_path, monkeypatch, keypair
):
    """The specimen every refusal below is measured against."""
    app, _ = door(tmp_path, monkeypatch, keypair)
    good = assertion(keypair[0])
    assert exchange(app, ({"cf-access-jwt-assertion": good}, INITIALIZE)) == [200]


def test_the_assertion_is_refused_everywhere_but_its_own_header(
    tmp_path, monkeypatch, keypair
):
    """The same valid assertion, delivered every other way.

    As a client bearer token it is discarded rather than forwarded: behind
    Access, the only credential that counts is the one Access put there. The
    browser cookie is never read. Two assertion headers count as none.
    """
    app, calls = door(tmp_path, monkeypatch, keypair)
    good = assertion(keypair[0])
    statuses = exchange(
        app,
        ({}, INITIALIZE),
        ({"authorization": "Bearer " + good}, INITIALIZE),
        ({"cookie": "CF_Authorization=" + good}, INITIALIZE),
        ({"cf-access-jwt-assertion": ""}, INITIALIZE),
        ({"cf-access-jwt-assertion": good}, INITIALIZE),
    )
    assert statuses == [401, 401, 401, 401, 200]
    assert calls == []


def test_a_client_bearer_does_not_displace_the_access_assertion(
    tmp_path, monkeypatch, keypair
):
    """Discarded in both directions: a bad bearer cannot spoil a good assertion,
    and a good bearer cannot rescue a bad one."""
    app, _ = door(tmp_path, monkeypatch, keypair)
    good = assertion(keypair[0])
    bad = assertion(keypair[0], common_name="fedcba9876543210fedcba9876543210.access")
    statuses = exchange(
        app,
        ({"cf-access-jwt-assertion": good, "authorization": "Bearer junk"}, INITIALIZE),
        (
            {"cf-access-jwt-assertion": bad, "authorization": "Bearer " + good},
            INITIALIZE,
        ),
    )
    assert statuses == [200, 401]


@pytest.mark.parametrize(
    "changes",
    (
        {"common_name": "fedcba9876543210fedcba9876543210.access"},
        {"aud": "1" * 64},
        {"iss": "https://someone-else.cloudflareaccess.com"},
        {"exp": 1},
    ),
)
def test_an_assertion_access_would_not_have_minted_for_this_door_is_refused(
    tmp_path, monkeypatch, keypair, changes
):
    app, calls = door(tmp_path, monkeypatch, keypair)
    statuses = exchange(
        app,
        ({"cf-access-jwt-assertion": assertion(keypair[0], **changes)}, INITIALIZE),
        ({"cf-access-jwt-assertion": assertion(keypair[0])}, INITIALIZE),
    )
    assert statuses == [401, 200]
    assert calls == []


def test_an_authenticated_caller_reaches_the_research_tools(
    tmp_path, monkeypatch, keypair
):
    """End to end: initialize, then a tool call reaches the research adapter."""
    import httpx2

    app, calls = door(tmp_path, monkeypatch, keypair)
    good = {"cf-access-jwt-assertion": assertion(keypair[0])}

    async def go():
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app)) as client,
        ):
            response = await client.post(RESOURCE, headers=BASE | good, json=INITIALIZE)
            assert response.status_code == 200, response.text
            session = {"mcp-session-id": response.headers["mcp-session-id"]}
            response = await client.post(
                RESOURCE,
                headers=BASE | good | session,
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            )
            assert response.status_code == 202, response.text
            response = await client.post(
                RESOURCE,
                headers=BASE | good | session,
                json=rpc(
                    "tools/call",
                    {
                        "name": PREFIX + "get_challenge_info",
                        "arguments": {"operation_id": "access-door-fixture-0001"},
                    },
                ),
            )
            assert response.status_code == 200, response.text
            assert response.json()["result"].get("isError") is not True, response.text

    asyncio.run(go())
    # The adapter is alice's by construction and startup refused any mapping
    # naming someone else, so reaching it is reaching alice's campaign.
    assert [(name, operation) for name, _arguments, operation in calls] == [
        (PREFIX + "get_challenge_info", "access-door-fixture-0001")
    ]


def test_the_per_access_guard_refuses_what_this_door_could_not_have_admitted(
    tmp_path, keypair
):
    """The guard every data access runs, driven directly.

    The specimen is the context `verify_token` actually produces; each variant
    changes one thing about it that this door would never have issued.
    """
    from mcp.server.auth.middleware.auth_context import auth_context_var
    from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser

    from carbon.miner_mcp.access_auth import load_access_verifier

    verifier = load_access_verifier(
        write(tmp_path, config()), fetch=fetcher(keypair[1])
    )
    issued = asyncio.run(verifier.verify_token(assertion(keypair[0])))
    assert issued is not None

    def guard(token):
        handle = auth_context_var.set(
            AuthenticatedUser(token) if token is not None else None
        )
        try:
            verifier.check_context()
            return "admitted"
        except PermissionError:
            return "refused"
        finally:
            auth_context_var.reset(handle)

    assert guard(issued) == "admitted"
    for variant in (
        None,
        issued.model_copy(update={"subject": "bob"}),
        issued.model_copy(update={"resource": "https://elsewhere.test/mcp"}),
        issued.model_copy(update={"expires_at": int(time.time()) - 1}),
        issued.model_copy(update={"scopes": []}),
        issued.model_copy(update={"claims": {"iss": "https://other.test"}}),
    ):
        assert guard(variant) == "refused", variant
