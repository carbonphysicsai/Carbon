"""Cloudflare Access fronts the remote MCP door; Carbon decides what it grants.

Decision CARBON-D-MCP-REMOTE-AUTH. Carbon runs no authorization server, issues
no OAuth signing keys and holds none. Access is the issuer; this module verifies
its assertion and maps a verified credential onto an existing Carbon principal.

**The split this module exists to keep.** Access *authenticates*: it establishes
which credential presented itself. Carbon *authorizes*: a verified identity is
looked up in a mapping the operator supplies, and the rights that follow come
from Carbon's own model. Nothing a caller's token says about its own privileges
is read. `verify_token` previously asserted `RESEARCH_SCOPE in claims["scope"]`,
and an Access assertion carries no scope at all - so deleting that check would
have made Access pass by removing the only thing asserting the caller was
entitled to the research surface. The mapping replaces it: an assertion for an
identity with no Carbon principal is refused, and a mapped one gets exactly the
scopes Carbon assigns rather than any the token claims.

**An absent claim cannot be a match.** A service token's `sub` is documented as
an empty string rather than missing, and an empty binding compared against an
empty claim is equal - a live hole rather than a style point. So the identity is
an `AccessIdentity`, which cannot be constructed from an empty or non-string
value, and the principal mapping is keyed by that type. An absent or empty claim
fails to become a key at all, before any comparison happens. That holds whether
Cloudflare emits `sub` as empty or omits it. Cloudflare's service-token page
documents creation and headers but not the claim shape; a real service-token
assertion captured on 23 September 2026 carried `sub` present and empty,
`common_name` holding the full Client ID including `.access`, `aud` as a plain
string, no `client_id` and no `scope`.

**Claims nobody documented are ignored, never read.** The same assertion
carried `type` and `h_INTERNAL_DO_NOT_USE`, neither of them documented.
Cloudflare evidently adds claims without notice, so verification must neither
fail on an unknown claim nor let one through: the token Carbon builds carries
only the issuer and the Carbon principal.

**Keys rotate.** Access rotates its signing key roughly every six weeks and
keeps the previous one valid for seven days. A key set frozen at construction
therefore works for six weeks and then fails in production with nothing in the
diff to blame. `AccessKeys` fetches the JWKS, reads `public_certs` rather than
the singular `public_cert` (which Cloudflare warns may be served stale), caches
under a TTL far below the seven-day overlap, and on an unknown `kid` refetches
exactly once before refusing - so a forged key id costs one fetch, not one per
request.

**Transport.** The assertion arrives in `Cf-Access-Jwt-Assertion` on every
request. The `CF_Authorization` cookie is browser-only and explicitly not
guaranteed; an MCP client is not a browser, so the cookie is never read.

**Two credential procedures that look alike and are not.** Binding on
`common_name` means the mapping keys on the service token's Client ID, and
Cloudflare documents that rotating a token's *secret* leaves the Client ID
unchanged - so routine rotation needs nothing from Carbon and the mapping keeps
working, with both secrets valid during the grace period. *Revoking and
re-issuing* a token produces a new Client ID, so the mapping must be updated or
the miner is locked out with a perfectly valid credential. Rotate and re-issue
are therefore different operations with different Carbon-side consequences, and
conflating them looks like an outage.

**What each door costs.** stdio is open and ungated: it takes no binding, no
keys and nothing issued by Carbon, and none of this module is on that path, so
it scales to any number of miners without Carbon doing anything. This remote
door is a Carbon-hosted convenience with a Carbon-issued credential, which means
an issuance step per miner who wants it. That is workable for a bounded set and
does not scale to open participation, and it should be said wherever the two are
offered so nobody plans around remote MCP as the general path.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass

#: Where Access publishes its rotating signing keys, relative to the team host.
CERTS_PATH = "/cdn-cgi/access/certs"

#: Cached well inside the seven-day window in which a rotated-out key stays
#: valid, so a rotation is picked up long before the old key expires.
KEY_CACHE_SECONDS = 3600

#: The header Access sets on every request, browser or not.
ASSERTION_HEADER = "Cf-Access-Jwt-Assertion"

#: Read for exactly one reason: to refuse a request that presents only it.
BROWSER_COOKIE = "CF_Authorization"


def _https_host(value: object, *, allow_path: bool = False) -> bool:
    """An https URL with a host, and no path unless one is expected.

    Deliberately small: these are operator-supplied identifiers compared for
    equality against a token's issuer, never fetched or dialled by this module.
    """
    prefix = "https://"
    if type(value) is not str or not value.startswith(prefix) or len(value) > 2048:
        return False
    remainder = value[len(prefix) :]
    host, separator, path = remainder.partition("/")
    if not host or any(character.isspace() for character in value):
        return False
    return not (separator and not allow_path and path)


class AccessFailure(Exception):
    """Closed refusal; nothing from the token or the issuer crosses the wire."""


class AccessIdentity(str):
    """A non-empty Access credential identity. Construction is validation.

    There is no path from an absent or empty claim to a value of this type, so
    an identity that was never presented cannot compare equal to a binding that
    was never configured. That is the whole point: string equality would make
    `"" == ""` an authenticated caller.
    """

    __slots__ = ()

    def __new__(cls, value):
        if type(value) is not str or not value.strip() or len(value) > 256:
            raise AccessFailure("a non-empty Access identity is required")
        return super().__new__(cls, value)


@dataclass(frozen=True)
class AccessBinding:
    """What Carbon will accept, and who it maps to.

    `audience` is the application's AUD tag - a hex identifier, not a URL. The
    resource URL the MCP server advertises is a separate value and the two were
    conflated in the previous binding.

    `principals` is Carbon's authorization decision, and the only one. An
    identity absent from it is refused however valid its assertion.
    """

    issuer: str
    audience: str
    resource: str
    principals: Mapping[AccessIdentity, str]

    def __post_init__(self):
        # Checked with plain string work rather than `urllib.parse`. The C-08
        # boundary admits exactly one `urlsplit` import, in the reviewed HTTP
        # factory, and widening that allowance so this module could pass would
        # be loosening a security invariant to fit new code - which is the
        # failure shape this door exists to avoid, not an exception to it.
        if not _https_host(self.issuer):
            raise AccessFailure("an https Access team issuer is required")
        if not (isinstance(self.audience, str) and 1 <= len(self.audience) <= 256):
            raise AccessFailure("the application AUD tag is required")
        if not _https_host(self.resource, allow_path=True):
            raise AccessFailure("an https resource URL is required")
        if not self.principals:
            raise AccessFailure("at least one identity-to-principal mapping required")
        for identity, principal in self.principals.items():
            # Keyed by the validated type rather than by str, so a mapping can
            # never be built around an empty identity in the first place.
            if type(identity) is not AccessIdentity:
                raise AccessFailure("principal mapping must be keyed by AccessIdentity")
            if type(principal) is not str or not principal.strip():
                raise AccessFailure("each identity must map to a Carbon principal")

    @property
    def certs_url(self) -> str:
        return self.issuer.rstrip("/") + CERTS_PATH

    def principal_for(self, identity: AccessIdentity) -> str:
        """Carbon's authorization decision. Refuses an unmapped identity."""
        if type(identity) is not AccessIdentity:
            raise AccessFailure("a validated Access identity is required")
        principal = self.principals.get(identity)
        if principal is None:
            raise AccessFailure("this credential maps to no Carbon principal")
        return principal


class AccessKeys:
    """The rotating JWKS, fetched rather than frozen.

    `fetch` is injected so this is testable without a network and so the
    operator chooses the client. It receives the certs URL and returns the
    decoded JSON body.
    """

    def __init__(self, binding: AccessBinding, *, fetch, clock=time.monotonic):
        self._binding, self._fetch, self._clock = binding, fetch, clock
        self._keys: dict[str, object] = {}
        self._loaded_at = None
        self.fetches = 0

    def _load(self):
        document = self._fetch(self._binding.certs_url)
        if isinstance(document, (bytes, str)):
            document = json.loads(document)
        # `public_certs`, never the singular `public_cert`: Cloudflare warns the
        # origin may read an expired value from an outdated cache there.
        entries = document.get("public_certs") if isinstance(document, dict) else None
        if not isinstance(entries, list) or not entries:
            raise AccessFailure("the Access certs document carried no public_certs")
        keys = {}
        for entry in entries:
            kid, cert = entry.get("kid"), entry.get("cert")
            if type(kid) is not str or type(cert) is not str:
                raise AccessFailure("malformed public_certs entry")
            keys[kid] = _public_key(cert)
        self._keys, self._loaded_at = keys, self._clock()
        self.fetches += 1

    def prime(self):
        """Load the key set now, so a wrong issuer fails at startup.

        Without this the first sign of a misconfigured team host is the first
        miner's request being refused, which reads as their credential being
        wrong. Called once when the door is built.
        """
        self._load()

    def _stale(self) -> bool:
        return (
            self._loaded_at is None
            or self._clock() - self._loaded_at >= KEY_CACHE_SECONDS
        )

    def key_for(self, kid: str):
        """The signing key for this kid, refetching at most once on a miss.

        A rotation shows up as an unknown kid, so one refetch resolves it. A
        forged kid also shows up as an unknown kid, so the refetch is capped at
        one per request rather than one per attempt - otherwise an attacker sets
        the fetch rate.
        """
        if type(kid) is not str or not kid:
            raise AccessFailure("the assertion carried no key id")
        if self._stale():
            self._load()
        if kid in self._keys:
            return self._keys[kid]
        self._load()
        if kid not in self._keys:
            raise AccessFailure("the assertion was signed by an unknown key")
        return self._keys[kid]


def _public_key(cert: str):
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from cryptography.x509 import load_pem_x509_certificate

    data = cert.encode()
    if b"CERTIFICATE" in data:
        return load_pem_x509_certificate(data).public_key()
    return load_pem_public_key(data)


class AccessVerifier:
    """Verify an Access assertion, then ask Carbon who that is.

    Returns an SDK `AccessToken` whose scopes are **Carbon's**, derived from the
    principal mapping. The assertion's own claims never contribute a privilege:
    Access says which credential arrived, and that is all it is trusted for.
    """

    def __init__(self, binding: AccessBinding, keys: AccessKeys, *, scopes=()):
        from carbon.miner_mcp.standard_http import RESEARCH_SCOPE

        self.binding = binding
        self._keys = keys
        self._scopes = tuple(scopes) or (RESEARCH_SCOPE,)

    def identity(self, claims: dict) -> AccessIdentity:
        """The service token's common_name, and never `sub`.

        MCP clients are programmatic, so a service token is the expected path
        and `common_name` carries its identity. `sub` is refused as an identity
        outright rather than used as a fallback: for a service token it is
        documented as an empty string, and a fallback is how an empty value
        becomes an authenticated caller.
        """
        if "common_name" not in claims:
            raise AccessFailure(
                "this door accepts Access service tokens; the assertion carried "
                "no common_name"
            )
        return AccessIdentity(claims["common_name"])

    def check_context(self):
        """The per-access guard: re-read what `verify_token` established.

        The SDK's middleware has already admitted the request, so this is not
        the first check - it is the one every data access runs, and it refuses
        a context this verifier could not have produced: another issuer,
        another resource, an expired token, or a principal outside this door's
        mapping.
        """
        from mcp.server.auth.middleware.auth_context import get_access_token

        from carbon.miner_mcp.standard_http import RESEARCH_SCOPE

        token = get_access_token()
        binding = self.binding
        if (
            token is None
            or (token.claims or {}).get("iss") != binding.issuer
            or token.resource != binding.resource
            or type(token.expires_at) is not int
            or token.expires_at <= time.time()
            or RESEARCH_SCOPE not in token.scopes
            or token.subject not in set(binding.principals.values())
        ):
            raise PermissionError("Carbon research authorization required")

    async def verify_token(self, token: str):
        """Authenticate the assertion. Authorization is the mapping, below."""
        import jwt
        from mcp.server.auth.provider import AccessToken

        if type(token) is not str or not 1 <= len(token) <= 16384:
            return None
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256":
                return None
            key = self._keys.key_for(header.get("kid"))
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.binding.issuer,
                audience=self.binding.audience,
                options={"require": ["iss", "aud", "exp", "iat"], "strict_aud": False},
            )
            # Access authenticated a credential. Carbon decides what it may do,
            # from its own mapping - not from anything the token asserts about
            # its own privileges, of which it asserts none.
            identity = self.identity(claims)
            principal = self.binding.principal_for(identity)
            return AccessToken(
                token=token,
                client_id=str(identity),
                subject=principal,
                resource=self.binding.resource,
                scopes=list(self._scopes),
                expires_at=int(claims["exp"]),
                claims={"iss": self.binding.issuer, "carbon_principal": principal},
            )
        except (AccessFailure, jwt.PyJWTError, ValueError, TypeError, KeyError):
            return None


def assertion_from(headers) -> str:
    """The token from the header Access always sets.

    The `CF_Authorization` cookie is browser-only and Cloudflare states it is
    not guaranteed, so a request carrying only the cookie is refused rather than
    accepted on a weaker signal.
    """
    value = None
    for name, raw in dict(headers).items():
        if name.lower() == ASSERTION_HEADER.lower():
            value = raw
            break
    if type(value) is not str or not value.strip():
        raise AccessFailure(
            "no Cf-Access-Jwt-Assertion header; the browser cookie is not accepted"
        )
    return value.strip()


# --- operator configuration --------------------------------------------------

#: The operator's description of the remote door. Closed: an unrecognised key
#: is refused rather than ignored, because an ignored key is a setting the
#: operator believes is in force and is not.
CONFIG_SCHEMA = "carbon.mcp.access-door.v1"
CONFIG_KEYS = frozenset({"schema", "issuer", "audience", "resource", "principals"})


def access_binding_from_config(document: object) -> AccessBinding:
    """Build the binding from the operator's configuration, or refuse.

    There is no default for any field. The team issuer and the application AUD
    tag belong to the operator's Cloudflare account and are not in this public
    repository, so a missing value has nothing correct to fall back to - and a
    door that starts with a guessed binding is a door whose authentication
    nobody decided.
    """
    if not isinstance(document, dict):
        raise AccessFailure("the Access door configuration must be a JSON object")
    unknown = set(document) - CONFIG_KEYS
    if unknown:
        raise AccessFailure(
            "unrecognised Access door configuration keys: " + ", ".join(sorted(unknown))
        )
    missing = CONFIG_KEYS - set(document)
    if missing:
        raise AccessFailure(
            "the Access door configuration is missing: " + ", ".join(sorted(missing))
        )
    if document["schema"] != CONFIG_SCHEMA:
        raise AccessFailure(
            f"the Access door configuration schema must be {CONFIG_SCHEMA}"
        )
    principals = document["principals"]
    if not isinstance(principals, dict):
        raise AccessFailure(
            "principals must map each service token Client ID to a Carbon principal"
        )
    return AccessBinding(
        issuer=document["issuer"],
        audience=document["audience"],
        resource=document["resource"],
        # Through the validated type, so an empty Client ID in the operator's
        # file is refused here rather than becoming a key that matches nothing
        # - or, worse, matches an empty claim.
        principals={AccessIdentity(key): value for key, value in principals.items()},
    )


def load_access_verifier(path, *, fetch) -> AccessVerifier:
    """The verifier for the remote door, from the operator's file, keys loaded.

    `fetch` is required and has no default. This package opens no network
    connection (the C-08 boundary), so the operator's startup code supplies the
    client that reads the JWKS. The key set is loaded here, once, so a wrong
    issuer or an unreachable team host stops startup instead of refusing the
    first miner who connects.
    """
    from pathlib import Path

    if not callable(fetch):
        raise AccessFailure("a JWKS fetch function is required; there is no default")
    source = Path(path)
    if not source.is_file():
        raise AccessFailure(
            f"no Access door configuration at {source}; the remote door does "
            "not start without one, and stdio needs none"
        )
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise AccessFailure(
            f"the Access door configuration at {source} is not valid JSON"
        ) from None
    binding = access_binding_from_config(document)
    keys = AccessKeys(binding, fetch=fetch)
    keys.prime()
    return AccessVerifier(binding, keys)


# --- transport ---------------------------------------------------------------


class AccessAssertionHeader:
    """Present the Access assertion to the SDK's bearer check, and only it.

    The SDK authenticates from `Authorization: Bearer`. Access delivers its
    assertion in `Cf-Access-Jwt-Assertion`. Without this adapter the verifier
    is never handed a token at all, and every request is refused - correctly,
    but for a reason nobody would guess.

    Any `Authorization` header the client sent is discarded, never forwarded.
    Behind Access the only credential that counts is the one Access minted; a
    client-supplied bearer value is not a second route in, even one that would
    go on to fail verification. More than one assertion header is treated as
    none. The browser cookie is never read.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            name = ASSERTION_HEADER.lower().encode()
            assertions = [
                value for key, value in scope["headers"] if key.lower() == name
            ]
            headers = [
                (key, value)
                for key, value in scope["headers"]
                if key.lower() not in (b"authorization", name)
            ]
            if len(assertions) == 1 and assertions[0].strip():
                headers.append((b"authorization", b"Bearer " + assertions[0].strip()))
            scope = {**scope, "headers": headers}
        await self.app(scope, receive, send)
