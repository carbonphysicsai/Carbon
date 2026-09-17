"""Authenticated tunnel to the unchanged twelve-operation research protocol.

The trusted composition installs one service per authenticated requester. This
adds no public listener and never sends research results through A7 submission.
"""

from __future__ import annotations

from carbon.research.canonical import canonical_bytes, load_canonical
from carbon.research.model import RESEARCH_NAMESPACE, ServiceCall
from carbon.research.service import LocalResearchService
from carbon.transport.gateway import AuthenticatedGateway


class AuthenticatedResearchService:
    def __init__(self, gateway, services):
        if type(gateway) is not AuthenticatedGateway or type(services) is not dict:
            raise TypeError("trusted authenticated composition required")
        if any(
            type(k) is not str or type(v) is not LocalResearchService
            for k, v in services.items()
        ):
            raise TypeError("exact requester-bound research services required")
        if len({id(v) for v in services.values()}) != len(services):
            raise ValueError("research service cannot be shared between requesters")
        self.gateway = gateway
        self._services = dict(services)

    async def call(self, body, headers):
        received = await self.gateway.receive(body, headers)
        call = received.call
        if (
            call.tool != RESEARCH_NAMESPACE
            or len(call.fields) != 1
            or call.fields[0].name != "call"
        ):
            raise ValueError("research namespace and exact canonical call required")
        payload = call.fields[0].value
        if type(payload) is not str or len(payload.encode()) > 1024**2:
            raise ValueError("bounded canonical research call required")
        decoded = load_canonical(payload.encode(), ServiceCall)
        if decoded.namespace != RESEARCH_NAMESPACE:
            raise ValueError("research namespace mismatch")
        service = self._services.get(received.requester.value)
        if service is None:
            raise ValueError("research requester unavailable")
        if decoded.request.challenge_key != self.gateway.challenge:
            raise ValueError("research challenge differs from authenticated context")
        # B-07G owns exact types, operations, bounds and disclosure. Never echo
        # the transport receipt, private provider or requester binding to agent.
        return canonical_bytes(service.call(decoded))
