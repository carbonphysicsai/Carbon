"""Serve an existing Carbon research campaign over standard MCP stdio.

The miner supplies their private runner profile (v2) and names one of their
campaigns. This command attaches to that prepared, frozen campaign; it never
starts the paid agent loop, generates cohorts, or runs final evaluation.

Registration is the only admission gate (C-MLP-02-D11): the campaign was
admitted by the registration its manifest records, and every research call
re-reads that registration from the chain. No grant exists on this path.

The host needs the exact accepted checkout and prepared worker images. Clients
need only the MCP command/connection, not access to that checkout or its
private records.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import json
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from carbon import research
from carbon.chain.models import CARBON_NETUID
from carbon.development_session.private_records import private_json
from carbon.development_session.profile import CHALLENGE, canonical
from carbon.development_session.research_control import CampaignControl
from carbon.development_session.research_ledger import PRODUCT, CampaignLedger
from carbon.development_session.research_material import PublicMaterial
from carbon.development_session.research_service import make_research_service
from carbon.development_session.research_tools import ResearchMinerTools
from carbon.miner_mcp.research import AuthenticatedResearchService
from carbon.miner_mcp.standard import ResearchToolAdapter
from carbon.miner_mcp.standard_server import create_stdio_server


@dataclass(frozen=True)
class OperatorProfile:
    """One attachable campaign and the profile that names it.

    `development_grant` is None for every campaign this door loads: a miner's
    campaign is admitted by registration (C-MLP-02-D11). It is set only by a
    development loader outside this package - Carbon's internal Workbench
    service on Carbon's own granted campaign - which this module neither
    imports nor calls; `load_profile` below can never produce one.
    """

    path: Path
    document: dict
    campaign: str
    root: Path
    manifest: dict
    cleanup_only: bool = False
    development_grant: object = None

    @property
    def registered_hotkey(self) -> str:
        if self.development_grant is not None:
            return self.development_grant.document["miner_identity"]
        return self.manifest["admission"]["hotkey"]


def load_profile(path: Path, campaign: str, *, cleanup_only=False) -> OperatorProfile:
    """Read the miner's profile and one of their campaigns; create nothing."""
    from scripts.dev.miner_launchpad.runner import validated_profile

    cfg = validated_profile(private_json(path))
    if cfg["enabled"] is not True and not cleanup_only:
        raise ValueError("closed enabled operator profile required")
    if (
        type(campaign) is not str
        or len(campaign) != 32
        or any(c not in "0123456789abcdef" for c in campaign)
    ):
        raise ValueError("a campaign id from this profile's campaigns is required")
    root = Path(cfg["campaigns_root"]) / campaign
    if (
        not root.is_dir()
        or (not cleanup_only and (root / "campaign-complete.json").exists())
        or not (root / "campaign.sqlite3").is_file()
        or (root / "campaign.sqlite3").is_symlink()
    ):
        raise ValueError("existing unfinished campaign required")
    manifest = private_json(root / "campaign-manifest.json")
    if (
        manifest.get("schema") != PRODUCT
        or manifest.get("principal") != cfg["principal"]
        or manifest.get("campaign_id") != "cmp-" + campaign
        or manifest.get("implementation", {}).get("revision")
        != cfg["accepted_revision"]
    ):
        raise ValueError("the campaign differs from this profile")
    if cleanup_only:
        meter = CampaignLedger(root)
        meter.generation = CampaignControl(meter).status()["generation"]
        if meter.retained_owner(manifest["owner"]) != manifest:
            raise ValueError("retained cleanup profile differs")
    return OperatorProfile(path, cfg, campaign, root, manifest, cleanup_only)


def _prepared_tasks(root, *, cleanup_only=False):
    path = root / "research-tasks" / "research-tasks.sqlite3"
    if not path.is_file() or path.is_symlink():
        raise ValueError("existing prepared research tasks required")
    with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as db:
        for (encoded,) in db.execute("SELECT view FROM tasks"):
            task = research.load_canonical(encoded, research.ResearchTaskView)
            if not cleanup_only and task.state in {
                research.ResearchTaskState.RUNNING,
                research.ResearchTaskState.CANCEL_REQUESTED,
            }:
                raise ValueError(
                    "uncertain task requires existing controller reconciliation"
                )


def _runtime(profile):
    """Reuse the accepted session's host/image/key and public science services."""
    from carbon.chain.auth import open_external_hotkey
    from carbon.development_session.research_campaign import (
        accepted_implementation,
        private_file,
        verify_current_worker,
    )
    from carbon.development_session.research_image import (
        load_analysis_image,
        verify_image,
    )
    from carbon.development_session.research_profile import document, public_cases
    from carbon.development_session.service import LocalMinerConnection
    from carbon.development_testnet.operator import load_config
    from carbon.reconstruction.worker.docker_runtime import doctor, load_image_identity

    cfg = profile.document
    paths = {name: Path(value) for name, value in cfg["paths"].items()}
    implementation = accepted_implementation(cfg["accepted_revision"])
    image = load_image_identity(paths["image_manifest"])
    verify_current_worker(image, implementation)
    if (
        not profile.cleanup_only
        and not doctor(image_id=image.image_id, image_identity=image).eligible
    ):
        raise ValueError("accepted numerical host unavailable")
    analysis = load_analysis_image(paths["analysis_image_manifest"])
    verify_image(analysis)
    if analysis.parent_image != image.image_id:
        raise ValueError("analysis image parent differs")
    runtime = {
        "implementation": implementation,
        "images": [image.image_id, analysis.image_id],
    }
    role_root = profile.root / "private-roles"
    authored = _authored_image(profile, analysis)
    _, scientific = _scientific_selection(
        profile.manifest["runtime"], image, role_root, authored
    )
    if scientific is not None:
        runtime["scientific_tasks"] = scientific
    if authored is not None:
        from carbon.development_session.julia_analysis import authored_julia_scope

        runtime["authored_research"] = [authored_julia_scope(authored)]
    gpu = _gpu_image(profile.root, profile.manifest["runtime"], role_root)
    if gpu is not None:
        from carbon.development_session.gpu_research import gpu_scope

        runtime["gpu_research"] = [gpu_scope(gpu, role_root)]
    # The runtime the campaign was admitted with, exactly - as it once had to
    # equal a grant's.
    if runtime != profile.manifest["runtime"]:
        raise ValueError("campaign runtime differs from the accepted runtime")
    if (
        profile.manifest.get("implementation") != implementation
        or profile.manifest.get("images") != runtime["images"]
        or profile.manifest.get("objective") != document()
    ):
        raise ValueError("campaign runtime or objective changed")
    if private_json(role_root / "research-profile.json") != document():
        raise ValueError("prepared public material profile changed")
    for role in ("research-train", "research-validation"):
        public_cases(role_root, role)  # Checks existing digests; never draws new cases.
    config = load_config(paths["operator_config"])
    public = json.loads(private_file(paths["miner_public"]).read_bytes())
    if (
        public["netuid"] != CARBON_NETUID
        or config.netuid != CARBON_NETUID
        or public["hotkey"] != profile.registered_hotkey
    ):
        raise ValueError("existing miner differs from the registered miner")
    key = open_external_hotkey(
        Path(public["key_file"]),
        private_file(paths["miner_password_file"]),
        public["hotkey"],
    )
    session = profile.root / "research-auth"
    if not session.is_dir() or session.is_symlink():
        raise ValueError("prepared authenticated session required")
    connection = LocalMinerConnection(
        session, paths["image_manifest"], config.context, config.publisher_hotkey, key
    )
    return connection, image, analysis, role_root


def _authored_image(profile, analysis):
    if "authored_research" not in profile.manifest["runtime"]:
        return None
    from carbon.development_session.research_campaign import registered_julia_image

    return registered_julia_image(profile.root, profile.manifest["runtime"], analysis)


def _gpu_image(root, runtime, role_root):
    """One resolver, shared with the campaign runner that now also composes this."""
    from carbon.development_session.gpu_research import registered_gpu_image

    return registered_gpu_image(root, runtime, role_root)


async def _requester(connection):
    """Use the existing signed gateway with a fresh bootstrap transmission ID."""
    from carbon.chain.auth import BittensorMessageSigner
    from carbon.transport.models import message

    snapshot = await connection.check_registration()
    call = research.ServiceCall(
        research.RESEARCH_NAMESPACE,
        "get_challenge_info",
        research.GetChallengeInfoRequest(CHALLENGE),
    )
    body = message(
        connection.chain_context,
        snapshot.snapshot_id,
        CHALLENGE,
        session="carbon-autoresearch",
        request="mcp-bootstrap-" + uuid.uuid4().hex,
        tool=research.RESEARCH_NAMESPACE,
        fields={
            "call_base64": base64.b64encode(research.canonical_bytes(call)).decode(
                "ascii"
            )
        },
    )
    headers = BittensorMessageSigner(connection.miner_key).sign(
        body, receiver=connection.publisher, nonce_ns=time.time_ns()
    )
    return (await connection.service.gateway.receive(body, headers)).requester.value


class _AdmittedConnection:
    def __init__(self, connection, profile, ledger, control):
        self.connection, self.profile, self.ledger, self.control = (
            connection,
            profile,
            ledger,
            control,
        )
        self.chain_context, self.publisher, self.miner_key = (
            connection.chain_context,
            connection.publisher,
            connection.miner_key,
        )
        self.closed = False

    async def check_cleanup_registration(self):
        if self.closed or private_json(self.profile.path) != self.profile.document:
            raise ValueError("operator profile changed or controller closed")
        retained = self.ledger.retained_owner(self.profile.manifest["owner"])
        if retained != self.profile.manifest:
            raise ValueError("retained campaign differs from connection")
        return await self.connection.check_registration()

    async def check_registration(self):
        profile = self.profile
        if profile.cleanup_only:
            raise ValueError("cleanup-only attachment cannot admit research")
        if self.closed or private_json(profile.path) != profile.document:
            raise ValueError("operator profile changed or controller closed")
        now = self.ledger.clock()
        self.ledger.authority(profile.manifest)
        with self.ledger.db() as db:
            started = db.execute("SELECT started FROM campaign WHERE id=1").fetchone()[
                0
            ]
        # The miner's own elapsed budget, if they set one; none is no deadline.
        elapsed = profile.manifest.get("elapsed_seconds")
        if started is not None and (
            now < started or (elapsed is not None and now >= started + elapsed)
        ):
            raise ValueError("campaign elapsed budget reached")
        status = self.control.status()
        if (
            status["generation"] != self.ledger.generation
            or status["desired"] != "RUN"
            or status["state"] in {"RECONCILIATION_REQUIRED", "COMPLETED", "STOPPED"}
        ):
            raise ValueError("campaign admission stopped")
        return await self.connection.check_registration()


def _scientific_selection(runtime, image, role_root, authored=None):
    """Recompute one closed registered combination; no schema label grants access."""
    if "scientific_tasks" not in runtime:
        return "legacy", None
    scopes = runtime["scientific_tasks"]
    if (
        type(scopes) is not list
        or not scopes
        or any(type(s) is not dict for s in scopes)
    ):
        raise ValueError("closed registered scientific scopes required")
    from carbon.development_session.advection_research import advection_scope
    from carbon.development_session.julia_analysis import authored_julia_scope
    from carbon.development_session.julia_envelope import julia_envelope_scope
    from carbon.development_session.julia_research import julia_burgers_scope
    from carbon.development_session.research_sequences import SCOPE as ENVELOPE_SCOPE

    schemas = [s.get("schema") for s in scopes]
    if schemas == ["carbon.public-advection-study.scope.v1"]:
        expected_authored = [authored_julia_scope(authored)]
        if (
            canonical(runtime.get("authored_research")) != canonical(expected_authored)
            or authored.parent.parent_image != image.image_id
        ):
            raise ValueError("separately bound advection analysis image required")
        kind, expected = "advection", [advection_scope(authored)]
    elif schemas == ["carbon.public-julia-study.scope.v1"]:
        kind, expected = "burgers", [julia_burgers_scope(image, role_root)]
    elif schemas == ["carbon.public-julia-study.scope.v1", ENVELOPE_SCOPE]:
        kind, expected = "envelope", [
            julia_burgers_scope(image, role_root),
            julia_envelope_scope(image, role_root),
        ]
    else:
        raise ValueError("unsupported scientific scope combination")
    if canonical(scopes) != canonical(expected):
        raise ValueError("registered scientific scope differs")
    return kind, expected


def _science(ledger, owner, image, role_root, *, cleanup_only=False, authored=None):
    from carbon.development_session.research_data import PublicReferenceData
    from carbon.development_session.research_provider import PublicPractice

    # The runtime the campaign was frozen with - never a grant's, which no
    # product campaign has.
    with ledger.db() as db:
        row = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
    runtime = json.loads(row[0]).get("runtime", {}) if row else {}
    kind, scopes = _scientific_selection(runtime, image, role_root, authored)
    data = PublicReferenceData(
        ledger=ledger, owner=owner, image=image, role_root=role_root
    )
    material = PublicMaterial(data)
    if kind in {"burgers", "envelope"}:
        from carbon.development_session.julia_research import (
            JuliaPublicMaterial,
            PublicJuliaStudy,
        )

        material = JuliaPublicMaterial(
            material,
            PublicJuliaStudy(
                data,
                cleanup=cleanup_only,
                envelope_scope=scopes[1] if kind == "envelope" else None,
            ),
        )
        if kind == "envelope":
            from carbon.development_session.julia_envelope import JuliaEnvelopeMaterial

            material = JuliaEnvelopeMaterial(material, cleanup=cleanup_only)
    elif kind == "advection":
        from carbon.development_session.advection_research import (
            PublicAdvectionMaterial,
        )

        material = PublicAdvectionMaterial(
            material, ledger=ledger, owner=owner, image=authored, cleanup=cleanup_only
        )
    gpu = _gpu_image(ledger.root, runtime, role_root)
    if gpu is not None:
        from carbon.development_session.gpu_research import PublicGPUPractice

        return material, PublicGPUPractice(
            data=data, image=gpu, cleanup_only=cleanup_only
        )
    return material, PublicPractice(data=data, ledger=ledger, owner=owner, image=image)


@contextlib.asynccontextmanager
async def attached(configuration: Path, campaign: str, *, cleanup_only=False):
    """Attach to one of the miner's own campaigns, named by its id.

    Yields ``(adapter, profile)``; see `attached_profile`.
    """
    profile = load_profile(configuration, campaign, cleanup_only=cleanup_only)
    async with attached_profile(profile) as attachment:
        yield attachment


@contextlib.asynccontextmanager
async def attached_profile(profile: OperatorProfile):
    """Hold the existing campaign ownership lock for the whole attachment.

    Yields ``(adapter, profile)``. The caller chooses the surface it is served
    through; this owns the lock, generation, reconciliation and cleanup, so no
    second consumer reimplements campaign ownership.
    """
    from scripts.dev.miner_launchpad.controller import owner_lock
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    if type(profile) is not OperatorProfile:
        raise TypeError("a loaded operator profile is required")
    cleanup_only = profile.cleanup_only
    with owner_lock(profile.root):
        # Registration first: the campaign's frozen record, its control
        # generation and its prepared tasks are not touched until the
        # authenticated owner is known to be the registered one. The
        # connection's session files already exist from launch.
        connection, image, analysis, role_root = _runtime(profile)
        owner = await _requester(connection)
        if owner != profile.manifest.get("owner"):
            raise ValueError("authenticated campaign owner changed")
        ledger = CampaignLedger(profile.root, admission=profile.development_grant)
        if not cleanup_only:
            ledger.freeze(profile.manifest)  # Must match the existing immutable record.
        with ledger.db() as db:
            if (
                not cleanup_only
                and db.execute(
                    "SELECT 1 FROM operations WHERE state='RESERVED' LIMIT 1"
                ).fetchone()
            ):
                raise ValueError("unresolved consumption requires reconciliation")
        _prepared_tasks(profile.root, cleanup_only=cleanup_only)
        control = CampaignControl(ledger)
        status = control.status()
        if not cleanup_only and (
            status["desired"] != "RUN"
            or status["state"]
            in {
                "RECONCILIATION_REQUIRED",
                "STOPPED",
                "COMPLETED",
            }
        ):
            raise ValueError("campaign is not available for research")
        ledger.generation = status["generation"] if cleanup_only else control.acquire()
        if cleanup_only:
            ledger.retained_owner(profile.manifest["owner"])
        authored = _authored_image(profile, analysis)
        material, practice = _science(
            ledger,
            owner,
            image,
            role_root,
            **({"authored": authored} if authored is not None else {}),
            **({"cleanup_only": True} if cleanup_only else {}),
        )
        composition = make_research_service(
            cleanup_only=cleanup_only,
            julia_image=authored,
            root=profile.root / "research-tasks",
            ledger=ledger,
            owner=owner,
            image=analysis,
            public_material=material,
            practice=practice,
        )
        bound = None
        try:
            bound = _AdmittedConnection(connection, profile, ledger, control)
            sdk = ResearchMinerTools(
                connection=bound,
                wrapper=AuthenticatedResearchService(
                    connection.service.gateway, {owner: composition.service}
                ),
                composition=composition,
                ledger=ledger,
                owner=owner,
            )
            adapter = ResearchToolAdapter(sdk, principal=owner)
            try:
                yield adapter, profile
            finally:
                await adapter.shutdown_tasks()
        finally:
            try:
                if bound is not None:
                    bound.closed = True
                    # A cancelled transport await does not cancel to_thread workers.
                    # Retain ownership until their existing deadline supervisors end.
                    clean = False
                    try:
                        await asyncio.get_running_loop().shutdown_default_executor()
                        clean = RunnerAdapter._cleanup(ledger)
                    finally:
                        if not cleanup_only or status["state"] not in {
                            "STOPPED",
                            "COMPLETED",
                        }:
                            control.settled(ledger.generation, cleanup_verified=clean)
                        elif not clean:
                            raise ValueError(
                                "terminal campaign cleanup requires reconciliation"
                            )
            finally:
                composition.tasks.close()


async def serve(configuration: Path, campaign: str, *, cleanup_only=False):
    """Hold the existing campaign ownership lock for the whole stdio lifetime."""
    async with attached(configuration, campaign, cleanup_only=cleanup_only) as (
        adapter,
        _,
    ):
        await create_stdio_server(adapter).run_async()


async def serve_operations(configuration: Path):
    """A miner's own client with their runner profile: the whole journey.

    Onboarding (the open tier, reading Carbon's testnet), every operation in
    the shared table - launch with or without an agent, observe, practice,
    freeze, submit, halt, resume - and attach/detach for deeper research. The
    operation tools are generated from the same table as the browser's routes,
    through the same campaign host over the same records. Nothing on this path
    is issued by Carbon.
    """
    from carbon.miner_mcp.mcp_operations import (
        Attachment,
        make_attachment_tools,
        make_operation_tools,
    )
    from carbon.miner_mcp.open_tier import create_open_tier_server
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    host = RunnerAdapter.for_profile(configuration)
    server = create_open_tier_server()
    attachment = Attachment(server, configuration)
    tools = server._tool_manager._tools
    for tool in [*make_operation_tools(host), *make_attachment_tools(attachment)]:
        tools[tool.name] = tool
    try:
        # A raw MCPServer: stdio is `run_stdio_async`. (The `run_async` of
        # `create_stdio_server` belongs to its wrapper, not to this class.)
        await server.run_stdio_async()
    finally:
        await attachment.detach()
        host.close()


async def serve_open_tier():
    """Serve the open tier alone: no profile, no grant, no campaign, no lock.

    Deliberately not a degraded version of `serve`. It takes no ownership lock
    because it owns nothing, and it reconciles nothing because it consumes
    nothing - which is the same statement as the tier rule that nothing here
    creates a campaign, consumes compute or touches the ledger.

    Onboarding reads Carbon's own testnet by default - the same context the
    browser door uses (`chain_onboarding.carbon_testnet_context`) - so `status`
    and `confirm` answer from public chain state on either door.
    """
    from carbon.miner_mcp.open_tier import create_open_tier_server

    # A raw MCPServer, whose stdio entry point is `run_stdio_async`. This read
    # `run_async` - the wrapper method of `create_stdio_server` - so the bare
    # open tier failed as soon as a client connected; its test replaced this
    # function and so never ran it.
    await create_open_tier_server().run_stdio_async()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--configuration",
        type=Path,
        help=(
            "Your private runner profile. With it and no --campaign: onboarding "
            "and every miner operation, including launch. Omit it to serve the "
            "open tier alone: registration onboarding and the published "
            "validator exam environment."
        ),
    )
    parser.add_argument(
        "--campaign",
        help="Which of your campaigns to attach to (its id under campaigns_root).",
    )
    parser.add_argument(
        "--cleanup-only",
        action="store_true",
        help="Observe/cancel retained owned tasks; cannot start research",
    )
    args = parser.parse_args(argv)
    if args.configuration is None and (args.cleanup_only or args.campaign):
        parser.error("--campaign and --cleanup-only need your runner profile")
    if args.cleanup_only and not args.campaign:
        parser.error("--cleanup-only needs the --campaign to clean up")
    try:
        if args.configuration is None:
            asyncio.run(serve_open_tier())
        elif not args.campaign:
            # With a profile and no campaign: every operation, including
            # launching one. A miner's own client needs nothing Carbon issues.
            asyncio.run(serve_operations(args.configuration))
        else:
            asyncio.run(
                serve(args.configuration, args.campaign, cleanup_only=args.cleanup_only)
            )
    except (Exception, KeyboardInterrupt):  # noqa: BLE001
        # The open tier has no profile, grant or campaign to verify, so it must
        # not be told to go and check them.
        print(
            (
                "Carbon MCP unavailable: verify your runner profile, the campaign named, your subnet registration, the accepted runtime and reconciliation state."
                if args.configuration is not None
                else "Carbon MCP unavailable."
            ),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
