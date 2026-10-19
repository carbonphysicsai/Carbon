"""Trusted local composition of one synthetic direct DEVELOPMENT research lane.

This is not a Challenge registration, product campaign adapter, bundle upload
endpoint, or validator evaluation. The caller supplies already verified owner,
ledger, signer-backed gateway, images and private task root. No public tool can
select those values. Only the versioned repository fixture supplies TRAIN.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from carbon import research
from carbon.chain.models import CARBON_NETUID, CARBON_NETWORK
from carbon.miner_mcp.research import AuthenticatedResearchService
from carbon.transport.gateway import AuthenticatedGateway

from .research_service import DirectFixtureDiscovery
from .research_tasks import DirectDevelopmentTasksV3


@dataclass(frozen=True)
class DirectResearchComposition:
    service: research.LocalResearchService
    tasks: DirectDevelopmentTasksV3
    challenge: research.ChallengeKey


def _selected_material(version: str):
    """Select only a repository-registered synthetic DEVELOPMENT kit."""
    from carbon.challenge_kit import synthetic_linear_field_2d as kit

    return {
        "1.1": kit.bundle_material_v3,
        "1.2": kit.bundle_material_v4,
        "1.3": getattr(kit, "bundle_material_v5", None),
    }.get(version)


class DirectDevelopmentConnection:
    """One exact synthetic DEVELOPMENT gateway using the normal chain auth.

    The legacy `LocalMinerConnection` fixes a different Challenge and creates
    the old science service, so it cannot be reused as a direct gateway. This
    type retains its verifier, snapshot reader and receipt-journal controls.
    """

    def __init__(self, *, root, version, chain_context, publisher, miner_key):
        from carbon.development_session.service import authenticated_research_gateway

        selected = _selected_material(version)
        if (
            selected is None
            or not isinstance(root, Path)
            or not root.is_absolute()
            or root.is_symlink()
            or chain_context.netuid != CARBON_NETUID
            or chain_context.network != CARBON_NETWORK
            or miner_key.ss58_address == publisher
        ):
            raise ValueError("exact direct DEVELOPMENT network connection required")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root.chmod(0o700)
        self.root = root
        self.chain_context = chain_context
        self.publisher = publisher
        self.miner_key = miner_key
        self.challenge = selected()["challenge_key"]
        self.transport, self.observed, gateway = authenticated_research_gateway(
            root, chain_context, publisher, self.challenge
        )
        self.service = SimpleNamespace(gateway=gateway)

    async def check_registration(self):
        from carbon.development_session.service import registered_research_snapshot

        return await registered_research_snapshot(
            self.chain_context, self.miner_key, self.publisher, self.observed
        )

    async def check_cleanup_registration(self):
        return await self.check_registration()


def compose_synthetic_direct_development(
    *,
    version: str,
    root: Path,
    owner: str,
    ledger,
    image=None,
    inference_image,
    gateway: AuthenticatedGateway,
    image_resolver=None,
) -> tuple[DirectResearchComposition, AuthenticatedResearchService]:
    """Compose an exact kit version and one authenticated durable task owner."""
    selected = _selected_material(version)
    if selected is None or type(gateway) is not AuthenticatedGateway:
        raise ValueError("registered direct DEVELOPMENT fixture required")
    material = selected()
    if gateway.challenge != material["challenge_key"]:
        raise ValueError("authenticated direct Challenge differs from fixed TRAIN")
    discovery = DirectFixtureDiscovery(material, task_admission=True)
    tasks = DirectDevelopmentTasksV3(
        root=root,
        requester=owner,
        ledger=ledger,
        owner=owner,
        discovery=discovery,
        image=image,
        inference_image=inference_image,
        image_resolver=image_resolver,
    )
    try:
        service = research.LocalResearchService(
            research.DirectPublicResearchContext(discovery, discovery, tasks)
        )
        composition = DirectResearchComposition(
            service, tasks, material["challenge_key"]
        )
        return composition, AuthenticatedResearchService(gateway, {owner: service})
    except BaseException:
        tasks.close()
        raise
