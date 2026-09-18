"""Authenticated MCP resource server for one existing Carbon principal/grant.

Operators supply the authorization server's reviewed public keys and explicit
issuer/client/subject-to-Carbon binding. No token issuer, dynamic key URL, cloud
listener or new grant is created here. Mount the returned ASGI app only in an
authorized private service. Existing services still check task/artifact ownership.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from types import MappingProxyType
from urllib.parse import urlsplit

from carbon.miner_mcp.standard import ResearchToolAdapter
from carbon.miner_mcp.standard_server import _create_server

RESEARCH_SCOPE = "carbon:research"


@dataclass(frozen=True)
class HttpPrincipalBinding:
    issuer: str
    resource: str
    client_id: str
    subject: str
    principal: str

    def __post_init__(self):
        for value in (self.issuer, self.resource):
            if type(value) is not str or len(value) > 2048:
                raise ValueError("invalid OAuth endpoint")
            parsed = urlsplit(value)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("exact HTTPS issuer/resource required")
        for value in (self.client_id, self.subject, self.principal):
            if (
                type(value) is not str
                or not 1 <= len(value) <= 256
                or any(ord(c) < 32 for c in value)
            ):
                raise ValueError("invalid principal binding")


class BoundTokenVerifier:
    """Fixed RS256 verifier; key rotation is an explicit operator config change."""

    def __init__(self, binding: HttpPrincipalBinding, *, public_keys: dict[str, bytes]):
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        if type(binding) is not HttpPrincipalBinding:
            raise TypeError("exact principal binding required")
        if type(public_keys) is not dict or not 1 <= len(public_keys) <= 8:
            raise ValueError("bounded pinned public key set required")
        keys = {}
        for kid, pem in public_keys.items():
            if (
                type(kid) is not str
                or not 1 <= len(kid) <= 128
                or type(pem) is not bytes
                or not 1 <= len(pem) <= 16384
            ):
                raise ValueError("invalid public key")
            key = load_pem_public_key(pem)
            if not isinstance(key, RSAPublicKey) or key.key_size < 2048:
                raise ValueError("RS256 key of at least 2048 bits required")
            keys[kid] = key
        self.binding = binding
        self._keys = MappingProxyType(keys)

    async def verify_token(self, token: str):
        import jwt
        from mcp.server.auth.provider import AccessToken

        if type(token) is not str or not 1 <= len(token) <= 16384:
            return None
        try:
            header = jwt.get_unverified_header(token)
            if (
                header.get("alg") != "RS256"
                or header.get("typ") not in ("JWT", "at+jwt")
                or set(header) - {"alg", "typ", "kid"}
                or type(header.get("kid")) is not str
                or header["kid"] not in self._keys
            ):
                return None
            binding = self.binding
            claims = jwt.decode(
                token,
                self._keys[header["kid"]],
                algorithms=["RS256"],
                issuer=binding.issuer,
                audience=binding.resource,
                options={
                    "require": [
                        "iss",
                        "aud",
                        "sub",
                        "client_id",
                        "exp",
                        "iat",
                        "scope",
                    ],
                    "strict_aud": True,
                },
            )
            if (
                claims["sub"] != binding.subject
                or claims["client_id"] != binding.client_id
                or type(claims["exp"]) is not int
                or type(claims["iat"]) is not int
                or claims["exp"] <= claims["iat"]
                or type(claims["scope"]) is not str
                or RESEARCH_SCOPE not in claims["scope"].split()
            ):
                return None
            return AccessToken(
                token=token,
                client_id=binding.client_id,
                subject=binding.subject,
                resource=binding.resource,
                scopes=claims["scope"].split(),
                expires_at=claims["exp"],
                claims={"iss": binding.issuer},
            )
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            return None

    def check_context(self):
        from mcp.server.auth.middleware.auth_context import get_access_token

        token = get_access_token()
        binding = self.binding
        if (
            token is None
            or token.client_id != binding.client_id
            or token.subject != binding.subject
            or (token.claims or {}).get("iss") != binding.issuer
            or token.resource != binding.resource
            or type(token.expires_at) is not int
            or token.expires_at <= time.time()
            or RESEARCH_SCOPE not in token.scopes
        ):
            raise PermissionError("Carbon research authorization required")


def create_http_app(adapter: ResearchToolAdapter, verifier: BoundTokenVerifier):
    """Return a bounded stateful Streamable HTTP app; do not start a listener."""
    from mcp.server.auth.settings import AuthSettings
    from mcp.server.transport_security import TransportSecuritySettings

    if (
        type(adapter) is not ResearchToolAdapter
        or type(verifier) is not BoundTokenVerifier
        or adapter.principal != verifier.binding.principal
    ):
        raise ValueError("HTTP identity must match the existing Carbon principal")
    binding = verifier.binding
    parsed = urlsplit(binding.resource)
    server = _create_server(
        adapter,
        guard=verifier.check_context,
        token_verifier=verifier,
        auth=AuthSettings(
            issuer_url=binding.issuer,
            resource_server_url=binding.resource,
            required_scopes=[RESEARCH_SCOPE],
            validate_token_resource=True,
        ),
    )
    return server.streamable_http_app(
        streamable_http_path=parsed.path or "/",
        json_response=True,
        stateless_http=False,
        max_request_body_size=65536,
        session_idle_timeout=300,
        max_sessions=16,
        transport_security=TransportSecuritySettings(
            allowed_hosts=[parsed.netloc],
            allowed_origins=[f"{parsed.scheme}://{parsed.netloc}"],
        ),
    )
