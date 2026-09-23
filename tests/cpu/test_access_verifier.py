"""Cloudflare Access authenticates; Carbon authorizes.

Assertions are minted locally from a test key, so every path here runs without
an account, a tunnel or a deployment.

The test that matters most is not that a good token passes. It is that removing
the scope check did not remove the authorization decision. `verify_token` used
to assert RESEARCH_SCOPE was in the token's own claims, and an Access assertion
carries no scope - so the obvious repair, deleting the requirement, would have
made Access pass by deleting the only thing asserting this caller was entitled
to the research surface. The principal mapping replaces it, and
`test_a_valid_assertion_for_an_unmapped_identity_is_refused` is what stops that
replacement being quietly dropped later.
"""

import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from carbon.miner_mcp.access_auth import (
    AccessBinding,
    AccessFailure,
    AccessIdentity,
    AccessKeys,
    AccessVerifier,
    assertion_from,
)

ISSUER = "https://carbon-team.cloudflareaccess.com"
AUD = "32eafc7626e974616deaf0dc3ce63d7bcbed58a2731e84d06bc3cdf1b53c4228"
RESOURCE = "https://carbon.example/mcp"
CLIENT = "e367826f93b8d71185e03fe518aff3b4.access"


def keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return key, pem.decode()


def binding(principals=None):
    return AccessBinding(
        issuer=ISSUER,
        audience=AUD,
        resource=RESOURCE,
        principals=principals or {AccessIdentity(CLIENT): "alice"},
    )


def mint(key, kid="k1", **overrides):
    import jwt

    claims = {
        "iss": ISSUER,
        # The shape observed in a real Cloudflare-minted service-token
        # assertion captured on 23 September 2026: `aud` a plain string (the
        # AUD tag, not a list and not a URL), `sub` present and empty,
        # `common_name` the full Client ID including `.access`, no `client_id`
        # or `scope`, and two claims Cloudflare does not document.
        "aud": AUD,
        "exp": int(time.time()) + 300,
        "iat": int(time.time()),
        "sub": "",
        "common_name": CLIENT,
        "type": "app",
        "h_INTERNAL_DO_NOT_USE": "opaque",
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})


def verifier(principals=None, *, kid="k1", clock=None):
    key, pem = keypair()
    bound = binding(principals)
    calls = []

    def fetch(url):
        calls.append(url)
        return {"public_certs": [{"kid": kid, "cert": pem}]}

    keys = AccessKeys(bound, fetch=fetch, clock=clock or time.monotonic)
    return key, AccessVerifier(bound, keys), keys, calls


def run(coro):
    import asyncio

    return asyncio.run(coro)


# --- authorization is Carbon's, not the token's ------------------------------


def test_a_mapped_identity_is_authenticated_and_authorized():
    key, verify, _keys, _calls = verifier()
    token = run(verify.verify_token(mint(key)))
    assert token is not None
    assert token.subject == "alice", "the Carbon principal, not the Access subject"
    assert token.client_id == CLIENT


def test_a_valid_assertion_for_an_unmapped_identity_is_refused():
    """What replaced the scope check.

    The assertion is perfectly valid - correct issuer, audience, signature and
    expiry. It is refused because Carbon has no principal for that credential,
    which is the authorization decision the deleted scope check was carrying.
    """
    key, verify, _keys, _calls = verifier(
        principals={AccessIdentity("somebody-else.access"): "bob"}
    )
    assert run(verify.verify_token(mint(key))) is None


def test_the_token_cannot_enlarge_its_own_rights():
    """A claim asserting privileges is ignored, not honoured.

    Access says which credential arrived and nothing more. Scopes come from
    Carbon's side, so a token claiming extra scope gains nothing by claiming it.
    """
    key, verify, _keys, _calls = verifier()
    token = run(verify.verify_token(mint(key, scope="carbon:admin carbon:everything")))
    assert token.scopes == ["carbon:research"]
    assert "carbon:admin" not in token.scopes


@pytest.mark.parametrize("aud", (AUD, [AUD]), ids=("observed-string", "list"))
def test_the_audience_matches_as_a_string_or_a_list(aud):
    """A plain string is what Access actually sent; a list is what the JWT
    specification also permits, so a change of shape is not an outage."""
    key, verify, _keys, _calls = verifier()
    assert run(verify.verify_token(mint(key, aud=aud))) is not None
    assert run(verify.verify_token(mint(key, aud="1" * 64))) is None


def test_undocumented_claims_neither_break_verification_nor_pass_through():
    """Cloudflare ships internal claims without notice.

    `h_INTERNAL_DO_NOT_USE` and `type` were present in the real assertion and
    appear in no documentation. They must not fail verification, and nothing
    from them may reach the token Carbon builds: its claims are Carbon's.
    """
    import jwt

    key, verify, _keys, _calls = verifier()
    raw = mint(key, h_INTERNAL_DO_NOT_USE="opaque", type="app", unheard_of={"x": 1})
    # Specimen: the claims really are in what was verified.
    presented = jwt.decode(raw, options={"verify_signature": False})
    assert {"h_INTERNAL_DO_NOT_USE", "type", "unheard_of"} <= set(presented)

    token = run(verify.verify_token(raw))
    assert token is not None
    assert set(token.claims) == {"iss", "carbon_principal"}


# --- an absent or empty claim cannot be a match ------------------------------


def test_an_empty_identity_cannot_be_constructed():
    """`"" == ""` would otherwise authenticate a caller that presented nothing."""
    for value in ("", "   ", None, 0, b"x"):
        with pytest.raises(AccessFailure):
            AccessIdentity(value)


def test_a_binding_cannot_be_keyed_by_an_unvalidated_identity():
    with pytest.raises(AccessFailure):
        AccessBinding(
            issuer=ISSUER, audience=AUD, resource=RESOURCE, principals={CLIENT: "alice"}
        )


def test_sub_is_never_accepted_as_an_identity():
    """A service token's sub is documented as empty, and is refused outright.

    Refused rather than used as a fallback, because a fallback is exactly how an
    empty value becomes an authenticated caller.
    """
    key, verify, _keys, _calls = verifier()
    without_common_name = mint(key)
    import jwt

    claims = jwt.decode(without_common_name, options={"verify_signature": False})
    del claims["common_name"]
    claims["sub"] = ""
    forged = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "k1"})
    assert run(verify.verify_token(forged)) is None


# --- keys rotate -------------------------------------------------------------


def test_a_key_outside_the_current_set_is_refused():
    _key, verify, _keys, _calls = verifier()
    other, _pem = keypair()
    assert run(verify.verify_token(mint(other))) is None


def test_an_unknown_kid_refetches_exactly_once():
    """A rotation is an unknown kid; so is a forgery.

    One refetch resolves the first and caps the second, so a forged key id costs
    one fetch rather than letting a caller set the fetch rate.
    """
    key, verify, keys, calls = verifier()
    assert run(verify.verify_token(mint(key, kid="rotated-away"))) is None
    assert keys.fetches == 2, "one initial load plus exactly one refetch"
    assert len(calls) == 2


def test_a_stale_cache_refreshes_rather_than_refusing():
    """Six weeks later the key has rotated and the cache must not be the reason."""
    now = [1000.0]
    key, verify, keys, _calls = verifier(clock=lambda: now[0])
    assert run(verify.verify_token(mint(key))) is not None
    assert keys.fetches == 1
    now[0] += 7200  # past the TTL, far inside Cloudflare's seven-day overlap
    assert run(verify.verify_token(mint(key))) is not None
    assert keys.fetches == 2, "refreshed on staleness, not refused"


def test_the_singular_public_cert_is_never_read():
    """Cloudflare warns the origin may read an expired value from that field."""
    bound = binding()
    keys = AccessKeys(bound, fetch=lambda url: {"public_cert": {"kid": "k1"}})
    with pytest.raises(AccessFailure):
        keys.key_for("k1")


def test_the_certs_url_is_the_documented_endpoint():
    assert binding().certs_url == ISSUER + "/cdn-cgi/access/certs"


# --- transport ---------------------------------------------------------------


def test_the_assertion_is_read_from_the_header():
    assert assertion_from({"Cf-Access-Jwt-Assertion": "  abc  "}) == "abc"
    assert assertion_from({"cf-access-jwt-assertion": "abc"}) == "abc"


def test_a_cookie_only_request_is_refused():
    """An MCP client is not a browser, and the cookie is not guaranteed."""
    with pytest.raises(AccessFailure):
        assertion_from({"Cookie": "CF_Authorization=abc"})


# --- stdio is not on this path -----------------------------------------------


def test_stdio_needs_no_carbon_issued_credential():
    """The guarantee, asserted rather than left as prose.

    If the stdio path ever acquires a credential requirement this fails, which
    is the point: BYO over stdio must never need something Carbon hands out.
    """
    import inspect

    from carbon.miner_mcp import open_tier

    server = open_tier.create_open_tier_server()
    assert server is not None

    source = inspect.getsource(open_tier)
    for token in ("AccessBinding", "AccessVerifier", "access_auth", "cloudflare"):
        assert token not in source, token

    signature = inspect.signature(open_tier.create_open_tier_server)
    assert all(
        parameter.default is not inspect.Parameter.empty
        for parameter in signature.parameters.values()
        if parameter.kind is not parameter.VAR_KEYWORD
    ), "every parameter optional: no credential is required to start"
